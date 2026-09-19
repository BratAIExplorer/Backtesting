"""Signal construction — PEAD events, point-in-time quintiles, calendar-time
portfolios, and the news panel features.

No-lookahead rule, enforced in one place (`build_events`): the entry is the
close of the **first trading day strictly after** the earnings announcement
date. Yahoo's announcement timestamps can be pre-open or post-close, so
"strictly after" is the only choice that can never peek. The forward return is
then measured from that entry close, market-adjusted against the index over the
identical window.

Quintiles are assigned with an *expanding* window over prior events only, so a
stock's rank never uses future information.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _index_on(prices_index: pd.DatetimeIndex, index_close: pd.Series) -> pd.Series:
    return index_close.reindex(prices_index).ffill()


def build_events(ticker: str, earnings: pd.DataFrame, prices: pd.DataFrame,
                 index_close: pd.Series, horizons=(1, 5, 20, 60)) -> pd.DataFrame:
    """One row per earnings event with abnormal forward returns.

    Columns: ticker, ann_date, entry_date, entry_pos, sue, surprise_pct,
             abn_{h}, ret_{h}, mkt_{h} for each horizon.
    """
    if earnings is None or earnings.empty or prices is None or prices.empty:
        return pd.DataFrame()
    idx = prices.index
    px = prices["Close"].to_numpy(dtype=float)
    idx_al = _index_on(idx, index_close).to_numpy(dtype=float)
    rows = []
    for ann_date, ev in earnings.iterrows():
        # first trading day strictly after the announcement
        pos = int(np.searchsorted(idx.values, np.datetime64(ann_date), side="right"))
        if pos >= len(idx) - 1:
            continue
        entry_px, entry_mkt = px[pos], idx_al[pos]
        if not (np.isfinite(entry_px) and entry_px > 0 and np.isfinite(entry_mkt)):
            continue
        row = {"ticker": ticker, "ann_date": ann_date, "entry_date": idx[pos],
               "entry_pos": pos, "sue": ev.get("sue", np.nan),
               "surprise_pct": ev.get("surprise_pct", np.nan)}
        for h in horizons:
            j = pos + h
            if j >= len(idx):
                continue
            r = px[j] / entry_px - 1.0
            m = idx_al[j] / entry_mkt - 1.0
            row[f"ret_{h}"] = r
            row[f"mkt_{h}"] = m
            row[f"abn_{h}"] = r - m
        rows.append(row)
    return pd.DataFrame(rows)


def assign_quintiles(events: pd.DataFrame, min_prior: int = 20) -> pd.DataFrame:
    """Point-in-time SUE rank: each event's rank uses only *earlier* events."""
    if events.empty:
        return events
    e = events.sort_values("ann_date").reset_index(drop=True).copy()
    e["q"] = np.nan
    for i in range(len(e)):
        prior = e["sue"].iloc[:i].dropna()
        if prior.size >= min_prior:
            e.loc[i, "q"] = float((prior < e.loc[i, "sue"]).mean())
    return e


def pead_weights(events: pd.DataFrame, prices: dict[str, pd.DataFrame],
                 all_dates: pd.DatetimeIndex, top_frac: float, horizon: int,
                 side: str = "top") -> pd.DataFrame:
    """Equal-weight daily membership matrix (dates x tickers) for a PEAD sleeve.

    `side='top'` holds events in the top `top_frac` of the point-in-time SUE
    rank; `side='bottom'` the bottom. Each event is held for `horizon` trading
    days from its entry close.
    """
    w = pd.DataFrame(0.0, index=all_dates, columns=sorted(prices.keys()))
    if events.empty:
        return w
    ev = events.dropna(subset=["q"])
    if side == "top":
        ev = ev[ev["q"] >= 1.0 - top_frac]
    else:
        ev = ev[ev["q"] <= top_frac]
    if ev.empty:
        return w
    for _, r in ev.iterrows():
        t = r["ticker"]
        if t not in w.columns:
            continue
        pidx = prices[t].index
        pos = int(r["entry_pos"])
        lo = pos
        hi = min(len(pidx), pos + horizon)
        if lo >= len(pidx):
            continue
        days = pidx[lo:hi]
        w.loc[w.index.isin(days), t] = 1.0
    # equal-weight within each day
    denom = w.sum(axis=1).replace(0.0, np.nan)
    return w.div(denom, axis=0).fillna(0.0)


def run_weights(w: pd.DataFrame, ret: pd.DataFrame, cost_bps: float):
    """Portfolio daily net returns. weights[d] held from close d -> close d+1.

    Mirrors strategies/factor_backtest.py's `_run` cost convention: turnover is
    the summed absolute weight change, charged at `cost_bps` (one-way).
    """
    w = w.reindex(index=ret.index, columns=ret.columns).fillna(0.0)
    held = w.shift(1).fillna(0.0)
    gross = (held * ret).sum(axis=1)
    turnover = w.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * cost_bps / 10_000.0
    return gross - cost


def forward_abnormal_returns(prices: pd.DataFrame, index_close: pd.Series,
                             event_dates, horizons=(1, 5, 20)) -> pd.DataFrame:
    """Generic event -> forward abnormal return, entry strictly after `event_date`.

    Same no-lookahead rule as `build_events`, for any dated event series (news,
    filings, etc.). Returns one row per event date with abn_{h}/ret_{h}/mkt_{h}.
    """
    idx = prices.index
    px = prices["Close"].to_numpy(dtype=float)
    idx_al = _index_on(idx, index_close).to_numpy(dtype=float)
    rows = []
    for d in event_dates:
        pos = int(np.searchsorted(idx.values, np.datetime64(d), side="right"))
        if pos >= len(idx) - 1:
            continue
        e_px, e_mkt = px[pos], idx_al[pos]
        if not (np.isfinite(e_px) and e_px > 0 and np.isfinite(e_mkt)):
            continue
        row = {"event_date": d, "entry_date": idx[pos], "entry_pos": pos}
        for h in horizons:
            j = pos + h
            if j >= len(idx):
                continue
            r, m = px[j] / e_px - 1.0, idx_al[j] / e_mkt - 1.0
            row[f"ret_{h}"], row[f"mkt_{h}"], row[f"abn_{h}"] = r, m, r - m
        rows.append(row)
    return pd.DataFrame(rows)


def news_features(news: pd.DataFrame) -> pd.DataFrame:
    """Turn the raw GDELT panel into point-in-time features per (date, symbol).

    - `vol_z`   : attention spike vs trailing 20-day mean/std
    - `tone_z`  : tone vs its own trailing 20-day mean/std
    - `tone`    : raw daily tone
    All trailing stats are shifted by 1 day (no same-day leakage).
    """
    if news.empty:
        return news
    out = []
    for sym, g in news.groupby("symbol"):
        g = g.sort_values("date").set_index("date")
        vol = g["vol"].astype(float)
        tone = g["tone"].astype(float)
        v_mean = vol.shift(1).rolling(20, min_periods=10).mean()
        v_std = vol.shift(1).rolling(20, min_periods=10).std()
        t_mean = tone.shift(1).rolling(20, min_periods=10).mean()
        t_std = tone.shift(1).rolling(20, min_periods=10).std()
        f = pd.DataFrame({
            "symbol": sym, "vol": vol, "tone": tone,
            "vol_z": (vol - v_mean) / v_std.replace(0.0, np.nan),
            "tone_z": (tone - t_mean) / t_std.replace(0.0, np.nan),
        }).reset_index()
        out.append(f)
    return pd.concat(out, ignore_index=True)


if __name__ == "__main__":
    from harness.data import load_daily, load_earnings, load_index

    px = load_daily("RELIANCE.NS", period="5y")
    ed = load_earnings("RELIANCE.NS")
    ix = load_index("NIFTYBEES.NS", period="5y")
    ev = build_events("RELIANCE.NS", ed, px, ix)
    assert not ev.empty, "no events built"
    # no-lookahead: every entry must be strictly after its announcement
    assert (ev["entry_date"] > ev["ann_date"]).all(), "lookahead!"
    q = assign_quintiles(ev, min_prior=8)
    assert q["q"].notna().any(), "quintiles not assigned"
    print(f"signals self-check ok: {len(ev)} events, "
          f"{int(q['q'].notna().sum())} ranked, horizons present "
          f"{[c for c in ev.columns if c.startswith('abn_')]}")

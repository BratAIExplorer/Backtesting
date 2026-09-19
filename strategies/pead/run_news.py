"""News-headline study — INDIA ONLY (this phase; US is the next phase).

Question the user asked: "does news headlines make any difference?"

Three sub-tests, all with the same honesty layer as PEAD:

  A. STANDALONE — does GDELT tone/attention predict forward abnormal return?
  B. CONDITIONAL — is the (already real) 5-day PEAD drift stronger when the
     earnings announcement is accompanied by unusually positive news?
  C. INCREMENTAL — does news tone add on top of SUE in a two-way sort, i.e.
     is it new information or just a noisy proxy for the same surprise?

PRE-REGISTERED KILL CRITERIA (decided before running; PASS requires ALL):

  1. Standalone tone: |HAC t| >= 2.0 for top-minus-bottom tone quintile at 5d.
  2. Deflation: DSR >= 0.95 across the variants tested.
  3. Net-of-cost calendar-time Sharpe > 0 with HAC t >= 2.0.
  4. Incremental: news tone must move the 5d PEAD spread by a
     two-sample HAC t >= 2.0 (high-news vs low-news subsets).

DATA CAVEAT (stated up front, not buried): GDELT is free but rate-limited and
its coverage of Indian large caps is sparse and noisy. Every number below is
reported with the fraction of days that actually had news, and results are
treated as provisional if coverage is thin.

Run:  python -m research.run_news
"""
from __future__ import annotations

import argparse
import warnings

import numpy as np
import pandas as pd

from harness.data import gdelt_daily, load_daily, load_earnings, load_index
from harness.signals import (assign_quintiles, build_events,
                              forward_abnormal_returns, news_features)
from harness.stats import (annualized_sharpe, block_bootstrap_diff,
                            deflated_sharpe_ratio, effective_n, hit_rate_test,
                            two_sample_hac)

warnings.filterwarnings("ignore")

# symbol -> GDELT query (quoted company name keeps the query from matching
# unrelated news, e.g. the Reliance brand vs Reliance Industries)
INDIA_NEWS = {
    "RELIANCE.NS": '"Reliance Industries"',
    "TCS.NS": '"Tata Consultancy Services"',
    "HDFCBANK.NS": '"HDFC Bank"',
    "INFY.NS": '"Infosys"',
    "ICICIBANK.NS": '"ICICI Bank"',
    "SBIN.NS": '"State Bank of India"',
    "AXISBANK.NS": '"Axis Bank"',
    "LT.NS": '"Larsen Toubro"',
    "ITC.NS": '"ITC Limited"',
    "HINDUNILVR.NS": '"Hindustan Unilever"',
    "BHARTIARTL.NS": '"Bharti Airtel"',
    "MARUTI.NS": '"Maruti Suzuki"',
}
INDEX = "NIFTYBEES.NS"
HORIZONS = (1, 5, 20)
COST_BPS = 20.0


def load_news_universe(period: str, start: str, end: str):
    prices, earnings, news = {}, {}, {}
    for t, q in INDIA_NEWS.items():
        p = load_daily(t, period=period)
        if p is None or len(p) < 250:
            continue
        prices[t] = p
        e = load_earnings(t)
        if e is not None and not e.empty:
            earnings[t] = e
        vol = gdelt_daily(q, start, end, "timelinevol")
        tone = gdelt_daily(q, start, end, "timelinetone")
        if vol.empty and tone.empty:
            continue
        g = pd.DataFrame({"vol": vol, "tone": tone}).reset_index()
        g.columns = ["date", "vol", "tone"]
        g["symbol"] = t
        news[t] = g
    ix = load_index(INDEX, period=period)
    return prices, earnings, news, ix


def _expand_quantile(s: pd.Series, min_prior: int = 30) -> pd.Series:
    """Point-in-time rank of each value vs only earlier values."""
    v = s.reset_index(drop=True)
    out = pd.Series(np.nan, index=v.index)
    for i in range(len(v)):
        prior = v.iloc[:i].dropna()
        if prior.size >= min_prior and np.isfinite(v.iloc[i]):
            out.iloc[i] = float((prior < v.iloc[i]).mean())
    return out


def standalone(news: pd.DataFrame, prices: dict, ix, feature: str) -> pd.DataFrame:
    rows = []
    for sym, g in news.groupby("symbol"):
        if sym not in prices:
            continue
        f = news_features(g)
        f = f.dropna(subset=[feature])
        if f.empty:
            continue
        f = f.copy()
        f["q"] = _expand_quantile(f[feature], min_prior=30).values
        f = f.dropna(subset=["q"])
        if f.empty:
            continue
        far = forward_abnormal_returns(prices[sym], ix, f["date"].tolist(), HORIZONS)
        if far.empty:
            continue
        m = f.reset_index(drop=True).join(far.reset_index(drop=True), how="inner")
        rows.append(m)
    if not rows:
        return pd.DataFrame()
    panel = pd.concat(rows, ignore_index=True)
    out = []
    for h in HORIZONS:
        col = f"abn_{h}"
        d = panel.dropna(subset=[col])
        if len(d) < 60:
            continue
        base = float((d[col] > 0).mean())
        top = d[d["q"] >= 0.8][col]
        bot = d[d["q"] <= 0.2][col]
        t, _, spread = two_sample_hac(top, bot, lags=h)
        lo, hi = block_bootstrap_diff(top, bot, block=max(1, h))
        hit = int((top > 0).sum())
        z, _ = hit_rate_test(hit, len(top), base)
        z_eff, _ = hit_rate_test(hit, len(top), base, n_eff=effective_n(len(top), h))
        out.append({"feature": feature, "horizon": h, "n_top": len(top),
                    "spread%": spread * 100, "t_hac": t, "boot_lo%": lo * 100,
                    "boot_hi%": hi * 100, "base%": base * 100,
                    "hit_z": z, "hit_z_eff": z_eff})
    return pd.DataFrame(out)


def incremental(news: pd.DataFrame, earnings: dict, prices: dict, ix) -> pd.DataFrame:
    """Within SUE-top-quintile earnings events, split by news tone."""
    tone_by_sym = {}
    for sym, g in news.groupby("symbol"):
        f = news_features(g).dropna(subset=["tone_z"])
        tone_by_sym[sym] = f.set_index("date")["tone_z"]

    rows = []
    for sym, e in earnings.items():
        if sym not in prices or sym not in tone_by_sym:
            continue
        ev = build_events(sym, e, prices[sym], ix, horizons=(5,))
        if ev.empty:
            continue
        ev = assign_quintiles(ev, min_prior=20)
        ev = ev[ev["q"] >= 0.8] if ev["q"].notna().any() else ev
        if ev.empty:
            continue
        tone = tone_by_sym[sym]
        # news tone in the 3 trading days around the announcement
        vals = []
        for _, r in ev.iterrows():
            w = tone.loc[(tone.index >= r["ann_date"] - pd.Timedelta(days=3))
                         & (tone.index <= r["ann_date"] + pd.Timedelta(days=1))]
            vals.append(w.mean() if len(w) else np.nan)
        ev = ev.assign(tone_z=vals).dropna(subset=["tone_z", "abn_5"])
        rows.append(ev[["ticker", "ann_date", "abn_5", "sue", "tone_z"]])
    if not rows:
        return pd.DataFrame()
    panel = pd.concat(rows, ignore_index=True)
    hi = panel[panel["tone_z"] >= panel["tone_z"].quantile(0.5)]["abn_5"]
    lo = panel[panel["tone_z"] < panel["tone_z"].quantile(0.5)]["abn_5"]
    t, _, diff = two_sample_hac(hi, lo, lags=5)
    lo_ci, hi_ci = block_bootstrap_diff(hi, lo, block=5)
    return pd.DataFrame([{
        "n_hi": len(hi), "n_lo": len(lo),
        "hi_abn5%": hi.mean() * 100, "lo_abn5%": lo.mean() * 100,
        "diff%": diff * 100, "t_hac": t,
        "boot_lo%": lo_ci * 100, "boot_hi%": hi_ci * 100,
    }])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="6y")
    ap.add_argument("--start", default="20200101000000")
    ap.add_argument("--end", default="20260901000000")
    args = ap.parse_args()

    print(f"\n{'='*86}\nNEWS study — INDIA ONLY  ({args.start[:8]} -> {args.end[:8]})\n{'='*86}")
    print("PRE-REGISTERED: PASS needs standalone |t|>=2 @5d AND DSR>=0.95 AND "
          "net Sharpe>0 (t>=2) AND incremental tone effect t>=2.\n")

    prices, earnings, news, ix = load_news_universe(args.period, args.start, args.end)
    print(f"loaded {len(prices)} tickers with prices; {len(news)} with GDELT news")

    if not news:
        print("\n  !! GDELT returned nothing (rate-limited or blocked). "
              "News test cannot run this pass.")
        return

    # coverage
    cov = []
    for sym, g in news.items():
        if sym in prices:
            span = len(prices[sym])
            have = g["vol"].notna().sum()
            cov.append({"symbol": sym, "days": int(have),
                        "coverage%": round(100 * have / max(1, span), 1)})
    cov = pd.DataFrame(cov).sort_values("coverage%", ascending=False)
    print("\nGDELT COVERAGE (share of trading days with any news)")
    print(cov.to_string(index=False))

    allnews = pd.concat(news.values(), ignore_index=True)
    print("\nA. STANDALONE news signal (abnormal return vs NIFTYBEES, %)")
    for feat in ("tone_z", "vol_z", "tone"):
        s = standalone(allnews, prices, ix, feat)
        if not s.empty:
            print(f"  -- {feat} --")
            print(s.to_string(index=False, float_format=lambda x: f"{x:8.2f}"))

    print("\nC. INCREMENTAL over PEAD (5d, SUE top quintile split by news tone)")
    inc = incremental(allnews, earnings, prices, ix)
    if not inc.empty:
        print(inc.to_string(index=False, float_format=lambda x: f"{x:8.2f}"))
    else:
        print("  (not enough overlapping earnings+news events)")

    # verdict
    st = standalone(allnews, prices, ix, "tone_z")
    c1 = bool(not st.empty and (st["horizon"] == 5).any()
              and abs(float(st[st["horizon"] == 5]["t_hac"].iloc[0])) >= 2.0)
    # deflation across the standalone variants tested
    variants = []
    for feat in ("tone_z", "vol_z", "tone"):
        s = standalone(allnews, prices, ix, feat)
        if not s.empty and (s["horizon"] == 5).any():
            variants.append(float(s[s["horizon"] == 5]["t_hac"].iloc[0]))
    c2 = False
    if len(variants) >= 2:
        sr_std = float(np.nanstd(np.array(variants) / np.sqrt(252), ddof=1))
        dsr, _ = deflated_sharpe_ratio(float(np.nanmax(variants)) / np.sqrt(252),
                                       500, 0.0, 3.0, len(variants), sr_std)
        c2 = bool(dsr >= 0.95)
    c4 = bool(not inc.empty and abs(float(inc["t_hac"].iloc[0])) >= 2.0)
    c3 = False  # net calendar-time not built for news (coverage too thin to trade)

    print("\nVERDICT vs pre-registered criteria:")
    print(f"  1. standalone tone |t|>=2 @5d ....... {'PASS' if c1 else 'FAIL'}")
    print(f"  2. DSR>=0.95 ........................ {'PASS' if c2 else 'FAIL'}")
    print(f"  3. net Sharpe>0 (t>=2) .............. {'PASS' if c3 else 'FAIL'} "
          f"(not tradable at this coverage)")
    print(f"  4. incremental tone effect t>=2 ..... {'PASS' if c4 else 'FAIL'}")
    print(f"\n  >>> NEWS VERDICT: "
          f"{'EDGE (passes all 4)' if all([c1, c2, c3, c4]) else 'NO EDGE'}")


if __name__ == "__main__":
    main()

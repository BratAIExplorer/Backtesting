"""Cached data layer for the research harness.

Three sources, all free, all cached to disk so re-runs are cheap and offline:

- `load_daily`      Yahoo daily bars, auto_adjust=True (total return), like
                    strategies/factor_backtest.py.
- `load_earnings`   Yahoo earnings dates + EPS estimate/actual/surprise.
                    ~25 quarters of history, India and US.
- `gdelt_daily`     GDELT DOC 2.0 timeline API — the only free source of
                    *historical* news (Google News RSS is current-only, so it
                    cannot be backtested). Returns daily volume and tone.

GDELT is aggressively rate-limited (HTTP 429), so every call is throttled to a
minimum interval, retried with backoff, and cached for a month. Coverage is
thin for small caps — results will be dominated by large caps, and the write-up
says so.
"""
from __future__ import annotations

import os
import time
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

CACHE = os.path.join(os.path.dirname(__file__), ".cache")
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

_GDELT_LAST_CALL = [0.0]
_GDELT_MIN_INTERVAL = 10.0         # seconds between GDELT calls, process-wide


def _path(name: str) -> str:
    os.makedirs(CACHE, exist_ok=True)
    return os.path.join(CACHE, name)


def _fresh(path: str, ttl_days: float) -> bool:
    return os.path.exists(path) and (time.time() - os.path.getmtime(path)) < ttl_days * 86_400


# ---------------------------------------------------------------- daily bars

def load_daily(ticker: str, period: str = "5y", ttl_days: float = 7.0,
               auto_adjust: bool = True) -> pd.DataFrame | None:
    """Daily OHLCV, indexed by tz-naive date. None on any failure."""
    cf = _path(f"d_{ticker}_{period}.pkl")
    if _fresh(cf, ttl_days):
        return pd.read_pickle(cf)
    try:
        import yfinance as yf

        d = yf.download(ticker, period=period, interval="1d",
                        progress=False, auto_adjust=auto_adjust)
        if d is None or d.empty:
            return None
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        d = d[["Open", "High", "Low", "Close", "Volume"]].dropna(how="all")
        d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
        d = d[~d.index.duplicated(keep="last")].sort_index()
        d.to_pickle(cf)
        return d
    except Exception:
        return None


def load_index(symbol: str, period: str = "5y", ttl_days: float = 7.0) -> pd.Series | None:
    d = load_daily(symbol, period=period, ttl_days=ttl_days)
    return None if d is None else d["Close"].rename(symbol)


# ----------------------------------------------------------------- earnings

def load_earnings(ticker: str, ttl_days: float = 7.0) -> pd.DataFrame | None:
    """Earnings events: one row per report, indexed by announcement date (naive).

    Columns: eps_est, eps_actual, surprise_pct, eps_delta, sue.
    Future/unreported rows (NaN actual) are dropped. `sue` is the standardized
    unexpected earnings = eps_delta / trailing std(eps_delta), point-in-time
    (only past surprises used).
    """
    cf = _path(f"e_{ticker}.pkl")
    if _fresh(cf, ttl_days):
        return pd.read_pickle(cf)
    try:
        import yfinance as yf

        ed = yf.Ticker(ticker).get_earnings_dates(limit=60)
        if ed is None or ed.empty:
            return None
        ed = ed.copy()
        ed.index = pd.to_datetime(ed.index).tz_localize(None).normalize()
        ed = ed.rename(columns={"EPS Estimate": "eps_est",
                                "Reported EPS": "eps_actual",
                                "Surprise(%)": "surprise_pct"})
        ed = ed.dropna(subset=["eps_actual"])
        ed["eps_delta"] = ed["eps_actual"] - ed["eps_est"]
        # point-in-time SUE: std of *prior* deltas only (expanding, shifted)
        prior = ed["eps_delta"].shift(1).expanding(min_periods=2)
        sd = prior.std()
        ed["sue"] = np.where(sd > 0, ed["eps_delta"] / sd, np.nan)
        ed = ed.sort_index()
        ed = ed[~ed.index.duplicated(keep="last")]
        ed.to_pickle(cf)
        return ed
    except Exception:
        return None


# --------------------------------------------------------------------- GDELT

def _gdelt_request(query: str, mode: str, start: str, end: str) -> dict:
    url = (f"{GDELT_URL}?query={urllib.parse.quote(query)}&mode={mode}"
           f"&startdatetime={start}&enddatetime={end}&format=json&timelinesmooth=0")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 research"})
    with urllib.request.urlopen(req, timeout=45) as r:
        import json
        return json.loads(r.read().decode("utf-8", "ignore"))


def _throttle() -> None:
    wait = _GDELT_MIN_INTERVAL - (time.time() - _GDELT_LAST_CALL[0])
    if wait > 0:
        time.sleep(wait)
    _GDELT_LAST_CALL[0] = time.time()


def _gdelt_series(query: str, mode: str, start: str, end: str,
                  retries: int = 5) -> pd.Series:
    """One timeline query, throttled + retried. Empty Series on failure."""
    for attempt in range(retries):
        try:
            _throttle()
            d = _gdelt_request(query, mode, start, end)
            tl = d.get("timeline", [])
            data = tl[0].get("data", []) if tl else []
            if not data:
                return pd.Series(dtype=float)
            idx = pd.to_datetime([p["date"] for p in data]).tz_localize(None).normalize()
            return pd.Series([float(p["value"]) for p in data], index=idx)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_time = 15.0 * (2 ** attempt)
                print(f"  [GDELT 429] Rate limited on {query} ({mode}). Waiting {wait_time}s (Attempt {attempt+1}/{retries})")
                time.sleep(wait_time)
            else:
                print(f"  [GDELT HTTP {e.code}] on {query}. Waiting 5s...")
                time.sleep(5.0)
        except Exception as e:
            print(f"  [GDELT Error] {str(e)} on {query}. Waiting 5s...")
            time.sleep(5.0)
    return pd.Series(dtype=float)


def gdelt_daily(query: str, start: str, end: str, mode: str = "timelinevol",
                ttl_days: float = 30.0, retries: int = 5) -> pd.Series:
    """Daily GDELT series for `query` between `start`/`end` (YYYYMMDD000000).

    mode='timelinevol'  -> share of monitored news mentioning the query (0-100)
    mode='timelinetone' -> average article tone (roughly -100..+100, usually -10..+10)

    Tries the full range in one call first (GDELT handles multi-year timeline
    queries); falls back to 3-month chunks only if that returns nothing.
    """
    tag = urllib.parse.quote(query, safe="")
    cf = _path(f"g_{mode}_{tag}_{start[:8]}_{end[:8]}.pkl")
    if _fresh(cf, ttl_days):
        return pd.read_pickle(cf)

    out = _gdelt_series(query, mode, start, end, retries)
    if out.empty:
        parts = []
        for s, e in _chunk_dates(start, end, months=3):
            p = _gdelt_series(query, mode, s, e, retries)
            if not p.empty:
                parts.append(p)
        out = pd.concat(parts).sort_index() if parts else pd.Series(dtype=float)
    out = out[~out.index.duplicated(keep="last")]
    out.to_pickle(cf)
    return out


def _chunk_dates(start: str, end: str, months: int = 3):
    s = pd.to_datetime(start)
    e = pd.to_datetime(end)
    cur = s
    out = []
    while cur < e:
        nxt = min(cur + pd.DateOffset(months=months), e)
        out.append((cur.strftime("%Y%m%d%H%M%S"), nxt.strftime("%Y%m%d%H%M%S")))
        cur = nxt
    return out


def news_panel(tickers: dict[str, str], start: str, end: str,
               ttl_days: float = 30.0) -> pd.DataFrame:
    """Build a per-ticker daily news panel.

    `tickers` maps symbol -> GDELT query (use quoted company names, e.g.
    '"Reliance Industries"'). Returns a long DataFrame:
    [date, symbol, vol, tone].
    """
    frames = []
    for sym, q in tickers.items():
        vol = gdelt_daily(q, start, end, "timelinevol", ttl_days=ttl_days)
        tone = gdelt_daily(q, start, end, "timelinetone", ttl_days=ttl_days)
        if vol.empty and tone.empty:
            continue
        df = pd.DataFrame({"vol": vol, "tone": tone})
        df["symbol"] = sym
        df = df.reset_index().rename(columns={"index": "date"})
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["date", "symbol", "vol", "tone"])
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    d = load_daily("RELIANCE.NS", period="1y")
    assert d is not None and len(d) > 200, "daily bars failed"
    assert {"Open", "High", "Low", "Close", "Volume"} <= set(d.columns)
    e = load_earnings("RELIANCE.NS")
    assert e is not None and len(e) >= 4, "earnings failed"
    assert e.index.is_monotonic_increasing
    assert e["eps_actual"].notna().all()
    print(f"data self-check ok: RELIANCE.NS {len(d)} bars, {len(e)} earnings events")

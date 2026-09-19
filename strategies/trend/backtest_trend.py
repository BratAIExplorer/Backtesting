"""Offline backtest: how accurate is pricing.classify_trend() historically? Also
tests two candidate improvements raised after the first (coin-flip) result —
a 200-day moving average regime filter, and relative momentum vs. Nifty 50 —
using the exact same no-lookahead, direction-only methodology.

Why this exists: the live trend_snapshots table (backend/jobs/trend_snapshot.py)
answers "was this call right?" but only after waiting 1/7/30 real days per
snapshot — weeks before there's enough data to trust. This script answers the
same question in one run using 2 years of Yahoo daily history already on hand,
with the exact same rule table and the exact same direction-only grading logic
already live in grade_pending_snapshots().

Honesty rule (same principle used in TradingBot/strategies/factor_backtest.py):
every day's RSI/MACD/ADX value must only use data up to and including that day
— never a future close. pandas .rolling()/.ewm() are strictly backward-looking
by construction, so computing the full indicator series once over the whole
history and reading off day t's value is equivalent to (but far faster than)
recomputing from scratch at every t — there is no lookahead here.

The RSI/MACD math below intentionally mirrors backend/pricing.py's
compute_rsi/compute_macd_hist (which only return the latest value, not a full
series) rather than refactoring those tested, live functions —
test_backtest_matches_live_pricing_functions in
backend/tests/test_backtest_trend.py cross-checks the two never drift apart.

ADX has no live counterpart in pricing.py — this file is its only
implementation (ported from C:/Antigravity/TradingBot/regime_monitor.py's
_calculate_adx(), same standard Wilder formula). It stays backtest-only
because the backtest below found no accuracy benefit from an ADX filter (see
CURRENT_STATUS.md) — nothing in production needs it yet.

Usage:
    python -m backend.tools.backtest_trend                      # sample NIFTY universe
    python -m backend.tools.backtest_trend RELIANCE TCS HDFCBANK # specific symbols
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

import pandas as pd

from .. import pricing

# A representative slice of liquid, well-covered NSE large/mid caps — not the
# user's actual portfolio (this script runs standalone, no DB dependency), but
# enough to see whether the rule table has any edge at all across sectors.
DEFAULT_UNIVERSE = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
    "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT", "AXISBANK",
    "MARUTI", "TITAN", "SUNPHARMA", "TATAMOTORS",
]

# Sourced from C:/Antigravity/TradingBot/nifty50.py verbatim. 16 stocks is a
# small club (real feedback, real point) — this is the widest liquid,
# well-covered NSE universe already on hand, used to re-check whether the
# momentum result holds at 3x the sample.
NIFTY_50 = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BPCL", "BHARTIARTL",
    "BRITANNIA", "CIPLA", "COALINDIA", "DIVISLAB", "DRREDDY",
    "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE",
    "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC",
    "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LTIM",
    "LT", "M&M", "MARUTI", "NTPC", "NESTLEIND",
    "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SBIN",
    "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL",
    "TECHM", "TITAN", "ULTRACEMCO", "UPL", "WIPRO",
]

WINDOWS = (1, 7, 30)  # trading days

# Sourced from C:/Antigravity/TradingBot/strategies/sector_map.py verbatim —
# reused rather than rebuilt. Needs more members per sector than
# DEFAULT_UNIVERSE has (IT/ENERGY/TELECOM there only have 1-2 names each),
# so the sector-relative momentum test uses this wider map instead.
SECTOR_MAP = {
    "HDFCBANK": "FINANCIALS", "ICICIBANK": "FINANCIALS", "SBIN": "FINANCIALS", "AXISBANK": "FINANCIALS",
    "KOTAKBANK": "FINANCIALS", "INDUSINDBK": "FINANCIALS", "BAJFINANCE": "FINANCIALS", "BAJAJFINSV": "FINANCIALS",
    "HDFCLIFE": "FINANCIALS", "SBILIFE": "FINANCIALS",
    "TCS": "IT", "INFY": "IT", "HCLTECH": "IT", "TECHM": "IT", "WIPRO": "IT", "LTIM": "IT",
    "RELIANCE": "ENERGY", "ONGC": "ENERGY", "BPCL": "ENERGY", "COALINDIA": "ENERGY", "NTPC": "ENERGY", "POWERGRID": "ENERGY",
    "ITC": "FMCG", "HINDUNILVR": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG", "TATACONSUM": "FMCG",
    "MARUTI": "AUTO", "M&M": "AUTO", "TATAMOTORS": "AUTO", "EICHERMOT": "AUTO", "HEROMOTOCO": "AUTO",
    "SUNPHARMA": "PHARMA", "DRREDDY": "PHARMA", "CIPLA": "PHARMA", "DIVISLAB": "PHARMA", "APOLLOHOSP": "PHARMA",
    "TATASTEEL": "METALS", "HINDALCO": "METALS", "JSWSTEEL": "METALS",
    "LT": "INFRA", "ULTRACEMCO": "INFRA", "GRASIM": "INFRA",
    "ASIANPAINT": "CONSUMER", "TITAN": "CONSUMER", "BHARTIARTL": "TELECOM",
}


def rsi_series(closes: pd.Series, period: int = 14) -> pd.Series:
    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.where(loss != 0, 100.0)  # matches compute_rsi: zero losses -> 100


def macd_hist_series(closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line


def adx_series(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    dm_plus = high.diff()
    dm_minus = -low.diff()
    dm_plus[dm_plus < 0] = 0
    dm_minus[dm_minus < 0] = 0
    tr_smooth = tr.rolling(period).mean()
    di_plus = 100 * dm_plus.rolling(period).mean() / tr_smooth
    di_minus = 100 * dm_minus.rolling(period).mean() / tr_smooth
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus)
    return dx.rolling(period).mean()


@dataclass
class BacktestRow:
    symbol: str
    label: str
    direction: str
    adx: float | None


def _grade_future(closes: pd.Series, i: int, n: int, price_t: float, direction: str) -> dict:
    """Shared by every backtest variant below: hit_Nd for each window, or None
    if the window runs past the end of the available data."""
    out = {}
    for w in WINDOWS:
        if i + w >= n:
            out[f"hit_{w}d"] = None
            continue
        price_future = closes.iloc[i + w]
        hit = price_future > price_t if direction == "up" else price_future < price_t
        out[f"hit_{w}d"] = bool(hit)  # native bool, not numpy.bool_ — object-dtype columns of
        # numpy bools silently produce wrong .mean() results under groupby (verified: gives
        # ~0.01 instead of ~0.45 on real data). Native Python bool avoids the landmine.
    return out


def backtest_symbol(df: pd.DataFrame, symbol: str, adx_gate: float | None = None,
                     require_sma200_alignment: bool = False) -> list[dict]:
    """One row per trading day with enough lookback: the label classify_trend()
    would have given that day, plus whether price direction matched it at each
    window.
    adx_gate: if set, only rows with ADX >= this are graded (tested — no help).
    require_sma200_alignment: if True, only grade a Bullish call when price is
    already above its 200-day average (Bearish: below) — the idea being RSI/MACD
    shouldn't be trusted against the stock's own primary trend."""
    closes = df["Close"]
    rsi = rsi_series(closes)
    macd = macd_hist_series(closes)
    adx = adx_series(df)
    sma200 = closes.rolling(200).mean()

    rows = []
    n = len(df)
    for i in range(35, n):  # 35 = enough bars for RSI+MACD+ADX to be defined
        trend = pricing.classify_trend(
            rsi.iloc[i] if pd.notna(rsi.iloc[i]) else None,
            macd.iloc[i] if pd.notna(macd.iloc[i]) else None,
        )
        if trend["direction"] == "flat":
            continue
        if adx_gate is not None and (pd.isna(adx.iloc[i]) or adx.iloc[i] < adx_gate):
            continue

        price_t = closes.iloc[i]
        if require_sma200_alignment:
            if pd.isna(sma200.iloc[i]):
                continue
            aligned = (trend["direction"] == "up" and price_t > sma200.iloc[i]) or \
                      (trend["direction"] == "down" and price_t < sma200.iloc[i])
            if not aligned:
                continue

        row = {"symbol": symbol, "label": trend["label"], "direction": trend["direction"], "adx": adx.iloc[i]}
        row.update(_grade_future(closes, i, n, price_t, trend["direction"]))
        rows.append(row)
    return rows


def fetch_index_history(symbol: str = "^NSEI", period: str = "2y") -> pd.DataFrame:
    """Nifty 50 index history — not a tradable stock, so pricing.py's
    NSE/.NS-suffix logic doesn't apply; fetched directly via yfinance."""
    import yfinance as yf
    df = yf.Ticker(symbol).history(period=period, interval="1d")
    if df.empty:
        raise ValueError(f"No index history found for {symbol}")
    return df


def _align(a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Timezone-naive date alignment, forward-filled onto `a`'s calendar.
    Shared by every benchmark-relative comparison below (Nifty or a synthetic
    sector index) — yfinance sometimes returns tz-aware indexes for one series
    and not the other depending on symbol/exchange."""
    a_idx = a.index.tz_localize(None) if a.index.tz is not None else a.index
    b_idx = b.index.tz_localize(None) if b.index.tz is not None else b.index
    a = pd.Series(a.values, index=a_idx)
    b = pd.Series(b.values, index=b_idx).reindex(a_idx, method="ffill")
    return a, b


def backtest_momentum(df: pd.DataFrame, benchmark_closes: pd.Series, symbol: str,
                       lookback: int = 126, deadband_pct: float = 1.0,
                       volume: pd.Series | None = None, volume_avg_days: int = 20) -> list[dict]:
    """Independent signal, not a filter on classify_trend: has this stock
    outperformed its benchmark (Nifty, or — see backtest_sector_momentum — its
    own sector peers) over the trailing `lookback` trading days (~6 months at
    126)? Label Outperform/Underperform, then check the same direction-only
    question as backtest_symbol — does relative momentum predict the stock's
    own future price direction? deadband_pct: skip days where the relative
    momentum is smaller than this, to avoid grading noise near zero as a call.

    volume: if given, only grade a call on days where that day's volume is
    above its own `volume_avg_days`-day average — tests whether "outperformance
    on real buying interest" beats outperformance alone.
    """
    closes, benchmark = _align(df["Close"], benchmark_closes)

    stock_mom = closes / closes.shift(lookback) - 1
    bench_mom = benchmark / benchmark.shift(lookback) - 1
    relative_mom = (stock_mom - bench_mom) * 100  # percentage points

    vol_confirmed = None
    if volume is not None:
        vol_aligned, _ = _align(volume, closes)  # reuse _align just for the tz/reindex logic
        vol_avg = vol_aligned.rolling(volume_avg_days).mean()
        vol_confirmed = vol_aligned > vol_avg

    rows = []
    n = len(closes)
    for i in range(lookback + 1, n):
        rel = relative_mom.iloc[i]
        if pd.isna(rel) or abs(rel) < deadband_pct:
            continue
        if vol_confirmed is not None and (pd.isna(vol_confirmed.iloc[i]) or not vol_confirmed.iloc[i]):
            continue
        direction = "up" if rel > 0 else "down"
        label = "Outperform" if rel > 0 else "Underperform"
        price_t = closes.iloc[i]
        row = {"symbol": symbol, "label": label, "direction": direction, "relative_momentum_pp": round(float(rel), 1)}
        row.update(_grade_future(closes, i, n, price_t, direction))
        rows.append(row)
    return rows


def build_sector_benchmark(sector_closes: dict[str, pd.Series], exclude_symbol: str) -> pd.Series:
    """Synthetic equal-weight sector index for one symbol's peers, leave-one-out
    (excludes the symbol itself, so a stock is never compared against a peer
    group that includes its own price). Each peer's price is normalized to 1.0
    at its first available date before averaging, so no single stock's price
    level dominates the index."""
    peers = {sym: s for sym, s in sector_closes.items() if sym != exclude_symbol}
    common_index = None
    for s in peers.values():
        common_index = s.index if common_index is None else common_index.union(s.index)

    normalized = []
    for s in peers.values():
        s = s.reindex(common_index, method="ffill")
        normalized.append(s / s.dropna().iloc[0])  # rebase each peer to 1.0 at its own first available close
    return pd.concat(normalized, axis=1).mean(axis=1)


def backtest_momentum_corrected(df: pd.DataFrame, benchmark_closes: pd.Series, symbol: str,
                                 lookback: int = 126, deadband_pct: float = 1.0) -> list[dict]:
    """Corrected diagnostic re-test of backtest_momentum(), fixing two flaws
    found on review of the original result:

    1. RELATIVE grading, not absolute. Outperform/Underperform is a claim
       about beating the benchmark, so the grade must check whether that
       outperformance *continued* into the next window — not just whether
       the stock's raw price went up (which mixes in generic market drift
       and was shown, by the base-rate check below, to explain most of the
       original "edge").
    2. NON-OVERLAPPING sampling. One observation per `lookback`-length block
       per symbol (both the momentum-formation window and the forward-check
       window), instead of a fresh row every trading day. Daily-sampled
       overlapping 126-day-lookback/30-day-forward windows share ~97% of
       their data day-to-day, which fakes up the sample size and inflates
       any z-score computed as if the rows were independent.

    This is a confirmatory diagnostic on the same 2-year window already used
    today, not a decisive test on its own — even corrected, ~16-50 stocks
    times ~3 non-overlapping blocks each is only 50-150 observations, well
    below BACKTEST_FINDINGS.md §9's 15-year/48-name/monthly result, which is
    the one with real statistical power. A null result here means "no
    detectable edge at this power," not "proven no edge."
    """
    closes, benchmark = _align(df["Close"], benchmark_closes)
    n = len(closes)

    rows = []
    i = lookback  # first block boundary with a full lookback behind it
    while i + lookback < n:  # also need a full lookback *ahead* to grade continuation
        stock_mom = closes.iloc[i] / closes.iloc[i - lookback] - 1
        bench_mom = benchmark.iloc[i] / benchmark.iloc[i - lookback] - 1
        rel = (stock_mom - bench_mom) * 100

        future_stock_mom = closes.iloc[i + lookback] / closes.iloc[i] - 1
        future_bench_mom = benchmark.iloc[i + lookback] / benchmark.iloc[i] - 1
        future_rel = (future_stock_mom - future_bench_mom) * 100

        if not pd.isna(rel) and not pd.isna(future_rel):
            row = {"symbol": symbol, "relative_momentum_pp": round(float(rel), 1),
                   "future_relative_pp": round(float(future_rel), 1),
                   "beat_benchmark_next_block": bool(future_rel > 0)}
            if abs(rel) >= deadband_pct:
                label = "Outperform" if rel > 0 else "Underperform"
                continued = (future_rel > 0) if rel > 0 else (future_rel < 0)
                row["label"] = label
                row["continued"] = bool(continued)
            rows.append(row)
        i += lookback  # non-overlapping: jump a full lookback, don't slide by 1 day
    return rows


def summarize_corrected(rows: list[dict]) -> dict:
    """Reports the corrected hit rate alongside its own matched empirical
    null (P(beat benchmark in the next block) across *all* blocks, signal or
    not) — never assumes 50/50, per the null-must-match-grading-type fix."""
    df = pd.DataFrame(rows)
    if df.empty:
        return {"n_total_blocks": 0}

    base_rate = round(100 * df["beat_benchmark_next_block"].astype(bool).mean(), 1)
    result = {"n_total_blocks": len(df), "base_rate_beat_benchmark_next_block_pct": base_rate}

    if "label" not in df.columns:
        return result
    signaled = df.dropna(subset=["label"])
    for label, group in signaled.groupby("label"):
        n = len(group)
        hit_rate = round(100 * group["continued"].astype(bool).mean(), 1) if n else None
        result[label] = {"n": n, "hit_rate_pct": hit_rate}
    return result


def run_momentum_corrected(symbols: list[str], lookback: int = 126) -> dict:
    nifty_closes = fetch_index_history()["Close"]
    all_rows = []
    for symbol in symbols:
        try:
            df = pricing.fetch_daily_history(symbol, "NSE", period="2y")
        except ValueError as e:
            print(f"  skipping {symbol}: {e}", file=sys.stderr)
            continue
        all_rows.extend(backtest_momentum_corrected(df, nifty_closes, symbol, lookback=lookback))
    return summarize_corrected(all_rows)


def run_sector_momentum_corrected(sector_map: dict[str, str], lookback: int = 126, min_peers: int = 2) -> dict:
    closes_by_symbol: dict[str, pd.Series] = {}
    for symbol in sorted(sector_map):
        try:
            df = pricing.fetch_daily_history(symbol, "NSE", period="2y")
        except ValueError as e:
            print(f"  skipping {symbol}: {e}", file=sys.stderr)
            continue
        closes_by_symbol[symbol] = df["Close"]

    by_sector: dict[str, dict[str, pd.Series]] = {}
    for symbol, sector in sector_map.items():
        if symbol in closes_by_symbol:
            by_sector.setdefault(sector, {})[symbol] = closes_by_symbol[symbol]

    all_rows = []
    for sector, members in by_sector.items():
        if len(members) < min_peers + 1:
            print(f"  skipping sector {sector}: only {len(members)} symbol(s) in universe", file=sys.stderr)
            continue
        for symbol, closes in members.items():
            benchmark = build_sector_benchmark(members, exclude_symbol=symbol)
            df = pd.DataFrame({"Close": closes})
            all_rows.extend(backtest_momentum_corrected(df, benchmark, symbol, lookback=lookback))
    return summarize_corrected(all_rows)


def summarize(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    out = []
    for label, group in df.groupby("label"):
        entry = {"label": label, "n": len(group)}
        for w in WINDOWS:
            col = f"hit_{w}d"
            graded = group[col].dropna()
            # .astype(bool) belt-and-suspenders: forces a clean numeric mean
            # regardless of whether the column ended up object-dtype.
            entry[f"hit_rate_{w}d"] = round(100 * graded.astype(bool).mean(), 1) if len(graded) else None
            entry[f"n_{w}d"] = len(graded)
        out.append(entry)
    return pd.DataFrame(out).sort_values("label")


def run(symbols: list[str], adx_gate: float | None = None,
        require_sma200_alignment: bool = False) -> pd.DataFrame:
    all_rows = []
    for symbol in symbols:
        try:
            df = pricing.fetch_daily_history(symbol, "NSE", period="2y")
        except ValueError as e:
            print(f"  skipping {symbol}: {e}", file=sys.stderr)
            continue
        all_rows.extend(backtest_symbol(df, symbol, adx_gate=adx_gate,
                                         require_sma200_alignment=require_sma200_alignment))
    return summarize(all_rows)


def run_momentum(symbols: list[str], lookback: int = 126, volume_confirm: bool = False) -> pd.DataFrame:
    nifty_df = fetch_index_history()
    nifty_closes = nifty_df["Close"]
    all_rows = []
    for symbol in symbols:
        try:
            df = pricing.fetch_daily_history(symbol, "NSE", period="2y")
        except ValueError as e:
            print(f"  skipping {symbol}: {e}", file=sys.stderr)
            continue
        volume = df["Volume"] if volume_confirm and "Volume" in df.columns else None
        all_rows.extend(backtest_momentum(df, nifty_closes, symbol, lookback=lookback, volume=volume))
    return summarize(all_rows)


def run_sector_momentum(sector_map: dict[str, str], lookback: int = 126, min_peers: int = 2) -> pd.DataFrame:
    """Same momentum test as run_momentum, but benchmarked against each
    symbol's own sector peers (leave-one-out) instead of the whole-market
    Nifty index — reuses backtest_momentum unchanged, just swapping the
    benchmark series."""
    closes_by_symbol: dict[str, pd.Series] = {}
    for symbol in sorted(sector_map):
        try:
            df = pricing.fetch_daily_history(symbol, "NSE", period="2y")
        except ValueError as e:
            print(f"  skipping {symbol}: {e}", file=sys.stderr)
            continue
        closes_by_symbol[symbol] = df["Close"]

    by_sector: dict[str, dict[str, pd.Series]] = {}
    for symbol, sector in sector_map.items():
        if symbol in closes_by_symbol:
            by_sector.setdefault(sector, {})[symbol] = closes_by_symbol[symbol]

    all_rows = []
    for sector, members in by_sector.items():
        if len(members) < min_peers + 1:  # need at least min_peers *other* stocks
            print(f"  skipping sector {sector}: only {len(members)} symbol(s) in universe", file=sys.stderr)
            continue
        for symbol, closes in members.items():
            benchmark = build_sector_benchmark(members, exclude_symbol=symbol)
            df = pd.DataFrame({"Close": closes})
            all_rows.extend(backtest_momentum(df, benchmark, symbol, lookback=lookback))
    return summarize(all_rows)


if __name__ == "__main__":
    symbols = sys.argv[1:] or DEFAULT_UNIVERSE
    pd.set_option("display.width", 120)

    print(f"Backtesting classify_trend() over 2y history, {len(symbols)} symbols...\n")

    print("=== UNGATED (current live rule table) ===")
    print(run(symbols).to_string(index=False))

    print("\n=== ADX >= 20 GATE (only grade calls made during an actual trend) ===")
    print(run(symbols, adx_gate=20).to_string(index=False))

    print("\n=== 200-DMA ALIGNMENT FILTER (only trust Bullish above / Bearish below 200 DMA) ===")
    print(run(symbols, require_sma200_alignment=True).to_string(index=False))

    print("\n=== RELATIVE MOMENTUM vs NIFTY 50 (independent signal, 6-month lookback) ===")
    print(run_momentum(symbols).to_string(index=False))

    print("\n=== RELATIVE MOMENTUM vs NIFTY 50 + VOLUME CONFIRMATION (above 20d avg volume) ===")
    print(run_momentum(symbols, volume_confirm=True).to_string(index=False))

    print(f"\n=== SECTOR-RELATIVE MOMENTUM (leave-one-out peer benchmark, {len(SECTOR_MAP)} symbols) ===")
    print(run_sector_momentum(SECTOR_MAP).to_string(index=False))

    print("\n=== CORRECTED DIAGNOSTIC: relative grading + non-overlapping blocks (confirmatory, not decisive) ===")
    print("--- vs Nifty 50 ---")
    print(run_momentum_corrected(symbols))
    print("--- sector-relative ---")
    print(run_sector_momentum_corrected(SECTOR_MAP))

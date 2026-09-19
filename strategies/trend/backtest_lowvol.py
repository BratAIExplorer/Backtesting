"""Offline backtest: does buying low-volatility stocks beat an equal-weight
buy-and-hold benchmark of the same universe? (The "low-volatility anomaly" —
lower-beta stocks historically showing better risk-adjusted, sometimes even
raw, returns than high-beta names.)

Deliberately excludes Piotroski F-Score from this backtest. F-Score needs
fundamentals *as they were known* at each historical rebalance date, and
yfinance only exposes a company's last ~4-5 quarters of financials as they
stand today (restated, not point-in-time) — scoring 2022 with 2026's
restated numbers is look-ahead bias, the exact category of mistake
CURRENT_STATUS.md's momentum retraction already cost this project once.
Piotroski is scored live-only instead, see piotroski_screen.py.

Volatility has no such landmine: it's computed purely from realized daily
price history up to and including the rebalance date, so it can be honestly
backtested with yfinance data alone.

Methodology mirrors backtest_trend.py's corrected momentum test:
- Non-overlapping periods only (rebalance every `lookback` trading days) —
  overlapping daily-sampled windows share most of their data and fake up
  the sample size (the exact bug that produced the retracted momentum
  result).
- Benchmark is equal-weight buy-and-hold of the SAME universe over the SAME
  period, not an assumed 50/50 coin flip.
- Transaction costs applied at every rebalance (both portfolios rebalance,
  so costs net out except for the actual portfolio composition churn).

Usage:
    python -m backend.tools.backtest_lowvol
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from .. import pricing
from .backtest_trend import NIFTY_50, _align

VOL_WINDOW = 60       # trading days of realized volatility used to rank at each rebalance
REBALANCE_EVERY = 63  # ~1 quarter of trading days; also the non-overlapping block length
DECILE_N = 10          # number of stocks in the low-vol / high-vol portfolios
ROUND_TRIP_COST_PCT = 0.2  # slippage + brokerage, applied to the fraction of the portfolio that turns over


def fetch_universe_closes(symbols: list[str], period: str = "5y") -> dict[str, pd.Series]:
    closes = {}
    for symbol in symbols:
        try:
            df = pricing.fetch_daily_history(symbol, "NSE", period=period)
        except ValueError as e:
            print(f"  skipping {symbol}: {e}", file=sys.stderr)
            continue
        closes[symbol] = df["Close"]
    return closes


def _realized_vol(closes: pd.Series, as_of_idx: int, window: int = VOL_WINDOW) -> float | None:
    """Annualized realized volatility using only data up to and including
    as_of_idx — never a future price."""
    if as_of_idx < window:
        return None
    window_closes = closes.iloc[as_of_idx - window: as_of_idx + 1]
    returns = window_closes.pct_change().dropna()
    if len(returns) < window * 0.8:  # tolerate a few missing days, not a sparse series
        return None
    return float(returns.std() * np.sqrt(252))


def _portfolio_return(closes_by_symbol: dict[str, pd.Series], symbols: list[str], start_idx: int, end_idx: int) -> float | None:
    """Equal-weight return of `symbols` from start_idx to end_idx, on each
    symbol's own index (already aligned to a common calendar by the caller)."""
    rets = []
    for sym in symbols:
        s = closes_by_symbol.get(sym)
        if s is None or start_idx >= len(s) or end_idx >= len(s):
            continue
        p0, p1 = s.iloc[start_idx], s.iloc[end_idx]
        if pd.isna(p0) or pd.isna(p1) or p0 == 0:
            continue
        rets.append(p1 / p0 - 1)
    return float(np.mean(rets)) if rets else None


def run(symbols: list[str] = NIFTY_50, period: str = "5y") -> dict:
    raw_closes = fetch_universe_closes(symbols, period=period)
    if len(raw_closes) < DECILE_N * 2:
        raise ValueError(f"Only {len(raw_closes)} symbols fetched — need at least {DECILE_N * 2} for two non-overlapping deciles")

    # Align every symbol onto NIFTY's trading calendar so index positions line up across stocks.
    from .backtest_trend import fetch_index_history
    nifty_closes = fetch_index_history(period=period)["Close"]
    nifty_idx = nifty_closes.index.tz_localize(None) if nifty_closes.index.tz is not None else nifty_closes.index
    aligned = {}
    for sym, s in raw_closes.items():
        _, aligned_s = _align(nifty_closes, s)
        aligned[sym] = aligned_s
    n = len(nifty_idx)

    rows = []
    prev_lowvol_holdings: set[str] | None = None
    i = VOL_WINDOW
    while i + REBALANCE_EVERY < n:
        vols = {sym: _realized_vol(s, i) for sym, s in aligned.items()}
        vols = {sym: v for sym, v in vols.items() if v is not None}
        if len(vols) < DECILE_N * 2:
            i += REBALANCE_EVERY
            continue

        ranked = sorted(vols, key=vols.get)
        low_vol_holdings = set(ranked[:DECILE_N])
        high_vol_holdings = set(ranked[-DECILE_N:])
        all_universe = list(vols.keys())

        low_ret = _portfolio_return(aligned, list(low_vol_holdings), i, i + REBALANCE_EVERY)
        high_ret = _portfolio_return(aligned, list(high_vol_holdings), i, i + REBALANCE_EVERY)
        bench_ret = _portfolio_return(aligned, all_universe, i, i + REBALANCE_EVERY)

        if low_ret is not None and bench_ret is not None:
            turnover = 0.0 if prev_lowvol_holdings is None else \
                len(low_vol_holdings - prev_lowvol_holdings) / DECILE_N
            cost = turnover * (ROUND_TRIP_COST_PCT / 100)
            rows.append({
                "period_start": nifty_idx[i], "low_vol_return_pct": round((low_ret - cost) * 100, 2),
                "high_vol_return_pct": round(high_ret * 100, 2) if high_ret is not None else None,
                "benchmark_return_pct": round(bench_ret * 100, 2),
                "low_vol_beat_benchmark": bool((low_ret - cost) > bench_ret),
            })
            prev_lowvol_holdings = low_vol_holdings
        i += REBALANCE_EVERY

    return summarize(rows)


def summarize(rows: list[dict]) -> dict:
    df = pd.DataFrame(rows)
    if df.empty:
        return {"n_periods": 0}

    low = df["low_vol_return_pct"]
    bench = df["benchmark_return_pct"]
    hit_rate = round(100 * df["low_vol_beat_benchmark"].mean(), 1)

    # Paired t-test on the return difference — honest significance check
    # against this specific matched-period null, not an assumed 50/50.
    diff = low - bench
    t_stat = float(diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff)))) if len(diff) > 1 and diff.std(ddof=1) > 0 else None

    sharpe = lambda s: round(float(s.mean() / s.std(ddof=1)), 2) if s.std(ddof=1) else None
    return {
        "n_periods": len(df),
        "low_vol_avg_return_pct": round(float(low.mean()), 2),
        "benchmark_avg_return_pct": round(float(bench.mean()), 2),
        "high_vol_avg_return_pct": round(float(df["high_vol_return_pct"].mean()), 2),
        "low_vol_beat_benchmark_pct_of_periods": hit_rate,
        "paired_t_stat": round(t_stat, 2) if t_stat is not None else None,
        "low_vol_sharpe_per_period": sharpe(low),
        "benchmark_sharpe_per_period": sharpe(bench),
    }


if __name__ == "__main__":
    print("Backtesting low-volatility decile vs equal-weight NIFTY 50 buy-and-hold, 5y history...\n")
    print("Note: |t| < ~2 is not distinguishable from noise at this sample size.\n")
    result = run()
    for k, v in result.items():
        print(f"  {k}: {v}")

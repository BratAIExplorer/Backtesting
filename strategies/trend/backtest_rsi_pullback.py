"""RSI pullback-in-uptrend, US equities, across 4 cap tiers.

Rule (pre-registered, not tuned on this data — textbook swing setup):
  uptrend  = Close > SMA200
  pullback = RSI14 crosses from >=35 to <35 while in uptrend (a dip, not a
             crash — RSI<35 is a mild oversold read, not RSI<20 capitulation)
  entry    = close of the pullback day
  exit     = close N trading days later (N in HORIZONS)

Grading follows the same rules FINDINGS.md already established for PEAD —
see strategies/trend/_common.py for the shared tier universes, cost model,
and HAC/bootstrap grading used by every script in this family.
"""
from __future__ import annotations

import pandas as pd

from ._common import HORIZONS, UNIVERSES, TierResult, grade_tier, load_tier_bars, print_report

RSI_THRESH = 35.0


def rsi_series(closes: pd.Series, period: int = 14) -> pd.Series:
    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return (100 - 100 / (1 + rs)).where(loss != 0, 100.0)


def _events_for_symbol(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Returns (pullback events, all uptrend-day forward returns) — the
    latter is the base-rate pool for this symbol."""
    closes = df["Close"]
    sma200 = closes.rolling(200).mean()
    rsi = rsi_series(closes)
    uptrend = closes > sma200
    was_ok = rsi.shift(1) >= RSI_THRESH
    pullback = uptrend & was_ok & (rsi < RSI_THRESH)

    n = len(df)
    events, base_rows = [], []
    for i in range(200, n):
        if not bool(uptrend.iloc[i]):
            continue
        row = {}
        for h in HORIZONS:
            row[h] = float(closes.iloc[i + h] / closes.iloc[i] - 1.0) if i + h < n else None
        base_rows.append(row)
        if bool(pullback.iloc[i]):
            events.append(row)
    return events, base_rows


def run_tier(tier: str, symbols: list[str]) -> TierResult:
    bars, n_skipped = load_tier_bars(symbols)
    events, base_pool = [], []
    for df in bars.values():
        ev, base = _events_for_symbol(df)
        events.extend(ev)
        base_pool.extend(base)
    return grade_tier(tier, len(symbols), n_skipped, events, base_pool)


def run_all() -> list[TierResult]:
    return [run_tier(tier, syms) for tier, syms in UNIVERSES.items()]


if __name__ == "__main__":
    print_report(run_all())

"""52-week-high momentum, US equities, across 4 cap tiers.

Rule (pre-registered, a distinct, well-documented anomaly from the 6-month
cross-sectional momentum already tested — George & Hwang 2004): a stock
making a fresh 52-week high tends to keep drifting up, no volume filter
(that's backtest_breakout.py's 20-day-high+volume setup, a different test).
  signal = close >= rolling 252-day max
  entry  = close of the signal day
  exit   = close N trading days later

Graded against the tier's own matched base rate, same HAC/bootstrap/cost
machinery as the rest of this family.
"""
from __future__ import annotations

import pandas as pd

from ._common import HORIZONS, TierResult, UNIVERSES, grade_tier, load_tier_bars, print_report

WINDOW = 252  # ~52 weeks of trading days


def _events_for_symbol(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    closes = df["Close"]
    rolling_high = closes.rolling(WINDOW).max()
    is_high = closes >= rolling_high

    n = len(df)
    events, base_pool = [], []
    for i in range(WINDOW, n):
        if pd.isna(rolling_high.iloc[i]):
            continue
        row = {}
        p0 = closes.iloc[i]
        for h in HORIZONS:
            row[h] = float(closes.iloc[i + h] / p0 - 1.0) if i + h < n else None
        base_pool.append(row)
        if bool(is_high.iloc[i]):
            events.append(row)
    return events, base_pool


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

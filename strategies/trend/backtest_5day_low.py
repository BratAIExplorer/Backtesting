"""5-day-low mean reversion, US equities, across 4 cap tiers.

Rule (pre-registered, textbook mean-reversion setup — not tuned here):
  signal = today's close is the lowest close of the last 5 trading days
           (today included)
  entry  = close of the signal day
  exit   = close N trading days later

Opposite bet from the momentum/breakout/pullback family already tested in
this directory (§9-11 of FINDINGS.md, verdict: no edge) — this buys
short-term weakness instead of strength. Graded against the tier's own
matched base rate, same HAC/bootstrap/cost machinery as the rest of the
family.
"""
from __future__ import annotations

import pandas as pd

from ._common import HORIZONS, UNIVERSES, TierResult, grade_tier, load_tier_bars, print_report

LOOKBACK = 5


def _events_for_symbol(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    closes = df["Close"]
    rolling_low = closes.rolling(LOOKBACK).min()
    is_5day_low = closes <= rolling_low

    n = len(df)
    events, base_pool = [], []
    for i in range(LOOKBACK, n):
        if pd.isna(rolling_low.iloc[i]):
            continue
        row = {}
        p0 = closes.iloc[i]
        for h in HORIZONS:
            row[h] = float(closes.iloc[i + h] / p0 - 1.0) if i + h < n else None
        base_pool.append(row)
        if bool(is_5day_low.iloc[i]):
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

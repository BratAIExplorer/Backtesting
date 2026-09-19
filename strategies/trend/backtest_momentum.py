"""Momentum continuation, US equities, across 4 cap tiers.

Rule (pre-registered, standard cross-sectional momentum — not tuned here):
  signal = 6-month (126 trading day) return is in the top 20% of the tier's
           own trailing-momentum distribution on that day (point-in-time:
           ranked only against other names in the SAME tier, SAME day)
  entry  = close of the signal day
  exit   = close N trading days later (buy strength, not dips — the opposite
           entry style from backtest_rsi_pullback.py)

Graded against the tier's own matched base rate, same HAC/bootstrap/cost
machinery as the rest of this family (see strategies/trend/_common.py).
"""
from __future__ import annotations

from ._common import (TierResult, UNIVERSES, cross_sectional_rank_events,
                       grade_tier, load_tier_bars, print_report)

LOOKBACK = 126   # ~6 months
TOP_PCT = 0.80   # top-20% cutoff


def run_tier(tier: str, symbols: list[str]) -> TierResult:
    bars, n_skipped = load_tier_bars(symbols)
    events, base_pool = cross_sectional_rank_events(bars, LOOKBACK, TOP_PCT, side="top") \
        if len(bars) >= 3 else ([], [])
    return grade_tier(tier, len(symbols), n_skipped, events, base_pool)


def run_all() -> list[TierResult]:
    return [run_tier(tier, syms) for tier, syms in UNIVERSES.items()]


if __name__ == "__main__":
    print_report(run_all())

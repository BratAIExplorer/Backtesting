"""Short-term reversal, US equities, across 4 cap tiers.

Rule (pre-registered — the mirror image of momentum, real literature behind
it at short horizons): buy the tier's own worst 5-day losers, not winners.
  signal = trailing 5-day return is in the bottom 20% of the tier's own
           cross-section that day (point-in-time rank, same mechanics as
           backtest_momentum.py via _common.cross_sectional_rank_events)
  entry  = close of the signal day
  exit   = close N trading days later

Graded against the tier's own matched base rate, same HAC/bootstrap/cost
machinery as the rest of this family.
"""
from __future__ import annotations

from ._common import (TierResult, UNIVERSES, cross_sectional_rank_events,
                       grade_tier, load_tier_bars, print_report)

LOOKBACK = 5     # trading days — short-term reversal, not 6-month momentum
BOTTOM_PCT = 0.80  # bottom-20% cutoff (worst losers)


def run_tier(tier: str, symbols: list[str]) -> TierResult:
    bars, n_skipped = load_tier_bars(symbols)
    events, base_pool = cross_sectional_rank_events(bars, LOOKBACK, BOTTOM_PCT, side="bottom") \
        if len(bars) >= 3 else ([], [])
    return grade_tier(tier, len(symbols), n_skipped, events, base_pool)


def run_all() -> list[TierResult]:
    return [run_tier(tier, syms) for tier, syms in UNIVERSES.items()]


if __name__ == "__main__":
    print_report(run_all())

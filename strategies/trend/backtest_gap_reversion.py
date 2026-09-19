"""Gap-down mean reversion, US equities, across 4 cap tiers.

Rule (pre-registered — a genuinely different mechanism from every trend/
momentum script in this family: exploits short-term overreaction, not
continuation; has real academic support at 1-5 day horizons):
  signal = today's open gapped down >=3% from yesterday's close
  entry  = today's close (after the gap has fully played out intraday)
  exit   = close N trading days later

Graded against the tier's own matched base rate (mean forward return of
every day with a valid prior close, signal or not), same HAC/bootstrap/cost
machinery as the rest of this family.
"""
from __future__ import annotations

import pandas as pd

from ._common import HORIZONS, TierResult, UNIVERSES, grade_tier, load_tier_bars, print_report

GAP_THRESHOLD = -0.03  # -3% or worse


def _events_for_symbol(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    closes, opens = df["Close"], df["Open"]
    prior_close = closes.shift(1)
    gap_pct = opens / prior_close - 1.0
    is_gap_down = gap_pct <= GAP_THRESHOLD

    n = len(df)
    events, base_pool = [], []
    for i in range(1, n):
        if pd.isna(gap_pct.iloc[i]):
            continue
        row = {}
        p0 = closes.iloc[i]
        for h in HORIZONS:
            row[h] = float(closes.iloc[i + h] / p0 - 1.0) if i + h < n else None
        base_pool.append(row)
        if bool(is_gap_down.iloc[i]):
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

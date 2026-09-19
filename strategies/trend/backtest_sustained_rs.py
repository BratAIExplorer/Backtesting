"""Sustained relative-strength, US equities, across 4 cap tiers.

Rule (pre-registered, new signal family per FINDINGS.md §12 next-steps):
persistent top-quintile 60-day cross-sectional return rank, not a
point-in-time snap like backtest_momentum.py. A symbol qualifies on day i if
it was in the top 20% of trailing-60d return within its tier on at least 15
of the last 20 trading days. Entry at that day's close, exit N days later.
Tests whether *staying* strong (not just being strong once) is the real
signal, since a one-day momentum snapshot is noisy and this smooths it.

Graded against the tier's own matched base rate (every eligible day, ranked
or not), same HAC/bootstrap/cost machinery as the rest of this family.
"""
from __future__ import annotations

import pandas as pd

from ._common import HORIZONS, TierResult, UNIVERSES, grade_tier, load_tier_bars, print_report

RS_LOOKBACK = 60      # days of trailing return used to rank
TOP_PCT = 0.80        # top-quintile cutoff (rank >= 80th percentile)
PERSIST_WINDOW = 20   # look at the last N days
PERSIST_MIN = 15      # must be top-quintile on at least this many of them


def _events_for_tier(bars: dict[str, pd.DataFrame]) -> tuple[list[dict], list[dict]]:
    closes = {s: df["Close"] for s, df in bars.items()}
    common_index = None
    for s in closes.values():
        common_index = s.index if common_index is None else common_index.union(s.index)
    common_index = common_index.sort_values()

    px = pd.DataFrame({s: c.reindex(common_index).ffill() for s, c in closes.items()})
    trail = px / px.shift(RS_LOOKBACK) - 1.0
    cutoff = trail.quantile(TOP_PCT, axis=1)
    is_top = trail.ge(cutoff, axis=0)
    persist_count = is_top.rolling(PERSIST_WINDOW).sum()
    qualifies = persist_count >= PERSIST_MIN

    events, base_pool = [], []
    n = len(common_index)
    start = RS_LOOKBACK + PERSIST_WINDOW
    for i in range(start, n):
        for sym in trail.columns:
            p0 = px.iloc[i][sym]
            if pd.isna(p0) or pd.isna(trail.iloc[i][sym]):
                continue
            row = {}
            for h in HORIZONS:
                if i + h >= n:
                    row[h] = None
                    continue
                p1 = px.iloc[i + h][sym]
                row[h] = float(p1 / p0 - 1.0) if pd.notna(p1) else None
            base_pool.append(row)
            if bool(qualifies.iloc[i][sym]):
                events.append(row)
    return events, base_pool


def run_tier(tier: str, symbols: list[str]) -> TierResult:
    bars, n_skipped = load_tier_bars(symbols)
    events, base_pool = _events_for_tier(bars) if len(bars) >= 3 else ([], [])
    return grade_tier(tier, len(symbols), n_skipped, events, base_pool)


def run_all() -> list[TierResult]:
    return [run_tier(tier, syms) for tier, syms in UNIVERSES.items()]


if __name__ == "__main__":
    print_report(run_all())

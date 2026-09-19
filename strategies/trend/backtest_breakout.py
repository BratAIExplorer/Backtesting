"""Volume-confirmed breakout, US equities, across 4 cap tiers.

Rule (pre-registered, standard swing breakout — not tuned here):
  signal = today's close is a new N-day high (N=20, ~1 trading month) AND
           today's volume is above its own 20-day average (confirms real
           buying interest, not a thin-volume false breakout)
  entry  = close of the signal day
  exit   = close N trading days later

Graded against the tier's own matched base rate (mean forward return of every
day with a valid 20-day high/volume reading, signal or not), same
HAC/bootstrap/cost machinery as the other scripts in this family.
"""
from __future__ import annotations

import pandas as pd

from ._common import HORIZONS, UNIVERSES, TierResult, grade_tier, load_tier_bars, print_report

BREAKOUT_WINDOW = 20
VOLUME_AVG_DAYS = 20


def _events_for_symbol(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    closes, volume = df["Close"], df["Volume"]
    rolling_high = closes.rolling(BREAKOUT_WINDOW).max()
    vol_avg = volume.rolling(VOLUME_AVG_DAYS).mean()
    is_breakout = (closes >= rolling_high) & (volume > vol_avg)

    n = len(df)
    events, base_pool = [], []
    for i in range(BREAKOUT_WINDOW, n):
        if pd.isna(rolling_high.iloc[i]) or pd.isna(vol_avg.iloc[i]):
            continue
        row = {}
        p0 = closes.iloc[i]
        for h in HORIZONS:
            row[h] = float(closes.iloc[i + h] / p0 - 1.0) if i + h < n else None
        base_pool.append(row)
        if bool(is_breakout.iloc[i]):
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

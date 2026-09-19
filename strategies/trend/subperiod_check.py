"""Sub-period stability check for a candidate (strategy, tier, horizon) —
the exact test that revealed momentum/Large/20d was a 2023-onward regime
artifact, not a real edge (FINDINGS.md §10). Any new candidate must clear
this before being called real: HAC-t >= 2 in the FULL period is necessary
but not sufficient if it flips sign across regimes.

Splits the same 8y sample into 3 windows: pre-2020, 2020-2022 (COVID crash +
bear), 2023+. Reuses the same per-symbol event functions each strategy
script already has — no new signal logic here, just a different date filter.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ._common import UNIVERSES, cross_sectional_rank_events, load_tier_bars
from harness import stats as hstats

PERIODS = [
    ("pre-2020", None, "2020-01-01"),
    ("2020-2022", "2020-01-01", "2023-01-01"),
    ("2023+", "2023-01-01", None),
]


def check_candidate(strategy_module, tier: str, horizon: int, per_symbol: bool = True) -> dict:
    """strategy_module must expose _events_for_symbol(df) -> (events, base_pool)
    where each row is a plain {h: return} dict; this function reruns the
    same logic but scopes each symbol's df to each sub-period's date range
    before calling _events_for_symbol, so the split is exact and no new
    signal math is introduced."""
    symbols = UNIVERSES[tier]
    bars, _ = load_tier_bars(symbols)

    out = {}
    for label, start, end in PERIODS:
        events, base_pool = [], []
        for df in bars.values():
            sub = df
            if start:
                sub = sub[sub.index >= pd.Timestamp(start)]
            if end:
                sub = sub[sub.index < pd.Timestamp(end)]
            if len(sub) < 250:
                continue
            ev, base = strategy_module._events_for_symbol(sub)
            events.extend(ev)
            base_pool.extend(base)
        sig = np.array([e[horizon] for e in events if e.get(horizon) is not None])
        base = np.array([b[horizon] for b in base_pool if b.get(horizon) is not None])
        if sig.size < 10 or base.size < 10:
            out[label] = {"n": int(sig.size), "note": "insufficient data in this sub-period"}
            continue
        t, _, _ = hstats.newey_west_tstat(sig - base.mean())
        out[label] = {
            "n": int(sig.size),
            "signal_ret_pct": round(100 * float(sig.mean()), 2),
            "base_ret_pct": round(100 * float(base.mean()), 2),
            "hac_t": round(t, 2) if np.isfinite(t) else None,
        }
    return out


def check_cross_sectional_candidate(tier: str, horizon: int, lookback: int,
                                     pct_cutoff: float, side: str) -> dict:
    """Same idea as check_candidate() but for momentum/reversal, which rank
    cross-sectionally across the whole tier rather than per-symbol."""
    symbols = UNIVERSES[tier]
    bars, _ = load_tier_bars(symbols)

    out = {}
    for label, start, end in PERIODS:
        sub_bars = {}
        for sym, df in bars.items():
            sub = df
            if start:
                sub = sub[sub.index >= pd.Timestamp(start)]
            if end:
                sub = sub[sub.index < pd.Timestamp(end)]
            if len(sub) > lookback + 20:
                sub_bars[sym] = sub
        if len(sub_bars) < 3:
            out[label] = {"n": 0, "note": "insufficient symbols in this sub-period"}
            continue
        events, base_pool = cross_sectional_rank_events(sub_bars, lookback, pct_cutoff, side=side)
        sig = np.array([e[horizon] for e in events if e.get(horizon) is not None])
        base = np.array([b[horizon] for b in base_pool if b.get(horizon) is not None])
        if sig.size < 10 or base.size < 10:
            out[label] = {"n": int(sig.size), "note": "insufficient data in this sub-period"}
            continue
        t, _, _ = hstats.newey_west_tstat(sig - base.mean())
        out[label] = {
            "n": int(sig.size),
            "signal_ret_pct": round(100 * float(sig.mean()), 2),
            "base_ret_pct": round(100 * float(base.mean()), 2),
            "hac_t": round(t, 2) if np.isfinite(t) else None,
        }
    return out


if __name__ == "__main__":
    import json

    from . import backtest_gap_reversion as gr
    from . import backtest_reversal as rv

    print("=== gap_reversion, Large, 20d ===")
    print(json.dumps(check_candidate(gr, "Large", 20), indent=2))

    print("\n=== gap_reversion, Mid, 20d ===")
    print(json.dumps(check_candidate(gr, "Mid", 20), indent=2))

    print("\n=== reversal (short-term), Penny, 5d ===")
    print(json.dumps(check_cross_sectional_candidate("Penny", 5, rv.LOOKBACK, rv.BOTTOM_PCT, "bottom"), indent=2))

    print("\n=== reversal (short-term), Penny, 10d ===")
    print(json.dumps(check_cross_sectional_candidate("Penny", 10, rv.LOOKBACK, rv.BOTTOM_PCT, "bottom"), indent=2))

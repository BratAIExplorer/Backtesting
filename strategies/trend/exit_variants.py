"""Stop-loss / profit-target exit variants for a candidate signal — tests
whether a fixed-time exit (the only exit rule used everywhere else in this
family) is hiding a worse or better real-world result. Daily-close precision
only (no intraday high/low triggering) — a stop/target is checked once per
day at the close, not tick-by-tick, so a -5% stop can still fill worse than
-5% on a gap day. That's a real limitation, flagged, not hidden.

Simulates, for each entry day: walk forward day by day up to max_hold. Exit
the first day the close return from entry crosses -stop_pct (loss) or
+target_pct (gain); otherwise exit at close of day max_hold (the same rule
every other script in this family already uses).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import backtest_gap_reversion as gr
from ._common import UNIVERSES, load_tier_bars
from harness import stats as hstats

MAX_HOLD = 20


def simulate_exit(closes: pd.Series, entry_i: int, max_hold: int,
                   stop_pct: float | None, target_pct: float | None) -> float | None:
    """Returns the trade return, or None if there isn't enough forward data."""
    n = len(closes)
    if entry_i + max_hold >= n:
        return None
    entry_px = closes.iloc[entry_i]
    for d in range(1, max_hold + 1):
        r = float(closes.iloc[entry_i + d] / entry_px - 1.0)
        if stop_pct is not None and r <= -stop_pct:
            return r
        if target_pct is not None and r >= target_pct:
            return r
    return float(closes.iloc[entry_i + max_hold] / entry_px - 1.0)


def _entry_indices(df: pd.DataFrame) -> list[int]:
    """Re-derives gap-down entry days (same rule as backtest_gap_reversion,
    just returning positions instead of precomputed h-return rows)."""
    closes, opens = df["Close"], df["Open"]
    gap_pct = opens / closes.shift(1) - 1.0
    is_gap_down = gap_pct <= gr.GAP_THRESHOLD
    return [i for i in range(1, len(df)) if bool(is_gap_down.iloc[i]) and not pd.isna(gap_pct.iloc[i])]


def run_variant(tier: str, stop_pct: float | None, target_pct: float | None) -> dict:
    bars, _ = load_tier_bars(UNIVERSES[tier])
    rets = []
    for df in bars.values():
        closes = df["Close"]
        for i in _entry_indices(df):
            r = simulate_exit(closes, i, MAX_HOLD, stop_pct, target_pct)
            if r is not None:
                rets.append(r)
    rets = np.array(rets)
    if rets.size < 10:
        return {"n": int(rets.size)}
    t, _, mu = hstats.newey_west_tstat(rets)
    return {
        "n": int(rets.size),
        "mean_ret_pct": round(100 * mu, 2),
        "median_ret_pct": round(100 * float(np.median(rets)), 2),
        "std_pct": round(100 * float(rets.std(ddof=1)), 2),
        "worst_pct": round(100 * float(rets.min()), 2),
        "sharpe_per_trade": round(float(mu / rets.std(ddof=1)), 3) if rets.std(ddof=1) > 0 else None,
        "hac_t_vs_zero": round(t, 2) if np.isfinite(t) else None,
        "pct_trades_positive": round(100 * float((rets > 0).mean()), 1),
    }


VARIANTS = [
    ("no stop / no target (baseline, fixed 20d)", None, None),
    ("stop -5%", 0.05, None),
    ("stop -8%", 0.08, None),
    ("target +5%", None, 0.05),
    ("target +8%", None, 0.08),
    ("stop -5% / target +8%", 0.05, 0.08),
    ("stop -8% / target +8%", 0.08, 0.08),
    ("stop -5% / target +5%", 0.05, 0.05),
]


def run_all(tier: str) -> dict:
    return {label: run_variant(tier, stop, target) for label, stop, target in VARIANTS}


if __name__ == "__main__":
    import json
    for tier in ("Large", "Mid", "Small"):
        print(f"=== Gap-down reversion, exit variants, {tier} caps (max hold {MAX_HOLD}d) ===")
        print(json.dumps(run_all(tier), indent=2))

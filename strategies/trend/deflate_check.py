"""Cross-strategy differential-DSR check across every (strategy, tier,
horizon) trial in the US swing family — rerun whenever a new candidate
script is added, instead of hand-computing deflation once and never
re-checking it as more variants pile on.

Differential, not raw: each trial's Sharpe is computed on (signal_return -
tier_base_rate), the same quantity each strategy script already HAC-tests.
Deflating raw signal Sharpe mostly measures "did the tier trend up" — see
FINDINGS.md §9's caveat on that earlier mistake.
"""
from __future__ import annotations

import numpy as np
from scipy import stats as sps

from . import backtest_52w_high as hi
from . import backtest_5day_low as fl
from . import backtest_breakout as bo
from . import backtest_gap_reversion as gr
from . import backtest_momentum as mo
from . import backtest_reversal as rv
from . import backtest_rsi_macd as rm
from . import backtest_rsi_pullback as rp
from . import backtest_sustained_rs as sr
from ._common import HORIZONS, UNIVERSES, cross_sectional_rank_events, load_tier_bars
from harness import stats as hstats

PER_SYMBOL_STRATEGIES = {
    "rsi_pullback": rp._events_for_symbol,
    "breakout": bo._events_for_symbol,
    "rsi_macd": rm._events_for_symbol,
    "gap_reversion": gr._events_for_symbol,
    "52w_high": hi._events_for_symbol,
    "5day_low": fl._events_for_symbol,
}
CROSS_SECTIONAL_STRATEGIES = {
    "momentum": (mo.LOOKBACK, mo.TOP_PCT, "top"),
    "reversal": (rv.LOOKBACK, rv.BOTTOM_PCT, "bottom"),
}
TIER_LEVEL_STRATEGIES = {"sustained_rs": sr._events_for_tier}


def _collect(strategy: str, bars: dict) -> tuple[list[dict], list[dict]]:
    if strategy in TIER_LEVEL_STRATEGIES:
        return TIER_LEVEL_STRATEGIES[strategy](bars) if len(bars) >= 3 else ([], [])
    if strategy in CROSS_SECTIONAL_STRATEGIES:
        lookback, pct, side = CROSS_SECTIONAL_STRATEGIES[strategy]
        return cross_sectional_rank_events(bars, lookback, pct, side=side) if len(bars) >= 3 else ([], [])
    fn = PER_SYMBOL_STRATEGIES[strategy]
    events, base_pool = [], []
    for df in bars.values():
        ev, base = fn(df)
        events.extend(ev)
        base_pool.extend(base)
    return events, base_pool


def run() -> dict:
    tier_bars = {tier: load_tier_bars(syms)[0] for tier, syms in UNIVERSES.items()}
    all_strategies = list(PER_SYMBOL_STRATEGIES) + list(CROSS_SECTIONAL_STRATEGIES) + list(TIER_LEVEL_STRATEGIES)

    diffs: dict[tuple, np.ndarray] = {}
    for strategy in all_strategies:
        for tier, bars in tier_bars.items():
            if len(bars) < 3:
                continue
            events, base_pool = _collect(strategy, bars)
            for h in HORIZONS:
                sig = np.array([e[h] for e in events if e.get(h) is not None])
                base = np.array([b[h] for b in base_pool if b.get(h) is not None])
                if sig.size > 10 and base.size > 10:
                    d = sig - base.mean()
                    if d.std(ddof=1) > 0:
                        diffs[(strategy, tier, h)] = d

    srs = {k: float(d.mean() / d.std(ddof=1)) for k, d in diffs.items()}
    n_trials = len(srs)
    sr_std = float(np.std(list(srs.values()), ddof=1))
    best_key = max(srs, key=srs.get)
    best = diffs[best_key]
    sr = srs[best_key]
    sk = float(sps.skew(best))
    ku = float(sps.kurtosis(best, fisher=False))
    dsr, sr0 = hstats.deflated_sharpe_ratio(sr, len(best), sk, ku, n_trials, sr_std)

    return {
        "n_trials": n_trials,
        "best_trial": best_key,
        "differential_sharpe_per_period": round(sr, 4),
        "sr0_benchmark": round(sr0, 4),
        "dsr": round(dsr, 4) if np.isfinite(dsr) else dsr,
        "dsr_pass": bool(np.isfinite(dsr) and dsr >= 0.95),
        "top_10_by_differential_sharpe": sorted(
            ((k, round(v, 4)) for k, v in srs.items()), key=lambda kv: -kv[1]
        )[:10],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2, default=str))

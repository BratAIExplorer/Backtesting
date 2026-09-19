"""Shared plumbing for the US swing-strategy family (rsi_pullback, momentum,
breakout): cap-tier universes, per-tier cost assumptions, and the
event-vs-matched-base-rate grading routine. Extracted after the 3rd strategy
script needed the identical tier loop + HAC/bootstrap grading — not built
ahead of need.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("strategies", 1)[0])  # repo root, for `harness.*`
from harness import data as hdata
from harness import stats as hstats

HORIZONS = (5, 10, 20)  # trading days

# Systematically screened per strategies/trend/screener.py (S&P 500/400/600 +
# NASDAQ-listed penny names, seeded random sample -> liquidity/ATR% filter),
# not hand-picked. See FINDINGS.md §12 for the screen run and rejection log.
UNIVERSES = {
    "Large": ['EME', 'MCD', 'CVNA', 'CBOE', 'CHTR', 'ECHO', 'COF', 'V', 'DAL', 'MKC',
              'AVY', 'SHW', 'GPC', 'KO', 'D', 'RCL', 'CAT', 'NOW', 'DOW', 'MRVL',
              'NVR', 'STZ', 'EOG', 'EW', 'MCK', 'CARR', 'PG', 'TGT', 'MRK', 'AIZ'],
    "Mid":   ['FAF', 'IESC', 'CW', 'TLN', 'BAH', 'OVV', 'CPRI', 'TREX', 'POR', 'UNM',
              'SITM', 'SHC', 'BKH', 'MUSA', 'AVNT', 'SUI', 'ESNT', 'CRBG', 'SARO', 'HLNE',
              'ENS', 'TXRH', 'CSL', 'MUR', 'SMG'],
    "Small": ['CALX', 'MD', 'ZWS', 'PENG', 'INSW', 'EXTR', 'CNXC', 'VCEL', 'BMI', 'CRK',
              'TFX', 'LTH', 'MMI', 'WEN', 'BTU', 'AUB', 'JBSS', 'POOL', 'CRSR', 'CRGY'],
    "Penny": ['WOOF', 'LSTA', 'OCGN', 'IQ', 'CERS', 'VBIO', 'MNTK', 'ATLX', 'CRMT',
              'COSM', 'INV', 'ALTI', 'AREC', 'OGI', 'CYPH'],
}

# Round-trip bps by tier: tighter spreads/deeper books at the top.
COST_BPS = {"Large": 10, "Mid": 20, "Small": 35, "Penny": 150}


@dataclass
class TierResult:
    tier: str
    n_symbols: int
    n_skipped: int
    n_events: dict[int, int]
    signal_ret_pct: dict[int, float]
    base_ret_pct: dict[int, float]
    hac_t: dict[int, float]
    boot_ci: dict[int, tuple[float, float]]
    net_of_cost_pct: dict[int, float]


def load_tier_bars(symbols: list[str], period: str = "8y") -> tuple[dict[str, pd.DataFrame], int]:
    bars, n_skipped = {}, 0
    for sym in symbols:
        df = hdata.load_daily(sym, period=period)
        if df is None or len(df) < 250:
            print(f"  skipping {sym}: no/insufficient data", file=__import__("sys").stderr)
            n_skipped += 1
            continue
        bars[sym] = df
    return bars, n_skipped


def grade_tier(tier: str, n_symbols: int, n_skipped: int,
               events: list[dict], base_pool: list[dict]) -> TierResult:
    """events/base_pool: list of {h: forward_return_or_None} dicts, h in HORIZONS.
    events is the signal's own set; base_pool is every eligible day (signal or
    not) in the same tier — the matched base rate, never a coin-flip null."""
    cost = COST_BPS[tier] / 10_000.0
    n_events, signal_ret, base_ret, hac_t, boot_ci, net_ret = {}, {}, {}, {}, {}, {}
    for h in HORIZONS:
        sig = np.array([e[h] for e in events if e.get(h) is not None])
        base = np.array([b[h] for b in base_pool if b.get(h) is not None])
        n_events[h] = int(sig.size)
        signal_ret[h] = round(100 * float(sig.mean()), 2) if sig.size else float("nan")
        base_ret[h] = round(100 * float(base.mean()), 2) if base.size else float("nan")
        t, _, _ = hstats.newey_west_tstat(sig - (base.mean() if base.size else 0.0))
        hac_t[h] = round(t, 2) if np.isfinite(t) else float("nan")
        lo, hi = hstats.block_bootstrap_mean_ci(sig) if sig.size else (float("nan"), float("nan"))
        boot_ci[h] = (round(100 * lo, 2), round(100 * hi, 2)) if np.isfinite(lo) else (float("nan"), float("nan"))
        net_ret[h] = round(signal_ret[h] - 100 * cost, 2) if sig.size else float("nan")
    return TierResult(tier, n_symbols, n_skipped, n_events, signal_ret, base_ret, hac_t, boot_ci, net_ret)


def cross_sectional_rank_events(bars: dict[str, pd.DataFrame], lookback: int,
                                 pct_cutoff: float, side: str = "top") -> tuple[list[dict], list[dict]]:
    """Point-in-time cross-sectional rank: for each day, rank every symbol in
    `bars` by its trailing `lookback`-day return, and flag the top/bottom
    `1-pct_cutoff` fraction as the signal. Shared by momentum (side='top',
    long lookback) and short-term reversal (side='bottom', short lookback) —
    identical mechanics, opposite bet.
    """
    closes = {s: df["Close"] for s, df in bars.items()}
    common_index = None
    for s in closes.values():
        common_index = s.index if common_index is None else common_index.union(s.index)
    common_index = common_index.sort_values()

    px = pd.DataFrame({s: c.reindex(common_index).ffill() for s, c in closes.items()})
    trail = px / px.shift(lookback) - 1.0

    if side == "top":
        cutoff = trail.quantile(pct_cutoff, axis=1)
        flagged = trail.ge(cutoff, axis=0)
    else:
        cutoff = trail.quantile(1.0 - pct_cutoff, axis=1)
        flagged = trail.le(cutoff, axis=0)

    events, base_pool = [], []
    n = len(common_index)
    for i in range(lookback, n):
        for sym in trail.columns:
            m = trail.iloc[i][sym]
            p0 = px.iloc[i][sym]
            if pd.isna(m) or pd.isna(p0):
                continue
            row = {}
            for h in HORIZONS:
                if i + h >= n:
                    row[h] = None
                    continue
                p1 = px.iloc[i + h][sym]
                row[h] = float(p1 / p0 - 1.0) if pd.notna(p1) else None
            base_pool.append(row)
            if bool(flagged.iloc[i][sym]):
                events.append(row)
    return events, base_pool


def print_report(results: list[TierResult]) -> None:
    for r in results:
        print(f"\n=== {r.tier} ({r.n_symbols} symbols, {r.n_skipped} skipped, "
              f"cost={COST_BPS[r.tier]}bps round-trip) ===")
        for h in HORIZONS:
            print(f"  {h:>2}d  n={r.n_events[h]:<5} "
                  f"signal={r.signal_ret_pct[h]:>6}%  base={r.base_ret_pct[h]:>6}%  "
                  f"HAC-t(signal-base)={r.hac_t[h]:>6}  boot90%CI={r.boot_ci[h]}  "
                  f"net-of-cost={r.net_of_cost_pct[h]:>6}%")

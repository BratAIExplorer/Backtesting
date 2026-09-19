"""Sub-period stability check for gap-down reversion 20d (Large/Mid/Small),
the only trial in strategies/trend/deflate_check.py to clear DSR>=0.95 on the
rescreened universe (see FINDINGS.md). Same rule as backtest_gap_reversion.py,
just keeps entry dates so returns can be sliced by regime — mirrors
momentum_robustness.py's sub-period check, applied to the new best trial.
"""
from __future__ import annotations

import pandas as pd

from . import backtest_gap_reversion as gr
from ._common import HORIZONS, UNIVERSES, load_tier_bars
from harness import stats as hstats

PERIODS = [("pre-2020", None, "2020-01-01"), ("2020-2022", "2020-01-01", "2023-01-01"),
           ("2023+", "2023-01-01", None)]
H = 20


def _dated_events_for_symbol(df: pd.DataFrame) -> pd.DataFrame:
    closes, opens = df["Close"], df["Open"]
    prior_close = closes.shift(1)
    gap_pct = opens / prior_close - 1.0
    n = len(df)
    rows = []
    for i in range(1, n):
        if pd.isna(gap_pct.iloc[i]) or i + H >= n:
            continue
        p0 = closes.iloc[i]
        ret = float(closes.iloc[i + H] / p0 - 1.0)
        rows.append({"date": df.index[i], "is_event": bool(gap_pct.iloc[i] <= gr.GAP_THRESHOLD), H: ret})
    return pd.DataFrame(rows)


def run() -> dict:
    out = {}
    for tier in ("Large", "Mid", "Small"):
        bars, _ = load_tier_bars(UNIVERSES[tier])
        all_rows = pd.concat([_dated_events_for_symbol(df) for df in bars.values()], ignore_index=True)
        tier_out = {}
        for label, lo, hi in PERIODS:
            sl = all_rows
            if lo: sl = sl[sl["date"] >= lo]
            if hi: sl = sl[sl["date"] < hi]
            sig = sl.loc[sl["is_event"], H].dropna().to_numpy()
            base = sl[H].dropna().to_numpy()
            if sig.size < 5 or base.size < 5:
                tier_out[label] = {"n": int(sig.size), "note": "too few events"}
                continue
            t, _, _ = hstats.newey_west_tstat(sig - base.mean())
            tier_out[label] = {"n": int(sig.size), "signal_ret_pct": round(100 * float(sig.mean()), 2),
                                "base_ret_pct": round(100 * float(base.mean()), 2), "hac_t": round(t, 2)}
        out[tier] = tier_out
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2, default=str))

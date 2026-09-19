"""Follow-up checks on the one result that cleared |HAC-t|>=2 in this project:
Large-cap 20d momentum continuation (backtest_momentum.py). Two questions:

1. Deflated Sharpe — does it survive having tried 4 tiers x 3 horizons = 12
   variants in this family (same count FINDINGS.md already flagged as owed)?
2. Sub-period stability — does it hold pre-2020, through the 2022 bear, and
   in 2023+, or is it a one-regime artifact like everything else here?

Not a new strategy: reuses the exact rule from backtest_momentum.py, just
adds dates to the event stream so returns can be sliced by period.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import backtest_momentum as bm
from ._common import HORIZONS, UNIVERSES, grade_tier, load_tier_bars
from harness import stats as hstats


def _dated_events_for_tier(bars: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Same rule as backtest_momentum._events_for_tier, but keeps entry date
    and symbol per event/base row instead of throwing them away."""
    closes = {s: df["Close"] for s, df in bars.items()}
    common_index = None
    for s in closes.values():
        common_index = s.index if common_index is None else common_index.union(s.index)
    common_index = common_index.sort_values()

    mom = pd.DataFrame({s: c.reindex(common_index).ffill() for s, c in closes.items()})
    mom = mom / mom.shift(bm.LOOKBACK) - 1.0
    px = pd.DataFrame({s: c.reindex(common_index).ffill() for s, c in closes.items()})
    cutoff = mom.quantile(bm.TOP_PCT, axis=1)
    is_top = mom.ge(cutoff, axis=0)

    rows = []
    n = len(common_index)
    for i in range(bm.LOOKBACK, n):
        for sym in mom.columns:
            m = mom.iloc[i][sym]
            if pd.isna(m):
                continue
            p0 = px.iloc[i][sym]
            if pd.isna(p0):
                continue
            row = {"date": common_index[i], "symbol": sym, "is_event": bool(is_top.iloc[i][sym])}
            for h in HORIZONS:
                p1 = px.iloc[i + h][sym] if i + h < n else None
                row[h] = float(p1 / p0 - 1.0) if p1 is not None and pd.notna(p1) else None
            rows.append(row)
    return pd.DataFrame(rows)


def deflate_large_20d() -> dict:
    """DSR for Large-20d against the 12 tier x horizon trials actually run."""
    trial_returns, best_index = [], None
    for tier, symbols in UNIVERSES.items():
        bars, _ = load_tier_bars(symbols)
        df = _dated_events_for_tier(bars) if len(bars) >= 3 else pd.DataFrame()
        for h in HORIZONS:
            if df.empty:
                trial_returns.append(np.array([np.nan]))
                continue
            sig = df.loc[df["is_event"] & df[h].notna(), h].to_numpy()
            trial_returns.append(sig if sig.size > 2 else np.array([np.nan]))
            if tier == "Large" and h == 20:
                best_index = len(trial_returns) - 1
    n_obs = int(np.sum(np.isfinite(trial_returns[best_index])))
    return hstats.dsr_from_trials(trial_returns, n_obs=n_obs, n_trials=len(trial_returns),
                                  best_index=best_index)


def subperiod_stability(horizon: int = 20) -> list[dict]:
    """Large-tier momentum, same horizon, split into 3 regimes: pre-2020
    (last leg of the 2010s bull), 2020-2022 (covid crash + 2022 bear), 2023+
    (recent bull). Each graded independently against ITS OWN period base rate."""
    bars, _ = load_tier_bars(UNIVERSES["Large"])
    df = _dated_events_for_tier(bars)
    df["date"] = pd.to_datetime(df["date"])

    periods = {
        "pre-2020": (df["date"] < "2020-01-01"),
        "2020-2022": (df["date"] >= "2020-01-01") & (df["date"] < "2023-01-01"),
        "2023+": (df["date"] >= "2023-01-01"),
    }
    out = []
    for name, mask in periods.items():
        sub = df.loc[mask]
        sig = sub.loc[sub["is_event"], horizon].dropna().to_numpy()
        base = sub[horizon].dropna().to_numpy()
        if sig.size < 5 or base.size < 5:
            out.append({"period": name, "n_events": int(sig.size), "note": "too few events"})
            continue
        t, _, _ = hstats.newey_west_tstat(sig - base.mean())
        out.append({
            "period": name,
            "n_events": int(sig.size),
            "signal_ret_pct": round(100 * sig.mean(), 2),
            "base_ret_pct": round(100 * base.mean(), 2),
            "hac_t": round(t, 2) if np.isfinite(t) else float("nan"),
        })
    return out


if __name__ == "__main__":
    print("=== Deflated Sharpe: Large-cap 20d momentum vs 12 tried variants ===")
    d = deflate_large_20d()
    print(f"  sharpe={d['sharpe_per_period']:.4f}  sr0(expected-max-of-{d['n_trials']})={d['sr0']:.4f}  "
          f"DSR={d['dsr']:.3f}  skew={d['skew']:.2f}  kurt={d['kurtosis']:.2f}")

    print("\n=== Sub-period stability: Large-cap 20d momentum ===")
    for r in subperiod_stability(20):
        print(f"  {r}")

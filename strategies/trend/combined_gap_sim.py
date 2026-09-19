"""Gap-down reversion 20d: Mid+Small pooled into ONE account vs each tier alone.
In-sample portfolio optimization, NOT validation -- entry rule is unchanged.
Pooled account charges the higher (Small) cost on every trade: conservative.
No T-bill yield on idle cash (simulate_portfolio doesn't model it)."""
from __future__ import annotations

import json

from .portfolio_sim import _aligned_closes, _mask_gap_reversion, simulate_portfolio
from ._common import COST_BPS, UNIVERSES, load_tier_bars

CAPITAL, HOLD = 5_000.0, 20


def _inputs(tiers):
    bars = {}
    for t in tiers:
        b, _ = load_tier_bars(UNIVERSES[t])
        bars.update(b)
    idx = None
    for df in bars.values():
        idx = df.index if idx is None else idx.union(df.index)
    idx = idx.sort_values()
    return bars, _aligned_closes(bars, idx), idx


def run() -> dict:
    out = {}
    cases = {"Mid": (("Mid",), COST_BPS["Mid"]), "Small": (("Small",), COST_BPS["Small"]),
             "Mid+Small": (("Mid", "Small"), max(COST_BPS["Mid"], COST_BPS["Small"]))}
    for name, (tiers, cost) in cases.items():
        bars, px, idx = _inputs(tiers)
        mask = _mask_gap_reversion(bars, idx)
        for slots in (5, 10):
            r = simulate_portfolio(mask, px, cost, HOLD, "gap_reversion", name, capital=CAPITAL, max_positions=slots)
            out[f"{name}/{slots}slots"] = None if r is None else {
                "cagr_pct": r.cagr_pct, "sharpe": r.sharpe, "max_dd_pct": r.max_drawdown_pct,
                "n_trades": r.n_trades, "win_rate_pct": r.win_rate_pct,
                "avg_positions": r.avg_positions_held, "skipped_too_small_pct": r.signals_skipped_too_small_pct}
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))

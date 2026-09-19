"""How much does account size itself matter for Penny/Mid/Small tiers, once
whole-share rounding is accounted for? A $500 slot buys plenty of a $12
Mid-cap stock but might buy zero shares of an $80 one, silently skipping
that signal. Large caps are left out here -- at $50k+ typical share prices
they're the least exposed to this effect and were already the weakest
tier-of-interest anyway (see FINDINGS.md).
"""
from __future__ import annotations

import json
from dataclasses import asdict

from ._common import COST_BPS
from .portfolio_sim import HOLD_DAYS_OPTIONS, STRATEGIES, _tier_inputs, simulate_portfolio

CAPITAL_LEVELS = (1_000.0, 2_500.0, 5_000.0, 10_000.0, 25_000.0)
TIERS = ("Penny", "Small", "Mid")


def run_all() -> list[dict]:
    results = []
    for tier in TIERS:
        loaded = _tier_inputs(tier)
        if loaded is None:
            continue
        bars, px, idx = loaded
        for strat_name, mask_fn in STRATEGIES.items():
            mask = mask_fn(bars, idx)
            for hold_days in HOLD_DAYS_OPTIONS:
                for capital in CAPITAL_LEVELS:
                    r = simulate_portfolio(mask, px, COST_BPS[tier], hold_days, strat_name, tier, capital=capital)
                    if r is not None:
                        results.append(asdict(r))
    return results


if __name__ == "__main__":
    results = run_all()
    with open("capital_sensitivity_results.json", "w") as f:
        json.dump(results, f)
    print(f"{len(results)} strategy x tier x hold_days x capital combos -> capital_sensitivity_results.json")

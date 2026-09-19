"""Portfolio-level position-sizing and equity-curve simulation.

Every backtest_*.py script in this family answers "if you took this trade,
what % did you make" (per-trade edge). It does NOT answer "if you had
$100k, sized positions some way, and could only hold N at once, what does
your account look like" (a tradeable portfolio). This module is that
missing piece.

Mechanics, stated plainly:
  - starting capital: $100,000
  - max 10 concurrent positions, each sized at 1/10th of CURRENT equity when
    opened (so the account compounds, and no single trade is oversized)
  - if more signals fire on a day than there are free slots, the extra
    signals are skipped that day (first-come by symbol order, not
    cherry-picked by which looked best -- that would be lookahead)
  - fixed-day exit only (no stop-loss / profit-target -- exit_variants.py
    already showed those make gap-down reversion worse; using the same
    exit rule everywhere keeps every strategy's comparison apples-to-apples)
  - round-trip cost per tier from _common.COST_BPS, charged on exit

Every strategy's entry signal is reused VERBATIM from its own backtest_*.py
module (same thresholds, same functions) so this can never silently drift
from what was actually backtested and reported in FINDINGS.md.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from . import backtest_52w_high as hi
from . import backtest_5day_low as fl
from . import backtest_breakout as bo
from . import backtest_gap_reversion as gr
from . import backtest_rsi_macd as rm
from . import backtest_rsi_pullback as rp
from . import backtest_sustained_rs as sr
from ._common import COST_BPS, UNIVERSES, load_tier_bars

STARTING_CAPITAL = 5_000.0
MAX_POSITIONS = 10
HOLD_DAYS_OPTIONS = (5, 10, 20)
EQUITY_SAMPLE_EVERY = 5  # downsample equity curve for the HTML report


def _aligned_closes(bars: dict[str, pd.DataFrame], idx: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame({s: df["Close"].reindex(idx).ffill() for s, df in bars.items()})


def _aligned(bars: dict[str, pd.DataFrame], col: str, idx: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame({s: df[col].reindex(idx).ffill() for s, df in bars.items()})


# ---- per-strategy boolean signal masks (dates x symbols) -------------------
# Each reuses its module's own thresholds/functions verbatim -- no re-derived
# logic, so this can't silently diverge from what backtest_*.py established.

def _mask_rsi_pullback(bars, idx):
    closes = _aligned_closes(bars, idx)
    sma200 = closes.rolling(200).mean()
    rsi = closes.apply(rp.rsi_series)
    uptrend = closes > sma200
    was_ok = rsi.shift(1) >= rp.RSI_THRESH
    return uptrend & was_ok & (rsi < rp.RSI_THRESH)


def _mask_breakout(bars, idx):
    closes = _aligned_closes(bars, idx)
    volume = _aligned(bars, "Volume", idx)
    rolling_high = closes.rolling(bo.BREAKOUT_WINDOW).max()
    vol_avg = volume.rolling(bo.VOLUME_AVG_DAYS).mean()
    return (closes >= rolling_high) & (volume > vol_avg)


def _mask_5day_low(bars, idx):
    closes = _aligned_closes(bars, idx)
    return closes <= closes.rolling(fl.LOOKBACK).min()


def _mask_52w_high(bars, idx):
    closes = _aligned_closes(bars, idx)
    return closes >= closes.rolling(hi.WINDOW).max()


def _mask_rsi_macd(bars, idx):
    closes = _aligned_closes(bars, idx)
    sma200 = closes.rolling(200).mean()
    rsi = closes.apply(rm.rsi_series)
    macd_line = closes.apply(lambda c: rm.macd_lines(c)[0])
    signal_line = closes.apply(lambda c: rm.macd_lines(c)[1])
    uptrend = closes > sma200
    fresh_cross = (macd_line.shift(1) <= signal_line.shift(1)) & (macd_line > signal_line)
    return uptrend & fresh_cross & (rsi > 50)


def _mask_gap_reversion(bars, idx):
    closes = _aligned_closes(bars, idx)
    opens = _aligned(bars, "Open", idx)
    gap_pct = opens / closes.shift(1) - 1.0
    return gap_pct <= gr.GAP_THRESHOLD


def _mask_momentum(bars, idx):
    px = _aligned_closes(bars, idx)
    trail = px / px.shift(126) - 1.0
    cutoff = trail.quantile(0.80, axis=1)
    return trail.ge(cutoff, axis=0)


def _mask_reversal(bars, idx):
    px = _aligned_closes(bars, idx)
    trail = px / px.shift(5) - 1.0
    cutoff = trail.quantile(0.20, axis=1)
    return trail.le(cutoff, axis=0)


def _mask_sustained_rs(bars, idx):
    px = _aligned_closes(bars, idx)
    trail = px / px.shift(sr.RS_LOOKBACK) - 1.0
    cutoff = trail.quantile(sr.TOP_PCT, axis=1)
    is_top = trail.ge(cutoff, axis=0)
    persist_count = is_top.rolling(sr.PERSIST_WINDOW).sum()
    return persist_count >= sr.PERSIST_MIN


STRATEGIES = {
    "rsi_pullback": _mask_rsi_pullback,
    "breakout": _mask_breakout,
    "5day_low": _mask_5day_low,
    "52w_high": _mask_52w_high,
    "rsi_macd": _mask_rsi_macd,
    "gap_reversion": _mask_gap_reversion,
    "momentum": _mask_momentum,
    "reversal": _mask_reversal,
    "sustained_rs": _mask_sustained_rs,
}


@dataclass
class PortfolioResult:
    strategy: str
    tier: str
    hold_days: int
    n_trades: int
    win_rate_pct: float
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    sharpe: float
    final_equity: float
    avg_positions_held: float
    capital: float
    signals_skipped_too_small_pct: float  # whole-share rounding made the slot un-buyable
    equity_dates: list  # downsampled, for the HTML report
    equity_values: list


def simulate_portfolio(mask: pd.DataFrame, px: pd.DataFrame, cost_bps: float, hold_days: int,
                        strategy: str, tier: str, capital: float = STARTING_CAPITAL,
                        max_positions: int = MAX_POSITIONS, whole_shares: bool = True) -> PortfolioResult | None:
    """whole_shares=True mirrors a real retail broker: most stocks can't be
    bought in fractions, so a slot too small to afford even 1 share is
    skipped rather than silently assumed fillable. This matters once
    capital/max_positions gets small relative to share price (Mid/Large
    names at low capital, or Penny names where 1 share is cheap but the
    150bps cost eats a bigger fraction of a tiny position)."""
    dates = px.index
    n = len(dates)
    cost = cost_bps / 10_000.0
    cash = capital
    open_pos: dict[str, dict] = {}
    equity_curve = np.empty(n)
    trade_returns: list[float] = []
    positions_held = np.empty(n, dtype=int)
    n_signals_seen = 0
    n_signals_too_small = 0

    first_valid = [mask[s].first_valid_index() for s in mask.columns if mask[s].first_valid_index() is not None]
    if not first_valid:
        return None
    start_i = dates.get_loc(max(first_valid))

    for i in range(n):
        to_close = [s for s, p in open_pos.items() if p["exit_i"] == i]
        for s in to_close:
            p = open_pos.pop(s)
            price = px[s].iloc[i]
            if pd.isna(price):
                price = p["entry_price"]
            proceeds = p["shares"] * price * (1 - cost)
            cash += proceeds
            trade_returns.append(proceeds / p["cost_basis"] - 1.0)

        mtm = 0.0
        for sym, p in open_pos.items():
            price = px[sym].iloc[i]
            mtm += p["shares"] * (price if pd.notna(price) else p["entry_price"])
        equity = cash + mtm
        equity_curve[i] = equity
        positions_held[i] = len(open_pos)

        if i < start_i or i + hold_days >= n:
            continue

        for s in mask.columns:
            if len(open_pos) >= max_positions:
                break
            if s in open_pos:
                continue
            sig = mask[s].iloc[i]
            if pd.isna(sig) or not bool(sig):
                continue
            price = px[s].iloc[i]
            if pd.isna(price) or price <= 0:
                continue
            n_signals_seen += 1
            slot_size = equity / max_positions
            if slot_size > cash:
                continue
            shares = np.floor(slot_size / price) if whole_shares else slot_size / price
            if whole_shares and shares < 1:
                n_signals_too_small += 1
                continue
            cost_basis = shares * price
            cash -= cost_basis
            open_pos[s] = {"shares": shares, "entry_price": price, "cost_basis": cost_basis, "exit_i": i + hold_days}

    curve = equity_curve[start_i:]
    if len(curve) < 30:
        return None
    n_days = len(curve)
    years = n_days / 252.0
    total_return = curve[-1] / curve[0] - 1.0
    cagr = (curve[-1] / curve[0]) ** (1.0 / years) - 1.0 if years > 0 and curve[0] > 0 else float("nan")
    daily_rets = np.diff(curve) / curve[:-1]
    sharpe = (np.sqrt(252) * daily_rets.mean() / daily_rets.std(ddof=1)
              if daily_rets.std(ddof=1) > 0 else float("nan"))
    running_max = np.maximum.accumulate(curve)
    max_dd = float((curve / running_max - 1.0).min())
    win_rate = 100 * float(np.mean([r > 0 for r in trade_returns])) if trade_returns else float("nan")

    sample_idx = list(range(0, n_days, EQUITY_SAMPLE_EVERY)) + [n_days - 1]
    sample_dates = [str(d.date()) for d in dates[start_i:][sample_idx]]
    sample_values = [round(float(v), 2) for v in curve[sample_idx]]

    return PortfolioResult(
        strategy=strategy, tier=tier, hold_days=hold_days,
        n_trades=len(trade_returns),
        win_rate_pct=round(win_rate, 1),
        total_return_pct=round(100 * total_return, 1),
        cagr_pct=round(100 * cagr, 2) if np.isfinite(cagr) else None,
        max_drawdown_pct=round(100 * max_dd, 1),
        sharpe=round(float(sharpe), 2) if np.isfinite(sharpe) else None,
        final_equity=round(float(curve[-1]), 0),
        avg_positions_held=round(float(positions_held[start_i:].mean()), 1),
        capital=capital,
        signals_skipped_too_small_pct=round(100 * n_signals_too_small / n_signals_seen, 1) if n_signals_seen else 0.0,
        equity_dates=sample_dates, equity_values=sample_values,
    )


def _tier_inputs(tier: str) -> tuple[dict, pd.DataFrame, pd.DatetimeIndex] | None:
    bars, _ = load_tier_bars(UNIVERSES[tier])
    if len(bars) < 3:
        return None
    idx = None
    for df in bars.values():
        idx = df.index if idx is None else idx.union(df.index)
    idx = idx.sort_values()
    return bars, _aligned_closes(bars, idx), idx


def run_all(capital: float = STARTING_CAPITAL, tiers: tuple[str, ...] = tuple(UNIVERSES)) -> list[PortfolioResult]:
    results = []
    for tier in tiers:
        loaded = _tier_inputs(tier)
        if loaded is None:
            continue
        bars, px, idx = loaded
        for strat_name, mask_fn in STRATEGIES.items():
            mask = mask_fn(bars, idx)
            for hold_days in HOLD_DAYS_OPTIONS:
                r = simulate_portfolio(mask, px, COST_BPS[tier], hold_days, strat_name, tier, capital=capital)
                if r is not None:
                    results.append(r)
    return results


if __name__ == "__main__":
    results = run_all()
    with open("portfolio_sim_results.json", "w") as f:
        json.dump([asdict(r) for r in results], f)
    print(f"{len(results)} strategy x tier x hold_days combos simulated -> portfolio_sim_results.json")

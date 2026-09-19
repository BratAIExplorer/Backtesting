"""Quality buy-and-hold pilot -- a genuinely different discipline from the
swing-trading family in strategies/trend/ (see FINDINGS.md and Voyager-US.html
for that side). This is a first, explicitly preliminary backtest, NOT held to
the same statistical bar (HAC-t/DSR/sub-period stability) as the swing work,
because free fundamentals data (yfinance) only goes back ~5 annual reports per
stock -- there simply isn't enough history for that machinery to mean
anything. Treat this as a directional pilot, not a proven strategy.

Rules (mirrors the Greenblatt/quality-factor discussion, adapted to what the
free data can actually support):

  BUY  (quality AND cheap enough), checked at each stock's own annual-report
       availability date (fiscal year end + 60-day filing-lag buffer, to
       avoid using data before the market could have seen it):
         - net income > 0 AND free cash flow > 0   (profit is real, not paper)
         - ROE >= 15%                                (quality bar)
         - revenue grew YoY                          (growing, not shrinking)
         - debt/equity < 1                           (not overleveraged --
           known simplification: not sector-adjusted, so this may wrongly
           penalize banks/REITs/utilities; flagged, not fixed, in this pilot)
         - earnings yield (trailing EPS / price) >= 5%, i.e. P/E <= 20
           (the "don't overpay" check -- an absolute cutoff, not a full
           cross-sectional Magic-Formula rank, because the short history here
           makes cross-sectional ranking noisy)

  SELL (quality breaks), checked the same way, looser than the buy bar so a
       name isn't churned on a single soft quarter:
         - net income < 0, OR free cash flow < 0, OR ROE < 10%

  TRIM  if a position grows past 20% of the portfolio, sell it back to 10%
        (concentration risk control, not a profit cap)

  No fixed profit target, ever -- letting winners compound is the entire
  point of this discipline (see the brainstorm in FINDINGS.md #14).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from harness import data as hdata
from harness import fundamentals as hfund
from strategies.trend._common import UNIVERSES

TIERS = ("Large", "Mid", "Small")  # Penny excluded -- doesn't fit this discipline
REPORTING_LAG_DAYS = 60
ROE_BUY, ROE_SELL = 0.15, 0.10
MAX_DE = 1.0
MIN_EARNINGS_YIELD = 0.05  # P/E <= 20
TARGET_POSITIONS = 15
TRIM_ABOVE_PCT = 0.20
TRIM_TO_PCT = 0.10
STARTING_CAPITAL = 100_000.0

# Exit-rule variants -- see QUALITY_EXIT_TEST_REQUEST.md. V0 is the existing
# baseline (no profit target, compound until fundamental break). V1/V2 add a
# profit-target scale-out + a hard loss floor; buy-screen and fundamental-break
# logic above are untouched, per that request's scope limits.
SCALE_OUT_FRACTION = 0.5  # fraction of position sold on the first profit-target hit
EXIT_VARIANTS = {
    "V0": {"profit_target": None, "loss_floor": None, "exit_on_retrace": False},
    "V1": {"profit_target": 0.05, "loss_floor": -0.20, "exit_on_retrace": True},
    "V2": {"profit_target": 0.09, "loss_floor": -0.20, "exit_on_retrace": True},  # midpoint of requested 8-10% range
    # One permitted redesign (see QUALITY_EXIT_TEST_REQUEST.md stop rule): V1/V2's
    # retrace-exit killed compounding on the remainder. V3 takes the same partial
    # profit lock but lets the remainder ride to a fundamental break, like V0.
    "V3": {"profit_target": 0.08, "loss_floor": -0.20, "exit_on_retrace": False},
}
STALE_HOLD_DAYS = 126  # ~2 quarters of trading days


@dataclass
class StockEvent:
    date: pd.Timestamp
    action: str  # "buy_eligible" or "sell_required"


def _build_events(ticker: str, fund: pd.DataFrame, prices: pd.Series) -> list[StockEvent]:
    events = []
    fund = fund.sort_index()
    for i, (fy_end, row) in enumerate(fund.iterrows()):
        available = fy_end + pd.Timedelta(days=REPORTING_LAG_DAYS)
        px_at = prices.reindex([available], method="ffill").iloc[0] if not prices.empty else None
        ni, fcf, eq, debt, shares, rev = (row.get(k) for k in
            ("net_income", "fcf", "stockholders_equity", "total_debt", "shares_out", "revenue"))
        if pd.isna(ni) or pd.isna(eq) or eq <= 0:
            continue
        roe = ni / eq
        de = (debt / eq) if pd.notna(debt) else None
        prev_rev = fund["revenue"].iloc[i - 1] if i > 0 else None
        rev_growth = (rev / prev_rev - 1.0) if (prev_rev and pd.notna(prev_rev) and prev_rev > 0 and pd.notna(rev)) else None
        eps = (ni / shares) if (pd.notna(shares) and shares > 0) else None
        earnings_yield = (eps / px_at) if (eps is not None and px_at and px_at > 0) else None

        sell_required = (ni < 0) or (pd.notna(fcf) and fcf < 0) or (roe < ROE_SELL)
        buy_eligible = (
            ni > 0 and pd.notna(fcf) and fcf > 0 and roe >= ROE_BUY
            and rev_growth is not None and rev_growth > 0
            and (de is None or de < MAX_DE)
            and earnings_yield is not None and earnings_yield >= MIN_EARNINGS_YIELD
        )
        if sell_required:
            events.append(StockEvent(available, "sell_required"))
        elif buy_eligible:
            events.append(StockEvent(available, "buy_eligible"))
    return events


def run(tiers: tuple[str, ...] = TIERS, variant: str = "V0") -> dict:
    profit_target = EXIT_VARIANTS[variant]["profit_target"]
    loss_floor = EXIT_VARIANTS[variant]["loss_floor"]
    exit_on_retrace = EXIT_VARIANTS[variant]["exit_on_retrace"]
    symbols = sorted({s for t in tiers for s in UNIVERSES[t]})
    prices: dict[str, pd.Series] = {}
    events_by_symbol: dict[str, list[StockEvent]] = {}
    for sym in symbols:
        df = hdata.load_daily(sym, period="8y")
        if df is None or len(df) < 250:
            continue
        fund = hfund.load_annual_fundamentals(sym)
        if fund is None or len(fund) < 2:
            continue
        prices[sym] = df["Close"]
        events_by_symbol[sym] = _build_events(sym, fund, df["Close"])

    if not prices:
        return {"error": "no usable symbols"}

    common_index = None
    for s in prices.values():
        common_index = s.index if common_index is None else common_index.union(s.index)
    common_index = common_index.sort_values()
    px = pd.DataFrame({s: c.reindex(common_index).ffill() for s, c in prices.items()})

    # timeline of (date, symbol, action), nearest trading day
    timeline = []
    for sym, evs in events_by_symbol.items():
        for e in evs:
            pos = common_index.searchsorted(e.date)
            if pos < len(common_index):
                timeline.append((common_index[pos], sym, e.action))
    timeline.sort(key=lambda x: x[0])
    events_by_date: dict[pd.Timestamp, list[tuple[str, str]]] = {}
    for d, sym, action in timeline:
        events_by_date.setdefault(d, []).append((sym, action))

    cash = STARTING_CAPITAL
    shares_held: dict[str, float] = {}
    entry_price: dict[str, float] = {}
    entry_day: dict[str, int] = {}
    scaled_out: dict[str, bool] = {}
    first_trigger_day: dict[str, int | None] = {}  # first scale/floor/retrace/fundamental-sell per position
    trades: list[dict] = []  # realized exit events (excludes trims) -- win rate / avg win-loss / hold time
    stale_hold_days: list[int] = []  # hold length up to first trigger (or to end, if never triggered)
    n = len(common_index)
    equity_curve = np.empty(n)
    n_buys = n_sells = n_trims = n_profit_scale = n_floor_exits = 0

    def _mark_trigger(sym: str, day: int) -> None:
        if first_trigger_day[sym] is None:
            first_trigger_day[sym] = day
            stale_hold_days.append(day - entry_day[sym])

    def _close(sym: str, price: float, day: int, reason: str) -> None:
        nonlocal cash
        _mark_trigger(sym, day)
        cash += shares_held.pop(sym) * price
        trades.append({
            "sym": sym, "ret_pct": round(100 * (price / entry_price[sym] - 1.0), 2),
            "hold_days": day - entry_day[sym], "reason": reason,
        })
        entry_price.pop(sym)
        entry_day.pop(sym)
        scaled_out.pop(sym)
        first_trigger_day.pop(sym)

    for i, date in enumerate(common_index):
        # 1. profit-target scale-out / hard loss-floor check (V1/V2 only; no-op for V0)
        if profit_target is not None:
            for sym in list(shares_held):
                price = px[sym].iloc[i]
                if pd.isna(price) or price <= 0:
                    continue
                ret = price / entry_price[sym] - 1.0
                if ret <= loss_floor:
                    _close(sym, price, i, "loss_floor")
                    n_floor_exits += 1
                elif not scaled_out[sym] and ret >= profit_target:
                    _mark_trigger(sym, i)
                    sell_shares = shares_held[sym] * SCALE_OUT_FRACTION
                    shares_held[sym] -= sell_shares
                    cash += sell_shares * price
                    trades.append({
                        "sym": sym, "ret_pct": round(100 * ret, 2),
                        "hold_days": i - entry_day[sym], "reason": "profit_scale",
                    })
                    scaled_out[sym] = True
                    n_profit_scale += 1
                elif exit_on_retrace and scaled_out[sym] and ret < profit_target:
                    _close(sym, price, i, "profit_retrace")

        # 2. process fundamentals events due today
        for sym, action in events_by_date.get(date, []):
            price = px[sym].iloc[i]
            if pd.isna(price) or price <= 0:
                continue
            if action == "sell_required" and sym in shares_held:
                _close(sym, price, i, "fundamental_break")
                n_sells += 1
            elif action == "buy_eligible" and sym not in shares_held:
                mtm = sum(sh * px[s].iloc[i] for s, sh in shares_held.items() if pd.notna(px[s].iloc[i]))
                equity = cash + mtm
                slot = equity / TARGET_POSITIONS
                if slot <= cash and len(shares_held) < TARGET_POSITIONS * 2:  # soft cap, avoid runaway names
                    shares_held[sym] = slot / price
                    cash -= slot
                    entry_price[sym] = price
                    entry_day[sym] = i
                    scaled_out[sym] = False
                    first_trigger_day[sym] = None
                    n_buys += 1

        # 3. trim oversized winners
        mtm = sum(sh * px[s].iloc[i] for s, sh in shares_held.items() if pd.notna(px[s].iloc[i]))
        equity = cash + mtm
        if equity > 0:
            for sym in list(shares_held):
                price = px[sym].iloc[i]
                if pd.isna(price):
                    continue
                weight = shares_held[sym] * price / equity
                if weight > TRIM_ABOVE_PCT:
                    target_value = TRIM_TO_PCT * equity
                    sell_value = shares_held[sym] * price - target_value
                    sell_shares = sell_value / price
                    shares_held[sym] -= sell_shares
                    cash += sell_shares * price
                    n_trims += 1

        mtm = sum(sh * px[s].iloc[i] for s, sh in shares_held.items() if pd.notna(px[s].iloc[i]))
        equity_curve[i] = cash + mtm

    # positions still open at the end: no trigger fired yet -- count toward the stale metric
    for sym in shares_held:
        if first_trigger_day[sym] is None:
            stale_hold_days.append((n - 1) - entry_day[sym])
    stale_count = sum(1 for d in stale_hold_days if d > STALE_HOLD_DAYS)

    n_trades = len(trades)
    wins = [t["ret_pct"] for t in trades if t["ret_pct"] > 0]
    losses = [t["ret_pct"] for t in trades if t["ret_pct"] <= 0]
    win_rate = len(wins) / n_trades if n_trades else None
    avg_win_pct = round(sum(wins) / len(wins), 2) if wins else None
    avg_loss_pct = round(sum(losses) / len(losses), 2) if losses else None
    avg_hold_days = round(sum(t["hold_days"] for t in trades) / n_trades, 1) if n_trades else None

    years = n / 252.0
    total_return = equity_curve[-1] / equity_curve[0] - 1.0
    cagr = (equity_curve[-1] / equity_curve[0]) ** (1.0 / years) - 1.0
    daily_rets = np.diff(equity_curve) / equity_curve[:-1]
    sharpe = np.sqrt(252) * daily_rets.mean() / daily_rets.std(ddof=1) if daily_rets.std(ddof=1) > 0 else float("nan")
    running_max = np.maximum.accumulate(equity_curve)
    max_dd = float((equity_curve / running_max - 1.0).min())

    # matched base rate: equal-weight buy-and-hold of the SAME universe, bought day 1
    bh_symbols = [s for s in px.columns if px[s].notna().sum() > 0]
    bh_weights = STARTING_CAPITAL / len(bh_symbols)
    bh_shares = {s: bh_weights / px[s].bfill().iloc[0] for s in bh_symbols}
    bh_curve = sum(sh * px[s].ffill().bfill() for s, sh in bh_shares.items()).to_numpy()
    bh_cagr = (bh_curve[-1] / bh_curve[0]) ** (1.0 / years) - 1.0
    bh_dd = float((bh_curve / np.maximum.accumulate(bh_curve) - 1.0).min())

    sample_idx = list(range(0, n, 10)) + [n - 1]
    return {
        "variant": variant,
        "profit_target_pct": round(100 * profit_target, 1) if profit_target else None,
        "loss_floor_pct": round(100 * loss_floor, 1) if loss_floor else None,
        "n_symbols_used": len(prices),
        "n_buys": n_buys, "n_sells": n_sells, "n_trims": n_trims,
        "n_profit_scale_outs": n_profit_scale, "n_floor_exits": n_floor_exits,
        "n_trades": n_trades, "win_rate": round(win_rate, 3) if win_rate is not None else None,
        "avg_win_pct": avg_win_pct, "avg_loss_pct": avg_loss_pct, "avg_hold_days": avg_hold_days,
        "stale_positions_gt_2q": stale_count,
        "cagr_pct": round(100 * cagr, 2),
        "sharpe": round(float(sharpe), 2) if np.isfinite(sharpe) else None,
        "max_drawdown_pct": round(100 * max_dd, 1),
        "total_return_pct": round(100 * total_return, 1),
        "final_equity": round(float(equity_curve[-1]), 0),
        "benchmark_equal_weight_bh_cagr_pct": round(100 * bh_cagr, 2),
        "benchmark_equal_weight_bh_max_dd_pct": round(100 * bh_dd, 1),
        "equity_dates": [str(common_index[j].date()) for j in sample_idx],
        "equity_values": [round(float(v), 2) for v in equity_curve[sample_idx]],
        "benchmark_values": [round(float(v), 2) for v in bh_curve[sample_idx]],
    }


if __name__ == "__main__":
    results = {v: run(variant=v) for v in EXIT_VARIANTS}
    with open("quality_bh_results.json", "w") as f:
        json.dump(results, f, indent=2)
    summary_keys = (
        "variant", "profit_target_pct", "loss_floor_pct", "n_trades", "win_rate",
        "avg_win_pct", "avg_loss_pct", "avg_hold_days", "stale_positions_gt_2q",
        "cagr_pct", "sharpe", "max_drawdown_pct", "benchmark_equal_weight_bh_cagr_pct",
    )
    print(json.dumps({v: {k: r[k] for k in summary_keys} for v, r in results.items()}, indent=2))

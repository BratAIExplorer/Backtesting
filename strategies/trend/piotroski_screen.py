"""LIVE SCREEN ONLY — NOT A BACKTEST. Scores today's NIFTY 50 stocks with
today's Piotroski F-Score (0-9, higher = stronger fundamentals) using
yfinance's current financial statements.

Why no backtest: F-Score needs fundamentals as they were known at each past
rebalance date. yfinance only exposes a company's last ~4-5 quarters of
financials as they stand *today* (restated for splits, corrections, etc.),
not a point-in-time snapshot from e.g. 2022. Scoring the past with today's
restated numbers is look-ahead bias — see backtest_lowvol.py's docstring and
CURRENT_STATUS.md for why this project treats that as a hard no. Point-in-time
fundamentals (needed for an honest backtest) would require a paid data vendor
(e.g. a fundamentals API with as-reported history) — out of scope until that
exists.

Use this output for idea generation only ("what looks fundamentally strong
right now"), never as evidence the F-Score predicts returns on this universe.

Usage:
    python -m backend.tools.piotroski_screen
"""
from __future__ import annotations

import sys

import yfinance as yf

from .backtest_trend import NIFTY_50


def _safe(series, key, default=None):
    try:
        val = series.get(key)
        return None if val is None else float(val)
    except Exception:
        return default


def piotroski_score(symbol: str) -> dict | None:
    ticker = yf.Ticker(f"{symbol}.NS")
    try:
        fin = ticker.financials
        bs = ticker.balance_sheet
        cf = ticker.cashflow
    except Exception as e:
        print(f"  skipping {symbol}: {e}", file=sys.stderr)
        return None
    if fin.empty or bs.empty or cf.empty or fin.shape[1] < 2 or bs.shape[1] < 2:
        return None

    curr, prev = fin.columns[0], fin.columns[1]
    bs_curr, bs_prev = bs.columns[0], bs.columns[1]

    net_income = _safe(fin[curr], "Net Income")
    net_income_prev = _safe(fin[prev], "Net Income")
    total_assets = _safe(bs[bs_curr], "Total Assets")
    total_assets_prev = _safe(bs[bs_prev], "Total Assets")
    op_cashflow = _safe(cf[cf.columns[0]], "Operating Cash Flow") or _safe(cf[cf.columns[0]], "Total Cash From Operating Activities")
    long_term_debt = _safe(bs[bs_curr], "Long Term Debt") or 0.0
    long_term_debt_prev = _safe(bs[bs_prev], "Long Term Debt") or 0.0
    current_assets = _safe(bs[bs_curr], "Current Assets")
    current_liab = _safe(bs[bs_curr], "Current Liabilities")
    current_assets_prev = _safe(bs[bs_prev], "Current Assets")
    current_liab_prev = _safe(bs[bs_prev], "Current Liabilities")
    shares_out = _safe(bs[bs_curr], "Ordinary Shares Number")
    shares_out_prev = _safe(bs[bs_prev], "Ordinary Shares Number")
    revenue = _safe(fin[curr], "Total Revenue")
    revenue_prev = _safe(fin[prev], "Total Revenue")
    gross_profit = _safe(fin[curr], "Gross Profit")
    gross_profit_prev = _safe(fin[prev], "Gross Profit")

    if None in (net_income, total_assets, total_assets_prev):
        return None  # not enough disclosed to score honestly — skip rather than guess

    score = 0
    signals = {}

    roa = net_income / total_assets if total_assets else None
    signals["profitable"] = roa is not None and roa > 0
    signals["positive_op_cashflow"] = op_cashflow is not None and op_cashflow > 0
    roa_prev = (net_income_prev / total_assets_prev) if (net_income_prev is not None and total_assets_prev) else None
    signals["roa_improving"] = roa is not None and roa_prev is not None and roa > roa_prev
    signals["cashflow_beats_earnings"] = op_cashflow is not None and net_income is not None and op_cashflow > net_income

    leverage_down = long_term_debt <= long_term_debt_prev
    signals["leverage_decreasing"] = leverage_down
    curr_ratio = (current_assets / current_liab) if (current_assets and current_liab) else None
    curr_ratio_prev = (current_assets_prev / current_liab_prev) if (current_assets_prev and current_liab_prev) else None
    signals["current_ratio_improving"] = curr_ratio is not None and curr_ratio_prev is not None and curr_ratio > curr_ratio_prev
    signals["no_new_shares_issued"] = shares_out is not None and shares_out_prev is not None and shares_out <= shares_out_prev

    gm = (gross_profit / revenue) if (gross_profit and revenue) else None
    gm_prev = (gross_profit_prev / revenue_prev) if (gross_profit_prev and revenue_prev) else None
    signals["gross_margin_improving"] = gm is not None and gm_prev is not None and gm > gm_prev
    asset_turnover = (revenue / total_assets) if (revenue and total_assets) else None
    asset_turnover_prev = (revenue_prev / total_assets_prev) if (revenue_prev and total_assets_prev) else None
    signals["asset_turnover_improving"] = asset_turnover is not None and asset_turnover_prev is not None and asset_turnover > asset_turnover_prev

    score = sum(1 for v in signals.values() if v)
    n_scored = sum(1 for v in signals.values() if v is not None)
    return {"symbol": symbol, "f_score": score, "signals_available": n_scored, "signals": signals}


def run(symbols: list[str] = NIFTY_50) -> list[dict]:
    results = []
    for symbol in symbols:
        result = piotroski_score(symbol)
        if result:
            results.append(result)
    return sorted(results, key=lambda r: r["f_score"], reverse=True)


if __name__ == "__main__":
    print("LIVE Piotroski F-Score screen — current fundamentals only, NOT backtested.\n")
    print("See module docstring for why: yfinance has no point-in-time fundamentals.\n")
    for r in run():
        print(f"  {r['symbol']:12s} F-Score: {r['f_score']}/9  (of {r['signals_available']} signals available)")

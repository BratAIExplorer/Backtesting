"""Cached annual fundamentals loader (yfinance free tier only gives ~5 years
of annual financials/balance-sheet/cashflow -- much thinner than the 8y of
daily bars everything else in this repo uses). Built for the quality
buy-and-hold pilot in strategies/quality/ -- NOT held to the same statistical
bar as the swing-strategy harness, because there simply isn't enough history
for HAC-t/DSR to mean anything on 3-4 annual data points per stock.
"""
from __future__ import annotations

import io
import json
import os
import time

import pandas as pd
import yfinance as yf

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache", "fundamentals")
os.makedirs(CACHE_DIR, exist_ok=True)


def _path(ticker: str) -> str:
    return os.path.join(CACHE_DIR, f"{ticker}.json")


def load_annual_fundamentals(ticker: str, ttl_days: float = 30.0) -> pd.DataFrame | None:
    """Returns a DataFrame indexed by fiscal-year-end date with columns:
    net_income, revenue, fcf, stockholders_equity, total_debt, shares_out.
    `available_date` (fiscal_year_end + REPORTING_LAG_DAYS) is added by the
    caller, not here, since that's a backtest-timing concern, not a data one.
    """
    path = _path(ticker)
    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < ttl_days * 86400:
        with open(path) as f:
            raw = json.load(f)
        if raw is None:
            return None
        df = pd.read_json(io.StringIO(raw), orient="split")
        df.index = pd.to_datetime(df.index)
        return df

    try:
        t = yf.Ticker(ticker)
        fin, bal, cf = t.financials, t.balance_sheet, t.cashflow
        if fin.empty or bal.empty or cf.empty:
            with open(path, "w") as f:
                json.dump(None, f)
            return None

        def row(df: pd.DataFrame, name: str) -> pd.Series:
            return df.loc[name] if name in df.index else pd.Series(dtype=float)

        out = pd.DataFrame({
            "net_income": row(fin, "Net Income"),
            "revenue": row(fin, "Total Revenue"),
            "fcf": row(cf, "Free Cash Flow"),
            "stockholders_equity": row(bal, "Stockholders Equity"),
            "total_debt": row(bal, "Total Debt"),
            "shares_out": row(bal, "Ordinary Shares Number"),
        }).dropna(how="all")
        out = out.sort_index()

        with open(path, "w") as f:
            json.dump(out.to_json(orient="split", date_format="iso"), f)
        return out
    except Exception as e:
        print(f"  fundamentals fetch failed for {ticker}: {e}")
        with open(path, "w") as f:
            json.dump(None, f)
        return None

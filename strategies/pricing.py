"""
Free public price data + simple technical signals — deliberately NOT pulled
from Zerodha's paid Kite Connect feed. Uses Yahoo Finance via yfinance, which
is free and needs no API key.

Indian tickers need an exchange suffix for Yahoo: ".NS" for NSE, ".BO" for BSE.

Everything here is descriptive, not predictive: RSI and MACD are standard,
well-known formulas computed off ~1 year of daily closes. classify_trend()
turns them into one plain-language word — it is a fixed rule table, not a
model, and it is never a buy/sell instruction.

# ponytail: this is a copy of FinFlow/backend/pricing.py (the live bot's
# module), pinned here so strategies/trend/*.py and tests/test_backtest_*.py
# have something to import after the trend code was migrated out of FinFlow.
# It is NOT auto-synced — if FinFlow/backend/pricing.py changes, re-copy it
# here, or the drift tripwire in test_backtest_trend.py stops meaning anything.
"""
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import yfinance as yf

_EXCHANGE_SUFFIX = {"NSE": ".NS", "BSE": ".BO"}


@dataclass
class PriceSignals:
    last_price: Optional[float]
    week52_high: Optional[float]
    week52_low: Optional[float]
    rsi_14: Optional[float]
    macd_hist: Optional[float]


def _yahoo_symbol(symbol: str, exchange: str) -> str:
    suffix = _EXCHANGE_SUFFIX.get(exchange.upper(), ".NS")
    return f"{symbol}{suffix}"


def fetch_daily_history(symbol: str, exchange: str, period: str = "1y") -> pd.DataFrame:
    """Raises ValueError if Yahoo has no data for this symbol (e.g. delisted,
    or the exchange suffix guess was wrong) — callers should show 'price
    unavailable' for that one stock rather than failing the whole sync."""
    ticker = _yahoo_symbol(symbol, exchange)
    df = yf.Ticker(ticker).history(period=period, interval="1d")
    if df.empty:
        raise ValueError(f"No price history found for {ticker}")
    return df


def compute_rsi(closes: pd.Series, period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    last_gain, last_loss = avg_gain.iloc[-1], avg_loss.iloc[-1]
    if pd.isna(last_gain) or pd.isna(last_loss):
        return None
    if last_loss == 0:
        return 100.0 if last_gain > 0 else 50.0  # no losses at all in the window: max strength, or flat if no moves either

    rs = last_gain / last_loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi), 1)


def compute_macd_hist(closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[float]:
    if len(closes) < slow + signal:
        return None
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    value = hist.iloc[-1]
    return round(float(value), 3) if pd.notna(value) else None


def compute_signals(symbol: str, exchange: str) -> PriceSignals:
    df = fetch_daily_history(symbol, exchange)
    closes = df["Close"]
    return PriceSignals(
        last_price=round(float(closes.iloc[-1]), 2),
        week52_high=round(float(closes.max()), 2),
        week52_low=round(float(closes.min()), 2),
        rsi_14=compute_rsi(closes),
        macd_hist=compute_macd_hist(closes),
    )


@dataclass
class CompanyMeta:
    company_name: Optional[str]
    sector: Optional[str]
    cap_tier: Optional[str]  # "Large" | "Mid" | "Small" | "Penny"


# SEBI-style buckets, in INR. Yahoo reports marketCap for .NS/.BO tickers in INR.
#   Large: >= ₹20,000 Cr   Mid: >= ₹5,000 Cr   Small: >= ₹500 Cr   else Penny
_CAP_TIERS = (
    (20_000e7, "Large"),
    (5_000e7, "Mid"),
    (500e7, "Small"),
)


def _cap_tier(market_cap: Optional[float]) -> Optional[str]:
    if not market_cap or market_cap <= 0:
        return None
    for threshold, name in _CAP_TIERS:
        if market_cap >= threshold:
            return name
    return "Penny"


def fetch_company_meta(symbol: str, exchange: str) -> CompanyMeta:
    """Best-effort company classification from Yahoo's .info blob. Yahoo's
    `.info` is slower and flakier than price history, so every field falls
    back to None and callers must treat a bare CompanyMeta(None, None, None)
    as normal — the sync should not fail because classification is missing."""
    try:
        info = yf.Ticker(_yahoo_symbol(symbol, exchange)).info or {}
    except Exception:
        return CompanyMeta(None, None, None)
    name = info.get("longName") or info.get("shortName")
    return CompanyMeta(
        company_name=name.strip() if isinstance(name, str) else None,
        sector=(info.get("sector") or None),
        cap_tier=_cap_tier(info.get("marketCap")),
    )


def classify_trend(rsi_14: Optional[float], macd_hist: Optional[float]) -> dict:
    """Returns {"label": str, "strength": 1|2, "direction": "up"|"down"|"flat"}.
    Fixed rule table — not a prediction, not investment advice:

      Very Bullish : RSI >= 60 AND MACD histogram clearly positive
      Bullish      : RSI >= 55 OR  MACD histogram positive
      Neutral      : everything in between
      Bearish      : RSI <= 45 OR  MACD histogram negative
      Very Bearish : RSI <= 40 AND MACD histogram clearly negative
    """
    if rsi_14 is None or macd_hist is None:
        return {"label": "Unknown", "strength": 0, "direction": "flat"}

    strong_macd_up = macd_hist > 0.5
    strong_macd_down = macd_hist < -0.5

    if rsi_14 >= 60 and strong_macd_up:
        return {"label": "Very Bullish", "strength": 2, "direction": "up"}
    if rsi_14 >= 55 or macd_hist > 0:
        return {"label": "Bullish", "strength": 1, "direction": "up"}
    if rsi_14 <= 40 and strong_macd_down:
        return {"label": "Very Bearish", "strength": 2, "direction": "down"}
    if rsi_14 <= 45 or macd_hist < 0:
        return {"label": "Bearish", "strength": 1, "direction": "down"}
    return {"label": "Neutral", "strength": 0, "direction": "flat"}

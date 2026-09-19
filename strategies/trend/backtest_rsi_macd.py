"""RSI + MACD combo, US equities, across 4 cap tiers.

Rule (pre-registered — the exact combo the user asked to test): in an
uptrend, wait for the MACD line to cross above its signal line (a fresh
bullish crossover, not just "MACD positive") AND RSI14 > 50 (momentum
confirmation) on the same day.
  uptrend  = Close > SMA200
  cross    = MACD line was <= signal line yesterday, > signal line today
  confirm  = RSI14 > 50
  entry    = close of the signal day
  exit     = close N trading days later

Two lagging trend indicators built off the same price series are usually
redundant rather than additive — this is the a-priori expectation, not a
foregone conclusion, hence testing it properly rather than assuming.

Graded against the tier's own matched base rate, same HAC/bootstrap/cost
machinery as the rest of this family.
"""
from __future__ import annotations

import pandas as pd

from ._common import HORIZONS, TierResult, UNIVERSES, grade_tier, load_tier_bars, print_report


def rsi_series(closes: pd.Series, period: int = 14) -> pd.Series:
    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return (100 - 100 / (1 + rs)).where(loss != 0, 100.0)


def macd_lines(closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series]:
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def _events_for_symbol(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    closes = df["Close"]
    sma200 = closes.rolling(200).mean()
    rsi = rsi_series(closes)
    macd_line, signal_line = macd_lines(closes)

    uptrend = closes > sma200
    was_below = (macd_line.shift(1) <= signal_line.shift(1))
    fresh_cross = was_below & (macd_line > signal_line)
    combo = uptrend & fresh_cross & (rsi > 50)

    n = len(df)
    events, base_pool = [], []
    for i in range(200, n):
        if not bool(uptrend.iloc[i]) or pd.isna(macd_line.iloc[i]) or pd.isna(signal_line.iloc[i]):
            continue
        row = {}
        p0 = closes.iloc[i]
        for h in HORIZONS:
            row[h] = float(closes.iloc[i + h] / p0 - 1.0) if i + h < n else None
        base_pool.append(row)
        if bool(combo.iloc[i]):
            events.append(row)
    return events, base_pool


def run_tier(tier: str, symbols: list[str]) -> TierResult:
    bars, n_skipped = load_tier_bars(symbols)
    events, base_pool = [], []
    for df in bars.values():
        ev, base = _events_for_symbol(df)
        events.extend(ev)
        base_pool.extend(base)
    return grade_tier(tier, len(symbols), n_skipped, events, base_pool)


def run_all() -> list[TierResult]:
    return [run_tier(tier, syms) for tier, syms in UNIVERSES.items()]


if __name__ == "__main__":
    print_report(run_all())

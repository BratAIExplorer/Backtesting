"""Systematic universe construction — replaces the hand-picked ticker lists
in _common.UNIVERSES that every strategy script used through FINDINGS.md §11.

Source of candidates (real, free, public — no ticker chosen by judgment):
  Large  -> S&P 500 constituents (Wikipedia)
  Mid    -> S&P 400 constituents (Wikipedia)
  Small  -> S&P 600 constituents (Wikipedia)
  Penny  -> NASDAQ-listed symbol directory (nasdaqtrader.com), filtered to
            price < $5 after a bulk price pull — there's no official "penny
            stock index," so this tier is built bottom-up from price alone.

Then every tier is filtered the same way (liquidity + volatility bands), so
"Large" etc. means something objective, not "names I recognized":
  - avg dollar volume (20d) >= MIN_DOLLAR_VOLUME  (must be fillable)
  - ATR% (14d, as % of price) inside [MIN_ATR_PCT, MAX_ATR_PCT]
    (excludes both dead stocks and stocks so violent they break the cost
    model everything else in this project assumes)

Practical compromise, stated plainly: candidate pools (500/400/600/~5600
names) are far too large to bulk-download and screen in full within this
harness's rate limits, so each pool is seeded-randomly sampled down to
SAMPLE_SIZE candidates *before* screening, not screened in full. This is a
real sample of the real index, not a hand-picked one — but it is a sample,
not a census. Increase SAMPLE_SIZE to widen the search at the cost of
runtime.
"""
from __future__ import annotations

import io
import random
import urllib.request

import numpy as np
import pandas as pd

from harness import data as hdata

SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
SP400_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"
SP600_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"

SEED = 20260917  # fixed seed: reproducible sample, not re-rolled per run
SAMPLE_SIZE = {"Large": 60, "Mid": 50, "Small": 45, "Penny": 150}
TARGET_COUNT = {"Large": 30, "Mid": 25, "Small": 20, "Penny": 15}  # after screening

MIN_DOLLAR_VOLUME = {"Large": 50_000_000, "Mid": 10_000_000, "Small": 2_000_000, "Penny": 500_000}
ATR_PCT_BAND = {  # (min, max) 14-day ATR as % of price — excludes dead & excludes chaos
    "Large": (0.010, 0.06), "Mid": (0.015, 0.08), "Small": (0.02, 0.10), "Penny": (0.02, 0.20),
}


def _fetch_wiki_symbols(url: str, symbol_col: str = "Symbol") -> list[str]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 research"})
    html = urllib.request.urlopen(req, timeout=30).read()
    for t in pd.read_html(io.BytesIO(html)):
        if symbol_col in t.columns:
            return [str(s).replace(".", "-") for s in t[symbol_col].tolist()]  # BRK.B -> BRK-B for yfinance
    raise ValueError(f"no table with column {symbol_col!r} at {url}")


def _fetch_nasdaq_listed() -> list[str]:
    req = urllib.request.Request(NASDAQ_LISTED_URL, headers={"User-Agent": "Mozilla/5.0 research"})
    text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    rows = [line.split("|") for line in text.splitlines()[1:-1]]  # header + trailer line
    out = []
    for r in rows:
        if len(r) < 4:
            continue
        symbol, _name, _market, test_issue = r[0], r[1], r[2], r[3]
        etf = r[6] if len(r) > 6 else "N"
        if test_issue == "N" and etf == "N" and symbol.isascii() and symbol.isalpha():
            out.append(symbol)
    return out


def candidate_pool(tier: str) -> list[str]:
    if tier == "Large":
        pool = _fetch_wiki_symbols(SP500_URL)
    elif tier == "Mid":
        pool = _fetch_wiki_symbols(SP400_URL)
    elif tier == "Small":
        pool = _fetch_wiki_symbols(SP600_URL)
    elif tier == "Penny":
        pool = _fetch_nasdaq_listed()
    else:
        raise ValueError(tier)
    rng = random.Random(SEED)
    rng.shuffle(pool)
    return pool[: SAMPLE_SIZE[tier]]


def _atr_pct(df: pd.DataFrame, period: int = 14) -> float | None:
    high, low, close = df["High"], df["Low"], df["Close"]
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    last_close = close.iloc[-1]
    if pd.isna(atr) or pd.isna(last_close) or last_close <= 0:
        return None
    return float(atr / last_close)


def screen_tier(tier: str) -> dict:
    """Returns {"symbols": [...], "n_candidates": int, "n_passed": int,
    "rejected": {symbol: reason}} — every rejection is logged, not silently
    dropped, so the screen is auditable."""
    candidates = candidate_pool(tier)
    lo_atr, hi_atr = ATR_PCT_BAND[tier]
    min_dv = MIN_DOLLAR_VOLUME[tier]

    passed, rejected = [], {}
    for sym in candidates:
        df = hdata.load_daily(sym, period="8y")
        if df is None or len(df) < 260:
            rejected[sym] = "no/insufficient price history"
            continue
        last_price = float(df["Close"].iloc[-1])
        if tier == "Penny" and last_price >= 5.0:
            rejected[sym] = f"price ${last_price:.2f} not a penny stock"
            continue
        if tier != "Penny" and last_price < 5.0:
            rejected[sym] = f"price ${last_price:.2f} too low for {tier}"
            continue
        dollar_vol = float((df["Close"] * df["Volume"]).tail(20).mean())
        if dollar_vol < min_dv:
            rejected[sym] = f"avg $ volume {dollar_vol:,.0f} below {min_dv:,.0f} floor"
            continue
        atr_pct = _atr_pct(df)
        if atr_pct is None:
            rejected[sym] = "ATR undefined (too little data)"
            continue
        if not (lo_atr <= atr_pct <= hi_atr):
            rejected[sym] = f"ATR% {atr_pct:.3f} outside [{lo_atr},{hi_atr}] band"
            continue
        passed.append(sym)
        if len(passed) >= TARGET_COUNT[tier]:
            break

    return {"symbols": passed, "n_candidates": len(candidates), "n_passed": len(passed), "rejected": rejected}


def build_universes() -> dict[str, list[str]]:
    return {tier: screen_tier(tier)["symbols"] for tier in ("Large", "Mid", "Small", "Penny")}


if __name__ == "__main__":
    import json
    for tier in ("Large", "Mid", "Small", "Penny"):
        result = screen_tier(tier)
        print(f"\n=== {tier}: {result['n_passed']}/{result['n_candidates']} candidates passed ===")
        print(result["symbols"])
        n_show = 5
        sample_rejections = dict(list(result["rejected"].items())[:n_show])
        print(f"(sample rejections, {len(result['rejected'])} total): {json.dumps(sample_rejections, indent=2)}")

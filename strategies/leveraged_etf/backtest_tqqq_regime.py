"""Backtest of the Malik/KINFO TQQQ+SQQQ trend/momentum system (50/250 SMA
regime filter + ROC acceleration trim, per the YouTube interview transcript).

Fixes over the naive first draft:

1. Financing drag scales with leverage and the actual risk-free rate, not a
   flat constant. A 3x fund borrows ~2x notional; that cost tracks T-bill
   yield (near 0% 2010-2021, ~5% 2022-2023). ^IRX (13-week T-bill, back to
   1960) supplies the daily rate; expense ratio (0.95%/yr) is added on top.
2. Slippage: 15bps charged on any day the weight changes, to price the
   spread cost of actually trading TQQQ/SQQQ at the close.
3. Cash earns the risk-free rate instead of 0% while the strategy is flat —
   otherwise "de-risking" periods look artificially worse than holding T-bills.
4. Real out-of-sample check, not a synthetic split: TQQQ/SQQQ didn't exist
   before Feb 2010, so pre-2010 returns are synthesized from ^NDX (documented
   as approximate); from 2010-02-11 onward this uses the ACTUAL TQQQ/SQQQ
   adjusted-close series. The strategy's rule table (50/250 SMA, ROC trim) is
   fixed from the interview, never fit on this data, so the post-2010 real-ETF
   segment is a genuine out-of-sample test, not a re-fit.
   Sharpe is also run through deflated_sharpe_ratio (harness/stats.py) against
   n_trials=350 (Malik's own stated search size) — the honest way to ask "does
   this survive having been one of 350 things tried," instead of trusting the
   raw Sharpe at face value.

Usage:
    python -m strategies.leveraged_etf.backtest_tqqq_regime
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from harness import data as harness_data
from harness import stats as harness_stats

EXPENSE_DRAG_ANNUAL = 0.0095      # TQQQ/SQQQ stated expense ratio
LEVERAGE = 3
BORROW_MULTIPLE = LEVERAGE - 1    # a 3x fund finances ~2x notional
SLIPPAGE_BPS = 0.0015             # per-trade cost on any day weight changes
SPLICE_DATE = "2010-02-11"        # first real TQQQ/SQQQ bar


def _daily_rf(irx_close: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """^IRX quotes an annualized T-bill discount yield in percent. Reindex onto
    the strategy's trading calendar and convert to a per-day rate."""
    rf = (irx_close / 100.0).reindex(index, method="ffill").bfill()
    return rf / 252.0


def build_synthetic_leverage(ndx_ret: pd.Series, daily_rf: pd.Series) -> tuple[pd.Series, pd.Series]:
    """3x long / -3x short daily-reset returns with leverage- and rate-aware
    financing drag (replaces the old flat 0.0095/252 constant)."""
    drag = EXPENSE_DRAG_ANNUAL / 252.0 + BORROW_MULTIPLE * daily_rf
    tqqq_sim = LEVERAGE * ndx_ret - drag
    sqqq_sim = -LEVERAGE * ndx_ret - drag
    return tqqq_sim, sqqq_sim


def compute_signal(ndx: pd.Series) -> pd.DataFrame:
    """50/250 SMA regime filter + 20-day ROC acceleration trim, exactly as
    described in the interview. Weights are shifted 1 day to trade at the
    next close, no lookahead."""
    sma_50 = ndx.rolling(50).mean()
    sma_250 = ndx.rolling(250).mean()
    roc_20 = ndx.pct_change(20)
    roc_accel = roc_20 - roc_20.shift(5)

    bull = (ndx > sma_50) & (ndx > sma_250)
    weak_bull = (ndx > sma_250) & (ndx <= sma_50)
    bear = ndx < sma_250

    tqqq_w = pd.Series(0.0, index=ndx.index)
    sqqq_w = pd.Series(0.0, index=ndx.index)
    tqqq_w[bull & (roc_accel >= 0)] = 1.00
    tqqq_w[bull & (roc_accel < 0)] = 0.30
    tqqq_w[weak_bull] = 0.15
    sqqq_w[bear & (roc_20 < -0.05)] = 0.30

    return pd.DataFrame({
        "tqqq_w": tqqq_w.shift(1),
        "sqqq_w": sqqq_w.shift(1),
    })


def compute_signal_sma250_only(ndx: pd.Series) -> pd.DataFrame:
    """Simplest possible version: 100% TQQQ above the 250-day SMA, 100% cash
    below it. No 50-day SMA, no ROC trim, no SQQQ short — the classic Meb
    Faber-style single-rule filter, to check whether Malik's extra rules (trim,
    weak-bull sizing, short leg) are earning their complexity or just curve-fit."""
    sma_250 = ndx.rolling(250).mean()
    tqqq_w = pd.Series(0.0, index=ndx.index)
    tqqq_w[ndx > sma_250] = 1.00
    return pd.DataFrame({
        "tqqq_w": tqqq_w.shift(1),
        "sqqq_w": pd.Series(0.0, index=ndx.index),
    })


def run_backtest(signal_fn=compute_signal) -> pd.DataFrame:
    ndx_df = harness_data.load_daily("^NDX", period="max", ttl_days=7.0)
    tqqq_df = harness_data.load_daily("TQQQ", period="max", ttl_days=7.0)
    sqqq_df = harness_data.load_daily("SQQQ", period="max", ttl_days=7.0)
    irx_df = harness_data.load_daily("^IRX", period="max", ttl_days=7.0)
    if ndx_df is None or tqqq_df is None or sqqq_df is None or irx_df is None:
        raise RuntimeError("data fetch failed for one of ^NDX/TQQQ/SQQQ/^IRX")

    ndx = ndx_df["Close"].dropna()
    weights = signal_fn(ndx)

    ndx_ret = ndx.pct_change()
    daily_rf = _daily_rf(irx_df["Close"], ndx.index)
    tqqq_sim, sqqq_sim = build_synthetic_leverage(ndx_ret, daily_rf)

    # Splice in real ETF returns from launch onward (auto_adjust=True closes
    # already include dividends, so pct_change is total return).
    tqqq_real_ret = tqqq_df["Close"].pct_change()
    sqqq_real_ret = sqqq_df["Close"].pct_change()
    splice = pd.Timestamp(SPLICE_DATE)
    tqqq_ret = tqqq_sim.copy()
    sqqq_ret = sqqq_sim.copy()
    real_idx = tqqq_ret.index[tqqq_ret.index >= splice]
    tqqq_ret.loc[real_idx] = tqqq_real_ret.reindex(real_idx)
    sqqq_ret.loc[real_idx] = sqqq_real_ret.reindex(real_idx)

    df = pd.DataFrame({
        "ndx_ret": ndx_ret,
        "tqqq_ret": tqqq_ret,
        "sqqq_ret": sqqq_ret,
        "rf": daily_rf,
        "tqqq_w": weights["tqqq_w"],
        "sqqq_w": weights["sqqq_w"],
    }).dropna(subset=["ndx_ret", "tqqq_ret", "sqqq_ret", "tqqq_w", "sqqq_w"])

    cash_w = 1.0 - df["tqqq_w"] - df["sqqq_w"]
    weight_turnover = (df["tqqq_w"].diff().abs().fillna(0) + df["sqqq_w"].diff().abs().fillna(0))
    slippage_cost = weight_turnover * SLIPPAGE_BPS

    df["strat_ret"] = (df["tqqq_w"] * df["tqqq_ret"] + df["sqqq_w"] * df["sqqq_ret"]
                       + cash_w * df["rf"] - slippage_cost)
    df["equity_strat"] = (1 + df["strat_ret"]).cumprod()
    df["equity_ndx"] = (1 + df["ndx_ret"]).cumprod()
    df["equity_tqqq_hold"] = (1 + df["tqqq_ret"]).cumprod()
    return df


def _metrics(equity: pd.Series, returns: pd.Series) -> dict:
    n = len(equity)
    cagr = float(equity.iloc[-1] ** (252 / n) - 1) if n and equity.iloc[-1] > 0 else float("nan")
    max_dd = float((equity / equity.cummax() - 1).min())
    sharpe = harness_stats.annualized_sharpe(returns)
    return {"CAGR": cagr, "MaxDD": max_dd, "Sharpe": sharpe}


def summarize(df: pd.DataFrame, label: str) -> dict:
    m_strat = _metrics(df["equity_strat"] / df["equity_strat"].iloc[0], df["strat_ret"])
    m_ndx = _metrics(df["equity_ndx"] / df["equity_ndx"].iloc[0], df["ndx_ret"])
    m_tqqq = _metrics(df["equity_tqqq_hold"] / df["equity_tqqq_hold"].iloc[0], df["tqqq_ret"])
    return {"segment": label, "n_days": len(df), "strategy": m_strat, "ndx_hold": m_ndx, "tqqq_hold": m_tqqq}


def print_summary(s: dict) -> None:
    print(f"\n=== {s['segment']} ({s['n_days']} trading days) ===")
    print(f"{'Metric':<10}{'Strategy':<15}{'NDX Hold':<15}{'TQQQ Hold':<15}")
    for k in ("CAGR", "MaxDD", "Sharpe"):
        a, b, c = s["strategy"][k], s["ndx_hold"][k], s["tqqq_hold"][k]
        if k == "Sharpe":
            print(f"{k:<10}{a:<15.2f}{b:<15.2f}{c:<15.2f}")
        else:
            print(f"{k:<10}{a*100:<14.2f}%{b*100:<14.2f}%{c*100:<14.2f}%")


def print_deflated_sharpe(post: pd.DataFrame, n_trials: int, label: str) -> None:
    from scipy import stats as _sps
    r = post["strat_ret"].dropna().values
    sr = r.mean() / r.std(ddof=1)
    dsr, sr0 = harness_stats.deflated_sharpe_ratio(
        sr=sr, n_obs=len(r), skew=float(_sps.skew(r)), kurt=float(_sps.kurtosis(r, fisher=False)),
        n_trials=n_trials, sr_std=sr * 0.5,  # sr_std unknown without the other trials; 0.5x sr is a rough floor
    )
    print(f"\nDeflated Sharpe ({label}, vs {n_trials}-trial search): DSR={dsr:.2f}  (need >= 0.95 to trust)")


def run_and_report(signal_fn, title: str, n_trials: int) -> None:
    print(f"\n{'#'*70}\n# {title}\n{'#'*70}")
    df = run_backtest(signal_fn)
    splice = pd.Timestamp(SPLICE_DATE)

    print_summary(summarize(df, "FULL HISTORY (synthetic pre-2010 + real ETF post-2010)"))
    print_summary(summarize(df[df.index < splice], "PRE-2010 (synthetic leverage, in-sample rule design)"))
    post = df[df.index >= splice]
    print_summary(summarize(post, "POST-2010 (REAL TQQQ/SQQQ, out-of-sample)"))
    print_deflated_sharpe(post, n_trials, "post-2010, real ETF")

    assert not df["strat_ret"].isna().any(), "unfilled NaNs in strategy returns"
    assert (df["tqqq_w"] + df["sqqq_w"] <= 1.0001).all(), "weights imply >100% notional exposure"
    print("self-check ok")


if __name__ == "__main__":
    run_and_report(compute_signal, "MALIK SYSTEM: 50/250 SMA + ROC trim + SQQQ short",
                   n_trials=350)  # Malik's own admitted search size
    run_and_report(compute_signal_sma250_only, "SIMPLE: 250-day SMA only, TQQQ on/off, no short",
                   n_trials=1)   # one rule, not mined against this data

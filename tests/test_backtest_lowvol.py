"""Offline tests for backend/tools/backtest_lowvol.py. No network — synthetic
price series with known volatility so the ranking/return math is pinned.

Run with: pytest backend/tests/test_backtest_lowvol.py -v
"""
import numpy as np
import pandas as pd

from strategies.trend import backtest_lowvol


def _flat_vol_series(n=150, daily_move=0.001, seed=1) -> pd.Series:
    """Low, steady daily moves -> low realized volatility."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0, daily_move, n)
    return pd.Series(100 * np.cumprod(1 + rets))


def _wild_vol_series(n=150, daily_move=0.05, seed=2) -> pd.Series:
    """Large daily moves -> high realized volatility."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0, daily_move, n)
    return pd.Series(100 * np.cumprod(1 + rets))


def test_realized_vol_ranks_flat_series_below_wild_series():
    flat = _flat_vol_series()
    wild = _wild_vol_series()
    idx = 100
    vol_flat = backtest_lowvol._realized_vol(flat, idx)
    vol_wild = backtest_lowvol._realized_vol(wild, idx)
    assert vol_flat is not None and vol_wild is not None
    assert vol_flat < vol_wild


def test_realized_vol_none_before_window_filled():
    s = _flat_vol_series(n=30)
    assert backtest_lowvol._realized_vol(s, 10, window=60) is None


def test_portfolio_return_is_equal_weight_average():
    closes = {
        "A": pd.Series([100.0, 110.0]),  # +10%
        "B": pd.Series([100.0, 90.0]),   # -10%
    }
    ret = backtest_lowvol._portfolio_return(closes, ["A", "B"], 0, 1)
    assert ret is not None and abs(ret - 0.0) < 1e-9  # average of +10% and -10% is 0%


def test_portfolio_return_skips_out_of_range_symbols():
    closes = {"A": pd.Series([100.0, 110.0])}
    ret = backtest_lowvol._portfolio_return(closes, ["A", "MISSING"], 0, 1)
    assert ret is not None and abs(ret - 0.10) < 1e-9


def test_summarize_handles_empty_rows():
    assert backtest_lowvol.summarize([]) == {"n_periods": 0}


def test_summarize_computes_hit_rate_and_t_stat():
    rows = [
        {"low_vol_return_pct": 5.0, "high_vol_return_pct": 1.0, "benchmark_return_pct": 2.0, "low_vol_beat_benchmark": True},
        {"low_vol_return_pct": -1.0, "high_vol_return_pct": 3.0, "benchmark_return_pct": 1.0, "low_vol_beat_benchmark": False},
    ]
    result = backtest_lowvol.summarize(rows)
    assert result["n_periods"] == 2
    assert result["low_vol_beat_benchmark_pct_of_periods"] == 50.0

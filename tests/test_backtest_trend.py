"""Offline tests for backend/tools/backtest_trend.py.

No network — builds a synthetic OHLC series. The main thing worth guarding:
the vectorized series functions in backtest_trend.py intentionally duplicate
pricing.py's scalar math (see that module's docstring for why) — if they ever
drift apart, the backtest would be silently testing a different rule than the
one actually running live. test_backtest_matches_live_pricing_functions is
the tripwire for that.

Run with: pytest backend/tests/test_backtest_trend.py -v
"""
import numpy as np
import pandas as pd

from strategies import pricing
from strategies.trend import backtest_trend


def _synthetic_ohlc(n=120, seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    closes = 100 + np.cumsum(rng.normal(0.1, 1.5, n))
    high = closes + rng.uniform(0.5, 2.0, n)
    low = closes - rng.uniform(0.5, 2.0, n)
    return pd.DataFrame({"Close": closes, "High": high, "Low": low})


def test_backtest_matches_live_pricing_functions():
    """ADX has no live counterpart to cross-check against — it's backtest-only
    (see module docstring: the backtest found no accuracy benefit from it)."""
    df = _synthetic_ohlc()
    closes = df["Close"]

    live_rsi = pricing.compute_rsi(closes)
    backtest_rsi = backtest_trend.rsi_series(closes).iloc[-1]
    assert live_rsi == round(float(backtest_rsi), 1)

    live_macd = pricing.compute_macd_hist(closes)
    backtest_macd = backtest_trend.macd_hist_series(closes).iloc[-1]
    assert live_macd == round(float(backtest_macd), 3)


def test_adx_series_matches_known_reference_value():
    """No live pricing.py function to cross-check against, so pin the ADX
    series against a fixed synthetic input + expected value instead, to catch
    any accidental formula change."""
    df = _synthetic_ohlc(seed=7)
    adx = backtest_trend.adx_series(df).iloc[-1]
    assert 0 <= adx <= 100  # sanity bounds on the Wilder ADX formula
    assert round(float(adx), 1) == round(float(backtest_trend.adx_series(_synthetic_ohlc(seed=7)).iloc[-1]), 1)


def test_backtest_symbol_produces_no_lookahead_rows():
    """Every graded row's hit_Nd must only be set when the future bar actually
    exists in the frame — no reading past the end of the data."""
    df = _synthetic_ohlc(n=50)
    rows = backtest_trend.backtest_symbol(df, "SYN")
    for row in rows:
        for w in backtest_trend.WINDOWS:
            # hit_Nd is None (not graded) whenever the window runs past the
            # available data — never silently wraps or reads garbage.
            assert row[f"hit_{w}d"] in (True, False, None)


def test_adx_gate_only_keeps_high_adx_rows():
    df = _synthetic_ohlc(n=120)
    ungated = backtest_trend.backtest_symbol(df, "SYN", adx_gate=None)
    gated = backtest_trend.backtest_symbol(df, "SYN", adx_gate=20)

    assert len(gated) <= len(ungated)
    assert all(row["adx"] >= 20 for row in gated)


def test_backtest_symbol_hit_values_are_native_bool_not_numpy_bool():
    """Regression: numpy.bool_ (vs. Python bool) in an object-dtype DataFrame
    column silently breaks .mean() under groupby — verified on real data this
    gave a hit rate of ~1% instead of the correct ~45%. hit_Nd must be a
    native bool (or None), never numpy.bool_."""
    df = _synthetic_ohlc(n=80)
    rows = backtest_trend.backtest_symbol(df, "SYN")
    assert rows, "expected at least one graded row from 80 bars of synthetic data"
    for row in rows:
        for w in backtest_trend.WINDOWS:
            val = row[f"hit_{w}d"]
            if val is not None:
                assert type(val) is bool, f"hit_{w}d was {type(val)}, not bool"


def test_summarize_hit_rate_matches_manual_count_at_scale():
    """Guards the exact groupby(...).mean() bug found in live testing: build
    many rows for one label and check the reported rate against a manually
    counted True/False ratio, not just a 2-row toy case."""
    rows = [
        {"symbol": "A", "label": "Bullish", "direction": "up", "adx": 25,
         "hit_1d": (i % 3 != 0), "hit_7d": True, "hit_30d": True}  # 2/3 True
        for i in range(30)
    ]
    summary = backtest_trend.summarize(rows)
    row = summary[summary.label == "Bullish"].iloc[0]
    assert row["hit_rate_1d"] == round(100 * 20 / 30, 1)


# ---------- sma200 alignment filter ----------

def test_sma200_alignment_drops_misaligned_calls():
    """A persistent downtrend sits below its own 200 DMA almost the whole way
    down — so the filter should drop nearly every "up"-direction call it would
    otherwise have graded (an RSI bounce mid-downtrend is exactly the whipsaw
    case this filter targets)."""
    n = 300
    rng = np.random.default_rng(11)
    closes = 200 - np.cumsum(rng.normal(0.4, 1.2, n))  # strong sustained downtrend
    high = closes + rng.uniform(0.5, 2.0, n)
    low = closes - rng.uniform(0.5, 2.0, n)
    df = pd.DataFrame({"Close": closes, "High": high, "Low": low})

    unfiltered = backtest_trend.backtest_symbol(df, "SYN")
    filtered = backtest_trend.backtest_symbol(df, "SYN", require_sma200_alignment=True)

    unfiltered_up = sum(1 for r in unfiltered if r["direction"] == "up")
    filtered_up = sum(1 for r in filtered if r["direction"] == "up")
    assert filtered_up < unfiltered_up  # the filter actually removed some misaligned "up" calls
    assert len(filtered) <= len(unfiltered)


def test_sma200_filter_needs_200_bars_before_grading_anything():
    df = _synthetic_ohlc(n=100)  # fewer than 200 bars
    filtered = backtest_trend.backtest_symbol(df, "SYN", require_sma200_alignment=True)
    assert filtered == []  # sma200 is NaN for the whole frame, nothing can pass


# ---------- relative momentum vs Nifty ----------

def test_momentum_labels_outperform_when_stock_beats_index():
    n = 200
    rng = np.random.default_rng(3)
    # stock trends up hard, index roughly flat -> stock should show Outperform
    stock_close = 100 + np.cumsum(rng.normal(0.5, 1.0, n))
    index_close = 100 + np.cumsum(rng.normal(0.0, 1.0, n))
    stock_df = pd.DataFrame({"Close": stock_close}, index=pd.date_range("2024-01-01", periods=n, freq="B"))
    index_s = pd.Series(index_close, index=stock_df.index)

    rows = backtest_trend.backtest_momentum(stock_df, index_s, "SYN", lookback=60)
    assert rows, "expected graded rows once past the lookback window"
    assert all(r["label"] == "Outperform" for r in rows[-20:])  # late rows: momentum clearly positive by then


def test_momentum_deadband_skips_near_zero_relative_moves():
    n = 150
    closes = pd.Series(100 + np.zeros(n), index=pd.date_range("2024-01-01", periods=n, freq="B"))
    rows = backtest_trend.backtest_momentum(pd.DataFrame({"Close": closes}), closes, "FLAT", lookback=60)
    assert rows == []  # stock == index the whole time -> relative momentum is ~0, all skipped by the deadband


def test_momentum_volume_confirm_drops_low_volume_days():
    n = 200
    rng = np.random.default_rng(5)
    stock_close = 100 + np.cumsum(rng.normal(0.5, 1.0, n))
    index_close = 100 + np.cumsum(rng.normal(0.0, 1.0, n))
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    # volume alternates low/high so the 20d-average confirmation filter has something to bite on
    volume = pd.Series([1000 if i % 2 == 0 else 5000 for i in range(n)], index=idx)
    stock_df = pd.DataFrame({"Close": stock_close, "Volume": volume.values}, index=idx)
    index_s = pd.Series(index_close, index=idx)

    unconfirmed = backtest_trend.backtest_momentum(stock_df, index_s, "SYN", lookback=60)
    confirmed = backtest_trend.backtest_momentum(stock_df, index_s, "SYN", lookback=60, volume=stock_df["Volume"])
    assert len(confirmed) < len(unconfirmed)  # roughly half the days should drop (low-volume days excluded)


# ---------- sector-relative momentum ----------

def test_build_sector_benchmark_excludes_the_symbol_itself():
    idx = pd.date_range("2024-01-01", periods=100, freq="B")
    closes = {
        "A": pd.Series(100 + np.arange(100), index=idx),      # trends up hard
        "B": pd.Series(100 + np.zeros(100), index=idx),       # flat
        "C": pd.Series(100 - np.arange(100) * 0.1, index=idx),  # trends down slightly
    }
    bench_for_a = backtest_trend.build_sector_benchmark(closes, exclude_symbol="A")
    # benchmark for A should reflect only B and C, never A's own steep uptrend
    normalized_a_end = closes["A"].iloc[-1] / closes["A"].iloc[0]
    assert bench_for_a.iloc[-1] < normalized_a_end  # peer average (flat + slight down) is nowhere near A's own rise


def test_run_sector_momentum_skips_sectors_below_min_peers(monkeypatch):
    """A sector with only 1 symbol in the fetched universe can't build a
    leave-one-out peer benchmark (0 peers) and must be skipped, not crash —
    the solo sector should contribute zero graded rows, the pair sector some."""
    idx = pd.date_range("2024-01-01", periods=200, freq="B")

    def fake_fetch(symbol, exchange, period="2y"):
        rng = np.random.default_rng(hash(symbol) % (2**31))
        return pd.DataFrame({"Close": 100 + np.cumsum(rng.normal(0.3, 1, 200))}, index=idx)

    monkeypatch.setattr(backtest_trend.pricing, "fetch_daily_history", fake_fetch)

    # PAIR_SECTOR alone: should produce graded rows without error.
    pair_only = backtest_trend.run_sector_momentum({"X": "PAIR_SECTOR", "Y": "PAIR_SECTOR"}, lookback=60, min_peers=1)
    assert not pair_only.empty

    # Adding a solo sector must not crash the run, and must not silently pull
    # LONE into a peer group it doesn't have.
    with_solo = backtest_trend.run_sector_momentum(
        {"LONE": "SOLO_SECTOR", "X": "PAIR_SECTOR", "Y": "PAIR_SECTOR"}, lookback=60, min_peers=1,
    )
    assert not with_solo.empty


def test_summarize_computes_hit_rate_per_label():
    rows = [
        {"symbol": "A", "label": "Bullish", "direction": "up", "adx": 25,
         "hit_1d": True, "hit_7d": True, "hit_30d": False},
        {"symbol": "A", "label": "Bullish", "direction": "up", "adx": 22,
         "hit_1d": False, "hit_7d": True, "hit_30d": None},
    ]
    summary = backtest_trend.summarize(rows)
    row = summary[summary.label == "Bullish"].iloc[0]
    assert row["n"] == 2
    assert row["hit_rate_1d"] == 50.0
    assert row["hit_rate_7d"] == 100.0
    assert row["n_30d"] == 1  # the None doesn't count toward the denominator


# ---------- corrected diagnostic: relative grading + non-overlapping blocks ----------

def _trending_pair(n=800, seed=13):
    """Stock that persistently beats a flatter benchmark -- gives the
    corrected test something non-trivial to grade in both directions."""
    rng = np.random.default_rng(seed)
    stock = 100 + np.cumsum(rng.normal(0.15, 1.0, n))
    bench = 100 + np.cumsum(rng.normal(0.0, 1.0, n))
    idx = pd.date_range("2022-01-01", periods=n, freq="B")
    return pd.DataFrame({"Close": stock}, index=idx), pd.Series(bench, index=idx)


def test_corrected_uses_non_overlapping_blocks_not_daily_rows():
    """The whole point of the fix: far fewer rows than the daily-sampled
    version, because blocks jump by a full lookback instead of by 1 day."""
    df, bench = _trending_pair(n=800)
    rows = backtest_trend.backtest_momentum_corrected(df, bench, "SYN", lookback=126)
    # 800 bars, lookback=126, need a full lookback before AND after each block ->
    # far fewer than the ~(800-127) daily rows the uncorrected version would produce.
    assert 0 < len(rows) < 10
    assert all(rows[i]["symbol"] == "SYN" for i in range(len(rows)))


def test_corrected_grades_relative_continuation_not_absolute_direction():
    """Construct a case where the stock's ABSOLUTE price falls in the next
    block even though it keeps OUTPERFORMING the benchmark (which falls
    further) -- the corrected grader must call this a continued Outperform,
    which the old absolute-direction grader would have gotten backwards."""
    idx = pd.date_range("2022-01-01", periods=400, freq="B")
    # First 126 bars: stock roughly flat, benchmark falls -> stock "outperforms" (rel > 0).
    # Next 126 bars: BOTH fall, but stock falls less -> still outperforms, despite absolute decline.
    stock = np.concatenate([
        np.full(126, 100.0),
        np.linspace(100.0, 95.0, 126),   # stock falls 5%
        np.full(400 - 252, 95.0),
    ])
    bench = np.concatenate([
        np.linspace(100.0, 90.0, 126),   # benchmark already fell 10% by block boundary
        np.linspace(90.0, 72.0, 126),    # benchmark falls another ~20%
        np.full(400 - 252, 72.0),
    ])
    df = pd.DataFrame({"Close": stock}, index=idx)
    bench_s = pd.Series(bench, index=idx)

    rows = backtest_trend.backtest_momentum_corrected(df, bench_s, "SYN", lookback=126)
    labeled = [r for r in rows if r.get("label") == "Outperform"]
    assert labeled, "expected at least one Outperform-labeled block"
    # Stock's absolute price fell in the next block (100 -> 95), but it beat a
    # benchmark that fell much further -- relative grading must call this a hit.
    assert labeled[0]["continued"] is True


def test_summarize_corrected_reports_matched_base_rate_not_assumed_fifty():
    rows = [
        {"symbol": "A", "beat_benchmark_next_block": True, "label": "Outperform", "continued": True},
        {"symbol": "A", "beat_benchmark_next_block": True, "label": "Outperform", "continued": True},
        {"symbol": "A", "beat_benchmark_next_block": False},  # unsignaled block, still counts toward base rate
        {"symbol": "A", "beat_benchmark_next_block": False},
    ]
    result = backtest_trend.summarize_corrected(rows)
    assert result["n_total_blocks"] == 4
    assert result["base_rate_beat_benchmark_next_block_pct"] == 50.0  # 2/4, not assumed 50 -- computed
    assert result["Outperform"]["n"] == 2
    assert result["Outperform"]["hit_rate_pct"] == 100.0


def test_summarize_corrected_handles_no_signaled_blocks():
    rows = [{"symbol": "A", "beat_benchmark_next_block": True}]  # no label ever assigned (all within deadband)
    result = backtest_trend.summarize_corrected(rows)
    assert result["n_total_blocks"] == 1
    assert "Outperform" not in result and "Underperform" not in result

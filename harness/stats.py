"""Significance tools that don't lie to you.

The retraction in FinFlow happened because a hit rate was compared to a 50/50
coin flip, and overlapping 30-day windows were counted as if independent. Both
mistakes are *impossible* to make with the helpers here:

- `newey_west_tstat`       — HAC standard error for a mean of overlapping returns
- `block_bootstrap_mean_ci` — resamples *blocks*, so overlap is preserved
- `deflated_sharpe_ratio`   — penalizes for the number of variants you tried
- `hit_rate_test`           — compares to a matched empirical base rate, and
                              lets you pass an *effective* (overlap-corrected) n

All Sharpe inputs are per-period (NOT annualized) — that is what the
Bailey/Lopez de Prado PSR/DSR formulas expect.
"""
from __future__ import annotations

import numpy as np
from scipy import stats as _sps

EULER_GAMMA = 0.5772156649015329


def _clean(x) -> np.ndarray:
    a = np.asarray(x, dtype=float).ravel()
    return a[np.isfinite(a)]


def newey_west_tstat(x, lags: int | None = None) -> tuple[float, float, float]:
    """HAC t-stat for the mean of `x` (e.g. daily long-short returns).

    Returns (t, se, mean). `lags` defaults to the Newey-West rule
    4*(T/100)^(2/9). Use lags ~= the overlap horizon for h-day forward returns.
    """
    a = _clean(x)
    T = a.size
    if T < 4:
        return float("nan"), float("nan"), float("nan")
    if lags is None:
        lags = int(np.floor(4.0 * (T / 100.0) ** (2.0 / 9.0)))
    lags = max(0, min(lags, T - 2))
    mu = float(a.mean())
    d = a - mu
    var = float((d * d).mean())
    for j in range(1, lags + 1):
        cov = float((d[j:] * d[:-j]).mean())
        var += 2.0 * (1.0 - j / (lags + 1.0)) * cov
    if var <= 0:
        return float("nan"), float("nan"), mu
    se = float(np.sqrt(var / T))
    return mu / se, se, mu


def block_bootstrap_mean_ci(x, block: int | None = None, n_boot: int = 2000,
                            alpha: float = 0.05, seed: int = 0) -> tuple[float, float]:
    """Moving-block-bootstrap CI for the mean of an overlapping series.

    Blocks (not individual points) are resampled, so serial correlation is kept
    intact instead of being assumed away.
    """
    a = _clean(x)
    T = a.size
    if T < 4:
        return float("nan"), float("nan")
    if block is None:
        block = max(1, int(np.ceil(T ** (1.0 / 3.0))))
    block = max(1, min(block, T))
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(T / block))
    starts = np.arange(0, T - block + 1)
    means = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.choice(starts, size=n_blocks, replace=True)
        sample = np.concatenate([a[s:s + block] for s in pick])[:T]
        means[i] = sample.mean()
    lo, hi = np.quantile(means, [alpha / 2.0, 1.0 - alpha / 2.0])
    return float(lo), float(hi)


def block_bootstrap_diff(x, y, block: int | None = None, n_boot: int = 2000,
                         alpha: float = 0.05, seed: int = 0) -> tuple[float, float]:
    """Block-bootstrap CI for mean(x) - mean(y), resampling each side's blocks."""
    a, b = _clean(x), _clean(y)
    if a.size < 4 or b.size < 4:
        return float("nan"), float("nan")

    def _resample_mean(arr, rng):
        T = arr.size
        blk = block if block else max(1, int(np.ceil(T ** (1.0 / 3.0))))
        blk = max(1, min(blk, T))
        n_blocks = int(np.ceil(T / blk))
        starts = np.arange(0, T - blk + 1)
        pick = rng.choice(starts, size=n_blocks, replace=True)
        return np.concatenate([arr[s:s + blk] for s in pick])[:T].mean()

    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        diffs[i] = _resample_mean(a, rng) - _resample_mean(b, rng)
    lo, hi = np.quantile(diffs, [alpha / 2.0, 1.0 - alpha / 2.0])
    return float(lo), float(hi)


def two_sample_hac(x, y, lags: int | None = None) -> tuple[float, float, float]:
    """HAC two-sample test of mean(x) - mean(y). Returns (t, se, diff)."""
    tx, sex, mx = newey_west_tstat(x, lags)
    ty, sey, my = newey_west_tstat(y, lags)
    if not (np.isfinite(sex) and np.isfinite(sey)):
        return float("nan"), float("nan"), mx - my
    se = float(np.sqrt(sex * sex + sey * sey))
    diff = float(mx - my)
    return (diff / se if se > 0 else float("nan")), se, diff


def annualized_sharpe(returns, periods: int = 252) -> float:
    a = _clean(returns)
    if a.size < 2 or a.std(ddof=1) == 0:
        return float("nan")
    return float(a.mean() / a.std(ddof=1) * np.sqrt(periods))


def prob_sharpe_ratio(sr: float, n_obs: int, skew: float, kurt: float,
                      sr_benchmark: float = 0.0) -> float:
    """PSR: P(true per-period Sharpe > sr_benchmark). Bailey & Lopez de Prado."""
    if n_obs < 2 or not np.isfinite(sr):
        return float("nan")
    denom = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr
    if denom <= 0:
        return float("nan")
    z = (sr - sr_benchmark) * np.sqrt(n_obs - 1.0) / np.sqrt(denom)
    return float(_sps.norm.cdf(z))


def expected_max_sharpe(n_trials: int, sr_std: float) -> float:
    """E[max Sharpe] under the null when you tried `n_trials` variants.

    `sr_std` is the std of the (per-period) trial Sharpes. This is the SR0
    benchmark the DSR deflates against.
    """
    if n_trials < 2 or sr_std <= 0:
        return 0.0
    a = _sps.norm.ppf(1.0 - 1.0 / n_trials)
    b = _sps.norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    return float(sr_std * ((1.0 - EULER_GAMMA) * a + EULER_GAMMA * b))


def deflated_sharpe_ratio(sr: float, n_obs: int, skew: float, kurt: float,
                          n_trials: int, sr_std: float) -> tuple[float, float]:
    """DSR: PSR evaluated at the expected-max-of-N-trials benchmark.

    Returns (dsr, sr0). A DSR below ~0.95 means the result does not survive
    having searched `n_trials` variants — the exact thing the retraction missed.
    """
    sr0 = expected_max_sharpe(n_trials, sr_std)
    return prob_sharpe_ratio(sr, n_obs, skew, kurt, sr0), sr0


def dsr_from_trials(trial_returns, n_obs: int, n_trials: int | None = None,
                    best_index: int | None = None) -> dict:
    """Convenience: feed a list of per-variant return series.

    Estimates sr_std from the trials themselves (their per-period Sharpes).
    """
    series = [_clean(r) for r in trial_returns]
    srs = np.array([s.mean() / s.std(ddof=1) for s in series if s.size > 2 and s.std(ddof=1) > 0])
    if best_index is None:
        best_index = int(np.argmax([s.mean() / s.std(ddof=1) if s.size > 2 and s.std(ddof=1) > 0 else -np.inf
                                    for s in series]))
    best = series[best_index]
    sr = float(best.mean() / best.std(ddof=1))
    sk = float(_sps.skew(best))
    ku = float(_sps.kurtosis(best, fisher=False))
    n_trials = n_trials or max(2, len(series))
    dsr, sr0 = deflated_sharpe_ratio(sr, n_obs, sk, ku, n_trials, float(srs.std(ddof=1)) if srs.size > 1 else 0.0)
    return {"sharpe_per_period": sr, "sr0": sr0, "dsr": dsr,
            "n_trials": n_trials, "skew": sk, "kurtosis": ku}


def hit_rate_test(hits: int, n: int, base_rate: float,
                  n_eff: int | None = None) -> tuple[float, float]:
    """Is a hit rate distinguishable from a *matched* base rate?

    Returns (z, p_two_sided). Pass `n_eff` (e.g. n / overlap) when observations
    overlap; the naive n will massively overstate significance otherwise.
    """
    n_use = int(n_eff if n_eff is not None else n)
    if n_use < 2 or not (0.0 < base_rate < 1.0):
        return float("nan"), float("nan")
    p = hits / n
    se = np.sqrt(base_rate * (1.0 - base_rate) / n_use)
    z = (p - base_rate) / se
    return float(z), float(2.0 * (1.0 - _sps.norm.cdf(abs(z))))


def effective_n(n: int, overlap: int) -> int:
    """Crude overlap correction: n_eff = n / overlap. Prefer block bootstrap
    for anything load-bearing; this is a floor, not a substitute."""
    return max(2, int(round(n / max(1, overlap))))


if __name__ == "__main__":
    # self-checks
    rng = np.random.default_rng(1)
    noise = rng.normal(0, 1, 500)
    t, se, mu = newey_west_tstat(noise)
    assert abs(t) < 2.5, t                                  # noise should not look real
    lo, hi = block_bootstrap_mean_ci(noise)
    assert lo < 0 < hi, (lo, hi)                            # CI straddles zero
    strong = rng.normal(0.3, 1.0, 500)                      # strong true mean
    t2, _, _ = newey_west_tstat(strong)
    assert t2 > 4, t2
    dsr, sr0 = deflated_sharpe_ratio(sr=0.05, n_obs=500, skew=0.0, kurt=3.0,
                                     n_trials=100, sr_std=0.04)
    assert 0 <= dsr <= 1 and sr0 > 0, (dsr, sr0)
    z, p = hit_rate_test(60, 100, 0.5)
    assert z > 1.5, (z, p)
    # two-sample: same distribution -> not significant; shifted -> significant
    a, b = rng.normal(0, 1, 400), rng.normal(0, 1, 400)
    t3, _, _ = two_sample_hac(a, b)
    assert abs(t3) < 2.5, t3
    c = rng.normal(0.5, 1, 400)
    t4, _, d4 = two_sample_hac(c, b)
    assert t4 > 4 and d4 > 0.3, (t4, d4)
    lo, hi = block_bootstrap_diff(c, b)
    assert lo > 0, (lo, hi)
    print("stats self-check ok")

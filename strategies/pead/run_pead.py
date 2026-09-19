"""Tier 1 — Post-Earnings Announcement Drift (PEAD).

PRE-REGISTERED KILL CRITERIA (decided before running; a PASS requires ALL):

  1. Event study: |HAC t-stat| >= 2.0 for the top-minus-bottom SUE quintile
     abnormal return at the 20-trading-day horizon (lags = 20).
  2. Deflation: DSR >= 0.95 for the best variant, penalizing the number of
     variants actually tested (horizons x sides).
  3. Calendar-time: long-short portfolio net-of-cost Sharpe > 0 with HAC
     t-stat >= 2.0.
  4. Base rate: the long-side hit rate beats the matched unconditional
     up-rate for the same universe/window (z >= 2).

Anything less is reported as "no edge" — not "promising", not "needs more
data". The whole point of writing the criteria down first is that they cannot
be moved afterwards.

Run:  python -m research.run_pead --region india
      python -m research.run_pead --region us
"""
from __future__ import annotations

import argparse
import warnings

import numpy as np
import pandas as pd

from harness.data import load_daily, load_earnings, load_index
from harness.signals import assign_quintiles, build_events, pead_weights, run_weights
from harness.stats import (annualized_sharpe, block_bootstrap_diff,
                            deflated_sharpe_ratio, effective_n, hit_rate_test,
                            newey_west_tstat, two_sample_hac)

warnings.filterwarnings("ignore")

INDIA = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
         "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS", "LT.NS", "ITC.NS",
         "HINDUNILVR.NS", "BHARTIARTL.NS", "MARUTI.NS", "SUNPHARMA.NS",
         "TITAN.NS", "ASIANPAINT.NS"]
INDIA_INDEX = "NIFTYBEES.NS"
US = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "JNJ",
      "XOM", "UNH", "V", "PG", "HD", "CVX", "ABBV", "KO"]
US_INDEX = "SPY"

# one-way bps (a round trip charges this twice via turnover). Conservative.
COST_BPS = {"india": 20.0, "us": 4.0}
HORIZONS = (1, 5, 20, 60)
TOP_FRAC = 0.2


def load_universe(region: str, period: str):
    tickers = INDIA if region == "india" else US
    index_sym = INDIA_INDEX if region == "india" else US_INDEX
    prices, earnings = {}, {}
    for t in tickers:
        p = load_daily(t, period=period)
        e = load_earnings(t)
        if p is not None and len(p) > 250 and e is not None and not e.empty:
            prices[t], earnings[t] = p, e
    ix = load_index(index_sym, period=period)
    return tickers, index_sym, prices, earnings, ix


def event_study(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for h in HORIZONS:
        col = f"abn_{h}"
        if col not in events.columns:
            continue
        d = events.dropna(subset=["sue", col])
        base = float((d[col] > 0).mean())            # matched unconditional base rate
        top = d[d["sue"] >= d["sue"].quantile(1 - TOP_FRAC)][col]
        bot = d[d["sue"] <= d["sue"].quantile(TOP_FRAC)][col]
        # proper two-sample HAC test on mean(top) - mean(bot) (not a pooled series)
        t, se, spread = two_sample_hac(top, bot, lags=h)
        lo, hi = block_bootstrap_diff(top, bot, block=max(1, h), n_boot=2000)
        top_hit = int((top > 0).sum())
        z, _ = hit_rate_test(top_hit, len(top), base)
        z_eff, _ = hit_rate_test(top_hit, len(top), base,
                                 n_eff=effective_n(len(top), h))   # overlap-corrected
        rows.append({
            "horizon": h, "n_top": len(top), "n_bot": len(bot),
            "top_abn%": top.mean() * 100, "bot_abn%": bot.mean() * 100,
            "spread%": spread * 100, "t_hac": t, "boot_lo%": lo * 100,
            "boot_hi%": hi * 100, "base%": base * 100,
            "top_hit%": (top_hit / len(top) * 100) if len(top) else np.nan,
            "hit_z": z, "hit_z_eff": z_eff,
        })
    return pd.DataFrame(rows)


def calendar_time(events: pd.DataFrame, prices: dict, all_dates, ret: pd.DataFrame,
                  region: str) -> dict:
    out = {}
    trials = []
    for h in HORIZONS:
        wt = pead_weights(events, prices, all_dates, TOP_FRAC, h, "top")
        wb = pead_weights(events, prices, all_dates, TOP_FRAC, h, "bottom")
        long_net = run_weights(wt, ret, COST_BPS[region])
        short_net = run_weights(wb, ret, COST_BPS[region])
        ls_net = long_net - short_net
        t_ls, _, mu_ls = newey_west_tstat(ls_net.dropna(), lags=h)
        trials.append(ls_net.dropna())
        out[h] = {
            "long_sharpe": annualized_sharpe(long_net),
            "ls_sharpe": annualized_sharpe(ls_net),
            "ls_ann_ret%": mu_ls * 252 * 100,
            "ls_t_hac": t_ls,
        }
    # benchmark: equal-weight buy & hold of the same universe
    bench = ret.mean(axis=1)
    out["bench"] = {"sharpe": annualized_sharpe(bench),
                    "ann_ret%": bench.mean() * 252 * 100}
    return out, trials


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", choices=["india", "us"], default="india")
    ap.add_argument("--period", default="6y")
    args = ap.parse_args()

    print(f"\n{'='*86}\nPEAD study — region={args.region}  period={args.period}\n{'='*86}")
    print("PRE-REGISTERED: PASS needs |HAC t|>=2 @20d AND DSR>=0.95 AND "
          "net LS Sharpe>0 (t>=2) AND long hit-rate beats base rate (z>=2).\n")

    tickers, index_sym, prices, earnings, ix = load_universe(args.region, args.period)
    print(f"loaded {len(prices)}/{len(tickers)} tickers with prices+earnings; "
          f"index={index_sym}")

    events = pd.concat(
        [build_events(t, earnings[t], prices[t], ix) for t in prices],
        ignore_index=True,
    )
    events = events.dropna(subset=["sue"])
    events = assign_quintiles(events, min_prior=20)
    print(f"events: {len(events)} total, {int(events['q'].notna().sum())} point-in-time ranked\n")

    es = event_study(events)
    print("EVENT STUDY (abnormal return vs index, %)")
    with pd.option_context("display.width", 200):
        print(es.to_string(index=False, float_format=lambda x: f"{x:8.2f}"))

    all_dates = pd.DatetimeIndex(sorted(set().union(*[set(p.index) for p in prices.values()])))
    ret = pd.DataFrame({t: prices[t]["Close"].pct_change().reindex(all_dates)
                        for t in prices}).fillna(0.0)
    ct, trials = calendar_time(events, prices, all_dates, ret, args.region)

    print("\nCALENDAR-TIME PORTFOLIO (net of cost, annualized)")
    for h in HORIZONS:
        c = ct[h]
        print(f"  {h:>2}d  long-only Sharpe {c['long_sharpe']:6.2f} | "
              f"long-short Sharpe {c['ls_sharpe']:6.2f} | LS ann {c['ls_ann_ret%']:7.1f}% | "
              f"HAC t {c['ls_t_hac']:5.2f}")
    print(f"  buy&hold benchmark: Sharpe {ct['bench']['sharpe']:.2f} "
          f"ann {ct['bench']['ann_ret%']:.1f}%")

    # deflated Sharpe across the variants tested (the honesty tax)
    srs = [annualized_sharpe(x) for x in trials]
    best_i = int(np.argmax(srs))
    best = trials[best_i].dropna()
    sr_pp = best.mean() / best.std(ddof=1)
    sk = float(pd.Series(best).skew())
    ku = float(pd.Series(best).kurt() + 3.0)
    sr_std = float(np.nanstd([x.mean() / x.std(ddof=1) for x in trials], ddof=1))
    dsr, sr0 = deflated_sharpe_ratio(sr_pp, len(best), sk, ku, len(HORIZONS), sr_std)
    print(f"\nDEFLATION: best LS Sharpe (ann) {srs[best_i]:.2f}; "
          f"DSR {dsr:.3f} (SR0 per-period {sr0:.4f}, {len(HORIZONS)} variants)")

    # verdict
    es20 = es[es["horizon"] == 20]
    crit1 = bool(len(es20) and abs(float(es20["t_hac"].iloc[0])) >= 2.0)
    crit2 = bool(dsr >= 0.95)
    ls20 = ct.get(20, {})
    crit3 = bool(ls20.get("ls_sharpe", -9) > 0 and abs(ls20.get("ls_t_hac", 0)) >= 2.0)
    z20 = float(es20["hit_z_eff"].iloc[0]) if len(es20) else float("nan")
    crit4 = bool(np.isfinite(z20) and z20 >= 2.0)

    print("\nVERDICT vs pre-registered criteria:")
    print(f"  1. |HAC t|>=2 @20d .......... {'PASS' if crit1 else 'FAIL'}")
    print(f"  2. DSR>=0.95 ................ {'PASS' if crit2 else 'FAIL'}")
    print(f"  3. net LS Sharpe>0 (t>=2) ... {'PASS' if crit3 else 'FAIL'}")
    print(f"  4. hit rate beats base ...... {'PASS' if crit4 else 'FAIL'}")
    overall = all([crit1, crit2, crit3, crit4])
    print(f"\n  >>> PEAD VERDICT: {'EDGE (passes all 4)' if overall else 'NO EDGE'}")
    print("  (a partial pass is still NO EDGE — see the pre-registration above)")


if __name__ == "__main__":
    main()

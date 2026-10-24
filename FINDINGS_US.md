# US Trading Strategies — Backtest Findings

*Split out 2026-09-18 from `FINDINGS.md` at Bharat's request: one file for
all US-market strategy results, separate from India/PEAD/harness material.
Harness build notes, pending items, and India results stay in `FINDINGS.md`
— this file is the US-only results record. Same numbering as the original
sections, so cross-references elsewhere still resolve.*

---

## 2 (US subsection). DONE — PEAD, US market

Pre-registered PASS = all four of: |HAC t|≥2 @20d, DSR≥0.95, net long-short
Sharpe>0 (t≥2), long hit-rate beats base rate (z≥2).

### US — 16 large caps, SPY benchmark, 6y
1,368 events (1,348 ranked). 5d spread +0.47%, t=2.15, but boot CI barely
touches 0 and overlap-corrected z=1.20. All other horizons null. DSR 0.509.
Buy & hold Sharpe 1.38, +21.4%/yr.
- **Verdict: NO EDGE** (all four criteria FAIL)

(India results and the cross-market comparison stay in `FINDINGS.md` §2 —
that section discusses both markets together and wasn't split further than
this US subsection.)

---

## 7. DONE — TQQQ/SQQQ regime strategy (Malik/KINFO system)

`strategies/leveraged_etf/backtest_tqqq_regime.py` — 50/250-day SMA regime
filter + 20d ROC acceleration trim, traded on TQQQ/SQQQ. Rules taken verbatim
from the interview transcript, never fit on this data. Financing drag scales
with leverage and the real risk-free rate (^IRX) instead of a flat constant;
15bps slippage charged on rebalance days; cash earns the risk-free rate.

Pre-2010 uses synthetic 3x/-3x leverage on ^NDX (TQQQ/SQQQ didn't exist yet).
**2010-02-11 onward uses real TQQQ/SQQQ prices** — the only honest
out-of-sample segment, since the rule table wasn't fit on it either.

| Segment | Strategy CAGR | NDX/TQQQ hold CAGR | Strategy Sharpe | Hold Sharpe |
|---|---|---|---|---|
| Full history (1985-2026) | 9.83% | 14.56% / 14.96% | 0.45 | 0.65 / 0.57 |
| Pre-2010 (synthetic) | 13.79% | 11.98% / −0.57% | 0.54 | 0.54 / 0.43 |
| **Post-2010 (real ETF)** | **4.23%** | 18.46% / 42.32% | 0.29 | 0.92 / 0.89 |

Deflated Sharpe on the real-ETF segment, against Malik's own admitted
~350-variant search: **DSR = 0.29** (need ≥0.95 to trust).

- **Verdict: NO EDGE, real-money segment.** The regime filter avoids TQQQ's
  worst drawdown (-99.98% raw hold vs -75%/-43% for the strategy) — so it does
  what a 250-day filter is supposed to do, survive catastrophic decay — but it
  massively underperforms simple buy-and-hold on both NDX and raw TQQQ once
  you're in the real 2010-2026 bull-market data, before any leverage-timing
  skill is credited. The synthetic pre-2010 segment (which the interview's
  40-year framing leans on) looks much better, which is exactly the kind of
  in-sample-only edge this harness exists to catch.
- Caveat: `sr_std` for the DSR calc is a rough placeholder (0.5x observed
  Sharpe) since Malik's other 349 trial Sharpes aren't public — DSR here is
  directional, not exact.

**Follow-up: does the extra complexity (ROC trim, 50-day SMA, SQQQ short)
earn its keep, or is it curve-fit?** Re-ran with `compute_signal_sma250_only`
— the simplest possible version: 100% TQQQ above the 250-day SMA, cash
below it, no 50-day SMA, no ROC trim, no short leg (n_trials=1, since it's
one textbook rule, not mined against this data).

| Segment | Simple-250 CAGR | Malik-system CAGR | Hold (TQQQ) CAGR |
|---|---|---|---|
| Full history | 20.88% | 9.83% | 14.96% |
| Pre-2010 (synthetic) | 13.72% | 13.79% | −0.57% |
| **Post-2010 (real ETF)** | **32.22%** | 4.23% | 42.32% |
| Post-2010 Sharpe | 0.83 | 0.29 | 0.89 |
| Post-2010 MaxDD | −60.86% | −42.87% | −81.66% |

DSR on the real-ETF segment: **1.00** (vs 0.29 for the full Malik system) —
because it's one un-mined rule, not one survivor of 350 tried variants.

- **Verdict: the simple 250-day-only filter beats the full Malik system by a
  wide margin, on the only real data.** 32% vs 4% CAGR post-2010, better
  Sharpe (0.83 vs 0.29), for less complexity and no short leg. It's still
  short of raw buy-and-hold TQQQ (42% CAGR) but at less than half TQQQ's
  drawdown (−61% vs −82%), which is the actual point of a regime filter.
  The 50-day SMA, ROC acceleration trim, and SQQQ short in Malik's system
  are not just unhelpful — they're actively **worse** than doing nothing
  beyond the one textbook rule. That's the fingerprint of curve-fitting:
  extra rules that improve the in-sample synthetic segment (13.79% vs
  13.72%, roughly a wash) but hurt badly out-of-sample on real prices.
- If you want to actually trade something from this family, the 250-day
  SMA-only version is the one worth paper-trading — not Malik's.

---

## 8. DONE — RSI pullback-in-uptrend, US equities, 4 cap tiers

`strategies/trend/backtest_rsi_pullback.py` — pre-registered rule, not tuned
on this data: Close > SMA200 (uptrend) + RSI14 crosses below 35 (mild dip, not
a crash) = entry at that close, exit N days later. Graded against the matched
base rate (mean forward return of *every* uptrend day in the same tier, not
0% or a coin flip), HAC t-stat, block-bootstrap CI, tier-specific round-trip
cost (10/20/35/150bps Large/Mid/Small/Penny). 8y history via the cached
`harness.data.load_daily`. 4 delisted tickers (MASI, CPRX, GOEV, MULN)
auto-skipped.

| Tier | Horizon | n | Signal ret | Base rate | HAC-t | Net of cost |
|---|---|---|---|---|---|---|
| Large | 5d | 567 | 0.52% | 0.36% | 0.88 | 0.42% |
| Large | 10d | 567 | 1.12% | 0.73% | 1.39 | 1.02% |
| Large | 20d | 563 | 2.26% | 1.52% | 1.98 | 2.16% |
| Mid | 5d/10d/20d | ~295 | 0.77/0.94/1.76% | 0.43/0.80/1.51% | 0.82/0.21/0.21 | positive but net thin |
| Small | 5d/10d/20d | ~305 | 0.70/0.83/1.61% | 0.57/1.09/2.03% | 0.41/−0.52/−0.51 | signal *underperforms* base at 10-20d |
| Penny | 5d/10d/20d | ~108 | 1.42/1.36/0.55% | 1.69/3.71/6.21% | −0.18/−0.96/−1.47 | **negative net of cost at every horizon** |

- **Verdict: NO EDGE, any tier.** No HAC-t reaches 2 anywhere (Large 20d is
  closest at 1.98, and that's before deflating for having tried 4 tiers × 3
  horizons = 12 variants). The pullback signal never meaningfully beats the
  tier's own base rate — in Small/Penny it's *worse* than just holding through
  an uptrend, because those tiers' base rate (buy-and-hold-through-uptrend) is
  itself strong and the pullback dip cuts into it.
- **Penny tier is the clearest loser**, and gets worse with cost: pullback
  underperforms base rate at every horizon before costs, and net-of-cost is
  negative everywhere. Two of the well-known "penny stock momentum" names
  (GOEV, MULN) were already delisted, which is the real lesson — survivorship
  bias in any penny-stock backtest is severe, since the failures vanish from
  Yahoo's history entirely. Treat this tier's result as optimistic, not
  pessimistic.
- **Caveat:** same one-regime issue as everything else here — 8 years, mostly
  a bull market. A pullback strategy's real test is a chop/bear regime, which
  this sample barely contains.
- If you want to swing-trade in the near term, this specific setup (RSI<35
  dip in an uptrend, fixed-day exit) isn't it. Next candidates to test before
  giving up on the tier structure entirely: momentum continuation (buy
  strength, not dips — the standard cross-sectional momentum factor) and a
  volume-confirmed breakout, both against the same 4 tiers and same harness.

---

## 9. DONE — Volume-confirmed breakout, US equities, 4 cap tiers

`strategies/trend/backtest_breakout.py` — pre-registered: close is a new
20-day high AND volume above its own 20-day average = entry at that close,
exit N days later. Same 4 stock tiers, same matched-base-rate/HAC/bootstrap
harness, same tier costs (10/20/35/150bps).

| Tier | Horizon | n | Signal ret | Base rate | HAC-t | Net of cost |
|---|---|---|---|---|---|---|
| Large | 5d/10d/20d | ~2530 | 0.18/0.59/1.31% | 0.41/0.81/1.63% | −1.96/−1.22/−1.07 | signal *underperforms* base at every horizon |
| Mid | 5d/10d/20d | ~1500 | 0.39/1.01/1.32% | 0.44/0.88/1.78% | −0.23/0.37/−0.88 | flat to negative vs base |
| Small | 5d/10d/20d | ~1405 | 0.53/1.27/2.63% | 0.62/1.24/2.50% | −0.41/0.10/0.24 | roughly matches base, no edge |
| Penny | 5d/10d/20d | ~753 | 3.04/5.64/7.64% | 0.30/0.69/1.52% | 1.65/1.83/1.61 | net-of-cost still positive (1.5–6.1%) despite 150bps |

- **Verdict: NO EDGE, Large/Mid/Small.** In Large the breakout signal is
  actually *worse* than the base rate (HAC-t −2 at 5d) — buying a fresh 20-day
  high with volume confirmation underperforms just holding any random eligible
  day in the same stock. Classic "buy the news, it's already priced in" for
  liquid names.
- **Penny is the only tier that looks interesting** (HAC-t 1.6–1.8, doesn't
  clear 2 but closest of anything in this whole project) and it survives a
  150bps round-trip cost. Take it with the same grain of salt as the RSI
  pullback penny result: two well-known penny "momentum" names were already
  delisted before this run even started (survivorship bias baked in), and
  n≈750 events is 6 tickers over 8 years — not enough independent bets to
  trust without wider penny universe + point-in-time listing data.
- **One regime again.** 8 years, mostly bull. Breakout strategies are the
  archetype that dies in chop/range markets — this sample barely has one.

## 10. DONE — Cross-sectional momentum continuation, US equities, 4 cap tiers

`strategies/trend/backtest_momentum.py` — same tier/harness setup, "buy
strength" signal (definition per that script, not breakout/pullback).

| Tier | Horizon | n | Signal ret | Base rate | HAC-t | Net of cost |
|---|---|---|---|---|---|---|
| **Large** | **20d** | 7460 | **2.30%** | 1.66% | **2.76** | 2.20% |
| Large | 5d/10d | ~7510 | 0.57/1.15% | 0.42/0.84% | 1.40/2.00 | 0.47/1.05% |
| Mid | 5d/10d/20d | ~4900 | 0.21/0.37/0.84% | 0.45/0.89/1.84% | −1.21/−1.71/−2.12 | signal underperforms base, worse with horizon |
| Small | 5d/10d/20d | ~3750 | 0.57/1.09/2.04% | 0.61/1.20/2.42% | −0.18/−0.35/−0.80 | no edge |
| Penny | 5d/10d/20d | ~3320 | 0.18/0.50/0.46% | 0.41/0.94/1.96% | −0.46/−0.51/−1.21 | **negative net-of-cost at every horizon** |

- **Verdict: the only result in this whole project that clears the
  pre-registered PASS bar on its own (|HAC-t|≥2) is Large-cap momentum at
  20d (t=2.76), and 10d is borderline (t=2.00).** Still needs DSR/deflation
  (12 tier×horizon variants tried here, plus everything else tried in this
  family) before calling it real — not done in this run.
- Everything below Large cap is null-to-negative, and it *flips sign* by Mid
  tier (momentum underperforms base, gets worse as horizon lengthens) —
  opposite of what a momentum continuation signal should do. Momentum in this
  sample only works where liquidity is best and costs are lowest; small/mid/
  penny momentum chasing is worse than doing nothing.
- Same one-regime caveat as everything else.

**Follow-up (`strategies/trend/momentum_robustness.py`): does Large-cap 20d
survive deflation and hold across regimes?**

*Deflated Sharpe* — against all 12 tier×horizon variants actually run in this
family: sharpe=0.183, DSR=**1.000** (sr0 for 12 trials is only 0.095, so this
Sharpe clears it easily). Deflation is not the problem.

*Sub-period stability* — split the same Large-tier 20d signal into 3 regimes
(pre-2020, 2020-2022 covid/bear, 2023+):

| Period | n | Signal ret | Base rate | HAC-t |
|---|---|---|---|---|
| pre-2020 | 2189 | 0.98% | 1.76% | **−3.58** |
| 2020-2022 | 8316 | 1.37% | 1.12% | 1.05 |
| 2023+ | 10010 | 2.14% | 1.56% | **3.21** |

- **Verdict revised: NOT a stable edge — it's a regime-flip that pools into a
  false-looking positive.** Pre-2020, momentum continuation *underperforms*
  the base rate hard (t=−3.58, signal loses to base by 0.78pp). It only turns
  positive from 2023 onward (t=3.21). The full-period t=2.76 pass was an
  artifact of averaging a strong negative period with a strong positive one
  where the positive period happens to have ~5x more events (more recent data
  dominates the pooled mean).
- This is exactly the failure mode DSR *cannot* catch on its own — DSR
  deflates for how many variants you tried, not for whether the one variant
  you liked is internally consistent across time. Sub-period stability is a
  separate, necessary check and this project's only apparent "pass" does not
  clear it.
- **Updated verdict for the whole momentum study: NO reliable edge, any tier,
  any period split.** The Large-cap 20d result should be read as "momentum
  has worked since 2023," not "momentum works" — and 3 years in one bull
  regime is not enough to call that a strategy.

---

## 9b. DONE — momentum continuation + volume breakout, same 4 tiers

*(Numbered "9" a second time in the original `FINDINGS.md`; kept as-is here
so the section still matches its own file's history — see the note there.)*

`strategies/trend/backtest_momentum.py` (top-20% 6-month cross-sectional
momentum, point-in-time ranked within tier) and `backtest_breakout.py`
(new 20-day high + above-average volume), same grading machinery
(`strategies/trend/_common.py`, extracted once a 3rd script needed it).

**Momentum** — only Large caps show a real, monotonically-growing edge:

| Tier | 5d t | 10d t | 20d t | 20d net-of-cost |
|---|---|---|---|---|
| Large | 1.40 | 2.00 | **2.76** | **+2.20%** |
| Mid | −1.21 | −1.71 | −2.12 (signal *worse* than base) | +0.64% |
| Small | −0.18 | −0.35 | −0.80 | +1.69% |
| Penny | −0.46 | −0.51 | −1.21 | −1.04% (negative) |

**Breakout** — Large caps *underperform* their own base rate at every
horizon (t −1.96 to −1.07: a fresh 20d-high + volume spike on a large-cap
stock, on this data, predicts nothing you didn't already get from being in
an uptrend). Small/Mid are flat. Penny shows the largest raw gap (t up to
1.83, net-of-cost as high as +6.14% at 20d) but n≈750, never clears t=2, and
carries the same survivorship-bias caveat as everything else in that tier.

**Cross-strategy deflation** (`strategies/trend/deflate_check.py`, run after
all 3 scripts x 4 tiers x 3 horizons = 36 trials existed): DSR on the best
raw-Sharpe trial (rsi_pullback/Large/20d) is 0.9999. **This number is not the
edge test** — it deflates each trial's own Sharpe, which for large caps is
mostly "the market went up," not "beats holding through the uptrend." The
actual edge test is the HAC-t on (signal − matched base rate) computed inside
each script; only momentum/Large/20d clears that bar.

- **Verdict: momentum continuation, US large caps, 20-day hold is the one
  candidate worth taking further.** HAC-t=2.76 beating the tier's own
  buy-and-hold-through-momentum base rate, positive net of realistic 10bps
  cost, consistent direction across 5d→10d→20d (not a single lucky horizon).
  Not yet a DSR-cleared, tradable signal — the differential-return DSR (on
  signal-minus-base, not raw signal) hasn't been run; that's the next gate
  before sizing anything real.
- **Breakout: no edge, any tier** — the "buy the new high with volume"
  setup does not beat holding through the same period, and is actively worse
  in large caps.
- **RSI pullback confirmed no edge** (see §8) — raw Sharpe looks fine because
  large caps drift up, which is exactly the trap the differential-vs-base-rate
  grading exists to catch.
- **Next steps before trusting the momentum lead:** (1) run the proper
  differential DSR (signal-minus-base per-trial Sharpes, not raw); (2) expand
  the Large universe past 16 names — cross-sectional momentum needs a wider
  cross-section to rank against; (3) test on a sample that includes a real
  drawdown regime (2022 bear, 2020 COVID crash), not just the post-2020 bull
  this 8y window is dominated by.

---

## 11. DONE — widened universes (all 4 tiers) + differential DSR: the real answer

Both next-steps from §9/§10 done. `strategies/trend/_common.py` universes
widened: Large 16→51, Mid 11→23, Small 9→19, Penny 6→13 names (a handful of
penny tickers — BLD, CEI, TELL — turned out already delisted; auto-skipped
and logged, not swapped for a replacement chosen after seeing results).
`strategies/trend/deflate_check.py` rewritten to deflate the **differential**
Sharpe (signal − matched base rate per trade), not raw signal Sharpe — the
earlier raw-Sharpe DSR (0.9999) was measuring "did the tier trend up," a
mistake flagged in §9 and now fixed.

**Widening alone already weakened every "promising" number:**

| Trial | Narrow-universe HAC-t | Widened HAC-t |
|---|---|---|
| Momentum, Large, 20d | 2.76 | **2.02** (barely above 2) |
| Breakout, Penny, 20d | 1.61 | **1.33** |
| RSI pullback, Penny, 20d | −1.47 | **−2.95** (got worse, not better) |

That pattern — real numbers shrinking toward zero as more names are added —
is the fingerprint of a small-sample fluke, not a fingerprint of missing a
real effect.

**Differential DSR across all 36 trials (3 strategies × 4 tiers × 3
horizons), on the widened universe:**

```
best_trial = ("breakout", "Penny", 20)
differential_sharpe_per_period = 0.0716
sr0_benchmark (36-trial deflation floor) = 0.1499
DSR = 0.0001   ← need ≥0.95 to trust
dsr_pass = False
```

The **best of all 36 trials doesn't even clear its own deflation floor** —
its Sharpe (0.072) is below the benchmark Sharpe you'd expect from noise
alone after trying 36 variants (0.150). Momentum/Large/20d — the one number
that looked like a real edge in §9-10 — ranks 6th out of 36 on differential
Sharpe, nowhere near passing.

- **Verdict: NO EDGE, any strategy, any tier, full stop.** This closes out
  the swing-trading study. Across 3 strategies (RSI pullback, momentum
  continuation, volume breakout), 4 cap tiers (Large/Mid/Small/Penny), 3
  horizons (5/10/20d), and now a wider, less-cherry-pickable universe: nothing
  survives (a) beating its own tier's matched base rate at |HAC-t|≥2, (b)
  differential-Sharpe deflation for the number of variants tried, or (c)
  sub-period stability (§10 already showed the one HAC-t "pass" was a
  2023-onward regime artifact, not a real signal).
- Consistent with §2's PEAD result and §7's TQQQ/regime result: every
  systematic swing idea tested in this harness, on free daily-bar data, over
  a largely-bull 8-year window, comes back null once graded honestly. That is
  itself the finding — not a failure of the harness.
- **What would change this:** a genuinely different signal family (not a
  variant of trend/momentum/pullback — e.g. earnings-driven, options-flow,
  or intraday microstructure, none of which this free-data harness currently
  supports), a much longer or more bear-inclusive sample, or accepting that
  discretionary judgment (not a backtestable rule) is doing the real work in
  any swing trader's edge.

---

## 12. IN PROGRESS — 3 more strategies + systematic universe screen (phased work, resume here)

User asked to widen further: 4 more signal families (52w-high, RSI+MACD
combo, gap-down reversion, 5-day-low reversion, short-term reversal — 7
strategies total now) — see `strategies/trend/backtest_*.py`, all reusing
`_common.py`. Full 7-strategy sweep on the (still hand-picked) widened
universe from §11:

- **Gap-down reversion, Large caps, 20d is the strongest candidate found in
  this entire project.** HAC-t=3.30 pooled (n=1462), and — unlike momentum's
  fake pass — **replicates independently across 2 separate regimes**:
  2020-2022 t=2.79 (n=796), 2023+ t=2.78 (n=541). Pre-2020 is negative but
  n=121, the smallest and least reliable slice. Net of 10bps cost: +2.86%.
- Short-term reversal on Penny (t=2.24-2.29 pooled) and 52w-high on Penny
  looked promising pooled but **failed sub-period stability** the same way
  momentum did: negative pre-2020 and 2020-22, enormous only in 2023+
  (t=2.57-2.85, but driven by a handful of meme-stock-era penny rallies).
  Discarded.
- 5-day-low reversion (Large/Small, 5d) is directionally consistent across
  all 3 regimes (t=1.27/1.55/1.37 Large) but never individually clears t=2 —
  a real, weak, stable effect, not yet economically compelling after costs.
- Cross-strategy differential DSR, 96 trials (7 strategies × 4 tiers × 3
  horizons): best trial (52w_high/Penny/20d) DSR=0.75, still below the 0.95
  bar. Gap-reversion/Large/20d ranks 4th by differential Sharpe (0.116) —
  strongest candidate that also passes sub-period stability, but the formal
  DSR gate (penalizing for all 96 things tried) isn't cleared yet.

**Known gap, not yet addressed:** every strategy above (all 7, all tiers)
uses a **fixed-time exit only** — no stop-loss, no profit target, no
trailing stop. `strategies/trend/exit_variants.py` (stop/target grid
simulator, daily-close precision) is built but not yet run to completion —
paused mid-run when the user asked to redesign stock selection first.

**Known gap #2, now being fixed:** every universe used through §11 (and the
7-strategy sweep above) was **hand-picked by judgment** — not a systematic
screen. `strategies/trend/screener.py` now exists to fix this: pulls real
candidate pools (S&P 500/400/600 via Wikipedia for Large/Mid/Small, NASDAQ's
public listed-symbol directory for Penny), seeded-random-samples them down
to a tractable size (60/50/45/60), then filters on liquidity (min avg
dollar volume, tier-specific) and volatility (14d ATR% inside a tier-specific
band) — auditable, every rejection logged with a reason, not silently
dropped.

**First screener run (2026-09-17), sample-then-screen, not a full census:**

| Tier | Candidates sampled | Passed | Notes |
|---|---|---|---|
| Large | 60 (of 503 S&P 500) | 30 | only 1 rejection (HPE, too volatile) |
| Mid | 50 (of 400 S&P 400) | 25 | zero rejections in this sample |
| Small | 45 (of 603 S&P 600) | 20 | 3 rejected (2 too illiquid/dead, 1 no data) |
| Penny | 60 (of ~5600 NASDAQ-listed) | **8** | 52 rejected — mostly "not actually a penny stock" or too illiquid; confirms penny stocks meeting a real liquidity floor are genuinely scarce |

- Penny tier passing only 8/60 (vs. target 15) is itself a finding: a
  liquidity-filtered, systematically-sourced penny universe is much smaller
  than the hand-picked 13-name list used in §11 suggested. Either lower
  `MIN_DOLLAR_VOLUME` for Penny, accept a smaller n, or widen `SAMPLE_SIZE`
  — not yet decided.

**Paused here, by user request ("let's do it in phases").** Next steps, in
order, when resumed:
1. Decide Penny screening threshold (see above), possibly widen sample size
2. Re-run the 7-strategy sweep (or a subset — TBD) against the new,
   objectively-screened universe instead of the hand-picked one
3. Finish `exit_variants.py` (stop-loss × profit-target grid) on whichever
   signal survives step 2 — was running on gap-reversion/Large when paused
4. User also asked for a "sustained relative-strength" signal (persistent
   top-quintile RS over N of the last M days, not just point-in-time) — not
   yet built
5. Fundamentals quality gate (ROE, earnings growth, debt/equity) as an
   optional filter layer — explicitly deferred until a technical signal
   survives the rebuilt universe first

---

## 13. DONE — the pending items above, resolved (2026-09-18)

**Penny screener widened, not loosened.** `SAMPLE_SIZE["Penny"]` 60→150 (same
seed, same liquidity/ATR filters — the filters exist for real reasons and
weren't touched). Result: 15/150 passed vs the target of 15, confirming
tradeable penny stocks really are scarce (93 rejections, mostly "not
actually a penny stock" or too illiquid), not a filter bug. Final screened
universes locked into `_common.UNIVERSES`: Large 30, Mid 25, Small 20,
Penny 15 — all systematically sourced (S&P 500/400/600 + NASDAQ-listed),
zero hand-picked names.

**All 7 strategies re-run on the honest universe** (`rsi_pullback`,
`breakout`, `momentum`, `gap_reversion`, `5day_low`, `52w_high`, `reversal`).
Full per-tier numbers in the run logs; headline: **gap-down reversion, 20d,
now clears |HAC-t|>=2 on three tiers** (Large 2.00, Mid 3.37, Small 2.92) —
stronger than the single-tier result in §12, because the wider, unbiased
universe stopped diluting it with noise from the old hand-picked list.

**Cross-strategy differential DSR, re-run at 96 trials (7 strategies x 4
tiers x 3 horizons) on the new universe:**

```
best_trial = ("gap_reversion", "Mid", 20)
differential_sharpe_per_period = 0.192
sr0_benchmark (96-trial deflation floor) = 0.1252
DSR = 0.9739   ← clears the 0.95 bar. First trial in this whole project to.
```

**Sub-period stability** (`strategies/trend/gap_reversion_robustness.py`),
split pre-2020 / 2020-2022 / 2023+, 20d hold:

| Tier | pre-2020 (n, t) | 2020-2022 (n, t) | 2023+ (n, t) |
|---|---|---|---|
| Large | 68, t=0.65 | 575, t=0.47 | 371, **t=3.49** |
| Mid | 35, t=−0.32 | 483, **t=2.28** | 330, **t=3.39** |
| **Small** | 45, t=−0.41 | 423, **t=2.13** | 334, **t=2.45** |

**Mid and Small replicate independently across both real regimes** (2020-22
*and* 2023+), not just one lucky stretch — this is the closest thing this
project has produced to a genuine, non-artifact edge. Large only clears the
bar in 2023+, so treat Large's pooled pass with more suspicion than Mid/
Small's. Pre-2020 samples are too small (35-68 events) to read either way.

**Stop-loss / profit-target grid** (`strategies/trend/exit_variants.py`),
Large/Mid/Small, gap-down reversion, 20d max hold. Every stop-loss and every
profit-target variant tested (−5%, −8%, +5%, +8%, and combinations)
**underperforms the plain fixed-20-day exit** already in use, in all three
tiers — e.g. Mid: baseline mean 5.81% (HAC-t 4.72) vs stop-5% mean 2.47%
(HAC-t 2.99), a real cost, not noise. This makes sense for a reversion
trade: a −5%/−8% stop fires almost exactly when the bounce it's betting on
would otherwise happen, converting a would-be winner into a locked-in loser.
**Verdict: no stop-loss.** The existing fixed-day exit is already the right
one for this signal family — a rare case where "add a safety rule" makes a
strategy worse, not safer.

**New "sustained relative strength" signal built and tested**
(`strategies/trend/backtest_sustained_rs.py`): persistent top-quintile
60-day return rank, required on >=15 of the last 20 days (not a one-day
snapshot like `backtest_momentum.py`). Looked strong in isolation — Large
clears |HAC-t|>=2 at all three horizons (2.01/2.53/3.04) — but folding it
into the 108-trial differential-DSR check barely moves the deflation floor
(0.1252->0.1256) and it ranks 7th-10th, nowhere near displacing
gap-down reversion. **Same failure mode as the old momentum "pass":**
large-cap sustained strength mostly measures "large caps went up," which
the differential-vs-base-rate grading is built to catch. **Verdict: no
edge**, consistent with everything else tried on large caps in this project.

**Fundamentals quality gate: still deferred, by design** (see §12 item 5).
The condition for building it — "a technical signal survives" — is now
arguably met (gap-down reversion, Mid/Small, DSR-passed, 2-regime-stable).
Worth revisiting as the next phase: does adding an ROE/earnings-growth/
debt filter improve or dilute the gap-reversion signal, or is it an
unnecessary extra variant to deflate against?

### Where this leaves the project

**Gap-down reversion (buy a >=3% intraday gap-down in an uptrend-agnostic
stock, hold 20 days, no stop-loss), Mid and Small cap tiers, is the first
and only candidate in this entire project's history to pass every gate at
once:** beats its tier's matched base rate (|HAC-t|>=2), survives deflation
for every variant tried (DSR>=0.95), replicates across two independent
regimes, and stop-loss testing confirms the simple exit is already optimal.
It is **not yet "trade this with real money"** — one more sample-period
(2024-2026 hasn't fully separated from "2023+" yet) and the fundamentals
question above are the natural next checks — but it is the strongest result
this harness has produced across PEAD, TQQQ timing, RSI pullback, breakout,
momentum, and now sustained-RS.

---

## 14. DONE — portfolio simulation & capital sensitivity (2026-09-18)

Everything in §7-13 answers "if you took this trade, what % did you make"
(per-trade edge). It does not answer "if you had $X, sized positions some
way, and could only hold N at once, what does your account actually look
like." `strategies/trend/portfolio_sim.py` is that missing piece.

**Mechanics:** starting capital, 10 equal-weight slots (10% of *current*
equity each — so it compounds automatically, see the reinvestment
discussion below), fixed-day exit only (no stop-loss, per §13), round-trip
cost by tier, extra signals skipped when all 10 slots are full. Every
strategy's entry rule is reused verbatim from its own `backtest_*.py`
module. Every strategy x tier x hold-day combo was run (9 x 4 x 3 = 108).

**A real bug was caught and fixed before trusting any of this:** the first
version's mark-to-market sum used a stale loop variable instead of each
position's own symbol, inflating equity nonsensically (a spurious -97%
drawdown from a bookkeeping error, not real trading). Fixed by iterating
`open_pos.items()` directly instead of a symbol list built in an outer
scope. Re-verified against a hand-traced day-by-day debug run before
re-running the full sweep. Flagged here because it's exactly the kind of
silent error that could have poisoned every number downstream.

**Whole-share realism, added after the first pass:** real brokers sell
whole shares, not fractions. A slot too small to afford even 1 share of a
signal's stock is now skipped (tracked as `signals_skipped_too_small_pct`),
not silently assumed fillable. This matters once capital/slots gets small
relative to share price — see the capital-sensitivity results below.

**Headline result, portfolio Sharpe ranking (full table in
`portfolio_report.html`):** `sustained_rs`/Large and `breakout`/Large rank
highest by raw portfolio Sharpe (~1.0-1.24) — but **both already failed the
per-trade statistical test** in §11/§13. Their good portfolio numbers come
from being invested often in large caps that drift up anyway (market beta),
not from a real signal — the same trap flagged for the old momentum result.
**Gap-down reversion (Mid/Small, the one proven edge) ranks lower on raw
portfolio Sharpe** (Mid: CAGR 8.2%, Sharpe 0.48, MaxDD -49%) because it only
fires often enough to fill ~3.5 of 10 slots on average — real edge, but
underused capital. The report tags every row CONFIRMED / WEAK / NOT PROVEN
against the §13 statistical verdicts specifically so a good Sharpe number
here can't be mistaken for a proven edge.

**Capital sensitivity** (`strategies/trend/capital_sensitivity.py`):
Penny/Small/Mid, gap-down reversion, 20d, at $1k/$2.5k/$5k/$10k/$25k:

| Tier | $1,000 | $2,500 | $5,000 | $10,000 | $25,000 |
|---|---|---|---|---|---|
| Mid — CAGR | 5.12% | 8.35% | 8.21% | 8.67% | 8.55% |
| Mid — skipped-too-small | 28% | 5.9% | 0% | 0% | 0% |
| Small — CAGR | 7.85% | 7.41% | 7.44% | 7.48% | 7.96% |
| Small — skipped-too-small | 7% | 2.2% | 0% | 0% | 0% |
| Penny — CAGR | 0.70% | −2.32% | −3.95% | −4.93% | −6.36% |
| Penny — MaxDD | −88.9% | −89.7% | −90.2% | −90.7% | −91.7% |

- **Mid needs roughly $2,500-5,000** before the whole-share penalty stops
  costing real performance (CAGR 5.1%→8.2%+ as skipped-rate drops 28%→0%).
- **Small works fine even at $1,000** — cheaper share prices there mean the
  whole-share constraint barely bites.
- **Penny is a dead end at every capital level tested, not a capital
  problem** — CAGR is negative and *gets worse* with more money (more
  capital fills more of the previously-unaffordable, worse-performing
  signals), and drawdown is catastrophic (-88% to -92%) regardless of
  budget. This confirms §2's Penny caveats from a different angle: don't
  fix this by adding money.

### Brainstorm: does reinvesting profits (compounding) actually help here?

The simulator already compounds — each slot is sized at 10% of *current*
equity, not a fixed dollar amount from day one, so a winning trade
automatically makes the next slot bigger. This is not a hypothetical to
test; it's already the default and it's why the Mid-tier equity curve grows
smoothly to $187-193k-equivalent-scale over the sample rather than staying
flat. So "what if profits got reinvested" is already answered: **it works,
and it's already the baseline** in every number reported above.

The real, unresolved question is *whether compounding this specific
strategy is capital-efficient*, and the honest answer is: not very, yet.
Gap-down reversion fires rarely (avg 3.5 of 10 slots filled on Mid caps) —
most of the account sits in cash most of the time, capturing nothing while
waiting for the next gap-down. Compounding a strategy that's idle 65% of
the time compounds slowly. Options worth exploring, roughly in order of
effort:

1. **Fewer, bigger slots** (e.g. 5 slots at 20% each instead of 10 at 10%)
   — since the signal rarely fills more than ~3-4 anyway, forcing it into
   10 slots dilutes capital into cash unnecessarily. Cheap to test:
   re-run `portfolio_sim.py` with `MAX_POSITIONS=5`.
2. **Combine gap-down reversion across Mid AND Small simultaneously** in
   one account (share the 10 slots across both tiers' signals) — more
   independent opportunities to fill idle slots, and Mid/Small have
   different underlying names so this adds diversification, not just more
   of the same bet. Needs a small change to `portfolio_sim.py` to accept a
   combined signal set across tiers.
3. **Park idle cash somewhere that earns something** (e.g. T-bill yield on
   uninvested cash, matching the risk-free-rate treatment already used in
   the TQQQ study, §7) instead of assuming 0% yield on cash sitting
   unused — this alone would lift the realistic CAGR without touching the
   strategy itself.
4. **Do NOT** respond to "the account sits idle" by loosening the
   gap-down entry threshold (e.g. -2% instead of -3%) to generate more
   signals — that's re-tuning the rule to the data after seeing the
   result, exactly the mistake this whole harness exists to prevent. Any
   looser threshold would need to go through the full HAC/DSR/sub-period
   gate again as a new pre-registered variant, not be adopted because it
   "fills more slots."
5. **Accept the low utilization as the honest price of a real edge** — a
   strategy that only trades on genuine, rare dislocations *should* be
   idle most of the time; forcing more frequent activity is usually how a
   real edge gets diluted into noise. 8% CAGR on Mid caps with real,
   proven statistical backing may simply be what this specific edge is
   worth, and the fix is a bigger account (so 8% is a bigger dollar
   number) or combining it with a genuinely different, uncorrelated edge —
   not squeezing this one harder.

**Recommendation:** don't touch the entry rule. Test #1 (fewer/bigger
slots) and #2 (Mid+Small combined) next — both are capital-efficiency
changes to the portfolio wrapper, not changes to the proven signal itself,
so they don't reopen the deflation/robustness question. #3 (cash yield) is
a free, honest CAGR bump worth adding regardless. Minimum practical account
size for gap-down reversion as currently sized: **~$2,500-5,000 on Mid
caps, ~$1,000 on Small caps, never on Penny.**

**Follow-up test actually run — fewer, bigger slots (`MAX_POSITIONS=5`)
on gap-down reversion, 20d, vs the 10-slot baseline:**

| Tier | Metric | 10 slots | 5 slots |
|---|---|---|---|
| Mid | CAGR | 8.2-8.7% | **18.4-20.5%** |
| Mid | Sharpe | 0.48-0.51 | 0.74-0.79 |
| Mid | Max Drawdown | -46% to -51% | -55% to -56% |
| Small | CAGR | 7.4-8.0% | 5.0-7.7% (flat to worse) |
| Small | Sharpe | 0.45-0.47 | 0.31-0.40 |

Confirms the prediction: Mid rarely fills more than ~3.5 of 10 slots, so
concentrating into 5 roughly doubles CAGR and improves Sharpe, at the cost
of a somewhat deeper drawdown (more concentration risk). Small already
fills slots efficiently at 10 and gets *worse* with fewer, bigger slots —
don't apply this change there. **Updated recommendation: 5 slots for Mid,
keep 10 for Small.**

---

## 15. DONE — quality buy-and-hold pilot (2026-09-18, PRELIMINARY)

A second, deliberately separate discipline from everything in §7-14:
instead of fast in-and-out swing trades, buy fundamentally strong,
reasonably-priced companies and hold until the fundamentals actually break
— no fixed profit target, trim only on concentration. This is explicitly
**not held to the same statistical bar** (HAC-t / DSR / sub-period
stability) as the swing work, because free fundamentals data (yfinance)
only provides **~4-5 annual financial reports per stock** — nowhere near
enough history for that machinery to mean anything. Treat everything below
as a directional pilot, not a proven strategy.

**Rules tested** (`strategies/quality/backtest_quality_bh.py`,
`harness/fundamentals.py`):
- **Buy** when, at each stock's own annual-report availability date (fiscal
  year end + 60-day filing-lag buffer, to avoid lookahead): net income > 0
  AND free cash flow > 0 AND ROE >= 15% AND revenue grew YoY AND
  debt/equity < 1 AND earnings yield >= 5% (P/E <= 20, the "don't overpay"
  check missing from the original screen).
- **Sell** (looser bar, avoids churning on one soft quarter): net income < 0
  OR FCF < 0 OR ROE < 10%.
- **Trim** (not sell) when a position exceeds 20% of the portfolio, back to
  10% — concentration control, not profit-taking.
- **No fixed profit target**, ever.
- Universe: the same systematically-screened Large+Mid+Small tiers as the
  swing work (75 names, Penny excluded — doesn't fit this discipline).
- Benchmark: equal-weight buy-and-hold of the *same* 75-name universe,
  bought day 1 — the matched base rate, same grading philosophy as
  everything else in this project.

**A real bug was caught and fixed:** the fundamentals cache used
`pd.read_json(raw_string)`, which pandas silently tried to interpret as a
*file path* rather than JSON content once the string got long enough,
throwing `OSError: Invalid argument`. Fixed with
`pd.read_json(io.StringIO(raw_string))` to force string-content parsing.
Caught immediately on the first full run rather than producing bad data
silently.

**Result, 2022-2026 window (all the annual history free data provides):**

| | Quality buy-and-hold | Equal-weight buy-everything (benchmark) |
|---|---|---|
| CAGR | 6.9% | **17.4%** |
| Sharpe | **0.80** | not computed (buy-and-hold-everything has no rebalancing cost, informal comparison only) |
| Max Drawdown | **-13.2%** | -35.5% |
| Trades | 16 buys, 2 sells, 2 trims (75-name universe) | 0 (bought once) |

**Read honestly, not spun:** this significantly **underperformed** just
buying everything and holding, on total return. But it did so with **less
than half the drawdown** (-13% vs -35%) and a *better* Sharpe ratio (0.80),
because the strict quality+value filter kept it mostly in cash or in a
small, defensive set of names during a period (2022-2026) that was
dominated by expensive, high-growth tech/AI names — exactly the kind of
stock this screen is designed to avoid buying. That's the screen doing what
it says on the tin, in a market regime where "cheap and safe" lagged
"expensive and exciting." It is not evidence the discipline is wrong; it's
evidence this specific 4-year window was unusually unfavorable for it, and
4 years is too short to conclude anything either way.

**Known limitations, unresolved:**
1. **Only ~4 usable annual snapshots per stock** — free data ceiling.
   Testing across a real bear market (e.g. 2008, 2000-02) is impossible
   without a paid fundamentals feed (Sharadar, EODHD) going back further.
2. **Debt/equity check is not sector-adjusted** — likely wrongly excludes
   or wrongly passes banks/REITs/utilities. Flagged in the original
   brainstorm, not yet fixed.
3. **Value filter is an absolute cutoff (P/E<=20)**, not a full
   cross-sectional Magic-Formula rank (quality rank + value rank combined)
   — a simplification forced by the short history making cross-sectional
   ranking noisy with so few rebalance dates. Worth revisiting with more
   data.
4. **Annual rebalancing only** — a real quality break (e.g. a fraud or
   guidance cut) could take up to a year to be reflected here, since
   detection depends on the next annual report, not quarterly ones (this
   pilot didn't use the thinner ~5-quarter quarterly data at all, to keep
   the point-in-time logic simple; a v2 could).

**Verdict: inconclusive on this data, not "doesn't work."** The lower
volatility profile (Sharpe 0.80, drawdown a third the size) is a genuinely
interesting result for a risk-focused allocation, but 4 years dominated by
one regime (expensive growth outperforming) is not enough to judge a
buy-and-hold discipline that's supposed to be evaluated over a decade-plus.
**Next steps, if pursued further:** loosen or cross-sectionally rank the
value filter instead of a hard P/E<=20 cutoff; sector-adjust the debt
check; and treat this as materially lower-confidence than the swing
project's gap-down reversion result until a paid data source allows testing
across at least one real bear market.

## 16. DONE — profit-target exit vs. compound, quality pilot (2026-09-18)

Per `QUALITY_EXIT_TEST_REQUEST.md`: does scaling out at a profit target beat
§15's "hold until fundamental break" baseline? Buy-screen and
fundamental-break logic untouched — only the exit rule varies, added to the
same file (`strategies/quality/backtest_quality_bh.py`, now takes a
`variant` argument).

**Variants tested** (50% scale-out fraction, same universe/window as §15):

| Variant | Exit rule | Trades | Win rate | Avg win/loss | CAGR | Sharpe | MaxDD |
|---|---|---|---|---|---|---|---|
| V0 (baseline) | none, compound to fundamental break | 2 | 0% | –/-19.3% | 6.9% | 0.80 | -13.2% |
| V1 | scale 50% at +5%, exit remainder on retrace below +5%, -20% floor | 25 | 84.0% | +5.5%/-13.4% | 2.98% | 0.52 | -10.5% |
| V2 | same, target +9% (midpoint of requested 8-10%) | 24 | 87.5% | +10.0%/-17.6% | 3.46% | 0.57 | -12.5% |
| V3 (redesign, see below) | scale 50% at +8%, remainder rides to fundamental break (no retrace-exit), -20% floor | 17 | 70.6% | +9.8%/-18.9% | 3.66% | 0.54 | -12.5% |

Benchmark (equal-weight buy-and-hold, same universe): **17.41% CAGR**.

**Gate result: FAIL for V1, V2, and the V3 redesign.** All three clear
criterion 1 (win rate beats the actual breakeven computed from their own
avg win/loss — e.g. V1's 84% beats its 70.7% breakeven) and criterion 3
(MaxDD well inside the -30% tolerance, using the realistic same-day
auto-sell floor, not an idealized number). **All three fail criterion 2**
(CAGR > benchmark) by a wide margin — none gets within 5x of the 17.4%
benchmark CAGR.

**One redesign used, per the stop rule:** V1/V2's forced exit on every
retrace below target was suspected of killing compounding and leaving
capital idle in cash between annual rebalance dates. V3 tested that theory
by dropping the retrace-exit and letting the un-scaled remainder ride to a
fundamental break, same as V0. It did not fix the underperformance — CAGR
barely moved (3.66% vs V1/V2's ~3%). The real constraint is upstream of the
exit rule: this is a 15-position, annually-rebalanced screen in a 4-year
window dominated by expensive growth names the screen is designed to
avoid, per §15 — no exit-rule change compounds fast enough to close a
14-point CAGR gap against buy-everything in that setup.

**Verdict, per the stop rule: no further iteration. V0 (no profit target)
remains the accepted answer — the profit-target idea is dropped.**

**What this result does NOT prove** (per the test request's explicit scope
limits — stated plainly, not just in the request doc):
1. **Fundamentals here are annual-only** (yfinance, ~5 years of history).
   The live bot's intended "2 consecutive quarters" fundamental-break rule
   is a *different, untested* rule — this backtest only exercises an
   annual approximation of it. This result settles the
   profit-target-vs-compound exit question only; the fundamental-break
   trigger itself remains unvalidated.
2. **The -20% floor is modeled as an instant auto-sell**, same day the
   breach happens. Live trading with an alert-then-human-approval step will
   underperform this backtest due to response delay — read the -20%
   floor's MaxDD numbers above as an optimistic upper bound, not an
   achievable one.
3. **Single 4-year regime** (COVID crash, 2022 bear, 2023-24 rally) — same
   caveat as §15. A clean pass here wouldn't have been proof of a durable
   edge either.

**Results file:** `quality_bh_results.json`, now keyed by variant
(`V0`/`V1`/`V2`/`V3`), each block matching §15's original field shape plus
new per-variant fields (`n_trades`, `win_rate`, `avg_win_pct`,
`avg_loss_pct`, `avg_hold_days`, `stale_positions_gt_2q`,
`n_profit_scale_outs`, `n_floor_exits`).

## 17. DONE — gap-down reversion: Mid+Small pooled in one account (2026-09-19)

`strategies/trend/combined_gap_sim.py`. Follow-up to §14's capital-efficiency
ideas: pool Mid and Small gap-down signals into one account to fill idle
slots. Entry rule unchanged (>=3% gap-down, 20d hold, no stop). $5,000
start, whole shares. Pooled account charges Small's higher 35bps cost on
every trade (conservative). No T-bill yield on idle cash (simulator doesn't
model it).

| Account | Slots | CAGR | Sharpe | MaxDD | Avg slots filled |
|---|---|---|---|---|---|
| Mid alone | 5 | **18.66%** | **0.75** | -55.4% | 2.6 |
| Mid alone | 10 | 8.21% | 0.48 | -49.4% | 3.6 |
| Small alone | 5 | 7.66% | 0.40 | -56.1% | 2.8 |
| Small alone | 10 | 7.44% | 0.45 | -47.4% | 3.9 |
| Mid+Small pooled | 5 | 14.08% | 0.57 | -61.0% | 3.4 |
| Mid+Small pooled | 10 | 9.76% | 0.48 | -63.7% | 5.7 |

- **Verdict: pooling does not help.** At 5 slots it loses to Mid alone on
  CAGR, Sharpe and drawdown (Small's weaker signals crowd out Mid's). At 10
  slots it edges Mid alone on CAGR (9.8% vs 8.2%) but with a much deeper
  drawdown (-64% vs -49%). **Recommendation stands: Mid alone, 5 slots.**
  Keep Small separate (10 slots).
- **Read as in-sample only.** Every number here comes from the same sample
  the rule was selected on. This is portfolio optimization, not validation;
  treat 18.7% as an upper bound, not a live expectation.
- **Correction to earlier framing:** the "2023+" slice in
  `gap_reversion_robustness.py` has no upper bound and the data covers ~2018
  to 2026, so it already includes 2024-2026. There is **no out-of-sample data
  in this project**. The only true out-of-sample test is forward
  paper-trading with the rule frozen; a 2024+ re-split would be a
  confirmatory sanity check, not validation. Not run, by request.
- **Still unmodeled:** T-bill yield on idle cash; drawdowns of -55% or worse
  are the real risk at 5 slots.

---

## 15. DONE (partial coverage) — US S&P 1500 screen + sell-rule test, 2026-10-19

`analysis/us_universe_scan.py` -> `analysis/us_scan_screen.csv`, `us_scan_rules.json`.
Universe: S&P 500/400/600 (1,503 names). Rerun with slow retries 2026-10-19: 1,463 of 1,503 scored, 232 pass (Large 108, Mid 58, Small 66); ~40 unscored.
Screen = Fortress verdict.ts fundamentals (growth/profit/debt/price/cash) >= +2 and 50>200 trend.
Live screen only: today's fundamentals, not point-in-time, so not a backtest.

Sell rules, buy every stock each quarter from 2021 (33,616 buys, prices only), mean / median return per buy:
hold 56% / 22% - seat belt 20% 7% / -4% - sell +20% 13% / 21% - +10% 7% / 11% - +5% 4% / 6% - under 100DMA 1.5% / -0.8% - under 20DMA 0.3% / -0.8%.
Same order as Deepak's India lots: hold wins, moving-average exits are worst.
Caveats: survivorship (today's index members), 2021-26 bull market, buys are not annualised
(early buys had longer to run), exited cash does not compound. Rule ranking is the signal, not the %.

**India (Nifty 500, same rules, `.NS`):** 495 of 501 scored, 33 pass. 9,612 buys, mean / median:
hold 62% / 11% - seat belt 17% / -2% - sell +20% 10% / 21% - +10% 6% / 11% - under 100DMA 5.6% / -0.3% - +5% 3% / 6% - under 20DMA 1.4% / -0.5%.
Same top and bottom as the US. Page for both: `reports/US_India_Screen.html` (built by `analysis/build_scan_html.py`).

**Other markets (19 Oct 2026, same rules):** Taiwan 50 (24 of 50 pass), JPX-Nikkei 400 (125 of 400), Europe large caps (46 of 195), Malaysia hand-picked 24 (1 pass). Hold first and 20-day exit last in every market. Korea, China not screened.
Single page for all six: `reports/Global_Stock_Screen.html` (`analysis/build_scan_html.py`, stdlib only). Supersedes `US_India_Screen.html`.
Env note: pandas/numpy in the user Python site-packages was broken on 2026-10-21 (numpy `_multiarray_umath` missing); the scan scripts need pandas, the page builder does not.
Price column (2026-10-21): `build_scan_html.py` now fetches current prices for the listed stocks from Yahoo's chart endpoint (stdlib) and converts to USD and MYR (USDMYR 4.0815). Python on this machine was damaged (pip/numpy files missing), so yfinance cannot be used until it is repaired.
Env fix (2026-10-21): global Python was damaged; scan scripts now run from `C:\Antigravity\Backtesting\.venv` (`.venv\Scripts\python -m analysis.us_universe_scan <US|IN|TW|JP|EU|MY>`). Malaysia list: 5336 (CKI, wrong company) replaced by 5286 (MI Technology). Full refresh of all six scans queued 21 Oct; counts above are the 19 Oct run until it finishes.

## 18. DONE (snapshot 1 of N, NOT a backtest) — US CAN SLIM check, 2026-10-24

`reports/canslim_us/canslim_yf.py` (yfinance, self-test passes). Input: 53 names from `analysis/us_scan_screen.csv`
(above trend, mcap > $2B, sales growth >= 15%, ROE >= 15%, OCF > 0, NI > 0). Output frozen:
`canslim_2026-10-24.csv/.md`. Rules at top of the script. Free data cannot backtest this; the list is a forward-tracking start.
- **M gate: NO-GO.** SPY below 50-day, above 200-day, 7 distribution days in 25 (limit 5). FMP skill also said "choppy", M 40/100.
- 6 of 6 letters: LLY only. 5 of 6: P, PLTR, MSFT, FTNT, MEDP. 12 of 53 are Energy (oil > $100, likely a price spike, not growth).
- The `canslim-screener` skill (FMP) does not work on the free key: most symbols return 402 "premium". Paid Starter plan is ~$30/mo, Bharat's call.
- Next snapshot 2026-11-01, then monthly. Grade each against SPY at 3 and 6 months. Do not edit a frozen list.
- View: open `reports/canslim_us/canslim_2026-10-24.html` in any browser (gate banner + colour table). Script now writes the .html each run and refuses to overwrite a frozen snapshot.
- Scheduled 2026-10-24: task `us-canslim-monthly-snapshot`, 1st of each month 09:00 local (runs only while the Claude app is open; otherwise on next launch). Refreshes the screen, snapshots, grades snapshots 90+ days old vs SPY into `reports/canslim_us/grading.csv`. First grade due 2027-01-22. Run with `.venv`, not system Python.
- Monthly run 2026-10-24 (scheduled-task test): universe scan refreshed OK, selftest OK, snapshot already frozen today so not rewritten. Gate still NO-GO, top name LLY (6/6). Grading: too early, first grade due 2027-01-22.
- **Six buckets (2026-10-24, Bharat's request):** US_large (over $2B, frozen v1, quality pre-filter), US_small ($500M-$2B), US_penny (price under $5, mcap over $30M, over $500K/day traded), IN_main (Nifty 500 over Rs 4,200 cr), IN_small (Rs 500-4,200 cr), IN_penny (price under Rs 30, mcap over Rs 100 cr, over Rs 50 lakh/day). Penny + small = the risky sleeve, kept separate. All except US_large use a price funnel (liquid, within 15% of 52w high, up 12m) before fundamentals, because Yahoo cash-flow/ROE is missing for many Indian names and the first quality pre-filter wrongly cut IN_main to 5 names. Funnel counts are printed on each page. Pages: `reports/canslim_us/index.html`. Code: `canslim_yf.py` + `canslim_universe.py`. Monthly task now runs all six.
- Limits: India ROE falls back to net income / equity when Yahoo has none; Russell-only US names outside the S&P 1500 are not in US_small; ADRs, SPACs, units and warrants are excluded from US_penny.
- **First six-bucket snapshot, 2026-10-24 (all gates NO-GO; India gate: Nifty 500 below 50d and 200d, 11 distribution days).** Floors applied: US_penny mcap over $50M / over $500K a day; IN_penny mcap over Rs 250 cr; IN_small and IN_penny over Rs 1 cr a day traded (raised from Rs 50 lakh after Bharat asked for separate floors).
  Names with 5+/6: IN_main 10 (VIJAYA, RADICO, MCX at 6/6), IN_small 3 (SHANTIGOLD, UNITEDPOLY, SBC), US_large 6, US_small 0, US_penny 0, IN_penny 0.
  Why so few in the small/penny buckets: only 6 of 53 US small caps near highs grew sales 20%+ (mostly banks and slow growers); 94% of US penny names have no usable earnings-growth number (loss-making). Data gaps do not explain it (sales growth missing for 0-5%).
  Caveats: IN_small passes fail the I letter (institutions own little of tiny Indian names); PCJEWELLER sits in IN_penny at Rs 17,700 cr mcap because its price is low, not its size; penny bucket is price-defined. Still not a backtest.

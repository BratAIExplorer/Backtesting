# Research Harness — Status

*Last updated: 2026-09-14. Working document: what's built, what's run, what's
pending. The eventual polished write-up is `FINDINGS.md` (not written yet).*

*Split 2026-09-18: all US-only strategy sections (former §7-16) moved to
`FINDINGS_US.md`, at Bharat's request — one file for US backtesting. This
file keeps harness build notes, pending items, and India/cross-market
results (§2's India subsection stays here; its US subsection moved).*

---

## 0. Why this exists

FinFlow retracted its one "real signal" (`FinFlow/CURRENT_STATUS.md`) after
finding a wrong null, absolute-vs-relative grading, and overlapping samples
inflated by ~80x. `strategies/BACKTEST_FINDINGS.md` had already produced a
well-replicated null across 4 strategy families, 2 countries, 15 years.

The user's question: **can we find signals that get better over time and help
day/swing trading — or do we give up?** Answer chosen: take the challenge, but
only with a harness that makes the previous failure mode structurally hard to
repeat. `harness/` + `strategies/` is that harness.

---

## 1. DONE — the harness (Tier 0)

7 files, all self-checks passing. Nothing here touches the live bot.

| File | What it does | Verified |
|---|---|---|
| `harness/stats.py` | Newey-West HAC t-stat; moving-block bootstrap CI (mean + difference); two-sample HAC test; Probabilistic/Deflated Sharpe (Bailey-Lopez de Prado); hit-rate test vs a *matched* base rate; overlap-corrected effective n | `python -m harness.stats` ✅ |
| `harness/walkforward.py` | `PurgedKFold` + expanding `walk_forward_blocks` (purge + embargo) | `python -m harness.walkforward` ✅ |
| `harness/data.py` | Cached daily bars (auto_adjust), earnings events w/ point-in-time SUE, GDELT historical news (throttled, retried, cached) | `python -m harness.data` ✅ |
| `harness/signals.py` | PEAD event build (hard no-lookahead: entry = close of first day *strictly after* announcement); point-in-time quintiles; calendar-time weights; generic forward-abnormal returns; news features | `python -m harness.signals` ✅ |
| `strategies/pead/run_pead.py` | The PEAD study, pre-registered criteria | run on India + US ✅ |
| `strategies/pead/run_news.py` | India news study, pre-registered criteria | **built, NOT run** ❌ |

**Design principle enforced in code:** every signal is graded against a matched
empirical base rate, never a 50/50 assumption; overlapping windows are handled
by HAC/block bootstrap, not naive z; every result is deflated by the number of
variants tried.

---

## 2. DONE — PEAD results (both markets)

Pre-registered PASS = all four of: |HAC t|≥2 @20d, DSR≥0.95, net long-short
Sharpe>0 (t≥2), long hit-rate beats base rate (z≥2).

### India — 16 large/mid caps, NIFTYBEES benchmark, 6y
1,279 events (1,259 point-in-time ranked).

| Horizon | Spread (abn vs index) | HAC t | Boot CI | Base rate | Top hit | hit_z (overlap-corr.) |
|---|---|---|---|---|---|---|
| 1d | +0.07% | 0.65 | −0.14 … 0.29 | 51.8% | 49.6% | −0.69 |
| **5d** | **+0.76%** | **3.45** | **0.32 … 1.18** | 40.3% | 54.7% | **2.10** |
| 20d | +1.59% | 2.17 | 0.56 … 3.37 | 37.0% | 39.8% | 0.21 |
| 60d | −2.25% | −1.48 | −6.18 … −0.71 | 52.8% | 48.1% | −0.19 |

- Calendar-time net long-short Sharpe: 0.44 / 0.03 / −0.49 / −0.09 (1/5/20/60d)
- Buy & hold benchmark: Sharpe 1.20, +16.2%/yr
- DSR **0.538**
- **Verdict: NO EDGE** (crit 1 PASS; crit 2, 3, 4 FAIL)

### US — moved to `FINDINGS_US.md` §2

Same PEAD study, US market (16 large caps, SPY benchmark) — see
`FINDINGS_US.md` §2 for the full US subsection (verdict: NO EDGE, all four
criteria fail).

### The one live lead
A **real but small 5-day gross PEAD effect in India** (t=3.45, and the
overlap-corrected hit-rate z=2.10 still clears 2). It does **not** survive:
costs (net LS Sharpe ≈ 0), deflation (DSR 0.54), or any longer horizon. This is
the only thing so far that isn't pure noise — and it is not yet tradable.

---

## 3. NOT DONE — news study (blocked, not skipped)

`strategies/pead/run_news.py` is written and the data layer works, but it has **never completed
a run**. Status:

- GDELT is the only free *historical* news source (Google News RSS and yfinance
  news are current-only → unbacktestable). Confirmed working: 2-year range in
  one call, daily volume + tone.
- **Blocker:** GDELT hard rate-limits (HTTP 429) after a burst. A 12-ticker ×
  2-mode pull (24 calls) was aborted. Only 1 GDELT cache file exists (a probe).
- **No news result exists yet. Nothing has been concluded about news.**

---

## 4. PENDING — prioritised

**P1 — Run the India news study** (`python -m strategies.pead.run_news`). Needs a slow,
throttled, resumable pull (caching already supports resume). Answers the user's
explicit question: does news make a difference, standalone and *incremental to*
the 5-day PEAD effect.

**P2 — Stress-test the India 5-day PEAD lead.** It's the only non-null. Before
believing or discarding it: more names (Nifty 100/200), more years, sub-period
stability (is it one regime?), and a **point-in-time universe** — the current
one is today's constituents (survivorship bias, flagged in `BACKTEST_FINDINGS.md` §4).

**P3 — pytest suite.** The harness has `__main__` self-checks but no test files.
Needed: no-lookahead regression tests, stats correctness, GDELT parser.

**P4 — Write `FINDINGS.md`** — the honest public write-up (mirroring the tone of
`BACKTEST_FINDINGS.md`).

**P5 — US phase.** User instruction: news/US is the *next* phase, India first.

---

## 5. Open data question (blocks deeper work)

The user's steer (this session): **do not subscribe to EODHD yet.** Test PEAD on
free data first; only pay if PEAD-alone shows something worth refining; skip
FinBERT/sentiment infra until then.

- **Free data is sufficient for what we ran:** `yfinance` gives ~25 quarters of
  earnings dates + consensus EPS estimate + actual + surprise, India and US.
  That is what produced the India 5-day lead — **no paid feed needed to get here.**
- **Where free data runs out:** point-in-time *fundamentals* and a
  survivorship-free universe (P2). Those genuinely need EODHD / Sharadar / NSE
  bhavcopy+announcements. Not needed until the lead survives P2.
- **Unresolved:** what free NSE earnings-surprise/consensus history actually
  exists outside yfinance (NSE/BSE corporate announcements + bhavcopy). This is
  the real blocker for a rigorous India PEAD re-test. **Not yet scoped.**

---

## 6. Honest caveats on everything above

- Universes are **today's** index members → survivorship bias inflates all results.
- 6 years, one regime (a strong bull). Sub-period stability untested.
- Costs are modelled (20bps one-way India, 4bps US), not real fills.
- GDELT coverage of Indian names is sparse and its "tone" is a rough proxy.
- A partial pass is still NO EDGE. Two markets, and only one small gross lead
  survived — consistent with the org's existing null.

---


## 7-16. US-only strategy results — moved to `FINDINGS_US.md`

TQQQ/SQQQ regime timing, RSI pullback, breakout, momentum, gap-down
reversion, portfolio simulation/capital sensitivity, and the quality
buy-and-hold pilot (+ its profit-target exit test) are all US-equity work.
Moved to `FINDINGS_US.md` §7-16 on 2026-09-18 so US backtesting lives in one
file, separate from harness notes and India/PEAD results here.

**Headline results, if you just need the summary:** every systematic
US swing-trading signal tested (RSI pullback, breakout, momentum, TQQQ
regime timing) came back NO EDGE once graded against a matched base rate
and deflated for the number of variants tried — except **gap-down
reversion (Mid/Small cap, 20-day hold)**, which is the one strategy in this
project's history to pass every gate (HAC-t, DSR≥0.95, 2-regime stability).
The quality buy-and-hold pilot underperformed its benchmark on raw return
but with a third of the drawdown; its profit-target exit variants (V1/V2/a
redesign V3) were tested and all failed to beat the buy-and-hold benchmark,
so the original no-profit-target design stands. Full detail, numbers, and
caveats in `FINDINGS_US.md`.

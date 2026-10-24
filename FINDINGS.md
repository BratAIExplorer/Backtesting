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

## 17. EMA 7 / EMA 20 crossover (run 2026-10-12)

`strategies/trend/backtest_ema_cross.py` (+ `tests/test_backtest_ema_cross.py`).
Long-only; buy on cross-up, sell on cross-down, next-open fills, 8y daily bars.
Universe: US Large/Mid/Small/Penny (`_common.UNIVERSES`, 90 names) + NIFTY 50
(48 loaded; LTIM, TATAMOTORS have no Yahoo data). Costs: round-trip bps per
tier (US per `_common.COST_BPS`; NSE flat 20 — a guess).

| Tier | Strategy total | Buy & hold | Beat B&H | Win rate | 20d signal vs base (HAC-t) |
|---|---|---|---|---|---|
| US Large | +189% | +239% | 17% | 34% | +1.63 vs +1.52 (0.3) |
| US Mid | +71% | +365% | 24% | 34% | +1.67 vs +1.70 (-0.1) |
| US Small | -2% | +129% | 15% | 28% | +0.70 vs +1.33 (-1.2) |
| US Penny | -76% | -81% | 67% | 21% | -0.15 vs +3.99 (-1.7) |
| NSE (NIFTY 50) | +136% | +233% | 17% | 36% | +2.00 vs +1.49 (2.7) |

**Verdict: NO EDGE.** The strategy lost to buy-and-hold in every tier (Penny
"beat" it only because both lose ~80%). The one nominal signal, NSE 20d
(HAC-t 2.7), is 1 of 15 tests, not deflated, and the actual cross-down exit
still trails buy-and-hold on NSE — it does not survive as a tradable rule.
Caveats: NIFTY 50 is current constituents (survivorship bias), universes are
the existing lists, not every NSE/EUR segment. Not tested: NSE mid/small/penny,
Ireland/EUR UCITS ETFs (no lists exist yet).

## 18. Golden Cross SMA50/SMA200, NSE daily (run 2026-10-19)

Source: YouTube claim (67% on 1h gold futures). Tested via
`strategies/trend/backtest_golden_cross.py`: long-only, next-open fills, 20bps
round trip, 10y daily, NIFTY 50 stocks (48 with data; LTIM, TATAMOTORS missing) + ^NSEI.

**Verdict: NO EDGE vs buy-and-hold.** Index +18.5% vs +129.7% hold (6 trips,
max DD -40%). Median stock +70% vs +207% hold; beat hold in 4/48. Pooled
309 trips: win 45%, PF 3.5, but driven by a few big winners and out of market
~45% of the time. Caveat: current constituents (survivorship bias); cost is a flat guess.

## 19. Dad's real trades vs Golden Cross vs Hold (run 2026-10-19)

Source: broker trade file 5 Jan – 16 Oct 2026 (1,919 trades, 61 stocks priced).
Code: `analysis/dad_trades.py` (FIFO matching), `analysis/dad_vs_strategies.py`
(same stocks, same rupees = dad's peak money per stock, ₹16.9L, from his first
trade in each stock). Output CSVs in `analysis/` (contain personal trade data — do not commit).

**Verdict: Hold > Golden Cross > Dad.** Profit: hold ₹7.2L (+43%), Golden Cross
₹4.4L (+26%), dad ₹0.69L (+4%, after est. costs ₹24k). Nifty 50 same window −11.8%.
Dad is a swing trader (3% same-day, 23% 1–7d, 65% 8–30d, 9% >30d); 1–7d made
68% of sold-trade profit. Win rate 91% but avg loss ₹461 vs avg win ₹198;
realized +₹2.33L, open positions −₹1.40L.
Caveats: hindsight on stocks he picked; costs are a 0.13%/side guess; pre-2026
holdings excluded; ESDS no price data; "same money" is approximate; ~9 months only.
Deck: claude.ai/artifact/CHQLK2y77E6ey15bjczNuw (private).

## 20. Deepak's own lots replayed under exit rules + research (run 2026-10-19)

`analysis/deepak_rules.py`: his 1,761 buy lots (same buys/dates, daily closes to
16 Oct 2026, 0.13% sell cost): hold ₹9.9L > sell +20% ₹7.7L > stop −15% ₹7.3L >
stop −10% ₹6.3L > sell +10% ₹4.5L > sell after 20d ₹2.8L > sell +5% ₹2.5L >
his actual ₹0.9L > sell after 5d ₹0.4L. Hold's gain is concentrated (top 5
stocks = 122% of it; 24 of 61 gained). Without AVALON hold ₹2.7L vs actual ₹0.2L.
Verdict across all 13 ideas in this file: none beats holding; gap-down reversion
(US Mid/Small) passes its gates but earns about what holding does, in-sample.
Research notes (SEBI, Odean, Barber-Odean, Bessembinder, missed-best-days):
`research_notes/Retail trading vs holding evidence/`. SEBI/fund-house numbers are
second-hand (SEBI site not fetchable). Deliverables: `reports/Deepak_vs_Holding_Report.html`
and the slide deck (claude.ai/artifact/CHQLK2y77E6ey15bjczNuw, private).

## 21. India-only insights for the Deepak deck (run 2026-10-19)

`analysis/india_insights.py` -> `analysis/india_insights.json`. (A) Nifty fund on
his money −₹1.37L: picking +₹8.57L, selling −₹6.51L, he beat the index by ₹2.06L.
(B) 56% of his 1,919 trades were in June; profit in 9 of 10 months. (C) 74% of
sales saw a flat/lower price 20d later (saved ₹3.6L), 26% rose (missed ₹8.6L).
(D) trailing stop 15/20/25/30% on his buys: ₹8.4/8.8/7.7/8.5L vs hold ₹9.9L vs
actual ₹0.9L. (E) NIFTY 50, 10y: 20-day breakout +1.63% vs base 1.43% (t=1.2),
RSI<35 dip +0.64% (t=-1.8), 5-day low +1.30% (t=-1.0): all no edge.
All US tests removed from the deck/report (kept in §2-§17).

## 22. Deck v3: dates/prices, market conditions, trend exits (run 2026-10-19)

`analysis/slide_tables.py` -> `analysis/slide_tables.json`. First-buy table (date, price) and
case files for his biggest stocks; true win rate 91% closed / 88% incl. open lots (64 of 68
open lots under water); 5 stocks = 91% of the "sold too early" regret (AVALON ₹3.6L,
KERNEX ₹2.2L, IDEA ₹1.2L); trend-exit on his buys: below 20d avg ₹1.4L, 50d ₹3.7L,
100d ₹7.2L (hold ₹9.9L, actual ₹0.9L). Market 1 Jan→16 Oct 2026: Nifty 50 −11.5%,
Sensex −12.3%, Midcap150 −3.7%, Smallcap250 +5.8%, VIX 14 (peak 27.9). Open book ₹7.2L,
22 stocks, −₹1.4L; KERNEX 17%, BSE 13%, IDEA 10.5%. Nifty Golden Cross: last death
cross 17 Mar 2026 (rule +18.8% vs hold +29.8% since 9 Sep 2022).

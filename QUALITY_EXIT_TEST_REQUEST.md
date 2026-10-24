# Test Request: Profit-Target Exit vs. Compounding — Quality US Stock Strategy

**Requested by**: Bharat
**Date**: 2026-09-18
**Status**: CLOSED — run 2026-09-18. Result: FAIL (V1/V2/redesign V3 all
failed the CAGR-vs-benchmark gate). V0 accepted, profit-target idea
dropped. See FINDINGS.md #16.

## Objective

The existing quality pilot (`strategies/quality/backtest_quality_bh.py`) has no
profit target — positions are held until a fundamental break, letting winners
compound (see `FINDINGS.md` #14). Bharat wants to test whether a **profit-target
exit** (scale out in chunks above a threshold, exit remainder on retrace below it)
beats that baseline. This contradicts the prior conclusion, so it needs to be
measured, not assumed, before any live bot is built on it.

**This is a request for the Testing project to design and run the backtest.**
No backtest code or bot code has been written as part of this request.

## Variants to test

Reuse the existing buy-screen and fundamental-break logic in
`backtest_quality_bh.py` unchanged (net income > 0 AND FCF > 0, ROE >= 15% buy /
< 10% sell, revenue growth, D/E < 1, earnings yield >= 5%, 60-day filing lag,
20%/10% concentration trim). Only the **exit rule** varies:

| Variant | Profit exit | Loss floor | Fundamental break |
|---|---|---|---|
| **V0** (existing baseline) | none — compound until fundamental break | none | net income<0 / FCF<0 / ROE<10% (existing) |
| **V1** | scale out in chunks above +5%, exit remainder on retrace below +5% | -20% | same as V0 |
| **V2** | same mechanism, target +8–10% | -20% | same as V0 |

## Metrics required per variant

- CAGR, Sharpe, MaxDD, total return
- Win rate, avg win %, avg loss %, trade count, avg hold time
- Equal-weight benchmark (existing convention in `backtest_quality_bh.py`)
- Count of stale positions: held >2 quarters with no exit triggered

## Pass/fail gate

All three must hold for **V1 or V2** to pass:

1. Win rate > implied breakeven (breakeven = avgLoss / (avgWin + avgLoss); with
   +5%/-20% sizing this is roughly 74–80% — compute exactly from the actual
   avg win/loss produced by the run, don't use the approximation as the gate).
2. CAGR > benchmark CAGR.
3. MaxDD better than -30% (Bharat's stated tolerance), measured against the
   **realistic auto-sell path** (i.e. the -20% floor executes immediately in
   the backtest, same as it will need to be modeled — do not use an idealized
   instant-response number that live trading won't be able to match).

## Stop rule (do not skip this)

If none of V0/V1/V2 clears the gate: **one** redesign variant is permitted
(e.g. a wider target or tighter floor). After that variant is tested, accept
whatever the result is — no further iteration. If everything still fails, V0
(no profit target) is the accepted answer and the profit-target idea is dropped.

This exists to prevent re-tuning the target repeatedly until something clears
the bar on backtest noise rather than genuine edge.

## Explicit scope limits — what a PASS does NOT prove

State these plainly in the findings writeup, not just here:

1. **Fundamentals are annual only** (yfinance, ~5 years of history). The
   quarterly "2 consecutive quarters" fundamental-break rule that the eventual
   live bot is meant to use is a **different, untested rule** — this backtest
   only exercises an annual approximation of it. A PASS validates the
   **profit-target-vs-compound exit decision only**, not the fundamental-break
   trigger, which remains unvalidated even after a PASS.
2. **-20% floor modeled as instant auto-sell.** Live trading with an
   "alert + human approval" step will underperform this backtest due to
   response delay — the backtest result should be read as an optimistic upper
   bound on the loss-floor's effectiveness.
3. **5-year window is one regime mix** (COVID crash, 2022 bear, 2023–24 rally).
   Even a clean PASS is directional evidence, not proof of a durable edge.

## Requested deliverables

- A results file (JSON), following the existing convention (see
  `quality_bh_results.json` for the baseline's existing output shape).
- A findings entry appended to `FINDINGS.md`, in the same format as existing
  numbered entries, explicitly including a "what this PASS does NOT validate"
  note per the scope limits above.

## Out of scope for this request

- No bot or live-trading code.
- No changes to the existing `backtest_quality_bh.py` buy-screen or
  fundamental-break logic — only new exit-rule variants are to be added.

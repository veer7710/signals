# Experiment ledger

Vocabulary (never blur these):
- **CONFIRMED** — replicated out-of-sample, survived adversarial review
- **SUPPORTED** — positive across walk-forward, costs, and Monte Carlo
- **PROMISING** — positive but not yet adversarially attacked
- **UNPROVEN** — result not distinguishable from noise
- **REJECTED** — negative expectancy after realistic costs
- **DISPROVEN** — a specific claim shown false

Command to reproduce all of these: `python3 JARVIS/research/study.py GOLD 1h`
Engine must pass `python3 JARVIS/research/test_engine.py` first.

---
## E-001 — Does the old signal system have an edge? (DISPROVEN)
- **Hypothesis:** the deleted scanner's intraday engine had a real edge
  ("~$150/day potential").
- **Data:** its own live-tracked log, 30 intraday trades, 2026-07-16 → 08-25.
- **Result:** 70% win rate, but average R:R 0.53 → break-even needs 65.4%.
  Wilson 95% CI on the win rate: 52.1%–83.3%, straddling break-even.
  Monte Carlo against a skill-free null with identical stop/target geometry:
  a random system beat its +$34.40 **32.2% of the time**.
  29 of 30 trades were LONG during a +17% gold bull run.
- **Conclusion:** DISPROVEN as an edge. Realised P&L was +$8.19/day, and
  96% of that came from a single swing trade that risked 100% of the account.
- **Do not repeat:** do not resurrect this logic without fixing R:R first.

## E-002 — Does the capped-target design cause the failure? (CONFIRMED)
- **Hypothesis:** capped TP + ATR-scaled SL is the structural fault.
- **Test:** `capped_target_trap` on GOLD 1h, 13,750 bars, 2024-04 → 2026-08.
- **Result:** 666 trades, **69.5% win rate** — and **-0.066R expectancy**,
  PF 0.79, -43.9R total, 0/6 walk-forward folds positive, P(losing) 99.6%.
- **Conclusion:** CONFIRMED. The design loses money *while winning 70% of
  trades*, exactly reproducing the live result. Root cause established.

## E-003 — Liquidity sweep / stop-run on gold (UNPROVEN, leaning REJECTED)
- **Hypothesis:** price spikes past swing highs/lows to trigger resting
  stops, then reverses; fading the sweep has an edge.
- **Test:** `liquidity_sweep`, GOLD 1h, 603 trades, 2 years.
- **Result:** +0.001R expectancy, t=+0.02, PF 1.00. Walk-forward 3/6.
  **Dies as costs rise:** 2x spread → -0.031R, 3x spread → -0.061R.
  Shorts (+0.054R) marginally better than longs (-0.018R).
- **Conclusion:** UNPROVEN. The raw concept has no edge on gold 1h at retail
  cost. NOT yet a verdict on liquidity as a family — only on this
  implementation and timeframe. Next: test on 15m, test session-scoped
  levels (prior day/week high-low), require displacement confirmation.

## E-004 — Donchian breakout trend-following (PROMISING)
- **Hypothesis:** classic 55-bar breakout + EMA20/100 filter + fixed 3R.
- **Test:** `donchian_trend`, GOLD 1h, 224 trades, 2 years.
- **Result:** 31.7% win rate, **+0.198R expectancy**, PF 1.28, +44.2R,
  max drawdown 9.7%. **Walk-forward 5/6 folds positive.** Survives 3x
  spread (+0.157R). Monte Carlo: P(drawdown>30%) = 0.0%,
  P(losing overall) = 5.6%.
- **Caveats:** t-statistic +1.63, below the t>2 bar, so the engine
  classifies it UNPROVEN by the strict rule. Longs (+0.292R) far outperform
  shorts (+0.007R) — likely gold's bull run. Worst losing streak 16 trades.
- **Conclusion:** PROMISING and the strongest candidate found. The boring
  classic beat the sophisticated liquidity concept. Must now face the
  adversarial reviewer and out-of-sample data on other symbols.

## E-005 — EMA pullback continuation with fixed R:R (REJECTED)
- **Result:** 102 trades, -0.142R expectancy, PF 0.80, 0/6 folds positive.
- **Conclusion:** REJECTED. Fixing the R:R alone does not rescue the old
  entry logic — the entries themselves carry no edge.

## E-006 — Is XAUUSD_QUAD v19.18 viable? (REJECTED)
- **Files:** received 2026-08-27, stored in `JARVIS/ea/inbox/`.
- **Measured:** 20,695 lines, 9,596 code lines, **748 input parameters**,
  274 functions, ~20 versions of patching (v12 -> v19.18).
- **Evidence from the EA's own header (its own live results):**
  spread bill GBP76.53 = **48% of the loss**; 153 of 188 losers never went
  GBP0.30 green; a -GBP159.79 day; efficiency ratio 0.038 (26:1 churn);
  hold time 4 min against a median 42-min move; 21 of 32 live exit routes
  fired ZERO times across 279 trades.
- **Cost arithmetic:** M1 gold, 1.40 x ATR stop = 1.40 price, against a
  0.30 round trip = **21.4% of risk lost to cost** before any edge.
- **Conclusion:** REJECTED as a live candidate. Root causes are structural:
  (a) 748 parameters cannot be validated on 279 trades, (b) M1 cost/risk is
  fatal, (c) exits fire before the move happens. Full audit in
  `JARVIS/ea/AUDIT_v19_18.md`.
- **Do not:** patch it to v19.19. Twenty rounds of patching is the failure
  mode, not the fix.

## E-007 — Timeframe effect on the same strategy (INCONCLUSIVE)
- **Test:** donchian_trend on GOLD 15m resampled to 30m/1h/2h, same costs.
- **Result:** 15m +0.130R (74 trades), 30m -0.022R (32), 1h -0.072R (17),
  2h +0.982R (4 trades).
- **Conclusion:** INCONCLUSIVE — only 70 days of 15m data exists, so the
  higher timeframes have far too few trades to read. Recorded so no future
  session mistakes this for evidence. The cost/risk arithmetic in E-006
  stands on its own and does not depend on this test.
- **To settle it:** need 15m history going back 2+ years.

# PROJECT TITAN — mission and live state

**Read this file first in any new session.** It is the entry point; the
filesystem is the memory, not the conversation.

## The mission
Discover whether a genuinely robust edge exists in the data we can reach, then
engineer the best implementation of it. Two products: one Pine for human
execution, one MT5 EA for automated execution. They need not share a strategy.
Existing code and ideas are disposable. Only evidence counts.

## Where we actually are — 2026-08-31

### The two results that dominate everything

**E-037 — the markets test as random walks.** Lo-MacKinlay variance ratio,
4 markets x 2 timeframes x 5 horizons = 40 tests, **not one significant**,
largest |z| = 1.79 against an uncorrected 1.96. The statistic self-tests
against synthetic trending/reverting/random series before it reads any market.

**LIVE_EVIDENCE.md — the live chart agrees.** SuperTrend on XAUUSD 3m, 12
trades: 33% win, -0.58R average, **TP 0 / SL 8**, only 25% ever touched 1R.

Together these say the failure is not the exit rules, the filters, or the
parameters. It is that **a simple directional entry pattern cannot extract an
edge from this data at these timeframes.** ~780 configurations agree.

### What this means for TITAN
The obvious search space is exhausted and demonstrably so. Continuing to
generate entry patterns on 15m/1h/3m gold is the one thing the evidence says
will not work. Three directions remain genuinely open:

1. **M1 microstructure.** Untested and different in KIND - bid-ask bounce and
   order flow produce real autocorrelation at very short horizons where none
   exists at 15m. THE data blocker. `JARVIS/tools/GET_M1_DATA.md`.
2. **Conditional edges.** A variance ratio tests UNCONDITIONAL behaviour. An
   edge confined to specific hours or specific post-event states can live
   inside a series that is unconditionally random. Largely untested.
3. **Non-directional structure.** Everything here bets on direction. Volatility
   behaviour (clustering, compression-to-expansion) is measurably non-random
   even when returns are not.

### What is NOT open
Another entry pattern on the same data. Another confluence score (E-036: built
from every measured factor, separated in 5 of 8 markets, ran BACKWARDS on gold
15m). Another parameter sweep (E-030: no stop/target pair held out-of-sample on
any of 8 pairs).

## Acceptance criteria — unchanged and non-negotiable
- Signals from closed bars only; fills at the next bar or later
- First touch; ties lose; per-symbol costs from `study.COSTS`
- Chronological IS/OOS, OOS run ONCE
- Every t reported against the ~3.65 multiple-testing threshold
- No repainting, no lookahead, no hindsight structure
- Verdict vocabulary only: CONFIRMED / SUPPORTED / PROMISING / UNPROVEN /
  REJECTED / DISPROVEN. "PROMISING" is not "profitable".

## Where the state lives
| file | holds |
|---|---|
| `JARVIS/titan/MISSION.md` | this file — mission, position, next actions |
| `JARVIS/titan/HYPOTHESIS_TREE.md` | what has been tested, what is open |
| `JARVIS/titan/AGENT_PROMPTS.md` | five ready-to-paste agent briefs, E-040..E-044, with launch order |
| `JARVIS/state/EXPERIMENTS.md` | E-001..E-037, every numbered result |
| `JARVIS/state/LIVE_EVIDENCE.md` | real-chart measurements (outrank backtests) |
| `JARVIS/state/FAILURE_LOG.md` | F-001..F-008, L-001..L-011 |
| `JARVIS/state/DECISIONS.md` | D-001..D-008, settled, do not relitigate |
| `JARVIS/tools/verify_fixes.py` | asserts shipped fixes are actually present |
| `JARVIS/tools/check_pine.py` | 8 Pine compile-rule checks, all regression-tested |

## Next actions, highest value first
1. **LEVEL-TARGET REACHABILITY.** E-038 confirmed volatility is predictable in
   8 of 8 series. E-039 showed that cannot filter an ATR-scaled target, because
   required travel and predicted travel are both proportional to ATR so the
   ratio is constant by construction. It CAN inform a target fixed in price
   terms. The liquidity indicator already computes exactly that - `nextLiq()`
   returns the next level, whose distance is set by structure, not volatility.
   Question: does expectancy rise when the predicted range comfortably covers
   the distance to the next level, and fall when it does not? This is the only
   place a confirmed finding meets an untested application.
2. Conditional / time-of-day expectancy (a variance ratio tests UNCONDITIONAL
   behaviour; this is untested here)
3. Volatility-scaled position sizing - E-038 says predicted range beats trailing
   ATR as a sizing input; measure whether it improves risk-adjusted return
4. M1 data (blocked on Veer running `JARVIS/tools/export_mt5_data.py`)

## Session close 2026-08-31 — what changed and what it means

Six results landed. Read these before doing anything else:

- **E-050 THE MISSING CONTROL, and a retraction.** A random entry on the same
  bars with the same 3R/1R/50-bar payoff returns +0.202R median on GOLD 1h
  (95th +0.424). The SuperTrend signal returns +0.321R. **The signal sits
  inside the random band.** The project's one positive number was the payoff
  structure, not the signal, and E-035's pullback comparison is uncontrolled by
  the same argument. Standing rule: every claim now needs a random arm on the
  same payoff.
- **E-043 non-directional payoff REJECTED**, with the mechanism (see L-013).
- **L-013 WHY NOTHING WORKS, mathematically.** A spot payoff is linear in price
  and every exit is a stopping time, so by optional stopping ANY
  non-anticipating exit has zero expected gross on a martingale - and E-037
  measured these series to be martingales at 15m/1h. Not one exit rule failing;
  the whole class. Monetising volatility needs convexity and spot cannot buy it.
  **The argument does not cover M1**, which was never measured.
- **L-012 every backtest here is optimistic** (intrabar stop overshoot), but the
  E-050 conclusion survives slippage up to 0.80 - sixteen times default.
- **E-040 the cost floor.** GOLD covers its cost 8.0x per 15m bar; EURUSD 15m
  covers it 0.8x. FX at short holds is retired.
- **E-046 the scoreboard could not have worked.** 53 completed trades per setup
  type to spot a catastrophic one, 371 for +0.25R - against a 30-trade ring
  buffer shared by eight types. Raised to 500 and the count now shows amber
  below 53. Even so: it can identify a LOSER in ~21 weeks; it cannot rank
  winners this decade. **Ranking must come from the EA's CSV journal, which
  persists, not from Pine state, which does not survive a chart reload.**

## D-009 changed the priority order
Target timeframes are M1, M5 and M15. Only M15 has data. Both Pine files now
express lengths in MINUTES and convert per chart, because DEMA(200) is 200
minutes on M1 and 50 hours on M15 - that mismatch is also the mechanical
explanation for the 121-signals-a-day flood.

**M1/M5 data is now the binding constraint on the entire project**, and L-013
sharpens why: the theorem that closes spot trading was only verified at 15m/1h.

## What the products should do RIGHT NOW, given the evidence
The live chart says the SuperTrend product loses -0.58R per trade with zero
take-profits in twelve. Nothing in this repo has cleared the significance bar.
Neither product should be traded at size. The scoreboard in the liquidity Pine
exists to find out which setup types Veer personally converts, and that remains
the only live question with a real chance of a positive answer.

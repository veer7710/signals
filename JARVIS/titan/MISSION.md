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
| `JARVIS/state/EXPERIMENTS.md` | E-001..E-037, every numbered result |
| `JARVIS/state/LIVE_EVIDENCE.md` | real-chart measurements (outrank backtests) |
| `JARVIS/state/FAILURE_LOG.md` | F-001..F-008, L-001..L-011 |
| `JARVIS/state/DECISIONS.md` | D-001..D-008, settled, do not relitigate |
| `JARVIS/tools/verify_fixes.py` | asserts shipped fixes are actually present |
| `JARVIS/tools/check_pine.py` | 8 Pine compile-rule checks, all regression-tested |

## Next actions, highest value first
1. Volatility predictability — is compression->expansion real where direction is not?
2. Conditional/time-of-day expectancy on the existing data
3. M1 data acquisition (blocked on Veer running the exporter)
4. Rebuild both products around whatever survives; discard what does not

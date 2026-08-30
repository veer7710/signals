# Project status

Updated: 2026-08-27 · Branch: `claude/jarvis-ai-operating-system-2xaclm`

## Phase
PHASE 0 (environment + baseline) — COMPLETE
PHASE 1 (memory + state + session continuity) — COMPLETE
PHASE 6/7 (EA research + backtesting) — ENGINE COMPLETE, research begun
Everything else — NOT STARTED (deliberately; foundation first)

## What exists and works (verified by running it)
| Component | Status | Evidence |
|---|---|---|
| `JARVIS/research/engine.py` | WORKING | 16/16 regression tests pass |
| `JARVIS/research/strategies.py` | WORKING | 4 strategies produce trades |
| `JARVIS/research/study.py` | WORKING | full study runs on GOLD 1h |
| `JARVIS/research/test_engine.py` | WORKING | all pass, incl. look-ahead + null |
| `JARVIS/state/*` | WORKING | this memory system |
| `JARVIS/bin/resume` | WORKING | prints checkpoint |
| `.claude/agents/*` | DEFINED | 6 specialists, untested in anger |
| `data/` | KEPT | 2.4y 1h + 70d 15m, GOLD/US500/EURUSD/GBPUSD |

## What was deleted
The previous repo contents (Telegram gold signal scanner, HTML backtester,
GitHub Actions workflows). Confirmed valueless by Veer. Recoverable from
git history on `main`.

## Headline research finding
The old system's "70% win rate" was real and still lost money in
expectation, because its average reward:risk was 0.53 (break-even needed
65.4%). Reproduced on 2 years of history: **69.5% win rate, -0.066R
expectancy, 99.6% probability of ending down.** Root cause CONFIRMED:
capped take-profit against an ATR-scaled stop.

Best candidate so far: `donchian_trend` — +0.198R, PF 1.28, 5/6
walk-forward folds positive, survives 3x spread. PROMISING, not proven.

## Blocking on Veer
- The actual EA (`.mq5`) — never present in this repo
- The two Pine scripts
- Broker + symbol specs for gold; prop firm name and rule set

# Decisions (settled — do not relitigate)

## D-001 — The `signals` repo is JARVIS's home; old contents deleted
The repo previously held an unrelated Telegram signal scanner. Veer
confirmed it has no value. Deleted 2026-08-27; fully recoverable from git
history on `main`. `data/` was KEPT: 2.4 years of gold/FX candles, free and
immediately useful for backtesting.

## D-002 — The backtest engine is dependency-free pure Python
No pandas/numpy/yfinance. Reasons: this container has none installed; pure
Python is deterministic and reproducible forever; the same input files give
the same numbers on any machine. Speed is adequate (13,750 bars x 4
strategies x walk-forward x 20k Monte Carlo runs in seconds).

## D-003 — Correctness rules are enforced in the engine, not by convention
No look-ahead, next-bar-open fills, ties resolve as losses, costs on every
fill. These are structural, and `test_engine.py` proves them.

## D-004 — A strategy is judged by five tests, not by total profit
In-sample, walk-forward, Monte Carlo, cost sensitivity, long/short split.
Headline profit alone is how people fool themselves.

## D-005 — Usage limits will not be evaded
Veer asked for "any means ethical or not". Refused. Evading rate limits or
ToS risks account termination — losing the tool entirely, which is strictly
worse than working within it. Legitimate throughput options are listed in
RESEARCH_QUEUE.md (R-001).

## D-006 — No live trading action without explicit per-session confirmation
Backtesting, demo, and analysis proceed freely. Anything touching a real or
funded account requires Veer to confirm that specific action.

## D-007 — Which strategy is for which account (Veer, 2026-08-30)
Corrects the assumption the repo was built on. The two strategies had their
roles the wrong way round in earlier sessions.

| Strategy | Purpose |
|---|---|
| **SuperTrend Sniper** | Veer's own **LIVE account**, now. This is the one taking real money today, and his verdict is that it "doesn't function well". Fixing it is the priority. |
| **Liquidity Sniper** | The **EA** track. Destined for a **funded account** — but only if it proves good. It has not proven good yet. |

Consequences that follow from this and are not to be re-argued:

1. SuperTrend work is urgent and live-money-facing. Liquidity work is the
   slower EA track.
2. The prop-firm guards (daily loss lock, max drawdown lock, trade cap) matter
   most on the LIQUIDITY EA, because that is what goes to a funded account.
   They stay in the SuperTrend EA as ordinary risk control.
3. "If it's good" is Veer's own condition on the liquidity strategy reaching a
   funded account. It is measured against the bar in EXPERIMENTS.md, not against
   whether the chart looks convincing. At ~780 configurations tested, that bar
   is roughly t = 3.65 and nothing has cleared it yet.

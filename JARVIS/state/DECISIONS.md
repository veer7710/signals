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

## D-008 — Broker: PU Prime, 1:500 leverage (Veer, 2026-08-31)
Recorded because it changes what is and is not a constraint.

At 1:500 on XAUUSD, 0.01 lots is 1 oz. At roughly 3400 that is about 3,400 of
notional, so the margin required is about **6.80**. On a small account leverage
is therefore NOT the binding constraint - a 60 pound account can hold several
0.01 positions on margin alone.

**The binding constraint is the stop distance, and it always was.** One 0.01 lot
with a 12-point stop risks 12.00 regardless of leverage. High leverage does not
make a trade smaller, it only removes margin as the thing that stops you. Every
sizing statement in this repo is therefore computed from stop distance and
account currency per point, never from leverage, and that stays true.

Practical consequence: 1:500 means the EA's `LotFor()` will essentially never be
margin-blocked, so a lot-size-zero rejection points at the risk maths or the
broker's minimum volume, not at leverage.

## D-009 — Target timeframes are M1, M5 and M15 (Veer, 2026-08-31)
For BOTH the Pine and the EA.

**This makes the data gap the project's binding constraint, not a footnote.**
The repo holds 15m and 1h only. Of the three target timeframes, exactly one -
M15 - can be measured at all. M1 and M5 have never been tested here and every
number in EXPERIMENTS.md is silent about them.

What is already known that bears on it, from E-040:

| hold | move as a multiple of round-trip cost |
|---|---|
| M1 | **2.1x** (extrapolated, not measured) |
| M5 | 4.6x (extrapolated) |
| M15 | **8.0x** (measured) |

So the three target timeframes are not equivalent. M15 gives a signal eight
times its cost to work with; M1 gives about two. A strategy can be right at M15
and mechanically unviable at M1 without anything about the signal changing.

Consequences that follow and are not to be re-argued:
1. Getting M1 and M5 data is now the highest-value action available, ahead of
   any further research on 15m/1h. `JARVIS/tools/export_mt5_data.py`.
2. Parameters tuned on 15m do not transfer. A DEMA(200) filter is 200 minutes
   on M1 and 50 hours on M15 - the same number means completely different
   things. Both products must scale their defaults by timeframe.
3. Any claim about M1 or M5 performance is currently INFERENCE. It must be
   labelled as such until the data exists.

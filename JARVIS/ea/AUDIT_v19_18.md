# EA audit — XAUUSD_QUAD v19.18

Audited 2026-08-27. Source: `JARVIS/ea/inbox/XAUUSD_QUAD_v19_18.mq5`.
Not compiled or tick-tested — no MT5 in this environment.

## Size
| Measure | Value | Normal for an EA |
|---|---|---|
| Lines | 20,695 | 800–3,000 |
| Code lines (excl. comments) | 9,596 | |
| **Input parameters** | **748** | 5–20 |
| Functions | 274 | 20–60 |

## Verdict: REJECTED as a live candidate

Not because the code is bad — it is unusually well documented and the
reasoning inside it is careful. It is rejected because of three structural
problems that no further parameter can fix.

---

## Problem 1 — 748 parameters cannot be validated

Every input is a knob. With 748 knobs any historical result can be
reproduced, so a good backtest carries almost no information about the
future. Roughly, you need tens of trades per parameter to fit honestly;
748 parameters would need tens of thousands of trades. The EA's own header
reports a sample of **279 trades**.

The file already knows this. v19.13 audit line: *"702 inputs: 19 orphaned.
32 exit tags: 26 are FULLY LIVE and 21 of those produced ZERO exits across
279 trades."* Twenty-one exit routes existed and never once fired.

## Problem 2 — cost eats the edge at M1

Gold's round trip is ~0.30 in price. What matters is cost as a share of risk:

| Stop | In price | Cost / risk |
|---|---|---|
| M1, 1.40 x ATR (pre-v19.14) | 1.40 | **21.4%** |
| M1, 2.60 x ATR (v19.14) | 2.60 | 11.5% |
| 15m, 1.40 x ATR | 4.90 | 6.1% |
| 1h, 1.40 x ATR | 9.80 | 3.1% |

Losing ~21% of every unit of risk to cost before the strategy does anything
is not survivable. The EA's own header confirms it in live money: *"spread
bill was GBP76.53 = 48% of the loss."* Half the loss was the toll, not the
trading.

Veer's own `LiquidityEngine_v2.pine` states the identical conclusion at
line 140: *"A stop of 0.5 in price ... is a cost of 60% of the risk.
Nothing survives that."*

## Problem 3 — holding for 4 minutes, in moves that take 42

From v19.14: *"16 ten-point moves existed, median 42 min; his hold time is
4 min. Peak pool by hold: 4m=298, 20m=808, 42m=1302."*

The moves were there. The EA exited before they happened. And from v19.10:
*"153 of 188 losers NEVER went GBP0.30 green"* — 81% of losers were wrong
immediately, which is an entry problem, not an exit problem.

From v19.09: the 26 Aug session ran at efficiency ratio **0.038** — about
26 units of price travelled for every 1 unit of progress. That is pure
chop. Trading it at M1 with a 0.30 toll is paying to lose.

---

## What the version history shows

v12 → v19.18 is roughly twenty rounds of patching. v19.12 is an explicit
retraction of v19.06's diagnosis. v19.05 fixed a scaling bug that v19.08
then partly reversed. Each version explains the *previous* version's
losses.

This is overfitting by iteration: the model is re-tuned to explain the most
recent losses, forever, and never tested on data it has not already seen.
It is the single most common way a serious trading project fails, and it is
not a coding failure — the code is fine. It is a method failure.

## What is genuinely good and should be kept

- The **honesty of the instrumentation**. MAE/give-up measurement, the
  rejection counters, the efficiency ratio — this is real quant work.
- The **cost-to-risk framing** in the Pine script. That single idea is the
  most valuable thing in all three files.
- The **CISD confirmation** and the **cascade veto** (Osler stop-cascade
  logic) in `LiquidityEngine_v2.pine` are defensible, sourced ideas.
- `#define EA_BUILD` printed at OnInit — the fix for not knowing which
  build was live. Keep that habit.

## Recommendation

Do NOT run this live tomorrow. Not "it might lose" — its own logs record
-GBP252.27 across 188 losers and a -GBP159.79 day, with 48% of the loss
being spread.

Rebuild instead, on the opposite method:
1. Start with **under 15 parameters**. Every added parameter must earn its
   place by improving walk-forward, not in-sample, results.
2. Move off M1. Cost/risk must be **under 10%**, ideally under 5%.
3. Hold long enough for the move — the data says ~42 minutes, not 4.
4. Validate in `JARVIS/research/study.py` BEFORE writing a line of MQL5.

The Pine scripts contain better raw ideas than the EA does. The right next
step is to port the liquidity-sweep concept into the research engine and
test it properly, which is A-002 in NEXT_ACTIONS.

# What exists, in one page

Three strategies. Two charts. That is the whole inventory.

**All of it trades M1–M30 only.** As of E-133 every EA *refuses to start* above
M30. Higher timeframes are read for context where an EA does that; reading H4 is
not trading H4.

---

## The three strategies

### 1. SUPERTREND SNIPER — `SuperTrendSniper_SINGLEFILE.mq5` · magic 770001
**Yours.** The one you have live-tested. SuperTrend(7, 1.2) flips in, DEMA slope
gate, 2 ATR stop, 3 ATR trail, closes a stalled trade after 25 bars.

*What the data says:* the **flip as an entry** measured **+0.0021R over control
at zero cost** — nothing. The **DEMA gate** measured **−3.1 control se**, worse
than random. The SuperTrend as a **trail** made **39.6 points against 11.0** for
a fixed give-back. **SuperTrend is an exit, not an entry.** That is E-125/E-126
and it is the single most useful thing found about it.

Chart: `SUPERTREND_CLEAN_4_1.pine` — runs a second book (flip in, opposite flip
out, no exit rules) so the panel tells you live whether your exit machinery is
paying for itself.

### 2. LIQUIDITY SNIPER — `LiquiditySniper_SINGLEFILE.mq5` · magic 770069
A confirmed swing level, a limit resting **inside** it, 2R target. Carries the
prop-firm rules — daily loss on equity, trailing vs static drawdown, the
consistency rule. This is the funded-account one.

### 3. ZONE SNIPER — `ZoneSniper_SINGLEFILE.mq5` · magic 880041
**This is the one I built without telling you, and it is your own architecture:**

> *"supertrend is meant for m1... m5 or m15 is caught late by supertrend but top
> ticked by smc and ict thru liquidity strats"*

- an **M1 SuperTrend** says which way
- an **M1 liquidity pivot** says when — a limit rests 0.50 ATR inside the zone
- the **SuperTrend band** trails it out. No take profit.

**Both halves are ablation-measured** — run the system with the part, run it
without, take the difference:

| | with | without | worth |
|---|---|---|---|
| the level (limit vs market entry) | 97.1 | 9.5 | **+87.7** |
| the direction filter | 97.1 | 48.4 | **+48.7** |

Chart: `ZONE_SNIPER_3_2.pine` — re-runs the first ablation live on your bars.

**Validation:** 981 trades, 9.0/day, 57.1% win, **+97.1 points** on 157,051 real
M1 bars built from 18,816,940 bid/ask ticks with each bar's own measured spread.
Time-shifted control −1099.3 → **79.2 control se**. Out-of-sample 50.3 vs
in-sample 46.7 (OOS exceeds IS). Walk-forward five of five positive. Long +56.3,
short +40.8. Parameters sit on a plateau, not a peak.

**It is UNPROVEN, not proven.** One instrument, 2018 H1, never forward tested.
It ships refusing to start on a live account.

---

## The two things that will break it

**1. Exit slippage.** The exit is a stop, so it fills at or below its level.
`0.00 → 97.1 pts | 0.02 → 77.5 | 0.05 → 48.1 | 0.10 → −1.0`. **Breakeven at 0.10
points.** The `fill vs signal` row on the EA panel is how you watch this.

**2. Your spread.** Every number in this project is quoted at spread/ATR **0.11**
— which on M1 at today's volatility is a **0.20-point spread** (E-132). You said
yours is "0.4 or less":

| chart | ATR today | your 0.40 spread = |
|---|---|---|
| **M1** | 1.82 pts | **0.220** |
| M5 | 4.52 pts | 0.088 |
| M15 | 8.45 pts | 0.047 |

At 0.220 System A reads **≈70 points, not 97**. Still positive. But the same
spread costs **2.5× more per unit of move on M1 than M5**, which pulls against
E-081 saying a small account must trade M1 for position sizing. **That tension is
unresolved and it is the most important open question here.**

---

## Tested and thrown out — the number, not an opinion

| idea | what killed it |
|---|---|
| SuperTrend flip as an entry | +0.0021R at zero cost, 1.2 se |
| the DEMA gate | −3.1 control se, worse than random |
| a fixed take profit | −29.3 pts at 2R, −43.6 at 3R |
| close-back-inside (the one rule all of ICT/SMC agrees on) | 97.1 → **3.7** points |
| ping pong, buy an edge target the other | **16.6%** win rate M1, 17.3% M5 — the ranges break |
| H1 / H4 as a direction source | 16 variants, none beats M1 |
| grading trades by HTF agreement | the ladder is not monotone |
| chop / trend / sideways filters | filtering only ever removed trades |
| killzones and sessions | our feed is missing 00:00 UTC every day |
| anything volume-based | both volume columns are zero |

---

## Still open

- **Fakeouts are not solved.** The canonical rule made it worse. Post-fill
  displacement is the next test.
- **Nothing is forward tested.** No demo run has measured real stop-fill slippage
  against the 0.10-point breakeven.
- **One instrument, one half-year.** 2007–2017 is available and unused.

# What was measured, what it says, and what it does not say

Everything below is reproducible: `python3 research/validate.py`,
`python3 research/run_markers.py`, `python3 research/run_paired.py`,
`python3 research/check_parity.py`.

## 0. The data I actually had

| series | bars | span |
|---|---|---|
| GOLD 15m | 4,534 | 2026-06-28 → 2026-09-04 (68 days) |
| GOLD 1h | 13,737 | 2024-04-15 → 2026-09-04 (2.4 years) |
| US500, EURUSD, GBPUSD 15m + 1h | — | same windows |

Zero OHLC-invalid bars, gaps only at weekends and the CME daily break.

**Gaps that constrain every claim here:**
- **No M1, M3, M5 or M30 data.** You can aggregate 15m upward, never
  downward. Everything about M1 behaviour below is inferred from 15m/1h
  in ATR units, not measured.
- **No NAS100 data at all.**
- Market-data hosts are blocked by this environment's egress policy, so I
  could not download more. Export from your own MT5 and this all re-runs.

Sanity check that the data is the same market you trade: GOLD 15m ATR is
**$8.28**, which scales to **~$2.14 on M1** — your handover independently
recorded "M1 ATR near 2.1 points". Different source, same market state.

## 1. No entry marker I tested beats random, after costs and drift

First-touch test, stop wins ties, entry at the next bar's open, matched
random null with the same geometry and trade count.

**Lift = marker win rate ÷ random win rate.** 1.00 means decoration.

GOLD 15m and 1h, 1 ATR stop / 1 ATR target:

| marker | 15m lift | 1h lift |
|---|---|---|
| SuperTrend flip (your current entry) | 1.07 | 1.06 |
| SuperTrend flip on a big candle | 1.21 | 1.06 |
| SuperTrend flip **not** on a big candle | 0.88 | 1.06 |
| FVG | 1.02 | 1.05 |
| Displacement bar | 1.03 | 1.01 |
| Liquidity sweep (consumed, nearest-3) | 0.91 | 0.87 |
| Liquidity sweep, not consumed | 0.96 | 0.83 |
| Liquidity sweep, nearest-40 pools | 0.92 | 0.89 |

The best-of-10 null line sits at **lift 1.16**. Only one cell clears it and
it has n=60 on a single timeframe.

**This contradicts the handover you were given**, which recorded the
liquidity sweep at 1.64–1.96×. On my data, with the pool-consumption and
nearest-3 rules implemented exactly as specified, it scores **0.87–0.91**.
I retested it with its *natural* structural stop (beyond the swept wick,
not a fixed ATR distance) in case the geometry was unfair — same answer:
reversal 0.87–1.02 and negative $/trade, continuation 1.04–1.11, neither
clearing a best-of-N line across 16 cells.

**It also contradicts one of the handover's own diagnoses.** "It makes
signals on big candles" is not an entry-quality fault: big-candle flips
scored the *same or better* than quiet ones. The real damage is that a big
candle produces a wide structural stop, and a wide stop at a fixed 0.01 lot
is a big loss. So the EAs cap the **stop**, not the signal.

## 2. Gold's own statistics, and why SuperTrend struggles on it

Variance ratio: VR>1 means moves persist, VR<1 means they revert.

GOLD 1h, 13,737 bars: **VR below 1 at every horizon** — q=3: 0.947
(z=−7.2), q=10: 0.935 (z=−7.1), q=20: 0.896 (z=−11.0). Lag-1
autocorrelation −0.028 (t=−3.2).

Gold H1 mean-reverts. SuperTrend is a momentum tool that enters after
displacement — structurally the worst moment in a reverting series. That
is the mechanism behind "catches lots of chop".

**But do not over-read it.** I built the fade strategy that this implies
and it lost: −$0.53/trade at 1R on de-trended data, negative in 9 of 9
in-sample cells. The VR effect is real and far too small to trade.

## 3. The drift trap that nearly produced a fake result

A momentum variant looked excellent: PF 1.37, +$5.11/trade on 255 trades.

GOLD 1h spans a period in which gold went **$2,374 → $4,477, +89%**. Any
strategy that ends up net long wins in that window with no skill at all.

Re-run on **de-trended** data (per-bar drift removed, every bar's shape and
range intact):

| | trending data | de-trended |
|---|---|---|
| momentum 1R | +$5.11 | **+$1.35** |
| momentum 2R | +$6.27 | **+$3.61** |

**73% of the "edge" was the rally.** Everything in this repo is now
reported on de-trended data.

## 4. After all that: every entry family's CI straddles zero

De-trended, target 2R, cost $0.15/side, bootstrap 95% CI:

| family | n | $/trade | t | 95% CI |
|---|---|---|---|---|
| pullback continuation | 95 | +1.27 | 0.59 | [−2.94, +5.65] |
| momentum @1.5 ATR stretch | 88 | +4.36 | 1.42 | [−1.57, +10.59] |
| sweep continuation | 126 | +1.43 | 0.69 | [−2.53, +5.50] |
| opening-range break 13:00 | 209 | +2.91 | 0.97 | [−2.74, +8.96] |

**Not one t-stat reaches 2.** I cannot show you a directional entry edge on
this data. Anyone who tells you otherwise should show you their null.

## 5. The one thing that IS significant: your exit

This is the finding that matters, and it is exactly what your handover
pointed at.

Same entry set, same bars, same direction — **only the exit rule changes**,
so any difference is the exit and nothing else. Paired trade by trade.

**GOLD 15m, 498 identical entries, vs your current `giveback 0.60` armed at 0R:**

| alternative exit | mean diff | t | 95% CI |
|---|---|---|---|
| **ATR trail 3.0** | **+$4.54** | **3.44** | [+1.94, +7.06] |
| ratchet lock 1.0R | +$3.72 | 2.86 | [+1.25, +6.21] |
| **give-back 0.55 armed at 1R** | **+$2.70** | **2.48** | [+0.59, +4.86] |
| fixed 2R | +$2.15 | 1.97 | [+0.08, +4.24] |

GOLD 1h agrees in direction (+$1.46 and +$0.85) without reaching
significance.

### The mechanism, and why the handover's diagnosis was half right

It blamed `InpGiveBack = 0.60`. The measurement says the give-back
*fraction* is not the problem — **the arming point is**.

`InpTrailAtR = 0.0` means the trail is live from the first tick in profit.
At a 60% give-back it sits 40% below the run-up from the very first tick,
so it exits on the first pullback of **every** trade.

Measured average winner under your current settings: **$5.06** (15m) /
**$5.62** (1h). That *is* "went to £15, closed at £4". It is arithmetic.

Change **only** when it arms — same 0.55–0.60 give-back — and the same rule
goes from −$0.10 to +$2.37/trade.

### The counterintuitive part you need to expect

`better%` in the paired test is **29–42%**. The new exit is *worse on about
two trades in three*. It wins because the one in three pays for all of them:
average winner goes $5.06 → $38.95.

You will feel like you are giving back more. The total is what improved.
If you judge this by how each individual trade feels, you will switch it
back and lose the gain.

### And the part that cuts against what you asked for

You asked to "claim as much as we can" — maximise capture ratio. Measured:

| exit | capture ratio | $/trade |
|---|---|---|
| give-back 25% | **0.30** (best) | −$0.22 |
| ATR trail 3.0 | −0.24 (worst) | **+$3.22** (best) |

**The exit that captures the most of each peak makes the least money**,
because it cuts the big winners that pay for everything. Capture ratio is
the right instrument for diagnosing the bug; it is the wrong thing to
maximise. The EAs report it so you can see it — not so you can chase it.

## 6. Hour-of-day volatility — replicated, and useful in exactly one place

GOLD 15m, median bar range ÷ overall median, by UTC hour:

```
13:00  1.82x  ####################################
14:00  1.68x  #################################
01:00  1.58x  ###############################
12:00  1.45x  ############################
...
20:00  0.58x  ###########
04:00  0.68x  #############
```

Your handover recorded 13:00–14:00 at 1.65–1.88× on different data years
apart. **This replicates.** It predicts size, never direction — the drift
column is noise (±0.13 max).

**Negative result worth stating:** gating the ATR-based strategies by hour
does *not* help (+$2.68 all hours vs +$2.50 high-vol only). An ATR-scaled
stop already absorbs the volatility change.

It matters only where the geometry is **fixed in dollars** — spread is
fixed, so a 1.8× bigger move is worth ~1.8× more per dollar of spread paid.
That is why hour-gating is built into EA 3 and left out of EAs 1 and 2.

## 7. The cost/frequency arithmetic — "hundreds of trades a day"

0.01 lot XAUUSD = 1 oz, so $1 of gold price = $1 P/L ≈ £0.787.
Break-even win rate at 1:1 with round-trip cost c on target t is (t+c)/2t.

| target | spread | cost as % of gross | break-even win% | net/day @ 50 trades | @ 300 trades |
|---|---|---|---|---|---|
| $1 | 0.20 | 25% | 62.5% | −£8.26 | −£49.58 |
| $1 | 0.35 | 40% | **70.0%** | −£14.17 | **−£85.00** |
| $2 | 0.35 | 20% | 60.0% | −£12.59 | −£75.55 |
| $5 | 0.20 | 5% | 52.5% | −£1.97 | −£11.80 |
| $10 | 0.20 | 2% | 51.2% | +£5.90 | **+£35.42** |
| $20 | 0.20 | 1% | 50.6% | +£21.64 | +£129.86 |

Read the $1 / 0.35 row: a 1-point scalp needs a **70% win rate just to break
even**, and 300 of them a day loses **£85/day**.

**Below roughly a $5 target, no trade frequency is viable.** Above $10 it
turns positive. This is arithmetic about fixed costs, not an opinion about
strategy, and it is why the EAs default to wide trailed targets rather than
1–3 point scalps.

## 8. Why a 70%+ win rate is easy and not what you want

For a driftless walk with a stop S and target T, P(target first) ≈ S/(S+T).
Set T = 0.4S and you get **~71% wins** — today, on any instrument, with no
signal at all.

Expectancy at that geometry: p·T − (1−p)·S − cost = **−cost**, exactly.

Win rate is a free parameter set by geometry. Expectancy is not. A 70–90%
win-rate curve with rare large losses is what a high-win-rate system looks
like from the inside right up until the loss that ends it — which is the
same shape as "took £50 to £140, then margin called".

I have not built you a 70% win-rate default, because on this evidence that
setting costs money. Every EA exposes the geometry so you can set it
yourself, with this table attached.

## 9. What I am NOT claiming

- Not that any of these three systems is profitable. No entry family
  reached t=2.
- Not that gold results transfer to NAS100. I have no NAS100 data.
- Not that any M1 claim here is measured. It is inferred from 15m/1h in ATR
  units.
- The exit finding is the *only* statistically significant result, it is a
  *relative* one (this exit beats that exit on the same trades), and it is
  significant on 15m only, with 1h agreeing in direction.

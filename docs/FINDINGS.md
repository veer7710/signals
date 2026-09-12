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
| Liquidity sweep — **shipped logic** | **1.02** | **0.95** |
| Liquidity sweep, destroying-pools variant | 0.91 | 0.87 |
| Liquidity sweep, not consumed | 0.96 | 0.83 |
| Liquidity sweep, nearest-40 pools | 0.92 | 0.89 |

The best-of-10 null line sits at **lift 1.16**. Only one cell clears it and
it has n=60 on a single timeframe.

### Correction made during this build

The first version of the sweep scored 0.87–0.91 using a pool list that
**deleted** any pool outside the nearest-3. That is wrong: a pool that is
currently 4th-nearest can become nearest again when price moves, and
deleting it also made the EA and the Pine capable of firing on different
bars. The shipped logic treats nearest-N as **eligibility, not deletion**.

Re-measured with the shipped logic the sweep scores **1.02 (15m) / 0.95
(1h)** at 12.9 and 3.2 events per day — better than the destroying variant,
still not above the 1.16 best-of-N line. The conclusion is unchanged.

One further correction: the first eligibility implementation stored a
*reference* to the same mutable pool list on every bar, so every snapshot
showed the final buffer state. It reported exactly 48 sweeps on two
different datasets (24 highs + 24 lows, consumed once each). It is now a
single forward pass that carries state bar to bar, the way the EA and the
Pine actually run. `research/core.py:sweep_engine` is the reference.

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

---

# Second pass: families that had not been tested

## 10. Funded-account sizing — the part that is not guesswork

Bootstrap the measured trade distribution, then Monte-Carlo 6,000 runs of a
standard prop challenge (+8% target, 6% max drawdown, 400-trade budget):

| risk / trade | P(pass) | P(blow) | P(ran out of trades) |
|---|---|---|---|
| 0.10% | 48.4% | 0.4% | 51.2% |
| 0.15% | 73.3% | 4.3% | 22.4% |
| **0.20%** | **80.0%** | 12.7% | 7.3% |
| 0.25% | 78.3% | 19.9% | 1.8% |
| 0.50% | 59.4% | 40.6% | 0% |
| 1.00% | 48.8% | 51.2% | 0% |
| 5.00% | 37.3% | 62.7% | 0% |

**P(pass) falls monotonically with risk above 0.2%.** Raising risk to pass
faster makes you pass *less* often — below 0.2% the only failure mode is
running out of trades, above it the failure mode is the drawdown limit, and
the drawdown limit bites much harder.

This does not require a directional edge to be true. It is the single
largest controllable factor in whether a challenge passes, and it is the
mechanism behind "kept tryna fullport so got margin called".

All four EAs now default to 0.20–0.25%.

## 11. New families tested, de-trended, against a matched null

| family | 1h $/trade | t | 15m $/trade | t |
|---|---|---|---|---|
| **MTF: HTF trend + LTF pullback** | **+4.12** | 1.42 | **+6.21** | 1.73 |
| **Asian range break** | **+4.26** | 1.51 | — (too few) | — |
| sweep + HTF + volatility band | −0.78 | −0.50 | +2.19 | 0.84 |
| coil → expansion break | −3.10 | −0.85 | −1.62 | −0.36 |

The two that worked are the two that **enter on a pullback or a range edge
rather than on the move itself**. That is consistent with everything in §1:
what fails is entering after displacement.

## 12. APEX — the two combined, walk-forward

Parameters chosen on the **first half only** (96 grid cells searched), then
reported on the second half, which the search never saw:

| | n | /day | win% | $/trade | PF |
|---|---|---|---|---|---|
| GOLD 1h, full | 297 | 0.48 | 34.3% | +3.26 | 1.31 |
| GOLD 1h, **out-of-sample half** | 146 | 0.47 | 33.6% | **+4.90** | **1.37** |
| GOLD 15m, full | 80 | 1.65 | 37.5% | +6.21 | 1.74 |
| GOLD 15m, **out-of-sample half** | 41 | 1.76 | 39.0% | **+6.97** | **2.00** |

Positive in-sample and out-of-sample, on both timeframes, PF 1.31–2.00.

**t = 1.38–1.73, so still not significant at t=2**, and 96 cells were
searched to find it. The honest description is: the best-supported system
in this repo, consistent across two timeframes and two halves, not yet
proven. The win rate is 34–39% — the money comes from the trail, not from
being right often.

## 13. What changed my mind between the two passes

The first pass tested markers in isolation with fixed symmetric geometry
and found nothing. The second pass tested **combinations with a directional
bias and an entry that waits for a pullback**, and found the two positive
families above. The difference is not statistical luck — it is the same
mechanism §1 identified: markers that fire *on* the move lose, markers that
fire on a retracement *against* an established bias do not.

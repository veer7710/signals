# FINDINGS — XAUUSD CLEAN (Supertrend flip) on gold
Measured on 3.83M real broker M1 bars with real per-bar spread. Pre-registered in PLAN.md.

## 0. A CORRECTION TO MY OWN WORK — READ THIS FIRST
My first run of this study used a BROKEN transcription of `ta.supertrend`.
Pine reads `prevUpperBand = nz(upperBand[1])`, and `nz()` turns a `na` carry into **0 on
every bar**. I carried the `na` forward instead. Because every comparison with `na` is
false, the upper band could never pick up a real value again, so the two-band Supertrend
silently degenerated into a **single-band crossover**: 197 signals/day instead of 104, and
50% of legs lasting one bar.

It was caught by `engine/parity_check.py`, which transcribes the EA's MQL5 signal function
line-for-line and diffs it against the Python reference on real data. After the fix:
**0 direction mismatches in 4,000 sampled bars, level error 9e-13.** PARITY PROVEN.
Every number below is from the corrected engine. This is also the check that was never
done for QUAD, whose Pine parity was assumed for 100+ versions.

## 1. THE HEADLINE — stronger than "no edge"
**On M1 the Supertrend flip is measurably WORSE THAN A COIN FLIP, before any cost.**

2019-2026, M1, 283,251 trades, gross (zero costs, zero exits):
**-0.0300 pt/trade, t = -5.44.**

That is not "no information" — it is anti-predictive, and significant. The mechanism is
plain: the flip fires when price crosses a band 1.2 x ATR away, so it systematically buys
after the move up and sells after the move down. Confirmed independently by the random
control below.

### Economics, 2024-01 -> 2026-11, hold to the opposite flip
| | points | GBP @0.01 lot |
|---|---|---|
| GROSS before cost | -1,352 | -991 |
| spread paid | -18,554 | -13,600 |
| NET | **-19,906** | **-14,591** |

93,391 trades, 103.8/day, 900 trading days. Net **-0.213 pt/trade** = almost exactly one
spread. **93% of the loss is transaction cost**, the rest is the negative edge.
Equity from GBP50 at 0.01 lots: ruin. Worst day -GBP157.94, median day -GBP14.30.

## 2. NO INFORMATION AT ANY HORIZON
Forward return after each flip, 93,391 signals, no costs, no exits:

| horizon | 1m | 2m | 3m | 5m | 10m | 15m | 30m | 60m | 120m | 240m |
|---|---|---|---|---|---|---|---|---|---|---|
| mean pt | -0.001 | -0.006 | -0.000 | +0.002 | -0.015 | -0.015 | -0.013 | -0.017 | -0.015 | -0.014 |
| t | -0.26 | -0.79 | -0.05 | +0.21 | -0.95 | -0.79 | -0.48 | -0.45 | -0.28 | -0.19 |

Every |t| < 0.95. A flip tells you nothing about the next minute or the next four hours.

## 3. NOT A PARAMETER PROBLEM
21 settings (multiplier 1.2-6.0 x ATR 7/10/14), 2024+. Every gross t-stat in [-0.95, +1.86].
Nothing significant. The useful part is the *shape*:

| multiplier | trades/day | gross/trade | gross t | net/trade | GBP/day |
|---|---|---|---|---|---|
| 1.2 | 103.8 | -0.0145 | -0.93 | -0.213 | -16.21 |
| 2.0 | 54.5 | -0.0142 | -0.49 | -0.213 | -8.49 |
| 3.0 | 29.7 | +0.0646 | +1.20 | -0.134 | -2.92 |
| **4.0** | 18.8 | **+0.1573** | **+1.86** | -0.042 | **-0.58** |
| 6.0 | 9.8 | +0.1152 | +0.73 | -0.085 | -0.61 |

Gross turns positive as the band widens, and multiplier 4.0 is the best cell in the whole
grid (consistent at t=1.86/1.73/1.66 across ATR 7/10/14). It is still **below
significance**, and net is still negative. Trading less shrinks the loss toward zero; it
does not make it positive.

## 4. NOT AN EXIT PROBLEM
38 exit variants. Pre-registered acceptance (PLAN 4.3): remove >=60% of losing points while
removing <25% of winning points. **NOTHING PASSED.** Nothing beat plain hold-to-flip
(-0.191/trade) by a meaningful margin; targets were strictly worse the tighter they got.

**Every early cut removed a larger share of WINNING points than of losing points:**

| cut | losing pts removed | winning pts removed |
|---|---|---|
| 0.5pt / 3bar | 49.1% | **58.1%** |
| 0.5pt / 2bar | 47.7% | **56.4%** |
| 0.8pt / 1bar | 33.4% | **39.4%** |
| 2.0pt / 2bar | 15.9% | **18.8%** |

That symmetry is the fingerprint of an entry with no edge. If the entries held one, cutting
the bad ones would be asymmetric in our favour. It never is, at any threshold.

## 5. THE "MONEY LEFT ON THE TABLE" NUMBER WAS A BIASED STATISTIC
The old diagnosis: "best moment of every trade summed to +GBP293 but GBP440 was handed
back, so the entries are fine and the exits lose it."
Summing each trade's best moment is positive for **any** entry, because you only count the
favourable extreme of each path. Control — random entries, same count, same holding times:

| | sum of best moments | net |
|---|---|---|
| Supertrend | +292,704 pt | -19,906 |
| coin flip (mean of 5 runs) | ~216,800 pt | **-19,314** |

The coin flip shows 74% of the same "available profit" **and finishes 592 points better.**
The Supertrend's extra best-moment total is just higher volatility at the moment it fires —
bigger excursions both ways, worse net. So "we are leaving money on the table" was
measuring an artefact. That is why 100+ versions of exit engineering never moved the
outcome: they were chasing a number with no edge in it.

## 6. THE TIMEFRAME LADDER — the one structural result
Same signal, same code, 2019-2026, varying only the clock:

| TF | trades | per day | median pts offered | offered/spread | gross/trade | gross t | net/trade | GBP/day |
|---|---|---|---|---|---|---|---|---|
| **M1** | 283,251 | 115.7 | 0.48 | 2.4 | -0.030 | **-5.44** | -0.266 | **-22.52** |
| M5 | 51,600 | 21.1 | 1.59 | 7.9 | -0.007 | -0.23 | -0.244 | -3.76 |
| M15 | 16,306 | 6.7 | 3.25 | 16.2 | +0.019 | +0.20 | -0.218 | -1.06 |
| M30 | 7,918 | 3.2 | 5.06 | 25.3 | +0.206 | +1.04 | -0.029 | -0.07 |
| **H1** | 3,803 | 1.6 | 7.86 | 39.3 | **+0.795** | **+1.88** | **+0.564** | **+0.64** |
| H4 | 1,060 | 0.4 | 15.51 | 76.9 | +1.557 | +1.17 | +1.326 | +0.42 |

Monotone and mechanically sensible. M1 is significantly negative. H1 is the only timeframe
with a positive net, and even there t=1.88 is **below significance on 3,803 trades**.
Slowing the clock removes the cost problem. It does not prove an edge.

## 7. NO REGIME HIDES AN EDGE
15 conditional subsets at the 15m horizon. Only one |t| > 2: "price AGAINST the DEMA60",
t = -2.54. Its complement (price agreeing with the DEMA) is only t = +0.90 — so filtering
to DEMA-agreeing trades removes some loss but does **not** create a positive edge, and
+0.021 pt/trade does not come close to covering a 0.20 spread.
All five sessions |t| < 1.03. All five ATR quintiles |t| < 0.88. Buy-only and sell-only
both insignificant. Every hour, session, weekday and volatility quintile is negative on net.

## 8. THE TARGET ARITHMETIC — stated once, plainly
At 0.01 lots, 1 point = GBP 0.733.
- GBP 200/day needs **273 net points/day**.
- Gold's entire daily range in 2026 is roughly 40-80 points.
- So that target needs 350-650% of the whole daily range, every day.
- At 0.05 lots it still needs ~55 points/day, about 100% of the daily range.
GBP 100-300/day is not reachable at 0.01-0.05 lots by any strategy, however good. It needs
a materially larger account AND a real edge. At 0.01 lots on GBP 50, a genuinely good edge
is worth a few pounds a day.

## 9. WHY THE GOOD DAYS WERE REAL
Median day -GBP14.30, best day **+GBP167.06**, worst -GBP157.94, at 0.01 lots. With ~104
trades/day the daily dispersion is enormous, so very good days happen often. They were
variance, not edge — which is exactly why they never persisted.

## 10. WHAT WOULD PROVE THIS WRONG (pre-registered, PLAN 6)
- A wrong Supertrend. **Addressed**: parity now PROVEN against the EA's own code, 0/4000
  mismatches. This is the error I actually made, and it is fixed.
- Bad data. Triple-sourced, cross-validated to within $0.09 median, matches his own tickets.
- Too-pessimistic costs. Does not apply: the GROSS figure uses zero costs and is negative.
- A hidden regime. 15 subsets, 6 timeframes, 21 parameterisations.
Remaining open question: whether a *different* signal on gold carries information.
That is the only constructive question left, and `research/screen.py` now answers it.

## 11. THE CONSTRUCTIVE SCREEN — 12 candidate signals, and why none of them work
Pre-registered in PLAN2.md. 492 tests: 12 candidates x 6 timeframes x 6 horizons.

### Stage 1 — four candidates cleared the full bar
|t| >= 4, mean >= 1.5x spread, consistent in both walk-forward halves, n >= 500:
- H1 "continue DEMA 2atr" @20 bars: +1.806 pt, t=5.53, 9.0x spread
- M30 "continue DEMA 2atr" @20 bars: +0.800 pt, t=5.59, 4.0x spread
- H1 "breakout 20b" @20 bars: +2.411 pt, t=5.05, 12.1x spread
- H1 "continue DEMA 2atr" @10 bars: +1.000 pt, t=4.51, 5.0x spread

### Stage 2 — those t-statistics were INFLATED, and I caught it
"continue DEMA 2atr" fires on **11,816 of 46,602 H1 bars (25% of all bars)** with 10-20 bar
forward windows. The windows overlap massively, so the observations are not independent and
the t-stat is badly overstated. It is a state, not an event.

Re-tested in `research/confirm.py` with:
 1. NON-OVERLAPPING windows (a signal only counts if it is >= horizon bars after the last),
    plus a stricter 2x-gap variant
 2. REAL EXECUTION — fill at the next bar's open, bid/ask handled, one full spread
 3. walk-forward halves and a max-drawdown path

**RESULT: NOTHING SURVIVES.** Best case H1 "breakout 20b" @20, gap=2h: t=2.62, n=917.
And its halves are **t_h1 = 0.37 / t_h2 = 2.68** — the entire apparent edge sits in the
second half of the sample.

That pattern repeats across every candidate: look down the t_h1 column and it is near zero
or negative almost everywhere, while t_h2 is 1.5-2.9. Gold trended hard from 2024 (2000 ->
5593 -> 3688), so every momentum/breakout signal looks good in that window and looks like
nothing in 2019-2022. **That is one directional regime, not a persistent edge.**

### What the screen DID establish — and it explains the Supertrend result
On M1 the statistically strongest structure is **mean reversion**, and it is very strong:
| M1 candidate | horizon | n | mean pt | t | mean/spread |
|---|---|---|---|---|---|
| fade breakout 60b | 3 | 187,093 | +0.047 | **+9.68** | 0.23 |
| revert EMA14 1.5atr | 2 | 548,217 | +0.020 | **+9.16** | 0.10 |
| revert DEMA 3.0atr | 2 | 286,126 | +0.025 | **+8.56** | 0.13 |
| breakout 60b (momentum) | 3 | 187,093 | -0.047 | **-9.68** | -0.23 |

Two things follow:
1. **Gold M1 mean-reverts at t~9-10.** Real, highly significant structure. But the mean move
   is 0.02-0.05 pt against a 0.20 spread — the edge is 4-10x SMALLER than the cost, so it is
   not tradeable. Significant and worthless at once.
2. **Momentum on M1 is the wrong side of that coin (t = -9.68).** The Supertrend flip IS a
   momentum/breakout entry. This is the mechanism behind its t = -5.44 gross loss: it is
   systematically trading against the one real statistical structure on the timeframe.

## 12. BOTTOM LINE
- The signal he trades is anti-predictive on the timeframe he trades it on.
- No parameter, exit, regime or timeframe fixes it.
- A broad screen of simple OHLC signals found nothing that survives honest statistics.
- The one real structure (M1 mean reversion) is smaller than the spread.
- Therefore: simple price-derived signals on gold M1 at retail spread do not contain a
  tradeable edge. The constraint is the cost-to-move ratio, not indicator choice.
- UNTESTED and still open: tick volume (present in the dataset, never used), and any
  discretionary rule he applies by eye that is not written down in the code.

---

## 13. Break-even and trail (v1.30). Owner-prompted; includes a bug of mine.

He said: *"there's no trailing SL or even break even here"* and *"we go into profit and
it just doesn't know when to close... we are capturing small profits hundreds of times
that's the goal."* Both fair. The 38-variant sweep in §7 contained profit LOCKS and
TARGETS but **never a true break-even**, and never break-even combined with a tight
trail. That was a real hole.

### 13.0 My bug, first
I placed the break-even stop at `fill + spread`. A long fills at ASK and exits on BID,
so P/L = exit − fill; a stop **at the fill price** is already exactly flat. The extra
spread booked **+0.32 pt/trade that never filled**. Every break-even figure I reported
in the v1.20 message was inflated by roughly that. Corrected everywhere below.

I also suspected same-bar look-ahead (arming a trail off the high of the bar the trade
is inside). I checked: the simulator already evaluated the stop *before* updating the
peak, so the level in force on bar *i* only used bars < *i*. That suspicion was wrong.

### 13.1 Corrected results — real per-bar spread x 1.90 (his broker), 93,391 trades

| rule | pt/trade | t | GBP/day |
|---|---|---|---|
| nothing (hold to flip) | −0.362 | −25.7 | −28.8 |
| break-even 0.10 ATR | −0.179 | −20.0 | −14.2 |
| break-even 0.10 + trail 0.25 ATR from +0.5 | **−0.075** | −12.1 | −5.9 |

Break-even arm swept 0.05–1.00; **0.10 is best and it is monotone** — the tighter the
better, which is itself evidence the entry has no drift to wait for. Fixed targets
remain strictly worse at every size.

### 13.2 The coin-flip control — this is the finding that matters
Same entry bars, same exit rules, direction randomised:

| | signal | random direction | signal's contribution |
|---|---|---|---|
| nothing | −0.362 | −0.358 | −0.004 |
| BE + trail | −0.075 | −0.099 | **+0.024** |

**The Supertrend's direction is worth +0.024 pt/trade, ~7% of one spread.** The exit
rule produces essentially the entire improvement. Any future work belongs in the entry,
not the exit — and the §3 result (flip is anti-predictive, t = −5.44) is consistent with
this: the indicator is close to informationless and the exits were masking it.

### 13.3 Slippage is now the binding constraint
With a trail, **99–100% of trades exit on a stop**, so slippage is a flat per-trade tax:

| avg stop slippage | BE+trail pt/trade |
|---|---|
| 0.00 | −0.075 |
| 0.10 | −0.174 |
| 0.20 | −0.274 |
| 0.29 | −0.362 = the whole gain gone |

No dataset I hold contains his broker's stop-fill slippage. **v1.30 measures it** in the
panel and in the journal (`stop_level`, `stop_hit`, `slip_pts`). Open question, highest
value of anything outstanding.

### 13.4 ATR dependence — pre-registered in PLAN3.md, partially accepted
Net rises monotonically with ATR, zero-crossing at **ATR ≈ 1.63** at a 0.320 spread.
Weighted slope **+0.070 pt per unit of ATR/spread, t = 38.4**. Sign agrees in both
walk-forward halves for every bucket.

| ATR | N | nothing | BE+trail | half A | half B |
|---|---|---|---|---|---|
| 0.00–0.75 | 27,317 | −0.313 | −0.273 | −0.251 | −0.216 |
| 0.75–1.25 | 21,652 | −0.312 | −0.174 | −0.176 | −0.187 |
| 1.25–2.00 | 21,370 | −0.299 | −0.064 | −0.078 | −0.024 |
| 2.00–2.50 | 8,597 | −0.197 | +0.051 | +0.116 | +0.174 |
| 2.50–3.50 | 8,252 | −0.363 | +0.124 | +0.169 | +0.269 |
| 3.50+ | 6,202 | −0.471 | +0.671 | +0.166 | +0.857 |

**PLAN3 acceptance: PARTIAL.** Slope t > 4 PASS. All bucket signs agree across halves
PASS. Top bucket positive with t > 2 in *both* halves **FAIL** (ATR 3.5+ gave t = 0.7 in
half A). The 2.5–3.5 bucket passes fully (A t = 2.2, B t = 9.3). So the relationship is
real; the extreme tail is not yet trustworthy.

Mechanism is **not** the indicator — the coin flip is positive in the high buckets too.
It is a long-volatility payoff: capped loss, open upside, which pays when realised
movement exceeds what the stop-outs cost. His live ATR of 2.824 sits in the
second-best bucket, which is the honest explanation for why the chart looks tradeable
to him right now and did not look that way in the 2024 data.

**Consequence is a signal filter, so it is NOT implemented.** Owner's call per the
standing rules. Number brought, decision not taken.

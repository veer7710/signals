# 10 — THE MISSED MOVES. Measuring the owner's complaint.

> *"the liquidity ea and pine are not good enough the signals don't use levels
> wisely they miss clear clear moves that could've made us 40-200 pounds
> easily... we need bsl ssl liquidity sweeps rejection zones support resistance
> play ping pong"*

**He is right that the moves are missed. He is wrong about why, and the four
concepts he named do not fix it.**

## Scope, stated up front

**GOLD only, 15m and 1h.** There is no M1 or M5 data in this repository and it
cannot be fetched. Veer trades M1/M5/M15. **Nothing below measures his
timeframes.** The 15m sample is 4554 bars (2026-06-22 → 2026-08-31); the 1h
sample is 13725 bars (2024-04-09 → 2026-08-31).

Reproduce:

```
python3 JARVIS/research/test_engine.py        # ALL TESTS PASSED, run first
python3 JARVIS/research/missed_moves.py       # steps 1 and 2
python3 JARVIS/research/level_concepts.py     # step 3
```

Definitions. A **big move** is a zigzag leg of at least X points measured from
the turning point it started at, X = 40 and separately 100. At 0.01 lots
XAUUSD is £0.787 per point, so 40 points ≈ £31 and 100 points ≈ £79 — the range
Veer named. The zigzag is computed over the whole series *with* hindsight: it is
the **scoreboard**, not a signal, and nothing in the trading path reads it. A
move is **CAUGHT** if the shipped stack (E-080: toptick + FVG + order block, one
position, first touched wins) entered in the **same direction** with its entry
bar within N = 3 bars of the turning point.

---

## 1. THE HEADLINE — the catch rate

```
GOLD 1h   1080 moves >= 40 points    CAUGHT 176 (16.3%)   MISSED 904 (83.7%)
GOLD 1h    182 moves >= 100 points   CAUGHT  50 (27.5%)   MISSED 132 (72.5%)
GOLD 15m   102 moves >= 40 points    CAUGHT  35 (34.3%)   MISSED  67 (65.7%)
GOLD 15m    18 moves >= 100 points   CAUGHT   9 (50.0%)   MISSED   9 (50.0%)
```

**On GOLD 1h the stack misses 83.7% of every 40-point move and 72.5% of every
100-point move.** In points on the table: 90 875 points of 40-point-plus legs
existed, 76 981 of them (84.7%) in legs the stack never traded.

The result is not an artefact of the ±3 bar window, but it is sensitive to it,
so the whole curve is reported rather than the one number:

```
              N=1     N=3     N=5    N=10    N=20
GOLD 15m    23.5%   34.3%   43.1%   56.9%   66.7%
GOLD 1h     11.7%   16.3%   20.1%   33.1%   50.6%
```

### But the miss is only half of the £40–200 complaint. The other half is the exit.

```
                              move offered      trade banked     capture
GOLD 1h,  caught >=40pt         78.9 pts          10.1 pts        12.9% median
GOLD 1h,  caught >=100pt       209.7 pts          14.3 pts         7.6% median
GOLD 15m, caught >=40pt         85.1 pts           2.2 pts         4.8% median
GOLD 15m, caught >=100pt       202.1 pts           4.0 pts         3.8% median
```

**When the stack DOES catch a 100-point move on 1h it banks 14.3 points — £11.22
at 0.01 lots — out of £165 that was there.** The stack's median winning trade is
12.2 points (£9.57) on 1h and 9.6 points (£7.56) on 15m. The best single trade in
13725 bars of 1h was 97 points (£76).

A 0.60 ATR stop with a 2R target is a ~1.2 ATR = ~15 point trade on 1h. **£40–200
per trade is arithmetically impossible at this geometry even at a 100% catch
rate.** Raising the catch rate cannot deliver what he is asking for on its own;
the target caps every trade at about £10. That is the single most important
sentence in this document, and it is an exit finding, not an entry finding.

---

## 2. WHY THE MISSES HAPPENED — ranked

Every missed move gets exactly one cause, assigned in priority order by
re-running the candidate generator with instrumentation (`zone_diag`), so the
counts add to the number of misses. GOLD 1h, 904 missed 40-point moves:

| rank | cause | misses | % | % of missed points |
|---|---|---|---|---|
| 1 | signal existed, limit NEVER FILLED inside its wait window | 463 | 51.2% | 52.2% |
| 2 | zone LIVE but older than `arm_life` = 60 bars | 223 | 24.7% | 23.7% |
| 3 | zone LIVE, resting limit NEVER REACHED (0.25 ATR past the far edge) | 107 | 11.8% | 13.1% |
| 4 | no level of any kind at the turn | 55 | 6.1% | 5.7% |
| 5 | signal existed and was fillable, account was BUSY | 26 | 2.9% | 2.8% |
| 6 | zone BLACKLISTED as already used | 18 | 2.0% | 1.7% |
| 7 | signal existed and WAS taken, but filled too late | 10 | 1.1% | 0.7% |
| 8 | no zone, but the level had been touched before | 2 | 0.2% | 0.1% |

On the 132 missed **100-point** 1h moves the order changes: cause 1 falls to
40.9% and **cause 2 rises to 32.6%**. On GOLD 15m (67 missed 40-point moves) the
order is the same: 47.8% cause 1, 19.4% cause 2, 13.4% cause 3.

### Cause 1 is not what its name suggests, and this matters

Every one of those 463 "signals" came from FVG (304) or order block (159), never
from the toptick zone — because `all_signals` emits an FVG/OB candidate on
**every bar** a gap of the right direction is live, and its limit is the gap's
midpoint. **The median distance from the turning point to that limit was 6.96
ATR — about 85 points.** These are not near-misses. They are directionally
correct levels sitting somewhere else entirely.

Read correctly, **cause 1 is a level-selection failure, not a fill failure**, and
it collapses into "the stack had no usable order near the turn".

### Was there a level at the turn at all?

Distance from the turning point to the nearest level of each kind the chart
already knew about, GOLD 1h, 40-point moves. The **random-bar column is 1500
random (bar, direction) pairs** and it is the only thing that makes the other two
columns mean anything.

| level kind | missed <1.0 ATR | caught <1.0 ATR | RANDOM <1.0 ATR |
|---|---|---|---|
| toptick zone edge | 31% | 60% | 21% |
| toptick resting limit | 27% | 56% | 16% |
| FVG mid | 23% | 27% | 11% |
| order block mid | 47% | 47% | 33% |
| **ANY stack resting order** | **67%** | **83%** | **48%** |
| any prior swing pivot | 65% | 81% | **67%** |
| equal-high/low pool (≥2) | 30% | 31% | **28%** |

Three things fall out of that table.

1. **At 67% of the missed turning points the stack already had a resting order
   within 1 ATR.** Against 48% at random bars. The levels were there. Something
   between the level and the order stopped the trade — which is exactly what
   causes 2, 3 and 6 describe. **Veer's phrasing "don't use levels wisely" is
   the accurate one; "don't have the levels" is not.**
2. **"The level had been touched before" carries zero information.** A prior
   swing pivot sits within 1 ATR of 65% of missed turns, 81% of caught turns —
   and **67% of random bars**. Adding untouched-before-levels to the level set
   would add noise, not signal.
3. **Equal-high/low pools are not at turning points more often than chance**
   at this proximity test: 30% missed / 31% caught / 28% random. That is a
   negative pre-test of concept (a) before it was ever traded.

### The two knobs the ranking names, turned

Causes 2 and 3 name two shipped parameters. `arm_life` = 60 bars and
`InpEntryPast` (`FRAC` = −0.25, the limit 0.25 ATR past the far edge). 15 cells
per timeframe, 30 in total — declared, because the best of 30 always looks good.

GOLD 1h, at the shipped FRAC:

| FRAC | arm_life | n | win% | expectancy | t | points | catch% |
|---|---|---|---|---|---|---|---|
| −0.25 | **60 (shipped)** | 517 | 48.7% | +0.414R | +6.28 | +2079 | 16.3% |
| −0.25 | 180 | 571 | 50.3% | +0.460R | +7.33 | +2473 | 18.6% |
| −0.25 | **600** | **600** | **51.2%** | **+0.487R** | **+7.95** | **+2743** | **19.7%** |
| −0.50 | 600 | 493 | 57.0% | +0.662R | +9.90 | **+2833** | 16.5% |

`arm_life = 600` is **not a tuned interior value — it equals the zone's own life
in `zone_stream`, so it is the removal of the constraint entirely.** Points
improve monotonically with `arm_life` in **14 of the 15** FRAC × timeframe
combinations tested.

Attacked properly (`arm_life_validate`):

```
GOLD 1h    base  arm_life 60   n 517  48.7%  +0.414R  t +6.28  +2079 points
           new   arm_life 600  n 600  51.2%  +0.487R  t +7.95  +2743 points
           THE TRADES IT ADDS  n 101  56.4%  +0.645R  t +4.35   +555 points
             added vs base +0.231R, +1.4 sd — not distinguishable, NOT worse
           OOS +0.526R / +0.448R   walk-forward 6/6   control 20 seeds +2.5 sd
           Monte Carlo drawdown median 10.2R, 95th 15.0R
GOLD 15m   base  n 170  +0.441R  +398 points -> new n 199  +0.510R  +565 points
           THE TRADES IT ADDS  n 36  58.3%  +0.697R  t +2.82  +165 points
           OOS +0.669R / +0.353R   walk-forward 6/6   control 20 seeds +3.4 sd
```

**Verdict on lifting `arm_life`: SUPPORTED.** It clears E-074's rule — the trades
it *adds* are not worse than the ones already there (+0.645R against +0.414R, and
statistically indistinguishable rather than worse) — it holds 6/6 walk-forward
folds on both timeframes, and it survives a 20-seed control. It is +32% points on
1h and +42% on 15m for a one-line change.

**But it recovers only 3.4 percentage points of catch rate (16.3% → 19.7%).** It
does not close the gap Veer is complaining about. And note the last row of the
table: **FRAC −0.50 / arm_life 600 banks MORE points (+2833) with FEWER trades
and a LOWER catch rate (16.5%).** Catching more turns and making more money are
different objectives, which is E-074 in a new place.

---

## 3. THE FOUR CONCEPTS HE NAMED

Each built as a standalone trigger, entry at the next bar's open, **stop 0.60
ATR**, one position at a time, ties lose, costs both ends (spread 0.46 measured
off his terminal). Control = 20 random-entry seeds with matched geometry; z is
against the **standard error of the control mean** (E-064), not the per-seed sd.
Exit rules reported: no fixed target at 200 bars (the brief's rule), no fixed
target at 20 bars (because the 200-bar version turns out to be degenerate), and
the 2R target the shipped stack uses. **26 cells in total, one parameter set per
concept fixed in advance from Veer's own description. No parameter search was
run, so no cell here is the best of a grid.**

### GOLD 1h

| concept | exit | n | win% | expectancy | t | points | wf | ctrl | z | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| a. BSL/SSL pool sweep | no tgt | 200 | 5.5% | +0.158R | +0.34 | −113 | 2/6 | +0.091R | +0.1 | **UNPROVEN** |
| a. BSL/SSL pool sweep | no tgt/20b | 280 | 16.8% | −0.080R | −0.51 | −547 | 2/6 | +0.004R | −0.5 | **REJECTED** |
| a. BSL/SSL pool sweep | 2R | 311 | 31.2% | −0.106R | −1.34 | −322 | 1/6 | −0.087R | −0.2 | **REJECTED** |
| b. rejection zone | no tgt | 412 | 4.6% | −0.160R | −0.63 | −521 | 1/6 | +0.035R | −0.8 | **REJECTED** |
| b. rejection zone | no tgt/20b | 718 | 13.0% | −0.291R | −3.51 | −2889 | 0/6 | −0.002R | −3.5 | **REJECTED** |
| b. rejection zone | 2R | 898 | 25.6% | −0.272R | −6.23 | −3395 | 0/6 | −0.096R | −4.0 | **REJECTED** |
| c. S/R flip | no tgt | 605 | 4.8% | −0.012R | −0.05 | −842 | 3/6 | +0.091R | −0.5 | **REJECTED** |
| c. S/R flip | no tgt/20b | 1434 | 15.0% | −0.021R | −0.28 | −1586 | 3/6 | −0.045R | +0.3 | **REJECTED** |
| c. S/R flip | 2R | 2286 | 30.0% | −0.145R | −5.03 | −3634 | 0/6 | −0.101R | −1.5 | **REJECTED** |
| d. ping pong | no tgt | 258 | 5.0% | +0.094R | +0.27 | +11 | 2/6 | +0.068R | +0.1 | **UNPROVEN** |
| d. ping pong | no tgt/20b | 388 | 15.7% | −0.249R | −2.15 | −821 | 0/6 | +0.000R | −2.1 | **REJECTED** |
| d. ping pong | 2R | 457 | 33.0% | −0.051R | −0.77 | +355 | 1/6 | −0.091R | +0.6 | **REJECTED** |
| d. ping pong | opp edge | 364 | 11.3% | −0.220R | −1.79 | −693 | 2/6 | −0.042R | −1.4 | **REJECTED** |

### GOLD 15m

| concept | exit | n | win% | expectancy | t | points | wf | z | verdict |
|---|---|---|---|---|---|---|---|---|---|
| a. BSL/SSL pool sweep | no tgt | 64 | 4.7% | −0.033R | −0.05 | +10 | 2/6 | −0.3 | **REJECTED** |
| a. BSL/SSL pool sweep | no tgt/20b | 75 | 14.7% | −0.243R | −0.83 | −73 | 1/6 | −1.0 | **REJECTED** |
| a. BSL/SSL pool sweep | 2R | 87 | 34.5% | −0.021R | −0.14 | −14 | 2/6 | +0.7 | **REJECTED** |
| b. rejection zone | no tgt | 129 | 5.4% | +0.275R | +0.49 | +153 | 4/6 | +0.1 | **UNPROVEN** |
| b. rejection zone | no tgt/20b | 206 | 14.1% | −0.151R | −0.69 | −314 | 2/6 | −0.5 | **REJECTED** |
| b. rejection zone | 2R | 249 | 27.7% | −0.223R | −2.63 | −385 | 0/6 | −1.1 | **REJECTED** |
| c. S/R flip | no tgt | 200 | 3.5% | −0.082R | −0.21 | −187 | 3/6 | −0.6 | **REJECTED** |
| c. S/R flip | no tgt/20b | 469 | 14.3% | −0.052R | −0.35 | −233 | 2/6 | −0.3 | **REJECTED** |
| c. S/R flip | 2R | 776 | 29.8% | −0.162R | −3.30 | −669 | 0/6 | −0.5 | **REJECTED** |
| d. ping pong | no tgt | 87 | 5.7% | −0.274R | −0.66 | −101 | 2/6 | −1.0 | **REJECTED** |
| d. ping pong | no tgt/20b | 120 | 22.5% | +0.293R | +1.11 | +199 | 4/6 | +1.2 | **UNPROVEN** |
| d. ping pong | 2R | 156 | 39.7% | +0.139R | +1.18 | +248 | 2/6 | +2.3 | **UNPROVEN** |
| d. ping pong | opp edge | 124 | 16.9% | +0.143R | +0.59 | +120 | 3/6 | +1.1 | **UNPROVEN** |

**Not one of the 26 cells reaches t = 2.0.** Not one is PROMISING. The best cell
in the whole table is ping pong / 2R on 15m at +0.139R, t = +1.18, 2/6
walk-forward folds — which is what the best of 26 looks like when there is
nothing there.

Two notes on fairness to the concepts:

* **The brief's "no fixed target" rule is degenerate at 200 bars.** With a 0.60
  ATR stop and no target, 94.5–95.4% of trades hit the stop on GOLD 1h (189/200,
  393/412, 576/605, 245/258) and the entire expectancy rests on the 11 to 29
  time exits that survive, which is why those t-statistics sit near zero in both
  directions. The 20-bar horizon was added so the rule could be measured at all.
  It did not rescue any concept.
* **Every concept is one-directional.** GOLD 1h no-target: S/R flip long +0.390R
  / short −0.521R; ping pong long +1.047R / short −0.499R; rejection zone long
  −0.270R / short +0.036R. On 15m the signs flip for BSL/SSL (long +0.538R /
  short −0.603R). An edge that exists in one direction on one timeframe and
  inverts on the other is gold's 2024–26 uptrend, not a concept.

### Do the concepts at least FIRE at the missed turns?

This is the question that matters more than their P&L, and it has a different
answer. A concept that fires often catches turns by luck, so each rate is shown
against two controls: **scatter** (same count, uniformly random bars — biased
against clustered signals, stated openly) and **time-shift** (the entire signal
train shifted circularly, preserving spacing and clustering exactly and
destroying only the alignment with price — **this is the fair one**). 16 seeds
each, z against the standard error of the control mean.

GOLD 1h, of the 904 missed 40-point moves:

| concept | signals | catches missed | time-shift control | z |
|---|---|---|---|---|
| **a. BSL/SSL pool sweep** | 357 | **106 (11.7%)** | 75.4 (8.3%) | **+11.5** |
| b. rejection zone | 1254 | 210 (23.2%) | 193.4 (21.4%) | +5.0 |
| c. S/R flip | 5924 | 443 (49.0%) | 437.8 (48.4%) | +1.2 |
| d. ping pong | 938 | 102 (11.3%) | 97.4 (10.8%) | +2.1 |

GOLD 15m, of the 67 missed 40-point moves:

| concept | signals | catches missed | time-shift control | z |
|---|---|---|---|---|
| **a. BSL/SSL pool sweep** | 97 | **9 (13.4%)** | 4.8 (7.1%) | **+7.7** |
| b. rejection zone | 335 | 17 (25.4%) | 13.7 (20.4%) | +6.0 |
| c. S/R flip | 1873 | 28 (41.8%) | 33.2 (49.5%) | −5.9 |
| d. ping pong | 283 | 14 (20.9%) | 7.6 (11.3%) | +12.7 |

**BSL/SSL pool sweep is the only concept that is clearly better than a fair
control on BOTH timeframes** — it fires at 1.4× to 1.9× the chance rate at
turning points the stack missed. **And it still does not pay**: 200 trades,
+0.158R, t = +0.34, 2/6 walk-forward, +0.1 control sd on 1h.

**That is the whole result in one line: equal highs and equal lows do mark
turning points more often than chance, but not often enough, and not with enough
follow-through, to be a trade at a 0.60 ATR stop.** Locational information is
not an edge.

**S/R flip fires on 5924 of 13725 bars (43%) and catches missed turns at exactly
the rate a time-shifted copy of itself does.** It is not a signal; it is a
description of price being near a round number of prior pivots.

---

## VERDICTS

| claim | verdict |
|---|---|
| "they miss clear clear moves" | **CONFIRMED.** 83.7% of 40-point and 72.5% of 100-point moves on GOLD 1h are not traded within ±3 bars of the turn; 65.7% / 50.0% on 15m. |
| "the signals don't use levels wisely" | **SUPPORTED.** At 67% of missed turns a stack order already rested within 1 ATR, against 48% at random bars. The levels are present; the arming and fill rules discard them. |
| "could've made us 40-200 pounds" | **DISPROVEN as an entry problem.** Caught 100-point moves bank 14.3 points (£11.22) of 209.7 offered. The 2R target caps every trade near £10 regardless of catch rate. |
| raising `arm_life` 60 → 600 | **SUPPORTED.** +32% points on 1h, +42% on 15m, added trades +0.645R vs base +0.414R, 6/6 walk-forward both timeframes, +2.5 / +3.4 control sd. Recovers only 3.4pp of catch rate. |
| (a) BSL/SSL pool sweep as a trigger | **UNPROVEN** (1h, t=+0.34, 2/6 folds) / **REJECTED** (15m, negative). Locationally real (+11.5 / +7.7 sd vs a fair control), financially absent. |
| (b) rejection zone as a trigger | **REJECTED.** Negative on 5 of 6 cells; 2R on 1h is −0.272R at t=−6.23. |
| (c) S/R flip as a trigger | **REJECTED.** Negative in every cell; catch rate indistinguishable from a time-shifted copy of itself. |
| (d) ping pong as a trigger | **REJECTED** on 1h in all four cells; **UNPROVEN** on 15m (best cell t=+1.18, 2/6 folds). |

**None of the four concepts would have caught the missed moves in a way that
paid.** Only BSL/SSL locates them better than chance, and it does not convert.

## The honest caveats

- **15m and 1h. No M1/M5 exists here.** D-010 says XAUUSD M1/M5/M15. The 1h
  result carries all the statistical weight and is a timeframe that is never
  traded. Exporting M1/M5 remains the blocker on every conclusion here.
- **The 15m sample is 70 days.** 102 forty-point moves and 18 hundred-point
  moves. Anything computed on the 100-point 15m row (n = 18) is noise.
- **The zigzag defines what counts as a "big move".** A different reversal
  threshold changes the population. 40 and 100 points were chosen from Veer's
  own £40–200 wording before anything was run, not tuned afterwards.
- **Multiple comparisons.** 26 concept cells + 30 lever cells + 5 window widths
  = 61 configurations in this document. At that count the honest t bar is around
  3.3, not 2.0. Only the `arm_life` result clears it (t = +7.95), and it clears
  it on a parameter that was set to its natural boundary rather than searched.
- **`arm_life = 600` was not tested out of this repository's data.** It should
  not be shipped on this evidence alone. That is Veer's decision after
  adversarial review, not a recommendation here.

## Files

- `/home/user/signals/JARVIS/research/missed_moves.py` — steps 1 and 2, the
  lever sweep and the `arm_life` validation
- `/home/user/signals/JARVIS/research/level_concepts.py` — the four concepts and
  the catch test

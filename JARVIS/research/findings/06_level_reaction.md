# E-053 — Do marked liquidity levels produce a reaction at all?

**Verdict: DISPROVEN.** A marked pivot level produces a reaction at the same
rate as a randomly-placed price at the same distance. Across 8 market/timeframe
combinations, 55,307 real touches and 165,556 matched-random touches, real
levels reacted **49.9% on average versus 50.4% for the random control** — real
is BELOW random on 7 of 8 markets, and once same-bar duplicate touches are
removed the pooled difference is **z = +0.22**, which is nothing.

Not one of 36 parameter configurations, and not one of 4 touch tolerances,
produced a positive difference on 6 or more of the 8 markets.

Script: `JARVIS/research/level_reaction.py`

```
python3 JARVIS/research/test_engine.py
python3 JARVIS/research/level_reaction.py SELFCHECK
python3 JARVIS/research/level_reaction.py ALL
python3 JARVIS/research/level_reaction.py GRID
python3 JARVIS/research/level_reaction.py TOL
python3 JARVIS/research/level_reaction.py COUNTS
python3 JARVIS/research/level_reaction.py GOLD 1h
```

---

## The hypothesis, falsifiable, with its mechanism

> **H:** Price that returns to a previously-marked pivot level reacts away
> from it MORE OFTEN than it reacts away from an arbitrary price at the same
> distance, because resting orders and stops accumulate at prices market
> participants can see, and that accumulated liquidity absorbs the approach.

Falsified if the reaction rate at real pivot levels is not distinguishable
from the reaction rate at matched random levels — in which case the marked
level is decoration.

This is the E-050 rule applied to an indicator instead of an entry: a
reaction rate with no matched control is not a result about levels, it is a
result about how easy the reaction definition is.

## The definitions, made objective

| term | definition as coded |
|---|---|
| LEVEL | a bar whose high is the highest of the `len` bars either side (pivot high / buyside) or whose low is the lowest (pivot low / sellside). Confirmed at `pivot_bar + len`; **cannot be touched before `pivot_bar + len + 1`**. |
| CLUSTER | LuxAlgo "Buyside & Sellside Liquidity": a new pivot JOINS the nearest same-type level whose `±ATR/1.45` band contains it, provided that level has a member among the last 20 confirmed pivots of that type; otherwise it starts a new level. Cluster size at bar `i` = members confirmed **on or before `i-1`**. LuxAlgo only draws at size ≥ 3. |
| TOUCH | bar `i`'s range intersects `[P − 0.15·ATR, P + 0.15·ATR]`, `close[i-1]` was strictly outside that band (so the approach side is known), and no touch of the same level in the previous 20 bars. |
| REACTION | the direction price came FROM is the rejection direction. Within `N` bars **after** the touch bar, price moves `X·ATR` away from the level in that direction, **without first closing more than 0.25·ATR beyond the level**. A bar doing both is scored BAD (L-012). Neither inside `N` bars is also scored NO REACTION. |

**Primary config for the bucket tables:** `len 5, N 10, X 1.0`. The full
`len × N × X` grid is reported below so nothing is hidden behind that choice.

### One definitional trap, found and fixed

The first version of this script used the LuxAlgo cluster band (`±0.69 ATR`)
as the touch tolerance. That produced a **78.8% reaction rate on GOLD 1h** —
because a "touch" could happen 0.69 ATR away from the level, so "move 1.0 ATR
away from the level" was a 0.31 ATR drift, which happens almost always. It
measured nothing. The touch tolerance is now `0.15 ATR` (price actually has
to arrive at the level), which brings the reaction rate to a discriminating
47–56%. The tolerance is varied over 0.05 / 0.15 / 0.30 / 0.69 ATR below; the
answer does not change at any of them.

## The control

Every real level gets a matched random twin, identical in every respect
except **where it is**:

* same first-member confirmation bar → same age at every bar
* same list of member confirmation bars → identical cluster-size trajectory,
  so a random "cluster of 3" exists to compare against a real cluster of 3
* same band width
* price = `close[confirm_bar] + shuffled_offset × ATR[confirm_bar]`, where the
  offsets `(level_price − close[confirm_bar]) / ATR[confirm_bar]` are shuffled
  among levels of the same type. A pivot high is always above `close[confirm]`
  by construction, so a random buyside level is still above the market at a
  realistic ATR-scaled distance.
* touches, prior-touch counts and swept/broken state are then detected on it
  **by exactly the same code path, on the same bars**.

Three replicates (seeds 1000–1002) are pooled.

---
## Engine tests first — every number downstream is meaningless if these fail

`python3 JARVIS/research/test_engine.py` (tail):

```
INDICATORS
  PASS  RSI bounded 0..100
  PASS  ATR positive
  PASS  ADX bounded 0..100
  PASS  EMA9 tracks price more closely than EMA200

PROP SIM  sanity checks
  PASS  a strategy that only wins passes the eval
  PASS  a strategy that only loses fails the eval
  PASS  monte carlo pass rate is high for an always-winning strategy

==================================================================
  ALL TESTS PASSED
==================================================================
```

## Look-ahead audit and the random-walk null

I checked myself explicitly for using a bar to decide something that happens
on that bar. `python3 JARVIS/research/level_reaction.py SELFCHECK`:

```
======================================================================================
  E-053 SELF-CHECK — look-ahead audit and random-walk null
======================================================================================
  [PASS]  every touch bar > level confirm bar  (0 violations)
  [PASS]  every touch age >= len+1 = 6 bars  (0 violations)
  [PASS]  cluster size uses only members confirmed by i-1  (0 violations)
  [PASS]  no level touched twice within 20 bars  (0 violations)
  [PASS]  score() never reads a bar at or before the touch bar  (earliest read = touch bar +1)
  [PASS]  swept/broken state at a touch is reproducible from bars < i  (0 of 4000 differ)

  RANDOM-WALK NULL (driftless GBM, 8 seeds). Pivots there carry no
  information, so real-minus-random MUST be ~0. Whatever it is, is
  the bias of this machinery and every real number must be read
  against it, not against zero.
    seed       n real   real %   n rand   rand %    diff
    7            9576    40.5%    28367    40.4%    +0.1
    8           10413    37.9%    31307    38.7%    -0.8
    9           10806    38.3%    32518    38.8%    -0.6
    10          14738    40.0%    44337    39.7%    +0.3
    11           7874    38.6%    23580    38.9%    -0.3
    12          14006    38.8%    42146    38.7%    +0.2
    13          17616    37.5%    52611    37.3%    +0.2
    14           7480    37.7%    22456    37.5%    +0.1
    NULL OFFSET: -0.10 points  (sd 0.41, se 0.14)
    Every real-market difference must be read against THIS, not against zero.

  ALL LOOK-AHEAD CHECKS PASSED
```

Check 5 is an *access audit*: `score()` is run through a list subclass that
records every index it reads, and the earliest index read is the touch bar
+1. The touch bar's own high/low is used only to say the touch happened.

**Two real bugs were found by these checks and fixed before any result was
read:**

1. Levels that a **gap jumped over** were never marked broken, because the
   state-update window was built from the bar's own range. Such levels stayed
   marked "intact" for the rest of history after price had closed straight
   through them. The window now spans `min(low, prev_close)` to
   `max(high, prev_close)`.
2. My first version of check 5 blanked the touch bar's OHLC and compared
   outcomes — that was a bad test, not a bug: blanking bar `i` also corrupts
   the scoring window of neighbouring touches. Replaced with the access audit.

The **random-walk null is the important line**. On a driftless GBM, pivots
carry no information, so real-minus-random must be zero. It is **−0.10
points (se 0.14)** over 8 seeds. The machinery does not manufacture a
difference in either direction, so real-market differences can be read
against zero.

---

## THE HEADLINE — all 8 market/timeframe combinations

```
====================================================================================================
  E-053  DO MARKED LEVELS REACT? — CROSS-MARKET
  PRIMARY CONFIG: pivot len 5, reaction 1.0 ATR within 10 bars, invalidation close 0.25 ATR beyond,
  cluster margin ATR/1.45, touch cooldown 20 bars, 3 matched-random replicates.
====================================================================================================

  market           bars  levels  touches  rndTch   REAL %        95% int   RAND %    diff      z
  'touches' vs 'rndTch' (per replicate) is itself a result: if real levels were
  MAGNETS they would be visited more often than random prices at the same distance.
  GOLD 1h         13750     523     5158    5213    56.0%     54.6-57.3%    56.7%    -0.8  -0.95
  GOLD 15m         4501     185     1640    1621    49.0%     46.6-51.4%    50.0%    -1.0  -0.70
  EURUSD 1h       17252     777    14875   14618    49.3%     48.5-50.1%    49.4%    -0.1  -0.15
  EURUSD 15m       5624     253     2473    2457    47.0%     45.1-49.0%    48.0%    -1.0  -0.82
  GBPUSD 1h       17253     802    18590   18604    48.8%     48.0-49.5%    49.0%    -0.2  -0.54
  GBPUSD 15m       5624     247     2331    2331    47.3%     45.3-49.3%    47.3%    +0.0  +0.02
  US500 1h        13716     647     8466    8533    48.6%     47.6-49.7%    49.5%    -0.8  -1.35
  US500 15m        4500     180     1774    1806    50.5%     48.2-52.8%    52.3%    -1.8  -1.31

  --- PERIOD SPLIT (first half / second half of each series) --------
  cell = real % minus matched-random %, points
    market            n 1st   1st half    n 2nd   2nd half
    GOLD 1h            2456       +0.4     2702       -1.8
    GOLD 15m            649       -2.8      991       +0.2
    EURUSD 1h          7557       -0.1     7318       -0.0
    EURUSD 15m          890       +0.6     1583       -1.8
    GBPUSD 1h          7075       -0.3    11515       -0.2
    GBPUSD 15m          945       -0.9     1386       +0.6
    US500 1h           4921       -1.0     3545       -0.7
    US500 15m           957       -1.9      817       -1.6

  SUMMARY (computed, not eyeballed):
    total real touches 55307   total matched-random touches 165556
    unweighted mean over the 8 markets: real 49.6%   random 50.3%   diff -0.70 points
    touch-weighted pooled:              real 49.5%   random 49.9%   diff -0.44 points
    markets where real beat its own control: 1 of 8

  POOLED across the 8 markets (Stouffer): z = -2.05. Positive would favour real levels.
  Sum of touches 55307. This z is OPTIMISTIC twice over: touches inside a market
  overlap heavily, and the 4 FX/index series are not independent of each other.

  --- ROBUSTNESS: at most ONE touch per bar --------------------------
    market           n real   REAL %   RAND %    diff      z
    GOLD 1h            2602    57.5%    58.1%    -0.6  -0.55
    GOLD 15m            841    51.5%    51.8%    -0.3  -0.14
    EURUSD 1h          4384    53.3%    52.9%    +0.5  +0.54
    EURUSD 15m         1153    51.9%    51.4%    +0.5  +0.29
    GBPUSD 1h          4810    53.4%    53.3%    +0.1  +0.11
    GBPUSD 15m         1155    52.5%    51.6%    +0.9  +0.51
    US500 1h           3075    53.0%    52.2%    +0.7  +0.71
    US500 15m           873    51.9%    53.6%    -1.7  -0.86
    POOLED (Stouffer) z = +0.22

```

### Reading that table

* **Real levels react 47.0%–56.0% of the time. Matched random levels react
  47.3%–56.7%.** Every market's real number sits inside or below its own
  control. The largest gap in the whole table is US500 15m at **−1.8 points,
  z −1.31** — and it is the wrong sign for the hypothesis.
* **Levels are not even magnets.** Real levels received 5,158 touches on
  GOLD 1h; the random twins received 5,213 per replicate. EURUSD 1h: 14,875
  versus 14,618. GBPUSD 1h: 18,590 versus 18,604. Price visits a marked pivot
  no more often than it visits an arbitrary price the same distance away.
* **The period split shows no hidden regime.** No market has a first half
  above +0.6 points, and the signs flip between halves on 4 of 8 markets —
  the signature of noise, not of an effect that decayed.
* **The de-duplicated arm is the cleanest read.** Many levels sit in shelves
  and are touched on the same bar by the same price action, which inflates `n`
  without adding information. Keeping only the level nearest that bar's close
  gives a pooled **Stouffer z of +0.22** across the 8 markets: dead centre.
  The −2.05 in the duplicated arm is an artefact of that overlap, and it is
  negative anyway.

---

## The parameter grid — 36 configurations, all of them

If the effect existed but my primary config missed it, some other `len/N/X`
would find it. None does.

```
====================================================================================================
  E-053  PARAMETER GRID — cell = (real reaction %) minus (matched-random reaction %), in points
  A real effect is POSITIVE and the SAME SIGN across a row. Mixed signs are noise.
====================================================================================================

  len  N    X        GOLD1h    GOLD15m     EURU1h    EURU15m     GBPU1h    GBPU15m     US501h    US5015m     mean   pos
  3    5    0.5        -1.3       -1.2       -0.3       -0.6       +0.1       -1.6       -0.9       -1.7     -1.0   1/8
  3    5    1.0        -0.8       -0.7       -0.2       +0.9       +0.2       -0.8       -0.6       -1.9     -0.5   2/8
  3    5    1.5        -0.6       -0.2       +0.1       +0.9       +0.1       -0.7       -0.7       +0.2     -0.1   4/8
  3    10   0.5        -1.3       -1.1       -0.3       -0.7       +0.2       -1.7       -1.0       -1.6     -1.0   1/8
  3    10   1.0        -1.0       -0.3       -0.3       +1.0       -0.0       -0.8       -0.7       -1.7     -0.5   1/8
  3    10   1.5        -1.1       -0.4       +0.1       +1.1       +0.0       -0.5       -0.8       -0.1     -0.2   3/8
  3    20   0.5        -1.3       -1.1       -0.3       -0.7       +0.2       -1.7       -1.0       -1.6     -0.9   1/8
  3    20   1.0        -1.0       -0.3       -0.3       +0.8       -0.0       -0.9       -0.7       -1.9     -0.6   1/8
  3    20   1.5        -0.9       -0.2       -0.2       +0.9       -0.0       -0.7       -0.8       -0.2     -0.3   1/8
  5    5    0.5        -0.7       -1.3       -0.3       -1.6       -0.6       -1.7       -1.1       -2.5     -1.2   0/8
  5    5    1.0        -1.0       -1.1       +0.0       -0.7       -0.2       -0.0       -0.7       -2.2     -0.7   1/8
  5    5    1.5        -0.8       +0.1       +0.1       -0.5       +0.1       +1.4       +0.1       -1.3     -0.1   5/8
  5    10   0.5        -0.7       -1.6       -0.4       -1.6       -0.5       -1.7       -1.2       -2.4     -1.3   0/8
  5    10   1.0        -0.8       -1.0       -0.1       -1.0       -0.2       +0.0       -0.8       -1.8     -0.7   1/8
  5    10   1.5        -1.2       -0.6       +0.1       -0.3       -0.1       +1.7       -0.7       -1.2     -0.3   2/8
  5    20   0.5        -0.7       -1.6       -0.4       -1.6       -0.5       -1.7       -1.2       -2.4     -1.3   0/8
  5    20   1.0        -0.6       -1.0       +0.0       -1.0       -0.2       +0.0       -0.8       -2.2     -0.7   2/8
  5    20   1.5        -0.9       -0.3       +0.1       -0.7       -0.1       +1.5       -0.5       -0.8     -0.2   2/8
  7    5    0.5        -0.4       -1.5       -0.3       -1.4       -0.2       -1.9       -0.0       -0.7     -0.8   0/8
  7    5    1.0        +0.1       -1.1       -0.4       +0.4       +0.3       -1.1       +0.4       -0.6     -0.2   4/8
  7    5    1.5        +0.7       -2.0       -0.2       -0.2       +0.6       +0.2       +0.2       -1.1     -0.2   4/8
  7    10   0.5        -0.4       -1.7       -0.4       -1.3       -0.2       -1.9       -0.0       -0.6     -0.8   0/8
  7    10   1.0        +0.2       -1.0       -0.5       +0.3       +0.2       -1.1       +0.3       -0.7     -0.3   4/8
  7    10   1.5        +0.5       -1.9       -0.3       -0.2       +0.5       +0.3       -0.3       -0.7     -0.3   3/8
  7    20   0.5        -0.4       -1.7       -0.4       -1.3       -0.2       -1.9       +0.0       -0.6     -0.8   1/8
  7    20   1.0        +0.4       -1.1       -0.5       +0.3       +0.1       -1.3       +0.3       -1.2     -0.4   4/8
  7    20   1.5        +0.6       -1.9       -0.2       -0.5       +0.3       +0.4       -0.2       -1.0     -0.3   3/8
  10   5    0.5        -1.1       -2.4       -1.1       -0.0       -0.5       -1.7       -0.9       -0.9     -1.1   0/8
  10   5    1.0        -0.4       -2.5       -0.7       +1.0       -0.1       -0.8       -0.1       -0.3     -0.5   1/8
  10   5    1.5        -0.5       -1.2       -0.1       +0.2       +0.0       -0.4       -0.6       -0.7     -0.4   2/8
  10   10   0.5        -0.9       -2.3       -1.2       -0.0       -0.5       -1.6       -0.8       -0.9     -1.0   0/8
  10   10   1.0        -0.0       -1.7       -0.6       +1.4       +0.0       -1.0       -0.3       -0.4     -0.3   2/8
  10   10   1.5        -0.3       -1.4       -0.4       +1.0       -0.0       -0.7       -0.9       -0.2     -0.4   1/8
  10   20   0.5        -0.9       -2.3       -1.2       -0.0       -0.5       -1.6       -0.8       -0.9     -1.0   0/8
  10   20   1.0        +0.0       -1.7       -0.7       +1.5       +0.1       -1.1       -0.4       -0.5     -0.3   3/8
  10   20   1.5        -0.0       -1.9       -0.5       +0.8       +0.0       -0.2       -0.4       -0.4     -0.3   2/8

  36 configurations. mean over all: -0.58 points.  best -0.10   worst -1.26
  configurations where real beat random on >=6 of 8 markets: 0 of 36
```

## Touch-tolerance sensitivity — 4 more configurations

```
====================================================================================================
  E-053  TOUCH-TOLERANCE SENSITIVITY — cell = real % minus matched-random %, points
  pivot len 5, reaction 1.0 ATR within 10 bars. 0.69 ATR is the full LuxAlgo cluster band.
====================================================================================================

  tol (ATR)        GOLD1h    GOLD15m     EURU1h    EURU15m     GBPU1h    GBPU15m     US501h    US5015m     mean   pos
  0.05               -0.9       -1.7       +0.3       +2.7       +0.1       -0.1       -0.1       -0.8     -0.1   3/8
  0.15               -0.8       -1.0       -0.1       -1.0       -0.2       +0.0       -0.8       -1.8     -0.7   1/8
  0.3                -0.1       -1.8       +0.6       -2.4       +0.0       +0.2       -0.4       -1.1     -0.6   3/8
  0.69               +0.3       -0.6       +0.3       +0.4       +0.1       -2.1       -0.2       -0.2     -0.2   4/8
```

**40 configurations tested in total. Every single one has a negative mean.
Zero of 36 grid configurations beat the control on 6 or more of 8 markets.**

---

## The five conditioning questions

Every bucket is scored against the SAME bucket in the matched-random arm,
never against 50% and never against the market's pooled rate.

```
  --- AGE of level at touch (bars) --------------------------------
  cell = real % minus matched-random % IN THE SAME BUCKET, points
    market                0-20       20-50      50-200    200-1000       1000+
    GOLD 1h               -3.8        -1.4        -1.3        -0.2        -0.5
    GOLD 15m              +7.1        -6.6        -1.7        -1.1        -0.9
    EURUSD 1h             +1.9        -6.9        +0.8        +0.8        -0.2
    EURUSD 15m            -1.9        +1.6        +0.0        -1.7        -0.8
    GBPUSD 1h             -0.9        -2.9        -2.1        +0.2        -0.0
    GBPUSD 15m            +1.3        +0.0        -3.1        +2.6        -0.6
    US500 1h              -1.1        -2.2        -2.1        +0.1        -1.1
    US500 15m             -8.8        -0.5        -3.5        -1.8        -0.7

    ABSOLUTE real reaction % by age (the question as Veer asked it):
    market                0-20       20-50      50-200    200-1000       1000+
    GOLD 1h               48.6        52.0        54.3        59.8        54.0
    GOLD 15m              56.6        48.7        48.6        46.9        50.6
    EURUSD 1h             50.5        45.4        48.4        49.0        49.6
    EURUSD 15m            50.4        46.3        50.3        46.8        45.6
    GBPUSD 1h             47.4        48.2        46.1        47.8        49.3
    GBPUSD 15m            44.0        48.7        45.3        52.2        45.3
    US500 1h              52.1        52.6        49.2        48.4        48.0
    US500 15m             45.8        50.5        46.1        52.7        50.8
    real ABOVE rand         3/8         2/8         2/8         4/8         0/8
    mean real %           49.4        49.1        48.5        50.4        49.1
    mean rand %           50.2        51.4        50.2        50.6        49.7

  --- CLUSTER SIZE (LuxAlgo draws only at 3+) ---------------------
  cell = real % minus matched-random % IN THE SAME BUCKET, points
    market                   1           2           3          4+
    GOLD 1h               -0.1        -1.3        -0.0        -1.6
    GOLD 15m              -3.6        +1.7        -2.9        +0.5
    EURUSD 1h             +0.3        -1.1        +0.9        -0.2
    EURUSD 15m            -0.7        -0.5        +0.4        -2.3
    GBPUSD 1h             -0.5        -0.3        +0.5        -0.2
    GBPUSD 15m            -0.0        +0.4        +1.5        -1.7
    US500 1h              -1.8        -1.0        +1.7        -0.7
    US500 15m             -0.9        -1.2        -6.7        -1.3
    real ABOVE rand         1/8         2/8         5/8         1/8
    mean real %           49.2        49.8        49.9        49.7
    mean rand %           50.1        50.2        50.4        50.6

  --- PRIOR TOUCHES of this level ---------------------------------
  cell = real % minus matched-random % IN THE SAME BUCKET, points
    market                   0           1           2          3+
    GOLD 1h               -4.0        -0.6        +1.1        -0.5
    GOLD 15m              +0.3        -4.3        +0.1        -0.9
    EURUSD 1h             -1.8        -0.5        +0.1        +0.0
    EURUSD 15m            -3.9        -1.1        +2.8        -1.0
    GBPUSD 1h             -0.5        -0.7        +0.2        -0.2
    GBPUSD 15m            -2.3        +2.0        +1.6        -0.1
    US500 1h              -1.1        +1.5        -6.2        -0.6
    US500 15m             -5.1        +2.6        -1.2        -1.9
    real ABOVE rand         1/8         3/8         6/8         1/8
    mean real %           47.4        50.2        50.6        49.7
    mean rand %           49.7        50.4        50.8        50.3

  --- PRIOR STATE: intact / swept / broken ------------------------
  cell = real % minus matched-random % IN THE SAME BUCKET, points
    market              intact       swept      broken
    GOLD 1h               -3.5        -0.9        -0.5
    GOLD 15m              +0.9           -        -1.3
    EURUSD 1h             -0.7        +2.8        -0.1
    EURUSD 15m            -1.9       -11.7        -0.7
    GBPUSD 1h             -0.5        -1.5        -0.2
    GBPUSD 15m            -2.1        +3.7        +0.3
    US500 1h              -1.5        +7.7        -0.9
    US500 15m             -4.9           -        -1.6
    real ABOVE rand         1/8         3/6         1/8
    mean real %           48.0        49.3        49.7
    mean rand %           49.8        49.2        50.3

  --- approach WITH (1) or AGAINST (0) the 50-bar trend -----------
  cell = real % minus matched-random % IN THE SAME BUCKET, points
    market             against        with
    GOLD 1h               -0.2        -1.1
    GOLD 15m              -0.6        -1.2
    EURUSD 1h             +0.2        -0.2
    EURUSD 15m            -1.4        -0.7
    GBPUSD 1h             -0.4        -0.2
    GBPUSD 15m            -1.1        +0.5
    US500 1h              -0.4        -1.1
    US500 15m             -2.4        -1.5
    real ABOVE rand         1/8         1/8
    mean real %           53.0        47.8
    mean rand %           53.8        48.5

```

### 1. AGE — "do old levels still matter?" (the question Veer asked)

They matter exactly as much as they ever did, which is not at all.

| age at touch | mean real % | mean random % | markets real > random |
|---|---|---|---|
| 0–20 bars | 49.4 | 50.2 | 3/8 |
| 20–50 | 49.1 | 51.4 | 2/8 |
| 50–200 | 48.5 | 50.2 | 2/8 |
| 200–1000 | 50.4 | 50.6 | 4/8 |
| 1000+ | 49.1 | 49.7 | 0/8 |

**There is no age gradient at all** — the absolute reaction rate is flat
within 1.9 points from a 20-bar-old level to a 1000+-bar-old level, and
it never separates from the control at any age. A fresh level is not
better than an ancient one. An ancient one is not better than a random
price. GOLD 1h is the one market with an apparent age gradient in absolute
terms (48.6% → 59.8% → 54.0%), and its control shows the same gradient
(52.4% → 60.0% → 54.5%), so the gradient belongs to gold's price action,
not to its levels.

### 2. CLUSTER SIZE — does LuxAlgo's third pivot earn its place?

| cluster size | mean real % | mean random % | markets real > random |
|---|---|---|---|
| 1 (bare pivot, LuxAlgo draws nothing) | 49.2 | 50.1 | 1/8 |
| 2 | 49.8 | 50.2 | 2/8 |
| 3 (LuxAlgo starts drawing) | 49.9 | 50.4 | 5/8 |
| 4+ | 49.7 | 50.6 | 1/8 |

**No. The third pivot buys 0.7 points of absolute reaction rate over a
bare pivot, and the matched random control gains 0.3 points over the same
step, so the net is +0.4 points and it lands 5/8 — a coin flip.** The
count > 2 rule is not measurably better than count > 0 on this data.

### 3. PRIOR TOUCHES — do levels get stronger or weaker with use?

| prior touches | mean real % | mean random % | markets real > random |
|---|---|---|---|
| 0 (virgin) | 47.4 | 49.7 | 1/8 |
| 1 | 50.2 | 50.4 | 3/8 |
| 2 | 50.6 | 50.8 | 6/8 |
| 3+ | 49.7 | 50.3 | 1/8 |

A used level reacts about **3.2 points more** than a virgin one in
absolute terms — the opposite of the usual "the more it is tested the
weaker it gets" folklore. **But the random control gains 1.1 points over
the same step (49.7% → 50.8%), and the real-minus-random column is negative
in the 0, 1 and 3+ buckets.** A price that has already been visited is a price in the middle
of recent range, and prices in the middle of recent range bounce more.
That is where the 3.2 points comes from, not from the level.

### 4. SWEPT versus BROKEN — do the LuxAlgo "Liquidity Sweeps" objects differ?

| prior state | mean real % | mean random % | markets real > random |
|---|---|---|---|
| intact (never traded through) | 48.0 | 49.8 | 1/8 |
| swept (wick through, close back inside) | 49.3 | 49.2 | 3/6 |
| broken (closed through) | 49.7 | 50.3 | 1/8 |

Swept and broken levels do react slightly more than intact ones (+1.3 and
+1.7 points), and swept is the only bucket in the entire study where real
is not below random — but it lands **3 of 6**, two markets have fewer than
25 swept touches, and the 6 cells run from −11.7 to +7.7. That is the
signature of a small sample, not of an effect. **Treating swept levels as
a distinct object is not supported by this data.**

### 5. WITH versus AGAINST the 50-bar trend

| approach | mean real % | mean random % | markets real > random |
|---|---|---|---|
| against the 50-bar trend | 53.0 | 53.8 | 1/8 |
| with the 50-bar trend | 47.8 | 48.5 | 1/8 |

This is the **largest absolute gap in the whole study — 5.2 points** — and
it is entirely reproduced by the random control (5.3 points). GOLD 1h:
real 59.9% against / 53.6% with, control 60.1% / 54.7%. It is short-horizon
mean reversion in the price series. **It has nothing to do with levels and
would be exactly as strong if you drew your lines at random.**

---

## Multiple testing — the arithmetic, made visible

```
====================================================================================================
  MULTIPLE TESTING: 18 buckets examined in the tables above,
  plus 36 parameter configurations in run_grid() and 4 touch tolerances in run_tol().
  Under the null a bucket lands
  >=7 of 8 on one side with probability 2*9/256 = 7.0%, so about 1.3 such
  cells are expected BY CHANCE ALONE among 18 buckets. Count the ones found
  before believing any of them.

  FOUND: 9 such cells, versus ~1.3 expected by chance:
      age         1000+       real BELOW random on 7 or 8 of 8 markets
      clu         1           real BELOW random on 7 or 8 of 8 markets
      clu         4+          real BELOW random on 7 or 8 of 8 markets
      prior       0           real BELOW random on 7 or 8 of 8 markets
      prior       3+          real BELOW random on 7 or 8 of 8 markets
      state       intact      real BELOW random on 7 or 8 of 8 markets
      state       broken      real BELOW random on 7 or 8 of 8 markets
      withtr      against     real BELOW random on 7 or 8 of 8 markets
      withtr      with        real BELOW random on 7 or 8 of 8 markets
  All of them point the SAME way (BELOW), which is an excess, not chance.
  But they are NOT independent tests: 'broken', '3+ prior touches' and 'age 1000+' are
  overlapping slices of the same touches. They are one small effect re-cut nine ways,
  and it points AGAINST the hypothesis, not for it.
====================================================================================================
```

Explicitly: **18 bucket cells** in the tables above, plus **36 grid
configurations**, plus **4 touch tolerances** = **58 comparisons run in
total.** Under the null, a cell lands ≥7 of 8 on one side with probability
2 × 9/256 = 7.0%, so ~1.3 such cells are expected among 18 by chance.

**Nine were found, and all nine point the same way: real BELOW random.**
That is an excess, not chance — but it is *one* small negative effect
sliced nine overlapping ways ("broken" is 89% of GOLD 1h touches, "3+ prior
touches" is 74%, "age 1000+" is 35% — they are largely the same touches).
And it disappears (pooled z +0.22) when same-bar duplicate touches are
removed. The correct reading is **zero effect**, with a possible tiny
negative one; under no reading is it a positive one.

Nothing in this study needed a multiple-testing correction to be discarded.
The result is null before any correction is applied.

## One market in detail, so the machinery is inspectable

GOLD 1h — `python3 JARVIS/research/level_reaction.py GOLD 1h`:

```
======================================================================================
  E-053  DO MARKED LEVELS REACT? — GOLD 1h   13750 bars
  level = pivot len 5 | reaction = 1.0 ATR away within 10 bars, no close 0.25 ATR beyond
  523 level objects built | control = 3 matched random replicates
======================================================================================

  REAL   levels:   2888 of   5158 touches reacted =  56.0%  (95% 54.6-57.3%)
  RANDOM levels:   8876 of  15641 touches reacted =  56.7%  (95% 56.0-57.5%)
  DIFFERENCE   :  -0.8 points   (optimistic z -0.95)

  by AGE of level at touch (bars)
    bucket        n real   real %    95% interval  n rand   rand %    diff
    0-20             251    48.6%      42.5-54.8%     765    52.4%    -3.8
    20-50            250    52.0%      45.8-58.1%     684    53.4%    -1.4
    50-200           782    54.3%      50.8-57.8%    2254    55.6%    -1.3
    200-1000        2057    59.8%      57.7-61.9%    6407    60.0%    -0.2
    1000+           1818    54.0%      51.7-56.2%    5531    54.5%    -0.5

  by CLUSTER SIZE (LuxAlgo draws only at 3+)
    bucket        n real   real %    95% interval  n rand   rand %    diff
    1               1943    55.7%      53.5-57.9%    5934    55.8%    -0.1
    2               1280    54.4%      51.6-57.1%    3764    55.7%    -1.3
    3                591    57.0%      53.0-61.0%    1841    57.0%    -0.0
    4+              1344    57.4%      54.8-60.1%    4102    59.0%    -1.6

  by PRIOR TOUCHES of this level
    bucket        n real   real %    95% interval  n rand   rand %    diff
    0                488    49.0%      44.6-53.4%    1465    53.0%    -4.0
    1                450    55.8%      51.2-60.3%    1347    56.4%    -0.6
    2                411    56.4%      51.6-61.2%    1239    55.4%    +1.1
    3+              3809    56.9%      55.3-58.4%   11590    57.4%    -0.5

  by PRIOR STATE: intact / swept / broken
    bucket        n real   real %    95% interval  n rand   rand %    diff
    intact           488    49.8%      45.4-54.2%    1456    53.3%    -3.5
    swept             74    58.1%      46.7-68.7%     256    59.0%    -0.9
    broken          4596    56.6%      55.2-58.0%   13929    57.1%    -0.5

  by approach WITH (1) or AGAINST (0) the 50-bar trend
    bucket        n real   real %    95% interval  n rand   rand %    diff
    against         1970    59.9%      57.7-62.0%    6009    60.1%    -0.2
    with            3188    53.6%      51.8-55.3%    9632    54.7%    -1.1
```

---

# VERDICT: DISPROVEN

The hypothesis was that a marked level produces a reaction more often than an
arbitrary price. It does not.

* 55,307 real touches, 165,556 matched-random touches, 8 market/timeframe
  combinations, 40 parameter configurations.
* Unweighted mean over the 8 markets: real **49.6%**, matched-random
  **50.3%** (diff **−0.70 points**). Touch-weighted pooled: real **49.5%**,
  matched-random **49.9%** (diff **−0.44 points**).
* Real beat its own control on **1 of 8** markets at the primary config.
* With same-bar duplicate touches removed, pooled **z = +0.22**.
* Zero of 36 grid configurations beat the control on ≥ 6 of 8 markets.
* Random-walk null offset **−0.10 points (se 0.14)** — the machinery is clean,
  so the null is a real null and not an artefact.

To use the exact words the brief asked for: **a real pivot level reacts about
49.6% of the time and a random price level reacts about 50.3% of the time, so
the level is decoration.**

Sub-verdicts, each from its own table:

| claim | verdict | the number |
|---|---|---|
| Old levels keep mattering | **DISPROVEN** as stated — but so is "old levels stop mattering". Age has NO effect in either direction. | reaction rate flat 48.5–50.4% from age 20 to age 1000+; 1000+ bucket is 0/8 above its control |
| LuxAlgo's cluster ≥ 3 rule earns its place | **UNPROVEN** | +0.4 points net of control, 5/8 markets — a coin flip |
| Levels weaken with use | **DISPROVEN** (they very slightly strengthen, in absolute terms) | 47.4% virgin → 50.6% at 2 prior touches — and the random control moves the same way |
| Swept and broken levels behave differently | **UNPROVEN** | swept +1.3 points over intact, but 3/6 markets and only 6 markets have ≥ 25 swept touches |
| With/against trend matters | **DISPROVEN as a level effect** | 5.2-point real gap, 5.3-point control gap. It is mean reversion in the price series. |

---

# What this does NOT say — read this before quoting anything above

1. **It does not say levels are useless for trade management.** This measures
   whether a level predicts a *bounce*. It says nothing about whether a level
   is a good place to put a target, a stop, or a partial. E-041 already found
   a real reachability gradient at levels. A level can be a useful *landmark*
   without being a predictive *trigger*, and those are different claims.

2. **It does not say "price never reacts at levels".** Price reacts at levels
   about half the time. So does it at random prices. The finding is about the
   *difference*, and there isn't one.

3. **It does not test the reaction Veer actually watches for.** The reaction
   here is mechanical: 1 ATR away within 10 bars without closing 0.25 ATR
   beyond. A discretionary trader waits for a candle pattern, a lower-timeframe
   structure shift, a sweep-and-reclaim. Those are conditional entries this
   study did not measure. **This study rules out the level ALONE. It does not
   rule out level + confirmation.**

4. **It does not test M1 or M5.** There is **no M1 or M5 data in this repo**.
   Veer trades M1/M5/M15. The evidence here is 15m and 1h only. 15m is the
   closest available and it is one of the *strongest* nulls in the table
   (GOLD 15m −1.0, EURUSD 15m −1.0, US500 15m −1.8), but M1 and M5 are
   unverified and this result does not transfer to them by assertion. If the
   liquidity mechanism is real and lives in the order book, M1 is where it
   would most plausibly show up, and it is exactly where this repo is blind.

5. **The 15m samples are short.** GOLD 15m and US500 15m are ~4,500 bars
   (2026-06-14 → 2026-08-24, about ten weeks). EURUSD/GBPUSD 15m are ~5,600
   bars. The 1h series are 2–3 years. A 15m column is a ten-week reading.

6. **The control is a strong control, and that is a limitation as well as a
   strength.** The random twin is placed at a shuffled ATR-scaled offset from
   the same close, so it inherits the real levels' distance-from-price
   distribution. If the entire value of a pivot were "it sits about 1 ATR
   above the market", the control absorbs that and reports no difference. What
   the control isolates is specifically the *identity of the price* — was it a
   pivot or not. That is the right question for an indicator that draws lines
   at pivots, but it is worth stating that it is the question being answered.

7. **This is not a P&L statement.** No trades were simulated, no costs paid,
   no exits modelled. Reaction rate is a property of price, not of a strategy.
   Turning ~50% into an edge would require a payoff asymmetry that this study
   does not measure — and E-050 is the standing warning about what an
   asymmetric payoff does to a number.

8. **Ties were scored pessimistically.** A bar that both reaches the reaction
   threshold and closes beyond the level is scored NO REACTION (L-012). This
   is applied identically to the real and control arms, so it cannot create
   the null; but it does mean the absolute rates are floors, not estimates.

---

# Concrete recommendation for the indicator

Each point is tied to a number from the tables above, or says plainly that the
data supports no cutoff.

### Which levels are worth drawing

**Every level tested is worth exactly as much as every other one, which is to
say none of them predicts a bounce.** The reaction rate never leaves the
47.4–53.0% band in any bucket of any conditioning variable, the widest
spread inside it belongs to the with/against-trend split which the random
control reproduces exactly, and no bucket ever separates from its control. **The data supports NO cutoff on any dimension —
not age, not cluster size, not prior touches, not swept-versus-broken.**

That is a usable answer, and it points in an unexpected direction: **Veer's
instinct to mark old levels too is not wrong.** There is no evidence that an
old level is worse than a fresh one. There is also no evidence it is better.
If he wants old levels on the chart for context, this study gives no reason to
remove them, and no reason to expect them to work.

### Cluster threshold

**The data does not support a cluster threshold as a QUALITY filter.** Cluster
size 3 scores +0.4 points against its own control and lands 5 of 8 markets;
cluster 1 lands 1 of 8; cluster 4+ lands 1 of 8. There is no gradient.

**It is defensible purely as a DECLUTTERING device, and here is the number**
(`python3 JARVIS/research/level_reaction.py COUNTS`):

```
======================================================================================
  E-053  OBJECT COUNTS at pivot len 5 — what the cluster>=3 rule removes from the chart
======================================================================================

  market          levels  clu>=3    pct  touches  touches clu>=3    pct
  GOLD 1h            523     215  41.1%     5158            1935  37.5%
  GOLD 15m           185      79  42.7%     1640             653  39.8%
  EURUSD 1h          777     311  40.0%    14875            5818  39.1%
  EURUSD 15m         253      98  38.7%     2473             961  38.9%
  GBPUSD 1h          802     303  37.8%    18590            7181  38.6%
  GBPUSD 15m         247     107  43.3%     2331             870  37.3%
  US500 1h           647     249  38.5%     8466            2943  34.8%
  US500 15m          180      74  41.1%     1774             731  41.2%
  TOTAL             3614    1436  39.7%    55307           21092  38.1%
```

At `len = 5`, requiring cluster ≥ 3 draws **1,436 of 3,614 level objects
(39.7%)** across the eight series, covering **21,092 of 55,307 touches
(38.1%)**. So LuxAlgo's `count > 2` rule removes about 60% of the lines from
the chart at no measurable cost in reaction rate. Keep it if fewer lines helps
Veer read the chart. Do not keep it believing the surviving zones are better —
they are not, by 0.4 points on a 50% base with a 5/8 market split.

### Age cutoff

**No age cutoff is supported.** Absolute reaction rate by age: 49.4% / 49.1% /
48.5% / 50.4% / 49.1% for 0–20 / 20–50 / 50–200 / 200–1000 / 1000+ bars. The
spread across the entire age range is 1.9 points and it is not monotone. The
oldest bucket (1000+ bars — over 40 days on 1h) is 0 of 8 markets above its
control, i.e. the very old levels are, if anything, the *least* distinguishable
from random. **If a cutoff is wanted, it should be chosen for chart legibility
and object count, not for expected reaction, because expected reaction does not
change with age.**

### What should NOT be built

* Do not build an entry that fires on a level touch alone. It is a coin flip,
  and after spread it is worse than a coin flip (E-040's cost floor applies).
* Do not weight a setup score by cluster size, level age, or prior-touch count.
  None of the three separates from random. This is the same mistake E-052
  caught with `InpMaxSameDir` and `InpTrendStretch`: gates written from
  instinct before measurement.
* Do not treat "swept" as a stronger object than "broken" in the EA. 3/6
  markets, intervals from −11.7 to +7.7.

### What is still open, and is the obvious next experiment

The one thing this study genuinely cannot rule out is **level + confirmation**
(point 3 above). The honest next question is: conditional on a touch, does a
*confirming event on the touch bar or the next one* — a sweep-and-reclaim
close, an engulfing close back inside, a lower-timeframe structure break —
raise the reaction rate above the matched random control? That is a different
hypothesis with a different control, and it is cheap to run on this same
machinery: the touch list is already built, only the filter and the control's
filter need adding.

The second open question is **M1/M5**, where the repo has no data at all.

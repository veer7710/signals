# 08 — Move size at the flip: can you tell a 0.1-point move from a 20-point move?

**Experiment number:** E-064 (E-060, E-061 and E-062 do **not exist** in
`JARVIS/state/EXPERIMENTS.md` — I was asked to read them and they are not
there. The file jumps E-059 -> E-063. Whatever E-060 contained was never
written down, so the worked example of a look-ahead bug I was pointed at
could not be read. I built my own look-ahead detector instead and planted a
bug in it to prove it fires; see below.)

**Script:** `JARVIS/research/movesize2.py`
(`movesize.py` already existed and was left untouched. It measures
*non-directional* travel at *every bar*, which is a different question.)

**Commands, exactly as run:**
```
python3 JARVIS/research/test_engine.py          # ALL TESTS PASSED, run first
python3 JARVIS/research/movesize2.py verify     # look-ahead check
python3 JARVIS/research/movesize2.py ALL        # everything below
python3 JARVIS/research/movesize2.py GOLD 1h    # one-market detail
```

---

## THE HYPOTHESIS, falsifiable, with its mechanism

> At the bar a SuperTrend(7,1.2)+DEMA flip fires, information available from
> bars already closed separates flips whose subsequent maximum favourable
> excursion is large (>= 4 ATR) from those whose MFE is tiny (< 0.5 ATR)
> **by more than the same information separates them at randomly chosen bars**.

Claimed mechanism: a flip on an expanding-range bar that closes at its extreme,
in a market that has been coiling (ATR7/ATR50 low, efficiency ratio low), and
that has just swept a swing point, is a flip where resting order flow has just
been released — and released imbalance travels further than noise.

The clause after "by more than" is the entire experiment. Volatility
clustering is already CONFIRMED in this project (E-038, E-019): *any* bar in
an expanding market is followed by a bigger move than any bar in a dead one.
A feature can therefore "predict move size at flips" while carrying zero
information about the flip. Per E-050, the only way to tell those apart is the
matched random arm, and this study runs every table twice.

---

## VERDICT

| claim | verdict |
|---|---|
| The 12 requested features separate large from tiny moves at a flip **better than at a random bar** | **REJECTED** |
| "Contracting volatility (ATR7/ATR50 < 0.8) predicts a large move at a flip" | **REJECTED as signal information** — the random arm reproduces it in 20 of 20 seeds, and it is additionally a normalisation artifact (below) |
| Move size at a flip is predictable *at all*, out of sample, by any combination of these features | **UNPROVEN**, mean OOS AUC 0.525 signal vs 0.520 random |
| Run age >= 100 bars precedes smaller moves (E-052's effect, re-measured on a new outcome) | **UNPROVEN** — 1/8 at N=50 but 3/8 at N=20, so it fails horizon robustness |
| Move size is *hugely* variable and worth predicting if you could | **CONFIRMED** — p90/p10 of MFE is 15x to 25x on GOLD |

**Plain answer to Veer's question: no. At the moment the flip fires, nothing
in this feature set tells a small move from a big one any better than the same
features would at a bar picked at random with a coin-flip direction.**

---

## 1. The single most useful finding, in the requested form

> **"If ATR(7)/ATR(50) < 0.8 at the flip, then P(MFE >= 4 ATR within 50 bars)
> is 51.4% against a base rate of 44.6%, in 8 of 8 markets."**

That sentence is true, it is the strongest cell in the study, it is the only
8-of-8 unanimous cell in the signal arm — and **it is worthless**, for two
independent reasons, each of which alone would kill it:

**(a) The random arm does it just as well.** At randomly chosen bars with a
coin-flip direction, the identical rule gives **50.5% against a base rate of
43.3%, also 8 of 8** — a +7.2 point lift against the signal arm's +6.8. Across
20 different random seeds the control landed 8/8 twelve times and 7/8 eight
times, mean effect **+8.4 points, range +6.1 to +10.1**. The signal arm's +7.2
sits *inside* that band, below its centre. The flip contributes nothing.

**(b) It is partly a measurement artifact of my own outcome variable.** MFE is
reported in units of ATR(14)-at-signal. `ATR7/ATR50 < 0.8` is low precisely
when short-horizon volatility — and therefore ATR(14) itself — is depressed
relative to the market's slower level. A forward move divided by a temporarily
small denominator looks large whether or not it is large. Re-normalising the
**identical** forward moves by ATR(50)-at-signal, which the feature does not
depress:

| normalisation | signal arm | random arm |
|---|---|---|
| MFE / ATR(14) | **+7.2 pts, 8/8 positive** | +8.3 pts, 8/8 |
| MFE / ATR(50) | **-0.9 pts, 2/8 positive** | +0.4 pts, 4/8 |

The effect does not shrink, it **inverts and disappears**. This is the same
class of error the brief warned me about: a beautiful unanimous result that is
an artifact of how I chose to measure. I found it by attacking my own headline,
not by finding more evidence for it.

**Consequence for an existing repo finding:** E-019 ("compressed volatility
precedes bigger moves", listed as the strongest finding in the project) used
the same ATR-normalised forward-travel outcome with `squeeze = ATR/median(ATR)`
as the predictor. That is structurally the same feature/denominator overlap.
E-019 has not been re-run here and I am not overturning it, but **it needs the
ATR(50)-denominator check before it is quoted again.**

## 2. The other cells that reached 7-of-8, and what the control did to them

| cell | signal arm | random arm | reading |
|---|---|---|---|
| atrratio 1.25-1.6 | 0/7 above base, -11.5 pts | 1/6, -9.7 | control matches it |
| hour 04-08 UTC | 6/6 above base, +10.2 pts | 6/8, +8.7 | control matches it |
| **atrratio 0-0.8** | **8/8, +7.2** | **8/8, +8.3** | control matches it |
| atrratio 1-1.25 | 0/7, -6.0 | 5/8, +0.0 | control does not — but see artifact (b) |
| **runbars 100+** | **1/8, -5.3** | 3/8, -0.5 | control does not — the one survivor |
| hour 08-12 UTC | 6/7, +5.2 | 5/6, +7.1 | control matches it |
| atrratio 0.8-1 | 7/8, +3.9 | 3/8, -2.5 | control does not — but see artifact (b) |

Only **run age >= 100 bars** survives both the control and the denominator
concern. It is the same direction as E-052 (which measured a completely
different outcome, P(+1R before -1R)) and pooled it is 39.7% vs a 44.6% base.
But it fails horizon robustness — 1/8 at N=50, 3/8 at N=20, 2/8 at N=120 — so
on this evidence alone it is **UNPROVEN**. Its only claim on belief is that it
agrees with an already-recorded finding measured a different way.

## 3. Multiple-testing arithmetic, stated explicitly

- **68 feature/bucket cells** were examined at the primary horizon (15 features,
  2-6 buckets each). **48** had >= 6 markets with a cell of at least 25 samples.
- Under the null that each market is an independent coin flip, P(a cell lands
  >= 7 of 8 on one side) = 2 x 9/256 = **7.0%**, and P(8 of 8) = 2/256 = **0.78%**.
- Among 48 testable cells the null therefore **expects about 3.4 cells at the
  7-of-8 level and 0.38 at 8-of-8**.
- **Observed: 7 in the signal arm. Observed: 8 in the random arm.** The signal
  arm did not even out-produce noise.
- The 8 markets are **not independent** — GOLD 15m overlaps GOLD 1h in time,
  and EURUSD/GBPUSD correlate about 0.9 (E-015). The true expected count is
  therefore **higher** than 3.4, not lower, which makes 7 look worse still.
- All three horizons (20, 50, 120) were computed. Quoting any horizon other
  than the pre-registered 50 multiplies the cell count by 3, to **204**.
- Counting the whole session honestly: 15 features x ~4.5 buckets x 3 horizons
  x 2 arms = **~408 cells rendered**, plus 4 auxiliary analyses.

## 4. The random control, which is the point of the study

Same features, same MFE, same fill rule, at bars chosen uniformly at random
with a coin-flip side, sample count matched market by market. Full tables in
the output below. Summary:

- The random arm produced **more** >=7-of-8 cells than the signal arm (8 vs 7).
- The signal arm's unanimous cell is reproduced by the random arm at 20/20 seeds.
- Out of sample, mean AUC: signal **0.525**, random **0.520** at N=50; signal
  **0.470**, random **0.510** at N=20. Both are 0.5 to within noise, and at the
  shorter horizon the fitted signal score is *worse than a coin flip*.
- ADX < 15 pooled: signal +5.4 pts, random **+11.2** pts. The control is
  stronger than the signal on the feature E-019 highlighted.

## 5. The one place the signal beats random — and why it is probably gold's trend

GOLD is the only instrument whose signal arm has a materially higher
unconditional P(large) than its own random arm (1h: 49.2% vs 36.5%; 15m: 52.2%
vs 39.9%). Every other market is a wash. Splitting by side:

| | signal | random | gap |
|---|---|---|---|
| GOLD 1h **long** (n=214) | 53.3% | 30.8% | **+22.5** |
| GOLD 1h **short** (n=156) | 43.6% | 41.4% | +2.2 |

The GOLD 1h gap is almost entirely **long-side**, over a 2024-04 to 2026-08
sample in which gold trended up hard. That is a directional trend showing
through, not evidence that a flip predicts move size. GOLD 15m is +7.6 long /
+16.8 short but rests on 138 signals over 70 days. **One instrument, mostly one
direction, one regime.** By the standing rule in this project that is
curve-fitting until shown otherwise.

## 6. Look-ahead: what I checked and how

`verify_no_lookahead()` rebuilds all 15 features from the **truncated** series
`s[0..i]` at 12 signal bars per market and asserts every value is identical to
the full-series computation. If any feature read bar i+1 or later, the
truncated rebuild could not match.

```
  LOOK-AHEAD CHECK  GOLD 1h: rebuilt all 15 features from truncated series at 12 signal bars.
  mismatches: 0   -> PASS

  LOOK-AHEAD CHECK  GOLD 15m: rebuilt all 15 features from truncated series at 12 signal bars.
  mismatches: 0   -> PASS
```

A check that cannot fail proves nothing, so I planted a violation — redefined
`barrange` to read bar i+1 — and re-ran the detector:

```
  LOOK-AHEAD at bar 309: barrange full=0.6716818410309334 truncated=1.3532762195993775
  LOOK-AHEAD at bar 3317: barrange full=1.0800250068709967 truncated=1.157169650218925
  LOOK-AHEAD at bar 7100: barrange full=1.397804292587926 truncated=0.9073224461714356
  LOOK-AHEAD at bar 10753: barrange full=1.0946941182312535 truncated=1.2973007591822285
  mismatches: 4   -> FAIL
  PLANTED-VIOLATION TEST: detector returned False -> expected False
```

Specifically checked by hand as well:
- **Swing pivots** are filled at index k+2, never at k, so a pivot is only
  visible once the two bars after it have closed.
- **MFE is the only forward-looking quantity in the file** and it is never an
  input to any feature; it lives in `mfe()`, which is the sole function that
  indexes beyond i.
- The **fill** is `open[i+1]` moved against us by half-spread + slippage, i.e.
  the engine's own rule — the measured move is one the trade could have had.
- `runbars`/`runmove` are derived from the gated signal stream up to i only.
- Rolling windows are all `[i-n .. i]` inclusive of i, exclusive of i+1.

## 7. The size of the prize, in Veer's own units

Veer says moves run "0.1 to 20-30 points". On this data, MFE at a flip:

| market | horizon | p10 | median | p90 | p90/p10 |
|---|---|---|---|---|---|
| GOLD 15m | 20 bars | 3.22 pts | 19.7 | 48.0 | **14.9x** |
| GOLD 15m | 50 bars | 4.92 pts | 34.9 | 78.7 | **16.0x** |
| GOLD 1h | 50 bars | 6.32 pts | 43.7 | 159 | **25.2x** |

So the phenomenon he describes is real and large — the spread between a dud
flip and a runner is 15x to 25x. **The prize is worth having. The measurement
says it is not collectable from these features.**

---

## WHAT THIS DOES *NOT* SAY

1. **It does not transfer to M1 or M5.** This repo contains **no M1 and no M5
   data** (D-009 records that this is the project's binding constraint). Veer
   trades M1/M5/M15; of those, only M15 exists here, and the 15m sample is
   70 days long with 138-267 signals. Every number above is 15m/1h. The bucket
   edges alone do not transfer: at his measured M1 ATR of ~0.5 (E-063), a
   "20-point move" is **40 ATR**, off the end of every table here, whereas on
   15m gold with ATR ~7.4 a 30-point move is ~4 ATR, i.e. the *middle* of the
   distribution. The regimes are not the same object.
2. **It does not say move size is unpredictable in general.** It says *these 12
   features, at these horizons, on these 8 series* do not beat a matched random
   control. Order-flow, depth, tick data, session-relative levels and news
   timing were not tested and cannot be tested with this data.
3. **It does not say volatility is unpredictable.** The opposite: the random
   arm predicts move size perfectly respectably (ADX<15 gives +11.2 points at
   random bars). Volatility clustering is real and already CONFIRMED as E-038.
   What is absent is anything *specific to the flip*.
4. **It does not say the SuperTrend entry is bad or good.** This study measures
   MFE, not P&L. MFE ignores the path — an entry with 6 ATR of MFE that first
   went 2 ATR against you is a loser under any real stop. E-050 already found
   the SuperTrend entry indistinguishable from random on expectancy; this is a
   separate measurement that happens to agree.
5. **It does not test exits or sizing.** "Hold the big ones, cut the small ones"
   was the motivation; nothing here shows how to do that, and E-056 (stall) is
   still the only measured, unanimous handle on that problem — but stall is a
   *post-entry* variable, available only after the trade is open. That is the
   distinction this study establishes: **at the flip there is no information;
   a few bars in, there is (E-056).**
6. **It does not survive being run again with different bucket edges.** Bucket
   edges were chosen once, before looking, but they were chosen by me. With 408
   cells rendered, the honest reading of any single cell is "expected under the
   null".
7. **`swept` is one definition of a sweep** (2-bar-each-side pivot taken out by
   the flip bar). It came out 5/8 and 2/6 — noise — but a different sweep
   definition is a different test, not a re-test.

---

## RAW OUTPUT — `python3 JARVIS/research/movesize2.py ALL`

```
================================================================================================
  E-064  CAN YOU TELL A 0.1-POINT MOVE FROM A 20-POINT MOVE AT THE FLIP?
  Outcome: MFE in ATR(14) units. LARGE = 4.0+ ATR, TINY = <0.5 ATR.
  Every cell = P(large) MINUS that market's own base rate, in percentage points.
  A feature that works has the SAME SIGN across a whole row. Mixed signs are noise.
================================================================================================

  SAMPLES AND BASE RATES
    market          signals  random   P(lg)@20   P(lg)@50  P(lg)@120    rnd@20    rnd@50   rnd@120
    GOLD 1h             370     370      25.4%      49.2%      66.8%     16.2%     36.5%     54.1%
    GOLD 15m            138     138      27.5%      52.2%      63.8%     17.4%     39.9%     57.2%
    EURUSD 1h           650     650      23.8%      46.3%      63.5%     22.8%     44.8%     64.3%
    EURUSD 15m          257     257      23.7%      40.9%      58.8%     24.1%     45.5%     66.5%
    GBPUSD 1h           645     645      22.3%      44.2%      62.5%     22.3%     43.7%     63.7%
    GBPUSD 15m          256     256      22.7%      44.9%      60.9%     26.6%     46.5%     68.8%
    US500 1h            460     460      22.4%      43.3%      62.0%     22.6%     44.8%     65.0%
    US500 15m           152     152      18.4%      30.3%      48.0%     18.4%     40.8%     63.2%


################################################################################################
#  ARM 1 — THE SIGNAL.  15 features at SuperTrend flips, horizon 50 bars
################################################################################################

  --- barrange: flip bar range / ATR (displacement)
    market                0-1      1-1.5    1.5-2.2    2.2-3.2       3.2+
    GOLD 1h              +2.1       +3.7       -3.9       -6.3          -
    GOLD 15m             -6.9       +9.8       -2.2          -          -
    EURUSD 1h            +2.2       -2.8       +3.4       -2.2       -7.8
    EURUSD 15m           -6.2       -1.3       +6.0          -          -
    GBPUSD 1h            -2.8       -0.1       +4.4       -7.5          -
    GBPUSD 15m           +8.1       -2.7       -4.6          -          -
    US500 1h             +1.6       -1.4       +3.9       -3.9       -7.3
    US500 15m            +8.2       -9.9      +10.5          -          -
    ABOVE base            5/8        2/8        5/8        0/4        0/2
    mean pts             +0.8       -0.6       +2.2       -5.0       -7.6

  --- closepos: close position in flip bar range (1 = closed at the extreme in trade direction)
    market             0-0.35   0.35-0.6   0.6-0.85      0.85+
    GOLD 1h                 -       +0.8       +4.1       -3.0
    GOLD 15m                -          -       -8.7       +2.6
    EURUSD 1h               -       +4.5       -0.5       -0.3
    EURUSD 15m              -          -       +8.2       -3.0
    GBPUSD 1h               -       -7.6       -2.9       +2.3
    GBPUSD 15m              -          -       +0.4       +0.6
    US500 1h                -      -11.3       +5.1       -0.2
    US500 15m               -          -       -1.7       +1.2
    ABOVE base              -        2/4        4/8        4/8
    mean pts                -       -3.4       +0.5       +0.0

  --- bodyfrac: body / range of the flip bar
    market              0-0.3    0.3-0.5    0.5-0.7       0.7+
    GOLD 1h              -0.8       +0.8       +7.1       -4.0
    GOLD 15m                -          -       -4.3       -1.3
    EURUSD 1h            +9.7       -3.3       +3.4       -2.1
    EURUSD 15m              -          -       -3.4       +2.1
    GBPUSD 1h            -9.3       +1.3       +4.2       -0.9
    GBPUSD 15m              -       +7.1       +0.3       -1.6
    US500 1h             +4.7      -11.2       +5.0       +0.3
    US500 15m               -       -7.2       -4.6       +2.2
    ABOVE base            2/4        3/6        5/8        3/8
    mean pts             +1.1       -2.1       +1.0       -0.7

  --- atrratio: ATR(7) / ATR(50)  (<1 = volatility contracting)
    market              0-0.8      0.8-1     1-1.25   1.25-1.6       1.6+
    GOLD 1h              +2.9       +7.9       -5.9      -11.0          -
    GOLD 15m             +7.1       +3.4      -10.1          -          -
    EURUSD 1h            +7.0       +5.0       -2.7      -16.7          -
    EURUSD 15m           +9.1       +3.0       -5.9       -9.8          -
    GBPUSD 1h            +5.8       +5.8       -4.1      -11.8          -
    GBPUSD 15m          +12.6       -1.8       -3.4      -16.7          -
    US500 1h             +8.5       +5.9       -9.9       -4.4          -
    US500 15m            +4.6       +2.4          -      -10.3          -
    ABOVE base            8/8        7/8        0/7        0/7          -
    mean pts             +7.2       +3.9       -6.0      -11.5          -

  --- er20: Kaufman efficiency ratio, 20 bars
    market              0-0.1    0.1-0.2   0.2-0.35  0.35-0.55      0.55+
    GOLD 1h              -0.0       +2.1       -1.9       -1.4          -
    GOLD 15m             -6.0       +8.9       -0.7          -          -
    EURUSD 1h            -4.3       +2.3       +5.8       -6.0          -
    EURUSD 15m           +2.9       -0.9       -0.9          -          -
    GBPUSD 1h            -6.8       +6.7       +1.9       +1.9          -
    GBPUSD 15m           +6.2       -7.1       +2.0       -2.1          -
    US500 1h             +6.3       -3.1       -1.1       -2.5          -
    US500 15m            +5.2       -4.7       -0.3          -          -
    ABOVE base            4/8        4/8        3/8        1/5          -
    mean pts             +0.4       +0.5       +0.6       -2.0          -

  --- er50: Kaufman efficiency ratio, 50 bars
    market             0-0.08  0.08-0.15  0.15-0.25   0.25-0.4       0.4+
    GOLD 1h              +3.5       -3.4       -5.6      +11.3          -
    GOLD 15m            -14.3       -2.2      +10.9          -          -
    EURUSD 1h            -3.9       +3.2       +1.9       -2.3          -
    EURUSD 15m           -1.7       +1.0       -1.5          -          -
    GBPUSD 1h            -0.5       +0.3       +3.9      -10.9          -
    GBPUSD 15m           -1.0       +0.4       +0.5          -          -
    US500 1h             +5.1       -1.9       -3.1       +2.4          -
    US500 15m            -5.9      +11.7       -2.4          -          -
    ABOVE base            2/8        5/8        4/8        2/4          -
    mean pts             -2.3       +1.2       +0.6       +0.1          -

  --- runbars: bars since the last opposite signal (run age, E-052)
    market                0-5       5-15      15-40     40-100       100+
    GOLD 1h             -11.1          -       +4.3      +13.0       -1.2
    GOLD 15m             +5.3          -          -       +1.7      -13.9
    EURUSD 1h           +11.0       -2.6       -1.5       -0.1       -8.6
    EURUSD 15m          -11.3          -      +15.0       +3.3       -2.3
    GBPUSD 1h            +1.5       -5.3      +10.4       -2.0       -5.4
    GBPUSD 15m           +5.1          -       +3.9       +6.9      -17.3
    US500 1h             +3.0          -       -5.6       +1.7       -1.1
    US500 15m            +4.0          -       -6.9       -8.0       +7.5
    ABOVE base            6/8        0/2        4/7        5/8        1/8
    mean pts             +0.9       -3.9       +2.8       +2.1       -5.3

  --- runmove: distance travelled in this run, ATR (E-052)
    market                0-1        1-2        2-4        4-8         8+
    GOLD 1h              -9.3       +0.8      +11.3      +10.8       +1.3
    GOLD 15m             +7.8          -       -0.6          -       -9.3
    EURUSD 1h            +7.1       +0.2       -3.1       -4.9       -4.3
    EURUSD 15m           -0.2       +3.1       -3.6       -3.6       +6.0
    GBPUSD 1h            +2.1       +5.1       -3.1       +1.6       -4.9
    GBPUSD 15m           +3.3       -2.6       +7.9       -0.7       -7.6
    US500 1h             +3.2       -2.8       -4.6       -0.8       +0.5
    US500 15m            +2.5          -          -      -18.3      +18.2
    ABOVE base            6/8        4/6        2/7        2/7        4/8
    mean pts             +2.1       +0.7       +0.6       -2.3       -0.0

  --- stretch: signed distance from DEMA200 in ATR (+ = already extended the trade's way)
    market                <-1       -1-0        0-1      1-2.5       2.5+
    GOLD 1h              +6.8          -       -9.5       -1.2       +2.2
    GOLD 15m                -          -          -      +10.3       -5.4
    EURUSD 1h           -18.7      +13.0       -4.1       -0.2       +0.7
    EURUSD 15m              -          -       +2.5       +3.7       +2.7
    GBPUSD 1h            +5.8       +1.3      -13.3       +1.2       +2.0
    GBPUSD 15m              -      -14.2       +1.0       +7.1       +3.5
    US500 1h             -6.1       +2.9       +4.8       -1.1       -0.7
    US500 15m               -          -          -       +1.3       -1.3
    ABOVE base            2/4        3/4        3/6        5/8        5/8
    mean pts             -3.1       +0.7       -3.1       +2.7       +0.5

  --- pos100: position in the last 100 bars' range, trade-direction adjusted
    market             0-0.25   0.25-0.5   0.5-0.75   0.75-0.9       0.9+
    GOLD 1h                 -       -3.0       +3.1       -1.3       -3.6
    GOLD 15m                -          -       -2.2       -9.6          -
    EURUSD 1h               -       -7.5       -2.6       +2.3       +3.7
    EURUSD 15m              -          -       -4.0       -4.9       +9.1
    GBPUSD 1h               -       +1.0       -1.3       +0.8       +1.3
    GBPUSD 15m              -          -       -1.2       +4.0       -1.3
    US500 1h                -       -1.9       +5.4       -2.9       -2.6
    US500 15m               -          -       +9.0       -4.4       -5.3
    ABOVE base              -        1/4        3/8        3/8        3/7
    mean pts                -       -2.9       +0.8       -2.0       +0.2

  --- adx: ADX at the flip
    market               0-15      15-20      20-25      25-35        35+
    GOLD 1h             +16.5       +5.6       -1.9      -13.2          -
    GOLD 15m                -       -7.0       -5.5      +11.0          -
    EURUSD 1h            +5.4       +1.0       -1.9       -4.2          -
    EURUSD 15m           -8.0       +6.5       +0.7       +0.4          -
    GBPUSD 1h            +4.7       +1.2       -0.8       -5.1          -
    GBPUSD 15m          +16.6       -1.0      -15.5       -3.5          -
    US500 1h             +7.5       -0.9       +1.3       -3.5          -
    US500 15m            -5.3       +8.4       +5.0       -9.2          -
    ABOVE base            5/7        5/8        3/8        2/8          -
    mean pts             +5.3       +1.7       -2.3       -3.4          -

  --- adxslope: ADX minus ADX 3 bars ago (falling / flat / rising)
    market                <-1       -1-1         1+
    GOLD 1h              +1.1       +0.4       -4.2
    GOLD 15m             -5.5      +13.7          -
    EURUSD 1h            -0.0       -0.9       +2.0
    EURUSD 15m           +1.8       -1.8       -1.8
    GBPUSD 1h            -3.5       +6.7       -2.6
    GBPUSD 15m           -4.1       +5.6       -0.2
    US500 1h             +0.5       +0.8       -3.0
    US500 15m            -4.0       +1.0       +6.8
    ABOVE base            3/8        6/8        2/7
    mean pts             -1.7       +3.2       -0.4

  --- swept: flip bar took out the previous swing point (0 = no, 1 = sweep)
    market                0-1         1+
    GOLD 1h              +0.7       -9.2
    GOLD 15m             +0.2          -
    EURUSD 1h            +0.4       -2.9
    EURUSD 15m           -0.9       +6.0
    GBPUSD 1h            +0.2       -1.5
    GBPUSD 15m           +1.5       -9.6
    US500 1h             -1.1       +6.0
    US500 15m            -0.3          -
    ABOVE base            5/8        2/6
    mean pts             +0.1       -1.9

  --- hour: hour of day, UTC
    market                0-4        4-8       8-12      12-16      16-20        20+
    GOLD 1h              +2.7       +2.5       +0.8       -4.7       -6.3      +11.4
    GOLD 15m            -11.4          -          -       +2.7          -          -
    EURUSD 1h            +0.2       +2.6       +5.2       -2.0       -7.0       -1.9
    EURUSD 15m           +6.2      +28.2       +1.0      -22.1      -17.8      -11.4
    GBPUSD 1h            -1.3      +11.0       +2.4       -4.4       -5.2          -
    GBPUSD 15m           +7.9      +13.8       -3.5      -13.8          -       -7.4
    US500 1h             +5.4       +3.3      +10.9       +1.3       -9.9      -14.0
    US500 15m           -13.6          -      +19.7       -0.3          -          -
    ABOVE base            5/8        6/6        6/7        2/8        0/5        1/5
    mean pts             -0.5      +10.2       +5.2       -5.4       -9.2       -4.7

  --- nflip20: SuperTrend flips in the last 20 bars (whipsaw density)
    market                0-2        2-3        3-5         5+
    GOLD 1h              -2.1       -0.1       +1.4          -
    GOLD 15m                -       -3.0       +7.1          -
    EURUSD 1h            -0.7       +1.1       -0.4       -5.1
    EURUSD 15m              -       -6.6       +1.7       -1.4
    GBPUSD 1h            +1.6       -1.5       +0.3          -
    GBPUSD 15m              -       +0.1       -1.2       +1.7
    US500 1h             +6.7       -2.7       +2.8          -
    US500 15m               -       +3.1       -3.9          -
    ABOVE base            2/4        3/8        5/8        1/3
    mean pts             +1.4       -1.2       +1.0       -1.6


################################################################################################
#  ARM 2 — THE RANDOM CONTROL.  identical tables at RANDOM bars, RANDOM side, matched n
#  Anything the control also achieves is volatility clustering (E-038), not signal quality.
################################################################################################

  --- barrange: flip bar range / ATR (displacement)
    market                0-1      1-1.5    1.5-2.2    2.2-3.2       3.2+
    GOLD 1h              +0.7       -1.2       -9.7          -          -
    GOLD 15m             +2.3       -0.3          -          -          -
    EURUSD 1h            -0.1       +0.3       +0.5          -          -
    EURUSD 15m           -6.9      +14.2      +14.5          -          -
    GBPUSD 1h            -2.4       +7.8       -4.8          -          -
    GBPUSD 15m           -3.4       +7.2       +5.2          -          -
    US500 1h             +2.2       -1.9       -8.4          -          -
    US500 15m            -3.3       -2.1          -          -          -
    ABOVE base            3/8        4/8        3/6          -          -
    mean pts             -1.4       +3.0       -0.4          -          -

  --- closepos: close position in flip bar range (1 = closed at the extreme in trade direction)
    market             0-0.35   0.35-0.6   0.6-0.85      0.85+
    GOLD 1h              +3.1       -3.2       -0.0       -3.7
    GOLD 15m             -0.3       +3.0       +4.3       -7.7
    EURUSD 1h            +2.6       -2.8       -3.5       +0.3
    EURUSD 15m           +4.0       -2.4       +4.5       -5.8
    GBPUSD 1h            -2.6       +3.4       -0.5       +2.2
    GBPUSD 15m           -0.3       +0.7       +2.4       -1.4
    US500 1h             -3.4       +1.4       +3.2       +2.7
    US500 15m            +5.8       -8.8       +0.2       -4.1
    ABOVE base            4/8        4/8        5/8        3/8
    mean pts             +1.1       -1.1       +1.3       -2.2

  --- bodyfrac: body / range of the flip bar
    market              0-0.3    0.3-0.5    0.5-0.7       0.7+
    GOLD 1h              -2.9       -8.5      +13.5       +4.1
    GOLD 15m             -3.7      +16.8       +8.5      -19.9
    EURUSD 1h            -1.8       +3.5       -8.9       +6.9
    EURUSD 15m          +10.4       +7.0       -4.6       -8.2
    GBPUSD 1h            -3.2       -5.2       +4.1       +4.1
    GBPUSD 15m           +0.4       +5.9       +7.2       -6.9
    US500 1h             -2.9       -4.8      +10.9       -3.5
    US500 15m            -1.6      +17.8       -4.4       -7.5
    ABOVE base            2/8        5/8        5/8        3/8
    mean pts             -0.7       +4.1       +3.3       -3.9

  --- atrratio: ATR(7) / ATR(50)  (<1 = volatility contracting)
    market              0-0.8      0.8-1     1-1.25   1.25-1.6       1.6+
    GOLD 1h             +10.6       -2.4       +1.7      -10.4          -
    GOLD 15m            +11.7      +10.1      -16.2          -          -
    EURUSD 1h            +5.2       -0.6       -2.8       -2.6          -
    EURUSD 15m           +2.6       +0.9       +2.6          -          -
    GBPUSD 1h            +3.6       -1.6       -0.6       +1.8          -
    GBPUSD 15m           +8.1       -2.9       +8.4      -23.9          -
    US500 1h             +6.5       +2.0       +0.0      -13.1          -
    US500 15m           +18.5      -25.4       +7.2      -10.0          -
    ABOVE base            8/8        3/8        5/8        1/6          -
    mean pts             +8.3       -2.5       +0.0       -9.7          -

  --- er20: Kaufman efficiency ratio, 20 bars
    market              0-0.1    0.1-0.2   0.2-0.35  0.35-0.55      0.55+
    GOLD 1h              +5.4       +0.3       +0.1       -6.1          -
    GOLD 15m             -1.4       -6.5       -8.3      +13.7          -
    EURUSD 1h            +0.8       +3.9       -1.2       -4.6       +5.2
    EURUSD 15m           +3.1       -1.1       -2.2       +1.7          -
    GBPUSD 1h            -1.2       +7.3       -1.5       -3.9       -4.3
    GBPUSD 15m           +1.6       +6.5       +1.9      -16.5          -
    US500 1h             -1.7       +1.0       -1.3       +3.2       -1.9
    US500 15m           -10.5       +2.5       +5.4       -0.2          -
    ABOVE base            4/8        6/8        3/8        3/8        1/3
    mean pts             -0.5       +1.7       -0.9       -1.6       -0.3

  --- er50: Kaufman efficiency ratio, 50 bars
    market             0-0.08  0.08-0.15  0.15-0.25   0.25-0.4       0.4+
    GOLD 1h              +2.7       +1.2       +6.1       -8.8          -
    GOLD 15m             -5.5       +4.6       +1.1          -          -
    EURUSD 1h            -1.6       -1.3       +4.9       -4.1          -
    EURUSD 15m           +0.6       +6.8       -6.1       +0.6          -
    GBPUSD 1h            +4.6       -7.6       -1.9       +9.0          -
    GBPUSD 15m           -0.3       +0.2       +6.8      -12.2          -
    US500 1h             -7.5       +0.6       +5.2       +4.0       -0.7
    US500 15m            +0.9       -4.1       +6.3       -8.6          -
    ABOVE base            4/8        5/8        6/8        3/7        0/1
    mean pts             -0.8       +0.0       +2.8       -2.9       -0.7

  --- runbars: bars since the last opposite signal (run age, E-052)
    market                0-5       5-15      15-40     40-100       100+
    GOLD 1h                 -       +5.8       +4.2       -1.3       -0.8
    GOLD 15m                -          -          -       -2.4       -5.1
    EURUSD 1h            +3.7       +7.4       +0.3       +3.2       -4.7
    EURUSD 15m              -       -4.8      -13.9       +4.5       +5.7
    GBPUSD 1h               -       -9.8       +6.3       +1.4       -2.9
    GBPUSD 15m              -          -       -1.7       +0.8       -2.5
    US500 1h                -       -3.1       +4.4       -1.6       +1.8
    US500 15m               -          -          -       -2.7       +4.8
    ABOVE base            1/1        2/5        4/6        4/8        3/8
    mean pts             +3.7       -0.9       -0.1       +0.2       -0.5

  --- runmove: distance travelled in this run, ATR (E-052)
    market                0-1        1-2        2-4        4-8         8+
    GOLD 1h              -5.5      -15.3       -0.9       +6.4       +6.2
    GOLD 15m                -          -       +1.3       -3.3      +14.4
    EURUSD 1h            -1.6      +14.1       -3.6       -1.7       -1.8
    EURUSD 15m           +1.1       -3.3       -6.5      +10.8       -3.3
    GBPUSD 1h            +1.4       +7.4       +0.7       -0.8       -4.3
    GBPUSD 15m           +3.5       +6.1       -0.3       -2.2       -3.4
    US500 1h             +0.1      -13.1       -0.3       +5.8       +0.2
    US500 15m           -12.8      +15.2       +2.1      -10.8       +5.2
    ABOVE base            4/7        4/7        3/8        3/8        4/8
    mean pts             -2.0       +1.6       -0.9       +0.5       +1.7

  --- stretch: signed distance from DEMA200 in ATR (+ = already extended the trade's way)
    market                <-1       -1-0        0-1      1-2.5       2.5+
    GOLD 1h              +0.7       -5.0       -2.5       +1.4       +2.8
    GOLD 15m             +1.7          -          -          -       -2.0
    EURUSD 1h            +2.0       -2.5       -5.7       -0.1       -0.3
    EURUSD 15m           +4.0          -          -       -0.1       -6.1
    GBPUSD 1h            -1.0       +8.0       -1.1       -3.5       +1.0
    GBPUSD 15m           -4.2      +21.5      -15.4       +6.5       +2.0
    US500 1h             -5.6       -1.0       +6.2       -1.5       +7.5
    US500 15m            +1.1          -          -          -       +6.9
    ABOVE base            5/8        2/5        1/5        2/6        5/8
    mean pts             -0.2       +4.2       -3.7       +0.4       +1.5

  --- pos100: position in the last 100 bars' range, trade-direction adjusted
    market             0-0.25   0.25-0.5   0.5-0.75   0.75-0.9       0.9+
    GOLD 1h              +0.7       +0.4       -0.9       +1.4       -3.2
    GOLD 15m             +1.2       -4.4       +0.9          -          -
    EURUSD 1h            +3.8       -0.5       -1.1       -5.3       +1.5
    EURUSD 15m           +4.5      +11.4       -7.3      -14.6          -
    GBPUSD 1h            +0.0       -2.7       +1.5       +5.3       -4.9
    GBPUSD 15m           -0.2       -4.7       +2.7       +5.9          -
    US500 1h             -0.6       +4.7       -7.7       -0.9       +6.9
    US500 15m            +9.2       +3.3       -4.6          -          -
    ABOVE base            6/8        4/8        3/8        3/6        2/4
    mean pts             +2.3       +1.0       -2.1       -1.4       +0.1

  --- adx: ADX at the flip
    market               0-15      15-20      20-25      25-35        35+
    GOLD 1h             +10.9       +7.5       +5.2       +2.9      -11.5
    GOLD 15m                -          -       +6.6      -11.6       +1.6
    EURUSD 1h            +7.5       +2.0       -2.8       -3.5       -1.6
    EURUSD 15m          +19.9       +3.1      -13.0       -3.7      -15.2
    GBPUSD 1h            +6.3       +7.6       -0.5       -5.8       -5.0
    GBPUSD 15m          +11.1       +5.6       -0.3      -12.4      -16.2
    US500 1h             +9.2       -8.7       +8.8       -5.0       +1.1
    US500 15m               -       -0.0       -0.8       -4.4          -
    ABOVE base            6/6        5/7        3/8        1/8        2/7
    mean pts            +10.8       +2.4       +0.4       -5.4       -6.7

  --- adxslope: ADX minus ADX 3 bars ago (falling / flat / rising)
    market                <-1       -1-1         1+
    GOLD 1h              -1.7       +3.8       -0.3
    GOLD 15m            -11.0       -1.4      +10.1
    EURUSD 1h            -0.3       +0.1       +0.3
    EURUSD 15m          -12.2      +10.7       +4.5
    GBPUSD 1h            -3.5       +1.2       +2.6
    GBPUSD 15m           -6.3       +3.5       +4.1
    US500 1h             +2.5       +2.8       -5.0
    US500 15m            -8.1       -1.7       +8.3
    ABOVE base            1/8        6/8        6/8
    mean pts             -5.1       +2.4       +3.1

  --- swept: flip bar took out the previous swing point (0 = no, 1 = sweep)
    market                0-1         1+
    GOLD 1h              -1.2       +4.0
    GOLD 15m             +0.7       -2.8
    EURUSD 1h            +2.0       -6.1
    EURUSD 15m           -2.7       +8.4
    GBPUSD 1h            -0.4       +1.1
    GBPUSD 15m           -3.6       +8.9
    US500 1h             +2.5       -6.7
    US500 15m            -2.7       +6.0
    ABOVE base            3/8        5/8
    mean pts             -0.7       +1.6

  --- hour: hour of day, UTC
    market                0-4        4-8       8-12      12-16      16-20        20+
    GOLD 1h              +4.3       +3.5       +0.6       +2.6       -8.5       -0.5
    GOLD 15m                -       -4.1          -       +0.1          -          -
    EURUSD 1h            -3.3       +5.2       -1.5       +3.3       +3.3       -7.1
    EURUSD 15m           +6.9      +18.9      +17.3      -13.1      -25.1       -4.1
    GBPUSD 1h            -6.9       -0.2       +4.6       +3.4       -5.5       +4.8
    GBPUSD 15m          +13.0      +26.8       +7.0       -5.9      -38.2       -0.1
    US500 1h             +3.6       +7.1      +14.9       -7.6       -9.6      -10.9
    US500 15m               -      +12.5          -      +16.9      -29.7      -29.3
    ABOVE base            4/6        6/8        5/6        5/8        1/7        1/7
    mean pts             +2.9       +8.7       +7.1       -0.0      -16.2       -6.7

  --- nflip20: SuperTrend flips in the last 20 bars (whipsaw density)
    market                0-2        2-3        3-5         5+
    GOLD 1h              -2.0       +0.9       +7.3          -
    GOLD 15m             -4.1      +10.1       -7.9          -
    EURUSD 1h            -4.4       +2.2       +3.3          -
    EURUSD 15m           +0.0       -0.8       -1.3          -
    GBPUSD 1h            -0.8       +3.1       -4.6          -
    GBPUSD 15m           -1.6       -1.8       +1.1          -
    US500 1h             +3.5       -3.4       -1.3          -
    US500 15m            -2.1      +16.7      -13.8          -
    ABOVE base            2/8        5/8        3/8          -
    mean pts             -1.4       +3.4       -2.1          -


================================================================================================
  SCOREBOARD — every cell with >= 7 of 8 markets on the same side, both arms
================================================================================================

  SIGNAL arm: 7 such cells out of 48 testable
    atrratio        1.25-1.6   0/7 above base   mean -11.5 pts
    hour                 4-8   6/6 above base   mean +10.2 pts
    atrratio           0-0.8   8/8 above base   mean +7.2 pts
    atrratio          1-1.25   0/7 above base   mean -6.0 pts
    runbars             100+   1/8 above base   mean -5.3 pts
    hour                8-12   6/7 above base   mean +5.2 pts
    atrratio           0.8-1   7/8 above base   mean +3.9 pts

  RANDOM arm: 8 such cells out of 57 testable
    hour               16-20   1/7 above base   mean -16.2 pts
    adx                 0-15   6/6 above base   mean +10.8 pts
    atrratio        1.25-1.6   1/6 above base   mean -9.7 pts
    atrratio           0-0.8   8/8 above base   mean +8.3 pts
    hour                8-12   5/6 above base   mean +7.1 pts
    hour                 20+   1/7 above base   mean -6.7 pts
    adx                25-35   1/8 above base   mean -5.4 pts
    adxslope             <-1   1/8 above base   mean -5.1 pts

  SIDE BY SIDE — does the random arm do it too?
    cell                                  signal            random
    atrratio 1.25-1.6                 0/7  -11.5         1/6  -9.7
    hour 4-8                          6/6  +10.2         6/8  +8.7
    atrratio 0-0.8                     8/8  +7.2         8/8  +8.3
    atrratio 1-1.25                    0/7  -6.0         5/8  +0.0
    runbars 100+                       1/8  -5.3         3/8  -0.5
    hour 8-12                          6/7  +5.2         5/6  +7.1
    atrratio 0.8-1                     7/8  +3.9         3/8  -2.5

================================================================================================
  MULTIPLE TESTING — read this before quoting any cell above
================================================================================================
  Feature/bucket cells examined at horizon 50: 68; 48 had >= 6 markets with enough data to score.
  Under the null (each market a coin flip), P(a cell lands >= 7 of 8 on one side) = 7.0%,
  and P(8 of 8) = 0.78%. So among 48 testable cells the null EXPECTS about 3.4 cells
  at the 7-of-8 level and 0.38 at 8-of-8.
  Observed in the SIGNAL arm: 7.  Observed in the RANDOM arm: 8.
  These markets are NOT independent (GOLD 15m overlaps GOLD 1h; EURUSD and GBPUSD correlate
  ~0.9, E-015), so the true expected count is HIGHER than the figure above, not lower.
  All three horizons ([20, 50, 120]) were computed, which multiplies the cell count by 3 if
  any horizon other than the pre-registered 50 is quoted.

================================================================================================
  HORIZON ROBUSTNESS for the signal-arm survivors
================================================================================================
    cell                                  N=20            N=50           N=120
    atrratio 1.25-1.6                0/7  -6.6      0/7  -11.5       0/7  -9.4
    hour 4-8                         5/6  +9.6      6/6  +10.2       5/6  +5.8
    atrratio 0-0.8                   6/8  +5.0       8/8  +7.2       8/8  +6.6
    atrratio 1-1.25                  2/7  -5.6       0/7  -6.0       0/7  -4.9
    runbars 100+                     3/8  -1.4       1/8  -5.3       2/8  -4.6
    hour 8-12                        6/7  +6.4       6/7  +5.2       6/7  +6.9
    atrratio 0.8-1                   7/8  +3.6       7/8  +3.9       7/8  +3.4

================================================================================================
  OUT-OF-SAMPLE SEPARABILITY, horizon 50 bars
  Score fitted on the first 70% of rows, scored on the last 30%.
  AUC = P(a LARGE-MFE entry outranks a TINY-MFE entry). 0.50 = no information at all.
================================================================================================
    market              arm  n test  nLarge  nTiny     AUC  topQ P(lg)  botQ P(lg)    base
    GOLD 1h          signal     111      56      7 too few
    GOLD 1h          random     111      54      9 too few
    GOLD 15m         signal      42      25      3 too few
    GOLD 15m         random      42      21      5 too few
    EURUSD 1h        signal     196      85     25   0.503       48.7%       46.2%   43.4%
    EURUSD 1h        random     196      96     19   0.354       35.9%       64.1%   49.0%
    EURUSD 15m       signal      78      24     12   0.514       26.7%       20.0%   30.8%
    EURUSD 15m       random      78      26     10   0.535       53.3%       40.0%   33.3%
    GBPUSD 1h        signal     194      82     27   0.569       57.9%       39.5%   42.3%
    GBPUSD 1h        random     194      93     16   0.496       44.7%       55.3%   47.9%
    GBPUSD 15m       signal      77      36     13   0.457       60.0%       40.0%   46.8%
    GBPUSD 15m       random      77      28     11   0.584       46.7%       33.3%   36.4%
    US500 1h         signal     138      48     14   0.583       40.7%       29.6%   34.8%
    US500 1h         random     138      67      9 too few
    US500 15m        signal      46      15      2 too few
    US500 15m        random      46      19      7 too few
    SIGNAL         mean AUC 0.525   AUC > 0.5 in 4/5   mean topQ lift +7.2 pts
    RANDOM         mean AUC 0.492   AUC > 0.5 in 2/4   mean topQ lift +3.5 pts

================================================================================================
  OUT-OF-SAMPLE: LARGE (>= 4.0 ATR) vs EVERYTHING ELSE, horizon 50. 70/30 chronological split.
  Both arms get the identical fitting procedure. Only the difference between them is evidence.
================================================================================================
    market            arm  nTest  nLarge     AUC     topQ     botQ    base    lift
    GOLD 1h        signal    111      56   0.514    54.5%    45.5%   50.5%    +4.1
    GOLD 1h        random    111      54   0.606    63.6%    40.9%   48.6%   +15.0
    GOLD 15m       signal     42      25   0.489    62.5%    50.0%   59.5%    +3.0
    GOLD 15m       random     42      21   0.397    62.5%    62.5%   50.0%   +12.5
    EURUSD 1h      signal    196      85   0.487    48.7%    46.2%   43.4%    +5.4
    EURUSD 1h      random    196      96   0.402    35.9%    64.1%   49.0%   -13.1
    EURUSD 15m     signal     78      24   0.502    26.7%    20.0%   30.8%    -4.1
    EURUSD 15m     random     78      26   0.578    53.3%    40.0%   33.3%   +20.0
    GBPUSD 1h      signal    194      82   0.561    57.9%    39.5%   42.3%   +15.6
    GBPUSD 1h      random    194      93   0.452    44.7%    55.3%   47.9%    -3.2
    GBPUSD 15m     signal     77      36   0.514    60.0%    40.0%   46.8%   +13.2
    GBPUSD 15m     random     77      28   0.586    46.7%    33.3%   36.4%   +10.3
    US500 1h       signal    138      48   0.546    40.7%    29.6%   34.8%    +6.0
    US500 1h       random    138      67   0.634    55.6%    22.2%   48.6%    +7.0
    US500 15m      signal     46      15   0.589    55.6%    11.1%   32.6%   +22.9
    US500 15m      random     46      19   0.503    44.4%    44.4%   41.3%    +3.1
    SIGNAL      mean AUC 0.525   AUC>0.5 in 6/8   mean topQ lift +8.3 pts
    RANDOM      mean AUC 0.520   AUC>0.5 in 5/8   mean topQ lift +6.5 pts

================================================================================================
  OUT-OF-SAMPLE: LARGE (>= 4.0 ATR) vs EVERYTHING ELSE, horizon 20. 70/30 chronological split.
  Both arms get the identical fitting procedure. Only the difference between them is evidence.
================================================================================================
    market            arm  nTest  nLarge     AUC     topQ     botQ    base    lift
    GOLD 1h        signal    111      32   0.463    18.2%    31.8%   28.8%   -10.6
    GOLD 1h        random    111      21   0.488    22.7%    22.7%   18.9%    +3.8
    GOLD 15m       signal     42      13   0.618    37.5%    12.5%   31.0%    +6.5
    GOLD 15m       random     42       9    thin
    EURUSD 1h      signal    196      51   0.400    17.9%    33.3%   26.0%    -8.1
    EURUSD 1h      random    196      47   0.410    10.3%    28.2%   24.0%   -13.7
    EURUSD 15m     signal     78      13   0.296     0.0%    26.7%   16.7%   -16.7
    EURUSD 15m     random     78      16   0.491    20.0%    33.3%   20.5%    -0.5
    GBPUSD 1h      signal    194      53   0.471    21.1%    26.3%   27.3%    -6.3
    GBPUSD 1h      random    194      42   0.494    28.9%    34.2%   21.6%    +7.3
    GBPUSD 15m     signal     77      23   0.474    26.7%    26.7%   29.9%    -3.2
    GBPUSD 15m     random     77      17   0.470    20.0%    20.0%   22.1%    -2.1
    US500 1h       signal    138      22   0.565    14.8%    11.1%   15.9%    -1.1
    US500 1h       random    138      33   0.628    40.7%    11.1%   23.9%   +16.8
    US500 15m      signal     46       9    thin
    US500 15m      random     46      11   0.587    33.3%    11.1%   23.9%    +9.4
    SIGNAL      mean AUC 0.470   AUC>0.5 in 2/7   mean topQ lift -5.6 pts
    RANDOM      mean AUC 0.510   AUC>0.5 in 2/7   mean topQ lift +3.0 pts

================================================================================================
  MULTI-SEED RANDOM CONTROL for the strongest signal-arm cell: atrratio 0-0.8, P(large@50)
================================================================================================
    seed  0: 8/8 markets above base, mean +8.3 pts
    seed  1: 8/8 markets above base, mean +9.2 pts
    seed  2: 7/8 markets above base, mean +8.4 pts
    seed  3: 8/8 markets above base, mean +6.1 pts
    seed  4: 7/8 markets above base, mean +7.6 pts
    seed  5: 7/8 markets above base, mean +6.5 pts
    seed  6: 7/8 markets above base, mean +10.1 pts
    seed  7: 8/8 markets above base, mean +8.6 pts
    seed  8: 8/8 markets above base, mean +9.3 pts
    seed  9: 8/8 markets above base, mean +7.9 pts
    seed 10: 8/8 markets above base, mean +9.5 pts
    seed 11: 8/8 markets above base, mean +9.0 pts
    seed 12: 8/8 markets above base, mean +8.4 pts
    seed 13: 8/8 markets above base, mean +10.1 pts
    seed 14: 7/8 markets above base, mean +7.2 pts
    seed 15: 8/8 markets above base, mean +9.0 pts
    seed 16: 7/8 markets above base, mean +10.0 pts
    seed 17: 8/8 markets above base, mean +6.5 pts
    seed 18: 8/8 markets above base, mean +6.7 pts
    seed 19: 7/8 markets above base, mean +9.5 pts
    ACROSS 20 SEEDS: median 8.0/8 above base, mean effect +8.4 pts, range +6.1 to +10.1

================================================================================================
  DENOMINATOR ROBUSTNESS: is 'atrratio 0-0.8 predicts a big move' an artifact of dividing
  MFE by ATR(14)-at-signal - a denominator this very feature helps define? Re-normalise the
  IDENTICAL forward moves by ATR(50)-at-signal, a slow denominator, and re-read the cell.
================================================================================================
    market            arm  base/ATR14  cell/ATR14  base/ATR50  cell/ATR50
    GOLD 1h        signal       49.2%       52.1%       46.8%       41.1%
    GOLD 1h        random       36.5%       47.1%       34.9%       35.3%
    GOLD 15m       signal       52.2%       59.3%       52.9%       55.6%
    GOLD 15m       random       39.9%       51.5%       37.0%       42.4%
    EURUSD 1h      signal       46.3%       53.3%       45.8%       42.9%
    EURUSD 1h      random       44.8%       50.0%       44.5%       42.2%
    EURUSD 15m     signal       40.9%       50.0%       37.0%       35.3%
    EURUSD 15m     random       45.5%       48.1%       47.1%       41.8%
    GBPUSD 1h      signal       44.2%       50.0%       44.5%       44.3%
    GBPUSD 1h      random       43.7%       47.3%       42.8%       42.7%
    GBPUSD 15m     signal       44.9%       57.5%       41.4%       50.7%
    GBPUSD 15m     random       46.5%       54.5%       46.1%       50.6%
    US500 1h       signal       43.3%       51.8%       42.2%       38.6%
    US500 1h       random       44.8%       51.2%       42.4%       38.0%
    US500 15m      signal       30.3%       34.9%       28.3%       23.3%
    US500 15m      random       40.8%       59.3%       38.2%       42.6%

    atrratio 0-0.8 effect, MFE / ATR14:  signal mean +7.2 pts (8/8 positive)   random mean +8.3 pts (8/8)
    atrratio 0-0.8 effect, MFE / ATR50:  signal mean -0.9 pts (2/8 positive)   random mean +0.4 pts (4/8)

================================================================================================
  LONG/SHORT SPLIT of P(large@50) — the gold gap, tested
================================================================================================
    market       side               signal            random     gap
    GOLD 1h      long        53.3% (n=214)     30.8% (n=172)   +22.5
    GOLD 1h      short       43.6% (n=156)     41.4% (n=198)    +2.2
    GOLD 15m     long         50.0% (n=68)      42.4% (n=66)    +7.6
    GOLD 15m     short        54.3% (n=70)      37.5% (n=72)   +16.8
    EURUSD 1h    long        45.6% (n=338)     47.0% (n=330)    -1.4
    EURUSD 1h    short       47.1% (n=312)     42.5% (n=320)    +4.6
    EURUSD 15m   long        41.2% (n=119)     52.0% (n=125)   -10.8
    EURUSD 15m   short       40.6% (n=138)     39.4% (n=132)    +1.2
    GBPUSD 1h    long        46.1% (n=332)     47.3% (n=328)    -1.2
    GBPUSD 1h    short       42.2% (n=313)     40.1% (n=317)    +2.1
    GBPUSD 15m   long        44.8% (n=134)     54.0% (n=124)    -9.3
    GBPUSD 15m   short       45.1% (n=122)     39.4% (n=132)    +5.7
    US500 1h     long        41.6% (n=286)     44.9% (n=216)    -3.3
    US500 1h     short       46.0% (n=174)     44.7% (n=244)    +1.3
    US500 15m    long         30.0% (n=80)      47.2% (n=72)   -17.2
    US500 15m    short        30.6% (n=72)      35.0% (n=80)    -4.4

================================================================================================
  THE SPREAD OF OUTCOMES IN PRICE POINTS (Veer's units), signal arm
  This is the size of the problem: the gap between a dud flip and a runner, before any
  attempt to predict it.
================================================================================================
    market           H     n      p10      p25   median      p75      p90       max  p90/p10
    GOLD 1h         20   370     3.72       10     22.7     52.8     90.3     247.6    24.3x
    GOLD 1h         50   370     6.32     18.4     43.7     84.3      159     558.6    25.2x
    GOLD 1h        120   370     9.02     31.8       72      129      216     913.4    24.0x
    GOLD 15m        20   138     3.22     7.02     19.7     34.9       48     101.5    14.9x
    GOLD 15m        50   138     4.92     12.6     34.9     60.7     78.7     138.4    16.0x
    GOLD 15m       120   138     5.82     20.8     58.3     90.9      123     228.5    21.2x
    EURUSD 1h       20   650  0.00027  0.00087  0.00218  0.00423  0.00654   0.03312    24.2x
    EURUSD 1h       50   650   0.0005  0.00157  0.00393  0.00656   0.0103   0.04433    20.6x
    EURUSD 1h      120   650  0.00089  0.00254  0.00595   0.0103    0.016   0.05158    18.0x
    EURUSD 15m      20   257    4e-05   0.0003   0.0007  0.00146  0.00235   0.00999    58.7x
    EURUSD 15m      50   257    4e-05  0.00043  0.00112  0.00225  0.00384   0.01257    96.0x
    EURUSD 15m     120   257  0.00018   0.0007  0.00185  0.00353  0.00601   0.01507    33.4x
    GBPUSD 1h       20   645  0.00033  0.00115  0.00265  0.00522  0.00793   0.01955    24.0x
    GBPUSD 1h       50   645  0.00068   0.0022  0.00481  0.00817   0.0129   0.02329    18.9x
    GBPUSD 1h      120   645  0.00107  0.00344   0.0073    0.013    0.018   0.04248    16.8x
    GBPUSD 15m      20   256    2e-05  0.00026  0.00088  0.00176  0.00346   0.00968   173.0x
    GBPUSD 15m      50   256  0.00015  0.00056  0.00158  0.00355  0.00517   0.01572    34.5x
    GBPUSD 15m     120   256  0.00024  0.00091  0.00259  0.00455   0.0071   0.02152    29.6x
    US500 1h        20   460      5.4     12.6     28.9     51.9     90.4     251.1    16.7x
    US500 1h        50   460     7.65     20.9     47.4     90.9      138     443.6    18.0x
    US500 1h       120   460     12.4     33.9     76.4      142      215     822.1    17.3x
    US500 15m       20   152      2.4     6.65     14.9     27.6     40.6      92.4    16.9x
    US500 15m       50   152     5.15     9.65     21.1     39.6     63.1     147.1    12.3x
    US500 15m      120   152     7.15     18.1     33.6     64.4     99.9     219.1    14.0x
```

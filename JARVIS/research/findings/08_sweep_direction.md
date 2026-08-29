# The liquidity sweep thesis is backwards on this data

**Status: strong negative result on the fade direction, tentative positive on
the follow direction. Phase 1 finding, not yet a strategy.**

Reproduce: `python3 JARVIS/research/sweep_study.py GOLD 15m --null`

## What was tested

A full sweep taxonomy was implemented (`JARVIS/research/sweeps.py`): liquidity
levels with confirmation lag, seven sweep classes (A-G), sweep depth, wick
ratio, reclaim speed, displacement, micro structure shift, and a liquidity
strength score. Decision-time features are held in a separate dict from
outcomes so a future value can never leak into a decision.

Entry is the close of the **decision bar** — the earliest bar at which the
classification was knowable. Stop 1 ATR, target 1R, **first-touch resolution**,
ties count as losses.

## Result 1 — fading sweeps is worse than a coin flip

GOLD 15m, 701 sweeps:

| | win rate at 1R |
|---|---|
| **Real sweeps, faded (the specified strategy)** | **44.5%** |
| Random side at the same bars | 49.2% |
| Random bars, same side mix | 49.4% |

**100% of random-side trials beat the real sweeps.** The sweep does not predict
direction, and sweep timing adds nothing over entering at random bars — it is
actively worse than both.

## Result 2 — the opposite direction works, on every market tested

| Market | bars | sweeps | FADE (as specified) | FOLLOW (opposite) |
|---|---|---|---|---|
| GOLD 15m | 4,501 | 701 | 44.5% | **54.1%** |
| GOLD 1h | 13,750 | 2,238 | 45.1% | **53.1%** |
| US500 1h | 13,716 | 2,198 | 45.0% | **52.0%** |
| EURUSD 1h | 17,252 | 2,244 | 48.3% | 49.7% |
| GBPUSD 1h | 17,253 | 2,841 | 46.9% | **51.7%** |

FOLLOW beats FADE on **5 of 5 markets**, and clears 50% on 4 of 5. The
direction of the effect is identical everywhere, across ~10,000 events.

## Why this is not surprising once stated

The retail narrative says price sweeps stops and *reverses*. The actual
microstructure research says the opposite: Osler's work on stop-loss cascades
found that triggered stop orders **accelerate** price, because a stop to sell
is a market sell. A cluster of stops is fuel in the direction of the break, not
against it.

The independent evidence review in `findings/01_liquidity_evidence.md` reached
the same place from the literature: the clustering phenomenon is real, the
reversal trade is not.

So "liquidity sweep" as a reversal signal appears to have the mechanism exactly
inverted. Type F in the taxonomy — "sweep + continuation", labelled the FAILURE
case — outperformed types A and B, the supposed successes (50% vs 42-43%).

## What this does NOT prove

- **Only one exit scheme tested** (1 ATR stop, 1R target). The direction of the
  result is stable, but the magnitude will move with R:R.
- **No costs applied yet.** At 54% and 1:1, gross expectancy is +0.08R. Gold's
  0.30 round-trip against a ~8.7 ATR stop on 15m is ~3.4% of risk, so net is
  roughly +0.05R — thin, and it would not survive a much tighter stop.
- **No MTF filter, no session filter, no regime filter.** The specification
  calls for M15→M5→M1 alignment; none of that is applied here.
- **EURUSD is nearly flat** (49.7% vs 48.3%), so the effect is not uniform.
- **No M1 data exists**, so the M1 sniper entry model is untested entirely.

## Result 3 — the sweep DOES add value, in the follow direction

The obvious challenge: does the whole sweep apparatus beat a three-line
momentum rule? Tested against "buy any 20-bar high, sell any 20-bar low",
identical stop, target and resolution — only the entry differs.

| Market | sweep-FOLLOW | plain 20-bar breakout | sweep advantage |
|---|---|---|---|
| GOLD 15m | 54.1% | 52.4% | +1.6 |
| GOLD 1h | 53.1% | 47.9% | **+5.2** |
| US500 1h | 52.0% | 50.2% | +1.7 |
| EURUSD 1h | 49.7% | 46.7% | +3.0 |
| GBPUSD 1h | 51.7% | 47.9% | +3.8 |

**Sweep detection beats plain momentum on 5 of 5 markets, average +3.1
points.** So the liquidity level is not decoration: breaking a level where
resting orders sit is measurably different from breaking an arbitrary 20-bar
high.

This is the first result in this project to beat its baseline consistently
across markets.

### Cost arithmetic, honestly

At 53-54% with a 1:1 reward:risk, gross expectancy is +0.06R to +0.08R.
Gold's ~0.35 round-trip against a 1-ATR stop is roughly 1.7% of risk on 1h and
4% on 15m, so net lands near **+0.04R per trade**. Real, but thin — and thin
enough that a materially worse broker, or a tighter stop, erases it.

### What it still has to survive

- The multiple-testing bar. This project has now run well over 50 variants; the
  luck threshold is around t = 2.8 and no t-statistic has been computed for
  this result yet.
- Walk-forward across six periods.
- Full cost sensitivity at 2x and 3x spread.
- Out-of-sample confirmation on data not used to find it.

Until those pass, this is **PROMISING**, not an edge.

## What it changes about the plan

1. **Do not build a sweep-fade EA.** The base signal is negative on every
   market tested. Filters applied to a negative base are fighting uphill.
2. **The continuation direction deserves the next round of work.** It is
   positive on 4 of 5 markets and beats the coin-flip baseline on gold by ~5
   points. That is a candidate, not an edge, until it survives costs,
   walk-forward and the multiple-testing bar.
3. **The sweep layer earns its place** — but only in the follow direction. It
   beats a plain breakout by ~3 points on every market tested, so the liquidity
   level carries information a generic price extreme does not.
4. **The next tests are the gauntlet**: t-statistic against the luck bar,
   walk-forward, cost sensitivity, and out-of-sample. Nothing gets built into
   an EA before those.

## Note on the screenshots

The Pine BUY/SELL labels and the liquidity boxes are separate datasets, as
specified. Nothing here evaluates the Pine signals — that is a separate test
which needs the Pine logic ported to the engine, and it should be run before
assuming the two should ever be combined.

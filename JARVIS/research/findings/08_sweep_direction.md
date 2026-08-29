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

## What it changes about the plan

1. **Do not build a sweep-fade EA.** The base signal is negative on every
   market tested. Filters applied to a negative base are fighting uphill.
2. **The continuation direction deserves the next round of work.** It is
   positive on 4 of 5 markets and beats the coin-flip baseline on gold by ~5
   points. That is a candidate, not an edge, until it survives costs,
   walk-forward and the multiple-testing bar.
3. **The next test is whether the sweep adds anything at all** over a plain
   momentum rule ("buy an N-bar high"). If it does not, the entire sweep
   apparatus is unnecessary complexity and should be deleted rather than
   tuned.

## Note on the screenshots

The Pine BUY/SELL labels and the liquidity boxes are separate datasets, as
specified. Nothing here evaluates the Pine signals — that is a separate test
which needs the Pine logic ported to the engine, and it should be run before
assuming the two should ever be combined.

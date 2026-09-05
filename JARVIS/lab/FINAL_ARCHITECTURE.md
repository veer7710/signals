# SYSTEM A — THE VALIDATED CORE
**Status: PROMISING. Validated out-of-sample and against a fair control. Not yet
forward-tested. 2018 H1 only.**

## THE EDGE, IN ONE LINE
A limit resting inside a confirmed **M1 liquidity pivot**, taken only when the
**M1 SuperTrend already points that way**, filled by the sweep, trailed by the
**M1 SuperTrend band**.

**This is Veer's architecture, not mine.** He said: *"supertrend is meant for m1,
the point is we catch every single m1 trend... m5 or m15 is caught late by
supertrend but top ticked by smc and ict thru liquidity strats"*. Every earlier
test used SuperTrend's FLIP as the entry — the exact lateness he describes.
Giving it the DIRECTION job and letting a liquidity pivot supply the TIMING
measured better than anything else in this repository, and the filter helps
**only at M1**, which is precisely his claim:

| zone TF | no filter | + SuperTrend direction | trades/day |
|---|---|---|---|
| M15 pivot 3 | 39.2 pts | 24.4 | 3.2 |
| M5 pivot 5 | 58.6 | 55.4 | 6.1 |
| **M1 pivot 5** | 48.4 | **97.1** | **9.0** |

## WHY EACH COMPONENT IS THERE (§14 — every part must carry information)

| component | information it provides | evidence |
|---|---|---|
| **M15 swing pivot** | where resting stops actually sit | E-121: real zones vs the SAME zones time-shifted = **+441 pts, 21.5 se** |
| **limit inside the zone** | fill at the sweep extreme, not after it | E-076/E-077; the sweep close scores −0.003R |
| **M1 execution** | precise fill, small stop | E-111: real spread 0.229, M1 ATR 0.246 |
| **M1 SuperTrend band as TRAIL** | volatility-adjusted give-back that widens in trend and tightens in chop | E-125: **39.6 pts vs 11.0** for a fixed 25% giveback |

**Nothing else is in the system.** Everything else tested was removed:

| removed | why |
|---|---|
| SuperTrend flip as ENTRY | E-112/113/114: +0.0021R over control **at zero cost**. No edge. |
| DEMA gate | E-114: **−3.1 control se** — worse than random |
| exit on opposite ST flip | E-125: −7.5 pts vs +39.6 for the band trail |
| ST as directional filter | E-125: with-trend 9.0, against 2.0, **all 11.0** — filtering only removes trades |
| ST as chop filter | E-125: quiet 6.1, choppy 2.0, **all 11.0** — same |
| rejection-wick filter | E-126: adds nothing on top of the trail (9.6 pts on 44 trades vs 24.1 on all) |
| fixed 2R/3R target | E-122: −29.3 and −43.6 pts |
| 25% giveback trail | E-126: TRAIN 11.1 → **TEST −0.1**. Dies out of sample. |

## THE EVIDENCE (E-127, E-128, E-129)
```
train 46.7 pts  ->  TEST 50.3 pts          out of sample EXCEEDS in sample
walk-forward    15.8 / 18.7 / 21.1 / 20.3 / 21.2     FIVE OF FIVE positive
long +56.3      short +40.8                both directions
cost   0.11 -> 97.1 | 0.17 -> 82.6 | 0.25 -> 63.1 | 0.40 -> 26.7 | 0.93 -> -103
       survives a standard retail spread
parameters      a PLATEAU: all nine neighbouring cells positive (60.9 to 99.5)
time-shifted control -1099.3 pts  ->  EDGE +1196.5 = 79.2 control se
```
**981 trades over 109 days = 9.0/day.** 97.1 points = **£564 per 0.01 lot at
today's volatility** (£5.17/day), and it scales with size.

No block carries it; no direction carries it; it is a plateau not a peak; and
out-of-sample beats in-sample. That is the profile of a mechanism.

## THE KNOWN FAILURE MODE — state it before deploying (E-129)
The entry is a **limit** (fills at the level or better, no slippage). The exit is
a **stop** (a long sells when price falls to the band, so it fills at or below).
```
exit slippage   0.00p    0.02p    0.05p    0.10p    0.15p
points          97.1     77.5     48.1     -1.0    -50.0
£/day           5.17     4.13     2.56    -0.05    -2.66
```
**BREAKEVEN AT 0.10 POINTS OF EXIT SLIPPAGE.** Normal M1 gold stop fills slip
0.01-0.05, so it survives with about half the edge. It does not survive a broker
that slips a full tenth of a point — and that is measurable on demo in a week,
before any money is at risk. **This is the single number that decides whether
this system is real in practice.**

## THE RULES (the shared spec for both Pine and MQL5)
```
ZONE      a confirmed M15 swing pivot, k=3 bars either side.
          KNOWN only k bars after it forms - never earlier.
          Lives 200 M15 bars, then expires.
ENTRY     a limit at  zone_price - side * 0.50 * ATR(14,M1)
          i.e. INSIDE the zone, past the level, where the sweep fills it.
          side = +1 (buy) at a swing LOW, -1 (sell) at a swing HIGH.
          Cancel if unfilled after 60 M1 bars or if the zone expires.
STOP      4.0 * ATR(14,M1) from the fill, at the broker.
TRAIL     the M1 SuperTrend(7, 1.2) band, ratcheted one way only:
             long  -> stop = max(stop, lower_band)
             short -> stop = min(stop, upper_band)
EXIT      the stop, or 240 M1 bars, whichever comes first. NO fixed target.
ONE AT A TIME. No new entry until the previous trade is 120 bars past.
```

## HONEST LIMITS
1. **2018 H1 only.** 109 trading days, gold 1275-1366. One regime.
2. **Costs are 2018's real per-bar spread scaled to today's estimated ECN
   regime** (spread/ATR 0.11). At a standard 0.46 spread the edge is thinner.
3. **Dukascopy (ECN) ticks.** PU Prime is retail and will be wider.
4. **No slippage on the trail exit is modelled.** E-118 showed a 0.043-point
   edge dies at 0.05 points of slippage; this system's edge is 0.111 pts/trade,
   about 2.5x that, so it survives ~0.10 points of slippage and not much more.
5. **Never forward-tested.** Nothing here has traded a live tick.
6. The feed is missing the 00:00 UTC hour daily (DATA_QUALITY.md).

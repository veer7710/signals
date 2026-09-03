# Deep code audit — XAUUSD_QUAD v19.18

Source: `/home/user/signals/JARVIS/ea/inbox/XAUUSD_QUAD_v19_18.mq5`
20,695 lines · 748 `input` declarations · 274 functions · 35 `CloseTagged()` call sites.

**NOT COMPILED, NOT TICK-TESTED.** There is no MT5 and no MetaEditor in this
container. Everything below is read from source. Anything that depends on
runtime values (actual broker ATR, actual tick value, actual fill behaviour)
is flagged in the last section.

This audit goes past `JARVIS/ea/AUDIT_v19_18.md`. That audit's three
conclusions (748 params unvalidatable, cost/risk fatal at M1, hold time too
short) are all **CONFIRMED**. Two of its supporting claims — both quoted from
the file's own header — are **WRONG for v19.18** and are corrected below.

---

## BOTTOM LINE

Every profit-protection mechanism in this EA is anchored to a "noise band"
(`NoiseFloorPts` = spread + 0.60 × ATR ≈ 1.2 points on M1 gold), it **arms** at
one band or more and it **gives back** at least one band — so a trade must peak
above ~2 bands before anything can bank it profitably, and whatever peaks above
that surrenders 40–60% of itself by construction. That is not a tuning miss; it
is arithmetic, and it produces both halves of the owner's complaint from one
cause: peaks below ~2.4 points can be banked by *nothing* and ride to the stop
("went up 50 points, closed in a loss"), while peaks above it are closed by
whichever of ~10 competing peak-anchored guards trips first, always well below
the top ("£10 of profit, never closed near it"). The EA does implement the
exact pattern that `06_exit_experiment.md` measured as the **worst** exit rule
on all four markets — break-even then trail — and it arms it at **≈0.24R**
(`T_MicroLock`, line 18264), even earlier than the 0.5R the experiment tested
at −0.161R on gold. Separately, with the shipped default `T_FixedLots = 0.03`,
`LotFor()` returns at line **7432** and never reaches the aggregate risk
ceilings at lines 7739/7752, so `AutoMaxExposurePct`, `InpMaxTotalLots` and
`T_MaxRiskStackMult` are dead — position size is a flat number unrelated to
stop distance or equity, and the only surviving cap is 0.30 lots per direction.
There is **no martingale, no grid and no averaging-down** in any live path
(one dormant exception, `InpDemaTopUp`, noted below), but there is also no
usable daily-loss guard: `InpMaxDailyLossPct = 40.0`.

---

## THE PEAK-GIVEBACK EXPLANATION

### The unit that governs everything

```
6712: double NoiseFloorPts(double atrTf)
6713: {
6714:    if(T_NoiseFloorAtr <= 0.0) return 0.0;
6715:    double n = (atrTf > 0.0) ? T_NoiseFloorAtr * atrTf : T_LegNoisePts;
6716:    return SpreadUSD() + n;
6717: }
```
`T_NoiseFloorAtr = 0.60` (line 4011). On the tape the file itself calibrates
against (M1 gold ATR ≈ 1.47, spread ≈ 0.30 — see the v19.14 note at line 1741),
**one band ≈ 1.18 points**.

Every peak-anchored guard is floored by this band, on both sides:

| Guard | Arms at | Gives back at least | Line |
|---|---|---|---|
| TRADE-LOCK | `max(T_TradeLockMinCash £0.50, 1.0 × band)` | `max(1.0 × band, 0.40 × peak)` | 16326–16334 |
| BASKET-LOCK | `max(T_BasketArmCash £5, 2.0 × band)` | `1.0 × band` | 9521–9539 |
| GIVEBACK | `peakR ≥ T_GivebackMinR 0.30` | `nfR` (= 1 band), capped 0.95 × peak | 17697–17700 |
| Peak trail (Chandelier) | `T_TrailArmR 0.35` **and** `min(PS(3.0), 0.35×peak)` pts | `T_TrailRoomAtr 1.30 × ATR` (band cap is **OFF**) | 17908–17930, 18081–18101 |
| Peak ratchet floor | inside micro-lock | `≥ 1 band` below peak (line 18383) | 18270–18410 |

So the *best possible* retention is `(peak − 1 band) / peak`:

| Peak | Retained | Given back |
|---|---|---|
| 1.0 pt | **nothing arms** | 100% (rides to stop) |
| 2.4 pts (2 bands) | ~50% | ~50% |
| 3.63 pts (the file's own measured average peak, line 8167) | ~67% | ~33% |
| 12 pts | ~90% | ~10% |

The file's own panel number — "peaks summed £110, handed back £73.43 on 43
trades" (header lines 12–14) — is 33% retained. That is this table, at the
average peak, exactly.

### Half the distribution cannot be banked at all

At ATR 1.47, `PtsScale()` = 1.47 / `T_PtsRefAtr` 1.80 = **0.82** (line 4663).
Stop floor = `max(T_SlFloorAtrMult 2.00 × 1.47, T_SlFloorPtsAbs 1.20,
3 × spread)` = **2.94 pts**, so R ≈ 2.94 (line 6621–6640).

Now take the owner's "chop trend goes up 50 points but we close in a loss".
50 broker points on a 2-digit gold quote is **0.50 in price**. Trace it:

* `T_MicroLock` (18264) needs `profitR ≥ 0.70` (**2.06 pts**) **or**
  `armByPoints`: `profitPts ≥ SpreadUSD() + min(T_BeArmPoints 0.40,
  T_BeArmAtr 0.80 × ATR)` = 0.30 + 0.40 = **0.70 pts** (18196–18208). Never reached.
* `T_BeArmPts` breakeven (18062) needs peak ≥ `PS(3.0)` = **2.46 pts**. Never.
* Trail (17908) needs `profitR ≥ 0.35` = **1.03 pts**. Never.
* GIVEBACK (17355) needs `peakR ≥ 0.30` = **0.88 pts**. Never.
* TRADE-LOCK (16326) needs peak ≥ 1 band = **1.18 pts**. Never.
* BASKET-LOCK (9521) needs the *basket total* ≥ 2 bands. Never.

**Nothing arms.** The only live exits are `MAX-LOSS` at `PS(T_MaxLossPts 3.0)`
= 2.46 pts down (8546) and the broker stop at 2.94. So a trade that goes 0.50
in price your way and then turns closes for a full-size loss. That is the
owner's sentence, mechanically, with line numbers.

### Why the big one never closes near the peak

"We enter with 5 × 0.01 lots totalling £10 profit but never close near that."

0.05 lots of gold is ≈ 5 currency units per point (`LossPerLot`, 6719).
£10 across the stack is therefore only **2.0 points of price**. The EA does not
see £10; it sees a 2-point wobble.

`LedgerBasket()` runs **first in OnTick** (line 20581), before any per-position
logic:

```
9521:    double armAt = T_BasketArmCash;
9522:    if(bandGBP > 0.0)
9523:       armAt = MathMax(T_BasketArmCash, T_BasketArmBands * bandGBP);
9525:    if(g_bskPeak < armAt) return;
...
9539:       newFloor = g_bskPeak - T_BasketGiveBackBands * bandGBP;
...
9570:    if(g_bskArmed && tot <= g_bskFloor)   ->  closes the WHOLE basket
```
`bandGBP` = 1.18 pts × 0.05 lots ≈ **£5.90**. `armAt` = max(£5, 2 × £5.90) =
**£11.80**. A £10 peak **never arms the basket lock at all**. If it had peaked
at £12, the floor would be £12 − £5.90 = **£6.10** — i.e. it banks half.

Meanwhile the per-ticket lock does fire, at 60% of peak:
```
16332:    double give    = MathMax(T_TradeLockGiveBands * band, T_TradeLockGivePct * pk);
16333:    double floorAt = pk - give;
```
`T_TradeLockGivePct = 0.40` (line 4707). **Every trade that arms this is closed
on a 40%-of-peak retrace, unconditionally, at market, on any tick.** It is the
third statement in `ManagePosition` (line 16375), it runs before `holdGrace`
exists, and it is tag-exempt from the winner floor (line 8695) and from the
arbiter (`IsSafetyExit` is bypassed by tag list at 8695). Nothing can veto it.

### And the guards fight each other — first to trigger wins

Roughly ten independent peak-anchored mechanisms are live at once, each with a
different allowance. The realised exit is the **minimum** of all of them, so the
system's effective giveback tolerance is the *tightest* one on any given tick,
not the one that was tuned. On a 3.63-pt peak at ATR 1.47:

| Mechanism | Fires at | Retained |
|---|---|---|
| Peak trail (`T_TrailRoomAtr 1.30 × ATR = 1.91`) | +1.72 pts | 47% |
| TRADE-LOCK (`0.40 × peak = 1.45`) | +2.18 pts | 60% |
| GIVEBACK (floored at 1 band = 1.18) | +2.45 pts | 67% |
| `hardGivebackCap` (`T_MaxGivebackPct 65%`) | +1.27 pts | 35% |

TRADE-LOCK wins in practice because it is a **market close on every tick**,
whereas the trail is a resting stop that needs price to actually trade there.
So the operative exit rule in v19.18 is: *close on a 40% retrace from peak, or
one noise band, whichever is larger.* Everything else in the 3,200-line
`ManagePosition` is decoration behind it.

### This is the BE-then-trail pattern, armed even earlier than 0.5R

`06_exit_experiment.md` measured "break-even at 0.5R then trail" at **−0.161R**
on gold, −0.188R US500, −0.308R EURUSD, −0.293R GBPUSD — worst on all four.

This EA implements it, at **0.24R**:

```
18155:    double microArm = T_MicroLockR;                 // = 0.70  (line 3138)
18196:    double armPts = T_BeArmPoints;                  // = 0.40  (line 3143)
18197:    if(T_BeArmAtr > 0.0 && atr > 0.0)
18199:       double propArm = MathMax(T_BeArmAtr * atr, 0.15);   // T_BeArmAtr = 0.80
18205:       armPts = (T_BeArmMode == 1) ? propArm : MathMin(armPts, propArm);
18207:    bool armByPoints = (armPts > 0.0) && (profitPts >= SpreadUSD() + armPts);
...
18264:    if(T_MicroLock && (profitR >= microArm || armByPoints))
18266:       double mlLevel = (dir > 0) ? entry + SpreadUSD() : entry - SpreadUSD();
...
18412:       newSL = (dir > 0) ? MathMax(newSL, mlLevel) : MathMin(newSL, mlLevel);
```

`T_BeArmMode = 0` (line 3222) so `armPts = min(0.40, 1.18) = 0.40`. The stop
goes to **entry + spread** once the trade is 0.70 points onside — 0.24R, and
**0.48 × ATR**. The break-even stop is parked half an ATR from price. Ordinary
M1 noise takes it out. That is the −0.161R rule, tightened.

There are two more layers of the same idea on top of it: `T_EarlyBE` at
`T_EarlyBE_R = 1.0` (line 18601) and `T_BeArmPts = 3.0` peak-armed breakeven at
line 18062. Three break-even mechanisms; none of them was removed when the next
was added.

### Are the thresholds absolute money, or do they scale?

Mixed, and the mixture is the problem.

* **Scaled with volatility:** everything wrapped in `PS()` (`PtsScale()`, line
  4663 — live M1 ATR / `T_PtsRefAtr` 1.80, clamped 0.30–3.50), plus everything
  keyed to `NoiseFloorPts` or raw ATR.
* **Absolute money, does not scale:** `T_TradeLockMinCash = 0.50` (4709),
  `T_BasketArmCash = 5.00` (2015), `T_BasketStepCash = 1.00` (2016),
  `T_BasketMinPeakCcy = 3.00` (1898), `T_ProveMaxAdverse = 0.30` (4808),
  `T_DailyTargetGBP`. These are the residue of the "fixed ruler" bug the file
  diagnosed at v19.05 and only half-fixed.
* **Absolute price units and therefore gold-only:** `T_SlFloorPts 2.50`,
  `T_SlFloorPtsAbs 1.20`, `T_MaxLossPts 3.0`, `T_TargetPts 8.0`,
  `T_MinWinnerExitPts 6.0`, `T_LegNoisePts`, `T_RoundTripLagPts`. See bug #4.

But volatility-scaling is not the fix, and this is the key point the file never
reaches: **scaling a threshold that is already several noise bands wide does not
make it reachable.** `PS()` scales the *threshold* and the *band* together, so
the ratio — which is what decides whether a peak is bankable — is unchanged.

### There is also a hard ceiling on every winner

```
8530:    if(T_TargetPts > 0.0 && pts >= PS(T_TargetPts))
8534:          ... "Tagged MAX-LOSS so no hold rule or arbiter can veto a deliberate target."
8535:       CloseTagged("MAX-LOSS", tk);
```
`T_TargetPts = 8.0` (8458) → `PS()` ≈ 6.6 pts ≈ **2.2R**. This is the first
statement executed in `ManagePosition` (via `MaxLossCheck` at 16360) and it is
deliberately mis-tagged `MAX-LOSS` so that it bypasses the winner floor and the
arbiter. `MAX-LOSS` itself fires at `PS(3.0)` ≈ 2.46 pts = **0.84R**, i.e.
*before* the 2.94-pt broker stop — the stop is essentially never reached.

So the per-trade outcome distribution is truncated to roughly **[−0.84R,
+2.2R]** before any of the other 30 exits, and the peak-anchored locks close
most trades far inside that at ~0.5R. `06_exit_experiment.md` is explicit that
total profit on gold comes from the tail (90th pct MFE 7.51R, max 102.68R).
This EA cannot reach 2.3R.

---

## ARCHITECTURE MAP

### What actually runs

Three engines exist. **Two are switched off in the shipped defaults:**
```
1653: input bool   InpUseTrend = true;    // E0 Trend Rider — M1+M3+M5, the only engine now
1654: input bool   InpUseScalp = false;
1655: input bool   InpUseApex  = false;
```
`Engine_Scalp()` (14654–15000), `Engine_Apex()` (15029–15194), the `E_SCALP`
and `E_APEX` branches of `ManagePosition`, `ApexHealth`, `PyramidCount`,
`QuickHoldSize` and all `SC_*` / `A_*` inputs are dead. The file says so itself
at line 19169: *"THIS WHOLE BRANCH IS UNREACHABLE."*

### OnTick order (20573–20694)

```
20578  QSP_TrackLive()          peak/MFE sampler for every open ticket
20579  LedgerTravel()
20580  LedgerBasket()           <- contains BASKET-LOCK, can close the whole book
20584  LiveMarginWatch()        <- can close the worst loser
20589  BasketGivebackGuard()    <- T_BasketGiveback = false, dormant
20591  UpdateShadows()
20593  day roll: g_dayStart = ACCOUNT_BALANCE
20630  daily halt / daily profit lock  (KillAllPendings only, does NOT flatten)
20645  ManageEngine(e) for e in {TREND, APEX, SCALP}   <- ManagePosition per ticket
20646  StopForensics / Diagnostics / EnforceNoOpposingPendings / MonitorManual / ReadPineSignals
20681  NewsFlatten() if N_CloseOpen  (N_CloseOpen = false)
20691  Engine_Scalp()  (dead)
20692  Engine_Trend()  <- every tick, not new-bar
20693  if(newM15) Engine_Apex()  (dead)
```

Note `OnTick`'s own comment says *"Entries only on a new bar"* (20644) and then
calls `Engine_Trend()` every tick. That comment is false.

### What triggers an entry

`Engine_Trend()` (12588) loops `k` over `{M1, M3, M5}`:

* **M3 is skipped outright** — `T_SkipM3 = true`, line 12661.
* **M5 only within 3 bars of its flip** — `T_M5BirthBars = 3`, line 11170.
* So in practice **M1 only**, plus an occasional M5 birth.

Signal = raw Supertrend flip:
```
12691:    bool flipUp = (stD == 1  && g_trLastDir[k] == -1);
12692:    bool flipDn = (stD == -1 && g_trLastDir[k] ==  1);
...
13031:    if(!flipUp && !flipDn) continue;   // THE SIGNAL = the raw flip
```
`T_StMultiplier = 1.2` (3647) — a very fast Supertrend, so flips are frequent.

Six entry paths exist (`PathName`, 4079): CONFIRMED, EARLY-FLIP,
MICRO-BREAKOUT, REVERSAL, PULLBACK, RECLAIM. `T_PineParity = true` (4067)
blocks MICRO-BREAKOUT, REVERSAL and PULLBACK at line 13091. **Live paths:
CONFIRMED, EARLY-FLIP, RECLAIM.**

`EARLY-FLIP` (5973) is an **intrabar** signal:
```
5984:    if(curDir == -1 && ask > stLevel + margin) want =  1;
5985:    if(curDir ==  1 && bid < stLevel - margin) want = -1;
```
It fires the moment bid/ask crosses the Supertrend line by
`T_EarlyFlipAtr = 0.15` × ATR, before the bar closes. It is debounced to once
per bar per clock (`g_earlyFlipBar`, 12817), but the underlying signal is not a
closed-bar signal. This is the mechanical source of "catches small trends from
birth often" — and of taking flips that un-form by bar close.

The **ANCHOR GUARD**, the file's own fix for "we bought at a peak" (13037), is
doubly disabled by defaults:
```
13038:  if(T_AnchorMode > 0 && !T_TakeEveryPine && T_AnchorGuardAll && ...)
```
`T_TakeEveryPine = true` (4066) makes the whole condition false, and even if it
were true, `T_AnchorMode = 1` (4049) is "measure only". Dead twice over.

### Indicator reads

`Supertrend()` (8860) and `ScalpST()` (14540) both compute from **shift 1**
(closed bars) and cache per bar. **No repainting in the Supertrend itself.**
But see bug #7 — the chain is re-seeded from scratch every bar.

---

## THE EXIT SYSTEM

### Every exit path (35 `CloseTagged` sites, 32 distinct tags)

| Tag | Line | Runs before `holdGrace`? | Suppressed by default? |
|---|---|---|---|
| MAX-LOSS (target `T_TargetPts`) | 8535 | **yes** | no |
| MAX-LOSS (loss cap) | 8549 | **yes** | no |
| MAX-LOSS (reversal cut) | 8595 | **yes** | no (aged 180 s) |
| MAX-LOSS (4th site) | 8416 | **yes** | no |
| INFANT-CUT | 16227 | **yes** | no |
| TRADE-LOCK | 16340 | **yes** | no |
| BASKET-LOCK | 9595 | n/a (OnTick) | no |
| MARGIN-WATCH | 20570 | n/a (OnTick) | no |
| BASKET-GIVEBACK | 20505 | n/a | **`T_BasketGiveback = false`** |
| NEWS-FLAT | 15572 | n/a | **`N_CloseOpen = false`** |
| FRI-FLAT | 16707 | no gate | no |
| SPREAD-PANIC | 15968 | Guardian, age ≥ 180 s | no |
| H1-FLIP | 15996 | Guardian | **`G_ExitOnHtfFlip=false`, and `T_HtfNeverCloses` vetoes it at 8602** |
| THESIS-DEAD | 16033 | Guardian | winner floor + arbiter |
| GAP-AGAINST | 16932 | no gate | no |
| LEG-TARGET | 16958 | — | **`T_BanksOff = true`** |
| SPIKE-PEAK | 16984 | — | exempted back on (`T_BanksOffExemptPeak`) |
| EXHAUSTION | 17007 | — | **`T_BanksOff = true`** |
| EARLY-FAIL | 17092 | `holdGraceVotes` | winner floor + arbiter |
| STRUCT-BREAK | 17103 | **`!holdGrace`** | winner floor + arbiter |
| RANGE-SCALP | 17135 | **`!holdGrace`** | `T_BanksOff` but floor-exempt |
| SMALL-MOVE | 17196 | — | exempted back on (`T_BanksOffExemptSmall`) |
| CHOP-STALL | 17253 | — | **`T_BanksOff = true`** |
| PEAK-BANK | 17314 | — | exempted back on |
| MOM-STALL | 17350 | — | **`T_BanksOff = true`** |
| GIVEBACK | 17815 | `!holdGrace \|\| giveOwns` | floor-exempt |
| CHOP-CLUSTER | 17875 | **`!holdGrace`** | winner floor |
| STACK-BANK | 18258 | — | floor-exempt |
| FLIP-CLOSE | 19010 | vote quorum | floor-exempt |
| M1-MICROCHOP | 19226 | — | winner floor |
| SCALP-ST-FLIP | 19282 | — | floor-exempt |
| MOM-FADE | 19316 | — | winner floor |
| APEX-HEALTH | 19369 | — | dead engine |
| STALL | 19492 | none | winner floor |
| MAX-HOLD | 19520 | none | winner floor |

### The min-hold / grace logic — and the header claim is FALSE for v19.18

```
16439:   long mhMinSecs = MathMax((long)T_MinHoldSecs, (long)T_MinHoldBars * MathMax(mhBarSecs, 1));
16471:   bool mhVoided  = T_MinHoldNeedsGreen && (profitR < -T_MinHoldGiveR);
16472:   bool inMinHold = (T_MinHoldSecs > 0 || T_MinHoldBars > 0)
16473:                    && (posAgeSecs < mhMinSecs)
16474:                    && (profitR > -T_MinHoldDangerR)
16475:                    && !mhVoided;
```
`T_MinHoldSecs = 180` (3030), `T_MinHoldBars = 3` (3031). On an M1 trade
`mhMinSecs = max(180, 180) = 180 s`. On an M5 trade it is `max(180, 900) =
900 s`. `T_MinHoldNeedsGreen = true` (3057) voids it once `profitR < −0.35`.

```
16683:   bool holdGrace  = inMinHold || g_holdToTarget
16684:                     || (holdVotesEff >= votesNeededEff && (strongVote || !T_HoldNeedStrong));
```

**The header's claim — "30 of 32 exits disabled for 75% of every trade's life"
(lines 55–59, restated at 71–74) — is not true of this build.** I grepped every
use of `holdGrace` between line 16700 and 19600. It appears at exactly **five**
decision sites: 17071 (EARLY-FAIL), 17098 (STRUCT-BREAK), 17130 (RANGE-SCALP),
17756 (soft GIVEBACK) and 17870 (CHOP-CLUSTER). Everything else ignores it.

The real suppressor is `CloseTagged()` itself (8600–8823), and it is
**age-independent** — it never stops:

1. `T_HtfNeverCloses` (8298, true) → vetoes any tag containing "H1", "H4",
   "M15", "HTF", "LOCKDOWN" (8602).
2. `T_MinWinnerExitPts = 6.00` (8328) → *"no exit may close a PROFITABLE trade
   for less than 6 points"* unless it is on the `truly` list (8659–8724).
   Peak-relative cap at line 8728: `wFloor = min(PS(6.0), 0.35 × peak)`.
3. `T_ExitArbiter` (8299, true) → blocks non-safety tags in the band
   `0 < R < min(1.00, 0.35 × peakR)` (8746–8766).
4. `T_BanksOff = true` (8145) → silently suppresses LEG-TARGET, EXHAUSTION,
   CHOP-STALL, MOM-STALL (8769–8781), counted as `~TAG` in the panel.

That is why 21 exit tags produced zero exits: not the grace window, the
chokepoint. Fixing `T_MinHoldNeedsGreen` (which v19.11 did) could not have
unlocked them, and the header's v19.13 diagnosis that it "IS the unlock for all
21" is wrong.

### Break-even arm, trailing arm, giveback guard — summary

| Mechanism | Arms at | Stop / bank level | Line |
|---|---|---|---|
| micro-lock (BE) | 0.70R **or** 0.70 pts (**≈0.24R**) | entry + spread, then peak-ratchet | 18155, 18264 |
| `T_EarlyBE` | `T_EarlyBE_R = 1.0` R | entry + spread | 18601 |
| `T_BeArmPts` BE | peak ≥ `PS(3.0)` = 2.46 pts | entry + `PS(0.50)` | 18062 |
| ST-line trail | `T_TrailArmR 0.35` **and** `min(PS(3.0), 0.35×peak)` pts | Supertrend line − buffer | 17908, 17936 |
| Chandelier peak trail | same arm | `peak − T_TrailRoomAtr 1.30 × ATR` | 18081 |
| GIVEBACK | `peakR ≥ 0.30` | `peak − max(tier%, 1 band, roundtrip)` capped at `0.50×peak` and `T_GivebackMaxBands 3` bands | 17355–17700 |
| hard giveback cap | any peak | `T_MaxGivebackPct 65%` of peak | 17701 |
| TRADE-LOCK | peak ≥ 1 band | `peak − max(1 band, 0.40×peak)` | 16326 |
| BASKET-LOCK | total ≥ 2 bands | `total peak − 1 band` | 9521 |
| `T_TargetPts` | +`PS(8.0)` = 6.6 pts | market close, tagged MAX-LOSS | 8530 |

Eight peak-anchored guards and three break-even mechanisms, all live at once,
all competing. There is no arbitration between them; whichever trips first
ends the trade.

### One more reason reversals get missed

```
18978:  if(flipConfirmed && T_FlipCloseNeedDema && profitR > 0.0 && !demaAgainst)
18980:     flipConfirmed = false;   // "PULLBACK, NOT REVERSAL ... HOLDING through the reversal."
```
A **winning** trade will not be closed by an opposite Supertrend flip while
price is still on its side of the DEMA. The DEMA lags. So the winner holds into
the reversal, gives back the peak, and then exits via TRADE-LOCK at 60% of
peak — or, if the peak was under 2 bands, via `MAX-LOSS`. That is the owner's
"sometimes misses clear reversals … never closes at the peak" in one branch.

---

## RISK AND SIZING

### Position sizing — the stop is attached at OrderSend (good)

```
11406:   ok = (dir > 0) ? trade.Buy(lots, _Symbol, 0.0, sl, tp, cmt)
11407:                  : trade.Sell(lots, _Symbol, 0.0, sl, tp, cmt);
```
SL and TP go with the order. `FloorStopAtBirth` (6577) and `ClampStops` (6648)
run before send; `RefreshStops()` reads `SYMBOL_TRADE_STOPS_LEVEL` and
`SYMBOL_TRADE_FREEZE_LEVEL` at runtime (6565–6571). Filling mode is negotiated
from `SYMBOL_FILLING_MODE` at 9194–9197. Order-send retry logic (11404–11455)
correctly distinguishes unambiguous retcodes from ambiguous ones and checks for
a duplicate fill before retrying. **This part is good work.**

### But the risk model is bypassed by the shipped default

```
7109: double LotFor(int eng, double slDist)
7110: {
7113:    if(T_FixedLots > 0.0)
7114:    {
       ... balance tiers, cluster trim, confluence, multipliers ...
7432:       return fl;                              <-- ALWAYS taken (T_FixedLots = 0.03, line 3507)
7433:    }
7434:    double eq   = AccountInfoDouble(ACCOUNT_EQUITY);
...
7739:    if(openLots + lots > maxLots)              <-- NEVER REACHED
7752:    double riskNow  = OpenRiskCash();
7754:    double riskCeil = eq * AutoMaxExposurePct / 100.0;
7755:    if(riskNow + riskAdd > riskCeil)           <-- NEVER REACHED
```

With `T_FixedLots = 0.03` these are all dead:
`AutoMaxExposurePct` (25% total cash-at-risk ceiling), `AutoMaxLots()` /
`InpMaxTotalLots` (0.25 total lots), `T_MaxRiskStackMult`, `InpRiskPctPerTrade`,
`LiveRisk()`, `CoordBoost`, `SessionQuality`, `T_HourLearning`, `T_WinLadder`.

The one remaining risk-normaliser in `Open()` is also dead:
```
11330:   double rl = AutoRiskLots(slD);
6688:    if(!T_AutoCalibrate || T_AutoRiskPct <= 0 || slDist <= 0) return 0.0;
613:     input double T_AutoRiskPct = 0.0;
```

**Net: position size is a fixed 0.03–0.04 lots with no relationship to stop
distance, volatility, or equity.** This directly violates the standing rule
"position size derived from stop distance and account equity, never fixed."

Surviving caps:
* `DirExposureFull` (10891), `T_MaxDirLots = 0.30` (2190) — 0.30 lots per
  direction. `T_LotTiersByEquity = false`, so no equity scaling.
* `MarginOkFor` (6993) with `T_MarginFloorPct`.
* `TooManyThisDirection` (10689), `T_MaxSameDirFast = 12` (2714).

Since `InpNoOpposing = false` (line 927 group), `DirectionAllowed()` returns
`true` unconditionally (7829) — **the EA may hold 0.30 lots long and 0.30 lots
short at once**. At gold ~$4500 that is 0.60 lots = 60 oz ≈ $270k notional.
`T_MaxLossPts` on a full 0.30-lot stack is 2.46 pts × 30 ≈ **$74 per side**.
The balance tiers (`T_TierBal1 = 100`, line 3449) imply an account of
£100–150. That is a 50–75% single-episode loss, permitted by design.

### Daily loss and drawdown guards

```
877:  input double InpMaxDailyLossPct  = 40.0;
858:  input bool   InpDailyHaltEnable  = true;
20630:  if(InpDailyHaltEnable && eq <= g_dayStart * (1.0 - InpMaxDailyLossPct/100.0) && !g_halt)
20633:     g_halt = true; ... KillAllPendings();
```
A **40% daily loss limit is not a limit.** And the halt only sets `g_halt`
(which blocks new entries via `WhyNotReady`, 7918) and cancels pending orders.
It **does not flatten open positions**. There is **no max-drawdown guard of any
kind** — no equity high-water mark, no total-drawdown check. For any prop-firm
use this fails outright.

`g_dayStart` is re-seeded on every `OnInit` (9199), so a restart mid-day resets
the daily baseline — a documented anti-pattern.

### Martingale / grid / averaging-down — SEARCHED, and the answer is NO

I searched for size-up-after-loss, recovery lots, grid spacing, and loss-streak
multipliers. Findings:

* `T_WinLadder` (7461) increases size after **consecutive wins**, capped by
  `T_WinLadderMax` — anti-martingale, correct direction.
* `Stat[e].consec` (10170) only ever **pauses** or **disables** after losses
  (10172–10187). `g_tfLossStreak` rests a timeframe. `DriftSizeFrac` (1355)
  cuts size against the drift. `LiveRisk` scales by proven expectancy.
* `T_ScaleAdd` (18420) fires **only inside the micro-lock block**, i.e. after
  the stop is already above entry — pyramiding into a winner with locked risk.
* `ProvePressCheck` (16243) adds size at 60 s **only if the trade has not been
  more than `T_ProveMaxAdverse` £0.30 down** and only if it already has a stop
  (`if(psl <= 0.0) return;`). Adding to a *winner*, not a loser.
* APEX pyramid (18815) is in dead code.

**One exception, and it is dormant.** `DemaTopUp` (6812):
```
6837:   bool ok = (dir > 0) ? trade.Buy(InpTopUpLots, _Symbol, px, 0, 0, "DEMA top-up")
6838:                       : trade.Sell(InpTopUpLots, _Symbol, px, 0, 0, "DEMA top-up");
```
It adds a lot **with SL = 0 and TP = 0**, on a DEMA agreement alone, with **no
check that the position is in profit**. That is averaging down into a losing
position with an unprotected fill. It is gated by `InpDemaTopUp = false` (903)
and `IsNettingAccount()`. **Do not turn it on.** It also leaks a
`GlobalVariable` per ticket (`"TOPUP_" + ticket`) that is only deleted on a
successful bank (6870).

---

## BUGS RANKED BY SEVERITY

**S1 — `LotFor()` early-returns past every aggregate risk ceiling.**
Line 7432 vs 7739/7752. With `T_FixedLots = 0.03` (the shipped default),
`AutoMaxExposurePct`, `InpMaxTotalLots`, `AutoMaxLots()`, `RiskCeilingLots()`
and `T_MaxRiskStackMult` are unreachable. The EA's own comment at 7720–7728
describes these as *"the risk ceiling … what stops the thing you did manually:
opening twelve 0.01 lots."* It does not run.

**S1 — `InpMaxDailyLossPct = 40.0`, and the halt does not flatten.**
Line 877, 20630. A 40% daily stop is not a stop. `g_halt` only blocks new
entries and cancels pendings; open positions ride on. No max-drawdown guard
exists anywhere in the file.

**S1 — A position with no stop loss gets *zero* management.**
```
16352:   double atr = (e == E_TREND) ? Buf(g_scAtr[TrendTFOf(tk)],0,1) : Buf(hAtr[e],0,1);
16353:   if(atr <= 0 || sl == 0) return;
```
This is the **first** guard in `ManagePosition`, before `TrackProgress`,
before `MaxLossCheck`, before `InfantCutCheck`, before `TradeLockCheck`. A
position whose SL is 0 — a `DemaTopUp` fill, a manually opened trade adopted by
magic, a broker-side SL removal, a partial-close edge case — is completely
unmanaged and unbounded. Also, `Buf()` returns 0 on any `CopyBuffer` failure
(6557–6562), so a transient indicator read failure silently skips management
for that tick too.

**S2 — On any non-gold symbol the exit stack dies and the stop floor explodes.**
The file's "point" is one unit of price, explicitly *not* MQL5's `_Point`
(6581–6583). `T_SlFloorPtsAbs = 1.20` (1761) is therefore a **1.20-in-price**
floor. On EURUSD:
```
6621:   want = MathMax(T_SlFloorAtrMult * fatr, T_SlFloorPtsAbs);
```
= `max(2.00 × 0.0006, 1.20)` = **1.20 = 12,000 pips**. Meanwhile
`PS(T_MaxLossPts 3.0)` = 3.0 in price, `PS(T_TargetPts 8.0)` = 8.0 in price —
neither can ever fire. `T_SymAgnosticSize` (2233) fixes only the *lot size*, not
the thresholds. The header's claim #2, *"MULTI-SYMBOL, FOR FREE"* (lines 22–25),
is **false**. This EA is gold-only, whatever the switches say.

**S2 — `TrackProgress` still has the blind-wrap bug the file claims to have
fixed in seven other registries.**
```
8834:   if(g_pCount >= 200) g_pCount = 0;   // recycle the oldest slot
8835:   g_pTicket[g_pCount] = tk;
```
There is no `SlotDead()` check. Slot 0 is overwritten while its position may
still be open. `g_pLast` drives `Stalled()` (8842) which drives the `STALL`
exit (19492), so a live position can inherit another ticket's progress record
and be cut, or become un-cuttable. `UpdatePeakR` (6084) and `TradePeakCash`
(16184) *were* fixed; this one was missed.

**S2 — `CloseTagged` logs "REJECTED, retrying" and never retries.**
```
8811:   bool ok = trade.PositionClose(t);
8812:   PrintFormat("[EXIT %s] ... %s", ..., ok ? "" : " — REJECTED, retrying");
```
There is no retry loop. A rejected close (requote, off-quotes) is logged as if
it will be retried and is simply dropped until the next tick happens to
re-evaluate the same branch — which for peak-anchored exits it may not, because
the peak has moved. `Open()` (11404) and `ModifySLTP()` (6972) both retry
properly; this one does not. Same class as the bug the file fixed at v17.33.

**S2 — No state survives a restart.**
`g_qspPeak` (peak/MFE), `g_pkR` (PeakR), `g_tlPk` (TRADE-LOCK), `g_bskPeak`
(BASKET-LOCK), `g_pPeak` (progress), `g_legDone`, `g_prTk`, `RDistOf`,
`RiskOf`, `SnapshotEntry` are all plain in-memory globals. Only the hour-of-day
learning persists via `GlobalVariable` (9085, 9324). On restart:
`QSP_TrackLive` (19926) re-seeds each open position's peak to the **current**
P/L, so a trade that peaked at +5 and is now at +1 is recorded as peaking at +1
and TRADE-LOCK/GIVEBACK will not act. `ClockFromComment()` (6028) self-heals
the timeframe registry from `POSITION_COMMENT`, which is genuinely good — but
nothing else does.

**S3 — Hedged books break the basket arithmetic.**
`InpNoOpposing = false` → `DirectionAllowed` always true (7829). `LedgerBasket`
(9477–9485) and `BasketGivebackGuard` (20473–20482) sum `POSITION_PROFIT`
across **both directions**. A hedged book nets toward zero, so `g_bskPeak`
never arms; conversely a peak recorded while hedged can be "given back" purely
by the hedge unwinding. BASKET-LOCK then closes **everything**, both sides.

**S3 — `MAX-HOLD` reads the engine timeframe, not the trade's.**
```
19501:   if(e != E_APEX && (TimeCurrent() - ot) > (long)Cfg[e].maxHold * PeriodSeconds(stallTf))
19506:      ENUM_TIMEFRAMES hTf = Cfg[e].tf;      // = PERIOD_M5 for TREND (line 9116)
19507:      int holdMins = ... (hTf == PERIOD_M5) ? T_HoldMinsM5 ...   // = 360
```
`Cfg[E_TREND].tf` is hardcoded `PERIOD_M5`, so **every** TREND trade — M1
included — is given the 360-minute M5 horizon, while the outer gate uses the
trade's own clock. `T_HoldMinsM1 = 50` is unreachable for TREND positions.

**S3 — `IsHtfCloseTag` uses substring matching on the tag.**
```
8345:   return (StringFind(t, "H1-FLIP") >= 0 || StringFind(t, "HTF") >= 0
8346:        || StringFind(t, "H1") >= 0 || StringFind(t, "H4") >= 0
8347:        || StringFind(t, "M15") >= 0 || StringFind(t, "LOCKDOWN") >= 0);
```
Any future tag containing "H1"/"H4"/"M15" as a substring will be silently
vetoed by `T_HtfNeverCloses`. Latent, not currently triggered.

**S3 — `Sleep()` inside the tick path.**
6988 (`ModifySLTP`) and 11456 (`Open`). `T_OrderRetryMs` × `T_OrderRetryN`
blocks `OnTick`. Live, this delays every other position's management.

**S4 — Supertrend chain is re-seeded from scratch every bar.**
```
8877:   if(i == bars - 1) { up = bUp; dn = bDn; d = (cl >= mid) ? 1 : -1; }
```
(also 14563). The chain is rebuilt over `T_StWarmupBars = 1000` bars each new
bar and the direction is seeded from close-vs-basis at bar 1000. If no flip
occurs inside the window the seed persists to the live bar. As the window
slides, the same historical bar can produce a different `dir` on different
bars. Not repainting in the classic sense, but it is a non-deterministic
signal: the current direction depends on where the window happens to start. It
also costs 1000 iterations × 3 clocks × per bar.

**S4 — `PtsScale()` reads M1 ATR for every clock.** (4665–4674, acknowledged at
6634–6638.) An M5 trade's thresholds are keyed to M1 volatility.

**S4 — `Guardian` reads `profitRAdj` but `UpdatePeakR` runs later.** Guardian is
called at 16720; `UpdatePeakR(tk, profitR)` is at 16773. Guardian's peak-relative
gates therefore see the previous tick's peak.

**Not a bug, but worth stating:** I found **no** look-ahead. All indicator and
candle reads outside `EarlyFlipForming` use shift ≥ 1. The only shift-0 reads
are at 12782 (the both-sides-pierced spike test, deliberate) and in the panel
drawing code.

---

## THE PARAMETER PROBLEM

748 `input` declarations; 712 unique names after de-duplication.

**Structurally orphaned (declared, never referenced in code):** 19 —
`AU_ReportEvery`, `InpBalance`, `InpBrokerGmtOffset`, `InpM15MinBalance`,
`InpMinBalanceToTrade`, `T_AtrSpikeMult`, `T_DeferChaseOLD`, `T_FailoverMinER`,
`T_FailoverSymbols`, `T_FlatBeforeClose`, `T_FlatBeforeCloseMin`,
`T_GoldSlowER`, `T_PullDepth`, `T_PullMaxBars`, `T_SlBuf`, `T_SlMax`,
`T_SlMin`, `T_TrailGivebackFrac`, `T_UseFailover`. (Matches the file's own
v19.13 count.)

**Effectively dead by default — far larger than 19:**

| Cause | Line | Kills |
|---|---|---|
| `InpUseScalp = false` | 1654 | every `SC_*` input, `Engine_Scalp`, the E_SCALP exit branch |
| `InpUseApex = false` | 1655 | every `A_*` and pyramid input, `Engine_Apex`, APEX-HEALTH |
| `T_FixedLots = 0.03` | 3507 | ~30 sizing inputs (see S1) |
| `T_AutoRiskPct = 0.0` | 613 | `AutoRiskLots` and its callers |
| `T_SkipM3 = true` | 4026 | the M3 clock |
| `T_PineParity = true` | 4067 | MICRO-BREAKOUT, REVERSAL, PULLBACK inputs |
| `T_TakeEveryPine = true` + `T_AnchorMode = 1` | 4066, 4049 | the whole anchor-guard family |
| `T_BanksOff = true` | 8145 | LEG-TARGET, EXHAUSTION, CHOP-STALL, MOM-STALL inputs |
| `T_HtfNeverCloses = true` | 8298 | the H1/H4/M15 exit family |
| `G_ExitOnHtfFlip = false`, `N_CloseOpen = false`, `T_BasketGiveback = false`, `InpDemaTopUp = false`, `InpMultiSymbolCap = false`, `InpReadPineFile = false`, `InpWatchManual = false`, `InpAutoDisable = false` | various | their entire families |

53 boolean inputs ship `false`. My conservative estimate is that **fewer than
120 of 748 inputs can change behaviour on the shipped defaults**, and fewer
than 40 have a first-order effect.

The parameters with the **largest effect**, ranked by what they actually do to
the P&L distribution:

1. `T_TradeLockGivePct = 0.40` (4707) — the operative exit rule.
2. `T_NoiseFloorAtr = 0.60` (4011) — the unit under every arm and every allowance.
3. `T_MicroLockR = 0.70` / `T_BeArmPoints = 0.40` (3138, 3143) — the BE arm.
4. `T_SlFloorAtrMult = 2.00` (1743) — sets R, and therefore every R-keyed threshold.
5. `T_MaxLossPts = 3.0` (8459) — fires before the stop; the real stop.
6. `T_TargetPts = 8.0` (8458) — the hard ceiling on every winner.
7. `T_StMultiplier = 1.2` (3647) — signal frequency.
8. `T_FixedLots = 0.03` (3507) — size, and the switch that kills the risk model.
9. `T_MinWinnerExitPts = 6.0` (8328) + `T_PeakGateFrac = 0.35` (8213).
10. `T_TrailRoomAtr = 1.30` (4156).

### The minimum viable 20

If the strategy were rebuilt honestly (and it should not be rebuilt at all
until it passes `study.py`), these are the only twenty knobs it needs. Every
one has a first-order effect and none is derivable from the others.

**Signal (4)**
1. `Timeframe` — entry clock. Must move off M1; see cost/risk below.
2. `T_StAtrLen` — Supertrend ATR length.
3. `T_StMultiplier` — Supertrend multiplier.
4. `UseEarlyFlip` (bool) — intrabar vs closed-bar signal. Default **false**.

**Risk (5)**
5. `RiskPctPerTrade` — the only sizing input. Lots = f(risk %, stop distance, tick value).
6. `StopAtrMult` — stop distance in ATR. Sets R.
7. `MaxOpenPositions`.
8. `MaxDailyLossPct` — real number, ≤ 3%, and it must **flatten**, not just halt.
9. `MaxDrawdownPct` — high-water-mark guard. Does not exist today.

**Exit (5)**
10. `TargetR` — fixed R target (the experiment's winner on gold).
11. `MaxHoldBars` — time exit. The data says ~42 min, not 4.
12. `TrailAfterR` — trail arms *only* above this; set well above 1R or 0 = off.
13. `TrailAtrMult` — trail standoff.
14. `UseBreakEven` (bool) — default **false**, per `06_exit_experiment.md`.

**Execution (4)**
15. `MaxSpread` — expressed as a fraction of the stop distance, not absolute.
16. `SlippagePoints`.
17. `MagicNumber`.
18. `OrderRetryN`.

**Housekeeping (2)**
19. `DemoOnly` (bool, default **true**) — see below.
20. `VerboseLog`.

Everything else in the current 748 is either dead, a duplicate of one of these,
or a mechanism that exists to undo the damage of another mechanism.

---

## WHAT TO SALVAGE

**Genuinely good and worth porting:**

* **`NoiseFloorPts()` (6712) as a *diagnostic*, not a threshold.** The idea that
  a bank or a stop inside `spread + 0.6 × ATR` is sampling noise is correct and
  well expressed. Use it to *reject markets/timeframes* where the target move is
  under ~4 bands, not to floor a giveback.
* **`EfficiencyRatio()` (11544).** Correct Kaufman ER — `|close[1] −
  close[1+n]| / Σ|close[i] − close[i+1]|`, all closed bars, guarded against
  division by zero. Clean. The v19.09 idea of sizing on measured ER rather than
  the clock is sound.
* **`ChoppinessIndex()` (11590).** Correct Dreiss formula, neutral fallback on
  bad data.
* **The MAE / give-up instrumentation.** `QSP_TrackLive` (19893) tracks
  per-ticket MFE in points every tick with proper slot recycling and a
  full-table warning. `QSP_TagRecord` / `QSP_Recompute` (8240, 20049) produce a
  per-exit-tag ledger of *points taken vs peak offered*, and — the key part —
  it records **suppressed** attempts as `~TAG` (8811, 8636, 8763, 8779) so the
  cost of every veto is visible. That is honest quant work and it is the single
  most valuable artefact in the file. Port it wholesale.
* **`TicketProfitR` / `RDistOf` / `StoreRDist` (8368, 6446).** Per-ticket R
  stored at entry and reconstructible from `|entry − sl|` on restart. Correct.
* **`ClockFromComment()` (6028).** Recovering per-position state from
  `POSITION_COMMENT` so the registry self-heals across restarts. Excellent
  pattern; generalise it.
* **The order-send retry classifier (11404–11455).** The distinction between
  unambiguous retcodes (REQUOTE, PRICE_CHANGED) and ambiguous ones (TIMEOUT,
  CONNECTION), with a duplicate-position check before retrying an ambiguous
  one, is better than most production EAs. Keep verbatim.
* **`SYMBOL_FILLING_MODE` negotiation (9194–9197).** Correct.
* **`#define EA_BUILD` printed at `OnInit`.** Keep the habit.
* **`LiveMarginWatch()` (20530).** "If one more noise band against the book puts
  free margin below zero, we choose the exit rather than the broker." Right
  idea, right implementation, closes one position per pass.
* **The rejection counters** — `g_anchorBlocked`, `g_parityBlocked`,
  `g_pathN[]`, `AuditSkip`/`UpdateShadows` (12062, 12092) which track what the
  *skipped* signals would have made. Also good.

**The Pine scripts contain the better idea.** `LiquidityEngine_v2.pine`
lines 136–143 state the cost-to-risk framing plainly and cite a 7-year,
2.55M-bar negative result on the naive version of its own strategy. That
intellectual honesty is worth more than the entire MQL5 file. `XAUUSD_CLEAN_3.5`
line 44: *"NOTHING HERE IS COMPILED OR BACKTESTED … The levels are real; the
edge is unproven."*

**Do not salvage:** the exit stack, the hold-vote quorum, the 32 tags, the
grace/arbiter/floor chokepoint machinery, or any of the eight peak-anchored
guards. They are a record of nineteen rounds of patching one arithmetic
problem, and the arithmetic problem is upstream of all of them.

---

## WHAT I COULD NOT VERIFY WITHOUT MT5

I cannot compile this file or run the strategy tester. Specifically unverified:

1. **It may not compile.** 20,695 lines with heavy forward-declaration
   juggling (the file itself notes "fifth signature/order trap this session",
   16333). I did not check every declaration-before-use.
2. **All ATR-derived arithmetic above uses M1 gold ATR ≈ 1.47 and spread ≈
   0.30**, taken from the file's own v19.14 calibration note (line 1741). If
   the broker's real ATR or spread differs, every threshold table in this audit
   shifts. The *ratios* (arm ≥ 1 band, giveback ≥ 1 band) do not shift — those
   are structural.
3. **`LossPerLot` / `g_tickVal`.** I assumed a 100-oz gold contract
   (`SYMBOL_TRADE_TICK_VALUE` 1.0 at tick size 0.01 → 0.01 lots = 1 ccy per
   point of price), consistent with the comment at 6581. Not confirmed against
   a real symbol spec. **A broker screenshot of the gold contract spec is still
   the missing input** (the inbox README asks for it).
4. **Whether `T_TargetPts` or the peak locks fire first in practice.** My
   ordering claim (TRADE-LOCK wins because it is a market close and the trail
   is a resting stop) is a reading of the code, not a measurement.
5. **Actual fill/slippage behaviour**, requote rates, and whether
   `ORDER_FILLING_FOK` is what the broker really grants.
6. **Whether the Supertrend re-seeding (S4) actually flips direction in
   practice.** With `T_StWarmupBars = 1000` it is probably rare, but it needs a
   tester run comparing `dir` across consecutive bars to confirm.
7. **CPU cost.** Three Supertrend chains × 1000 iterations rebuilt per bar,
   plus `PositionsTotal()` loops in `QSP_TrackLive`, `LedgerBasket`,
   `LiveMarginWatch`, `OpenRiskCash`, `OpenLotsThisDir` and `ManageEngine` ×3 —
   all on **every tick**. On gold at London open this may be too slow. Unmeasured.
8. **The panel/`ObjectCreate` code (20011–20460)** was skimmed, not audited.

---

## RECOMMENDATION

Unchanged from `AUDIT_v19_18.md`, and now with mechanism rather than inference:
**do not run this live.** Two additions to that recommendation:

1. **If it is ever put on a demo account for instrumentation**, add a demo
   guard first. There is none in the file — no `ACCOUNT_TRADE_MODE` check
   anywhere. Per the standing rule, every new or adopted EA defaults to
   demo-only until Veer explicitly removes it:
   ```
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   { Print("DEMO ONLY — refusing to attach to a live account."); return INIT_FAILED; }
   ```
2. **The salvage list above is the deliverable**, not the EA. Port
   `QSP_TrackLive` + `QSP_TagRecord`, `EfficiencyRatio`, `ChoppinessIndex`,
   `NoiseFloorPts`, `ClockFromComment` and the order-retry classifier into the
   rebuild. Leave the other 20,000 lines here.

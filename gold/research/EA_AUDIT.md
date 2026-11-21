# EA AUDIT — XAUUSD_QUAD_v19_04.mq5 (19,662 lines, 715 input lines)
Verified against source. Several HANDOVER CLAIMS ARE WRONG — corrected here.

## Handover claims REFUTED
| Claim | Reality |
|---|---|
| "the only Open() call is Open(E_TREND,...)" | **SIX** Open() sites across 3 engines (13572, 13751, 17809 TREND; 14219 SCALP; 14417/14427 APEX). The in-file comment at 18147-18149 is false. SCALP is dead by the ENGINE GATE (`Cfg[E_SCALP].on=false`), not by call-site absence. |
| "25 call sites for trade.PositionClose()" | **ONE**, at 8159 inside `CloseTagged`. Comments at 7484 / 8120-8123 are false. 5 partial-close sites. |
| "no clamp on stop distance at all" | Clamps DO exist. T_SlMin/T_SlMax are genuinely dead (declared, never read), but the real stop is `max(signal-line dist, 1.40xATR_M1, 1.20pt, 3xspread)` via `FloorStopAtBirth` (6067), then capped by `CapStopToCash` (6237), then `ClampStops` broker min. |
| "~15 unguarded iHighest/iLowest -1 sites" | **0 in live code.** `SafeHighest/SafeLowest` (5988) used at 14 sites; 13 of 15 raw sites explicitly guarded; the 2 unguarded are in `RecentSweep`, reachable only from dead Engine_Scalp. |
| "Supertrend rebuilt from 150 vs 120 bar windows" | Both now identical: `MathMax(50, T_StWarmupBars)` = **1000** (8217, 13795). Fixed in v18.88. Stale comments remain at 1205 / 8212 / 13794. |
| "margin only checked before sending an order" | `LiveMarginWatch()` (19497) runs EVERY tick from OnTick (19552) and closes the worst position. ACCOUNT_MARGIN_LEVEL is indeed unused, but a live margin check exists. |
| "19 dead inputs + 5 read only in dead code" | 19 never-read VERIFIED. But **>=49** (not 5) are read ONLY in unreachable code — lower bound. |
| "every discretionary exit evaluated before the stop moves" | False both ways: Guardian's SL pull-in (15319) precedes 16 discretionary exits; STALL (18473) and MAX-HOLD (18501) are evaluated AFTER the main trail write (18466). |

## Handover claims VERIFIED
- Engines: `InpUseTrend=true`, `InpUseScalp=false`, `InpUseApex=false`. SCALP branch 18027-18301 = **275 dead lines**.
- `T_BanksOff=true` suppresses 8 BANK tags; 3 are exempted (PEAK-BANK, SPIKE-PEAK, SMALL-MOVE), so **5 are actually suppressed with NO individual off-switch**: LEG-TARGET, EXHAUSTION, RANGE-SCALP, CHOP-STALL, MOM-STALL.
- `LotFor()` returns at 6791 inside `if(T_FixedLots > 0.0)` (default 0.03), so everything 6792-7136 is unreachable: session/hour/win-ladder/confidence/regime multipliers AND the AutoMaxExposurePct risk ceiling.
- `#property version "19.04"` and `EA_BUILD "v19.04"` AGREE.

## NEW DEFECTS FOUND (not in the handover)
1. **Pyramid adds fill at 3x intended size.** `g_forceLots` (the exact-size override for top-ups, set at 17805 to T_PyramidLots=0.01 / T_PyramidT3Lots=0.02) is read at 6860 — BELOW LotFor's 6791 return. So every pyramid add fills at **0.03**, not 0.01/0.02. The comment at 6857 claiming it "passes through every ceiling below" describes code that never runs.
2. **Cash stop cap is 3x too loose.** `CapStopToCash(..., SYMBOL_VOLUME_MIN)` at 13438/13619 sizes the budget for 0.01 lots while the fill is 0.03 → `T_MaxStopRiskPct = 8.0%` behaves as **~24% of equity**.
3. **The emergency-stop rescue can never run.** `if(sl == 0)` at 18365 is unreachable because 15389 already did `if(atr <= 0 || sl == 0) return;` and `sl` is never reassigned in between. A naked position is silently abandoned, not rescued.
4. **T_GivebackAtrFloor is nullified by T_GivebackPeakCap.** Floor applied at 16507, cap at 16583 — cap always wins. With R ~= 1.40xATR, floorR ~= 0.714R vs cap 0.50xpeakR, so across the whole 0.3R-1.43R band (where nearly every trade lives) the ATR floor has **no effect**.
5. **T_MinFillGapSecs = 0** renders the double-fill lockout at 10448 inert at defaults, despite the comment calling it "the one shared door every entry passes through".
6. **Order paths that bypass the stacking guards:** `DemaTopUp` (6283/6284) bypasses ALL seven guards and MarginOkFor — dormant only because `InpDemaTopUp=false`. `scale-add` (17447) has DirExposureFull + MarginOkFor only, bypassing DuplicateFill, dup-cluster, ChasingTheExtreme, DirectionUnderwater, TooManyThisDirection, fill-gap.
7. No pending-order code exists anywhere (no OrderSend/BuyStop/etc), so comments at 8977 and 15153 about pendings bypassing Open() are stale.

## Exit evaluation order per tick (TREND) — for any future exit work
OnTick: BASKET-LOCK -> MARGIN-WATCH -> BASKET-GIVEBACK -> ManagePosition:
MAX-LOSS, FRI-FLAT, Guardian(SPREAD-PANIC, H1-FLIP, THESIS-DEAD, **SL pull-in**), partial,
GAP-AGAINST, LEG-TARGET, SPIKE-PEAK, EXHAUSTION, EARLY-FAIL, STRUCT-BREAK, RANGE-SCALP,
SMALL-MOVE, CHOP-STALL, PEAK-BANK, MOM-STALL, GIVEBACK, CHOP-CLUSTER, STACK-BANK, trim,
FLIP-CLOSE, **MAIN SL WRITE**, STALL, MAX-HOLD -> NEWS-FLAT.
23 ordered stages. Fixing one promotes the next-tightest — which is why single fixes never moved the outcome.

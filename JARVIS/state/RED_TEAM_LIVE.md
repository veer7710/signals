# RED TEAM — SuperTrendSniper 2.22 on a LIVE £60 PU Prime XAUUSD M1 account

**DO NOT DEPLOY TODAY.** The EA as shipped does not fail because the edge is
weak. It fails because three of its own default settings are arithmetically
incompatible with a £60 balance at the 0.01-lot floor, and the failure is
measurable, reproducible and near-certain inside the first trading day.

Audited: `JARVIS/ea/build/SuperTrendSniper.mq5` (build 2.22, 3893 lines),
branch `claude/trading-ea-pine-scripts-xv4m8q`, 2026-09-04.

Every number below was computed, not estimated. Scripts and method are named
per finding. **All price evidence is GOLD 15m and 1h — `data/` contains no M1
file of any kind (`EURUSD/GBPUSD/GOLD/US500 × 15m,1h` only). Nothing here has
ever been measured on the timeframe this EA is being sent to trade.**

Constants used throughout: 0.01 lots = **£0.787/point** (E-081, cannot be
smaller); gold = **$4491.80** (last bar in `data/GOLD_15m.json`); GBPUSD 1.27;
M1 ATR(7) ≈ **2.2 points** (E-081's own scaling), so `InpStopAtrMult = 2.0`
gives a **4.40-point stop = £3.46 = 5.77% of £60**.

---

## 1. THE BASKET GIVE-BACK ARMS AT £0.25 AND TURNS THE EA INTO A SCRATCH MACHINE
### This is E-083 reproduced exactly, in the one rule E-083's fix never touched.

**Evidence — `SuperTrendSniper.mq5:3275`:**
```cpp
double arm = MathMin(MathMax(eq * InpBasketArmPct / 100.0, 0.25),
                     InpBasketMinMoney);
```
On £60: `max(60 × 0.004, 0.25) = 0.25`, `min(0.25, 1.00)` = **£0.25**.
`InpBasketGiveBack = 0.20`, so `ProtectBasket` closes everything the moment
floating profit falls to `peak × 0.80`. From a £0.25 peak that trigger is
**£0.05 = 0.064 gold points** — smaller than one spread, checked on **every
tick** (`OnTick:3877`). There is **no R term anywhere in this rule**: it is a
pure money threshold, and E-083's verdict was *"A money threshold does not
survive a change of timeframe or of lot size."* The give-back and the
per-position lock were fixed to be R-first with money as a floor
(`LockPositions:3178`). `ProtectBasket` was not.

**Measured, GOLD 15m real bars, shipped exit stack, 0.01 lots, £60 equity**
(`JARVIS/research/rt_live_basket.py`, derived from `JARVIS/research/small_account.py`):

| config | n | win% | mean R | avg win | avg loss | exits |
|---|---|---|---|---|---|---|
| A. no basket, no daily guard — **what EXPERIMENTS.md measured** | 107 | 48.6% | +0.158 | +£17.94 | −£11.39 | stop 100, timecap 7 |
| B. **+ InpUseBasket as shipped** | 156 | **94.2%** | +0.199 | **+£3.72** | −£13.03 | **basket 147**, stop 9 |
| C. **+ InpDailyLossPct=3 as shipped** | 159 | 34.0% | **+0.033** | +£4.47 | −£1.80 | dailyguard 105, basket 54 |

Row B is E-083's signature verbatim: *"93.1% win rate — and the wins were
+0.013R scratches."* **147 of 156 trades are closed by the basket rule.** The
result is not sensitive to the intrabar assumption: checking the give-back on
bar close only still gives 94.2% win rate and 142/156 basket exits.

**Consequence in pounds:** the winning tail that produces the entire measured
expectancy is amputated. Average win collapses from £17.94 to £3.72 while the
average loss stays at £13.03. On M1, where 1R is only £3.46, £0.25 is 0.072R —
E-075 measured arming at 1R as +0.136R against +0.368R at 3R; 0.072R is off the
bottom of that dial entirely.

**Fix:** `InpUseBasket = false` for any single-position account, or gate the
basket arm on R exactly as the give-back was fixed
(`peakR >= InpGbArmR` AND money as a floor). Do not "tune" `InpBasketArmPct`
— on a £60 account the `0.25` hard floor inside the `MathMax` dominates and no
input value can lift it.

---

## 2. THE DAILY-LOSS GUARD IS SMALLER THAN ONE STOP LOSS
### Every losing trade is cut at half its stop, and then the day is over.

`InpDailyLossPct = 3.0` (`:512`) on £60 = **£1.80 = 2.29 gold points**.
The stop is **4.40 points = £3.46**. `CheckGuardsTick` (`:3341`) runs on every
tick against `ACCOUNT_EQUITY`, i.e. **floating** P/L, and flattens
(`InpFlattenOnBreach = true`, `:516`).

So the guard fires at **52% of the way to the stop** and then locks out the
rest of the day. Measured on real bars (`JARVIS/research/rt_live_mae.py`, MAE per trade):

```
MAE reaches -0.30R on  85/112 = 75.9% of trades
MAE reaches -0.52R on  72/112 = 64.3% of trades   <-- the guard threshold
```

**64.3% of all trades touch the guard before they resolve** — and that is
measured on 15m *bar lows*, which understate the true excursion of a tick-level
check on M1.

This is E-091 in a new costume. E-091 measured every tight brake and found
*"never green, 0.55 of stop against"* costs **−682 to −779 points**. The daily
guard is that exact brake, applied at 0.52 of stop, plus it stops trading.

**Consequence in pounds:** the trade the EA was measured on no longer exists.
Row D of the table above — daily guard alone, basket off — is **10.1% win rate,
mean +0.019R**, with 141 of 158 exits taken by the guard.

**Fix:** the guard must be wider than one stop. `InpDailyLossPct` must be at
least `100 × 2 × 3.46 / 60 = 11.5%` for two stops of headroom on £60, or the
account must be large enough that 3% > 2 stops, which is **£231**.

---

## 3. THE PERMANENT MAX-DRAWDOWN LOCK BRICKS THE EA IN THE FIRST DAY OR TWO
### P(permanent lock within 9 days) = 97.5%–100%. P(reaching £260) = 0.00%.

`InpMaxDDPct = 6.0` (`:513`) on £60 = **£3.60**. One full stop is **£3.46 =
96% of the entire lifetime drawdown budget.** At the cost-floor stop width
(5.45 points at a 0.46 spread) one stop is **£4.29 = 119% of the budget** —
a single loss locks the account permanently.

Worse: the peak is taken from **floating** equity, `OnTick:3835`
```cpp
double eq = AccountInfoDouble(ACCOUNT_EQUITY);
if(eq > g_peakEq) g_peakEq = eq;
```
A trade that merely floats +£2.00 and scratches back to breakeven moves the
lock threshold to £58.28, leaving **£1.72 of budget — less than one daily-guard
hit (£1.80).** The next guard flatten ends the EA permanently. `g_lockedPerm`
persists to a terminal global variable (`LoadGuards:1093`) and can only be
cleared by hand, so an unattended EA bricks itself silently while Veer is at
work.

**Monte Carlo, 20,000 runs** (`JARVIS/research/rt_live_account.py`; £60, fixed 0.01 lots, 9
trading days, R and MAE block-resampled from the shipped stack's own trades,
peak taken on **realised** equity only — i.e. deliberately optimistic):

```
GUARDS ON, as shipped
 stop pts risk GBP risk% trades/day median  5th  95th  P(>=260) P(perm lock) P(end<60) avg trades
    2.72    2.14   3.6%       6      58.87 54.76 78.27    0.00%      98.2%     56.8%      12.5
    4.40    3.46   5.8%       6      58.20 54.76 75.73    0.00%      99.8%     63.5%       9.0
    5.45    4.29   7.1%       6      58.20 54.76 72.48    0.00%     100.0%     55.3%       7.9

GUARDS OFF (hypothetical, both set to 100)
    4.40    3.46   5.8%       6      72.70 41.50 114.07   0.00%       0.0%     28.4%      31.3
    5.45    4.29   7.1%      12      88.96 35.92 165.85   0.07%       0.0%     21.3%      51.2

At E-089's honest M1 expectancy (+0.041R):
    4.40                      6      58.20                0.00%     100.0%     69.4%
```

**Median outcome as shipped: £58.20 after an average of 9 trades, then dead.**
**P(£260) = 0.00% in every single configuration tested, guards on or off.**

**Fix:** `InpMaxDDPct` must exceed several stops. On £60 that means ≥ 20%, which
means the guard is no longer a guard. The honest reading is E-096's: **the
account is too small**, and the threshold it named was £100.

---

## 4. `LotFor()` SILENTLY SIZES 11.5× THE CONFIGURED RISK
**Evidence — `LotFor():1441–1474`, final line:**
```cpp
lots = MathMax(minL, MathMin(maxL, lots));
```
At `InpRiskPct = 0.50` (`:346`) on £60, `riskCash = £0.30`. `lossPerLot` for a
4.40-point stop = `4.40 × £78.70 = £346.28`. `lots = 0.30 / 346.28 = 0.00087`.
`MathFloor(0.00087 / 0.01) × 0.01 = 0.00`, then `MathMax(0.01, 0.00)` = **0.01**.

The EA computes it should trade **1/11.5 of the minimum lot**, sends the
minimum, and **prints nothing**. Actual risk is **£3.46 = 5.77% of equity**
against a configured 0.5%. E-098 records that `LiquiditySniper`'s `BookLots()`
was changed to *"warn rather than silently rounding"* for exactly this reason.
**That fix was never carried into `SuperTrendSniper`.**

Compounding it, `TryEntry:1705`:
```cpp
// The broker's floor. Widen to it and let LotFor re-derive the size, so
// the risk in money is unchanged and only the distance moves.
```
**This comment is false on this account.** `LotFor` is at its floor, so
widening the stop from 2.72 to 5.45 points raises money risk from £2.14 to
£4.29 with no offsetting size reduction. The same is true of the cost floor at
`:1690`. Every widening rule in the EA is a risk *increase* at 0.01 lots.

**Fix:** `LotFor` must `Print` a named warning whenever the clamp binds, and
`TryEntry` must refuse the trade when `stopDist × pointValue × minLot` exceeds
`InpRiskPct` of equity by more than some factor.

---

## 5. £60 → £260 IS ARITHMETICALLY UNREACHABLE AT 0.01 LOTS — BEFORE ANY RISK ARGUMENT
£200 of profit at £0.787/point = **254.1 net gold points**. Note also that from
Friday 2026-09-04 to Friday 2026-09-11 there are **5 trading days, not 9**:

| horizon | points/day needed | £/day | compounded daily return |
|---|---|---|---|
| 5 days | 50.8 | £40.00 | **34.1%/day** |
| 9 days | 28.2 | £22.22 | **17.7%/day** |

`InpMaxTradesDay = 20` (`:514`) caps the whole attempt at 180 trades over 9
days. Expected profit at that ceiling, guards ignored entirely:

```
15m measured +0.158R, stop 4.40 pts : +£98.42  -> end £158.42
15m measured +0.158R, stop 2.72 pts : +£60.84  -> end £120.84
E-089 M1     +0.041R, stop 4.40 pts : +£25.56  -> end  £85.56
E-089 M1     +0.041R, stop 2.72 pts : +£15.80  -> end  £75.80
```

**The EA's own trade cap makes £260 impossible even if every guard is removed
and the optimistic 15m expectancy holds on M1.** The target is not aggressive;
it is outside the reachable set. Reaching it needs 0.03 lots or better, which
at a 4.40-point stop is £10.39 per trade = **17.3% of £60** — a two-loss account.

---

## 6. THE GUARD-BREACH FLATTEN NEVER RETRIES, AND FAILS SILENTLY
**Evidence — `CheckGuardsTick:3368–3382`:**
```cpp
if(!hit) return;
Log(why);
PersistGuards();
if(!InpFlattenOnBreach) return;
for(int i = PositionsTotal() - 1; i >= 0; i--)
{
   ...
   if(trade.PositionClose(tk))
      Log("closed on guard breach: " + IntegerToString((int)tk));
}
```
`hit` is true **only on the tick the lock first trips**. On every subsequent
tick both locks are already set, so `hit` is false and the function returns
before the loop. If `PositionClose` fails once — requote, off-quotes, trade
context busy, momentary disconnect, which is exactly what happens during the
news spike that caused the breach — **the position is never closed and never
attempted again**, and there is **no `else` branch**, so nothing is written to
the log or the journal.

Contrast `ProtectPositions:3130`, which does this correctly:
```cpp
if(!ok) Log(StringFormat("give-back %s REJECTED, retcode %d - will retry", ...));
```

**Consequence in pounds:** the guard promises to cap the day at £1.80; on a
failed close the trade runs to £3.46 or, through a news gap, further, while the
EA is permanently locked and reports itself as flat.

**Fix:** move the flatten loop outside the `if(!hit)` gate — retry on every
tick while `(g_lockedDay || g_lockedPerm)` and a magic-matching position exists
— and log every failed close with its retcode.

---

## 7. THE NIGHTLY GOLD ROLLOVER BREACHES THE DAILY GUARD WITH NO PRICE MOVEMENT
Floating P/L on a long is marked against the **bid**. Gold spreads on a retail
feed routinely go from ~0.30 to 2–5 points across the 22:00–01:00 server
rollover. With one 0.01-lot position open and price completely unchanged:

```
spread 0.30 -> 1.00 : floating P/L drops £0.55
spread 0.30 -> 2.00 : floating P/L drops £1.34
spread 0.30 -> 3.00 : floating P/L drops £2.12   BREACH (budget £1.80)
spread 0.30 -> 5.00 : floating P/L drops £3.70   BREACH
```

The EA then flattens **at that widened spread** (finding 6's loop), paying the
blowout on the way out. `DisasterBrake` (`:2910`) fires on the same event
(`spNow > 3 × spAvg`) and closes for the same reason at the same price. The
`RiskAllowsEntry` spread gate at `:1431` prevents *new* entries but does
nothing for an open one.

**Fix:** a session filter that keeps the EA flat across rollover
(`InpUseSession = true`, `:279`, is available and off), or exclude the widening
of the spread from the guard's equity measurement by computing floating P/L at
the mid.

---

## 8. `InpMaxSpreadAtr = 0.15` SILENCES THE EA ON M1 AT VEER'S OWN MEASURED SPREAD
`RiskAllowsEntry:1431` refuses every entry when `spread > 0.15 × ATR`. On M1,
ATR(7) ≈ 2.2 points, so the ceiling is **0.33 points**. E-089 records Veer's own
terminal at a **0.46** spread. At that spread **the EA takes zero trades and
prints only skip lines.** Unattended, this looks identical to "no signals".

This is the same class of defect the code itself documents at `:419`:
*"0.10 WAS A BUG AND IT SILENCED THE EA."* The fix was applied to
`InpMaxCostFrac` and not to `InpMaxSpreadAtr`.

**Fix:** before deploying, read the actual PU Prime XAUUSD spread on M1 across a
full session and set the ceiling from it, or delete the gate — `InpUseCostGate`
already covers blown-out spreads on a better metric.

---

## 9. THERE IS NO BROKER-SIDE TAKE PROFIT, AND `InpTpAtLevel` IS DEAD CODE
`TryEntry:1841`:
```cpp
double tp = (InpTargetR <= 0.0) ? 0.0 : NormalizeDouble(ask + InpTargetR * stopDist, dg);
```
`InpTargetR = 0.0` (`:197`), so `tp` is always 0. The level-target block that
follows is guarded by `if(tp > 0.0 && capped > ask && capped < tp)` (`:1851`,
and `:1910` for shorts) — **it can never execute.** `InpTpAtLevel = true`
(`:310`) is a no-op, and E-087's shipped-on-by-default level target
(*"+563 points, average win +3.21R"*) **is not running.**

Separately, this means the only broker-side order on the position is the stop.
Every profitable exit — trail, give-back, basket, stall, bar cap — requires
`OnTick` to fire. `OnTimer` (`:3758`) only calls `Readout()` and `DrawBox()`.
A VPS or feed outage therefore leaves a position with downside protection and
no upside management.

**Fix:** either set `InpTargetR` > 0 so the level cap can bind, or move the
level target into the `tp == 0` branch. This one is free money left on the
floor and should be fixed regardless of the deploy decision.

---

## 10. THE EVIDENCE BASE DOES NOT SUPPORT THE STRATEGY, LET ALONE THE TARGET
- **No M1 data exists anywhere in this repository.** `data/` holds 15m and 1h
  only. The EA is for M1. Every number in EXPERIMENTS.md is an extrapolation.
- **The 15m sample is 10 weeks**: 2026-06-22 to 2026-08-31, gold 4193 → 4492.
- **The shorts do not work.** Shipped stack, same entries:
```
GOLD 15m  LONG  n= 57 mean=+0.290R t=+2.03   SHORT n= 50 mean=+0.007R t=+0.04
GOLD 1h   LONG  n=229 mean=+0.128R t=+1.74   SHORT n=136 mean=+0.041R t=+0.37
```
  The 1h sample runs 2024-04 to 2026-08 with gold going **2362 → 4492 (+90%)**.
  A long-only edge in the largest gold bull run on record is directional beta
  until a bear sample says otherwise.
- **The whole-sample t is +1.80, n=112, 95% CI [−0.016, +0.379]R** — it does not
  exclude zero. A skill-free control preserving the same R shape and geometry
  beats the measured mean **4.06%** of the time. That is a hair inside 5%, on a
  strategy that has been through ~780 configurations by E-098's own count
  (which puts the multiple-comparison bar at t ≈ 3.65).

**Status per the project's own vocabulary: UNPROVEN.** E-096 already says so.

---

## 11. SMALLER ITEMS THAT STILL COST MONEY UNATTENDED
- **Order-send failures are not retried and are barely logged.** `:1894`,
  `:1946`, `:1876`, `:1928` are all `else Log("Buy failed: " + retcode)` with no
  retry and **no `Journal()` row**. `Log()` (`:1032`) is suppressed entirely if
  `InpVerboseLog = false`. A rejected entry leaves no trace in the CSV that is
  supposed to be the account's evidence base.
- **`PositionClose` failures in `ManagePosition` are completely silent** —
  `:2139`, `:2158`, `:2169` have no `else` branch at all. A stall exit or bar-cap
  exit that is rejected simply doesn't happen and nothing says so.
- **The guards are account-wide, not EA-wide.** `RiskAllowsEntry:1397` and
  `CheckGuardsTick:3343` both read `ACCOUNT_EQUITY`. A manual trade, or
  `LiquiditySniper` (magic 770069) on the same £60 account, will trip
  SuperTrendSniper's £1.80 daily lock and vice versa. On this balance the two
  EAs will lock each other out within minutes.
- **No weekend flatten and no news blackout.** There is no `DayOfWeek` check
  anywhere in the file. `InpMaxBars = 50` counts *bars*, not minutes, and bars
  stop forming at the close — a Friday 20:5x entry is carried through the
  weekend gap on a £3.46 stop with £3.60 of lifetime drawdown budget.
- **Margin must be confirmed before anything else.** 0.01 lots = 1 oz =
  $4491.80 notional:
```
1:500 -> £7.07 margin (11.8% of £60)     1:100 -> £35.37 (58.9%)
1:200 -> £17.68 (29.5%)                  1:50  -> £70.74  ORDER REJECTED
                                         1:20  -> £176.84 ORDER REJECTED
```
  If PU Prime gives gold less than about 1:80, **the EA cannot open a single
  position** and will log `retcode 10019` into a suppressible Print.
- **`SYMBOL_TRADE_STOPS_LEVEL` must be read on the live symbol.** `MinStopDist()`
  (`:2580`) widens the stop to `stops_level × 1.2` (`:1707`). If PU Prime sets it
  to anything above ~3.0 price units the stop becomes ≥ £2.83 and — per finding
  4 — the lot size cannot shrink to compensate. Above 3.81 price units one stop
  exceeds the entire 6% permanent-drawdown budget. **Print
  `SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL)` and
  `SYMBOL_TRADE_FREEZE_LEVEL` on the live account before deploying.**
- **`InpDemoOnly = true`** (`:519`) returns `INIT_FAILED` on a live account
  (`:3766`). The plan cannot start without deliberately disabling the last
  safety interlock in the file.

---

## WHAT WAS CHECKED AND IS GENUINELY CLEAN
Stated so the fixes above are not confused with a general condemnation.
- **Stops are real broker stops**, attached at `OrderSend` (`:1885`, `:1937`),
  not held in EA memory. The worst unattended failure mode is absent.
- **No look-ahead.** `UpdateSuperTrend:1227` recomputes from history over a
  fixed 400-bar warm-up and never reads shift 0; `BuildLevels:1329` confirms
  pivots from shifts `i−j ≥ 1`, all closed bars. No relative of F-001 found.
- **Guard state survives restart, recompile and parameter change** via terminal
  global variables keyed on login+magic (`LoadGuards:1093`). The blocker
  documented at `:1083` really was fixed.
- **Magic numbers do not collide**: 770001 vs LiquiditySniper's 770069.
- **`PositionModify` calls are all guarded** against the broker stop level
  (`:2255`, `:3196`, `:3033`) and ratchet in one direction only.

---

## WHAT WOULD HAVE TO CHANGE BEFORE THIS RUNS LIVE
In order. Items 1–4 are blockers; the target is not recoverable at all.

1. `InpUseBasket = false` (finding 1), or the arm made R-based.
2. `InpDailyLossPct` and `InpMaxDDPct` raised above two stop-losses, **or** the
   balance raised to at least **£231** so 3% clears two stops. E-096's £100 is
   the floor for ruin risk; it is *not* enough for these guard defaults.
3. `LotFor` made to warn and `TryEntry` made to refuse when the 0.01 floor
   overshoots `InpRiskPct`.
4. `CheckGuardsTick`'s flatten moved out of the `if(!hit)` gate and made to
   retry and log.
5. **Abandon £260.** The reachable expected ceiling at 0.01 lots and 20
   trades/day is **£158 on the optimistic 15m number and £86 on E-089's M1
   number.** Any lot size that reaches £260 puts ruin above 50%.
6. Read the live `SYMBOL_TRADE_STOPS_LEVEL`, `SYMBOL_TRADE_FREEZE_LEVEL`,
   margin rate and a full session of M1 spread from the actual PU Prime symbol.
   Three of the findings above cannot be closed without those four numbers.
7. Then run **two weeks on demo on M1**, unattended, and read the journal CSV.
   That is the only thing that produces M1 evidence, which this project has
   never had.

**The single test that would change this verdict:** the same simulation in
`JARVIS/research/rt_live_account.py` and `JARVIS/research/rt_live_basket.py`, re-run on real XAUUSD M1 bars
with real PU Prime spreads, showing P(permanent lock inside 9 days) below 10%
and mean R above zero with the basket rule on. Nothing short of M1 data settles
it, because every failure above is a money threshold meeting a lot-size floor,
and both of those are timeframe-dependent.

---

*Scripts: `JARVIS/research/rt_live_mae.py` (R + MAE from the shipped exit stack),
`JARVIS/research/rt_live_account.py` (£60 account Monte Carlo with the EA's own guards),
`JARVIS/research/rt_live_basket.py` (basket / daily-guard exit attribution). All derive from
`JARVIS/research/small_account.py` and `JARVIS/research/pine_ea_parity.py`.*

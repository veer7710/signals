# Adversarial audit — `JARVIS/ea/build/SuperTrendSniper.mq5` (2204 lines)

Date: 2026-09-01. Auditor: JARVIS review pass, no MetaTrader in this
environment. Nothing here was compiled and nothing was tick-tested. Per L-009,
`python3 JARVIS/tools/check_mq5.py` returning clean is evidence that the
specific things the checker models are absent, not evidence the file compiles.

Read against E-051, E-052, E-053, D-010 and FAILURE_LOG F-006/F-007/F-008.
The file was NOT edited.

Severity classes used below:
- **BLOCKER** — will compile and lose money or breach a prop rule.
- **SERIOUS** — will compile and misbehave in a way that changes results.
- **MISMATCH** — the code does not do what a comment in the file says it does.
- **STYLE** — waste or fragility, no measured consequence.

---

## 0. COMPILE — what I checked, and what I found

**No hard compile error found.** That is a statement about the classes below,
not a claim that MetaEditor will accept the file.

Checked explicitly and believed correct:

| thing | verdict |
|---|---|
| `struct Basket` (404) defined before its first use in the forward decl (434) | OK |
| all 24 forward declarations (429-452) have matching definitions and signatures | OK — none would produce a link error |
| `Snapshot(Basket &b)` — struct passed by reference, and all **14** members are assigned before any read (1515-1519, 1559-1563) | OK, no uninitialised member |
| `uchar g_flipHist[MAX_FLIPHIST]` (383); write `(dir != dirPrev) ? (uchar)1 : (uchar)0` (637) — both ternary arms same type; read `!= 0` (1653) | OK |
| `ObjectSetInteger(0,nm,OBJPROP_CORNER,(ENUM_BASE_CORNER)InpBoxCorner)` (1976) — explicit int→enum cast, enum→long param | OK |
| `ObjectSetInteger(0,nm,OBJPROP_COLOR,c)` (1990) with `color c` → long param | OK |
| `ObjectSetString(0,nm,OBJPROP_FONT,"Consolas")` / `OBJPROP_TEXT,txt` (1980, 1989) | OK |
| `UpdateSuperTrend` array bounds: `atrBuf[s]` s≤warm-1 size warm; `r[s+1]` s≤warm-1 size warm+1 (601-604, 620-640) | OK, no overrun |
| `atrBuf`/`r` index alignment (both copied from shift 1) | OK, aligned |
| every `StringFormat`/`PrintFormat` in the file: specifier count and type vs arguments, including all `%.*f` two-argument forms | OK — 40+ call sites checked, all match |
| CTrade signatures: `Buy`, `Sell`, `BuyLimit`, `SellLimit`, `PositionClose`, `PositionClosePartial`, `PositionModify`, `OrderDelete` | OK |
| `OnTradeTransaction` signature (1376-1378) | OK, exact |
| global declaration order — every global is declared above every function that reads it | OK |
| `Journal`, `SkipLog`, `RiskTag`, `LotFor`, `NearestLevel`, `AddLevel` called before their definitions | OK in MQL5 (unlike Pine — F-008 does not apply here) |

Two things I **cannot** verify without MetaEditor:
1. `input long InpMagic` → `trade.SetExpertMagicNumber(InpMagic)` (2130) is
   `long`→`ulong`. May emit a conversion warning. Harmless at 770001.
2. `ArrayRemove` (1233, 1248) requires terminal build ≥ 2005 and
   `input group` requires ≥ 2085. Fine on any current build.

---

## BLOCKER 1 — the prop-firm guards are write-only. A restart deletes them.

**Where:** comment 471-484; `PersistGuards()` 507-515; `OnInit` 2134-2139.

`PersistGuards()` writes `peakEq`, `dayStartEq`, `dayStamp`, `tradesDay`,
`lockDay`, `lockPerm` into terminal GlobalVariables. **Nothing ever reads any
of them back.** `GGet` is called in exactly one place — `LoadStats()` (2104-2113)
— and `LoadStats` reads only the seven display statistics. `OnInit` then does:

```
   g_dayStartEq = eq;
   g_peakEq     = eq;
   g_dayStamp   = DayStamp();
```

and `g_lockedDay` / `g_lockedPerm` keep their file-scope initialiser `false`
(343-344).

The comment block at 471-484 states the exact opposite, in detail:

> "OnInit used to re-seed g_peakEq to the CURRENT equity and clear both locks.
> ... A guard a restart removes is not a guard. These values now live in
> terminal global variables, which survive a restart"

They do not. The defect the comment describes as fixed is still present, in
full, plus a new one: the *write* path now exists so the values look persisted
in the terminal's Global Variables window.

**What breaks, concretely:** account is 5% down on the day, `g_lockedDay` is
true, entries blocked. Veer changes `InpBoxSize`, or the terminal reconnects
and recompiles, or he switches the chart from M1 to M5 and back. `OnInit`
runs. The daily-loss baseline is re-seeded to the already-drawn-down equity, so
the day now reads 0% loss, and both locks are cleared. The EA resumes trading
into a breached daily limit. The max-drawdown lock behaves the same way:
`g_peakEq` is re-seeded to the drawn-down equity, so a drawdown already
incurred can never fire the 6% lock.

This is the single highest-consequence item in the file and it is on a live
account.

---

## BLOCKER 2 — basket protection liquidates the runner immediately after any partial close. Default settings.

**Where:** `UpdatePeaks` 1768-1780 (peak only resets when flat);
`ProtectBasket` 1846-1892; the level partial `ManagePosition` 1300-1325.

`g_bkPeak` is a running maximum of *floating* profit and is reset only when
`b.n == 0` (1770-1774). Realising money removes it from the floating total
without reducing `g_bkPeak`, so **every partial close is recorded as a
give-back of exactly the amount that was banked.**

The arithmetic, with the shipped defaults (`InpRiskPct` 0.50 line 195,
`InpBasketArmPct` 0.60 line 292, `InpBasketGiveBack` 0.35 line 294,
`InpPartialAtLevel` true line 190, `InpUseBasket` true line 291):

- arm threshold = `max(equity × 0.60%, £2.00)`; at 0.5% risk per trade that is
  **1.2R** of the trade's own risk, at any account size.
- the level partial closes half the volume, so floating profit **halves**.
- the basket floor is `peak × 0.65`. Half of the peak is always below 65% of
  the peak, at every account size:

```
  eq      500  risk/trade   2.50  arm  3.00  peak   3.25  after partial   1.62  floor   2.11  -> CLOSES
  eq     2000  risk/trade  10.00  arm 12.00  peak  13.00  after partial   6.50  floor   8.45  -> CLOSES
  eq    10000  risk/trade  50.00  arm 60.00  peak  65.00  after partial  32.50  floor  42.25  -> CLOSES
```

So: the trade reaches a level at ≥1.2R, `ManagePosition` banks half exactly as
designed, and on the **next tick** `ProtectBasket` reads the halved floating
total as a 50% give-back and closes the runner.

The file's own scenario map (88-100) and the comment at 1286-1299 describe
"bank half, let the rest ride through if it breaks" as the central design
answer to wanting both the pennies and the big moves. `ProtectBasket` destroys
it on the next tick, at defaults, on every trade that partials above 1.2R.

If the partial happens *below* the arm threshold it is worse in a different
way: `g_bkPeak` still holds a full-size peak, so the half-size runner is
measured against a floor it can only clear by roughly doubling its own former
peak in R.

**Same root cause, second symptom:** a full close of one position out of
several (SL, TP, time cap, or the per-trade give-back exit at 1815) also drops
`b.money` without touching `g_bkPeak`. So closing the winner mechanically
manufactures a basket give-back that liquidates everything else. With
`InpMaxStack = 1` only the partial path can reach this; see SERIOUS 9 for what
happens at `InpMaxStack = 3`.

---

## BLOCKER 3 — no `SYMBOL_TRADE_STOPS_LEVEL` or freeze-level check anywhere.

**Where:** absent. Confirmed by grep: no occurrence of `STOPS_LEVEL` or
`FREEZE` in the file. Affected sites: entry SL/TP 1030-1043 and 1090-1105, the
level-capped TP 1035-1043, break-even `PositionModify` 1348, trail
`PositionModify` 1358, and both limit orders 1057, 1112.

Stops are placed at `ask ± 1.5 × ATR(7)` with no comparison against the
broker's minimum stop distance. Per D-010 this EA runs on **M1**. M1 gold
ATR(7) is small; `InpLevelBufAtr` can pull the TP to within a fraction of an
ATR of price; and PU Prime style CFD accounts commonly carry a non-zero
stops level. The failure mode is `OrderSend` returning 10016 `INVALID_STOPS`
on every signal, or the trail silently refusing every modification, with the
only trace being `Log("Buy failed: 10016")` and no journal row. The EA would
appear to be "not trading" with no visible reason.

The audit checklist lists this explicitly and it is not implemented.

---

## BLOCKER 4 — the daily-loss and max-drawdown locks only block entries, and are only evaluated when a signal fires.

**Where:** `RiskAllowsEntry` 742-786; its single call site `TryEntry` 890.

Two independent problems.

1. **They are only evaluated inside `TryEntry`,** which is reached only on a
   bar close AND only after `HasPending()` (874) and the flip test (879-881)
   pass. On a quiet M1 hour with no SuperTrend flip, the daily-loss check does
   not run at all. `g_peakEq` is updated every tick (2162-2163), but nothing
   compares it to anything every tick.
2. **Nothing closes open positions when a lock fires.** `g_lockedDay` and
   `g_lockedPerm` only cause `RiskAllowsEntry` to return false. A position
   already open when the account crosses `InpMaxDDPct` keeps running to its
   stop.

For a prop account, `InpMaxDDPct = 6.0` is a breach threshold, not an advisory.
The audit checklist requires it enforced in code; here it is enforced only
against new entries, only on flip bars.

There is also **no news blackout** of any kind (the header at 111 says so
honestly), which some firms require.

---

## SERIOUS 5 — repeated close attempts every tick, with no backoff and no failure logging.

**Where:** `ProtectPositions` 1815-1833, `ProtectBasket` 1889-1892.

`ProtectPositions` wraps the close in `if(trade.PositionClose(tk))` and has
**no `else` branch** — a failed close is completely silent. `ProtectBasket`
ignores the return value entirely (`trade.PositionClose(tk);`, 1891).

Neither records that a close has been attempted for a ticket. The trigger
condition (`rNow <= keep`, `b.money <= floorMoney`) does not change because the
close failed, so on the next tick both fire again. On M1 gold that is 10-30
close requests per second per position for as long as the failure persists.

Failure conditions that persist for many ticks: `TRADE_RETCODE_REQUOTE`,
`TRADE_RETCODE_MARKET_CLOSED`, `TRADE_RETCODE_TRADE_DISABLED`, price inside
the freeze level, `TRADE_RETCODE_TOO_MANY_REQUESTS` (which this behaviour
itself causes), or the terminal being off-quotes around a news print — exactly
the moment the give-back rule is most likely to trigger.

`ProtectBasket` additionally re-`Log`s its full multi-line BASKET PROTECT
message and re-writes a `Journal` CSV row (1871-1895) on **every** such tick.
`Journal` does `FileOpen`/`FileWrite`/`FileClose` per call (1155-1176), so a
stuck basket close writes and closes the journal file tens of times a second.

Minimum fix: record the ticket and the tick/time of the last close attempt,
back off, and log the retcode on failure.

---

## SERIOUS 6 — `ProtectPositions` and `ProtectBasket` act on independent snapshots of the same tick.

**Where:** `OnTick` 2184-2187; `ProtectBasket` calls `Snapshot` at 1841,
`DrawBox` calls it again at 2003, `UpdatePeaks` at 1769.

Three separate `Snapshot()` passes plus two more raw `PositionsTotal()` loops
run per tick, and `ProtectPositions` closes positions *between* them.
`ProtectBasket`'s snapshot is taken after those closes. Two consequences:

- If the terminal's position pool has not yet dropped the just-closed ticket,
  `b.money` includes a position that no longer exists and `ProtectBasket` can
  fire on stale money and then issue a second `PositionClose` on the same
  ticket. The second attempt fails silently (see SERIOUS 5).
- If the pool *has* dropped it, `b.money` has fallen by the closed position's
  profit while `g_bkPeak` has not — which is BLOCKER 2's cascade, deterministic
  rather than racy.

`ManagePosition` (1255) also closes on the time cap and can partial. It runs
*after* the protection block in the same tick, so it will not double-close a
ticket that closed successfully; it can, however, `PositionModify` a ticket
whose close silently failed.

The cheap structural fix is one `Snapshot` per tick, shared, plus a
"closed-this-tick" ticket set that all three paths respect.

---

## SERIOUS 7 — the every-tick give-back rule is NOT the rule E-051 measured. It is strictly more aggressive.

**Where:** EA `OnTick` 2184-2185 (`UpdatePeaks()` then `ProtectPositions()`),
`UpdatePeaks` 1750-1758, `ProtectPositions` 1797-1812.
Study: `JARVIS/research/exits.py:252-269`.

The measured rule:

```python
        prev_peak = p.get("gb_peak", 0.0)          # peak as of the LAST bar
        if prev_peak >= arm_r * p["risk"]:
            trig = p["entry"] + side * prev_peak * (1.0 - gb)
            ...
        p["gb_peak"] = max(prev_peak, fav)          # update AFTER the test
```

The EA updates the peak **before** the test, from the **current tick**. So a
tick that makes a new high immediately raises the exit floor by 70% of that
new high, and the retrace from that same spike can then exit the trade on the
next tick. E-051's "No look-ahead" section says this assumption "is worth
roughly a third of the measured result, so it is not made."

**Direction of the difference: the EA is MORE aggressive.** It will exit on
single-tick spike-and-retrace sequences the study deliberately ignored, and it
exits at a higher absolute price when it does. The comment at 1713-1720
argues that acting sooner "can only close nearer the trigger, never further
from it" — that is true of *evaluation frequency* (bar vs tick), and it is
correct. It is not true of the *trigger level*, which the EA recomputes from
intrabar data the study refused to use. The comment conflates the two.

This is not necessarily worse — a live EA genuinely does see the peak before
the retrace, which OHLC cannot. But **E-051's numbers (+0.099R GOLD 1h,
+0.059R GOLD 15m) do not describe this rule** and must not be quoted about it.

---

## SERIOUS 8 — the give-back tiers and the trend-risk multipliers were never measured, and at high trend risk the trigger sits inside the M1 cost band.

**Where:** input group 261-284 (header: "PROFIT PROTECTION (E-051: measured,
not guessed)"), tiers at 279-283; `GiveBackAllowed` 1694-1708.

E-051's headline result is `giveback 30% arm@1R` — a **flat** 30%
(`exits.py:323`). The two ratchets that were actually coded in the lab are
`45/30/22` and `50/35/25` (`exits.py:327-330`), and neither is the reported
result. The EA ships `30/24/18` — **tighter than any ratchet that was tested**
— and then multiplies it by 0.80 / 0.62 / 0.45 for trend risk, with a floor of
0.08. None of those seven numbers appears in any experiment.

The input group is headed *"PROFIT PROTECTION (E-051: measured, not guessed)"*
(261) and its body (268-273) cites only E-051's 5-of-5 result. The six tier
parameters declared immediately underneath (279-283) were guessed. E-051 says
of its own defaults only: "arm at 1.0R, give back 30%, tightening as the peak
grows" — and its table contains no tightening either.

What the parameters actually produce (computed, not estimated):

```
 peakR | risk0: gb%  dropR | risk1: gb%  dropR | risk2: gb%  dropR | risk3: gb%  dropR
   1.0 |         30.0  0.300 |         24.0  0.240 |         18.6  0.186 |         13.5  0.135
   1.5 |         30.0  0.450 |         24.0  0.360 |         18.6  0.279 |         13.5  0.203
   2.0 |         24.0  0.480 |         19.2  0.384 |         14.9  0.298 |         10.8  0.216
   4.0 |         18.0  0.720 |         14.4  0.576 |         11.2  0.446 |          8.1  0.324
   6.0 |         18.0  1.080 |         14.4  0.864 |         11.2  0.670 |          8.1  0.486
```

E-053 puts the M1 gold round trip at **0.15–0.22R** of the 1.5-ATR stop. At
trend risk 3, the exit fires on a 0.135R–0.216R retrace — **inside the cost
band**. At trend risk 2 it is 0.186R–0.298R, straddling it. On the timeframe
this EA is deployed on (D-010: M1 only), the give-back trigger at high trend
risk is smaller than the toll the trade pays to exist.

E-052 also says of the run-age effect: *"deliberately proportionate to a
3-point edge"*. Cutting the give-back allowance by 55% is not proportionate to
3 percentage points on a base rate near 50%.

E-051 caveat 4 says M1 is unverified. The EA ships these numbers as defaults on
a live M1 account.

---

## SERIOUS 9 — what breaks at `InpMaxStack = 3`

Asked specifically. Walked through `StackAllows` (1905-1952) and everything
downstream.

| component | at MaxStack=3 |
|---|---|
| `b.n >= InpMaxStack` cap (1911) | works |
| hedge refusal (1914) | works |
| cool-down (1917-1921) | works, but `g_lastEntryBar` is set by `RegisterEntry` when a **limit is placed** (1954-1958), not when it fills |
| trend-risk refusal at ≥2 (1925-1927) | works |
| "no add at a worse price" (1934-1940) | works, and it will refuse almost every add — a SuperTrend continuation signal is by construction beyond the basket average, so stacking will rarely fire at all |
| auto net-lot cap (1942-1950) | **wrong test.** It compares *existing* `b.netLots` against the cap and never accounts for the lot about to be added, so the resulting exposure can exceed the cap by one full position |
| **basket peak** | **BREAKS.** See BLOCKER 2. Any one of the three closing (SL, TP, time cap, or the per-trade give-back at 1815) drops `b.money` without touching `g_bkPeak`, so `ProtectBasket` reads it as a give-back and dumps the other two. The per-trade rule closing the winner at its peak is the *most likely* trigger. |
| **new entries** | **BREAK the basket too.** A new position opens at −spread, which lowers `b.money` while `g_bkPeak` is unchanged. If the basket is near its floor, the act of adding closes the whole basket including the position just opened. |
| give-back registry | fine — one slot per ticket, `TrackAdd` at 1477, pruned every tick at 1762-1764, `MAX_TRACK` 64 is unreachable |
| per-trade R arithmetic | fine — each position carries its own `g_tkRisk` from its own comment |
| risk guards | 3 × `InpRiskPct` 0.5% = 1.5% concurrent risk against a 3% daily limit — arithmetically inside it, but note BLOCKER 4: nothing closes anything if the limit is hit |
| netting accounts | **BREAKS silently.** No `ACCOUNT_MARGIN_MODE` check anywhere. On a netting account three "stacked" entries merge into one position with one ticket and a moving open price, so `g_tkRisk` / `g_tkPeakPx` become meaningless and `OnTradeTransaction`'s `DEAL_ENTRY_OUT` filter (1385) misses `DEAL_ENTRY_INOUT` reversals entirely. |

Verdict: `InpMaxStack = 3` should not be enabled until BLOCKER 2 is fixed.

---

## SERIOUS 10 — `OriginalRisk` degrades badly, not gracefully, when the comment is gone

**Where:** `RiskTag` 1196-1199, `OriginalRisk` 1201-1211, first use
`UpdatePeaks` 1746, second use `ManagePosition` 1279.

The tag is short (`"STS|3.45"`), so broker comment **truncation** at 31 chars
is not a risk. The real risk is **replacement** — many brokers and bridges
overwrite the position comment with their own (`[sl]`, `[tp]`, a bridge id, or
blank). The fallback is `MathAbs(openPx - sl)`, and the comment at 1192-1194
calls that "wrong but not fatal". It is worse than that, because
`g_tkRisk[ti]` is captured **once**, at whatever moment `UpdatePeaks` first
sees the position (1746):

- If the trail has already moved the stop, `g_tkRisk` is captured as the
  *trail distance* (3 ATR = 2× the true 1.5 ATR risk). `peakR` then reads half
  its true value, so the rule **never arms** at `InpGbArmR = 1.0` — the
  position silently has no give-back protection at all.
- If the trail has crossed the entry, `|open − sl|` is near zero. `TrackAdd`
  stores a near-zero risk; `peakR` and `rNow` both explode but the ratio test
  `rNow > keep` is scale-invariant, so the *trigger* still works — what breaks
  is the **arm**: `peakR >= 1.0` is satisfied by one tick of noise, and the
  position is protected from the moment it is +1 point green.
- If `|open − sl| == 0` exactly (no stop, e.g. a stop rejected at entry),
  `g_tkRisk = 0`, `ProtectPositions` skips it at 1795 and `ManagePosition`
  `continue`s at 1280. The position is **completely unmanaged** and no message
  is printed.

None of the three cases logs anything. At minimum the fallback should print a
warning and re-derive the risk from `InpStopAtrMult × ATR(at open)` rather
than from a stop that has moved.

Related and worth stating: **the peak registry does not survive a restart.**
`g_tkPeakPx` (361) is plain global state, zeroed on every `OnInit` including a
parameter change. A trade that peaked at 5R and is now at 3R is re-armed from
scratch at 3R with a fresh 30% allowance. The comment at 1189-1191 correctly
explains why the *risk* was moved onto the position; the *peak* was not, and
the file does not say so.

---

## SERIOUS 11 — the headline box metric, KEPT OF PEAK, is systematically wrong when partials are on

**Where:** `OnTradeTransaction` 1414-1425; `DrawBox` 2032-2035.

```
   if(PositionSelectByTicket(pid)) return;      // still open: this was a partial
```

Everything below that line — including `g_stRealized += money` — is skipped for
partial closes. So **the money banked by every partial is never added to
`g_stRealized`**, while `g_stPeakSum` still gets the full-size peak when the
remainder finally closes. `KEPT OF PEAK = g_stRealized / g_stPeakSum` (2032) is
therefore biased low, and `InpPartialAtLevel` is **true by default**.

`g_stGivenBack += MathMax(0.0, peakMoney - money)` (1425) has the same defect
from the other side: `g_tkPeakMoney` holds the full-size peak (1757) and
`money` is only the final, half-size deal, so a trade that banked half at the
top and the rest well is recorded as a large give-back. `g_stDayRealized`
(1424) is wrong for the same reason, so the "today" row of the box is wrong.

The comment at 1410-1413 explains why partials are excluded from the *trade
count*, which is right. It does not notice that they were also excluded from
the *money*.

Second, independent defect at the same line: at the moment
`TRADE_TRANSACTION_DEAL_ADD` arrives, MT5 does not guarantee the position has
already been removed from the terminal's pool. If `PositionSelectByTicket(pid)`
still succeeds for a **fully** closed position, the handler returns early and
that trade is never counted at all — no `g_stTrades`, no GREEN→RED check, no
`TrackDrop`. The registry entry is then cleaned up by `UpdatePeaks` on the next
tick (1762-1764), so the peak is lost and the trade is invisible forever. A
volume comparison (`deal volume` vs `position volume before the deal`) is the
robust test, not position existence.

---

## SERIOUS 12 — `TrendRisk` measures the newest signal's run and applies it to every open position, including ones facing the other way

**Where:** `RegisterSignal` 1604-1612, `RunBars` 1587-1592,
`TrendRisk` 1657-1692, consumers at 1704-1707 (`GiveBackAllowed`) and
1849/1861-1864 (`ProtectBasket`).

`RegisterSignal` resets the run whenever a signal's direction differs from
`g_lastSigDir`, so `RunBars()` always describes the run of the **most recent
signal**. `GiveBackAllowed` then applies that score to every open position
regardless of the position's own direction.

Concrete case: a long is open from an old, exhausted up-run. A short signal
fires, `RegisterSignal(-1)` resets the run to 0 bars, `TrendRisk` drops to
0 or 1 — and the still-open long, which is now on the wrong side of a turn,
gets its give-back allowance *loosened* from 13.5% back to 30% at exactly the
moment it most needs tightening. The finding is applied backwards for any
position that outlives the run it was opened in.

**Separate and larger problem with the same variable:** `RegisterSignal` is
called at 920, *after* four early returns —

- `HasPending()` (874)
- `StackAllows(...)` (889-890), which at the default `InpMaxStack = 1` returns
  false for **every** signal while a position is open
- `RiskAllowsEntry(...)` (892), which returns false on a locked day, at the
  trade cap, or on a wide spread
- the DEMA and ADX filters (895-916)

so **no signal that occurs while a position is open is ever registered**. With
a 50-bar time cap on M1, the EA is blind to the run for most of its life, the
opposite-direction signals that would have reset `g_runStartBar` are never
seen, and `RunBars()` is therefore systematically **inflated** relative to
`continuation.py`'s definition (`run_start = i` on every direction change,
`continuation.py:62-73`). The `run >= 100 bars` gate then fires far more often
than the measurement it is derived from, halving lot sizes (1010-1021) and
cutting give-back allowances on a reading the study would have reset many
times.

The DEMA/ADX part of the definition **is** faithful — `strategies.py:576-594`
gates on the ADX ceiling and the DEMA slope exactly as `TryEntry` does, and
`RunMoveAtr` (1594-1599) matches `continuation.py:118`. The gating-order bug is
the whole of the problem.

---

## SERIOUS 13 — every-tick cost of the display path on M1

**Where:** `DrawBox` 1999-2085, called unconditionally at 2187.

Per tick, `DrawBox` alone does:

- one `Snapshot()` (its third of the tick), plus `TrendRisk()` twice (2006 and
  again inside `GiveBackAllowed` at 2076), each of which calls `ADXValue`
  (`CopyBuffer`), `RunBars` (`iBarShift`) and `RunMoveAtr` (`ATR` →
  `CopyBuffer`, plus `iClose`);
- `EfficiencyRatio(50)` (2069) → **103 `iClose` calls in a loop** (1635-1646);
- `FlipsIn(20)`, `RoundTripCost()`, `ATR(1)`;
- ~17 `ObjectFind` + 17 `ObjectSetString` + 17 `ObjectSetInteger`;
- a fixed `for(int i = r; i < 40; i++) ObjectDelete(...)` loop (2083-2084) that
  attempts ~23 deletes of objects that do not exist, **every tick**, each
  setting `_LastError = 4202`.

Every one of those inputs reads **closed bars only**, so all of them are
constant within a bar and are being recomputed 10-30 times a second on M1 gold.
The efficiency-ratio loop alone is on the order of 3,000 `iClose` calls per
second during active trade. Nothing here feeds a decision — it is a panel.

This is not fatal but it is the largest avoidable CPU cost in the EA and it
dirties the chart object list on every tick. `DrawBox` should be throttled to
once per second or once per bar, and the closed-bar quantities cached per bar.
The protection path itself (`UpdatePeaks` + `ProtectPositions`) is cheap by
comparison and I have no objection to it running every tick.

---

## SERIOUS 14 — money arithmetic: right formula, three real edge cases

**`MoneyPerPricePerLot()` (1450-1456) = `TICK_VALUE / TICK_SIZE`.** The formula
is correct and it is the right generalisation:

- **Gold, 2-digit feed:** tick size 0.01, tick value ≈ 1.00 per lot →
  100 currency units per $1 of price per lot. Correct.
- **Gold, 3-digit feed:** tick size 0.001 → 1000 per $1 per lot. Also correct,
  because both numerator and denominator scale.
- **Indices with tick size ≠ point** (e.g. 0.25 or 0.1): still correct, for
  the same reason. Hardcoding `_Point` here would have been the bug; the file
  does not do that.
- `LotFor` (788-807) uses the same pair consistently. Correct.

The three real problems:

1. **`InpSlipPoints` is in POINTS (1626).** `slip = 2.0 × InpSlipPoints ×
   SYMBOL_POINT`. The default 5 gives $0.05 per side on a **2-digit** gold
   feed, matching E-053's assumption exactly. On a **3-digit** gold feed the
   same input gives $0.005 per side — **ten times too small** — and the cost
   gate silently under-counts. This is the digits/point trap from the
   checklist. It must be verified against PU Prime's actual `SYMBOL_DIGITS`
   before this gate is trusted.
2. **`InpCommPerLot` has no stated currency (1628).** `comm = InpCommPerLot /
   mpp` divides a commission by a money-per-price figure that is in **account
   currency**. If the account is GBP and the broker quotes commission in USD
   (the default 7.0 is E-053's "$7 per lot"), the commission term is
   overstated/understated by the GBPUSD rate — about 27% at 1.27. The input
   comment (225) says "YOUR broker's commission, per lot, round turn" and does
   not say in which currency.
3. **`tv <= 0` is not guarded** in `MoneyPerPricePerLot` (only `ts <= 0` is).
   Some brokers report tick value 0 for a CFD until the symbol is fully
   selected in Market Watch. The result is `mpp == 0`, the `mpp > 0.0` test at
   1628 then **silently drops the commission from the cost gate**, and `LotFor`
   returns 0 so entries are refused with "lot size rounded to zero". Both
   failures are silent.

Also: `trade.SetDeviationInPoints(20)` (2132) is hardcoded, not derived from
the symbol. $0.20 on 2-digit gold is reasonable; $0.02 on a 3-digit feed will
cause constant rejections on M1.

---

## MISMATCH — comments the code does not honour

E-053 already caught one of these (the chop refusal claimed at line 67 that did
not exist). It was fixed. Here are the ones still in the file.

| # | line(s) | the comment says | the code does |
|---|---|---|---|
| M1 | 471-484 | guard values "live in terminal global variables, which survive a restart" | nothing reads them back; `OnInit` 2137-2139 re-seeds. **BLOCKER 1** |
| M2 | 2090-2092 | stats globals are "keyed per symbol and timeframe so two charts do not overwrite each other" | `GKey` (487-491) keys on **login + magic only**. Two charts with the same magic share and corrupt one another's counters. The other comment (478) states the key correctly, so the file contradicts itself |
| M3 | 1566-1586 | `TrendRisk`'s three readings are "AGE / **STRETCH** / **CROWDING**" and quotes "-0.132R against +0.304R (the ADX result)" | E-052 **disproved** stretch and crowding and they were deleted. The code (1657-1692) scores run age, run distance and ADX. E-052 rates ADX "the weakest of the three… mean only −1.3 pts", not −0.132R vs +0.304R. The input group at 300-320 describes this correctly — so the file carries both the right and the wrong description |
| M4 | 31 | "this EA defaults to: NO break-even move, **NO early trail**, a fixed R target, and a time cap. Every one of those defaults is the option that measured best" | `InpUseTrail = true` (138) and `InpTrailAtR = 0.0` (139) — the trail arms **immediately** |
| M5 | 23 | "hold 20 bars : +0.201R **<- BEST**" presented as the basis for the defaults | `InpMaxBars = 50` (137) |
| M6 | 60-113 | the scenario map, which exists specifically so the answers "can be checked against the code" | it lists the trail, the level partial, the time cap and the trend flip as the exits. It **does not mention the give-back exit or basket protection at all** — the two exits that are on by default and that fire *before* everything it does list. This is the same defect class E-053 found, inverted |
| M7 | 79 | "one position or one pending, never both" | true only at `InpMaxStack = 1`; no caveat |
| M8 | 126-140, esp. 130 | quotes `trail 3xATR … out-of-sample **+0.505R**` on GOLD 1h as the reason it is the default | E-051's table gives `trail 3xATR` on GOLD 1h as **+0.077R**. Both may be honest results from different studies on different entries, but a reader of this file cannot tell, and the two sit 90 lines apart in the same input section |
| M9 | 261, 268-270 | "MEASURED, on identical entries, only the exit changing (E-051): vs the 3xATR trail **this EA used to ship**…" | `giveback_study.py:35` runs `strategies.donchian_trend`. The give-back rule has **never** been measured on this EA's SuperTrend entries. The phrasing implies otherwise |
| M10 | 261 vs 279-283 | the group is headed "E-051: **measured, not guessed**" | the six tier parameters directly beneath it were guessed — E-051 tested a **flat** 30%, and the only ratchets in `exits.py` are 45/30/22 and 50/35/25. **SERIOUS 8** |
| M11 | 1690-1693 | "an old, **stretched, crowded** trend deserves less rope" | same removed readings as M3 |
| M12 | 415-422 | "Prototypes make the question moot: **every** function below is declared before anything calls it" | `Journal`, `SkipLog`, `RiskTag`, `LotFor`, `NearestLevel`, `NearAnyLevel`, `AddLevel`, `HasPending` are all called before their definitions and are **not** forward-declared. Harmless in MQL5, but the stated invariant is false |
| M13 | 583-590 | criticises the old code because it "seeded direction from a SINGLE bar…, which is a guess" | the new `UpdateSuperTrend` **also** seeds from a single bar (613-620), just 400 bars back. The improvement is determinism, not the removal of the seed. The claim that live, tester and chart therefore "agree" is stronger than what the code supports |
| M14 | 592-593 | "Set AFTER the copy: that guarantees index 0 is the newest element **no matter which direction the copy filled the array in**" | `CopyBuffer`/`CopyRates` fill deterministically; `ArraySetAsSeries` is an indexing flag. The **behaviour is correct**; the stated reason is not |
| M15 | 829-831 | "Cancel a limit that has sat unfilled too long… after `InpLimitLifeBars`" | implemented as wall-clock seconds (833, 842): `InpLimitLifeBars × PeriodSeconds`. Across a gap or a dead-tick period the two differ |
| M16 | 123 | `InpDemaLen` "DEMA length (60 on M1, 100 on M3)" | default is **200**, and D-010 fixes this EA to M1 only. The comment's own advice contradicts the shipped default for the only timeframe it runs on |
| M17 | 1250-1254 | "Two rules are ON by default…: a wide 3-ATR trail…, and a 50-bar stall exit" | the **level partial** is also on by default (190) and is in the same function |
| M18 | 1445-1449 | "Everything below is quoted to Veer **in pounds**" | `Money()` (1458-1462) prints a bare number with no currency symbol and no account-currency lookup |

---

## STYLE

- `HasPosition()` (856-866) is defined and **never called**. Dead.
- `g_tkWorstPx` (362) is written (1756) and never read. `g_bkStart` (372) is
  assigned (1775) and never read. `Basket.sincePeakSec` (1563) and
  `Basket.oldestBars` are computed every tick and used only by the box.
- `AddLevel` (663) calls `ATR(1)` — a `CopyBuffer` — once per level, up to 200
  times per bar inside `BuildLevels`. Hoist it.
- `MarkPartialed`/`MarkLvlPartialed` (1227-1248) trim the **oldest** 200
  tickets past 400; in principle a very old ticket could be re-partialed. Not
  reachable in practice.
- `ProtectBasket` sets `g_bkArmed` only when `InpUseBasket` is true, so the box
  row "armed" reads "no" permanently when the basket rule is off (2019-2021).
- On the first tick after `OnInit`, `g_lastBarTime == 0`, so the bar-close block
  runs immediately and can fire an entry off the last closed bar. That means a
  parameter change mid-session can trigger an immediate entry.

---

## Explicitly checked and believed CORRECT

Stated so the absence of a finding is not mistaken for an omission.

- **No repainting.** `UpdateSuperTrend` reads shift ≥ 1 throughout (601-604, the
  loop comment at 596-597 is accurate), `ATR(1)`, `ADXValue(1)`, `DEMA(len,1)`,
  `iClose(...,1)`. The forming bar is never read for a signal. `g_stDirPrev` is
  the direction on the bar before the last closed bar, so `flipUp`/`flipDown`
  (879-881) detect a flip on a **closed** bar. Entries are on bar close only.
- **Recomputing SuperTrend from history each bar** rather than carrying
  recursive state is the right call and the reasoning at 578-590 is sound, the
  seeding caveat in M13 aside.
- **`Snapshot` initialises all 14 `Basket` members** before any read.
- **Peak registry does not leak.** `UpdatePeaks` prunes closed tickets every
  tick (1762-1764) and `TrackDrop` (1491-1504) compacts correctly. `MAX_TRACK`
  64 is unreachable from this EA's own entries, and overflow degrades to
  "untracked", as the comment claims.
- **Give-back R arithmetic is spread-neutral.** Both the peak and the current
  reading use BID for longs and ASK for shorts (1749-1750, 1804-1808), so the
  measured retrace is bid-to-bid and the spread does not appear in it.
- **Price-based peaks survive a partial close correctly** — `g_tkPeakPx` is an
  excursion in price and is size-independent. (`g_tkPeakMoney` is not; see
  SERIOUS 11.)
- **Position sizing** (`LotFor`, 788-807) is derived from stop distance and
  equity, reads `VOLUME_MIN/MAX/STEP` at runtime, floors to the step. Correct,
  and nothing about it is hardcoded for gold.
- **Stops are attached at `OrderSend`** (1030-1043, 1090-1105), not managed
  later. Correct, and the comment saying so is true.
- **`ORDER_FILLING`** is set from the symbol via
  `trade.SetTypeFillingBySymbol(_Symbol)` (2131). Correct.
- **Positions are identified by magic + symbol** in every loop I read
  (`HasPending`, `ExpireStalePendings`, `ManagePosition`, `Snapshot`,
  `UpdatePeaks`, `ProtectPositions`, `ProtectBasket`, `OnTradeTransaction`).
  No loop is missing the pair.
- **Downward iteration while closing** (`for(int i = PositionsTotal()-1; i>=0; i--)`)
  is correct in all five loops that close or modify.
- **The trail only ratchets** (1355-1360) and break-even only moves in the
  trade's favour (1348-1351). Correct.
- **`ExpireStalePendings`** handles the weekend correctly by using wall clock;
  `InpMaxBars` uses `iBarShift` so a weekend does not inflate the bar count.
  Both are the right choice for their respective jobs.
- **The demo guard** (2118-2124) is present, defaults on, and fails init rather
  than warning. Correct.
- **`RegisterSignal`'s run definition matches `continuation.py`** — reset on
  direction change, distance measured from the run's start close over ATR
  (`continuation.py:62-73, 117-118` vs EA 1594-1612). Faithful; the problem is
  purely where it is called from (SERIOUS 12).
- **`GuardsPersist()` disabling globals in the tester** (482-485) is correct and
  prevents optimisation-pass leakage.
- **`OnTradeTransaction` reads `DEAL_REASON`** rather than inferring the exit
  cause. Correct, and the comment explaining why (1370-1375) is accurate.

---

## What I could not verify without MT5

1. That the file compiles. Only MetaEditor can say that.
2. Actual `SYMBOL_DIGITS`, `SYMBOL_POINT`, `SYMBOL_TRADE_TICK_VALUE`,
   `SYMBOL_TRADE_TICK_SIZE` and `SYMBOL_TRADE_STOPS_LEVEL` on Veer's XAUUSD
   symbol — SERIOUS 14 and BLOCKER 3 both hinge on these.
3. Whether PU Prime preserves the position comment. SERIOUS 10 hinges on it.
4. Whether the account is hedging or netting. SERIOUS 9's last row hinges on it.
5. Real tick-rate CPU cost of the every-tick display path (SERIOUS 13).
6. Whether `PositionSelectByTicket` returns false reliably at `DEAL_ADD` time on
   this broker's server (SERIOUS 11, second defect).

## Suggested order of work

1. BLOCKER 1 — read the persisted guards back in `OnInit`. Smallest fix,
   largest consequence.
2. BLOCKER 2 — reduce `g_bkPeak` by realised profit whenever volume leaves the
   basket, or track the basket peak in R rather than in floating money.
3. BLOCKER 3 — read `SYMBOL_TRADE_STOPS_LEVEL` and clamp every SL/TP/modify.
4. BLOCKER 4 — evaluate the locks every tick and flatten on breach.
5. SERIOUS 5/6 — one snapshot per tick, a closed-this-tick set, retcode logging
   and a close-attempt backoff.
6. Then the measurement-fidelity items (7, 8, 12) — these change what the EA
   *is*, so they should not be mixed into the safety fixes.

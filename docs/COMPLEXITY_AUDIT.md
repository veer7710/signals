# COMPLEXITY AUDIT — SNIPER.mq5 and SMC_LIQUIDITY.mq5

*"The more we complicate this, the more room for errors."* This is that count, made
mechanically. Every number below is reproducible with `python3 tools/mql5_check.py`
plus the three scans described in §6. Baseline is commit `f2f4f16`
(`mq5/SNIPER.mq5` 21,480 lines / 748 inputs; `mq5/SMC_LIQUIDITY.mq5` 1,069 / 62).

---

## 1. Input census

| category | SNIPER | SMC_LIQUIDITY | test applied |
|---|---:|---:|---|
| **LOAD-BEARING** | 326 | 17 | named in `SNIPER_AUDIT.md`, **or** its own comment block cites a date, a ticket, an n, a percentile or a £ figure |
| **UNTESTED KNOB** | 318 | 45 | reachable at defaults, no measurement anywhere in repo or comment |
| **REDUNDANT / inert** | 77 | 0 | readable only inside a master switch that ships `false`, or is itself such a switch |
| **DEAD** | **27** | 0 | 19 with zero reads + 8 read only by a function nobody calls |
| total | **748** | **62** | |

Two things this table hides and should not. **Only 17 of 326 "load-bearing"
SNIPER inputs are corroborated outside the file** — the rest are load-bearing on
their own say-so, and the file's own history (v18.59 vs v18.63, v16.60's duplicate
`T_SessionWeight`) shows how often that say-so was wrong. And **144 of 748 inputs
can only be read inside one other input's `if` block**: they are not knobs, they
are the second half of a knob. SMC_LIQUIDITY is the control case: 62 inputs, zero
dead, zero inert, checker clean. Same author, same week, 1/20th the size.

### The 27 dead, by class

| class | inputs |
|---|---|
| safety that never fires | `InpMinBalanceToTrade` 634, `InpM15MinBalance` 644, `T_FlatBeforeClose` 3951, `T_FlatBeforeCloseMin` 3952 |
| a control whose mechanism ignores it | `T_AtrSpikeMult` 2886 (guard at 13937 uses a hard-coded `97.0` percentile), `T_SlBuf` 1716, `T_SlMin` 2452, `T_SlMax` 2454, `T_PullDepth` 4422, `T_PullMaxBars` 4423 |
| scaffolding never wired | `T_UseFailover` 2739 + `T_FailoverSymbols` 2740 + `T_FailoverMinER` 2741 + `T_GoldSlowER` 2742 |
| withdrawn, left behind | `T_TrailGivebackFrac` 2451, `T_DeferChaseOLD` 3536, `AU_ReportEvery` 762, `InpBalance` 857, `InpBrokerGmtOffset` 1578 |
| read only by an uncalled function | `T_SessionWeight` 2860, `T_RegimeStrength` 4104, `T_StrengthMaxBoost` 4107, `T_SessionPrimeX/GoodX/DeadX` 4118-4120, `T_WinPress` 4125, `T_WinPressMax` 4128 |

`InpBrokerGmtOffset = 3` is the one to look at twice: the EA reads `TimeGMT()`
everywhere and never applies the offset, so the hour-of-day statistics it persists
are keyed to server time while the session windows are keyed to GMT.

---

## 2. Contradictions

### C1 — the v20 block could not compile, so nothing in it ever ran *(fixed)*

`SN_LadderCheck`, `SN_TryLimit` and `SN_CancelLimit` were pasted out of
`SMC_LIQUIDITY.mq5` with three identifiers that exist there and **not** in
SNIPER: `Trade` (11492, 11543, 11604-11613 — this file's `CTrade` is `trade`,
line 535), `InpMagic` (11433, 11514) and `InpJournal` (11403, 11497, 11545,
11608, 11618). MQL5 is case-sensitive; the file did not build. Worse, had it
built, `POSITION_MAGIC != InpMagic` would have matched nothing — every position
carries `Cfg[].magic` (770100 / 770700 / 770800, set at 9337-9350). **The
breakeven ladder and the retail limit — the two headline v20 mechanisms, and the
only ones the audit doc calls immune to the veto stack — were unreachable twice
over.** `tools/mql5_check.py` does not resolve identifiers, so it passed.

### C2 — five mechanisms now write the same `POSITION_SL`

`SN_LadderCheck` (11432, 1-second timer) · the bank leg's breakeven move (11511) ·
`main trail/ratchet` (20323) · `HARD LOCK` folded into it (`T_HardLockOn` 3380,
arm 3.0 pts) · `thesis-weakening pull-in` (16900). The trail is monotone by
construction, so they cannot loosen each other — but they can *pre-empt* each
other, and one does. `SN_LadderCheck` moves the stop to entry once peak ≥ 0.50
noise band (≈0.59 pts at ATR 1.47) and its only distance test is
`SYMBOL_TRADE_STOPS_LEVEL`. It therefore places a stop exactly where
`T_LockRoomAtr = 0.90` (4422) and `T_TrailRoomAtr = 1.30` (4421) forbid the trail
to place one — the `LOCK HELD BACK` guard at 19489/19502, added in v17.72/v17.84
for the complaint *"we keep closing way too early due to trailing."* **The v20
ladder re-creates the bug v17.84 fixed, one function further along.**

### C3 — a floor above the distribution, and six switches to get past it

`T_MinWinnerExitPts = 6.00` (8552) refuses every non-safety exit below 6 points.
Measured peaks reach £6 on **4.0%** of trades (`SNIPER_AUDIT.md` §20); the 75th
percentile is £1.22. The file's answer was not to lower it but to add
`T_PeakGateFrac` (8414), `T_PeakGateWinner/Arbiter/Trail` (8431-8433),
`T_BasketExemptFloor` (8526), `T_GivebackExemptFloor` (8731), `T_FlipExemptFloor`
(8734), `T_RangeExemptFloor` (8736) and `T_RevEscapeAllTags` (8739) — **nine
inputs whose whole job is to get around one input.** This is the documented
"157 of 181 suppressed" pattern still standing.

### C4 — the grace window the audit doc says was removed is still here

`SNIPER_AUDIT.md` §"Bug 1" states that in SNIPER the grace "defaults to 0 and is
hard-capped below the fast-fail window in code (`GraceSecs()`)". **There is no
`GraceSecs()` in `mq5/SNIPER.mq5`, and `T_MinHoldSecs = 180` at line 3305** with
`T_MinHoldBars = 3` (3306) — on M1 that is `max(180, 3×60) = 180 s` against the
240 s average hold, i.e. 75% of a trade's life, exactly as the file's own header
note at lines 71-72 says. `GraceSecs()` and `InpGraceSecs = 0` live in
`SNIPER_MANAGER.mq5` (443, 108). Same for the fast-fail the doc calls "mechanism
#1, the whole build": `InpFastFail` / `InpFFShadow` / `InpManageOnly` exist only
in `SNIPER_MANAGER.mq5`. **The doc describes the manager and names the EA.**

### C5 — defaults that make other inputs unreachable

| unreachable | made so by | where |
|---|---|---|
| `T_Tp3R = 4.5` (4471) | `InpRideToFlip = true` (1705) forces `tp = 0.0` at every open, so `if(tp > 0 && tpR > 0)` at 17230 is never true | 17229-17230 |
| `SN_MatureMult = 0.40` | `g_snMatMult` (2180) is written at 11401/11413 and **never read** — with `SN_MatureRefuse = false`, the maturity gate only increments a counter | 11399-11414 |
| 24 `SC_*` + the APEX group | `InpUseScalp = false` (1645), `InpUseApex = false` (1646) | — |
| `InpMinConfluence = 1` (SMC 93) | `Confluence()` returns up to 3 from `GapScore` alone (SMC 595-604), so one inverted HTF gap satisfies it; `InpUseOTE/Discount/OB/FVG` + `InpOTELo/Hi` tune a gate that is effectively always open | SMC 595, 705 |

### C6 — 32 ways out, one way in

`CloseTagged()` carries **32 distinct tags** across 47 call sites, plus 5
`PositionClosePartial` sites, the broker stop, and now the bank leg. Against that,
**one** `Open()` — which itself holds 25 `return false` refusal paths (11857-12290).
The arbiter comment at 8489 already says this; it has since grown by one exit.
In SMC_LIQUIDITY the same count is 4 exits / 1 entry / 9 refusals.

---

## 3. Dead code

| kind | found | action |
|---|---|---|
| uncalled functions | 7 | 4 deleted (`PyramidDone`, `ClockIndexOfTf`, `OpenRiskCashAllSymbols`, `GmtHour`); 3 kept — `RegimeStrengthMult`, `SessionMult`, `WinPressMult` are the only readers of 8 inputs the file says to keep "so existing .set files still load" |
| globals assigned, never read | 10 | 6 zero-reference ones deleted (`g_eChop`, `g_eNoRoom`, `g_scTFofPos`, `g_scTfN`, `g_trTfN`, `g_dirTk[64]`); 4 written-but-unread left and reported: `g_snMatMult`, `g_snLimitDir`, `g_vwapBars`, `g_apexEnt` |
| unreachable branches | 4 | see C5; plus `MaxLossCheck`'s own note at 8757 that a target test below `pts >= 0` would be dead |

**The checker had two blind spots, both material.** Its write-only-global scan
stops at `body_start` = the first function definition, **line 1355 of 21,480** —
the entire v20 global block at 2098-2290 was never examined, which is why it
reported zero write-only globals while ten exist. And `INPUT_DEF` still used
`^\s*`, the exact bug `SNIPER_AUDIT.md` §1 records fixing in `FUNC_DEF`: `\s`
eats preceding newlines, so the reported declaration line was one or more lines
early, and an input whose *real* declaration then counted as a "use" was never
flagged. That hid 6 of the 19 orphans.

---

## 4. A minimal core — 25 inputs

One entry, one stop, one exit ladder, one size lever. Everything else is off.

| # | input | why it survives |
|---:|---|---|
| 1 | `InpUseTrend` | the only engine that runs; the other two ship `false` |
| 2 | `InpDemaLen` | the trend filter, and the parity contract with the Pine (§4) |
| 3 | `InpSignalLineStop` | the stop is the signal line, not an R-multiple — the chart sets it |
| 4 | `InpRideToFlip` | no fixed TP; measured peaks say a target above £2 is a 17.9% event |
| 5 | `T_SlFloorPts` | screenshots read 1.11/1.16 ATR — "the stop geometry is fine"; this keeps it |
| 6 | `T_MaxStopPts` | applied before sizing, so lot maths sees real risk |
| 7 | `T_MaxLossPts` | the own-accord cap, and the only loss brake no grace can defer |
| 8 | `T_LotCeilHard` | the standing maximum; size is the only lever, so it needs one bound |
| 9 | `SN_SpreadGate` | spread is £76.53 of a £159.79 loss (48%) and is a fee, not a bet |
| 10 | `SN_MaxSpreadMult` | measured against its own median — no per-symbol number to tune |
| 11 | `SN_Ladder` | ranked best of four exit shapes: −151.7 vs −293.9 per 275 trades |
| 12 | `SN_BEBands` | ~9% of trades reach breakeven and fail; converting those beats every winner change |
| 13-14 | `SN_Lock1Bands`, `SN_Lock1Keep` | the 65%-at-1-band stage, from that same ranking |
| 15-16 | `SN_Lock2Bands`, `SN_Lock2Keep` | the 85%-at-2.5-band stage, same |
| 17 | `SN_ChandelierATR` | a % lock gives back 0.31-1.02 ATR on 3-10 pt peaks and kills the runners |
| 18-21 | `SN_BankLeg`, `SN_BankAtR`, `SN_BankFrac`, `SN_BankBEOff` | frontier sweep over 1,543 + 498 identical entries: "reached +1R and still lost" 37% → 2% |
| 22 | `T_BasketArmBands` | BASKET-LOCK kept 98% of peak vs SL-HIT's −32%; the band arm scales, £5 did not |
| 23 | `T_MinHoldSecs` | kept **only so it can be set to 0** — at 180 it is C4 |
| 24 | `T_TradeJournal` | the CSV is what makes any of the above checkable next session |
| 25 | `InpVerboseLog` | every refusal counter is unreadable without it |

Deleted wholesale in that core: the nine inputs of C3 (`T_MinWinnerExitPts = 0`
retires all of them), the hard lock (C2 — the ladder supersedes it), the maturity
gate (C5), the failover scaffolding, and the four off-by-default entry gates until
one is measured on its own counter.

`SMC_LIQUIDITY.mq5` needs no cut. Its 62 are already one mechanism deep; the ten
that must survive are `InpSwingN`, `InpEqTolATR`, `InpPierceATR`, `InpExpandATR`,
`InpNeedReclaim`, `InpNoiseATR`, `InpStopBands`, `InpMinRR`, `InpRiskPct`,
`InpDailyLossPct`. Its one soft spot is `InpMinConfluence = 1` (C5).

---

## 5. What was actually changed

Every step re-ran `python3 tools/mql5_check.py`; **PASS, 0 errors, at every step.**

| # | change | file:line (baseline) | verification |
|---|---|---|---|
| 1 | `INPUT_DEF` `^\s*` → `^[ \t]*` | `tools/mql5_check.py:74` | orphan reports 13 → 19, read-above-declaration errors 0 → 0, all 6 EAs still PASS |
| 2 | `Trade.` → `trade.` ×7 | SNIPER 11492, 11543, 11604, 11605, 11609, 11610, 11613 | no undeclared identifier remains |
| 3 | `InpJournal` → `InpVerboseLog` ×5 | SNIPER 11403, 11497, 11545, 11608, 11618 | same bool semantics, declared at 1579 |
| 4 | `POSITION_MAGIC != InpMagic` → `EngineOf(POSITION_MAGIC) < 0` ×2 | SNIPER 11433, 11514 | `EngineOf()` defined at 7995, above both uses |
| 5 | deleted 19 orphaned inputs (31 lines with their comments) | listed in §1 | checker orphan count 19 → **0** |
| 6 | deleted 4 uncalled functions | 6461, 6521, 7237 (+ its header), 9271 | checker uncalled 7 → 3 |
| 7 | deleted 6 never-read globals | 2108 ×2, 5108, 5111, 5154, 10946 | independent whole-file scan: write-only 10 → 4 |

Nothing else. **No default value was changed, no mechanism with evidence was
removed, no working logic was restructured.** Changes 2-4 are the one category the
brief allows beyond deletion: a mechanism that provably could not fire.

Mid-audit a concurrent session committed `v20.01 the bank leg`
(`42f25af`, `9a53c32`) into the same file. Those four inputs are counted in the
733-input post-state and in C2; they were not written by this audit.

---

## 6. Reproduce

```
python3 tools/mql5_check.py                  # 10 checks, all six EAs
```
Three scans this audit added on top, because the checker does not do them:
**(a)** input census — declaration regex over the raw file, reads counted over
`strip_noise()` output, so a name inside a string or comment is not a read;
**(b)** whole-file write-only globals — same rule as check 7 but without the
`body_start` cut-off; **(c)** undeclared-identifier scan for `Inp*`, `SN_*`,
`T_*`, `g_*` against every declaration, `#define`, parameter and enum member,
which is what found C1. (a) and (c) belong in `mql5_check.py`; (b) is a two-line
fix to check 7.

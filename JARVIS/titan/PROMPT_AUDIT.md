# PROMPT AUDIT — what was asked, what was delivered, and where I was wrong

Written 2026-09-01 by the prompt-master role. Veer asked for "agents to
research and audit my prompts and improve mistakes and do the things i said".
This file is the audit and the briefs. It contains no new numbers: every
figure quoted here is copied from a file in this repository and cited with a
line number, or it is a count I made with `grep`/`wc` and said so.

## What I checked, and what I did not
Read in full: `CLAUDE.md`, `DECISIONS.md` (D-001..D-010), `FAILURE_LOG.md`
(F-001..F-008), `LESSONS_LEARNED.md`, E-050/E-051/E-052/E-053,
`titan/MISSION.md`, `titan/AGENT_PROMPTS.md`, `NEXT_ACTIONS.md`,
`KNOWN_LIMITATIONS.md`, `SuperTrendSniper.mq5` (2204 lines),
`SuperTrendSniper_v1.pine` (747), `LiquiditySniper_v1.pine` (2215),
`continuation.py`, `giveback_study.py`, `level_reaction.py`, `sweeps.py`.

Ran, because they are the repo's own gates and are read-only:
- `python3 JARVIS/research/test_engine.py` → **ALL TESTS PASSED**
- `check_pine.py` on both indicators → **CLEAN** (both). Per L-009 this means
  "passes static checks", not "compiles".
- `check_mq5.py` on the EA → **0 problems**
- `verify_fixes.py` → **27/27 present**

So the shipped artifacts are not broken in the F-005/F-006/F-007/F-008 way.
The defects below are of a different and harder kind: **the code is valid and
does something other than what its own comments say it does.**

I did not run any experiment and did not modify any file other than this one.

---
---

# PART 1 — THE AUDIT

## 1.0 Delivery scoreboard

| # | What Veer asked for | Status |
|---|---|---|
| 1 | Manage TOTAL basket profit, not per-trade | **DONE** — `Basket` struct + `Snapshot()` (mq5:410-421, 1513-1564), `ProtectBasket()` (1832-1895) |
| 2 | Basket state: open P/L, lots, weighted avg entry, peak, given back, MFE, MAE, time in trade, time since peak | **PARTIAL** — MAE and time-since-peak are computed and then **never read by anything** (§1.2) |
| 3 | Execution box: current/peak/realized, captured, given back, % of peak, green→red count | **DONE** — `DrawBox()` (mq5:2003-2085). Best-delivered item in the project |
| 4 | Intelligent state-aware protection, NOT a fixed TP | **DONE but on an unmatched control** (Part 2, P2-1). `InpTargetR=3.0` fixed TP is also still on |
| 5 | Zone-reaction engine M15 → M5 → M1 | **NOT STARTED** as a cascade. What exists is a flat union of levels from 15/60/240 (§1.4) |
| 6 | React NEAR zones, not exactly at them | **DONE** — `zoneTol` (pine:121), `NearAnyLevel()` (mq5:729) |
| 7 | Old-level relevance by age / TF / reaction strength / count / invalidation | **PARTIAL** — memory built (pine:361-436), filter shipped OFF and self-described as unmeasured (pine:130-131). Never measured (§1.3, B1) |
| 8 | LuxAlgo "Buyside & Sellside": zone only where ≥3 pivots cluster; zone with real width | **NOT STARTED** (§1.4) |
| 9 | LuxAlgo "Liquidity Sweeps": pivot objects with broken/mitigated/taken/wick state; WICK SWEEP ≠ OUTBREAK+RETEST | **NOT STARTED in the product**, though the taxonomy exists in research (§1.4, §1.3) |
| 10 | Faster reversals, but no flip on one opposite M1 candle | **SILENTLY DROPPED** (§1.1 D1, §1.2) |
| 11 | Stacking needs a reason; sniper entries; no adding after profit | **DONE** — `StackAllows()` (mq5:1907-1952), including the price-worse-than-average refusal at 1934-1937. Default `InpMaxStack=1` so it is dormant, and unmeasured |
| 12 | Re-entry preferred over stubborn holding | **SILENTLY DROPPED** — mq5:110 states plainly "It does not re-enter automatically after a stop-out"; never flagged to Veer as a dropped requirement |
| 13 | Two Pine scripts, different jobs, clean and minimal | **DONE on "different jobs", FAILED on "minimal"** — 108 and 47 `input.` calls, 2215 and 747 lines (§1.5) |
| 14 | 12 named test scenarios | **PARTIAL and pointed at the wrong product** — 18 scenarios P-01..P-18 exist in `EA_ARCHITECTURE.md` §5.2, for the LiquiditySniper Pine↔MQL5 parity. The LiquiditySniper MQL5 is a non-building skeleton, so none can be run. **The SuperTrend EA — the one on live money — has no test fixture at all** |
| 15 | Modular engines | **PARTIAL / STALE** — `JARVIS/ea/src/*.mqh` (16 files, 2210 lines) is declarations-only and untouched since commit `755f78f`. The live EA is one 2204-line file |
| 16 | Measure the profit capture ratio | **PARTIAL** — measured live in the box (`KEPT OF PEAK`, mq5:2032) but **never computed in any backtest**, and the CSV journal cannot reconstruct it (§1.2) |
| 17 | Advise whether to open a demo with his real broker | **NOT STARTED.** `grep -rn "demo account"` across `JARVIS/state/`, `JARVIS/titan/` and the root markdown returns **nothing**. He asked a direct question and never got an answer |
| 18 | Treat his observations as hypotheses to test, not instructions | **DONE and it worked** — E-052 and E-053 are exactly this, and both overturned something |
| 19 | Limit loss in sideways action | **ANSWERED (E-053) but not ACTED ON** (Part 2, P2-2) |
| 20 | Trends do not last forever | **DONE and measured** (E-052), with a stale comment block left behind (§1.1 D2) |

---

## 1.1 Documentation that lies about the code — the E-053 class, three more found

E-053 found that `SuperTrendSniper.mq5:67` documented a chop refusal the EA
did not implement. That was not a one-off. Three more:

**D1 — `SuperTrendSniper.mq5:91` claims a flip-close that does not exist.**
The scenario map, under HOLD, reads:

```
//   trend flips against it ............. closed
```

There is no such rule. `ManagePosition()` (lines 1255-1367) implements time
cap, level partial, 1R partial, break-even, trail — and nothing else. `grep`
for `flip` across the file returns only the chop counter, the entry test, and
this comment. What actually happens when the SuperTrend flips against an open
position: `TryEntry()` calls `StackAllows()`, which returns false with
`"would hedge the basket"` (mq5:1922), and the opposite signal is **discarded
entirely**. The position is held to its stop, trail, give-back or time cap.

This is precisely the behaviour Veer complained about — "re-entry preferred
over stubborn holding", "faster reversals" — and the file says it is handled.
It is not. **This is the single most consequential documentation defect in the
repo, because Veer will have read that line and believed it.**

**D2 — `SuperTrendSniper.mq5:1566-1583` still describes the two readings
E-052 disproved.** The module header for TREND PERSISTENCE reads:

```
//   AGE      - how long this SuperTrend direction has already lasted
//   STRETCH  - how far price has travelled from its own DEMA, in ATRs
//   CROWDING - how many same-direction entries have been taken in a row
```

E-052 measured stretch (5/8, no gradient, wrong-signed) and streak/crowding
(4/8, 4/8, 2/6, 2/8, 5/8 — "a coin flip") and **deleted both**. `TrendRisk()`
at 1657-1692 correctly implements run-age / run-distance / ADX. The comment
directly above it names three readings, two of which the project's own ledger
records as not replicating. The input-group comment at mq5:300-322 is correct
and current; the function-level comment was never updated with it.

**D3 — the same stale vocabulary at mq5:1693 and mq5:1846.** Both read "an
old, **stretched, crowded** trend/run", inside `GiveBackAllowed()` and
`ProtectBasket()` — functions whose actual behaviour is driven by
`TrendRisk()`, which no longer measures stretch or crowding.

**D4 — a real behavioural bug, not just a comment: the run clock stops while
a position is open.** `RegisterSignal()` is called at mq5:920. But `TryEntry()`
returns early at:
- 874 `if(HasPending()) return;`
- 889 `if(!StackAllows(...)) { SkipLog(...); return; }`
- 892 `if(!RiskAllowsEntry(...)) { SkipLog(...); return; }`

With the default `InpMaxStack = 1`, `StackAllows()` returns false for **every
signal that arrives while a position is open**. So `g_runStartBar` and
`g_lastSigDir` are not updated, and an opposite-direction signal during an
open trade does not reset the run.

The study this is meant to mirror does the opposite. `continuation.py:74-79`
resets `run_start = i` on **every** signal whose side differs, whether or not
anything is open:

```python
if side == last_side:
    streak += 1
else:
    streak = 1
    run_start = i
```

Consequence: `RunBars()` keeps accumulating across direction changes, so the
EA will report runs that are "100+ bars old" when the study would have reset
them, and will size down or refuse on the strength of a number the experiment
never measured. Given the time cap is 50 bars and the trail arms immediately,
positions are open a large fraction of the time, so this is the common case,
not an edge case.

---

## 1.2 Work done and then never surfaced

**Computed, then dropped on the floor.**
- `g_tkWorstPx` — maximum adverse excursion. Declared mq5:362, written
  mq5:1757, and **read nowhere**. `grep` confirms four occurrences, all
  writes or array shuffles. Veer asked for MAE by name.
- `Basket.sincePeakSec` — declared mq5:418, computed mq5:1563, **read
  nowhere**. Veer asked for time-since-peak by name.

**The CSV journal cannot answer the question the journal exists for.**
`Journal()` (mq5:1150-1176) writes: time, event, dir, price, lots, sl, tp,
money, atr, adx, spread, equity, note. The EXIT row is written at mq5:1405.
At that exact point in `OnTradeTransaction`, `peakMoney`, `peakR` and the
tracked MAE are all in scope (1416-1419) and are used for the on-screen
counters — and **none of them is written to the CSV**. Neither is bars-held.

MISSION.md states: *"Ranking must come from the EA's CSV journal, which
persists, not from Pine state, which does not survive a chart reload."* The
journal as shipped cannot produce a per-trade capture ratio, an MAE
distribution, or a holding-time distribution. Adding four columns costs one
line. This is the cheapest high-value fix in the repository.

**Research written, committed, and never turned into a result.**
- `conditional_edge.py` — 743 lines, committed (`65250a7`, `2d19d9a`),
  briefed as A3 = **E-042** in `AGENT_PROMPTS.md:513`. **There is no E-042 in
  EXPERIMENTS.md.** The E-number sequence present is E-001..E-041, E-043,
  E-046, E-050..E-053. E-042, E-044 (A5 vol-scaled sizing) and E-045 (A6 M1
  readiness) were all assigned and never written. MISSION.md still lists
  conditional expectancy as open next-action #2 while the script sits finished
  in the tree.
- `level_reaction.py` — 709 lines, **uncommitted** (`git status` shows ` M`,
  120 insertions in the working tree). It is the best-designed script in this
  repo: it carries a *matched* random control (same confirmation bars, same
  cluster-size trajectory, shuffled ATR-scaled offsets), a random-walk null
  offset over 8 seeds, and seven explicit look-ahead assertions. It implements
  the LuxAlgo cluster rule (`MARGIN = 1.45`, `CLU_PIV = 20`) and answers both
  of Veer's most-repeated questions. It has never been run to a recorded
  result, it is not in EXPERIMENTS.md, and its docstring claims the number
  **E-053, which is already taken by the chop study.** It is one `rm` from
  being lost.

---

## 1.3 The two LuxAlgo indicators — measured in research, absent from the product

Veer described "Liquidity Sweeps" precisely: pivots as objects with
broken / mitigated / taken / wick state, and a **WICK SWEEP** (high pierces
the level, close returns inside) separated from an **OUTBREAK AND RETEST**.

That taxonomy already exists in this repo, in `sweeps.py:106-110`:

```
"A": "wick sweep + rejection (closed back inside same bar)",
"B": "close beyond level + rapid reclaim within window",
"C": "deep sweep + rejection (depth > deep_atr)",
"D": "sweep + displacement (expansion candle after reclaim)",
"E": "sweep + structure shift (micro MSS after reclaim)",
```

The Pine implements none of it. `LiquiditySniper_v1.pine:745-778` collapses
every case into one boolean and one state flag:

```pine
broke = needClose ? (close > p) : (high > p)
if broke and barstate.isconfirmed
    array.set(hiDead, i, true)
```

`needClose` defaults **true** (pine:172), so a wick sweep — the event Veer
named first — does not register at all. There is one state (`dead`), not four.
`needRetest` exists (pine:176) but defaults false and is not tied to any
wick-vs-close classification.

This is the "done but never surfaced" failure at its worst: the distinction was
built, measured (E-017/E-018) and then not carried into the thing he looks at.

---

## 1.4 "Buyside & Sellside Liquidity" and the M15→M5→M1 cascade

**The ≥3-pivot cluster rule is not implemented.** `addLevel()`
(`LiquiditySniper_v1.pine:438-470`) merges a new pivot into any existing level
within `eqTol * atr` and then sets the stored price to the **extreme**:

```pine
array.set(px, i, isHigh ? math.max(array.get(px, i), p) : math.min(...))
array.set(hits, i, array.get(hits, i) + 1)
```

So a cluster becomes a single price plus a counter. There is no `hits >= 3`
gate anywhere — every level is drawn regardless of cluster size. And the
"zone" is cosmetic: `extend()` at pine:655 sets

```pine
zh = (zoneGrow ? 0.16 : 0.07) * atr * thick        // thick = min(hits, 3)
```

The zone's height is an ATR constant scaled by the hit count. **It is not the
span of the clustered pivots.** Veer asked for a zone whose width is the
cluster; he got a line with a decorative band.

**The cascade does not exist.** `useHtf` pulls levels from `htf1/htf2/htf3` =
`"15"/"60"/"240"` (pine:87-89) and unions them into the same two arrays as
every local pivot. There is no M15-bias → M5-refine → M1-trigger structure,
and **M5 is not in the defaults at all** despite being the middle rung of the
cascade Veer named. Separately, D-010 says H1 and H4 are "read for context,
never acted on" — but levels sourced from `"60"` and `"240"` arm sweeps and
fire signals on exactly the same code path as everything else. The decision
was recorded and the code was not changed.

---

## 1.5 Two claims shipped to Veer that the evidence does not support

**The ADX numbers.** `-0.132R` / `+0.304R` appear at `SuperTrendSniper.mq5`
lines 148-149, 904-905, 1005 and 1583, and at `SuperTrendSniper_v1.pine`
lines 29 and 81. The Pine tooltip at line 81 reads:

> "MEASURED: ADX >= 35 at entry gave -0.132R per trade. ADX < 20 gave +0.304R.
> **This is the single filter that survived being tested on data it was not
> chosen on.**"

Provenance: `setup_score.py:17` labels the source `E-0xx`. **There is no such
experiment number.** Nothing in EXPERIMENTS.md contains those figures. And
they are R-conditioned numbers with no random-entry arm, which is the exact
class E-050 (EXPERIMENTS.md:1069+) retracted. E-052 re-measured the same axis
under a control-free-free outcome and got "ADX 25-35: 6/8, mean only −1.3 pts.
**The weakest of the three kept.**" The tooltip is the strongest unbacked
claim in anything Veer has been given, and it is on his chart right now.

**"The EA's defaults" claim in the Pine header.** `SuperTrendSniper_v1.pine`
lines 8-11: *"Every number below is the EA's default... If you change a
setting here, change it there too or you are trading two systems."* He is
already trading two systems:

| | Pine | EA |
|---|---|---|
| chop guard | `skipChop = true` (pine:65) — **ON** | `InpUseChopGuard = false` (mq5:243) — **OFF** |
| chop threshold | >3 flips in 50 bars (pine:76-77) | ≥5 flips in 20 bars (mq5:246-247) |
| give-back exit (E-051) | **absent entirely** | `InpUseGiveBack = true` (mq5:277) |
| trend-persistence risk (E-052) | **absent entirely** | `InpUseTrendAge = true` (mq5:323) |
| time cap | 750 MINUTES, converted per chart (pine:99-102) | 50 BARS, never converted (mq5:137) |
| trend filter length | 3000 MINUTES, converted (pine:57) | `InpDemaLen = 200` bars (mq5:123) |

The two most important results of the last session (E-051, E-052) went into
the EA and not into the indicator he actually watches.

**And the EA has no timeframe scaling at all.** `grep` for `PeriodSeconds`,
`barMins` or any minutes conversion in the EA returns exactly one hit
(mq5:833, the pending-order lifetime). D-009 consequence 2 states: *"Both
products must scale their defaults by timeframe."* Only the Pine does. D-010
states the SuperTrend EA is **M1 only**. So on the only timeframe it is
supposed to run on, the shipped EA uses a 200-minute trend filter where the
Pine uses 3000, a 50-minute time cap where the Pine uses 750, and a
100-**minute** run-age threshold for an effect measured on 15m and 1h bars.
`InpDemaLen`'s comment — `// DEMA length (60 on M1, 100 on M3)` — is an
instruction to Veer to hand-edit it, and it does not even agree with the
Pine's own conversion.

---

## 1.6 Memory integrity — the session-start protocol points a new session at closed work

`CLAUDE.md` orders a new session to read `SESSION_STATE.md` and
`NEXT_ACTIONS.md` **first**. Both are stale by four sessions.

| file | what it still says | reality |
|---|---|---|
| `SESSION_STATE.md` (tail) | "`donchian_trend` is PROMISING", "No EA written", "No Pine script analysed" | E-009 downgraded it to UNPROVEN; both products shipped |
| `NEXT_SESSION_PROMPT.md` | "**Your first action:** A-001 — spawn the adversarial-reviewer and try to destroy `donchian_trend`" | closed by E-009/E-010 |
| `NEXT_ACTIONS.md` A-000 | "RERUN THE FIVE CUT-OFF RESEARCH JOBS [DO FIRST] ... wrote NOTHING" | `findings/01`, `02`, `05` exist |
| `MISSION.md` next action #1 | "LEVEL-TARGET REACHABILITY" | ran as E-041; `AGENT_PROMPTS.md:287` itself marks it SUPERSEDED |
| `MISSION.md` line 66 | "F-001..F-008, **L-001..L-011**" | `LESSONS_LEARNED.md` has no L-011. It is stranded in `LIVE_EVIDENCE.md:45` |
| `USER_GOALS.md` | "MT5 broker + symbol specs: **UNKNOWN**" | D-008: PU Prime, 1:500, recorded 2026-08-31 |

CLAUDE.md's own rule — *"If memory and repository disagree, TRUST THE
REPOSITORY and fix memory"* — has been invoked and not executed. The last
three sessions ended by committing code and EXPERIMENTS entries without the
checkpoint the file mandates.

**One stale artifact worth naming:** `JARVIS/ea/LiquiditySniper.mq5` plus the
16 files in `JARVIS/ea/src/` (2210 lines total) have not been touched since
`755f78f` and are declarations-only by design — they will not build. Anyone
reading the tree sees a modular EA that does not exist.

---
---

# PART 2 — WHERE MY PROMPTS AND MY REASONING HAVE BEEN WRONG

Veer asked for his prompts to be audited. The useful direction is the other
one. E-052 is the model: he said "trends don't last forever", I wrote gates on
streak and stretch from instinct, measured them, and both died while run-age
and run-distance replicated. Here is where the same thing is sitting
unmeasured right now.

## P2-1 — I broke E-050's own rule one experiment after writing it

E-050 ends with a standing rule, in its own words:

> "Every future strategy claim in this project must be reported against a
> random-entry arm with the **SAME payoff structure**, the same bars and the
> same costs, or it is not a claim about a signal."

`giveback_study.py` has no random arm. `grep -n 'random\|seed\|shuffle'`
returns three hits — the import, and `curve_stats(..., seed=7)` at lines 44
and 51, which is the **drawdown bootstrap**, not an entry control.

E-051 handles this by quoting E-050's `+0.202R`. But `+0.202R` was measured
under a 3R-target / 1R-stop / 50-bar-cap payoff. The give-back rule is a
*different payoff*. Comparing `giveback = +0.099R` to a random entry measured
under a different exit is exactly the mismatch E-050 exists to forbid.

And `InpUseGiveBack = true` is now the **shipped default** on that basis
(mq5:277), with the EA's own comment at 273-276 saying "it did not beat a
random entry on GOLD 1h (E-050)" — which quietly concedes the comparison it
should not have been making. I wrote the rule, then broke it, then shipped the
default. This is the highest-priority item in Part 3 after B1.

## P2-2 — I substituted my framing for his, then acted on my framing

He said: *"u can [see] how we perform shit in sideways price action make sure
we can limit loss on those."* I converted "limit loss in sideways" into "build
a chop filter", measured the chop filter, and E-053 correctly found it fails
(5 of 8, and it helps losers while hurting winners). E-053's real finding is
that this is a **cost** problem, and it names the honest levers explicitly:

> "The honest levers on M1 are a **wider stop, a bigger required move, or a
> cheaper instrument/timeframe** — all of which reduce cost/stop directly.
> Filtering does not."

What then went into the product: the chop guard, defaulted off (mq5:243-247).
**None of the three named levers has been measured or implemented.**
`InpStopAtrMult` is still 1.5. There is no minimum-required-move gate. The
cost gate refuses trades but does not change the trade. So his question is
still open, and the disproven mechanism is the thing sitting in the code.

## P2-3 — "Has it been measured" was never closed on the level work

He said: *"we can be able to react to previous levels we need to see if price
is near a price where it previously reacted too."* I built the zone memory
(pine:361-436), the hold/break record, the per-side split, and the filter
`useZoneFilter` — which ships **OFF** with a tooltip that says, correctly,
*"it has not been measured yet"* (pine:130-131).

That is honest, and it is also the whole problem. The feature was delivered,
the measurement was not, and Veer was never told that the answer to his
question does not exist. The script that would answer it is `level_reaction.py`
and it is **uncommitted**. Brief B1 exists to close this.

## P2-4 — Assumptions sitting live in the code, unmeasured, in the E-052 mould

Every one of these is default-ON, affects real money on Veer's live account,
and has never been measured.

1. **Three level rules, all on, all pointing against the evidence.**
   `InpTpAtLevel`, `InpPartialAtLevel`, `InpSkipNoRoom` all default `true`
   (mq5:189-191). E-041 measured level-target reachability and found "the BEST
   bucket in every market was still at or below zero". E-026 found HTF level
   confluence gives no advantage. Two experiments point away from level-based
   selection; three level-based rules are on by default anyway. **This is the
   largest unmeasured block in the live product.**
2. **The trail and the give-back rule run simultaneously.** E-051 measured
   them as **alternatives** — "identical entries, only the exit changes".
   `InpUseTrail = true` (mq5:138) and `InpUseGiveBack = true` (mq5:277) are
   both on, so the 3-ATR trail can pre-empt the give-back trigger. The
   combination was never in any table. The EA is running a third exit rule
   that has never been tested.
3. **Invented coefficients.** `GiveBackAllowed()` multiplies by
   0.80 / 0.62 / 0.45 by trend-risk score (mq5:1699-1701); `ProtectBasket()`
   repeats the same three numbers (mq5:1858-1861) plus `arm *= 0.60` at 1848.
   E-052's measured effect is **3 percentage points**. Nothing licenses these
   specific coefficients. They are E-052's mistake — instinct written as code —
   in a place nobody has thought to measure.
4. **The whole basket layer.** `InpBasketArmPct = 0.60`, `InpBasketMinMoney =
   2.00`, `InpBasketGiveBack = 0.35`, `InpBasketCloseAll = true`. The code
   comment at mq5:1877-1880 admits "Neither version has been measured against
   the other." This is what Veer asked for most insistently, which is exactly
   why it is where I was most likely to implement instead of test.
5. **Two rules on one axis.** `InpMaxAdx = 35` refuses entries above 35;
   `InpRunAdx = 25` awards a risk point above 25. So in the 25-35 band the EA
   both permits the trade and penalises it, driven by the weakest of E-052's
   three readings (−1.3 pts). The interaction is unmeasured.
6. **`InpRunOldBars = 100` on M1.** Measured on 15m and 1h; applied on M1 with
   no conversion (§1.5). 100 bars is 100 hours on H1 and 100 minutes on M1.

## P2-5 — Too literal in one direction, too loose in the other

- **Too loose:** D-010 settles that H1/H4 are context only. I recorded the
  decision and left `htf2 = "60"`, `htf3 = "240"` generating levels that arm
  sweeps (§1.4). Recording a decision is not implementing it.
- **Too literal:** he asked for two Pine scripts, "clean and minimal". I
  delivered 108 and 47 inputs across 2962 lines. Every single input has a
  justifying tooltip; the aggregate is the opposite of what he asked for; and
  I never once put the input count in front of him so he could object.
- **Too literal:** "manage the total basket" became `InpUseBasket = true` with
  five invented thresholds, shipped as defaults, rather than a hypothesis with
  a control. He explicitly asked that his observations be treated as
  hypotheses. The basket layer is the one place I did not do that.

---
---

# PART 3 — THE BRIEFS

Ranked by (value of the answer × probability the answer is obtainable here) ÷
cost. Every brief carries the four standing constraints below; they are
repeated in full inside each prompt so no agent is launched with half its
context.

**Standing constraints for every brief**
1. **NO M1 OR M5 DATA EXISTS IN THIS REPO.** `data/` holds 15m and 1h only,
   four symbols: GOLD (4501 × 15m, 13750 × 1h), US500 (4500, 13716), EURUSD
   (5624, 17252), GBPUSD (5624, 17253). Dukascopy and every market-data host
   are blocked by egress policy (KNOWN_LIMITATIONS.md) — **do not attempt a
   download, it is a policy denial, not a transient failure.** There is no
   MetaTrader here; nothing can be compiled or tick-tested. If your question
   needs M1, say so explicitly, state what you did instead, and label every
   M1 statement as EXTRAPOLATION.
2. **Verdict vocabulary only:** CONFIRMED / SUPPORTED / PROMISING / UNPROVEN /
   REJECTED / DISPROVEN. Nothing else. "PROMISING" is not "profitable".
3. **Never report a number you have not computed.** Paste real output. Run
   `python3 JARVIS/research/test_engine.py` first; if it fails, stop.
4. **All 8 symbol/timeframe combinations, with explicit multiple-testing
   arithmetic in the E-052 style.** E-052's paragraph is the template: state
   how many buckets/cells were examined, state P(a cell lands ≥7 of 8 on one
   side) under the null, state how many such cells are expected by chance, and
   compare that to how many were found. A result that is not stated against
   its own multiple-testing expectation is not a result.
5. **A well-evidenced NO is a complete deliverable.** E-041, E-043, E-053 and
   E-050 are the most valuable results this project has produced and every one
   of them is negative. Do not manufacture a positive.
6. **Label what you could not verify.** A search summary is not a read source.

**Launch order.** Batch 1: **B1 + B2** (both are reads, both write to
different files, both settle something already shipped). Batch 2: **B3** alone
— it is the only WRITE brief and must not run beside anything that touches the
same files. Batch 3: **B4 + B5**. Never more than 2-3 at once (F-003).

---

## B1 — Do marked levels produce a reaction at all? [HIGHEST VALUE]
**Agent type:** general-purpose · **Experiment number: E-054**

**Why first.** The script is already written, already controlled, and is
uncommitted — one careless command from being lost. It answers the question
Veer has asked more times than any other, and it is the only place in this
repo where a LuxAlgo idea meets a matched random control.

### PROMPT (paste in full)

> You are running one experiment for Project TITAN. Read these first, in this
> order: `/home/user/signals/CLAUDE.md`,
> `/home/user/signals/JARVIS/state/DECISIONS.md` (D-009 and D-010 especially),
> `/home/user/signals/JARVIS/state/EXPERIMENTS.md` E-050, E-041, E-026, E-017,
> `/home/user/signals/JARVIS/state/LESSONS_LEARNED.md` L-012 and L-013,
> `/home/user/signals/JARVIS/state/KNOWN_LIMITATIONS.md`.
>
> **THE QUESTION, falsifiable.** When price returns to a previously-marked
> pivot level, does it react away from that level MORE OFTEN than it reacts
> away from a matched random price at the same distance and the same age?
>
> **DISPROVEN IF** the real-level reaction rate minus the matched-random
> reaction rate is not distinguishable from the random-walk null offset the
> script itself computes. If real levels react 55% and matched random levels
> react 54%, the level is decoration and you must write those words.
>
> **THE SCRIPT ALREADY EXISTS.** `/home/user/signals/JARVIS/research/level_reaction.py`
> (709 lines, currently uncommitted). **Read it end to end before you touch
> it.** It already implements: the LuxAlgo "Buyside & Sellside Liquidity"
> cluster rule (`MARGIN = 1.45`, `CLU_PIV = 20`, cluster size counted only
> from members confirmed on or before i-1); a TOUCH definition with a cooldown
> so one approach is not counted twenty times; a REACTION definition that
> checks invalidation FIRST on every bar because OHLC cannot order intrabar
> events (L-012); a MATCHED random control (same confirmation bars, same
> cluster-size trajectory, price drawn by shuffling real ATR-scaled offsets),
> pooled over 3 seeds; and a `selfcheck()` with seven look-ahead assertions
> plus a driftless-random-walk NULL OFFSET over 8 seeds.
>
> Your job is to RUN it, not to rewrite it. Change it only if you find a
> defect, and if you do, say exactly what was wrong and why.
>
> **METHOD, in this order, and stop at the first failure.**
> 1. `python3 JARVIS/research/test_engine.py` — must print ALL TESTS PASSED.
> 2. `python3 JARVIS/research/level_reaction.py SELFCHECK`. **If any
>    look-ahead check FAILS, stop and report that. Do not run the markets.**
>    Record the NULL OFFSET (mean and standard error) — it is the number every
>    later result must be read against, not zero.
> 3. `python3 JARVIS/research/level_reaction.py ALL` — all 8 combinations.
> 4. `python3 JARVIS/research/level_reaction.py TOL` and `... GRID` —
>    sensitivity. A real effect degrades gracefully across `ln`, `N`, `X` and
>    the touch tolerance; an artifact lives at one setting.
> 5. Report the cluster-size gradient separately: is a cluster of 3+ pivots
>    (what LuxAlgo would actually draw) better than a bare single pivot
>    (cluster size 1, which LuxAlgo would not draw)? **This is the specific
>    question that decides whether the ≥3-pivot rule is worth building into
>    the Pine, and it is the only reason that rule would be worth building.**
>
> **THE CONTROL is the matched random level, and it is non-negotiable.** Do
> not report a bare reaction rate. E-050 exists because a headline number
> (+0.321R on GOLD 1h) died the moment a random arm was finally run on the
> same payoff, and the project had reported it to Veer for weeks. Every
> proportion you print gets: n, a Wilson 95% interval, the matched-random
> proportion beside it, and the difference read against the null offset.
>
> **HOW THIS RESULT COULD BE FOOLED — check each and say you checked.**
> - *Tolerance inflation.* If the touch band is as wide as the cluster band
>   (±0.69 ATR), "moving 1 ATR away" becomes a 0.31 ATR drift that happens
>   most of the time and measures nothing. The script's docstring says the
>   first version made exactly this mistake. Confirm `TOUCH_TOL` is 0.15 and
>   report the full tolerance sweep.
> - *Survivorship in the cluster.* A level only reaches cluster size 3 because
>   price came back to it twice already. The control must share that history —
>   verify that `randomise()` copies the member confirmation-bar list, and say
>   so.
> - *Multiple testing.* Count every bucket you look at across all 8 markets.
>   State P(a bucket lands ≥7 of 8 on one side) under the null, state how many
>   such cells are expected by chance, and compare to how many you found.
>   E-052's paragraph is the template — follow it literally.
> - *Direction of the null offset.* If the machinery has a positive bias on a
>   random walk, a small positive real result is that bias. Say which.
>
> **CONSTRAINTS.** No M1 or M5 data exists — 15m and 1h only, four symbols.
> Do not try to download data; every provider is blocked by egress policy.
> Verdict vocabulary only: CONFIRMED / SUPPORTED / PROMISING / UNPROVEN /
> REJECTED / DISPROVEN. Never report a number you did not compute. A
> well-evidenced NO is a complete deliverable — E-041, E-043 and E-053 are all
> negative and are the most useful results here.
>
> **DELIVERABLES.**
> 1. Append **E-054** to `/home/user/signals/JARVIS/state/EXPERIMENTS.md`
>    (E-054 is free; check first and note it if the number moved). Structure:
>    the question · the definitions · the null offset · the result table
>    (8 combinations, real vs matched-random vs difference) · the cluster-size
>    gradient · the sensitivity sweep · multiple-testing arithmetic · the
>    verdict in one word · what this does NOT say.
> 2. **Fix the script's docstring: it claims E-053, which is taken by the chop
>    study.** Renumber it to whatever you actually used.
> 3. Write `/home/user/signals/JARVIS/research/findings/10_level_reaction.md`
>    with the raw console output pasted verbatim.
> 4. One paragraph, in plain English with no jargon, that could be read to
>    Veer, answering his exact words: *"we can be able to react to previous
>    levels we need to see if price is near a price where it previously
>    reacted too."*
> 5. State plainly whether the ≥3-pivot cluster rule and the wick-sweep /
>    outbreak-retest split are worth building into
>    `JARVIS/pine/LiquiditySniper_v1.pine`, or whether the evidence says they
>    are decoration. **Do not edit the Pine — recommend only.**

**Good result:** an E-054 with 8 rows, every proportion carrying n and a
Wilson interval, the difference stated against the null offset, a clear
cluster-size gradient or a clear absence of one, and a one-word verdict.
**Bad result:** "levels react 58% of the time" with no control; or a positive
that only exists at one tolerance; or the phrase "statistically significant"
without the multiple-testing count beside it.

---

## B2 — Does the give-back exit beat a random entry on ITS OWN payoff?
**Agent type:** general-purpose · **Experiment number: E-055**

**Why second.** `InpUseGiveBack = true` is a shipped default on Veer's live
account, justified by E-051, and E-051 does not carry the control its own
predecessor E-050 made mandatory. This is the audit's most serious methodology
finding and it is cheap to settle.

### PROMPT (paste in full)

> You are running one experiment for Project TITAN. Read first:
> `/home/user/signals/CLAUDE.md`; `EXPERIMENTS.md` **E-050 in full** (it
> contains the standing rule you are enforcing), **E-051 in full** (the result
> you are testing), E-008 and E-052; `LESSONS_LEARNED.md` L-012 and L-013;
> `DECISIONS.md` D-009 and D-010.
>
> **THE QUESTION.** E-051 concluded that a peak-give-back exit (arm at 1.0R,
> give back 30%, tightening to 24% past 2R and 18% past 4R) beats the 3×ATR
> trail on 5 of 5 markets, and that conclusion put `InpUseGiveBack = true`
> into the live EA. E-050 established a standing rule: *"Every future strategy
> claim must be reported against a random-entry arm with the SAME payoff
> structure, the same bars and the same costs."*
>
> **E-051 does not have one.** `grep -n 'random' JARVIS/research/giveback_study.py`
> returns only the drawdown bootstrap (`curve_stats(..., seed=7)`, lines 44
> and 51). E-051 instead quotes E-050's `+0.202R`, which was measured under a
> 3R-target / 1R-stop / 50-bar-cap payoff — **a different exit rule**.
>
> So: **on identical bars, identical costs, and the GIVE-BACK EXIT ITSELF,
> does a random coin-flip entry score inside or outside the band that the
> SuperTrend entry achieves?**
>
> **DISPROVEN / the verdict flips to UNPROVEN IF** the SuperTrend entry's
> give-back expectancy sits inside the 5th-to-95th percentile band of 20+
> random-direction seeds on the same bars with the same give-back exit, on
> GOLD 1h or GOLD 15m. In that case E-051's "5 of 5" is a statement about an
> exit's interaction with a payoff, not about a signal, and it must be
> re-worded in EXPERIMENTS.md and in the EA's comment block.
>
> **METHOD.**
> 1. `python3 JARVIS/research/test_engine.py` — must pass.
> 2. Read `JARVIS/research/exits.py` (the give-back policy) and
>    `JARVIS/research/inversion.py` (which is where E-050's random arm lives —
>    reuse its machinery rather than writing a second one).
> 3. Build a random arm: same entry BARS as `donchian_trend` produced in
>    E-051, direction drawn by coin flip, **at least 20 seeds**, identical
>    costs from `study.COSTS`, and the **give-back exit** applied by the same
>    code path as the signal arm. Report median, 5th and 95th percentile.
> 4. Run all 8 symbol/timeframe combinations, not the 5 E-051 used. State the
>    three extra rows explicitly — E-051 reported 5 and there are 8.
> 5. Run the same comparison for the 3×ATR trail, so the *change* E-051
>    claims (trail → give-back) is measured against random on both sides. It
>    is entirely possible the give-back rule beats the trail AND both sit
>    inside the random band; that is a real and reportable outcome.
> 6. **Additionally measure the combination the EA actually runs.** The
>    shipped EA has `InpUseTrail = true` (mq5:138) AND `InpUseGiveBack = true`
>    (mq5:277) simultaneously, while E-051 measured them as alternatives. Add
>    a third policy arm: trail AND give-back together. **This configuration
>    has never appeared in any table and it is what is on the live account.**
>
> **THE CONTROL is the 20-seed random-direction arm on the same bars with the
> same exit.** Nothing else counts as a control here.
>
> **HOW THIS COULD BE FOOLED.**
> - *Payoff smuggling.* If the random arm gets a different stop, cap or cost
>   than the signal arm, the comparison is void. Assert equality of every exit
>   parameter across arms and print the assertion.
> - *L-012 optimism.* Every stop fill here is booked at its level, which is
>   free money. E-050 survived slippage up to 0.80 (16× default). Repeat that
>   sensitivity here; if the give-back rule's advantage evaporates at 4×
>   default slippage, say so — it triggers more often than a trail and so is
>   more exposed to fill optimism, and nobody has checked that.
> - *Seed count.* 5 seeds is not a band. Use ≥20 and report the percentiles.
> - *Cherry-picking the 5 markets.* Report all 8 or explain which failed.
>
> **CONSTRAINTS.** No M1 or M5 data — 15m and 1h, four symbols. Every provider
> is blocked by egress policy; do not attempt a download. Verdict vocabulary
> only. Never report a number you did not compute. **A negative here is the
> most valuable outcome available**, because it corrects a live default.
>
> **DELIVERABLES.**
> 1. Append **E-055** to `EXPERIMENTS.md` (check the next free number first).
> 2. `JARVIS/research/findings/11_giveback_control.md` — raw output pasted.
> 3. **If the verdict is that E-051's control was inadequate, edit E-051's
>    "What this does NOT say" section to add the finding, and say in your
>    report which lines of `SuperTrendSniper.mq5` (currently 261-284) now
>    carry a claim that needs re-wording.** Do not edit the .mq5 yourself —
>    B3 is the write brief and two writers on one file is a merge problem.
> 4. A one-paragraph recommendation to Veer: keep `InpUseGiveBack = true`,
>    turn it off, or keep it for the drawdown-path reason only. E-051 already
>    says it is "a redistribution, not an improvement in edge" — say whether
>    that survives.

**Good result:** three arms (signal / random×20 / inverted) × three exit
policies (trail / give-back / both) × 8 markets, with the slippage sensitivity
and an explicit statement of whether E-051's headline survives.
**Bad result:** re-running E-051 and reporting the same 5 rows; or comparing
against E-050's `+0.202R` again, which is the exact error being audited.

---

## B3 — Make the EA and the Pine tell the truth, and scale them to M1
**Agent type:** mql5-engineer (WRITE brief — run alone, nothing in parallel)

**Why third.** No data needed, nothing can be fooled by a backtest, and it
closes a defect class that has now bitten three times (E-053's chop comment,
plus D1/D2/D3 in this audit). It also removes a real behavioural bug (D4) that
makes the E-052 gate fire on a number the study never measured.

### PROMPT (paste in full)

> You are doing an engineering pass on two shipped artifacts, with NO new
> research. Read first: `/home/user/signals/CLAUDE.md`;
> `JARVIS/titan/PROMPT_AUDIT.md` **Part 1 in full** (it lists every defect by
> line number); `DECISIONS.md` D-009 and D-010; `EXPERIMENTS.md` E-051, E-052,
> E-053; `FAILURE_LOG.md` F-005 through F-008 and `LESSONS_LEARNED.md` L-008
> through L-010 — those five entries are about patch scripts that reported
> success while writing nothing, and you are about to run patch scripts.
>
> **THE PRINCIPLE.** A comment that describes behaviour the code does not have
> is worse than no comment, because Veer reads the comments and trusts them.
> Every change below either makes the code match its documentation or makes
> the documentation match the code — and you must say, for each, which
> direction you chose and why.
>
> **THE WORK, in priority order.**
>
> **1. `SuperTrendSniper.mq5:91` — "trend flips against it ... closed" is
> false.** No flip-close exists; `ManagePosition()` (1255-1367) has time cap,
> level partial, 1R partial, break-even and trail, and nothing else. When the
> SuperTrend flips against an open position, `StackAllows()` returns
> `"would hedge the basket"` (1922) and the signal is discarded.
> Veer's requirements are: *"faster reversals but no flip on a single opposite
> M1 candle"* and *"re-entry preferred over stubborn holding"*.
> **Do NOT implement a flip-close from instinct — that is the E-052 mistake.**
> Implement it as a switchable input **defaulting OFF**, with a confirmation
> requirement (N consecutive opposite closed bars, N as an input) so a single
> opposite M1 candle cannot flip it, and change line 91 to state the true
> default. Then write the brief for the experiment that would settle N. The
> honest deliverable here is a correct comment plus a testable switch, not a
> new behaviour turned on.
>
> **2. `RegisterSignal()` is unreachable while a position is open — a real
> bug.** It is called at line 920, after early returns at 874 (`HasPending`),
> 889 (`StackAllows`) and 892 (`RiskAllowsEntry`). With the default
> `InpMaxStack = 1`, `StackAllows()` returns false for every signal arriving
> while a position is open, so `g_runStartBar` and `g_lastSigDir` never
> update. `continuation.py:74-79` — the study E-052's gate is derived from —
> resets `run_start` on **every** side change regardless of position state.
> Move the `RegisterSignal()` call so the run clock tracks signals the way the
> study measured them. **Then state, in the commit message and in your report,
> what changes about `RunBars()` — this alters when the size-halving and the
> refusal fire, and Veer must be told it changed.**
>
> **3. Stale comments that contradict E-052.** Lines 1566-1583 still name
> `AGE / STRETCH / CROWDING` as the three readings; E-052 disproved stretch
> and crowding and the code implements run-age / run-distance / ADX. Lines
> 1693 and 1846 both say "old, stretched, crowded". Rewrite all three to match
> `TrendRisk()` (1657-1692) and E-052's actual table.
>
> **4. The ADX claim, `-0.132R` / `+0.304R`.** It appears at mq5:148-149,
> 904-905, 1005, 1583 and at `SuperTrendSniper_v1.pine`:29 and :81. Its only
> provenance is `setup_score.py:17`, which labels it `E-0xx` — **no such
> experiment exists**, and no entry in EXPERIMENTS.md contains those figures.
> They are R-conditioned with no random arm, which E-050 retracts as a class,
> and E-052 re-measured the same axis at "−1.3 pts, the weakest of the three".
> The Pine tooltip at line 81 calls it *"the single filter that survived being
> tested on data it was not chosen on"*. **Either find the experiment that
> produced those numbers and cite it by number, or replace both quotations
> with E-052's measured figures and delete the "single filter that survived"
> sentence.** Do not leave an unsourced measured-sounding number on Veer's
> chart.
>
> **5. The EA has no timeframe scaling and D-010 says it runs on M1 only.**
> `grep` for any minutes conversion returns one hit (line 833). The Pine
> converts everything via `barMins`. So the two products disagree on M1 by
> construction: trend filter 200 bars vs 3000 minutes, time cap 50 bars vs
> 750 minutes. `InpRunOldBars = 100` is an E-052 threshold measured on 15m/1h
> bars, applied raw. **Add the same minutes-based auto-scaling the Pine has,
> defaulting to the Pine's values, so the two products agree on any chart.**
> `InpDemaLen`'s comment `// DEMA length (60 on M1, 100 on M3)` is an
> instruction to hand-edit and it does not agree with the Pine — remove it.
>
> **6. Pine/EA parity.** `SuperTrendSniper_v1.pine`:8-11 claims "Every number
> below is the EA's default". It is not true: chop guard ON in Pine (65) vs
> OFF in EA (243); >3 flips in 50 bars vs ≥5 in 20; **no give-back rule in the
> Pine at all** (E-051); **no trend-persistence in the Pine at all** (E-052).
> Port E-051 and E-052 into the indicator, or amend the header to state
> exactly which rows differ and why. Veer watches the Pine and trades the EA.
>
> **7. The journal cannot answer the question it exists for.** `Journal()`
> (1150-1176) omits peak-R, peak-money, MAE and bars-held. At the EXIT write
> (line 1405) all four are in scope (1416-1419) and are used for the on-screen
> counters. `g_tkWorstPx` (MAE, declared 362, written 1757) is **read
> nowhere**; `Basket.sincePeakSec` (418, computed 1563) is **read nowhere**.
> MISSION.md says "Ranking must come from the EA's CSV journal, which
> persists." Add the columns. This is four lines and it is the cheapest
> high-value change available.
>
> **PROCESS RULES — F-005 through F-008 are all about this.**
> - Every programmatic edit must `assert` its anchor was found before writing.
>   A `str.replace` that matches nothing returns the input unchanged and
>   reports success (L-008).
> - **Write the file after EVERY edit, not once at the end.** F-007 lost a
>   money bug's fix because a patch script died before its single final write,
>   having already printed "ok" for edits that never reached disk (L-010).
> - After every change: `python3 JARVIS/tools/check_mq5.py <file>`,
>   `python3 JARVIS/tools/check_pine.py <file>`, and
>   `python3 JARVIS/tools/verify_fixes.py`. Per L-009, CLEAN means "passes the
>   specific checks modelled", **never** "compiles". There is no MetaTrader
>   here. Say so in your report.
> - Add a regression case to `verify_fixes.py` for each of the seven items, so
>   a future lost edit is caught by inspecting the artifact rather than by
>   trusting a log.
>
> **CONSTRAINTS.** Change no default that turns a new behaviour ON without an
> experiment number backing it. If you cannot cite an E-number, the default is
> OFF and the comment says it is untested. Do not touch
> `JARVIS/research/*.py` — B1 and B2 own those files.
>
> **DELIVERABLES.** The edited `.mq5` and `.pine`; the extended
> `verify_fixes.py`; and a report listing, for each of the seven items,
> whether you changed the code or the comment, and what Veer will observe
> differently. **Item 2 changes live behaviour — lead the report with it.**

**Good result:** seven items closed, every checker green, a regression case
per item, and an explicit "here is what will behave differently" paragraph.
**Bad result:** turning on a flip-close because it sounds right; or "fixing"
comments by deleting them; or reporting CLEAN as "compiles" (L-009).

---

## B4 — E-053's unanswered question: do the cost levers actually work?
**Agent type:** general-purpose · **Experiment number: E-056**

**Why fourth.** E-053 identified the mechanism behind Veer's live complaint —
cost as a fraction of stop — and named three levers, then implemented none of
them. This is the only brief that attacks the problem E-053 says is the real
one, and it is scale-free arithmetic, so 15m/1h results transfer to M1 better
than anything else in this repo.

### PROMPT (paste in full)

> You are running one experiment for Project TITAN. Read first:
> `/home/user/signals/CLAUDE.md`; `EXPERIMENTS.md` **E-053 in full**, plus
> E-040, E-041, E-050 and E-052; `DECISIONS.md` D-008, D-009, D-010;
> `LESSONS_LEARNED.md` L-012 and L-013; `KNOWN_LIMITATIONS.md`.
>
> **WHERE THIS COMES FROM.** E-053 found the ordering across 8 markets is
> almost perfectly explained by round-trip cost as a fraction of the 1.5-ATR
> stop: every market where the stop is more than ~15× the round trip is
> positive or flat, and both markets where it is under 2.5× lose about a third
> of a unit of risk per trade. It then extrapolated GOLD M1 at cost/stop
> 0.15-0.22 and concluded: *"The honest levers on M1 are a wider stop, a
> bigger required move, or a cheaper instrument/timeframe — all of which
> reduce cost/stop directly. Filtering does not."*
>
> **Nobody measured the levers.** `InpStopAtrMult` is still 1.5. There is no
> minimum-required-move gate anywhere in the EA.
>
> **THE QUESTION.** As the stop is widened (and position size shrunk to hold
> risk constant), cost/stop falls mechanically. Does expectancy in R actually
> rise with it, and is there an optimum — or does widening the stop simply
> trade one loss for another because a wider stop takes longer to resolve and
> the time cap or the trend closes it first?
>
> **DISPROVEN IF** expectancy in R is flat or falls as cost/stop falls, across
> the markets where cost/stop is currently high. That would mean the E-053
> correlation is not causal and is instead an artifact of which instruments
> happen to be cheap — which is a genuinely important negative and you must
> write it plainly.
>
> **THE OBJECTIVE DEFINITIONS you must code.**
> - `cost_frac(i) = round_trip_cost / (stop_atr_mult * ATR[i])`, with
>   round-trip cost = spread + 2×slippage + commission converted to price, all
>   from `study.COSTS`. This is E-053's own definition — reuse it, do not
>   invent a second one.
> - Sweep `stop_atr_mult` over at least {1.0, 1.5, 2.0, 3.0, 4.0, 6.0} with
>   **risk held constant in R terms**, so a wider stop is a smaller position
>   and never a bigger bet. State the assertion that verifies this.
> - Sweep a minimum-required-move gate: refuse the entry unless the target
>   distance is at least K × round-trip cost, K over {0, 5, 10, 20, 40}.
>   K = 0 is the current EA.
> - Report expectancy in R, trade count, and median `cost_frac` for every
>   cell. **A cell that improves expectancy by deleting 90% of the trades is
>   E-053's chop filter again — trade count must be in the table.**
>
> **THE CONTROL, and this is what makes the answer mean anything.** A wider
> stop with a fixed R-multiple target changes the payoff geometry, and E-050
> proved that a payoff structure can generate positive expectancy with no
> signal at all. So **every cell must also be run with a 20-seed random
> coin-flip entry on the same bars with the same stop and the same target.**
> The number that matters is not "expectancy rises with a wider stop" — it is
> "expectancy rises with a wider stop MORE than the random arm's does". If the
> signal arm and the random arm rise together, you have measured geometry, not
> a lever.
>
> **HOW THIS COULD BE FOOLED.**
> - *Survivorship via the time cap.* A wider stop resolves more slowly, so
>   more trades exit on the 50-bar cap rather than at stop or target. Report
>   the exit-reason mix per cell. If the improvement is really "more trades
>   exit at the time cap", say so — E-008 already measured that time exits do
>   well, and you will have rediscovered it.
> - *Sample shrinkage.* Wider stops on the same data give fewer resolved
>   trades. Report n per cell and a t-stat against the ~3.65 multiple-testing
>   threshold from MISSION.md.
> - *L-012.* Wider stops are hit less often, so intrabar overshoot optimism
>   falls with the stop width — which can look like an improvement. Run the
>   slippage sensitivity E-050 used (default up to 16× default) and report
>   whether the gradient survives.
> - *Gold's bull market.* KNOWN_LIMITATIONS names this as the single biggest
>   data risk. Split long/short per D-004 and report both.
>
> **THE M1 PROBLEM, stated honestly.** This repo has **no M1 or M5 data** —
> 15m and 1h only, four symbols, and every market-data host is blocked by
> egress policy. Do not attempt a download. What you CAN do is compute the
> gradient of expectancy against `cost_frac` on the data that exists, across
> its full observed range, and state what that gradient predicts at the
> 0.15-0.22 band E-053 extrapolates for GOLD M1. **Label every M1 statement
> as EXTRAPOLATION, as D-010 requires.** If the honest answer is "the observed
> range does not reach 0.15-0.22 on gold, so this cannot be answered here",
> that is a complete and useful deliverable — it converts an open question
> into a precise data request for Veer.
>
> **CONSTRAINTS.** All 8 symbol/timeframe combinations. Multiple-testing
> arithmetic in the E-052 style, stated explicitly. Verdict vocabulary only.
> Never report a number you did not compute. Run
> `python3 JARVIS/research/test_engine.py` first.
>
> **DELIVERABLES.**
> 1. `JARVIS/research/cost_lever.py` — new file, do not modify `chop.py` or
>    `cost_floor.py`.
> 2. Append **E-056** to `EXPERIMENTS.md`.
> 3. `JARVIS/research/findings/12_cost_levers.md` with raw output.
> 4. A specific recommendation on `InpStopAtrMult` and on whether a
>    minimum-required-move input should exist, with the number and the
>    evidence — or an explicit "the data cannot settle this, here is what
>    Veer must export."

**Good result:** a 6×5 grid per market with trade counts, exit-reason mix, the
random arm beside every cell, and a clear statement of whether the gradient is
signal or geometry.
**Bad result:** "a 3-ATR stop is better" with no random arm, no trade count,
and no exit-reason mix — which would be E-050 and E-053 repeated together.

---

## B5 — Run the conditional-edge script that already exists
**Agent type:** general-purpose · **Experiment number: E-042 (its assigned number)**

**Why fifth, not first.** `conditional_edge.py` is 743 lines, committed, and
briefed in full at `AGENT_PROMPTS.md:513-744` as A3. **The brief already
exists and is good.** It is ranked below B1-B4 only because those four correct
things that are currently live on Veer's account, whereas this opens a new
branch. It should not be rewritten from scratch.

### PROMPT

> Use `JARVIS/titan/AGENT_PROMPTS.md`, section **A3 — CONDITIONAL EXPECTANCY
> (E-042)**, lines 513-744, as your brief. Paste it in full. It is
> self-contained by design.
>
> **Three amendments, which are the whole reason this is being re-briefed:**
>
> 1. **The script already exists and is committed.**
>    `JARVIS/research/conditional_edge.py`, 743 lines, added in commits
>    `65250a7` / `2d19d9a`. A3 was written on the assumption it might be in
>    flight (`AGENT_PROMPTS.md:36-42`). It is not in flight; it is finished
>    and was never run to a recorded result. **Read it end to end first, run
>    it, and only modify it if you find a defect.** There is no E-042 in
>    EXPERIMENTS.md — confirm that with `grep` before you start, and if the
>    number has since been taken, use the next free one and say so.
>
> 2. **E-050 post-dates the A3 brief and changes what counts as a result.**
>    Any conditional state that shows a positive forward return must be
>    reported against a **random-entry arm on the same bars with the same
>    payoff**, not against zero. A3 as written predates that rule. Add the
>    arm. If the script does not have one, that is the defect you are allowed
>    to fix.
>
> 3. **D-010 post-dates it too.** Veer trades M1 for the SuperTrend EA and
>    M15/M5/M1 for liquidity. H1 results are evidence about the strategy
>    FAMILY and about scale-free mechanisms; they are **not** evidence about
>    his account and must not be presented as a recommendation. Any hour-of-day
>    or day-of-week finding on 1h data must carry that label. State explicitly
>    whether the state you found is scale-free (calendar effects mostly are;
>    "N bars after a shock" mostly is not).
>
> Everything else in A3 — the five state families, the look-ahead rules, the
> multiple-testing requirement, the deliverable structure — stands as written.

**Good result:** E-042 finally exists, with a verdict, and MISSION.md's
next-action list loses an item.
**Bad result:** rewriting the 743-line script from scratch, or reporting a
time-of-day effect with no random arm and no multiple-testing count. There are
24 hours × 5 days × 4 markets × 2 timeframes of places to find noise.

---

## B6 — Two small things Veer asked for that need no agent

Do these in the main session; they are too small to spawn for.

1. **Answer the demo-account question.** He asked, weeks ago, whether he
   should open a demo account with his real broker. `grep -rn "demo account"`
   across `JARVIS/state/`, `JARVIS/titan/` and the root markdown returns
   nothing. The material to answer it already exists: D-006 (no live action
   without per-session confirmation), D-008 (PU Prime, 1:500, and the finding
   that stop distance not leverage is the binding constraint), E-053's note
   that *"If PU Prime's M1 gold spread is wider than 0.30 at the times Veer
   trades, every number above is optimistic"*, and mq5:256 (`InpDemoOnly =
   true` by default). A demo on **his own broker** is the only way to measure
   the real M1 spread and the real slippage, both of which every M1 number in
   this repo currently assumes. That is a yes with a reason, and it has been
   sitting unstated.

2. **Fix the memory files, per CLAUDE.md's own rule.** §1.6 lists six
   specific staleness defects. `SESSION_STATE.md` and `NEXT_SESSION_PROMPT.md`
   still send a new session to attack `donchian_trend`, which E-009 closed;
   `NEXT_ACTIONS.md` A-000 still says five findings files are missing when
   three exist; `MISSION.md`'s next-action #1 ran as E-041; L-011 is
   referenced by MISSION.md and AGENT_PROMPTS.md but lives in
   `LIVE_EVIDENCE.md:45` instead of `LESSONS_LEARNED.md`; `USER_GOALS.md`
   still says the broker is unknown. CLAUDE.md says: *"If memory and
   repository disagree, TRUST THE REPOSITORY and fix memory."* It has not been
   done for four sessions.

---

## Deliberately NOT briefed, and why

- **Another entry pattern, filter, or confluence score on 15m/1h.** Closed by
  E-036, E-039, E-041 and restated in `AGENT_PROMPTS.md:26-32`: a filter moves
  a zero-edge entry toward zero, never past it. Any brief that would improve a
  directional entry is dead on arrival.
- **Non-directional / volatility structure on spot.** Closed by E-043 and
  L-013: a spot payoff is linear in price, every exit is a stopping time, and
  by optional stopping any non-anticipating exit has zero expected gross on a
  martingale. It reopens only if an options-capable account exists.
- **Any parameter sweep for its own sake.** E-021 and E-030: in-sample winners
  failed out-of-sample, and no stop/target pair held on any of 8 pairs.
- **Downloading M1 data.** Blocked by egress policy, not by effort
  (KNOWN_LIMITATIONS.md). The route is `JARVIS/ea/tools/ExportHistory.mq5`
  and it runs on Veer's machine, not here. Every brief above states this so no
  agent burns a run rediscovering it.

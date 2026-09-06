# Failure log

Failures are training data. Every entry: what broke, root cause, class, fix,
and the regression test that now guards it.

---
## F-001 — walk-forward produced impossible 0% win rates
- **Class:** CODE / ARCHITECTURE
- **Symptom:** Walk-forward folds reported 0% win rate over 40+ trades and
  ~-0.95R expectancy. Statistically impossible; a real strategy cannot lose
  every single trade.
- **Root cause:** Strategies precompute per-series state (higher-timeframe
  trend gate, swing pivots) indexed by bar position. `walk_forward()` was
  handed a strategy object built on the FULL series, then ran it over a
  SLICE. Bar index `i` therefore referred to two different bars — the gate
  and pivots came from the wrong point in history. Stops were placed on the
  wrong side of price, so almost everything stopped out.
- **Detection:** The number was too extreme to be real. A plausible-looking
  wrong number would have shipped.
- **Fix:** `walk_forward()` now takes a FACTORY `make_fn(sub) -> signal_fn`
  and rebuilds the strategy per fold, so all precomputed state matches the
  series being traded.
- **Regression test:** `test_engine.py` :: F-001 block asserts walk-forward
  folds never show sub-2% win rates.
- **Lesson:** Any strategy carrying precomputed per-bar state MUST be
  rebuilt for each data slice. Generalised in LESSONS_LEARNED L-002.

---
## F-002 — bulk `rm -rf` of repo contents was blocked
- **Class:** PERMISSION
- **Symptom:** Combined `git rm -r --cached . && rm -rf ...` denied by the
  sandbox classifier.
- **Root cause:** Broad recursive deletion is treated as destructive.
- **Fix:** Used explicit `git rm <named files>` instead — tracked, reviewable,
  recoverable from git history.
- **Lesson:** Delete by explicit filename, never by recursive wildcard.

---
## F-003 — five research agents killed by the account usage limit
- **Class:** ENVIRONMENT / EXECUTION
- **Symptom:** all five background research agents terminated with HTTP 429
  ("session limit") within minutes of each other. Four had reached the point of
  writing their findings; only one file survived.
- **Root cause:** five Opus agents launched simultaneously, each doing
  web-heavy research, against a shared session budget. Anthropic's own
  reporting puts multi-agent token use at roughly 15x a chat interaction, so
  five in parallel exhausted the budget quickly.
- **Fix:** launch research agents in batches of 2-3, not 5. Checkpoint the main
  session's own findings to disk BEFORE spawning, so a limit hit never costs
  verified work.
- **Lesson:** parallelism is not free. Budget it like any other resource.
  Generalised in LESSONS_LEARNED L-007.

---
## F-004 — recommended installing a tool that evades provider limits
- **Class:** REASONING / RESEARCH
- **Symptom:** recommended OmniRoute to Veer after one web search, in the same
  session that refused to evade usage limits on principle (D-005).
- **Root cause:** treated search-result enthusiasm as evidence. The tool ships
  TLS/JA3-JA4 fingerprint stealth, whose purpose is defeating provider
  anti-abuse detection, plus a disclosed default-secret auth bypass. The URL
  cited was also not the canonical repository.
- **Fix:** recommendation retracted in RESEARCH_QUEUE R-001.
- **Lesson:** L-006 — verify the canonical source and what a tool actually does
  before recommending an install.

---
## F-005 — shipped a Pine file that could not compile
- **Class:** CODE / PROCESS
- **Symptom:** `LiquiditySniper_v1.pine` v1.2 was sent to Veer using
  `needRetest` and `retestBars` in seven places while declaring neither. It
  would have failed on paste.
- **Root cause:** a Python string replacement meant to add those two inputs did
  not match — the anchor had `minLvlAge  = ` (two spaces), the file had
  `minLvlAge = ` (one). `str.replace` returns the string unchanged when the
  anchor is absent, so it FAILED SILENTLY and reported success.
- **Why my own audit missed it:** the audit I ran checked declaration ORDER
  (nothing used before it is defined) but never declaration EXISTENCE. It
  passed a file with two names that were never defined at all.
- **Fixes:**
  1. `JARVIS/tools/check_pine.py` — a real static checker that verifies every
     identifier used is declared somewhere. Regression-tested against the exact
     broken file: it reports both names and exits 1.
  2. Any `str.replace` used to edit code must `assert` its anchor was found.
     A silent no-op that reports success is worse than a crash.
- **Lesson:** generalised in LESSONS_LEARNED L-008.

## F-006 — Shipped a Pine file that could not compile, for five commits
An adversarial review found this construct in BOTH indicators:

```pine
        totM += (array.get(hExt, j) - array.get(hEnt, j)) * array.get(hDir, j)
                * ccyPerPt * (lotSize / 0.01)
```

The first line closes every bracket it opens, so the second is an explicit
wrapped line - and it is indented 16 spaces. Pine requires a wrapped line to be
indented by a number of spaces that is NOT a multiple of four, because those
boundaries delimit blocks. At 16 the parser raises `end of line without line
continuation`.

Introduced in `892c12f` and present in five subsequent commits. Every one of
those was sent to Veer described as ready to paste and trade. **The files had
not compiled since.**

WHY THE CHECKER MISSED IT. `check_pine.py` gained a continuation check earlier
the same session - and it matched only lines beginning `and`, `or`, `?` or `:`.
This line begins with `*`. The check was written against the failure I had in
mind rather than against the rule, so it passed a file that violated the rule
it was written to enforce.

This is F-005 repeating with a different mechanism: a tool built after shipping
a non-compiling file, which then failed to catch the next non-compiling file.

FIXES
1. Both files corrected - the expression is now two statements, no wrap.
2. The continuation check now matches ANY operator that can start a wrapped
   line (`* / + - % == != <= >= < >` as well as and/or/?/:), and is
   regression-tested against a file containing the exact original defect.
3. LESSON L-009 below.

## L-009 — A check written from the example, not the rule, only catches the example
The continuation check was built from one remembered failure shape and matched
four operators. The rule it was enforcing - "a wrapped line must not be indented
by a multiple of four" - says nothing about which operator starts the line. Any
check that encodes an instance instead of the rule will pass the next instance.

Corollary that cost the most here: a static checker reporting CLEAN was treated
as evidence the file compiled. It is not. It is evidence that the specific
things the checker models are absent. Nothing in this repo can compile Pine, so
"CLEAN" must always be reported as "passes static checks", never as "compiles".

## F-007 — Shipped a file with an undeclared variable, and lost a money bug's fix with it
Veer pasted the indicator and got `Undeclared identifier "lastFireBar"` at line
1314. He was right and it was my error.

WHAT HAPPENED. A patch script applied `lastFireBar := bar_index` successfully,
printed "ok" for the edit that DECLARED it, and then aborted on a later anchor.
The script only wrote the file at the very end, so every edit it had already
reported as done was discarded - the "ok" lines described an in-memory string
that never reached disk. The declaration was lost; the usage, added by a
different script, survived.

WHAT ELSE WENT WITH IT. The same abort dropped the fix for the triple-entry bug
(`canFire` counting only OPEN trades and not the pending queue) - the defect
that put three positions on one idea and turned a 1R loss into 3R. **I had told
Veer that was fixed. It was not.**

WHY THE CHECKER DID NOT CATCH IT. `check_pine.py` treated `:=` as a
declaration. So it saw `lastFireBar := bar_index`, recorded the name as
declared, and never reported that nothing declared it. In Pine `:=` is
ASSIGNMENT to a name that must already exist; only `=` declares. With that
fixed the checker reproduces Veer's exact error on the exact line.

FIXES
1. `:=` no longer counts as a declaration in check_pine.py.
2. Patch scripts write the file after EVERY edit, not once at the end.
3. `JARVIS/tools/verify_fixes.py` asserts all 27 claimed fixes are present in
   the files, by pattern, so a lost edit is caught by checking the artifact
   rather than by trusting a script's own output.

## L-010 — A patch script's success message is not evidence the file changed
Every "ok" printed by a patch script describes an in-memory operation. If the
script dies before writing, all of them are lies, and they are convincing ones
because they are specific and ordered. Two rules follow: write after every
edit, and verify the artifact afterwards rather than reading the log. This is
the same failure family as L-009 - trusting a proxy for the thing instead of
the thing.

## F-008 — A function defined after its first call; the checker could not see it
Veer pasted the indicator and got `Could not find function or function
reference 'keepSweep'` at line 718. `keepSweep` was defined at line 1618 and
called at 718. Pine is single-pass: a function must appear before its first use.

WHY THE CHECKER MISSED IT, and this one is structural. The identifier scan uses
`(?<![\w.])([a-zA-Z_]\w*)(?![\w(])` - the trailing `(?!\()` deliberately skips
any name followed by an opening bracket, so that builtins like `math.max(` are
not reported as undeclared. The side effect is that a FUNCTION CALL is never
examined at all, by the existence check or the ordering check. Every user
function call in both files was invisible to the tool.

Fixed with a dedicated `check_call_order`: collect every `name(...) =>`
definition line, then flag any call appearing earlier in the file.
Regression-tested against a file containing exactly this fault.

This is the third distinct compile rule the checker has learned by first
letting a real failure through: illegal line wrapping (F-006), then `:=`
treated as a declaration (F-007), now function calls excluded from scanning.
Each hole was invisible until a specific file fell into it, which is the
argument for keeping every regression case rather than deleting them once
green.

---

## F-009 — Shipped a non-compiling Pine for the fourth time. `ta.adx` does not exist.
Date: 2026-09-01. Veer's screenshot: `SuperTrendSniper_v2.pine` line 116,
**"Could not find function or function reference 'ta.adx' (CE10271)"**.

Pine has no `ta.adx`. ADX comes out of `ta.dmi(diLength, adxSmoothing)` as the
THIRD element of a tuple: `[diPlus, diMinus, adx] = ta.dmi(14, 14)`.

### Why the checker passed it
`check_pine.py` validated that `ta` was a known namespace and then accepted
**anything** after the dot. Every `ta.<something>` was invisible to it.

This is the same shape as F-006 and F-008 and it is the third time:
- F-006: the continuation check matched `and|or|?|:` because those were in the
  example, not because the rule was about operators. `*` slipped through.
- F-008: the identifier regex skipped names followed by `(`, so every function
  CALL was invisible and a call-before-definition shipped.
- F-009: the namespace check stopped at the dot, so every member name was
  invisible.

**The pattern in all three: the checker verified the part of the expression it
happened to parse and silently accepted the part it did not.** A checker that
does not know it is ignoring something reports CLEAN with total confidence.

### Fixed
`check_namespace_members()` now validates the member names of `ta.`, `math.`
and `str.` against explicit lists, and REPORTS an unknown one rather than
assuming it is fine. The lists are not exhaustive and do not need to be: a
false alarm costs one line in a list, a missed one costs a shipped file that
does not compile. Confirmed by watching it fail on the real line before fixing
the code.

### The rule this should have followed the first time
**Never let a checker's silence mean "valid".** If a check cannot parse part of
an expression, that part must be reported as unchecked, not treated as correct.
Three of the four shipped compile failures came from a checker being confidently
quiet about something it never looked at.

---

## F-010 — I filtered the EA into silence, twice, after being told not to
Date: 2026-09-01. Veer: *"we are now not hitting same trades as before and
having delayed entry"*.

`InpMaxCostFrac` shipped at **0.10**. E-053, which I wrote the same day,
measured M1 gold at **0.15–0.22** cost/stop. **The EA therefore refused
essentially every M1 gold entry.** The identical mistake was in
`SuperTrendSniper_v2.pine`, where the cost gate deleted the signals and the
panel quietly said "refused by COST" — Veer reported that one first and I
fixed the Pine without checking whether the EA had the same constant. It did.

On top of it: a 15-bar same-direction re-entry cooldown, a trend-risk score
that REFUSED entries at 3/3, and a chop guard. Four gates, stacked.

### Why this is worse than a bug
Two things I already knew said not to do it.
1. **Veer, repeatedly, from his first message:** 100+ signals a day is FINE and
   must not be reduced; the problem is execution AFTER entry, not signal count.
2. **My own E-053:** filters improved total R in 5 of 8 markets — a coin flip —
   and they hurt precisely the markets that were winning, because they do not
   select, they just remove trades and drag the result toward zero.

I measured that filters do not work, wrote it down, and then spent the
afternoon adding filters.

### Fixed
- `InpMaxCostFrac` 0.10 → 0.30, i.e. it catches a blown-out spread and nothing
  else. The cost problem is real; the answer to it is a wider stop or a
  different timeframe, not refusing to trade.
- `InpReentryCool` 15 → 3 bars, `InpReentryNeedsNewSignal` → false. Stops the
  instant same-candle re-entry without deleting the day.
- Trend risk now SIZES DOWN and never refuses. A three-percentage-point
  measured effect is a discount, not a veto.

### The rule
**A gate that fires in normal conditions is not a gate, it is a switch that
turns the strategy off.** Before shipping any threshold, compute where the
live market actually sits relative to it — the number was already in E-053 and
I did not look at it.

---

## 2026-09-06 — TWENTY-THREE LIVE-SAFETY DEFECTS, NONE OF THEM SYNTAX

An MQL5 audit of both EAs, run because E-151 found one silent-failure bug in
`SweepSniper.TrailStop()` and the obvious next question was how many more of
that class there were. The static checker reports both files clean and always
did: **none of this is syntax, and no tool in this repo could have caught any
of it.**

The pattern, stated once because it is the same pattern twenty-three times:
**a trade call whose result is discarded, followed by a log line that announces
success.** Read the Experts log afterwards and it says the trade exited. It did
not.

### The ones that would have cost money first
- **The pending order was tracked in one `ulong`.** A failed `OrderDelete` set
  it to 0 anyway; so did every `OnInit` (restart, recompile, timeframe change,
  **any parameter change**); so did an async `ResultOrder()` of 0. Then `TryArm`
  believes it is flat and arms a SECOND order on a live one. Both fill. That is
  double the position and double the risk cap that the whole of E-138 exists to
  enforce. Fixed by counting orders at the broker, which is the only source of
  truth.
- **The daily-loss and max-drawdown guards never closed anything.** They
  cancelled the pending order and stopped arming. The position whose floating
  loss caused the breach kept running - and a prop firm measures the daily limit
  on EQUITY, so the guard fired at the exact moment it needed to act and did
  nothing. SuperTrendSniper had the fix (`InpFlattenOnBreach`); SweepSniper
  never received it.
- **SuperTrendSniper's flatten ran once, on the transition tick, unchecked.**
  The breach tick is a fast, wide-spread, requote-prone tick - the likeliest
  tick in the session for a close to be rejected. One rejection and the position
  ran to its stop with the feature switched on and nothing in the log.
- **The max drawdown was measured from ATTACH equity, not peak.** Attach at £60,
  floor £56.40. Grow to £100 and the floor is *still* £56.40 - a 44% drawdown
  from peak before a "6% max drawdown" guard says a word. `g_peakEq` was being
  computed every tick and read by nothing.
- **`SweepSniper`'s only exit was unverified.** There is no take profit in that
  EA by design, so `PositionClose` on the give-back is the exit. Its result was
  discarded and `"trail level already passed - market exit"` was logged either
  way.
- **`DisasterBrake` force-closed every losing short on the first ticks after
  attach.** `iClose()` returns 0.0 for a bar not yet cached; for a short,
  `against = (0 - 3900) * -1` clears any threshold. It is the FIRST thing
  `OnTick` calls, above the bars-available guard.
- **`Bars()` was used as a clock.** It plateaus at the terminal's "max bars in
  chart" setting - after which the time exit never fires again - and jumps by
  thousands when history back-fills, firing the time exit on a position seconds
  old. Now `iBarShift` off the position's own open time.
- **`SYMBOL_TRADE_FREEZE_LEVEL` was read nowhere in the project.** Inside that
  band the broker refuses both a stop modification and an EA close, and the
  give-back trail puts its stop close to price by construction.
- **The fixed-lot path ignored `SYMBOL_VOLUME_MIN/STEP`.** If this broker's
  minimum on gold is not 0.01, every order returns 10014 and the EA silently
  never trades.
- **Nothing ever asked whether trading was possible** - `TERMINAL_CONNECTED`,
  `MQL_TRADE_ALLOWED`, `ACCOUNT_TRADE_EXPERT` were checked nowhere. AutoTrading
  off meant the exits logged success while doing nothing.
- **A "confirmed pivot" could be accepted at price 0.0.** `iHigh`/`iLow` return
  0.0 for bars that are not loaded, and 0.0 passes every comparison.
- **`DEAL_ENTRY_INOUT` was dropped** (netting accounts, which several prop firms
  use) and a PARTIAL close reset the trail's peak on a position still open.
- **`OrderCalcMargin` was called nowhere**, so a too-small account produced 120
  bars of identical rejections and a log that looked like a broker fault.

### The lesson, and it is a rule now
**A trade call whose return value is discarded is a bug, without exception.**
Not a style point. Every single one of these produced a log that said the
opposite of what happened, which is worse than no log at all: it is what you
would read after losing money, to find out why, and be told nothing was wrong.

### Still unverified, and it needs a terminal
Nothing here has been compiled - `check_mq5.py` cannot do that and says so. PU
Prime's actual stops level, freeze level, volume min/step, tick size, filling
mode and XAUUSD margin are all numbers the code now reads instead of assuming,
but which of them bite can only be seen on a live chart. **Print them all in
OnInit and read them off the terminal before the funded account.**

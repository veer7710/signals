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

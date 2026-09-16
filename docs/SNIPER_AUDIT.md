# SNIPER — audit, decisions, and what each change is worth

`XAUUSD_QUAD` is retired. Everything is `SNIPER` v20.00.

**The source files were not reachable.** `XAUUSD_QUAD.mq5` (~20,700 lines) and
`xau clean` are not in this repo and not in its history — I searched every
commit on every branch and the whole filesystem. So `mq5/SNIPER.mq5` and
`pine/XAU_CLEAN.pine` are **built from the brief**, not patched from source.
Send the originals and I will diff mechanism by mechanism.

---

## 1. The verification harness — built first, and it earned its place immediately

`tools/mql5_check.py` is the compiler substitute. Ten checks: brace/paren
balance, declare-before-use, duplicate definitions, call-site arity vs
definition arity, inputs read above their declaration, orphaned inputs,
write-only globals, uncalled functions, format-string arg counts, include
sanity. `tools/add_fwd_decls.py` generates the forward-declaration block.

**On first run it failed all five existing EAs** with exactly the trap the
brief describes — functions called before definition with no prototype. It
then caught a signature trap I introduced while fixing them
(`CloseAll("time stop")` against a zero-arg definition), and four orphaned
inputs of the `T_GoldSlowER` class — `InpMaxBars` declared and never wired in
four files, `InpStallBars`, and a write-only `gTicket`.

It also had three bugs of its own, found and fixed:
- `armedDir==1` matched the assignment regex, because `==` starts with `=`
- `FUNC_FWD`'s `[^;]*` ran past the `)` into the function **body** and matched
  its first `;`, so every definition registered as its own forward declaration
- `^\s*` swallowed preceding blank lines, shifting every reported line by 6

All six files now pass. Run it on every change.

---

## 2. What each mechanism is worth, from the tickets

Reproduce with `python3 research/sniper_economics.py`.

### Mechanism 1 — the 60-second cut. This is the whole build.

| Finding 2 cohort | n | net | hit rate |
|---|---|---|---|
| went 0.60+ adverse in first 60s | 48 | −£86.49 | **6.2%** |
| did not | 23 | **+£49.92** | **82.6%** |

Cutting the adverse cohort at −0.60 costs 0.60 pts + 0.30 spread = **£0.66**
each. 48 × £0.66 = £31.67 instead of £86.49. The 71-trade block goes
**−£36.57 → +£18.25**.

Checked against a **bigger independent slice** — Finding 4's 153 losers that
never got even £0.30 up, losing £252.27 between them, average £1.65 each.
Cutting at £0.66 saves £0.99 each = **£151 on a day that lost £147.04.**

Two independent slices of the same day agree. Nothing else in the brief comes
close to this, which is why it is mechanism #1 and why the EA runs a
**1-second timer** — a bar-close EA physically cannot enforce a 60-second rule,
which is part of why it was never enforced.

**The 82.6% is not a projection. It is what your own tickets say.** It is also
not an entry filter — you cannot know in advance which cohort a trade is in.
It is a *management* rule, and that is why it works.

### Mechanism 2 — the peak lock

| exit | n | peak pts | net pts | kept |
|---|---|---|---|---|
| SL-HIT | 109 | 173.4 | −54.7 | −32% |
| **BASKET-LOCK** | 15 | 26.0 | +25.4 | **98%** |

Near-identical average peak per trade (£1.62 vs £1.64). One kept 98%, the
other gave back its entire peak and more. **The only difference was which
mechanism owned the exit.** So every exit in SNIPER locks like BASKET-LOCK.

Your instinct — a stop at £1 of profit, trailed up — is right. The unit is
wrong. At M1 ATR 1.47 one bar moves **£1.08** at 0.01 lots: a flat £1 lock is
unreachable on a dead night and triggered by a single bar on a normal one. So
the lock is in ATR, and the keep-fraction **scales with the peak** — 50% of a
small peak rising to 85% of a large one — which protects a small winner
without capping a runner.

### Bug 1 — the inverted grace window, and why it mattered most

`T_MinHoldSecs = 180` against a 240-second average hold stood down every
discretionary exit for 75% of a trade's life. **21 of 32 exit mechanisms fired
zero times in 279 trades.** The exit attribution table was not telling you
which exits were right — only which were *reachable*.

In SNIPER the grace window defaults to 0 and is **hard-capped below the
fast-fail window** in code (`GraceSecs()`), so the cut can always act. A grace
window that outlives the exit it gates is the bug, not the setting.

### Bug 3 — the duplicate guard

`DuplicateFill()` read deal history, which is empty when two clocks fire in one
`OnTick`. The guard is now **in memory at send time** (bar + direction + price
within 0.05 ATR). Note Part 6 #3: volumes summing to 0.02–0.05 at one price are
**one signal split**, not duplicates — blocking those just trades smaller, and
that revert is respected here. The first leg carries the full size.

---

## 3. Where I disagree with the brief

**Spread is 48%, but not at 0.01 lots.** The brief says £76.53 of a £159.79
loss. 275 × 0.30 = 82.5 pts; £76.53 / 82.5 = **£0.928/pt**, which is ~0.0127
lots average, not 0.01. The 48% is right; the "at 0.01 lots" framing is not.
It matters because it means average size was already above minimum.

**Finding 7 and Part 5D are the same instinct, opposite outcomes.** Fading
distance from the mean lost in every bucket; fading range extremes lost both
ways. But Part 5D's sweep is *also* fading an extreme — the difference is the
confirmation. So the confirmation is not a refinement of the idea, it **is**
the idea, and SNIPER refuses any absorption entry that lacks it
(reclaim + body close through the run origin + at least 2 measured touches).

**The 82.6% cohort cannot be selected in advance.** I want to be exact about
this because it is the one thing that could be over-read: you do not get to
enter only those 23 trades. You enter all 71 and the rule removes the other 48
cheaply. The hit rate of what *survives* is 82.6%; the hit rate of what you
*enter* is unchanged.

---

## 4. Parity contract

| | EA | Pine |
|---|---|---|
| ATR | `iATR(14)` | `ta.atr(14)` |
| level | swing ±3, merged within 0.15 ATR | same |
| significance | ≥2 measured touches | same |
| pierce | 0.05 ATR | same |
| expansion | close beyond by 0.35 ATR → level dead | same |
| confirmation | body close through run origin | same |
| one event per level | level marked dead on fire | same |
| range rotation | ER < 0.15, 20% / 80% of range | same |
| stop | swing ±3 + 0.30 ATR, skip > 3 ATR | same |
| signal timing | closed bar → next bar | confirmed bars only |

The Pine also draws the **cut level** (dotted) and turns the stop line solid
once the lock arms, so you can see which mechanism owns the exit at a glance.

---

## 5. Still open

- **Part 5E, legs-to-legs** — untested. Needs the M1 tick/bar export; it is
  folklore until measured, and the one cohort the brief says tested positive
  (entries at 60–80% of the prior 30-min range in the trend direction) is worth
  measuring first.
- **Part 5G, limit orders at levels** — capturing the spread instead of paying
  it is worth roughly half the loss if it fills reliably. SNIPER sends market
  orders today. The absorption entry is a natural limit candidate because the
  level is known in advance.
- **Part 5F, the signal audit** — Supertrend/DEMA/Two-Pole/confluence vote has
  never been instrumented. The CSV now makes that answerable.

The CSV (`SNIPER_trades.csv`, common folder) writes one row per trade with
entry/exit, MFE as `peak_pts`, `kept_frac`, hold seconds, regime, both size
multipliers, and whether the cut or the lock fired. **"How many trades went
above £1" is now a spreadsheet filter.** One live session with this on is worth
more than a week of screenshots.

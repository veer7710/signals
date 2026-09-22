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

---

# 6. Four faults read off the live M1 screenshots (15 Sep, 18:23–20:04)

Reproduce with `python3 research/chart_read.py`. Every number is read off the
price axis in the images.

**The screenshots cross-check clean.** 0.02 lots showing +£0.98 = +0.67 pts,
i.e. £1.466/pt, exactly 2× the brief's £0.733 at 0.01. The stops read
1.63 and 1.70 pts = **1.11 and 1.16 ATR**. The stop geometry is fine. The stop
is not the problem.

### Fault 1 — the spike-top entry, on camera

The 18:53 bar ran **4290.10 → 4294.52 = 4.42 pts = 3.0 ATR in one minute**, and
a blue BUY arrow sits *inside* it around 4291.9–4292.5. The next arrow is a red
SELL about two bars later near 4289.75. That is **−2.45 pts = −£3.59 at 0.02
before spread**.

Fix: `TravelOK()` gates on how far price has already travelled **within the
bar, in the trade's own direction** — not on bar size. A big bar you enter at
the *start* of is fine; 1.5 ATR up its own body is not.

### Fault 2 — the whipsaw is eating the move

Image 4: roughly **20 arrows between 18:52 and 20:04** — one every 3.6 minutes,
16.7/hour, alternating buy/sell.

| lots | spread per hour | per 8h session |
|---|---|---|
| 0.01 | £3.67 | £29.32 |
| 0.02 | £7.33 | £58.64 |
| 0.03 | £11.00 | £87.96 |

Across that 72-minute window price moved **11.70 pts** and the spread bill at
0.02 was **6.00 pts**. You are paying **51% of the entire move** before a
single trade is right or wrong.

Fix: `FlipOK()` — the opposite direction is refused for 180s unless price has
moved 0.80 ATR since the last exit.

### Fault 3 — the equal high. This is the one you described.

> *"bullish trend hit an equality high and we had entered a buy before and it
> just started dumping and we hit stop loss"*

An equal high is **not resistance**. It is a shelf of resting sell orders plus
the stops of everyone long underneath it. Price is *attracted* to it, trades
through to fill them, then reverses. Buying into an untested shelf is buying
the liquidity that the move exists to collect — so the dump was the point of
the move, not bad luck.

Fix: `RoomOK()` requires **≥1.20 ATR of clear air** to the nearest untested
level, and only blocks when that level is a genuine **shelf** (two or more
levels within 0.20 ATR, or 3+ measured touches). A lone swing high does not
block. After the sweep the same level becomes tradeable the *other* way, which
is the absorption test already in SNIPER.

The Pine draws that shelf in orange **only while it is actually blocking**, so
you can see the reason rather than just the refusal.

### Fault 4 — news and the volume that front-runs it

> *"may have been cuz news was in few minutes volume was being put into market"*

Fix: `NewsClear()` uses two independent detectors — the terminal economic
calendar (high-impact events, 5 min before / 3 min after, on the symbol's
profit currency) **and** a raw tick-volume surge at 3× the 50-bar median, which
works on any terminal whether or not the calendar is populated.

---

# 7. The fast-fail ships in SHADOW MODE, and here is why

You described a live 0.03: **−£5 first, then +£5, back to +£3, then closed.**

−£5 on 0.03 lots is 2.27 pts = **1.55 ATR against**. If that happened inside
the first 60 seconds, mechanism 1 would have cut it at −£1.32 and missed the
whole recovery.

Finding 2 says cutting is right *on average* — 48 trades at a 6.2% hit rate.
Your trade may be a genuine counterexample, or the −£5 may have taken ten
minutes, in which case the rule would never have touched it. **I cannot tell
from a screenshot, and it is your money.**

So `InpFFShadow = true` by default. The EA logs every trade it *would* have
cut, lets it run, and records the outcome in the CSV column `ff_shadow`. After
one session you can filter that column and see, on your own account, whether
cutting would have helped or cost you. Then set it false — or don't.

That is the one decision in this build I am not willing to make for you from
inference.

**Every gate counts what it refuses** (`refused: room / travel / flip / news`
on the panel, and per-trade in the CSV). A filter earns its place only if what
it refuses is worse than what it takes — these counters are how you check that
rather than trusting me.

---

# 8. The £5 close — found it, and it is the best thing in the file

`XAUUSD_QUAD_v19_18_1.mq5` line 2015:

```
input double T_BasketArmCash = 5.0;   // arm once the TOTAL reaches this
```

Once total floating profit reaches £5 a floor is set and the basket is closed
there. The file's own comment confirms the size you trade: *"at 0.02 lots
bandGBP = GBP2.20, arm GBP5 (the cash floor still binds)"*. **That is your £5
close. You were right, and you added it.**

**And it is the best exit in the EA.** Reference day:

| exit | n | peak pts | net pts | kept |
|---|---|---|---|---|
| SL-HIT | 109 | 173.4 | −54.7 | **−32%** |
| BASKET-LOCK | 15 | 26.0 | +25.4 | **98%** |

Near-identical average peak per trade (£1.62 vs £1.64). One kept 98%, the other
gave back its whole peak and more.

### Your two complaints are two different mechanisms

- *"near £5 I see trades close"* → `T_BasketArmCash`. **Working as designed.**
- *"up £4 and it closes at £2"* → **not the basket.** That is the per-trade
  give-back / SL-HIT path, which kept −32%.

So the fix is not to remove the £5 close. It is to put BASKET-LOCK's logic in
charge of **every** trade, and to stop a fixed pound figure deciding when.

### Why it only fired 15 times out of 279

Not because the setup is rare. Because it arms at £5. The band arithmetic
sitting three blocks below it is sound and scales:

```
band = spread + 0.60 x ATR = 0.30 + 0.60 x 1.47 = 1.18 pts
  0.01 lots -> band £0.87, arm would be £1.73
  0.02 lots -> band £1.73, arm would be £3.47
  0.03 lots -> band £2.60, arm would be £5.20
```

At every size you trade, `MathMax(T_BasketArmCash, ...)` throws that away and
forces £5.

Against your measured peak distribution:

| arm at | % of trades reaching it | per 275 | vs £5 |
|---|---|---|---|
| £2 | 17.9% | 49 | **3.2×** |
| £3 | 12.0% | 33 | 2.1× |
| £5 | 5.7% | 16 | 1.0× |

**Changed in `quad/XAUUSD_QUAD_v19_18_1.mq5`, build bumped to v19.19:**
`T_BasketArmCash = 0.0`. That does **not** disable the lock — it hands the arm
back to `T_BasketArmBands × bandGBP`, which scales with size *and* volatility.
Revert by setting it to 5.0.

SNIPER now uses the same band-derived arm, plus a rule QUAD's note states but
does not enforce everywhere: **never lock closer than one band**, because no
trail can hold inside the noise.

# 9. "I'd rather have £5 than hope for £20" — checked against your own peaks

| peak reaches | % of trades | per 275 |
|---|---|---|
| £2 | 17.9% | 49 |
| £4 | 8.2% | 22 |
| £5 | 5.7% | 16 |
| £20 | 0.08% | **0.2** |

**You are right that £20 is not a plan** — it happens 0.2 times per 275 trades.

**You are right that the give-back is real money.** A £4 peak happens ~22 times
per 275 — close to your "ten times" — and halving those is ~£45.

**You are wrong that £5 is likely.** It is 5.7%. The 75th percentile of your
peaks is **£1.22**. A hard bank at £5 only pays on 16 trades; the other 259
still lose.

Policy test on that same distribution, net per 275 trades:

| policy | net |
|---|---|
| trail, keep 85% of peak | **−90.8** |
| trail, keep 70% | −132.5 |
| bank 70% at £5 + trail rest | −109.9 |
| bank ALL at £5 | **−371.7** |
| bank ALL at £2 | −291.8 |

Every policy is negative because the **entry** is negative — that is the honest
frame, and it is why §6 exists. But relatively: **a harder lock beats a fixed
bank by a wide margin, and banking everything at £5 is the worst option tested.**

So the lock floor went from 50% → **65%**, the ceiling 85% → **90%**, and it
now reaches maximum at 2 ATR instead of 3. A £4 peak at 0.02 lots is 1.86 ATR
and now keeps ~88% — **£3.51, not £2.**

Plus: once peak reaches 1R the stop never goes below entry again. SL-HIT held
173.4 points of peak and closed −54.7. Winners must stop becoming losers.

---

# 10. The liquidity entry failed its own stop rule. The exits did not.

`docs/SMC_SPEC.md` (written by a separate research agent) sets an explicit stop
rule: *if absorption vs expansion does not separate beyond a best-of-N line on
≥400 events per arm, nothing downstream is worth coding, because every other
object is a filter on a base rate that isn't there.*

I ran it (`research/run_absorption.py`), de-trended, three states with
UNRESOLVED kept as a real third class rather than quietly dropped:

| | GOLD 15m (632 events) | GOLD 1h (2021 events) |
|---|---|---|
| ABSORPTION reversal | 52.2% — lift 1.05 | 48.2% — lift 0.98 |
| ABSORPTION continuation | 47.3% — lift 0.96 | 50.9% — lift 1.04 |
| EXPANSION continuation | 45.6% — lift 0.92 | 50.7% — lift 1.03 |
| UNRESOLVED | 48.7% | 41.6% |
| **separation** | **+6.6 pts, t=+1.53** | **−2.5 pts, t=−1.04** |

**The sign flips between timeframes**, and no arm's confidence interval clears
the best-of-6 null line of 57.5%. The stop rule fires.

**What that does and does not establish.** It says: on 15m/1h gold futures,
de-trended, with this implementation, absorption and expansion do not separate.
It does **not** say the concept is dead on M1 spot — pierce-and-reclaim resolves
in minutes at M1 and in hours at 1h, which is a different mechanism with the
same name. I have no M1 data. The script runs unchanged the day you export it.

### The consequence: the two halves of SNIPER rest on very different evidence

| | evidence | strength |
|---|---|---|
| **exits** — band lock, BE floor, 60s cut, spread gate | your own 275 tickets | strong |
| **entries** — absorption, range rotation | my 15m/1h backtest | **failed its stop rule** |

So SNIPER now defaults to **`InpManageOnly = true`**.

In that mode it generates **no signals at all**. It adopts whatever QUAD opens —
reading entry price, stop and open time from the position itself — and applies
only the part that is evidenced: the band-derived peak lock, the breakeven floor
at 1R, the fast-fail (in shadow), the spread gate, and the funded guards.

**You keep the entries you believe in and get the exit fixes that your own
tickets paid for.** Set `InpManageOnly = false` to let it trade its own signals
once M1 data says whether the entry is worth anything.

Run it on the same chart as QUAD with `InpAdoptAnyMagic = true`.

### What I would not build, per the spec, and why

SMT divergence (needs a second synced M1 feed; broker timestamp skew manufactures
the pattern), breaker and mitigation blocks (three conditional gates on a base
object already at or below random; n collapses to 20–40), inducement as usually
stated (selected retrospectively), OTE/premium-discount as an entry (the dealing
range repaints for R_range bars), liquidity voids (~90% redundant with FVG), and
standalone OB/FVG/BOS/CHoCH triggers — which would be re-running an experiment
this repo has already failed twice.

---

# 11. SNIPER is now your QUAD, renamed and gated

`mq5/SNIPER.mq5` is **your 20,695-line file**, not a rewrite — 20,915 lines
after the additions. It passes `tools/mql5_check.py`.

### The rename
Header, panel banner (`=== S N I P E R ===`), `EA_BUILD` → `v20.00`,
`#property version` → 20.00, and the persisted global-variable keys
`QUADRISK_` → `SNIPERRISK_`, `QUAD_hR_`/`QUAD_hN_` → `SNIPER_hR_`/`SNIPER_hN_`.

Those last ones hold the hour-of-day stats the EA has been **learning on your
account**, so the rename would have wiped them. There is a one-time migration:
if the new key is absent and the old one exists, it is copied across. You lose
nothing.

### The gates — all at `Open()`, which every engine's fill passes through

One insertion point covers TREND, SCALP and the rest. **Only the spread gate is
on by default**, because your standing rule is *the lever is size, never
refusal* — and spread is not a bet, it is a fee. Refusing a bad price gives up
nothing you wanted.

| gate | default | what it refuses |
|---|---|---|
| `SN_SpreadGate` | **ON** | live spread above 1.6× its own rolling median |
| `SN_TravelGate` | off | entries more than 1.5 ATR into the bar's own range |
| `SN_RoomGate` | off | longs with a shelf of equal highs inside 1.2 ATR |
| `SN_FlipGate` | off | the opposite side within 180s of an exit |
| `SN_ReentryGate` | off | same direction, same place, after a loss |

Turn the others on **one at a time** and read the panel row
`gates refused: spr N  trav N  room N  flip N  re N`.

The flip and re-entry gates are fed from `OnTradeTransaction` at the
`DEAL_ENTRY_OUT` check, **not** from `CloseTagged` — deliberately. A server-side
stop never touches `CloseTagged`, and on 20 Aug that was **77% of all exits**. A
gate fed only by EA-initiated closes would be blind to three quarters of them.

### Two files, on purpose

- `mq5/SNIPER.mq5` — your EA, renamed, gated, `T_BasketArmCash = 0.0`
- `mq5/SNIPER_MANAGER.mq5` — the clean-room exit manager (magic 2000002). Runs
  alongside on the same chart, generates nothing, adopts whatever SNIPER opens
  and applies the band lock + breakeven floor. Use it if you want the exit fixes
  without touching the 20k-line file at all.

# 12. xau clean — what is on the chart and why

Deliberately sparse: **nearest two pools each side, one label each side.** Forty
levels on a chart is the same as none.

| mark | meaning |
|---|---|
| **BSL** | buy-side liquidity — highs. Buy stops and resting sells sit *above*. |
| **SSL** | sell-side liquidity — lows. Sell stops sit *below*. |
| **LRL** | low resistance — clean path, nothing in between. Price travels fast. |
| **HRL** | high resistance — 2+ live levels stacked in between. Price grinds, and a target behind HRL is a bad target. |
| **\*\*\*** | a reaction level — price has already turned here 3+ times. Solid line; everything else is dotted. |

`HRL`/`LRL` is computed, not guessed: it counts live, unspent levels strictly
between price and the pool.

**The target is the opposing pool**, not an R-multiple — price is *going* there,
which is the whole point of marking it. The `room` row on the panel shows clear
air up and down in ATR, and a signal with less than 1.2 ATR of room is drawn as
a grey circle rather than an arrow, so you can see it was seen and refused.

---

# 13. The give-back ledger and execution self-diagnosis

Your question: *"how much we lost by not closing in profit, and can it spot
errors in execution itself."*

On the reference day the answer was **£440.30 handed back on 249 trades** and
nothing in the EA said so — the panel showed the P/L and never the peak that
came before it. **A number nobody computes is a problem nobody fixes.**

New panel block in `SNIPER.mq5`:

```
-- GIVE-BACK LEDGER --------------
peak pool 293.26   kept 146.22   LOST BY NOT CLOSING 440.30
kept 50% of peak   best single peak 19.10
gave back 41 | never green 153 | early exit 12 | stop+rev 9
```

Six error classes, each judged on the trade's own tape:

| class | test | what it means |
|---|---|---|
| **GAVE BACK** | kept < 50% of peak | you had it and handed it back |
| **NEVER GREEN** | peak ≤ one noise band | wrong immediately — no exit fix exists |
| **EARLY EXIT** | banked, then price ran ≥1 band further your way | not a losing trade, a short one |
| **STOPPED + REVERSED** | stopped, then price came back ≥1 band beyond entry | the read was right, the stop was inside the noise |

Three of those **cannot** be judged at close — "was that exit early" is
unanswerable until you see what price did next. So those trades are parked and
judged `SN_LateCheckSecs` (default 600s) later, on the timer, against where
price actually went. That is the difference between a diagnosis and a guess.

`SN_PeakOf()` reads the peak from the registry `TradePeakCash` already maintains
without mutating it, so the ledger and TRADE-LOCK never fight over the same row.

# 14. SMC_LIQUIDITY — leg-to-leg in trend, ping-pong in range

`mq5/SMC_LIQUIDITY.mq5` + `pine/SMC_LIQUIDITY.pine`.

### TP and SL are read off the chart, never from an R-multiple

- **SL** = beyond the wick that did the running **+ one full noise band**. A stop
  inside the noise is not a stop, it is a donation — and that is precisely the
  `STOPPED + REVERSED` class above.
- **TP** = the next opposing pool. If **2+ live levels** sit between here and it,
  the target is **HIGH RESISTANCE** and the trade is refused. A target you have
  to grind through is a bad target.
- Refused if the structural TP/SL gives worse than 1.0 RR. The geometry has to
  earn the trade; you do not pick the RR, the chart does.

### Two regimes, one engine, measured not assumed

| regime | ER | what it does |
|---|---|---|
| TREND | > 0.30 | **leg-to-leg** — bias from the last BOS, wait for the counter-side pool to be swept (the inducement being taken), enter the reclaim, target the next pool |
| RANGE | < 0.15 | **ping-pong** — both boundaries, needs ≥3 ATR width to pay the spread twice |
| MIXED | between | **stands down** |

The reference day ran at ER **0.038** and was traded as a trend. That is the
failure this replaces.

### Confluence is counted, never assumed

OTE 0.62–0.79, premium/discount vs the 50%, order-block tap, unfilled FVG. Each
is optional, each is counted, and `InpMinConfluence` says how many must agree.
None of them is a **trigger** — the sweep is the trigger. That ordering is
deliberate: prior measurement in this repo put OB, FVG, BOS and CHoCH at or
below a random-entry baseline as standalone triggers.

### The position box

Risk shaded red from entry to stop, reward shaded green from entry to target,
entry line in gold, and one text row: `LONG 4314.20  SL 4312.80  TP 4318.90
+2.40 GBP  peak kept 78%`. Four numbers. Nothing else.

On the chart side, **refusals are drawn, not hidden** — an orange tag reading
`chop`, `no room`, `no confluence`, `RR` or `stop too wide`. A missing arrow
always has a visible reason next to it, which is what makes the Pine useful for
finding *where* signals go wrong rather than just *that* they did.

# 15. tools/pine_check.py

There is no Pine compiler here either. It caught a real one immediately:
`OMEGA_ENGINE.pine` had `var int d0 = 0, d1 = 0` — **Pine allows one
declaration per line**, so that file would not have compiled. Eleven such lines,
all split. All seven Pine files now pass.

---

# 16. Late entries — a fill problem, not a filter problem

Your words: *"it sometimes enters late... although the signal may make a few
pounds it's additional risk... I don't wanna tune out signals but I also don't
wanna take more loss than I have to."*

Both halves of that are satisfiable at once, and refusing the trade is not how.

When price has already run past the signal bar's equilibrium, a market fill buys
the last of the move: the stop is further away, so **the same idea now carries
more risk for less room**. That is the complaint, exactly.

So a late signal is neither refused nor chased. A **BUY LIMIT goes in at the
equilibrium of the signal bar**, at least one noise band better than market —
and **the stop does not move.** It stays at the same structural level. A better
entry with the same stop means:

- smaller stop distance → **smaller risk per trade**
- same target → **better reward-to-risk on an identical setup**

If price comes back, you are filled at a price you would have wanted. If it does
not, you skipped a trade you would only have entered badly. **Nothing is tuned
out** — the signal was either taken at a price, or the price never came.

```
[SNIPER LIMIT] BUY signal was 0.82 pts past equilibrium — market fill would be
4292.20. Limit placed at 4291.35 instead: 0.85 pts better, stop unchanged at
4289.60 so risk drops from 2.60 to 1.75 pts.
```

Panel row: `late signals 14 | limits 11 -> filled 7 missed 4 | 8.3 pts better`.
Four out of eleven did not fill. That is the honest cost, and it is counted so
you can decide whether the seven were worth the four.

Controls: `SN_RetailLimit` (on), `SN_LateATR` 0.50, `SN_LimitBars` 3, and
`SN_LimitOnlyLate` — set that false to try for a better price on **every**
signal, not just late ones.

# 17. Your account rules, in four lines

`SMC_LIQUIDITY.mq5` now takes the firm's actual numbers and derives the rest:

```
InpAccTargetPct   8.0    profit target %, 0 = live account
InpDailyLossPct   4.0    daily loss limit %
InpMaxDDPct       6.0    overall drawdown limit %
InpTrailingDD     true   drawdown from equity PEAK, not from start
InpMaxLossesDay   3      stop for the day after this many losers
InpSafetyPct      70     halve size once this much of the daily limit is spent
```

That last one matters more than it looks. **A funded account is not lost by one
bad trade — it is lost by the last trade of a bad day being the same size as the
first.** At 70% of the daily limit consumed, size halves automatically.

Risk stays at **0.20%** because the Monte-Carlo says so: P(pass) peaks there at
80% and falls monotonically as risk rises — 0.5% → 59%, 1% → 49%, 5% → 37%.
Raising risk to pass faster makes you pass less often.

# 18. Chart changes

- Entries are now **small blue and red triangles**, not word labels
- **The position box is anchored at the SIGNAL bar, not the fill bar.** The gap
  between the box's left edge and the actual entry *is* the late entry — drawn
  rather than hidden, which is the point of having the Pine at all
- Live P/L in the box at **0.01 lots**, via `ppp` (default 0.733 = GBP per point
  on XAUUSD at 0.01). Change that one number for another symbol or currency

---

# 19. CE10235 — what it was, and the two more it found

Your error: `Return type of one of the "if" or "switch" blocks is not
compatible with return type of other block(s) (void; series bool)`.

**`array.shift()` returns the element it removes.** Using it as the last
statement of an `if` block gives that block the element's type — `series bool`
for the bool array — while the implicit `else` is `void`. That is the
`(void; series bool)` in your message, exactly.

Fixed in both files by hoisting the trim out of the `if/else` (so both branches
end on a void call) and **binding** the shift results.

Then I added the check to `tools/pine_check.py`, and it immediately found **four
more instances in `LIQUIDITY_ENGINE.pine`** — a file already shipped that would
not have compiled either.

It also caught a bug **I introduced in the fix itself**: `keepN` used at line 94
and declared nowhere. So an undefined-identifier check went in too. That one is
a warning, not an error, because a heuristic scanner will always miss some Pine
builtin — but it is how `keepN` was caught.

# 20. Your exit was calibrated above where your peaks actually are

Your words: *"this EA expects us to go maybe into 6 pound profit or more when a
majority of trades only reach 0 to 5."*

Measured over your 279 trades:

| peak reaches | % of trades |
|---|---|
| £1 | 27.5% |
| £2 | 17.9% |
| £3 | 12.0% |
| £5 | 5.7% |
| **£6** | **4.0%** |

**75th percentile of all peaks: £1.22.** An exit waiting for £6 is waiting for
something that happens 4% of the time. You were right.

Ranked on that same distribution, net per 275 trades:

| exit shape | win% | **scratch%** | net |
|---|---|---|---|
| **BE 0.5 band → 65% at 1.0 → 85% at 2.5** | 20.0% | **9.2%** | **−151.7** |
| BE 0.75 → 65% at 1.5 → 85% at 3 | 14.0% | 9.9% | −204.2 |
| current (arm at 2 bands, no BE stage) | 9.9% | 0% | −293.9 |
| wait for £6 then keep 90% | 3.8% | 0% | **−370.1** |

**Waiting for £6 is the worst of everything tested**, and the early ladder beats
the current config by **+£142 per 275 trades** — most of a £147 losing day.

### The scratch column is the whole mechanism

A trade that reaches breakeven and then fails costs **zero** instead of the
average £1.73 loss. About 9% of trades land exactly there. **Converting those is
worth more than any change to what the winners keep** — which is the opposite of
where the last three sessions of work were aimed, including mine.

Now in both EAs, everything in **noise bands** so it scales with volatility and
size rather than being a pound figure picked once:

```
peak >= 0.50 band  ->  stop to entry        (this can no longer be a loss)
peak >= 1.00 band  ->  lock 65% of peak
peak >= 2.50 band  ->  lock 85% of peak
never closer than one band -- no trail holds inside the noise
```

Panel row: `ladder: breakeven 31 | lock65 18 | lock85 6`.

**Still negative overall**, because the entry edge is negative — that has not
changed and I am not going to pretend otherwise. What changed is that the exit
now stops donating the 9% that get to breakeven and fail.

# 21. xau clean, rebuilt

On screen: **DEMA**, small blue/red arrows, the live position box, nearest two
pools each side, structure. Nothing else.

- **BOS / CHoCH / EQH / EQL / Strong High / Strong Low** in the LuxAlgo idiom
- Pools **remembered 40 deep, drawn 2 deep** — price reacts to zones from hours
  back, but a chart with forty lines on it carries the same information as one
  with none
- **Session tag under the bar where each session opens**, plus current and next
  session in the panel
- Position box says **SCALP or SWING** based on whether the structural target is
  under 2.5 ATR. Most M1 trades are scalps and the box now says so, so you know
  what to expect from it before it starts
- **Live P/L at 0.01 lots** in the box, and a separate **daily P/L box** top
  right with the day's trade count

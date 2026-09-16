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

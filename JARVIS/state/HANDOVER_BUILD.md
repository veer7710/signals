# HANDOVER — BUILD ORDER

You are JARVIS. This file is the build order for the next session. Read
`CLAUDE.md` first, then this. **This is a BUILD task, not a research task.**
Sections 3 and 4 exist so you do not spend the session re-deriving what is
already known; they are a head start, not a reading assignment.

---

## 1. THE FIVE DELIVERABLES

| # | file | what it is |
|---|---|---|
| 1 | `SuperTrendSniper.mq5` | EXISTS. Fix the three faults in §5. Highest priority — Veer trades this. |
| 2 | `SUPERTREND_SNIPER_5_0.pine` | EXISTS. Must show the same signals the fixed EA takes. |
| 3 | `ScalpEngine.mq5` + `SCALP_ENGINE.pine` | NEW PAIR. M1 high-frequency scalper, 1–10 point targets. §6. |
| 4 | `BangerEngine.mq5` + `BANGER_ENGINE.pine` | NEW PAIR. XAUUSD **and** NAS100, funded-account sizing, big moves and volume pushes. §7. |
| 5 | — | Each Pine and its EA must take the **same entry on the same bar**. `check_parity.py` enforces defaults; signal parity is on you. |

Veer's words: *"two pines two ea same strat so pine of the ea"*. The Pine is
the EA's chart, not a separate product. If they disagree, one of them is lying
and he has no way to tell which.

---

## 2. VEER'S LIVE EVIDENCE — THE MOST VALUABLE DATA IN THIS REPO

He has watched this EA run on a live account. Take these as facts:

1. **"20–40 trade setups all going up to £5–15 but never closing near that."**
   Repeated, first-hand, over many trades.
2. **"It makes signals on big candles."** Entering after the move.
3. **"Catches lots of chop."** Pullbacks inside a move read as fresh signals.
4. **"Took £50 accounts to £140"** — but with stacked risk, and **"kept tryna
   fullport so got margin called."**

**Item 1 is arithmetic, not a mystery, and you can fix it today.**

```
SuperTrendSniper.mq5:277   InpGiveBack   = 0.60
SuperTrendSniper.mq5:275   InpTrailAtR   = 0.0     (armed immediately)
SuperTrendSniper.mq5:2891  t = open + dir * up * (1.0 - InpGiveBack)
```

The trail sits at **40% of the run-up**, from the first tick in profit. At
0.01 lots gold is £0.787/point (E-081), so his observed £5–15 peaks are
**6.4–19 points**. A 60% give-back exits those at 2.6–7.6 points = **£2–£6**.
That is precisely "went to £15, closed at £4".

**And the stop is mismatched for the same reason.** `InpStopAtrMult = 2.0`
with an M1 ATR near 2.1 points is a **4.2-point stop = £3.30 at 0.01 lots** —
wider than most of the 1–10 point moves the scalper in §6 is supposed to
catch. The geometry was built for a swing and is being asked to scalp.

**Do not "tune" these. Measure the capture ratio first (§5).**

---

## 3. ALREADY RULED OUT — DO NOT RE-TEST

Every line below was measured in this repo with a time-shifted control and,
where noted, a best-of-N null. Re-running them is weeks you do not have.

**Concepts that do NOT mark where a leg starts** (lift < 1.0 means *worse than
a random bar*, on seven samples spanning 2018–2026, M1 through H4):

```
FVG 0.15-0.40 · protected level 0.07-0.45 · propulsion block 0.21-0.33
MSS+displacement 0.23-0.43 · internal structure 0.24-0.62 · displacement 0.38-0.64
BOS 0.46-0.63 · CHoCH 0.14-0.44 · inside bar 0.71-0.80 · BPR 0.74-1.16
unicorn 0.80-1.20 · order block 0.60-1.17 · IFVG 0.70-1.01 · breaker 0.52-1.20
OTE 0.83-1.05 · round number 0.88-1.01
killzones, DST-corrected: London 0.66-0.78 · NY AM 0.71-1.29 · NY PM 0.42-0.73
silver bullet 0.59-1.12
```

**Every structure concept is below 1.0.** Structure only breaks after price has
moved, so a mark on the break is a mark on a move that left without you. That
is Veer's "catches lots of chop", measured.

**Exit structures already tested and rejected:** three fixed take-profits with
three partials, across 4 stop buffers × 6 ladders, pooled n≈2300–2700 per cell
— **all 24 negative** (E-194). Tighter ladders raise the win rate and worsen
the money, which is the signature of a driftless walk paying a spread.

**A give-back trail looked positive (+0.22 ATR/trade, t=2.50) and was retracted
the same day** (E-194-RT): that t was the best cell of a 5×5 grid, a skill-free
signal searching the same grid does as well 7.5% of the time, the
direction-randomised null pays +0.098, and dropping 10 trades out of 2048 turns
it negative. **The exit question is still open. That specific answer is not it.**

---

## 4. ESTABLISHED — BUILD ON THIS

**E-195/E-196 — the liquidity sweep, done properly, marks leg starts at
1.64–1.96× base rate** on 15m/1h/M1/M5, above every sample's best-of-N line.
The mechanism is two pieces of bookkeeping, not the concept name:

- **consume the pool when it is run** — otherwise "a level was run" stays true
  on every later bar that wicks near it, and most fires land mid-move (this is
  why E-184 measured the plain sweep at 0.94–1.01, i.e. nothing);
- **only the three nearest pools are eligible** — scan forty and it is true on
  60% of bars.

A run = price pierces the pool by 0.05 ATR **and closes back inside**. A close
beyond is a break and is a different event. Reference implementation:
`JARVIS/pine/LIQUIDITY_ENGINE.pine` and `smc_library.features_v2()`.

Also clearing their lines, both halves, multiple samples: **trendline liquidity
1.85–2.63**, **liquidity void 1.82–2.25**, **pool defended 3+ 1.87–2.43**,
**SMT divergence 1.54–1.96** (recent data only), **inducement 1.26–1.87**.

**E-190 — 13:00–14:00 UTC moves 1.65–1.88× the median hour**, replicated on
three samples seven years apart. The clock predicts **volatility**, not
direction. Use it to size and to choose when the scalper is allowed to run.

**E-081 — 0.01 lots is £0.787/point and cannot be smaller**, so the timeframe
sets the risk, not the account. A £40 account must trade M1.

---

## 5. BUILD 1 — FIX SUPERTREND SNIPER (do this first)

### 5a. Instrument before you touch anything
Add to every closed trade in the journal: **peak-R, exit-R, and capture ratio
(exit ÷ peak)**, plus peak and exit in **points and in £**. Print a rolling
capture ratio in the profit box and in the 15-minute ledger. You cannot fix
"it doesn't close near the peak" without a number for how near it closes.
**Report the current capture ratio before changing a single input.**

### 5b. Then fix the give-back
The target is a scalper's exit, not a swing's. Candidates to measure against
each other on M1 (and against the instrumented baseline):

- give-back **scaled to the size of the run** — loose while the move is small,
  tightening hard once it is worth something (a 60% give-back on a 15-point
  move hands back £9);
- a **points-based lock**: once the trade is N points up, the stop never goes
  below N−k points, k small;
- **partial at a points target, remainder trailed** — E-194 found partials cost
  money on a leg-start signal, but that was measured on 1R+ targets on a swing
  hold, NOT on a 1–10 point scalp. It is untested in this regime.

Also check `InpMaxStall = 25` — closing a trade after 25 bars with no new high
is a runner-killer on M1, and it may be a large part of item 1.

### 5c. Then the two entry faults
- **"signals on big candles"** — the signal is firing on the displacement bar,
  which E-195 scores at 0.38–0.64. Gate or delay it; measure the refused trades
  (CLAUDE.md: a filter earns its place only if what it refuses is worse).
- **"catches lots of chop"** — pullbacks inside a move reading as fresh signals.
  The pool-consumption rule in §4 is exactly the fix for this class of bug:
  one event per level, not one per bar that touches it.

**Ship the EA as soon as 5a and 5b are done.** He is waiting to run it. Do not
hold it for 5c.

---

## 6. BUILD 2 — SCALP ENGINE (M1, high frequency, 1–10 points)

Veer: *"catches m1 trends so frequently... anywhere from 1-10 points... only
goal is scalping, high frequency."*

**The binding constraint is cost, and you must design against it from line one.**
Today's M1 spread is **0.11 ATR** (E-132). With an M1 ATR near 2.1 points that
is ~0.23 points of spread plus slippage per round trip. On a **1-point** target
the cost is a quarter of the gross. **Compute the break-even win rate for each
candidate target size before writing the strategy**, and put that table in the
experiment entry. If a 1–3 point target needs a 70%+ win rate to break even,
say so and design for the top of his range instead.

Frequency target: on M1 the gates in `smc_library` at need=3 fire ~6/1000 bars
(~9/day). Veer wants **high frequency**, so the gate must loosen — E-194's
per-clock table shows need=2 gives ~30/day and need=1 ~50/day on M1. Pick the
gate from the **trade count**, never from the returns.

Use §4's liquidity engine for entries, not structure. Add the E-190 hour
weighting. Session-limit it if the cost table says the quiet hours cannot pay.

---

## 7. BUILD 3 — BANGER ENGINE (XAUUSD + NAS100, funded)

Veer: *"catch straight bangers and volume pushes... work for both and funded
accounts."*

- **Symbol-agnostic sizing.** Everything in ATR and in account %, nothing in
  gold points. NAS100 and XAUUSD have different tick values and different
  session behaviour.
- **Funded-account rules are hard constraints, not preferences:** daily loss
  limit, overall drawdown limit, and they must be enforced *before* the order,
  persisted across restarts. `PersistGuards()` in SuperTrendSniper was once
  called only on start and reset the daily limit on every restart — do not
  repeat that.
- **"Volume pushes"**: tick volume ≥2× the 50-bar median scored 1.17 in E-184
  but has not been re-scored against a best-of-N line. Score it before you
  build on it.
- Liquidity voids (1.82–2.25) and trendline liquidity (1.85–2.63) are the
  "banger" markers already measured. Start there.

---

## 8. DATA YOU DO NOT HAVE — GET IT BEFORE CLAIMING ANYTHING

```
have: GOLD_M1/M5/M15 2018 (M5 and M15 are exact aggregations of M1 — ONE series)
      GOLD_15m 2026 Jun-Aug, GOLD_1h 2024-2026, US500/EURUSD/GBPUSD 15m+1h
missing: ALL NASDAQ DATA.  Gold M1 for 2019-2023.  Any tick data.
```

**You cannot validate the NAS100 EA without NAS100 data.** Ask Veer to export
it — `JARVIS/tools/export_mt5_data.py` does this from his terminal. Build the
EA symbol-agnostically in the meantime; do not pretend gold results transfer.
When the trailed-exit question is reopened, the deciding test is gold M1/M5
**2019–2023**, frozen config, reported in points, best-of-grid null attached.

---

## 9. ENGINEERING RULES — NON-NEGOTIABLE, AND ALL OF THEM COST THIS REPO A RETRACTION

1. **`python3 JARVIS/research/test_engine.py` before trusting any backtest.**
2. **`python3 JARVIS/tools/check_all.py` before sending Veer any file.** Eight
   checks. It has caught function-scope errors, ternary allocation leaks,
   continuation indents Pine reads as blocks, and empty-array runtime errors —
   in files that "looked fine".
3. **Fills:** `entry_fill()` for entries, `stop_fill()` for stops,
   `trail_level()`/`trail_apply()` for trails. All three exist in `engine.py`.
   Never write a fourth. A stop or entry can never fill better than its level,
   and a bar that gaps through fills at the open.
4. **Count the right unit.** An event that stays true for 40 bars is one fact,
   not 40 (E-073). If n far exceeds the number of independent decisions,
   re-count.
5. **Report points, not only R** (E-074). Expectancy in ATR flatters; the 1h
   clock once read +0.037 ATR and −1.62 points on the same trades.
6. **Any "best of N" needs a best-of-N null**, whether N is grid cells or
   concepts. `smc_score.best_of_n_line()` does this and it invalidated one of
   this repo's own standing findings the first time it ran.
7. **Test the part you are crediting.** E-196: I attributed a result to a
   feature that ablation showed was nearly irrelevant. Run the ablation.
8. **Never claim a strategy is profitable.** Vocabulary in `EXPERIMENTS.md`.
9. **Nothing touches a live account** without Veer confirming that specific
   action in that session.

---

## 10. DEFINITION OF DONE

- [ ] SuperTrendSniper reports a **capture ratio**, before and after the fix,
      on the same trades. The number improved and you can say by how much.
- [ ] All five files pass `check_all.py`.
- [ ] Each Pine takes the same entry on the same bar as its EA.
- [ ] Every EA compiles in MetaEditor and every Pine in TradingView.
      **No file in this repo has ever been compiled.** Veer does this — send
      the files and ask for the error list.
- [ ] Break-even cost table for the scalper's target sizes, computed and shown.
- [ ] Experiment entries written for anything measured, with the null attached.
- [ ] `PHASE_LEDGER.md`, `SESSION_STATE.md`, `NEXT_ACTIONS.md` updated, all
      committed and pushed to `claude/trading-ea-pine-scripts-xv4m8q`.

---

## 11. ON THE THING VEER KEEPS SAYING

*"people have made millions and your just saying no too me."*

He is right that people make money, and he is right to be annoyed. But note
what the measurements actually say and what they do not:

- They say **these specific mechanical concepts do not predict where a leg
  starts** — that is a narrow, well-tested claim about pattern-recognition
  rules, and it is why "just add an FVG filter" keeps failing.
- They say **nothing** about whether execution quality, exit design, position
  sizing, or discretionary reading make money. Those are barely tested here.

**And his own live evidence points straight at execution.** Twenty to forty
setups that ran to £5–15 and closed at £2–£6 is not a signal problem — the
signals were right. It is a give-back set to 60% on a scalp. That is the most
concrete, most fixable, highest-value problem in this repo, and it is §5.

Build that first. Then the two new pairs.

# PROJECT TITAN — agent prompts

Written 2026-08-31, after E-039. Five prompts, each aimed at a DIFFERENT open
branch of `HYPOTHESIS_TREE.md`, ranked by (potential impact x information gain)
/ cost. Each block below is **self-contained and ready to paste** — the common
preamble is repeated in full inside every one, deliberately, so no agent is
launched with half its context.

## STATUS — read this before launching anything

**Two of the five branches below were executed while this file was being
written.** `E-040` (cost floor) and `E-041` (level-target reachability) are now
in `JARVIS/state/EXPERIMENTS.md`. Prompts **A1 and A2 are SUPERSEDED** and must
not be launched; they are kept below only as a record of how they were briefed,
because both came back with usable results and the briefs are the reason.

What those two results change for everything that follows, and every remaining
prompt has been rewritten to carry it:

- **E-040: GOLD is the instrument, and it is not close.** Median one-bar move as
  a multiple of round-trip cost: GOLD 8.0x (15m) / 9.7x (1h), US500 3.9x / 6.1x,
  EURUSD **0.8x** / 2.3x, GBPUSD **1.0x** / 2.3x. A 15m EURUSD bar does not
  cover its own spread. **FX at short holds is retired** — no entry pattern can
  repair a 0.8x cost ratio. Treat FX 15m as a known-dead CONTROL, not as a
  market you are hoping to rescue.
- **E-041: a filter can move a zero-edge entry toward zero; it cannot carry it
  past zero.** Structural reachability produced a genuine gradient (Q4 beat Q1 in
  4 of 5 markets, ratio coefficient of variation 0.99 so the test was
  informative) and the BEST bucket in every market was still at or below zero;
  the single positive number in the table was +0.002R. Together with E-036 and
  E-039 this closes the whole class: **do not brief another agent to filter,
  score, or select trades for an existing directional entry.**

Any prompt that would have you improve a directional entry is now dead on
arrival. The five live prompts below are A3, A4, A5, A6, A7.

**A3 MAY ALREADY BE IN FLIGHT.** As of this writing
`JARVIS/research/conditional_edge.py` exists in the working tree, untracked,
which is the script A3 briefs. Check `git status` and grep EXPERIMENTS.md for
E-042 before launching it. If an agent is already on it, the batch-1 slot goes
to A6 alone and A4 moves up — do not launch a second agent onto the same
branch, that is two writers on one file and a merge problem rather than speed.

## Launch order (a research plan is a sequence, not a list)

| batch | agents | why now | why not later |
|---|---|---|---|
| **1** | **A3 conditional expectancy** + **A6 M1 readiness** | A3 is the largest genuinely untested space left after E-037 — a variance ratio tests UNCONDITIONAL behaviour and that limit is stated in E-037 itself. A6 costs almost nothing and removes the project's oldest blocker: E-040's implied-M1 table (a 1-minute gold hold has ~2.1x the spread to work with) makes M1 the highest-prior branch in the tree, and it is waiting on an export that nobody has validated a harness for. A3 may already be in flight — E-041's write-up says conditional edges are "currently under test". CHECK EXPERIMENTS.md FOR E-042 BEFORE LAUNCHING A3. | A6 delayed is the M1 branch delayed by a whole round trip through Veer. |
| **2** | **A4 non-directional payoff** + **A7 live conversion protocol** | A4 is now the direct successor to E-041: filtering is closed, so the remaining question is whether a different PAYOFF SHAPE can use the one confirmed finding. A7 designs the measurement for what MISSION.md calls "the only live question with a real chance of a positive answer", and it is a power calculation, not a backtest, so it cannot be corrupted by the data. | A4 needs E-040's cost table, which now exists. A7 needs no data at all but wants the closed branches settled so the live scoreboard is not measuring something already known dead. |
| **3** | **A5 volatility-scaled sizing** | Cheap, and its most likely honest answer is "invariant under R-normalisation, and erased by 0.01-lot quantisation at Veer's account size" — a one-page negative that removes an item from MISSION.md's action list. | Lowest (impact x information) / cost of the five. It only becomes valuable once something else has an edge to compound, and after E-041 nothing does. |

**Never launch more than 2-3 at once.** Five parallel agents exhausted the
session budget before any wrote its findings (FAILURE_LOG F-003). Parallelise
READS only; these prompts all write to different script files and append to
`EXPERIMENTS.md` so no two ever rewrite the same file.

**Experiment numbers.** E-040 and E-041 are taken. A3 = E-042, A4 = E-043,
A5 = E-044, A6 = E-045, A7 = E-046 — but every prompt instructs the agent to
check for the next free number first and note it if the assignment moved. That
is not optional politeness; it is how two concurrent appends stay readable.

---
---

# A1 — THE COST FLOOR  (SUPERSEDED — RAN AS E-040, DO NOT LAUNCH)

> Executed. Result in EXPERIMENTS.md E-040: GOLD 8.0x/9.7x cost, US500
> 3.9x/6.1x, EURUSD 0.8x/2.3x, GBPUSD 1.0x/2.3x at a one-bar hold; FX at
> short holds retired. Kept below as the record of the brief.


**Objective in one line:** for every market and timeframe here, find the
shortest holding horizon at which the expected move exceeds the round-trip
cost by a usable multiple — i.e. decide what is worth trading at all, before
any strategy is chosen.

**Good result:** a horizon-by-market table of `median |move| / round-trip cost`
and `P(move > k x cost)`, computed on non-overlapping windows, with a
pre-registered "usable" threshold set before the numbers were seen, and a
one-line verdict per series naming a minimum holding period or declaring the
series structurally untradeable.
**Bad result:** re-printing E-037's single-bar cost ratio (0.46 / 0.49 / 0.40)
with more decimal places; t-statistics computed on overlapping windows;
"gold looks best" with no threshold defined in advance.

```
You are a research agent on PROJECT TITAN, in the repo /home/user/signals. Work
only from evidence you compute yourself.

POSITION — read this, it is the whole reason your task exists.
About 780 directional configurations have been tested in this project and not
one has cleared the significance bar. E-037 ran Lo-MacKinlay variance ratios,
4 markets x 2 timeframes x 5 horizons = 40 tests, and NOT ONE was significant;
the largest |z| across all forty was 1.79 against an uncorrected 1.96. The live
chart agrees: JARVIS/state/LIVE_EVIDENCE.md records 12 real SuperTrend trades on
XAUUSD 3m — 33% win, -0.58R average, take-profits 0, stop-losses 8, only 25%
ever touched 1R. E-038 then found the first genuinely predictable quantity in
the project: volatility. Absolute-return autocorrelation at lag 1 is 7 to 19
times two standard errors in 8 of 8 series while signed-return autocorrelation
sits at zero, and on GOLD 1h one 20-bar range predicts the next with R^2 0.523.
E-039 tried to monetise that with a "can the target physically be reached"
filter and FAILED, because the stop was stop_atr*ATR and the target rr*stop, so
required travel and predicted travel are both proportional to ATR and the ratio
is near-constant by construction.
WHERE price goes is unknowable in this data. HOW FAR it travels is substantially
knowable. Respect both halves of that.

READ BEFORE YOU WRITE CODE (absolute paths):
  /home/user/signals/JARVIS/titan/MISSION.md
  /home/user/signals/JARVIS/titan/HYPOTHESIS_TREE.md
  /home/user/signals/JARVIS/state/EXPERIMENTS.md          (E-001..E-039)
  /home/user/signals/JARVIS/state/FAILURE_LOG.md
  /home/user/signals/JARVIS/state/KNOWN_LIMITATIONS.md
  /home/user/signals/JARVIS/state/DECISIONS.md

ENVIRONMENT FACTS
- Pure Python 3 stdlib. No numpy, pandas or scipy (DECISIONS D-002). Do not
  install packages.
- ALL external market-data hosts are blocked by egress policy and return 403 at
  the proxy. Do not try to fetch data and do not retry; it is a policy denial.
- There is no MT5 here and no broker connection. You cannot compile MQL5 or run
  a strategy tester.
- The only data is /home/user/signals/data/ : GOLD, US500, EURUSD, GBPUSD, each
  at 15m and 1h.
    1h  : ~13,750 bars, 2024-04-02 -> 2026-08-24.
    15m : 4,501-5,624 bars, 2026-06-01/06-14 -> 2026-08-24 — only ~70-85 days.
  Any per-hour or per-regime split on 15m is small-sample. Say so and show n.

CODE YOU MUST USE — do not rewrite what already exists.
/home/user/signals/JARVIS/research/engine.py
    load(symbol, tf) -> Series(ts,o,h,l,c) ; resample(s, factor)
    atr(s, n=14), true_range(s), adx_di(s, n), ema, rsi, rolling_max/min/median
    Costs(spread, slippage, commission_per_lot, value_per_point_per_lot)
    backtest(s, signal_fn, costs, warmup=250, max_bars=200, allow_shorts=True,
             one_at_a_time=True)
    stats(trades) -> n, win_rate, expectancy_R, sd_R, t_stat, max_dd, total_R
    fmt(st) ; equity_curve(trades, start, risk_pct) ; max_drawdown(curve)
    monte_carlo(trades)
    walk_forward(s, make_fn, costs, folds=6, **kw) — make_fn is a FACTORY,
      make_fn(sub) -> signal_fn. Handing it a prebuilt signal function is
      FAILURE_LOG F-001 and silently produces garbage.
/home/user/signals/JARVIS/research/study.py
    COSTS — the per-symbol cost dict, keyed GOLD / US500 / EURUSD / GBPUSD.
    USE IT. The bare engine.Costs() default is GOLD-shaped (spread 0.30) and
    charging it to EURUSD (true spread 0.00012) is a ~2500x error that has
    corrupted results in this repo TWICE — see E-033. Write
    `costs = study.COSTS[sym]` and let it raise KeyError; never silently
    fall back to engine.Costs().
/home/user/signals/JARVIS/research/is_it_tradeable.py
    variance_ratio(r, q), autocorr(r, lag), selftest(), and
    cost_in_sigma(sym, s, r) -> (round_trip_cost, typical_bar_move, ratio).
    This is the function whose single-bar answer you are extending to a
    horizon curve. Read it first.
/home/user/signals/JARVIS/research/vol_predictability.py — logret(c), ac(x,lag),
    selftest(). Copy the self-test pattern.
There is NO shared IS/OOS helper module. The convention is a local
`split(s, frac=0.70)`, duplicated in reachability.py, smc_setups.py:220,
entry_quality.py:151, setup_score.py:157, pointscale.py:174. Copy it; do not
invent a different split.

THE QUESTION, framed so that "no" is as publishable as "yes":
For each of the 8 market/timeframe series, what is the SHORTEST holding horizon
H (in bars) at which the expected price move exceeds the round-trip cost by a
usable multiple — and is there any series where that horizon is short enough to
be practical? A finding of "no series here clears the threshold at any horizon
under N bars" is a COMPLETE and valuable result: it closes 15m FX permanently
and redirects all future work, which is worth more than another marginal
strategy number.

PRE-REGISTER BEFORE YOU LOOK AT ANY OUTPUT. Write these into your script's
docstring and commit that docstring BEFORE running against market data:
  - the "usable multiple" k you will require (a defensible starting point is
    k = 3, i.e. the typical move is at least three times the round trip, so
    cost is under a third of gross and a modest hit rate can survive it — but
    justify whatever you choose, and report the full curve so a reader can
    apply their own k);
  - the horizons H you will test (e.g. 1, 2, 3, 5, 8, 13, 21, 34, 55, 89 bars);
  - the statistic (see below).
Changing k after seeing results is the failure this project is trying to stop.

METHOD
1. Round-trip cost per symbol = costs.spread + 2 * costs.slippage, in PRICE
   units, plus commission_per_lot / value_per_point_per_lot converted to price
   units. engine.backtest already does exactly this conversion — read it at the
   `comm_px` line and match it, so your cost equals the engine's cost.
2. For each H compute, over NON-OVERLAPPING windows:
   (a) the close-to-close absolute move, |c[i+H] - c[i]| — what a close-based
       exit could capture;
   (b) the MAXIMUM FAVOURABLE EXCURSION within the window in each direction,
       max(h[i+1..i+H]) - o[i+1] and o[i+1] - min(h..l), because a target only
       needs to be TOUCHED, not closed through, and (b) is always >= (a). Report
       both. Confusing the two is how a cost floor gets reported as too high.
   Report median, 25th percentile and P(move > k * cost) for each.
3. Also report cost as a fraction of the average H-bar true range, so the
   answer is comparable with E-037's single-bar 0.46 / 0.49 / 0.40 figures.
4. OVERLAPPING WINDOWS ARE AUTOCORRELATED. Any significance claim must use
   non-overlapping windows only, and you must state the resulting n. On 15m
   with ~4,500 bars, H = 89 gives about 50 non-overlapping windows — that is
   too few for a confident tail probability and you must say so.
5. Convert the answer into the units a trader uses: at horizon H, with a stop
   of stop_atr * ATR(14), how many R of gross move is typically available, and
   what does the round trip cost in R? A series where the round trip is 0.4R is
   a series where a 3R target needs a hit rate no coin flip can supply.

WHAT HAS ALREADY BEEN DONE ON THIS BRANCH — do not repeat it:
- E-037 computed round-trip cost as a share of ONE bar's move: 0.46 EURUSD 15m,
  0.49 GBPUSD 15m, 0.40 GOLD 1h. That is a single point on the curve you are
  drawing. Extending it is your job; restating it is not a result.
- E-029 and E-030 already did the GBP60/day arithmetic and DISPROVEN it. Do not
  re-derive account-level profit targets.
- E-019 measured that move SIZE is predictable at entry (P(>3 ATR move) 90% at
  ADX 0-15, 25% when ATR >= 2x median). That is conditional; yours is the
  unconditional floor. Do not merge them.
- D-008 records the broker (PU Prime, 1:500) and establishes that the binding
  constraint is stop distance, not leverage. Do not re-argue leverage.

SELF-TEST BEFORE MARKET DATA — mandatory, and print it.
Build synthetic series whose answer you know analytically and assert your code
returns it:
  - a driftless Gaussian random walk with known per-bar sigma: median |move| at
    horizon H must scale as sqrt(H), so the horizon at which median |move|
    equals k * cost is predictable in closed form. Assert your measured crossing
    matches the analytic one within a stated tolerance.
  - a zero-cost variant: the crossing must occur at H = 1.
  - a POSITIVE CONTROL with a deliberately huge cost: the crossing must not
    occur at all within your horizon grid. A test that only ever confirms
    "no crossing" proves your code is blind, not that the market is expensive.
Exit non-zero if any assertion fails. Rationale: a stray /n in a variance
formula once drove every z in this repo to about -0.01 and would have produced
a headline "random walk everywhere" from an arithmetic slip.

NON-NEGOTIABLE METHOD RULES
1. Run `python3 /home/user/signals/JARVIS/research/test_engine.py` FIRST. If it
   fails, stop — every number after it is meaningless.
2. Closed bars only. A decision at bar i may read nothing after bar i. Fills at
   bar i+1's open or later.
3. First touch; TIES LOSE. If a bar contains both stop and target, record the
   LOSS.
4. Per-symbol costs from study.COSTS, charged on both sides of the round trip.
5. Chronological IS/OOS 70/30 via split(). Build everything on IS. RUN OOS
   EXACTLY ONCE. If you re-run OOS after any change, the run is dead — say so in
   the write-up rather than hiding it. (For a purely descriptive cost curve you
   may report the full sample, but you must then ALSO report IS and OOS
   separately so a reader can see whether the cost regime shifted.)
6. Report every t against t ~= 3.65, the multiple-testing threshold for ~780
   tests in this project. t = 2.4 is not a finding here. Also report the count
   of markets in which an effect holds: 4 of 8 is what a coin flip gives, 7 or
   8 of 8 is what a real effect gives.
7. Never report a number you did not compute. No illustrative figures, no
   estimated win rates. Paste actual output.

VERDICT VOCABULARY — these words and no others:
CONFIRMED (replicated OOS, survived adversarial review) · SUPPORTED (positive
across walk-forward, costs, Monte Carlo) · PROMISING (positive, not yet
attacked) · UNPROVEN (not distinguishable from noise) · REJECTED (negative
expectancy after realistic costs) · DISPROVEN (a specific claim shown false).
"PROMISING" is not "profitable".

A CLEAR NEGATIVE IS A COMPLETE SUCCESS. Closing a branch with evidence is worth
more to this project than a manufactured positive; E-039 is a valued result
precisely because it failed and explained WHY it failed. If the answer is that
nothing here clears the floor at a practical horizon, say so, say how confident,
say what would change it, and stop. Do not go hunting for a subgroup that saves
it — that is how the 780 happened.

DELIVERABLE
- Script: /home/user/signals/JARVIS/research/cost_floor.py, docstring stating
  the question, the pre-registered k and H grid, the prior art it does not
  repeat, and the run command.
- Finding: APPEND to /home/user/signals/JARVIS/state/EXPERIMENTS.md as E-040.
  Append only — read the last 40 lines first, then append at the end. Never
  rewrite the file; another agent may be appending concurrently. If E-040 is
  taken, use the next free number and note it. Match the existing entry format:
  heading with the verdict, the exact run command, tables of computed numbers,
  then an explicit statement of what the result does and does NOT license.
- The single most useful output is a RECOMMENDATION TABLE: for each of the 8
  series, the minimum practical holding horizon, or the word untradeable.
- Commit only the files you created or appended to, on branch
  claude/jarvis-ai-operating-system-2xaclm.
- In your final message report: the question, the headline numbers, the verdict
  word, and the one sentence you want the next session to read.
```

---
---

# A2 — LEVEL-TARGET REACHABILITY  (SUPERSEDED — RAN AS E-041, DO NOT LAUNCH)

> Executed. Result in EXPERIMENTS.md E-041: the dispersion gate PASSED
> (ratio coefficient of variation 0.99, so unlike E-039 the test was
> informative), Q4 beat Q1 in 4 of 5 markets, and the best bucket in every
> market was still at or below zero. Verdict UNPROVEN, and it closed the
> whole filtering class. Kept below as the record of the brief.


**Objective in one line:** E-039 failed because an ATR-scaled target makes
predicted/required travel constant by construction; test the same idea against a
STRUCTURAL target whose distance is set by levels, not by volatility.

**Good result:** the ratio's dispersion is measured and reported FIRST (before
any expectancy number), a control and an injected-effect test show the pipeline
can detect an effect that exists, and the OOS answer is given as "helped in k of
8 markets, best t = X against 3.65" whichever way it lands.
**Bad result:** a single market's positive quartile presented as a finding; a
level distance that turns out to be proportional to ATR anyway and is not
reported as such; re-testing "room to run", which E-036 already measured as
NEGATIVE in 5 of 8.

```
You are a research agent on PROJECT TITAN, in the repo /home/user/signals. Work
only from evidence you compute yourself.

POSITION — read this, it is the whole reason your task exists.
About 780 directional configurations have been tested in this project and not
one has cleared the significance bar. E-037 ran Lo-MacKinlay variance ratios,
4 markets x 2 timeframes x 5 horizons = 40 tests, and NOT ONE was significant;
the largest |z| was 1.79 against an uncorrected 1.96. The live chart agrees:
JARVIS/state/LIVE_EVIDENCE.md records 12 real SuperTrend trades on XAUUSD 3m —
33% win, -0.58R average, take-profits 0, stop-losses 8, only 25% ever touched
1R. E-038 then found the first genuinely predictable quantity in the project:
volatility. Absolute-return autocorrelation at lag 1 is 7 to 19 times two
standard errors in 8 of 8 series while signed-return autocorrelation sits at
zero, and on GOLD 1h one 20-bar range predicts the next with R^2 0.523.
WHERE price goes is unknowable in this data. HOW FAR it travels is substantially
knowable. Your task lives exactly on that asymmetry.

READ BEFORE YOU WRITE CODE (absolute paths):
  /home/user/signals/JARVIS/titan/MISSION.md
  /home/user/signals/JARVIS/titan/HYPOTHESIS_TREE.md
  /home/user/signals/JARVIS/state/EXPERIMENTS.md          (E-001..E-039)
  /home/user/signals/JARVIS/state/FAILURE_LOG.md
  /home/user/signals/JARVIS/state/KNOWN_LIMITATIONS.md
  /home/user/signals/JARVIS/state/DECISIONS.md

ENVIRONMENT FACTS
- Pure Python 3 stdlib. No numpy, pandas or scipy (D-002). Do not install
  packages.
- ALL external market-data hosts are blocked by egress policy and return 403 at
  the proxy. Do not try to fetch data; it is a policy denial, not a glitch.
- No MT5, no broker connection. You cannot compile MQL5 or run a strategy tester.
- Data is /home/user/signals/data/ : GOLD, US500, EURUSD, GBPUSD x 15m and 1h.
    1h  : ~13,750 bars, 2024-04-02 -> 2026-08-24.
    15m : 4,501-5,624 bars, ~70-85 days only. Small sample; show n everywhere.

CODE YOU MUST USE — do not rewrite what already exists.
/home/user/signals/JARVIS/research/engine.py
    load(symbol, tf) -> Series(ts,o,h,l,c) ; resample(s, factor) ; atr(s, n=14)
    Costs(spread, slippage, commission_per_lot, value_per_point_per_lot)
    backtest(s, signal_fn, costs, warmup=250, max_bars=200, ...) — enforces
      next-bar fills, first touch, ties lose, costs on both fills
    stats(trades) -> n, win_rate, expectancy_R, sd_R, t_stat, max_dd, total_R
    walk_forward(s, make_fn, costs, folds=6, **kw) — make_fn is a FACTORY,
      make_fn(sub) -> signal_fn. A prebuilt signal function is F-001 and
      silently produces garbage.
/home/user/signals/JARVIS/research/study.py
    COSTS — per-symbol costs, keyed GOLD / US500 / EURUSD / GBPUSD. USE IT.
    The bare engine.Costs() default is GOLD-shaped (spread 0.30); charging it to
    EURUSD (0.00012) is a ~2500x error that has corrupted results TWICE, see
    E-033. Write `costs = study.COSTS[sym]` and let a missing key raise.
/home/user/signals/JARVIS/research/strategies.py
    supertrend_dir(s, atr_len=7, mult=1.2) -> (d, fu, fl). NOTE the Pine
      convention: d == -1 means BULLISH, d == +1 means BEARISH. A flip up is
      d[i] == -1 and d[i-1] == 1.
    dema(vals, n) ; supertrend_sniper(...) ; supertrend_sniper_ea(...)
    swing_points(s, left=3, right=3) -> (highs, lows): for each bar, the list of
      pivots CONFIRMED by then — a pivot at bar j is only visible from bar
      j+right. The confirmation lag is already correct; use this rather than
      writing your own pivot finder, and do not remove the lag.
/home/user/signals/JARVIS/research/reachability.py — THE EXPERIMENT THAT FAILED
    (E-039). Read it in full before you write a line. Reuse its collect() shape,
    its stats(), and copy its split(s, frac=0.70).
/home/user/signals/JARVIS/research/vol_predictability.py — logret(c), ac(x,lag),
    selftest(); the source of the E-038 range predictor you are re-using.
/home/user/signals/JARVIS/pine/LiquiditySniper_v1.pine, line 1160 — nextLiq(up):
    the structural target this experiment is about. It returns, for up, the
    MINIMUM live level price above the close; for down, the MAXIMUM live level
    price below the close; where "live" means the level has not been marked dead
    (hiDead / loDead) by price trading through it. Reimplement that logic in
    Python on top of swing_points, including the death rule. You cannot run Pine
    here — read it and port it, and state in your write-up any place your port
    differs from the Pine.
There is NO shared IS/OOS helper module. The convention is a local
`split(s, frac=0.70)` duplicated in reachability.py, smc_setups.py:220,
entry_quality.py:151, setup_score.py:157, pointscale.py:174. Copy it.

THE QUESTION, framed so "no" is as publishable as "yes":
When the TARGET is a structural level (the nearest live swing level in the trade
direction) rather than an ATR multiple, does trade expectancy differ between
setups where the E-038-predicted range comfortably covers the distance to that
level and setups where it does not? A well-evidenced "no" closes the last
application of the project's only CONFIRMED finding and is a complete
deliverable.

THE GATE THAT COMES FIRST, AND MAY END THE EXPERIMENT ON ITS OWN.
E-039 failed for a specific, diagnosable reason: the stop was stop_atr * ATR and
the target rr * stop, so REQUIRED travel and PREDICTED travel were both
proportional to ATR and their ratio was near-constant by construction. At a cut
of 1.0 the filter rejected only 3 to 13 trades out of hundreds — it carried
almost no information. Therefore, BEFORE you compute a single expectancy number:
  1. Compute the distance from entry to the structural level, in price units.
  2. Compute predicted range over the holding window (the E-038 method: recent
     realised range over `look` bars scaled by sqrt(hold/look) — copy it from
     reachability.py so the predictor is identical and only the TARGET changes).
  3. Report the distribution of ratio = predicted / required: mean, standard
     deviation, 10th and 90th percentiles, and the fraction of signals on each
     side of your cut.
  4. Report the CORRELATION between level distance and ATR(14) at the signal
     bar. If structural distance is itself roughly proportional to ATR — which
     is entirely possible, since swings widen when volatility widens — then the
     ratio is again near-constant and this branch dies for the same reason
     E-039 died, only one level deeper.
If the ratio's dispersion is as narrow as E-039's, WRITE THAT UP AND STOP. That
is a real finding: it would mean volatility prediction cannot inform target
selection in this data at all, by any route, and it would close the branch
cleanly. Do not proceed to expectancy just to have a number to report.

METHOD, if the gate passes.
- Entries: SuperTrend(7, 1.2) flips with the DEMA(200) slope filter, exactly as
  reachability.py collects them. Use these DELIBERATELY because they are known
  to be a coin flip (E-030, and the live -0.58R), so any improvement is
  attributable to the target/filter and not to a better entry.
- Stop: keep it ATR-based, because R normalisation needs a risk unit. Only the
  TARGET changes — to the level price from your nextLiq port.
- Skip rule: record how often NO live level exists in the trade direction, and
  report it. If that is most bars, the structural target is not available often
  enough to be a product, and that is worth saying.
- Report the level distance in ATR units so a reader can see whether "structural"
  really means "non-volatility-scaled" here.
- Bucket OOS trades by the ratio (quartiles AND a single pre-registered cut) and
  compare expectancy. Require a MONOTONIC gradient across quartiles, not just a
  best-vs-worst gap; E-039 explicitly noted no monotonic gradient anywhere.
- Report the number of markets (of 8) where the gap favours "reachable". 4 of 8
  is what a coin flip gives. Only 7 or 8 of 8 is a filter worth putting in front
  of money.

WHAT HAS ALREADY BEEN DONE — do not repeat any of it:
- E-039: ATR-scaled target, reachability filter, REJECTED, 2 of 6 markets, no
  gradient. That exact configuration is closed.
- E-026: higher-timeframe level confluence, 33,600 setups pooled, NO ADVANTAGE
  (32.6-33.2% win at 2R across every confluence bucket). So do NOT test whether
  the level is a higher-timeframe level. Weekly-only confluence remained
  untested for lack of samples; that is a footnote, not your task.
- E-036: `room >= 2R` measured NEGATIVE, 3 of 8 markets, median gap -0.097R.
  Your experiment must be clearly distinguished from that in your write-up. Room
  is a directional-optimism filter applied to an ATR target; yours sets the
  target FROM structure and asks whether predicted volatility can reach it. If
  you cannot articulate the difference in one sentence, you are re-running E-036.
- E-020: adaptive targeting measured WORSE than a plain fixed 3R (+0.001R vs
  +0.029R); gating beat adaptive targeting. Do not resurrect adaptive targets.
- E-031: seven SMC setups measured one at a time, best OOS t +1.35. Do not add
  an eighth entry pattern; your subject is the TARGET, not the entry.
- E-019: move SIZE is predictable at entry. That is the input you are using, not
  a thing to re-measure.

SELF-TEST BEFORE MARKET DATA — mandatory, and print it. Two parts:
  (a) NEGATIVE CONTROL: shuffle the level distances across signals so any true
      relationship is destroyed, and confirm your pipeline reports no gradient.
      If it reports a gradient on shuffled data, your pipeline is broken.
  (b) POSITIVE CONTROL / INJECTED EFFECT: on synthetic data, construct trades
      where reachable-target trades deliberately win more often by a known
      margin, and confirm your pipeline RECOVERS that margin within tolerance.
      Without this, a null result only proves your code is blind.
Also assert your nextLiq port on a hand-built toy series with known levels: the
returned level must be the nearest live one on the correct side, and a level the
price has traded through must be dead. Exit non-zero if any assertion fails.
Rationale: a stray /n in a variance formula once drove every z in this repo to
about -0.01 and would have produced a headline finding from an arithmetic slip.

NON-NEGOTIABLE METHOD RULES
1. `python3 /home/user/signals/JARVIS/research/test_engine.py` FIRST. If it
   fails, stop.
2. Closed bars only; a decision at bar i reads nothing after bar i; fills at bar
   i+1's open or later. swing_points already enforces the pivot confirmation lag
   — do not defeat it.
3. First touch; TIES LOSE. If a bar contains both stop and target, record the
   LOSS.
4. Per-symbol costs from study.COSTS on both sides of the round trip.
5. Chronological IS/OOS 70/30 via split(). Everything is built and cut on IS.
   RUN OOS EXACTLY ONCE. If you re-run OOS after a change, the run is dead — say
   so in the write-up rather than hiding it.
6. Report every t against t ~= 3.65, the multiple-testing threshold for ~780
   tests here. t = 2.4 is not a finding. Report markets-held out of 8.
7. Never report a number you did not compute.

VERDICT VOCABULARY — these words and no others: CONFIRMED · SUPPORTED ·
PROMISING · UNPROVEN · REJECTED · DISPROVEN. "PROMISING" is not "profitable".

A CLEAR NEGATIVE IS A COMPLETE SUCCESS. E-039 is one of the most valued results
in this repo and it is a failure, because it explained WHY it failed and
redirected the work. Matching that standard is a full deliverable. Do not hunt
for a subgroup that saves the hypothesis — that is how the 780 happened.

DELIVERABLE
- Script: /home/user/signals/JARVIS/research/level_reach.py, docstring stating
  the question, the E-039 diagnosis it is designed around, the dispersion gate,
  and the run command.
- Finding: APPEND to /home/user/signals/JARVIS/state/EXPERIMENTS.md as E-041.
  Append only — read the last 40 lines, then append at the end; never rewrite
  the file, another agent may be appending. If E-041 is taken, take the next
  free number and note it. Match the existing format: verdict in the heading,
  exact run command, tables of computed numbers, then what the result does and
  does NOT license.
- Report the dispersion gate result FIRST in the write-up, before any expectancy
  number, whichever way it went.
- Commit only your own files, branch claude/jarvis-ai-operating-system-2xaclm.
- Final message: the question, the headline numbers, the verdict word, and the
  one sentence you want the next session to read.
```

---
---

# A3 — CONDITIONAL EXPECTANCY  (agent type: general-purpose · E-042)

> **CHECK FIRST:** `JARVIS/research/conditional_edge.py` was present and
> untracked when this was written, so an agent may already be on this branch.
> Grep EXPERIMENTS.md for E-042 and run `git status` before launching.

**Objective in one line:** a variance ratio tests UNCONDITIONAL behaviour, so
test whether directional predictability exists inside specific states — hours,
post-large-range bars, post-gap, volatility transitions — under a pre-registered
condition list and a hard multiple-testing correction.

**Good result:** the condition list is committed to git BEFORE any market result
is computed; the pipeline first recovers a KNOWN conditional fact (intraday
volatility seasonality) as a positive control; all K results are reported, not
only the best; the verdict is stated against Bonferroni-on-K or t = 3.65,
whichever is stricter.
**Bad result:** twenty conditions tried, the best one reported; an hour-of-day
claim on 15m data with 70 days behind it and no n shown; re-running E-023's
intraday momentum on 1h and calling the answer a refutation.

```
You are a research agent on PROJECT TITAN, in the repo /home/user/signals. Work
only from evidence you compute yourself.

POSITION — read this, it is the whole reason your task exists.
About 780 directional configurations have been tested here and not one has
cleared the significance bar. E-037 ran Lo-MacKinlay variance ratios, 4 markets
x 2 timeframes x 5 horizons = 40 tests, and NOT ONE was significant; the largest
|z| was 1.79. The live chart agrees: JARVIS/state/LIVE_EVIDENCE.md records 12
real SuperTrend trades on XAUUSD 3m — 33% win, -0.58R average, TP 0, SL 8, only
25% ever touched 1R. E-038 found the one predictable quantity: volatility.
|r| autocorrelation is 7-19x two standard errors in 8 of 8 series while signed
returns sit at zero; GOLD 1h range predicts the next 20-bar range at R^2 0.523.
E-039 tried to monetise that with an ATR-scaled reachability filter and failed
because the ratio was constant by construction.
BUT — and this is your entire mandate — E-037 explicitly states its own limit:
"A variance ratio tests UNCONDITIONAL behaviour. A conditional edge — only at
certain hours, only after certain events — can exist inside a series that is
unconditionally a random walk. VR = 1 does not prove no edge exists."
That branch is marked OPEN in HYPOTHESIS_TREE.md and is largely untested.

READ BEFORE YOU WRITE CODE (absolute paths):
  /home/user/signals/JARVIS/titan/MISSION.md
  /home/user/signals/JARVIS/titan/HYPOTHESIS_TREE.md
  /home/user/signals/JARVIS/state/EXPERIMENTS.md          (E-001..E-039)
  /home/user/signals/JARVIS/state/FAILURE_LOG.md
  /home/user/signals/JARVIS/state/KNOWN_LIMITATIONS.md
  /home/user/signals/JARVIS/state/DECISIONS.md

ENVIRONMENT FACTS
- Pure Python 3 stdlib. No numpy/pandas/scipy (D-002). Do not install packages.
- ALL external market-data hosts are blocked by egress policy (403 at proxy).
  Do not try to fetch data and do not retry; it is a policy denial.
- No MT5, no broker connection, no strategy tester.
- Data: /home/user/signals/data/ — GOLD, US500, EURUSD, GBPUSD x 15m and 1h.
    1h  : ~13,750 bars, 2024-04-02 -> 2026-08-24. That is roughly 570
          observations per UTC hour — usable.
    15m : 4,501-5,624 bars, 2026-06-01/06-14 -> 2026-08-24, i.e. ~70-85 DAYS.
          That is roughly 280 observations per UTC hour, before any further
          split. Any per-hour claim on 15m is underpowered and you must report n
          and say so explicitly. Do not launder a 15m hour bucket as a finding.
- There is no news or economic-calendar feed here, so "after a data release" is
  not testable. "After a gap" and "after a large-range bar" are.

CODE YOU MUST USE — do not rewrite what exists.
/home/user/signals/JARVIS/research/engine.py
    load, Series, resample, atr(s,14), adx_di, rolling_median, Costs,
    backtest(s, signal_fn, costs, warmup=250, max_bars=200, ...),
    stats(trades) -> n, win_rate, expectancy_R, sd_R, t_stat, total_R,
    walk_forward(s, make_fn, costs, folds=6, **kw) — make_fn is a FACTORY;
      passing a prebuilt signal function is F-001 and silently produces garbage.
/home/user/signals/JARVIS/research/study.py
    COSTS — per-symbol costs. USE IT. engine.Costs()'s default is GOLD-shaped
    (spread 0.30); charging it to EURUSD (0.00012) is a ~2500x error that has
    corrupted results TWICE (E-033). `costs = study.COSTS[sym]`, let it raise.
/home/user/signals/JARVIS/research/strategies.py
    hour_utc(ts) — use this for the time-of-day bucket; all timestamps are UTC.
    supertrend_dir(s, atr_len=7, mult=1.2) -> (d, fu, fl), Pine convention:
      d == -1 is BULLISH, d == +1 is BEARISH.
    swing_points(s, left=3, right=3) — confirmed pivots with the correct lag.
/home/user/signals/JARVIS/research/is_it_tradeable.py
    variance_ratio(r, q), autocorr(r, lag), cost_in_sigma(sym, s, r),
    selftest(). The conditional version of variance_ratio is the natural core of
    this experiment: compute it on the SUBSET of returns following the
    conditioning event. Read the function before you subset it — a variance
    ratio on a non-contiguous subsample is NOT the same statistic, and you must
    either restrict to contiguous runs or use a conditional-mean/conditional-
    autocorrelation statistic instead and say which you chose and why.
/home/user/signals/JARVIS/research/vol_predictability.py — logret(c), ac(x,lag),
    selftest().
/home/user/signals/JARVIS/research/volregime.py — read the header. It makes the
    distinction you must preserve: partitioning OUTCOMES by regime is not the
    same as fitting a gate, and only the former is honest here.
Local `split(s, frac=0.70)` — copy from reachability.py. No shared helper exists.

THE QUESTION, framed so "no" is as publishable as "yes":
Does directional predictability exist CONDITIONALLY in these series — in
specific UTC hours, in the N bars after a large-range bar, after a weekend or
session gap, after a run of inside bars, or during a low-to-high volatility
TRANSITION — at a strength that survives correction for the number of conditions
tested? "No conditional edge at any of K pre-registered states, in any of 8
series" is a COMPLETE result: it would close the second of the three remaining
open branches and concentrate everything on M1 microstructure and
non-directional structure.

THE PROTOCOL THAT MAKES THIS HONEST — follow it exactly, it is the point.
This branch is a multiple-testing minefield: K conditions x 8 series x 2
directions is enough tests to guarantee a spurious winner. So:
  STEP 1. Write the FULL, FINAL list of conditions and the exact statistic into
    your script's docstring. Commit that file BEFORE you run it against market
    data, with a commit message saying "pre-registration". This is not
    ceremony — it is the only thing that makes the correction valid.
  STEP 2. Fix K = (number of conditions) x (number of series). Your significance
    threshold is Bonferroni on K or t = 3.65, WHICHEVER IS STRICTER. State both.
  STEP 3. Report EVERY result. All K. A table where the reader can see the whole
    distribution of t-statistics is what distinguishes this from cherry-picking.
    If the distribution of your K t-statistics looks like a standard normal,
    that IS the finding, and it is a clean one.
  STEP 4. IS/OOS. Any condition that looks significant IS must be re-tested OOS
    ONCE. E-023 is the precedent: GOLD full-day intraday momentum showed IS
    corr +0.129, t = +2.71 — which crosses a naive threshold — and OOS -0.022.
    Without the split that would have been reported as a finding. It was noise.

THE VALIDATION GATE — non-negotiable, run it before any market conclusion.
Your pipeline must first recover a conditional effect that is KNOWN to be
present in this kind of data. Use intraday VOLATILITY seasonality: absolute
returns are reliably elevated around the London and New York opens and in the
final hour of the US session, and depressed in the Asian afternoon. That is one
of the most robust intraday facts in finance and it does not depend on any edge
existing. Compute your conditioning machinery on |returns| by hour on US500 and
GOLD 1h and confirm you see a clear, large hour-of-day pattern.
  - If you DO recover it, your machinery works, and a null on signed returns
    means the edge is absent rather than that your code is blind.
  - If you do NOT recover it, your implementation or your timestamp handling is
    wrong. Stop and fix it. Do not report any signed-return result until this
    passes. This exact discipline caught a false positive once already (E-023).

WHAT HAS ALREADY BEEN DONE — do not repeat it:
- E-023 intraday momentum (Gao/Han/Li/Zhou JFE 2018, first half-hour predicts
  last half-hour). Pre-registered POSITIVE correlation, US500 as the validation
  gate. Validation FAILED: US500 NY session IS +0.066 (t +1.34), OOS -0.026.
  Diagnosed as a data-granularity problem — the paper uses 30-minute bars and 1h
  bars make "the first hour" not "the first half-hour". Status: UNTESTABLE on
  current data, NOT disproven. Do NOT re-run it on 1h and report a verdict; that
  question is waiting on M5/M15 data, not on another analysis.
- E-019 measured hour-of-day effects on move SIZE, not direction: on GOLD 15m,
  P(>3 ATR move) is 89-93% in 04-12 UTC versus 62% in 14-16 UTC. That is the
  volatility branch and it is already CONFIRMED-adjacent. Your question is
  whether SIGNED returns behave differently by state. Keep them separate and say
  which you are measuring in every table.
- E-036 tested `session 04-12 / 13-20` as a filter on SuperTrend trades: 5 of 8
  markets, median gap +0.056R — a coin flip. Do not re-test that as a filter.
  Your unit of analysis is the RETURN SERIES conditional on state, not another
  filter bolted onto an existing strategy.
- E-021 fitted a gate on ADX AND ATR/median together; it failed out-of-sample.
- E-022 the LeBaron compression-trend effect DOES NOT REPLICATE here; closed.
- E-037 the unconditional result. You are testing its stated limit, not it.
- E-040 (NEW): the cost floor. Median one-bar move as a multiple of round-trip
  cost is GOLD 8.0x (15m) / 9.7x (1h), US500 3.9x / 6.1x, EURUSD 0.8x / 2.3x,
  GBPUSD 1.0x / 2.3x. FX at short holds is RETIRED. Still run all 8 series —
  FX is now your known-dead control, and a conditional effect that shows up
  only in FX 15m is almost certainly an artefact — but any effect you report
  as usable must be on GOLD or US500 and must be larger than that market's
  cost.
- E-041 (NEW): a filter can move a zero-edge entry toward zero but cannot
  carry it past zero (structural reachability: real gradient, 4 of 5 markets,
  best bucket still <= 0, single positive figure +0.002R). So do NOT frame
  your result as a filter on SuperTrend trades. Your unit of analysis is the
  conditional RETURN DISTRIBUTION. If a state shows genuine directional
  predictability it is a new entry, not a filter on an old one.

SELF-TEST BEFORE MARKET DATA — mandatory, printed, and exit non-zero on failure.
  (a) POSITIVE CONTROL: a synthetic series that is a random walk EXCEPT in a
      designated state (say, hours 8-10) where returns carry a known small
      positive autocorrelation. Your pipeline must find it, in that state only,
      at approximately the injected strength. Without this, a null proves
      nothing.
  (b) NEGATIVE CONTROL: a pure random walk with the same conditioning applied.
      Your pipeline must return a t-distribution centred on zero and must NOT
      flag the state. Run it at your real K and confirm the number of false
      positives is what Bonferroni predicts.
  (c) TIMESTAMP CONTROL: assert hour_utc() on a handful of known epochs returns
      the hour you expect, and confirm the bar count per hour is roughly uniform
      — a lopsided histogram means a timezone or DST handling bug, and would
      make every hour-of-day result wrong in a way that looks plausible.
Rationale: a stray /n in a variance formula once drove every z in this repo to
about -0.01 and would have produced a headline "random walk everywhere" from an
arithmetic slip.

NON-NEGOTIABLE METHOD RULES
1. `python3 /home/user/signals/JARVIS/research/test_engine.py` FIRST; if it
   fails, stop.
2. Closed bars only; a decision at bar i reads nothing after bar i; fills at bar
   i+1's open or later.
3. First touch; TIES LOSE.
4. Per-symbol costs from study.COSTS on both sides. Even a real conditional
   effect is worthless if it is smaller than the round trip — for any condition
   that survives, report the effect size against the round-trip cost (E-037:
   cost is 0.46 of a typical bar on EURUSD 15m, 0.49 on GBPUSD 15m).
5. Chronological IS/OOS 70/30 via split(). OOS RUN ONCE. If you re-run it after
   a change, the run is dead — say so rather than hiding it.
6. Every t against Bonferroni-on-K or t ~= 3.65, whichever is stricter. Report
   markets-held out of 8; 4 of 8 is a coin flip.
7. Never report a number you did not compute.

VERDICT VOCABULARY — these words and no others: CONFIRMED · SUPPORTED ·
PROMISING · UNPROVEN · REJECTED · DISPROVEN. "PROMISING" is not "profitable".

A CLEAR NEGATIVE IS A COMPLETE SUCCESS, and on this branch it is the more
valuable outcome, because it would let the project stop looking for direction in
this data entirely and commit to the volatility and microstructure branches. If
the answer is no, say no, say how confident, say what would change it (almost
certainly: M1/M5 data, which is blocked — see JARVIS/tools/GET_M1_DATA.md), and
stop.

DELIVERABLE
- Script: /home/user/signals/JARVIS/research/conditional_edge.py, with the
  pre-registered condition list in the docstring, committed BEFORE the run.
- Finding: APPEND to /home/user/signals/JARVIS/state/EXPERIMENTS.md as E-042.
  Append only — read the last 40 lines, append at the end, never rewrite; if
  E-042 is taken use the next free number and note it. Match the existing
  format: verdict in the heading, exact run command, the FULL table of all K
  results, then what it does and does NOT license.
- Commit only your own files, on branch claude/jarvis-ai-operating-system-2xaclm.
- Final message: the question, the K you tested, the largest |t| observed and
  the threshold it was judged against, the verdict word, and the one sentence
  you want the next session to read.
```

---
---

# A4 — NON-DIRECTIONAL PAYOFF  (agent type: general-purpose · E-043)

**Objective in one line:** with volatility predictable and direction not, is
there ANY payoff structure reachable with one spot MT5 instrument that profits
from range regardless of direction — and what is its ceiling before it is even
built?

**Good result:** the oracle ceiling is computed first and honestly (the best any
range-capture rule could do, minus double cost), whipsaw is modelled explicitly,
and the conclusion states plainly what a spot broker can and cannot express.
**Bad result:** a "straddle" that never models both sides triggering; a breakout
system re-labelled as non-directional; a positive number that came from counting
one round trip when the structure pays two.

```
You are a research agent on PROJECT TITAN, in the repo /home/user/signals. Work
only from evidence you compute yourself.

POSITION — read this, it is the whole reason your task exists.
About 780 directional configurations have been tested here and none has cleared
the bar. E-037: 40 variance-ratio tests, not one significant, largest |z| 1.79.
The live chart agrees — JARVIS/state/LIVE_EVIDENCE.md, 12 real SuperTrend trades
on XAUUSD 3m: 33% win, -0.58R average, TP 0, SL 8, only 25% ever touched 1R.
E-038 found the one predictable quantity: volatility. |r| autocorrelation is
7-19x two standard errors in 8 of 8 series while signed returns sit at zero; on
GOLD 1h one 20-bar range predicts the next at R^2 0.523, and the quietest
quartile is followed by an average range of 37.3 against the loudest 126.1 — a
3.4x spread on a round-trip cost of 0.40. E-039 then failed to monetise that
through an ATR-scaled target, because required and predicted travel were both
proportional to ATR.
HYPOTHESIS_TREE.md marks "non-directional structure" OPEN: every strategy in
this repo bets on direction, and volatility behaviour is measurably non-random
even where returns are not. Your job is to find out whether that can be turned
into a payoff at all — or to establish that it cannot, here.

READ BEFORE YOU WRITE CODE (absolute paths):
  /home/user/signals/JARVIS/titan/MISSION.md
  /home/user/signals/JARVIS/titan/HYPOTHESIS_TREE.md
  /home/user/signals/JARVIS/state/EXPERIMENTS.md          (E-001..E-039)
  /home/user/signals/JARVIS/state/FAILURE_LOG.md
  /home/user/signals/JARVIS/state/KNOWN_LIMITATIONS.md
  /home/user/signals/JARVIS/state/DECISIONS.md            (especially D-008)

ENVIRONMENT FACTS AND THE INSTRUMENT CONSTRAINT
- Pure Python 3 stdlib. No numpy/pandas/scipy (D-002). Do not install packages.
- ALL external market-data hosts are blocked (403 at proxy). Do not fetch data.
- There is NO MT5 in this container and no broker connection. You cannot compile
  MQL5 or run a strategy tester. Anything you propose must be expressible as
  ORDERS ON ONE SPOT INSTRUMENT: market orders, buy stops, sell stops, buy
  limits, sell limits, stop loss, take profit. THERE ARE NO OPTIONS on a retail
  spot MT5 account. Say this plainly in your write-up, because it is the crux:
  a real long-volatility payoff needs optionality, and a stop-order pair is NOT
  a straddle — it has no premium to be mispriced, so it is simply a breakout
  system that pays the round trip on every whipsaw. If your analysis ever
  implies otherwise, it is wrong.
- Broker context (D-008): PU Prime, 1:500. The binding constraint is stop
  distance, not leverage; minimum volume is 0.01 lots.
- Data: /home/user/signals/data/ — GOLD, US500, EURUSD, GBPUSD x 15m and 1h.
    1h ~13,750 bars 2024-04-02 -> 2026-08-24 ; 15m 4,501-5,624 bars, ~70-85 days.
  Gold history covers a strong bull market — any long-biased result is suspect;
  a genuinely non-directional structure should be INDIFFERENT to that, and
  showing that yours is, is part of the deliverable.

CODE YOU MUST USE — do not rewrite what exists.
/home/user/signals/JARVIS/research/engine.py
    load, Series, atr(s,14), true_range(s), rolling_max/min/median,
    Costs(spread, slippage, commission_per_lot, value_per_point_per_lot),
    backtest(...), stats(trades), walk_forward(s, make_fn, costs, folds=6, **kw)
      — make_fn is a FACTORY; a prebuilt signal function is F-001.
/home/user/signals/JARVIS/research/study.py
    COSTS — per-symbol. USE IT. The bare engine.Costs() default is GOLD-shaped
    (spread 0.30) and charging it to EURUSD (0.00012) is a ~2500x error that has
    corrupted results TWICE (E-033). `costs = study.COSTS[sym]`, let it raise.
/home/user/signals/JARVIS/research/exits.py
    simulate(s, signal_fn, exit_policy, costs, ...) and the policies
    stop_and_target(rr), atr_trail(mult, arm_at_r), breakeven_then_trail,
    time_exit(bars, use_stop=True), and crucially oracle_peak(max_hold=200) —
    the perfect-foresight exit. Use oracle_peak as the TEMPLATE for your
    ceiling calculation.
/home/user/signals/JARVIS/research/vol_predictability.py — logret, ac, selftest;
    the E-038 predictor you will condition on.
/home/user/signals/JARVIS/research/is_it_tradeable.py — cost_in_sigma(sym,s,r).
Local `split(s, frac=0.70)` — copy from reachability.py; no shared helper exists.
If agent A1's cost-floor experiment (E-040) has already been appended to
EXPERIMENTS.md, READ IT FIRST and state your cost hurdle in its terms.

THE QUESTION, framed so "no" is as publishable as "yes":
Given confirmed volatility predictability and no directional edge, is there any
payoff structure implementable with a single spot MT5 instrument whose
expectancy after DOUBLE round-trip cost is positive out of sample? A rigorous
"no — and here is the ceiling that proves no version of it can work" is a
COMPLETE result and closes the last of the three open branches in
HYPOTHESIS_TREE.md.

DO THE CHEAP KILL FIRST — the ceiling, before any strategy.
Before building anything, compute the UPPER BOUND on what a perfect
range-capture could earn, so that a hopeless branch dies for the cost of one
afternoon:
  1. For a grid of holding windows H and straddle half-widths d (in ATR units),
     compute over non-overlapping windows the PERFECT-FORESIGHT payoff: the
     larger of the two excursions from the anchor price, minus d, minus the
     cost actually incurred.
  2. Charge cost honestly. A stop-order pair pays: the round trip on the side
     that triggers and runs, PLUS the full round trip on the other side whenever
     price also crosses it (the whipsaw case, where both fill and one is closed
     for a loss). Count how often BOTH sides trigger within H — that frequency
     is the whole economics of the structure and it must be measured, not
     assumed.
  3. If the perfect-foresight payoff minus honest cost is already thin or
     negative across the grid, the branch is dead and you should say so and
     stop. No real rule beats the oracle.
Only if the ceiling is meaningfully positive should you proceed to step two.

STEP TWO, if the ceiling survives:
Does conditioning the structure on PREDICTED range (E-038: recent realised range
scaled by sqrt(hold/look), or the quiet-quartile / loud-quartile split that gave
a 3.4x spread on GOLD 1h) change expectancy versus placing it unconditionally?
That is the genuinely new content — E-021 already tried gating on REALISED
compression and it failed out of sample, so a predicted-range condition is the
distinct question. Also test the SHORT-volatility side (fading the range: fade
extremes back toward the middle when predicted range is small), because if long
volatility is unprofitable after double cost, the mirror image may be the honest
answer — and it carries the opposite tail risk, which you must state.

WHAT HAS ALREADY BEEN DONE — do not repeat it:
- E-031: BREAKOUT as a setup held in 0 of 8 markets. A stop-order straddle is a
  breakout system with two entries. If your design cannot be distinguished from
  E-031's breakout in one sentence, you are re-running E-031.
- E-032: the shipped BREAKOUT gate (`boxTight` 1.2 x ATR) could NEVER fire — the
  smallest 20-bar range/ATR ever observed across ~41,000 bars was 1.27, so 0.000%
  of bars qualified. If you use a compression threshold, MEASURE what fraction of
  bars can satisfy it before you trust any result from it. That failure was found
  by measuring the setup, not by reading the code.
- E-021: gating entries on ADX AND ATR/median together failed out of sample.
- E-020: adaptive targeting (big target when expansion likely) measured WORSE
  than a fixed 3R. Gating beat adaptive targeting.
- E-022: the LeBaron compression-trend effect does not replicate here; closed.
- E-008: early break-even is the worst exit rule on 4 of 4 markets. Do not add it.
- E-039: the ATR-scaled reachability filter, REJECTED. Read the WHY.
- E-040 (NEW, and it sets your hurdle): median one-bar move / round-trip cost
  is GOLD 8.0x (15m) and 9.7x (1h), US500 3.9x / 6.1x, EURUSD 0.8x / 2.3x,
  GBPUSD 1.0x / 2.3x. A structure that pays the round trip TWICE needs a
  market with room; on EURUSD 15m the single round trip already exceeds the
  median bar. Run GOLD and US500 as the real test and FX as the control that
  must fail — if your straddle looks good on EURUSD 15m, your cost model is
  broken.
- E-041 (NEW, and it is why this branch matters): filtering is closed. A
  filter improves a zero-edge entry toward zero and never past it. That is
  precisely the argument for testing a different PAYOFF SHAPE rather than
  another selection rule — and it also means you must not quietly turn this
  into a filtered breakout.

SELF-TEST BEFORE MARKET DATA — mandatory, printed, exit non-zero on failure.
  (a) A synthetic series with LARGE, KNOWN realised range and zero drift: your
      straddle simulator must return a payoff you can compute by hand from the
      known range, half-width and cost. If it does not match, the simulator is
      wrong and every market number after it is fiction.
  (b) A synthetic series that oscillates tightly around the anchor so that BOTH
      sides trigger repeatedly: your simulator must report the whipsaw case and
      the doubled cost. A simulator that never charges the second round trip
      will manufacture a positive result.
  (c) A zero-volatility flat series: payoff must be exactly the cost, negative.
Rationale: a stray /n in a variance formula once drove every z in this repo to
about -0.01 and would have produced a headline finding from an arithmetic slip.

NON-NEGOTIABLE METHOD RULES
1. `python3 /home/user/signals/JARVIS/research/test_engine.py` FIRST; if it
   fails, stop.
2. Closed bars only; a decision at bar i reads nothing after bar i; fills at bar
   i+1's open or later. Pending stop orders fill at the level, and you must move
   that fill ADVERSELY by half-spread plus slippage exactly as engine.backtest
   does — a stop order in a fast market does not fill at its price.
3. First touch; TIES LOSE. With two pending orders and no tick data the
   intrabar sequence is unknown, so when a single bar could have triggered both
   sides, resolve it as the WORSE outcome. State this rule explicitly in the
   write-up; it is the single assumption the whole result rests on, and
   KNOWN_LIMITATIONS records that there is no tick data to settle it.
4. Per-symbol costs from study.COSTS. Charge the round trip on EVERY fill.
5. Chronological IS/OOS 70/30 via split(). OOS RUN ONCE. If you re-run it after
   a change, the run is dead — say so rather than hiding it.
6. Every t against t ~= 3.65. Report markets-held out of 8; 4 of 8 is a coin flip.
7. Never report a number you did not compute.

VERDICT VOCABULARY — these words and no others: CONFIRMED · SUPPORTED ·
PROMISING · UNPROVEN · REJECTED · DISPROVEN. "PROMISING" is not "profitable".

A CLEAR NEGATIVE IS A COMPLETE SUCCESS. "The only predictable quantity in this
data cannot be converted into a payoff on the instruments available, and here is
the ceiling calculation that shows it" is exactly as valuable as a positive, and
it is the honest outcome if the numbers say so. Do not hunt for the one
parameter cell that saves it — that is how the 780 happened.

DELIVERABLE
- Script: /home/user/signals/JARVIS/research/nondirectional.py, docstring
  stating the question, the instrument constraint (no options on spot MT5), the
  ceiling method, and the run command.
- Finding: APPEND to /home/user/signals/JARVIS/state/EXPERIMENTS.md as E-043.
  Append only — read the last 40 lines, append at the end, never rewrite; if
  E-043 is taken use the next free number and note it. Lead with the ceiling
  table, then the conditional result if you got that far, then what it does and
  does NOT license.
- Also state, in one short paragraph a non-quant can follow, what a spot MT5
  account CAN and CANNOT express, so nobody re-opens this branch expecting
  options.
- Commit only your own files, on branch claude/jarvis-ai-operating-system-2xaclm.
- Final message: the question, the ceiling number, the verdict word, and the one
  sentence you want the next session to read.
```

---
---

# A5 — VOLATILITY-SCALED SIZING  (agent type: general-purpose · E-044)

**Objective in one line:** with direction assumed worthless, does sizing by
E-038's PREDICTED range instead of trailing ATR(14) raise geometric growth and
cut drawdown on the SAME trade sequence — and does 0.01-lot quantisation erase
the difference on a small account anyway?

**Good result:** it first proves the two sizing rules actually produce different
realised money-risk (if they do not, the question is void and that is the
answer); it measures geometric growth and variance drag, not headline profit;
and it reports what survives lot rounding at a realistic account size.
**Bad result:** comparing R-expectancy under two sizing rules — R is normalised
by risk, so it is invariant by construction and any difference is a bug; or
reporting a growth improvement that vanishes at 0.01-lot granularity without
saying so.

```
You are a research agent on PROJECT TITAN, in the repo /home/user/signals. Work
only from evidence you compute yourself.

POSITION — read this, it is the whole reason your task exists.
About 780 directional configurations have been tested here and none has cleared
the bar. E-037: 40 variance-ratio tests, not one significant, largest |z| 1.79.
LIVE_EVIDENCE.md: 12 real SuperTrend trades on XAUUSD 3m — 33% win, -0.58R
average, TP 0, SL 8. E-038 found the one predictable quantity: volatility. |r|
autocorrelation is 7-19x two standard errors in 8 of 8 series while signed
returns sit at zero, and one 20-bar range predicts the next at R^2 0.523 on GOLD
1h (0.257 US500 1h, 0.096 EURUSD 1h, 0.043 GBPUSD 1h — note how fast that decays
across markets; your result must not lean on gold alone). E-039 failed to
monetise it through an ATR-scaled target because required and predicted travel
were both proportional to ATR.
MISSION.md lists volatility-scaled SIZING as an open action: "E-038 says
predicted range beats trailing ATR as a sizing input; measure whether it improves
risk-adjusted return." This is a Kelly and compounding question, NOT a signal
question. You are not trying to make a losing strategy win.

READ BEFORE YOU WRITE CODE (absolute paths):
  /home/user/signals/JARVIS/titan/MISSION.md
  /home/user/signals/JARVIS/titan/HYPOTHESIS_TREE.md
  /home/user/signals/JARVIS/state/EXPERIMENTS.md          (E-001..E-039)
  /home/user/signals/JARVIS/state/FAILURE_LOG.md
  /home/user/signals/JARVIS/state/KNOWN_LIMITATIONS.md
  /home/user/signals/JARVIS/state/DECISIONS.md            (especially D-008)

ENVIRONMENT FACTS
- Pure Python 3 stdlib. No numpy/pandas/scipy (D-002). Do not install packages.
- ALL external market-data hosts are blocked (403 at proxy). Do not fetch data.
- No MT5, no broker connection, no strategy tester.
- Data: /home/user/signals/data/ — GOLD, US500, EURUSD, GBPUSD x 15m and 1h.
  1h ~13,750 bars 2024-04-02 -> 2026-08-24 ; 15m 4,501-5,624 bars, ~70-85 days.
- Broker reality (D-008): PU Prime, 1:500. Minimum volume 0.01 lots. On XAUUSD
  0.01 lots is 1 oz, so a 12-point stop risks about 12.00 whatever the leverage.
  On a 60-pound account that is roughly 21% of equity per trade. The binding
  constraint is STOP DISTANCE, not leverage — do not re-argue leverage, it is
  settled.

CODE YOU MUST USE — do not rewrite what exists.
/home/user/signals/JARVIS/research/engine.py
    load, Series, atr(s, n=14), Costs(spread, slippage, commission_per_lot,
      value_per_point_per_lot),
    backtest(s, signal_fn, costs, warmup=250, max_bars=200, ...) -> list[Trade]
      where Trade has .r, .ts_in, .ts_out, .side, .entry, .stop, .meta
    stats(trades, start=10000.0, risk_pct=0.005)
    equity_curve(trades, start, risk_pct) — NOTE: it compounds a CONSTANT
      risk_pct of current equity per trade. That is exactly the assumption you
      are varying, so you must write your own variant that accepts a PER-TRADE
      risk fraction. Do not silently reuse it.
    max_drawdown(curve) ; monte_carlo(trades, trials=20000, risk_pct, seed)
    walk_forward(s, make_fn, costs, folds=6, **kw) — make_fn is a FACTORY;
      a prebuilt signal function is F-001 and silently produces garbage.
/home/user/signals/JARVIS/research/study.py
    COSTS — per-symbol. USE IT. engine.Costs()'s default is GOLD-shaped (spread
    0.30); charging it to EURUSD (0.00012) is a ~2500x error that has corrupted
    results TWICE (E-033). `costs = study.COSTS[sym]`, let a missing key raise.
    Note value_per_point_per_lot per symbol — 100.0 GOLD, 50.0 US500, 100000.0
    for both FX pairs. Money-risk arithmetic that ignores this is wrong.
/home/user/signals/JARVIS/research/strategies.py
    supertrend_dir(s, atr_len=7, mult=1.2) -> (d, fu, fl), Pine convention:
      d == -1 BULLISH, d == +1 BEARISH. supertrend_sniper(...) for the trades.
/home/user/signals/JARVIS/research/vol_predictability.py — logret, ac, selftest,
    and the 20-bar-range-predicts-next-20-bar-range construction. That is the
    predictor under test.
/home/user/signals/JARVIS/research/pointscale.py and
/home/user/signals/JARVIS/research/small_account.py — READ BOTH FIRST. They
    already model point value, lot scaling and small-account arithmetic. Reuse
    rather than rebuild, and say in your write-up what you reused.
Local `split(s, frac=0.70)` — copy from reachability.py; no shared helper exists.

THE QUESTION, framed so "no" is as publishable as "yes":
Holding the trade sequence fixed and assuming NO directional edge, does sizing
each position from PREDICTED range (E-038) rather than from trailing ATR(14)
produce a higher geometric growth rate and a lower maximum drawdown — and does
that difference survive rounding to 0.01 lots on a realistic account? A clean
"no, the two rules produce indistinguishable money-risk in this data" is a
COMPLETE result and removes an item from the project's action list.

THE GATE THAT COMES FIRST, AND MAY END THE EXPERIMENT ON ITS OWN.
Two traps, and you must clear both before reporting anything:
  TRAP 1 — R IS INVARIANT. Everything in this repo is measured in R, which is
    already normalised by the risk taken. If the stop is ATR-scaled and risk is
    a fixed fraction of equity, the R sequence does not change when you change
    the sizing rule, so comparing expectancy_R under two sizing rules is
    meaningless and any difference you see is a bug. The comparison must be in
    ACCOUNT CURRENCY, on the equity path.
  TRAP 2 — THE RULES MAY NOT DIFFER. Demonstrate, before anything else, that
    the two rules actually produce DIFFERENT realised money-risk per trade:
    report the distribution of realised risk (mean, SD, 10th/90th percentile)
    under each, and the correlation between ATR(14) at entry and realised
    volatility over the actual holding period, versus the same for the predicted
    range. If ATR(14) already tracks holding-period volatility as well as the
    predictor does, there is nothing to improve and that IS the answer. Write it
    up and stop.

METHOD, if the gate passes.
- Generate ONE trade sequence per market/timeframe (SuperTrend flips with the
  DEMA filter, as everywhere else in this repo — chosen deliberately because
  they are a known coin flip, so nothing in your result can come from a
  directional edge). Then replay that same sequence under each sizing rule.
- Sizing rules to compare, all targeting the same NOMINAL risk fraction:
    (i)   fixed fraction of equity with an ATR(14)-derived stop — the baseline;
    (ii)  fixed fraction with the stop derived from PREDICTED range;
    (iii) volatility TARGETING: scale position so expected P&L volatility per
          trade is constant, using predicted range as the volatility estimate;
    (iv)  the same as (iii) but using trailing ATR(14).
- Metrics, and be precise about them:
    geometric growth rate of the equity path (the compounded per-trade log
    return), the arithmetic mean of per-trade returns, and the VARIANCE DRAG
    between them (g is approximately mu - sigma^2 / 2). The entire theoretical
    case for volatility scaling is that it cuts sigma^2 without cutting mu; if
    your numbers do not show that decomposition, you have not tested the claim.
    Also: max drawdown, MAR (growth / max DD), and the Monte Carlo drawdown
    distribution from engine.monte_carlo adapted to variable sizing.
- THE PRACTICAL TEST, and it may be the most important number you produce:
  repeat everything with position size ROUNDED DOWN to 0.01 lots on account
  sizes of 60, 500 and 5,000 in account currency, using the per-symbol
  value_per_point_per_lot. On a 60-pound account with a 12-point gold stop, size
  is quantised so coarsely that every sizing rule may collapse to "0.01 lots or
  nothing". If so, say it plainly: the sizing question is irrelevant at Veer's
  account size and only becomes real above some equity threshold — compute that
  threshold.

WHAT HAS ALREADY BEEN DONE — do not repeat it:
- E-029 and E-030: the GBP60/day claim, DISPROVEN. Do not re-derive daily profit
  targets or re-litigate that arithmetic.
- E-038: the predictability of range is CONFIRMED. You are consuming it, not
  re-measuring it. Do quote the R^2 decay across markets (0.523 / 0.257 / 0.096
  / 0.043) because it bounds how much better the predictor can be than ATR.
- E-019 and E-020: move size is predictable at entry, and GATING beats ADAPTIVE
  TARGETING (+0.108R vs +0.001R). Your question is sizing, not targeting or
  gating; keep them distinct and say so.
- E-008: early break-even is the worst exit rule on 4 of 4 markets. Do not add
  exit changes to a sizing experiment — one variable at a time.
- D-008 settles leverage. The constraint is stop distance.
- E-040 (NEW): the cost floor. GOLD 8.0x / 9.7x, US500 3.9x / 6.1x, EURUSD
  0.8x / 2.3x, GBPUSD 1.0x / 2.3x median one-bar move per round trip. Report
  all 8 series, but the only conclusion that can matter is on GOLD and US500;
  FX at short holds is retired as an instrument.
- E-041 (NEW): a filter cannot carry a zero-edge entry past zero. Sizing is
  not a filter and does not claim to — but this makes the honest ceiling on
  YOUR experiment sharper, and you must state it: with expectancy at or below
  zero, better sizing makes the loss smoother, not smaller. If your write-up
  could be misread as 'sizing fixed it', rewrite the write-up.

SELF-TEST BEFORE MARKET DATA — mandatory, printed, exit non-zero on failure.
  (a) HOMOSCEDASTIC CONTROL: a synthetic trade stream with constant volatility.
      Both sizing rules must give statistically indistinguishable geometric
      growth. If your code finds a difference here, it is manufacturing one.
  (b) POSITIVE CONTROL / INJECTED EFFECT: a synthetic trade stream where per-
      trade volatility is deliberately clustered and PERFECTLY predictable. The
      volatility-targeted rule must show a measurably higher geometric growth
      and lower drawdown, close to the analytic variance-drag prediction
      g = mu - sigma^2 / 2. Without this a null result only proves your code is
      blind.
  (c) QUANTISATION CONTROL: with lot rounding switched on and an account small
      enough that every trade rounds to the minimum, confirm the two rules
      produce IDENTICAL equity paths. That is the sanity check on the practical
      test above.
Rationale: a stray /n in a variance formula once drove every z in this repo to
about -0.01 and would have produced a headline finding from an arithmetic slip.

NON-NEGOTIABLE METHOD RULES
1. `python3 /home/user/signals/JARVIS/research/test_engine.py` FIRST; if it
   fails, stop.
2. Closed bars only; a decision at bar i reads nothing after bar i; fills at bar
   i+1's open or later. The sizing input must come from data available at the
   DECISION bar — using the volatility that actually occurred during the trade
   is look-ahead and would produce a spectacular, fake result.
3. First touch; TIES LOSE.
4. Per-symbol costs from study.COSTS on both sides, and commission converted to
   price units the way engine.backtest does at its `comm_px` line.
5. Chronological IS/OOS 70/30 via split(). Fit any scaling constant on IS only.
   OOS RUN ONCE. If you re-run it after a change, the run is dead — say so
   rather than hiding it.
6. Every t against t ~= 3.65. Report markets-held out of 8; 4 of 8 is a coin
   flip. Note that with a zero directional edge the mean is near zero by
   construction, so the claim under test is about VARIANCE and DRAWDOWN, and you
   must state which statistic you are testing in every table.
7. Never report a number you did not compute.

VERDICT VOCABULARY — these words and no others: CONFIRMED · SUPPORTED ·
PROMISING · UNPROVEN · REJECTED · DISPROVEN. "PROMISING" is not "profitable".
And note the honest ceiling on this whole experiment: better sizing cannot turn
a negative expectancy positive. It can only reduce the variance around whatever
expectancy exists. Say that in the write-up so nobody reads a drawdown
improvement as an edge.

A CLEAR NEGATIVE IS A COMPLETE SUCCESS. "ATR(14) is already an adequate
volatility estimate at this holding period, and lot quantisation erases the
difference below N equity" closes an action item and is a genuinely useful
answer. Do not hunt for the parameter cell that saves it.

DELIVERABLE
- Script: /home/user/signals/JARVIS/research/vol_sizing.py, docstring stating
  the question, the two traps above, what it reuses from pointscale.py and
  small_account.py, and the run command.
- Finding: APPEND to /home/user/signals/JARVIS/state/EXPERIMENTS.md as E-044.
  Append only — read the last 40 lines, append at the end, never rewrite; if
  E-044 is taken use the next free number and note it. Lead with the money-risk
  dispersion gate, then growth/drawdown, then the lot-quantisation threshold.
- Commit only your own files, on branch claude/jarvis-ai-operating-system-2xaclm.
- Final message: the question, whether the two rules differed at all, the
  equity threshold above which sizing becomes a real choice, the verdict word,
  and the one sentence you want the next session to read.
```

---
---

# A6 — M1 READINESS AND PRE-REGISTRATION  (agent type: general-purpose · E-045)

**Objective in one line:** make the M1 branch executable and un-p-hackable the
moment Veer's export lands — a data-integrity harness that can tell real
tick-derived M1 from smoothed vendor fill, plus the M1 hypothesis written down
and committed BEFORE the data exists.

**Good result:** an integrity checker that fails loudly on synthetic bad data
(gaps, duplicate timestamps, wrong timezone, weekend bars, smoothed prices), a
pre-registered M1 test plan with its threshold fixed in advance, and a
validation gate that checks THE DATA rather than the code — bid-ask bounce must
appear at M1 or the export is not what it claims to be.
**Bad result:** a wrapper around the existing export script; a plan that says
"run study.py GOLD 1m and see"; anything that requires fetching data (every
provider is 403 here and that is a policy denial, not a glitch).

```
You are a research agent on PROJECT TITAN, in the repo /home/user/signals. Work
only from evidence you compute yourself.

POSITION — read this, it is the whole reason your task exists.
About 780 directional configurations have been tested here and none has cleared
the significance bar. E-037: Lo-MacKinlay variance ratios, 40 tests, not one
significant, largest |z| 1.79 — these series are statistically random walks at
15m and 1h. The live chart agrees (LIVE_EVIDENCE.md: 12 real trades on XAUUSD
3m, 33% win, -0.58R, TP 0, SL 8). E-038 found the one predictable quantity,
volatility, in 8 of 8 series. E-039 and E-041 then established that filtering
cannot convert it: a filter moves a zero-edge entry toward zero and never past
it. E-040 measured the cost floor and found GOLD is the instrument (8.0x / 9.7x
median one-bar move per round trip) and FX at short holds is retired (EURUSD 15m
0.8x — the median bar does not cover its own spread).
E-037 states its own two limits explicitly, and one of them is yours: "It is 15m
and 1h. M1 is untested and is genuinely different in kind — bid-ask bounce and
order-flow effects produce real autocorrelation at very short horizons. This is
now the strongest argument in the repo for getting M1 data, because it is the
one place a directional edge could still be hiding."
E-040 sharpened it: extrapolating range as sqrt(time) — justified here precisely
because E-037 found random-walk behaviour — a 1-minute gold hold has about 2.1x
the round-trip cost to work with, 3.6x at 3 minutes, 8.0x at 15 minutes. That is
EXTRAPOLATED, NOT MEASURED, and it stops being an extrapolation the moment the
export arrives.

YOU ARE NOT GETTING THE DATA. THAT IS THE POINT.
KNOWN_LIMITATIONS.md records that ALL market-data providers are blocked by the
organisation's egress policy in this container — Yahoo, Stooq, AlphaVantage,
Tiingo and Nasdaq Data Link all return 403 at the proxy. Do not attempt any of
them and do not retry: it is a policy denial, not a transient failure. There is
no MT5 here either. The M1 data can only come from Veer running
JARVIS/tools/export_mt5_data.py on his Windows PC.
Your job is to make sure that when it arrives, it is (a) verified before it is
believed and (b) tested against a hypothesis that was written down first.

READ BEFORE YOU WRITE CODE (absolute paths):
  /home/user/signals/JARVIS/titan/MISSION.md
  /home/user/signals/JARVIS/titan/HYPOTHESIS_TREE.md
  /home/user/signals/JARVIS/state/EXPERIMENTS.md   (E-001..E-041; read E-037,
      E-038, E-040 in full — E-040 contains the implied-M1 table you are
      preparing to falsify or confirm)
  /home/user/signals/JARVIS/state/FAILURE_LOG.md   (F-005..F-008 and L-009,
      L-010 are directly about tools that reported success while being wrong —
      that is the failure mode you are building against)
  /home/user/signals/JARVIS/state/KNOWN_LIMITATIONS.md
  /home/user/signals/JARVIS/tools/GET_M1_DATA.md
  /home/user/signals/JARVIS/tools/export_mt5_data.py

CODE YOU MUST USE — do not rewrite what exists.
/home/user/signals/JARVIS/research/engine.py
    load(symbol, tf) — note it already sorts by timestamp and DROPS exact
      duplicate timestamps silently. That silent drop is a data-quality event
      your checker must SURFACE, because a vendor repeating bars is a symptom.
    Series, atr, true_range, Costs(spread, slippage, commission_per_lot,
      value_per_point_per_lot)
/home/user/signals/JARVIS/research/study.py — COSTS, the per-symbol dict. The
    export script reads the broker's REAL spread and commission; your harness
    must produce the exact COSTS entry to paste in, and must flag how far the
    real numbers are from the current assumptions (GOLD spread 0.30,
    commission 7.0/lot, value_per_point_per_lot 100.0). E-033 is the precedent
    for what wrong costs do to results.
/home/user/signals/JARVIS/research/is_it_tradeable.py — variance_ratio(r, q),
    autocorr(r, lag), cost_in_sigma(sym, s, r), selftest(). These are the exact
    statistics the M1 test will run; do not rewrite them, wire them up.
/home/user/signals/JARVIS/research/vol_predictability.py — logret, ac, selftest.
/home/user/signals/JARVIS/research/cost_floor.py — E-040's script. Your harness
    must be able to re-run it on M1 and replace the extrapolated table with a
    measured one.
/home/user/signals/JARVIS/tools/check_pine.py and verify_fixes.py — read them as
    the house style for a checker: every rule regression-tested against a file
    that actually contains the fault it is meant to catch. F-006, F-007 and
    F-008 are three consecutive cases of a checker that passed a broken file
    because its rule encoded one remembered EXAMPLE instead of the RULE. Do not
    make that mistake a fourth time.
Local `split(s, frac=0.70)` — copy from reachability.py; no shared helper exists.

DELIVERABLE ONE — the integrity harness.
Write /home/user/signals/JARVIS/tools/check_data.py which takes a candle JSON
and reports, with a non-zero exit on failure:
  - bar count, first and last timestamp, and the implied calendar span;
  - GAPS: the distribution of inter-bar intervals against the nominal one, with
    weekend and session breaks classified separately from true holes. On M1 gold
    a missing hour inside a trading session is a data defect; a 48-hour weekend
    is not;
  - DUPLICATES: exact-duplicate timestamps, and near-duplicates (identical OHLC
    on consecutive bars), which is the fingerprint of a vendor forward-filling;
  - TIMEZONE AND DST: the bar-count histogram by UTC hour. A broker server on
    EET/EEST will shift the session by an hour across DST boundaries, and every
    hour-of-day result computed on it would be wrong in a way that looks
    entirely plausible. Detect the shift and report it rather than assuming;
  - OHLC SANITY: high >= max(open, close), low <= min(open, close), no zero or
    negative prices, no bars whose range is zero for long runs (a flatline is a
    feed outage, not a quiet market);
  - PRICE GRANULARITY: the smallest non-zero price increment actually observed,
    compared with the instrument's tick size. If M1 prices are quantised more
    coarsely than the tick size, the data has been smoothed or resampled from a
    higher timeframe, and every microstructure conclusion drawn from it would be
    an artefact of the vendor.

DELIVERABLE TWO — the validation gate, which tests THE DATA, not the code.
This is the most valuable single idea in your brief, so implement it carefully.
Genuine M1 data from a real feed MUST show microstructure noise: bid-ask bounce
produces NEGATIVE lag-1 autocorrelation in returns at very short horizons. That
is not a hopeful hypothesis, it is a mechanical consequence of trades
alternating between the bid and the ask, and it is one of the most reliably
documented facts in market microstructure.
  - If the M1 data shows it, the data is real and the M1 branch can be tested.
  - If the M1 data shows NOTHING — lag-1 autocorrelation indistinguishable from
    zero, exactly like the 15m and 1h series in E-037 — then either the feed is
    mid-price rather than traded price (bid-ask bounce does not appear in a
    mid-price series, and this is the likeliest benign explanation and must be
    checked FIRST), or the bars were interpolated. Either way the "M1 is
    different in kind" argument does not survive contact with THIS data, and
    that is itself a headline result: it would close the last branch on which a
    directional edge was still plausible in this project.
Write the gate so it produces one of those three verdicts explicitly. Do not let
it return a vague pass.

DELIVERABLE THREE — the pre-registration, committed BEFORE the data exists.
Write /home/user/signals/JARVIS/titan/M1_TEST_PLAN.md stating, in advance:
  - the exact hypotheses to be tested on M1, in order, with the statistic for
    each (start from: lag-1 to lag-10 autocorrelation of returns; variance ratio
    at q = 2, 4, 8, 16, 32; absolute-return autocorrelation as the E-038
    replication; and cost_in_sigma / cost_floor to REPLACE E-040's extrapolated
    implied-M1 table with a measured one);
  - the number of tests K and therefore the correction, and the significance
    threshold, FIXED NOW. The project threshold is t ~= 3.65 for ~780 tests;
    state whether M1 tests inherit it and justify the answer either way;
  - the IS/OOS split and the rule that OOS runs ONCE;
  - what result would DISPROVE the M1 hypothesis, written as plainly as what
    would support it;
  - and the note that E-023 (intraday momentum) becomes testable at M5/M15 and
    should be re-run then — it is currently UNTESTABLE, not disproven, and the
    plan must not let anyone forget which of those two it is.
A hypothesis written after seeing the data is not a hypothesis. This file is the
mechanism that stops that, and it is worth more than the code.

SELF-TEST BEFORE ANYTHING IS TRUSTED — mandatory, printed, exit non-zero on
failure. Every check above must be regression-tested against SYNTHETIC data that
actually contains the fault:
  - a series with an injected mid-session gap — the gap check must find it and
    must NOT flag the weekend;
  - a series with duplicated and forward-filled bars — both must be reported;
  - a series shifted by one hour halfway through — the DST check must find it;
  - a series with high < close — the OHLC check must fail it;
  - a synthetic series WITH bid-ask bounce (alternate a half-spread on each
    return) — the validation gate must report clear negative lag-1
    autocorrelation, at approximately the analytic value for the spread you
    injected;
  - the SAME series without bounce — the gate must report absence.
And a clean, correct series must pass everything. A checker that only ever says
"fail" is as useless as one that only ever says "pass"; L-009 in FAILURE_LOG is
exactly this lesson and it has already cost this project five commits of
non-compiling shipped code.

NON-NEGOTIABLE METHOD RULES
1. `python3 /home/user/signals/JARVIS/research/test_engine.py` FIRST; if it
   fails, stop.
2. Do not fetch data. Do not retry blocked hosts. Do not fabricate an M1 file
   and present its output as a result — synthetic data is for testing the
   harness and must be labelled as such in every line of output it produces.
3. Per-symbol costs from study.COSTS; the bare engine.Costs() default is
   GOLD-shaped and charging it to another instrument is E-033.
4. Report every t against t ~= 3.65 and state the correction you applied.
5. Never report a number you did not compute. Label clearly which numbers in
   your write-up are MEASURED and which are EXTRAPOLATED — E-040 did this
   correctly for its implied-M1 table and you must match that standard.
6. A static checker reporting CLEAN is evidence that the specific things it
   models are absent, NOT evidence that the data is good. Say so in the tool's
   own output. This is L-009, verbatim, and it is in the failure log because
   ignoring it shipped five broken files.

VERDICT VOCABULARY — these words and no others: CONFIRMED · SUPPORTED ·
PROMISING · UNPROVEN · REJECTED · DISPROVEN.

A CLEAR NEGATIVE IS A COMPLETE SUCCESS. If your honest conclusion is that the
export cannot deliver what the M1 hypothesis needs — for example because the
broker only serves mid-price bars, so bid-ask bounce can never appear — then
saying so now, before Veer spends an evening on it, is worth more than any
harness.

DELIVERABLE SUMMARY AND COMMIT
- /home/user/signals/JARVIS/tools/check_data.py (harness + regression tests)
- /home/user/signals/JARVIS/titan/M1_TEST_PLAN.md (the pre-registration)
- Finding: APPEND to /home/user/signals/JARVIS/state/EXPERIMENTS.md as E-045 —
  check the file for the next free number first, take it, and note if the
  assignment moved. Append only: read the last 40 lines and append at the end,
  never rewrite; another agent may be appending concurrently. Record what the
  harness checks, what it CANNOT check, and the pre-registered thresholds.
- Update /home/user/signals/JARVIS/tools/GET_M1_DATA.md with the one extra
  instruction the harness needs from Veer, if any, keeping it to the same short,
  plain-English, three-minute shape it has now. Do not lengthen it.
- Commit only your own files, on branch claude/jarvis-ai-operating-system-2xaclm.
- Final message: what the harness catches, the three verdicts the validation
  gate can return, and the one sentence you want the next session to read.
```

---
---

# A7 — HOW MANY LIVE TRADES SETTLE IT  (agent type: general-purpose · E-046)

**Objective in one line:** MISSION.md says the live scoreboard — which setup
types Veer personally converts — is "the only live question with a real chance
of a positive answer"; compute how many live trades are actually needed to
answer it, and the sequential rule that stops early without inflating the false
positive rate.

**Good result:** a hard number of trades per setup type for a stated detectable
effect size, computed from the observed R distribution rather than assumed; a
sequential test with its error rates simulated, not quoted; and an honest
statement of how many weeks that is at the observed trade rate.
**Bad result:** a textbook power formula applied to a win rate with no reference
to this project's R distribution or its multiple-testing history; a protocol
that would let 12 trades mean something.

```
You are a research agent on PROJECT TITAN, in the repo /home/user/signals. Work
only from evidence you compute yourself. This task is a STATISTICS AND DESIGN
task, not a backtest — but every number in it must still be computed.

POSITION — read this, it is the whole reason your task exists.
About 780 directional configurations have been tested in this project and none
has cleared the significance bar. E-037: 40 variance-ratio tests, not one
significant. E-038: volatility is predictable in 8 of 8 series — the project's
only CONFIRMED finding. E-039 and E-041: filtering cannot convert it; a filter
moves a zero-edge entry toward zero and never past it. E-040: GOLD is the only
instrument with real room (8.0x / 9.7x median one-bar move per round trip);
FX at short holds is retired.
JARVIS/state/LIVE_EVIDENCE.md is the only out-of-repo measurement either system
has: SuperTrend Sniper on XAUUSD 3m, last 12 trades — 33% win, -6.9R total,
-0.58R average, take-profits 0, stop-losses 8, and only 25% of trades ever
touched 1R. It also records that the Liquidity Sniper was producing ~120 signals
a day, which is a noise generator rather than a signal generator (lesson L-011).
MISSION.md's closing paragraph is your brief: "The scoreboard in the liquidity
Pine exists to find out which setup types Veer personally converts, and that
remains the only live question with a real chance of a positive answer."
Nobody has computed what it would take to answer it.

THE QUESTION, framed so "no" is as publishable as "yes":
How many LIVE trades, per setup type, are required before Veer's per-setup
conversion rate can be distinguished from chance at this project's evidential
standard — and given his observed trade rate, how long is that in calendar time?
If the honest answer is "more trades than he will place in a year", that is a
COMPLETE and decision-changing result: it would mean the live scoreboard cannot
settle the question as designed, and the design must change (fewer setup types,
a pooled test, or a different question entirely).

WHY THIS IS THE HIGHEST-VALUE DESIGN TASK LEFT.
Twelve trades were used to form a judgement about a strategy. Twelve trades
cannot distinguish -0.58R from 0.00R at any useful confidence, and the same
error is about to be repeated across eight setup types at once — which is eight
simultaneous tests on a handful of samples each. Getting the required n on paper
BEFORE the data is collected is the only way that scoreboard produces knowledge
instead of another confident wrong answer.

READ BEFORE YOU WRITE CODE (absolute paths):
  /home/user/signals/JARVIS/titan/MISSION.md
  /home/user/signals/JARVIS/state/LIVE_EVIDENCE.md
  /home/user/signals/JARVIS/state/EXPERIMENTS.md    (E-024, E-025, E-027,
      E-031, E-035, E-036, E-041 — the setup-type work and what it measured)
  /home/user/signals/JARVIS/state/FAILURE_LOG.md    (L-011 on the signal flood)
  /home/user/signals/JARVIS/state/DECISIONS.md      (D-006 no live action
      without per-session confirmation; D-007 which strategy is on which
      account; D-008 the broker and the 0.01-lot constraint)
  /home/user/signals/JARVIS/state/KNOWN_LIMITATIONS.md

CODE AND DATA YOU MUST USE — do not rewrite what exists.
/home/user/signals/JARVIS/research/engine.py
    load, Series, backtest(s, signal_fn, costs, ...), stats(trades) — which
      already returns n, win_rate, expectancy_R, sd_R and t_stat; sd_R is the
      quantity your power calculation needs and it must come from measured
      trades, not from an assumption
    monte_carlo(trades, trials=20000, risk_pct, seed) — the bootstrap you should
      extend rather than replace
/home/user/signals/JARVIS/research/study.py — COSTS per symbol; engine.Costs()'s
    default is GOLD-shaped and charging it elsewhere is E-033
/home/user/signals/JARVIS/research/strategies.py — supertrend_dir(s, 7, 1.2)
    (Pine convention: d == -1 BULLISH, +1 BEARISH), supertrend_sniper(...)
/home/user/signals/JARVIS/research/smc_setups.py — the seven setup types
    implemented as the Pine implements them (make_fvg, make_ob, make_pullback,
    make_breakout, make_discount, plus swings/structure), and E-031's per-setup
    results. This is where you get the realistic per-setup trade FREQUENCY and R
    dispersion from.
/home/user/signals/JARVIS/research/entry_quality.py — heat(), limit_test(), and
    E-035's measurement that 71.7% of signals retrace through the entry within
    three bars. Relevant because it bounds how much execution variance sits on
    top of the setup's own variance.
/home/user/signals/JARVIS/pine/LiquiditySniper_v1.pine — the scoreboard whose
    design you are evaluating. Read what it currently records per setup type.
Local `split(s, frac=0.70)` — copy from reachability.py; no shared helper exists.

METHOD
1. ESTIMATE THE NUISANCE PARAMETER FROM DATA, NOT FROM A TEXTBOOK. The required
   sample size depends on the standard deviation of per-trade R. Compute sd_R
   per setup type from the backtested trade populations (smc_setups.py, E-031)
   AND from the 12 live trades, and report both — if they disagree materially,
   the live one wins, because LIVE_EVIDENCE.md outranks backtests in this
   project, and say how wide the error bar on 12 observations is.
2. POWER CURVE. For each setup type, compute the number of trades n required to
   detect a true expectancy of +0.10R, +0.25R and +0.50R at 80% power, at three
   thresholds: an uncorrected t = 2.0, a Bonferroni correction for the number of
   setup types being scored simultaneously, and this project's t ~= 3.65. Give
   the whole grid. The comparison between the three columns IS the finding.
3. VERIFY THE POWER CALCULATION BY SIMULATION, not by formula alone. Bootstrap
   from the measured R distribution — which is skewed and fat-tailed, so the
   normal approximation understates the required n — and confirm the empirical
   rejection rate at your chosen n matches the nominal power. Report both the
   analytic and simulated n. Where they differ, the simulated one is the answer.
4. CALENDAR TIME. Using the measured signal frequency per setup type, convert n
   into weeks and months at Veer's actual trading rate. State it in weeks. That
   single number is the most useful thing in this experiment.
5. SEQUENTIAL RULE. Design a stopping rule that can abandon a setup type early
   when it is clearly bad, without inflating the false-positive rate — a
   sequential probability ratio test or an alpha-spending boundary is the
   natural fit. SIMULATE its actual error rates under a null of zero expectancy
   and under the alternatives from step 2. Do not quote a textbook boundary;
   measure the one you propose. An early-stop rule that is not simulated is a
   guess with a Greek letter on it.
6. THE DESIGN VERDICT. Given the numbers, answer directly: can the scoreboard as
   currently designed — eight setup types scored in parallel — ever answer the
   question? If not, say what would: fewer types, pooling, a longer horizon, or
   a different question. Be concrete and be willing to say the design must
   change.
7. THE LOGGING SCHEMA. Specify exactly what must be recorded per live trade for
   this analysis to be possible at all: setup type, timestamp, side, entry,
   stop, target, exit, exit reason, MFE and MAE in R, slippage against the
   signalled price, and whether it was taken manually or by the EA. If a field
   is not recorded it does not exist, and the analysis is not recoverable later.

WHAT HAS ALREADY BEEN DONE — do not repeat it:
- E-031 measured all seven setup types on history, one at a time, best OOS
  t +1.35 against a threshold of about 3.65 — all UNPROVEN. You are not
  re-measuring them on history; you are computing what it takes to measure them
  LIVE.
- E-036 established that history cannot rank these setups, which is exactly why
  the ranking has to come from Veer's own results. That is the premise of your
  task, not a thing to re-test.
- E-025, E-026, E-027, E-035 measured bounce setups, HTF confluence, trade
  frequency and entry quality. Use their numbers as inputs; do not re-derive.
- E-029 and E-030 disproved the GBP60/day arithmetic. Do not re-derive profit
  targets.
- E-041 closed the filtering class. Do not propose a filter.

SELF-TEST BEFORE ANY REAL NUMBER — mandatory, printed, exit non-zero on failure.
  (a) POSITIVE CONTROL: simulate a setup type with a TRUE expectancy of +0.25R
      and the measured sd_R. At your computed n, your test must reject the null
      approximately 80% of the time. If it does not, your power calculation is
      wrong and every n in your table is wrong with it.
  (b) NEGATIVE CONTROL: simulate a true expectancy of exactly zero. Your test
      must reject at approximately the nominal alpha and no more — run this at
      the number of setup types being scored in parallel and confirm the
      family-wise error rate is what your correction claims.
  (c) SEQUENTIAL CONTROL: run the stopping rule over many simulated paths under
      the null and confirm the realised false-positive rate matches its design.
      Peeking at accumulating data without a boundary inflates alpha badly, and
      demonstrating the size of that inflation on your own simulation is a
      persuasive line for the write-up.
Rationale: this project's headline near-miss (E-023, GOLD IS t +2.71, OOS
-0.022) is exactly what happens when a threshold is trusted without checking
what the procedure actually does.

NON-NEGOTIABLE METHOD RULES
1. `python3 /home/user/signals/JARVIS/research/test_engine.py` FIRST; if it
   fails, stop.
2. Closed bars only, next-bar fills, first touch, TIES LOSE, per-symbol costs
   from study.COSTS — for any backtested population you use to estimate sd_R or
   trade frequency. An sd_R estimated from a cost-free backtest is the wrong
   number.
3. Chronological IS/OOS via split() for anything estimated from history; OOS
   runs ONCE.
4. Report against t ~= 3.65 as well as the uncorrected threshold, and make the
   difference between them explicit in trades-required terms. "Correcting for
   multiple testing costs you N extra trades per setup type" is the sentence
   that will actually change behaviour.
5. Never report a number you did not compute. No assumed win rates. The 12 live
   trades are the only live data that exists; treat their small n as a headline
   caveat, not a footnote.
6. NOTHING IN YOUR OUTPUT AUTHORISES A LIVE TRADE. D-006: no live action without
   Veer confirming that specific action in that session. You are designing a
   measurement, not instructing anyone to place orders, and the write-up must
   say so.

VERDICT VOCABULARY — these words and no others: CONFIRMED · SUPPORTED ·
PROMISING · UNPROVEN · REJECTED · DISPROVEN.

A CLEAR NEGATIVE IS A COMPLETE SUCCESS. "The live scoreboard as designed cannot
answer this question inside a year, and here is the arithmetic" is a genuinely
valuable result — it prevents months of collecting data that could never have
settled anything, which is the single most expensive failure mode still
available to this project.

DELIVERABLE
- Script: /home/user/signals/JARVIS/research/live_power.py, docstring stating
  the question, the estimated sd_R and where it came from, and the run command.
- Finding: APPEND to /home/user/signals/JARVIS/state/EXPERIMENTS.md as E-046 —
  check for the next free number first and note it if the assignment moved.
  Append only: read the last 40 lines, append at the end, never rewrite the
  file. Lead with the trades-required table and the calendar-time number.
- A short protocol section, plain English, that Veer can follow: what to log,
  how many trades before anyone is allowed to draw a conclusion, and the
  stopping rule. Keep it to one screen. If it is longer than one screen it will
  not be used.
- Commit only your own files, on branch claude/jarvis-ai-operating-system-2xaclm.
- Final message: trades required per setup type at the project threshold, the
  calendar time that implies, whether the current design can work, the verdict
  word, and the one sentence you want the next session to read.
```

---

## Branches deliberately NOT briefed, and why

- **Another entry pattern, confluence score, filter or parameter sweep.** Closed
  by E-030, E-036, E-037, E-039 and now decisively by E-041: a filter improves a
  zero-edge entry toward zero and never past it. An agent sent there would be
  configuration 782.
- **FX at short holds.** Retired by E-040 — the median EURUSD 15m bar is 0.8x
  its own round-trip cost. It stays in every test as a control that should fail,
  never as a market to rescue.
- **Re-running E-023 intraday momentum on 1h data.** Diagnosed as a granularity
  problem; status UNTESTABLE, not disproven. It waits on M5/M15, which is why it
  is written into A6's pre-registration rather than briefed as its own agent.
- **Fetching data of any kind.** Every provider returns 403 at the proxy by
  organisation policy (KNOWN_LIMITATIONS.md). Briefing an agent to do it would
  burn a run on a policy denial. The M1 request goes to Veer; A6 prepares for it.

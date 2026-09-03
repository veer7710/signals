# PROJECT SNIPER — THE MASTER PROMPT
### A multi-session build order. Load this at the start of every session until it is finished.

---

## 0. WHAT THIS IS

This is not a description of a goal. It is a **work order with 112 numbered
phases**, a ledger that records which are done, and a set of gates that decide
whether a phase counts as done. It exists so that a session which has never
seen this project can open it, read the ledger, and continue mid-stride.

**The deliverable, by Saturday 2026-09-05:**

| # | artefact | for | must satisfy |
|---|---|---|---|
| 1 | `SuperTrendSniper.mq5` | Veer's live PU Prime account, **starting at £40** | grows 0.01 → 0.03 by the ladder in Phase 4, survives Phase 6 ruin test |
| 2 | `LiquiditySniper.mq5` | funded accounts **and** live | one input block re-sizes it for any account, Phase 5 |
| 3 | `XAUUSD_CLEAN.pine` | reading the SuperTrend trade by eye | chart matches Veer's own 3.5 spec exactly |
| 4 | `LIQUIDITY_CLEAN.pine` | reading the liquidity trade by eye | signals identical to the EA's, provably |

**XAUUSD only. M1, M5, M15 only.** H1/H4 are context and are never traded.

---

## 1. THE LAWS

These outrank every phase below. A phase that requires breaking one of these is
wrong and gets rewritten, not executed.

1. **Never claim a strategy is profitable.** The vocabulary is CONFIRMED /
   SUPPORTED / PROMISING / UNPROVEN / REJECTED / DISPROVEN and nothing else.
2. **Never report a number that was not computed.** Paste the output.
3. **Ties lose.** If a bar's range holds both the stop and the target, it is a
   loss. OHLC cannot say which came first.
4. **Every claim needs a matched random control**, and the control needs ≥12
   seeds. A single-seed control has its own sampling error.
5. **Count the right unit.** Bars are not trades. E-073 destroyed the project's
   most-cited result because it counted 61 bars of one trade as 61 facts.
   *Any result whose n far exceeds the number of independent decisions behind
   it is wrong until re-counted.*
6. **Expectancy is not money.** E-074: the best per-trade gate set banked the
   least. Every comparison reports **points**, not only R.
7. **Nothing touches the live account** without Veer confirming that specific
   action in that session.
8. **No secrets in the repo.**
9. **A filter earns its place only if the trades it REFUSES are worse than the
   ones it allows.** Otherwise it is a cost with no benefit.
10. **Run `test_engine.py`, `check_mq5.py` and `check_pine.py` before shipping
    anything.** Four non-compiling Pines have already been shipped.

---

## 2. THE GOVERNING CONSTRAINT  (E-081, already measured)

0.01 lots of XAUUSD is **£0.787 per point** and cannot be made smaller.
Therefore the account does not choose its risk — **the timeframe does**:

| timeframe | 0.60 ATR stop | risk on 0.01 | as % of £40 |
|---|---|---|---|
| 1h | 8.61 pts | £6.78 | **17.0%** |
| 15m | 5.05 pts | £3.98 | **10.0%** |
| M5 (est) | 2.92 pts | £2.30 | 5.7% |
| **M1 (est)** | **1.31 pts** | **£1.03** | **2.6%** |

**A £40 account must trade M1.** Not as a preference — as the only timeframe
where the smallest position the broker allows is a survivable bet. Every phase
below inherits this.

---

## 3. THE PHASES

Status lives in `JARVIS/state/PHASE_LEDGER.md`. A phase is DONE only when its
**gate** passes. A phase that fails its gate is not skipped — it is reworked,
or explicitly marked BLOCKED with the reason and what would unblock it.

### BLOCK A — DATA. Nothing downstream is real without this. (P1–P8)
- **P1** Get M1/M5/M15 XAUUSD into `data/`. `ExportHistory.mq5` is written and
  has never been run. If Veer cannot run it, find another route: MT5 Python
  API, a broker CSV export, a public dataset. **Do not accept "blocked".**
- **P2** Validate the import: bar counts, gaps, duplicate timestamps, weekend
  bars, session boundaries. A silent data bug invalidates every phase after it.
- **P3** Measure the real M1 ATR distribution by hour of day. The £1.03 risk
  figure above is a square-root-of-time *estimate* and Block C depends on it.
- **P4** Measure the real M1 spread by hour, from the EA's journal if possible.
  A 0.60 ATR stop on M1 is ~1.3 points; a 0.46 spread is a **third** of it.
- **P5** Re-run E-069, E-077 and E-080 on M1. Every headline is currently a
  1h/15m result being applied to an M1 EA.
- **P6** Re-run on M5 and M15. Three timeframes, one table.
- **P7** Build a walk-forward harness that never fits and tests on the same
  window, and re-run every surviving result through it.
- **P8** Cross-check M1 results against 15m: an edge that exists on one and not
  the other is a timeframe artefact and must be explained, not shipped.
- **Gate A:** every headline number in the repo is measured on the timeframe it
  will be traded on.

### BLOCK B — ENTRY. (P9–P26)
- **P9** Re-verify E-076 on M1: does the top-tick limit still beat the retest?
- **P10** Sweep the entry offset (`InpEntryPast`) on M1: −0.5 to +0.5 ATR.
- **P11** Does the zone's *age* predict? A level born 5 bars ago vs 500.
- **P12** Does the number of pivots in a zone predict? (E-068 said 3 kills the
  frequency; does 2 beat 1 on *quality* per trade?)
- **P13** Does zone *width* predict? Tight clusters vs loose ones.
- **P14** First touch vs second touch vs third of the same level.
- **P15** FVG size: does a bigger gap pay better? Sweep `InpMinGapAtr`.
- **P16** FVG age at fill.
- **P17** Order block: body-only vs body+wick as the zone.
- **P18** Order block: displacement threshold sweep, 0.5–2.0 ATR.
- **P19** Confluence: FVG *inside* a liquidity zone — is the overlap better
  than either alone? (Test as a *scoring* rank, not a filter — Law 9.)
- **P20** Session: does the London/NY open change entry quality on M1?
- **P21** The first N minutes after a session open, specifically.
- **P22** News-time behaviour: can it be detected from spread alone?
- **P23** Round numbers (2600.00, 2650.00) as levels in their own right.
- **P24** Previous day/week high and low as levels.
- **P25** Re-test every rejected SMC idea (iFVG, BOS, CHoCH) **on M1** — they
  were rejected on 1h and the timeframe may be why.
- **P26** Entry portfolio: which combination of sources maximises **points**,
  not expectancy, with one position at a time.
- **Gate B:** the entry stack beats its 30-seed control by ≥3 sd on M1, walk-
  forward ≥5/6, and fires often enough for Veer's trade count.

### BLOCK C — EXIT. This is where the money is lost. (P27–P50)
- **P27** Re-run the E-071 stop/target grid on M1.
- **P28** Re-run the E-075 exit-policy comparison on M1.
- **P29** Give-back arming level swept on M1 (E-075 found it monotone on 1h).
- **P30** Trail distance swept on M1.
- **P31** Trail *armed at* swept.
- **P32** Break-even: re-test on M1. It has failed four times on other data;
  five is not redundant if the timeframe is the variable.
- **P33** Partial exits: 0.02 as two 0.01s, every split from 0/100 to 100/0.
- **P34** Partial + trail on the remainder.
- **P35** Partial + give-back on the remainder.
- **P36** Time stops: is there an M1 bar count after which a trade is dead?
- **P37** Exit on an opposing signal (a sweep the other way).
- **P38** Exit on structure (close beyond the last swing).
- **P39** MFE/MAE study on M1: how much of the move is reachable at all?
- **P40** The ORACLE gap: what % of the perfect exit does each rule capture?
- **P41** Does the best exit differ by session?
- **P42** Does the best exit differ by ATR regime?
- **P43** Does the best exit differ by entry source (zone vs FVG vs OB)?
- **P44** Cost sensitivity of every surviving exit.
- **P45** Slippage sensitivity: what happens at 1, 2, 5 points of slippage?
- **P46** Weekend/rollover gap exposure.
- **P47** Re-entry after a stop: does the same level pay twice?
- **P48** Re-entry after a target: how soon is too soon?
- **P49** The scale-add rule Veer wants: add on what, sized how, stopped where?
- **P50** Scale-add vs one bigger position — the honest comparison.
- **Gate C:** the chosen exit beats a fixed 2R target on **points** on M1, and
  the choice is stable across at least two of {session, regime, entry source}.

### BLOCK D — MARKET CONDITIONS. (P51–P66)
- **P51** Classify every M1 bar into a regime (trend/chop/expansion/contraction)
  using only past data.
- **P52** Strategy performance by regime. Where does it lose?
- **P53** Can the losing regime be detected *in advance*? (Law 9 applies.)
- **P54** Sideways: the specific failure Veer named. Measure it, then fix it.
- **P55** Fast trend: does the top-tick entry get run over?
- **P56** Session open dumps and spikes — Veer named these explicitly.
- **P57** Asian session: is it tradeable at all on M1, or is it cost?
- **P58** London open.
- **P59** New York open, and the London/NY overlap.
- **P60** Friday close and Sunday open.
- **P61** High-impact news: measured by spread widening, not by a calendar.
- **P62** Volatility clustering: does a big bar predict the next one?
- **P63** Day-of-week effects, with the multiple-testing arithmetic stated.
- **P64** Month/seasonality — expected to be noise, tested so it can be closed.
- **P65** Correlation with DXY/US500 if data can be obtained.
- **P66** A single "market state" readout the EA can print on the chart.
- **Gate D:** the EA's behaviour in each regime is *documented and intended*,
  not incidental.

### BLOCK E — THE LIVE £40 ACCOUNT. (P67–P78)
- **P67** Ruin analysis on the **M1-measured** edge (E-081 used the 1h one).
- **P68** The lot ladder: 0.01 to £100, then 0.01–0.03. Exact thresholds,
  measured against ruin, not chosen.
- **P69** Does scaling up at £100 change the ruin profile materially?
- **P70** Maximum consecutive losses in the measured distribution, and the
  balance that survives it.
- **P71** Daily loss limit, set from the measured daily P/L distribution.
- **P72** Maximum drawdown lock, same method.
- **P73** Recovery behaviour: after a locked day, what re-arms it and when?
- **P74** Margin: what balance cannot open a 0.01 lot at 1:500?
- **P75** The compounding schedule — and whether compounding *helps* at this
  size or just raises ruin.
- **P76** A £40-specific input preset, shipped in the EA.
- **P77** Forward-test protocol: what Veer runs on demo, for how long, and what
  result would *stop* the live deployment.
- **P78** The kill-switch: what makes the EA turn itself off permanently.
- **Gate E:** ruin < 1% over 400 M1 trades on the M1-measured edge, or the
  ladder is changed until it is.

### BLOCK F — FUNDED ACCOUNTS. (P79–P90)
- **P79** Encode the actual rules: daily loss, max drawdown, profit target,
  minimum days, consistency rules.
- **P80** One input block that re-sizes everything for account size and rule set.
- **P81** Risk-per-trade as a % of the funded balance, not a fixed lot.
- **P82** Simulate a full challenge on the measured distribution: pass rate.
- **P83** Simulate the funded phase: payout rate and time to first payout.
- **P84** The consistency rule (no single day > X% of profit) — this kills most
  strategies that pass, and it must be simulated, not assumed.
- **P85** Trailing drawdown vs static — they are different strategies.
- **P86** How many attempts before a pass is likely, and what that costs.
- **P87** A "funded mode" that trades differently from live mode, if measured
  to be better.
- **P88** The high-win-rate variant: E-069's 87.8% shape has a place here even
  though it makes less money, *if* it passes challenges more reliably. Measure.
- **P89** Preset blocks for the common firm rule sets.
- **P90** A one-page card: which preset, for which firm, and why.
- **Gate F:** simulated pass rate reported with its confidence interval, and
  the consistency rule explicitly modelled.

### BLOCK G — THE CODE. (P91–P104)
- **P91** Parity harness: port each EA's logic to Python and prove it reproduces
  the backtest. **No EA ships without this.**
- **P92** Same for the Pines: the Pine's signals must match the EA's, bar for bar.
- **P93** Extend `check_mq5.py` with every rule that has ever bitten.
- **P94** Extend `check_pine.py` likewise.
- **P95** The position box: one implementation, timer-driven, on both EAs.
- **P96** Journal: every entry and exit, with spread, stop, cost/stop, peak, kept.
- **P97** A reader for that journal that compares live to backtest.
- **P98** Error handling: rejected orders, requotes, disconnects, partial fills.
- **P99** Restart safety: GlobalVariables, orphaned pendings, state recovery.
- **P100** Two EAs on one account: magic numbers, symbol locks, no interference.
- **P101** Strategy-tester run with real ticks, and what it says.
- **P102** Optimisation guardrails: what may be tuned and what may not.
- **P103** The chart: exactly what Veer's 3.5 spec allows, nothing else.
- **P104** Input documentation: every input's tooltip carries its measurement.
- **Gate G:** both EAs compile, pass parity, and produce a journal that can be
  compared to the backtest.

### BLOCK H — PROOF AND HANDOVER. (P105–P112)
- **P105** Re-run every experiment end to end from a clean checkout.
- **P106** A single results table: every strategy, every timeframe, one verdict.
- **P107** The adversarial pass: try to destroy the surviving strategy.
- **P108** The red team's findings, answered or accepted.
- **P109** Demo forward-test results vs backtest expectation.
- **P110** The go/no-go call for the live £40 account, with its condition.
- **P111** Update every state file so the next session starts cold and correct.
- **P112** The one-page operating manual: what to run, what to watch, what to do
  when it goes wrong.
- **Gate H:** a session with no memory of this project can read the repo and
  run the system correctly.

---

## 4. HOW A SESSION RUNS

1. Read `SESSION_STATE.md`, `NEXT_ACTIONS.md`, `DECISIONS.md`, `FAILURE_LOG.md`.
2. Read `PHASE_LEDGER.md`. Take the **lowest-numbered phase that is not DONE**.
3. Work it. Write the experiment as a file in `JARVIS/research/`, with the
   reasoning in its docstring — the docstring is the record, not the chat.
4. Run it. Paste the output. If it contradicts an earlier finding, the newer
   measurement wins and the older one gets corrected in `EXPERIMENTS.md`.
5. **Attack your own result before believing it.** Wrong control, wrong unit,
   look-ahead, a filter that never binds, an n that is bars not trades.
6. Update the ledger, `EXPERIMENTS.md`, and the state files. Commit and push.
7. If the phase produced a code change, run the checkers before committing.
8. Never end a session without a checkpoint.

**When a phase is blocked:** do not report the blockage and stop. Do every
phase that does not depend on it, then state the blockage in one line with the
single action that would clear it.

---

## 5. WHAT "DONE" MEANS FOR THE WHOLE THING

A money-making machine is not a backtest with a good number. It is:

- an edge measured **on the timeframe it will trade**,
- that beats a matched control by a margin larger than the control's own noise,
- that survives walk-forward and out-of-sample,
- whose **worst realistic run** the account can survive,
- implemented in code **proven to match** the thing that was measured,
- with a chart Veer can read and a box that tells him the truth,
- and an honest sentence about what would make it stop working.

Anything less is a number, not a machine.

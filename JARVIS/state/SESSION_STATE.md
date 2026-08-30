# Session state — checkpoint

**Session:** 2026-08-27/28 (sessions 1-2 merged)
**Branch:** `claude/jarvis-ai-operating-system-2xaclm`
**Model:** claude-opus-5

## What this session did
1. Inspected the environment and the whole repository before building.
2. Audited the pre-existing signal system against its own live trade log
   and **disproved its edge** (E-001).
3. Deleted the old project on Veer's instruction; kept `data/`.
4. Built a dependency-free backtest engine with anti-look-ahead structure,
   realistic costs, walk-forward, Monte Carlo, and cost sensitivity.
5. **Found and fixed a bug in my own walk-forward** (F-001) that was
   producing impossible 0% win rates, then wrote regression tests.
6. Ran the first real study on GOLD 1h — results in EXPERIMENTS.md.
7. Researched prop-firm multi-account rules (R-002) — found a hard
   constraint on the 40-account scaling plan.
8. Established this memory system, the resume script, and 6 agents.

## Where the work stopped
Foundation complete and committed. Strategy research has produced ONE
promising candidate (`donchian_trend`) that has not yet faced adversarial
review or out-of-sample testing on other symbols.

## What is NOT done
- No EA written (the source EA was never in the repo).
- No Pine script analysed (never supplied).
- Liquidity family barely explored — one implementation, one timeframe.
- No dashboard, voice, scheduler, or business engines.

## Do not repeat
- Do not re-audit the deleted signal system. It is DISPROVEN (E-001).
- Do not rebuild the capped-target design. Root cause CONFIRMED (E-002).
- Do not re-ask whether to evade usage limits. Settled (D-005).

---
# UPDATE — overnight research session (2026-08-28)

## What happened
Received the real EA (`XAUUSD_QUAD_v19_18.mq5`, 20,695 lines, 748 inputs) and
both Pine scripts. Audited them. Built an exit laboratory and a cross-market
robustness scan. Launched five deep-research agents.

## USAGE LIMIT HIT
All five research agents were killed by the account session limit (resets
01:40 UTC) before writing their findings. Their five topics are UNFINISHED and
are the first actions for the next session. Do NOT assume any of their results
exist — no findings files were written except `06_exit_experiment.md`, which
was produced by the main session.

## Verified findings this session
- **E-008 CONFIRMED:** early break-even is the worst exit rule on all four
  markets (-0.161 to -0.308R). Veer's "protect indubitable profits" instinct
  is the mechanism destroying his EA.
- **E-008:** an oracle peak-exit returns +3.019R vs +0.201R for the best real
  exit. "Never closing at the peak" is universal and permanent.
- **E-009/E-010:** 8 strategies x 4 markets — NOTHING reaches PROMISING.
  `donchian_trend` DOWNGRADED from PROMISING to UNPROVEN (fails on 3 of 4
  markets). `liquidity_sweep` positive on 1 of 4 = likely artifact.
- **E-006:** EA REJECTED — 748 parameters on a 279-trade sample.
- **E-011:** every test so far is 1h on 4 correlated instruments; the published
  trend evidence is daily+ across 50+ diversified markets. Wrong search space.

## Where the work stopped
`JARVIS/MASTER_REPORT.md` and `JARVIS/TOMORROW.md` written. 4 commits ready.
**Push still blocked (403)** — the Claude GitHub App is not installed for
`veer7710/signals`. This is the top blocker; the container is ephemeral.


---
# UPDATE — Pine indicator + automated search session

## Built
- `JARVIS/pine/LiquiditySniper_v1.pine` (v1.2, 525 lines, 39 inputs) — live on
  Veer's charts and compiling. Encodes the continuation finding, the expansion
  filter as an adjustable preset rather than a hard gate, retest confirmation,
  multi-trade concurrency, and prior-day/session/round-number liquidity.
- `JARVIS/research/autosearch.py` — the zero-AI-cost search engine. 672 tests in
  40 seconds. Chronological 70/30 split, out-of-sample run once, multiple-testing
  correction stated. THIS IS THE USAGE-CONSERVATION ANSWER: the model picks the
  search space once, local Python does the grinding.
- `JARVIS/research/sweeps.py`, `sweep_study.py`, `movesize.py`, `volregime.py`,
  `intraday_momentum.py` — all runnable locally at no usage cost.

## Bugs I made and caught (all before they reached a result)
- MFE/MAE measured independently reported "75% reached 1R" while 85% stopped
  out. Fixed to first-touch, ties lose. Honest figure 44.5%.
- Momentum comparison run with the fade direction, concluding sweeps were worse
  than momentum. Would have killed a real finding.
- Pine: ta.dmi returns [+DI,-DI,ADX] and the ADX variable was reading +DI.
- Pine: merged equal-high levels moved their price but the line never followed.
- Pine: line(na) is not a valid constructor.

## What the next session should NOT redo
E-001, E-002, E-017 (fade), E-022 (LeBaron), lead-lag. All closed with evidence.

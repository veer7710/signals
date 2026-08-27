# Next actions (highest value first)

## A-001 — Attack `donchian_trend` before believing it   [JARVIS can do now]
It is the only promising candidate. Run the adversarial-reviewer agent:
- Test on US500, EURUSD, GBPUSD (`study.py US500 1h`). An edge that exists
  on one symbol only is probably curve-fit.
- Perturb parameters (Donchian 40/55/70, stop 1.5/2.0/2.5 ATR, R 2/3/4).
  A real edge degrades gracefully; a fitted one collapses.
- Split by year. Gold's bull run may be doing all the work — longs earn
  +0.292R, shorts only +0.007R.
- Report the drawdown a 16-trade losing streak causes at prop-firm risk.

## A-002 — Test the liquidity family properly   [JARVIS can do now]
E-003 tested ONE implementation. Still untested: prior-day/week levels,
session highs/lows, equal highs/lows, sweep-then-reclaim on 15m,
displacement confirmation. Each is a separate hypothesis with its own entry.

## A-003 — Get the real EA and Pine scripts   [BLOCKED ON VEER]
Upload `.mq5` source + both Pine scripts into `JARVIS/ea/inbox/`. Until
then no audit of "the current EA" is possible — it has never been in this
repo.

## A-004 — Re-plan the funded-account scaling around R-002  [BLOCKED ON VEER]
FTMO caps allocation at $400k per trader OR STRATEGY; identical fills across
firms trigger copy-trade detection and dual payout denial. Need from Veer:
which firms, which account sizes, current pass/fail history. Then model
realistic expected value including challenge fees and failure rates.

## A-005 — Install throughput tooling   [BLOCKED ON VEER — his PC]
OmniRoute for provider fallback; Ollama for local background models.
Graphify only once this repo is large enough to matter.

## A-006 — Build the JARVIS dashboard   [JARVIS can do, lower priority]
Single page reading `JARVIS/state/*` and `JARVIS/reports/*`: phase, open
questions, experiment verdicts, next actions. Only worth it once there is
more state to display.

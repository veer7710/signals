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

## A-003 — Audit the EA and Pine scripts   [DONE 2026-08-27]
Received and audited. EA REJECTED (E-006), see `JARVIS/ea/AUDIT_v19_18.md`.
Pine scripts read: `XAUUSD_CLEAN_3.5` (Supertrend flips + SNAP/SWEEP/BREAK
grading) and `LiquidityEngine_v2` (sweep/cascade/CISD — the better of the
two, and the source of the cost-to-risk insight).

## A-007 — Port the LiquidityEngine concepts into the research engine   [NEXT]
`LiquidityEngine_v2.pine` contains the best ideas in all three files, and
they have never been measured: the cascade veto (do not fade a sweep that
agrees with a strong trend), CISD confirmation, the cost-to-risk gate, and
give-up measurement after a stop. Implement each as a SEPARATE testable
hypothesis in `strategies.py`, so each earns or loses its place on its own
numbers rather than arriving as a bundle.

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

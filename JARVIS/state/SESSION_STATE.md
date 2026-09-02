# SESSION STATE — 2026-09-01

## What this session actually established

**E-063 / E-059 — cost is the dominant term, and I had the input wrong twice.**
Spread was assumed at 0.30 for months; Veer's screenshots show 0.46. I then
extrapolated M1 volatility from repo data covering a MORE volatile period than
he trades. Both errors made the strategy look cheaper than it is.
**BUT: Veer has since said his EA runs on a DIFFERENT broker from those charts,
that PU Prime charges no commission, and that his spread is not large.** So the
0.46 figure may not apply to the account that trades. The EA now MEASURES its
own spread every tick and writes it to the journal and the box. That settles it
next session; do not re-argue it from a chart.

**E-064 — the GOLD edge is real and modest.** Signal +0.26R (15m) / +0.23R (1h)
against a random control, beating 12 of 12 and 11 of 12 seeds, at 1.7–1.8
control standard deviations. Not the 3.65 bar. One instrument.

**E-056 — stall is the strongest execution result: 8 of 8 markets, monotone.**
Bars since a trade last made a new best predicts give-back, 24% at stall 0–1
against 62% at stall 25+ on GOLD 15m. NOT YET RE-TESTED with one observation
per trade instead of per bar — the red team was told to do that and died first.
**That test is the highest-value unfinished item in the project.**

**E-060 — early entry at the SuperTrend band does NOT help.** My first version
scored +0.214R and was a look-ahead bug (it only entered on bars that turned
out to flip). Honest version: beats the close entry in 3 of 8, identical pooled.

**E-061/062 — the geometry the EA already ships (1.5 ATR stop, 3R, 50 bars) is
at the out-of-sample optimum on GOLD 1h.** 60 cells searched. No improvement
found. GOLD 15m OOS had n=17–37 per cell and was discarded.

## Shipped and pushed
- `SuperTrendSniper.mq5` — cost floor on the stop (InpMinStopCostX), spread
  telemetry, stall exit, give-back banking half, basket engine, guards that
  survive restart, broker stop-level handling, execution box with ChartRedraw.
- `XAUUSD_CLEAN_3_6.pine` — Veer's own 3.5 with measured readings in the STATUS
  LINE only, plus a position box. His chart rule kept exactly.
- `LIQUIDITY_CLEAN_1_0.pine` — the two LuxAlgo scripts and nothing else.
- `ExportHistory.mq5` — drag onto a chart, writes M1/M5/M15 JSON for the engine.

## The two files that unblock everything
1. `MQL5/Files/STS_journal_XAUUSD_PERIOD_M1.csv` — every entry now carries
   spread, stop and cost/stop. One session of it answers the cost question.
2. `GOLD_M1.json` / `GOLD_M5.json` from ExportHistory.mq5 — every experiment
   in this repo has run on 15m/1h. He trades M1. This ends the extrapolating.

## Failures logged this session
F-009 (ta.adx does not exist; the checker validated the namespace and ignored
the member), F-010 (the cost gate at 0.10 refused nearly every M1 entry while
E-053 said M1 sits at 0.15–0.22 — I measured that filters do not work and then
spent the afternoon adding filters).

## Standing correction to how I work
Two of the three biggest errors this session were WRONG INPUTS, not wrong
analysis, and neither was found by more analysis. Check the input against the
user's own screenshots before running anything on top of it.

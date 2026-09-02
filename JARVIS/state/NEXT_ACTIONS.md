# NEXT ACTIONS

## For Veer, in order of what unblocks the most

1. **Run `JARVIS/ea/tools/ExportHistory.mq5`.** Drag it onto an XAUUSD chart.
   It writes GOLD_M1/M5/M15.json. This is the single thing blocking every M1
   conclusion in the project — right now M1 is extrapolated from 15m and 1h.
2. **Recompile both EAs in MetaEditor (F7)** and check the build stamp on the
   chart matches: SuperTrend `2.14`, Liquidity `1.00`. If the stamp is old,
   MetaEditor has not rebuilt and none of this session's changes are running.
3. **Load `LIQUIDITY_CLEAN_1_1.pine`** and confirm the signal count looks like
   the chart you actually trade. If it is still sparse, `minPiv` is the dial.
4. **Send the journal CSV** (`STS_journal_XAUUSD_PERIOD_M1.csv`) once the EA
   has run a session. Every entry logs spread, stop and cost/stop; every exit
   logs peak and kept.

## For the next session, in order of value

1. **Parity-check LiquiditySniper.mq5 against E-069.** Port the EA's exact
   logic to Python and confirm it reproduces the measured numbers. The EA is
   new and about to be run; implementation drift is the obvious risk.
2. **Re-measure everything on M1** once the data exists. E-069 and E-071 are
   both 15m/1h results being applied to an M1 EA.
3. **The basket engine has never been measured**, only reasoned about. It is
   the last large piece of the SuperTrend EA with no experiment behind it.
4. **"African scalps on lower tf"** — Veer mentioned this once and it has
   never been asked about or implemented.

# Gold EA research + lean rebuild

## Read in this order
1. `research/FINDINGS.md`  — what the data says. Start here.
2. `research/PLAN.md` / `PLAN2.md` — the measures, pre-registered BEFORE looking at data.
3. `research/DATA_REPORT.md` — the dataset and its validation.
4. `research/EA_AUDIT.md` — audit of the old 19,662-line EA; corrects several handover claims.

## Headline
The Supertrend flip (the CLEAN indicator) is **anti-predictive on gold M1**: gross, before
any cost, −0.030 pt/trade at **t = −5.44** over 283,251 trades. Mechanism: M1 gold
mean-reverts at t≈9–10, and a Supertrend flip is a breakout entry, so it trades against the
only real structure on the timeframe. No parameter, exit, regime or timeframe fixes it, and
a 492-test screen of 12 alternative signals found nothing that survives non-overlapping
windows plus real execution plus walk-forward.

## Layout
- `ea/XAUUSD_LEAN.mq5`        — the rebuild. 780 lines, 29 inputs, 0 dead. NOT COMPILED (no
                                MetaEditor on Linux) — compile with F7.
- `ea/XAUUSD_QUAD_v19_04.mq5` — the old EA, kept as reference/benchmark only.
- `pine/XAUUSD_CLEAN_3.5.pine`— the indicator.
- `engine/pine.py`            — Pine-exact ta.supertrend / ta.atr / ta.rma / ta.dema.
- `engine/parity_check.py`    — PROVES the EA's MQL5 signal == the Pine reference.
                                Currently 0 mismatches / 4000 bars, level error 9e-13.
- `engine/replay.py`          — bar-by-bar replay + the pre-registered measures.
- `engine/sim.py`             — exit-rule simulator (correct bid/ask trigger timing).
- `research/*.py`             — the studies. Each writes a .log and .csv beside it.

## Regenerating the data (not committed — 747 MB + a 116 MB parquet)
See `data/REGENERATE.md`.

## Standing warnings
- `ea/XAUUSD_LEAN.mq5` will LOSE MONEY on the Supertrend signal, fastest on M1. It is a
  trustworthy chassis for testing a signal, not a profitable strategy.
- Win rate is not used as evidence anywhere in this work. Points and t-statistics only.

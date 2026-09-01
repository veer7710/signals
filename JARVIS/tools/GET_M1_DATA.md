# Get M1 data into the repo — 3 minutes, on your Windows PC

Every backtest in this repo is 15m and 1h. **You trade M1.** Until M1 data is
here, nothing measured can honestly describe what you actually do — and that
is the single biggest gap in the whole project, bigger than any indicator
setting.

## The easy way — no Python, no install (added 2026-09-01)

`JARVIS/ea/tools/ExportHistory.mq5` does the same job from inside MT5 itself.

1. Put `ExportHistory.mq5` in **MQL5/Scripts/** and press **F7** to compile.
2. Open a **XAUUSD** chart. Press **Home** and hold it for a few seconds on
   each of M1, M5 and M15 — MT5 only exports bars it has actually downloaded,
   and the script prints how many it found so you can tell if it worked.
3. **Drag the script onto the chart.** Tick "Allow" if it asks.
4. Files appear in **MQL5/Files/** (reach it with *File > Open Data Folder*)
   named `GOLD_M1.json`, `GOLD_M5.json`, `GOLD_M15.json`. Send those.

They are already in the exact format `JARVIS/research/engine.py` loads, so
they drop straight into `data/` and every study in the repo re-runs on the
timeframes you actually trade — with no code changes.

**Why this matters more than any indicator setting:** every experiment in this
project, E-001 through E-053, ran on 15m and 1h. You trade M1. Every M1 number
I have given you is an extrapolation and is labelled as one. This file ends
that.

## The other way — Python, and it also gets your REAL broker costs

Worth doing as well, because it reads the live spread and commission from
your PU Prime account. E-053 showed that round-trip cost as a fraction of the
stop separates the winning markets from the losing ones almost perfectly, and
the gold cost I have been assuming (spread 0.30, $7/lot) is an estimate. If
PU Prime is worse than that at the hours you trade, several conclusions move.

## Do this

1. Open MetaTrader 5 and log in. Leave it open.
2. Open a chart of **XAUUSD on M1**, then press **Home** and hold it for a few
   seconds. MT5 only downloads history you have actually scrolled to — if you
   skip this, the export comes back nearly empty.
3. Open Command Prompt and run:

```
pip install MetaTrader5
python export_mt5_data.py
```

4. It writes a folder called `mt5_export`. Send me that folder, or just the
   `XAUUSD_1m.json` and `XAUUSD_5m.json` files inside it.

## What it also grabs, which matters as much as the candles

Your broker's **real spread and commission**, read straight from the terminal.

Every result in this repo currently assumes a gold spread of 0.30 and $7 per
lot. Those are reasonable guesses, not your numbers. On M1 that matters far
more than on 15m: if the typical move you are trading is 2 points and the real
spread is 0.5 instead of 0.3, a fifth of the edge is gone before the trade
starts. Guessing here is not acceptable, so the script reads it rather than
assuming.

## Then what

With `XAUUSD_1m.json` in `data/`, these run immediately and describe the
timeframe you actually trade:

```
python3 JARVIS/research/pointscale.py        # how far M1 signals really run
python3 JARVIS/research/small_account.py     # what a small account can do on M1
python3 JARVIS/research/study.py GOLD 1m     # the full five-test verdict
```

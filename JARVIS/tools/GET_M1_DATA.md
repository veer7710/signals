# Get M1 data into the repo — 3 minutes, on your Windows PC

Every backtest in this repo is 15m and 1h. **You trade M1.** Until M1 data is
here, nothing measured can honestly describe what you actually do — and that
is the single biggest gap in the whole project, bigger than any indicator
setting.

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

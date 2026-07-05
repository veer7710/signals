# fetch_data.py — downloads candle data for the strategy-lab web app.
# Saves JSON files into /data. Run via the fetch-data workflow.
import os, json, time
import yfinance as yf
import pandas as pd

SYMBOLS = {"GOLD": "GC=F", "US500": "ES=F",
           "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X"}
SETS = [("15m", "60d"), ("1h", "730d")]   # short window fine-grain + 2 years hourly

os.makedirs("data", exist_ok=True)
for key, tk in SYMBOLS.items():
    for interval, period in SETS:
        for _ in range(2):
            d = yf.download(tk, period=period, interval=interval, progress=False)
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            if len(d):
                break
            time.sleep(2)
        d = d.dropna(subset=["Close"])
        d.index = (d.index.tz_localize("UTC") if d.index.tz is None
                   else d.index.tz_convert("UTC"))
        rows = [[int(t.timestamp()), round(float(o), 5), round(float(h), 5),
                 round(float(l), 5), round(float(c), 5)]
                for t, o, h, l, c in zip(d.index, d["Open"], d["High"],
                                         d["Low"], d["Close"])]
        with open(f"data/{key}_{interval}.json", "w") as f:
            json.dump(rows, f, separators=(",", ":"))
        print(key, interval, len(rows), "candles")
print("done")

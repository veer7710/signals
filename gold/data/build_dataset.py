"""Consolidate Best6626840 XAUUSDm M1 bid bars -> one parquet, with source flags."""
import sys, glob, os
import pandas as pd, numpy as np

SRC = "raw/Best6626840_xauusd-m1-data"
OUT = "xauusd_m1.parquet"

frames = []
for f in sorted(glob.glob(os.path.join(SRC, "XAUUSDm_M1_*.csv"))):
    d = pd.read_csv(f)
    frames.append(d)
    print(f"  {os.path.basename(f)}  rows={len(d)}", flush=True)
df = pd.concat(frames, ignore_index=True)
df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
df = df.sort_values("time_utc").drop_duplicates("time_utc").reset_index(drop=True)

# mark backfilled (non-Exness) bars so they can be excluded
fb = os.path.join(SRC, "filled_bars.csv.gz")
df["src"] = "exness"
if os.path.exists(fb):
    s = pd.read_csv(fb)
    s["time_utc"] = pd.to_datetime(s["time_utc"], utc=True)
    m = dict(zip(s["time_utc"], s.get("source", pd.Series(["dukascopy"] * len(s)))))
    df["src"] = df["time_utc"].map(m).fillna("exness")

df = df.rename(columns={"time_utc": "dt"})
df["ts"] = (df["dt"] - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds().astype("int64")
# spread_points: 1 point = $0.001  -> convert to price units ("pt" = $1.00)
df["spread"] = df["spread_points"] * 0.001
df = df[["ts", "dt", "open", "high", "low", "close", "tick_volume", "spread", "src"]]
df.to_parquet(OUT, index=False)
print(f"\nwrote {OUT}  rows={len(df):,}  {df.dt.min()} -> {df.dt.max()}")
print(df.src.value_counts().to_dict())

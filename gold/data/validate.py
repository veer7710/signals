import pandas as pd, numpy as np, glob, os
df = pd.read_parquet("xauusd_m1.parquet")

print("=" * 72); print("DATA HEALTH — xauusd_m1.parquet"); print("=" * 72)
g = np.diff(df.ts.values)
print(f"rows {len(df):,}   {df.dt.min()} -> {df.dt.max()}")
print(f"modal gap {pd.Series(g).mode().iloc[0]}s   gaps==60s: {100*(g==60).mean():.2f}%")
bad = ((df.high < df.low) | (df.close > df.high) | (df.close < df.low) |
       (df.open > df.high) | (df.open < df.low))
print(f"OHLC violations: {int(bad.sum())}")
print(f"non-positive prices: {int((df[['open','high','low','close']] <= 0).sum().sum())}")
print(f"duplicate timestamps: {int(df.ts.duplicated().sum())}")

# weekend boundary -> confirms the timezone label
df["dow"] = df.dt.dt.dayofweek; df["hr"] = df.dt.dt.hour
fri = df[df.dow == 4].groupby(df.dt.dt.date).hr.max()
sun = df[df.dow == 6].groupby(df.dt.dt.date).hr.min()
print(f"Friday last-bar hour (UTC): mode {fri.mode().iloc[0]}  median {fri.median():.0f}")
print(f"Sunday first-bar hour (UTC): mode {sun.mode().iloc[0]}  median {sun.median():.0f}")
print("  (FX closes Fri 21:00 UTC / opens Sun 21:00 UTC -> expect 20-21 both)")
print(f"Saturday bars (should be ~0): {int((df.dow == 5).sum())}")

print("\nper-year: bars, coverage of expected trading minutes, spread, price")
for y, d in df.groupby(df.dt.dt.year):
    gg = np.diff(d.ts.values)
    miss = int(((gg > 60) & (gg <= 3 * 3600)).sum())
    lost = int(np.clip(gg[(gg > 60) & (gg <= 3 * 3600)] / 60 - 1, 0, None).sum())
    print(f"  {y}  bars {len(d):7,}  intraday_gaps {miss:5d} (~{lost:6,d} min lost)  "
          f"spread med {d.spread.median():.3f} p90 {d.spread.quantile(.9):.3f}  "
          f"close {d.close.min():7.1f}-{d.close.max():7.1f}  exness {100*(d.src=='exness').mean():5.1f}%")

print("\nspread ($) by UTC hour, 2024-2026 (this is the real cost clock)")
r = df[df.dt.dt.year >= 2024]
t = r.groupby(r.dt.dt.hour).spread.agg(["median", "mean", lambda s: s.quantile(.9), "size"])
t.columns = ["med", "mean", "p90", "n"]
print(t.round(3).to_string())

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))
import pandas as pd, numpy as np, replay, sim

START = sys.argv[1] if len(sys.argv) > 1 else "2024-01-01"
TAG   = sys.argv[2] if len(sys.argv) > 2 else "2024plus"
EXTRA = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0   # commission in price units

t0 = time.time()
df = pd.read_parquet("data/xauusd_m1.parquet")
df = df[df.dt >= START].reset_index(drop=True)
print(f"bars {len(df):,}  {df.dt.min()} -> {df.dt.max()}  "
      f"spread med {df.spread.median():.3f}  exness {100*(df.src=='exness').mean():.1f}%", flush=True)

legs, d, buy, sell, st = replay.build_legs(df, 1.2, 7, spread_col="spread", extra_cost=EXTRA)
print(f"legs {len(legs):,}  built in {time.time()-t0:.0f}s", flush=True)
legs.to_parquet(f"research/legs_{TAG}.parquet", index=False)

txt = replay.report(legs, df, out=f"research/STUDY_{TAG}.txt")
print(txt)

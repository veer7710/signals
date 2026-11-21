"""
CONTROL EXPERIMENT. The old diagnosis said "sum of best-moments = +293 GBP, so the
entries are fine and the exits lose it". That statistic is BIASED: the favourable
extreme of a random walk is positive in expectation, so sum(MFE) is positive for
ANY entry rule, including a coin flip. This measures how much of the Supertrend's
"available profit" a RANDOM entry with the same trade count and same holding times
would also have shown. If they match, sum(MFE) is not evidence of edge.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))
import pandas as pd, numpy as np

df = pd.read_parquet("data/xauusd_m1.parquet")
df = df[df.dt >= "2024-01-01"].reset_index(drop=True)
legs = pd.read_parquet("research/legs_2024plus.parquet")
o = df.open.values; h = df.high.values; l = df.low.values; spr = df.spread.values
n = len(df)

real_mfe = legs.mfe.sum(); real_net = legs.net.sum(); N = len(legs)
hold = legs.bars.values                      # reuse the REAL holding times
print(f"REAL Supertrend: {N} trades  sum MFE {real_mfe:+.0f}  net {real_net:+.0f}")

rng = np.random.default_rng(42)
res = []
for trial in range(5):
    ent = rng.integers(1, n - 2, size=N)
    dirs = rng.choice([1, -1], size=N)
    mfe = np.zeros(N); net = np.zeros(N)
    for i in range(N):
        e = ent[i]; d = dirs[i]; k = max(int(hold[i]), 1)
        x = min(e + k, n - 1)
        s_in = spr[e]
        entry = o[e] + s_in if d > 0 else o[e]
        adj = 0.0 if d > 0 else s_in
        best = (h[e:x].max() if d > 0 else l[e:x].min() + adj) if x > e else entry
        mfe[i] = (best - entry) * d
        exit_ = o[x] if d > 0 else o[x] + spr[x]
        net[i] = (exit_ - entry) * d
    res.append((mfe.sum(), net.sum()))
    print(f"  random trial {trial+1}: sum MFE {mfe.sum():+.0f}   net {net.sum():+.0f}")

m = np.mean([r[0] for r in res]); nt = np.mean([r[1] for r in res])
print(f"\nRANDOM mean: sum MFE {m:+.0f}   net {nt:+.0f}")
print(f"Supertrend  : sum MFE {real_mfe:+.0f}   net {real_net:+.0f}")
print(f"\n=> Supertrend MFE is {100*real_mfe/m:.0f}% of what a COIN FLIP shows.")
print(f"=> Supertrend net is {real_net - nt:+.0f} pt vs the coin flip.")
print("\nINTERPRETATION: if the ratio is ~100%, sum(MFE) carries no information about")
print("entry quality, and 'we left money on the table' was measuring a statistical")
print("artefact rather than a real missed edge.")

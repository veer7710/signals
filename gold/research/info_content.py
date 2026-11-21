"""
THE PUREST TEST: does a Supertrend flip predict anything at all?
Forward return after the signal bar, at fixed horizons, with NO costs and NO exit
rules. If no horizon shows a t-statistic beyond +/-2, the signal carries no
directional information and nothing downstream can create an edge from it.
Also tests the conditional hypotheses: DEMA agreement, volatility regime, session.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))
import pandas as pd, numpy as np
from pine import clean_signals, pine_atr, pine_dema

df = pd.read_parquet("data/xauusd_m1.parquet")
df = df[df.dt >= "2024-01-01"].reset_index(drop=True)
h, l, c = df.high.values, df.low.values, df.close.values
n = len(df)
print(f"bars {n:,}  {df.dt.min()} -> {df.dt.max()}", flush=True)

d, buy, sell, st = clean_signals(h, l, c, 1.2, 7)
atr = pine_atr(h, l, c, 14)
dema = pine_dema(c, 60)
sig = np.where(buy | sell)[0]
dirs = np.where(buy[sig], 1, -1)
print(f"signals {len(sig):,}\n", flush=True)

HOR = [1, 2, 3, 5, 10, 15, 30, 60, 120, 240]

def tstat(x):
    x = x[~np.isnan(x)]
    if len(x) < 30: return np.nan, np.nan, 0
    return x.mean(), x.mean() / (x.std(ddof=1) / np.sqrt(len(x))), len(x)

print("=" * 76)
print("FORWARD RETURN AFTER A FLIP — no costs, no exits, pure information content")
print("=" * 76)
print(f"{'horizon':>8} {'mean_pt':>10} {'t_stat':>8} {'n':>8}   {'verdict':<28}")
rows = {}
for k in HOR:
    idx = sig[sig + k < n]
    dd = dirs[sig + k < n]
    r = (c[idx + k] - c[idx]) * dd
    rows[k] = r
    m, t, nn = tstat(r)
    v = ("EDGE" if abs(t) > 2 and m > 0 else
         "REVERSES (edge the other way)" if abs(t) > 2 and m < 0 else "no information")
    print(f"{k:>6}m {m:>10.4f} {t:>8.2f} {nn:>8}   {v:<28}")
print("\n(|t| > 2 ~ 5% significance. With n ~ 175k the smallest detectable")
print(" edge at 2 SE is about 0.01-0.02 pt/trade, so this test has ample power.)")

print("\n" + "=" * 76)
print("CONDITIONAL TESTS — is the edge hiding in a subset? (horizon 15m)")
print("=" * 76)
k = 15
idx = sig[sig + k < n]; dd = dirs[sig + k < n]
r = (c[idx + k] - c[idx]) * dd
hour = df.dt.dt.hour.values[idx]
a = atr[idx]
dm = dema[idx]
px = c[idx]
with_dema = np.where(dd > 0, px > dm, px < dm)

def show(name, mask):
    m, t, nn = tstat(r[mask])
    flag = "  <== SIGNIFICANT" if abs(t) > 2 else ""
    print(f"  {name:<34} n={nn:>7}  mean {m:>8.4f}  t {t:>6.2f}{flag}")

show("ALL", np.ones(len(r), bool))
show("price AGREES with DEMA60", with_dema)
show("price AGAINST DEMA60", ~with_dema)
qs = np.nanpercentile(a, [20, 40, 60, 80])
for i, lab in enumerate(["ATR Q1 quiet", "ATR Q2", "ATR Q3", "ATR Q4", "ATR Q5 wild"]):
    lo = -np.inf if i == 0 else qs[i-1]
    hi = np.inf if i == 4 else qs[i]
    show(lab, (a > lo) & (a <= hi))
for nm, m_ in (("Asia 00-06", (hour < 7)), ("London 07-11", (hour >= 7) & (hour < 12)),
               ("Overlap 12-15", (hour >= 12) & (hour < 16)), ("NY 16-20", (hour >= 16) & (hour < 21)),
               ("Late 21-23", hour >= 21)):
    show(nm, m_)
show("BUY signals only", dd > 0)
show("SELL signals only", dd < 0)

print("\nMULTIPLE-COMPARISONS NOTE: 15 subsets tested. At 5% significance, expect")
print("~0.75 false positives by chance. A single |t|~2 result here is NOT a finding.")

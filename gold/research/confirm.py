"""
CONFIRMATION TEST for the candidates that cleared the screen.

The screen's t-stats are INFLATED: signals fired on up to 25% of bars with 10-20 bar
forward windows, so the observations overlap heavily and are not independent.
This re-tests with:
  1. NON-OVERLAPPING windows  — a signal is only accepted if it is at least `horizon`
     bars after the last accepted one (and a 2x-gap variant, stricter still).
  2. REAL EXECUTION           — fill at the NEXT bar's open, exit at the close of the
     last held bar, bid/ask handled properly, one full spread per round trip.
  3. WALK-FORWARD halves and an equity path with max drawdown.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))
import pandas as pd, numpy as np
from pine import pine_atr, pine_dema

m1 = pd.read_parquet("data/xauusd_m1.parquet")
m1 = m1[m1.dt >= "2019-01-01"].reset_index(drop=True)

def resample(df, rule):
    g = df.set_index("dt").resample(rule, label="left", closed="left")
    o = g.agg(open=("open","first"), high=("high","max"), low=("low","min"),
              close=("close","last"), spread=("spread","mean")).dropna(subset=["close"])
    return o.reset_index()

def sig_continue_dema(d, k=2.0):
    c = d.close.values
    atr = pine_atr(d.high.values, d.low.values, c, 14)
    dm = pine_dema(c, 60)
    st = (c - dm) / np.where(atr > 0, atr, np.nan)
    m = (np.abs(st) > k) & ~np.isnan(st)
    i = np.where(m)[0]
    return i, np.where(st[i] > 0, 1, -1)

def sig_breakout(d, N=20):
    h, l, c = d.high.values, d.low.values, d.close.values
    hi = pd.Series(h).rolling(N).max().shift(1).values
    lo = pd.Series(l).rolling(N).min().shift(1).values
    up = (c > hi); dn = (c < lo)
    m = (up | dn) & ~np.isnan(hi)
    i = np.where(m)[0]
    return i, np.where(up[i], 1, -1)

CANDS = {
    "continue DEMA 2atr": lambda d: sig_continue_dema(d, 2.0),
    "continue DEMA 3atr": lambda d: sig_continue_dema(d, 3.0),
    "breakout 20b":       lambda d: sig_breakout(d, 20),
    "breakout 60b":       lambda d: sig_breakout(d, 60),
}
TFS = [("M15","15min"), ("M30","30min"), ("H1","1h"), ("H4","4h")]
GBP = 0.733

def dedupe(idx, dirs, gap):
    """keep only signals at least `gap` bars after the last kept one -> no overlap"""
    keep_i, keep_d = [], []
    last = -10**9
    for a, b in zip(idx, dirs):
        if a - last >= gap:
            keep_i.append(a); keep_d.append(b); last = a
    return np.array(keep_i), np.array(keep_d)

rows = []
for tfname, rule in TFS:
    d = resample(m1, rule)
    o, c, spr = d.open.values, d.close.values, d.spread.values
    n = len(c)
    days = len(set(d.dt.dt.date))
    for cname, fn in CANDS.items():
        idx0, dirs0 = fn(d)
        for hor in (10, 20):
            for mult, tag in ((1, "gap=h"), (2, "gap=2h")):
                idx, dirs = dedupe(idx0, dirs0, hor * mult)
                m = (idx + 1 + hor) < n
                idx, dirs = idx[m], dirs[m]
                if len(idx) < 150:
                    continue
                e = idx + 1                      # fill at the NEXT bar's open
                x = idx + hor                    # exit at the close of the last held bar
                entry = np.where(dirs > 0, o[e] + spr[e], o[e])
                exit_ = np.where(dirs > 0, c[x], c[x] + spr[x])
                net = (exit_ - entry) * dirs
                t = net.mean() / (net.std(ddof=1) / np.sqrt(len(net)))
                half = d.dt.iloc[n // 2]
                h1m = d.dt.values[idx] < np.datetime64(half.tz_localize(None))
                def tt(v):
                    if len(v) < 60: return 0.0, 0.0
                    return v.mean(), v.mean() / (v.std(ddof=1) / np.sqrt(len(v)))
                m1_, t1_ = tt(net[h1m]); m2_, t2_ = tt(net[~h1m])
                eq = np.cumsum(net) * GBP
                dd = float((np.maximum.accumulate(eq) - eq).max())
                rows.append(dict(tf=tfname, cand=cname, hor=hor, dedupe=tag,
                                 n=len(net), net_per_trade=round(net.mean(), 4),
                                 t=round(t, 2), net_pt=round(net.sum(), 0),
                                 gbp_day=round(net.sum() * GBP / days, 3),
                                 t_h1=round(t1_, 2), t_h2=round(t2_, 2),
                                 maxdd_gbp=round(dd, 2),
                                 per_day=round(len(net) / days, 2)))
    print(f"  {tfname} done", flush=True)

t = pd.DataFrame(rows)
t.to_csv("research/confirm.csv", index=False)
pd.set_option("display.width", 260)
print("\n=== ALL RESULTS, NON-OVERLAPPING, REAL EXECUTION (sorted by t) ===")
print(t.sort_values("t", ascending=False).head(22).to_string(index=False))
print("\n=== SURVIVES EVERYTHING (|t|>=4, net>0, both halves |t|>=2 same sign, n>=150) ===")
ok = t[(t.t >= 4.0) & (t.net_per_trade > 0) & (t.t_h1 >= 2) & (t.t_h2 >= 2)]
print(ok.to_string(index=False) if len(ok) else ">>> NOTHING SURVIVES <<<")
print("\n=== survives at the stricter gap=2h only ===")
ok2 = t[(t.dedupe == "gap=2h") & (t.t >= 3.0) & (t.net_per_trade > 0) &
        (t.t_h1 >= 1.5) & (t.t_h2 >= 1.5)]
print(ok2.to_string(index=False) if len(ok2) else "(none)")

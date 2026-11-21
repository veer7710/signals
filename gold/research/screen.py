"""Signal information screen. See PLAN2.md for pre-registered acceptance."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))
import pandas as pd, numpy as np
from pine import clean_signals, pine_atr, pine_dema, pine_ema

m1 = pd.read_parquet("data/xauusd_m1.parquet")
m1 = m1[m1.dt >= "2019-01-01"].reset_index(drop=True)

def resample(df, rule):
    g = df.set_index("dt").resample(rule, label="left", closed="left")
    o = g.agg(open=("open","first"), high=("high","max"), low=("low","min"),
              close=("close","last"), spread=("spread","mean")).dropna(subset=["close"])
    return o.reset_index()

def rollmax(a, n):
    return pd.Series(a).rolling(n).max().values
def rollmin(a, n):
    return pd.Series(a).rolling(n).min().values
def sma(a, n):
    return pd.Series(a).rolling(n).mean().values

def candidates(d):
    """returns dict name -> (signal_bar_index array, direction array)"""
    h, l, c, o = d.high.values, d.low.values, d.close.values, d.open.values
    n = len(c)
    atr = pine_atr(h, l, c, 14)
    out = {}
    i = np.arange(n)

    # 1 baseline: Supertrend flip
    dirn, buy, sell, _ = clean_signals(h, l, c, 1.2, 7)
    s = np.where(buy | sell)[0]
    out["ST flip 1.2/7"] = (s, np.where(buy[s], 1, -1))

    # 2 Donchian breakout (momentum)
    for N in (20, 60):
        hi, lo = rollmax(h, N), rollmin(l, N)
        up = (c > np.roll(hi, 1)) & (i > N)
        dn = (c < np.roll(lo, 1)) & (i > N)
        s = np.where(up | dn)[0]
        out[f"breakout {N}b"] = (s, np.where(up[s], 1, -1))

    # 3 Donchian FADE (the mirror: mean reversion at the extreme)
    for N in (20, 60):
        hi, lo = rollmax(h, N), rollmin(l, N)
        up = (c > np.roll(hi, 1)) & (i > N)
        dn = (c < np.roll(lo, 1)) & (i > N)
        s = np.where(up | dn)[0]
        out[f"fade breakout {N}b"] = (s, np.where(up[s], -1, 1))

    # 4 stretch from DEMA -> trade back toward it
    dm = pine_dema(c, 60)
    st = (c - dm) / np.where(atr > 0, atr, np.nan)
    for k in (2.0, 3.0):
        m = np.abs(st) > k
        s = np.where(m & ~np.isnan(st))[0]
        out[f"revert DEMA {k}atr"] = (s, np.where(st[s] > 0, -1, 1))

    # 5 stretch from DEMA -> trade WITH it (trend continuation)
    m = np.abs(st) > 2.0
    s = np.where(m & ~np.isnan(st))[0]
    out["continue DEMA 2atr"] = (s, np.where(st[s] > 0, 1, -1))

    # 6 single-bar reversion / continuation (micro autocorrelation)
    rng = h - l
    body = c - o
    big = (rng > 1.5 * atr) & (np.abs(body) > 0.6 * rng)
    s = np.where(big & ~np.isnan(atr))[0]
    out["big bar continue"] = (s, np.sign(body[s]).astype(int))
    out["big bar fade"] = (s, -np.sign(body[s]).astype(int))

    # 7 volatility expansion with direction
    arise = atr > 1.3 * np.roll(sma(atr, 20), 1)
    m = arise & (np.abs(body) > 0.5 * rng) & ~np.isnan(atr)
    s = np.where(m)[0]
    out["vol expansion dir"] = (s, np.sign(body[s]).astype(int))

    # 8 RSI-style extreme via EMA of gains (mean reversion)
    e = pine_ema(c, 14)
    dev = (c - e) / np.where(atr > 0, atr, np.nan)
    m = np.abs(dev) > 1.5
    s = np.where(m & ~np.isnan(dev))[0]
    out["revert EMA14 1.5atr"] = (s, np.where(dev[s] > 0, -1, 1))

    # 9 time-of-day drift: long every bar at a fixed UTC hour
    hr = d.dt.dt.hour.values
    for H in (8, 13):
        s = np.where((hr == H) & (np.roll(hr, 1) != H))[0]
        out[f"long at {H:02d}h UTC"] = (s, np.ones(len(s), int))
    return out

HOR = [1, 2, 3, 5, 10, 20]
TFS = [("M1", None), ("M5", "5min"), ("M15", "15min"), ("M30", "30min"),
       ("H1", "1h"), ("H4", "4h")]
rows = []
for tfname, rule in TFS:
    d = m1 if rule is None else resample(m1, rule)
    c = d.close.values; n = len(c)
    med_spr = float(d.spread.median())
    half = d.dt.iloc[n // 2]
    cands = candidates(d)
    for name, (sig, dirs) in cands.items():
        if len(sig) < 200:
            continue
        for k in HOR:
            m = sig + k < n
            s2, d2 = sig[m], dirs[m]
            if len(s2) < 200: continue
            r = (c[s2 + k] - c[s2]) * d2
            mu = r.mean(); t = mu / (r.std(ddof=1) / np.sqrt(len(r)))
            # walk-forward halves
            isH1 = d.dt.values[s2] < np.datetime64(half)
            def tt(x):
                if len(x) < 100: return 0.0, 0.0
                return x.mean(), x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
            m1_, t1_ = tt(r[isH1]); m2_, t2_ = tt(r[~isH1])
            rows.append(dict(tf=tfname, cand=name, hor=k, n=len(r),
                             mean_pt=round(mu, 4), t=round(t, 2),
                             spread=round(med_spr, 3),
                             mean_over_spread=round(mu / med_spr, 2) if med_spr else 0,
                             t_h1=round(t1_, 2), t_h2=round(t2_, 2)))
    print(f"  {tfname} done", flush=True)

t = pd.DataFrame(rows)
t.to_csv("research/screen.csv", index=False)
pd.set_option("display.width", 250)
print(f"\ntotal tests: {len(t)}")
print("\n=== TOP 25 BY |t| ===")
print(t.reindex(t.t.abs().sort_values(ascending=False).index).head(25).to_string(index=False))
print("\n=== PRE-REGISTERED ACCEPTANCE (PLAN2) ===")
ok = t[(t.t.abs() >= 4.0) & (t.mean_over_spread >= 1.5) & (t.n >= 500) &
       (np.sign(t.t_h1) == np.sign(t.t_h2)) & (t.t_h1.abs() >= 2) & (t.t_h2.abs() >= 2)]
print(ok.to_string(index=False) if len(ok) else ">>> NOTHING CLEARS THE BAR <<<")
print("\n=== near-misses: |t|>=4 and clears spread, but fails walk-forward ===")
nm = t[(t.t.abs() >= 4.0) & (t.mean_over_spread >= 1.5) & (t.n >= 500)]
print(nm.to_string(index=False) if len(nm) else "(none)")

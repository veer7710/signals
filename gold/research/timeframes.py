"""
Is the problem THIS INDICATOR, or is it M1 GOLD AT RETAIL SPREAD?
Same CLEAN signal (Supertrend 1.2/ATR7 flip, closed bar) on M1..H4, full history.
Two tests per timeframe:
  (a) information: forward return after the flip, no costs, t-stat
  (b) economics : hold-to-flip net with the real per-bar spread
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))
import pandas as pd, numpy as np
from pine import clean_signals
import replay

m1 = pd.read_parquet("data/xauusd_m1.parquet")
m1 = m1[m1.dt >= "2019-01-01"].reset_index(drop=True)   # 2019+ = 100% broker data
print(f"M1 bars {len(m1):,}  {m1.dt.min()} -> {m1.dt.max()}", flush=True)

def resample(df, rule):
    g = df.set_index("dt").resample(rule, label="left", closed="left")
    out = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                close=("close", "last"), spread=("spread", "mean"),
                tick_volume=("tick_volume", "sum")).dropna(subset=["close"])
    out = out.reset_index()
    out["ts"] = (out["dt"] - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds().astype("int64")
    return out

TFS = [("M1", None), ("M5", "5min"), ("M15", "15min"), ("M30", "30min"),
       ("H1", "1h"), ("H4", "4h")]
HOR = [1, 2, 3, 5, 10]
rows = []
for name, rule in TFS:
    t0 = time.time()
    d = m1 if rule is None else resample(m1, rule)
    h, l, c = d.high.values, d.low.values, d.close.values
    n = len(d)
    dirn, buy, sell, st = clean_signals(h, l, c, 1.2, 7)
    sig = np.where(buy | sell)[0]
    dirs = np.where(buy[sig], 1, -1)

    # (a) information content: best |t| over horizons measured in BARS of this TF
    best = None
    for k in HOR:
        m = sig + k < n
        r = (c[sig[m] + k] - c[sig[m]]) * dirs[m]
        if len(r) < 50: continue
        t = r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))
        if best is None or abs(t) > abs(best[1]): best = (k, t, r.mean(), len(r))

    # (b) economics
    legs, *_ = replay.build_legs(d, 1.2, 7, spread_col="spread")
    days = len(set(d.dt.dt.date))
    net = legs.net.sum(); gross = legs.gross.sum()
    se = legs.gross.std() / np.sqrt(len(legs))
    rows.append(dict(
        tf=name, bars=n, trades=len(legs), per_day=round(len(legs)/days, 2),
        avail_med=round(legs.avail.median(), 2),
        spread=round(d.spread.median(), 3),
        avail_over_spread=round(legs.avail.median()/d.spread.median(), 2),
        gross_per_trade=round(gross/len(legs), 4),
        gross_t=round((gross/len(legs))/se, 2),
        net_per_trade=round(net/len(legs), 4),
        net_pt=round(net, 0), gbp_day=round(net*0.733/days, 2),
        best_hor_bars=best[0] if best else None,
        best_t=round(best[1], 2) if best else None))
    print(f"  {name} done {time.time()-t0:.0f}s  trades={len(legs)}", flush=True)

t = pd.DataFrame(rows)
t.to_csv("research/timeframes.csv", index=False)
pd.set_option("display.width", 250)
print("\n" + t.to_string(index=False))
print("\navail_over_spread = median points the signal offers / median spread.")
print("Below ~3 the cost structurally dominates whatever the signal knows.")
print("gross_t = t-statistic of gross points per trade. |t|>2 would be a real edge.")

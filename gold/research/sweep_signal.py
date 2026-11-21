"""Does the SIGNAL parameterisation matter? factor x atr_len grid, hold-to-flip."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))
import pandas as pd, numpy as np, replay

START = sys.argv[1] if len(sys.argv) > 1 else "2024-01-01"
df = pd.read_parquet("data/xauusd_m1.parquet")
df = df[df.dt >= START].reset_index(drop=True)
days = len(set(df.dt.dt.date))
print(f"bars {len(df):,}  trading days {days}  {df.dt.min()} -> {df.dt.max()}", flush=True)

rows = []
for atrp in (7, 10, 14):
    for fac in (1.2, 1.6, 2.0, 2.5, 3.0, 4.0, 6.0):
        t0 = time.time()
        legs, *_ = replay.build_legs(df, fac, atrp, spread_col="spread")
        n = len(legs)
        if not n:
            continue
        net = legs.net.sum(); gross = legs.gross.sum()
        se = legs.gross.std() / np.sqrt(n)          # is GROSS distinguishable from zero?
        rows.append(dict(
            atr=atrp, factor=fac, n=n, per_day=round(n / days, 1),
            gross_pt=round(gross, 0), gross_per_trade=round(gross / n, 4),
            gross_t_stat=round((gross / n) / se, 2) if se > 0 else 0,
            cost_pt=round(gross - net, 0),
            net_pt=round(net, 0), net_per_trade=round(net / n, 4),
            net_per_day=round(net / days, 2),
            avail_per_trade=round(legs.avail.mean(), 2),
            capture_pct=round(100 * net / legs.avail.sum(), 1),
            med_bars=int(legs.bars.median()),
            pct_1bar=round(100 * (legs.bars <= 1).mean(), 1),
            gbp_day=round(net * 0.733 / days, 2)))
        print(f"  atr{atrp} f{fac}: n={n} {time.time()-t0:.0f}s", flush=True)

t = pd.DataFrame(rows)
t.to_csv("research/sweep_signal.csv", index=False)
pd.set_option("display.width", 250)
print("\n" + t.to_string(index=False))

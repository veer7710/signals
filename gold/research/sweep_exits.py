"""Can EXITS rescue the live config (1.2 / ATR7)? Pre-registered acceptance test applied."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))
import pandas as pd, numpy as np, sim

df = pd.read_parquet("data/xauusd_m1.parquet")
df = df[df.dt >= "2024-01-01"].reset_index(drop=True)
legs = pd.read_parquet("research/legs_2024plus.parquet")
days = len(set(df.dt.dt.date))
print(f"legs {len(legs):,}  days {days}", flush=True)

base_tr = sim.simulate(df, legs, {}, spread=None)
W0 = base_tr.net[base_tr.net > 0].sum()
L0 = base_tr.net[base_tr.net <= 0].sum()
print(f"BENCHMARK hold-to-flip: net {base_tr.net.sum():+.0f}  winning pts {W0:+.0f}  losing pts {L0:+.0f}", flush=True)

grid = [("V0 hold-to-flip", {})]
for pts in (0.5, 0.8, 1.0, 1.5, 2.0):
    for nb in (1, 2, 3):
        grid.append((f"INFANT {pts}pt/{nb}bar", dict(infant_pts=pts, infant_bars=nb)))
for k in (1.0, 1.5, 2.0, 3.0):
    grid.append((f"STOP {k}ATR", dict(stop_mode="atr", stop_k=k)))
grid += [("STOP st_line", dict(stop_mode="st_line")),
         ("STOP st_line+1band", dict(stop_mode="st_line", stop_buffer_atr=0.6))]
for arm, give in ((2, 1), (3, 1.5), (4, 2), (6, 2)):
    grid.append((f"LOCK arm{arm}/give{give}", dict(lock_arm=arm, lock_give=give)))
for k, arm in ((1.5, 2), (2, 2), (3, 3)):
    grid.append((f"TRAIL {k}ATR arm{arm}", dict(trail_k=k, trail_arm=arm)))
for t in (2, 3, 4, 6, 10):
    grid.append((f"TARGET {t}pt", dict(target_pts=t)))
grid += [("TIME 5bar", dict(max_bars=5)), ("TIME 15bar", dict(max_bars=15)),
         ("TIME 30bar", dict(max_bars=30))]

rows = []
for label, pp in grid:
    tr = sim.simulate(df, legs, pp, spread=None)
    net = tr.net.sum()
    W = tr.net[tr.net > 0].sum(); L = tr.net[tr.net <= 0].sum()
    rows.append(dict(label=label, n=len(tr), net_pt=round(net, 0),
                     per_trade=round(net / len(tr), 4),
                     net_per_day=round(net / days, 2),
                     gbp_day=round(net * 0.733 / days, 2),
                     win_pts=round(W, 0), loss_pts=round(L, 0),
                     loss_removed_pct=round(100 * (1 - L / L0), 1),
                     win_removed_pct=round(100 * (1 - W / W0), 1),
                     med_bars=int(tr.bars.median()),
                     beats_bench=net > base_tr.net.sum()))
    print(f"  {label:24s} net {net:+9.0f}  /trade {net/len(tr):+.4f}", flush=True)

t = pd.DataFrame(rows).sort_values("net_pt", ascending=False)
t.to_csv("research/sweep_exits.csv", index=False)
pd.set_option("display.width", 260)
print("\n" + t.to_string(index=False))
print("\nPRE-REGISTERED ACCEPTANCE (PLAN 4.3): a cut is accepted only if it removes")
print(">=60% of losing points AND <25% of winning points.")
ok = t[(t.loss_removed_pct >= 60) & (t.win_removed_pct < 25)]
print(ok.to_string(index=False) if len(ok) else "  >>> NOTHING PASSES <<<")

"""Combine the two families that measured best, and find the true risk optimum."""
import sys, numpy as np
sys.path.insert(0,"research")
import core, backtest as bt
from run_drift import detrend
from run_mtf import signals as mtf_sig, htf_trend, split
from run_newfam import asia_break
from run_decisive import tstat, boot_ci
from run_funded import challenge

def apex_signals(d, htf=6, hema=20, slope=4, lema=50, trig=1,
                 use_mtf=True, use_asia=True, require_bias=True):
    """Union of the two families, both filtered by the SAME HTF bias so the
    engine has one opinion about direction at any moment."""
    T = htf_trend(d, htf, hema, slope)
    out = {}
    if use_mtf:
        for i,s in mtf_sig(d, htf, hema, slope, lema, trig): out[i]=s
    if use_asia:
        for i,s in asia_break(d):
            if not require_bias or T[i]==s: out.setdefault(i,s)
    return sorted(out.items())

EXIT=dict(mode="trail_atr",trail=3.0)
for sym,tf in [("GOLD","1h"),("GOLD","15m")]:
    d=detrend(core.load(sym,tf)); ins,oos=split(d)
    print(f"\n{'='*100}\n{sym} {tf}  APEX = MTF pullback + Asian break, one HTF bias\n{'='*100}")
    print(f"  {'variant':<40}{'n':>5}{'/day':>7}{'win%':>7}{'$/trd':>8}{'t':>6}{'PF':>6}{'CI95':>19}")
    for name,kw in [("MTF only",dict(use_asia=False)),
                    ("Asian only",dict(use_mtf=False)),
                    ("APEX union, bias-filtered",dict()),
                    ("APEX union, no bias filter",dict(require_bias=False))]:
        sg=apex_signals(d,**kw)
        if len(sg)<25: print(f"  {name:<40}{len(sg):>5}   too few"); continue
        r=bt.run(d,sg,stop_fn=bt.stop_struct(0.25),exit_cfg=EXIT,cost=0.15,max_bars=120)
        s=r.stats(); pts=[x["pts"] for x in r.t]; lo,hi=boot_ci(pts)
        print(f"  {name:<40}{s['n']:>5}{s['per_day']:>7.2f}{100*s['win']:>7.1f}"
              f"{s['pts']:>8.2f}{tstat(pts):>6.2f}{s['pf']:>6.2f}  [{lo:>6.2f},{hi:>6.2f}]")
    # out-of-sample on the union
    sg=apex_signals(oos)
    if len(sg)>=25:
        r=bt.run(oos,sg,stop_fn=bt.stop_struct(0.25),exit_cfg=EXIT,cost=0.15,max_bars=120)
        s=r.stats(); pts=[x["pts"] for x in r.t]
        print(f"  {'^ OUT-OF-SAMPLE HALF ONLY':<40}{s['n']:>5}{s['per_day']:>7.2f}"
              f"{100*s['win']:>7.1f}{s['pts']:>8.2f}{tstat(pts):>6.2f}{s['pf']:>6.2f}")

print(f"\n{'='*100}\nFUNDED SIZING -- fine sweep on the APEX trade distribution\n{'='*100}")
d=detrend(core.load("GOLD","1h")); sg=apex_signals(d)
r=bt.run(d,sg,stop_fn=bt.stop_struct(0.25),exit_cfg=EXIT,cost=0.15,max_bars=120)
Rs=np.array([x["R"] for x in r.t])
print(f"  {len(Rs)} trades  meanR {Rs.mean():+.3f}  win {100*(Rs>0).mean():.1f}%")
print(f"  {'risk':>8}{'P(pass)':>10}{'P(blow)':>10}{'P(run out)':>12}")
best=None
for risk in (0.001,0.0015,0.002,0.0025,0.003,0.004,0.005,0.0075,0.01,0.02):
    p,f_,t_=challenge(Rs,risk)
    if best is None or p>best[0]: best=(p,risk)
    print(f"  {100*risk:>7.2f}%{100*p:>9.1f}%{100*f_:>9.1f}%{100*t_:>11.1f}%")
print(f"  --> optimum {100*best[1]:.2f}% risk, P(pass) {100*best[0]:.1f}%")

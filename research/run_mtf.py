"""Walk-forward on the MTF family: tune on the first half ONLY, report the
second half. A parameter picked on the data it is reported on is not a result."""
import sys, numpy as np
sys.path.insert(0,"research")
import core, backtest as bt
from run_drift import detrend
from run_decisive import tstat, boot_ci

def htf_trend(d, htf, ema_n, slope):
    """HTF EMA slope, mapped to LTF bars with NO look-ahead: an HTF bar is
    only usable from the LTF bar on which it has fully closed."""
    n=d["n"]; H=core.resample(d,htf); he=core.ema(H["c"],ema_n)
    t=np.zeros(n,dtype=np.int8)
    for k in range(ema_n+slope, H["n"]):
        lo_=k*htf+htf-1
        if lo_>=n: break
        hi_=min((k+1)*htf+htf-1,n)
        t[lo_:hi_]= 1 if he[k]>he[k-slope] else (-1 if he[k]<he[k-slope] else 0)
    return t

def signals(d, htf, ema_n, slope, ltf_ema, trig):
    a=core.atr(d,14); n=d["n"]
    T=htf_trend(d,htf,ema_n,slope)
    e=core.ema(d["c"],ltf_ema)
    out=[]; armed=0
    for i in range(max(ema_n*htf, ltf_ema)+20, n-1):
        if np.isnan(a[i]) or a[i]<=0 or T[i]==0 or np.isnan(e[i]): continue
        dev=(d["c"][i]-e[i])/a[i]
        if T[i]==1:
            if dev < -0.0: armed=1
            elif armed==1 and d["c"][i] > d["h"][i-trig:i].max():
                out.append((i,1)); armed=0
        else:
            if dev > 0.0: armed=-1
            elif armed==-1 and d["c"][i] < d["l"][i-trig:i].min():
                out.append((i,-1)); armed=0
    return out

def split(d,frac=0.5):
    m=int(d["n"]*frac)
    a={k:(v[:m] if hasattr(v,"__len__") else v) for k,v in d.items()}; a["n"]=m
    b={k:(v[m:] if hasattr(v,"__len__") else v) for k,v in d.items()}; b["n"]=d["n"]-m
    return a,b

EXITS={"trail3":dict(mode="trail_atr",trail=3.0),
       "trail2":dict(mode="trail_atr",trail=2.0),
       "gb55arm1":dict(mode="giveback",give=0.55,arm=1.0)}

GRID=[(htf,en,sl,le,tg) for htf in (4,6) for en in (20,50) for sl in (2,4)
                        for le in (20,50) for tg in (1,3)]

for sym,tf in [("GOLD","1h"),("GOLD","15m")]:
    d=detrend(core.load(sym,tf)); ins,oos=split(d)
    print(f"\n{'='*104}\n{sym} {tf}  WALK-FORWARD  (tune on 1st half, report 2nd half)\n{'='*104}")
    best=None
    for g in GRID:
        for ename,ecfg in EXITS.items():
            sg=signals(ins,*g)
            if len(sg)<30: continue
            r=bt.run(ins,sg,stop_fn=bt.stop_struct(0.25),exit_cfg=ecfg,cost=0.15,max_bars=120)
            s=r.stats()
            if not s.get("n") or s["n"]<25: continue
            if best is None or s["pts"]>best[0]: best=(s["pts"],g,ename,ecfg,s)
    if best is None: print("  no cell qualified"); continue
    _,g,ename,ecfg,sIn=best
    print(f"  chosen on IN-SAMPLE only: htf={g[0]} htfEMA={g[1]} slope={g[2]} "
          f"ltfEMA={g[3]} trig={g[4]} exit={ename}")
    print(f"    in-sample : n={sIn['n']:<4} {sIn['pts']:+.2f}$/trd  win {100*sIn['win']:.1f}%")
    sg=signals(oos,*g)
    r=bt.run(oos,sg,stop_fn=bt.stop_struct(0.25),exit_cfg=ecfg,cost=0.15,max_bars=120)
    s=r.stats()
    if s.get("n"):
        pts=[x["pts"] for x in r.t]; lo,hi=boot_ci(pts)
        print(f"    OUT-OF-SAMPLE: n={s['n']:<4} {s['pts']:+.2f}$/trd  t={tstat(pts):+.2f}  "
              f"win {100*s['win']:.1f}%  PF {s['pf']:.2f}  CI[{lo:+.2f},{hi:+.2f}]  "
              f"{s['per_day']:.2f}/day")
    # best-of-N null: how good is the BEST of this many cells on noise?
    nCells=len(GRID)*len(EXITS)
    print(f"    cells searched: {nCells}. A best-of-{nCells} search on a driftless")
    print(f"    series routinely produces an in-sample winner; only the OOS line counts.")

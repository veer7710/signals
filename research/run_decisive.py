import sys, numpy as np, datetime as dt
sys.path.insert(0,"research")
import core, backtest as bt
from run_meanrev import mr_signals
from run_drift import detrend

def tstat(x):
    x=np.asarray(x,float)
    return float(x.mean()/(x.std(ddof=1)/np.sqrt(len(x)))) if len(x)>2 and x.std()>0 else 0.0

def boot_ci(x, reps=4000, seed=7):
    rng=np.random.default_rng(seed); x=np.asarray(x,float)
    m=[rng.choice(x,len(x),replace=True).mean() for _ in range(reps)]
    return float(np.percentile(m,2.5)), float(np.percentile(m,97.5))

def hours(d):
    return np.array([dt.datetime.utcfromtimestamp(int(t)).hour for t in d["t"]])

HI = {12,13,14,15,0,1}      # measured 1.29-1.82x median range
LO = {3,4,9,10,17,18,20,22} # measured 0.58-0.88x

def gate(d, keep):
    h=hours(d); return np.isin(h, list(keep))

# ---- signal families -------------------------------------------------
def pullback_cont(d, ema_n=50, pull=0.5, look=3):
    """Trend by EMA slope; enter on a PULLBACK that then resumes.
    Entry is NOT on the displacement bar -- that is the whole point."""
    a=core.atr(d,14); e=core.ema(d["c"],ema_n); n=d["n"]; out=[]; armed=0
    for i in range(ema_n+20,n-1):
        if np.isnan(a[i]) or a[i]<=0: continue
        up = e[i]>e[i-look]; dn = e[i]<e[i-look]
        dev=(d["c"][i]-e[i])/a[i]
        if up and dev<pull: armed=1
        elif dn and dev>-pull: armed=-1
        if armed==1 and up and d["c"][i]>d["h"][i-1] and dev>pull*0.5:
            out.append((i,1)); armed=0
        elif armed==-1 and dn and d["c"][i]<d["l"][i-1] and dev<-pull*0.5:
            out.append((i,-1)); armed=0
    return out

def orb(d, open_hour=13, win=4, look=16):
    """Session opening-range break: range of the `look` bars before the
    session hour; trade the first break of it."""
    h=hours(d); n=d["n"]; out=[]; done=set()
    for i in range(look+2,n-1):
        if h[i]!=open_hour: continue
        day=int(d["t"][i]//86400)
        if day in done: continue
        hi=d["h"][i-look:i].max(); lo=d["l"][i-look:i].min()
        for k in range(i,min(i+win,n-1)):
            if d["c"][k]>hi: out.append((k,1)); done.add(day); break
            if d["c"][k]<lo: out.append((k,-1)); done.add(day); break
    return out

def sweep_cont(d):
    from run_sweep_geom import sweep_trades
    return [(j-1,-s) for j,s,_,_ in sweep_trades(d)]

FAMS = {"pullback-continuation": pullback_cont,
        "momentum @1.5ATR stretch": lambda dd: [(i,-s) for i,s in mr_signals(dd,50,1.5,True)],
        "sweep continuation": sweep_cont,
        "opening-range break 13:00": orb}

if __name__ == "__main__":
    print(f"{'='*104}")
    print("DECISIVE PASS -- de-trended data only (so nothing is credited to gold's rally)")
    print("target 2R, stop struct+0.25ATR, cost $0.15/side, one position at a time")
    print(f"{'='*104}")
    for sym,tf in [("GOLD","1h"),("GOLD","15m")]:
        raw=core.load(sym,tf); d=detrend(raw)
        print(f"\n--- {sym} {tf} (de-trended, {d['n']} bars) ---")
        print(f"  {'family / hour gate':<40}{'n':>5}{'/day':>7}{'win%':>7}{'$/trd':>8}"
              f"{'t':>7}{'CI95':>18}{'capt':>7}")
        for fname,fn in FAMS.items():
            sig=fn(d)
            if not sig: continue
            for gname,mask in [("all hours",None),
                               ("HIGH-vol hrs",gate(d,HI)),
                               ("LOW-vol hrs",gate(d,LO))]:
                r=bt.run(d,sig,stop_fn=bt.stop_struct(0.25),
                         exit_cfg=dict(mode="fixed",rr=2.0),cost=0.15,
                         max_bars=80,session_mask=mask)
                s=r.stats()
                if not s.get("n") or s["n"]<20: continue
                pts=[x["pts"] for x in r.t]; lo_,hi_=boot_ci(pts)
                print(f"  {fname+' | '+gname:<40}{s['n']:>5}{s['per_day']:>7.2f}"
                      f"{100*s['win']:>7.1f}{s['pts']:>8.2f}{tstat(pts):>7.2f}"
                      f"  [{lo_:>6.2f},{hi_:>6.2f}]{s['capture']:>7.2f}")

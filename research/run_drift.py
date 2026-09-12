import sys, numpy as np
sys.path.insert(0,"research")
import core, backtest as bt
from run_meanrev import mr_signals

def by_side(r):
    L=[x["pts"] for x in r.t if x["dir"]>0]; S=[x["pts"] for x in r.t if x["dir"]<0]
    return L,S

def detrend(d):
    """Remove the sample's average per-bar log drift, keeping every bar's
    shape and range intact. If an 'edge' survives only on the trending
    series, it was the trend."""
    lc = np.log(d["c"]); n=d["n"]
    mu = (lc[-1]-lc[0])/(n-1)
    adj = np.exp(-mu*np.arange(n))
    return dict(t=d["t"], o=d["o"]*adj, h=d["h"]*adj, l=d["l"]*adj,
                c=d["c"]*adj, n=n)

def direction_matched_null(d, sigs, rr, cost, reps=150, seed=3):
    """Same NUMBER of longs and shorts, same exit geometry, random times.
    This is what the sample's drift pays with no skill at all."""
    rng=np.random.default_rng(seed); nL=sum(1 for _,s in sigs if s>0); nS=len(sigs)-nL
    a=core.atr(d,14); ok=np.nonzero(~np.isnan(a)&(a>0))[0]; ok=ok[(ok>60)&(ok<d["n"]-120)]
    tot=[]
    for _ in range(reps):
        idx=rng.choice(ok,size=len(sigs),replace=True)
        dirs=np.array([1]*nL+[-1]*nS); rng.shuffle(dirs)
        r=bt.run(d, list(zip(idx.tolist(),dirs.tolist())),
                 stop_fn=bt.stop_struct(0.25),
                 exit_cfg=dict(mode="fixed",rr=rr),cost=cost,max_bars=80,
                 one_at_a_time=False)
        s=r.stats()
        if s.get("n"): tot.append(s["pts"])
    return np.array(tot)

if __name__ == "__main__":
    for sym,tf in [("GOLD","1h"),("GOLD","15m")]:
        d=core.load(sym,tf); dt_=detrend(d)
        drift=100*(d["c"][-1]/d["c"][0]-1)
        print(f"\n{'='*94}\n{sym} {tf}: sample drift {drift:+.1f}%  "
              f"-- testing whether 'momentum' is just that drift\n{'='*94}")
        print(f"  {'test':<40}{'n':>5}{'win%':>7}{'$/trd':>9}{'long$':>9}{'short$':>9}{'null$':>9}{'edge':>8}")
        for rr in (1.0,2.0):
            sig=mr_signals(d,50,1.5,True)
            mom=[(i,-s) for i,s in sig]
            for name,ss,use in [(f"momentum {rr}R  ON TRENDING data",mom,d),
                                (f"momentum {rr}R  ON DE-TRENDED data",mom,dt_),
                                (f"fade     {rr}R  ON DE-TRENDED data",sig,dt_)]:
                if use is dt_:
                    s2=mr_signals(dt_,50,1.5,True)
                    ss = [(i,-x) for i,x in s2] if name.startswith("momentum") else s2
                r=bt.run(use,ss,stop_fn=bt.stop_struct(0.25),
                         exit_cfg=dict(mode="fixed",rr=rr),cost=0.15,max_bars=80)
                st=r.stats()
                if not st.get("n"): continue
                L,S=by_side(r)
                nul=direction_matched_null(use,ss,rr,0.15)
                edge=st["pts"]-nul.mean()
                print(f"  {name:<40}{st['n']:>5}{100*st['win']:>7.1f}{st['pts']:>9.2f}"
                      f"{np.mean(L) if L else 0:>9.2f}{np.mean(S) if S else 0:>9.2f}"
                      f"{nul.mean():>9.2f}{edge:>8.2f}")

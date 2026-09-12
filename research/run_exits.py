import sys, numpy as np
sys.path.insert(0,"research")
import core, backtest as bt
from run_drift import detrend
from run_decisive import pullback_cont, sweep_cont, tstat, boot_ci
from run_meanrev import mr_signals

def all_entries(d):
    """Pool every entry family into ONE fixed set, then vary only the exit.
    Same trades, same bars, same direction -- so any difference is the exit
    and nothing else."""
    s = {}
    for fn in (pullback_cont, sweep_cont,
               lambda dd: [(i,-x) for i,x in mr_signals(dd,50,1.5,True)]):
        for i,sd in fn(d): s.setdefault(i, sd)
    return sorted(s.items())

EXITS = {
 "fixed 1R":            dict(mode="fixed", rr=1.0),
 "fixed 2R":            dict(mode="fixed", rr=2.0),
 "fixed 3R":            dict(mode="fixed", rr=3.0),
 "giveback 60% (CURRENT SNIPER)": dict(mode="giveback", give=0.60, arm=0.0),
 "giveback 40%":        dict(mode="giveback", give=0.40, arm=0.0),
 "giveback 25%":        dict(mode="giveback", give=0.25, arm=0.0),
 "giveback 60%, arm 1R":dict(mode="giveback", give=0.60, arm=1.0),
 "giveback 25%, arm 1R":dict(mode="giveback", give=0.25, arm=1.0),
 "ATR trail 1.0":       dict(mode="trail_atr", trail=1.0),
 "ATR trail 2.0":       dict(mode="trail_atr", trail=2.0),
 "ATR trail 3.0":       dict(mode="trail_atr", trail=3.0),
 "ratchet lock 0.5R":   dict(mode="lock", lock_step=0.5),
 "ratchet lock 1.0R":   dict(mode="lock", lock_step=1.0),
 "hybrid 3R + lock0.5R":dict(mode="hybrid", rr=3.0, lock_step=0.5),
 "fixed 2R + stall 25": dict(mode="fixed", rr=2.0, stall=25),
 "ATR trail 2.0 + stall 25": dict(mode="trail_atr", trail=2.0, stall=25),
}

def deep(r):
    """The metrics that answer 'it went to £15 and closed at £4'."""
    t=r.t
    if not t: return None
    pk=np.array([x["peak_R"] for x in t]); R=np.array([x["R"] for x in t])
    good = pk>=0.5                      # trades that were meaningfully up
    cap  = R[good]/pk[good] if good.sum() else np.array([np.nan])
    gave = ((pk>=1.0)&(R<=0)).sum()     # reached +1R then closed at a LOSS
    n1 = (pk>=1.0).sum()
    return dict(capture_good=float(np.nanmean(cap)),
                gaveback_all=float(gave/n1) if n1 else float("nan"),
                n_good=int(good.sum()))

if __name__ == "__main__":
    for sym,tf in [("GOLD","1h"),("GOLD","15m")]:
        raw=core.load(sym,tf); d=detrend(raw)
        sig=all_entries(d)
        print(f"\n{'='*108}")
        print(f"{sym} {tf} DE-TRENDED -- SAME {len(sig)} entries, ONLY the exit changes "
              f"(cost $0.15/side)")
        print(f"{'='*108}")
        print(f"  {'exit rule':<32}{'n':>5}{'win%':>7}{'$/trd':>8}{'t':>6}"
              f"{'capt*':>7}{'gaveback':>10}{'avgW':>8}{'avgL':>8}{'maxDD':>8}")
        rows=[]
        for name,cfg in EXITS.items():
            r=bt.run(d,sig,stop_fn=bt.stop_struct(0.25),exit_cfg=cfg,
                     cost=0.15,max_bars=120)
            s=r.stats(); dd=deep(r)
            if not s.get("n") or not dd: continue
            pts=np.array([x["pts"] for x in r.t])
            w=pts[pts>0]; l=pts[pts<=0]
            rows.append((s["pts"],name,s,dd,tstat(pts),
                         float(w.mean()) if len(w) else 0,
                         float(l.mean()) if len(l) else 0))
        for v,name,s,dd,t_,aw,al in sorted(rows,reverse=True):
            star="  <<<" if "CURRENT" in name else ""
            print(f"  {name:<32}{s['n']:>5}{100*s['win']:>7.1f}{s['pts']:>8.2f}"
                  f"{t_:>6.2f}{dd['capture_good']:>7.2f}"
                  f"{100*dd['gaveback_all']:>9.0f}%{aw:>8.2f}{al:>8.2f}"
                  f"{s['maxdd_pts']:>8.0f}{star}")
        print("  capt* = exit-R / peak-R on trades that reached >= 0.5R peak")
        print("  gaveback = % of trades that reached +1R peak and still closed at a LOSS")

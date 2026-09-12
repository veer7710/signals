"""Regenerates every number quoted in docs/FINDINGS.md. Run before shipping."""
import sys, numpy as np
sys.path.insert(0,"research")
import core, backtest as bt
from run_drift import detrend
from run_exits import all_entries, deep
from run_decisive import tstat, boot_ci, pullback_cont, sweep_cont, gate, HI
from run_meanrev import mr_signals

SHIP = {
 "SNIPER v1 (broken: giveback .60 armed at 0R)": dict(mode="giveback",give=0.60,arm=0.0),
 "SNIPER v2 (giveback .55 armed at 1.0R)":       dict(mode="giveback",give=0.55,arm=1.0),
 "SNIPER v2-wide (ATR trail 3.0)":               dict(mode="trail_atr",trail=3.0),
}
print("="*100)
print("SHIPPING CONFIG VALIDATION -- de-trended gold, cost $0.15/side, stop struct+0.25ATR")
print("="*100)
for sym,tf in [("GOLD","15m"),("GOLD","1h")]:
    d=detrend(core.load(sym,tf)); sig=all_entries(d)
    print(f"\n--- {sym} {tf}  ({len(sig)} entry events) ---")
    print(f"  {'config':<46}{'n':>5}{'win%':>7}{'$/trd':>8}{'avgW':>8}{'avgL':>8}"
          f"{'PF':>6}{'capt*':>7}{'maxDD$':>8}")
    store={}
    for name,cfg in SHIP.items():
        r=bt.run(d,sig,stop_fn=bt.stop_struct(0.25),exit_cfg=cfg,cost=0.15,max_bars=120)
        s=r.stats(); dd=deep(r)
        pts=np.array([x["pts"] for x in r.t])
        # PAIRED arm must NOT gate on position availability, otherwise the two
        # arms trade different bars and the comparison stops being paired.
        rp=bt.run(d,sig,stop_fn=bt.stop_struct(0.25),exit_cfg=cfg,cost=0.15,
                  max_bars=120,one_at_a_time=False)
        store[name]={x["i"]:x["pts"] for x in rp.t}
        w=pts[pts>0]; l=pts[pts<=0]
        print(f"  {name:<46}{s['n']:>5}{100*s['win']:>7.1f}{s['pts']:>8.2f}"
              f"{(w.mean() if len(w) else 0):>8.2f}{(l.mean() if len(l) else 0):>8.2f}"
              f"{s['pf']:>6.2f}{dd['capture_good']:>7.2f}{s['maxdd_pts']:>8.0f}")
    k0="SNIPER v1 (broken: giveback .60 armed at 0R)"
    for name in SHIP:
        if name==k0: continue
        ks=sorted(set(store[k0])&set(store[name]))
        df=np.array([store[name][k]-store[k0][k] for k in ks])
        lo,hi=boot_ci(df)
        print(f"    paired vs v1: {name[:34]:<36}{df.mean():+7.2f}$/trd  "
              f"t={tstat(df):+5.2f}  CI[{lo:+.2f},{hi:+.2f}]  n={len(ks)}")

print("\n"+"="*100)
print("HOUR GATE: same strategy, high-vol hours vs low-vol hours (de-trended 1h)")
print("="*100)
d=detrend(core.load("GOLD","1h")); sig=all_entries(d)
for gname,mask in [("all hours",None),("high-vol hours only",gate(d,HI))]:
    r=bt.run(d,sig,stop_fn=bt.stop_struct(0.25),
             exit_cfg=dict(mode="trail_atr",trail=3.0),cost=0.15,
             max_bars=120,session_mask=mask)
    s=r.stats(); pts=[x["pts"] for x in r.t]
    print(f"  {gname:<24}n={s['n']:<5} $/trd {s['pts']:+.2f}  t={tstat(pts):+.2f}  "
          f"win {100*s['win']:.1f}%  total ${s['total']:+.0f}")

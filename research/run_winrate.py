"""
The win-rate frontier: how high can win rate go while expectancy stays
positive? Partials + breakeven raise the headline win rate; the question is
what they cost. Same APEX entries, only the exit structure changes.
"""
import sys, numpy as np, itertools
sys.path.insert(0,"research")
import core, backtest as bt, staged
from run_drift import detrend
from run_apex import apex_signals

def frontier(sym, tf):
    d=detrend(core.load(sym,tf)); sg=apex_signals(d)
    days=(d["t"][-1]-d["t"][0])/86400*5/7
    rows=[]
    for tp1,f1,be,lock,tr,arm in itertools.product(
            (0.25,0.4,0.5,0.75,1.0), (0.3,0.5,0.7,0.85),
            (0,1), (0.0,0.1), (2.0,3.0), (1.0,)):
        cfg=dict(tp1_R=tp1,f1=f1,trail_atr=tr,arm_R=arm,
                 be_at_R=(tp1 if be else 0.0), be_lock_R=lock)
        t=staged.run_staged(d,sg,stop_fn=bt.stop_struct(0.25),cfg=cfg,
                            cost=0.15,max_bars=160)
        s=staged.summarise(t,days)
        if s["n"]<40: continue
        s.update(tp1=tp1,f1=f1,be=be,lock=lock,tr=tr)
        rows.append(s)
    # baseline: no partial at all
    t=staged.run_staged(d,sg,stop_fn=bt.stop_struct(0.25),
        cfg=dict(trail_atr=3.0,arm_R=1.0),cost=0.15,max_bars=160)
    base=staged.summarise(t,days); base.update(tp1=0,f1=0,be=0,lock=0,tr=3.0)
    return rows, base, days

for sym,tf in [("GOLD","1h"),("GOLD","15m")]:
    rows,base,days=frontier(sym,tf)
    print(f"\n{'='*104}")
    print(f"{sym} {tf}  WIN-RATE FRONTIER  ({len(rows)} exit structures, same entries)")
    print(f"{'='*104}")
    print(f"  baseline (pure trail, no partial): win {100*base['win']:.1f}%  "
          f"${base['pts']:+.2f}/trade  PF {base['pf']:.2f}  t={base['t_']:+.2f}")
    pos=[r for r in rows if r["pts"]>0]
    print(f"  {len(pos)} of {len(rows)} structures keep expectancy positive")
    print(f"\n  HIGHEST WIN RATE with expectancy still positive:")
    print(f"  {'tp1':>5}{'f1':>6}{'BE':>4}{'lock':>6}{'trail':>6}{'n':>5}"
          f"{'win%':>7}{'$/trd':>8}{'PF':>6}{'t':>6}{'avgW':>8}{'avgL':>8}")
    for r in sorted(pos,key=lambda x:-x["win"])[:10]:
        print(f"  {r['tp1']:>5.2f}{r['f1']:>6.2f}{r['be']:>4}{r['lock']:>6.2f}"
              f"{r['tr']:>6.1f}{r['n']:>5}{100*r['win']:>7.1f}{r['pts']:>8.2f}"
              f"{r['pf']:>6.2f}{r['t_']:>6.2f}{r['avgW']:>8.2f}{r['avgL']:>8.2f}")
    print(f"\n  HIGHEST EXPECTANCY:")
    for r in sorted(pos,key=lambda x:-x["pts"])[:5]:
        print(f"  {r['tp1']:>5.2f}{r['f1']:>6.2f}{r['be']:>4}{r['lock']:>6.2f}"
              f"{r['tr']:>6.1f}{r['n']:>5}{100*r['win']:>7.1f}{r['pts']:>8.2f}"
              f"{r['pf']:>6.2f}{r['t_']:>6.2f}{r['avgW']:>8.2f}{r['avgL']:>8.2f}")

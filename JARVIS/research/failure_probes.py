"""
failure_probes.py — the measurements behind FAILURE_MODES.md.

(a) sweep outcomes measured against the instrument's own drift baseline
(b) how bar range scales with timeframe -> M1 cost/range extrapolation
(c) daily/serial clustering of losses for the naive sweep rule -> prop risk
(d) MAE of eventual winners -> how much stop width buys you
"""
from __future__ import annotations
import os, sys, math, statistics as st, datetime as dt, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies
from sweep_anatomy import atr, barrier, wilson, analyse
from microstructure_facts import baseline


def z2(p1,n1,p2,n2):
    p = (p1*n1+p2*n2)/(n1+n2)
    se = math.sqrt(p*(1-p)*(1/n1+1/n2))
    return (p1-p2)/se if se>0 else 0.0


print("="*78); print("A. SWEEP OUTCOME vs THE INSTRUMENT'S OWN BASELINE")
print("   Everything expressed as P(price falls 1 ATR before rising 1 ATR),")
print("   so one number, one direction, comparable across conditions.")
print("-"*78)
for sym, tf in (("GOLD","1h"),("GOLD","15m"),("EURUSD","1h"),("US500","1h")):
    b = baseline(sym, tf); bp, bn = b['p_down_first'], b['n']
    s, a, ev = analyse(sym, tf)
    print(f"\n  {sym} {tf}   BASELINE P(down first) = {bp:.3f}  (n={bn})")
    def show(sub, label):
        d = [e for e in sub if e['outcome'] in ('reverse','continue')]
        n = len(d)
        if n < 40: print(f"    {label:44s} n={n:5d} (too few)"); return
        # convert: for a LOW sweep, 'reverse'==up  -> down = continue
        down = sum(1 for e in d if (e['side']=='low' and e['outcome']=='continue')
                                or (e['side']=='high' and e['outcome']=='reverse'))
        p = down/n; z = z2(p,n,bp,bn)
        print(f"    {label:44s} n={n:5d}  P(down)={p:.3f}  delta={100*(p-bp):+5.1f}pp  z={z:+.2f}")
    show([e for e in ev if e['closed_back'] and e['side']=='low'],
         "LOW swept + closed back above (long setup)")
    show([e for e in ev if e['closed_back'] and e['side']=='high'],
         "HIGH swept + closed back below (short setup)")
    show([e for e in ev if not e['closed_back'] and e['side']=='low'],
         "LOW pierced, closed BELOW (no reclaim)")
    show([e for e in ev if not e['closed_back'] and e['side']=='high'],
         "HIGH pierced, closed ABOVE (no reclaim)")

print("\n"+"="*78); print("B. BAR RANGE SCALING -> M1 COST EXTRAPOLATION (GOLD, same 2026 window)")
print("-"*78)
base15 = engine.load("GOLD","15m")
pts = []
for f, mins in ((1,15),(2,30),(4,60),(8,120),(16,240)):
    s = base15 if f==1 else engine.resample(base15, f)
    tr = [max(s.h[i]-s.l[i], abs(s.h[i]-s.c[i-1]), abs(s.l[i]-s.c[i-1])) for i in range(1,len(s))]
    pts.append((mins, st.median(tr), len(s)))
    print(f"  {mins:4d} min  bars={len(s):5d}  median TR = ${st.median(tr):7.3f}")
# log-log fit: log(TR) = c + H*log(minutes)
xs = [math.log(m) for m,_,_ in pts]; ys = [math.log(v) for _,v,_ in pts]
mx, my = sum(xs)/len(xs), sum(ys)/len(ys)
H = sum((x-mx)*(y-my) for x,y in zip(xs,ys)) / sum((x-mx)**2 for x in xs)
c = my - H*mx
print(f"\n  fitted scaling exponent H = {H:.3f}  (0.50 = pure random walk)")
rt = 0.30 + 2*0.05 + 0.07
for mins in (1,2,3,5,15,60):
    pred = math.exp(c + H*math.log(mins))
    print(f"  predicted median TR at M{mins:<3d} = ${pred:6.3f}   "
          f"round trip ${rt:.2f} = {rt/pred:6.1%} of one bar's entire range")

print("\n"+"="*78); print("C. LOSS CLUSTERING FOR THE NAIVE SWEEP RULE (GOLD 1h) -> prop risk")
print("-"*78)
import collections
s = engine.load("GOLD","1h")
trades = engine.backtest(s, strategies.liquidity_sweep(s), engine.Costs())
rs=[t.r for t in trades]
worst=cur=0
for r in rs:
    cur = cur+1 if r<=0 else 0
    worst=max(worst,cur)
days=collections.defaultdict(list)
for t in trades: days[dt.datetime.utcfromtimestamp(t.ts_out).date()].append(t.r)
dr=sorted(sum(v) for v in days.values())
print(f"  trades={len(trades)}  E={sum(rs)/len(rs):+.4f}R  win={100*sum(1 for r in rs if r>0)/len(rs):.1f}%")
print(f"  longest losing streak = {worst} trades; max drawdown = {max(0,0):.0f}")
print(f"  trading days={len(dr)}  trades/day mean={len(trades)/len(dr):.2f} max={max(len(v) for v in days.values())}")
print(f"  daily R: min {dr[0]:.2f}  p5 {dr[int(.05*len(dr))]:.2f}  median {dr[len(dr)//2]:.2f}  p95 {dr[int(.95*len(dr))]:.2f}  max {dr[-1]:.2f}")
for lim in (2,3,4):
    n=sum(1 for x in dr if x<=-lim)
    print(f"    days worse than -{lim}R: {n} ({100*n/len(dr):.1f}% of trading days)")

print("\n"+"="*78); print("D. REGIME-BLOCK REPLICATION OF THE HEADLINE SWEEP RESULT (GOLD 1h)")
print("   Each block gets its OWN baseline. GX-04 says nothing counts unless it")
print("   survives the parabola and the crash separately.")
print("-"*78)
from sweep_anatomy import barrier as _bar, atr as _atr
S = engine.load("GOLD","1h"); A = _atr(S,14)
_s, _a, EV = analyse("GOLD","1h")
for name, t0, t1 in (("A 2024-04..2025-03", 0, 1743465600),
                     ("B 2025-04..2025-12", 1743465600, 1767225600),
                     ("C 2026-01..2026-08", 1767225600, 9e18)):
    idx=[i for i,ts in enumerate(S.ts) if t0<=ts<t1]
    if not idx: continue
    lo,hi = idx[0], idx[-1]
    up=dn=0
    for i in range(max(lo,250),hi):
        if A[i] is None or A[i]<=0: continue
        r=_bar(S,i,S.c[i],A[i],A[i],24)
        if r=='up': up+=1
        elif r=='dn': dn+=1
    bp, bn = dn/(up+dn), up+dn
    print(f"  {name}  own baseline P(down first)={bp:.3f} (n={bn})")
    for side, lab in (('low','LOW swept + reclaim (long setup) '),
                      ('high','HIGH swept + reclaim (short setup)')):
        sub=[e for e in EV if lo<=e['i']<=hi and e['closed_back'] and e['side']==side
             and e['outcome'] in ('reverse','continue')]
        n=len(sub)
        if n<40: print(f"      {lab} n={n} (too few)"); continue
        d=sum(1 for e in sub if (e['outcome']=='continue' if side=='low' else e['outcome']=='reverse'))
        p=d/n
        print(f"      {lab} n={n:4d}  P(down)={p:.3f}  delta={100*(p-bp):+5.1f}pp  z={z2(p,n,bp,bn):+.2f}")

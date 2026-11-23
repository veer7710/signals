"""
HIS HYPOTHESIS, tested directly:
  "we go into profit and don't take it. M1 trends are small - 20p to 3-5 pounds.
   And there's no trailing SL or even break-even here."
Both are fair. Break-even specifically was NEVER tested on its own before - the earlier
sweep only had profit LOCKS (arm X, give back Y), not "once +X, move the stop to entry".
Everything is priced at HIS broker's spread (0.320), not the feed's (0.168).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))
import pandas as pd, numpy as np

df = pd.read_parquet("data/xauusd_m1.parquet")
df = df[df.dt >= "2024-01-01"].reset_index(drop=True)      # SAME slice the legs index into
legs = pd.read_parquet("research/legs_2024plus.parquet")
STRIDE = 3
legs = legs.iloc[::STRIDE].copy()
o, h, l = df.open.values, df.high.values, df.low.values
n = len(df); days = len(set(df.dt.dt.date)) / STRIDE
GBP = 0.767; SPREAD_HIS = 0.320
print(f"legs {len(legs):,} (every {STRIDE}rd)  spread {SPREAD_HIS} = his broker\n", flush=True)

def run(stop_atr=1.5, target_atr=0.0, be_arm=0.0, trail_atr=0.0, trail_arm=0.0,
        spread=SPREAD_HIS):
    """be_arm: once profit >= be_arm*ATR, stop moves to entry+spread (true break-even)."""
    tot=0.0; wins=0; wsum=0.0; lsum=0.0; nl=0
    for r in legs.itertuples(index=False):
        d, e = r.dir, r.entry_i
        if e >= n-1: continue
        atr = r.atr if r.atr == r.atr else 1.0
        entry = o[e] + spread if d > 0 else o[e]
        adj = 0.0 if d > 0 else spread
        stop = entry - d*stop_atr*atr if stop_atr > 0 else None
        tgt  = entry + d*target_atr*atr if target_atr > 0 else None
        peak = 0.0; ext = entry; out = None
        for bi in range(e, min(r.exit_i, n-1)):
            hi, lo = h[bi]+adj, l[bi]+adj
            if stop is not None and ((lo <= stop) if d > 0 else (hi >= stop)):
                out = stop; break                       # protective level first
            if tgt is not None and ((hi >= tgt) if d > 0 else (lo <= tgt)):
                out = tgt; break
            fav = (hi-entry)*d if d > 0 else (entry-lo)*d*-1
            fav = (hi-entry) if d > 0 else (entry-lo)
            if fav > peak:
                peak = fav; ext = hi if d > 0 else lo
            if be_arm > 0 and peak >= be_arm*atr:        # true break-even
                lvl = entry + d*spread
                stop = lvl if stop is None else (max(stop,lvl) if d>0 else min(stop,lvl))
            if trail_atr > 0 and peak >= trail_arm*atr:
                lvl = ext - d*trail_atr*atr
                stop = lvl if stop is None else (max(stop,lvl) if d>0 else min(stop,lvl))
        if out is None:
            xi = min(r.exit_i, n-1); out = o[xi] + adj
        p = (out-entry)*d
        tot += p
        if p > 0: wins += 1; wsum += p
        else: nl += 1; lsum += p
    N = len(legs)
    return dict(net=tot, per=tot/N, wr=100*wins/N, aw=wsum/max(wins,1),
                al=lsum/max(nl,1), gbp_day=tot*GBP/days)

print("="*88)
print("A. WHAT HIS BROKER'S SPREAD ALONE COSTS (stop 1.5 ATR, hold to flip)")
print("="*88)
for sp,lab in ((0.168,"my feed (Exness)"),(0.320,"HIS broker (PU Prime, +90%)")):
    r=run(spread=sp); print(f"  spread {sp:.3f}  {lab:28s} {r['per']:+.3f} pt/trade  {r['gbp_day']:+.2f} GBP/day")

print("\n"+"="*88)
print("B. BREAK-EVEN AND TRAILING — the two he says are missing. stop 1.5 ATR throughout.")
print("="*88)
print(f"  {'rule':<34}{'net/trade':>11}{'win%':>8}{'avg win':>9}{'avg loss':>10}{'GBP/day':>9}")
rows=[("nothing (as shipped)",dict()),
      ("break-even at +0.25 ATR",dict(be_arm=0.25)),
      ("break-even at +0.50 ATR",dict(be_arm=0.5)),
      ("break-even at +1.00 ATR",dict(be_arm=1.0)),
      ("break-even at +1.50 ATR",dict(be_arm=1.5)),
      ("trail 0.5 ATR from +0.5 ATR",dict(trail_atr=0.5,trail_arm=0.5)),
      ("trail 1.0 ATR from +1.0 ATR",dict(trail_atr=1.0,trail_arm=1.0)),
      ("BE +0.5 then trail 1.0 ATR",dict(be_arm=0.5,trail_atr=1.0,trail_arm=1.5))]
best=None
for lab,kw in rows:
    r=run(**kw)
    print(f"  {lab:<34}{r['per']:>+11.3f}{r['wr']:>7.1f}%{r['aw']:>9.2f}{r['al']:>10.2f}{r['gbp_day']:>+9.2f}")
    if best is None or r['per']>best[0]: best=(r['per'],lab,r)

print("\n"+"="*88)
print("C. BANK EARLY: stop (rows) x target (cols), both in ATR. net pt/trade.")
print("="*88)
tg=[0.25,0.5,0.75,1.0,1.5,2.0,0]
print("  stop\\tgt"+"".join([f"{(('%.2f'%t) if t>0 else 'hold'):>9}" for t in tg]))
for s in (0.5,1.0,1.5,2.0,3.0):
    row=f"  {s:>7.2f} "
    for t in tg:
        r=run(stop_atr=s,target_atr=t)
        row+=f"{r['per']:>9.3f}"
        if r['per']>best[0]: best=(r['per'],f"stop {s} ATR / target {t} ATR",r)
    print(row,flush=True)

b=best[2]
print(f"\n  BEST OF EVERYTHING TESTED: {best[1]}")
print(f"    {b['per']:+.3f} pt/trade   {b['gbp_day']:+.2f} GBP/day   win {b['wr']:.1f}%")
be=abs(b['al'])/(b['aw']+abs(b['al']))*100
print(f"    needs {be:.1f}% to break even, gets {b['wr']:.1f}% -> "
      f"{'CLEARS' if b['wr']>be else 'SHORT by %.1f points'%(be-b['wr'])}")

print("\n"+"="*88)
print("D. WHY IT CANNOT WORK: win rate rises exactly as fast as the average win falls")
print("="*88)
print(f"  {'target':>10}{'win rate':>10}{'avg win':>10}{'avg loss':>10}{'product':>10}")
for t in (0.25,0.5,1.0,2.0,0):
    r=run(stop_atr=1.5,target_atr=t)
    print(f"  {('hold' if t==0 else '%.2f ATR'%t):>10}{r['wr']:>9.1f}%{r['aw']:>10.2f}"
          f"{r['al']:>10.2f}{r['per']:>+10.3f}")

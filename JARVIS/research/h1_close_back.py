"""
E-130 / H-1 — WAS IT ACTUALLY A SWEEP? The one rule the whole field agrees on.

From the ICT/SMC research (JARVIS/lab/ICT_SMC_RESEARCH.md): across every
practitioner source and every open-source implementation reviewed, exactly three
rules are universal. The first is:

    A break of a level is a SWEEP only if price CLOSES BACK INSIDE it.
    Otherwise it is a breakout, and it is not the same trade.

System A (E-127) does not test this. Its limit rests past the level and fills on
the touch - identically whether price rejects and reverses, or slices through and
keeps going. **E-122 measured MFE/|MAE| = 0.96 on these fills, which is precisely
the signature of two populations averaged together.**

TWO WAYS TO USE THE RULE, and only one of them is honest:
  WRONG   fill at the limit, then keep the trade only if a close-back happens.
          That is a filter applied with information from after the entry.
  RIGHT   do not enter at the touch at all. WAIT for the bar that closes back
          inside the level, and enter at ITS close. Later entry, worse price,
          but every trade is a confirmed rejection.

Only the second is implemented. It costs entry price and trade count; the
question is whether the population it selects is enough better to pay for both.

Also relevant, and recorded because it cuts against the reversal reading:
Osler (2003, 2005) documents real stop clustering at round numbers from an
actual bank order book - but the documented behaviour at a cluster is
ACCELERATION THROUGH IT, not reversal. So this rule is not obviously right, and
that is exactly why it is being measured rather than assumed.
"""
from __future__ import annotations
import os, sys, statistics, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
from engine import atr as watr
from liq_m1 import load, GBP
from supertrend_rescue import st_state
from st_context_liq_entry import swings

TODAY = 7.38

s1, SP1 = load("M1")
A1 = watr(s1, 14)
va = sorted(x for x in A1[100:] if x); med_a = va[len(va)//2]
med_sp = statistics.median(SP1)
d1, fu1, fl1 = st_state(s1, 7, 1.2)
days = len(s1)/1440
Z = swings(s1, 5)


def run(confirm_bars, ratio=0.11, past=0.5, stop_a=4.0, hold=240, cool=120,
        need_dir=True, collect=False):
    """confirm_bars = -1 : enter at the touch (System A as it ships)
       confirm_bars >= 0 : wait for a bar that CLOSES back inside the level,
                           within that many bars of the touch, and enter at its
                           close. Abandon the setup if it never does."""
    cs = ratio/(med_sp/med_a)
    tot, busy, paths = [], -1, []
    for (i0, px, dr) in Z:
        if i0 <= busy: continue
        a = A1[i0]
        if not a or a <= 0: continue
        side = 1 if dr == -1 else -1
        if need_dir:
            st = d1[i0]
            if not ((st == -1 and side > 0) or (st == 1 and side < 0)): continue
        lvl = px - side*past*a
        j = None
        for k in range(i0+1, min(i0+61, len(s1))):
            if (side == 1 and s1.l[k] <= lvl) or (side == -1 and s1.h[k] >= lvl):
                j = k; break
        if j is None: continue

        if confirm_bars < 0:
            e_bar = j
            entry = lvl + side*SP1[j]*cs/2.0
        else:
            # THE RULE: a close back on the far side of the LEVEL ITSELF (px),
            # not of the limit. The level is what was swept.
            e_bar = None
            for k in range(j, min(j+confirm_bars+1, len(s1))):
                back = (s1.c[k] > px) if side > 0 else (s1.c[k] < px)
                if back: e_bar = k; break
            if e_bar is None: continue
            entry = s1.c[e_bar] + side*SP1[e_bar]*cs/2.0

        sl = entry - side*stop_a*a
        po = None
        for k in range(e_bar, min(e_bar+hold, len(s1))):
            if (side > 0 and s1.l[k] <= sl) or (side < 0 and s1.h[k] >= sl):
                po, kk = sl, k; break
            band = fl1[k] if side > 0 else fu1[k]
            if band is not None:
                sl = max(sl, band) if side > 0 else min(sl, band)
        if po is None:
            kk = min(e_bar+hold, len(s1)-1); po = s1.c[kk]
        pts = side*((po - side*SP1[kk]*cs/2.0) - entry)
        tot.append(pts)
        if collect:
            mfe = mae = 0.0
            for k in range(e_bar, min(e_bar+hold, len(s1))):
                f = side*((s1.h[k] if side > 0 else s1.l[k]) - entry)
                d = side*((s1.l[k] if side > 0 else s1.h[k]) - entry)
                if f > mfe: mfe = f
                if d < mae: mae = d
            paths.append((mfe, mae))
        busy = kk + cool
    return (tot, paths) if collect else tot


def main():
    print("="*96)
    print("  E-130 / H-1 — enter only on a CONFIRMED close back inside the level")
    print("  The one rule every ICT/SMC source and implementation agrees on.")
    print("="*96)
    print(f"  {'entry rule':<34} {'n':>6} {'/day':>6} {'win%':>7} {'points':>9} "
          f"{'£ today':>9} {'pts/trade':>10}")
    print("  "+"-"*88)
    base = None
    for lab, cb in (("at the touch (System A ships)", -1),
                    ("close back within 0 bars", 0),
                    ("close back within 1 bar", 1),
                    ("close back within 2 bars", 2),
                    ("close back within 3 bars", 3),
                    ("close back within 5 bars", 5)):
        r = run(cb)
        if len(r) < 30: continue
        p = sum(r); w = 100.0*sum(1 for x in r if x > 0)/len(r)
        print(f"  {lab:<34} {len(r):>6} {len(r)/days:>6.1f} {w:>6.1f}% {p:>9.1f} "
              f"{p*TODAY*GBP:>9.2f} {p/len(r):>10.4f}")
        if cb == -1: base = p

    print(f"\n  DOES IT SPLIT THE POPULATION? (MFE / |MAE| — 0.96 means undiscriminated)")
    print(f"  {'entry rule':<34} {'n':>6} {'mean MFE':>10} {'mean MAE':>10} {'ratio':>8}")
    print("  "+"-"*72)
    for lab, cb in (("at the touch", -1), ("close back within 2 bars", 2)):
        r, paths = run(cb, collect=True)
        if not paths: continue
        mf = statistics.mean(p[0] for p in paths)
        ma = statistics.mean(p[1] for p in paths)
        print(f"  {lab:<34} {len(paths):>6} {mf:>10.3f} {ma:>10.3f} "
              f"{mf/abs(ma) if ma else 0:>8.2f}")


if __name__ == "__main__":
    main()

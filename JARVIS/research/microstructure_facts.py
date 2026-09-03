"""
microstructure_facts.py — unconditional facts about the instruments we hold,
used to CALIBRATE the sweep numbers in sweep_anatomy.py.

A conditional frequency means nothing without its unconditional baseline.
Gold has asymmetric short-horizon volatility, so a symmetric +/-1 ATR barrier
does NOT resolve 50/50 from a random bar. This file measures that baseline,
plus the cost/range arithmetic per timeframe, same-bar ambiguity rates,
give-back frequency, and loss clustering.
"""
from __future__ import annotations
import os, sys, math, statistics as st, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
from sweep_anatomy import atr, barrier, wilson


def baseline(symbol, tf, horizon=24, mult=1.0, step=1):
    s = engine.load(symbol, tf); a = atr(s, 14)
    up = dn = amb = non = 0
    for i in range(250, len(s)-1, step):
        if a[i] is None or a[i] <= 0: continue
        r = barrier(s, i, s.c[i], mult*a[i], mult*a[i], horizon)
        if r == 'up': up += 1
        elif r == 'dn': dn += 1
        elif r == 'ambig': amb += 1
        else: non += 1
    n = up+dn
    lo, hi = wilson(dn, n)
    return dict(n=n, p_down_first=dn/n, ci=(lo,hi), ambig=amb, unresolved=non)


def cost_vs_range(symbol, tfs, spread, slip=0.05, comm_px=0.07):
    """Round-trip cost in price units vs the median bar TRUE RANGE."""
    out = []
    base = engine.load(symbol, tfs[0][0])
    for tf, factor in tfs:
        s = engine.load(symbol, tf) if factor == 1 else engine.resample(engine.load(symbol, tfs[0][0]), factor)
        tr = []
        for i in range(1, len(s)):
            tr.append(max(s.h[i]-s.l[i], abs(s.h[i]-s.c[i-1]), abs(s.l[i]-s.c[i-1])))
        med = st.median(tr)
        rt = spread + 2*slip + comm_px          # round-trip, price units
        out.append((tf if factor==1 else f"{tf}x{factor}", len(s), med, rt, rt/med))
    return out


def give_back(symbol, tf, horizon=48, stop_mult=1.0, tgt_mult=3.0):
    """Of trades that go 1R green, how many still end at the stop?
    Long-only structural probe from every bar (not a strategy)."""
    s = engine.load(symbol, tf); a = atr(s, 14)
    tot = green1 = green1_then_stop = tgt = amb_bar = 0
    for i in range(250, len(s)-1):
        if a[i] is None or a[i] <= 0: continue
        e = s.c[i]; R = stop_mult*a[i]
        stop = e - R; target = e + tgt_mult*R
        tot += 1
        hit_green = False; done = False
        for j in range(i+1, min(i+1+horizon, len(s))):
            if s.h[j] >= e+R: hit_green = True
            if s.l[j] <= stop and s.h[j] >= target: amb_bar += 1; done=True; break
            if s.l[j] <= stop:
                if hit_green: green1_then_stop += 1
                done = True; break
            if s.h[j] >= target:
                tgt += 1; done = True; break
        if hit_green: green1 += 1
    return dict(probes=tot, reached_1R=green1, of_those_stopped=green1_then_stop,
                give_back_rate=green1_then_stop/max(green1,1),
                reached_3R=tgt, same_bar_ambiguous=amb_bar,
                ambig_rate=amb_bar/max(tot,1))


def gap_stats(symbol, tf):
    s = engine.load(symbol, tf)
    a = atr(s, 14)
    gaps = []
    for i in range(1, len(s)):
        dtsec = s.ts[i]-s.ts[i-1]
        if dtsec > 3*3600 and a[i-1]:
            gaps.append(abs(s.o[i]-s.c[i-1])/a[i-1])
    if not gaps: return None
    gaps.sort()
    return dict(n=len(gaps), median_atr=gaps[len(gaps)//2],
                p90=gaps[int(0.9*len(gaps))], max=gaps[-1],
                frac_over_1atr=sum(1 for g in gaps if g>1)/len(gaps))


def hourly_range(symbol, tf="1h"):
    s = engine.load(symbol, tf)
    buckets = {}
    for i in range(1, len(s)):
        h = dt.datetime.utcfromtimestamp(s.ts[i]).hour
        buckets.setdefault(h, []).append(s.h[i]-s.l[i])
    return {h: (len(v), st.median(v)) for h, v in sorted(buckets.items())}


if __name__ == "__main__":
    print("="*78); print("1. BASELINE: P(down 1 ATR before up 1 ATR) from a RANDOM bar close")
    print("   (the null the sweep numbers must be compared to, NOT 0.500)")
    print("-"*78)
    for sym, tf in (("GOLD","1h"),("GOLD","15m"),("EURUSD","1h"),("US500","1h")):
        b = baseline(sym, tf)
        print(f"  {sym:7s}{tf:4s} n={b['n']:6d}  P(down first)={b['p_down_first']:.3f} "
              f"95%CI[{b['ci'][0]:.3f},{b['ci'][1]:.3f}]  ambig={b['ambig']} unresolved={b['unresolved']}")

    print("="*78); print("2. COST vs BAR RANGE (gold, $0.30 spread + 2x$0.05 slip + ~$0.07 comm)")
    print("-"*78)
    print(f"  {'TF':8s} {'bars':>7s} {'median TR $':>12s} {'round trip $':>13s} {'cost/range':>11s}")
    for tf, n, med, rt, ratio in cost_vs_range("GOLD", [("15m",1),("15m",2),("15m",4),("15m",8),("15m",16)], 0.30):
        print(f"  {tf:8s} {n:7d} {med:12.3f} {rt:13.2f} {ratio:10.1%}")
    for tf, n, med, rt, ratio in cost_vs_range("GOLD", [("1h",1),("1h",4),("1h",24)], 0.30):
        print(f"  {tf:8s} {n:7d} {med:12.3f} {rt:13.2f} {ratio:10.1%}")

    print("="*78); print("3. GIVE-BACK: probes that reach +1R then still stop out (GOLD)")
    print("-"*78)
    for sym, tf in (("GOLD","1h"),("GOLD","15m")):
        g = give_back(sym, tf)
        print(f"  {sym} {tf}: probes={g['probes']}  reached +1R={g['reached_1R']} "
              f"({g['reached_1R']/g['probes']:.1%})")
        print(f"        of those, stopped out anyway = {g['of_those_stopped']} "
              f"-> give-back rate {g['give_back_rate']:.1%}")
        print(f"        reached +3R = {g['reached_3R']} ({g['reached_3R']/g['probes']:.1%})")
        print(f"        SAME-BAR ambiguity (stop AND target in one bar) = "
              f"{g['same_bar_ambiguous']} ({g['ambig_rate']:.2%} of probes)")

    print("="*78); print("4. WEEKEND / SESSION GAPS (|open - prev close| in ATR)")
    print("-"*78)
    for sym in ("GOLD","EURUSD","US500"):
        g = gap_stats(sym, "1h")
        if g: print(f"  {sym:7s} n={g['n']:4d} median={g['median_atr']:.2f} ATR  "
                    f"p90={g['p90']:.2f}  max={g['max']:.2f}  >1ATR: {g['frac_over_1atr']:.1%}")

    print("="*78); print("5. GOLD median 1h bar range by UTC hour")
    print("-"*78)
    hr = hourly_range("GOLD")
    mx = max(v[1] for v in hr.values())
    for h,(n,m) in hr.items():
        bar = "#"*int(40*m/mx)
        print(f"  {h:02d}:00  n={n:5d}  median range ${m:6.3f}  {bar}")
    print("="*78)

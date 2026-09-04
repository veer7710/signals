"""
E-112 — THE FIRST HONEST M1 TEST IN THIS PROJECT'S HISTORY.

157,051 real M1 bars built from 18.8M bid/ask ticks, with the REAL per-bar
spread carried through instead of an assumed constant. Costs are charged from
each bar's own measured spread, not from `Costs.spread = 0.46`.

THE QUESTION: does ANY of the mechanisms this project has spent 111 experiments
on survive at M1 resolution once the real cost is applied bar by bar?

Tested: the SuperTrend flip (the live EA's own signal), and a matched random
control on the identical geometry. If the strategy cannot beat the control at
M1, the live account's premise is wrong and it does not matter how the exit is
tuned.

CAVEAT CARRIED IN THE OUTPUT: 2018 H1 gold ranged 1275-1366 with M1 ATR 0.246
and a 0.229 spread, so spread/ATR here is 0.93 - roughly EIGHT TIMES today's
estimated 0.11-0.25. This period is a worst case for cost, not a typical one.
A mechanism that survives here is robust; one that dies here may still work now.
"""
from __future__ import annotations
import os, sys, json, random, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
from engine import atr as watr


def load_with_spread(tf="M1_2018"):
    rows = json.load(open(f"/home/user/signals/data/GOLD_{tf}.json"))
    rows.sort(key=lambda r: r[0])
    s = engine.Series([r[0] for r in rows], [r[1] for r in rows],
                      [r[2] for r in rows], [r[3] for r in rows],
                      [r[4] for r in rows])
    return s, [r[5] for r in rows]          # per-bar mean spread, in points


def supertrend_dir(s, A, mult=1.2):
    n = len(s); d = [0]*n; fu = [None]*n; fl = [None]*n
    for i in range(n):
        a = A[i]
        if a is None or a <= 0: continue
        mid = (s.h[i]+s.l[i])/2.0
        bu, bl = mid+mult*a, mid-mult*a
        if i == 0 or fu[i-1] is None:
            fu[i], fl[i] = bu, bl; d[i] = 1; continue
        pu, pl, pc = fu[i-1], fl[i-1], s.c[i-1]
        fu[i] = bu if (bu < pu or pc > pu) else pu
        fl[i] = bl if (bl > pl or pc < pl) else pl
        d[i] = d[i-1]
        if d[i-1] == 1 and s.c[i] > fu[i]: d[i] = -1
        elif d[i-1] == -1 and s.c[i] < fl[i]: d[i] = 1
    return d


def run(s, SP, A, sigs, stop_atr, trail, maxbars):
    """Costs come from each bar's OWN measured spread. Ties lose."""
    out, busy = [], -1
    n = len(s)
    for (i, side) in sigs:
        if i <= busy or i+1 >= n: continue
        a = A[i]
        if not a or a <= 0: continue
        half_in = SP[i+1]/2.0
        entry = s.o[i+1] + side*half_in
        risk = stop_atr*a
        stop = entry - side*risk
        peak = entry
        px = None
        for k in range(i+1, min(i+1+maxbars, n)):
            if (side > 0 and s.l[k] <= stop) or (side < 0 and s.h[k] >= stop):
                px = stop; kk = k; break
            peak = max(peak, s.h[k]) if side > 0 else min(peak, s.l[k])
            t = peak - side*trail*a
            cand = max(stop, t) if side > 0 else min(stop, t)
            worst = s.l[k] if side > 0 else s.h[k]
            if cand != stop and ((side > 0 and worst <= cand) or (side < 0 and worst >= cand)):
                px = cand; kk = k; break
            stop = cand
        if px is None:
            kk = min(i+maxbars, n-1); px = s.c[kk]
        fill = px - side*SP[kk]/2.0
        pts = side*(fill-entry)
        out.append({"r": pts/risk, "pts": pts, "out": kk})
        busy = kk
    return out


def stat(tr):
    if len(tr) < 30: return None
    n = len(tr); m = sum(t["r"] for t in tr)/n
    sd = (sum((t["r"]-m)**2 for t in tr)/(n-1))**0.5
    w = 100.0*sum(1 for t in tr if t["pts"] > 0)/n
    return n, m, sd/n**0.5, m/(sd/n**0.5), w, sum(t["pts"] for t in tr)


def main():
    s, SP = load_with_spread("M1_2018")
    A = watr(s, 14)
    va = sorted(x for x in A[100:] if x)
    med_a, med_sp = va[len(va)//2], statistics.median(SP)
    print("="*94)
    print("  E-112 — GOLD M1 2018, real ticks, per-bar real spread")
    print(f"  {len(s):,} bars | M1 ATR {med_a:.3f} | spread {med_sp:.3f} | "
          f"spread/ATR {med_sp/med_a:.2f}")
    print("  CAVEAT: spread/ATR here is 0.93 vs ~0.11-0.25 estimated for today.")
    print("  This is a WORST CASE for cost. Survival here is strong evidence.")
    print("="*94)

    d = supertrend_dir(s, A)
    flips = [(i, 1 if (d[i] == -1 and d[i-1] == 1) else -1)
             for i in range(300, len(s)-1)
             if (d[i] == -1 and d[i-1] == 1) or (d[i] == 1 and d[i-1] == -1)]
    print(f"\n  SuperTrend(7,1.2) flips on M1: {len(flips):,} "
          f"({len(flips)/(len(s)/1440):.0f} per trading day)")

    print(f"\n  {'stop':>6} {'trail':>6} {'hold':>6} {'n':>6} {'mean R':>9} "
          f"{'t':>7} {'win%':>7} {'points':>10}")
    print("  " + "-"*74)
    best = None
    for stop_atr in (2.0, 4.0, 8.0):
        for trail, maxbars in ((3.0, 60), (3.0, 240)):
            r = stat(run(s, SP, A, flips, stop_atr, trail, maxbars))
            if not r: continue
            n, m, se, t, w, pts = r
            print(f"  {stop_atr:>5.1f}A {trail:>5.1f}A {maxbars:>6} {n:>6} "
                  f"{m:>+9.4f} {t:>7.2f} {w:>6.1f}% {pts:>10.1f}")
            if best is None or t > best[0]: best = (t, stop_atr, trail, maxbars)

    # matched control: same count, same geometry, random bars and sides
    print(f"\n  MATCHED RANDOM CONTROL at the best cell "
          f"(stop {best[1]:.1f}A, trail {best[2]:.1f}A, hold {best[3]})")
    means = []
    for sd_ in range(12):
        rng = random.Random(200+sd_)
        rs = []
        i = 300
        while i < len(s)-best[3]-2:
            rs.append((i, rng.choice((1, -1))))
            i += rng.randrange(20, 400)
        r = stat(run(s, SP, A, rs, best[1], best[2], best[3]))
        if r: means.append(r[1])
    cm = sum(means)/len(means)
    cse = (sum((x-cm)**2 for x in means)/(len(means)-1))**0.5/len(means)**0.5
    r = stat(run(s, SP, A, flips, best[1], best[2], best[3]))
    print(f"  control ({len(means)} seeds): {cm:+.4f}R   se of mean {cse:.4f}")
    print(f"  SuperTrend:                  {r[1]:+.4f}R")
    print(f"  edge over control: {r[1]-cm:+.4f}R = "
          f"{(r[1]-cm)/cse if cse > 0 else 0:.1f} control se")


if __name__ == "__main__":
    main()

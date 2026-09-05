"""
E-127 — VEER'S ARCHITECTURE: M1 SuperTrend for the TREND, liquidity for the ENTRY.

Him: "supertrend is meant for m1, the point is we catch every single m1 trend...
m5 or m15 is caught late by supertrend but top ticked by smc and ict thru
liquidity strats".

That is a real architectural claim and this repo has never tested it. Every
SuperTrend test here (E-112..E-117) used the FLIP AS THE ENTRY - which is
exactly the "late" he is describing. And E-119..E-126 used M15 zones with
SuperTrend only as the trail, ignoring its direction entirely.

The untested combination is his: SuperTrend supplies the DIRECTION, a liquidity
level supplies the TIMING, and the trade is only taken when both agree.

  BASELINE 1  the flip as entry            (known: no edge, E-112/113/114)
  BASELINE 2  M15 zone + ST trail          (known: works, 21.0 control se)
  NEW         M1 SuperTrend direction, entered at a liquidity level in that
              direction, trailed by the band

Frequency matters here: he wants every M1 trend, so M1 and M5 zones are tested
as well as M15 - the point of the cascade is that the lower the zone timeframe
the more entries there are, and the question is where that stops paying.
"""
from __future__ import annotations
import os, sys, statistics, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
from engine import atr as watr
from liq_m1 import load, GBP
from supertrend_rescue import st_state

TODAY = 7.38


def swings(s, k):
    """Confirmed swing pivots on any series: (bar_it_becomes_known, price, dir).
    dir -1 = a swing LOW (a buy zone), +1 = a swing HIGH (a sell zone)."""
    out = []
    for i in range(k, len(s)-k):
        if s.l[i] == min(s.l[i-k:i+k+1]): out.append((i+k, s.l[i], -1))
        if s.h[i] == max(s.h[i-k:i+k+1]): out.append((i+k, s.h[i],  1))
    return out


def main():
    s1, SP1 = load("M1")
    A1 = watr(s1, 14)
    va = sorted(x for x in A1[100:] if x); med_a = va[len(va)//2]
    med_sp = statistics.median(SP1)
    cs = 0.11/(med_sp/med_a)
    d1, fu1, fl1 = st_state(s1, 7, 1.2)
    days = len(s1)/1440

    series = {"M1": (s1, s1.ts)}
    for tf in ("M5", "M15"):
        s, _ = load(tf)
        series[tf] = (s, s.ts)
    idx1 = {t: i for i, t in enumerate(s1.ts)}

    def zones_from(tf, k):
        s, ts = series[tf]
        out = []
        for (b, px, dr) in swings(s, k):
            t = ts[b]
            i0 = idx1.get(t)
            if i0 is None: continue
            out.append((i0, px, dr))
        out.sort()
        return out

    def run(zlist, past, stop_a, need_trend, hold=240, cooldown=120):
        tot, busy = [], -1
        for (i0, px, dr) in zlist:
            if i0 <= busy: continue
            a = A1[i0]
            if not a or a <= 0: continue
            side = 1 if dr == -1 else -1
            # HIS RULE: only take the sweep if the M1 SuperTrend already points
            # that way. The trend says WHICH WAY, the level says WHEN.
            if need_trend:
                st = d1[i0]
                if not ((st == -1 and side > 0) or (st == 1 and side < 0)):
                    continue
            lvl = px - side*past*a
            j = None
            for k in range(i0+1, min(i0+61, len(s1))):
                if (side == 1 and s1.l[k] <= lvl) or (side == -1 and s1.h[k] >= lvl):
                    j = k; break
            if j is None: continue
            sp = SP1[j]*cs
            entry = lvl + side*sp/2.0
            sl = entry - side*stop_a*a
            px_out = None
            for k in range(j, min(j+hold, len(s1))):
                if (side > 0 and s1.l[k] <= sl) or (side < 0 and s1.h[k] >= sl):
                    px_out, kk = sl, k; break
                band = fl1[k] if side > 0 else fu1[k]
                if band is not None:
                    sl = max(sl, band) if side > 0 else min(sl, band)
            if px_out is None:
                kk = min(j+hold, len(s1)-1); px_out = s1.c[kk]
            tot.append(side*((px_out - side*SP1[kk]*cs/2.0) - entry))
            busy = kk + cooldown
        return tot

    print("="*100)
    print("  E-127 — M1 SuperTrend as DIRECTION, liquidity as TIMING, band as trail")
    print(f"  {len(s1):,} real M1 bars, real per-bar spread scaled to today's ECN")
    print("="*100)
    print(f"  {'zone TF / pivot':<22} {'trend filter':<14} {'n':>6} {'/day':>6} "
          f"{'win%':>7} {'points':>9} {'£ today':>9}")
    print("  "+"-"*84)
    results = {}
    for tf, k in (("M15", 3), ("M5", 3), ("M5", 5), ("M1", 5), ("M1", 10)):
        z = zones_from(tf, k)
        for need in (False, True):
            r = run(z, 0.5, 4.0, need)
            if len(r) < 30: continue
            p = sum(r); w = 100.0*sum(1 for x in r if x > 0)/len(r)
            lab = f"{tf} pivot {k}"
            print(f"  {lab:<22} {'ST agrees' if need else 'none':<14} {len(r):>6} "
                  f"{len(r)/days:>6.1f} {w:>6.1f}% {p:>9.1f} {p*TODAY*GBP:>9.2f}")
            results[(tf, k, need)] = (p, len(r), z)
    if not results: return

    # the fair control on the best cell: same zones, shifted in time
    best = max(results, key=lambda kk: results[kk][0])
    p, n, z = results[best]
    print(f"\n  BEST: {best[0]} pivot {best[1]}, trend filter "
          f"{'ON' if best[2] else 'off'} -> {p:.1f} points, {n} trades")
    sh = []
    for sd in range(14):
        rng = random.Random(31000+sd)
        off = rng.randrange(500, 40000)
        zz = sorted([((i0+off) % (len(s1)-500) + 200, px, dr) for (i0, px, dr) in z])
        r = run(zz, 0.5, 4.0, best[2])
        if len(r) > 30: sh.append(sum(r))
    cm = sum(sh)/len(sh)
    cse = (sum((x-cm)**2 for x in sh)/(len(sh)-1))**0.5/len(sh)**0.5
    print(f"  time-shifted control ({len(sh)} shifts): {cm:.1f} points, se {cse:.1f}")
    print(f"  EDGE {p-cm:+.1f} points = {(p-cm)/cse if cse > 0 else 0:.1f} control se")


if __name__ == "__main__":
    main()

"""adv_ — independent harness for attacking the E-151 sweep claim. Read-only w.r.t. existing files."""
from __future__ import annotations
import os, sys, statistics, math, random, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, trail_level, cost_scale
from liq_m1 import load
from sweep_winrate import pivots

GBP = 0.787
BPD = {"M1": 1440, "M5": 288, "M15": 96}


def sweep_candidates(s, A, SPC, pk=5, sweep_atr=0.10, wick=0.6460, buf=0.30,
                     cap=1.2, life=120):
    """Exactly combined.candidates() restricted to SWEEP, but taking a
    PRE-SCALED spread array SPC (in price units) instead of SP*cs."""
    out = []
    for (kb, px, side) in pivots(s, pk):
        a = A[kb]
        if not a or a <= 0:
            continue
        t = -side
        need = px + side * sweep_atr * a
        sw, ext = None, None
        for k in range(kb + 1, min(kb + life, len(s))):
            if (s.h[k] >= need) if side > 0 else (s.l[k] <= need):
                sw, ext = k, (s.h[k] if side > 0 else s.l[k]); break
        if sw is None:
            continue
        rng = s.h[sw] - s.l[sw]
        if (abs(s.c[sw] - s.o[sw]) / rng if rng > 0 else 1.0) > wick:
            continue
        j = None
        for k in range(sw + 1, min(sw + life, len(s))):
            if (s.h[k] >= px) if t > 0 else (s.l[k] <= px):
                j = k; break
            ext = max(ext, s.h[k]) if side > 0 else min(ext, s.l[k])
        if j is None:
            continue
        sl = ext - t * buf * a
        if not (0 < abs(px - sl) <= cap * a):
            continue
        out.append((j, t, px + t * SPC[j] / 2.0, sl, kb, sw))
    out.sort(key=lambda x: x[0])
    return out


def simulate(s, SPC, cand, give=0.25, hold=240, cooldown=5, slip=0.0, comm=0.0):
    """combined.simulate for the sweep, returning full trade records."""
    out, busy = [], -1
    for (j, d, entry, sl0, kb, sw) in cand:
        if j <= busy:
            continue
        sl = sl0; peak = entry; px_out = kk = None
        for k in range(j, min(j + hold, len(s))):
            if (s.l[k] <= sl) if d > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k; break
            if k == j:
                continue
            peak = max(peak, s.h[k]) if d > 0 else min(peak, s.l[k])
            nsl = trail_level(entry, sl, peak, s.c[k], d, give)
            if nsl is None:
                px_out, kk = s.c[k], k; break
            sl = nsl
        if px_out is None:
            kk = min(j + hold, len(s) - 1); px_out = s.c[kk]
        pts = d * ((px_out - d * SPC[kk] / 2.0) - entry) - slip - comm
        out.append({"pts": pts, "d": d, "j": j, "kk": kk, "ts": s.ts[j],
                    "risk": abs(entry - sl0)})
        busy = kk + cooldown
    return out


def summ(r):
    n = len(r)
    if n == 0:
        return None
    p = [x["pts"] for x in r]
    m = sum(p) / n
    sd = (sum((x - m) ** 2 for x in p) / (n - 1)) ** 0.5 if n > 1 else 0.0
    t = m / (sd / n ** 0.5) if sd > 0 else 0.0
    eq = peak = mdd = 0.0
    for x in p:
        eq += x; peak = max(peak, eq); mdd = max(mdd, peak - eq)
    return dict(n=n, pts=sum(p), per=m, t=t, win=100.0 * sum(1 for x in p if x > 0) / n,
                mdd=mdd, sd=sd)


def line(lbl, r, w=34):
    z = summ(r)
    if z is None or z["n"] == 0:
        print(f"  {lbl:<{w}}   no trades"); return
    print(f"  {lbl:<{w}}{z['n']:>6}{z['win']:>7.1f}%{z['pts']:>10.1f}"
          f"{z['per']:>+11.4f}{z['t']:>8.2f}{z['mdd']:>10.1f}")


def hdr(title, w=34):
    print("=" * (w + 52)); print("  " + title); print("=" * (w + 52))
    print(f"  {'cell':<{w}}{'n':>6}{'win%':>8}{'points':>10}{'per trade':>11}{'t':>8}{'maxDD':>10}")


def ctx(tf):
    s, SP = load(tf)
    A = watr(s, 14)
    va = sorted(x for x in A[100:] if x)
    cs = cost_scale(SP, A)   # E-173: one PRICE on every clock - never re-derived per timeframe
    return s, SP, A, cs

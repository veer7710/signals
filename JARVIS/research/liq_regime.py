"""
E-179 — THE LIQUIDITY SWEEP ON 2024-2026 GOLD, PER CLOCK.

Every liquidity result in this repo (E-076, E-119, E-149, E-168, E-172) was
computed on Jan-Jun 2018. E-176 showed what that sample did to the SuperTrend
verdict. The same question has never been asked of the sweep, and Veer wants it
running on M1/M5/M15/M30 with settings chosen per clock.

THE SETUP, unchanged from combined.py so this is a regime test and not a new
strategy: a confirmed pivot is a level; price sweeps THROUGH it by sweepAtr;
the sweep bar must not be a full-bodied displacement candle (wickCut); price
then returns to the level and a stop order fills there; the stop sits beyond
the sweep's extreme by stopBuf, capped at maxRisk ATR.

FILL RULES ENFORCED: entry_fill (E-165) - a stop order cannot fill at its level
once the bar has opened past it. trail_level (E-151) is not needed here because
the exit is a fixed target or the stop.

Cost is charged as a fixed fraction of ATR, and the sensitivity is printed,
because these files carry no spread column.
"""
from __future__ import annotations
import os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, entry_fill
from regime import load_plain, resample

COST_ATR = 0.02


def pivots(s, k):
    out = []
    for i in range(k, len(s)-k):
        if s.h[i] == max(s.h[i-k:i+k+1]): out.append((i+k, s.h[i], "high"))
        if s.l[i] == min(s.l[i-k:i+k+1]): out.append((i+k, s.l[i], "low"))
    return out


def book(s, tgtR, pk=5, cap=1.2, buf=0.30, wick=0.646, sweep=0.10,
         hold=240, cool=5, cost=COST_ATR):
    A = watr(s, 14)
    out, busy = [], -1
    for (kb, px, kind) in pivots(s, pk):
        side = 1 if kind == "high" else -1
        a = A[kb]
        if not a or a <= 0:
            continue
        t = -side
        need = px + side * sweep * a
        sw, ext = None, None
        for k in range(kb+1, min(kb+120, len(s))):
            if (s.h[k] >= need) if side > 0 else (s.l[k] <= need):
                sw, ext = k, (s.h[k] if side > 0 else s.l[k]); break
        if sw is None:
            continue
        rng = s.h[sw]-s.l[sw]
        if (abs(s.c[sw]-s.o[sw])/rng if rng > 0 else 1.0) > wick:
            continue
        j = None
        for k in range(sw+1, min(sw+120, len(s))):
            if (s.h[k] >= px) if t > 0 else (s.l[k] <= px):
                j = k; break
            ext = max(ext, s.h[k]) if side > 0 else min(ext, s.l[k])
        if j is None or j <= busy:
            continue
        sl = ext - t*buf*a
        if not (0 < abs(px-sl) <= cap*a):
            continue
        entry = entry_fill(px, s.o[j], t)
        risk = abs(entry-sl)
        if risk <= 0:
            continue
        tgt = entry + t*tgtR*risk
        px_out, kk = None, None
        for k in range(j, min(j+hold, len(s))):
            if (s.l[k] <= sl) if t > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k; break
            if k > j and ((s.h[k] >= tgt) if t > 0 else (s.l[k] <= tgt)):
                px_out, kk = tgt, k; break
        if px_out is None:
            kk = min(j+hold, len(s)-1); px_out = s.c[kk]
        out.append(t*(px_out-entry)/a - cost)
        busy = kk + cool
    return out


def line(lbl, r):
    if len(r) < 20:
        print(f"  {lbl:<28}  only {len(r)} trades")
        return
    m = statistics.fmean(r)
    t = m/(statistics.pstdev(r)/len(r)**0.5)
    w = 100.0*sum(1 for x in r if x > 0)/len(r)
    print(f"  {lbl:<28}{len(r):>6}{w:>7.1f}%{m:>+10.3f}{t:>+7.2f}{sum(r):>9.1f}")


def main():
    h1 = load_plain("GOLD_1h.json")
    g15 = load_plain("GOLD_15m.json")
    sets = [("2024-2026  1h", h1), ("2024-2026  4h", resample(h1, 4)),
            ("2026       15m", g15), ("2026       1h", resample(g15, 4))]
    print("=" * 92)
    print("  E-179 — the liquidity sweep on RECENT gold. Every previous")
    print("  liquidity number in this repo came from Jan-Jun 2018.")
    print("=" * 92)
    for lbl, s in sets:
        print(f"\n  ---- {lbl} ----")
        print(f"  {'target':<28}{'n':>6}{'win%':>8}{'ATR/trd':>10}{'t':>7}{'total':>9}")
        for tgt in (1.0, 1.5, 2.0, 3.0):
            line(f"{tgt:.1f}R target", book(s, tgt))

    print("\n" + "=" * 92)
    print("  the pivot size, which is the one setting that should differ by"
          " clock (a 5-bar pivot")
    print("  on 15m is 75 minutes of structure; on 1h it is five hours)")
    print("=" * 92)
    for lbl, s in sets:
        print(f"\n  ---- {lbl}, 2R target ----")
        print(f"  {'pivot':<28}{'n':>6}{'win%':>8}{'ATR/trd':>10}{'t':>7}{'total':>9}")
        for pk in (3, 5, 8, 12):
            line(f"pivot {pk} bars each side", book(s, 2.0, pk=pk))


if __name__ == "__main__":
    main()

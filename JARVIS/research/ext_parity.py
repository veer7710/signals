"""
E-164 — THE SWEEP'S STOP IS IN THREE DIFFERENT PLACES.

P92's lesson was that the chart and the EA were not the same strategy. This is
the same defect one layer down, on the stop rather than the signal, and it was
found by a code review rather than by anything in the repo noticing.

The sweep's stop sits `stopBuf` past the sweep's EXTREME. All three
implementations extend that extreme differently:

  EA        freezes it when the order is ARMED, which is right after the sweep.
            Tightest stop. Arms a resting stop order and never revises it.
  RESEARCH  extends it up to but NOT including the bar that fills. Middle.
  PINE      extended it INCLUDING the fill bar. Widest. (Now fixed to match
            the research - this file is why.)

A wider stop is hit less often, which flatters, and breaches the risk cap more
often, which refuses trades. The two effects pull opposite ways and no argument
settles it, so it is measured.
"""
from __future__ import annotations
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, trail_level, cost_scale
from liq_m1 import load, GBP
from sweep_winrate import pivots

TODAY = 7.38
GBP_PT = TODAY * GBP


def book(tf, mode, pk=5, sweep_atr=0.10, wick=0.646, buf=0.30, cap=1.2,
         give=0.25, hold=240, cooldown=5):
    """mode: 'frozen' (EA), 'to_fill' (research/Pine now), 'incl_fill' (old Pine)"""
    s, SP = load(tf)
    A = watr(s, 14)
    va = sorted(x for x in A[100:] if x)
    cs = cost_scale(SP, A)   # E-173: one PRICE on every clock - never re-derived per timeframe
    out, refused, busy = [], 0, -1
    for (kb, px, side) in pivots(s, pk):
        a = A[kb]
        if not a or a <= 0:
            continue
        t = -side
        need = px + side * sweep_atr * a
        sw, ext = None, None
        for k in range(kb + 1, min(kb + 120, len(s))):
            if (s.h[k] >= need) if side > 0 else (s.l[k] <= need):
                sw, ext = k, (s.h[k] if side > 0 else s.l[k])
                break
        if sw is None:
            continue
        rng = s.h[sw] - s.l[sw]
        if (abs(s.c[sw] - s.o[sw]) / rng if rng > 0 else 1.0) > wick:
            continue
        frozen = ext
        j = None
        for k in range(sw + 1, min(sw + 120, len(s))):
            if (s.h[k] >= px) if t > 0 else (s.l[k] <= px):
                j = k
                break
            ext = max(ext, s.h[k]) if side > 0 else min(ext, s.l[k])
        if j is None:
            continue
        use = (frozen if mode == "frozen" else
               ext if mode == "to_fill" else
               (max(ext, s.h[j]) if side > 0 else min(ext, s.l[j])))
        sl = use - t * buf * a
        entry = px + t * SP[j] * cs / 2.0
        # The cap is measured LEVEL to stop, which is the convention every other
        # file in this repo uses. Measuring it entry-to-stop instead adds half a
        # spread and refused about 18% more setups - the two files then reported
        # different trade counts for the same strategy, which is how P92 started.
        risk = abs(px - sl)
        if risk <= 0:
            continue
        if risk > cap * a:
            refused += 1
            continue
        if j <= busy:
            continue
        peak, px_out, kk = entry, None, None
        for k in range(j, min(j + hold, len(s))):
            if (s.l[k] <= sl) if t > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k; break
            if k == j:
                continue
            peak = max(peak, s.h[k]) if t > 0 else min(peak, s.l[k])
            nsl = trail_level(entry, sl, peak, s.c[k], t, give)
            if nsl is None:
                px_out, kk = s.c[k], k; break
            sl = nsl
        if px_out is None:
            kk = min(j + hold, len(s) - 1); px_out = s.c[kk]
        out.append(t * ((px_out - t * SP[kk] * cs / 2.0) - entry))
        busy = kk + cooldown
    return out, refused


def main():
    for tf in ("M1", "M5"):
        print("=" * 96)
        print(f"  E-164 — {tf}: the same sweep, three stop placements")
        print("=" * 96)
        print(f"  {'where the extreme stops':<26}{'n':>7}{'refused':>9}{'win%':>7}"
              f"{'points':>9}{'/trade':>9}{'maxDD':>8}{'worst':>8}")
        for mode, lbl in (("frozen", "at the sweep (the EA)"),
                          ("to_fill", "at the fill (research)"),
                          ("incl_fill", "past the fill (old Pine)")):
            p, ref = book(tf, mode)
            eq = pkq = dd = 0.0
            for x in p:
                eq += x; pkq = max(pkq, eq); dd = max(dd, pkq - eq)
            win = 100.0 * sum(1 for x in p if x > 0) / len(p)
            print(f"  {lbl:<26}{len(p):>7}{ref:>9}{win:>6.1f}%{sum(p):>9.1f}"
                  f"{sum(p)/len(p):>+9.4f}{dd:>8.1f}{min(p):>8.2f}")
        print()


if __name__ == "__main__":
    main()

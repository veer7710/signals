"""
E-160 — THE RISK CAP IS ALREADY THE FILTER, AND IT IS SET TOO WIDE.

E-159 found the one thing that sorts a sweep from a bad sweep: **how far past
the level the sweep ran**, measured as the stop's width in ATR. It is monotone
across all four quartiles on both clocks, at the same place on both clocks
(~0.70 ATR), and it holds on data it never saw.

That is not a new filter. `InpMaxRiskAtr` / `maxRisk` already refuses a setup
whose stop is too wide - it is set to 1.2 ATR, chosen in E-138 to stop one trade
taking 57% of the account. E-159 says 1.2 is a SAFETY limit that happens to sit
well above where the EDGE actually falls off.

So this sweeps the cap itself and prices every consequence, including the one
CLAUDE.md warns about: E-074, the best per-trade gate set banked the LEAST. A
cap that raises quality and cuts total points has to justify itself on something
other than per-trade, and for a funded account that something is the pass rate.
"""
from __future__ import annotations
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, trail_level, cost_scale
from liq_m1 import load, GBP
import combined as C
import funded as F

TODAY = 7.38
GBP_PT = TODAY * GBP
PER_DAY = {"M1": 23.8, "M5": 5.2}
_P = {}


def prep(tf):
    if tf not in _P:
        s, SP = load(tf)
        A = watr(s, 14)
        va = sorted(x for x in A[100:] if x)
        cs = cost_scale(SP, A)   # E-173: one PRICE on every clock - never re-derived per timeframe
        # generated ONCE at the widest cap; the sweep below only re-filters
        cand = [c for c in C.candidates(s, A, cs, SP, {C.SWEEP}, cap=99.0)
                if c[1] == C.SWEEP]
        _P[tf] = (s, SP, A, cs, cand)
    return _P[tf]


def book(tf, cap, give=0.25, cooldown=5, hold=240, subset=None):
    s, SP, A, cs, cand = prep(tf)
    pts, rs, busy = [], [], -1
    for (j, _, d, entry, sl0) in cand:
        if j <= busy:
            continue
        if subset and not (subset[0] <= j < subset[1]):
            continue
        a = A[j] if A[j] else 0.0
        risk = abs(entry - sl0)
        if a <= 0 or risk <= 0 or risk > cap * a:
            continue
        sl, peak, px_out, kk = sl0, entry, None, None
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
        p = d * ((px_out - d * SP[kk] * cs / 2.0) - entry)
        pts.append(p); rs.append(p / risk)
        busy = kk + cooldown
    return pts, rs


def stat(p):
    eq = pk = dd = 0.0
    run = worst = 0
    for x in p:
        eq += x; pk = max(pk, eq); dd = max(dd, pk - eq)
        run = run + 1 if x <= 0 else 0
        worst = max(worst, run)
    n = len(p); t = sum(p)
    return n, t, t / n, dd, worst, 100.0 * sum(1 for x in p if x > 0) / n, min(p)


CAPS = (0.5, 0.6, 0.7, 0.8, 1.0, 1.2, 1.6, 99.0)


def main():
    for tf in ("M1", "M5"):
        s, _, _, _, _ = prep(tf)
        half = len(s) // 2
        print("=" * 104)
        print(f"  E-160 — {tf}: how wide should the sweep's stop be allowed to be?")
        print(f"  1 point = GBP{GBP_PT:.2f} at 0.01 lots. Shipped cap is 1.2 ATR.")
        print("=" * 104)
        print(f"  {'cap':>6}{'n':>7}{'/day':>7}{'win%':>7}{'points':>9}{'/trade':>9}"
              f"{'maxDD':>8}{'DD GBP':>8}{'worst':>8}{'run':>5}")
        books = {}
        for cap in CAPS:
            p, r = book(tf, cap)
            books[cap] = (p, r)
            n, t, per, dd, run, win, wst = stat(p)
            lbl = "none" if cap > 90 else f"{cap:.1f}"
            print(f"  {lbl:>6}{n:>7}{n/109.0:>7.1f}{win:>6.1f}%{t:>9.1f}{per:>+9.4f}"
                  f"{dd:>8.1f}{dd*GBP_PT:>8.0f}{wst:>8.2f}{run:>5}")

        print(f"\n  OUT OF SAMPLE — the cap is chosen on the 1st half only")
        best, bestv = None, None
        for cap in CAPS:
            p, _ = book(tf, cap, subset=(0, half))
            if len(p) >= 100 and (bestv is None or sum(p) > bestv):
                bestv, best = sum(p), cap
        for cap in sorted({best, 0.7, 1.2}):
            p2, _ = book(tf, cap, subset=(half, len(s)))
            if not p2:
                continue
            n, t, per, dd, run, win, wst = stat(p2)
            tag = "  <- picked on the 1st half by points" if cap == best else ""
            lbl = "none" if cap > 90 else f"{cap:.1f}"
            print(f"    cap {lbl:>5}  unseen n={n:<5} {t:>7.1f} pts {per:+.4f}/tr "
                  f"DD {dd:.1f} ({dd*GBP_PT:.0f} GBP) {win:.1f}% win{tag}")

        print(f"\n  AND THROUGH THE FIRMS, 0.25% risk a trade")
        show = [0.7, 1.0, 1.2]
        print(f"    {'firm':<34}" + "".join(f"{'cap '+str(c):>12}" for c in show))
        tpd = [max(1, int(round(PER_DAY[tf])))]
        for key, firm in F.FIRMS.items():
            cells = []
            for c in show:
                _, r = books[c]
                cells.append(F.pass_rate(r, tpd, firm, 0.0025, trials=400, seed=11)[0])
            print(f"    {firm.name:<34}" + "".join(f"{x*100:>11.1f}%" for x in cells))
        print()


if __name__ == "__main__":
    main()

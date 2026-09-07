"""
E-166 — "IT REACTED THERE BEFORE", ASKED AGAIN UNDER HONEST FILLS.

Veer has pointed at this twice, with a screenshot both times: price reacted to a
zone at 3pm and reacted to it again at 7pm, and nothing in the system knew.

E-143 measured it and found a PERFECTLY MONOTONE ladder in the OPPOSITE
direction - a level that had never reacted was the best to trade, one that had
reacted repeatedly the worst. That result was computed with the E-165 entry
bug, and there is a specific reason to think the bug MADE it:

    A level price has visited many times is a level price is hovering around.
    Hovering means the entry bar is far more likely to OPEN already past the
    level - which is exactly the condition the old code mispriced. The more
    reactions, the more impossible fills, the more the old code inflated that
    group. Inflate the low-reaction group least and the high-reaction group
    most and you manufacture a monotone ladder pointing the wrong way.

So this reports, per reaction count: the honest per-trade result, the old
broken one, AND the share of entries that opened past the level. If that share
climbs with the reaction count, the mechanism above is real.
"""
from __future__ import annotations
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, trail_level, entry_fill, cost_scale
from liq_m1 import load
from sweep_winrate import pivots

REACT_NEAR = 0.15
REACT_AWAY = 0.50


def reactions_before(s, A, px, upto, side, look=3000):
    """How many times price came to this level and was refused, before bar
    `upto`. Uses only bars strictly before `upto`."""
    n, i = 0, max(1, upto - look)
    while i < upto:
        a = A[i] if A[i] else 0.0
        if a <= 0:
            i += 1
            continue
        if abs((s.h[i] if side > 0 else s.l[i]) - px) <= REACT_NEAR * a:
            # did it leave without closing through?
            j = i + 1
            gone = False
            while j < min(i + 60, upto):
                if (s.c[j] > px) if side > 0 else (s.c[j] < px):
                    break
                if abs(s.c[j] - px) >= REACT_AWAY * a:
                    gone = True
                    break
                j += 1
            if gone:
                n += 1
                i = j
        i += 1
    return n


def run(tf, honest, cap=1.2, buf=0.30, give=0.25, hold=240, cooldown=5):
    s, SP = load(tf)
    A = watr(s, 14)
    va = sorted(x for x in A[100:] if x)
    cs = cost_scale(SP, A)   # E-173: one PRICE on every clock - never re-derived per timeframe
    out, busy = [], -1
    for (kb, px, side) in pivots(s, 5):
        a = A[kb]
        if not a or a <= 0:
            continue
        t = -side
        need = px + side * 0.10 * a
        sw, ext = None, None
        for k in range(kb + 1, min(kb + 120, len(s))):
            if (s.h[k] >= need) if side > 0 else (s.l[k] <= need):
                sw, ext = k, (s.h[k] if side > 0 else s.l[k])
                break
        if sw is None:
            continue
        rng = s.h[sw] - s.l[sw]
        if (abs(s.c[sw] - s.o[sw]) / rng if rng > 0 else 1.0) > 0.646:
            continue
        j = None
        for k in range(sw + 1, min(sw + 120, len(s))):
            if (s.h[k] >= px) if t > 0 else (s.l[k] <= px):
                j = k
                break
            ext = max(ext, s.h[k]) if side > 0 else min(ext, s.l[k])
        if j is None:
            continue
        sl = ext - t * buf * a
        if not (0 < abs(px - sl) <= cap * a):
            continue
        if j <= busy:
            continue
        past = t * (s.o[j] - px) > 0
        trig = entry_fill(px, s.o[j], t) if honest else px
        entry = trig + t * SP[j] * cs / 2.0
        peak, px_out, kk = entry, None, None
        for k in range(j, min(j + hold, len(s))):
            if (s.l[k] <= sl) if t > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k
                break
            if k == j:
                continue
            peak = max(peak, s.h[k]) if t > 0 else min(peak, s.l[k])
            nsl = trail_level(entry, sl, peak, s.c[k], t, give)
            if nsl is None:
                px_out, kk = s.c[k], k
                break
            sl = nsl
        if px_out is None:
            kk = min(j + hold, len(s) - 1)
            px_out = s.c[kk]
        pts = t * ((px_out - t * SP[kk] * cs / 2.0) - entry)
        nr = reactions_before(s, A, px, kb, side)
        out.append((nr, pts, past))
        busy = kk + cooldown
    return out


def main():
    for tf in ("M1", "M5"):
        H = run(tf, True)
        B = run(tf, False)
        print("=" * 96)
        print(f"  E-166 — {tf}: does a level that reacted before trade better?")
        print("=" * 96)
        print(f"  {'prior reactions':<18}{'n':>7}{'HONEST/tr':>12}{'points':>10}"
              f"{'win%':>7}{'OLD (broken)':>14}{'opened past':>13}")
        buckets = [("0 — never", lambda k: k == 0),
                   ("1 — once", lambda k: k == 1),
                   ("2 — twice", lambda k: k == 2),
                   ("3+", lambda k: k >= 3)]
        for lbl, f in buckets:
            h = [(p, q) for (k, p, q) in H if f(k)]
            b = [p for (k, p, q) in B if f(k)]
            if len(h) < 20:
                print(f"  {lbl:<18}{len(h):>7}   too few to say")
                continue
            pts = [p for p, q in h]
            past = 100.0 * sum(1 for p, q in h if q) / len(h)
            print(f"  {lbl:<18}{len(h):>7}{sum(pts)/len(pts):>+12.4f}"
                  f"{sum(pts):>10.1f}"
                  f"{100.0*sum(1 for x in pts if x>0)/len(pts):>6.1f}%"
                  f"{(sum(b)/len(b) if b else 0):>+14.4f}{past:>12.0f}%")
        allh = [p for (k, p, q) in H]
        print(f"  {'ALL':<18}{len(allh):>7}{sum(allh)/len(allh):>+12.4f}{sum(allh):>10.1f}")
        print()


if __name__ == "__main__":
    main()

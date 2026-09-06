"""
E-143 — DOES A LEVEL THAT HAS ALREADY REACTED REACT AGAIN?

Veer, pointing at his own chart: "where my mouse crosshair is, price reacted to
that zone at 7pm which it had ALSO reacted to at 3pm. point being there was
liquidity there and a zone".

That is a specific, falsifiable claim and nothing in the shipped system knows
about it. Every level is treated as brand new: a pivot forms, it gets swept, we
trade it. Whether price has ALREADY turned at that price once today is not
looked at.

His claim is the standard one in the literature - a level "proves itself" by
being respected - and it is exactly the kind of claim that sounds obviously
true and is often worth nothing. E-135 quartiled POOL SIZE (how many pivots sit
at the same price) and the ladder was not monotone. But a pool is not a
reaction: three highs at the same price is geometry, whereas price arriving,
refusing to go through, and leaving is BEHAVIOUR. They are different features
and only one of them has been tested.

WHAT COUNTS AS A REACTION, defined before looking at any outcome:
    price comes within `near` ATR of the level, and then within `win` bars
    moves `away` ATR in the opposite direction WITHOUT closing through it.
That is "it came, it was refused, it left".

THE TEST: take the validated sweep setup unchanged and count, at the moment of
entry, how many prior reactions that level already had. Quartile the outcome.
Direction is pre-registered from the claim: MORE prior reactions should be
BETTER. If the ladder is flat or inverted, the idea is dead and no amount of
chart-reading rescues it.
"""
from __future__ import annotations
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr
from liq_m1 import load, GBP
from sweep_winrate import pivots

TODAY = 7.38
GBP_PT = TODAY * GBP
BPD = {"M1": 1440, "M5": 288, "M15": 96}


def reactions_before(s, A, lvl, upto, since, near=0.15, away=0.50, win=30):
    """How many times price came to `lvl`, was refused, and left - strictly
    BEFORE bar `upto`. Scans from `since` so the count is about recent
    behaviour rather than the whole history of the chart."""
    n = 0
    k = max(1, since)
    while k < upto:
        a = A[k]
        if not a or a <= 0:
            k += 1
            continue
        if abs(s.h[k] - lvl) <= near * a or abs(s.l[k] - lvl) <= near * a:
            # did it get refused? move away by `away` ATR without closing through
            hi = lo = s.c[k]
            through = False
            for m in range(k + 1, min(k + win, upto)):
                hi = max(hi, s.h[m])
                lo = min(lo, s.l[m])
                if (s.c[m] > lvl + away * a) and (s.l[k] <= lvl):
                    n += 1
                    k = m
                    through = True
                    break
                if (s.c[m] < lvl - away * a) and (s.h[k] >= lvl):
                    n += 1
                    k = m
                    through = True
                    break
            if not through:
                k += win
            continue
        k += 1
    return n


def run(tf="M1", pk=5, sweep_atr=0.10, wick=0.6460, buf=0.30, give=0.25,
        max_risk_atr=1.2, hold=240, cooldown=5, cost_frac=0.11,
        lookback=720, subset=None):
    s, SP = load(tf)
    A = watr(s, 14)
    va = sorted(x for x in A[100:] if x)
    cs = cost_frac / (statistics.median(SP) / va[len(va) // 2])
    out, busy = [], -1
    for (kb, px, side) in pivots(s, pk):
        if kb <= busy:
            continue
        a = A[kb]
        if not a or a <= 0:
            continue
        tside = -side
        need = px + side * sweep_atr * a
        sw, ext = None, None
        for k in range(kb + 1, min(kb + 120, len(s))):
            if (s.h[k] >= need) if side > 0 else (s.l[k] <= need):
                sw, ext = k, (s.h[k] if side > 0 else s.l[k])
                break
        if sw is None:
            continue
        rng = s.h[sw] - s.l[sw]
        disp = (abs(s.c[sw] - s.o[sw]) / rng) if rng > 0 else 1.0
        if disp > wick:
            continue
        j = None
        for k in range(sw + 1, min(sw + 120, len(s))):
            if (s.h[k] >= px) if tside > 0 else (s.l[k] <= px):
                j = k
                break
            ext = max(ext, s.h[k]) if side > 0 else min(ext, s.l[k])
        if j is None:
            continue
        if subset and not (subset[0] <= j < subset[1]):
            continue
        sp = SP[j] * cs
        entry = px + tside * sp / 2.0
        sl = ext - tside * buf * a
        risk = abs(entry - sl)
        if risk <= 0 or risk > max_risk_atr * a:
            continue

        # THE FEATURE, counted strictly before the level was even confirmed, so
        # no bar at or after the entry can contribute to it
        nreact = reactions_before(s, A, px, kb, max(0, kb - lookback))

        peak = entry
        px_out, kk = None, None
        for k in range(j, min(j + hold, len(s))):
            if (s.l[k] <= sl) if tside > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k
                break
            if k == j:
                continue
            peak = max(peak, s.h[k]) if tside > 0 else min(peak, s.l[k])
            up = tside * (peak - entry)
            if up > 0:
                c = entry + tside * up * (1.0 - give)
                sl = max(sl, c) if tside > 0 else min(sl, c)
        if px_out is None:
            kk = min(j + hold, len(s) - 1)
            px_out = s.c[kk]
        out.append((tside * ((px_out - tside * SP[kk] * cs / 2.0) - entry), nreact, tside))
        busy = kk + cooldown
    return out


def main():
    for tf in ("M1", "M5"):
        rows = run(tf)
        n = len(rows)
        tot = sum(r[0] for r in rows)
        s, _ = load(tf)
        days = len(s) / BPD[tf]
        print("=" * 88)
        print(f"  E-143 — {tf}: does a level that has already reacted react again?")
        print(f"  baseline {n} trades, {n/days:.1f}/day, "
              f"{100.0*sum(1 for r in rows if r[0]>0)/n:.1f}% win, {tot:+.1f} points")
        print("=" * 88)
        print(f"  {'prior reactions':<20}{'n':>7}{'share':>8}{'win%':>8}"
              f"{'points':>10}{'per trade':>12}")
        print("  " + "-" * 65)
        for lo, hi, lbl in ((0, 0, "0  never reacted"), (1, 1, "1  once"),
                            (2, 2, "2  twice"), (3, 99, "3+ three or more")):
            b = [r for r in rows if lo <= r[1] <= hi]
            if not b:
                continue
            p = sum(x[0] for x in b)
            print(f"  {lbl:<20}{len(b):>7}{100.0*len(b)/n:>7.1f}%"
                  f"{100.0*sum(1 for x in b if x[0]>0)/len(b):>7.1f}%"
                  f"{p:>10.1f}{p/len(b):>+12.4f}")
        means = []
        for lo, hi in ((0, 0), (1, 1), (2, 2), (3, 99)):
            b = [r for r in rows if lo <= r[1] <= hi]
            if b:
                means.append(sum(x[0] for x in b) / len(b))
        print(f"  MONOTONE (more reactions = better): "
              f"{'YES' if means == sorted(means) else 'NO'}"
              f"   ({' -> '.join(f'{m:+.4f}' for m in means)})")
        print()


if __name__ == "__main__":
    main()

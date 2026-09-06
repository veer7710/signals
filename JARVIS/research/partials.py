"""
E-147 — PARTIALS: does banking half early beat letting it all run?

Veer asked for partials on the chart. E-137 measured whole-position exits - fixed
targets, ATR trails, give-backs, the next level - and the give-back won. It never
tested SPLITTING the position, and a chart that draws a partial level nobody has
measured is a chart telling you to do something unknown.

THE TEST, on the shipped sweep setup with everything else unchanged:
    close `frac` of the position at `n` x risk
    let the remainder run on the same 25% give-back trail
Compared against the shipped whole-position exit.

The intuition for partials is real - it converts an open trade into a closed
profit and a free option - but it has a cost that is easy to miss: the half you
banked at 1R is the half that would have carried the trade that ran 6R, and this
system's whole edge is a trail with no target (E-137: every fixed target banked
less). So the question is whether the smoothing is worth the top slice.

Reported in POINTS, not R. E-074: the best per-trade gate set in this project
banked the LEAST money, and this is exactly the shape of question where R lies.
Also reported: max drawdown and worst trade, because the honest case FOR partials
is a smoother path, not a bigger total - and if that is what they buy, that has
to show up here or the argument is empty.
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


def run(tf="M1", part_r=0.0, part_frac=0.5, pk=5, sweep_atr=0.10, wick=0.6460,
        buf=0.30, give=0.25, max_risk_atr=1.2, hold=240, cooldown=5,
        cost_frac=0.11, subset=None):
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
        j = None
        for k in range(sw + 1, min(sw + 120, len(s))):
            if (s.h[k] >= px) if t > 0 else (s.l[k] <= px):
                j = k
                break
            ext = max(ext, s.h[k]) if side > 0 else min(ext, s.l[k])
        if j is None:
            continue
        if subset and not (subset[0] <= j < subset[1]):
            continue
        sp = SP[j] * cs
        entry = px + t * sp / 2.0
        sl = ext - t * buf * a
        risk = abs(entry - sl)
        if risk <= 0 or risk > max_risk_atr * a:
            continue
        tp = entry + t * part_r * risk if part_r > 0 else None

        booked = 0.0
        openf = 1.0
        peak = entry
        px_out, kk = None, None
        for k in range(j, min(j + hold, len(s))):
            if (s.l[k] <= sl) if t > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k
                break
            if k == j:
                continue
            # the partial is checked BEFORE the trail is advanced on this bar,
            # and never on the entry bar - same E-110 rule as everything else
            if tp is not None and openf > part_frac / 2 and (
                    (s.h[k] >= tp) if t > 0 else (s.l[k] <= tp)):
                booked += part_frac * (t * (tp - entry) - SP[k] * cs)
                openf -= part_frac
                tp = None
            peak = max(peak, s.h[k]) if t > 0 else min(peak, s.l[k])
            up = t * (peak - entry)
            if up > 0:
                c = entry + t * up * (1.0 - give)
                sl = max(sl, c) if t > 0 else min(sl, c)
        if px_out is None:
            kk = min(j + hold, len(s) - 1)
            px_out = s.c[kk]
        rest = openf * (t * ((px_out - t * SP[kk] * cs / 2.0) - entry))
        out.append(booked + rest)
        busy = kk + cooldown
    return out


def stats(r):
    eq = peak = mdd = 0.0
    for x in r:
        eq += x
        peak = max(peak, eq)
        mdd = max(mdd, peak - eq)
    return (len(r), 100.0 * sum(1 for x in r if x > 0) / len(r), sum(r),
            sum(r) / len(r), mdd, min(r))


def main():
    for tf in ("M1", "M5"):
        s, _ = load(tf)
        n = len(s)
        print("=" * 92)
        print(f"  E-147 — partials on {tf}: bank half early, or let it all run?")
        print("=" * 92)
        print(f"  {'exit':<28}{'n':>6}{'win%':>8}{'points':>9}{'per trade':>12}"
              f"{'maxDD GBP':>11}{'worst GBP':>11}")
        print("  " + "-" * 76)
        rows = [("no partial (shipped)", 0.0, 0.0)]
        for r_ in (0.5, 1.0, 1.5, 2.0):
            for f_ in (0.5, 0.33):
                rows.append((f"close {int(f_*100)}% at {r_:.1f}R", r_, f_))
        base = None
        for lbl, r_, f_ in rows:
            res = run(tf, part_r=r_, part_frac=f_)
            if len(res) < 40:
                continue
            N, W, P, PT, DD, WT = stats(res)
            if base is None:
                base = P
            print(f"  {lbl:<28}{N:>6}{W:>7.1f}%{P:>9.1f}{PT:>+12.4f}"
                  f"{DD*GBP_PT:>11.2f}{WT*GBP_PT:>11.2f}")
        # does the best partial hold out of sample?
        print("\n  out of sample, best partial vs shipped")
        for lbl, r_, f_ in (("shipped", 0.0, 0.0), ("close 50% at 1.0R", 1.0, 0.5)):
            a = stats(run(tf, part_r=r_, part_frac=f_, subset=(0, n // 2)))
            b = stats(run(tf, part_r=r_, part_frac=f_, subset=(n // 2, n)))
            print(f"    {lbl:<20} IS {a[2]:>7.1f} pts {a[3]:+.4f}/tr   "
                  f"OOS {b[2]:>7.1f} pts {b[3]:+.4f}/tr")
        print()


if __name__ == "__main__":
    main()

"""
E-140 — THE PER-TRADE SIZE PROBLEM, AND THE OBVIOUS PLACE TO FIX IT.

Veer: "0.1840 is that points if so that's a joke, i hit 30 to 80 points trading
liquidity sweeps... supertrend signals normally hit 3-4 points on average low
end thats alot dude thats 2-4 pound".

FIRST, THE UNITS, because they were never stated plainly and he was right to
ask. In this repo a "point" is 1.00 of XAUUSD price - one dollar. E-081's
GBP0.787 per point is 0.01 lots = 1 ounce, so a $1 move is $1 is about 79p.
That is the same unit he is using: his "3-4 points" being "2-4 pound" only
works if a point is a dollar, and it is.

    system per trade   +0.1119 points, in 2018 scale
                       x 7.38 for today's volatility = 0.83 points = 65p
    his SuperTrend     3-4 points = GBP2.40-3.10
    his sweeps         30-80 points

So our per-trade is roughly FOUR TIMES smaller than his SuperTrend average and
forty times smaller than his sweeps. He is not wrong. The system makes its money
from 23.6 trades a day, not from the size of any one of them - and that is
precisely the shape most exposed to cost, which is why 0.05 points of slippage
already takes 42% of it.

SECOND, THE LOGICAL FIX, and it is not "try harder on M1". E-132 measured the
cost of a trade in the only unit that compares across clocks:

    the same 0.40 spread is    0.220 of ATR on M1
                               0.088 on M5
                               0.047 on M15

M1 is the most expensive place on the chart to take a small move. The same
rules on a slower clock capture a bigger move per trade against a smaller
fraction of cost. That is arithmetic, not a hunch, and it is the first thing
that should have been tried.

Tested on M1, M5 and M15: same sweep, same wick filter, same stop beyond the
sweep extreme, same give-back, same risk cap. Only the clock changes.
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


def run(tf, pk=5, sweep_atr=0.10, buf=0.30, give=0.25, max_risk_atr=1.2,
        wick=0.6460, hold=240, cooldown=5, cost_frac=0.11, slip=0.0,
        subset=None):
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
        out.append(tside * ((px_out - tside * SP[kk] * cs / 2.0) - entry) - slip)
        busy = kk + cooldown
    return out


def main():
    print("=" * 100)
    print("  E-140 — the same sweep rules on M1, M5 and M15")
    print("  A 'point' here is $1.00 of XAUUSD. 0.01 lots = 1 oz = GBP0.787 per")
    print("  point (E-081) - the same unit Veer uses when he says 3-4 points is")
    print("  2-4 pound. All 'today' figures scale 2018 by x7.38 (E-132).")
    print("=" * 100)
    print(f"  {'TF':>4}{'n':>7}{'/day':>7}{'win%':>7}{'pts 2018':>10}"
          f"{'per trade':>11}{'per trade TODAY':>17}{'GBP/day':>10}{'GBP total':>11}")
    print("  " + "-" * 84)
    keep = {}
    for tf in ("M1", "M5", "M15"):
        r = run(tf)
        if len(r) < 40:
            continue
        s, _ = load(tf)
        days = len(s) / BPD[tf]
        p = sum(r)
        w = 100.0 * sum(1 for x in r if x > 0) / len(r)
        per_today = (p / len(r)) * TODAY
        print(f"  {tf:>4}{len(r):>7}{len(r)/days:>7.1f}{w:>6.1f}%{p:>10.1f}"
              f"{p/len(r):>+11.4f}{per_today:>13.2f} pts"
              f"{p*GBP_PT/days:>10.2f}{p*GBP_PT:>11.2f}")
        keep[tf] = (r, days)

    print("\n  COST AND SLIPPAGE — the whole reason to look at a slower clock.")
    print("  E-132: a 0.40 spread is 0.220 of ATR on M1, 0.088 on M5, 0.047 on M15.")
    print(f"\n  {'TF':>4}{'spread 0.20':>13}{'0.30':>9}{'0.40':>9}"
          f"   |{'slip 0.02':>11}{'0.05':>9}{'0.10':>9}{'0.20':>9}")
    print("  " + "-" * 77)
    for tf in keep:
        costs = [sum(run(tf, cost_frac=c)) for c in (0.110, 0.165, 0.220)]
        slips = [sum(run(tf, slip=x)) for x in (0.02, 0.05, 0.10, 0.20)]
        print(f"  {tf:>4}" + "".join(f"{c:>13.1f}" if i == 0 else f"{c:>9.1f}"
                                     for i, c in enumerate(costs))
              + "   |" + "".join(f"{x:>11.1f}" if i == 0 else f"{x:>9.1f}"
                                 for i, x in enumerate(slips)))

    print("\n  OUT OF SAMPLE")
    print(f"  {'TF':>4}{'IS n':>7}{'IS pts':>10}{'IS/tr':>10}"
          f"{'OOS n':>7}{'OOS pts':>10}{'OOS/tr':>10}")
    print("  " + "-" * 60)
    for tf in keep:
        s, _ = load(tf)
        n = len(s)
        a = run(tf, subset=(0, n // 2))
        b = run(tf, subset=(n // 2, n))
        if not a or not b:
            continue
        print(f"  {tf:>4}{len(a):>7}{sum(a):>10.1f}{sum(a)/len(a):>+10.4f}"
              f"{len(b):>7}{sum(b):>10.1f}{sum(b)/len(b):>+10.4f}")


if __name__ == "__main__":
    main()

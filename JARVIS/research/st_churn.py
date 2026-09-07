"""
E-175 — THE SUPERTREND CHURN. Why the live panel showed what it showed.

Veer ran SUPERTREND_SNIPER on a live chart for four days and the panel read
304 trades, 62.8 per day, -117.1 points, of which 88% was transaction cost, and
the row "exit adds -32.1pt" - meaning the whole exit stack (trail, stall,
reversal, level targets) banked LESS than simply holding to the opposite flip.

That is two separate claims and this file tests both:

  1. GROSS. Strip every cost and every exit rule. Enter on the flip, leave on
     the opposite flip. If gross is ~0 then no parameter and no exit rule can
     save it, because there is nothing there to keep.
  2. CHURN. If gross IS positive, then the fix is frequency: a slower clock or
     a lazier SuperTrend flips less often and pays the spread fewer times.
     Sweep (ATR length, multiplier) x clock and watch cost as a share.

Cost is charged with engine.cost_scale (E-173): the same PRICE on every clock,
which is the whole point of asking whether a slower clock helps.
"""
from __future__ import annotations
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, cost_scale
from liq_m1 import load, GBP
from supertrend_rescue import st_state

TODAY = 7.38
GBP_PT = TODAY * GBP
BPD = {"M1": 1440, "M5": 288, "M15": 96}


def flips(s, d):
    """Every direction change, as (bar, new_dir). The signal, nothing else."""
    out = []
    for i in range(1, len(s)):
        if d[i] and d[i - 1] and d[i] != d[i - 1]:
            out.append((i, -d[i]))      # Pine: d=-1 bullish, so trade dir = -d
    return out


def book(s, SP, cs, d, hold=None):
    """Flip in, opposite flip out. No stop, no trail, no target, no filter.
    Returns (gross_points, cost_points) so the two can be read apart."""
    fl = flips(s, d)
    gross, cost = [], []
    for k, (i, t) in enumerate(fl):
        if i + 1 >= len(s):
            break
        j = fl[k + 1][0] if k + 1 < len(fl) else len(s) - 1
        if hold:
            j = min(j, i + hold)
        # entry and exit both at the NEXT bar's open: a flip is only known at
        # the close of the bar that made it.
        e, x = s.o[i + 1], s.o[min(j + 1, len(s) - 1)]
        gross.append(t * (x - e))
        cost.append(SP[i] * cs)          # one round trip
    return gross, cost


def main():
    print("=" * 96)
    print("  E-175 — SuperTrend: is there anything there before cost?")
    print("  flip in, opposite flip out. no stop, no trail, no stall, no filter.")
    print("=" * 96)
    print(f"  {'tf':>4}{'len':>5}{'mult':>6}{'n':>7}{'/day':>7}{'gross':>10}"
          f"{'cost':>9}{'net':>9}{'cost%':>7}{'per trade':>11}")
    print("  " + "-" * 88)
    for tf in ("M1", "M5", "M15"):
        s, SP = load(tf)
        A = watr(s, 14)
        cs = cost_scale(SP, A)
        days = len(s) / BPD[tf]
        for ln, mult in ((7, 1.2), (7, 2.0), (10, 3.0), (14, 3.0), (20, 4.0)):
            d, _, _ = st_state(s, ln, mult)
            g, c = book(s, SP, cs, d)
            if len(g) < 30:
                continue
            G, C = sum(g), sum(c)
            share = 100.0 * C / abs(G - C) if (G - C) else 0.0
            print(f"  {tf:>4}{ln:>5}{mult:>6.1f}{len(g):>7}{len(g)/days:>7.1f}"
                  f"{G:>10.1f}{-C:>9.1f}{G - C:>9.1f}{share:>6.0f}%"
                  f"{(G - C)/len(g):>+11.4f}")
        print()

    # the decisive column: gross with a t-stat, on the shipped setting
    print("  the shipped setting (7, 1.2), GROSS only, with a t-stat:")
    for tf in ("M1", "M5", "M15"):
        s, SP = load(tf)
        d, _, _ = st_state(s, 7, 1.2)
        g, _ = book(s, SP, 0.0, d)
        m = sum(g) / len(g)
        t = m / (statistics.pstdev(g) / len(g) ** 0.5)
        print(f"    {tf:>4}  n {len(g):>6}  gross {sum(g):>+9.1f} pts  "
              f"{m:>+8.4f}/trade  t {t:>+6.2f}")


if __name__ == "__main__":
    main()

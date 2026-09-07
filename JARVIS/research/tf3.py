"""
E-174 — M3, THE CLOCK NOBODY HAS EVER MEASURED.

Veer: "but we targeting m3 m5 m15". M1, M5 and M15 have data files. M3 does
not, and it has therefore never been tested - it has been quietly assumed to
sit between M1 and M5. This builds M3 from the real M1 bars and asks the same
fixed-target question as E-172, with the E-173-corrected cost.

The spread of a 3-minute bar is taken as the MAX of its three minutes, which is
the conservative reading: it charges the worst spread inside the bar, not the
best.

The alignment caveat: bars are grouped from the first M1 bar in the file, so the
3-minute boundaries are wherever that bar fell, not a broker's clock. On a
scale-free question like "what win rate does a 1R target get" that does not
matter; do not read this as a bar-for-bar replica of a broker's M3 chart.
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Series
from liq_m1 import load, GBP
import tp1r

TODAY = 7.38
GBP_PT = TODAY * GBP


def build(factor):
    """M1 -> factor-minute bars, carrying the spread as the worst inside the bar."""
    s, SP = load("M1")
    ts, o, h, l, c, sp = [], [], [], [], [], []
    for i in range(0, len(s) - factor + 1, factor):
        ts.append(s.ts[i]); o.append(s.o[i])
        h.append(max(s.h[i:i + factor])); l.append(min(s.l[i:i + factor]))
        c.append(s.c[i + factor - 1]); sp.append(max(SP[i:i + factor]))
    return Series(ts, o, h, l, c), sp


def main():
    print("=" * 92)
    print("  E-174 — M3 built from real M1 bars, E-165 fills, E-173 cost")
    print("  break-even needs: 1.0R -> 50%   0.5R -> 67%   0.25R -> 80%   (before cost)")
    print("=" * 92)
    for factor in (2, 3, 4):
        d = build(factor)
        print(f"\n  ---- M{factor} ({len(d[0]):,} bars) ----")
        print(f"  {'target':>8}{'n':>7}{'win%':>8}{'need':>7}{'points':>10}"
              f"{'per trade':>11}{'GBP @0.01':>11}")
        for tgtR in (0.5, 1.0, 1.5, 2.0, 3.0):
            r = tp1r.book(None, tgtR, data=d)
            if len(r) < 30:
                continue
            w = 100.0 * sum(1 for x in r if x > 0) / len(r)
            need = 100.0 / (1.0 + tgtR)
            print(f"  {tgtR:>8.2f}{len(r):>7}{w:>7.1f}%{need:>6.0f}%"
                  f"{sum(r):>10.1f}{sum(r)/len(r):>+11.4f}{sum(r)*GBP_PT:>+11.0f}")


if __name__ == "__main__":
    main()

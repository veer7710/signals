"""
E-062 — Does the target-size gradient survive out of sample?

E-061 found that on GOLD, the edge over a matched random control grows
MONOTONICALLY with target size, on both timeframes:

    target        1R      1.5R       2R       3R       5R
    GOLD 15m   +0.07     +0.09    +0.11    +0.21    +0.37
    GOLD 1h    +0.07     +0.11    +0.15    +0.24    +0.48

A monotone gradient in the same direction on two independent timeframes is a
much better sign than one excellent cell, and it has a mechanism: the cost is
fixed per round trip, so a bigger target dilutes it. But 60 cells were
examined and the best of 60 noise draws always looks good.

So: fit NOTHING, and re-run the same grid on the LAST 30% of the data only.
The first 70% is what E-061 saw. If the gradient is real it appears again in
data that had no chance to influence it.

Run:  python3 JARVIS/research/oos.py
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, early
from engine import Series

TARGETS = [1.0, 1.5, 2.0, 3.0, 5.0]


def slice_series(s: Series, frm: float, to: float) -> Series:
    a = int(len(s) * frm)
    b = int(len(s) * to)
    return Series(s.ts[a:b], s.o[a:b], s.h[a:b], s.l[a:b], s.c[a:b])


def row(s, costs, stop_atr, cap):
    out = []
    for rr in TARGETS:
        real = early.simulate(s, costs, "close", stop_atr=stop_atr, rr=rr, max_bars=cap)
        ctrl = early.simulate(s, costs, "random", stop_atr=stop_atr, rr=rr, max_bars=cap)
        n, e, w, t = early.stat(real)
        _n2, ec, _w2, _t2 = early.stat(ctrl)
        out.append((n, e - ec, e, t))
    return out


def main():
    print("=" * 92)
    print("  E-062  OUT OF SAMPLE — the last 30% only, nothing fitted to it")
    print("=" * 92)

    for tf in ("15m", "1h"):
        s = engine.load("GOLD", tf)
        costs = study.COSTS.get("GOLD", engine.Costs())
        iss = slice_series(s, 0.0, 0.70)
        oos = slice_series(s, 0.70, 1.0)
        print(f"\n  GOLD {tf}   in-sample {len(iss)} bars, out-of-sample {len(oos)} bars")
        for stop_atr, cap in ((1.5, 50), (2.0, 50), (3.0, 50)):
            ri = row(iss, costs, stop_atr, cap)
            ro = row(oos, costs, stop_atr, cap)
            print(f"\n    stop {stop_atr:g} ATR, cap {cap} bars")
            print(f"      {'':<12}" + "".join(f"{f'{t:g}R':>12}" for t in TARGETS))
            print(f"      {'IS edge':<12}" + "".join(f"{c[1]:>+12.3f}" for c in ri))
            print(f"      {'OOS edge':<12}" + "".join(f"{c[1]:>+12.3f}" for c in ro))
            print(f"      {'OOS exp':<12}" + "".join(f"{c[2]:>+12.3f}" for c in ro))
            print(f"      {'OOS n':<12}" + "".join(f"{c[0]:>12}" for c in ro))
            mono_i = all(ri[k][1] <= ri[k + 1][1] + 0.02 for k in range(len(ri) - 1))
            mono_o = all(ro[k][1] <= ro[k + 1][1] + 0.02 for k in range(len(ro) - 1))
            print(f"      gradient rises with target:  IS {'yes' if mono_i else 'no'}"
                  f"   OOS {'yes' if mono_o else 'no'}")

    print("\n" + "=" * 92)
    print("  THE TENSION THIS CREATES WITH THE STATED DESIGN")
    print("=" * 92)
    print("""
  Veer wants hundreds of positions a day, each netting GBP 1-5. The geometry
  that carries the edge is the opposite shape: a WIDER stop, a BIGGER target
  and a LONGER hold, which means FEWER trades that are each worth more.

  That is not a preference, it is the cost arithmetic. At 0.03 lots the round
  trip costs GBP 1.33, and it is charged once per trade whatever the trade is
  worth. A 1R target pays it out of a small gross; a 5R target pays the same
  fee out of a gross five times larger. Trading more often multiplies the fee
  and does not multiply the edge.

  Both can be true at once and the numbers above say which is which:
    · the SIGNAL can fire hundreds of times a day - that costs nothing
    · the POSITION should be taken with a target big enough to survive the fee
""")


if __name__ == "__main__":
    main()

"""
E-061 — The geometry search. Stop, target and time cap, on GOLD, at real cost.

Veer trades gold on M1 (D-010). E-060 established two things at his REAL costs:
  · the close entry and the band entry are the same thing (band beat close in
    3 of 8 markets; pooled they are identical). Early entry is not the lever.
  · on GOLD the entry DOES beat a matched random control - +0.27R on 15m and
    +0.08R on 1h - while on EURUSD/GBPUSD it does not. Gold is the whole
    edge and the FX pairs were dragging every pooled number down.

So this searches the only thing left that is free: the GEOMETRY. Stop distance,
target multiple, time cap. Every cell is run with a matched random control at
the SAME geometry, because a wider target lifts a random entry too and without
the control that lift reads as skill.

MULTIPLE TESTING IS THE WHOLE DANGER HERE. 4 stops x 5 targets x 3 caps = 60
cells per market. The best of 60 noise draws looks excellent. Rules:
  · every cell reports expectancy MINUS its own random control
  · a cell only counts if it wins on BOTH gold timeframes
  · the t-statistic is printed and the threshold is stated, not implied

Run:  python3 JARVIS/research/geometry.py
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, early

STOPS   = [1.0, 1.5, 2.0, 3.0]
TARGETS = [1.0, 1.5, 2.0, 3.0, 5.0]
CAPS    = [20, 50, 120]


def cell(s, costs, stop_atr, rr, cap):
    real = early.simulate(s, costs, "close", stop_atr=stop_atr, rr=rr, max_bars=cap)
    ctrl = early.simulate(s, costs, "random", stop_atr=stop_atr, rr=rr, max_bars=cap)
    nr, er, wr, tr = early.stat(real)
    nc, ec, wc, tc = early.stat(ctrl)
    return nr, er, wr, tr, ec


def main():
    print("=" * 94)
    print("  E-061  GEOMETRY SEARCH ON GOLD, AT VEER'S REAL 0.46 SPREAD")
    print("  Every cell shows expectancy MINUS its own matched random control.")
    print("  60 cells per timeframe: the best of 60 noise draws looks great, so")
    print("  a cell only counts if it wins on BOTH 15m and 1h.")
    print("=" * 94)

    res = {}
    for tf in ("15m", "1h"):
        s = engine.load("GOLD", tf)
        costs = study.COSTS.get("GOLD", engine.Costs())
        print(f"\n  GOLD {tf}   (edge over random, in R)")
        print(f"  {'stop':<7}{'cap':<6}" + "".join(f"{f'{t:g}R':>11}" for t in TARGETS))
        for stop_atr in STOPS:
            for cap in CAPS:
                row = f"  {stop_atr:<7.1f}{cap:<6}"
                for rr in TARGETS:
                    n, e, w, t, ec = cell(s, costs, stop_atr, rr, cap)
                    if n < 40:
                        row += f"{'-':>11}"
                        continue
                    res[(tf, stop_atr, cap, rr)] = (n, e, w, t, e - ec)
                    row += f"{e - ec:>+11.3f}"
                print(row)

    print("\n" + "=" * 94)
    print("  CELLS THAT BEAT THEIR CONTROL ON BOTH TIMEFRAMES")
    print("=" * 94)
    print(f"  {'stop':<7}{'cap':<6}{'target':<9}"
          f"{'15m edge':>11}{'1h edge':>11}{'15m exp':>10}{'1h exp':>10}"
          f"{'15m t':>8}{'1h t':>8}{'n 15m':>7}{'n 1h':>7}")
    keep = []
    for stop_atr in STOPS:
        for cap in CAPS:
            for rr in TARGETS:
                a = res.get(("15m", stop_atr, cap, rr))
                b = res.get(("1h", stop_atr, cap, rr))
                if not a or not b:
                    continue
                if a[4] > 0 and b[4] > 0:
                    keep.append((a[4] + b[4], stop_atr, cap, rr, a, b))
    keep.sort(reverse=True)
    for _sc, stop_atr, cap, rr, a, b in keep[:15]:
        print(f"  {stop_atr:<7.1f}{cap:<6}{rr:<9.1f}"
              f"{a[4]:>+11.3f}{b[4]:>+11.3f}{a[1]:>+10.3f}{b[1]:>+10.3f}"
              f"{a[3]:>+8.2f}{b[3]:>+8.2f}{a[0]:>7}{b[0]:>7}")
    print(f"\n  {len(keep)} of 60 cells beat their control on both timeframes.")
    print("  Under the null about 15 of 60 would do so by chance (0.5 x 0.5),")
    print("  so the COUNT alone proves nothing - read the t column and the")
    print("  size of the edge, and prefer a cell whose neighbours also work.")


if __name__ == "__main__":
    main()

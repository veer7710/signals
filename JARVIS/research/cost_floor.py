"""
WHICH MARKET AND TIMEFRAME SHOULD BE TRADED AT ALL?

Asked before any strategy question, because it constrains every one of them.

A trade must clear the round-trip cost before it can make anything. So for each
market and timeframe there is a minimum holding period below which trading is
arithmetically pointless regardless of how good the signal is - the expected
move simply does not cover the spread by enough to matter.

E-037 already showed 15m FX round-trip cost is 46-49% of a typical bar. That is
a structural fact about the instrument, not a fact about a strategy, and it
explains why every FX result in this repo came back negative. This generalises
that observation into a table.

THE MEASURE
  For each holding period N, take the typical absolute move over N bars (the
  median, not the mean - the mean is dragged by tails you cannot rely on) and
  divide by the round-trip cost. That ratio is how many times the cost the
  average trade has to work with.

  ratio < 2   : hopeless. Cost eats half of a typical move.
  ratio 2-5   : a real edge could survive, but nothing sloppy will.
  ratio 5-10  : workable.
  ratio > 10  : cost is not the binding constraint.

This says nothing about whether an edge exists. It says where one would have
room to exist if it did - which is the question to settle first.

Run:  python3 JARVIS/research/cost_floor.py
"""
from __future__ import annotations
import os, sys, statistics as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study


def run(sym, tf):
    s = engine.load(sym, tf)
    c = study.COSTS.get(sym, engine.Costs())
    cost = c.spread + 2 * c.slippage
    if cost <= 0:
        print(f"  {sym} {tf}: no cost model"); return
    bars_per_day = {"15m": 96, "1h": 24}.get(tf, 24)

    print(f"\n  {sym} {tf}   round-trip cost {cost:.5f}")
    print(f"     {'hold':>6}{'~time':>10}{'median move':>14}{'x cost':>9}   verdict")
    for n in (1, 2, 4, 8, 16, 32, 64, 128):
        moves = []
        for i in range(250, len(s) - n, max(1, n // 2)):
            moves.append(abs(s.c[i + n] - s.c[i]))
        if len(moves) < 30:
            continue
        med = st.median(moves)
        ratio = med / cost
        hrs = n * (0.25 if tf == "15m" else 1.0)
        tstr = f"{hrs:.1f}h" if hrs < 48 else f"{hrs/24:.1f}d"
        v = ("hopeless" if ratio < 2 else
             "needs a real edge" if ratio < 5 else
             "workable" if ratio < 10 else "cost not binding")
        print(f"     {n:>6}{tstr:>10}{med:>14.5f}{ratio:>9.1f}   {v}")
    return


def m1_extrapolation():
    """What this implies for M1 gold - the timeframe actually traded.

    LABELLED AS AN EXTRAPOLATION, not a measurement. There is no M1 data in this
    repo. Price range scales roughly with the square root of time under a random
    walk, and E-037 found these series ARE statistically random walks, so the
    scaling is better justified here than it usually would be - but it is still
    an inference and it stops being one the moment the M1 export arrives."""
    print(f"\n{'='*72}\n  IMPLIED M1 GOLD - EXTRAPOLATED, NOT MEASURED\n{'='*72}")
    s = engine.load("GOLD", "15m")
    import statistics as _st
    moves = [abs(s.c[i + 1] - s.c[i]) for i in range(250, len(s) - 1)]
    med15 = _st.median(moves)
    cost = study.COSTS["GOLD"].spread + 2 * study.COSTS["GOLD"].slippage
    print(f"     measured: median 15m 1-bar move {med15:.3f}, cost {cost:.2f}"
          f"  -> {med15/cost:.1f}x")
    print(f"\n     {'hold':>8}{'implied move':>15}{'x cost':>9}   verdict")
    for mins in (1, 2, 3, 5, 10, 15, 30, 60):
        implied = med15 * (mins / 15.0) ** 0.5
        ratio = implied / cost
        v = ("hopeless" if ratio < 2 else "needs a real edge" if ratio < 5
             else "workable" if ratio < 10 else "cost not binding")
        print(f"     {str(mins)+'m':>8}{implied:>15.3f}{ratio:>9.1f}   {v}")
    print("\n     A 1-minute hold on gold has about twice the spread to work")
    print("     with. That is not impossible, but nothing sloppy survives it -")
    print("     and it explains why an M1 scalp that looks right on the chart")
    print("     still bleeds. Holding minutes rather than seconds is what buys")
    print("     the room.")


if __name__ == "__main__":
    print(__doc__)
    for sym in ("GOLD", "US500", "EURUSD", "GBPUSD"):
        for tf in ("15m", "1h"):
            try: run(sym, tf)
            except FileNotFoundError: pass
    print("\n" + "=" * 72)
    m1_extrapolation()
    print("\n" + "=" * 72)
    print("  Read this before choosing a strategy, not after. A signal cannot")
    print("  fix an instrument whose typical move does not clear its own spread.")
    print("=" * 72)

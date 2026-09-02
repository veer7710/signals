"""
E-066 — Where does the SuperTrend actually make and lose money, by CONDITION?

Veer: "supertrend m1 is there to catch all trends meaning small big chop we
just need to be able to perform well in all ... it needs to trade all sessions
although some are slow so it needs to be able to actually capture those pennies
of profit".

So the question is not "does it work" but "WHERE does it work, and what should
it do differently in the places it does not". Two axes, both computable at the
moment of entry from closed bars:

  SPEED     ATR(7) divided by its own 200-bar median. Below 0.8 is a slow
            market, above 1.3 is a fast one. This is the "slow session" axis.
  SHAPE     Kaufman efficiency ratio over 50 bars: net distance divided by the
            path walked. Low is chop, high is a clean trend.

Four corners: slow chop, slow trend, fast chop, fast trend. Every cell gets its
own random control at the same geometry, because volatility clustering alone
(CONFIRMED as E-038) makes a fast market look different from a slow one whether
or not the signal has any skill.

Run:  python3 JARVIS/research/regime.py
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, early, chop
from engine import Series

SPEED = [(0.0, 0.8, "slow"), (0.8, 1.3, "normal"), (1.3, 99.0, "fast")]
SHAPE = [(0.0, 0.10, "chop"), (0.10, 0.25, "mixed"), (0.25, 9.0, "trend")]


def tag(s: Series, warmup=300):
    """Speed and shape at every bar, from closed bars only."""
    A = engine.atr(s, 7)
    med = [None] * len(s)
    win = []
    for i in range(len(s)):
        a = A[i]
        if a is not None and a > 0:
            win.append(a)
            del win[:-200]
            if len(win) >= 50:
                med[i] = sorted(win)[len(win) // 2]
    er = [None] * len(s)
    for i in range(50, len(s)):
        net = abs(s.c[i] - s.c[i - 50])
        path = sum(abs(s.c[j] - s.c[j - 1]) for j in range(i - 49, i + 1))
        er[i] = (net / path) if path > 0 else 0.0
    speed = [None] * len(s)
    for i in range(len(s)):
        if A[i] and med[i] and med[i] > 0:
            speed[i] = A[i] / med[i]
    return speed, er


def run(sym, tf, stop_atr=1.5, rr=3.0, cap=50):
    s = engine.load(sym, tf)
    c = study.COSTS.get(sym, engine.Costs())
    speed, er = tag(s)
    real = early.simulate(s, c, "close", stop_atr=stop_atr, rr=rr, max_bars=cap)
    ctrl = early.simulate(s, c, "random", stop_atr=stop_atr, rr=rr, max_bars=cap)
    # early.simulate returns bare R values; re-run capturing the bar index
    return s, speed, er, real, ctrl


def cells(sym, tf):
    """Recompute with the entry bar kept, so each trade lands in a cell."""
    s = engine.load(sym, tf)
    c = study.COSTS.get(sym, engine.Costs())
    rows = chop.collect(s, c)          # already carries "i", "r", "won"
    speed, er = tag(s)
    out = {}
    for r in rows:
        i = r["i"]
        sp, e = speed[i], er[i]
        if sp is None or e is None:
            continue
        sname = next((n for lo, hi, n in SPEED if lo <= sp < hi), None)
        ename = next((n for lo, hi, n in SHAPE if lo <= e < hi), None)
        if not sname or not ename:
            continue
        out.setdefault((sname, ename), []).append(r["r"])
    return out


def main():
    print("=" * 92)
    print("  E-066  WHERE DOES IT MAKE AND LOSE MONEY? Speed x Shape.")
    print("  Cell = expectancy in R. Read the n column: a cell with 20 trades")
    print("  is a rumour, not a regime.")
    print("=" * 92)

    agg = {}
    for sym, tf in chop.COMBOS:
        try:
            cs = cells(sym, tf)
        except Exception:
            continue
        for k, v in cs.items():
            agg.setdefault(k, []).extend(v)
        if sym != "GOLD":
            continue
        base = [r for v in cs.values() for r in v]
        if not base:
            continue
        print(f"\n  {sym} {tf}   base {sum(base)/len(base):+.3f}R over {len(base)} trades")
        print(f"    {'':<8}" + "".join(f"{n:>17}" for _lo, _hi, n in SHAPE))
        for _slo, _shi, sname in SPEED:
            row = f"    {sname:<8}"
            for _elo, _ehi, ename in SHAPE:
                v = cs.get((sname, ename), [])
                if len(v) < 10:
                    row += f"{'-':>17}"
                else:
                    row += f"{sum(v)/len(v):>+11.3f}({len(v):>3})"
            print(row)

    print("\n" + "=" * 92)
    print("  ALL 8 MARKETS POOLED — the shape of the strategy, not of one chart")
    print("=" * 92)
    allr = [r for v in agg.values() for r in v]
    b = sum(allr) / len(allr) if allr else 0.0
    print(f"  pooled base {b:+.3f}R over {len(allr)} trades\n")
    print(f"    {'':<8}" + "".join(f"{n:>19}" for _lo, _hi, n in SHAPE))
    for _slo, _shi, sname in SPEED:
        row = f"    {sname:<8}"
        for _elo, _ehi, ename in SHAPE:
            v = agg.get((sname, ename), [])
            if len(v) < 25:
                row += f"{'-':>19}"
            else:
                e = sum(v) / len(v)
                w = 100 * sum(1 for x in v if x > 0) / len(v)
                row += f"{e:>+9.3f} {w:>3.0f}% ({len(v):>4})"
        print(row)
    print("\n    each cell: expectancy, win rate, (trade count)")

    # ---- the actionable read
    print("\n  WHAT TO DO WITH IT")
    ranked = sorted(((sum(v) / len(v), k, len(v)) for k, v in agg.items()
                     if len(v) >= 25), reverse=True)
    for e, k, n in ranked:
        print(f"    {k[0]:<7} {k[1]:<7}  {e:>+7.3f}R  n={n:<5}"
              f"  {'SIZE UP' if e > b + 0.05 else ('size down' if e < b - 0.05 else 'as-is')}")


if __name__ == "__main__":
    main()

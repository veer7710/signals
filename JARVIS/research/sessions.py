"""
E-055 — Sessions. Do session opens really create different trends?

Veer: "think in terms of sessions sometimes session opens create diffrent
trends".

Testable, and the trap is obvious in advance: there are 24 hours and 4 or 5
session labels, so SOMETHING will look good by chance. The defence is the
same as in E-052 - every cell is scored against that market's own base rate,
every market is shown, and the multiple-testing arithmetic is printed rather
than left to the reader.

Timestamps in this repo's data are UTC. London opens 07:00 UTC, New York
12:00-13:00 UTC depending on daylight saving, Tokyo 23:00-00:00. The session
blocks below are deliberately coarse for that reason: an hour-precise boundary
that moves twice a year is a boundary this data cannot resolve.

Run:  python3 JARVIS/research/sessions.py
"""
from __future__ import annotations
import os, sys, math, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, chop

SESSIONS = [
    ("Asia",        0, 7),     # Tokyo through the London pre-open
    ("London open", 7, 10),    # the open itself
    ("London",     10, 12),
    ("NY overlap", 12, 16),    # both books live - the fattest hours
    ("NY late",    16, 21),
    ("Close/thin", 21, 24),
]


def hour_of(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).hour


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def main():
    combos = chop.COMBOS
    store = {}
    for sym, tf in combos:
        s = engine.load(sym, tf)
        costs = study.COSTS.get(sym, engine.Costs())
        rows = chop.collect(s, costs)
        if len(rows) < 100:
            continue
        store[(sym, tf)] = (rows, s)

    print("=" * 86)
    print("  E-055  SESSIONS — does the hour of entry change the outcome?")
    print("  Cell = expectancy in that block MINUS that market's own base rate.")
    print("  A real session effect has the SAME SIGN across a column.")
    print("=" * 86)

    for sym, tf in store:
        rows, s = store[(sym, tf)]
        print(f"  {sym} {tf}: {len(rows)} signals, "
              f"base {sum(r['r'] for r in rows)/len(rows):+.3f}R")

    print(f"\n  {'market':<14}" + "".join(f"{nm:>13}" for nm, a, b in SESSIONS))
    below = [0] * len(SESSIONS)
    seen = [0] * len(SESSIONS)
    counts = {nm: 0 for nm, a, b in SESSIONS}

    for (sym, tf), (rows, s) in store.items():
        base = sum(r["r"] for r in rows) / len(rows)
        cells = []
        for bi, (nm, a, b) in enumerate(SESSIONS):
            sel = [r for r in rows if a <= hour_of(s.ts[r["i"]]) < b]
            counts[nm] += len(sel)
            if len(sel) < 25:
                cells.append(f"{'-':>13}")
                continue
            e = sum(r["r"] for r in sel) / len(sel)
            cells.append(f"{e - base:>+13.3f}")
            seen[bi] += 1
            if e < base:
                below[bi] += 1
        print(f"  {sym+' '+tf:<14}" + "".join(cells))

    print(f"  {'BELOW base':<14}"
          + "".join(f"{f'{below[i]}/{seen[i]}':>13}" for i in range(len(SESSIONS))))
    print(f"  {'signals':<14}"
          + "".join(f"{counts[nm]:>13}" for nm, a, b in SESSIONS))

    n_cells = len(SESSIONS)
    print(f"\n  MULTIPLE TESTING: {n_cells} session blocks examined.")
    print(f"  Under the null, P(a block lands >=7 of 8 on one side) is about")
    print(f"  3.5%, so roughly {n_cells * 0.035:.1f} such block(s) are expected by")
    print(f"  chance alone. Count what you see before believing any of it.")

    # ---- the finer cut: by hour, pooled, for the market that matters
    print("\n" + "=" * 86)
    print("  GOLD ONLY, BY HOUR — the instrument actually traded")
    print("=" * 86)
    for tf in ("15m", "1h"):
        if ("GOLD", tf) not in store:
            continue
        rows, s = store[("GOLD", tf)]
        base = sum(r["r"] for r in rows) / len(rows)
        print(f"\n  GOLD {tf}   base {base:+.3f}R over {len(rows)} signals")
        print(f"  {'hour UTC':<10}{'n':>6}{'expectancy':>13}{'vs base':>10}"
              f"{'P(+1R first)':>14}")
        for h in range(24):
            sel = [r for r in rows if hour_of(s.ts[r["i"]]) == h]
            if len(sel) < 15:
                continue
            e = sum(r["r"] for r in sel) / len(sel)
            k = sum(1 for r in sel if r["won"])
            print(f"  {h:02d}:00     {len(sel):>6}{e:>+12.3f}R{e-base:>+9.3f}"
                  f"{100*k/len(sel):>13.1f}%")


if __name__ == "__main__":
    main()

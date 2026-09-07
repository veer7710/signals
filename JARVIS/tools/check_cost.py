#!/usr/bin/env python3
"""
Find hand-rolled cost scales in JARVIS/research.

E-173. The cost charged per trade was written inline, one line at a time, in
twenty-two separate files, always as

    cs = 0.11 / (median(spread) / median(ATR))

and always re-derived FROM THE TIMEFRAME BEING TESTED. That forces spread/ATR to
0.11 on every clock, which is backwards: the spread is a fixed PRICE, and a
slower clock's larger ATR is exactly what makes it cheaper. The line charged M5
2.5x and M15 4.6x what those clocks actually pay, and every M5/M15 result in
this repo was measured through it.

`engine.cost_scale` is now the only correct implementation. This tool exists so
a twenty-third copy cannot be written quietly.

    python3 JARVIS/tools/check_cost.py          # report
    python3 JARVIS/tools/check_cost.py --strict # exit 1 on any hand-rolled copy
"""
from __future__ import annotations
import os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "research")

# 0.11 divided by anything that smells like a measured ratio, or a bare
# median(spread)/median(ATR) being used as a cost basis.
# `0.11 / <anything>` is the bug's signature. The second alternative catches the
# same ratio hidden behind a name - but only when it is built from a SPREAD, so
# a median over volume or range is not a false positive.
HAND = re.compile(r"0\.11\s*/\s*[\(\w]|"
                  r"^\s*\w+\s*=\s*(?:statistics\.|stt\.)?median\(SP\w*\)\s*/",
                  re.M)
SAFE = re.compile(r"cost_scale|COST_M1_SPREAD_ATR")


def main():
    strict = "--strict" in sys.argv
    bad = []
    for f in sorted(os.listdir(ROOT)):
        if not f.endswith(".py"):
            continue
        p = os.path.join(ROOT, f)
        src = open(p).read()
        for m in HAND.finditer(src):
            line = src[:m.start()].count("\n") + 1
            text = src.splitlines()[line - 1].strip()
            # engine.py and the checker's own docs are allowed to name the bug
            if f == "engine.py" or SAFE.search(text):
                continue
            bad.append((f, line, text))

    print("=" * 78)
    print("  E-173 — hand-rolled cost scales (engine.cost_scale is the only one)")
    print("=" * 78)
    if not bad:
        print("  clean: every cost scale in JARVIS/research goes through cost_scale()")
    for f, line, text in bad:
        print(f"  {f}:{line}  {text}")
    if bad and strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

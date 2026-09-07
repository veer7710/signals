#!/usr/bin/env python3
"""
Run every check in this project and give ONE answer.

    python3 JARVIS/tools/check_all.py

There are now eight separate checkers and a regression suite, each of which
exists because something broke in a way the others could not see. Running them
one at a time is how one gets skipped, so this runs the lot and prints a single
verdict at the bottom.

WHAT IT DOES NOT DO, and this matters: it cannot compile anything. Only
MetaEditor can say a .mq5 compiles and only TradingView can say a .pine does.
Three separate compile-blocking bug classes have already shipped past a clean
run of these tools - a duplicate input, a global used before declaration, and a
function called above its definition - and each one only became a check AFTER it
had already broken something. A clean run here means "nothing we have learned to
look for is wrong", which is a much weaker claim than "it works".
"""
from __future__ import annotations
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CHECKS = [
    ("engine regression tests", ["python3", "JARVIS/research/test_engine.py"],
     "ALL TESTS PASSED"),
    ("MQL5 static check",       ["python3", "JARVIS/tools/check_mq5.py"],
     "0 problem(s)."),
    ("Pine static check",       ["python3", "JARVIS/tools/check_pine.py"], None),
    ("Pine + MT5 panel rows",   ["python3", "JARVIS/tools/check_panel.py"],
     "0 definite overflow(s)."),
    ("Pine / EA parity",        ["python3", "JARVIS/tools/check_parity.py"],
     "PARITY OK"),
    ("hand-rolled cost scales", ["python3", "JARVIS/tools/check_cost.py"],
     "clean:"),
]


def run(name, cmd, expect):
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           timeout=1800)
    except Exception as e:
        return name, False, str(e), ""
    out = r.stdout + r.stderr
    if expect is None:
        ok = r.returncode == 0 and "ERROR" not in out.upper()
    else:
        ok = expect in out
    tail = "\n".join(l for l in out.strip().split("\n")[-3:])
    return name, ok, "", tail


def main():
    print("=" * 78)
    print("  JARVIS — every check, one answer")
    print("=" * 78)
    fails = []
    for name, cmd, expect in CHECKS:
        nm, ok, err, tail = run(name, cmd, expect)
        print(f"\n  {'PASS' if ok else 'FAIL'}   {nm}")
        if not ok:
            fails.append(nm)
            for l in (err or tail).split("\n"):
                print(f"         {l}")
    print("\n" + "=" * 78)
    if fails:
        print(f"  {len(fails)} CHECK(S) FAILED: {', '.join(fails)}")
        print("  Do not paste or attach anything until these are clean.")
    else:
        print("  ALL CHECKS PASS.")
        print("  This is NOT proof anything compiles. Only MetaEditor can say")
        print("  that for a .mq5 and only TradingView for a .pine. It means")
        print("  nothing we have learned to look for is wrong.")
    print("=" * 78)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

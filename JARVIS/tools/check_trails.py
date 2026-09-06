#!/usr/bin/env python3
"""
Find hand-rolled trailing stops in JARVIS/research.

E-151 cost three signals their status. The bug was a trailing stop computed from
a bar's own extreme and then filled at, even when that level sat on the far side
of the same bar's close - a stop no order could have been resting at. It was
written inline, three lines at a time, in TWELVE separate files, and every one
of them had it. The reason it survived so long is that each copy looked correct
on its own.

`engine.trail_level` / `engine.trail_apply` are now the only correct
implementation. This tool exists so a thirteenth copy cannot be written quietly.

    python3 JARVIS/tools/check_trails.py          # report
    python3 JARVIS/tools/check_trails.py --strict # exit 1 on any unguarded copy
"""
from __future__ import annotations
import os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "research")

# a candidate trail level being computed from `peak`
TRAIL = re.compile(r"^\s*(?:\w+)\s*=\s*(?:entry\s*[+\-].*\(1(?:\.0)?\s*-\s*\w+\)"
                   r"|peak\s*[+\-]\s*\w+\s*\*)", re.M)
# the ratchet that follows it, which is the half that needs the side check
RATCHET = re.compile(r"^\s*\w+\s*=\s*max\(\w+,\s*\w+\)\s*if\s+\w+\s*>\s*0\s*"
                     r"else\s+min\(", re.M)
SAFE = re.compile(r"trail_level|trail_apply")


def compile_sweep():
    """Every research file must actually COMPILE.

    ast.parse() is not enough: it accepts `from __future__ import annotations`
    after another statement, which the compiler rejects. A batch edit that
    prepended a docstring to eleven files passed an ast.parse sweep and broke
    nine of them, and only running the test suite found it.
    """
    bad = []
    for fn in sorted(os.listdir(ROOT)):
        if not fn.endswith(".py"):
            continue
        path = os.path.join(ROOT, fn)
        try:
            compile(open(path).read(), path, "exec")
        except SyntaxError as e:
            bad.append((fn, e.lineno, e.msg))
    if bad:
        print("=" * 74)
        print("  FILES THAT DO NOT COMPILE")
        print("=" * 74)
        for fn, ln, msg in bad:
            print(f"  {fn}:{ln}  {msg}")
        print()
    return len(bad)


def main():
    strict = "--strict" in sys.argv
    n_broken = compile_sweep()
    bad = []
    for fn in sorted(os.listdir(ROOT)):
        if not fn.endswith(".py") or fn == "engine.py":
            continue
        path = os.path.join(ROOT, fn)
        src = open(path).read()
        lines = src.splitlines()
        hits = []
        for m in RATCHET.finditer(src):
            ln = src[:m.start()].count("\n") + 1
            window = "\n".join(lines[max(0, ln - 8):ln + 1])
            if TRAIL.search(window) and not SAFE.search(window):
                hits.append(ln)
        if hits:
            guarded = "E-151" in src[:2000]
            bad.append((fn, hits, guarded))

    if not bad:
        print("  CLEAN — every trailing stop in JARVIS/research goes through "
              "engine.trail_level / trail_apply.")
        return 1 if n_broken else 0

    print("=" * 74)
    print("  HAND-ROLLED TRAILING STOPS (E-151 defect class)")
    print("=" * 74)
    n_unmarked = 0
    for fn, hits, guarded in bad:
        tag = "declared at the top of the file" if guarded else "NOT DECLARED"
        print(f"  {fn:<26} lines {hits}   {tag}")
        if not guarded:
            n_unmarked += 1
    print(f"\n  {len(bad)} file(s), {n_unmarked} with no E-151 warning banner.")
    print("  Fix by importing engine.trail_level / engine.trail_apply. If the")
    print("  file is a dead exploratory script, put an E-151 banner at the top")
    print("  saying its numbers are not to be quoted.")
    return 1 if (n_broken or (strict and n_unmarked)) else 0


if __name__ == "__main__":
    sys.exit(main())

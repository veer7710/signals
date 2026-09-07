#!/usr/bin/env python3
"""
Does a Pine panel write more rows than its table reserves?

`table.cell(tp, col, row)` at a row index past the table's size is a Pine
RUNTIME ERROR: the panel stops drawing and the script reports an error on the
chart. The row count is an expression over the user's inputs, so it can be
correct on the defaults and wrong two checkboxes later - or, as LIQUIDITY_SNIPER
shipped, correct only when EVERY toggle is on, which is the one configuration
nobody runs. On the shipped defaults it wrote 16 rows into a table of 15,
because the formula still charged 3 rows for a block that had been deleted and
charged nothing for the 5-row block that replaced it.

This walks the panel block, tracks which `if <flag>` scopes each row sits in,
and enumerates every combination of those flags to find the worst case. It
counts two idioms: a running counter (`r += 1`, `row += 1`) and hard-coded
indices (`f_row(3, ...)`, `table.cell(tp, 0, 3, ...)`).

    python3 JARVIS/tools/check_panel.py            # every pine file
    python3 JARVIS/tools/check_panel.py --strict   # exit 1 on a possible overflow

IT CANNOT READ THE RESERVED COUNT when that is an expression, so it prints the
worst-case rows written and the table.new line and leaves the comparison to a
human when the count is not a literal. That is a real limit, not a passing test.
"""
from __future__ import annotations
import glob, itertools, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "pine")
NEW = re.compile(r"table\.new\(\s*\w+\s*,\s*\d+\s*,\s*([^,]+),")
CELL = re.compile(r"table\.cell\(\s*\w+\s*,\s*\d+\s*,\s*(\d+)")
FROW = re.compile(r"f_(?:row|sep)\(\s*(\d+)\s*,")
INC = re.compile(r"^(\w+)\s*\+=\s*1$")
IFFLAG = re.compile(r"^if\s+(\w+)\s*$")


def flags_in(lines):
    return sorted({m.group(1) for m in
                   (IFFLAG.match(l.strip()) for l in lines) if m})


def rows_written(lines, flags):
    counters, maxr, stack = {}, 0, []
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("//"):
            continue
        ind = len(ln) - len(ln.lstrip())
        while stack and ind <= stack[-1][0]:
            stack.pop()
        m = IFFLAG.match(s)
        if m:
            stack.append((ind, flags.get(m.group(1), True)))
            continue
        if s.startswith(("if ", "else")):
            stack.append((ind, True))
            continue
        live = all(v for _, v in stack)
        if not live:
            continue
        m = INC.match(s)
        if m:
            counters[m.group(1)] = counters.get(m.group(1), 0) + 1
            maxr = max(maxr, counters[m.group(1)] + 1)
            continue
        for pat in (CELL, FROW):
            for h in pat.finditer(s):
                maxr = max(maxr, int(h.group(1)) + 1)
    return maxr


def check(path):
    src = open(path, encoding="utf-8").read().split("\n")
    hits = [i for i, l in enumerate(src) if "table.new(" in l]
    if not hits:
        return 0
    bad = 0
    for i in hits:
        m = NEW.search(src[i])
        reserved = m.group(1).strip() if m else "?"
        body = src[i:]
        fl = flags_in(body)[:12]
        worst, wflags = 0, {}
        for combo in itertools.product([True, False], repeat=len(fl)):
            f = dict(zip(fl, combo))
            n = rows_written(body, f)
            if n > worst:
                worst, wflags = n, f
        lit = reserved.isdigit()
        print(f"  {os.path.basename(path)}:{i+1}")
        print(f"      reserved : {reserved}")
        print(f"      written  : {worst} (worst case)")
        if lit and worst > int(reserved):
            print(f"      *** OVERFLOW: writes {worst} into {reserved} ***")
            bad += 1
        elif lit:
            print(f"      OK, {int(reserved) - worst} spare")
        else:
            on = [k for k, v in wflags.items() if v]
            print(f"      the count is an expression - check it against {worst}")
            print(f"      worst case has these ON: {', '.join(on) or '(none)'}")
    return bad


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    paths = args or sorted(glob.glob(os.path.join(ROOT, "*.pine")))
    print("=" * 74)
    print("  PINE PANEL ROW COUNT — a cell past the table's size is a runtime error")
    print("=" * 74)
    bad = sum(check(p) for p in paths)
    print()
    print(f"  {bad} definite overflow(s).")
    return 1 if (bad and "--strict" in sys.argv) else 0


if __name__ == "__main__":
    sys.exit(main())

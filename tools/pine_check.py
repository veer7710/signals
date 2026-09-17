#!/usr/bin/env python3
"""
pine_check.py -- structural lint for Pine v5/v6. There is no Pine compiler
here either, so these are the checks that have actually caught something:

  1  tabs (Pine rejects mixed indentation)
  2  bracket balance
  3  a name reassigned with := that was never declared
  4  ta.* inside a user-defined function body -- Pine needs those on every bar
  5  comma-separated declarations (`var int a = 0, b = 0`). Pine allows ONE
     declaration per line; this is invalid and caught OMEGA_ENGINE.pine.
  6  @version header present
"""
import re, sys, os, glob

def check(path):
    s = open(path).read()
    lines = s.split("\n")
    bad = []
    if "\t" in s:
        bad.append("contains TAB")
    for ch, (a, b) in {"()": ("(", ")"), "[]": ("[", "]")}.items():
        if s.count(a) != s.count(b):
            bad.append(f"unbalanced {ch}: {s.count(a)} vs {s.count(b)}")
    if not lines[0].startswith("//@version"):
        bad.append("missing //@version header")
    for i, l in enumerate(lines, 1):
        m = re.match(r"^(var\s+\w+)\s+([^=]+=.+)$", l)
        if m and "," in m.group(2).split("//")[0] and "(" not in m.group(2):
            bad.append(f"L{i}: comma-separated declaration -- Pine allows one per line")
    for n in sorted(set(re.findall(r"^\s*(\w+)\s*:=", s, re.M))):
        if not re.search(rf"\bvar\s+\w+\s+{n}\b|\bvar\s+{n}\b|^\s*{n}\s*=[^=]|\[\s*{n}\s*[,\]]", s, re.M):
            bad.append(f"'{n}' reassigned but never declared")
    infn = False
    for i, l in enumerate(lines, 1):
        if re.match(r"^\w+\(.*\)\s*=>", l):
            infn = True
            continue
        if infn:
            if l and not l.startswith(" ") and not l.startswith("//"):
                infn = False
            elif "ta." in l:
                bad.append(f"L{i}: ta.* inside a function body")
    return bad

if __name__ == "__main__":
    targets = sys.argv[1:] or sorted(glob.glob("pine/*.pine"))
    fail = 0
    for t in targets:
        bad = check(t)
        n = len(open(t).read().split("\n"))
        print(f"{os.path.basename(t):<30}{n:>5} lines  " + ("OK" if not bad else ""))
        for b in bad:
            print(f"   ERROR  {b}")
        if bad:
            fail += 1
    print(f"\n{'FAIL' if fail else 'PASS'}: {fail} file(s) with errors")
    sys.exit(1 if fail else 0)

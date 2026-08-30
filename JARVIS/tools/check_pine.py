"""
Pine static checker — catches what a "structural audit" misses.

Written after a silent failure: a text replacement that was supposed to add two
inputs did not match (one space vs two), so `needRetest` and `retestBars` were
USED in seven places and DECLARED nowhere. The earlier audit checked
declaration ORDER but never declaration EXISTENCE, so it passed a file that
could not compile.

This checks the thing that actually broke.

Run:  python3 JARVIS/tools/check_pine.py <file.pine>
"""
from __future__ import annotations
import re, sys

BUILTIN = set("""
open high low close volume time bar_index na true false math ta array box line label
table str color input indicator strategy plot plotshape plotchar bgcolor alertcondition
alert request barmerge syminfo timeframe chart hour minute second dayofweek year month
dayofmonth barstate nz fixnan int float bool string void var varip if for while switch
and or not to by in export method type enum size shape location text style xloc yloc
display format extend position scale currency session adjustment lookahead strategy
runtime timenow last_bar_index last_bar_time
else if elif for while switch break continue return type enum method import export
""".split())

DECL = re.compile(r'^\s*(?:var\s+(?:\w+\s+)?)?([a-zA-Z_]\w*)\s*(?::=|=)(?!=)')
MULTI = re.compile(r'^\s*\[([^\]]+)\]\s*=')
FUNC = re.compile(r'^([a-zA-Z_]\w*)\s*\(')
PARAM = re.compile(r'\b(?:int|float|bool|string|color|line|label|box|table|array<[^>]+>)\s+([a-zA-Z_]\w*)')
IDENT = re.compile(r'(?<![\w.])([a-zA-Z_]\w*)(?![\w(])')


def check(path):
    src = open(path, encoding="utf-8").read().split("\n")
    declared, problems = set(BUILTIN), []

    # pass 1: collect every name this file defines
    for l in src:
        code = l.split("//")[0]
        m = DECL.match(code)
        if m:
            declared.add(m.group(1))
        m = MULTI.match(code)
        if m:
            for n in m.group(1).split(","):
                declared.add(n.strip())
        m = FUNC.match(code)
        if m and "=>" in code:
            declared.add(m.group(1))
        for n in PARAM.findall(code):
            declared.add(n)
        # loop variables
        m = re.match(r'\s*for\s+([a-zA-Z_]\w*)\s*=', code)
        if m:
            declared.add(m.group(1))

    # pass 2: every identifier used must be known
    for i, l in enumerate(src, 1):
        code = l.split("//")[0]
        if not code.strip() or code.strip().startswith("//"):
            continue
        code = re.sub(r'"[^"]*"', '""', code)          # strip string literals
        # Hex colour literals: #FF5370 leaves "FF5370" behind and looks like a name.
        code = re.sub(r'#[0-9A-Fa-f]{6,8}', '0', code)
        # NAMED ARGUMENTS are not identifiers. `minval = 5` inside a call is a
        # keyword, not a variable being read. Any name immediately followed by a
        # single '=' is either a kwarg or a declaration, and declarations were
        # already collected in pass 1 - so dropping both here is safe and kills
        # the false-positive class that made the first version of this checker
        # unusable.
        code = re.sub(r'\b[a-zA-Z_]\w*\s*=(?!=)', ' ', code)
        for name in IDENT.findall(code):
            if name in declared or name.isdigit():
                continue
            if re.match(r'^(size|shape|location|color|line|label|box|style|xloc|'
                        r'yloc|display|format|extend|position|text|scale|barmerge|'
                        r'strategy|alert|currency|session|adjustment|math|ta|str|'
                        r'array|table|input|request|syminfo|timeframe|chart|'
                        r'barstate|runtime|plot)$', name):
                continue
            problems.append((i, name, l.strip()[:70]))

    print("=" * 74)
    print(f"  PINE STATIC CHECK — {path.split('/')[-1]}")
    print("=" * 74)
    if not problems:
        print(f"  CLEAN — every identifier used is declared. "
              f"({len(src)} lines, {len(declared)-len(BUILTIN)} own names)")
        return 0
    seen = {}
    for ln, name, ctx in problems:
        seen.setdefault(name, []).append(ln)
    print(f"  {len(seen)} UNDECLARED IDENTIFIER(S) — this file will not compile:\n")
    for name, lines in sorted(seen.items()):
        print(f"    {name:<20} used at line(s) {', '.join(map(str, lines[:8]))}")
    return 1


if __name__ == "__main__":
    sys.exit(check(sys.argv[1] if len(sys.argv) > 1
                   else "JARVIS/pine/LiquiditySniper_v1.pine"))

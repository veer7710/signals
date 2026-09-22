#!/usr/bin/env python3
"""
pine_check.py -- structural lint for Pine v5/v6. There is no Pine compiler in
this environment, so these are the checks that have actually caught something
in this project:

  1  tabs (Pine rejects mixed indentation)
  2  bracket balance
  3  a name reassigned with := that was never declared
  4  ta.* inside a user-defined function body -- Pine needs those on every bar
  5  comma-separated declarations (`var int a = 0, b = 0`) -- Pine allows ONE
     per line. Caught OMEGA_ENGINE.pine.
  6  CE10235: a value-returning call as the LAST statement of a block. Pine
     types a block by its last statement, so `array.shift(D)` (which RETURNS
     the removed element) makes the block `series bool` while the implicit
     else is `void`. Caught xau clean and SMC_LIQUIDITY.
  7  @version header present
"""
import re, sys, os, glob

# these all RETURN the element they remove/read -- they cannot end a block
RETURNING = ("array.shift(", "array.pop(", "array.remove(", "array.get(")


def check(path):
    s = open(path).read()
    lines = s.split("\n")
    bad = []
    warns = []

    if "\t" in s:
        bad.append("contains TAB")
    for name, (a, b) in {"()": ("(", ")"), "[]": ("[", "]")}.items():
        if s.count(a) != s.count(b):
            bad.append(f"unbalanced {name}: {s.count(a)} vs {s.count(b)}")
    if not lines[0].startswith("//@version"):
        bad.append("missing //@version header")

    # 5 -- comma-separated declarations
    for i, l in enumerate(lines, 1):
        m = re.match(r"^(var\s+\w+)\s+([^=]+=.+)$", l)
        if m and "," in m.group(2).split("//")[0] and "(" not in m.group(2):
            bad.append(f"L{i}: comma-separated declaration -- Pine allows one per line")

    # 3 -- reassigned but never declared
    for n in sorted(set(re.findall(r"^\s*(\w+)\s*:=", s, re.M))):
        pat = (rf"\bvar\s+\w+\s+{n}\b|\bvar\s+{n}\b|^\s*{n}\s*=[^=]|"
               rf"\[\s*{n}\s*[,\]]|,\s*{n}\s*\]")
        if not re.search(pat, s, re.M):
            bad.append(f"'{n}' reassigned but never declared")

    # 6 -- CE10235
    for i, l in enumerate(lines):
        st = l.strip()
        if not any(st.startswith(r) for r in RETURNING):
            continue
        if re.match(r"^\w[\w\s]*=\s*", st):        # bound to a variable: fine
            continue
        ind = len(l) - len(l.lstrip())
        nxt = None
        for j in range(i + 1, len(lines)):
            if lines[j].strip() and not lines[j].strip().startswith("//"):
                nxt = lines[j]
                break
        if nxt is None or (len(nxt) - len(nxt.lstrip())) < ind:
            call = st.split("(")[0]
            bad.append(f"L{i+1}: {call}() ends a block but RETURNS a value -- "
                       f"the block gets that type while the implicit else is "
                       f"void (CE10235). Bind it: x = {st}")

    # 8 -- an identifier used but never declared anywhere in the file. This is
    #      what let `keepN` through: it is only ever READ, so the := check above
    #      could not see it. Reported as a WARN because a heuristic scanner will
    #      always miss some Pine builtin; it is still how keepN was caught.
    code_lines = []
    for l in lines:
        l = re.sub(r'"(?:\\.|[^"\\])*"', '""', l)
        l = re.sub(r"//.*$", "", l)
        code_lines.append(l)
    code = "\n".join(code_lines)

    declared = set()
    declared |= set(re.findall(r"^\s*(?:var(?:ip)?\s+\w+\s+|var(?:ip)?\s+)?(\w+)\s*=[^=]", code, re.M))
    declared |= set(re.findall(r"^\s*var(?:ip)?\s+\w+\s+(\w+)\b", code, re.M))
    declared |= set(re.findall(r"^\s*(?:var(?:ip)?\s+)?(?:float|int|bool|string|color|line|label|box|table|matrix|map)(?:\[\])?\s+(\w+)\s*=", code, re.M))
    declared |= set(re.findall(r"^(\w+)\(", code, re.M))
    for m in re.finditer(r"^\w+\(([^)]*)\)\s*=>", code, re.M):
        for prm in m.group(1).split(","):
            tok = prm.strip().split()
            if tok:
                declared.add(tok[-1])
    for grp in re.findall(r"\[([^\]]+)\]\s*=", code):
        for t in grp.split(","):
            declared.add(t.strip())
    declared |= set(re.findall(r"for\s+(\w+)\s*=", code))

    NS = set("""ta math array str color line box label table input request barstate
        syminfo timeframe strategy matrix map chart session order shape location
        size format display extend position scale xloc yloc alert currency
        barmerge adjustment text font""".split())
    KW = set("""textcolor border_width border_color bgcolor text_color text_size
        style width color1 color2 force_overlay if else for while to by and or not na true false var varip int float
        bool string color line label box table array export import method type
        switch continue break return series simple const input open high low close
        volume time time_close bar_index hl2 hlc3 ohlc4 hlcc4 last_bar_index
        last_bar_time timenow indicator library plot plotshape plotchar plotarrow
        plotcandle plotbar bgcolor barcolor fill hline alertcondition alert nz
        fixnan iff sign abs hour minute second year month dayofmonth dayofweek
        weekofyear tostring tonumber overlay max_boxes_count max_lines_count
        max_labels_count max_bars_back tooltip group minval maxval step options
        defval title inline confirm timezone""".split())

    seen = set()
    for m in re.finditer(r"\b([A-Za-z_]\w*)\b", code):
        n = m.group(1)
        if n in declared or n in KW or n in NS or n in seen:
            continue
        if n.startswith("_") or n[0].isdigit():
            continue
        if code[max(0, m.start()-1):m.start()] == ".":
            continue
        if code[m.end():m.end()+1] == "(":
            continue
        seen.add(n)
        warns.append(f"'{n}' used but not declared in this file -- check it is a Pine builtin")

    # 4 -- ta.* inside a function body
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
    return bad, warns


if __name__ == "__main__":
    targets = sys.argv[1:] or sorted(glob.glob("pine/*.pine"))
    fail = 0
    for t in targets:
        bad, warns = check(t)
        n = len(open(t).read().split("\n"))
        print(f"{os.path.basename(t):<30}{n:>5} lines  " + ("OK" if not bad else ""))
        for b in bad:
            print(f"   ERROR  {b}")
        for w in warns[:6]:
            print(f"   warn   {w}")
        if bad:
            fail += 1
    print(f"\n{'FAIL' if fail else 'PASS'}: {fail} file(s) with errors")
    sys.exit(1 if fail else 0)

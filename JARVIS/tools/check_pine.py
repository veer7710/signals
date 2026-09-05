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


def strip_comment(line):
    """Drop a // comment, but not one that lives inside a string literal.
    `label.new(... , "a // b")` is a legal Pine string and chopping it there
    silently truncated the line every check below then read."""
    out, instr, prev = [], False, ""
    i = 0
    while i < len(line):
        ch = line[i]
        if instr:
            out.append(ch)
            if ch == '"' and prev != "\\":
                instr = False
        else:
            if ch == '"':
                instr = True
                out.append(ch)
            elif ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                break
            else:
                out.append(ch)
        prev = ch
        i += 1
    return "".join(out)

import re, sys

BUILTIN = set(
    # price shorthands and namespaces missing until 2026-09-01
    'hl2 hlc3 ohlc4 hlcc4 order dayofweek dayofmonth weekofyear '
    'earnings dividends splits chart currency display format scale '
    'position size text xloc yloc extend adjustment barmerge session '.split() +
    """
open high low close volume time bar_index na true false math ta array box line label
table str color input indicator strategy plot plotshape plotchar bgcolor alertcondition
alert request barmerge syminfo timeframe chart hour minute second dayofweek year month
dayofmonth barstate nz fixnan int float bool string void var varip if for while switch
and or not to by in export method type enum size shape location text style xloc yloc
display format extend position scale currency session adjustment lookahead strategy
runtime timenow last_bar_index last_bar_time
else if elif for while switch break continue return type enum method import export
""".split())

# ':=' is ASSIGNMENT to a variable that must already exist. Treating it as a
# declaration is exactly how an undeclared name slips through: the checker sees
# `lastFireBar := bar_index`, records it as declared, and never reports that
# nothing ever declared it. Only '=' (with or without var/varip) declares.
DECL = re.compile(r'^\s*(?:var(?:ip)?\s+(?:\w+(?:<[^>]+>)?\s+)?)?([a-zA-Z_]\w*)\s*=(?!=)')
ASSIGN = re.compile(r'^\s*([a-zA-Z_]\w*)\s*:=')
MULTI = re.compile(r'^\s*\[([^\]]+)\]\s*=')
FUNC = re.compile(r'^([a-zA-Z_]\w*)\s*\(')
PARAM = re.compile(r'\b(?:int|float|bool|string|color|line|label|box|table|array<[^>]+>)\s+([a-zA-Z_]\w*)')
IDENT = re.compile(r'(?<![\w.])([a-zA-Z_]\w*)(?![\w(])')



# ---------------------------------------------------------------- order

# -------------------------------------------------- line continuations

# ------------------------------------------------- functions inside blocks

# --------------------------------------------- user functions called too early
def check_call_order(src):
    """A user function must be DEFINED before it is called - Pine is
    single-pass. The identifier scan cannot catch this: its regex deliberately
    skips any name followed by '(' so that builtins like math.max do not get
    flagged, which means a function call is never checked for ordering at all.
    That hole shipped 'Could not find function or function reference keepSweep'
    to the user, so it gets its own check."""
    defs = {}
    for i, l in enumerate(src, 1):
        m = re.match(r'^([a-zA-Z_]\w*)\s*\([^)]*\)\s*=>', strip_comment(l))
        if m and m.group(1) not in defs:
            defs[m.group(1)] = i
    out = []
    for i, l in enumerate(src, 1):
        code = re.sub(r'"(\\.|[^"\\])*"', '""', strip_comment(l))
        if re.match(r'^[a-zA-Z_]\w*\s*\([^)]*\)\s*=>', code):
            continue                       # the definition itself
        for fn, dline in defs.items():
            if i < dline and re.search(r'(?<![\w.])' + fn + r'\s*\(', code):
                out.append((i, f"FUNCTION '{fn}' CALLED BEFORE IT IS DEFINED "
                               f"(defined line {dline}; Pine is single-pass)",
                            l.strip()[:60]))
                break
    return out


def check_nested_func(src):
    """A Pine function must be declared at GLOBAL scope. Declaring one inside
    an if/for body does not compile, and it is an easy mistake because the
    function often only makes sense in that context."""
    out = []
    for i, l in enumerate(src, 1):
        code = strip_comment(l)
        if not code.strip():
            continue
        m = re.match(r'^(\s+)([a-zA-Z_]\w*)\s*\(([^)]*)\)\s*=>', code)
        if m and len(m.group(1)) > 0:
            out.append((i, f"FUNCTION '{m.group(2)}' DECLARED INSIDE A BLOCK "
                           f"(Pine requires global scope)", l.strip()[:60]))
    return out


def check_continuation(src):
    """A continuation line indented by a multiple of 4 reads as a new block, so
    a multi-line boolean silently becomes a statement that does nothing.

    This only applies OUTSIDE brackets. Inside an unclosed ( or [ Pine ignores
    indentation entirely, so a ternary wrapped across lines inside a function
    call is fine - flagging those was pure noise."""
    out = []
    depth = 0
    for i, l in enumerate(src, 1):
        code = re.sub(r'"(\\.|[^"\\])*"', '""', strip_comment(l))
        if depth == 0 and code.strip():
            # ANY operator can start a wrapped line, not just and/or. The
            # version of this check that only looked for and/or/?/: let a
            # `* ccyPerPt` continuation through, and both indicators failed to
            # compile for five commits because of it.
            m = re.match(r'^(\s+)([-+*/%]|and\b|or\b|\?|:|==|!=|<=|>=|<|>|\band\b)\s',
                         code)
            if m and len(m.group(1)) % 4 == 0:
                out.append((i, "CONTINUATION indented by a multiple of 4 "
                               "(reads as a new block, not a continuation)",
                            l.strip()[:60]))
        depth += code.count("(") + code.count("[")
        depth -= code.count(")") + code.count("]")
        depth = max(depth, 0)
    return out


# ----------------------------------------------- variable history offset
def check_var_offset(src):
    """`close[j]` with a LOOP VARIABLE offset. Pine cannot always infer how far
    back to buffer, and throws 'cannot determine the referencing length' at
    runtime. Declaring max_bars_back on the indicator() call fixes it."""
    loopvars = set(re.findall(r'^\s*for\s+([a-zA-Z_]\w*)\s*=', "\n".join(src), re.M))
    if not loopvars:
        return []
    # `max_bars_back` is an argument to indicator()/strategy(), and that call can
    # sit anywhere - these files carry long change-log headers and 3.8's pushed
    # it past line 120, which made this check fire on a file that declares it.
    # So look at the CODE, not at a fixed window: strip comments and search the
    # whole script. A commented-out mention no longer counts either.
    code_only = "\n".join(strip_comment(l) for l in src)
    has_mbb = "max_bars_back" in code_only
    if has_mbb:
        return []
    out = []
    for i, l in enumerate(src, 1):
        code = strip_comment(l)
        for v in loopvars:
            if re.search(r'\b(?:open|high|low|close|volume|time)\s*\[\s*' + v + r'\s*\]', code):
                out.append((i, f"VARIABLE HISTORY OFFSET ([{v}]) with no "
                               f"max_bars_back declared on indicator()",
                            l.strip()[:60]))
                break
    return out


def check_order(src, declared):
    """Pine is single-pass: a name must appear textually BEFORE it is used.
    The existence check alone passes a file that reads a variable declared
    fifty lines further down, which will not compile."""
    first = {}
    for i, l in enumerate(src, 1):
        code = strip_comment(l)
        m = DECL.match(code)
        # A named argument on a continuation line ("color = isHigh ? ..") looks
        # exactly like a declaration. A builtin name is never being declared.
        if m and m.group(1) not in first and m.group(1) not in BUILTIN:
            first[m.group(1)] = i
        m = MULTI.match(code)
        if m:
            for n in m.group(1).split(","):
                first.setdefault(n.strip(), i)
        m = FUNC.match(code)
        if m and "=>" in code:
            first.setdefault(m.group(1), i)
        for n in PARAM.findall(code):
            first.setdefault(n, i)
        m = re.match(r'\s*for\s+([a-zA-Z_]\w*)\s*=', code)
        if m:
            first.setdefault(m.group(1), i)

    out = []
    for i, l in enumerate(src, 1):
        code = strip_comment(l)
        if not code.strip():
            continue
        code = re.sub(r'"[^"]*"', '""', code)
        code = re.sub(r'#[0-9A-Fa-f]{6,8}', '0', code)
        code = re.sub(r'\b[a-zA-Z_]\w*\s*=(?!=)', ' ', code)
        for name in IDENT.findall(code):
            d = first.get(name)
            if d is not None and d > i:
                out.append((i, f"USED BEFORE DECLARED ({name}, declared line {d})",
                            l.strip()[:70]))
    return out


# ---------------------------------------------------------------- arity
def check_arity(src):
    """A user function called with the wrong number of arguments. This is what
    a rename or a signature change silently leaves behind."""
    sig = {}
    for i, l in enumerate(src, 1):
        code = strip_comment(l)
        m = re.match(r'^([a-zA-Z_]\w*)\s*\(([^)]*)\)\s*=>', code)
        if m:
            params = [p for p in m.group(2).split(",") if p.strip()]
            sig[m.group(1)] = (len(params), i)

    out = []
    for i, l in enumerate(src, 1):
        code = strip_comment(l)
        if re.match(r'^[a-zA-Z_]\w*\s*\([^)]*\)\s*=>', code):
            continue                      # the definition itself
        for fn, (want, dline) in sig.items():
            for m in re.finditer(r'(?<![\w.])' + fn + r'\s*\(', code):
                rest, depth, args, cur = code[m.end():], 1, [], ""
                instr = False
                prev = ""
                for ch in rest:
                    # A comma inside a string literal is TEXT, not an argument
                    # separator. Missing this reported a 4-arg call as 5 because
                    # the label read "87.8% on 401, PF 1.85".
                    if instr:
                        cur += ch
                        if ch == '"' and prev != "\\":
                            instr = False
                        prev = ch
                        continue
                    if ch == '"':
                        instr = True; cur += ch; prev = ch; continue
                    prev = ch
                    if ch in "([": depth += 1
                    elif ch in ")]":
                        depth -= 1
                        if depth == 0: break
                    if ch == "," and depth == 1:
                        args.append(cur); cur = ""; continue
                    cur += ch
                else:
                    continue              # call spans lines; skip rather than guess
                if cur.strip() or args:
                    args.append(cur)
                got = len([a for a in args if a.strip()])
                if got != want:
                    out.append((i, f"ARITY: {fn}() wants {want} arg(s), called "
                                   f"with {got} (defined line {dline})",
                                l.strip()[:70]))
    return out


# --------------------------------------------------------------- tables
def check_tables(src):
    """table.cell() writing outside the rows/columns the table was created
    with. Pine throws at runtime, so the script loads and then dies."""
    dims, out = {}, []
    for i, l in enumerate(src, 1):
        code = strip_comment(l)
        m = re.search(r'(?:var\s+)?table\s+([a-zA-Z_]\w*)\s*=\s*table\.new\s*\(([^)]*)', code)
        if m:
            parts = [p.strip() for p in m.group(2).split(",")]
            nums = [p for p in parts if re.fullmatch(r'\d+', p)]
            if len(nums) >= 2:
                dims[m.group(1)] = (int(nums[0]), int(nums[1]), i)

    for i, l in enumerate(src, 1):
        code = strip_comment(l)
        for m in re.finditer(r'table\.cell\s*\(\s*([a-zA-Z_]\w*)\s*,\s*([^,]+),\s*([^,]+),', code):
            t = m.group(1)
            if t not in dims:
                continue
            cols, rows, dl = dims[t]
            for val, lim, what in ((m.group(2), cols, "column"),
                                   (m.group(3), rows, "row")):
                v = val.strip()
                if re.fullmatch(r'\d+', v) and int(v) >= lim:
                    out.append((i, f"TABLE BOUNDS: {t} has {lim} {what}s "
                                   f"(0..{lim-1}), writing {what} {v}",
                                l.strip()[:70]))
    return out


# ------------------------------------------------- drawings in ternaries
def check_draw_in_ternary(src):
    """box.new / line.new / label.new inside a ternary. Pine evaluates both
    branches, so the branch you thought was skipped still allocates an object
    every bar - a silent leak that eventually hits max_boxes_count."""
    out = []
    for i, l in enumerate(src, 1):
        code = strip_comment(l)
        if "?" not in code:
            continue
        head = code.split("?")[0]
        if re.search(r'(box|line|label|table)\.new\s*\(', code) and \
           not re.search(r'(box|line|label|table)\.new\s*\(', head):
            out.append((i, "DRAWING INSIDE A TERNARY (both branches allocate)",
                        l.strip()[:70]))
    return out


# ---------------------------------------------------------------------------
# NAMESPACE MEMBERS  (added 2026-09-01 after F-009)
#
# The checker validated that `ta` was a known namespace and then accepted
# ANYTHING after the dot. So `ta.adx(14, 14)` passed here and failed in
# TradingView with "Could not find function or function reference 'ta.adx'".
# Pine has no ta.adx - ADX comes out of ta.dmi() as the third element of a
# tuple. That is the fourth non-compiling Pine file shipped to Veer, and the
# third time the cause was a rule this checker did not know rather than a
# mistake it failed to spot.
#
# These lists are not exhaustive and do not need to be. An unknown member is
# REPORTED, not ignored: a false alarm costs one line here, a missed one costs
# a shipped file that will not compile.
TA_MEMBERS = set("""
alma atr barssince bb bbw cci change cmo cog correlation cross crossover
crossunder cum dev dmi ema falling highest highestbars hma kc kcw linreg
lowest lowestbars macd max median mfi min mode mom percentile_linear_interpolation
percentile_nearest_rank percentrank pivot_point_levels pivothigh pivotlow
range rci rising rma roc rsi sar sma stdev stoch supertrend swma tr tsi
valuewhen variance vwap vwma wma wpr sum
""".split())

MATH_MEMBERS = set("""
abs acos asin atan avg ceil cos exp floor log log10 max min pow random round
round_to_mintick sign sin sqrt sum tan todegrees toradians e phi pi rphi
""".split())

STR_MEMBERS = set("""
contains endswith format format_time length lower match pos repeat replace
replace_all split startswith substring tonumber tostring trim upper
""".split())

NAMESPACE_MEMBERS = {"ta": TA_MEMBERS, "math": MATH_MEMBERS, "str": STR_MEMBERS}


def check_namespace_members(src):
    """`ta.adx(...)` compiles here and fails in TradingView. Catch it."""
    out = []
    for i, l in enumerate(src, 1):
        code = strip_comment(l)
        for m in re.finditer(r'\b(ta|math|str)\.([a-zA-Z_]\w*)', code):
            ns, name = m.group(1), m.group(2)
            if name not in NAMESPACE_MEMBERS[ns]:
                out.append((i, f"{ns}.{name} IS NOT A PINE FUNCTION",
                            f"no such member of the '{ns}' namespace - "
                            f"this will not compile"))
    return out



# Pine allows these ONLY at global scope. Indenting one into an if-block or a
# function is a compile error, and it is an easy mistake to make while moving
# drawing code around - which is exactly when it happens.
GLOBAL_ONLY = ("plot", "plotshape", "plotchar", "plotarrow", "plotcandle",
               "plotbar", "fill", "bgcolor", "barcolor", "hline",
               "alertcondition", "indicator", "strategy", "library")


def check_global_only(src):
    out = []
    lines = src if isinstance(src, list) else src.split("\n")
    for i, l in enumerate(lines, 1):
        if not l[:1].isspace():
            continue
        stripped = l.strip()
        if stripped.startswith("//"):
            continue
        for fname in GLOBAL_ONLY:
            if stripped.startswith(fname + "(") or stripped.startswith(fname + " ("):
                out.append((i, "%s() IS GLOBAL-SCOPE ONLY in Pine - it cannot sit "
                               "inside an if, a for or a function" % fname,
                            stripped[:70]))
                break
    return out


def check(path):
    src = open(path, encoding="utf-8").read().split("\n")
    declared, problems = set(BUILTIN), []
    in_type = [False]   # mutable so the loop body can flip it

    # pass 1: collect every name this file defines
    for l in src:
        code = strip_comment(l)
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
            # ...and its PARAMETERS. PARAM below only matches TYPED parameters
            # (`int len`), but Pine's common form is untyped - `f(src, len) =>`
            # - and every one of those names was invisible to this checker,
            # so any file using one drew a false "undeclared identifier".
            # Added 2026-09-01 after four such alarms on a correct file.
            # Take the parameter list by BALANCING from the opening paren,
            # not by finding the last ')' on the line: in a one-line function
            # like `f_up(l) => ... (l - close) ...` the last ')' is in the
            # BODY, and slicing to it produced a nonsense parameter list and a
            # false alarm on a file that compiles. (Fixed 2026-09-01.)
            inner = ""
            op = code.find("(")
            if op >= 0:
                d = 0
                for _k in range(op, len(code)):
                    if code[_k] == "(":
                        d += 1
                    elif code[_k] == ")":
                        d -= 1
                        if d == 0:
                            inner = code[op + 1:_k]
                            break
            for prm in inner.split(","):
                prm = prm.strip()
                if "=" in prm:
                    prm = prm.split("=")[0].strip()
                prm = prm.split()[-1] if prm.split() else ""
                if re.fullmatch(r'[A-Za-z_]\w*', prm or ""):
                    declared.add(prm)
        for n in PARAM.findall(code):
            declared.add(n)
        # loop variables
        m = re.match(r'\s*for\s+([a-zA-Z_]\w*)\s*=', code)
        if m:
            declared.add(m.group(1))
        # ---- USER-DEFINED TYPES (Pine v5+). Added 2026-09-01 after this
        # checker reported three false alarms on a file that was correct.
        # A false alarm is not harmless: a checker that cries wolf is a
        # checker that gets ignored, and being ignored is how F-006 shipped
        # five times. Three shapes have to be understood:
        #   type Lvl            -> declares the type name
        #       float px        -> declares a field name
        #   Lvl L = array.get() -> an explicitly typed local declaration
        m = re.match(r'\s*type\s+([A-Za-z_]\w*)\s*$', code)
        if m:
            declared.add(m.group(1))
            in_type[0] = True
            continue
        if in_type[0]:
            # a type body is indented; the first unindented line ends it
            if code.strip() and not code[:1].isspace():
                in_type[0] = False
            else:
                m = re.match(r'\s+(?:\w+(?:<[^>]*>)?)\s+([A-Za-z_]\w*)', code)
                if m:
                    declared.add(m.group(1))
                continue
        # an explicitly typed declaration, including a user type
        m = re.match(r'\s*(?:var\s+|varip\s+)?'
                     r'(?:int|float|bool|string|color|line|label|box|table|'
                     r'linefill|array|matrix|map|[A-Z]\w*)'
                     r'(?:<[^>]*>)?(?:\s*\[\s*\])?\s+([a-zA-Z_]\w*)\s*(?:=|:=)',
                     code)
        if m:
            declared.add(m.group(1))

    # pass 2: every identifier used must be known
    for i, l in enumerate(src, 1):
        code = strip_comment(l)
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

    problems += check_call_order(src)
    problems += check_nested_func(src)
    problems += check_continuation(src)
    problems += check_var_offset(src)
    problems += check_order(src, declared)
    problems += check_namespace_members(src)
    problems += check_arity(src)
    problems += check_tables(src)
    problems += check_draw_in_ternary(src)
    problems += check_global_only(src)

    print("=" * 74)
    print(f"  PINE STATIC CHECK — {path.split('/')[-1]}")
    print("=" * 74)
    if not problems:
        print(f"  CLEAN — every identifier used is declared. "
              f"({len(src)} lines, {len(declared)-len(BUILTIN)} own names)")
        return 0
    bare = [(ln, n, c) for ln, n, c in problems if " " not in n]
    rich = [(ln, n, c) for ln, n, c in problems if " " in n]
    if bare:
        seen = {}
        for ln, name, ctx in bare:
            seen.setdefault(name, []).append(ln)
        print(f"  {len(seen)} UNDECLARED IDENTIFIER(S) — will not compile:\n")
        for name, lines in sorted(seen.items()):
            print(f"    {name:<20} used at line(s) {', '.join(map(str, lines[:8]))}")
    if rich:
        print(f"\n  {len(rich)} STRUCTURAL PROBLEM(S):\n")
        for ln, msg, ctx in rich[:40]:
            print(f"    line {ln:<5} {msg}")
            print(f"              {ctx}")
    return 1


if __name__ == "__main__":
    sys.exit(check(sys.argv[1] if len(sys.argv) > 1
                   else "JARVIS/pine/LiquiditySniper_v1.pine"))

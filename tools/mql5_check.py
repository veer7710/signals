#!/usr/bin/env python3
"""
mql5_check.py -- the compiler substitute.

MQL5 cannot be compiled in this environment, and per the brief six
declaration-order / signature traps were hit in a single prior session. This
runs the checks that caught them. Run it on EVERY change.

Checks
  1  brace / paren / bracket balance, per function and whole file
  2  declare-before-use for every user function (MQL5 is strict about this)
  3  duplicate function definitions
  4  call-site arity vs definition arity
  5  inputs referenced above their own declaration line
  6  orphaned inputs (declared, never read)
  7  write-only globals (assigned, never read)
  8  uncalled functions (excluding OnX handlers and ones marked SUPERSEDED)
  9  string-format arg count vs Print/PrintFormat/StringFormat placeholders
 10  #property / #include sanity
Exit 1 on any ERROR. WARNs are informational.
"""
import re, sys, os

MQL_BUILTINS = set("""
OnInit OnTick OnDeinit OnTimer OnTrade OnTradeTransaction OnChartEvent OnTester
Print PrintFormat StringFormat ArrayResize ArraySize ArraySetAsSeries ArraySort
MathMax MathMin MathAbs MathFloor MathCeil MathRound MathSqrt MathPow MathLog
NormalizeDouble DoubleToString StringToDouble StringToInteger IntegerToString
TimeCurrent TimeGMT TimeToStruct StructToTime TimeToString
iTime iOpen iHigh iLow iClose iATR iMA iRSI iADX iCustom Bars CopyBuffer CopyRates
SymbolInfoDouble SymbolInfoInteger SymbolInfoString
AccountInfoDouble AccountInfoInteger AccountInfoString
PositionSelect PositionSelectByTicket PositionsTotal PositionGetTicket
PositionGetDouble PositionGetInteger PositionGetString
OrdersTotal OrderGetTicket OrderCalcMargin OrderSend
HistorySelect HistoryDealsTotal HistoryDealGetTicket HistoryDealGetDouble
HistoryDealGetInteger HistoryDealGetString
ObjectCreate ObjectFind ObjectDelete ObjectsDeleteAll ObjectSetInteger
ObjectSetString ObjectSetDouble ChartRedraw
FileOpen FileClose FileWrite FileReadString FileIsEnding FileSeek FileFlush
EventSetTimer EventKillTimer IndicatorRelease Comment Alert SendNotification
StringLen StringSubstr StringFind StringReplace StringSplit StringTrimLeft
StringTrimRight StringConcatenate StringToUpper StringToLower
GetLastError ResetLastError TerminalInfoInteger MQLInfoInteger
EnumToString ZeroMemory ArrayInitialize ArrayCopy ArrayFill ArrayMaximum
ArrayMinimum ArrayReverse ArrayBsearch MathMod MathRand MathSrand
UninitializeReason ChartID ChartGetInteger ChartSetInteger
if for while switch return sizeof new delete
""".split())

def strip_noise(src):
    """Remove comments and string literals so they cannot create false hits,
    but keep line count identical so reported line numbers stay true."""
    out = []
    for line in src.split("\n"):
        s = re.sub(r'"(?:\\.|[^"\\])*"', '""', line)
        s = re.sub(r"'(?:\\.|[^'\\])*'", "''", s)
        s = re.sub(r"//.*$", "", s)
        out.append(s)
    txt = "\n".join(out)
    # block comments, preserving newlines
    txt = re.sub(r"/\*.*?\*/", lambda m: "\n"*m.group(0).count("\n"), txt, flags=re.S)
    return txt

# ^[ \t]* not ^\s* : \s swallows preceding blank lines and shifts every
# reported line number. [^;{\n]* not [^;]* : otherwise a prototype pattern
# runs past the ")" into the function BODY and matches its first ";", so a
# definition registers as its own forward declaration.
FUNC_DEF = re.compile(
    r"^[ \t]*(?:static\s+)?(void|int|double|bool|string|long|ulong|datetime|color|char|short|uchar|uint|float)\s+"
    r"(\w+)\s*\(([^;{\n]*)\)[ \t]*(?:\{|$)", re.M)
FUNC_FWD = re.compile(
    r"^[ \t]*(?:void|int|double|bool|string|long|ulong|datetime|color|char|short|uchar|uint|float)\s+"
    r"(\w+)\s*\([^;{\n]*\)[ \t]*;[ \t]*$", re.M)
INPUT_DEF = re.compile(r"^\s*(?:input|sinput|extern)\s+\w+(?:\s+\w+)?\s+(\w+)\s*=", re.M)
GLOBAL_DEF = re.compile(r"^(?:static\s+)?(?:void|int|double|bool|string|long|ulong|datetime|color|uchar|uint)\s+(\w+)\s*(?:=[^;]*)?;", re.M)

def check(path):
    raw = open(path).read()
    src = strip_noise(raw)
    lines = src.split("\n")
    errors, warns = [], []

    # ---- 1 balance -------------------------------------------------
    for name,(o,c) in {"brace":("{","}"), "paren":("(",")"), "bracket":("[","]")}.items():
        if src.count(o) != src.count(c):
            errors.append(f"{name} imbalance: {src.count(o)} '{o}' vs {src.count(c)} '{c}'")

    # ---- collect definitions ---------------------------------------
    defs, arity, deflines = {}, {}, {}
    for m in FUNC_DEF.finditer(src):
        nm = m.group(2)
        if nm in ("if","for","while","switch","return"): continue
        ln = src[:m.start()].count("\n")+1
        params = m.group(3).strip()
        plist = [p for p in params.split(",") if p.strip()] if params else []
        n = len(plist)
        # a parameter with "= value" may be omitted at the call site
        nmin = len([p for p in plist if "=" not in p])
        if nm in defs:
            errors.append(f"duplicate definition of {nm}() at line {ln} (first at {deflines[nm]})")
        defs[nm]=ln; deflines[nm]=ln; arity[nm]=(nmin, n)
    fwd = {m.group(1): src[:m.start()].count("\n")+1 for m in FUNC_FWD.finditer(src)}

    # ---- 2 declare-before-use --------------------------------------
    fwd_lines = {src[:m.start()].count("\n")+1 for m in FUNC_FWD.finditer(src)}
    called = {}
    for m in re.finditer(r"\b(\w+)\s*\(", src):
        nm = m.group(1)
        if nm in MQL_BUILTINS or nm not in defs: continue
        ln = src[:m.start()].count("\n")+1
        if ln == defs[nm]: continue
        if ln in fwd_lines: continue          # a prototype, not a call
        called.setdefault(nm, []).append(ln)
    for nm, sites in called.items():
        first = min(sites)
        # MQL5 resolves functions across the whole file -- unlike C it does NOT
        # require a prototype. Verified against XAUUSD_QUAD v19.18, which runs
        # live with 23 call-before-define cases. A prototype is harmless
        # insurance, not a requirement, so this is a WARNING.
        if first < defs[nm] and nm not in fwd:
            warns.append(f"{nm}() called at line {first}, defined at {defs[nm]} "
                         f"(legal in MQL5; a prototype would make the order explicit)")
        elif nm in fwd and fwd[nm] > first:
            warns.append(f"{nm}() prototype at {fwd[nm]} sits after first use at {first}")

    # ---- 4 arity ----------------------------------------------------
    for nm, sites in called.items():
        for ln in sites:
            if ln in fwd_lines: continue
            line = lines[ln-1]
            mm = re.search(rf"\b{nm}\s*\((.*)", line)
            if not mm: continue
            seg, depth = "", 0
            for ch in mm.group(1):
                if ch == "(": depth += 1
                elif ch == ")":
                    if depth == 0: break
                    depth -= 1
                seg += ch
            if seg.count("(") != seg.count(")"): continue     # multi-line call
            # a line whose argument list ends in a comma is CONTINUED on the
            # next line -- counting it here produced five false positives on
            # XAUUSD_QUAD (Open, AtLegExtreme, QSP_Row)
            if seg.rstrip().endswith(","): continue
            if not line.rstrip().endswith((")", ");", ",")) and "(" in line: continue
            got = 0 if not seg.strip() else len([a for a in re.split(r",(?![^(]*\))", seg) if a.strip()])
            lo, hi = arity[nm]
            if got < lo or got > hi:
                rng = str(lo) if lo == hi else f"{lo}-{hi}"
                errors.append(f"line {ln}: {nm}() called with {got} args, defined with {rng}")

    # ---- 5/6 inputs --------------------------------------------------
    inputs = {m.group(1): src[:m.start()].count("\n")+1 for m in INPUT_DEF.finditer(src)}
    for nm, dln in inputs.items():
        uses = [src[:m.start()].count("\n")+1
                for m in re.finditer(rf"\b{nm}\b", src)
                if src[:m.start()].count("\n")+1 != dln]
        if not uses:
            warns.append(f"orphaned input {nm} (line {dln}) -- declared, never read")
        elif min(uses) < dln:
            errors.append(f"input {nm} read at line {min(uses)} but declared at {dln}")

    # ---- 7 write-only globals ---------------------------------------
    body_start = min([defs[k] for k in defs] or [len(lines)])
    head = "\n".join(lines[:body_start])
    for m in GLOBAL_DEF.finditer(head):
        nm = m.group(1)
        if nm in defs or nm in inputs: continue
        reads = 0
        for mm in re.finditer(rf"\b{nm}\b", src):
            ln = src[:mm.start()].count("\n")+1
            if ln <= body_start: continue
            after = src[mm.end():mm.end()+4]
            # judge THIS occurrence, not the whole line: a line can both
            # read and write the same variable
            if re.match(r"\s*(?:\+=|-=|\*=|/=|\+\+|--|=(?!=))", after): continue
            reads += 1
        if reads == 0:
            warns.append(f"write-only global {nm} -- assigned, never read")

    # ---- 8 uncalled --------------------------------------------------
    for nm, ln in defs.items():
        if nm.startswith("On"): continue
        ctx = "\n".join(lines[max(0,ln-4):ln])
        if "SUPERSEDED" in raw.split("\n")[max(0,ln-4):ln][0:1] or "SUPERSEDED" in ctx:
            continue
        if nm not in called:
            warns.append(f"uncalled function {nm}() at line {ln}")

    # ---- 9 format placeholders --------------------------------------
    for i, line in enumerate(raw.split("\n"), 1):
        m = re.search(r"\b(PrintFormat|StringFormat)\s*\(\s*(\"(?:\\.|[^\"\\])*\")", line)
        if not m: continue
        fmt = m.group(2)
        # only trust single-line calls
        tail = line[m.end():]
        # a complete single-line call ends with ");" and balances; anything
        # else is a continuation and cannot be counted from this line alone
        if not tail.rstrip().endswith(");"): continue
        if tail.count("(") != tail.count(")"): continue
        want = len(re.findall(r"%[-+ #0-9.]*[a-zA-Z]", fmt)) - 2*len(re.findall(r"%%", fmt))
        args = [a for a in re.split(r",(?![^()]*\))", tail) if a.strip().strip(");")]
        if want and abs(len(args)-want) > 0:
            warns.append(f"line {i}: {m.group(1)} has {want} placeholders, ~{len(args)} args")

    # ---- 10 properties ------------------------------------------------
    if "#property" not in raw: warns.append("no #property directives")
    for inc in re.findall(r"#include\s+<([^>]+)>", raw):
        if "\\" not in inc and inc.endswith(".mqh") and "/" not in inc:
            warns.append(f"#include <{inc}> -- MQL5 standard library uses backslashes")

    return errors, warns

if __name__ == "__main__":
    targets = sys.argv[1:] or [f for f in os.listdir("mq5") if f.endswith(".mq5")]
    targets = [t if os.path.sep in t else os.path.join("mq5", t) for t in targets]
    bad = 0
    for t in targets:
        e, w = check(t)
        print(f"\n=== {t} ===")
        if not e and not w: print("  clean")
        for x in e: print(f"  ERROR  {x}"); 
        for x in w[:25]: print(f"  warn   {x}")
        if len(w) > 25: print(f"  warn   ... and {len(w)-25} more")
        if e: bad += 1
    print(f"\n{'FAIL' if bad else 'PASS'}: {bad} file(s) with errors")
    sys.exit(1 if bad else 0)

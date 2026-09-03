#!/usr/bin/env python3
"""
check_mq5.py - refuse to ship an MQL5 file that will not compile.

WHY THIS EXISTS
There is a check_pine.py because a Pine file was shipped to Veer five times
in a state that would not compile (F-006), then twice more after that
(F-007 undeclared identifier, F-008 function used before its definition).
The .mq5 file has had no equivalent check at all. This is that check.

WHAT IT CANNOT DO
It is not a compiler. It cannot type-check, it does not know MQL5's full
standard library, and a clean run here is not proof the file builds - only
MetaEditor can say that. What it CAN do is catch the specific class of
mistake that has actually shipped: an identifier that was never declared, a
function that was never defined, an argument count that does not match, a
brace that does not close, and an assignment to a read-only input.

Run:  python3 JARVIS/tools/check_mq5.py JARVIS/ea/build/SuperTrendSniper.mq5
"""
from __future__ import annotations
import re, sys, os

# ---------------------------------------------------------------- lexing
def strip_code(src: str) -> str:
    """Blank out comments and string/char literals, preserving line structure
    so every reported line number is the real one."""
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == '/' and i + 1 < n and src[i+1] == '/':
            while i < n and src[i] != '\n':
                out.append(' '); i += 1
        elif c == '/' and i + 1 < n and src[i+1] == '*':
            out.append('  '); i += 2
            while i + 1 < n and not (src[i] == '*' and src[i+1] == '/'):
                out.append('\n' if src[i] == '\n' else ' '); i += 1
            out.append('  '); i += 2
        elif c in '"\'':
            q = c; out.append(' '); i += 1
            while i < n and src[i] != q:
                if src[i] == '\\':
                    out.append(' '); i += 1
                if i < n:
                    out.append('\n' if src[i] == '\n' else ' '); i += 1
            out.append(' '); i += 1
        else:
            out.append(c); i += 1
    return ''.join(out)


# MQL5 built-ins this file is allowed to use without defining them. Not the
# whole language - just enough that a genuine typo stands out. Anything not
# here and not defined in the file is REPORTED, not ignored: a false alarm
# costs one line in this list, a missed one costs a shipped broken file.
BUILTIN_FUNCS = set("""
Print PrintFormat Comment Alert StringFormat StringConcatenate StringLen
StringSubstr StringFind StringReplace StringTrimLeft StringTrimRight
StringToUpper StringToLower StringSplit StringToDouble StringToInteger
DoubleToString IntegerToString TimeToString StringToTime CharToString
NormalizeDouble MathAbs MathMax MathMin MathFloor MathCeil MathRound
MathSqrt MathPow MathLog MathExp MathSin MathCos MathTan MathMod MathRand
MathIsValidNumber ArraySize ArrayResize ArraySetAsSeries ArrayInitialize
ArrayCopy ArrayFree ArraySort ArrayMaximum ArrayMinimum ArrayRange
TimeCurrent TimeLocal TimeGMT TimeToStruct StructToTime GetTickCount
Sleep IsStopped
SymbolInfoDouble SymbolInfoInteger SymbolInfoString SymbolInfoTick
AccountInfoDouble AccountInfoInteger AccountInfoString
PositionsTotal PositionGetTicket PositionGetDouble PositionGetInteger
PositionGetString PositionSelect PositionSelectByTicket
OrdersTotal OrderGetTicket OrderGetDouble OrderGetInteger OrderGetString
OrderSelect HistorySelect HistoryDealsTotal HistoryDealGetTicket
HistoryDealGetDouble HistoryDealGetInteger HistoryDealGetString
HistoryDealSelect HistoryOrderSelect
iTime iOpen iHigh iLow iClose iVolume iBars iBarShift iHighest iLowest
Bars CopyRates CopyBuffer CopyTime CopyClose CopyHigh CopyLow CopyOpen
iATR iADX iMA iRSI iMACD iStochastic iBands iCustom IndicatorRelease
ObjectCreate ObjectDelete ObjectFind ObjectSetInteger ObjectSetDouble
ObjectSetString ObjectGetInteger ObjectGetDouble ObjectGetString
ObjectsDeleteAll ChartRedraw ChartID ChartGetInteger ChartSetInteger
GlobalVariableSet GlobalVariableGet GlobalVariableCheck GlobalVariableDel
GlobalVariablesTotal GlobalVariableName
FileOpen FileClose FileWrite FileWriteString FileRead FileReadString
FileSeek FileIsExist FileDelete FileSize FileFlush
TerminalInfoInteger TerminalInfoString MQLInfoInteger MQLInfoString
EnumToString ColorToString ResetLastError GetLastError
OnInit OnDeinit OnTick OnTimer OnTrade OnTradeTransaction OnChartEvent
OnStart OnCalculate OnTester OnTimer EventSetTimer EventKillTimer
EventSetMillisecondTimer EventChartCustom
ZeroMemory ArrayFill CheckPointer ArrayRemove ArrayInsert ArrayReverse
PeriodSeconds Period Symbol Digits Point SeriesInfoInteger RefreshRates
StringGetCharacter StringSetCharacter StringInit StringBufferLen
MathLog10 MathArctan MathArcsin MathArccos MathSrand MathExpm1
""".split())

# CTrade methods, reached through the `trade` object - checked as members, not
# as free functions, so they are listed separately.
CTRADE_METHODS = set("""
Buy Sell BuyLimit SellLimit BuyStop SellStop PositionClose PositionModify
PositionClosePartial OrderDelete OrderModify SetExpertMagicNumber
SetTypeFilling SetTypeFillingBySymbol SetDeviationInPoints SetAsyncMode
ResultRetcode ResultRetcodeDescription ResultDeal ResultOrder ResultPrice ResultVolume ResultComment
""".split())

TYPE_WORDS = set("""
void bool char uchar short ushort int uint long ulong float double string
color datetime enum struct class union const static extern input sinput
virtual override final template typename public private protected
""".split())

KEYWORDS = set("""
if else for while do switch case default break continue return goto sizeof
new delete this true false NULL EMPTY_VALUE WHOLE_ARRAY INVALID_HANDLE
and or not
""".split())


def check(path: str):
    src = io_read(path)
    code = strip_code(src)
    lines = code.split('\n')
    raw = src.split('\n')
    problems = []

    def bad(ln, msg):
        problems.append((ln, msg))

    # ---- 1. brace / paren balance -------------------------------------
    depth = 0
    for i, l in enumerate(lines, 1):
        depth += l.count('{') - l.count('}')
        if depth < 0:
            bad(i, "closing brace with nothing open")
            depth = 0
    if depth != 0:
        bad(len(lines), "file ends with %d unclosed brace(s)" % depth)

    par = 0
    for i, l in enumerate(lines, 1):
        par += l.count('(') - l.count(')')
    if par != 0:
        bad(len(lines), "unbalanced parentheses across the file (%+d)" % par)

    brk = sum(l.count('[') - l.count(']') for l in lines)
    if brk != 0:
        bad(len(lines), "unbalanced square brackets across the file (%+d)" % brk)

    # ---- 2. every function that is CALLED must be defined --------------
    # definitions and prototypes both count
    defined = set()
    for m in re.finditer(r'^\s*(?:[A-Za-z_]\w*[\s*&]+)+([A-Za-z_]\w*)\s*\([^;{]*\)\s*[;{]',
                         code, re.M):
        defined.add(m.group(1))
    for m in re.finditer(r'#define\s+([A-Za-z_]\w*)', code):
        defined.add(m.group(1))

    called = {}
    for i, l in enumerate(lines, 1):
        for m in re.finditer(r'(?<![\w.>])([A-Za-z_]\w*)\s*\(', l):
            nm = m.group(1)
            if nm in KEYWORDS or nm in TYPE_WORDS:
                continue
            called.setdefault(nm, i)
    for nm, ln in sorted(called.items(), key=lambda kv: kv[1]):
        if nm in defined or nm in BUILTIN_FUNCS or nm in CTRADE_METHODS:
            continue
        if nm.startswith('ENUM_') or nm.isupper():
            continue          # a cast to an enum or a macro constant
        bad(ln, "calls '%s()' which is neither defined in this file nor a "
                "known built-in - typo, or a real missing function" % nm)

    # ---- 3. member calls on the CTrade object --------------------------
    for i, l in enumerate(lines, 1):
        for m in re.finditer(r'\btrade\.([A-Za-z_]\w*)\s*\(', l):
            if m.group(1) not in CTRADE_METHODS:
                bad(i, "trade.%s() is not a CTrade method this checker knows" % m.group(1))

    # ---- 4. inputs are READ ONLY ---------------------------------------
    inputs = set(re.findall(r'^\s*(?:input|sinput)\s+(?:\w+\s+)+?(\w+)\s*=', code, re.M))
    for i, l in enumerate(lines, 1):
        if re.match(r'^\s*(?:input|sinput)\b', l):
            continue
        for m in re.finditer(r'\b(Inp\w*|\w+)\s*(?:=(?!=)|\+\+|--|\+=|-=|\*=|/=)', l):
            nm = m.group(1)
            if nm in inputs:
                bad(i, "assigns to input '%s' - MQL5 inputs are read-only "
                       "and this will not compile" % nm)

    # ---- 5. globals used but never declared ----------------------------
    declared = set(inputs)
    for m in re.finditer(r'^\s*(?:static\s+)?(?:\w+)\s+(\w+)(?:\s*\[[^\]]*\])?\s*(?:=[^;]*)?;',
                         code, re.M):
        declared.add(m.group(1))
    for m in re.finditer(r'^\s*(?:\w+)\s+([\w,\s]+);', code, re.M):
        for nm in m.group(1).split(','):
            nm = nm.strip().split('[')[0].strip()
            if re.fullmatch(r'\w+', nm or ''):
                declared.add(nm)
    for m in re.finditer(r'\b(g_\w+)\b', code):
        declared.add(m.group(1)) if False else None
    used_g = {}
    for i, l in enumerate(lines, 1):
        for m in re.finditer(r'\b(g_\w+)\b', l):
            used_g.setdefault(m.group(1), i)
    for nm, ln in sorted(used_g.items(), key=lambda kv: kv[1]):
        if nm not in declared:
            bad(ln, "uses global '%s' which is never declared" % nm)

    # ---- 6. StringFormat / PrintFormat argument counts ------------------
    # A MULTI-LINE CALL USED TO BE SKIPPED HERE. The old code said "call wraps
    # lines; counted below" and there was no below, so every StringFormat laid
    # out over several lines - which is most of the interesting ones - went
    # unchecked. A bad edit then put NINE arguments against THREE specifiers in
    # DrawBox and nothing in this file noticed. Continuation lines are now
    # joined until the parentheses balance, so the call is checked as written.
    for i, l0 in enumerate(raw, 1):
        for fn in ("StringFormat", "PrintFormat"):
            j = 0
            l = l0
            while True:
                j = l.find(fn + "(", j)
                if j < 0:
                    break
                seg, ok = _balanced(l, j + len(fn))
                if not ok:
                    # pull in following lines until it closes, or give up
                    joined = l
                    for k in range(i, min(i + 30, len(raw))):
                        joined = joined.rstrip("\n") + " " + raw[k]
                        seg, ok = _balanced(joined, joined.find(fn + "(", j) + len(fn))
                        if ok:
                            break
                    if not ok:
                        break             # genuinely cannot tell; do not guess
                    l = joined
                j += len(fn)
                args = _split_args(seg)
                if not args:
                    break
                fmt = args[0].strip()
                if not (fmt.startswith('"') and fmt.endswith('"')):
                    break                 # not a literal, cannot check
                want = _spec_count(fmt)
                got = len(args) - 1
                if want != got:
                    bad(i, "%s has %d format specifier(s) but %d argument(s)"
                           % (fn, want, got))

    # ---- 6b. a bare statement at FILE SCOPE ------------------------------
    # A stray "foo();" outside any function is a guaranteed compile error and
    # is exactly what a careless edit leaves behind - a replacement that landed
    # in the forward-declaration block instead of in OnTick. Nothing here
    # looked for it. Depth is tracked by counting braces on stripped code.
    depth = 0
    for i, l in enumerate(lines, 1):
        c = strip_code(l)
        stripped = c.strip()
        if depth == 0 and re.match(r'^[A-Za-z_]\w*\s*\(.*\)\s*;\s*$', stripped):
            # a prototype is "type name(args);" - a CALL has no leading type
            if not re.match(r'^(void|int|double|bool|string|long|ulong|datetime|color|char|short|uint|ushort|float)\b',
                            stripped):
                bad(i, "statement '%s' sits OUTSIDE any function - will not compile"
                       % stripped[:48])
        depth += c.count("{") - c.count("}")
        if depth < 0:
            depth = 0

    # ---- 7. #define used but never defined ------------------------------
    defs = set(re.findall(r'#define\s+([A-Za-z_]\w*)', code))
    for i, l in enumerate(lines, 1):
        for m in re.finditer(r'\b(MAX_[A-Z_]+|ST_[A-Z_]+)\b', l):
            if m.group(1) not in defs:
                bad(i, "uses macro '%s' which is never #defined" % m.group(1))

    return problems


def _balanced(line, start):
    """Return the text inside the parens starting at `start`, and whether it
    closed on this line."""
    d = 0
    for k in range(start, len(line)):
        if line[k] == '(':
            d += 1
        elif line[k] == ')':
            d -= 1
            if d == 0:
                return line[start + 1:k], True
    return "", False


def _split_args(s):
    out, cur, d, q = [], "", 0, None
    for ch in s:
        if q:
            cur += ch
            if ch == q:
                q = None
            continue
        if ch in '"\'':
            q = ch; cur += ch; continue
        if ch in '([': d += 1
        elif ch in ')]': d -= 1
        if ch == ',' and d == 0:
            out.append(cur); cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def _spec_count(fmt):
    """Count printf specifiers. '%%' is a literal percent and takes nothing;
    '*' in a width takes an EXTRA argument, which is how %.*f works and is
    used throughout this EA."""
    n = 0
    i = 0
    while i < len(fmt):
        if fmt[i] == '%':
            if i + 1 < len(fmt) and fmt[i+1] == '%':
                i += 2; continue
            j = i + 1
            while j < len(fmt) and fmt[j] in "-+ #0123456789.*":
                if fmt[j] == '*':
                    n += 1
                j += 1
            while j < len(fmt) and fmt[j] in "hlIq":
                j += 1
            if j < len(fmt) and fmt[j] in "diouxXeEfgGcsp":
                n += 1
            i = j + 1
        else:
            i += 1
    return n


def io_read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def main():
    paths = sys.argv[1:] or ["JARVIS/ea/build/SuperTrendSniper.mq5"]
    total = 0
    for p in paths:
        if not os.path.exists(p):
            print("MISSING: %s" % p); total += 1; continue
        probs = check(p)
        print("=" * 70)
        print("  %s  (%d lines)" % (p, len(io_read(p).splitlines())))
        print("=" * 70)
        if not probs:
            print("  no problems found by these checks.")
            print("  This is NOT proof it compiles - only MetaEditor can say that.")
        for ln, msg in sorted(probs):
            print("  line %-5d %s" % (ln, msg))
        total += len(probs)
    print()
    print("%d problem(s)." % total)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())

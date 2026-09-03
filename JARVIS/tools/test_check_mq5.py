#!/usr/bin/env python3
"""
Regression test for check_mq5.py.

A checker that has never been shown to FAIL on broken input is decoration.
F-006 happened because check_pine.py was written from one example rather than
from the rule, so it caught that example and nothing else. Every check in
check_mq5.py gets a deliberately broken file here, and the test fails if the
checker passes it.
"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_mq5

GOOD = '''
#property strict
#include <Trade/Trade.mqh>
CTrade trade;
#define MAX_THING 10
input double InpRisk = 0.5;
input int    InpBars = 20;
double g_value = 0.0;
int    g_count = 0;

double Helper(double x)
{
   return x * 2.0;
}

void OnTick()
{
   double a = Helper(g_value);
   g_count++;
   PrintFormat("value %.2f count %d risk %.2f", a, g_count, InpRisk);
   if(g_count > MAX_THING) trade.PositionClose(1);
}
'''

CASES = [
    ("undefined function",
     GOOD.replace("Helper(g_value)", "Helpr(g_value)"),
     "Helpr"),
    ("undeclared global",
     GOOD.replace("double a = Helper(g_value);",
                  "double a = Helper(g_missing);"),
     "g_missing"),
    ("assignment to an input",
     GOOD.replace("g_count++;", "InpBars = 5;"),
     "read-only"),
    ("too few format arguments",
     GOOD.replace('"value %.2f count %d risk %.2f", a, g_count, InpRisk',
                  '"value %.2f count %d risk %.2f", a, g_count'),
     "format specifier"),
    ("too many format arguments",
     GOOD.replace('"value %.2f count %d risk %.2f", a, g_count, InpRisk',
                  '"value %.2f", a, g_count, InpRisk'),
     "format specifier"),
    ("unclosed brace",
     GOOD.replace("   return x * 2.0;\n}", "   return x * 2.0;"),
     "unclosed brace"),
    ("unbalanced parenthesis",
     GOOD.replace("double a = Helper(g_value);", "double a = Helper(g_value;"),
     "parenthes"),
    ("unknown CTrade method",
     GOOD.replace("trade.PositionClose(1)", "trade.PositionKill(1)"),
     "PositionKill"),
    ("undefined macro",
     GOOD.replace("#define MAX_THING 10\n", ""),
     "MAX_THING"),
]


def run_one(text):
    fd, path = tempfile.mkstemp(suffix=".mq5")
    os.write(fd, text.encode()); os.close(fd)
    try:
        return check_mq5.check(path)
    finally:
        os.unlink(path)


def main():
    fails = 0

    probs = run_one(GOOD)
    if probs:
        print("  FAIL  clean file was rejected:")
        for ln, m in probs:
            print("          line %d %s" % (ln, m))
        fails += 1
    else:
        print("  PASS  clean file passes")

    for name, text, needle in CASES:
        probs = run_one(text)
        hit = any(needle.lower() in m.lower() for _, m in probs)
        if hit:
            print("  PASS  catches: %s" % name)
        else:
            print("  FAIL  MISSED:  %s   (looked for %r, got %r)"
                  % (name, needle, [m for _, m in probs]))
            fails += 1

    print()
    if fails:
        print("%d CHECK(S) DO NOT WORK. Do not trust this checker." % fails)
        return 1
    print("All %d checks demonstrated on broken input." % len(CASES))
    return 0


if __name__ == "__main__":
    sys.exit(main())

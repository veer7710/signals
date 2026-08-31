"""
Assert that every fix claimed to be in the Pine files is ACTUALLY in them.

Written after shipping a file with `lastFireBar := bar_index` and no
declaration anywhere. The patch script that was supposed to add the
declaration printed "ok" for that edit and then aborted on a LATER anchor -
and because it only wrote the file at the very end, every edit it had reported
as done was discarded. The success messages were about an in-memory string
that never reached disk.

The same abort also silently dropped the fix for the triple-entry bug, which
had been reported to Veer as done. It was not.

So: never trust a patch script's own output. Check the file.

Run:  python3 JARVIS/tools/verify_fixes.py
"""
import re, sys

L = open("JARVIS/pine/LiquiditySniper_v1.pine", encoding="utf-8").read()
S = open("JARVIS/pine/SuperTrendSniper_v1.pine", encoding="utf-8").read()

CHECKS = [
    ("wrapped-line compile fix",     L, r"mj = \(array\.get\(hExt"),
    ("wrapped-line compile fix",     S, r"mj = \(array\.get\(hExt"),
    ("entryDelay minimum is 1",      L, r'entryDelay = input\.int\(1,[^)]*minval = 1'),
    ("entryDelay minimum is 1",      S, r'entryDelay = input\.int\(1,[^)]*minval = 1'),
    ("stop fills at a gap",          L, r"stopFill = d > 0 \? math\.min"),
    ("stop fills at a gap",          S, r"stopFill = d > 0 \? math\.min"),
    ("reversal exit needs held>0",   L, r"hitRev = useRevExit and held > 0"),
    ("reversal exit needs held>0",   S, r"hitRev = useRevExit and held > 0"),
    ("flip exit needs held>0",       L, r"hitFlp = useFlipExit and held > 0"),
    ("consumed FVG box deleted",     L, r"box\.delete\(bx0\)"),
    ("wrong-side level born dead",   L, r"array\.push\(dead, bornDead\)"),
    ("structure bias decays",        L, r"bar_index - lastBosBar > biasLife"),
    ("order blocks expire",          L, r"bar_index - obUpBar\) <= obLife"),
    ("order-row fn global scope",    L, r"(?m)^oRow\(int r"),
    ("order drawings cleared",       L, r"(?m)^clearOrders\(\) =>"),
    ("cap counts pending queue",     L, r"array\.size\(trDir\) \+ array\.size\(pdDir\) < maxTrades"),
    ("cap counts pending queue",     S, r"array\.size\(trDir\) \+ array\.size\(pdDir\) < maxTrades"),
    ("entry cooldown declared",      L, r"var int lastFireBar"),
    ("entry cooldown declared",      S, r"var int lastFireBar"),
    ("inverse fair value gaps",      L, r"array\.set\(fvInv, i, true\)"),
    ("BSL/SSL naming",               L, r'isHigh \? "SSL" : "BSL"'),
    ("sweep marks pruned",           L, r"(?m)^keepSweep\(label l\) =>"),
    ("zone labels only near price",  L, r"labelNear \* atr"),
    ("clean mode",                   L, r"cleanMode = input\.bool"),
    ("setup scoreboard",             L, r"var table board = table\.new"),
    ("order book",                   L, r"var table obook = table\.new"),
    ("max_bars_back declared",       L, r"max_bars_back = 500"),
]

def main():
    bad = 0
    for name, src, rx in CHECKS:
        which = "LIQ" if src is L else "ST "
        ok = bool(re.search(rx, src))
        if not ok:
            bad += 1
        print(f"  {'ok     ' if ok else 'MISSING'} {which}  {name}")
    print(f"\n  {len(CHECKS)-bad}/{len(CHECKS)} present")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())

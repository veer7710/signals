#!/usr/bin/env python3
"""
Every stop an EA asks the broker to hold must be on the right side of price.

E-151 was a RESEARCH bug: a trail computed from a bar's own extreme and then
filled at, on the far side of that same bar's close. check_trails.py catches
that class in JARVIS/research. The EAs were never covered, and they have the
same failure mode with a different symptom: a PositionModify to a level on the
wrong side of price is rejected by the broker, so the stop silently stops
moving while the log says the trail is running. Three of those rejections were
found unlogged in an earlier audit (F13).

For every trade.PositionModify(...) call this asks two questions:

  1. is the requested level tested against the CURRENT price before it is sent?
     A level already behind price cannot be placed - the fix is to leave the
     stop where it is, never to send it anyway.
  2. is the result checked? MQL5's PositionModify returns bool and an unchecked
     false is a stop that did not move, reported as one that did.

It reads intent from the surrounding lines rather than parsing MQL5 properly,
so it is A PROMPT TO GO AND LOOK, NOT A PROOF. It errs toward reporting, and
both calls it currently reports turn out to be safe because of conditions
further up their functions that it cannot see - a break-even move gated on the
trade already being in profit, and a give-back stop that price must have passed
through to reach. Reported anyway, because "safe because of something twenty
lines away" is exactly the kind of safety that stops being true after an edit.

    python3 JARVIS/tools/check_ea_stops.py
    python3 JARVIS/tools/check_ea_stops.py --strict
"""
from __future__ import annotations
import glob, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "ea", "build")
# What counts as a real side test: the requested level compared against the
# CURRENT PRICE, with direction. A ratchet (level vs the OLD stop) is NOT the
# same thing and does not count - LiquiditySniper has a ratchet and a
# broker-minimum-distance test and still had no price-side test, which is how
# this distinction earned its own line.
# What counts as a real side test: the requested level compared against the
# CURRENT PRICE, with direction.
#
# Two things deliberately do NOT count, and loosening the pattern to accept
# them was a mistake made once already while writing this file:
#   * a RATCHET (level vs the OLD stop) says the stop only improves. It says
#     nothing about whether the new level is on the right side of price now.
#   * a DISTANCE test, MathAbs(px - want) < minStop, rejects levels too CLOSE
#     to price in EITHER direction. A level on the wrong side but far away
#     sails through it.
# Both appear in this codebase and both were briefly accepted here, which made
# a real gap disappear from the report. The strict pattern is the honest one.
# `dir * (a - b)` where EITHER side is the current price is a genuine
# directional test - SweepSniper writes it as dir * (px - cand), which the
# first version of this pattern missed and reported as a gap.
SIDE = re.compile(r"dir\s*\*\s*\(\s*\w+\s*-\s*(?:price|px|bid|ask)\b|"
                  r"dir\s*\*\s*\(\s*(?:price|px|bid|ask)\s*-\s*\w+|"
                  r"\(dir > 0\)\s*\?\s*\(?\s*\w+\s*[<>]\s*(?:price|px)\b|"
                  r"(?:price|px)\s*[<>]\s*\w+\s*\)?\s*:\s*")
RESULT = re.compile(r"if\s*\(.*PositionModify|!\s*trade\.PositionModify|"
                    r"=\s*trade\.PositionModify")


def check(path, window=14):
    src = open(path, encoding="utf-8").read().split("\n")
    out = []
    for i, ln in enumerate(src):
        if "PositionModify(" not in ln or ln.strip().startswith("//"):
            continue
        ctx = "\n".join(src[max(0, i - window):i + 2])
        side = bool(SIDE.search(ctx))
        res = bool(RESULT.search(ln))
        if side and res:
            continue
        why = []
        if not side:
            why.append("no side/placeability test in the %d lines above" % window)
        if not res:
            why.append("the return value is not checked")
        out.append((i + 1, ln.strip()[:70], "; ".join(why)))
    return out


def main():
    paths = [p for p in sorted(glob.glob(os.path.join(ROOT, "*.mq5")))
             if "_SINGLEFILE" not in p]
    print("=" * 78)
    print("  EA STOP PLACEMENT — E-151's class, on the MQL5 side")
    print("=" * 78)
    total = 0
    for p in paths:
        hits = check(p)
        print(f"\n  {os.path.basename(p)}: "
              f"{'clean' if not hits else str(len(hits)) + ' to look at'}")
        for ln, code, why in hits:
            print(f"      line {ln}: {code}")
            print(f"          {why}")
            total += 1
    print(f"\n  {total} call(s) worth reading.")
    return 1 if (total and "--strict" in sys.argv) else 0


if __name__ == "__main__":
    sys.exit(main())

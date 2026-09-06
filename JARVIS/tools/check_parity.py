#!/usr/bin/env python3
"""
Does the Pine ship the same strategy as the EA?

P92 is the reason this exists: the assumption the whole project rests on - that
the chart and the EA are the same thing - went unchecked for 180 commits, and
when it was finally checked, 52-54% of the chart's labels were trades the EA
refused. That was a SIGNAL difference. This tool catches the cheaper and more
embarrassing version: the two files drifting apart on a DEFAULT.

It cannot check logic. It checks that every parameter the two files share has
the same default, and that neither has quietly gained a knob the other lacks.

    python3 JARVIS/tools/check_parity.py
"""
from __future__ import annotations
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINE = os.path.join(ROOT, "pine", "LIQUIDITY_SNIPER_2_0.pine")
EA   = os.path.join(ROOT, "ea", "build", "SweepSniper.mq5")

# Pine name -> EA name. Anything not in here is reported as unpaired, so adding
# an input to one file and not the other is caught rather than assumed benign.
PAIRS = {
    "pvLen":      "InpPivotBars",
    "sweepAtr":   "InpSweepAtr",
    "wickCut":    "InpWickCut",
    "useDisp":    "InpUseDisp",
    "stopBuf":    "InpStopBufAtr",
    "maxRisk":    "InpMaxRiskAtr",
    "giveBack":   "InpGiveBack",
    "maxHold":    "InpMaxBars",
    "useSweep":   "InpUseSweep",
    "useBR":      "InpUseBR",
    "brAtr":      "InpBrAtr",
    "brTol":      "InpBrTol",
    "brWait":     "InpBrWait",
    "obLen":      "InpObLen",
    "sessFilter": "InpOverlapOnly",
    "lifeBars":   "InpSetupLife",
    "obThr":      "InpObThrPct",
}
# The Pine has ONE order-block switch; the EA splits it into the two entry
# types. Checked separately because "equal" means something different here.
OB_PINE, OB_EA = "useOB", ("InpUseObDetect", "InpUseObReturn")

# Deliberately unpaired, with the reason. Anything else unpaired is a finding.
PINE_ONLY = {
    "showLvl": "drawing", "showSmc": "drawing", "showZones": "drawing",
    "showLive": "drawing", "showHist": "drawing", "showPanel": "drawing",
    "showSess": "drawing", "showRefused": "drawing", "panelBig": "drawing",
    "panelPos": "drawing", "keepDead": "drawing", "tgtMode": "drawing",
    "tgtR": "drawing", "sessA": "drawing", "sessL": "drawing",
    "sessN": "drawing", "tzSess": "drawing", "cBuy": "drawing",
    "cSell": "drawing", "ccy": "money display", "gbpPoint": "money display",
    "lots": "money display", "spreadPts": "cost model, panel only",
    "slipPts": "cost model, panel only", "obMode": "EA has two switches",
    "dispCut": "matched below", "maxLvlAge": "Pine-side housekeeping",
    "maxOB": "how many zones to DRAW - the EA draws nothing",
    "obRealtime": "draws the forming block - the EA draws nothing",
    "showLevels": "the SMC level layer - drawing only",
    "htfOn": "higher-timeframe bias, drawing and panel only",
    "htfTf": "bias timeframe, drawing and panel only",
    "htfLen": "bias EMA length, drawing and panel only",
    "htfDim": "how against-trend signals are drawn",
    "showLegs": "the leg scoreboard - drawing and panel only",
    "legMin": "smallest leg to draw, drawing only",
    "legLbl": "leg size labels, drawing only",
    "obRule": "which block rule to DRAW - the EA draws nothing",
    "volLen": "volume pivot length, drawing only",
    "showBreak": "drawing only",
    "maxLvl": "how many levels to DRAW - the EA draws nothing",
}


def pine_inputs(src):
    out = {}
    pat = re.compile(r"^(\w+)\s*=\s*input\.\w+\(\s*([^,\)]+)", re.M)
    for m in pat.finditer(src):
        out[m.group(1)] = m.group(2).strip()
    return out


def ea_inputs(src):
    out = {}
    pat = re.compile(r"^input\s+\w+\s+(\w+)\s*=\s*([^;]+);", re.M)
    for m in pat.finditer(src):
        out[m.group(1)] = m.group(2).strip()
    return out


def norm(v):
    v = v.strip().strip('"')
    if v in ("true", "false"):
        return v
    try:
        return f"{float(v):.6g}"
    except ValueError:
        return v


def main():
    p = open(PINE).read()
    e = open(EA).read()
    P, E = pine_inputs(p), ea_inputs(e)
    print("=" * 74)
    print("  PINE / EA PARITY — shared parameters must have the same default")
    print("=" * 74)
    bad = 0
    for pn, en in sorted(PAIRS.items()):
        if pn not in P:
            print(f"  MISSING in Pine: {pn}"); bad += 1; continue
        if en not in E:
            print(f"  MISSING in EA:   {en}"); bad += 1; continue
        a, b = norm(P[pn]), norm(E[en])
        if a != b:
            print(f"  DIFFERENT  {pn} = {a}   but   {en} = {b}"); bad += 1
        else:
            print(f"  ok         {pn:<12} = {a:<8} == {en}")

    if OB_PINE in P:
        want = norm(P[OB_PINE])
        for en in OB_EA:
            if en in E and norm(E[en]) != want:
                print(f"  DIFFERENT  {OB_PINE} = {want}   but   {en} = {norm(E[en])}")
                bad += 1
            elif en in E:
                print(f"  ok         {OB_PINE:<12} = {want:<8} == {en}")

    known = set(PAIRS) | {OB_PINE} | set(PINE_ONLY)
    extra = [k for k in P if k not in known]
    if extra:
        print("\n  Pine inputs with no EA counterpart and no stated reason:")
        for k in extra:
            print(f"    {k} = {P[k]}")
        print("  Either pair it in PAIRS, or list it in PINE_ONLY with why.")
        bad += len(extra)

    print("\n  " + ("PARITY OK" if not bad else f"{bad} MISMATCH(ES)"))
    print("  This checks DEFAULTS, not logic. Signal parity is P92 / E-139.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

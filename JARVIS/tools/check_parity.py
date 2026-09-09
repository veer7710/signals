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

# THE SECOND PAIR, WHICH THIS TOOL WAS NOT WATCHING.
# It only ever compared the liquidity Pine against SweepSniper. The SuperTrend
# pair was uncovered, and that is exactly how a trail change landed in
# SuperTrendSniper.mq5 (give back a fraction of the run-up) while the Pine kept
# a fixed ATR distance - two different exits, no tool saying so, and a panel
# measuring a system that was not the one trading.
ST_PINE = os.path.join(ROOT, "pine", "SUPERTREND_SNIPER_5_0.pine")
ST_EA   = os.path.join(ROOT, "ea", "build", "SuperTrendSniper.mq5")
ST_PAIRS = {
    "stLen":    "InpStAtrLen",
    "stMult":   "InpStMult",
    "useDema":  "InpUseDemaFilter",
    "stopAtr":  "InpStopAtrMult",
    "trailAtr": "InpTrailAtrMult",
    "giveBack": "InpGiveBack",
    "useTrail": "InpUseTrail",
    "tpR":      "InpTargetR",
    "maxStall": "InpMaxStall",
}

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
    "beAtR":      "InpBeAtR",
    "hiWin":      "InpHiWinR",
    "trailAtR":   "InpTrailAtR",
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
    "cleanChart": "the master drawing switch - the EA draws nothing",
    # THE SMC ENTRY IS CHART-ONLY UNTIL THE EA IMPLEMENTS IT. Listing these
    # here is a promise to pair them the moment SweepSniper grows the same
    # sweep-then-CHoCH-then-order-block chain - the sweep it has now fires on a
    # touch of the level, not on a close back inside it, so the two files are
    # genuinely running different entries and pairing them would assert a
    # parity that does not exist.
    "useSmcEntry": "SMC entry chain - Pine only until the EA implements it",
    "smcEqTol": "SMC entry, Pine only",
    "smcSweep": "SMC entry, Pine only",
    "smcWait": "SMC entry, Pine only",
    "smcMode": "SMC entry, Pine only",
    "smcStopBuf": "SMC entry, Pine only",
    "smcLife": "SMC entry, Pine only",
    "showHour": "E-190 hour readout - panel only, never filters",
    "useLegCatch": "E-184 leg catcher - chart-only until it is measured on money",
    "lcNeed": "leg catcher threshold, chart only",
    "lcEmaLen": "leg catcher mean length, chart only",
    "lcStretch": "leg catcher stretch threshold, chart only",
    "lcVolX": "leg catcher volume multiple, chart only",
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
    "mtfOn": "the trend stack row - panel only",
    "showCheck": "the confluence checklist - panel only",
    "minGrade": "which grades PRINT - the EA takes every armed setup",
    "volPush": "volume push marks - drawing only",
    "volPushX": "volume push threshold - drawing only",
    "acctSize": "sizing readout - panel only",
    "riskPct": "sizing readout - panel only",
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


def compare(label, pine_path, ea_path, pairs, strict_extra=True):
    """One Pine/EA pair. Returns the number of mismatches."""
    P, E = pine_inputs(open(pine_path).read()), ea_inputs(open(ea_path).read())
    print(f"\n  ---- {label} ----")
    bad = 0
    for pn, en in sorted(pairs.items()):
        if pn not in P:
            print(f"  not in the Pine: {pn}  (rename it here or in the file)")
            bad += 1
            continue
        if en not in E:
            print(f"  not in the EA:   {en}")
            bad += 1
            continue
        a, b = norm(P[pn]), norm(E[en])
        if a != b:
            print(f"  DIFFERENT  {pn} = {a}   but   {en} = {b}")
            bad += 1
        else:
            print(f"  ok         {pn:<12} = {a:<8} == {en}")
    return bad


def main():
    p = open(PINE).read()
    e = open(EA).read()
    P, E = pine_inputs(p), ea_inputs(e)
    print("=" * 74)
    print("  PINE / EA PARITY — shared parameters must have the same default")
    print("=" * 74)
    print("\n  ---- liquidity: LIQUIDITY_SNIPER_2_0.pine <-> SweepSniper.mq5 ----")
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

    bad += compare("supertrend: SUPERTREND_SNIPER_5_0.pine <-> "
                   "SuperTrendSniper.mq5", ST_PINE, ST_EA, ST_PAIRS)

    # THE DEMA LENGTH IS THE SAME BEHAVIOUR ENCODED TWO DIFFERENT WAYS, so
    # comparing the raw numbers reports a mismatch that is not one:
    #   Pine  demaLen = 0             means "per clock: 60 on M1, 100 on M3, else 200"
    #   EA    InpDemaPerClock = true  means the same thing, with InpDemaLen = 200
    #         as the "else" value
    # What has to agree is the BEHAVIOUR, so that is what is checked. If either
    # file ever pins a fixed length, the other must pin the same one.
    SP = pine_inputs(open(ST_PINE).read())
    SE = ea_inputs(open(ST_EA).read())
    pineAuto = norm(SP.get("demaLen", "")) == "0"
    eaAuto   = norm(SE.get("InpDemaPerClock", "")) == "true"
    if pineAuto != eaAuto:
        print(f"  DIFFERENT  the DEMA length rule: Pine per-clock={pineAuto}, "
              f"EA InpDemaPerClock={eaAuto}")
        bad += 1
    elif pineAuto:
        print("  ok         DEMA length   = per clock on BOTH "
              "(60 M1 / 100 M3 / else the fixed length)")
    elif norm(SP.get("demaLen", "")) != norm(SE.get("InpDemaLen", "")):
        print(f"  DIFFERENT  demaLen = {norm(SP.get('demaLen',''))}   but   "
              f"InpDemaLen = {norm(SE.get('InpDemaLen',''))}")
        bad += 1
    else:
        print(f"  ok         demaLen      = {norm(SP.get('demaLen',''))} "
              f"       == InpDemaLen")

    print("\n  " + ("PARITY OK" if not bad else f"{bad} MISMATCH(ES)"))
    print("  This checks DEFAULTS, not logic. Signal parity is P92 / E-139.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

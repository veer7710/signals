"""
READ THE DEMO EXECUTION JOURNAL — and replace the assumption at the centre of
this project with a measurement.

Every backtest in this repo charges cost through one assumed number: today's
spread as 0.11 of M1 ATR (E-132), applied as one fixed price on every clock
(E-173). Slippage is assumed to be exactly zero. Neither has ever been observed
on Veer's broker, and both are load-bearing - E-149's M5 book is +24.2 points
and turns negative at 0.02 points of slippage.

The EAs now write JARVIS_exec_<EA>_<SYMBOL>.csv into MQL5/Files. Copy those
files into JARVIS/data/exec/ and run:

    python3 JARVIS/research/read_exec.py

It reports the two numbers that matter - measured spread/ATR and measured
slippage - and then says, in points, what they do to the research.

WHAT WOULD MAKE THIS DATA WORTHLESS
  * fewer than ~30 fills: the slippage median is noise
  * a demo server that fills every stop order at exactly the level: some demo
    feeds do, and it will read as zero slippage that live will not honour.
    The file prints the share of EXACTLY-zero-slip fills so that is visible.
"""
from __future__ import annotations
import csv, glob, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import COST_M1_SPREAD_ATR

DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "data", "exec")


def rows():
    out = []
    for p in sorted(glob.glob(os.path.join(DIR, "JARVIS_exec_*.csv"))):
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                out.append(r)
    return out


def num(r, k):
    try:
        return float(r[k])
    except (KeyError, TypeError, ValueError):
        return None


def main():
    R = rows()
    if not R:
        print(f"  no journals found under {DIR}")
        print("  copy JARVIS_exec_*.csv out of MetaTrader's MQL5/Files folder.")
        return 1

    print("=" * 88)
    print(f"  EXECUTION JOURNAL — {len(R)} rows from "
          f"{len(set(r['ea'] for r in R))} EA(s)")
    print("=" * 88)

    fills = [r for r in R if r["event"] == "FILL"]
    print(f"\n  {'ea':<18}{'fills':>7}{'exits':>7}{'med spread':>12}"
          f"{'med ATR':>10}{'sp/ATR':>9}{'med slip':>10}{'worst':>9}")
    print("  " + "-" * 82)
    for ea in sorted(set(r["ea"] for r in R)):
        f = [r for r in fills if r["ea"] == ea]
        x = [r for r in R if r["ea"] == ea and r["event"] == "EXIT"]
        sp = [v for v in (num(r, "spread_pts") for r in f) if v]
        at = [v for v in (num(r, "atr") for r in f) if v]
        sl = [v for v in (num(r, "slip_pts") for r in f) if v is not None]
        if not f:
            continue
        msp = statistics.median(sp) if sp else 0.0
        mat = statistics.median(at) if at else 0.0
        print(f"  {ea:<18}{len(f):>7}{len(x):>7}{msp:>12.4f}{mat:>10.4f}"
              f"{(msp / mat if mat else 0):>9.3f}"
              f"{(statistics.median(sl) if sl else 0):>10.4f}"
              f"{(max(sl) if sl else 0):>9.4f}")

    sp = [v for v in (num(r, "spread_pts") for r in fills) if v]
    at = [v for v in (num(r, "atr") for r in fills) if v]
    sl = [v for v in (num(r, "slip_pts") for r in fills) if v is not None]
    if not (sp and at and sl):
        print("\n  not enough numeric rows to conclude anything.")
        return 0

    msp, mat = statistics.median(sp), statistics.median(at)
    ratio = msp / mat if mat else 0.0
    zero = 100.0 * sum(1 for v in sl if v == 0.0) / len(sl)

    print("\n" + "=" * 88)
    print("  THE TWO NUMBERS THE RESEARCH ASSUMES")
    print("=" * 88)
    print(f"  spread / ATR        assumed {COST_M1_SPREAD_ATR:.3f}"
          f"    measured {ratio:.3f}"
          f"    {'CHEAPER than assumed' if ratio < COST_M1_SPREAD_ATR else 'MORE EXPENSIVE than assumed'}")
    print(f"  slippage per fill   assumed 0.0000 pts"
          f"  measured median {statistics.median(sl):+.4f}"
          f"  mean {statistics.fmean(sl):+.4f}")
    print(f"                      worst {max(sl):+.4f}, best {min(sl):+.4f},"
          f" n = {len(sl)}")
    print(f"  {zero:.0f}% of fills slipped EXACTLY zero.", end=" ")
    if zero > 60:
        print("On a demo feed that usually means the")
        print("  server is filling at the requested level as a courtesy. Live will not.")
    else:
        print("")

    print("\n  WHAT IT DOES TO THE RESEARCH")
    extra = statistics.fmean(sl)
    print(f"  Slippage costs {extra:+.4f} pts per fill, in ADDITION to the spread.")
    print(f"  E-149's M5 book was +24.2 pts over 2058 trades (+0.0118/trade) and")
    print(f"  break-even slippage there is 0.0118 pts.")
    if extra >= 0.0118:
        print(f"  Measured slippage is {extra:.4f} >= 0.0118, so that book is NEGATIVE"
              " in reality.")
    else:
        print(f"  Measured slippage is {extra:.4f} < 0.0118, so that book survives its"
              " own")
        print("  slippage test - which is necessary and nowhere near sufficient.")
    print("\n  This measures EXECUTION. It says nothing about whether the signal"
          " has an edge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

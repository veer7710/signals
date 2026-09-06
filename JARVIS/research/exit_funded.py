"""
E-156 — THE EXIT DECIDED BY THE RULES IT HAS TO LIVE UNDER.

E-155 left the sweep's exit genuinely undecided, and it should have:

    M1  give 0.25   288.6 pts   maxDD GBP18   53.3% win   longest losing run 10
    M1  atr 1.5     372.8 pts   maxDD GBP35   40.8% win   longest losing run 17
    M5  give 0.25   171.3 pts   maxDD GBP26   55.6% win   run 9   <- also the
                                                                     risk-adjusted
                                                                     winner
Points say one thing, drawdown says another, and neither is the actual
constraint. The actual constraints are: a GBP60 live account that cannot size
below 0.01 lots (E-081), and prop-firm rules that fail an account on EQUITY,
enforce a minimum number of profitable days, and in four of seven cases enforce
a consistency cap on the best day.

So the exits are put through the firms. `funded.pass_rate` walks a simulated
account day by day under each firm's real rules.
"""
from __future__ import annotations
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, trail_level, trail_apply
from liq_m1 import load
import combined as C
import funded as F
import exit_riskadj as RA

PER_DAY = {"M1": 23.8, "M5": 5.2}


def book_R(tf, mode, param, cooldown=5, hold=240):
    """Per-trade result in R - what the funded simulator needs."""
    s, SP, A, cs, cand = RA.prep(tf)
    out, busy = [], -1
    for (j, _, d, entry, sl0) in cand:
        if j <= busy:
            continue
        risk = abs(entry - sl0)
        if risk <= 0:
            continue
        px, kk = RA.trade(s, A, j, d, entry, sl0, mode, param)
        pts = d * ((px - d * SP[kk] * cs / 2.0) - entry)
        out.append(pts / risk)
        busy = kk + cooldown
    return out


def main():
    EXITS = (("give", 0.25, "give 0.25"),
             ("atr", 1.5, "atr 1.5"),
             ("atr", 3.0, "atr 3"))
    for tf in ("M1", "M5"):
        tpd = [max(1, int(round(PER_DAY[tf])))]
        print("=" * 104)
        print(f"  E-156 — {tf} sweep: which exit survives the funded rules")
        print("=" * 104)
        books = {}
        for (mode, param, lbl) in EXITS:
            R = book_R(tf, mode, param)
            books[lbl] = R
            print(f"    {lbl:<12} n={len(R):<6} mean {statistics.mean(R):+.4f}R  "
                  f"sd {statistics.pstdev(R):.3f}  "
                  f"win {100*sum(1 for x in R if x>0)/len(R):.1f}%")
        for risk_pct in (0.0025, 0.005):
            print(f"\n    ---- risking {risk_pct*100:.2f}% of the account per trade ----")
            print(f"    {'firm':<34}" + "".join(f"{l:>13}" for (_, _, l) in EXITS))
            for key, firm in F.FIRMS.items():
                cells = []
                for (_, _, lbl) in EXITS:
                    pr, dys, why = F.pass_rate(books[lbl], tpd, firm, risk_pct,
                                               trials=400, seed=11)
                    cells.append(pr)
                print(f"    {firm.name:<34}" +
                      "".join(f"{x*100:>12.1f}%" for x in cells))
        print()


if __name__ == "__main__":
    main()

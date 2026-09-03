"""
E-086 — Back-to-back same-direction signals. Veer says they lose. Do they?

From forward testing: "back to back same direction signals can cause loss as m1
trends are not often big and the ea shouldn't assume they continue".

That is a precise, falsifiable claim about the EA's own signal stream, and it
has never been measured. The EA's only defence today is InpReentryCool = 3
bars, which was set by argument rather than by measurement.

Three questions, in order:
  1. Is a SAME-direction signal worse than an ALTERNATING one?
  2. If so, does it depend on how the previous trade ENDED - a winner
     continuing is a different animal from a loser being re-tried?
  3. Does the gap in bars since the last exit change it?

Every trade is the EA's own: SuperTrend(7,1.2) + DEMA, 2.0 ATR stop, the
R-denominated exit stack build 2.15 ships with. Ties lose, costs both ends.

Run:  python3 JARVIS/research/reentry.py
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from liquidity import stat
from failure_map import supertrend_trades

GBP = 1.00 / 1.27


def annotate(tr):
    """Tag each trade with what came before it. Nothing here looks forward."""
    out = []
    for k, x in enumerate(tr):
        y = dict(x)
        if k == 0:
            y["same_dir"] = None
            y["prev_won"] = None
            y["gap"] = None
        else:
            p = tr[k - 1]
            y["same_dir"] = 1.0 if p["side"] == x["side"] else 0.0
            y["prev_won"] = 1.0 if p["r"] > 0 else 0.0
            y["gap"] = x["i_in"] - p["i_out"]
        out.append(y)
    return out


def line(name, sel, tot_pts):
    if not sel:
        return
    a = stat(sel)
    p = sum(x["pts"] for x in sel)
    share = 100.0 * p / tot_pts if tot_pts else 0.0
    flag = "   <-- LOSES" if a["exp"] < 0 else ""
    print(f"   {name:<34}{a['n']:>6}{a['win']:>7.1f}%{a['exp']:>+9.3f}R"
          f"{a['pf']:>7.2f}{p:>+9.0f}{p*GBP:>+8.0f}{share:>8.0f}%{flag}")


def main():
    print("=" * 100)
    print("  E-086  BACK-TO-BACK SAME-DIRECTION SIGNALS")
    print("  Veer's forward-test claim, measured on the EA's own trade stream.")
    print("  'share' is that group's contribution to total points.")
    print("=" * 100)

    pool = []
    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        tr = annotate(supertrend_trades(s, study.COSTS["GOLD"]))
        pool += tr
        tot = sum(x["pts"] for x in tr)
        print(f"\n  ### {sym} {tf}   {len(tr)} trades, {tot:+.0f} points total")
        print(f"   {'group':<34}{'n':>6}{'win%':>8}{'expect':>10}{'PF':>7}"
              f"{'points':>9}{'GBP':>8}{'share':>9}")
        print("   " + "-" * 90)
        line("ALTERNATING direction", [x for x in tr if x["same_dir"] == 0.0], tot)
        line("SAME direction as the last", [x for x in tr if x["same_dir"] == 1.0], tot)
        line("  same dir, previous WON", [x for x in tr if x["same_dir"] == 1.0
                                          and x["prev_won"] == 1.0], tot)
        line("  same dir, previous LOST", [x for x in tr if x["same_dir"] == 1.0
                                           and x["prev_won"] == 0.0], tot)

    tot = sum(x["pts"] for x in pool)
    print(f"\n  ### POOLED   {len(pool)} trades, {tot:+.0f} points")
    print(f"   {'group':<34}{'n':>6}{'win%':>8}{'expect':>10}{'PF':>7}"
          f"{'points':>9}{'GBP':>8}{'share':>9}")
    print("   " + "-" * 90)
    line("ALTERNATING direction", [x for x in pool if x["same_dir"] == 0.0], tot)
    line("SAME direction as the last", [x for x in pool if x["same_dir"] == 1.0], tot)
    line("  same dir, previous WON", [x for x in pool if x["same_dir"] == 1.0
                                      and x["prev_won"] == 1.0], tot)
    line("  same dir, previous LOST", [x for x in pool if x["same_dir"] == 1.0
                                       and x["prev_won"] == 0.0], tot)

    # ---- does the gap matter?
    print(f"\n  SAME-DIRECTION ONLY, by bars since the previous trade closed")
    print(f"   {'gap':<34}{'n':>6}{'win%':>8}{'expect':>10}{'PF':>7}"
          f"{'points':>9}{'GBP':>8}{'share':>9}")
    print("   " + "-" * 90)
    sd = [x for x in pool if x["same_dir"] == 1.0 and x["gap"] is not None]
    for lo, hi in ((0, 1), (1, 3), (3, 8), (8, 20), (20, 10 ** 9)):
        sel = [x for x in sd if lo <= x["gap"] < hi]
        lbl = f"{lo}-{hi} bars" if hi < 10 ** 9 else f"{lo}+ bars"
        line(lbl, sel, tot)

    print("\n  WHAT THE ANSWER LICENSES")
    print("  * If same-direction is worse, the fix is NOT automatically to ban it:")
    print("    E-074 and E-085 both found that removing trades removes more money")
    print("    than it saves. Size down first, and read the 'share' column - a")
    print("    group carrying real points is not one to delete.")


if __name__ == "__main__":
    main()

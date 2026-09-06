"""
E-154 — 3-ATR TRAIL vs 25% GIVE-BACK: THE WHOLE COST, NOT JUST THE POINTS.

E-153 says the sweep wants a 3 ATR trail, chosen on the first half and winning
on the second half it never saw, on BOTH clocks. Before that ships it has to be
priced properly, because it buys its extra points with something:

    give 0.25   53.3% win   many small wins, small give-back
    atr 3       28.7% win   few big wins, four losers out of five

Veer trades this by hand at a high win rate and says so often. A 29% win rate
is a different job psychologically, and on a FUNDED account it is a different
job mechanically too: long losing streaks are what breach a daily loss limit
and what trip a consistency rule.

So this measures both exits on everything that decides whether it can be run:
points, worst trade, max drawdown in points, longest losing streak, the
distribution of streaks, slippage sensitivity, and the funded pass rate.
"""
from __future__ import annotations
import os, sys, statistics, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liq_m1 import load, GBP
import per_signal_exit2 as X
import combined as C
import funded as F

TODAY = 7.38
GBP_PT = TODAY * GBP


def series(tf, mode, param, slip=0.0):
    r = X.book(tf, C.SWEEP, mode, param)
    return [x - slip for x in r] if slip else r


def stats(r):
    n = len(r)
    tot = sum(r)
    eq, peak, dd = 0.0, 0.0, 0.0
    streak, worst_streak = 0, 0
    streaks = []
    for x in r:
        eq += x
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
        if x <= 0:
            streak += 1
        else:
            if streak:
                streaks.append(streak)
            worst_streak = max(worst_streak, streak)
            streak = 0
    worst_streak = max(worst_streak, streak)
    if streak:
        streaks.append(streak)
    streaks.sort()
    return {
        "n": n, "pts": tot, "per": tot / n,
        "win": 100.0 * sum(1 for x in r if x > 0) / n,
        "best": max(r), "worst": min(r),
        "dd": dd, "maxstreak": worst_streak,
        "streak95": streaks[int(0.95 * (len(streaks) - 1))] if streaks else 0,
        "sd": statistics.pstdev(r),
        "t": (tot / n) / (statistics.pstdev(r) / n ** 0.5),
    }


def main():
    print("=" * 100)
    print("  E-154 — the sweep's exit, priced in full. XAUUSD.")
    print("  Points are $1.00 of XAUUSD. 0.01 lots = GBP0.787 a point (E-081).")
    print("=" * 100)
    for tf in ("M1", "M5"):
        print(f"\n  ---------------- {tf} ----------------")
        print(f"  {'exit':<12}{'n':>6}{'win%':>7}{'points':>9}{'/trade':>9}"
              f"{'t':>7}{'maxDD':>8}{'worst':>8}{'best':>8}{'lose run':>10}")
        rows = {}
        for (mode, param, lbl) in (("give", 0.25, "give 0.25"),
                                   ("atr", 3.0, "atr 3"),
                                   ("atr", 2.0, "atr 2"),
                                   ("atr", 5.0, "atr 5")):
            st = stats(series(tf, mode, param))
            rows[lbl] = st
            print(f"  {lbl:<12}{st['n']:>6}{st['win']:>6.1f}%{st['pts']:>9.1f}"
                  f"{st['per']:>+9.4f}{st['t']:>7.2f}{st['dd']:>8.1f}"
                  f"{st['worst']:>8.2f}{st['best']:>8.2f}{st['maxstreak']:>10}")
        a, b = rows["give 0.25"], rows["atr 3"]
        print(f"\n  In money at 0.01 lots: give 0.25 = GBP{a['pts']*GBP_PT:,.0f} "
              f"with GBP{a['dd']*GBP_PT:,.0f} max drawdown")
        print(f"                          atr 3     = GBP{b['pts']*GBP_PT:,.0f} "
              f"with GBP{b['dd']*GBP_PT:,.0f} max drawdown")
        print(f"  Longest run of losers: give 0.25 = {a['maxstreak']}, "
              f"atr 3 = {b['maxstreak']}  (95th pct {a['streak95']} vs {b['streak95']})")

        print(f"\n  SLIPPAGE — total points, the thing that killed the extras")
        print(f"    {'exit':<12}" + "".join(f"{s:>10}" for s in
                                            ("0.00", "0.02", "0.05", "0.10", "0.20")))
        for lbl, (mode, param) in (("give 0.25", ("give", 0.25)),
                                   ("atr 3", ("atr", 3.0))):
            out = []
            for sl in (0.0, 0.02, 0.05, 0.10, 0.20):
                out.append(sum(series(tf, mode, param, slip=sl)))
            print(f"    {lbl:<12}" + "".join(f"{x:>10.1f}" for x in out))


if __name__ == "__main__":
    main()

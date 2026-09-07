"""
E-155 — CHOOSING THE EXIT ON RISK, NOT ON POINTS ALONE.

E-154 laid out the trade the exit makes:

    M1  give 0.25   288.6 pts   maxDD  3.0 pts (GBP18)   longest losing run 10
    M1  atr 3       324.1 pts   maxDD 10.3 pts (GBP60)   longest losing run 19

More points, and a drawdown that is the ENTIRE ACCOUNT. E-081 says 0.01 lots is
the floor and cannot be made smaller, so a GBP60 account cannot buy its way out
of that with size. On a funded account the same drawdown is a rounding error.
The exit is therefore not one decision - it is one decision per account.

This file adds the exit Veer actually described - "tp levels are not always hit
its best to take our peak and get out" - as a STALL EXIT: if the trade has not
made a new best in N bars, the move is over, take what is there. And it selects
on a RISK-ADJUSTED criterion (points per unit of drawdown, and points subject to
a drawdown cap) rather than on points, then checks the choice on unseen data.
"""
from __future__ import annotations
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, trail_level, trail_apply, cost_scale
from liq_m1 import load, GBP
from sweep_winrate import pivots
import combined as C

TODAY = 7.38
GBP_PT = TODAY * GBP
_C = {}


def prep(tf):
    if tf not in _C:
        s, SP = load(tf)
        A = watr(s, 14)
        va = sorted(x for x in A[100:] if x)
        cs = cost_scale(SP, A)   # E-173: one PRICE on every clock - never re-derived per timeframe
        cand = [c for c in C.candidates(s, A, cs, SP, {C.SWEEP}) if c[1] == C.SWEEP]
        _C[tf] = (s, SP, A, cs, cand)
    return _C[tf]


def trade(s, A, j, d, entry, sl, mode, param, stall=0, hold=240):
    a = A[j] if A[j] else 1.0
    peak, last_new = entry, j
    for k in range(j, min(j + hold, len(s))):
        if (s.l[k] <= sl) if d > 0 else (s.h[k] >= sl):
            return sl, k
        if k == j:
            continue
        p2 = max(peak, s.h[k]) if d > 0 else min(peak, s.l[k])
        if d * (p2 - peak) > 0:
            last_new = k
        peak = p2
        # the stall: the move has stopped making new ground, so take it
        if stall and k - last_new >= stall and d * (s.c[k] - entry) > 0:
            return s.c[k], k
        nsl = (trail_level(entry, sl, peak, s.c[k], d, param) if mode == "give"
               else trail_apply(sl, peak - d * param * a, s.c[k], d))
        if nsl is None:
            return s.c[k], k
        sl = nsl
    kk = min(j + hold, len(s) - 1)
    return s.c[kk], kk


def book(tf, mode, param, stall=0, subset=None, cooldown=5):
    s, SP, A, cs, cand = prep(tf)
    out, busy = [], -1
    for (j, _, d, entry, sl0) in cand:
        if j <= busy:
            continue
        if subset and not (subset[0] <= j < subset[1]):
            continue
        px, kk = trade(s, A, j, d, entry, sl0, mode, param, stall)
        out.append(d * ((px - d * SP[kk] * cs / 2.0) - entry))
        busy = kk + cooldown
    return out


def m(r):
    eq = peak = dd = 0.0
    run = worst = 0
    for x in r:
        eq += x; peak = max(peak, eq); dd = max(dd, peak - eq)
        run = run + 1 if x <= 0 else 0
        worst = max(worst, run)
    n = len(r); tot = sum(r)
    return dict(n=n, pts=tot, per=tot / n, dd=dd, run=worst,
                win=100.0 * sum(1 for x in r if x > 0) / n,
                t=(tot / n) / (statistics.pstdev(r) / n ** 0.5),
                ppd=tot / dd if dd > 0 else float("inf"))


MENU = ([("give", g, 0) for g in (0.25, 0.40, 0.60, 0.80)]
        + [("atr", a, 0) for a in (1.0, 1.5, 2.0, 3.0)]
        + [("atr", a, st) for a in (1.5, 2.0, 3.0) for st in (5, 10, 20, 40)]
        + [("give", 0.60, st) for st in (10, 20)])


def main():
    for tf in ("M1", "M5"):
        s, _, _, _, _ = prep(tf)
        half = len(s) // 2
        print("=" * 104)
        print(f"  E-155 — {tf}: the sweep's exit chosen on RISK. "
              f"1 point = GBP{GBP_PT:.2f} at 0.01 lots, today's gold.")
        print("=" * 104)
        print(f"  {'exit':<18}{'n':>6}{'win%':>7}{'points':>9}{'/trade':>9}"
              f"{'t':>7}{'maxDD':>8}{'DD GBP':>9}{'run':>5}{'pts/DD':>8}")
        rows = []
        for (mode, param, stall) in MENU:
            r = book(tf, mode, param, stall)
            if len(r) < 100:
                continue
            st = m(r)
            lbl = f"{mode} {param:g}" + (f" stall {stall}" if stall else "")
            rows.append((st["ppd"], lbl, mode, param, stall, st))
        rows.sort(reverse=True)
        for (_, lbl, mode, param, stall, st) in rows:
            print(f"  {lbl:<18}{st['n']:>6}{st['win']:>6.1f}%{st['pts']:>9.1f}"
                  f"{st['per']:>+9.4f}{st['t']:>7.2f}{st['dd']:>8.1f}"
                  f"{st['dd']*GBP_PT:>9.0f}{st['run']:>5}{st['ppd']:>8.1f}")

        # --- the honest selection: pick on the first half, judge on the second
        print(f"\n  SELECTION — chosen on the 1st half, judged on the 2nd it never saw")
        for crit, name in ((lambda st: st["ppd"], "points per unit of drawdown"),
                           (lambda st: st["pts"], "points alone"),
                           (lambda st: st["pts"] if st["dd"] * GBP_PT <= 20 else -1e9,
                            "most points with drawdown under GBP20")):
            cands = []
            for (mode, param, stall) in MENU:
                r = book(tf, mode, param, stall, subset=(0, half))
                if len(r) >= 100:
                    cands.append((crit(m(r)), mode, param, stall))
            if not cands:
                continue
            cands.sort(reverse=True)
            _, mode, param, stall = cands[0]
            lbl = f"{mode} {param:g}" + (f" stall {stall}" if stall else "")
            r2 = book(tf, mode, param, stall, subset=(half, len(s)))
            sh = book(tf, "give", 0.25, 0, subset=(half, len(s)))
            a, b = m(r2), m(sh)
            print(f"    by {name:<34} -> {lbl}")
            print(f"       unseen: {a['pts']:>7.1f} pts  {a['per']:+.4f}/tr  "
                  f"DD {a['dd']:.1f} (GBP{a['dd']*GBP_PT:.0f})  {a['win']:.1f}% win  run {a['run']}")
            print(f"       shipped give 0.25: {b['pts']:>7.1f} pts  {b['per']:+.4f}/tr  "
                  f"DD {b['dd']:.1f} (GBP{b['dd']*GBP_PT:.0f})  {b['win']:.1f}% win  run {b['run']}")
        print()


if __name__ == "__main__":
    main()

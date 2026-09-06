"""
E-150 — EACH SIGNAL ITS OWN EXIT.

Veer: "perfect everything all signals each to their own analysis and execution
tp so everything".

Right, and it has never been tested. Every signal here shares ONE exit - a 25%
give-back - because that is what won on the SWEEP (E-137). The other three
inherited it without ever being asked. They are different trades:

    SWEEP           fades a level. The move it catches is a reversal, and
                    reversals stall - a tight give-back should suit it.
    BREAK+RETEST    trades WITH a break. That is momentum, and momentum runs -
                    a tight give-back may be cutting it off at the knees.
    OB DETECTION    enters at the birth of a move with no confirmation at all,
                    so it should have the widest spread of outcomes.
    OB RETURN       enters into a pullback, which is a reversal again.

So: hold the ENTRY, the STOP and the RISK CAP fixed, and let each source pick
its own exit from the same menu that E-137 used. If they all land on 25% then
one rule was right all along and this file says so. If they do not, the shipped
system has been leaving money on three of its four signals.

Judged on POINTS, not R (E-074), and the winner has to survive an out-of-sample
split before it is allowed to change anything - a per-signal exit is four times
the opportunity to overfit.
"""
from __future__ import annotations
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr
from liq_m1 import load, GBP
import combined as C

TODAY = 7.38
GBP_PT = TODAY * GBP
BPD = {"M1": 1440, "M5": 288, "M15": 96}


def exit_variant(s, j, d, entry, sl, mode, param, hold=240):
    """One trade, one exit rule. Returns (exit price, exit bar)."""
    peak = entry
    for k in range(j, min(j + hold, len(s))):
        if (s.l[k] <= sl) if d > 0 else (s.h[k] >= sl):
            return sl, k
        if k == j:
            continue
        peak = max(peak, s.h[k]) if d > 0 else min(peak, s.l[k])
        up = d * (peak - entry)
        c = None
        if mode == "give" and up > 0:
            c = entry + d * up * (1.0 - param)
        elif mode == "atr":
            c = peak - d * param
        if c is not None:
            # E-151. The trail is computed from THIS bar's extreme, so it can
            # only be placed once this bar has closed. A stop on the wrong side
            # of the market cannot be placed: for a long, a sell-stop above the
            # close does not exist. If the rule wants a level price has already
            # left behind, the honest fill is a market exit at the close - NOT
            # the peak. Without this clamp the trail books the previous bar's
            # favourable extreme, and the tighter the trail the more often it
            # does, which manufactures a monotone preference for tightness.
            if d * (c - s.c[k]) >= 0:
                return s.c[k], k
            sl = max(sl, c) if d > 0 else min(sl, c)
        elif mode == "fixed":
            tp = entry + d * param * abs(entry - sl)
            if (s.h[k] >= tp) if d > 0 else (s.l[k] <= tp):
                return tp, k
    kk = min(j + hold, len(s) - 1)
    return s.c[kk], kk


def book(tf, src, mode, param, subset=None, cooldown=5):
    s, SP = load(tf)
    A = watr(s, 14)
    va = sorted(x for x in A[100:] if x)
    cs = 0.11 / (statistics.median(SP) / va[len(va) // 2])
    cand = [c for c in C.candidates(s, A, cs, SP, {src}) if c[1] == src]
    out, busy = [], -1
    for (j, _, d, entry, sl0) in cand:
        if j <= busy:
            continue
        if subset and not (subset[0] <= j < subset[1]):
            continue
        a = A[j] if A[j] else 1.0
        p = param * a if mode == "atr" else param
        px_out, kk = exit_variant(s, j, d, entry, sl0, mode, p)
        out.append(d * ((px_out - d * SP[kk] * cs / 2.0) - entry))
        busy = kk + cooldown
    return out


def main():
    MENU = [("give", 0.15), ("give", 0.25), ("give", 0.40), ("give", 0.60),
            ("atr", 1.0), ("atr", 2.0), ("atr", 3.0),
            ("fixed", 1.5), ("fixed", 2.0), ("fixed", 3.0)]
    for tf in ("M1", "M5"):
        s, _ = load(tf)
        n = len(s)
        print("=" * 96)
        print(f"  E-150 — {tf}: does each signal want a DIFFERENT exit?")
        print("  Entry, stop and risk cap held fixed. Only the exit changes.")
        print("=" * 96)
        for src in (C.SWEEP, C.BR, C.OBD, C.OBR):
            rows = []
            for mode, param in MENU:
                r = book(tf, src, mode, param)
                if len(r) < 30:
                    continue
                rows.append((sum(r), mode, param, len(r),
                             100.0 * sum(1 for x in r if x > 0) / len(r)))
            if not rows:
                continue
            rows.sort(reverse=True)
            shipped = [x for x in rows if x[1] == "give" and x[2] == 0.25]
            sp = shipped[0][0] if shipped else 0.0
            print(f"\n  {C.NAME[src]}   (shipped: give 25% -> {sp:.1f} pts)")
            print(f"    {'exit':<16}{'n':>6}{'win%':>8}{'points':>10}{'vs shipped':>12}")
            for (p, mode, param, N, W) in rows[:4]:
                lbl = f"{mode} {param:g}" + (" <- shipped" if mode == "give"
                                             and param == 0.25 else "")
                print(f"    {lbl:<16}{N:>6}{W:>7.1f}%{p:>10.1f}{p-sp:>+12.1f}")
            best = rows[0]
            if best[1] == "give" and best[2] == 0.25:
                print("    the shipped exit already wins here")
                continue
            # A winner picked on the WHOLE sample cannot be validated on a half
            # of that same sample - the half helped choose it. So pick again on
            # the first half only, then judge that pick on the second half,
            # which the choice has never seen.
            isr = []
            for mode, param in MENU:
                r = book(tf, src, mode, param, subset=(0, n // 2))
                if len(r) >= 30:
                    isr.append((sum(r), mode, param))
            if not isr:
                continue
            isr.sort(reverse=True)
            pick = isr[0]
            print(f"    picked on 1st half: {pick[1]} {pick[2]:g}")
            b = book(tf, src, pick[1], pick[2], subset=(n // 2, n))
            sb = book(tf, src, "give", 0.25, subset=(n // 2, n))
            if b and sb:
                pb, ps = sum(b) / len(b), sum(sb) / len(sb)
                print(f"    2nd half (unseen)  pick {sum(b):.1f} pts ({pb:+.4f}/tr)"
                      f"   shipped {sum(sb):.1f} pts ({ps:+.4f}/tr)")
                same = pick[1] == best[1] and pick[2] == best[2]
                if pb > ps and same:
                    print(f"    -> ADOPT {pick[1]} {pick[2]:g}")
                elif pb > ps:
                    print(f"    -> ADOPT {pick[1]} {pick[2]:g} "
                          f"(differs from the full-sample winner {best[1]} {best[2]:g})")
                else:
                    print("    -> REJECT - does not hold out of sample")
        print()


if __name__ == "__main__":
    main()

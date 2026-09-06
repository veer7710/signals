"""
E-149 — THE COMBINED BOOK. What the chart and the EA ACTUALLY do.

Every signal in this project has been measured on its own, each with the whole
market to itself. That is not what runs. The chart holds ONE POSITION AT A TIME
and four entry types compete for it, strongest first. Three things can happen
that none of the separate tests can see:

  1. CANNIBALISATION. A weak signal takes the slot and a strong one arrives two
     bars later to find it occupied. The combined book is then WORSE than the
     sweep alone, and every separate measurement would still look fine.
  2. DILUTION. More trades at a lower average, so total points rise while
     quality falls - and a per-trade edge that thin dies to slippage.
  3. GENUINE ADDITION. The extra signals fill the gaps when the sweep is idle.

Only a joint simulation can tell these apart, so this is it. Exactly the
priority the chart uses: sweep > break+retest > order block (detection) >
order block (return), which is the order of their measured control se.

Everything else is held fixed - the same stop rule per source, the same 1.2 ATR
cap, the same 25% give-back, the same cost.
"""
from __future__ import annotations
import os, sys, statistics, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, trail_level, entry_fill
from liq_m1 import load, GBP
from sweep_winrate import pivots
from orderblock import blocks

TODAY = 7.38
GBP_PT = TODAY * GBP
BPD = {"M1": 1440, "M5": 288, "M15": 96}
SWEEP, BR, OBD, OBR = 1, 2, 3, 4
NAME = {SWEEP: "SWEEP", BR: "BREAK+RETEST", OBD: "OB detection", OBR: "OB return"}


def candidates(s, A, cs, SP, use, pk=5, sweep_atr=0.10, wick=0.6460,
               brk=0.10, tol=0.20, wait=60, buf=0.30, cap=1.2, obLen=3):
    """Every entry any enabled signal would ever want, as
    (bar, source, dir, entry, stop). The scheduler decides which get taken."""
    out = []

    if SWEEP in use or BR in use:
        for (kb, px, side) in pivots(s, pk):
            a = A[kb]
            if not a or a <= 0:
                continue
            # ---- sweep: taken by a WICK, traded back through
            if SWEEP in use:
                t = -side
                need = px + side * sweep_atr * a
                sw, ext = None, None
                for k in range(kb + 1, min(kb + 120, len(s))):
                    if (s.h[k] >= need) if side > 0 else (s.l[k] <= need):
                        sw, ext = k, (s.h[k] if side > 0 else s.l[k])
                        break
                if sw is not None:
                    rng = s.h[sw] - s.l[sw]
                    if (abs(s.c[sw] - s.o[sw]) / rng if rng > 0 else 1.0) <= wick:
                        j = None
                        for k in range(sw + 1, min(sw + 120, len(s))):
                            if (s.h[k] >= px) if t > 0 else (s.l[k] <= px):
                                j = k
                                break
                            ext = max(ext, s.h[k]) if side > 0 else min(ext, s.l[k])
                        if j is not None:
                            sl = ext - t * buf * a
                            # E-165. The sweep bar is a WICK - it closes back
                            # through the level - so on ~75% of setups this bar
                            # OPENS past the level and no stop could still be
                            # resting there. Book the open, which is what you
                            # would really get. Booking the level made a random
                            # walk pay +0.0226 a trade at t = 5.
                            fill = entry_fill(px, s.o[j], t)
                            if 0 < abs(px - sl) <= cap * a:
                                out.append((j, SWEEP, t,
                                            fill + t * SP[j] * cs / 2.0, sl))
            # ---- break + retest: taken by a CLOSE, traded with the break
            if BR in use:
                d = side
                bb = None
                for k in range(kb + 1, min(kb + wait, len(s))):
                    if (s.c[k] > px + brk * a) if d > 0 else (s.c[k] < px - brk * a):
                        bb = k
                        break
                if bb is not None:
                    rt = None
                    for k in range(bb + 1, min(bb + wait, len(s))):
                        if (s.c[k] < px - tol * a) if d > 0 else (s.c[k] > px + tol * a):
                            break
                        touched = (s.l[k] <= px + tol * a) if d > 0 else (s.h[k] >= px - tol * a)
                        held = (s.c[k] > px) if d > 0 else (s.c[k] < px)
                        if touched and held:
                            rt = k
                            break
                    if rt is not None:
                        trig = s.h[rt] if d > 0 else s.l[rt]
                        sl = (s.l[rt] if d > 0 else s.h[rt]) - d * buf * a
                        if 0 < abs(trig - sl) <= cap * a:
                            j = None
                            for k in range(rt + 1, min(rt + wait, len(s))):
                                if (s.h[k] >= trig) if d > 0 else (s.l[k] <= trig):
                                    j = k
                                    break
                                if (s.c[k] < px - tol * a) if d > 0 else (s.c[k] > px + tol * a):
                                    break
                            if j is not None:
                                out.append((j, BR, d, trig + d * SP[j] * cs / 2.0, sl))

    if OBD in use or OBR in use:
        for (kb, top, bot, d) in blocks(s, obLen, 0.0, True):
            a = A[kb]
            if not a or a <= 0:
                continue
            far = bot if d > 0 else top
            sl = far - d * buf * a
            if OBD in use:
                e = s.c[kb] + d * SP[kb] * cs / 2.0
                if 0 < abs(e - sl) <= cap * a:
                    out.append((kb, OBD, d, e, sl))
            if OBR in use:
                lvl = top if d > 0 else bot
                if 0 < abs(lvl - sl) <= cap * a:
                    j = None
                    for k in range(kb, min(kb + 240, len(s))):
                        if (s.l[k] <= lvl) if d > 0 else (s.h[k] >= lvl):
                            j = k
                            break
                    if j is not None:
                        out.append((j, OBR, d, lvl + d * SP[j] * cs / 2.0, sl))
    # bar first, then priority - exactly how the chart resolves a tie
    out.sort(key=lambda x: (x[0], x[1]))
    return out


def simulate(s, SP, A, cs, cand, give=0.25, hold=240, cooldown=5, slip=0.0):
    """ONE POSITION AT A TIME. This is the whole point of the file."""
    out, busy = [], -1
    for (j, src, d, entry, sl0) in cand:
        if j <= busy:
            continue
        sl = sl0
        peak = entry
        px_out, kk = None, None
        for k in range(j, min(j + hold, len(s))):
            if (s.l[k] <= sl) if d > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k
                break
            if k == j:
                continue
            peak = max(peak, s.h[k]) if d > 0 else min(peak, s.l[k])
            # E-151: one trail, in engine.py. None = exit at this close.
            nsl = trail_level(entry, sl, peak, s.c[k], d, give)
            if nsl is None:
                px_out, kk = s.c[k], k
                break
            sl = nsl
        if px_out is None:
            kk = min(j + hold, len(s) - 1)
            px_out = s.c[kk]
        out.append((d * ((px_out - d * SP[kk] * cs / 2.0) - entry) - slip, src))
        busy = kk + cooldown
    return out


def st(r):
    if not r:
        return (0, 0.0, 0.0, 0.0, 0.0)
    p = sum(x[0] for x in r)
    eq = peak = mdd = 0.0
    for x, _ in r:
        eq += x
        peak = max(peak, eq)
        mdd = max(mdd, peak - eq)
    return (len(r), 100.0 * sum(1 for x in r if x[0] > 0) / len(r), p, p / len(r), mdd)


def main():
    for tf in ("M1", "M5"):
        s, SP = load(tf)
        A = watr(s, 14)
        va = sorted(x for x in A[100:] if x)
        cs = 0.11 / (statistics.median(SP) / va[len(va) // 2])
        n = len(s)
        days = n / BPD[tf]
        print("=" * 94)
        print(f"  E-149 — {tf}: ONE POSITION, four signals competing for it")
        print("=" * 94)
        print(f"  {'enabled':<34}{'n':>6}{'/day':>7}{'win%':>7}{'points':>9}"
              f"{'per trade':>12}{'maxDD GBP':>11}")
        print("  " + "-" * 86)
        COMBOS = [({SWEEP}, "SWEEP alone"),
                  ({SWEEP, BR}, "SWEEP + break/retest"),
                  ({SWEEP, OBD}, "SWEEP + OB detection"),
                  ({SWEEP, BR, OBD}, "SWEEP + B/R + OB detection"),
                  ({SWEEP, BR, OBD, OBR}, "ALL FOUR (what ships)"),
                  ({OBD}, "OB detection alone"),
                  ({OBR}, "OB return alone")]
        keep = {}
        for use, lbl in COMBOS:
            c = candidates(s, A, cs, SP, use)
            r = simulate(s, SP, A, cs, c)
            if len(r) < 20:
                continue
            N, W, P, PT, DD = st(r)
            print(f"  {lbl:<34}{N:>6}{N/days:>7.1f}{W:>6.1f}%{P:>9.1f}"
                  f"{PT:>+12.4f}{DD*GBP_PT:>11.2f}")
            keep[lbl] = r
        full = keep.get("ALL FOUR (what ships)")
        if full:
            print("\n  inside the combined book, who actually got the slot:")
            for src in (SWEEP, BR, OBD, OBR):
                b = [x for x in full if x[1] == src]
                if b:
                    p = sum(x[0] for x in b)
                    print(f"    {NAME[src]:<16}{len(b):>6} trades  {p:>7.1f} pts  "
                          f"{p/len(b):+.4f}/trade  "
                          f"{100.0*sum(1 for x in b if x[0]>0)/len(b):.1f}% win")
            print("\n  slippage on the combined book:")
            for sl in (0.02, 0.05):
                c = candidates(s, A, cs, SP, {SWEEP, BR, OBD, OBR})
                r = simulate(s, SP, A, cs, c, slip=sl)
                print(f"    {sl:.2f} pts: {sum(x[0] for x in r):>8.1f} points")
        print()


if __name__ == "__main__":
    main()

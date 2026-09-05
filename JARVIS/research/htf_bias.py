"""
E-133 — HIGHER TIMEFRAME FOR CONTEXT, LOW TIMEFRAME FOR THE ENTRY.

Veer, and this is the architecture, not a suggestion:

  "we trade m1 m5 m15 and m3 maybe, we simply LOOK AT higher timeframes we
   don't trade them... if h1 shows that there may be a new trend direction
   then we enter on a lower tf for perfect entry, or if h4 shows something
   due to strategy again enter perfect entry lower timeframe"

System A today takes its direction from the M1 SuperTrend. That is a 7-bar
band on a 1-minute chart - it is the fastest possible read of direction and it
has no idea what the hour is doing. This tests whether the hour and the
four-hour know something the minute does not.

WHAT IS TESTED, all with the SAME M1 entry, stop, trail and ceiling so the only
variable is where the DIRECTION comes from:

   A  M1 direction only                      the shipped system, 97.1 pts
   B  M1 AND H1 must agree
   C  M1 AND H4 must agree
   D  M1 AND H1 AND H4 must agree
   E  H1 direction only, M1 ignored
   F  H4 direction only, M1 ignored
   G  M15 AND M1                             a nearer clock, as a control on
                                             "higher is better"

THE RULE THAT DECIDES IT (CLAUDE.md): a filter earns its place only if the
trades it REFUSES are worse than the ones it ALLOWS. So every variant reports
both books - what it took, and what it threw away. A filter that removes trades
of the same quality is a cost with no benefit, and this project has shipped
that mistake before.

AND THE GRADE QUESTION, which is Veer's other ask - "make sure ea treats each
trade according to the analysis done behind it". If HTF agreement is real, then
the NUMBER of clocks agreeing should predict outcome. That is a monotonicity
test: grade 1 (M1 only) < grade 2 (M1+H1) < grade 3 (M1+H1+H4). If the ladder
is not monotone, grading is decoration and the EA must not size on it.

NO LOOKAHEAD: an H1 bar is only usable once it has CLOSED. A SuperTrend value
computed on the H1 bar containing minute i is not knowable at minute i, so
every HTF read is taken from the LAST CLOSED HTF bar - which is what the EA can
actually see. Getting this wrong is how HTF filters "work" in backtests and
fail live.
"""
from __future__ import annotations
import os, sys, statistics, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, resample
from liq_m1 import load, GBP
from supertrend_rescue import st_state
from st_context_liq_entry import swings

TODAY = 7.38


def htf_dir_map(s1, factor, stlen=7, stmult=1.2):
    """SuperTrend direction from a resampled series, mapped back to M1 bars.

    THE HONEST PART: aggregated bar k covers M1 bars [k*factor, (k+1)*factor).
    Its SuperTrend value is only known once it CLOSES, so it may be used from
    M1 bar (k+1)*factor onward - never inside its own window. Off-by-one here
    is a genuine look-ahead and it flatters HTF filters enormously.
    """
    h = resample(s1, factor)
    d, _, _ = st_state(h, stlen, stmult)
    out = [0] * len(s1)
    for k in range(len(h)):
        start = (k + 1) * factor          # first M1 bar that can see this close
        end = min(len(s1), start + factor)
        if start >= len(s1):
            break
        v = d[k] if d[k] is not None else 0
        for i in range(start, end):
            out[i] = v
    return out


def main():
    s1, SP1 = load("M1")
    A1 = watr(s1, 14)
    va = sorted(x for x in A1[100:] if x)
    med_a = va[len(va) // 2]
    cs = 0.11 / (statistics.median(SP1) / med_a)
    d1, fu1, fl1 = st_state(s1, 7, 1.2)
    days = len(s1) / 1440

    print("=" * 100)
    print("  E-133 — does the HOUR know something the MINUTE does not?")
    print(f"  {len(s1):,} real M1 bars. Same entry, stop, trail and ceiling")
    print("  throughout - the ONLY variable is where direction comes from.")
    print("=" * 100)

    print("\n  building higher-timeframe direction maps (last CLOSED bar only)...")
    dM15 = htf_dir_map(s1, 15)
    dH1  = htf_dir_map(s1, 60)
    dH4  = htf_dir_map(s1, 240)
    print("  done.")

    zl = sorted((i0, px, dr) for (i0, px, dr) in swings(s1, 5))

    def agrees(dmap, i, side):
        # Pine/engine convention: -1 = bullish, +1 = bearish
        v = dmap[i]
        return (v == -1 and side > 0) or (v == 1 and side < 0)

    def run(cond):
        """Returns (taken, refused). Both books, always - a filter is only
        worth having if what it refuses is worse than what it allows."""
        took, ref, busy = [], [], -1
        for (i0, px, dr) in zl:
            if i0 <= busy:
                continue
            a = A1[i0]
            if not a or a <= 0:
                continue
            side = 1 if dr == -1 else -1
            lvl = px - side * 0.5 * a
            j = None
            for k in range(i0 + 1, min(i0 + 61, len(s1))):
                if (side == 1 and s1.l[k] <= lvl) or (side == -1 and s1.h[k] >= lvl):
                    j = k
                    break
            if j is None:
                continue
            sp = SP1[j] * cs
            entry = lvl + side * sp / 2.0
            sl = entry - side * 4.0 * a
            out = None
            for k in range(j, min(j + 240, len(s1))):
                if (side > 0 and s1.l[k] <= sl) or (side < 0 and s1.h[k] >= sl):
                    out, kk = sl, k
                    break
                band = fl1[k] if side > 0 else fu1[k]
                if band is not None:
                    sl = max(sl, band) if side > 0 else min(sl, band)
            if out is None:
                kk = min(j + 240, len(s1) - 1)
                out = s1.c[kk]
            pts = side * ((out - side * SP1[kk] * cs / 2.0) - entry)
            if cond(i0, side):
                took.append(pts)
                busy = kk + 120
            else:
                ref.append(pts)
        return took, ref

    VARIANTS = [
        ("A  M1 only            (shipped)", lambda i, s: agrees(d1, i, s)),
        ("B  M1 + H1",   lambda i, s: agrees(d1, i, s) and agrees(dH1, i, s)),
        ("C  M1 + H4",   lambda i, s: agrees(d1, i, s) and agrees(dH4, i, s)),
        ("D  M1 + H1 + H4", lambda i, s: agrees(d1, i, s) and agrees(dH1, i, s)
                                          and agrees(dH4, i, s)),
        ("E  H1 only",   lambda i, s: agrees(dH1, i, s)),
        ("F  H4 only",   lambda i, s: agrees(dH4, i, s)),
        ("G  M1 + M15",  lambda i, s: agrees(d1, i, s) and agrees(dM15, i, s)),
    ]

    print(f"\n  {'variant':<34}{'n':>6}{'/day':>6}{'win%':>7}{'points':>9}"
          f"{'per trade':>11}   | {'REFUSED n':>9}{'pts':>9}{'per trade':>11}")
    print("  " + "-" * 106)
    results = {}
    for name, cond in VARIANTS:
        took, ref = run(cond)
        if len(took) < 30:
            print(f"  {name:<34}{len(took):>6}   too few trades")
            continue
        p = sum(took)
        w = 100.0 * sum(1 for x in took if x > 0) / len(took)
        rp = sum(ref) if ref else 0.0
        rpt = rp / len(ref) if ref else 0.0
        print(f"  {name:<34}{len(took):>6}{len(took)/days:>6.1f}{w:>6.1f}%"
              f"{p:>9.1f}{p/len(took):>11.4f}   | {len(ref):>9}{rp:>9.1f}{rpt:>11.4f}")
        results[name] = (p, len(took), took, ref)

    # ---- THE GRADE LADDER -------------------------------------------------
    # Veer: "make sure ea treats each trade according to the analysis behind
    # it". That only works if more agreement really does mean a better trade.
    print("\n  " + "=" * 96)
    print("  THE GRADE LADDER — does MORE agreement mean a BETTER trade?")
    print("  If this is not monotone, grading is decoration and the EA must")
    print("  not size on it.")
    print("  " + "-" * 96)
    buckets = {0: [], 1: [], 2: []}
    _, _, _, _ = 0, 0, 0, 0
    took_all, _ = run(lambda i, s: agrees(d1, i, s))
    # re-run capturing the grade of each taken trade
    grades = []
    busy = -1
    for (i0, px, dr) in zl:
        if i0 <= busy:
            continue
        a = A1[i0]
        if not a or a <= 0:
            continue
        side = 1 if dr == -1 else -1
        if not agrees(d1, i0, side):
            continue
        lvl = px - side * 0.5 * a
        j = None
        for k in range(i0 + 1, min(i0 + 61, len(s1))):
            if (side == 1 and s1.l[k] <= lvl) or (side == -1 and s1.h[k] >= lvl):
                j = k
                break
        if j is None:
            continue
        sp = SP1[j] * cs
        entry = lvl + side * sp / 2.0
        sl = entry - side * 4.0 * a
        out = None
        for k in range(j, min(j + 240, len(s1))):
            if (side > 0 and s1.l[k] <= sl) or (side < 0 and s1.h[k] >= sl):
                out, kk = sl, k
                break
            band = fl1[k] if side > 0 else fu1[k]
            if band is not None:
                sl = max(sl, band) if side > 0 else min(sl, band)
        if out is None:
            kk = min(j + 240, len(s1) - 1)
            out = s1.c[kk]
        pts = side * ((out - side * SP1[kk] * cs / 2.0) - entry)
        g = (1 if agrees(dH1, i0, side) else 0) + (1 if agrees(dH4, i0, side) else 0)
        buckets[g].append(pts)
        grades.append((g, pts))
        busy = kk + 120

    print(f"  {'grade':<32}{'n':>6}{'win%':>8}{'points':>10}{'per trade':>12}")
    for g in (0, 1, 2):
        b = buckets[g]
        if not b:
            continue
        lbl = {0: "M1 alone, HTF disagrees", 1: "M1 + one higher clock",
               2: "M1 + H1 + H4 all agree"}[g]
        w = 100.0 * sum(1 for x in b if x > 0) / len(b)
        print(f"  {g}  {lbl:<29}{len(b):>6}{w:>7.1f}%{sum(b):>10.1f}"
              f"{sum(b)/len(b):>12.4f}")
    mono = [sum(buckets[g]) / len(buckets[g]) for g in (0, 1, 2) if buckets[g]]
    print(f"  MONOTONE: {'YES' if mono == sorted(mono) else 'NO'}"
          f"   ({' -> '.join(f'{x:+.4f}' for x in mono)})")


if __name__ == "__main__":
    main()


# ===========================================================================
#  E-133b — HIS ACTUAL WORDING, which is not what the table above tested.
#
#  "if h1 shows that there may be a NEW TREND DIRECTION then we enter on a
#   lower tf for perfect entry"
#
#  The table above used the HTF's STATE - is the hour bullish right now. He
#  described the hour CHANGING - a fresh H1 turn, and then a window in which
#  low-timeframe entries in that new direction are taken. Those are different
#  claims and the second one is his, so it gets tested on its own terms.
#
#  A window is required, because "a new direction" is an event with a shelf
#  life. If the effect is real it should be STRONGEST just after the turn and
#  decay - and that decay is itself the evidence. A flat profile across every
#  window means the flip is not doing anything and we are back to state.
# ===========================================================================
def fresh():
    s1, SP1 = load("M1")
    A1 = watr(s1, 14)
    va = sorted(x for x in A1[100:] if x)
    med_a = va[len(va) // 2]
    cs = 0.11 / (statistics.median(SP1) / med_a)
    d1, fu1, fl1 = st_state(s1, 7, 1.2)
    days = len(s1) / 1440
    zl = sorted((i0, px, dr) for (i0, px, dr) in swings(s1, 5))

    print("\n" + "=" * 100)
    print("  E-133b — a FRESH higher-timeframe turn, then enter on M1")
    print("=" * 100)

    for factor, label in ((60, "H1"), (240, "H4")):
        h = resample(s1, factor)
        dh, _, _ = st_state(h, 7, 1.2)
        # bars_since[i] = M1 bars since the last CLOSED HTF bar that flipped.
        # Same honesty rule as above: a flip on aggregated bar k is only known
        # from M1 bar (k+1)*factor.
        since = [10 ** 9] * len(s1)
        newdir = [0] * len(s1)
        last_flip_i, last_dir = None, 0
        for k in range(1, len(h)):
            if dh[k] is None or dh[k - 1] is None:
                continue
            if dh[k] != dh[k - 1]:
                last_flip_i = (k + 1) * factor
                last_dir = dh[k]
            if last_flip_i is None:
                continue
            start = (k + 1) * factor
            end = min(len(s1), start + factor)
            if start >= len(s1):
                break
            for i in range(start, end):
                since[i] = i - last_flip_i
                newdir[i] = last_dir

        print(f"\n  {label} turn -> M1 entry in the new direction")
        print(f"  {'window after the turn':<28}{'n':>6}{'/day':>7}{'win%':>7}"
              f"{'points':>9}{'per trade':>11}")
        print("  " + "-" * 68)

        for win, wl in ((60, "within 1 hour"), (180, "within 3 hours"),
                        (360, "within 6 hours"), (720, "within 12 hours"),
                        (10 ** 9, "any time (= state)")):
            took, busy = [], -1
            for (i0, px, dr) in zl:
                if i0 <= busy:
                    continue
                a = A1[i0]
                if not a or a <= 0:
                    continue
                side = 1 if dr == -1 else -1
                if since[i0] > win:
                    continue
                v = newdir[i0]
                if not ((v == -1 and side > 0) or (v == 1 and side < 0)):
                    continue
                lvl = px - side * 0.5 * a
                j = None
                for k in range(i0 + 1, min(i0 + 61, len(s1))):
                    if (side == 1 and s1.l[k] <= lvl) or (side == -1 and s1.h[k] >= lvl):
                        j = k
                        break
                if j is None:
                    continue
                sp = SP1[j] * cs
                entry = lvl + side * sp / 2.0
                sl = entry - side * 4.0 * a
                out = None
                for k in range(j, min(j + 240, len(s1))):
                    if (side > 0 and s1.l[k] <= sl) or (side < 0 and s1.h[k] >= sl):
                        out, kk = sl, k
                        break
                    band = fl1[k] if side > 0 else fu1[k]
                    if band is not None:
                        sl = max(sl, band) if side > 0 else min(sl, band)
                if out is None:
                    kk = min(j + 240, len(s1) - 1)
                    out = s1.c[kk]
                took.append(side * ((out - side * SP1[kk] * cs / 2.0) - entry))
                busy = kk + 120
            if len(took) < 25:
                print(f"  {wl:<28}{len(took):>6}   too few trades")
                continue
            p = sum(took)
            w = 100.0 * sum(1 for x in took if x > 0) / len(took)
            print(f"  {wl:<28}{len(took):>6}{len(took)/days:>7.2f}{w:>6.1f}%"
                  f"{p:>9.1f}{p/len(took):>11.4f}")

    print("\n  reference — the shipped M1-only system: 981 trades, 9.0/day, "
          "57.1% win, 97.1 points, +0.0990/trade")


if __name__ == "__main__":
    fresh()


# ===========================================================================
#  E-133c — THE INVERSE, because E-133b falsified the idea in a specific
#  direction and that direction is itself usable.
#
#  E-133b: the FRESHER the higher-timeframe turn, the WORSE the entry.
#      H1  within 1h +0.0753  ->  3h +0.1176  ->  6h +0.1131  -> any +0.1010
#      H4  within 1h -0.0212  ->  3h +0.0039  ->  6h +0.0754  -> any +0.0886
#  H4 is outright NEGATIVE in the first hour after its own turn, at a 41.8%
#  win rate. The freshest higher-timeframe signal is the worst moment to act
#  on it, and it recovers monotonically as the turn ages.
#
#  That is mechanically sensible: immediately after an H4 band flips, nobody
#  yet knows whether the flip holds. That is the definition of the fakeout
#  Veer wants filtered out, and it says the fakeout risk is CONCENTRATED and
#  TIMEABLE rather than distributed.
#
#  So the rule to test is not "enter on a fresh HTF turn". It is "STAND ASIDE
#  for a while after one". Same system, one line added.
# ===========================================================================
def inverse():
    s1, SP1 = load("M1")
    A1 = watr(s1, 14)
    va = sorted(x for x in A1[100:] if x)
    med_a = va[len(va) // 2]
    cs = 0.11 / (statistics.median(SP1) / med_a)
    d1, fu1, fl1 = st_state(s1, 7, 1.2)
    days = len(s1) / 1440
    zl = sorted((i0, px, dr) for (i0, px, dr) in swings(s1, 5))

    def since_map(factor):
        h = resample(s1, factor)
        dh, _, _ = st_state(h, 7, 1.2)
        since = [10 ** 9] * len(s1)
        last = None
        for k in range(1, len(h)):
            if dh[k] is None or dh[k - 1] is None:
                continue
            if dh[k] != dh[k - 1]:
                last = (k + 1) * factor
            if last is None:
                continue
            start = (k + 1) * factor
            end = min(len(s1), start + factor)
            if start >= len(s1):
                break
            for i in range(start, end):
                since[i] = i - last
        return since

    sH1 = since_map(60)
    sH4 = since_map(240)

    def run(skip_h1, skip_h4):
        took, ref, busy = [], [], -1
        for (i0, px, dr) in zl:
            if i0 <= busy:
                continue
            a = A1[i0]
            if not a or a <= 0:
                continue
            side = 1 if dr == -1 else -1
            v = d1[i0]
            if not ((v == -1 and side > 0) or (v == 1 and side < 0)):
                continue
            lvl = px - side * 0.5 * a
            j = None
            for k in range(i0 + 1, min(i0 + 61, len(s1))):
                if (side == 1 and s1.l[k] <= lvl) or (side == -1 and s1.h[k] >= lvl):
                    j = k
                    break
            if j is None:
                continue
            sp = SP1[j] * cs
            entry = lvl + side * sp / 2.0
            sl = entry - side * 4.0 * a
            out = None
            for k in range(j, min(j + 240, len(s1))):
                if (side > 0 and s1.l[k] <= sl) or (side < 0 and s1.h[k] >= sl):
                    out, kk = sl, k
                    break
                band = fl1[k] if side > 0 else fu1[k]
                if band is not None:
                    sl = max(sl, band) if side > 0 else min(sl, band)
            if out is None:
                kk = min(j + 240, len(s1) - 1)
                out = s1.c[kk]
            pts = side * ((out - side * SP1[kk] * cs / 2.0) - entry)
            blocked = (sH1[i0] < skip_h1) or (sH4[i0] < skip_h4)
            if blocked:
                ref.append(pts)
            else:
                took.append(pts)
                busy = kk + 120
        return took, ref

    print("\n" + "=" * 100)
    print("  E-133c — STAND ASIDE for a while after a higher-timeframe turn")
    print("  The rule a filter must pass (CLAUDE.md): what it REFUSES has to be")
    print("  worse than what it ALLOWS. Both books are printed.")
    print("=" * 100)
    print(f"  {'skip after H1 / H4 turn':<30}{'n':>6}{'/day':>7}{'win%':>7}"
          f"{'points':>9}{'per trade':>11}  | {'REFUSED':>8}{'pts':>8}{'per trade':>11}")
    print("  " + "-" * 98)
    for (h1, h4, lbl) in ((0, 0, "nothing (shipped)"),
                          (0, 60, "H4 only, 1 hour"),
                          (0, 180, "H4 only, 3 hours"),
                          (0, 360, "H4 only, 6 hours"),
                          (60, 180, "H1 1h + H4 3h"),
                          (180, 180, "H1 3h + H4 3h"),
                          (60, 360, "H1 1h + H4 6h")):
        took, ref = run(h1, h4)
        if len(took) < 30:
            continue
        p = sum(took)
        w = 100.0 * sum(1 for x in took if x > 0) / len(took)
        rp = sum(ref) if ref else 0.0
        rpt = rp / len(ref) if ref else 0.0
        print(f"  {lbl:<30}{len(took):>6}{len(took)/days:>7.2f}{w:>6.1f}%"
              f"{p:>9.1f}{p/len(took):>11.4f}  | {len(ref):>8}{rp:>8.1f}{rpt:>11.4f}")


if __name__ == "__main__":
    inverse()

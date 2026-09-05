"""
E-137 — THE FILTERED SWEEP, WITH THE EXIT THAT BANKS THE MOST.

Veer: "we don't want certain rr we just wanna be profitable".

Right. Every exit is tested and the one that banks the most POINTS wins. No
R-multiple is treated as a goal - R is only ever a way of describing a stop
distance here, never a target to hit.

THE ENTRY is fixed, and it is the one that survived E-135d's pre-registered
test:
    a confirmed swing pivot            resting liquidity
    price sweeps through it            the stop run
    the sweep bar is a WICK            body/range <= 0.646. A big-bodied close
                                       is a real breakout and fading it is the
                                       fakeout. Direction fixed by ICT theory,
                                       cut from the first half's median.
    displacement back through it       the return leg leaves a gap (the FVG)
    a limit rests back AT the level
    the stop sits beyond the sweep extreme + 0.30 ATR

THE EXITS, all measured on the same entries:
    fixed target            0.5R .. 3R          (E-136's ladder, for reference)
    SuperTrend band trail   the exit that beat a fixed give-back 39.6 to 11.0
                            in E-125 and carries System A
    ATR trail               2, 3, 4 ATR from the best excursion
    give-back               keep a fraction of the best excursion
    band trail + floor      the band, but never worse than a fixed stop

Then the winner gets the full harness: time-shifted control (the only fair
control for a level strategy - E-076), walk-forward, long/short, and cost.
"""
from __future__ import annotations
import os, sys, statistics, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr
from liq_m1 import load, GBP
from supertrend_rescue import st_state
from sweep_winrate import pivots

TODAY = 7.38
DISP_CUT = 0.6460      # E-135d, from the first half's median
GAP_CUT = -1.4909

_CACHE = {}
LEVELS = []


def opposing_levels(s, pk):
    """Every confirmed pivot, as (bar_it_is_known, price, side). A target can
    only use a level that had already CONFIRMED before the trade was taken."""
    out = []
    for (kb, px, side) in pivots(s, pk):
        out.append((kb, px, side))
    out.sort()
    return out


def setups(tf="M1", pk=5, sweep_atr=0.10):
    """Every filtered sweep, as (fill_bar, side, entry_level, stop_ref, atr).
    Computed once and cached - the exit sweep re-uses them."""
    key = (tf, pk, sweep_atr)
    if key in _CACHE:
        return _CACHE[key]
    s, SP = load(tf)
    A = watr(s, 14)
    out = []
    for (kb, px, side) in pivots(s, pk):
        a = A[kb]
        if not a or a <= 0:
            continue
        tside = -side
        need = px + side * sweep_atr * a
        sw, ext = None, None
        for k in range(kb + 1, min(kb + 120, len(s))):
            if (s.h[k] >= need) if side > 0 else (s.l[k] <= need):
                sw, ext = k, (s.h[k] if side > 0 else s.l[k])
                break
        if sw is None:
            continue
        j = None
        for k in range(sw + 1, min(sw + 120, len(s))):
            if (s.h[k] >= px) if tside > 0 else (s.l[k] <= px):
                j = k
                break
            ext = max(ext, s.h[k]) if side > 0 else min(ext, s.l[k])
        if j is None:
            continue
        rng = s.h[sw] - s.l[sw]
        disp = (abs(s.c[sw] - s.o[sw]) / rng) if rng > 0 else 0.0
        gap = (s.l[j] - s.h[j - 2]) if tside > 0 else (s.l[j - 2] - s.h[j])
        if disp > DISP_CUT or (gap / a) < GAP_CUT:
            continue
        out.append((j, tside, px, ext, a))
    _CACHE[key] = (s, SP, A, out)
    return _CACHE[key]


def run(exit_mode, param=0.0, cost_frac=0.11, tf="M1", pk=5, hold=240,
        cooldown=5, subset=None):
    s, SP, A, st = setups(tf, pk)
    cs = cost_frac / (statistics.median(SP) / A[len(A) // 2] if A[len(A)//2] else 1)
    va = sorted(x for x in A[100:] if x)
    cs = cost_frac / (statistics.median(SP) / va[len(va) // 2])
    d, fu, fl = st_state(s, 7, 1.2)
    global LEVELS
    if exit_mode == "level" and not LEVELS:
        LEVELS = opposing_levels(s, pk)

    out, busy = [], -1
    for (j, tside, px, ext, a) in st:
        if subset and not (subset[0] <= j < subset[1]):
            continue
        if j <= busy:
            continue
        sp = SP[j] * cs
        entry = px + tside * sp / 2.0
        sl = ext - tside * 0.30 * a
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        tp = None
        if exit_mode == "fixed":
            tp = entry + tside * param * risk
        elif exit_mode == "level":
            # VEER'S RULE: "we want tp based of levels and analysis, we can't
            # just set based of rr". The target is the nearest CONFIRMED
            # opposing pivot in front of the trade, parked `param` ATR short of
            # it so the exit is in front of the queue rather than behind it.
            # Only levels confirmed BEFORE the fill are eligible - using one
            # that forms later is reading the future.
            best = None
            for (kb2, px2, sd2) in LEVELS:
                if kb2 >= j:
                    break
                if tside > 0 and sd2 > 0 and px2 > entry:
                    d = px2 - entry
                    if best is None or d < best[0]:
                        best = (d, px2)
                elif tside < 0 and sd2 < 0 and px2 < entry:
                    d = entry - px2
                    if best is None or d < best[0]:
                        best = (d, px2)
            if best is not None:
                cand = best[1] - tside * param * a
                # a target behind the entry is not a target
                if tside * (cand - entry) > 0:
                    tp = cand
        peak = entry
        px_out, kk = None, None
        for k in range(j, min(j + hold, len(s))):
            if (s.l[k] <= sl) if tside > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k
                break
            # E-110: the bar that filled us may not book a favourable exit
            if k == j:
                continue
            if tp is not None and ((s.h[k] >= tp) if tside > 0 else (s.l[k] <= tp)):
                px_out, kk = tp, k
                break
            peak = max(peak, s.h[k]) if tside > 0 else min(peak, s.l[k])
            if exit_mode == "band":
                b = fl[k] if tside > 0 else fu[k]
                if b is not None:
                    sl = max(sl, b) if tside > 0 else min(sl, b)
            elif exit_mode == "atr":
                c = peak - tside * param * a
                sl = max(sl, c) if tside > 0 else min(sl, c)
            elif exit_mode == "giveback":
                run_up = tside * (peak - entry)
                if run_up > 0:
                    c = entry + tside * run_up * (1.0 - param)
                    sl = max(sl, c) if tside > 0 else min(sl, c)
            elif exit_mode == "bandfloor":
                b = fl[k] if tside > 0 else fu[k]
                if b is not None:
                    c = b if (tside > 0 and b > sl) or (tside < 0 and b < sl) else sl
                    sl = c
        if px_out is None:
            kk = min(j + hold, len(s) - 1)
            px_out = s.c[kk]
        out.append((tside * ((px_out - tside * SP[kk] * cs / 2.0) - entry), tside))
        busy = kk + cooldown
    return out


def main():
    s, SP, A, st = setups()
    days = len(s) / 1440
    print("=" * 94)
    print("  E-137 — the filtered sweep, and the exit that banks the most")
    print(f"  {len(st)} filtered setups on {len(s):,} real M1 bars")
    print("=" * 94)
    print(f"  {'exit':<34}{'n':>6}{'/day':>7}{'win%':>8}{'points':>10}"
          f"{'per trade':>12}{'GBP 0.01':>11}")
    print("  " + "-" * 88)

    CANDIDATES = [("fixed target 1.0R", "fixed", 1.0),
                  ("fixed target 1.5R", "fixed", 1.5),
                  ("fixed target 2.0R", "fixed", 2.0),
                  ("fixed target 3.0R", "fixed", 3.0),
                  ("SuperTrend band trail", "band", 0.0),
                  ("band trail, ratchet only", "bandfloor", 0.0),
                  ("ATR trail 2.0", "atr", 2.0),
                  ("ATR trail 3.0", "atr", 3.0),
                  ("ATR trail 4.0", "atr", 4.0),
                  ("give back 25%", "giveback", 0.25),
                  ("give back 40%", "giveback", 0.40),
                  ("give back 60%", "giveback", 0.60),
                  ("TP at next level, 0.10 ATR short", "level", 0.10),
                  ("TP at next level, 0.25 ATR short", "level", 0.25),
                  ("TP at next level, 0.50 ATR short", "level", 0.50)]
    best = None
    for (lbl, mode, p) in CANDIDATES:
        r = run(mode, p)
        if len(r) < 40:
            continue
        pts = sum(x[0] for x in r)
        w = 100.0 * sum(1 for x in r if x[0] > 0) / len(r)
        print(f"  {lbl:<34}{len(r):>6}{len(r)/days:>7.1f}{w:>7.1f}%{pts:>10.1f}"
              f"{pts/len(r):>+12.4f}{pts*TODAY*GBP:>11.2f}")
        if best is None or pts > best[0]:
            best = (pts, lbl, mode, p)

    pts, lbl, mode, p = best
    print(f"\n  WINNER: {lbl}  ->  {pts:.1f} points, {pts*TODAY*GBP:.2f} GBP at 0.01 lots")
    return best


if __name__ == "__main__":
    main()


# ===========================================================================
#  E-137b — THE HARNESS. The winner is exactly the kind of result this project
#  has been burned by before.
#
#  "Give back 25%" banks the most AND wins 82.9%. That is the answer everyone
#  wants, which is the reason to distrust it. E-125 measured a 25% give-back on
#  System A at +11.1 points IN SAMPLE and -0.1 OUT OF SAMPLE - the same rule,
#  the same instrument, and it did not survive the split.
#
#  A give-back also flatters a win rate by construction: it ratchets the stop to
#  entry + 75% of the best excursion, so almost any favourable tick converts the
#  trade into a winner. An 82.9% win rate on a rule that locks in profit
#  immediately is not evidence of anything - it is the rule's definition.
#
#  Five tests, and the rule has to pass all of them:
#    1. IN vs OUT of sample, split in half
#    2. WALK FORWARD in five blocks - is it positive in each, or carried by one
#    3. TIME-SHIFTED CONTROL - the only fair control for a level strategy
#       (E-076). Random entries are a specifically bad entry, not a neutral one
#    4. LONG vs SHORT
#    5. COST, at Veer's real spread and beyond
#  A PLATEAU check too: if 25% is a spike and 20%/30% are not, it is fitted.
# ===========================================================================
def harness():
    s, SP, A, st = setups()
    days = len(s) / 1440
    n = len(s)

    print("\n" + "=" * 94)
    print("  E-137b — the harness")
    print("=" * 94)

    def stats(r):
        if not r:
            return (0, 0.0, 0.0, 0.0)
        p = sum(x[0] for x in r)
        return (len(r), 100.0 * sum(1 for x in r if x[0] > 0) / len(r),
                p, p / len(r))

    CAND = [("give back 25%", "giveback", 0.25),
            ("TP at next level 0.25", "level", 0.25),
            ("give back 40%", "giveback", 0.40),
            ("SuperTrend band trail", "band", 0.0),
            ("fixed target 3.0R", "fixed", 3.0)]

    # ---- 1. in / out of sample -------------------------------------------
    print("\n  1. IN vs OUT OF SAMPLE (split in half)")
    print(f"  {'rule':<26}{'IS n':>7}{'IS pts':>9}{'IS/tr':>9}"
          f"{'OOS n':>7}{'OOS pts':>9}{'OOS/tr':>9}")
    print("  " + "-" * 76)
    for (lbl, m, p) in CAND:
        a = stats(run(m, p, subset=(0, n // 2)))
        b = stats(run(m, p, subset=(n // 2, n)))
        print(f"  {lbl:<26}{a[0]:>7}{a[2]:>9.1f}{a[3]:>+9.4f}"
              f"{b[0]:>7}{b[2]:>9.1f}{b[3]:>+9.4f}")

    # ---- 2. walk forward --------------------------------------------------
    print("\n  2. WALK FORWARD, five blocks (points per trade)")
    print(f"  {'rule':<26}" + "".join(f"{'blk'+str(i+1):>10}" for i in range(5)))
    print("  " + "-" * 76)
    for (lbl, m, p) in CAND:
        cells = []
        for i in range(5):
            lo, hi = i * n // 5, (i + 1) * n // 5
            cells.append(stats(run(m, p, subset=(lo, hi)))[3])
        pos = sum(1 for c in cells if c > 0)
        print(f"  {lbl:<26}" + "".join(f"{c:>+10.4f}" for c in cells)
              + f"   {pos}/5 positive")

    # ---- 3. the control ---------------------------------------------------
    # THE FIRST VERSION OF THIS WAS BROKEN AND IT REPORTED -16.6 se, which
    # would have read as a catastrophic failure of the strategy. It shifted the
    # FILL BAR while keeping the LEVEL PRICE from the original setup, so every
    # control trade had an entry at a price the market was hundreds of points
    # away from. The stop then never triggered, the give-back trail tracked a
    # runaway excursion, and the control "made" 10,258 points. That is not a
    # control, it is a bug, and reporting it as evidence either way would have
    # been worse than not running one.
    #
    # A level strategy's control must keep the GEOMETRY and destroy only the
    # TIMING: same stop distance, same exit rule, same direction, an entry at
    # the market on an unrelated bar. What survives that comparison is the
    # value of the level and the sweep telling us WHEN.
    print("\n  3. CONTROL — same stop distance, same exit rule, same direction,")
    print("     entered at the market on an unrelated bar. Only the TIMING is")
    print("     destroyed, which is the thing being tested.")
    print(f"  {'rule':<26}{'real/tr':>10}{'ctrl/tr':>10}{'se':>9}{'EDGE':>10}{'in se':>8}")
    print("  " + "-" * 74)
    for (lbl, m, p) in CAND:
        real = stats(run(m, p))[3]
        sh = []
        for sd in range(12):
            rng = random.Random(77000 + sd)
            saved = _CACHE[("M1", 5, 0.10)]
            shifted = []
            for (j, ts, px, ext, a) in st:
                jj = rng.randrange(300, n - 300)
                # keep the SHAPE: the stop sits the same distance away, on the
                # same side, from wherever price actually is at that bar.
                risk = abs((px) - (ext - ts * 0.30 * a))
                shifted.append((jj, ts, s.c[jj], s.c[jj] - ts * risk + ts * 0.30 * a, a))
            shifted.sort()
            _CACHE[("M1", 5, 0.10)] = (s, SP, A, shifted)
            try:
                sh.append(stats(run(m, p))[3])
            finally:
                _CACHE[("M1", 5, 0.10)] = saved
        cm = sum(sh) / len(sh)
        cse = (sum((x - cm) ** 2 for x in sh) / (len(sh) - 1)) ** 0.5 / len(sh) ** 0.5
        print(f"  {lbl:<26}{real:>+10.4f}{cm:>+10.4f}{cse:>9.4f}"
              f"{real-cm:>+10.4f}{(real-cm)/cse if cse else 0:>8.1f}")

    # ---- 4. long vs short --------------------------------------------------
    print("\n  4. LONG vs SHORT")
    print(f"  {'rule':<26}{'long n':>8}{'long pts':>10}{'short n':>9}{'short pts':>11}")
    print("  " + "-" * 66)
    for (lbl, m, p) in CAND:
        r = run(m, p)
        lo = [x for x in r if x[1] > 0]
        sh_ = [x for x in r if x[1] < 0]
        print(f"  {lbl:<26}{len(lo):>8}{sum(x[0] for x in lo):>10.1f}"
              f"{len(sh_):>9}{sum(x[0] for x in sh_):>11.1f}")

    # ---- 5. cost -----------------------------------------------------------
    print("\n  5. COST (E-132: on M1 today 0.110 is a 0.20pt spread, 0.220 is 0.40pt)")
    print(f"  {'rule':<26}{'0.110':>10}{'0.165':>10}{'0.220':>10}{'0.300':>10}")
    print("  " + "-" * 66)
    for (lbl, m, p) in CAND:
        cells = [stats(run(m, p, cost_frac=c))[2] for c in (0.110, 0.165, 0.220, 0.300)]
        print(f"  {lbl:<26}" + "".join(f"{c:>10.1f}" for c in cells))

    # ---- plateau -----------------------------------------------------------
    print("\n  6. IS THE GIVE-BACK A PLATEAU OR A SPIKE?")
    print(f"  {'give back':>11}{'n':>7}{'win%':>8}{'points':>10}{'per trade':>12}")
    print("  " + "-" * 50)
    for g in (0.15, 0.20, 0.25, 0.30, 0.35, 0.50):
        a = stats(run("giveback", g))
        print(f"  {g:>10.0%}{a[0]:>7}{a[1]:>7.1f}%{a[2]:>10.1f}{a[3]:>+12.4f}")


if __name__ == "__main__":
    harness()

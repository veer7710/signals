"""
E-132 — PING PONG, RETESTED ON REAL M1/M5 TICKS.

Veer: "sometimes m1 or m5 plays ping ping w price lets catch that if u can".

E-100 already rejected ping-pong. That rejection DOES NOT ANSWER HIS QUESTION
and must not be quoted at him, for three reasons that are all in E-100's own
header:

  1. "GOLD 15m and 1h only. There is no M1/M5 data in this repository."
     He asked about M1 and M5. E-100 never saw either.
  2. It charged spread 0.46, taken off his terminal by eye. DATA_QUALITY.md
     later measured the real spread from 18.8M ticks at 0.229 - E-100 charged
     DOUBLE the real cost on a strategy whose whole thesis is small moves.
  3. It predates the E-110 fill-convention fix.

So the honest position is that ping-pong is UNTESTED at the timeframe he means,
under a cost assumption that was wrong by 2x. This retests it.

THE RULE, kept as close to E-100's as the new data allows so the two are
comparable:
    a range built from CLOSED bars only: hi/lo of the last `look` bars,
    width between min_w and max_w ATR, at least `min_touch` touches of EACH
    edge. Buy the lower edge targeting the upper, and the mirror.

THREE EXITS are reported, because "target the other edge" is the concept's own
rule and the two exits the shipped stack uses are the fair comparison:
    opposite edge      the concept's own rule
    2R target
    SuperTrend trail   the exit E-125 found actually works

E-110 IS ENFORCED: an entry taken on bar i is never allowed to book bar i's
favourable extreme. Every exit scan starts at i+1.

CONTROL: the same range detections, time-shifted. Random entries are not a fair
control for a level strategy - E-076 established that and it cost this project
six invalidated "validations" to learn.
"""
from __future__ import annotations
import os, sys, statistics, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr
from liq_m1 import load, GBP
from supertrend_rescue import st_state

TODAY = 7.38


def ranges(s, A, look, min_w, max_w, tol_f, min_touch):
    """Every bar at which a ping-pong range is live and price is AT an edge.
    Returns (bar, side, target, stop_ref) using CLOSED bars only."""
    out = []
    for i in range(max(200, look), len(s) - 2):
        a = A[i]
        if not a or a <= 0:
            continue
        w = s.h[i - look + 1:i + 1]
        v = s.l[i - look + 1:i + 1]
        hi, lo = max(w), min(v)
        width = hi - lo
        if width <= 0 or not (min_w * a <= width <= max_w * a):
            continue
        tol = tol_f * width
        th = sum(1 for x in w if x >= hi - tol)
        tl = sum(1 for x in v if x <= lo + tol)
        if th < min_touch or tl < min_touch:
            continue
        if s.c[i] <= lo + tol:
            out.append((i, 1, hi - tol, lo))
        elif s.c[i] >= hi - tol:
            out.append((i, -1, lo + tol, hi))
    return out


def run(s, SP, A, cs, sigs, exit_mode, stop_a, fu=None, fl=None,
        hold=240, cooldown=0):
    """Enter at the NEXT bar's open. E-110: the exit scan starts at the bar
    AFTER the entry bar, so a bar can never fill us and pay us."""
    tot, busy = [], -1
    for (i, side, tgt, edge) in sigs:
        if i <= busy:
            continue
        j = i + 1
        if j >= len(s) - 2:
            continue
        a = A[i]
        sp = SP[j] * cs
        entry = s.o[j] + side * sp / 2.0
        sl = entry - side * stop_a * a
        tp = tgt if exit_mode == "edge" else (
            entry + side * stop_a * a * 2.0 if exit_mode == "2R" else None)
        out, kk = None, None
        for k in range(j + 1, min(j + hold, len(s))):
            hit_sl = (side > 0 and s.l[k] <= sl) or (side < 0 and s.h[k] >= sl)
            hit_tp = tp is not None and (
                (side > 0 and s.h[k] >= tp) or (side < 0 and s.l[k] <= tp))
            # a bar that touches both is scored as the LOSS. Ties lose.
            if hit_sl:
                out, kk = sl, k
                break
            if hit_tp:
                out, kk = tp, k
                break
            if exit_mode == "trail" and fu is not None:
                band = fl[k] if side > 0 else fu[k]
                if band is not None:
                    sl = max(sl, band) if side > 0 else min(sl, band)
        if out is None:
            kk = min(j + hold, len(s) - 1)
            out = s.c[kk]
        tot.append(side * ((out - side * SP[kk] * cs / 2.0) - entry))
        busy = kk + cooldown
    return tot


def main():
    print("=" * 96)
    print("  E-132 — PING PONG on real M1/M5 ticks (E-100 tested 15m/1h only,")
    print("          at spread 0.46 when the measured spread is 0.229)")
    print("=" * 96)

    for tf in ("M1", "M5"):
        s, SP = load(tf)
        A = watr(s, 14)
        va = sorted(x for x in A[100:] if x)
        med_a = va[len(va) // 2]
        cs = 0.11 / (statistics.median(SP) / med_a)
        d, fu, fl = st_state(s, 7, 1.2)
        bars_per_day = 1440 if tf == "M1" else 288
        days = len(s) / bars_per_day

        print(f"\n  {tf}: {len(s):,} bars, {days:.0f} days, "
              f"median ATR {med_a:.3f}, median spread {statistics.median(SP):.3f}")
        print(f"  {'look':>5} {'width ATR':>11} {'exit':>7} {'n':>6} {'/day':>6} "
              f"{'win%':>7} {'points':>9} {'£ 0.01':>9}")
        print("  " + "-" * 74)

        best = None
        for look in (20, 40, 60):
            for (lo_w, hi_w) in ((1.5, 6.0), (2.0, 8.0)):
                sigs = ranges(s, A, look, lo_w, hi_w, 0.15, 2)
                if len(sigs) < 40:
                    continue
                for mode in ("edge", "2R", "trail"):
                    r = run(s, SP, A, cs, sigs, mode, 0.60, fu, fl)
                    if len(r) < 30:
                        continue
                    p = sum(r)
                    w = 100.0 * sum(1 for x in r if x > 0) / len(r)
                    print(f"  {look:>5} {lo_w:>5.1f}-{hi_w:<5.1f} {mode:>7} "
                          f"{len(r):>6} {len(r)/days:>6.1f} {w:>6.1f}% "
                          f"{p:>9.1f} {p*TODAY*GBP:>9.2f}")
                    if best is None or p > best[0]:
                        best = (p, look, lo_w, hi_w, mode, len(r), sigs)

        if best is None:
            print("  no cell produced enough trades")
            continue

        p, look, lo_w, hi_w, mode, n, sigs = best
        print(f"\n  BEST {tf}: look {look}, width {lo_w}-{hi_w} ATR, exit "
              f"'{mode}' -> {p:.1f} points over {n} trades")

        # THE CONTROL: the same range detections, offered at unrelated times.
        sh = []
        for sd in range(14):
            rng = random.Random(52000 + sd)
            off = rng.randrange(500, max(1000, len(s) - 1000))
            zz = sorted([(((i + off) % (len(s) - 500)) + 200, side, tgt, edge)
                         for (i, side, tgt, edge) in sigs])
            r = run(s, SP, A, cs, zz, mode, 0.60, fu, fl)
            if len(r) > 30:
                sh.append(sum(r))
        if len(sh) < 3:
            print("  control did not produce enough shifts")
            continue
        cm = sum(sh) / len(sh)
        cse = (sum((x - cm) ** 2 for x in sh) / (len(sh) - 1)) ** 0.5 / len(sh) ** 0.5
        se = (p - cm) / cse if cse > 0 else 0.0
        print(f"  time-shifted control ({len(sh)} shifts): {cm:.1f} points, "
              f"se of the mean {cse:.1f}")
        print(f"  EDGE {p - cm:+.1f} points = {se:.1f} control se")
        print(f"  VERDICT: {'worth pursuing' if se >= 2.0 else 'NOT SEPARATED FROM THE CONTROL'}")


if __name__ == "__main__":
    main()


# ===========================================================================
#  E-132b — THE HARSH PASS.
#
#  The first table looks good and that is exactly why it cannot be trusted yet.
#  Three things in it are warnings, not results:
#
#   1. The TIME-SHIFTED CONTROL made +234.1 points on M1. A control that
#      profitable means most of the headline number is NOT the range - it is
#      whatever the trail does when you run it 124 times a day. The edge over
#      control is the only part that belongs to ping-pong.
#   2. 13,569 trades at 124/day. E-073: a result whose n far exceeds the number
#      of independent decisions behind it is wrong until re-counted.
#   3. The concept's OWN rule - "target the opposite edge" - wins 17.1% of the
#      time. If price actually ping-ponged, that number would be HIGH. A 17%
#      win rate on "reach the other side" says the ranges BREAK, and the money
#      is being made by the trail riding the break. That is the opposite of the
#      strategy Veer described.
#
#  So: cost sensitivity (at 124 trades/day cost is the whole game), an
#  out-of-sample split, and the decisive test - the same trail fired at a
#  MATCHED FREQUENCY with no range condition at all. If that matches the real
#  thing, the range is decoration.
# ===========================================================================
def harsh():
    print("\n" + "=" * 96)
    print("  E-132b — THE HARSH PASS on ping pong")
    print("=" * 96)

    for tf, look, lo_w, hi_w in (("M1", 20, 2.0, 8.0), ("M5", 20, 2.0, 8.0)):
        s, SP = load(tf)
        A = watr(s, 14)
        va = sorted(x for x in A[100:] if x)
        med_a = va[len(va) // 2]
        base = statistics.median(SP) / med_a
        d, fu, fl = st_state(s, 7, 1.2)
        bars_per_day = 1440 if tf == "M1" else 288
        days = len(s) / bars_per_day
        sigs = ranges(s, A, look, lo_w, hi_w, 0.15, 2)

        print(f"\n  ---------- {tf}  look {look}, width {lo_w}-{hi_w} ATR ----------")

        # ---- 1. does price actually reach the opposite edge? ---------------
        for mode, label in (("edge", "its OWN rule: target the opposite edge"),
                            ("trail", "SuperTrend trail")):
            r = run(s, SP, A, med_a and 0.11 / base, sigs, mode, 0.60, fu, fl)
            w = 100.0 * sum(1 for x in r if x > 0) / len(r)
            print(f"  {label:<42} n {len(r):>6}  win {w:>5.1f}%  "
                  f"{sum(r):>8.1f} pts")

        # ---- 2. cost sensitivity -------------------------------------------
        print(f"\n  cost sensitivity (spread as a fraction of ATR), trail exit:")
        for frac in (0.11, 0.17, 0.25, 0.40):
            r = run(s, SP, A, frac / base, sigs, "trail", 0.60, fu, fl)
            print(f"    spread/ATR {frac:.2f}   {sum(r):>8.1f} pts   "
                  f"{sum(r)/len(r):+.4f}/trade   {sum(r)*TODAY*GBP:>9.2f} GBP")

        cs = 0.11 / base

        # ---- 3. out of sample ----------------------------------------------
        half = len(s) // 2
        a_sig = [x for x in sigs if x[0] < half]
        b_sig = [x for x in sigs if x[0] >= half]
        ra = run(s, SP, A, cs, a_sig, "trail", 0.60, fu, fl)
        rb = run(s, SP, A, cs, b_sig, "trail", 0.60, fu, fl)
        print(f"\n  first half  {sum(ra):>8.1f} pts over {len(ra):>6} trades  "
              f"{sum(ra)/len(ra):+.4f}/trade")
        print(f"  second half {sum(rb):>8.1f} pts over {len(rb):>6} trades  "
              f"{sum(rb)/len(rb):+.4f}/trade")

        # ---- 4. THE DECISIVE TEST -----------------------------------------
        # Same trail, same stop, same cost, fired every Nth bar with NO range
        # condition whatsoever. N is chosen to match the real trade count, so
        # the two are compared at the same frequency and the same cost load.
        real = run(s, SP, A, cs, sigs, "trail", 0.60, fu, fl)
        step = max(1, len(s) // max(1, len(real)))
        print(f"\n  THE DECISIVE TEST — is the range doing anything?")
        print(f"    ping-pong entries        {sum(real):>8.1f} pts over "
              f"{len(real):>6} trades  {sum(real)/len(real):+.4f}/trade")
        flat = []
        for off in range(0, 5):
            blind = [(i, 1 if (i // step) % 2 == 0 else -1, None, None)
                     for i in range(200 + off, len(s) - 3, step)]
            rr = run(s, SP, A, cs, blind, "trail", 0.60, fu, fl)
            if rr:
                flat.append(sum(rr) / len(rr))
        if flat:
            m = sum(flat) / len(flat)
            sd = (sum((x - m) ** 2 for x in flat) / max(1, len(flat) - 1)) ** 0.5
            print(f"    every {step}th bar, no range  {m:+.4f}/trade  "
                  f"(sd {sd:.4f} over {len(flat)} offsets)")
            print(f"    the range adds           {sum(real)/len(real) - m:+.4f}/trade")


if __name__ == "__main__":
    harsh()

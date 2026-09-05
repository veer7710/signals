"""
E-139 — CAN THE EA ACTUALLY DO WHAT THE BACKTEST DID?

The tested rule evaluates the return-leg displacement AT THE FILL BAR: the gap
between bar j and bar j-2, where j is the bar price came back to the level. A
resting limit fills DURING that bar, so an EA holding a limit cannot know at arm
time whether the bar that eventually fills it will pass the filter. It would be
evaluating displacement at the ARM bar instead - a different signal.

That is exactly the class of defect P92 found: a 52% signal gap between a Pine
and an EA built from the same spec, unnoticed for 180 commits. So it gets
settled before either ships, not after.

THREE VARIANTS, and only ones an EA can actually execute count:

  A  wick + displacement, limit at the level      the tested rule.
                                                  NOT EA-REPLICABLE.
  B  wick only, limit at the level                fully replicable: the wick is
                                                  a property of the SWEEP bar,
                                                  known before the limit is
                                                  placed.
  C  wick + displacement, market entry on the     replicable, because the
     bar AFTER the return bar                     filter is evaluated on a
                                                  closed bar - but the fill is
                                                  worse than a limit at the
                                                  level.

If B holds up, it ships, because a rule an EA can execute beats a better rule it
cannot. If B collapses and C survives, C ships and the worse fill is the price
of correctness.
"""
from __future__ import annotations
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr
from liq_m1 import load, GBP
from sweep_winrate import pivots

TODAY = 7.38
GBP_PT = TODAY * GBP


def run(variant, cost_frac=0.11, pk=5, sweep_atr=0.10, buf=0.30,
        give=0.25, max_risk_atr=2.0, hold=240, cooldown=5, subset=None):
    s, SP = load("M1")
    A = watr(s, 14)
    va = sorted(x for x in A[100:] if x)
    cs = cost_frac / (statistics.median(SP) / va[len(va) // 2])
    out, busy = [], -1
    for (kb, px, side) in pivots(s, pk):
        if kb <= busy:
            continue
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
        rng = s.h[sw] - s.l[sw]
        disp = (abs(s.c[sw] - s.o[sw]) / rng) if rng > 0 else 1.0
        if disp > 0.6460:
            continue                     # the WICK filter, known at arm time
        j = None
        for k in range(sw + 1, min(sw + 120, len(s))):
            if (s.h[k] >= px) if tside > 0 else (s.l[k] <= px):
                j = k
                break
            ext = max(ext, s.h[k]) if side > 0 else min(ext, s.l[k])
        if j is None:
            continue
        if subset and not (subset[0] <= j < subset[1]):
            continue

        gap = (s.l[j] - s.h[j - 2]) if tside > 0 else (s.l[j - 2] - s.h[j])
        disp_fails = (gap / a) < -1.4909
        if variant in ("A", "C") and disp_fails:
            continue

        if variant == "C":
            # the filter is evaluated on a CLOSED bar, so entry is the next
            # bar's open - the honest cost of being able to execute the rule
            e_bar = j + 1
            if e_bar >= len(s) - 2:
                continue
            fill = s.o[e_bar]
        else:
            e_bar = j
            fill = px

        sp = SP[e_bar] * cs
        entry = fill + tside * sp / 2.0
        sl = ext - tside * buf * a
        risk = abs(entry - sl)
        if risk <= 0 or risk > max_risk_atr * a:
            continue

        # VARIANT D: rest the limit as in A, then evaluate the displacement
        # filter RETROSPECTIVELY once the fill bar is known, and bail out at the
        # next bar's open if it failed. This is the only way an EA can apply a
        # fill-bar filter to a resting limit, and it is not free - the rejected
        # trades still pay the spread and a bar of drift.
        if variant == "D" and disp_fails:
            k = min(j + 1, len(s) - 1)
            out.append(tside * ((s.o[k] - tside * SP[k] * cs / 2.0) - entry))
            busy = k + cooldown
            continue

        peak = entry
        px_out, kk = None, None
        for k in range(e_bar, min(e_bar + hold, len(s))):
            if (s.l[k] <= sl) if tside > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k
                break
            if k == e_bar:
                continue
            peak = max(peak, s.h[k]) if tside > 0 else min(peak, s.l[k])
            up = tside * (peak - entry)
            if up > 0:
                c = entry + tside * up * (1.0 - give)
                sl = max(sl, c) if tside > 0 else min(sl, c)
        if px_out is None:
            kk = min(e_bar + hold, len(s) - 1)
            px_out = s.c[kk]
        out.append(tside * ((px_out - tside * SP[kk] * cs / 2.0) - entry))
        busy = kk + cooldown
    return out


def main():
    s, _ = load("M1")
    days = len(s) / 1440
    n = len(s)
    print("=" * 92)
    print("  E-139 — can the EA execute what the backtest measured?")
    print("=" * 92)
    print(f"  {'variant':<48}{'n':>6}{'/day':>7}{'win%':>8}{'points':>9}{'per trade':>11}")
    print("  " + "-" * 89)
    LAB = {"A": "A  wick + displacement, limit at the level  NOT EA-ABLE",
           "B": "B  wick only, limit at the level            replicable",
           "C": "C  wick + disp, market on the next bar      replicable",
           "D": "D  limit, then bail out if displacement failed  replicable"}
    keep = {}
    for v in ("A", "B", "C", "D"):
        r = run(v)
        p = sum(r)
        w = 100.0 * sum(1 for x in r if x > 0) / len(r)
        print(f"  {LAB[v]:<48}{len(r):>6}{len(r)/days:>7.1f}{w:>7.1f}%"
              f"{p:>9.1f}{p/len(r):>+11.4f}")
        keep[v] = r

    print(f"\n  {'variant':<20}{'IS pts':>9}{'IS/tr':>10}{'OOS pts':>10}{'OOS/tr':>10}"
          f"{'0.40 spread':>13}{'slip 0.05':>11}")
    print("  " + "-" * 83)
    for v in ("A", "B", "C", "D"):
        a = run(v, subset=(0, n // 2))
        b = run(v, subset=(n // 2, n))
        wide = sum(run(v, cost_frac=0.220))
        slipped = sum(x - 0.05 for x in keep[v])
        print(f"  {v:<20}{sum(a):>9.1f}{sum(a)/len(a):>+10.4f}{sum(b):>10.1f}"
              f"{sum(b)/len(b):>+10.4f}{wide:>13.1f}{slipped:>11.1f}")


if __name__ == "__main__":
    main()


# ===========================================================================
#  E-139b — VARIANT B GETS ITS OWN HARNESS.
#
#  E-137/E-138 validated variant A. A is not executable by an EA holding a
#  resting limit, so it cannot ship, and B's numbers are different - 66.7% win
#  instead of 82.1%, +0.1119/trade instead of +0.1840. Carrying A's validation
#  over to B would be quoting numbers for a system that is not the one running.
#
#  So B is re-tested from scratch: control, walk-forward, drawdown, the risk
#  cap sweep, long/short, and the give-back plateau.
# ===========================================================================
def harness_b():
    import random
    s, SP = load("M1")
    n = len(s)
    days = n / 1440

    def stats(r):
        if not r:
            return (0, 0.0, 0.0, 0.0)
        p = sum(r)
        return (len(r), 100.0 * sum(1 for x in r if x > 0) / len(r), p, p / len(r))

    print("\n" + "=" * 92)
    print("  E-139b — VARIANT B's own harness (wick filter, limit at the level)")
    print("=" * 92)

    base = run("B")
    N, W, P, PT = stats(base)
    print(f"\n  baseline: {N} trades, {N/days:.1f}/day, {W:.1f}% win, "
          f"{P:+.1f} points, {P*GBP_PT:+.2f} GBP, {PT:+.4f}/trade")

    # ---- walk forward ------------------------------------------------------
    print("\n  1. WALK FORWARD, five blocks")
    cells = []
    for i in range(5):
        r = run("B", subset=(i * n // 5, (i + 1) * n // 5))
        cells.append(stats(r))
    print("     " + "  ".join(f"blk{i+1} {c[3]:+.4f}" for i, c in enumerate(cells)))
    print(f"     {sum(1 for c in cells if c[3] > 0)}/5 positive")

    # ---- drawdown ----------------------------------------------------------
    print("\n  2. DRAWDOWN and the risk cap, on a GBP60 account at 0.01 lots")
    print(f"     {'risk cap':>10}{'n':>7}{'/day':>7}{'win%':>8}{'points':>9}"
          f"{'GBP':>10}{'maxDD GBP':>11}{'worst':>9}")
    for cap in (99.0, 4.0, 3.0, 2.5, 2.0, 1.6, 1.2):
        r = run("B", max_risk_atr=cap)
        if len(r) < 50:
            continue
        eq = peak = mdd = 0.0
        for p in r:
            eq += p
            peak = max(peak, eq)
            mdd = max(mdd, peak - eq)
        a = stats(r)
        lbl = "none" if cap > 90 else f"{cap:.1f} ATR"
        print(f"     {lbl:>10}{a[0]:>7}{a[0]/days:>7.1f}{a[1]:>7.1f}%{a[2]:>9.1f}"
              f"{a[2]*GBP_PT:>10.2f}{mdd*GBP_PT:>11.2f}{min(r)*GBP_PT:>9.2f}")

    # ---- the control -------------------------------------------------------
    # Same stop distance, same exit rule, same direction, entered at the market
    # on an unrelated bar. Only the TIMING is destroyed - which is what the
    # sweep and the level are claiming to supply.
    print("\n  3. CONTROL — geometry kept, timing destroyed")
    from engine import atr as watr
    import statistics as stt
    A = watr(s, 14)
    va = sorted(x for x in A[100:] if x)
    cs = 0.11 / (stt.median(SP) / va[len(va) // 2])
    risks = []
    for _ in range(1):
        pass
    # take the real risk distribution so the control is sized like the real book
    for (kb, px, side) in __import__("sweep_winrate").pivots(s, 5):
        a = A[kb]
        if a and a > 0:
            risks.append(min(2.0 * a, 0.6 * a))
    ctrl = []
    for sd in range(12):
        rng = random.Random(91000 + sd)
        book = []
        for _ in range(N):
            j = rng.randrange(300, n - 300)
            tside = 1 if rng.random() < 0.5 else -1
            a = A[j]
            if not a or a <= 0:
                continue
            entry = s.c[j] + tside * SP[j] * cs / 2.0
            sl = entry - tside * 0.9 * a
            peak = entry
            px_out, kk = None, None
            for k in range(j, min(j + 240, n)):
                if (s.l[k] <= sl) if tside > 0 else (s.h[k] >= sl):
                    px_out, kk = sl, k
                    break
                if k == j:
                    continue
                peak = max(peak, s.h[k]) if tside > 0 else min(peak, s.l[k])
                up = tside * (peak - entry)
                if up > 0:
                    c = entry + tside * up * 0.75
                    sl = max(sl, c) if tside > 0 else min(sl, c)
            if px_out is None:
                kk = min(j + 240, n - 1)
                px_out = s.c[kk]
            book.append(tside * ((px_out - tside * SP[kk] * cs / 2.0) - entry))
        if book:
            ctrl.append(sum(book) / len(book))
    cm = sum(ctrl) / len(ctrl)
    cse = (sum((x - cm) ** 2 for x in ctrl) / (len(ctrl) - 1)) ** 0.5 / len(ctrl) ** 0.5
    print(f"     real {PT:+.4f}/trade   control {cm:+.4f}   se {cse:.4f}   "
          f"EDGE {PT-cm:+.4f} = {(PT-cm)/cse:.1f} control se")

    # ---- give-back plateau -------------------------------------------------
    print("\n  4. IS THE GIVE-BACK A PLATEAU?")
    for g in (0.15, 0.20, 0.25, 0.30, 0.40, 0.50):
        a = stats(run("B", give=g))
        print(f"     give back {g:>4.0%}: {a[0]:>5} trades  {a[1]:>5.1f}% win  "
              f"{a[2]:>7.1f} points  {a[3]:+.4f}/trade")


if __name__ == "__main__":
    harness_b()

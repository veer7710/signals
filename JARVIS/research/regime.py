"""
E-176 — WAS E-175 A FACT ABOUT SUPERTREND, OR A FACT ABOUT JANUARY-JUNE 2018?

Veer: "ur telling me it loses on m1 when ive tested it for months seeing profit
on m1 dude what m1 is what worked for jt well".

He is describing months of his own live testing on TODAY'S gold. E-175 tested
five and a half months of gold from 1 Jan to 19 Jun 2018, when the metal
traded a range around 1300. That is the whole M1 data set in this repo. A
TREND-FOLLOWING system judged only on a rangebound half-year is being judged on
precisely the regime it is built to lose in, and I published "DISPROVEN" off it.

This file separates the two explanations. Same clock, same code, same signal -
only the REGIME changes:

    GOLD_M1_2018.json  resampled to 1h   Jan-Jun 2018,   gold ~1300, ranging
    GOLD_1h.json                          Apr 2024-Aug 2026, gold 2362 -> 4491

If SuperTrend is negative in both, E-175 stands and the sample was not the
problem. If it flips sign, then E-175 measured the sample, not the strategy,
and the honest verdict is that this project has never had the data to judge it.

Trendiness is reported alongside as the efficiency ratio - net displacement over
total path length, per 100 bars. It is not a result, it is a description of what
each sample IS, so the reader can see the two are not the same market.
"""
from __future__ import annotations
import json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Series, atr as watr, ema
from liq_m1 import load
from supertrend_rescue import st_state
from st_churn import flips

DATA = "/home/user/signals/data"


def load_plain(name):
    rows = json.load(open(f"{DATA}/{name}"))
    rows.sort(key=lambda r: r[0])
    seen, out = set(), []
    for r in rows:
        if r[0] in seen:
            continue
        seen.add(r[0])
        out.append(r)
    return Series([r[0] for r in out], [r[1] for r in out], [r[2] for r in out],
                  [r[3] for r in out], [r[4] for r in out])


def resample(s, factor):
    ts, o, h, l, c = [], [], [], [], []
    for i in range(0, len(s) - factor + 1, factor):
        ts.append(s.ts[i]); o.append(s.o[i])
        h.append(max(s.h[i:i + factor])); l.append(min(s.l[i:i + factor]))
        c.append(s.c[i + factor - 1])
    return Series(ts, o, h, l, c)


def efficiency(s, win=100):
    """Net displacement / total path, per `win` bars. 1.0 = a straight line,
    0.0 = pure noise. This is what 'trending' MEANS, quantified."""
    out = []
    for i in range(win, len(s), win):
        seg = s.c[i - win:i]
        path = sum(abs(seg[k] - seg[k - 1]) for k in range(1, len(seg)))
        if path > 0:
            out.append(abs(seg[-1] - seg[0]) / path)
    return statistics.fmean(out) if out else 0.0


def book(s, d, cost_pts=0.0):
    """Flip in, opposite flip out. Identical to E-175's decisive column."""
    fl = flips(s, d)
    out = []
    for k, (i, t) in enumerate(fl):
        if i + 1 >= len(s):
            break
        j = fl[k + 1][0] if k + 1 < len(fl) else len(s) - 1
        e, x = s.o[i + 1], s.o[min(j + 1, len(s) - 1)]
        out.append(t * (x - e) - cost_pts)
    return out


def report(label, s, note):
    d, _, _ = st_state(s, 7, 1.2)
    g = book(s, d)
    if len(g) < 30:
        print(f"  {label:<34} too few trades")
        return
    m = statistics.fmean(g)
    t = m / (statistics.pstdev(g) / len(g) ** 0.5)
    A = watr(s, 14)
    va = sorted(x for x in A[100:] if x)
    print(f"  {label:<34}{len(s):>8}{efficiency(s):>9.3f}"
          f"{va[len(va)//2]:>9.2f}{len(g):>7}{sum(g):>+10.1f}{m:>+10.3f}{t:>+7.2f}"
          f"   {note}")


def main():
    print("=" * 118)
    print("  E-176 — the same SuperTrend, the same 1-hour clock, two different"
          " golds. GROSS, no cost, no filter, no exit rules.")
    print("=" * 118)
    print(f"  {'sample':<34}{'bars':>8}{'trendy':>9}{'medATR':>9}{'n':>7}"
          f"{'gross':>10}{'/trade':>10}{'t':>7}")
    print("  " + "-" * 112)

    m1, _ = load("M1")
    report("2018 Jan-Jun, M1 -> 1h", resample(m1, 60), "the whole M1 data set")
    report("2024-2026, real 1h", load_plain("GOLD_1h.json"), "2362 -> 4491")

    print()
    g15 = load_plain("GOLD_15m.json")
    report("2026 Jun-Aug, real 15m", g15, "the most recent data there is")
    report("2018 Jan-Jun, M1 -> 15m", resample(m1, 15), "same clock, old gold")

    print()
    print("  and the 2024-2026 sample cut in half, to see if it is one lucky leg:")
    h = load_plain("GOLD_1h.json")
    half = len(h) // 2
    report("2024-2026 1h, FIRST half",
           Series(h.ts[:half], h.o[:half], h.h[:half], h.l[:half], h.c[:half]),
           "out of sample for the second")
    report("2024-2026 1h, SECOND half",
           Series(h.ts[half:], h.o[half:], h.h[half:], h.l[half:], h.c[half:]),
           "unseen by the first")





# ===========================================================================
# PART 2 — in ATR units, across clocks, and WITH the DEMA filter he runs.
#
# Two things E-175 got wrong and this part fixes:
#
#  1. POINTS ARE NOT COMPARABLE ACROSS REGIMES. 2018 gold had a median 1h ATR
#     of 2.47; 2025-26 gold has 12.14. Reporting points per trade compares a
#     move in a quiet market with a move in a violent one and calls the second
#     better for being bigger. Everything below is per trade in ATR.
#
#  2. "NO FILTER CAN FIX A NEGATIVE GROSS" IS FALSE, and it contradicts this
#     repo's own standing rule: a filter earns its place when the trades it
#     REFUSES are worse than the ones it allows. Stripping the DEMA filter
#     tested a strategy Veer does not run. So the filter goes back on and the
#     refused trades are measured separately, which is the only honest test.
# ===========================================================================
def dema_of(vals, n):
    e1 = ema(vals, n)
    e2 = ema([x if x is not None else 0.0 for x in e1], n)
    return [None if (e1[i] is None or e2[i] is None) else 2 * e1[i] - e2[i]
            for i in range(len(vals))]


def split_by_dema(s, d, dLen):
    """Flip in, opposite flip out, split by whether the DEMA slope agreed.
    In ATR units."""
    D = dema_of(s.c, dLen)
    A = watr(s, 14)
    fl = flips(s, d)
    allr, taken, refused = [], [], []
    for k, (i, t) in enumerate(fl):
        if i + 1 >= len(s):
            break
        j = fl[k + 1][0] if k + 1 < len(fl) else len(s) - 1
        a = A[i]
        if not a or a <= 0 or i < 2 or D[i] is None or D[i - 2] is None:
            continue
        r = t * (s.o[min(j + 1, len(s) - 1)] - s.o[i + 1]) / a
        allr.append(r)
        slope = D[i] - D[i - 2]
        ok = (slope >= 0) if t > 0 else (slope <= 0)
        (taken if ok else refused).append(r)
    return allr, taken, refused


def stat(r):
    if len(r) < 20:
        return None
    m = statistics.fmean(r)
    return len(r), m, m / (statistics.pstdev(r) / len(r) ** 0.5)


def part2():
    print("\n" + "=" * 120)
    print("  PART 2 — per trade in ATR (points are not comparable across"
          " regimes), and the DEMA filter judged by what it REFUSES")
    print("=" * 120)
    m1, _ = load("M1")
    h1 = load_plain("GOLD_1h.json")
    g15 = load_plain("GOLD_15m.json")
    samples = [("2018 Jan-Jun  M1", m1),
               ("2018 Jan-Jun  M1->5m", resample(m1, 5)),
               ("2018 Jan-Jun  M1->15m", resample(m1, 15)),
               ("2018 Jan-Jun  M1->1h", resample(m1, 60)),
               ("2026 Jun-Aug  real 15m", g15),
               ("2026 Jun-Aug  15m->1h", resample(g15, 4)),
               ("2024-2026     real 1h", h1),
               ("2024-2026     1h->4h", resample(h1, 4))]
    print(f"  {'sample':<26}{'n all':>7}{'ATR/trd':>9}{'t':>7}   |"
          f"{'n took':>8}{'ATR/trd':>9}{'t':>7}   |{'refused':>9}"
          f"{'ATR/trd':>9}   does the filter earn its place?")
    print("  " + "-" * 114)
    for label, s in samples:
        d, _, _ = st_state(s, 7, 1.2)
        dLen = 60 if label.endswith("M1") else 200
        allr, tk, rf = split_by_dema(s, d, dLen)
        sa, stk, srf = stat(allr), stat(tk), stat(rf)
        if not (sa and stk):
            continue
        verdict = "too few refused to say"
        if srf:
            verdict = ("YES - refused are worse" if srf[1] < stk[1]
                       else "NO - refused are BETTER")
        print(f"  {label:<26}{sa[0]:>7}{sa[1]:>+9.3f}{sa[2]:>+7.2f}   |"
              f"{stk[0]:>8}{stk[1]:>+9.3f}{stk[2]:>+7.2f}   |"
              f"{(srf[0] if srf else 0):>9}{(srf[1] if srf else 0):>+9.3f}"
              f"   {verdict}")


if __name__ == "__main__":
    main()
    part2()

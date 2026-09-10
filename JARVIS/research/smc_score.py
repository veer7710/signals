"""
E-195 — SCORE EVERY SMC / ICT / LIQUIDITY CONCEPT, WITH THE BEST-OF-N NULL.

Forty-four concepts. E-184's seventeen plus smc_library's twenty-seven.
One question each, the only one that has ever replicated in this repo:

    DOES THIS MARK THE START OF A LEG?

scored as LIFT against a TIME-SHIFTED copy of the same series - identical shape
and frequency, timing destroyed.

WHAT IS NEW HERE, AND IT IS THE WHOLE POINT.

E-194-RT killed a result of mine because I searched a 5x5 grid and quoted the
best cell as though it were a measurement. Scoring 44 concepts and quoting the
best three is the SAME MISTAKE at a larger scale: with 44 tries, several will
beat their own twin by luck.

So every concept is measured against TWO bars, not one:

  1. ITS OWN CONTROL   - lift > 1 means it beat a timing-destroyed copy of
                         itself. This is E-184's test and it is necessary.
  2. THE BEST-OF-N LINE - the 95th percentile of the MAXIMUM lift across all
                         44 concepts when NONE of them has any edge. This is
                         sufficient. A concept below this line is what the
                         best of forty coin flips looks like.

The null is exact rather than simulated by re-shuffling: under no edge, a
concept that fires `f` times catches Binomial(f, ctrl) legs, so its lift is
Binomial(f, ctrl) / (f * ctrl). Sampling that for all 44 at once and taking the
max gives the distribution of "the best score a completely empty library would
have reported". No look at the data is needed to compute it, so it cannot be
contaminated by the data.

Then the survivors are re-checked OUT OF SAMPLE (E-150): scored on the first
half, confirmed on the second. A concept that clears the best-of-N line on the
first half and does it again on the second is a finding. Nothing else is.
"""
from __future__ import annotations
import json, os, random, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, Series
from regime import load_plain, resample
from legcatch import legs, features as base_features, score
import smc_library


def all_features(s, A, V=None, other=None):
    """E-184's seventeen and smc_library's twenty-seven, in one dict."""
    F = dict(base_features(s, A, V))
    F.update(smc_library.features(s, A, V, other=other))
    return F


def best_of_n_line(rows, base, trials=20000, seed=17, pct=95):
    """The lift the best of these N concepts would report with NO edge at all.

    rows: the (name, fired, rate, ctrl, lift, avg) tuples from score().
    Under the null a concept firing f times catches Binomial(f, ctrl) legs.
    Sampling all N and taking the max, `trials` times, gives the distribution
    of the maximum. The `pct`-th percentile of it is the line.
    """
    rnd = random.Random(seed)
    live = [(f, c if c > 0 else base) for (_, f, _, c, _, _) in rows if f >= 30]
    if not live:
        return None, 0
    maxes = []
    for _ in range(trials):
        best = 0.0
        for (f, c) in live:
            # a fast Normal approximation to Binomial(f, c); f >= 30 and the
            # counts here are in the hundreds, so this is well inside its range
            sd = (f * c * (1.0 - c)) ** 0.5
            k = rnd.gauss(f * c, sd)
            lift = (k / f) / c if c > 0 else 0.0
            if lift > best:
                best = lift
        maxes.append(best)
    maxes.sort()
    return maxes[int(len(maxes) * pct / 100.0)], len(live)


def report(label, s, V=None, other=None, pv=3, minAtr=2.0, slack=3,
           quiet=False):
    A = watr(s, 14)
    lg = legs(s, A, pv=pv, minAtr=minAtr)
    F = all_features(s, A, V, other)
    rows, base, nStart = score(F, lg, len(s), slack=slack)
    line, nLive = best_of_n_line(rows, base)
    if not quiet:
        print()
        print("-" * 82)
        print(f"  {label}   {len(s)} bars   {len(lg)} legs   base {base:.3f}")
        print(f"  BEST-OF-{nLive} NULL LINE (95th pct): lift {line:.2f}"
              f"  — anything under this is what the best of {nLive} empty"
              f" concepts scores")
        print(f"  {'':28}{'fires':>7}{'/1000':>8}{'rate':>7}{'ctrl':>7}"
              f"{'LIFT':>7}")
        print("  " + "-" * 80)
        for (name, fired, rate, ctrl, lift, avg) in rows:
            if fired < 30:
                continue
            mark = "  CLEARS" if lift >= line else ""
            print(f"  {name:<28}{fired:>7}{fired / len(s) * 1000:>8.1f}"
                  f"{rate:>7.3f}{ctrl:>7.3f}{lift:>7.2f}{mark}")
    return {r[0]: r for r in rows}, line, base


def load2018(name):
    rows = sorted(json.load(open(f"/home/user/signals/data/{name}")),
                  key=lambda r: r[0])
    return Series([r[0] for r in rows], [r[1] for r in rows],
                  [r[2] for r in rows], [r[3] for r in rows],
                  [r[4] for r in rows])


def samples():
    """Every sample, each with its SMT partner where one exists.

    2018 has no second market in the repo, so SMT cannot be scored there and
    is reported as unscorable rather than as zero.
    """
    h1 = load_plain("GOLD_1h.json")
    g15 = load_plain("GOLD_15m.json")
    out = [("15m 2026", g15, load_plain("US500_15m.json"), 3),
           ("30m 2026", resample(g15, 2), resample(load_plain("US500_15m.json"), 2), 3),
           ("1h 24-26", h1, load_plain("US500_1h.json"), 3),
           ("4h 24-26", resample(h1, 4), resample(load_plain("US500_1h.json"), 4), 4)]
    for f, lb in (("GOLD_M1_2018.json", "M1 2018"),
                  ("GOLD_M5_2018.json", "M5 2018"),
                  ("GOLD_M15_2018.json", "M15 2018")):
        if os.path.exists(f"/home/user/signals/data/{f}"):
            out.append((lb, load2018(f), None, 3))
    return out


def halves(s):
    m = len(s) // 2
    return (Series(s.ts[:m], s.o[:m], s.h[:m], s.l[:m], s.c[:m]),
            Series(s.ts[m:], s.o[m:], s.h[m:], s.l[m:], s.c[m:]))


def main():
    S = samples()
    print("=" * 82)
    print("  E-195 — FORTY-FOUR SMC / ICT / LIQUIDITY CONCEPTS, ONE QUESTION:")
    print("  does it mark the START of a leg? LIFT is against a time-shifted")
    print("  copy of the SAME series. THE BEST-OF-N LINE is what the best of")
    print("  the whole library scores when nothing in it has any edge.")
    print("=" * 82)

    tabs, lines = {}, {}
    for (lb, s, o, pv) in S:
        r, line, base = report(lb, s, other=o, pv=pv)
        tabs[lb] = r
        lines[lb] = line

    names = sorted({k for r in tabs.values() for k in r})
    print()
    print("=" * 82)
    print("  REPLICATION. A concept has to clear its sample's own best-of-N")
    print("  line, on more than one sample, or it is the best of forty coins.")
    print("=" * 82)
    hdr = "".join(f"{lb.split()[0]:>10}" for lb, _, _, _ in S)
    print(f"  {'concept':<28}{hdr}{'clears':>8}")
    print(f"  {'best-of-N line ->':<28}"
          + "".join(f"{lines[lb]:>10.2f}" for lb, _, _, _ in S))
    print("  " + "-" * 80)
    scored = []
    for nm in names:
        cells, clears = [], 0
        for (lb, _, _, _) in S:
            r = tabs[lb].get(nm)
            if not r or r[1] < 30:
                cells.append(f"{'-':>10}")
                continue
            cells.append(f"{r[4]:>10.2f}")
            if r[4] >= lines[lb]:
                clears += 1
        scored.append((clears, nm, "".join(cells)))
    scored.sort(key=lambda x: -x[0])
    for (clears, nm, cells) in scored:
        print(f"  {nm:<28}{cells}{clears:>8}")

    print()
    print("=" * 82)
    print("  OUT OF SAMPLE (E-150). The concepts that cleared on more than one")
    print("  sample, re-scored on the FIRST and SECOND half of each separately.")
    print("  Clearing twice on one half and never on the other is a sweep.")
    print("=" * 82)
    keep = [nm for (c, nm, _) in scored if c >= 2]
    if not keep:
        print("  NOTHING cleared on two samples. There is nothing to test.")
        return
    for (lb, s, o, pv) in S:
        a, b = halves(s)
        oa = ob = None
        if o is not None:
            oa, ob = halves(o)
        ra, la, _ = report(lb, a, other=oa, pv=pv, quiet=True)
        rb, lb2, _ = report(lb, b, other=ob, pv=pv, quiet=True)
        print(f"\n  {lb}   first-half line {la:.2f}   second-half line {lb2:.2f}")
        for nm in keep:
            x, y = ra.get(nm), rb.get(nm)
            if not x or not y or x[1] < 30 or y[1] < 30:
                print(f"    {nm:<28}   too few fires in a half")
                continue
            m1 = "CLEARS" if x[4] >= la else "  -   "
            m2 = "CLEARS" if y[4] >= lb2 else "  -   "
            print(f"    {nm:<28}{x[4]:>7.2f} {m1}   {y[4]:>7.2f} {m2}")


if __name__ == "__main__":
    main()

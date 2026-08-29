"""
Does the sweep taxonomy actually predict anything?

The master specification proposes seven sweep classes and a quality score. That
is only worth building if the classes SEPARATE outcomes. If Type D behaves like
Type A, the taxonomy is narrative, not signal, and every parameter it
introduces is pure overfitting surface.

This is the falsification test for the whole approach, run before any EA code
exists.

Run:  python3 JARVIS/research/sweep_study.py [SYMBOL] [TF]
"""
from __future__ import annotations
import os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, sweeps as sw


def med(xs):
    return st.median(xs) if xs else 0.0


def table(groups, label):
    print(f"\n{label}")
    print(f"  {'group':<18}{'n':>6}{'win 1R':>9}{'win 2R':>9}"
          f"{'med MFE':>10}{'med MAE':>10}{'stopped':>9}")
    print("  " + "-" * 72)
    rows = []
    for k in sorted(groups):
        g = [x for x in groups[k] if x.outcome]
        if len(g) < 15:
            print(f"  {str(k):<18}{len(g):>6}   (too few to read)")
            continue
        p1 = sum(1 for x in g if x.outcome["won_1R"]) / len(g)
        p2 = sum(1 for x in g if x.outcome["won_2R"]) / len(g)
        mf = med([x.outcome["mfe_R"] for x in g])
        ma = med([x.outcome["mae_R"] for x in g])
        sp = sum(1 for x in g if x.outcome["hit_stop"]) / len(g)
        rows.append((k, len(g), p1, p2, mf, ma, sp))
        print(f"  {str(k):<18}{len(g):>6}{100*p1:>8.0f}%{100*p2:>8.0f}%"
              f"{mf:>10.2f}{ma:>10.2f}{100*sp:>8.0f}%")
    return rows


def run(symbol="GOLD", tf="15m"):
    s = engine.load(symbol, tf)
    levels = sw.find_levels(s)
    events = sw.detect_sweeps(s, levels)
    sw.add_outcomes(s, events)
    tradeable = [e for e in events if e.side != 0 and e.outcome]

    print("=" * 80)
    print(f"  SWEEP TAXONOMY STUDY — {symbol} {tf}")
    print(f"  {len(s)} bars · {len(levels)} levels · {len(events)} sweeps · "
          f"{len(tradeable)} with a side and an outcome")
    print("=" * 80)
    print("\nEntry = close of the DECISION bar (earliest obtainable price once the")
    print("class was knowable). Stop = 1 ATR, target hit BEFORE stop = a win.")
    print("Ties (both touched on one bar) count as LOSSES.")

    by_type = {}
    for e in tradeable:
        by_type.setdefault(e.stype, []).append(e)
    rows = table(by_type, "BY SWEEP TYPE  (A=wick reject  B=reclaim  C=deep  "
                          "D=displacement  E=structure shift  F=continuation)")

    # does the strength score separate anything?
    by_str = {}
    for e in tradeable:
        b = ("0.0-0.3" if e.features["level_strength"] < 0.3 else
             "0.3-0.5" if e.features["level_strength"] < 0.5 else
             "0.5-0.7" if e.features["level_strength"] < 0.7 else "0.7+")
        by_str.setdefault(b, []).append(e)
    table(by_str, "BY LIQUIDITY STRENGTH SCORE")

    by_depth = {}
    for e in tradeable:
        d = e.features["depth_atr"]
        b = ("<0.25" if d < 0.25 else "0.25-0.5" if d < 0.5 else
             "0.5-1.0" if d < 1.0 else "1.0+")
        by_depth.setdefault(b, []).append(e)
    table(by_depth, "BY SWEEP DEPTH (ATR)")

    # ---- the verdict
    print("\n" + "=" * 80)
    if len(rows) >= 3:
        best = max(rows, key=lambda r: r[2])
        worst = min(rows, key=lambda r: r[2])
        spread = best[2] - worst[2]
        base = sum(1 for x in tradeable if x.outcome["won_1R"]) / len(tradeable)
        print(f"  baseline win-1R across all sweeps: {100*base:.0f}%")
        print(f"  best type  {best[0]}: {100*best[2]:.0f}%   "
              f"worst type {worst[0]}: {100*worst[2]:.0f}%   "
              f"spread {100*spread:.0f} points")
        if spread < 0.10:
            print("\n  VERDICT: the taxonomy does NOT separate outcomes.")
            print("  The classes are narrative, not signal. Building a quality")
            print("  score on them would be pure overfitting surface.")
        elif spread < 0.20:
            print("\n  VERDICT: weak separation. Worth one more test on a bigger")
            print("  sample before any of it is built into an EA.")
        else:
            print("\n  VERDICT: the taxonomy separates outcomes materially.")
            print("  Worth carrying into the specification — but confirm on")
            print("  out-of-sample data and after costs before trusting it.")
    print("=" * 80)
    return rows


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "GOLD",
        sys.argv[2] if len(sys.argv) > 2 else "15m")


# ---------------------------------------------------------------- null test
def null_test(symbol="GOLD", tf="15m", trials=200, seed=13):
    """
    THE FALSIFICATION TEST.

    Two nulls, each isolating a different claim:

      NULL 1 — random SIDE at the same bars the sweeps fired.
               Controls for timing and market conditions completely.
               If sweeps do not beat this, the sweep does not predict DIRECTION.

      NULL 2 — the same side distribution at random bars.
               If sweeps do not beat this, sweep TIMING is worthless.

    A strategy that cannot beat both of these is measuring gold's volatility,
    not an edge.
    """
    import random
    s = engine.load(symbol, tf)
    levels = sw.find_levels(s)
    events = sw.detect_sweeps(s, levels)
    sw.add_outcomes(s, events)
    real = [e for e in events if e.side != 0 and e.outcome]
    if not real:
        print("no events"); return
    real_win = sum(1 for e in real if e.outcome["won_1R"]) / len(real)

    rng = random.Random(seed)

    A = engine.atr(s, 14)          # precompute once, not per call

    def resolve(bar, side, horizon=40, stop_atr=1.0):
        a = A
        if bar + 2 >= len(s):
            return None
        entry, av = s.c[bar], (a[bar] or 0)
        if av <= 0:
            return None
        risk = stop_atr * av
        for j in range(bar + 1, min(bar + 1 + horizon, len(s))):
            fav = (s.h[j] - entry) if side > 0 else (entry - s.l[j])
            adv = (entry - s.l[j]) if side > 0 else (s.h[j] - entry)
            if adv >= risk:
                return False                    # ties lose
            if fav >= risk:
                return True
        return False

    # NULL 1: same bars, random side
    n1 = []
    for _ in range(trials):
        wins = tot = 0
        for e in real:
            r = resolve(e.decision_bar, rng.choice((1, -1)))
            if r is not None:
                tot += 1; wins += int(r)
        if tot:
            n1.append(wins / tot)
    # NULL 2: random bars, same side mix
    sides = [e.side for e in real]
    n2 = []
    lo, hi = 50, len(s) - 60
    for _ in range(trials):
        wins = tot = 0
        for sd in sides:
            r = resolve(rng.randrange(lo, hi), sd)
            if r is not None:
                tot += 1; wins += int(r)
        if tot:
            n2.append(wins / tot)
    n1.sort(); n2.sort()
    q = lambda a, p: a[int(p * (len(a) - 1))] if a else 0

    print("\n" + "=" * 80)
    print(f"  NULL TEST — {symbol} {tf}   ({len(real)} real sweeps, {trials} trials each)")
    print("=" * 80)
    print(f"  REAL sweeps, win rate at 1R          : {100*real_win:.1f}%")
    print(f"  NULL 1 (same bars, RANDOM side)      : median {100*q(n1,.5):.1f}%   "
          f"95th pct {100*q(n1,.95):.1f}%")
    print(f"  NULL 2 (random bars, same side mix)  : median {100*q(n2,.5):.1f}%   "
          f"95th pct {100*q(n2,.95):.1f}%")
    beat1 = sum(1 for v in n1 if v >= real_win) / len(n1) if n1 else 1
    beat2 = sum(1 for v in n2 if v >= real_win) / len(n2) if n2 else 1
    print(f"\n  P(random side beats the real sweeps) = {100*beat1:.1f}%")
    print(f"  P(random bars beats the real sweeps) = {100*beat2:.1f}%")
    print()
    if beat1 > 0.05:
        print("  DIRECTION: sweeps do NOT predict direction. A coin flip at the")
        print("  same moments does as well or better.")
    else:
        print("  DIRECTION: sweeps beat a coin flip at the same moments.")
    if beat2 > 0.05:
        print("  TIMING: sweep timing adds nothing over entering at random bars.")
    else:
        print("  TIMING: sweep timing beats random entry bars.")
    print("=" * 80)
    return real_win, q(n1, .5), q(n2, .5)


if __name__ == "__main__" and "--null" in sys.argv:
    null_test(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "GOLD",
              sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "15m")

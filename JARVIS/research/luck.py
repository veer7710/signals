"""
E-054 — "The EA made me 50+ in a few hours." What does that actually tell us?

Veer: "the ea made me 50+ even with its shit stacking shit closing at peaks in
a few hours this means if we improve even on chop days and good days we will
see straight green and consistent results".

The inference is: a good result while broken implies a better result once
fixed. That is only true if the good result came from EDGE. If it came from
SIZE, the same size produces the mirror image just as easily, and fixing the
execution changes the sign of nothing.

This does not argue. It computes: how often does a system with NO EDGE AT ALL
produce a +124% run (GBP50 -> GBP112) in a single session, at various risk
settings? If a no-edge system does it often, the result is not evidence.

THE METHOD, and why it is fair to the claim
The R distribution is taken from the REAL SuperTrend strategy on the closest
data this repo has (GOLD 15m, the EA's own gating), then DE-MEANED so its
expectancy is exactly zero. That keeps the real shape - the fat right tail,
the cluster of full-R losses - and removes only the edge. Every run below is
therefore a system that is genuinely worthless, trading Veer's actual payoff
shape.

Run:  python3 JARVIS/research/luck.py
"""
from __future__ import annotations
import os, sys, random, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies, study, chop


def r_distribution(symbol="GOLD", tf="15m"):
    s = engine.load(symbol, tf)
    rows = chop.collect(s, study.COSTS.get(symbol, engine.Costs()))
    rs = [r["r"] for r in rows]
    m = sum(rs) / len(rs)
    return [r - m for r in rs], m, len(rs)          # de-meaned: zero edge


def simulate(rs, risk, n_trades, target, trials=200000, seed=5):
    """Fraction of sessions that reach `target` growth, and that lose half."""
    rng = random.Random(seed)
    hit = 0
    ruin = 0
    ends = []
    k = len(rs)
    for _ in range(trials):
        eq = 1.0
        best = 1.0
        worst = 1.0
        for _ in range(n_trades):
            eq += eq * risk * rs[rng.randrange(k)]
            if eq > best:
                best = eq
            if eq < worst:
                worst = eq
            if eq <= 0.05:
                break
        ends.append(eq)
        if best >= target:
            hit += 1
        if worst <= 0.5:
            ruin += 1
    ends.sort()
    return hit / trials, ruin / trials, ends


def main():
    rs, real_mean, n = r_distribution()
    print("=" * 78)
    print("  E-054  WAS THE +GBP50 SESSION EVIDENCE OF AN EDGE?")
    print("=" * 78)
    print(f"\n  Payoff shape taken from {n} real SuperTrend trades (GOLD 15m).")
    print(f"  That sample's true expectancy was {real_mean:+.3f}R; it has been")
    print(f"  shifted to EXACTLY ZERO, so every system below is worthless by")
    print(f"  construction and only the shape of the wins and losses is real.")
    print(f"  sd of R = {statistics.pstdev(rs):.2f}, "
          f"best {max(rs):+.1f}R, worst {min(rs):+.1f}R")

    target = 112.0 / 50.0        # the run being explained: GBP50 -> GBP112
    print(f"\n  TARGET: reach {target:.2f}x starting equity (GBP50 -> GBP112)")
    print(f"  in ONE session, with a ZERO-EDGE system.\n")
    print(f"  {'risk/trade':<12}{'trades':>8}{'P(hit +124%)':>15}"
          f"{'P(lose half)':>15}{'median end':>13}")
    print("  " + "-" * 61)

    for risk in (0.01, 0.02, 0.05, 0.10, 0.20):
        for nt in (20, 40, 80):
            p, ruin, ends = simulate(rs, risk, nt, target, trials=40000)
            med = ends[len(ends) // 2]
            print(f"  {100*risk:>5.0f}%      {nt:>8}{100*p:>14.1f}%"
                  f"{100*ruin:>14.1f}%{med:>12.2f}x")
        print()

    print("  READ IT LIKE THIS")
    print("  Find the row matching how much you actually risked per trade and")
    print("  how many trades you took. The P(hit) column is how often a system")
    print("  with NO EDGE WHATSOEVER produces the session you had. The column")
    print("  beside it is how often the same settings halve the account -")
    print("  because the two are the same coin and only one of them gets")
    print("  screenshotted.")


if __name__ == "__main__":
    main()

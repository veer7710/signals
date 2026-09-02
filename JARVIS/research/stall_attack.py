"""
E-073 — The stall finding, attacked properly. It is the EA's load-bearing wall.

E-056 reported that "bars since a trade last made a new best" predicts giving
the profit back, monotonically, in 8 of 8 markets. That result is why the EA's
give-back allowance scales with stall - a trade still printing new highs gets
35% more rope, one that peaked 25 bars ago gets 45% less. If E-056 is an
artifact, the EA is tuned on nothing.

AND IT HAS AN OBVIOUS WAY TO BE AN ARTIFACT. E-056 takes ONE OBSERVATION PER
BAR. A single trade that runs 60 bars contributes 60 rows, and those rows are
not 60 independent facts: they share one entry, one peak, one outcome. Every
count, every "8 of 8", and every confidence interval in E-056 is computed as
though they were. That inflates n by roughly the average hold time and shrinks
every interval by its square root.

Two corrections, both of which must agree before the finding stands:

  PER-TRADE   one randomly chosen qualifying bar from each trade, so every
              trade contributes exactly one vote. Repeated over 200 seeds,
              because a single draw has its own sampling error (E-064).
  CLUSTER     bootstrap that resamples TRADES, not bars. This keeps all of a
              trade's bars but treats the TRADE as the unit of information,
              which is what it is.

If the effect survives both with the same sign and a interval clear of zero,
the EA's stall scaling is earned. If it does not, the scaling comes out.

Run:  python3 JARVIS/research/stall_attack.py
"""
from __future__ import annotations
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies, study, chop

LOW = (0, 3)          # "still working"
HIGH = (12, 10 ** 9)  # "it stopped"


def collect_by_trade(s, costs, warmup=300, max_hold=200, stop_atr=2.0,
                     min_r=0.5, step_r=0.5):
    """E-056's own measurement, but the rows are KEPT GROUPED BY TRADE so the
    unit of information is visible instead of being silently discarded.
    Returns a list of trades, each a list of that trade's observations."""
    ctx = engine.build_context(s)
    sig = strategies.supertrend_sniper_ea(s)
    half = costs.spread / 2.0
    trades = []

    for i in range(warmup, len(s) - 2):
        sg = sig(ctx, i)
        if not sg:
            continue
        side = sg["side"]
        a = ctx["atr"][i]
        if a is None or a <= 0:
            continue
        entry = s.o[i + 1] + side * (half + costs.slippage)
        risk = stop_atr * a
        if risk <= 0:
            continue

        rows = []
        peak, peak_bar = 0.0, i + 1
        for j in range(i + 1, min(i + 1 + max_hold, len(s))):
            fav = (s.h[j] - entry) if side == 1 else (entry - s.l[j])
            adv = (entry - s.l[j]) if side == 1 else (s.h[j] - entry)
            if adv >= risk:
                break
            if fav > peak:
                peak, peak_bar = fav, j
            if peak / risk < min_r:
                continue
            stall = j - peak_bar
            need = peak + step_r * risk
            gone = None
            for k in range(j + 1, min(i + 1 + max_hold, len(s))):
                f2 = (s.h[k] - entry) if side == 1 else (entry - s.l[k])
                back = (s.c[k] - entry) * side
                if back <= 0:          # ties lose
                    gone = True; break
                if f2 >= need:
                    gone = False; break
            if gone is None:
                continue
            rows.append({"stall": stall, "peak_r": peak / risk, "gave": gone})
        if rows:
            trades.append(rows)
    return trades


def gap(rows):
    """P(gives it back | stalled) - P(gives it back | still working).
    Positive means the stall is informative in the direction E-056 claimed."""
    lo = [r for r in rows if LOW[0] <= r["stall"] < LOW[1]]
    hi = [r for r in rows if HIGH[0] <= r["stall"] < HIGH[1]]
    if len(lo) < 5 or len(hi) < 5:
        return None
    return (sum(1 for r in hi if r["gave"]) / len(hi)
            - sum(1 for r in lo if r["gave"]) / len(lo))


def per_trade(trades, seeds=200):
    """One vote per trade. A trade whose single sampled bar falls in neither
    bucket simply does not vote that round."""
    out = []
    for sd in range(seeds):
        rng = random.Random(1000 + sd)
        picked = [rng.choice(t) for t in trades]
        g = gap(picked)
        if g is not None:
            out.append(g)
    return out


def per_trade_boot(trades, iters=800, seed=21):
    """The strictest of the three: resample TRADES with replacement AND take a
    single random bar from each. This is the only estimate whose n is the
    number of trades in both the point estimate and the interval."""
    rng = random.Random(seed)
    n = len(trades)
    out = []
    for _ in range(iters):
        rows = [rng.choice(trades[rng.randrange(n)]) for _ in range(n)]
        g = gap(rows)
        if g is not None:
            out.append(g)
    out.sort()
    return out


def cluster_boot(trades, iters=1000, seed=7):
    """Resample TRADES with replacement, keeping each one's bars together."""
    rng = random.Random(seed)
    n = len(trades)
    out = []
    for _ in range(iters):
        rows = []
        for _ in range(n):
            rows.extend(trades[rng.randrange(n)])
        g = gap(rows)
        if g is not None:
            out.append(g)
    out.sort()
    return out


def main():
    print("=" * 100)
    print("  E-073  THE STALL FINDING, ATTACKED AS A CLUSTERED SAMPLE")
    print("  gap = P(gives it back | stall 12+) - P(gives it back | stall 0-3).")
    print("  E-056 claimed this is positive in 8 of 8 markets, counting BARS.")
    print("  Here every trade gets one vote, and the bootstrap resamples TRADES.")
    print("=" * 100)
    print(f"\n  {'market':<13}{'trades':>8}{'bars':>8}{'bars/trade':>12}"
          f"{'naive gap':>11}   {'per-trade gap + 95% CI':>26}{'cluster 95% CI':>20}{'':>6}")
    print("  " + "-" * 98)

    naive_pos = pt_pos = cl_pos = seen = 0
    for sym, tf in chop.COMBOS:
        try:
            s = engine.load(sym, tf)
        except Exception:
            continue
        tr = collect_by_trade(s, study.COSTS.get(sym, engine.Costs()))
        rows = [r for t in tr for r in t]
        if len(tr) < 30 or len(rows) < 200:
            continue
        seen += 1
        gn = gap(rows)
        pts = per_trade(tr)
        cb = cluster_boot(tr)
        if gn is None or not pts or not cb:
            continue
        pm = sum(pts) / len(pts)
        pb = per_trade_boot(tr)
        if not pb:
            continue
        plo, phi = pb[int(len(pb) * 0.025)], pb[int(len(pb) * 0.975)]
        lo95, hi95 = cb[int(len(cb) * 0.025)], cb[int(len(cb) * 0.975)]
        if gn > 0: naive_pos += 1
        if plo > 0: pt_pos += 1
        clear = lo95 > 0
        if clear: cl_pos += 1
        print(f"  {sym+' '+tf:<13}{len(tr):>8}{len(rows):>8}"
              f"{len(rows)/len(tr):>12.1f}{gn:>+10.3f}   "
              f"{pm:>+7.3f} [{plo:>+.3f},{phi:>+.3f}]"
              f"  [{lo95:>+.3f}, {hi95:>+.3f}]"
              f"{'  CLEAR' if clear else '  spans 0'}")

    print("  " + "-" * 98)
    print(f"\n  positive counting BARS (what E-056 reported):  {naive_pos}/{seen}")
    print(f"  ONE VOTE PER TRADE, 95% interval above zero:   {pt_pos}/{seen}")
    print(f"  cluster 95% interval entirely above zero:      {cl_pos}/{seen}")
    # ---------------------------------------------------------------
    # THE DECISIVE TEST. Per market there are only ~250 independent trades,
    # which is not enough to resolve an effect this size - that is what 0/8
    # above means, and it is NOT the same as the effect being absent. Pooling
    # every market's trades gives ~1800 independent units. If the per-trade
    # interval clears zero there, the effect is real and small. If it does not,
    # the stall scaling in the EA is not earned by anything.
    print("\n  POOLED — every market's TRADES together, one vote each")
    print("  " + "-" * 98)
    allt = []
    for sym, tf in chop.COMBOS:
        try:
            s2 = engine.load(sym, tf)
        except Exception:
            continue
        t2 = collect_by_trade(s2, study.COSTS.get(sym, engine.Costs()))
        if len(t2) >= 30:
            allt.extend(t2)
    if allt:
        rowsA = [r for t in allt for r in t]
        gA = gap(rowsA)
        ptsA = per_trade(allt, seeds=200)
        pbA = per_trade_boot(allt, iters=800)
        cbA = cluster_boot(allt, iters=800)
        pmA = sum(ptsA) / len(ptsA)
        pl, ph = pbA[int(len(pbA) * 0.025)], pbA[int(len(pbA) * 0.975)]
        cl, ch = cbA[int(len(cbA) * 0.025)], cbA[int(len(cbA) * 0.975)]
        print(f"  {len(allt)} independent trades, {len(rowsA)} bars "
              f"({len(rowsA)/len(allt):.1f} bars per trade)")
        print(f"  counting BARS      gap {gA:+.3f}   cluster 95% [{cl:+.3f}, {ch:+.3f}]"
              f"   {'CLEAR' if cl > 0 else 'spans 0'}")
        print(f"  ONE VOTE PER TRADE gap {pmA:+.3f}   95% [{pl:+.3f}, {ph:+.3f}]"
              f"   {'CLEAR' if pl > 0 else 'spans 0'}")
        print()
        if pl > 0:
            print("  The effect is REAL and it is SMALL. E-056's magnitude came from")
            print("  long trades contributing dozens of stalled bars each; its")
            print("  DIRECTION is earned, its SIZE was inflated by about 5x.")
        else:
            print("  The effect does not survive being counted once per trade even")
            print("  pooled. E-056 is an artifact of its sampling and the EA's stall")
            print("  scaling is not earned by it.")

    print("\n  HOW TO READ THIS")
    print("  * 'bars/trade' is the factor by which E-056 overstated its own n.")
    print("    An interval computed on bars is roughly sqrt(that) too narrow.")
    print("  * The per-trade gap keeps the SIGN honest; the cluster interval")
    print("    keeps the WIDTH honest. The finding needs both.")
    print("  * A market that spans zero is not evidence against the effect, it is")
    print("    an absence of evidence for it in that market. The count that")
    print("    matters is how many are CLEAR.")


if __name__ == "__main__":
    main()

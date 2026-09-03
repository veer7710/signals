"""
E-085 — The middle of the range is where SuperTrend dies. What to do about it.

E-084 mapped every trade against nine backward-looking price-action descriptors.
Eight showed nothing coherent. One showed a clean U:

  GOLD 1h, position in the last 20-bar range, expectancy by quintile
     bottom 36%   +0.221R          <- range low, a real reversal
     0.36-0.50    -0.013R
     0.50-0.63    -0.159R          <- these two carry 53% OF ALL LOSSES
     0.63-0.78    +0.341R
     top 22%      +0.372R          <- range high, a real break

A U-shape is far stronger evidence than one odd bucket, because it has a
mechanism and a direction: a SuperTrend flip AT a range extreme is a genuine
break or reversal; the same flip in the MIDDLE of a range is the market
changing its mind inside noise, which is exactly the "false move" Veer
describes and exactly where a trend-following signal should fail.

It replicates on 15m (0.29-0.43 at -0.038R, 0.55-0.73 at -0.028R, extremes
+0.241/+0.281/+0.414).

BUT 45 cells were inspected (9 descriptors x 5 buckets), so some negatives are
expected by chance. This file does not trust the finding - it tests it:

  1. OUT OF SAMPLE   fit the band on the first half, apply it to the second.
  2. THE RIGHT ACTION  E-074's lesson is that removing trades usually removes
     more money than it saves. So SIZE DOWN is tested before SKIP, and both
     are judged on POINTS, not expectancy.
  3. POOLED          1h and 15m together, because the 15m buckets are thin.

Run:  python3 JARVIS/research/rangepos.py
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from liquidity import stat
from failure_map import supertrend_trades

GBP = 1.00 / 1.27
LO, HI = 0.35, 0.70          # the losing band, read off the 1h quintiles


def apply(tr, mode, lo=LO, hi=HI, size=0.5):
    """Return (weighted trades, size taken) under each policy. A 'size' of 0.5
    halves BOTH the win and the loss - it does not halve the risk of being
    wrong about the band."""
    out = []
    for x in tr:
        rp = x.get("range_pos")
        inband = rp is not None and lo <= rp <= hi
        if mode == "full" or not inband:
            w = 1.0
        elif mode == "skip":
            continue
        else:
            w = size
        y = dict(x)
        y["r"] *= w
        y["pts"] *= w
        out.append(y)
    return out


def line(name, tr):
    if len(tr) < 20:
        return
    a = stat(tr)
    p = sum(x["pts"] for x in tr)
    print(f"   {name:<26}{a['n']:>6}{a['win']:>7.1f}%{a['exp']:>+9.3f}R"
          f"{a['pf']:>7.2f}{a['t']:>+8.2f}{p:>+10.0f}{p*GBP:>+9.0f}")


def main():
    print("=" * 96)
    print("  E-085  THE MIDDLE OF THE RANGE — size down, or skip, or leave alone?")
    print(f"  The band is {LO}-{HI} of the last 20-bar range, read off the 1h quintiles.")
    print("  Judged on POINTS. E-074: removing trades usually removes more money")
    print("  than it saves, so 'skip' has to beat 'half size' to be worth it.")
    print("=" * 96)

    pool = []
    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        tr = supertrend_trades(s, c)
        pool += tr
        print(f"\n  ### {sym} {tf}")
        print(f"   {'policy':<26}{'n':>6}{'win%':>8}{'expect':>10}{'PF':>7}"
              f"{'t':>8}{'points':>10}{'GBP':>9}")
        print("   " + "-" * 76)
        line("leave it alone", apply(tr, "full"))
        line("quarter size in the band", apply(tr, "size", size=0.25))
        line("half size in the band", apply(tr, "size", size=0.5))
        line("skip the band entirely", apply(tr, "skip"))
        inb = [x for x in tr if x.get("range_pos") is not None
               and LO <= x["range_pos"] <= HI]
        if inb:
            a = stat(inb)
            print(f"   (the band on its own: n={a['n']}, {a['exp']:+.3f}R, "
                  f"{sum(x['pts'] for x in inb):+.0f} points)")

    print(f"\n  ### POOLED 1h + 15m")
    print(f"   {'policy':<26}{'n':>6}{'win%':>8}{'expect':>10}{'PF':>7}"
          f"{'t':>8}{'points':>10}{'GBP':>9}")
    print("   " + "-" * 76)
    for nm, md, sz in (("leave it alone", "full", 1.0),
                       ("quarter size in the band", "size", 0.25),
                       ("half size in the band", "size", 0.5),
                       ("skip the band entirely", "skip", 0.0)):
        line(nm, apply(pool, md, size=sz))

    # ---------------- the test that matters
    print("\n" + "=" * 96)
    print("  OUT OF SAMPLE — the band was read off the FIRST half. Does it hold")
    print("  in the second half, which had no say in choosing it?")
    print("=" * 96)
    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        tr = supertrend_trades(s, study.COSTS["GOLD"])
        h = len(tr) // 2
        for half, nm in ((tr[:h], "first half (where it was found)"),
                         (tr[h:], "SECOND HALF (out of sample)")):
            inb = [x for x in half if x.get("range_pos") is not None
                   and LO <= x["range_pos"] <= HI]
            out = [x for x in half if x.get("range_pos") is not None
                   and not (LO <= x["range_pos"] <= HI)]
            if len(inb) < 15 or len(out) < 15:
                continue
            a, b = stat(inb), stat(out)
            print(f"\n  {sym} {tf} — {nm}")
            print(f"    inside the band   n={a['n']:<4} {a['exp']:+.3f}R"
                  f"  {sum(x['pts'] for x in inb):+.0f} points")
            print(f"    outside it        n={b['n']:<4} {b['exp']:+.3f}R"
                  f"  {sum(x['pts'] for x in out):+.0f} points")
            print(f"    separation        {b['exp']-a['exp']:+.3f}R"
                  f"   {'HOLDS' if b['exp'] > a['exp'] else 'DOES NOT HOLD'}")


if __name__ == "__main__":
    main()

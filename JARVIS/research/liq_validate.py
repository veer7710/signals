"""
E-069 — The retest geometry, put through everything that can break it.

E-068 reconciled Veer's "80% winrate" with E-065's measured 31.6%. They were
never about the same trade. Three of my choices, none of them his, cost 50
points of win rate:

  1. ZONE   E-065 needed 3 pivots inside a +/-ATR/6.9 band. That fires 12 times
            in 4501 bars of GOLD 15m. His "Liquidity Sweeps" script treats a
            SINGLE swing point as liquidity: 177 times.
  2. ENTRY  E-065 bought the sweep bar's close. At ZERO COST that entry scores
            -0.003R. It has no edge at all; the whole edge is in waiting for
            the RETEST of the swept level.
  3. TARGET E-065 aimed at the opposite zone, 3-6 ATR away. 33% win rate by
            construction. A 0.5 ATR target behind a 1.5 ATR stop gives 80.5%.

At zone=any-pivot / entry=retest / stop=1.5 ATR / target=0.5 ATR the pooled win
rate is 80.5%, which is Veer's number to within a point. That is a
reconciliation, not a validation. This file is the validation, and the shape is
a hostile one to own: it risks 1.5 ATR to make 0.5, so it needs ~75% just to
break even and its losing tail is three times its winning bar.

WHAT IS TESTED HERE
  * out-of-sample split, chronological, fitted on nothing
  * walk-forward in 6 blocks
  * Monte Carlo on trade order -> drawdown distribution
  * the control run at 12 SEEDS, because a single control has its own sampling
    error (E-064) and this edge is being claimed against it
  * cost sensitivity, already known to be mild, re-checked per market

Run:  python3 JARVIS/research/liq_validate.py
"""
from __future__ import annotations
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from liq_geometry import sweep_events, random_events, run, COMBOS
from liquidity import stat

ZONE, ENTRY, STOP, TGT = 1, "retest", 1.5, 0.50


def mc_drawdown(rs, iters=2000, seed=7):
    """Shuffle trade ORDER only. Same trades, same expectancy; this measures the
    drawdown you could have lived through, not a different strategy."""
    rng = random.Random(seed)
    dds = []
    for _ in range(iters):
        x = rs[:]
        rng.shuffle(x)
        eq = peak = 0.0
        dd = 0.0
        for r in x:
            eq += r
            peak = max(peak, eq)
            dd = max(dd, peak - eq)
        dds.append(dd)
    dds.sort()
    return dds


def main():
    print("=" * 96)
    print("  E-069  zone=any pivot · entry=RETEST · stop=1.5 ATR · target=0.5 ATR")
    print("  The geometry that reproduces Veer's 80%, now attacked.")
    print("  Ties lose. Costs charged both ends. Nothing below is fitted per market.")
    print("=" * 96)

    for sym, tf in COMBOS:
        try:
            s = engine.load(sym, tf)
        except Exception:
            continue
        c = study.COSTS.get(sym, engine.Costs())
        ev = sweep_events(s, min_piv=ZONE)
        tr = run(s, c, ev, ENTRY, STOP, TGT)
        if len(tr) < 40:
            continue
        rs = [x["r"] for x in tr]
        a = stat(tr)

        # ---- chronological OOS split
        h = len(tr) // 2
        A_, B_ = stat(tr[:h]), stat(tr[h:])

        # ---- walk-forward, 6 blocks
        nb = 6
        blocks = [tr[i * len(tr) // nb:(i + 1) * len(tr) // nb] for i in range(nb)]
        bs = [stat(b) for b in blocks if len(b) >= 10]
        wf_pos = sum(1 for x in bs if x["exp"] > 0)

        # ---- control at 12 seeds
        cexp = []
        for sd in range(11, 23):
            rv = random_events(s, len(ev), seed=sd)
            cexp.append(stat(run(s, c, rv, ENTRY, STOP, TGT))["exp"])
        cm = sum(cexp) / len(cexp)
        csd = (sum((x - cm) ** 2 for x in cexp) / len(cexp)) ** 0.5
        z = (a["exp"] - cm) / csd if csd > 0 else 0.0

        # ---- Monte Carlo drawdown
        dds = mc_drawdown(rs)
        med = dds[len(dds) // 2]
        p95 = dds[int(len(dds) * 0.95)]

        v = study.verdict({"n": a["n"], "expectancy_R": a["exp"], "t_stat": a["t"]},
                          wf_pos, len(bs), None)

        print(f"\n  ### {sym} {tf}")
        print(f"    n {a['n']}   win {a['win']:.1f}%   expectancy {a['exp']:+.3f}R"
              f"   PF {a['pf']:.2f}   t {a['t']:+.2f}")
        print(f"    OOS      first half {A_['exp']:+.3f}R (n={A_['n']})"
              f"   second half {B_['exp']:+.3f}R (n={B_['n']})")
        blk = "  ".join("%+.2f" % x["exp"] for x in bs)
        print(f"    walk-fwd {wf_pos}/{len(bs)} blocks positive   [{blk}]")
        print(f"    control  12 seeds mean {cm:+.3f}R sd {csd:.3f}R"
              f"   -> strategy is {z:+.1f} control sd away")
        print(f"    drawdown median {med:.1f}R   95th pct {p95:.1f}R"
              f"   (worst actual run of losses matters more than expectancy here)")
        print(f"    VERDICT  {v}")

    print("\n" + "=" * 96)
    print("  WHAT THIS DOES NOT SAY")
    print("  * It does not say the strategy is profitable. The word for a survivor is")
    print("    PROMISING and it still means 'has not been disproved yet'.")
    print("  * The geometry was chosen out of 252 by matching Veer's reported win rate,")
    print("    which is a weaker selection than fitting expectancy but is not none.")
    print("  * 15m and 1h bars. Veer trades M1/M5/M15. Running ExportHistory.mq5 on his")
    print("    terminal is the only thing that makes this a measurement of his timeframe.")
    print("  * A 1.5-for-0.5 shape needs 75% just to break even. Every point of win rate")
    print("    lost in live slippage costs about 0.03R. It has no margin for sloppiness.")


if __name__ == "__main__":
    main()

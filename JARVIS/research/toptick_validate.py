"""
E-077 — The top-tick entry, attacked. This is the one that would be traded.

E-076 found the cell I had never tested: a limit resting INSIDE the liquidity
zone, filled BY the sweep rather than after it, with a small stop just past the
poke and a 2R target. Veer's description of it: "we do a small stop loss which
is reasonable and catch a massiveeee entry from the tick".

It beats everything shipped before it, on both timeframes, with MORE trades:

                              n     win%   expectancy   points
  E-069 retest (shipped)    401    87.8%     +0.106R      ~
  E-076 top-tick GOLD 1h    491    47.5%     +0.378R    +2172
  E-076 top-tick GOLD 15m   158    48.1%     +0.380R     +301

That is 3.5x the expectancy in the opposite geometry. A result that large from
a cell I had not tried is exactly the kind that turns out to be a bug or a fit,
so this file exists to break it.

  * chronological out-of-sample split
  * walk-forward in 6 blocks
  * a control that resamples ENTRY BARS at random with identical geometry,
    12 seeds, because one control seed has its own sampling error (E-064)
  * Monte Carlo on trade order for the drawdown actually lived through
  * the parameter neighbourhood, because one good cell in a grid of 80 is
    a coincidence and a smooth plateau is a finding
  * cost sensitivity: this shape has a SMALL stop, so unlike E-069 it should
    be cost-SENSITIVE, and if it is not, something is wrong with the model

Run:  python3 JARVIS/research/toptick_validate.py
"""
from __future__ import annotations
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from engine import Series
from liquidity import stat
from liq_validate import mc_drawdown
from toptick import zone_stream, run, entry_level

FRAC, STOP, TGT = -0.25, 0.60, ("r", 2.0)     # the cell E-076 picked


def control(s, costs, per_bar, A, frac, stop_atr, tgt, seed, n_want,
            max_bars=200, warmup=250):
    """Same geometry, same count, RANDOM bars and random direction. Only the
    trigger differs, so this is what the zone logic has to beat."""
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot
    kind, mag = tgt
    rng = random.Random(seed)
    idx = [i for i in range(warmup, len(s) - 2) if A[i] and A[i] > 0]
    out, busy = [], -1
    tries = 0
    while len(out) < n_want and tries < n_want * 40:
        tries += 1
        i = rng.choice(idx)
        if i <= busy:
            continue
        a = A[i]
        side = 1 if rng.random() < 0.5 else -1
        entry = s.o[i + 1] + side * (half + costs.slippage)
        stop = entry - side * stop_atr * a
        risk = (entry - stop) * side
        if risk <= 0:
            continue
        tgtpx = entry + side * mag * risk
        done = None
        for q in range(i + 1, min(i + 1 + max_bars, len(s))):
            hs = (s.l[q] <= stop) if side == 1 else (s.h[q] >= stop)
            ht = (s.h[q] >= tgtpx) if side == 1 else (s.l[q] <= tgtpx)
            if hs: done = (stop, q); break
            if ht: done = (tgtpx, q); break
        if done is None:
            q = min(i + 1 + max_bars, len(s)) - 1
            done = (s.c[q], q)
        px, q = done
        fill = px - side * (half + costs.slippage)
        out.append({"r": ((fill - entry) * side - comm_px) / risk})
        busy = q
    return out


def main():
    print("=" * 100)
    print("  E-077  THE TOP-TICK ENTRY, ATTACKED")
    print("  limit 0.25 ATR past the zone's far edge · stop 0.60 ATR · target 2R")
    print("  XAUUSD only. Ties lose. Costs both ends. Nothing fitted per timeframe.")
    print("=" * 100)

    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        per_bar, A = zone_stream(s)
        tr = run(s, c, per_bar, A, FRAC, STOP, TGT)
        if len(tr) < 40:
            continue
        rs = [x["r"] for x in tr]
        a = stat(tr)
        pts = sum(x["pts"] for x in tr)

        h = len(tr) // 2
        A_, B_ = stat(tr[:h]), stat(tr[h:])
        nb = 6
        bl = [tr[i * len(tr) // nb:(i + 1) * len(tr) // nb] for i in range(nb)]
        bs = [stat(b) for b in bl if len(b) >= 10]
        wf = sum(1 for x in bs if x["exp"] > 0)

        # 30 seeds, not 12. A 0.6 ATR stop with a 2R target is a high-variance
        # lottery, so a control run's own expectancy scatters widely; averaging
        # more of them is what makes the comparison sharp rather than shrugging
        # at the scatter.
        ce = [stat(control(s, c, per_bar, A, FRAC, STOP, TGT, sd, len(tr)))["exp"]
              for sd in range(31, 61)]
        cm = sum(ce) / len(ce)
        csd = (sum((x - cm) ** 2 for x in ce) / len(ce)) ** 0.5
        # The question is whether OUR expectancy differs from the EXPECTED
        # expectancy of a random entry with this geometry. That expected value
        # is estimated by the control MEAN, whose error is sd/sqrt(seeds) - not
        # sd. Dividing by sd instead understates the separation, which is the
        # wrong direction to be wrong in when the answer is "trade it".
        se_ours = abs(a["exp"] / a["t"]) if a["t"] != 0 else 0.0
        se_ctrl = csd / math.sqrt(len(ce))
        den = math.sqrt(se_ours ** 2 + se_ctrl ** 2)
        z = (a["exp"] - cm) / den if den > 0 else 0.0
        z_naive = (a["exp"] - cm) / csd if csd > 0 else 0.0

        dds = mc_drawdown(rs)
        v = study.verdict({"n": a["n"], "expectancy_R": a["exp"], "t_stat": a["t"]},
                          wf, len(bs), None)
        blk = "  ".join("%+.2f" % x["exp"] for x in bs)

        print(f"\n  ### {sym} {tf}")
        print(f"    n {a['n']}   win {a['win']:.1f}%   expectancy {a['exp']:+.3f}R"
              f"   PF {a['pf']:.2f}   t {a['t']:+.2f}   points {pts:+.0f}")
        print(f"    OOS      first half {A_['exp']:+.3f}R (n={A_['n']})"
              f"   second half {B_['exp']:+.3f}R (n={B_['n']})")
        print(f"    walk-fwd {wf}/{len(bs)} blocks positive   [{blk}]")
        print(f"    control  {len(ce)} seeds mean {cm:+.3f}R  (per-seed sd {csd:.3f}R,"
              f" sd of the mean {se_ctrl:.3f}R)")
        print(f"             separation {a['exp']-cm:+.3f}R  ->  {z:+.1f} sd"
              f"   (vs one seed's own scatter: {z_naive:+.1f} sd)")
        print(f"    drawdown median {dds[len(dds)//2]:.1f}R   95th pct "
              f"{dds[int(len(dds)*0.95)]:.1f}R")
        print(f"    exits    " + "  ".join(
            f"{w} {100.0*sum(1 for x in tr if x['why']==w)/len(tr):.0f}%"
            for w in ("target", "stop", "time")))
        print(f"    VERDICT  {v}")

    # ---- neighbourhood: one good cell is a coincidence, a plateau is a finding
    print("\n" + "=" * 100)
    print("  PARAMETER NEIGHBOURHOOD, GOLD 1h — expectancy / points")
    print("=" * 100)
    s = engine.load("GOLD", "1h"); c = study.COSTS["GOLD"]
    per_bar, A = zone_stream(s)
    print(f"\n   {'stop':>7} |" + "".join(f"{('%.1fR'%m):>20}" for m in (1.5, 2.0, 2.5, 3.0)))
    for st_ in (0.35, 0.45, 0.60, 0.75, 0.90):
        cells = []
        for m in (1.5, 2.0, 2.5, 3.0):
            tr = run(s, c, per_bar, A, FRAC, st_, ("r", m))
            a = stat(tr)
            pts = sum(x["pts"] for x in tr) if tr else 0.0
            cells.append(f"{a['n']:>4} {a['exp']:>+6.2f}R {pts:>+6.0f}" if a["n"] >= 25
                         else " " * 19)
        print(f"   {st_:>6.2f}A |" + "".join(f"{x:>20}" for x in cells))

    # ---- cost sensitivity. A SMALL stop should be cost-SENSITIVE.
    print("\n  COST SENSITIVITY, GOLD 1h. This shape risks 0.60 ATR, so unlike")
    print("  E-069 it SHOULD care about the spread. If it does not, the model is wrong.")
    print(f"\n  {'spread':>9}{'n':>7}{'win%':>8}{'expect':>10}{'PF':>7}{'points':>10}")
    for sp in (0.00, 0.10, 0.20, 0.30, 0.46, 0.70, 1.00):
        cc = engine.Costs(spread=sp, slippage=0.05, commission_per_lot=0.0,
                          value_per_point_per_lot=100.0)
        tr = run(s, cc, per_bar, A, FRAC, STOP, TGT)
        a = stat(tr)
        pts = sum(x["pts"] for x in tr) if tr else 0.0
        print(f"  {sp:>9.2f}{a['n']:>7}{a['win']:>7.1f}%{a['exp']:>+9.3f}R"
              f"{a['pf']:>7.2f}{pts:>+10.0f}")


if __name__ == "__main__":
    main()

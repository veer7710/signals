"""
RED TEAM / E-056 part C. E-056 measured P(gives it back) and never measured R.
A stall exit only pays if it raises expectancy. Simulate it.

Same entries as stall.py (supertrend_sniper_ea), same 1.5xATR stop, same costs.
Baseline = stop / target / 200-bar cap. Variants add: if the trade is >= +0.5R
and has not made a new favourable extreme for S bars, close at that bar's close.

CONTROL (E-050 standing rule): a random exit that closes at a random bar drawn
to match the stall rule's own holding-time distribution, so the comparison is
against the same amount of 'exiting early', not against holding forever.
"""
from __future__ import annotations
import os, sys, math, random, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies, study, chop

STALLS = [3, 6, 12, 25]


def run(s, costs, stall_cap=None, rand_exit_bars=None, warmup=300,
        max_hold=200, stop_atr=1.5, rr=2.0, min_r=0.5, seed=11):
    ctx = engine.build_context(s)
    sig = strategies.supertrend_sniper_ea(s)
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot
    rng = random.Random(seed)
    rs, holds = [], []
    i = warmup
    n = len(s)
    while i < n - 2:
        sg = sig(ctx, i)
        if not sg:
            i += 1; continue
        side = sg["side"]; a = ctx["atr"][i]
        if a is None or a <= 0:
            i += 1; continue
        entry = s.o[i + 1] + side * (half + costs.slippage)
        risk = stop_atr * a
        if risk <= 0:
            i += 1; continue
        stop = entry - side * risk
        target = entry + side * rr * risk
        peak = 0.0; peak_bar = i + 1
        r = None; out_j = None
        forced = rand_exit_bars.pop() if rand_exit_bars else None
        for j in range(i + 1, min(i + 1 + max_hold, n)):
            adv = (entry - s.l[j]) if side == 1 else (s.h[j] - entry)
            fav = (s.h[j] - entry) if side == 1 else (entry - s.l[j])
            if adv >= risk:                       # ties lose
                r = (-risk - comm_px) / risk; out_j = j; break
            if fav >= rr * risk:
                fill = target - side * (half + costs.slippage)
                r = ((fill - entry) * side - comm_px) / risk; out_j = j; break
            if fav > peak:
                peak = fav; peak_bar = j
            stall = j - peak_bar
            hit = False
            if forced is not None:
                hit = (j - (i + 1)) >= forced
            elif stall_cap is not None and peak / risk >= min_r and stall >= stall_cap:
                hit = True
            if hit:
                fill = s.c[j] - side * (half + costs.slippage)
                r = ((fill - entry) * side - comm_px) / risk; out_j = j; break
        if r is None:
            j = min(i + max_hold, n - 1)
            fill = s.c[j] - side * (half + costs.slippage)
            r = ((fill - entry) * side - comm_px) / risk; out_j = j
        rs.append(r); holds.append(out_j - (i + 1))
        i = out_j                                    # one position at a time
    return rs, holds


def stat(rs):
    if not rs: return 0, 0.0, 0.0
    e = statistics.mean(rs)
    sd = statistics.pstdev(rs) or 1e-12
    return len(rs), e, e / (sd / math.sqrt(len(rs)))


def main():
    print("=" * 104)
    print("  RED TEAM / E-056 part C — DOES A STALL EXIT MAKE MONEY?")
    print("  supertrend_sniper_ea entries, 1.5xATR stop, 2R target, 200-bar cap,")
    print("  Veer's measured costs. 'ctrl' = random exit matched to the same")
    print("  holding-time distribution the stall rule itself produced.")
    print("=" * 104)
    hdr = f"  {'market':<12}{'baseline':>22}" + "".join(f"{f'stall<={x}':>22}" for x in STALLS)
    print(hdr)
    wins = {x: 0 for x in STALLS}; beats_ctrl = {x: 0 for x in STALLS}; seen = 0
    for sym, tf in chop.COMBOS:
        try:
            s = engine.load(sym, tf)
        except Exception:
            continue
        c = study.COSTS.get(sym, engine.Costs())
        n0, e0, t0 = stat(run(s, c)[0])
        if n0 < 40:
            continue
        seen += 1
        row = f"  {sym+' '+tf:<12}{f'{e0:+.3f}R n={n0} t{t0:+.1f}':>22}"
        for x in STALLS:
            rs, holds = run(s, c, stall_cap=x)
            n1, e1, t1 = stat(rs)
            # matched random-exit control, 10 seeds
            ctrl = []
            for sd in range(10):
                rr_ = random.Random(sd)
                bag = [rr_.choice(holds) for _ in range(len(holds) + 50)]
                cr, _ = run(s, c, rand_exit_bars=bag, seed=sd)
                ctrl.append(statistics.mean(cr) if cr else 0.0)
            ec = statistics.median(ctrl)
            row += f"{f'{e1:+.3f} (ctl {ec:+.3f})':>22}"
            if e1 > e0: wins[x] += 1
            if e1 > ec: beats_ctrl[x] += 1
        print(row)
    print(f"\n  stall exit BEATS the baseline in:      "
          + "  ".join(f"stall<={x}: {wins[x]}/{seen}" for x in STALLS))
    print(f"  stall exit BEATS its RANDOM control in: "
          + "  ".join(f"stall<={x}: {beats_ctrl[x]}/{seen}" for x in STALLS))


if __name__ == "__main__":
    main()

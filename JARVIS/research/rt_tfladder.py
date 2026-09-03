"""
RED TEAM / attack 4. Every M1 conclusion in this project is extrapolated from
15m and 1h. There is no M1 data. But there IS a way to test the DIRECTION of
the extrapolation with the data that exists: build a ladder of bar durations by
aggregating, and measure the SuperTrend entry's edge over a matched random
control at each rung. If the edge shrinks as bars get shorter, extrapolating
down to M1 is optimistic and E-060's 'gold is the whole edge' does not carry.

Both arms pay identical costs, so cost cancels in the DIFFERENCE and what is
left is signal quality alone. The 'net' column keeps cost in, because that is
what the account sees.
"""
from __future__ import annotations
import os, sys, math, random, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies, study
from engine import Series


def sim(s, costs, mode, atr_len=7, mult=1.2, dema_len=200, stop_atr=1.5,
        rr=2.0, cap=50, adx_max=35.0, warmup=300, seed=7, zero_cost=False):
    c = engine.Costs(0, 0, 0, costs.value_per_point_per_lot) if zero_cost else costs
    ctx = engine.build_context(s)
    d, fu, fl = strategies.supertrend_dir(s, atr_len, mult)
    A = engine.atr(s, atr_len)
    D = strategies.dema(s.c, dema_len)
    half = c.spread / 2.0
    comm = c.commission_per_lot / c.value_per_point_per_lot
    rng = random.Random(seed)
    rs = []
    i = warmup
    n = len(s)
    while i < n - 2:
        side = 0
        a = A[i]
        if a and a > 0 and d[i] and d[i - 1] and D[i] is not None:
            ad = ctx["adx"][i]
            if ad is not None and ad <= adx_max:
                if d[i] == -1 and d[i - 1] == 1 and s.c[i] > D[i]:
                    side = 1
                elif d[i] == 1 and d[i - 1] == -1 and s.c[i] < D[i]:
                    side = -1
        if mode == "random" and side != 0:
            side = rng.choice((1, -1))
        if side == 0:
            i += 1; continue
        entry = s.o[i + 1] + side * (half + c.slippage)
        risk = stop_atr * a
        stop = entry - side * risk
        tgt = entry + side * rr * risk
        r = None; oj = None
        for j in range(i + 1, min(i + 1 + cap, n)):
            adv = (entry - s.l[j]) if side == 1 else (s.h[j] - entry)
            fav = (s.h[j] - entry) if side == 1 else (entry - s.l[j])
            if adv >= risk:
                r = (-risk - comm) / risk; oj = j; break
            if fav >= rr * risk:
                f = tgt - side * (half + c.slippage)
                r = ((f - entry) * side - comm) / risk; oj = j; break
        if r is None:
            j = min(i + cap, n - 1)
            f = s.c[j] - side * (half + c.slippage)
            r = ((f - entry) * side - comm) / risk; oj = j
        rs.append(r); i = oj
    return rs


def st(rs):
    if len(rs) < 2: return 0, 0.0, 0.0
    e = statistics.mean(rs); sd = statistics.pstdev(rs) or 1e-12
    return len(rs), e, e / (sd / math.sqrt(len(rs)))


def edge(s, costs, zero_cost=False, **kw):
    real = sim(s, costs, "close", zero_cost=zero_cost, **kw)
    n, e, t = st(real)
    ctrl = [statistics.mean(sim(s, costs, "random", seed=k, zero_cost=zero_cost, **kw))
            for k in range(12) if sim(s, costs, "random", seed=k, zero_cost=zero_cost, **kw)]
    ctrl.sort()
    med = statistics.median(ctrl) if ctrl else 0.0
    p95 = ctrl[int(0.95 * (len(ctrl) - 1))] if ctrl else 0.0
    return n, e, t, med, p95


def main():
    costs = study.COSTS["GOLD"]
    print("=" * 106)
    print("  RED TEAM / attack 4 — THE TIMEFRAME LADDER ON GOLD")
    print("  SuperTrend(7,1.2)+DEMA200+ADX35, 1.5xATR stop, 2R target, 50-bar cap,")
    print("  Veer's 0.46 spread. 'edge' = expectancy MINUS the median of 12")
    print("  matched random-direction controls on the SAME bars and geometry.")
    print("=" * 106)
    print(f"  {'source':<12}{'bar mins':>9}{'n':>6}{'signal':>9}{'t':>7}"
          f"{'rand med':>10}{'rand p95':>10}{'EDGE':>9}{'EDGE(no cost)':>15}")
    base = engine.load("GOLD", "15m")
    b1h  = engine.load("GOLD", "1h")
    rungs = [("15m x1", base, 15), ("15m x2", engine.resample(base, 2), 30),
             ("15m x4", engine.resample(base, 4), 60),
             ("15m x8", engine.resample(base, 8), 120),
             ("1h x1", b1h, 60), ("1h x2", engine.resample(b1h, 2), 120),
             ("1h x4", engine.resample(b1h, 4), 240),
             ("1h x8", engine.resample(b1h, 8), 480)]
    for name, s, mins in rungs:
        if len(s) < 700:
            print(f"  {name:<12}{mins:>9}   too few bars"); continue
        n, e, t, med, p95 = edge(s, costs)
        _n2, e2, _t2, med2, _p2 = edge(s, costs, zero_cost=True)
        print(f"  {name:<12}{mins:>9}{n:>6}{e:>+9.3f}{t:>+7.2f}{med:>+10.3f}"
              f"{p95:>+10.3f}{e-med:>+9.3f}{e2-med2:>+15.3f}")

    # ---------- parameter perturbation, +-30%, on the rung closest to M1
    print("\n" + "=" * 106)
    print("  PARAMETER PERTURBATION +-30%, GOLD 15m (the shortest bar in the repo)")
    print("  Every cell is EDGE OVER ITS OWN MATCHED RANDOM CONTROL.")
    print("=" * 106)
    grid = [("atr_len", [5, 7, 9]), ("mult", [0.84, 1.2, 1.56]),
            ("dema_len", [140, 200, 260]), ("stop_atr", [1.05, 1.5, 1.95]),
            ("rr", [1.4, 2.0, 2.6]), ("cap", [35, 50, 65]),
            ("adx_max", [24.5, 35.0, 45.5])]
    for tf in ("15m", "1h"):
        s = engine.load("GOLD", tf)
        print(f"\n  GOLD {tf}")
        print(f"  {'parameter':<12}{'-30%':>26}{'default':>26}{'+30%':>26}")
        for pname, vals in grid:
            cells = ""
            for v in vals:
                kw = {pname: v}
                n, e, t, med, p95 = edge(s, costs, **kw)
                cells += f"{f'{v}: {e-med:+.3f} (n={n})':>26}"
            print(f"  {pname:<12}{cells}")


if __name__ == "__main__":
    main()

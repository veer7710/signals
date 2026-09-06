"""SKILL-FREE NULL. Same code, same geometry, same cost, on synthetic bars from
a DRIFTLESS random walk calibrated to the real M1 series. If the simulation
reports the same edge here, the edge is the simulation, not the market."""
import os, sys, random, statistics, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adv_harness as H
from engine import Series, atr as watr


def synth(n, sigma_tick, ticks, seed, p0=1300.0):
    """Bar OHLC built from a tick-level driftless walk - the honest way to get
    realistic highs and lows (a Gaussian-OHLC fake would understate range)."""
    rng = random.Random(seed)
    ts, o, h, l, c = [], [], [], [], []
    p = p0
    t0 = 1514847600
    for i in range(n):
        op = p
        hi = lo = p
        for _ in range(ticks):
            p += rng.gauss(0.0, sigma_tick)
            if p > hi: hi = p
            if p < lo: lo = p
        ts.append(t0 + 60 * i); o.append(op); h.append(hi); l.append(lo); c.append(p)
    return Series(ts, o, h, l, c)


def main():
    s, SP, A, cs = H.ctx("M1")
    SPC0 = [x * cs for x in SP]
    # calibrate: match the real series' median ATR14 and median bar range
    ra = sorted(x for x in watr(s, 14)[100:] if x)
    med_atr = ra[len(ra) // 2]
    rr = sorted(s.h[i] - s.l[i] for i in range(len(s)))
    med_rng = rr[len(rr) // 2]
    med_sp = statistics.median(SPC0)
    ticks = 120
    # tune sigma_tick so median synthetic bar range matches the real one
    sig = med_rng / (2.0 * math.sqrt(ticks))
    for _ in range(14):
        t = synth(20000, sig, ticks, 1)
        m = sorted(t.h[i] - t.l[i] for i in range(len(t)))[10000]
        sig *= (med_rng / m) ** 0.5
    t = synth(30000, sig, ticks, 1)
    m = sorted(t.h[i] - t.l[i] for i in range(len(t)))[15000]
    ta = sorted(x for x in watr(t, 14)[100:] if x)
    print(f"  calibration: real median bar range {med_rng:.4f} / ATR14 {med_atr:.4f}")
    print(f"               synth median bar range {m:.4f} / ATR14 {ta[len(ta)//2]:.4f}")
    print(f"  cost held identical: flat spread {med_sp:.5f} (the real median charged spread)\n")

    H.hdr("SWEEP on a DRIFTLESS RANDOM WALK (same code, same cost)", 34)
    r = H.simulate(s, SPC0, H.sweep_candidates(s, A, SPC0))
    H.line("REAL M1 gold 2018", r, 34)
    pers = []
    N = len(s)
    for sd in range(8):
        ss = synth(N, sig, ticks, 100 + sd)
        AA = watr(ss, 14)
        SPC = [med_sp] * len(ss)
        rr2 = H.simulate(ss, SPC, H.sweep_candidates(ss, AA, SPC))
        z = H.summ(rr2)
        pers.append(z["per"])
        H.line(f"synthetic walk seed {sd}", rr2, 34)
    mm = sum(pers) / len(pers)
    se = (sum((x - mm) ** 2 for x in pers) / (len(pers) - 1)) ** 0.5 / len(pers) ** 0.5
    real = H.summ(r)["per"]
    print(f"\n  null mean per trade {mm:+.4f}  (sd across seeds "
          f"{(sum((x-mm)**2 for x in pers)/(len(pers)-1))**0.5:.4f}, se {se:.4f})")
    print(f"  real per trade      {real:+.4f}")
    print(f"  REAL MINUS NULL     {real-mm:+.4f}   = {(real-mm)/se:.1f} null-mean se")
    print(f"  seeds beating the real result: {sum(1 for x in pers if x >= real)}/{len(pers)}")


main()

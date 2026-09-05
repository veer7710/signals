"""
E-125 — THE SUPERTREND RESCUE. Tested as a component, not as a trigger.

Every earlier test in this repo (E-112, E-113, E-114, E-115, E-116, E-117) used
SuperTrend ONE way: the flip as an ENTRY TRIGGER. All were negative, including at
zero cost. But a flip-trigger is only one of a dozen jobs the indicator can hold,
and killing the whole thing on that basis is a mistake.

SuperTrend is a volatility-adjusted trend STATE. Its natural jobs are:
   DIRECTIONAL FILTER   trade only with (or only against) the prevailing state
   TRAILING MECHANISM   the band is a ready-made structural trail
   REGIME DETECTOR      flip density measures chop directly
   EXIT                 leave when the state turns against the position

So it is tested here as each of those, ON TOP OF the one edge this project has
actually proven: M15 liquidity zones swept and executed on M1 (E-121, +441
points against a time-shifted control, 21.5 se).

BASELINE = the zone system alone. A component is kept ONLY if it beats that
baseline out of sample. Judged in POINTS (E-074), threshold-free where possible,
and every keep/refuse decision is scored on data it did not choose.
"""
from __future__ import annotations
import os, sys, statistics, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
from engine import atr as watr
from liq_m1 import load, build_zones, GBP

TODAY = 7.38          # measured M15 ATR growth 2018 -> today (DATA_QUALITY.md)


def st_state(s, atr_len, mult):
    """SuperTrend direction per bar. -1 bullish, +1 bearish (Pine convention)."""
    A = watr(s, atr_len)
    n = len(s); d = [0]*n; fu = [None]*n; fl = [None]*n
    for i in range(n):
        a = A[i]
        if a is None or a <= 0: continue
        mid = (s.h[i]+s.l[i])/2.0
        bu, bl = mid+mult*a, mid-mult*a
        if i == 0 or fu[i-1] is None:
            fu[i], fl[i] = bu, bl; d[i] = 1; continue
        pu, pl, pc = fu[i-1], fl[i-1], s.c[i-1]
        fu[i] = bu if (bu < pu or pc > pu) else pu
        fl[i] = bl if (bl > pl or pc < pl) else pl
        d[i] = d[i-1]
        if d[i-1] == 1 and s.c[i] > fu[i]: d[i] = -1
        elif d[i-1] == -1 and s.c[i] < fl[i]: d[i] = 1
    return d, fu, fl


def main():
    s1, SP1 = load("M1"); s15, _ = load("M15")
    A1 = watr(s1, 14)
    va = sorted(x for x in A1[100:] if x); med_a = va[len(va)//2]
    med_sp = statistics.median(SP1)
    cs = 0.11/(med_sp/med_a)                 # scale cost to today's ECN regime
    idx = {t: i for i, t in enumerate(s1.ts)}
    ts15 = {t: i for i, t in enumerate(s15.ts)}

    # SuperTrend on BOTH timeframes: M15 for state, M1 for the trail
    d15, _, _ = st_state(s15, 7, 1.2)
    d1, fu1, fl1 = st_state(s1, 7, 1.2)
    flip1 = [0]*len(s1)
    for i in range(1, len(s1)):
        if d1[i] != d1[i-1]: flip1[i] = 1

    # ---- collect every filled sweep once, with all features and the raw path
    recs = []
    busy = -1
    for z in build_zones(s15, k=3):
        i0 = idx.get(z["known_ts"]); b = ts15.get(z["known_ts"])
        if i0 is None or b is None or i0 <= busy: continue
        a = A1[i0]
        if not a or a <= 0: continue
        side = 1 if z["dir"] == -1 else -1
        lvl = z["px"] - side*0.5*a
        j = None
        for k in range(i0+1, min(i0+61, len(s1))):
            if s1.ts[k] > z["dead_ts"]: break
            if (side == 1 and s1.l[k] <= lvl) or (side == -1 and s1.h[k] >= lvl):
                j = k; break
        if j is None: continue
        rng = max(s1.h[j]-s1.l[j], 1e-9)
        wick = ((min(s1.o[j], s1.c[j])-s1.l[j]) if side > 0
                else (s1.h[j]-max(s1.o[j], s1.c[j])))/rng
        # SuperTrend state on M15 at the moment of the fill (bar b, no future)
        st15 = d15[b]
        with_trend = (st15 == -1 and side > 0) or (st15 == 1 and side < 0)
        chop = sum(flip1[max(0, j-60):j])     # M1 flips in the last hour
        recs.append({"j": j, "side": side, "lvl": lvl, "a": a,
                     "wick": wick, "with_trend": with_trend, "chop": chop})
        busy = j + 120

    print("="*94)
    print(f"  E-125 — SUPERTREND AS A COMPONENT. {len(recs)} filled M15-zone sweeps.")
    print(f"  Baseline = the zone system alone. Cost = today's ECN regime.")
    print("="*94)

    def sim(sel, exit_mode, stop_a=4.0, give=0.25, hold=240):
        tot = []
        for r in sel:
            j, side, lvl, a = r["j"], r["side"], r["lvl"], r["a"]
            sp = SP1[j]*cs; entry = lvl + side*sp/2.0
            sl = entry - side*stop_a*a
            post = (s1.o[j] <= lvl) if side > 0 else (s1.o[j] >= lvl)
            peak = 0.0; armed = None; px = None
            for k in range(j, min(j+hold, len(s1))):
                if (side > 0 and s1.l[k] <= sl) or (side < 0 and s1.h[k] >= sl):
                    px, kk = sl, k; break
                ok = (k > j) or post
                if exit_mode == "st_trail":
                    # the SuperTrend band itself is the stop, ratcheted one way
                    band = fl1[k] if side > 0 else fu1[k]
                    if band is not None:
                        sl = max(sl, band) if side > 0 else min(sl, band)
                elif exit_mode == "st_flip":
                    if k > j and flip1[k] and ((side > 0 and d1[k] == 1) or
                                              (side < 0 and d1[k] == -1)):
                        px, kk = s1.c[k], k; break
                if exit_mode == "give" and ok:
                    if armed is not None:
                        w = s1.l[k] if side > 0 else s1.h[k]
                        if side*(w-armed) <= 0: px, kk = armed, k; break
                    f = side*((s1.h[k] if side > 0 else s1.l[k])-entry)
                    if f > peak:
                        peak = f
                        if peak*(1-give) > SP1[k]*cs:
                            armed = entry + side*peak*(1-give)
            if px is None:
                kk = min(j+hold, len(s1)-1); px = s1.c[kk]
            tot.append(side*((px-side*SP1[kk]*cs/2.0)-entry))
        return tot

    def line(name, sel, mode):
        if len(sel) < 30:
            print(f"  {name:<40} {len(sel):>5}   too few"); return None
        r = sim(sel, mode); p = sum(r)
        w = 100.0*sum(1 for x in r if x > 0)/len(r)
        print(f"  {name:<40} {len(sel):>5} {w:>6.1f}% {p:>9.1f} "
              f"{p*TODAY*GBP:>9.2f}")
        return p

    print(f"\n  1. SUPERTREND AS AN EXIT / TRAIL  (all {len(recs)} sweeps)")
    print(f"  {'exit mechanism':<40} {'n':>5} {'win%':>7} {'points':>9} {'£ today':>9}")
    print("  "+"-"*74)
    base = line("25% giveback (baseline)", recs, "give")
    line("M1 SuperTrend band as trail", recs, "st_trail")
    line("exit on opposite M1 SuperTrend flip", recs, "st_flip")

    print(f"\n  2. SUPERTREND AS A DIRECTIONAL FILTER  (M15 state at the fill)")
    print(f"  {'selection':<40} {'n':>5} {'win%':>7} {'points':>9} {'£ today':>9}")
    print("  "+"-"*74)
    line("all sweeps (baseline)", recs, "give")
    line("only WITH the M15 SuperTrend", [r for r in recs if r["with_trend"]], "give")
    line("only AGAINST it (fade the trend)", [r for r in recs if not r["with_trend"]], "give")

    print(f"\n  3. SUPERTREND AS A CHOP DETECTOR  (M1 flips in the prior hour)")
    print(f"  {'selection':<40} {'n':>5} {'win%':>7} {'points':>9} {'£ today':>9}")
    print("  "+"-"*74)
    ch = sorted(r["chop"] for r in recs)
    lo, hi = ch[len(ch)//3], ch[2*len(ch)//3]
    line("all sweeps (baseline)", recs, "give")
    line(f"QUIET: <= {lo} flips/hr", [r for r in recs if r["chop"] <= lo], "give")
    line(f"CHOPPY: >= {hi} flips/hr", [r for r in recs if r["chop"] >= hi], "give")

    print(f"\n  4. COMBINED with the one filter that survived OOS (E-124 wick)")
    print(f"  {'selection':<40} {'n':>5} {'win%':>7} {'points':>9} {'£ today':>9}")
    print("  "+"-"*74)
    wc = sorted(r["wick"] for r in recs)[int(len(recs)*0.75)]
    line("wick filter alone", [r for r in recs if r["wick"] >= wc], "give")
    line("wick + with-trend", [r for r in recs if r["wick"] >= wc and r["with_trend"]], "give")
    line("wick + quiet", [r for r in recs if r["wick"] >= wc and r["chop"] <= lo], "give")

    json.dump([{k: v for k, v in r.items()} for r in recs],
              open("/tmp/claude-0/-home-user-signals/6ed3e965-d728-5c44-94ac-73a8079dc33a/scratchpad/sweeps.json", "w"))
    print(f"\n  (sweep records cached for the out-of-sample pass)")


if __name__ == "__main__":
    main()

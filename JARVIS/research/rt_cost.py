"""
RED TEAM / E-063. The claim 'the spread is 61% of the way to the stop' is
one ratio:   cost/stop = (spread + 2*slip) / (stopAtrMult * ATR_M1)
Two inputs: the spread (0.46, off a screenshot of a DIFFERENT broker's chart)
and ATR_M1 (~0.5, eyeballed from one 24-minute screenshot Veer posted BECAUSE
it was the worst chop of the day).

Three things measured here rather than assumed:
 1. the VOLATILITY SCALING EXPONENT in this repo's own data. E-053 and E-063
    both extrapolate ATR down to M1 with sqrt(time), i.e. exponent 0.5. If the
    true exponent is below 0.5, M1 ATR is LARGER than assumed and every M1
    cost figure in this project is too pessimistic. Measured by aggregating
    15m -> 30m -> 1h -> 2h -> 4h and fitting log(ATR) on log(bars).
 2. what GOLD's own ATR actually is at the END of the sample, not the median
    of the whole thing.
 3. the full sensitivity surface of cost/stop in (spread, ATR_M1), so the
    exact contour where the conclusion flips is visible.
"""
from __future__ import annotations
import os, sys, math, statistics, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study

def med_atr(s, n=7):
    a = [x for x in engine.atr(s, n)[100:] if x]
    return statistics.median(a)

def main():
    print("=" * 92)
    print("  RED TEAM / E-063  —  the volatility scaling exponent, measured")
    print("=" * 92)
    print("  If ATR scales as (bar minutes)^k, E-053/E-063 assume k = 0.500.")
    print(f"  {'symbol':<9}{'base tf':>9}" + "".join(f"{f'x{m}':>10}" for m in (1,2,4,8,16))
          + f"{'fitted k':>11}{'ATR_M1 @k':>11}{'ATR_M1 @0.5':>13}")
    for sym in ("GOLD", "US500", "EURUSD", "GBPUSD"):
        for tf, mins in (("15m", 15), ("1h", 60)):
            try:
                s = engine.load(sym, tf)
            except Exception:
                continue
            xs, ys, cells = [], [], []
            for f in (1, 2, 4, 8, 16):
                ss = engine.resample(s, f) if f > 1 else s
                if len(ss) < 400:
                    cells.append(f"{'-':>10}"); continue
                a = med_atr(ss)
                cells.append(f"{a:>10.4f}")
                xs.append(math.log(mins * f)); ys.append(math.log(a))
            if len(xs) < 3:
                continue
            mx, my = statistics.mean(xs), statistics.mean(ys)
            k = sum((x-mx)*(y-my) for x, y in zip(xs, ys)) / sum((x-mx)**2 for x in xs)
            a0 = med_atr(s)
            m1_k = a0 * (1.0/mins) ** k
            m1_h = a0 * (1.0/mins) ** 0.5
            print(f"  {sym:<9}{tf:>9}" + "".join(cells)
                  + f"{k:>11.3f}{m1_k:>11.4f}{m1_h:>13.4f}")

    # ---- 2. gold volatility over time: is the sample period really 4x hotter?
    print("\n" + "=" * 92)
    print("  GOLD 15m — median bar RANGE and median ATR(7) by month")
    print("=" * 92)
    s = engine.load("GOLD", "15m")
    A = engine.atr(s, 7)
    buckets = {}
    for i in range(100, len(s)):
        d = datetime.datetime.fromtimestamp(s.ts[i], datetime.timezone.utc)
        k = f"{d.year}-{d.month:02d}"
        buckets.setdefault(k, []).append((s.h[i]-s.l[i], A[i], s.c[i]))
    print(f"  {'month':<10}{'bars':>7}{'med range':>12}{'med ATR7':>11}{'close':>11}"
          f"{'ATR/close bp':>14}")
    for k in sorted(buckets):
        v = buckets[k]
        print(f"  {k:<10}{len(v):>7}{statistics.median(x[0] for x in v):>12.3f}"
              f"{statistics.median(x[1] for x in v):>11.3f}"
              f"{statistics.median(x[2] for x in v):>11.1f}"
              f"{10000*statistics.median(x[1] for x in v)/statistics.median(x[2] for x in v):>14.1f}")

    # ---- 3. the sensitivity surface
    print("\n" + "=" * 92)
    print("  cost/stop SURFACE at a 1.5xATR stop. Cells are cost/stop.")
    print("  E-053's own table: >0.40 lost ~1/3 R per trade; <0.07 was positive.")
    print("=" * 92)
    atrs = [0.30, 0.50, 0.80, 1.10, 1.50, 1.90]
    print(f"  {'spread':<9}" + "".join(f"{f'ATR={a}':>11}" for a in atrs))
    for spread in (0.12, 0.20, 0.30, 0.46, 0.60):
        row = f"  {spread:<9.2f}"
        for a in atrs:
            rt = spread + 2*0.05
            row += f"{rt/(1.5*a):>11.3f}"
        print(row)
    print("\n  The same surface with the EA's OWN slippage model")
    print("  (InpSlipSpreads=0.25, so round trip = 1.5 x spread):")
    print(f"  {'spread':<9}" + "".join(f"{f'ATR={a}':>11}" for a in atrs))
    for spread in (0.12, 0.20, 0.30, 0.46, 0.60):
        row = f"  {spread:<9.2f}"
        for a in atrs:
            row += f"{(1.5*spread)/(1.5*a):>11.3f}"
        print(row)
    print("\n  Under the EA's own model cost/stop reduces EXACTLY to spread/ATR")
    print("  at a 1.5xATR stop: both 1.5s cancel. The whole of E-063 is that ratio.")

if __name__ == "__main__":
    main()

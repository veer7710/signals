"""RED TEAM / E-063 input check. Veer's ATR estimate came from ONE 24-minute
screenshot at 20:04-20:28, chosen BECAUSE it was the worst chop of the day.
Measure how much of gold's volatility is hour-of-day, so it is clear how much
of the 4x gap between E-053's extrapolation and E-063's eyeball is the CLOCK
rather than the regime."""
from __future__ import annotations
import os, sys, math, statistics, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine

s = engine.load("GOLD", "15m")
A = engine.atr(s, 7)
by = {}
for i in range(100, len(s)):
    h = datetime.datetime.fromtimestamp(s.ts[i], datetime.timezone.utc).hour
    if A[i]: by.setdefault(h, []).append(A[i])
allm = statistics.median(x for v in by.values() for x in v)
print("=" * 96)
print("  GOLD 15m ATR(7) BY UTC HOUR   (whole-sample median ATR15 = %.3f)" % allm)
print("  ATR_M1 columns: measured k=0.535 (this repo's own fit) and sqrt(15).")
print("  cost/stop = spread / ATR_M1 at a 1.5xATR stop, EA slippage model.")
print("=" * 96)
print(f"  {'UTC hr':<7}{'n':>6}{'medATR15':>10}{'vs day':>8}{'ATR_M1 k':>10}"
      f"{'ATR_M1 sqrt':>13}{'c/s @0.46':>11}{'c/s @0.20':>11}{'c/s @0.12':>11}")
for h in sorted(by):
    v = by[h]; m = statistics.median(v)
    m1k = m * (1.0/15.0) ** 0.535
    m1s = m / math.sqrt(15.0)
    print(f"  {h:<7}{len(v):>6}{m:>10.3f}{m/allm:>8.2f}{m1k:>10.3f}{m1s:>13.3f}"
          f"{0.46/m1k:>11.3f}{0.20/m1k:>11.3f}{0.12/m1k:>11.3f}")
lo = min(by, key=lambda h: statistics.median(by[h]))
hi = max(by, key=lambda h: statistics.median(by[h]))
print(f"\n  quietest hour {lo:02d}:00 = {statistics.median(by[lo]):.3f}   "
      f"busiest hour {hi:02d}:00 = {statistics.median(by[hi]):.3f}   "
      f"ratio {statistics.median(by[hi])/statistics.median(by[lo]):.2f}x")
print("  Veer's screenshot window 19:00-21:00 UTC med ATR15 = %.3f (%.2fx the day)"
      % (statistics.median([x for h in (19,20) for x in by.get(h,[])]),
         statistics.median([x for h in (19,20) for x in by.get(h,[])])/allm))

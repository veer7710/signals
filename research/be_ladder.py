"""
"this EA expects us to go into 6 pound or more when a majority of trades only
 reach 0 to 5... I want us moving closer to breakeven as we go into profit
 then trail hard where needed."

He is describing a calibration error, and his own peak distribution says he is
right. Test the ladder against it before building it.
"""
import sys, numpy as np
sys.path.insert(0,"research")
from bank_vs_trail import sample_peaks, N, AVG_LOSS

peaks = sample_peaks()
BAND_002 = 1.18 * 0.733 * 2          # noise band in GBP at 0.02 lots

print("="*78)
print("WHERE YOUR PEAKS ACTUALLY ARE  (measured, 279 trades)")
print("="*78)
for t in (1,2,3,4,5,6,8):
    print(f"   reaches GBP{t:<3}  {100*(peaks>=t).mean():>5.1f}%   {(peaks>=t).mean()*N:>3.0f} per 275")
print(f"\n   75th percentile of peaks: GBP{np.percentile(peaks,75):.2f}")
print(f"   one noise band at 0.02 lots: GBP{BAND_002:.2f}")
print(f"\n   An exit that waits for GBP6 is waiting for something that happens")
print(f"   {100*(peaks>=6).mean():.1f}% of the time. You were right.")

def ladder(p, be_at, lock_at, keep_lo, hard_at, keep_hi):
    """BE first, then progressively harder locks."""
    if p < be_at:  return -AVG_LOSS          # never reached breakeven
    if p < lock_at: return 0.0               # scratched at BE
    if p < hard_at: return p * keep_lo
    return p * keep_hi

def flat(p, arm, keep):
    if p < arm: return -AVG_LOSS
    return p * keep

print("\n"+"="*78)
print("WHAT EACH EXIT SHAPE IS WORTH ON THOSE SAME PEAKS")
print("="*78)
print(f"   {'exit':<46}{'win%':>7}{'scratch%':>10}{'net/275':>10}")
rows=[]
for name, fn in [
  ("current: arm 2 bands, keep 65-90%",
     lambda p: flat(p, 2*BAND_002, 0.78)),
  ("wait for GBP6 then keep 90%",
     lambda p: flat(p, 6.0, 0.90)),
  ("BE 0.75 band, lock 50% at 1.5, hard 75% at 3",
     lambda p: ladder(p, 0.75*BAND_002, 1.5*BAND_002, 0.50, 3*BAND_002, 0.75)),
  ("BE 0.75 band, lock 65% at 1.5, hard 85% at 3",
     lambda p: ladder(p, 0.75*BAND_002, 1.5*BAND_002, 0.65, 3*BAND_002, 0.85)),
  ("BE 0.5 band, lock 65% at 1.0, hard 85% at 2.5",
     lambda p: ladder(p, 0.5*BAND_002, 1.0*BAND_002, 0.65, 2.5*BAND_002, 0.85)),
  ("BE 1.0 band, lock 65% at 2.0, hard 85% at 4",
     lambda p: ladder(p, 1.0*BAND_002, 2.0*BAND_002, 0.65, 4*BAND_002, 0.85)),
]:
    v = np.array([fn(p) for p in peaks[:60000]])
    rows.append((v.mean()*N, name, (v>0).mean(), (v==0).mean()))
for net, name, w, sc in sorted(rows, reverse=True):
    print(f"   {name:<46}{100*w:>6.1f}%{100*sc:>9.1f}%{net:>10.1f}")

best = max(rows)
print(f"\n   best: {best[1]}")
print(f"\n   The scratch column is the point. A trade that reaches breakeven and")
print(f"   then fails costs ZERO instead of GBP1.73. On a distribution where")
print(f"   {100*(peaks>=0.75*BAND_002).mean():.0f}% of trades get that far, turning those losses into")
print(f"   scratches is worth more than any change to what the winners keep.")

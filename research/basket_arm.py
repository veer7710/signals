"""
BASKET-LOCK is the best mechanism in QUAD and it almost never fires.
What does lowering T_BasketArmCash actually buy?
"""
import numpy as np, sys
sys.path.insert(0,"research")
from bank_vs_trail import sample_peaks, N

peaks = sample_peaks()
print("="*78)
print("THE ONE EXIT THAT WORKS, AND HOW RARELY IT GETS TO WORK")
print("="*78)
print("  exit attribution, reference day (brief, Part 2):")
print(f"  {'exit':<14}{'n':>5}{'peak pts':>10}{'net pts':>10}{'kept':>8}")
for nm,n,net,gb in [("SL-HIT",109,-54.7,-228.1),("BASKET-LOCK",15,25.4,-0.6)]:
    pk = net-gb
    print(f"  {nm:<14}{n:>5}{pk:>10.1f}{net:>10.1f}{100*net/pk:>7.0f}%")
print("\n  BASKET-LOCK kept 98%. SL-HIT gave back its entire peak and more.")
print("  BASKET-LOCK fired 15 times out of 279 = 5.4% of trades.")
print("  It is not that the mechanism is rare-by-nature. It arms at GBP5.")

print("\n"+"="*78)
print("COVERAGE vs ARM LEVEL, on your measured peak distribution")
print("="*78)
print(f"  {'arm at':>8}{'% of trades reaching it':>26}{'per 275':>10}{'vs GBP5':>10}")
base = (peaks>=5).mean()
for a in (1.0,1.5,2.0,2.5,3.0,3.5,4.0,5.0):
    pr = (peaks>=a).mean()
    print(f"  {'GBP'+str(a):>8}{100*pr:>25.1f}%{pr*N:>10.0f}{pr/base:>9.1f}x")
print("\n  Dropping the arm from GBP5 to GBP2 puts the 98%-keeping mechanism")
print(f"  in charge of {(peaks>=2).mean()/base:.1f}x as many trades.")

print("\n"+"="*78)
print("WHY IT IS SET AT 5, AND WHAT THE FILE'S OWN MATHS SAYS")
print("="*78)
ATR, SPREAD, NF = 1.47, 0.30, 0.60
band_pts = SPREAD + NF*ATR
print(f"  band = spread + {NF} x ATR = {SPREAD} + {NF}x{ATR} = {band_pts:.2f} pts")
for lots in (0.01,0.02,0.03,0.06,0.12):
    band_gbp = band_pts*0.733*(lots/0.01)
    arm_band = 2.0*band_gbp
    arm_real = max(5.0, arm_band)
    print(f"    {lots:.2f} lots: band GBP{band_gbp:5.2f}  band-arm GBP{arm_band:5.2f}"
          f"  ACTUAL arm GBP{arm_real:5.2f}"
          f"{'   <- cash floor binds' if arm_real==5.0 else ''}")
print("\n  The band arithmetic (2 bands to guarantee 1 after giving 1 back) is")
print("  sound. The GBP5 CASH FLOOR overrides it at every size you trade.")
print("  At 0.02 lots the maths wants GBP3.46; the floor forces GBP5.")
print("\n  T_BasketArmCash = 0 hands the decision back to the band arithmetic,")
print("  which scales with your size and with volatility instead of being a")
print("  number picked once for one balance.")

print("\n"+"="*78)
print("AND THIS IS WHY YOUR TWO COMPLAINTS ARE DIFFERENT MECHANISMS")
print("="*78)
print('  "near GBP5 I see trades close"        -> T_BasketArmCash = 5.0.')
print("                                           Working as designed. Keeps 98%.")
print('  "up GBP4 and it closes at GBP2"       -> NOT the basket. That is the')
print("                                           per-trade give-back / SL-HIT path,")
print("                                           which kept -32% of its peak.")
print("\n  So the fix is not to remove the GBP5 close. It is to put the")
print("  BASKET-LOCK logic in charge of EVERY trade, at an arm derived from")
print("  the band rather than a fixed GBP5.")

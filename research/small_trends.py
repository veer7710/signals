"""
"we basically just catch every trend on M1 and often we are late as they are so
 small... but sometimes it does go up there, seen some rockets go to 30 pound."

Both halves are true and they are not in tension. Work out which one the
peak distribution was actually measuring.
"""
GBP001 = 0.733
ATR_M1 = 1.47

print("="*78)
print("1. WHAT THE MARKET OFFERED vs WHAT THE EA CAPTURED")
print("="*78)
print("  Brief, Finding 6:  16 ten-point excursions in 16.7 hours,")
print("                     MEDIAN DURATION 42 MINUTES.")
print("                     Average hold: 4 minutes.")
print()
for lots in (0.01, 0.02, 0.03):
    v = 10 * GBP001 * (lots/0.01)
    print(f"    a 10-point excursion at {lots} lots = GBP {v:5.2f}")
print(f"    a 20-point excursion at 0.02 lots = GBP {20*GBP001*2:.2f}")
print()
print("  So GBP30 rockets are NOT rare. A 20-pt move at 0.02 is GBP29.32, and")
print("  the tape produced SIXTEEN ten-point moves in one session.")
print()
print("  >>> THE PEAK DISTRIBUTION I BUILT MEASURED WHAT THE EA CAPTURED,")
print("      NOT WHAT THE MARKET OFFERED. Mean peak GBP1.07 against a tape")
print("      carrying a 10-point move roughly every hour. The EA was not")
print("      present for them -- it had already left.")

print("\n"+"="*78)
print("2. THE DOUBLE LOSS: A SMALL MOVE, ENTERED LATE")
print("="*78)
print("  His description: M1 trends are small, AND we are late into them.")
print("  Those multiply, they do not add.\n")
print(f"  {'trend size':>12}{'late by':>10}{'captured':>11}{'% of move':>11}{'at 0.02':>10}")
for trend in (3.0, 5.0, 8.0):
    for late in (0.5, 1.0, 1.5):
        cap = trend - late
        print(f"  {trend:>10.1f}p{late:>9.1f}p{cap:>10.1f}p{100*cap/trend:>10.0f}%"
              f"{cap*GBP001*2:>10.2f}")
print()
print("  A 3-point trend entered 1.5 points late gives up HALF the move before")
print("  the exit logic has done anything at all. That is the arithmetic behind")
print("  'we capture a small amount'. It is an ENTRY loss, not an exit loss.")

print("\n"+"="*78)
print("3. SO THE TWO FIXES ARE NOT THE SAME FIX")
print("="*78)
print("  BREAKEVEN LADDER  fixes the bleed: ~9% of trades reach breakeven and")
print("                    then fail. Those become scratches instead of losses.")
print("                    Worth about +142 per 275 trades. Still true.")
print()
print("  HOLD TIME         fixes the ceiling. A 42-minute move cannot be caught")
print("                    by a 4-minute hold, no matter how good the entry or")
print("                    the lock. This is why the peaks look small.")
print()
print("  THE LADDER MUST NOT CAP THE ROCKET. Check that it does not:")
for peak in (2.0, 5.0, 10.0, 20.0, 30.0):
    band = 1.73                       # one noise band at 0.02 lots
    if peak >= 2.5*band:  keep, stage = 0.85, "lock 85%"
    elif peak >= 1.0*band: keep, stage = 0.65, "lock 65%"
    elif peak >= 0.5*band: keep, stage = 0.0,  "breakeven"
    else: keep, stage = None, "nothing armed"
    if keep is None:
        print(f"    peak GBP{peak:5.2f} -> {stage}")
    else:
        locked = peak*keep
        print(f"    peak GBP{peak:5.2f} -> {stage:<10} stop locks GBP{locked:6.2f}"
              f"   still running, gives back GBP{peak-locked:5.2f}")
print()
print("  The lock TRAILS the peak, it never caps it. A GBP30 rocket locks")
print("  GBP25.50 and keeps going. Nothing in the ladder closes a runner.")
print("  What closes runners is the TIME STOP -- that is the thing to check.")

"""
What the four live M1 screenshots (15 Sep 18:23-20:04) actually show.
Measured off the price axes in the images, not inferred.
"""
GBP_PER_PT_001 = 0.733
ATR_M1 = 1.47
SPREAD_RT = 0.30

print("="*76)
print("1. SIZE / P-L CROSS-CHECK  (confirms the screenshots are self-consistent)")
print("="*76)
# img1: BUY 0.02 showing +0.98 GBP ; img2: BUY 0.02 showing -0.34 GBP
for lots, gbp in [(0.02, 0.98), (0.02, -0.34)]:
    pts = gbp / (GBP_PER_PT_001 * lots/0.01)
    print(f"  {lots} lots  {gbp:+.2f} GBP  =  {pts:+.2f} pts  ({pts/ATR_M1:+.2f} ATR)")
print("  -> GBP/pt at 0.02 = %.3f. Matches the brief's 0.733 at 0.01." %
      (GBP_PER_PT_001*2))

print("\n"+"="*76)
print("2. THE STOP IS ~1.1 ATR  (read off the SL lines)")
print("="*76)
for entry, sl in [(4289.82, 4288.19), (4289.91, 4288.21)]:
    d = entry - sl
    print(f"  entry {entry}  SL {sl}  =  {d:.2f} pts = {d/ATR_M1:.2f} ATR"
          f" = GBP {d*GBP_PER_PT_001*2:.2f} at 0.02")
print("  -> the stop geometry is sane. The stop is NOT the problem.")

print("\n"+"="*76)
print("3. WHIPSAW COST  (image 4: ~20 arrows between 18:52 and 20:04)")
print("="*76)
mins, sigs = 72, 20
per_h = sigs/(mins/60.0)
print(f"  {sigs} signals in {mins} min = one every {mins/sigs:.1f} min = {per_h:.1f}/hour")
for lots in (0.01, 0.02, 0.03):
    cost_h = per_h * SPREAD_RT * GBP_PER_PT_001 * (lots/0.01)
    print(f"    at {lots} lots: GBP {cost_h:5.2f}/hour of spread"
          f"  = GBP {cost_h*8:6.2f} over an 8h session")
rng = 4297.30-4285.60
print(f"\n  price range across image 4 = {rng:.2f} pts in {mins} min")
print(f"  spread paid at 0.02 over that window = {per_h*(mins/60.0)*SPREAD_RT*GBP_PER_PT_001*2:.2f} GBP"
      f" = {per_h*(mins/60.0)*SPREAD_RT:.2f} pts")
print(f"  -> you are paying {100*per_h*(mins/60.0)*SPREAD_RT/rng:.0f}% of the whole move in spread,")
print(f"     before a single trade is right or wrong.")

print("\n"+"="*76)
print("4. THE SPIKE-TOP ENTRIES  (images 1-3, the 18:53 candle)")
print("="*76)
print("  18:53 candle ran 4290.10 -> 4294.52 = 4.42 pts = 3.0 ATR in one bar.")
print("  A blue BUY arrow sits at ~4291.9-4292.5, i.e. INSIDE that candle,")
print("  and the next arrow is a red SELL ~2 bars later at ~4289.6-4289.9.")
buy_at, sell_at = 4292.20, 4289.75
print(f"  buy {buy_at} -> sell {sell_at} = {sell_at-buy_at:+.2f} pts"
      f" = GBP {(sell_at-buy_at)*GBP_PER_PT_001*2:+.2f} at 0.02, before spread")
print("  -> this is the 'signals on big candles' fault, on camera.")
print("     Buying 3 ATR into a vertical bar is buying the last of the move.")

print("\n"+"="*76)
print("5. THE EQUAL-HIGH STORY  (his words, and it is the real mechanism)")
print("="*76)
print("  'bullish trend hit an equality high, we had entered a buy before,")
print("   it just started dumping, we hit stop loss'")
print()
print("  An equal high is not resistance. It is a SHELF OF RESTING SELL ORDERS")
print("  plus the stops of everyone long underneath it. Price is ATTRACTED to")
print("  it, trades through it to fill them, and then reverses. Buying INTO an")
print("  untested equal high means buying the liquidity that the move exists")
print("  to collect.")
print()
print("  So the rule is not 'avoid resistance'. It is:")
print("    do not OPEN a long whose room-to-target is less than the distance")
print("    to the nearest untested equal high; and once price is within that")
print("    distance, stop adding and tighten.")
print("  After the sweep, the same level becomes tradeable in the OTHER")
print("  direction -- which is exactly the absorption test already in SNIPER.")

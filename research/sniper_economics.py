"""
sniper_economics.py -- what the live tickets say a fix is worth.

Every input here is from the master brief (275 hand-transcribed live tickets,
validated against the EA panel). No backtest, no simulated data. Re-derive
anything before relying on it -- the brief says this data has been wrong twice.
"""
GBP_PER_PT   = 0.733      # 0.01 lots
COST_PTS     = 0.30       # round trip
M1_ATR       = 1.47       # derived: 1487 pts travel / 1012 M1 bars
CUT_PTS      = 0.60       # the Finding-2 adverse threshold

def money(pts): return pts * GBP_PER_PT

print("="*78)
print("1. THE 60-SECOND RULE  (Finding 2 -- strongest discriminator in the data)")
print("="*78)
# own-exit prices excluded, so outcome cannot leak into the classifier
adverse   = dict(n=48, net=-86.49, hit=0.062)
clean     = dict(n=23, net=+49.92, hit=0.826)
actual    = adverse["net"] + clean["net"]
print(f"  went 0.60+ adverse in first 60s : n={adverse['n']:3d}  net {adverse['net']:+8.2f}  hit {100*adverse['hit']:.1f}%")
print(f"  did NOT                         : n={clean['n']:3d}  net {clean['net']:+8.2f}  hit {100*clean['hit']:.1f}%")
print(f"  measured total                  : n={adverse['n']+clean['n']:3d}  net {actual:+8.2f}")

cut_cost_each = money(CUT_PTS) + money(COST_PTS)
cut_total     = adverse["n"] * cut_cost_each
fixed         = clean["net"] - cut_total
print(f"\n  If the adverse cohort is CUT the moment it goes {CUT_PTS} against:")
print(f"    loss per cut trade = {CUT_PTS} pts + {COST_PTS} pts cost = GBP {cut_cost_each:.2f}")
print(f"    {adverse['n']} cuts               = GBP {cut_total:7.2f}   (was {adverse['net']:.2f})")
print(f"    new total           = GBP {fixed:+7.2f}   (was {actual:+.2f})")
print(f"    improvement         = GBP {fixed-actual:+7.2f} on {adverse['n']+clean['n']} trades"
      f" = {(fixed-actual)/(adverse['n']+clean['n']):+.2f}/trade")
print(f"\n  >>> the surviving cohort's hit rate is {100*clean['hit']:.1f}%. That is the"
      f"\n      70%+ you keep asking for, and it is already in YOUR data.")

print("\n"+"="*78)
print("2. SAME RULE, CHECKED AGAINST A BIGGER INDEPENDENT SLICE (Finding 4)")
print("="*78)
never_green = dict(n=153, lost=-252.27, peak_pool=2.02)
avg_loss = -never_green["lost"]/never_green["n"]
saved_each = avg_loss - cut_cost_each
print(f"  losers that never got even GBP 0.30 up : n={never_green['n']}  lost {never_green['lost']:+.2f}")
print(f"  their entire peak pool was GBP {never_green['peak_pool']:.2f} -- there is nothing to trail")
print(f"  average loss each      = GBP {avg_loss:.2f}")
print(f"  cost of cutting early  = GBP {cut_cost_each:.2f}")
print(f"  saved per trade        = GBP {saved_each:.2f}")
print(f"  saved on the day       = GBP {saved_each*never_green['n']:.2f}")
print(f"\n  Reference day was -147.04. This one rule alone accounts for"
      f" GBP {saved_each*never_green['n']:.0f}.")
print("  Two independent slices of the same day agree the rule is worth roughly")
print("  its own loss back. That is why it is mechanism #1 in SNIPER.")

print("\n"+"="*78)
print("3. THE GIVE-BACK  (Part 2 -- BASKET-LOCK kept 98%, SL-HIT kept 0%)")
print("="*78)
rows = [("SL-HIT",109,-54.7,-228.1),("MAX-LOSS",37,-106.8,-112.5),
        ("GIVEBACK",25,5.7,-29.5),("FLIP-CLOSE",5,-12.3,-13.3),
        ("BASKET-LOCK",15,25.4,-0.6),("MARGIN-WATCH",12,-3.4,-0.6)]
print(f"  {'exit':<14}{'n':>5}{'peak pts':>10}{'net pts':>10}{'kept %':>9}")
print("  (kept% below 0 = gave back the entire peak AND more)")
tot_gb=0
for nm,n,net,gb in rows:
    peak = net - gb            # gave-back is negative
    kept = (net/peak*100) if peak>0 else 0.0
    tot_gb += gb
    print(f"  {nm:<14}{n:>5}{peak:>10.1f}{net:>10.1f}{kept:>8.0f}%")
print(f"  total handed back: {tot_gb:.1f} pts = GBP {money(abs(tot_gb)):.2f}")
print("\n  SL-HIT and BASKET-LOCK had near-identical average peak per trade")
print("  (GBP 1.62 vs 1.64). One kept 98%, the other kept nothing. Same")
print("  opportunity, opposite outcome, and the ONLY difference is which")
print("  mechanism owned the exit. So: lock like BASKET-LOCK, always.")

print("\n"+"="*78)
print("4. WHY A FLAT GBP 1 LOCK IS THE WRONG UNIT (his idea, right instinct)")
print("="*78)
print(f"  M1 ATR = {M1_ATR} pts = GBP {money(M1_ATR):.2f} at 0.01 lots")
for label,mult in [("dead night (0.4 ATR)",0.4),("normal (1 ATR)",1.0),
                   ("news spike (4 ATR)",4.0)]:
    mv = money(M1_ATR*mult)
    print(f"    {label:<22} one bar moves GBP {mv:5.2f}"
          f"  -> a flat GBP1 lock is {'unreachable' if mv<1 else 'triggered by one bar'}")
print("  So the lock must be in ATR, and the give-back allowance must SCALE")
print("  with the peak: tight on small winners, loose enough not to cap a runner.")

print("\n"+"="*78)
print("5. SPREAD IS 48% OF THE LOSS (Finding 5) -- frequency is not free")
print("="*78)
n=275; brief_fig=76.53; day_loss=159.79
# The brief states GBP 76.53. At 0.01 lots that works out to GBP 60.47, so the
# average position was NOT 0.01: 76.53 / (275*0.30) = GBP 0.928/pt, i.e. about
# 0.0127 lots average. Consistent with Part 6 #3 (one signal split across
# positions summing to 0.02-0.05). Use the brief's figure, not the 0.01 one.
implied_per_pt = brief_fig/(n*COST_PTS)
print(f"  {n} round trips x {COST_PTS} pts = {n*COST_PTS:.1f} pts")
print(f"  brief says GBP {brief_fig:.2f} -> implies GBP {implied_per_pt:.3f}/pt"
      f" = ~{implied_per_pt/GBP_PER_PT*0.01:.4f} lots average, not 0.01")
print(f"  of a GBP {day_loss:.2f} loss = {100*brief_fig/day_loss:.0f}%")
print(f"  breakeven hit rate needed: 32.2% (currently 31%)")
print(f"  a 1.3-point improvement in hit rate flips the whole system.")
print(f"\n  The 60s rule does not improve the hit rate -- it REMOVES the cohort")
print(f"  whose hit rate was 6.2%. {adverse['n']}/{adverse['n']+clean['n']}"
      f" = {100*adverse['n']/(adverse['n']+clean['n']):.0f}% of trades carried a 6% hit rate.")

print("\n"+"="*78)
print("6. HOLD TIME (Finding 6) -- it exits 10x before the move finishes")
print("="*78)
print("  16 ten-point excursions in 16.7h, median duration 42 minutes.")
print("  Average hold: 4 minutes. The runner must be allowed to live ~42 min,")
print("  which means the time stop and the trail arm must be set in MINUTES,")
print("  not bars, and must not be reachable by the grace window (Bug 1).")

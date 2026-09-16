"""
"Where else do we enter bad?"

Taxonomy built from the tickets, ranked by what each class actually costs.
Finding 4 is the anchor: 77% of the loss is entries that were wrong
IMMEDIATELY -- 153 trades that never got even GBP0.30 up, with a total peak
pool of GBP2.02 between them. There is no exit fix for those. Only entry.
"""
GBP001, ATR, SPREAD = 0.733, 1.47, 0.30

print("="*80)
print("WHERE THE LOSS ACTUALLY LIVES (Finding 4, his tickets)")
print("="*80)
rows = [("never got GBP0.30 up",153,-252.27,2.02),
        ("got GBP0.30-1.50",      17, -30.76,13.56),
        ("got GBP1.50+",          18, -41.95,79.56)]
tot = sum(r[2] for r in rows)
print(f"  {'cohort':<26}{'n':>5}{'lost':>10}{'peak pool':>11}{'% of loss':>11}{'fixable by':>12}")
for nm,n,lost,pool in rows:
    print(f"  {nm:<26}{n:>5}{lost:>10.2f}{pool:>11.2f}{100*lost/tot:>10.0f}%"
          f"{('EXIT' if pool>40 else 'ENTRY'):>12}")
print(f"\n  -> {100*rows[0][2]/tot:.0f}% of the loss has a peak pool of GBP2.02 across 153 trades.")
print("     You cannot trail your way out of that. It is an ENTRY problem.")

print("\n"+"="*80)
print("THE BAD-ENTRY CLASSES, RANKED BY WHAT THEY COST")
print("="*80)
print("  [built] = already gated in SNIPER   [NEW] = added this pass\n")

items = [
 ("counter-drift", "Finding 3", 97, -109.41,
  "97 trades AGAINST the prior 30m drift lost GBP109.41 (-1.13 each) while 137\n"
  "     WITH it lost GBP20.39 (-0.15 each). 68% of the day's loss from 35% of trades,\n"
  "     identifiable from price alone before entry.", "[built] sized to 0.35x, never refused"),

 ("adverse in first 60s", "Finding 2", 48, -86.49,
  "6.2% hit rate vs 82.6% for everything else. Not selectable in advance --\n"
  "     this is a management rule, not an entry filter.", "[built] fast-fail, shadow by default"),

 ("into an equal-high shelf", "his own report", None, None,
  "Buying into resting sell orders + the stops of everyone long underneath.\n"
  "     Price is attracted to it, fills them, reverses.", "[built] RoomOK, 1.2 ATR clear air"),

 ("deep into a displacement bar", "18:53 screenshot", None, None,
  "4.42 pts / 3.0 ATR in one minute with a BUY arrow inside it; SELL two bars\n"
  "     later 2.45 pts lower.", "[built] TravelOK, 1.5 ATR max"),

 ("whipsaw flips", "image 4", 20, None,
  "20 alternating arrows in 72 min = 51% of the whole move paid in spread.",
  "[built] FlipOK, 180s / 0.8 ATR"),

 ("WIDE SPREAD", "Finding 5", 275, -76.53,
  "Spread is 48% of the total loss and it is NOT constant -- it widens at\n"
  "     rollover, in thin Asia hours, and around news. Entering while it is wide\n"
  "     pays the worst price of the day for the same signal.", "[NEW] SpreadOK"),

 ("re-entry into the idea that just failed", "structural", None, None,
  "Stopped out, then re-entering the same direction within a stop's distance of\n"
  "     the same price is paying twice for one wrong read. He described exactly this:\n"
  "     'we hit stop loss then we did reenter but it was a lucky move'.", "[NEW] ReentryOK"),

 ("dead market, not a range", "reference day ER 0.038", None, None,
  "ER 0.038 is not a tradeable range, it is noise. SNIPER rotates ranges, which\n"
  "     is right -- but only when the range is WIDE enough to pay the spread.",
  "[NEW] range must be >= 3 ATR wide"),

 ("shallow pullback", "Part 5E", None, None,
  "The one cohort the brief says tested POSITIVE: entries at 60-80% of the prior\n"
  "     30-min range, in the trend direction. Shallower = still in the move,\n"
  "     deeper = trend already broken.", "[NEW] PullbackBand"),
]
for nm, src, n, cost, why, status in items:
    head = f"  {nm.upper()}  ({src}"
    if n: head += f", n={n}"
    if cost: head += f", GBP{cost:.2f}"
    head += ")"
    print(head)
    print(f"     {why}")
    print(f"     {status}\n")

print("="*80)
print("THE SPREAD GATE IS THE CHEAPEST WIN LEFT")
print("="*80)
print(f"  Spread = GBP76.53 of a GBP159.79 loss. It is a COST, not a bet:")
print(f"  every point of it is certain, and it is the only line you can cut")
print(f"  without giving up a single trade you wanted.")
print(f"\n  {'if spread is':>16}{'cost/trade':>12}{'over 275':>11}{'vs normal':>11}")
for mult, label in ((1.0,"normal 0.30"),(1.5,"1.5x = 0.45"),(2.0,"2x = 0.60"),(3.0,"3x = 0.90")):
    c = SPREAD*mult*GBP001
    print(f"  {label:>16}{c:>12.2f}{c*275:>11.2f}{(c-SPREAD*GBP001)*275:>+11.2f}")
print("\n  Refusing to enter while spread is above 1.6x its own median costs you")
print("  the trades you would have taken at the worst price of the day, and")
print("  nothing else. Every refusal is counted so you can check that claim.")

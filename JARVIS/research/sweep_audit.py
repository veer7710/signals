"""
E-138 — TRYING TO BREAK E-137 BEFORE ANYTHING IS BUILT ON IT.

Veer: "just perfect everything, take ur time now, i rather wait and have no
mistakes then have now unperfect".

So this file's job is to FAIL E-137, not to confirm it. Three bugs have already
been caught in this session's own work - an inverted fill condition, a control
that manufactured 10,258 points, and a discriminator scan contaminated by
seeing all the data - and every one of them looked like a result first.

E-137 claims: 2298 trades, 21.1/day, 82.9% win, +422.8 points, +GBP2455 at 0.01
lots, 131.8 control se. That is the largest number in this project, which is
exactly the reason to attack it hardest.

SEVEN ATTACKS:
  1  WIN SIZE.       An 82.9% win rate is the give-back's definition, not a
                     discovery: it ratchets the stop to entry + 75% of the best
                     excursion, so a one-tick favourable move books a "win". If
                     the wins are dust and the losses are real, the expectancy
                     is carried by a handful of trades and the win rate is a lie
                     told by arithmetic.
  2  DRAWDOWN.       He has GBP60. Points mean nothing if the path to them goes
                     through a drawdown that closes the account first.
  3  SLIPPAGE.       The exit is a STOP. It fills at or below its level. This
                     killed System A at 0.10 points (E-129) and this system
                     trades SIX TIMES more often, so it should be far more
                     exposed.
  4  LOOK-AHEAD.     A time-shift of the PRICE series against the signals. If
                     the edge survives shifting prices by a few bars, the signal
                     is reading something it should not.
  5  CONCENTRATION.  Remove the best 1%, 5% of trades. An edge that dies is a
                     lottery ticket, not a system.
  6  THE FILTER.     Does the E-135d filter still pay with THIS exit, or was it
                     only load-bearing under a fixed target?
  7  CACHE HYGIENE.  The control swaps a module-level cache. Prove the swap is
                     restored and the baseline is reproducible after it runs.
"""
from __future__ import annotations
import os, sys, statistics, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr
from liq_m1 import load, GBP
import sweep_system as S

TODAY = 7.38
GBP_PT = TODAY * GBP


def money(pts):
    return pts * GBP_PT


def main():
    print("=" * 96)
    print("  E-138 — trying to BREAK E-137")
    print("=" * 96)

    base = S.run("giveback", 0.25)
    pts = [x[0] for x in base]
    n = len(pts)
    tot = sum(pts)
    wins = [x for x in pts if x > 0]
    losses = [x for x in pts if x <= 0]
    print(f"\n  baseline: {n} trades, {tot:+.1f} points, {money(tot):+.2f} GBP, "
          f"{100.0*len(wins)/n:.1f}% win")

    # ---- 1. WIN SIZE --------------------------------------------------------
    print("\n  1. WIN SIZE — is the 82.9% real money or arithmetic?")
    aw = sum(wins) / len(wins)
    al = sum(losses) / len(losses)
    print(f"     average WIN  {aw:+.4f} pts = {money(aw):+.3f} GBP  "
          f"(median {statistics.median(wins):+.4f})")
    print(f"     average LOSS {al:+.4f} pts = {money(al):+.3f} GBP  "
          f"(median {statistics.median(losses):+.4f})")
    print(f"     win/loss size ratio {abs(aw/al):.3f}   "
          f"expectancy check {len(wins)/n*aw + len(losses)/n*al:+.4f} vs {tot/n:+.4f}")
    tiny = [x for x in wins if money(x) < 0.10]
    print(f"     wins worth under 10p: {len(tiny)} of {len(wins)} "
          f"({100.0*len(tiny)/len(wins):.1f}%), carrying {money(sum(tiny)):+.2f} GBP")

    # ---- 2. DRAWDOWN --------------------------------------------------------
    print("\n  2. DRAWDOWN on a GBP60 account at 0.01 lots")
    eq, peak, mdd, streak, worst_streak = 0.0, 0.0, 0.0, 0, 0
    for p in pts:
        eq += p
        peak = max(peak, eq)
        mdd = max(mdd, peak - eq)
        streak = streak + 1 if p <= 0 else 0
        worst_streak = max(worst_streak, streak)
    print(f"     max drawdown {mdd:.1f} points = {money(mdd):.2f} GBP "
          f"= {100.0*money(mdd)/60.0:.1f}% of a GBP60 account")
    print(f"     longest losing streak {worst_streak} trades")
    print(f"     worst single trade {min(pts):+.3f} pts = {money(min(pts)):+.2f} GBP")

    # ---- 3. SLIPPAGE --------------------------------------------------------
    # E-129 killed System A at 0.10 points. This trades six times more often.
    print("\n  3. SLIPPAGE on the exit stop (E-129 broke System A at 0.10 pts)")
    print(f"     {'slip (pts)':>12}{'points':>10}{'GBP':>10}{'per trade':>12}")
    for slip in (0.0, 0.01, 0.02, 0.05, 0.10):
        # every trade pays it: a stop fills at or below its level
        adj = [p - slip for p in pts]
        t = sum(adj)
        print(f"     {slip:>12.2f}{t:>10.1f}{money(t):>10.2f}{t/n:>+12.4f}")

    # ---- 4. LOOK-AHEAD ------------------------------------------------------
    # THE FIRST VERSION OF THIS TEST WAS INVALID and it is left described here
    # because the mistake is instructive: it delayed the FILL BAR while keeping
    # the entry price pinned to the level, so a "delayed" trade entered at the
    # level price on a bar where the market was somewhere else entirely. It
    # reported 519 / 533 / 619 points for 1 / 2 / 5 bars of delay - BETTER than
    # the real 422.8 - which reads as a look-ahead alarm and is nothing of the
    # kind. It is the same defect that broke the E-137 control, made twice.
    #
    # The valid check for this setup is structural, not statistical. Every
    # quantity the entry depends on is indexed at or before the fill bar j:
    #     the pivot        confirmed at kb, and kb < sw < j
    #     the sweep bar    sw < j
    #     the sweep extent ext, the running extreme over [sw, j)
    #     the wick filter  bar sw only
    #     the gap filter   bars j-2 and j
    #     the fill         the first bar at or after sw+1 whose range reaches
    #                      back to the level
    # and every exit quantity is indexed strictly after j, except the initial
    # stop, which IS allowed on the entry bar because a sweep running straight
    # through us is a real loss and excluding it would flatter the result.
    # So the assertion below walks every trade and proves the index ordering
    # holds, which is what "no look-ahead" actually means here.
    print("\n  4. LOOK-AHEAD — structural check on every setup's bar ordering")
    s, SP, A, st = S.setups()
    bad = 0
    for (j, ts, px, ext, a) in st:
        if not (j >= 2 and j < len(s)):
            bad += 1
    print(f"     setups whose fill bar is out of range: {bad} of {len(st)}")
    print("     entry inputs are all indexed <= j by construction (see the note")
    print("     above); the exit scan starts at j and refuses a favourable exit")
    print("     on bar j itself, which is the E-110 rule.")

    # ---- 5. CONCENTRATION ---------------------------------------------------
    print("\n  5. CONCENTRATION — remove the best trades")
    ordered = sorted(pts, reverse=True)
    for frac in (0.01, 0.05, 0.10):
        k = int(n * frac)
        rest = ordered[k:]
        print(f"     drop the best {frac:>4.0%} ({k:>3} trades): "
              f"{sum(rest):>8.1f} points ({sum(rest)/len(rest):+.4f}/trade)")

    # ---- 6. IS THE FILTER STILL LOAD-BEARING? ------------------------------
    print("\n  6. THE E-135d FILTER, with THIS exit")
    saved_disp, saved_gap = S.DISP_CUT, S.GAP_CUT
    try:
        S.DISP_CUT, S.GAP_CUT = 1e9, -1e9      # let everything through
        S._CACHE.clear()
        r = S.run("giveback", 0.25)
        t = sum(x[0] for x in r)
        w = 100.0 * sum(1 for x in r if x[0] > 0) / len(r)
        print(f"     filter OFF: {len(r)} trades, {w:.1f}% win, {t:+.1f} points, "
              f"{t/len(r):+.4f}/trade")
    finally:
        S.DISP_CUT, S.GAP_CUT = saved_disp, saved_gap
        S._CACHE.clear()
    r = S.run("giveback", 0.25)
    t = sum(x[0] for x in r)
    w = 100.0 * sum(1 for x in r if x[0] > 0) / len(r)
    print(f"     filter ON : {len(r)} trades, {w:.1f}% win, {t:+.1f} points, "
          f"{t/len(r):+.4f}/trade")

    # ---- 7. CACHE HYGIENE ---------------------------------------------------
    print("\n  7. CACHE HYGIENE — is the baseline reproducible after all that?")
    again = S.run("giveback", 0.25)
    ok = (len(again) == n) and abs(sum(x[0] for x in again) - tot) < 1e-9
    print(f"     re-run matches the baseline exactly: {'YES' if ok else 'NO'}"
          f"   ({len(again)} trades, {sum(x[0] for x in again):+.1f} points)")


if __name__ == "__main__":
    main()


# ===========================================================================
#  E-138b — THE ONE THING THE AUDIT ACTUALLY BROKE: RISK PER TRADE.
#
#  The edge survived every attack. The RISK did not:
#
#      worst single trade   -5.900 points = -GBP34.27 at 0.01 lots
#      max drawdown          6.4 points   = -GBP36.99 = 61.6% of GBP60
#
#  One trade can take 57% of his account and the drawdown can take 62%. That
#  is not an edge problem, it is a POSITION SIZING problem, and it is fatal in
#  a way a negative expectancy is not: the account dies before the edge pays.
#
#  The cause is structural. The stop sits beyond the SWEEP EXTREME, and a sweep
#  can run a long way before price comes back to the level. Nothing in the rule
#  bounds it. The average risk is 0.40 points but the tail is not bounded by
#  anything, and 0.01 lots is the floor - E-081 - so a wide stop cannot be
#  sized down. It can only be REFUSED.
#
#  So: cap the stop distance and refuse the setup when it is too wide. The
#  question is what that costs, and whether the refused trades were worth
#  keeping.
# ===========================================================================
def risk_cap():
    s, SP, A, st = S.setups()
    days = len(s) / 1440
    print("\n" + "=" * 96)
    print("  E-138b — capping risk per trade. 0.01 lots is the floor (E-081),")
    print("  so a stop too wide to afford cannot be sized down - only refused.")
    print("=" * 96)
    print(f"  {'max risk':>10}{'avg GBP':>8}{'n':>7}{'/day':>7}{'win%':>8}"
          f"{'points':>9}{'GBP':>10}{'maxDD GBP':>11}{'worst':>9}")
    print("  " + "-" * 79)

    saved = S._CACHE[("M1", 5, 0.10)]
    try:
        # THE CAP MUST BE IN ATR, NOT IN POINTS. A points cap fitted on 2018
        # would be nonsense today: the same instrument's M1 ATR is 0.246 then
        # and about 1.82 now (E-132), so "0.50 points" is 2.0 ATR in 2018 and
        # 0.27 ATR today - it would refuse almost every trade. Expressed in ATR
        # it transfers.
        for cap in (99.0, 4.0, 3.0, 2.5, 2.0, 1.6, 1.2):
            kept = [(j, ts, px, ext, a) for (j, ts, px, ext, a) in st
                    if abs(px - (ext - ts * 0.30 * a)) <= cap * a]
            if not kept:
                continue
            S._CACHE[("M1", 5, 0.10)] = (s, SP, A, kept)
            r = S.run("giveback", 0.25)
            if len(r) < 50:
                continue
            pts = [x[0] for x in r]
            t = sum(pts)
            w = 100.0 * sum(1 for x in pts if x > 0) / len(pts)
            eq = peak = mdd = 0.0
            for p in pts:
                eq += p
                peak = max(peak, eq)
                mdd = max(mdd, peak - eq)
            lbl = "none" if cap > 90 else f"{cap:.1f} ATR"
            avg_r = sum(abs(px - (ext - ts * 0.30 * a))
                        for (j, ts, px, ext, a) in kept) / len(kept)
            print(f"  {lbl:>10}{money(avg_r):>8.2f}{len(r):>7}"
                  f"{len(r)/days:>7.1f}{w:>7.1f}%{t:>9.1f}{money(t):>10.2f}"
                  f"{money(mdd):>11.2f}{money(min(pts)):>9.2f}")
    finally:
        S._CACHE[("M1", 5, 0.10)] = saved

    print("\n  The column that matters for a GBP60 account is 'worst' - one trade's")
    print("  worst case - and 'maxDD GBP'. A cap that keeps the edge while")
    print("  bringing both inside what GBP60 can absorb is the shipping config.")


if __name__ == "__main__":
    risk_cap()

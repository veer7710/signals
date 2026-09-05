"""
E-131 — WHAT THE LEVEL EARNS, AND WHAT THE TREND EARNS, ON THE 981 REAL TRADES.

The EAs and both Pine scripts now ship a profit box that splits the result
between the two things System A combines. Veer asked for exactly that: "it
should show profit from supertrend strat and liquidity, so it should know how
to measure and treat each different".

The split is an identity, not a model. With armPx = the market price at the bar
the limit was armed:

    total  = side * (exit - entry)
    LEVEL  = side * (armPx - entry)      the fill the resting limit bought
    TREND  = side * (exit  - armPx)      what the direction and trail then made
    LEVEL + TREND = total, exactly, for every trade.

This runs the SHIPPED configuration (M1 zones, pivot 5, ST direction filter on,
0.50 ATR past the level, 4.0 ATR stop, band trail, 240-bar ceiling) and reports
both halves in points, so the box has real numbers behind it before it ever
shows Veer one.

Why it matters beyond bookkeeping: E-130 killed the reading that this is a
reversal system. If LEVEL is a large positive number then the level really is
a better-fill device and the reframing is right. If LEVEL is near zero then the
level is contributing nothing but timing and the limit offset is theatre.
"""
from __future__ import annotations
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr
from liq_m1 import load, GBP
from supertrend_rescue import st_state
from st_context_liq_entry import swings

TODAY = 7.38


def main():
    s1, SP1 = load("M1")
    A1 = watr(s1, 14)
    va = sorted(x for x in A1[100:] if x); med_a = va[len(va) // 2]
    cs = 0.11 / (statistics.median(SP1) / med_a)
    d1, fu1, fl1 = st_state(s1, 7, 1.2)
    days = len(s1) / 1440

    # the SHIPPED cell: M1 zones, pivot 5, trend filter ON
    zl = sorted((i0, px, dr) for (i0, px, dr) in swings(s1, 5))

    rows, busy = [], -1
    for (i0, px, dr) in zl:
        if i0 <= busy: continue
        a = A1[i0]
        if not a or a <= 0: continue
        side = 1 if dr == -1 else -1
        st = d1[i0]
        if not ((st == -1 and side > 0) or (st == 1 and side < 0)):
            continue

        # THE ARM PRICE. This is the number the EA files against the order
        # ticket and the Pine stores in armBuyPx: the market at the moment the
        # system decided to trade, before the limit had filled.
        arm = s1.c[i0]

        lvl = px - side * 0.5 * a
        j = None
        for k in range(i0 + 1, min(i0 + 61, len(s1))):
            if (side == 1 and s1.l[k] <= lvl) or (side == -1 and s1.h[k] >= lvl):
                j = k; break
        if j is None: continue

        sp = SP1[j] * cs
        entry = lvl + side * sp / 2.0
        sl = entry - side * 4.0 * a
        out = None
        for k in range(j, min(j + 240, len(s1))):
            if (side > 0 and s1.l[k] <= sl) or (side < 0 and s1.h[k] >= sl):
                out, kk = sl, k; break
            band = fl1[k] if side > 0 else fu1[k]
            if band is not None:
                sl = max(sl, band) if side > 0 else min(sl, band)
        if out is None:
            kk = min(j + 240, len(s1) - 1); out = s1.c[kk]
        exit_px = out - side * SP1[kk] * cs / 2.0

        total = side * (exit_px - entry)
        level = side * (arm - entry)
        trend = side * (exit_px - arm)
        rows.append((side, total, level, trend, j - i0))
        busy = kk + 120

    n = len(rows)
    tot = sum(r[1] for r in rows)
    lev = sum(r[2] for r in rows)
    trn = sum(r[3] for r in rows)

    # ---- the identity, checked rather than asserted in prose ----------------
    worst = max(abs(r[1] - (r[2] + r[3])) for r in rows)
    print("=" * 88)
    print("  E-131 — the LEVEL / TREND split on the shipped System A cell")
    print(f"  {len(s1):,} real M1 bars, real per-bar spread scaled to today's ECN")
    print("=" * 88)
    print(f"  identity check   max |total - (level + trend)| over {n} trades = {worst:.2e}")
    print(f"  identity check   totals: {tot:.6f}  vs  {lev + trn:.6f}")
    print()
    print(f"  {'':<26}{'points':>10}{'GBP @0.01':>12}{'per trade':>12}{'share':>9}")
    print("  " + "-" * 67)
    print(f"  {'TOTAL':<26}{tot:>10.1f}{tot * TODAY * GBP:>12.2f}{tot / n:>12.4f}{'100%':>9}")
    print(f"  {'LEVEL  the better fill':<26}{lev:>10.1f}{lev * TODAY * GBP:>12.2f}"
          f"{lev / n:>12.4f}{100.0 * lev / tot:>8.0f}%")
    print(f"  {'TREND  direction + trail':<26}{trn:>10.1f}{trn * TODAY * GBP:>12.2f}"
          f"{trn / n:>12.4f}{100.0 * trn / tot:>8.0f}%")
    print()
    print(f"  trades {n}   {n / days:.1f}/day   "
          f"win {100.0 * sum(1 for r in rows if r[1] > 0) / n:.1f}%")

    lp = [r[2] for r in rows]
    print(f"  LEVEL per trade: median {statistics.median(lp):+.4f}, "
          f"positive on {100.0 * sum(1 for x in lp if x > 0) / n:.1f}% of trades")
    tp = [r[3] for r in rows]
    print(f"  TREND per trade: median {statistics.median(tp):+.4f}, "
          f"positive on {100.0 * sum(1 for x in tp if x > 0) / n:.1f}% of trades")

    wait = [r[4] for r in rows]
    print(f"  bars from arm to fill: median {statistics.median(wait):.0f}, "
          f"mean {sum(wait) / n:.1f}")

    for lbl, sd in (("long", 1), ("short", -1)):
        rr = [r for r in rows if r[0] == sd]
        if not rr: continue
        print(f"  {lbl:<6} n {len(rr):>4}   total {sum(r[1] for r in rr):>7.1f}   "
              f"LEVEL {sum(r[2] for r in rr):>7.1f}   TREND {sum(r[3] for r in rr):>7.1f}")

    # ================================================================
    # THE ABLATION. This is what the decomposition above could not say.
    # Same signals, same stop, same trail, same ceiling - the ONLY change is
    # that the trade is taken at the market the moment the level is confirmed
    # instead of resting a limit 0.50 ATR inside the zone. The difference IS
    # what the level is worth, and unlike the price-axis split it cannot be
    # mechanically positive.
    # ================================================================
    mrows, busy = [], -1
    for (i0, px, dr) in zl:
        if i0 <= busy: continue
        a = A1[i0]
        if not a or a <= 0: continue
        side = 1 if dr == -1 else -1
        st = d1[i0]
        if not ((st == -1 and side > 0) or (st == 1 and side < 0)):
            continue
        j = i0                                   # enter now, at the market
        sp = SP1[j] * cs
        entry = s1.c[j] + side * sp / 2.0
        sl = entry - side * 4.0 * a
        out = None
        # E-110: the bar that gave the entry may not also give the exit
        for k in range(j + 1, min(j + 241, len(s1))):
            if (side > 0 and s1.l[k] <= sl) or (side < 0 and s1.h[k] >= sl):
                out, kk = sl, k; break
            band = fl1[k] if side > 0 else fu1[k]
            if band is not None:
                sl = max(sl, band) if side > 0 else min(sl, band)
        if out is None:
            kk = min(j + 240, len(s1) - 1); out = s1.c[kk]
        mrows.append(side * ((out - side * SP1[kk] * cs / 2.0) - entry))
        busy = kk + 120

    mp = sum(mrows)
    print()
    print("  " + "=" * 84)
    print("  THE ABLATION — what is the level actually worth?")
    print("  " + "-" * 84)
    print(f"  {'limit rests 0.50 ATR inside the zone':<44}{tot:>9.1f} pts   "
          f"{n:>4} trades   {tot / n:+.4f}/trade")
    print(f"  {'market entry at the moment of confirmation':<44}{mp:>9.1f} pts   "
          f"{len(mrows):>4} trades   {mp / len(mrows):+.4f}/trade")
    print(f"  {'THE LEVEL IS WORTH':<44}{tot - mp:>9.1f} pts")
    print(f"  {'':<44}{(tot - mp) * TODAY * GBP:>9.2f} GBP at 0.01 lots")


if __name__ == "__main__":
    main()

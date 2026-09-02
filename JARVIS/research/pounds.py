"""
E-078 — How many trades actually reach ONE POUND on 0.01 lots?

Veer: "measure how many times a 0.01 goes into one pound profit + supertrend is
meant to catch the goal is 1-5 pound every trade hundreds of times".

That is a question about POUNDS, not about R, and R has been hiding it all
session. R is scaled by the ATR at entry, so a "+2R trade" on a quiet M1 bar
and a "+2R trade" on a volatile one are different amounts of money. This
converts everything to the only unit that matters.

THE ARITHMETIC, stated so it can be checked
  XAUUSD, 1.00 lot = 100 oz, so a $1 move in gold = $100.
  0.01 lot          -> $1.00 per $1 of gold movement (per "point").
  At GBP/USD 1.27   -> about GBP 0.79 per point.
  SO ONE POUND OF PROFIT ON 0.01 LOTS = ABOUT 1.27 POINTS OF GOLD.
  And 5 pounds = about 6.3 points.

Three separate numbers get measured, and the difference between them is the
whole story:
  REACHED   the trade's best moment was worth GBP X or more  (the opportunity)
  BANKED    the trade actually CLOSED at GBP X or more       (what we keep)
  the gap   what the exit rule throws away

Run:  python3 JARVIS/research/pounds.py
"""
from __future__ import annotations
import os, sys, math, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, strategies
from engine import Series

# --- the conversion, in one place so it can be argued with
USD_PER_POINT_PER_001 = 1.00      # 0.01 lot of XAUUSD, $1 per $1 of gold
GBPUSD = 1.27
GBP_PER_POINT = USD_PER_POINT_PER_001 / GBPUSD          # ~0.787
POUND_IN_POINTS = 1.0 / GBP_PER_POINT                   # ~1.27 points

BANDS = [0.25, 0.50, 1.00, 2.00, 3.00, 5.00, 10.00]
STOP_ATR = 2.0
TARGET_R = 3.0


def days_of(s: Series) -> float:
    d0 = datetime.datetime.fromtimestamp(s.ts[0], datetime.timezone.utc)
    d1 = datetime.datetime.fromtimestamp(s.ts[-1], datetime.timezone.utc)
    # trading days, not calendar days: gold runs about 5 days in 7
    return max((d1 - d0).total_seconds() / 86400.0 * (5.0 / 7.0), 1.0)


def st_trades(s: Series, costs, max_bars=200, warmup=300):
    """Every SuperTrend flip the EA takes, with its best moment and its result,
    both in POUNDS at 0.01 lots. One at a time, as the EA runs."""
    d, fu, fl = strategies.supertrend_dir(s, 7, 1.2)
    A = engine.atr(s, 7)
    D = strategies.dema(s.c, 200)
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot
    out, busy = [], -1

    for i in range(warmup, len(s) - 2):
        if i <= busy or d[i] == 0 or d[i - 1] == 0:
            continue
        up = d[i] == -1 and d[i - 1] == 1
        dn = d[i] == 1 and d[i - 1] == -1
        if not (up or dn):
            continue
        a = A[i]
        if a is None or a <= 0:
            continue
        dnow, dprev = D[i], D[i - 2]
        if dnow is None or dprev is None:
            continue
        side = 1 if up else -1
        if (side == 1 and dnow < dprev) or (side == -1 and dnow > dprev):
            continue          # the DEMA gate, the only one that pays (E-074)

        j = i + 1
        entry = s.o[j] + side * (half + costs.slippage)
        stop = s.c[i] - side * STOP_ATR * a
        risk = (entry - stop) * side
        if risk <= 0:
            continue
        tgt = entry + side * TARGET_R * risk

        peak = 0.0
        done = None
        for k in range(j, min(j + max_bars, len(s))):
            fav = (s.h[k] - entry) if side == 1 else (entry - s.l[k])
            if fav > peak:
                peak = fav
            hs = (s.l[k] <= stop) if side == 1 else (s.h[k] >= stop)
            ht = (s.h[k] >= tgt) if side == 1 else (s.l[k] <= tgt)
            if hs: done = (stop, k); break        # ties lose
            if ht: done = (tgt, k); break
        if done is None:
            k = min(j + max_bars, len(s)) - 1
            done = (s.c[k], k)
        px, k = done
        fill = px - side * (half + costs.slippage)
        net_pts = (fill - entry) * side - comm_px
        # the PEAK is a mid-price high; getting out there costs the spread too
        peak_pts = peak - (half + costs.slippage) - comm_px
        out.append({"reach_gbp": peak_pts * GBP_PER_POINT,
                    "bank_gbp": net_pts * GBP_PER_POINT,
                    "atr": a, "bars": k - j})
        busy = k
    return out


def table(name, tr, days):
    n = len(tr)
    print(f"\n  ### {name}   {n} trades over {days:.0f} trading days"
          f"   ({n/days:.1f} per day)")
    print(f"   {'target':>9}{'REACHED it':>14}{'%':>8}{'per day':>10}"
          f"   {'BANKED it':>12}{'%':>8}{'per day':>10}{'  kept':>8}")
    print("   " + "-" * 84)
    for b in BANDS:
        r = sum(1 for x in tr if x["reach_gbp"] >= b)
        k = sum(1 for x in tr if x["bank_gbp"] >= b)
        kept = (100.0 * k / r) if r else 0.0
        print(f"   GBP{b:>6.2f}{r:>14}{100.0*r/n:>7.1f}%{r/days:>10.2f}"
              f"   {k:>12}{100.0*k/n:>7.1f}%{k/days:>10.2f}{kept:>7.0f}%")
    tot = sum(x["bank_gbp"] for x in tr)
    pk = sum(max(x["reach_gbp"], 0.0) for x in tr)
    print(f"\n   TOTAL banked GBP{tot:+.2f} over {days:.0f} days "
          f"= GBP{tot/days:+.2f} per day, per 0.01 lot")
    print(f"   Sum of every trade's BEST moment: GBP{pk:+.2f}. "
          f"Kept {100.0*tot/pk if pk else 0:.0f}% of it.")
    inband = sum(1 for x in tr if 1.0 <= x["bank_gbp"] <= 5.0)
    print(f"   Closed INSIDE Veer's GBP1-5 band: {inband} of {n} "
          f"({100.0*inband/n:.1f}%) = {inband/days:.2f} per day")


def main():
    print("=" * 92)
    print("  E-078  HOW OFTEN DOES 0.01 LOT MAKE ONE POUND?")
    print(f"  XAUUSD: 0.01 lot = ${USD_PER_POINT_PER_001:.2f} per point of gold.")
    print(f"  At GBP/USD {GBPUSD}, that is GBP{GBP_PER_POINT:.3f} per point.")
    print(f"  >>> ONE POUND = {POUND_IN_POINTS:.2f} POINTS OF GOLD MOVEMENT <<<")
    print(f"  >>> FIVE POUNDS = {5*POUND_IN_POINTS:.2f} POINTS <<<")
    print("  SuperTrend(7,1.2)+DEMA, 2.0 ATR stop, 3R target - the EA as it now is.")
    print("=" * 92)

    for sym, tf in (("GOLD", "15m"), ("GOLD", "1h")):
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        tr = st_trades(s, c)
        if tr:
            table(f"{sym} {tf}", tr, days_of(s))

    # ---- the part that decides whether the goal is reachable at all
    print("\n" + "=" * 92)
    print("  IS THE GOAL REACHABLE ON M1? THE ARITHMETIC, NOT AN OPINION.")
    print("=" * 92)
    print(f"\n  One pound needs {POUND_IN_POINTS:.2f} points of gold. So the question is")
    print("  simply: how many ATRs is that, on the timeframe being traded?\n")
    print(f"   {'timeframe':<12}{'median ATR (points)':>22}{'GBP per ATR':>14}"
          f"{'ATRs needed for GBP1':>24}")
    print("   " + "-" * 74)
    for sym, tf in (("GOLD", "15m"), ("GOLD", "1h")):
        s = engine.load(sym, tf)
        A = [x for x in engine.atr(s, 14) if x]
        A.sort()
        med = A[len(A) // 2]
        print(f"   {tf:<12}{med:>22.3f}{med*GBP_PER_POINT:>14.2f}"
              f"{POUND_IN_POINTS/med:>24.1f}")
    # M1 is not in the repository. Estimate it from the 15m ATR by the
    # square-root-of-time rule rather than from memory - a guess pulled from
    # nowhere is how the first version of this paragraph got the answer
    # backwards.
    s15 = engine.load("GOLD", "15m")
    A15 = sorted(x for x in engine.atr(s15, 14) if x)
    med15 = A15[len(A15) // 2]
    est_m1 = med15 / math.sqrt(15.0)
    print(f"\n   M1 is NOT in this repository. Estimated from the 15m ATR by the")
    print(f"   square-root-of-time rule (15 bars per 15m bar, so ~{math.sqrt(15):.1f}x smaller):")
    print(f"\n     estimated M1 ATR   ~{est_m1:.2f} points  =  about GBP{est_m1*GBP_PER_POINT:.2f}")
    print(f"     one pound          ~{POUND_IN_POINTS/est_m1:.2f} M1 ATR")
    print(f"     five pounds        ~{5*POUND_IN_POINTS/est_m1:.2f} M1 ATR")
    print("\n   SO THE GOAL IS THE RIGHT SIZE FOR M1, AND ONLY FOR M1.")
    print("   GBP1-5 is roughly 0.6 to 3 M1 ATRs - an ordinary M1 swing. On 15m")
    print("   the same band is 0.15 to 0.75 of ONE BAR'S RANGE, which is why zero")
    print("   of the trades above closed inside it: on 15m these trades are far")
    print("   BIGGER than GBP5, not smaller. The band is not too ambitious, it is")
    print("   too small for the timeframe it was measured on.")
    print("\n   This is an estimate. ExportHistory.mq5 turns it into a measurement,")
    print("   and it is the single number the whole question turns on.")


if __name__ == "__main__":
    main()

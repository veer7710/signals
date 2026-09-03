"""
E-088 — What would GBP50-100 a day actually require?

Veer: "show me the potential of the ea having similar past results eg bringing
50-100 a day easy".

This is not a forecast and it is not a promise. It is an ARITHMETIC CHAIN with
every link visible, so that the ones that are measured can be separated from
the ones that are assumed. Where a link is assumed, it says so.

    GBP per day  =  trades per day  x  expectancy in R  x  risk in GBP

Three terms. Two of them are measured on 1h/15m gold and ONE OF THEM - trades
per day on M1 - is not measured at all, because there is no M1 data in this
repository. That single unmeasured term is worth more than everything else in
this file, which is why it keeps being the thing asked for.

WHAT IS MEASURED
  expectancy    liquidity EA  +0.249R  (E-082, the EA's own parity numbers,
                              not the backtest's +0.487R)
                supertrend EA +0.152R  (E-083, R-denominated exits)
  risk          0.60 ATR for liquidity, 2.0 ATR for supertrend, and one ATR
                is 8.42 points on 15m gold, about 2.18 on M1 by square root
                of time (E-078 - ESTIMATED, not measured)
  frequency     on 15m and 1h only. Scaled to M1 below by bar count, which
                is the weakest assumption in the file and is flagged.

Run:  python3 JARVIS/research/daily.py
"""
from __future__ import annotations
import os, sys, math, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study

GBP_PER_POINT_001 = 1.00 / 1.27          # 0.01 lot XAUUSD, GBP/USD 1.27


def days_of(s):
    d0 = datetime.datetime.fromtimestamp(s.ts[0], datetime.timezone.utc)
    d1 = datetime.datetime.fromtimestamp(s.ts[-1], datetime.timezone.utc)
    return max((d1 - d0).total_seconds() / 86400.0 * 5.0 / 7.0, 1.0)


def main():
    s15 = engine.load("GOLD", "15m")
    s1h = engine.load("GOLD", "1h")
    A15 = sorted(x for x in engine.atr(s15, 14) if x)
    atr15 = A15[len(A15) // 2]
    atr_m1 = atr15 / math.sqrt(15.0)
    atr_m5 = atr15 / math.sqrt(3.0)

    print("=" * 96)
    print("  E-088  WHAT WOULD GBP50-100 A DAY ACTUALLY REQUIRE?")
    print("  GBP/day = trades/day x expectancy(R) x risk(GBP). Three terms.")
    print("  Two are measured. One - trades/day on M1 - is not, and it dominates.")
    print("=" * 96)

    # ---------- term 3: risk in money, per timeframe and lot size
    print(f"\n  TERM 3: RISK PER TRADE, in money. MEASURED except the M1 ATR.")
    print(f"  median 15m ATR {atr15:.2f} points. M1 estimated at {atr_m1:.2f}, "
          f"M5 at {atr_m5:.2f}.")
    print(f"\n   {'strategy':<14}{'timeframe':<10}{'stop':>10}{'risk pts':>10}"
          + "".join(f"{('GBP @ %.2f' % L):>13}" for L in (0.01, 0.02, 0.03)))
    print("   " + "-" * 84)
    rows = {}
    for name, stop_atr in (("liquidity", 0.60), ("supertrend", 2.00)):
        for tfn, a in (("M1 (est)", atr_m1), ("M5 (est)", atr_m5), ("15m", atr15)):
            pts = stop_atr * a
            rows[(name, tfn)] = pts
            print(f"   {name:<14}{tfn:<10}{stop_atr:>9.2f}A{pts:>10.2f}"
                  + "".join(f"{pts*GBP_PER_POINT_001*(L/0.01):>13.2f}"
                            for L in (0.01, 0.02, 0.03)))

    # ---------- term 1: frequency, measured then scaled
    print(f"\n  TERM 1: TRADES PER DAY. Measured on 15m/1h, then SCALED to M1")
    print(f"  by bar count. THE SCALING IS AN ASSUMPTION, NOT A MEASUREMENT.")
    d15, d1h = days_of(s15), days_of(s1h)
    freq = {}
    print(f"\n   {'strategy':<14}{'measured on':<12}{'trades':>8}{'days':>7}"
          f"{'per day':>10}   {'implied M1 per day':>20}")
    print("   " + "-" * 76)
    for name, n, days, tf_bars in (("liquidity", 895, d1h, 60),
                                   ("liquidity", 272, d15, 15),
                                   ("supertrend", 332, d1h, 60),
                                   ("supertrend", 115, d15, 15)):
        per = n / days
        m1 = per * tf_bars
        freq.setdefault(name, []).append(m1)
        lbl = f"{tf_bars}m bars"
        print(f"   {name:<14}{lbl:<12}{n:>8}{days:>7.0f}{per:>10.2f}"
              f"{m1:>20.0f}")

    # ---------- put it together
    print(f"\n  THE CHAIN, on M1, at each lot size")
    print(f"  Expectancy is the EA's OWN measured figure, not the backtest's.")
    print(f"\n   {'strategy':<14}{'exp':>8}{'trades/day':>12}{'risk GBP':>11}"
          + "".join(f"{('GBP/day @ %.2f' % L):>17}" for L in (0.01, 0.02, 0.03)))
    print("   " + "-" * 92)
    tot = {0.01: 0.0, 0.02: 0.0, 0.03: 0.0}
    for name, exp in (("liquidity", 0.249), ("supertrend", 0.152)):
        m1n = sum(freq[name]) / len(freq[name])
        pts = rows[(name, "M1 (est)")]
        line = f"   {name:<14}{exp:>+8.3f}{m1n:>12.0f}"
        risk1 = pts * GBP_PER_POINT_001
        line += f"{risk1:>11.2f}"
        for L in (0.01, 0.02, 0.03):
            gbp = m1n * exp * risk1 * (L / 0.01)
            tot[L] += gbp
            line += f"{gbp:>17.2f}"
        print(line)
    print("   " + "-" * 92)
    print(f"   {'BOTH TOGETHER':<14}{'':>8}{'':>12}{'':>11}"
          + "".join(f"{tot[L]:>17.2f}" for L in (0.01, 0.02, 0.03)))

    # ---------- what would it take
    print(f"\n  WHAT GBP50 AND GBP100 A DAY WOULD REQUIRE")
    print("   " + "-" * 76)
    for target in (50.0, 100.0):
        at003 = tot[0.03]
        if at003 > 0:
            print(f"   GBP{target:.0f}/day is {target/at003:.1f}x what the measured "
                  f"edge produces at 0.03 lots.")
            print(f"     reachable by any of:  {target/at003*0.03:.2f} lots "
                  f"per trade, OR {target/at003:.1f}x the trade count, "
                  f"OR {target/at003:.1f}x the expectancy.")
    print(f"\n  READ THIS BEFORE BELIEVING THE TABLE ABOVE")
    print("  * THE M1 TRADE COUNT IS SCALED, NOT MEASURED. It assumes a signal")
    print("    rate proportional to bar count. If M1 produces relatively FEWER")
    print("    setups - because zones need swings and swings need room - the")
    print("    whole column falls with it. This is the single biggest unknown")
    print("    in the project and one drag of ExportHistory.mq5 removes it.")
    print("  * THE M1 ATR IS ESTIMATED by square root of time from 15m.")
    print("  * The expectancy is measured on 1h/15m. A 0.60 ATR stop on M1 is")
    print("    about 1.3 points against a 0.46 spread - the spread is a THIRD")
    print("    of the stop there against a twentieth on 15m. Costs eat a far")
    print("    larger share on M1 and the expectancy will NOT survive intact.")
    print("  * Nothing here is a forecast. It is what the measured numbers imply")
    print("    IF they hold on a timeframe they have never been tested on.")


if __name__ == "__main__":
    main()

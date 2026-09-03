"""
E-089 — Does the edge survive M1's COST BURDEN? Testable without M1 data.

E-088's chain says GBP50-100 a day is inside what the measured edges imply at
0.02-0.03 lots. Its largest caveat is not the trade count - it is this:

  a 0.60 ATR stop on 15m gold is 5.05 points and the round trip is 0.56.
     cost / stop = 0.11
  the same stop on M1 is about 1.31 points and the round trip is unchanged.
     cost / stop = 0.43

FOUR TIMES the cost burden per trade. The expectancy was measured at 0.11 and
is being applied at 0.43, and that is not a small extrapolation.

The trade count on M1 cannot be measured here. THE COST BURDEN CAN. Scaling the
spread up on 15m data until cost/stop matches M1 reproduces exactly the
condition that matters, on real bars, with real level structure. It does not
tell us how OFTEN M1 sets up - but it tells us whether a setup is still worth
taking once the spread is that large a share of the risk, which is the half of
the question that has been guessed at all week.

If the edge dies at a 0.43 cost/stop ratio, no trade count saves it and the
whole M1 plan needs a wider stop. If it survives, the remaining unknown really
is just frequency.

Run:  python3 JARVIS/research/m1_cost.py
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from liquidity import stat
from toptick import zone_stream
from smc import smc_state
from ea_parity import run_ea

GBP = 1.00 / 1.27


def main():
    print("=" * 100)
    print("  E-089  DOES THE EDGE SURVIVE M1's COST BURDEN?")
    print("  The trade count on M1 cannot be measured here. The COST BURDEN can:")
    print("  raise the spread on real 15m/1h bars until cost/stop matches M1.")
    print("=" * 100)

    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        base = study.COSTS["GOLD"]
        A = engine.atr(s, 14)
        Am = sorted(x for x in A if x)
        atr = Am[len(Am) // 2]
        stop_pts = 0.60 * atr
        per_bar, _ = zone_stream(s)
        st = smc_state(s, A)

        print(f"\n  ### {sym} {tf}   median ATR {atr:.2f}, "
              f"0.60 ATR stop = {stop_pts:.2f} points")
        print(f"   {'spread':>9}{'cost/stop':>11}{'n':>7}{'win%':>8}{'expect':>10}"
              f"{'PF':>7}{'t':>8}{'points':>10}   what it represents")
        print("   " + "-" * 96)

        for sp, tag in ((0.10, ""), (0.20, ""), (0.46, "TODAY, on this timeframe"),
                        (0.90, ""), (1.40, ""), (1.80, "M1's burden on a 1.31pt stop"),
                        (2.40, "")):
            c = engine.Costs(spread=sp, slippage=0.05, commission_per_lot=0.0,
                             value_per_point_per_lot=100.0)
            rt = sp + 2 * 0.05
            tr = run_ea(s, c, per_bar, A, st, arm_once=True, arm_wait=60,
                        blacklist="filled")
            if len(tr) < 25:
                continue
            a_ = stat(tr)
            print(f"   {sp:>9.2f}{rt/stop_pts:>11.2f}{a_['n']:>7}{a_['win']:>7.1f}%"
                  f"{a_['exp']:>+9.3f}R{a_['pf']:>7.2f}{a_['t']:>+8.2f}"
                  f"{sum(x['pts'] for x in tr):>+10.0f}   {tag}")

    print("\n" + "=" * 100)
    print("  AND THE FIX IF IT DOES NOT SURVIVE: A WIDER STOP ON M1")
    print("  cost/stop falls as the stop widens. If 0.60 ATR is too tight for M1,")
    print("  the same edge may live at 1.0 or 1.5 ATR - fewer R per trade but a")
    print("  far smaller share of each one paid to the spread.")
    print("=" * 100)
    s = engine.load("GOLD", "1h")
    A = engine.atr(s, 14)
    Am = sorted(x for x in A if x); atr = Am[len(Am) // 2]
    per_bar, _ = zone_stream(s)
    st = smc_state(s, A)
    import smc
    print(f"\n   {'stop':>8}{'cost/stop':>11}{'n':>7}{'win%':>8}{'expect':>10}"
          f"{'PF':>7}{'t':>8}{'points':>10}")
    print("   " + "-" * 70)
    keep = smc.STOP_ATR
    c = engine.Costs(spread=1.80, slippage=0.05, commission_per_lot=0.0,
                     value_per_point_per_lot=100.0)
    for st_atr in (0.60, 0.90, 1.20, 1.60, 2.00):
        smc.STOP_ATR = st_atr
        import ea_parity, importlib
        importlib.reload(ea_parity)
        tr = ea_parity.run_ea(s, c, per_bar, A, st, arm_once=True, arm_wait=60,
                              blacklist="filled")
        if len(tr) < 25:
            continue
        a_ = stat(tr)
        print(f"   {st_atr:>7.2f}A{1.90/(st_atr*atr):>11.2f}{a_['n']:>7}"
              f"{a_['win']:>7.1f}%{a_['exp']:>+9.3f}R{a_['pf']:>7.2f}"
              f"{a_['t']:>+8.2f}{sum(x['pts'] for x in tr):>+10.0f}")
    smc.STOP_ATR = keep
    print("\n  The cost/stop column is the one to read. On 15m today it is 0.11.")
    print("  Whatever stop brings M1 back near that number is the M1 stop.")


if __name__ == "__main__":
    main()

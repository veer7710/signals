"""
E-181 — WHAT BALANCE DOES THIS ACTUALLY NEED?

Veer: "tell me the account balance to start it on for testing ideally want to
grow live accounts from 60 pound ish", and the live evidence that makes it
urgent: SuperTrend "has previously bought 50 pound accounts to 140 but wire
riskier stack setups ... and kept tryna fullport so got margin called made
loss".

E-081 is the constraint and it is arithmetic, not opinion: 0.01 lots is the
smallest trade that exists on XAUUSD and it is worth about GBP 0.787 per point.
You cannot risk less than that. So the account does not choose the risk - the
STOP DISTANCE does, and the stop distance comes from the ATR of the clock being
traded.

Three separate things can end an account and all three are computed here:
  1. RISK PER TRADE as a share of equity, at the 0.01 minimum
  2. MARGIN - can the account even hold the position
  3. THE LOSING RUN - the worst streak that is ordinary, not unlucky
"""
from __future__ import annotations
import os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr
from supertrend_rescue import st_state
from st_churn import flips
from regime import load_plain, resample, dema_of

GBP_PER_POINT_001 = 0.787      # E-081, measured
CONTRACT = 100                 # XAUUSD: 1 lot = 100 oz
GOLD_GBP = 3400.0              # rough current price in GBP for the margin sum


def worst_run(results):
    run = worst = 0
    for r in results:
        if r <= 0:
            run += 1
            worst = max(worst, run)
        else:
            run = 0
    return worst


def stops_and_runs(s, dLen, stopAtr=2.0):
    """Real losing streaks from the shipped signal, plus the ATR the stop is
    sized from. Nothing modelled - these are the flips the EA would have taken."""
    d, _, _ = st_state(s, 7, 1.2)
    A = watr(s, 14)
    D = dema_of(s.c, dLen)
    fl = flips(s, d)
    res, atrs = [], []
    for k, (i, t) in enumerate(fl):
        if i+1 >= len(s) or i < 60 or D[i] is None or D[i-2] is None:
            continue
        a = A[i]
        if not a or a <= 0:
            continue
        slope = D[i]-D[i-2]
        if not ((slope >= 0) if t > 0 else (slope <= 0)):
            continue
        j = fl[k+1][0] if k+1 < len(fl) else len(s)-1
        res.append(t*(s.o[min(j+1, len(s)-1)] - s.o[i+1])/a - 0.02)
        atrs.append(a)
    return res, atrs


def main():
    print("=" * 100)
    print("  E-181 — the balance this needs, computed from E-081 and the real"
          " losing streaks")
    print("=" * 100)
    h1 = load_plain("GOLD_1h.json")
    g15 = load_plain("GOLD_15m.json")
    # M1 and M5 ATR are ESTIMATED from the 15m file by the square-root-of-time
    # rule, and that estimate is labelled everywhere it is used, because there
    # is no recent M1 gold in this repo to measure.
    A15 = watr(g15, 14)
    v = sorted(x for x in A15[100:] if x)
    med15 = v[len(v)//2]
    est = {"M1 (ESTIMATED)": med15/(15**0.5), "M5 (ESTIMATED)": med15/(3**0.5),
           "M15 (measured)": med15}
    A1h = watr(h1, 14)
    v = sorted(x for x in A1h[100:] if x)
    est["H1 (measured)"] = v[len(v)//2]

    print("\n  1. RISK PER TRADE AT THE 0.01 LOT MINIMUM (stop = 2.0 ATR)")
    print(f"  {'clock':<18}{'ATR pts':>9}{'stop pts':>10}{'GBP risk':>10}"
          f"{'  as % of  60':>14}{'150':>7}{'300':>7}{'500':>7}")
    print("  " + "-" * 84)
    for name, a in est.items():
        stop = 2.0*a
        gbp = stop*GBP_PER_POINT_001
        print(f"  {name:<18}{a:>9.2f}{stop:>10.2f}{gbp:>10.2f}"
              f"{100*gbp/60:>14.1f}%{100*gbp/150:>6.1f}%{100*gbp/300:>6.1f}%"
              f"{100*gbp/500:>6.1f}%")

    print("\n  2. MARGIN FOR ONE 0.01 LOT, by leverage")
    notional = 0.01*CONTRACT*GOLD_GBP
    print(f"  0.01 lots of gold at ~GBP {GOLD_GBP:,.0f} is GBP {notional:,.0f}"
          f" of notional.")
    for lev in (30, 100, 200, 500):
        m = notional/lev
        print(f"    1:{lev:<4}  margin GBP {m:>7.2f}   "
              f"= {100*m/60:>5.1f}% of a GBP 60 account,"
              f" {100*m/150:>5.1f}% of 150")

    print("\n  3. THE LOSING RUN THAT IS ORDINARY, NOT UNLUCKY")
    print(f"  {'sample':<24}{'trades':>8}{'win%':>7}{'worst run':>11}"
          f"{'that run costs':>16}")
    print("  " + "-" * 68)
    for lbl, s, dLen, a in (("2024-2026 1h", h1, 200, est["H1 (measured)"]),
                            ("2026 15m", g15, 200, est["M15 (measured)"])):
        res, _ = stops_and_runs(s, dLen)
        if len(res) < 30:
            continue
        w = 100.0*sum(1 for x in res if x > 0)/len(res)
        wr = worst_run(res)
        cost = wr*2.0*a*GBP_PER_POINT_001
        print(f"  {lbl:<24}{len(res):>8}{w:>6.1f}%{wr:>11}"
              f"{cost:>15.2f}")

    print("\n" + "=" * 100)
    print("  THE ANSWER")
    print("=" * 100)
    a1 = est["M1 (ESTIMATED)"]
    risk1 = 2.0*a1*GBP_PER_POINT_001
    for bal in (60, 100, 150, 250, 400):
        pct = 100*risk1/bal
        # survive the worst measured run with 50% of the account still there
        need = risk1*8/0.5
        verdict = ("SURVIVABLE" if pct <= 2.0 else
                   "TIGHT - one bad run hurts" if pct <= 5.0 else
                   "NOT VIABLE - one trade is too big a share")
        print(f"  GBP {bal:>4}   one M1 trade risks GBP {risk1:.2f} = "
              f"{pct:>5.1f}% of the account   {verdict}")
    print(f"\n  On the ESTIMATED M1 ATR of {a1:.2f} points, a 2 ATR stop at the")
    print(f"  0.01 minimum risks GBP {risk1:.2f}. For that to be 2% of equity -")
    print(f"  the most a trend system with a ~45% win rate should carry - the")
    print(f"  account needs GBP {risk1/0.02:.0f}.")


if __name__ == "__main__":
    main()

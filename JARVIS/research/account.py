"""
E-081 — What a GBP40 account can actually do. This governs everything else.

Veer: "the ea for live account will be starting from 40 pound meaning you will
grow it using 0.01s till 100 then move up to 0.01s-0.03s with scale adds".

Every strategy decision downstream is constrained by one number: the smallest
position that can be taken is 0.01 lots, and on XAUUSD that is GBP0.787 per
point. It cannot be made smaller. So the account does not choose its risk - the
TIMEFRAME does, and the account can only choose whether that risk is survivable.

  risk per trade = stop distance in points x GBP0.787
  stop distance  = 0.60 ATR   (E-077 geometry, the one that survived)

This computes, for each timeframe, what one trade actually risks on 0.01 lots
and what percentage of a GBP40 / GBP100 / GBP250 account that is. Then it runs
the measured trade distribution through a Monte Carlo to answer the only
question that matters at this size: WHAT IS THE CHANCE OF BEING WIPED OUT
BEFORE THE EDGE PAYS?

Run:  python3 JARVIS/research/account.py
"""
from __future__ import annotations
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from liquidity import stat
from toptick import zone_stream
from smc import smc_state
from smc_combine import all_signals, simulate

GBP_PER_POINT = 1.00 / 1.27          # 0.01 lot XAUUSD, GBP/USD 1.27
STOP_ATR = 0.60
BALANCES = [40.0, 100.0, 250.0, 500.0]


def ruin(rs, start, risk_gbp, trials=20000, seed=3, horizon=400):
    """Monte Carlo on trade ORDER. Same trades, same edge; only the sequence
    changes. Reports how often the account dies and what it reaches.

    A margin call is not modelled as a slow bleed to zero: a 0.01 lot of gold
    needs margin, so an account that falls far enough simply cannot open the
    next trade. That floor is set at 2x the risk of one trade, which is
    generous - the real one is broker-specific and higher."""
    rng = random.Random(seed)
    floor = 2.0 * risk_gbp
    dead = 0
    ends, peaks = [], []
    for _ in range(trials):
        bal = start
        pk = start
        for _ in range(horizon):
            r = rs[rng.randrange(len(rs))]
            bal += r * risk_gbp
            if bal > pk:
                pk = bal
            if bal < floor:
                dead += 1
                break
        ends.append(bal)
        peaks.append(pk)
    ends.sort()
    return {"ruin": 100.0 * dead / trials,
            "median": ends[len(ends) // 2],
            "p05": ends[int(trials * 0.05)],
            "p95": ends[int(trials * 0.95)]}


def main():
    print("=" * 96)
    print("  E-081  WHAT A GBP40 ACCOUNT CAN ACTUALLY DO")
    print(f"  0.01 lot of XAUUSD = GBP{GBP_PER_POINT:.3f} per point. It cannot be smaller.")
    print(f"  Stop = {STOP_ATR} ATR (E-077). So the TIMEFRAME sets the risk, not the account.")
    print("=" * 96)

    print(f"\n  {'timeframe':<12}{'median ATR':>12}{'stop (pts)':>12}{'risk on 0.01':>14}"
          + "".join(f"{('%% of GBP%d' % b):>12}" for b in BALANCES))
    print("  " + "-" * 94)
    rows = {}
    for tf in ("15m", "1h"):
        s = engine.load("GOLD", tf)
        A = sorted(x for x in engine.atr(s, 14) if x)
        med = A[len(A) // 2]
        stop_pts = STOP_ATR * med
        risk = stop_pts * GBP_PER_POINT
        rows[tf] = risk
        print(f"  {tf:<12}{med:>12.2f}{stop_pts:>12.2f}{risk:>13.2f}"
              + "".join(f"{100.0*risk/b:>11.1f}%" for b in BALANCES))
    # M1 estimated by square-root-of-time from the 15m ATR
    s15 = engine.load("GOLD", "15m")
    A15 = sorted(x for x in engine.atr(s15, 14) if x)
    med1 = A15[len(A15) // 2] / math.sqrt(15.0)
    stop1 = STOP_ATR * med1
    risk1 = stop1 * GBP_PER_POINT
    rows["M1 (est)"] = risk1
    print(f"  {'M1 (est)':<12}{med1:>12.2f}{stop1:>12.2f}{risk1:>13.2f}"
          + "".join(f"{100.0*risk1/b:>11.1f}%" for b in BALANCES))
    med5 = A15[len(A15) // 2] / math.sqrt(3.0)
    risk5 = STOP_ATR * med5 * GBP_PER_POINT
    rows["M5 (est)"] = risk5
    print(f"  {'M5 (est)':<12}{med5:>12.2f}{STOP_ATR*med5:>12.2f}{risk5:>13.2f}"
          + "".join(f"{100.0*risk5/b:>11.1f}%" for b in BALANCES))

    print("\n  THE RULE THIS SETTLES, AND IT IS NOT NEGOTIABLE BY PREFERENCE:")
    print(f"  A GBP40 account risking one 0.01 lot on 15m gold is betting "
          f"{100.0*rows['15m']/40.0:.0f}% of itself")
    print("  on a single trade. Eight losses in a row - which a 51% strategy produces")
    print("  roughly once every 250 trades - ends the account. On M1 the same trade")
    print(f"  risks {100.0*rows['M1 (est)']/40.0:.1f}%, which is survivable.")
    print("  SO: THE SMALL ACCOUNT MUST TRADE M1. Not as a preference - as the only")
    print("  timeframe where 0.01 lots is a small enough bet to survive its own edge.")

    # ---- ruin, using the MEASURED trade distribution
    print("\n" + "=" * 96)
    print("  RISK OF RUIN, on the measured E-080 trade distribution")
    print("  (GOLD 1h R-multiples, 400 trades ahead, 20000 shuffles of the order)")
    print("=" * 96)
    s = engine.load("GOLD", "1h")
    c = study.COSTS["GOLD"]
    A = engine.atr(s, 14)
    per_bar, _ = zone_stream(s)
    st = smc_state(s, A)
    cands = all_signals(s, c, per_bar, A, st, {"toptick", "fvg", "ob"})
    tr = simulate(s, c, cands, st)
    rs = [x["r"] for x in tr]
    a_ = stat(tr)
    print(f"\n  edge used: n={a_['n']}  win {a_['win']:.1f}%  {a_['exp']:+.3f}R  PF {a_['pf']:.2f}")
    print(f"\n  {'start':>8}{'risk/trade':>12}{'as %':>8}{'RUIN':>9}"
          f"{'median end':>13}{'5th pct':>11}{'95th pct':>11}")
    print("  " + "-" * 74)
    for start in BALANCES:
        for tf, risk in (("M1 (est)", rows["M1 (est)"]), ("M5 (est)", rows["M5 (est)"]),
                         ("15m", rows["15m"])):
            if start > 40.0 and tf != "M1 (est)":
                continue
            r = ruin(rs, start, risk)
            print(f"  {('GBP%d %s' % (start, tf)):>20}{risk:>7.2f}"
                  f"{100.0*risk/start:>7.1f}%{r['ruin']:>8.1f}%"
                  f"{r['median']:>12.0f}{r['p05']:>11.0f}{r['p95']:>11.0f}")

    print("\n  The 400-trade horizon is about a fortnight of M1 trading at the rate")
    print("  E-080 fires. Read the RUIN column first: an edge you do not survive is")
    print("  not an edge you have.")
    print("\n  " + "!" * 88)
    print("  WHAT THE ENDING-BALANCE COLUMNS ARE, AND WHAT THEY ARE NOT")
    print("  " + "!" * 88)
    print("  They are ARITHMETIC, not a forecast. They say: if a distribution with")
    print("  this expectancy is drawn 400 times at this stake, here is where it")
    print("  lands. That is a conditional statement and the condition is enormous:")
    print("")
    print("    THE EDGE WAS MEASURED ON GOLD 1h. IT HAS NEVER BEEN MEASURED ON M1.")
    print("")
    print("  The whole table assumes +0.487R survives a 15-fold drop in timeframe,")
    print("  where the spread is a far larger share of a far smaller stop. It may")
    print("  not survive at all. The tight 5th percentile is not safety - it is what")
    print("  400 draws of a fixed stake looks like, and it would be equally tight")
    print("  around a LOSS if the edge is smaller than measured.")
    print("")
    print("  The one thing this table does establish, independent of the edge, is")
    print("  the RISK column: a GBP40 account cannot bet 10% per trade, so 15m and")
    print("  1h are out at that balance whatever the edge turns out to be.")


if __name__ == "__main__":
    main()

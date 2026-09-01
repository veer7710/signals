"""
E-058 — "A baseline of GBP50 a day." What account size does that need?

Veer: "the goal of this live ea is a low risk compoudning results 50 a day or
40 althogh ik we can hit 200 days we want a baseline of 50 a day which is
possible it happend today".

GBP50 a day is not one target. It is a completely different target depending
on the account it comes out of, and the difference is not a matter of degree:

  on GBP112   GBP50/day is  45% of the account per day
  on GBP1000  GBP50/day is   5% per day
  on GBP5000  GBP50/day is   1% per day

The first is not a low-risk goal that needs better execution. The third is a
demanding but coherent one. Nothing about the EA's code distinguishes them -
the same settings produce all three - so the question "what should the EA be
tuned for" cannot be answered until this is.

This computes, from the daily R the strategy actually generates, the account
size at which GBP50/day is a LOW-RISK target rather than a coin toss.

Run:  python3 JARVIS/research/target.py
"""
from __future__ import annotations
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, chop


def daily_R(expectancy_r, trades_per_day):
    return expectancy_r * trades_per_day


def main():
    print("=" * 82)
    print("  E-058  WHAT ACCOUNT DOES GBP50 A DAY NEED?")
    print("=" * 82)

    # ---- what does a day actually generate, in R?
    print("\n  STEP 1 — how much R does a day produce?")
    print("  Veer reports the M1 EA generating on the order of 50-100 signals")
    print("  a day. Expectancy per trade is the number nobody can promise:")
    print("  E-050 could not separate this entry from a random one, and the")
    print("  best honest figure measured anywhere in this repo is GOLD 15m at")
    print("  +0.227R. Everything below is therefore conditional - 'IF the edge")
    print("  is this, THEN', not a forecast.\n")

    print(f"  {'expectancy':<14}{'trades/day':>12}{'R per day':>12}"
          f"{'% of account/day at 1% risk':>30}")
    for e in (0.05, 0.10, 0.227, 0.35):
        for n in (20, 50):
            dr = daily_R(e, n)
            print(f"  {e:>+9.3f}R    {n:>12}{dr:>12.2f}{dr * 1.0:>29.1f}%")
    print("\n  Read the right-hand column carefully. At +0.227R and 50 trades")
    print("  a day that is 11.4% of the account PER DAY at 1% risk, which is")
    print("  already an extraordinary claim - it compounds to roughly 25x in a")
    print("  month. The realistic reading is that either the expectancy or the")
    print("  trade count in that row is too high, and the honest response is")
    print("  to measure it on M1 rather than argue about it.")

    # ---- account size needed
    print("\n" + "=" * 82)
    print("  STEP 2 — the account size GBP50/day implies")
    print("=" * 82)
    print(f"\n  {'daily return':<16}{'account for GBP50/day':>24}"
          f"{'what that daily return is':>32}")
    for pct in (0.5, 1.0, 2.0, 5.0, 10.0, 45.0):
        need = 50.0 / (pct / 100.0)
        if pct <= 1.0:
            note = "demanding but coherent"
        elif pct <= 2.0:
            note = "very good, sustainable"
        elif pct <= 5.0:
            note = "top decile, hard to sustain"
        elif pct <= 10.0:
            note = "not sustainable"
        else:
            note = "this is what GBP112 requires"
        print(f"  {pct:>6.1f}% / day{need:>22,.0f}   {note:>30}")

    # ---- the compounding reality check
    print("\n" + "=" * 82)
    print("  STEP 3 — why 'GBP50/day on GBP112' cannot be a baseline")
    print("=" * 82)
    eq = 112.0
    print(f"\n  If GBP50/day were truly a BASELINE on a GBP112 account, and the")
    print(f"  account compounded at that rate on 20 trading days:\n")
    for d in (1, 5, 10, 20):
        v = 112.0 * (1.45 ** d)
        print(f"    after {d:>2} days   GBP{v:>18,.0f}")
    print(f"\n  That is the arithmetic of 45% a day, and it is why the word")
    print(f"  'baseline' cannot attach to it. One GBP50 day on GBP112 is a")
    print(f"  real event that happened. A BASELINE of GBP50/day on GBP112 is")
    print(f"  a different claim, and the table above is what it implies.")

    # ---- what risk is needed, and what it costs
    print("\n" + "=" * 82)
    print("  STEP 4 — the risk GBP50/day needs on a small account, and its cost")
    print("=" * 82)
    rs, _mean, _n = _zero_edge()
    print(f"\n  Using the REAL SuperTrend payoff shape with expectancy forced to")
    print(f"  ZERO, 40 trades, 20,000 runs:\n")
    print(f"  {'risk/trade':<12}{'P(+45% day)':>14}{'P(-45% day)':>14}"
          f"{'P(halved)':>12}")
    for risk in (0.01, 0.02, 0.05, 0.10, 0.20):
        up, dn, half = _day(rs, risk)
        print(f"  {100*risk:>7.0f}%     {100*up:>13.1f}%{100*dn:>13.1f}%"
              f"{100*half:>11.1f}%")
    print("\n  The two middle columns are the same coin. There is no risk")
    print("  setting where the good day is likely and the bad day is not.")

    print("\n" + "=" * 82)
    print("  WHAT THIS MEANS FOR THE EA")
    print("=" * 82)
    print("""
  GBP50/day is a coherent, low-risk target - at GBP2,500 to GBP5,000, where it
  is 1-2% a day. On GBP112 it requires the risk settings that halve the account
  in the majority of sessions (E-054), and no amount of execution work changes
  that: closing at peaks improves what you keep from a move, it does not make
  a 45% daily return low-risk.

  So the EA should be tuned for the account it will grow into, not for the one
  it is on. The settings that get GBP112 to GBP5,000 fastest are also the ones
  most likely to take it to zero first, and the EA cannot tell which of those
  two runs it is in until afterwards.

  The part of Veer's claim that IS supported: today's session left money on the
  table, the give-back was real and measurable, and closing nearer the peak is
  worth a measurable amount (E-051b, E-056, E-057). That is a genuine
  improvement to capture. It is not the same claim as GBP50 a day being a floor.
""")


def _zero_edge():
    s = engine.load("GOLD", "15m")
    rows = chop.collect(s, study.COSTS.get("GOLD", engine.Costs()))
    rs = [r["r"] for r in rows]
    m = sum(rs) / len(rs)
    return [r - m for r in rs], m, len(rs)


def _day(rs, risk, n=40, trials=20000, seed=9):
    rng = random.Random(seed)
    up = dn = half = 0
    k = len(rs)
    for _ in range(trials):
        eq = 1.0
        low = 1.0
        for _ in range(n):
            eq += eq * risk * rs[rng.randrange(k)]
            low = min(low, eq)
            if eq <= 0.02:
                break
        if eq >= 1.45:
            up += 1
        if eq <= 0.55:
            dn += 1
        if low <= 0.5:
            half += 1
    return up / trials, dn / trials, half / trials


if __name__ == "__main__":
    main()

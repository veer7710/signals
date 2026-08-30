"""
SMALL ACCOUNT SIMULATION — what a 60 pound account can and cannot do.

Veer: "i wanna trade and bring a 60 pound account to 150 in a day tmr".

That is a +150% day. It is a question with a computable answer, so this
computes it instead of arguing about it.

THE CONSTRAINT THAT DRIVES EVERYTHING
  The minimum lot on gold is 0.01, which is about 1.00 of account currency per
  1.00 of price. The measured stop on this strategy is ~12.4 points. So one
  trade risks about 12.40 - and on a 60 pound account that is 20.7% of the
  account, on the SMALLEST position it is possible to open. You cannot risk
  less. The account size chooses the risk, not the trader.

METHOD
  Real measured trades from the engine (no invented numbers), bootstrapped into
  days at the measured trade rate, 20,000 simulated days. Each trade's outcome
  is its actual R multiple; the money is that R times the real per-trade risk.

Run:  python3 JARVIS/research/small_account.py
"""
from __future__ import annotations
import os, sys, random, statistics as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
import study
from engine import Costs
import strategies as S

random.seed(20260830)          # reproducible


def trades_for(sym, tf):
    s = engine.load(sym, tf)
    fn = S.supertrend_sniper_ea(s) if callable(getattr(S, "supertrend_sniper_ea", None)) \
         else None
    if fn is None:
        return [], 0.0
    tr = engine.backtest(s, fn, study.COSTS.get(sym, Costs()),
                         warmup=300, max_bars=50)
    days = (s.ts[-1] - s.ts[0]) / 86400.0
    return tr, (len(tr) / days if days else 0.0)


def simulate(rs, per_day, start, target, stop_money, n=20000):
    """Bootstrap whole days. stop_money is what ONE trade risks, in account
    currency, at the minimum 0.01 lot."""
    if not rs or per_day <= 0:
        return None
    hit = ruin = 0
    ends = []
    for _ in range(n):
        eq = start
        k = 0
        # trades per day varies; Poisson-ish via fractional carry
        m = int(per_day) + (1 if random.random() < (per_day % 1) else 0)
        for _ in range(m):
            if eq < stop_money:        # cannot open the minimum lot any more
                break
            eq += random.choice(rs) * stop_money
            k += 1
        ends.append(eq)
        if eq >= target: hit += 1
        if eq <= stop_money: ruin += 1
    ends.sort()
    return {"hit": hit / n, "ruin": ruin / n, "median": ends[n // 2],
            "p5": ends[int(0.05 * n)], "p95": ends[int(0.95 * n)],
            "trades_per_day": per_day}


def run(sym, tf, start=60.0, target=150.0):
    tr, per_day = trades_for(sym, tf)
    if not tr:
        print(f"  {sym} {tf}: no trades"); return
    rs = [t.r for t in tr]
    stops = [abs(t.entry - t.stop) for t in tr]
    med_stop = st.median(stops)
    exp = sum(rs) / len(rs)

    # 0.01 lot on gold ~ 1.00 account ccy per 1.00 of price
    risk_money = med_stop * 1.00

    print(f"\n{'='*72}\n  {sym} {tf}  —  {len(tr)} measured trades, "
          f"{per_day:.2f}/day, expectancy {exp:+.3f}R\n{'='*72}")
    print(f"  median stop        : {med_stop:.2f} points")
    print(f"  risk at 0.01 lot   : {risk_money:.2f}  "
          f"= {100*risk_money/start:.1f}% of a {start:.0f} account, "
          f"and you cannot go smaller")

    # The ceiling, before any question of probability: if EVERY trade in a day
    # were a full winner, where does the account actually land?
    best_r = max(rs)
    ceiling = start + per_day * best_r * risk_money
    print(f"\n  BEST POSSIBLE DAY (every trade a maximum winner, {best_r:.2f}R):")
    print(f"     {start:.0f} -> {ceiling:.2f}   "
          f"{'reaches' if ceiling >= target else 'CANNOT REACH'} {target:.0f}")

    r = simulate(rs, per_day, start, target, risk_money)
    if not r: return
    print(f"\n  ONE DAY, starting {start:.0f}, aiming for {target:.0f}:")
    print(f"     reaches {target:.0f}          : {100*r['hit']:.2f}%")
    print(f"     account effectively gone : {100*r['ruin']:.2f}%")
    print(f"     median end of day        : {r['median']:.2f}")
    print(f"     5th / 95th percentile    : {r['p5']:.2f} / {r['p95']:.2f}")

    # what it takes if you keep going
    for days, label in ((5, "a week"), (21, "a month")):
        rr = simulate(rs, per_day * days, start, target, risk_money)
        print(f"     over {label:<8}: reaches {target:.0f} {100*rr['hit']:.1f}%, "
              f"gone {100*rr['ruin']:.1f}%, median {rr['median']:.2f}")


if __name__ == "__main__":
    print(__doc__)
    for sym, tf in (("GOLD", "15m"), ("GOLD", "1h")):
        run(sym, tf)
    print("\n" + "=" * 72)
    print("  The minimum lot is the whole problem. On a 60 pound account the")
    print("  smallest position it is possible to open already risks about a")
    print("  fifth of the account, so position sizing - the only real defence")
    print("  against a losing streak - is not available at this account size.")
    print("=" * 72)

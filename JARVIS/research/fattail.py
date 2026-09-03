"""
E-090 — "we can't measure rr because some trades do 40rr some 0.5"

Veer is right and this is a criticism of my method, not of the strategy.

Every SuperTrend measurement in this project has used a FIXED TARGET - 2R or
3R. If the edge lives in a fat tail, a fixed target is the one thing guaranteed
to destroy it: it converts the 40R trade into a 3R trade and then reports the
average as though nothing was lost. Worse, it makes the COST analysis wrong
too, because one 40R winner pays the spread on a great many losers.

So this measures the strategy the way he actually trades it: A TIGHT STOP AND
NO CEILING. The only exit is a trail, and the trade ends where the market ends
it. What matters then is not the mean - it is the SHAPE:

    how many trades reach 5R, 10R, 20R, 40R at all
    what share of ALL the profit those few trades carry
    whether the tail survives M1's cost burden, which the capped version did not

If the top 5% of trades carry most of the money, then "expectancy" was never
the right summary and every conclusion drawn from it needs re-reading.

Run:  python3 JARVIS/research/fattail.py
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, strategies
from engine import Series
from liquidity import stat

GBP = 1.00 / 1.27


def run(s: Series, costs, stop_atr, trail_atr, arm_r=0.0, max_bars=600,
        warmup=300, target_r=None):
    """Tight stop, trailing exit, NO CEILING unless target_r is given."""
    d, fu, fl = strategies.supertrend_dir(s, 7, 1.2)
    A = engine.atr(s, 7)
    D = strategies.dema(s.c, 200)
    half = costs.spread / 2.0
    comm = costs.commission_per_lot / costs.value_per_point_per_lot
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
            continue

        j = i + 1
        entry = s.o[j] + side * (half + costs.slippage)
        stop = s.c[i] - side * stop_atr * a
        risk = (entry - stop) * side
        if risk <= 0:
            continue
        tgt = entry + side * target_r * risk if target_r else None
        cur = stop
        peak = 0.0
        done = None
        for k in range(j, min(j + max_bars, len(s))):
            fav = (s.h[k] - entry) if side == 1 else (entry - s.l[k])
            if fav > peak:
                peak = fav
            hs = (s.l[k] <= cur) if side == 1 else (s.h[k] >= cur)
            if hs:
                done = (cur, k); break                    # ties lose
            if tgt is not None:
                ht = (s.h[k] >= tgt) if side == 1 else (s.l[k] <= tgt)
                if ht:
                    done = (tgt, k); break
            if peak / risk >= arm_r:
                t = s.c[k] - side * trail_atr * a
                if (t - cur) * side > 0:
                    cur = t
        if done is None:
            k = min(j + max_bars, len(s)) - 1
            done = (s.c[k], k)
        px, k = done
        fill = px - side * (half + costs.slippage)
        out.append({"r": ((fill - entry) * side - comm) / risk,
                    "pts": (fill - entry) * side - comm,
                    "mfe_r": peak / risk, "bars": k - j})
        busy = k
    return out


def shape(name, tr):
    if not tr:
        return
    rs = sorted(x["r"] for x in tr)
    tot = sum(x["pts"] for x in tr)
    n = len(tr)
    a = stat(tr)
    print(f"\n  {name}")
    print(f"    n {n}   win {a['win']:.1f}%   mean {a['exp']:+.3f}R   PF {a['pf']:.2f}"
          f"   t {a['t']:+.2f}   {tot:+.0f} points")
    print(f"    best trade {rs[-1]:+.1f}R    worst {rs[0]:+.1f}R"
          f"    median {rs[n//2]:+.2f}R")
    # how many reach each rung, and what share of the profit they carry
    gross = sum(x["pts"] for x in tr if x["pts"] > 0) or 1.0
    print(f"    {'reached':>10}{'trades':>8}{'% of all':>10}{'their points':>14}"
          f"{'% of gross profit':>19}")
    for rung in (2, 5, 10, 20, 40):
        sel = [x for x in tr if x["r"] >= rung]
        if not sel:
            continue
        p = sum(x["pts"] for x in sel)
        print(f"    {('%dR+' % rung):>10}{len(sel):>8}{100.0*len(sel)/n:>9.1f}%"
              f"{p:>14.0f}{100.0*p/gross:>18.0f}%")
    # the top 5% of trades
    k = max(1, n // 20)
    top = sorted(tr, key=lambda x: -x["pts"])[:k]
    print(f"    TOP 5% ({k} trades) carry {100.0*sum(x['pts'] for x in top)/gross:.0f}%"
          f" of gross profit")


def main():
    print("=" * 96)
    print("  E-090  THE FAT TAIL — measuring SuperTrend with NO CEILING")
    print("  Every earlier measurement capped the winner at 2R or 3R. If the edge")
    print("  is in the tail, that cap is what destroyed it. Tight stop, trail, and")
    print("  the trade ends where the market ends it. Ties lose, costs both ends.")
    print("=" * 96)

    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        print(f"\n  ### {sym} {tf}")
        shape("CAPPED at 3R, stop 2.0 ATR  (what every earlier test did)",
              run(s, c, 2.0, 3.0, target_r=3.0))
        shape("UNCAPPED, stop 2.0 ATR, trail 3 ATR",
              run(s, c, 2.0, 3.0))
        shape("UNCAPPED, stop 0.6 ATR, trail 3 ATR  (tight stop, let it run)",
              run(s, c, 0.6, 3.0))
        shape("UNCAPPED, stop 0.6 ATR, trail 1.5 ATR",
              run(s, c, 0.6, 1.5))

    # ---- and the question that actually decides M1
    print("\n" + "=" * 96)
    print("  DOES THE UNCAPPED VERSION SURVIVE M1's COST BURDEN?")
    print("  The capped one did not: +0.249R fell to +0.041R. A fat tail should")
    print("  care far LESS about the spread, because one big winner pays for many.")
    print("=" * 96)
    s = engine.load("GOLD", "1h")
    print(f"\n   {'spread':>9}{'stop':>8}{'n':>6}{'win%':>7}{'mean':>9}{'PF':>7}"
          f"{'t':>7}{'points':>9}{'best':>8}")
    print("   " + "-" * 72)
    for st_ in (0.6, 2.0):
        for sp in (0.46, 1.00, 1.80, 2.40):
            c = engine.Costs(spread=sp, slippage=0.05, commission_per_lot=0.0,
                             value_per_point_per_lot=100.0)
            tr = run(s, c, st_, 3.0)
            if len(tr) < 25:
                continue
            a = stat(tr)
            print(f"   {sp:>9.2f}{st_:>7.1f}A{a['n']:>6}{a['win']:>6.1f}%"
                  f"{a['exp']:>+8.3f}R{a['pf']:>7.2f}{a['t']:>+7.2f}"
                  f"{sum(x['pts'] for x in tr):>+9.0f}"
                  f"{max(x['r'] for x in tr):>+7.1f}R")


if __name__ == "__main__":
    main()

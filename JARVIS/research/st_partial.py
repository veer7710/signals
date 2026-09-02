"""
E-072 — Two lots, two jobs. Does scaling out give Veer the shape he wants?

E-071 put a hard number on a conflict that has been running all session.

  Veer, three times in writing: "we are not looking for massive profits ... we
  want small consistent profits hundreds of times", "im happy if maximum
  potential profit on a trend is not taken as long as we actually took a solid
  ammount".

  E-071, GOLD 1h, SuperTrend flips, stop 3.0 ATR, target 0.25 ATR:
  90.9% WIN RATE, walk-forward 0 of 6 blocks, MINUS 611 POINTS.

A 91% win rate that loses money is not a paradox, it is arithmetic: the near
target caps every winner while the wide stop pays every loser in full. On the
SuperTrend flip the money is in the 1R-3R tail and nothing else, which is the
OPPOSITE of what E-069 found for liquidity sweeps. Different trade, different
physics: a sweep is a rejection, a flip is a breakout.

But Veer does not trade one lot. He trades 0.02 as TWO 0.01s - "we will trade
only 0.02 for entry and 0.01 for scalps", "was up 2.50 on two 0.01s total".
That structure can hold both shapes at once, so this measures it honestly:

  runner      both lots to the far target                (E-071's winner)
  scalp       both lots to the near target               (what Veer describes)
  split_be    half at the near target, half runs, and the stop on the
              remainder moves to break-even when the first half is banked
  split_hold  half at the near target, half runs, stop UNCHANGED

split_be is the version everyone reaches for and it is the one to distrust:
moving to break-even sounds free and is not. It converts trades that would have
dipped and recovered into scratches, and E-047 already measured break-even as
the worst exit rule on all four markets tested. This is that claim re-run on
the EA's own signals, with the scale-out that makes it plausible.

Reported per lot-pair, so a row's R is what the WHOLE 0.02 made, and the
points column is what it made in pounds at Veer's actual size.

Ties lose. Costs charged on every leg - a scale-out pays the spread twice.

Run:  python3 JARVIS/research/st_partial.py
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from engine import Series
from liquidity import stat
from st_entry import signals, COMBOS


def run(s: Series, costs, events, mode, stop_atr=2.0, near_atr=0.5,
        far_r=2.0, max_bars=200):
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot
    trades, busy = [], -1

    for ev in events:
        i, side, a = ev["i"], ev["side"], ev["atr"]
        if i <= busy:
            continue
        j = i + 1
        if j >= len(s):
            continue
        entry = s.o[j] + side * (half + costs.slippage)
        stop = ev["close"] - side * stop_atr * a
        risk = (entry - stop) * side
        if risk <= 0:
            continue
        near = entry + side * near_atr * a
        far = entry + side * far_r * risk

        # w1 is the first lot's weight, w2 the second's
        if mode == "runner":  w1, t1 = 0.0, None
        elif mode == "scalp": w1, t1 = 1.0, near
        else:                 w1, t1 = 0.5, near

        banked = 0.0          # in price units, weighted
        # THE WHOLE POSITION IS AT RISK UNTIL THE FIRST TARGET IS BANKED.
        # This started at 1.0 - w1, so a stop-out before the scale-out banked
        # only the remainder's loss - and in 'scalp' mode, where w1 is 1.0, it
        # banked NOTHING. That produced a profit factor of 0.00 (no losses at
        # all) and a t of +63, which is what gave it away.
        left = 1.0
        cur_stop = stop
        got1 = False
        done = None

        for k in range(j, min(j + max_bars, len(s))):
            hs = (s.l[k] <= cur_stop) if side == 1 else (s.h[k] >= cur_stop)
            # TIES LOSE: the stop is checked first, on every bar, including the
            # bar the first target is hit on.
            if hs:
                px = cur_stop
                fill = px - side * (half + costs.slippage)
                banked += left * ((fill - entry) * side)
                done = (k, "stop" if not got1 else "stop_after_scale")
                left = 0.0
                break
            if (not got1) and t1 is not None:
                h1 = (s.h[k] >= t1) if side == 1 else (s.l[k] <= t1)
                if h1:
                    fill = t1 - side * (half + costs.slippage)
                    banked += w1 * ((fill - entry) * side)
                    left = 1.0 - w1
                    got1 = True
                    if mode == "split_be":
                        # break-even PLUS the round trip, so a scratch is a
                        # scratch and not a small loss
                        cur_stop = entry + side * (2 * (half + costs.slippage) + comm_px)
                    if left <= 0.0:
                        done = (k, "scalp")
                        break
            if left > 0.0:
                h2 = (s.h[k] >= far) if side == 1 else (s.l[k] <= far)
                if h2:
                    fill = far - side * (half + costs.slippage)
                    banked += left * ((fill - entry) * side)
                    done = (k, "target")
                    left = 0.0
                    break
        if done is None:
            k = min(j + max_bars, len(s)) - 1
            fill = s.c[k] - side * (half + costs.slippage)
            banked += left * ((fill - entry) * side)
            done = (k, "time")
        k, why = done
        # commission is charged per leg actually closed
        legs = 2.0 if (t1 is not None and got1 and w1 < 1.0) else 1.0
        r = (banked - comm_px * legs) / risk
        trades.append({"r": r, "why": why, "bars": k - j,
                       "pts": banked - comm_px * legs})
        busy = k
    return trades


MODES = ["runner", "scalp", "split_hold", "split_be"]


def main():
    print("=" * 104)
    print("  E-072  ONE ENTRY, TWO LOTS — does scaling out give Veer his shape?")
    print("  stop 2.0 ATR · near target 0.5 ATR · far target 2R · market entry")
    print("  R and points are for the WHOLE 0.02, so the rows are comparable.")
    print("  Ties lose. The stop is checked before the near target on every bar.")
    print("  Costs charged on EVERY leg - a scale-out pays the spread twice.")
    print("=" * 104)

    pooled = {m: [] for m in MODES}
    gold = {m: [] for m in MODES}
    for sym, tf in COMBOS:
        try:
            s = engine.load(sym, tf)
        except Exception:
            continue
        c = study.COSTS.get(sym, engine.Costs())
        ev = signals(s)
        print(f"\n  ### {sym} {tf}   {len(ev)} flips")
        print(f"   {'mode':<12}{'n':>6}{'win%':>8}{'expect':>10}{'PF':>7}{'t':>7}"
              f"{'total R':>10}{'points':>10}")
        for m in MODES:
            tr = run(s, c, ev, m)
            pooled[m] += tr
            if sym == "GOLD":
                gold[m] += tr
            if not tr:
                continue
            a = stat(tr)
            pts = sum(x["pts"] for x in tr)
            print(f"   {m:<12}{a['n']:>6}{a['win']:>7.1f}%{a['exp']:>+9.3f}R"
                  f"{a['pf']:>7.2f}{a['t']:>+7.2f}{a['exp']*a['n']:>+9.1f}R{pts:>+9.1f}")

    for name, book in (("GOLD ONLY — the account Veer actually runs", gold),
                       ("POOLED, all eight markets", pooled)):
        print(f"\n  {name}")
        print("  " + "-" * 86)
        print(f"   {'mode':<12}{'n':>6}{'win%':>8}{'expect':>10}{'PF':>7}{'t':>7}"
              f"{'total R':>10}{'points':>10}")
        for m in MODES:
            tr = book[m]
            if not tr:
                continue
            a = stat(tr)
            pts = sum(x["pts"] for x in tr)
            print(f"   {m:<12}{a['n']:>6}{a['win']:>7.1f}%{a['exp']:>+9.3f}R"
                  f"{a['pf']:>7.2f}{a['t']:>+7.2f}{a['exp']*a['n']:>+9.1f}R{pts:>+9.1f}")

    print("\n  WHAT TO LOOK AT")
    print("  * 'scalp' is the shape Veer describes wanting. Read its points column.")
    print("  * 'split_be' is the one that feels safest. Compare it to split_hold:")
    print("    the difference between them is the entire cost of moving to")
    print("    break-even, with nothing else changed.")


if __name__ == "__main__":
    main()

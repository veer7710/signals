"""
E-091 — The disaster brake. A wide stop is only safe if something cuts sooner.

Veer: "stop loss initially is way too far, if news or reversals happens that's a
massive massive loss unless we can close immediately thru ea".

He is right, and it is a direct consequence of my own fix. E-089 forced the stop
WIDER so the spread could not own it - 7 round trips - which makes a full
stop-out a big loss. A wide stop without a faster brake is not risk management,
it is just a bigger bet.

But "cut early" is exactly the kind of rule that FEELS safe and costs money, so
it gets measured, not assumed. Three brakes, each testable:

  NEVER GREEN   the trade has gone `adverse` of the stop against us within
                `bars` and has never been more than `green` in profit. That is
                not a trade going wrong, it is an entry that was wrong - which
                is Veer's "enter late / enter wrong / enter on bad signals".
  VELOCITY      price has moved `v` ATR against us inside `vbars` bars. This is
                the news spike, and it is the one that cannot wait for a stop.
  BOTH

For each: what does it save, what does it cost, and what is the NET. The
question is never "does it avoid losses" - of course it does - it is whether
the trades it cuts would have recovered.

Run:  python3 JARVIS/research/brake.py
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, strategies
from liquidity import stat

GBP = 1.00 / 1.27


def run(s, costs, brake=None, stop_atr=2.0, trail_atr=3.0, warmup=300,
        max_bars=600, adverse=0.50, bars=5, green=0.10, v=1.0, vbars=2):
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
        cur, peak = stop, 0.0
        done = None
        for k in range(j, min(j + max_bars, len(s))):
            fav = (s.h[k] - entry) if side == 1 else (entry - s.l[k])
            adv = (entry - s.l[k]) if side == 1 else (s.h[k] - entry)
            if fav > peak:
                peak = fav
            hs = (s.l[k] <= cur) if side == 1 else (s.h[k] >= cur)
            if hs:
                done = (cur, k, "stop"); break

            # ---- the brakes, checked on the CLOSED bar
            if brake in ("nevergreen", "both"):
                if (k - j) <= bars and peak < green * risk and adv >= adverse * risk:
                    done = (s.c[k], k, "brake:never green"); break
            if brake in ("velocity", "both"):
                if k - j >= vbars:
                    move = (s.c[k - vbars] - s.c[k]) * side
                    if move >= v * a and (s.c[k] - entry) * side < 0:
                        done = (s.c[k], k, "brake:velocity"); break

            t = s.c[k] - side * trail_atr * a
            if (t - cur) * side > 0:
                cur = t
        if done is None:
            k = min(j + max_bars, len(s)) - 1
            done = (s.c[k], k, "cap")
        px, k, why = done
        fill = px - side * (half + costs.slippage)
        out.append({"r": ((fill - entry) * side - comm) / risk,
                    "pts": (fill - entry) * side - comm, "why": why,
                    "i": i, "bars": k - j})
        busy = k
    return out


def line(nm, tr, base_pts):
    a = stat(tr)
    p = sum(x["pts"] for x in tr)
    braked = [x for x in tr if x["why"].startswith("brake")]
    print(f"   {nm:<30}{a['n']:>6}{a['win']:>7.1f}%{a['exp']:>+9.3f}R{a['pf']:>7.2f}"
          f"{a['t']:>+7.2f}{p:>+9.0f}{p-base_pts:>+9.0f}{len(braked):>8}")


def main():
    print("=" * 100)
    print("  E-091  THE DISASTER BRAKE — a wide stop is only safe if something cuts sooner")
    print("  'delta' is points against leaving it alone. A brake that avoids losses")
    print("  and still loses money has cut trades that would have recovered.")
    print("=" * 100)

    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        base = run(s, c, None)
        bp = sum(x["pts"] for x in base)
        print(f"\n  ### {sym} {tf}")
        print(f"   {'brake':<30}{'n':>6}{'win%':>8}{'expect':>10}{'PF':>7}{'t':>7}"
              f"{'points':>9}{'delta':>9}{'cut':>8}")
        print("   " + "-" * 90)
        line("none (leave it alone)", base, bp)
        for adv in (0.40, 0.55, 0.70):
            for bb in (3, 6, 10):
                line(f"never green: {adv:.2f} in {bb} bars",
                     run(s, c, "nevergreen", adverse=adv, bars=bb), bp)
        for vv in (0.8, 1.2, 1.8):
            line(f"velocity: {vv:.1f} ATR in 2 bars",
                 run(s, c, "velocity", v=vv), bp)
        line("both (0.55/6 and 1.2 ATR)",
             run(s, c, "both", adverse=0.55, bars=6, v=1.2), bp)


if __name__ == "__main__":
    main()

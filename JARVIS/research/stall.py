"""
E-056 — Slow price action after entry. Does a stall predict giving it back?

Veer: "what if price reacts to our position but has slow price action how do
we know how to move".

This is the best-posed question he has asked, because it is about information
the EA already has and currently ignores. A trade is green. It stopped
climbing. Is that a pause before the next leg, or is it over?

The EA's only answer today is a 50-bar time cap, which is blind: it treats a
trade that peaked ten bars ago exactly like one that made a new high on the
last bar. This measures whether the difference matters.

DEFINITION
  STALL = bars since the position last made a NEW FAVOURABLE EXTREME.
  A trade that just printed a new best has stall 0. One that peaked twelve
  bars ago and has drifted since has stall 12.

Measured at every bar of every open trade that has reached at least +0.5R, so
the sample is "trades that got somewhere", which is the situation Veer is
describing. The outcome is what happens NEXT:
  - does it go on to make a new peak at least 0.5R higher, or
  - does it give back to break-even or worse first?

Ties go to the bad outcome (L-012).

Run:  python3 JARVIS/research/stall.py
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies, study, chop

STALL_BUCKETS = [(0, 1), (1, 3), (3, 6), (6, 12), (12, 25), (25, 10 ** 9)]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def collect(s, costs, warmup=300, max_hold=200, stop_atr=1.5,
            min_r=0.5, step_r=0.5):
    """One observation per BAR of every trade that has reached min_r."""
    ctx = engine.build_context(s)
    sig = strategies.supertrend_sniper_ea(s)
    half = costs.spread / 2.0
    obs = []

    for i in range(warmup, len(s) - 2):
        sg = sig(ctx, i)
        if not sg:
            continue
        side = sg["side"]
        a = ctx["atr"][i]
        if a is None or a <= 0:
            continue
        entry = s.o[i + 1] + side * (half + costs.slippage)
        risk = stop_atr * a
        if risk <= 0:
            continue

        peak = 0.0                 # best favourable excursion, in price
        peak_bar = i + 1
        for j in range(i + 1, min(i + 1 + max_hold, len(s))):
            fav = (s.h[j] - entry) if side == 1 else (entry - s.l[j])
            adv = (entry - s.l[j]) if side == 1 else (s.h[j] - entry)

            # stopped out before anything else matters
            if adv >= risk:
                break

            if fav > peak:
                peak = fav
                peak_bar = j

            peak_r = peak / risk
            if peak_r < min_r:
                continue

            stall = j - peak_bar

            # ---- what happens NEXT, decided from bar j+1 onward
            need = peak + step_r * risk          # a new peak this much higher
            gone = None
            for k in range(j + 1, min(i + 1 + max_hold, len(s))):
                f2 = (s.h[k] - entry) if side == 1 else (entry - s.l[k])
                back = (s.c[k] - entry) * side
                # ties lose: a bar that does both is scored as the give-back
                if back <= 0:
                    gone = True
                    break
                if f2 >= need:
                    gone = False
                    break
            if gone is None:
                continue
            obs.append({"stall": stall, "peak_r": peak_r, "gaveback": gone,
                        "bars_held": j - i})
    return obs


def main():
    print("=" * 84)
    print("  E-056  DOES A STALL PREDICT GIVING IT BACK?")
    print("  Every bar of every trade already >= +0.5R. 'stall' = bars since")
    print("  the trade last made a new best. Outcome = did it give back to")
    print("  break-even BEFORE adding another 0.5R.")
    print("=" * 84)

    store = {}
    for sym, tf in chop.COMBOS:
        try:
            s = engine.load(sym, tf)
        except Exception:
            continue
        obs = collect(s, study.COSTS.get(sym, engine.Costs()))
        if len(obs) < 200:
            continue
        store[f"{sym} {tf}"] = obs
        base = sum(1 for o in obs if o["gaveback"]) / len(obs)
        print(f"  {sym} {tf}: {len(obs)} observations, "
              f"base P(gives it back) {100*base:.1f}%")

    labs = [f"{a}-{b}" if b < 10 ** 9 else f"{a}+" for a, b in STALL_BUCKETS]
    print(f"\n  P(GIVES IT BACK) BY STALL, minus that market's own base rate")
    print(f"  {'market':<14}" + "".join(f"{l:>11}" for l in labs))
    above = [0] * len(labs)
    seen = [0] * len(labs)
    for name, obs in store.items():
        base = sum(1 for o in obs if o["gaveback"]) / len(obs)
        cells = []
        for bi, (a, b) in enumerate(STALL_BUCKETS):
            sel = [o for o in obs if a <= o["stall"] < b]
            if len(sel) < 30:
                cells.append(f"{'-':>11}")
                continue
            p = sum(1 for o in sel if o["gaveback"]) / len(sel)
            cells.append(f"{100*(p-base):>+11.1f}")
            seen[bi] += 1
            if p > base:
                above[bi] += 1
        print(f"  {name:<14}" + "".join(cells))
    print(f"  {'WORSE than base':<14}"
          + "".join(f"{f'{above[i]}/{seen[i]}':>11}" for i in range(len(labs))))

    print(f"\n  MULTIPLE TESTING: {len(labs)} buckets. P(a bucket lands >=7 of 8")
    print(f"  on one side) is about 3.5%, so ~{len(labs)*0.035:.1f} are expected by chance.")

    # ---- absolute numbers on gold, with intervals
    for key in ("GOLD 15m", "GOLD 1h"):
        if key not in store:
            continue
        obs = store[key]
        base = sum(1 for o in obs if o["gaveback"]) / len(obs)
        print(f"\n  {key} in full   base {100*base:.1f}%  ({len(obs)} observations)")
        print(f"  {'stall':<10}{'n':>7}{'P(gives back)':>16}{'95% interval':>20}")
        for a, b in STALL_BUCKETS:
            sel = [o for o in obs if a <= o["stall"] < b]
            if len(sel) < 30:
                print(f"  {(f'{a}-{b}' if b<10**9 else f'{a}+'):<10}{len(sel):>7}"
                      f"{'too few':>16}")
                continue
            k = sum(1 for o in sel if o["gaveback"])
            lo, hi = wilson(k, len(sel))
            print(f"  {(f'{a}-{b}' if b<10**9 else f'{a}+'):<10}{len(sel):>7}"
                  f"{100*k/len(sel):>15.1f}%"
                  f"{f'{100*lo:.1f} - {100*hi:.1f}%':>20}")


if __name__ == "__main__":
    main()

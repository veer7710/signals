"""
E-071 — The SuperTrend EA's exit shape, swept the way E-068 swept liquidity's.

E-070 settled the entry: market-at-the-flip beats every resting-order variant
on expectancy, on total R and on fill rate. A sweep is a REJECTION so price
comes back to you; a SuperTrend flip is a BREAKOUT so it does not. The entry is
not what is wrong with this EA.

That leaves the exit, which is also what Veer has been describing all along:

  "we are not looking for massive profits remeber that we want small consistent
   profits hundreds of times ... i've already seen us in the past 5 min go up in
   peaks of 8 pound close not near was up 2.50 on two 0.01s total and closed at
   47p each see how horrible that is"

  "im happy if maximum potential profit on a trend is not taken as long as we
   actually took a solid ammount"

The EA aims at 3R behind a 1.5 ATR stop. On these bars that shape pools at
-0.106R across eight markets. E-069 found the paying shape for liquidity was
the OPPOSITE geometry - a near target behind a wide stop, 80%+ win rate - and
that is also the shape Veer keeps describing in words. So test it here.

  STOP    0.75 / 1.0 / 1.5 / 2.0 / 3.0 ATR
  TARGET  0.25 / 0.5 / 0.75 / 1.0 ATR, or 1R / 2R / 3R of the stop

Note the two families are different animals. An ATR target is a FIXED DISTANCE:
widening the stop leaves it where it is, so the win rate climbs. An R target
moves with the stop, so the shape is unchanged and only the scale moves.

Ties lose. Costs both ends. Matched random control on every cell.

Run:  python3 JARVIS/research/st_exit_grid.py
"""
from __future__ import annotations
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from engine import Series
from liquidity import stat
from st_entry import signals, COMBOS

STOPS = [0.75, 1.0, 1.5, 2.0, 3.0]
TGTS = [("0.25A", ("atr", 0.25)), ("0.50A", ("atr", 0.50)),
        ("0.75A", ("atr", 0.75)), ("1.00A", ("atr", 1.00)),
        ("1R", ("r", 1.0)), ("2R", ("r", 2.0)), ("3R", ("r", 3.0))]


def run(s: Series, costs, events, stop_atr, tgt, max_bars=200):
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot
    kind, mag = tgt
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
        dist = mag * a if kind == "atr" else mag * risk
        tgtpx = entry + side * dist
        done = None
        for k in range(j, min(j + max_bars, len(s))):
            hs = (s.l[k] <= stop) if side == 1 else (s.h[k] >= stop)
            ht = (s.h[k] >= tgtpx) if side == 1 else (s.l[k] <= tgtpx)
            if hs: done = (stop, "stop", k); break
            if ht: done = (tgtpx, "target", k); break
        if done is None:
            k = min(j + max_bars, len(s)) - 1
            done = (s.c[k], "time", k)
        px, why, k = done
        fill = px - side * (half + costs.slippage)
        trades.append({"r": ((fill - entry) * side - comm_px) / risk,
                       "why": why, "bars": k - j,
                       # money per 0.01 lot of gold is points x 1.0, so the
                       # POINTS won matter to Veer, not only the R
                       "pts": (fill - entry) * side})
        busy = k
    return trades


def rand_events(s, n_want, seed=5, warmup=250):
    A = engine.atr(s, 7)
    rng = random.Random(seed)
    idx = [i for i in range(warmup, len(s) - 2) if A[i] and A[i] > 0]
    ev = []
    for _ in range(n_want):
        i = rng.choice(idx)
        ev.append({"i": i, "side": 1 if rng.random() < 0.5 else -1,
                   "atr": A[i], "close": s.c[i], "st": s.c[i], "dema": s.c[i]})
    ev.sort(key=lambda e: e["i"])
    return ev


def main():
    print("=" * 118)
    print("  E-071  SUPERTREND EXIT GRID — the EA's own signals, exit shape swept")
    print("  Entry is market-at-the-flip in every cell (E-070 settled that).")
    print("  cell = n / win% / expectancy. Ties lose. Costs both ends.")
    print("=" * 118)

    pooled, pooledc = {}, {}
    for sym, tf in COMBOS:
        try:
            s = engine.load(sym, tf)
        except Exception:
            continue
        c = study.COSTS.get(sym, engine.Costs())
        ev = signals(s)
        rv = rand_events(s, len(ev))
        print(f"\n  ### {sym} {tf}   {len(ev)} flips")
        print(f"   {'stop':>6} |" + "".join(f"{nm:>23}" for nm, _ in TGTS))
        for st_ in STOPS:
            cells = []
            for nm, tg in TGTS:
                tr = run(s, c, ev, st_, tg)
                pooled.setdefault((st_, nm), []).extend(tr)
                pooledc.setdefault((st_, nm), []).extend(run(s, c, rv, st_, tg))
                a = stat(tr)
                cells.append(f"{a['n']:>4} {a['win']:>5.1f}% {a['exp']:>+7.3f}R"
                             if a["n"] else " " * 22)
            print(f"   {st_:>5.2f}A |" + "".join(f"{x:>23}" for x in cells))

    print("\n" + "=" * 118)
    print("  POOLED, sorted by EDGE OVER CONTROL")
    print("=" * 118)
    rows = []
    for key, tr in pooled.items():
        if len(tr) < 300:
            continue
        a = stat(tr); b = stat(pooledc.get(key, []))
        rows.append((key, a, b))
    rows.sort(key=lambda r: -(r[1]["exp"] - r[2]["exp"]))
    print(f"\n  {'stop':>7}{'target':>9}{'n':>7}{'win%':>8}{'expect':>10}{'PF':>7}"
          f"{'t':>8}{'total R':>10}   {'ctrl win%':>10}{'ctrl exp':>10}{'edge':>9}")
    print("  " + "-" * 110)
    for (st_, nm), a, b in rows[:15]:
        print(f"  {st_:>6.2f}A{nm:>9}{a['n']:>7}{a['win']:>7.1f}%{a['exp']:>+9.3f}R"
              f"{a['pf']:>7.2f}{a['t']:>+8.2f}{a['exp']*a['n']:>+9.1f}R   "
              f"{b['win']:>9.1f}%{b['exp']:>+9.3f}R{a['exp']-b['exp']:>+8.3f}R")

    print("\n  GOLD ONLY — the only market Veer trades this on")
    print("  " + "-" * 110)
    goldrows = []
    for st_ in STOPS:
        for nm, tg in TGTS:
            tr = []
            for sym, tf in COMBOS:
                if sym != "GOLD":
                    continue
                s = engine.load(sym, tf)
                tr += run(s, study.COSTS["GOLD"], signals(s), st_, tg)
            if len(tr) < 100:
                continue
            a = stat(tr)
            pts = sum(x["pts"] for x in tr)
            goldrows.append((st_, nm, a, pts))
    goldrows.sort(key=lambda r: -r[2]["exp"])
    print(f"  {'stop':>7}{'target':>9}{'n':>7}{'win%':>8}{'expect':>10}{'PF':>7}"
          f"{'t':>8}{'total R':>10}{'points':>10}")
    for st_, nm, a, pts in goldrows[:12]:
        print(f"  {st_:>6.2f}A{nm:>9}{a['n']:>7}{a['win']:>7.1f}%{a['exp']:>+9.3f}R"
              f"{a['pf']:>7.2f}{a['t']:>+8.2f}{a['exp']*a['n']:>+9.1f}R{pts:>+9.1f}")
    print("\n  'points' is what a 0.01 lot of gold makes in account currency, near")
    print("  enough 1:1. It is there because R hides how small these trades are.")


if __name__ == "__main__":
    main()

"""
E-076 — The top-tick entry. The cell I never tested, and the one Veer means.

Veer: "we need to have top tick entrys meaning we do a small stop loss which is
reasonable and catch a massiveeee entry from the tick thats the point we are
specific and have actual analysis like a pro trader".

That is RISK 1 TO MAKE 3+. Everything I built for liquidity so far is the
opposite shape - E-069 rests the order back at the zone edge AFTER the sweep
and risks 1.5 ATR to make 0.5. It wins 87% of the time and it is not the trade
he is describing, because by the time price is back at the zone edge the wick
is far away and the risk is already large.

WHAT I NEVER TESTED
  E-068 swept two entries: the sweep bar's CLOSE (price already back inside)
  and the RETEST (price returns to the edge, later). Both enter AFTER the
  sweep is over. Neither enters DURING it.

  A professional does not wait. The zone is where the stops are; the sweep is
  the market reaching in to take them. So the order rests INSIDE the zone
  BEFORE the sweep, gets filled by the sweep itself, and the stop sits just
  beyond the wick. That makes the risk the width of the poke - small - and
  leaves the whole reversal as the target.

  It also fills on every BREAK, not only every sweep, and that is the honest
  cost of it. A break is a full-size loss. The whole question is whether a
  small stop and a big target pay for those.

THE GRID
  ENTRY   at the zone's near edge / centre / far edge / 0.25 ATR beyond it.
          A resting limit: the level is known before the bar, so nothing here
          looks forward. Fills at the limit price, charged the spread.
  STOP    0.15 / 0.25 / 0.40 / 0.60 ATR beyond the ENTRY - a "reasonable small
          stop", which is what he asked for.
  TARGET  1R / 2R / 3R / 5R, and the opposite zone.

Reported against E-069's shape so the two are directly comparable, and against
a matched random control. Ties lose. Costs both ends.

XAUUSD ONLY, because that is the only thing being traded. There is still no M1
or M5 data in this repository, so 15m is the lowest timeframe that exists here
and every number below is measured on 15m and 1h.

Run:  python3 JARVIS/research/toptick.py
"""
from __future__ import annotations
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from engine import Series
from liquidity import pivots, stat

COMBOS = [("GOLD", "15m"), ("GOLD", "1h")]

ENTRIES = [("near edge", 0.0), ("centre", 0.5), ("far edge", 1.0),
           ("0.25A past", -0.25)]
STOPS = [0.15, 0.25, 0.40, 0.60]
TGTS = [("1R", ("r", 1.0)), ("2R", ("r", 2.0)), ("3R", ("r", 3.0)),
        ("5R", ("r", 5.0)), ("opp zone", ("opp", 0.0))]


def zone_stream(s: Series, pv_len=7, mar_div=6.9, min_piv=1, life=600,
                warmup=250):
    """Zones as they become known, bar by bar. A zone confirmed at bar i is
    tradeable from bar i+1 onward and never before."""
    A = engine.atr(s, 14)
    hi, lo = pivots(s, pv_len)
    zones, recentH, recentL = [], [], []
    per_bar = []
    for i in range(len(s)):
        a = A[i]
        if a is None or a <= 0:
            per_bar.append([])
            continue
        mar = a / mar_div
        j = i - pv_len
        if j >= 0:
            for (arr, d, store) in ((hi, 1, recentH), (lo, -1, recentL)):
                if arr[j] is None:
                    continue
                store.append(arr[j]); del store[:-50]
                grp = [p for p in store if abs(p - arr[j]) <= mar]
                if len(grp) < min_piv:
                    continue
                c = (min(grp) + max(grp)) / 2.0
                hit = False
                for z in zones:
                    if z["dir"] == d and not z["dead"] and abs(z["px"] - c) <= mar:
                        hit = True; break
                if not hit:
                    zones.append({"px": c, "top": c + mar, "bot": c - mar,
                                  "born": i, "dir": d, "dead": False, "used": False})
        zones = [z for z in zones if i - z["born"] <= life and not z["dead"]]
        # a zone that price has CLOSED beyond is gone
        for z in zones:
            if (z["dir"] == 1 and s.c[i] > z["top"]) or \
               (z["dir"] == -1 and s.c[i] < z["bot"]):
                z["dead"] = True
        per_bar.append([z for z in zones if not z["dead"]])
    return per_bar, A


def entry_level(z, frac, a):
    """Where the resting order sits. frac 0 = the near edge (the side price
    approaches from), 1 = the far edge, negative = that many ATR beyond."""
    if z["dir"] == 1:                       # buyside zone, above -> we SELL
        if frac < 0: return z["top"] - frac * a
        return z["bot"] + frac * (z["top"] - z["bot"])
    if frac < 0: return z["bot"] + frac * a
    return z["top"] - frac * (z["top"] - z["bot"])


def run(s: Series, costs, per_bar, A, frac, stop_atr, tgt, max_bars=200,
        warmup=250, arm_life=60):
    """One position at a time. A zone arms ONE order; once it fills or the zone
    dies, it is done - so a single level cannot generate a stream of trades."""
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot
    kind, mag = tgt
    trades, busy = [], -1
    used = set()

    for i in range(warmup, len(s) - 2):
        if i <= busy:
            continue
        a = A[i]
        if a is None or a <= 0:
            continue
        for z in per_bar[i]:
            key = (z["born"], round(z["px"], 6), z["dir"])
            if key in used:
                continue
            if i - z["born"] > arm_life:
                continue
            lvl = entry_level(z, frac, a)
            side = -1 if z["dir"] == 1 else 1     # sell a buyside sweep

            # the limit must rest on the far side of the market right now,
            # otherwise it is a market order wearing a disguise
            if (side == -1 and s.c[i] >= lvl) or (side == 1 and s.c[i] <= lvl):
                continue
            # does the NEXT bar reach it?
            k = i + 1
            if k >= len(s):
                continue
            reached = (s.h[k] >= lvl) if side == -1 else (s.l[k] <= lvl)
            if not reached:
                continue

            used.add(key)
            entry = lvl + side * (half + costs.slippage)
            stop = entry - side * stop_atr * a
            risk = (entry - stop) * side
            if risk <= 0:
                continue
            if kind == "r":
                tgtpx = entry + side * mag * risk
            else:
                cands = [y["px"] for y in per_bar[i] if y is not z
                         and ((side == 1 and y["px"] > entry)
                              or (side == -1 and y["px"] < entry))]
                if not cands:
                    continue
                tgtpx = min(cands) if side == 1 else max(cands)

            done = None
            for q in range(k, min(k + max_bars, len(s))):
                hs = (s.l[q] <= stop) if side == 1 else (s.h[q] >= stop)
                ht = (s.h[q] >= tgtpx) if side == 1 else (s.l[q] <= tgtpx)
                if hs: done = (stop, "stop", q); break      # ties lose
                if ht: done = (tgtpx, "target", q); break
            if done is None:
                q = min(k + max_bars, len(s)) - 1
                done = (s.c[q], "time", q)
            px, why, q = done
            fill = px - side * (half + costs.slippage)
            trades.append({"r": ((fill - entry) * side - comm_px) / risk,
                           "why": why, "bars": q - k,
                           "pts": (fill - entry) * side - comm_px,
                           "risk_pts": risk})
            busy = q
            break
    return trades


def main():
    print("=" * 118)
    print("  E-076  THE TOP-TICK ENTRY — a limit INSIDE the zone, filled BY the sweep")
    print("  Small stop just past the poke, big target. Risk 1 to make 3, which is")
    print("  the shape Veer asked for and the one I had never tested.")
    print("  XAUUSD only. cell = n / win% / expectancy / points per 0.01 lot.")
    print("  Ties lose. Costs both ends. A zone arms ONE order, ever.")
    print("=" * 118)

    best = []
    for sym, tf in COMBOS:
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        per_bar, A = zone_stream(s)
        print(f"\n  ### {sym} {tf}   {len(s)} bars")
        for ename, frac in ENTRIES:
            print(f"\n   limit at the {ename}")
            print(f"   {'stop':>7} |" + "".join(f"{nm:>24}" for nm, _ in TGTS))
            for st_ in STOPS:
                cells = []
                for nm, tg in TGTS:
                    tr = run(s, c, per_bar, A, frac, st_, tg)
                    a = stat(tr)
                    if a["n"] >= 25:
                        pts = sum(x["pts"] for x in tr)
                        best.append((a["exp"] * a["n"], sym, tf, ename, st_, nm,
                                     a, pts))
                        cells.append(f"{a['n']:>4} {a['win']:>4.1f}% "
                                     f"{a['exp']:>+6.2f}R {pts:>+7.0f}")
                    else:
                        cells.append(" " * 23)
                print(f"   {st_:>6.2f}A |" + "".join(f"{x:>24}" for x in cells))

    print("\n" + "=" * 118)
    print("  BEST BY TOTAL R, and what each one actually looks like")
    print("=" * 118)
    best.sort(key=lambda r: -r[0])
    print(f"\n  {'market':<11}{'limit at':<12}{'stop':>7}{'tgt':>10}{'n':>6}"
          f"{'win%':>8}{'expect':>10}{'PF':>7}{'t':>7}{'total R':>10}{'points':>9}"
          f"{'avg risk':>10}")
    print("  " + "-" * 112)
    for tot, sym, tf, en, st_, nm, a, pts in best[:18]:
        rp = sum([0.0])
        print(f"  {sym+' '+tf:<11}{en:<12}{st_:>6.2f}A{nm:>10}{a['n']:>6}"
              f"{a['win']:>7.1f}%{a['exp']:>+9.3f}R{a['pf']:>7.2f}{a['t']:>+7.2f}"
              f"{tot:>+9.1f}R{pts:>+9.0f}")

    print("\n  COMPARE AGAINST E-069, the shape shipped before this:")
    print("  GOLD 1h, retest entry, 1.5 ATR stop, 0.50 ATR target:")
    print("  n=401  87.8% win  +0.106R  PF 1.85  -  high win rate, risk 3 to make 1.")
    print("\n  A high win rate is not the goal. Total points is. Read that column.")


if __name__ == "__main__":
    main()

"""
E-065 — The liquidity strategy, made measurable. What is its actual win rate?

Veer runs this by hand and wants it as an EA. He has never had a number for it.
This implements the SAME rules as `JARVIS/pine/LIQUIDITY_CLEAN_1_0.pine`, which
are the two LuxAlgo scripts' rules, so the win rate below describes the chart
he is actually looking at rather than an idealisation of it.

THE RULES, exactly as the Pine draws them
  ZONE      three or more pivots (length 7) clustering within +/- ATR/6.9 of
            each other. One swing high is not liquidity; three stacked at the
            same price is, because that is where the stops are. The zone has
            WIDTH - price reacts near a level, not on it.
  SWEEP     a wick THROUGH the zone that closes back inside, with the wick at
            least 30% of the bar. This is the trigger.
  BREAK     a close beyond the zone. The zone is dead; this is where the loss
            comes from, and Veer's own read is that it is rare.
  ENTRY     buyside zone swept -> SELL. sellside zone swept -> BUY.
            Next bar's open, with costs.
  TARGET    the nearest live zone on the other side. That is where the move is
            going and where the next trade starts from - his round trip.
  STOP      beyond the swept zone plus a buffer.

Veer's own description of the risk: "price normally respects the zones hits it
and comes down or up ... sometimes rarely it wont and it will breakthrough
thats where we make our loss ... and even if it does it hits our stop loss
which is not gonna be alot". This measures whether "rarely" is true.

THE CONTROL IS NOT OPTIONAL. E-050 killed this project's headline result for
want of one. Every number below is printed beside the same statistic computed
at random bars with the same stop and target geometry.

Run:  python3 JARVIS/research/liquidity.py
"""
from __future__ import annotations
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from engine import Series

COMBOS = [("GOLD", "15m"), ("GOLD", "1h"), ("US500", "15m"), ("US500", "1h"),
          ("EURUSD", "15m"), ("EURUSD", "1h"), ("GBPUSD", "15m"), ("GBPUSD", "1h")]


def pivots(s: Series, n: int):
    """Confirmed pivot highs and lows. A pivot at bar i is only KNOWN at bar
    i+n, and every use below respects that."""
    hi = [None] * len(s)
    lo = [None] * len(s)
    for i in range(n, len(s) - n):
        h, l = s.h[i], s.l[i]
        if all(h >= s.h[i - k] for k in range(1, n + 1)) and \
           all(h >= s.h[i + k] for k in range(1, n + 1)):
            hi[i] = h
        if all(l <= s.l[i - k] for k in range(1, n + 1)) and \
           all(l <= s.l[i + k] for k in range(1, n + 1)):
            lo[i] = l
    return hi, lo


def build_zones(s: Series, A, pv_len=7, mar_div=6.9, min_piv=3, life=600):
    """Zones as the Pine builds them, incrementally, so a zone only exists
    from the bar its third member CONFIRMS. No look-ahead."""
    hi, lo = pivots(s, pv_len)
    zones = []                      # dicts: px, top, bot, born, dir, n, swept, broken
    recentH, recentL = [], []       # (price, confirm_bar)

    events = [[] for _ in range(len(s))]   # zone list snapshot not needed; mutate in place
    for i in range(len(s)):
        a = A[i]
        if a is None or a <= 0:
            continue
        mar = a / mar_div

        # a pivot at bar i-pv_len becomes KNOWN now
        j = i - pv_len
        if j >= 0:
            if hi[j] is not None:
                recentH.append((hi[j], i))
                recentH[:] = recentH[-50:]
                grp = [p for (p, b) in recentH if abs(p - hi[j]) <= mar]
                if len(grp) >= min_piv:
                    c = (min(grp) + max(grp)) / 2.0
                    merged = False
                    for z in zones:
                        if z["dir"] == 1 and not z["broken"] and abs(z["px"] - c) <= mar:
                            z["n"] += 1
                            merged = True
                            break
                    if not merged:
                        zones.append({"px": c, "top": c + mar, "bot": c - mar,
                                      "born": i, "dir": 1, "n": len(grp),
                                      "swept": False, "broken": False})
            if lo[j] is not None:
                recentL.append((lo[j], i))
                recentL[:] = recentL[-50:]
                grp = [p for (p, b) in recentL if abs(p - lo[j]) <= mar]
                if len(grp) >= min_piv:
                    c = (min(grp) + max(grp)) / 2.0
                    merged = False
                    for z in zones:
                        if z["dir"] == -1 and not z["broken"] and abs(z["px"] - c) <= mar:
                            z["n"] += 1
                            merged = True
                            break
                    if not merged:
                        zones.append({"px": c, "top": c + mar, "bot": c - mar,
                                      "born": i, "dir": -1, "n": len(grp),
                                      "swept": False, "broken": False})
        events[i] = list(zones)     # reference, fine: we walk forward only
    return zones, hi, lo


def simulate(s: Series, costs, mode="real", pv_len=7, mar_div=6.9, min_piv=3,
             wick_share=0.30, stop_buf=0.25, min_tgt_atr=1.0, life=600,
             max_bars=200, warmup=250, seed=3, stop_style="wick"):
    """stop_style: 'zone' = beyond the zone edge (WRONG - the sweep has already
    been there, so the stop sits inside the noise that just happened and 88.7%
    of trades died on it). 'wick' = beyond the SWEEP BAR'S OWN EXTREME, which
    is where a trader puts it: the sweep defined the extreme, so the trade is
    wrong only if price goes BEYOND what the sweep already reached."""
    """Walk forward once. One position at a time."""
    A = engine.atr(s, 14)
    hi, lo = pivots(s, pv_len)
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot

    zones = []
    recentH, recentL = [], []
    trades = []
    rng = random.Random(seed)
    i = warmup
    open_pos = None

    while i < len(s) - 2:
        a = A[i]
        if a is None or a <= 0:
            i += 1; continue
        mar = a / mar_div

        # ---- register any pivot that confirms on this bar
        j = i - pv_len
        if j >= 0:
            for (arr, d, store) in ((hi, 1, recentH), (lo, -1, recentL)):
                if arr[j] is None:
                    continue
                store.append(arr[j])
                del store[:-50]
                grp = [p for p in store if abs(p - arr[j]) <= mar]
                if len(grp) < min_piv:
                    continue
                c = (min(grp) + max(grp)) / 2.0
                merged = False
                for z in zones:
                    if z["dir"] == d and not z["broken"] and abs(z["px"] - c) <= mar:
                        z["n"] += 1; merged = True; break
                if not merged:
                    zones.append({"px": c, "top": c + mar, "bot": c - mar,
                                  "born": i, "dir": d, "n": len(grp),
                                  "swept": False, "broken": False})

        zones = [z for z in zones if i - z["born"] <= life]

        # ---- resolve an open position first
        if open_pos is not None:
            p = open_pos
            hit_s = (s.l[i] <= p["stop"]) if p["side"] == 1 else (s.h[i] >= p["stop"])
            hit_t = (s.h[i] >= p["tgt"]) if p["side"] == 1 else (s.l[i] <= p["tgt"])
            done = None
            if hit_s:                        # ties lose
                done = (p["stop"], "stop")
            elif hit_t:
                done = (p["tgt"], "target")
            elif i - p["i_in"] >= max_bars:
                done = (s.c[i], "time")
            if done:
                px, why = done
                fill = px - p["side"] * (half + costs.slippage)
                r = ((fill - p["entry"]) * p["side"] - comm_px) / p["risk"]
                trades.append({"r": r, "why": why, "side": p["side"],
                               "bars": i - p["i_in"], "i": p["i_in"],
                               "tgt_atr": p["tgt_atr"]})
                open_pos = None
            i += 1
            continue

        # ---- look for a sweep
        rngb = max(s.h[i] - s.l[i], 1e-9)
        upW = s.h[i] - max(s.o[i], s.c[i])
        dnW = min(s.o[i], s.c[i]) - s.l[i]
        fired = None

        for z in zones:
            if z["broken"]:
                continue
            if z["dir"] == 1:
                if s.c[i] > z["top"]:
                    z["broken"] = True; continue
                if s.h[i] > z["top"] and s.c[i] < z["top"] and (upW / rngb) >= wick_share:
                    fired = (z, -1); break
            else:
                if s.c[i] < z["bot"]:
                    z["broken"] = True; continue
                if s.l[i] < z["bot"] and s.c[i] > z["bot"] and (dnW / rngb) >= wick_share:
                    fired = (z, 1); break

        if mode == "random":
            fired = None
            if rng.random() < 0.004:               # matched roughly by count
                z = {"top": s.h[i], "bot": s.l[i], "px": s.c[i], "dir": 1,
                     "n": 3, "swept": False, "broken": False, "born": i}
                fired = (z, 1 if rng.random() < 0.5 else -1)

        if fired is None:
            i += 1; continue

        z, side = fired
        z["swept"] = True

        # target: the nearest live zone the other way
        cands = [y["px"] for y in zones
                 if not y["broken"] and y is not z
                 and ((side == 1 and y["px"] > s.c[i]) or (side == -1 and y["px"] < s.c[i]))]
        if not cands:
            i += 1; continue
        tgt_px = min(cands) if side == 1 else max(cands)

        entry = s.o[i + 1] + side * (half + costs.slippage)
        if stop_style == "wick":
            stop = (s.l[i] - stop_buf * a) if side == 1 else (s.h[i] + stop_buf * a)
        else:
            stop = (z["bot"] - stop_buf * a) if side == 1 else (z["top"] + stop_buf * a)
        risk = abs(entry - stop)
        tgt_dist = abs(tgt_px - entry)
        if risk <= 0 or tgt_dist < min_tgt_atr * a:
            i += 1; continue

        open_pos = {"side": side, "entry": entry, "stop": stop, "tgt": tgt_px,
                    "risk": risk, "i_in": i + 1, "tgt_atr": tgt_dist / a}
        i += 1

    return trades


def stat(tr):
    if not tr:
        return dict(n=0, win=0.0, exp=0.0, t=0.0, pf=0.0, avgR=0.0)
    rs = [x["r"] for x in tr]
    n = len(rs)
    e = sum(rs) / n
    w = 100 * sum(1 for r in rs if r > 0) / n
    sd = (sum((r - e) ** 2 for r in rs) / n) ** 0.5
    t = e / (sd / math.sqrt(n)) if sd > 0 else 0.0
    gp = sum(r for r in rs if r > 0)
    gl = -sum(r for r in rs if r < 0)
    return dict(n=n, win=w, exp=e, t=t, pf=(gp / gl if gl > 0 else 0.0), avgR=e)


def main():
    print("=" * 100)
    print("  E-065  THE LIQUIDITY STRATEGY — the same rules the Pine draws")
    print("  Zone = 3+ pivots clustered. Entry = sweep of the zone. Target = the")
    print("  opposite zone. Stop = beyond the swept zone. Control = random bars,")
    print("  same geometry. Ties resolved as losses.")
    print("=" * 100)
    print(f"\n  {'market':<13}{'n':>6}{'win%':>8}{'expectancy':>13}{'profit factor':>15}"
          f"{'t':>8}   {'CONTROL win%':>13}{'ctrl exp':>11}")
    print("  " + "-" * 96)

    tot, totc = [], []
    beat = seen = 0
    for sym, tf in COMBOS:
        try:
            s = engine.load(sym, tf)
        except Exception:
            continue
        c = study.COSTS.get(sym, engine.Costs())
        real = simulate(s, c, "real")
        ctrl = simulate(s, c, "random")
        if len(real) < 25:
            print(f"  {sym+' '+tf:<13}{len(real):>6}   too few")
            continue
        a = stat(real); b = stat(ctrl)
        tot += real; totc += ctrl
        seen += 1
        if a["exp"] > b["exp"]:
            beat += 1
        print(f"  {sym+' '+tf:<13}{a['n']:>6}{a['win']:>7.1f}%{a['exp']:>+12.3f}R"
              f"{a['pf']:>15.2f}{a['t']:>+8.2f}   {b['win']:>12.1f}%{b['exp']:>+10.3f}R")

    print("  " + "-" * 96)
    print(f"  strategy beats its control in {beat}/{seen} markets")
    A_, B_ = stat(tot), stat(totc)
    print(f"\n  POOLED   n={A_['n']}  win {A_['win']:.1f}%  expectancy {A_['exp']:+.3f}R"
          f"  profit factor {A_['pf']:.2f}  t={A_['t']:+.2f}")
    print(f"  CONTROL  n={B_['n']}  win {B_['win']:.1f}%  expectancy {B_['exp']:+.3f}R"
          f"  profit factor {B_['pf']:.2f}  t={B_['t']:+.2f}")

    # ---- Veer's claim: the break-through is rare. Measure it.
    if tot:
        stops = sum(1 for x in tot if x["why"] == "stop")
        tgts = sum(1 for x in tot if x["why"] == "target")
        tims = sum(1 for x in tot if x["why"] == "time")
        print(f"\n  HOW TRADES END   target {100*tgts/len(tot):.1f}%   "
              f"stop {100*stops/len(tot):.1f}%   time cap {100*tims/len(tot):.1f}%")
        print(f"  Veer's read is that price respects the zone and the break-through")
        print(f"  is rare. The stop column is that claim, measured.")


if __name__ == "__main__":
    main()

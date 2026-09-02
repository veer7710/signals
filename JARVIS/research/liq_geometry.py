"""
E-068 — The 80% question.

Veer: "i personally have a 80% winrate w liquidity strat and losses dont even
compare to the profits". E-065 measured the same trigger at 31.6% win and a
68% stop rate. Both cannot be right about the same trade, so E-065 is not
measuring the trade he takes.

THE FIRST THING THIS FOUND, before any geometry was swept: E-065's trigger
fires 12 TIMES IN 4501 BARS on GOLD 15m. Its 117 pooled trades were ~15 per
market. Nothing measured on that sample — not the 31.6% win rate, not the 68%
stop rate, not the PF of 1.03 — describes a strategy Veer could have traded,
because he takes more trades than that in a morning.

The cause is a filter I built and he never specified. E-065 requires THREE
pivots inside a +/- ATR/6.9 band (about 0.145 ATR wide). He sent TWO LuxAlgo
scripts: "Liquidity Sweeps", which treats a SINGLE swing point as liquidity,
and "Buyside & Sellside Liquidity", which clusters. I ANDed them together and
kept the strictest reading of each. Frequency, GOLD 15m, per 1000 bars:

    min_piv=1  ATR/6.9 band   39.3 sweeps      <- Liquidity Sweeps' reading
    min_piv=2  ATR/6.9 band   14.4 sweeps
    min_piv=3  ATR/6.9 band    2.7 sweeps      <- E-065

So the zone definition is not a detail, it is the dominant variable, and it
belongs in the grid. It is swept here alongside:
  ENTRY   sweep close     — fill next open, as E-065
          confirm         — wait for the NEXT bar to close in our direction
          retest          — resting order back at the zone edge, 20 bars to fill
  ZONE    piv1 (any confirmed pivot) / piv2 / piv3 (E-065)
  STOP    0.5 / 1.0 / 1.5 / 2.5 ATR beyond the sweep bar's own extreme
  TARGET  0.25 / 0.5 / 0.75 / 1.0 / 1.5 / 2.5 ATR, or the opposite zone

Every cell prints win% AND expectancy AND profit factor, because a win rate on
its own is not a claim about money. Ties resolve as losses. Costs charged both
ends. A matched random control runs the same grid.

Run:  python3 JARVIS/research/liq_geometry.py
"""
from __future__ import annotations
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from engine import Series
from liquidity import pivots, stat

COMBOS = [("GOLD", "15m"), ("GOLD", "1h"), ("US500", "15m"), ("US500", "1h"),
          ("EURUSD", "15m"), ("EURUSD", "1h"), ("GBPUSD", "15m"), ("GBPUSD", "1h")]


def sweep_events(s: Series, pv_len=7, mar_div=6.9, min_piv=3, life=600,
                 wick_share=0.30, warmup=250):
    """Every sweep the E-065 rules fire, with the state a trade would need.
    Zones are built incrementally so nothing here sees the future."""
    A = engine.atr(s, 14)
    hi, lo = pivots(s, pv_len)
    zones, recentH, recentL = [], [], []
    out = []
    for i in range(warmup, len(s) - 2):
        a = A[i]
        if a is None or a <= 0:
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
                if any(z["dir"] == d and not z["broken"] and abs(z["px"] - c) <= mar
                       for z in zones):
                    for z in zones:
                        if z["dir"] == d and not z["broken"] and abs(z["px"] - c) <= mar:
                            z["n"] += 1; break
                else:
                    zones.append({"px": c, "top": c + mar, "bot": c - mar,
                                  "born": i, "dir": d, "n": len(grp), "broken": False})
        zones = [z for z in zones if i - z["born"] <= life]

        rngb = max(s.h[i] - s.l[i], 1e-9)
        upW = s.h[i] - max(s.o[i], s.c[i])
        dnW = min(s.o[i], s.c[i]) - s.l[i]
        for z in zones:
            if z["broken"]:
                continue
            if z["dir"] == 1:
                if s.c[i] > z["top"]:
                    z["broken"] = True; continue
                if s.h[i] > z["top"] and s.c[i] < z["top"] and (upW / rngb) >= wick_share:
                    side = -1
                else:
                    continue
            else:
                if s.c[i] < z["bot"]:
                    z["broken"] = True; continue
                if s.l[i] < z["bot"] and s.c[i] > z["bot"] and (dnW / rngb) >= wick_share:
                    side = 1
                else:
                    continue
            cands = [y["px"] for y in zones
                     if not y["broken"] and y is not z
                     and ((side == 1 and y["px"] > s.c[i]) or (side == -1 and y["px"] < s.c[i]))]
            opp = (min(cands) if side == 1 else max(cands)) if cands else None
            out.append({"i": i, "side": side, "atr": a,
                        "wick": s.l[i] if side == 1 else s.h[i],
                        "edge": z["bot"] if side == 1 else z["top"],
                        "opp": opp, "n": z["n"]})
            break
    return out


def random_events(s: Series, n_want, seed=11, warmup=250):
    """Matched control: same count, same ATR-relative geometry, random bars and
    random direction. The 'wick' is that bar's own extreme, exactly as a real
    sweep's is, so only the TRIGGER differs."""
    A = engine.atr(s, 14)
    rng = random.Random(seed)
    idx = [i for i in range(warmup, len(s) - 2) if A[i] and A[i] > 0]
    if not idx:
        return []
    out = []
    for _ in range(n_want):
        i = rng.choice(idx)
        side = 1 if rng.random() < 0.5 else -1
        a = A[i]
        out.append({"i": i, "side": side, "atr": a,
                    "wick": s.l[i] if side == 1 else s.h[i],
                    "edge": s.c[i], "opp": s.c[i] + side * 4.0 * a, "n": 3})
    out.sort(key=lambda e: e["i"])
    return out


def run(s: Series, costs, events, entry_mode, stop_atr, tgt_atr,
        max_bars=200, retest_wait=20, confirm_wait=3):
    """Replay one geometry. One position at a time; a sweep that arrives while
    a trade is live is skipped, which is what a human with one account does."""
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot
    trades = []
    busy_until = -1

    for ev in events:
        i, side, a = ev["i"], ev["side"], ev["atr"]
        if i <= busy_until:
            continue

        # ---------- entry
        if entry_mode == "close":
            j = i + 1
            if j >= len(s): continue
            entry = s.o[j] + side * (half + costs.slippage)
        elif entry_mode == "confirm":
            j = None
            for k in range(i + 1, min(i + 1 + confirm_wait, len(s))):
                if (side == 1 and s.c[k] > s.o[k]) or (side == -1 and s.c[k] < s.o[k]):
                    j = k + 1; break
                # a close beyond the sweep extreme kills the setup
                if (side == 1 and s.c[k] < ev["wick"]) or (side == -1 and s.c[k] > ev["wick"]):
                    break
            if j is None or j >= len(s): continue
            entry = s.o[j] + side * (half + costs.slippage)
        elif entry_mode == "retest":
            lvl = ev["edge"]
            j = None
            for k in range(i + 1, min(i + 1 + retest_wait, len(s))):
                if (side == 1 and s.l[k] <= lvl) or (side == -1 and s.h[k] >= lvl):
                    j = k; break
                if (side == 1 and s.c[k] < ev["wick"]) or (side == -1 and s.c[k] > ev["wick"]):
                    break
            if j is None: continue
            entry = lvl + side * (half + costs.slippage)
        else:
            raise ValueError(entry_mode)

        stop = ev["wick"] - side * stop_atr * a
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        if tgt_atr is None:
            if ev["opp"] is None: continue
            tgt = ev["opp"]
            if (tgt - entry) * side <= 0: continue
        else:
            tgt = entry + side * tgt_atr * a

        # ---------- resolve
        done = None
        for k in range(j, min(j + max_bars, len(s))):
            hit_s = (s.l[k] <= stop) if side == 1 else (s.h[k] >= stop)
            hit_t = (s.h[k] >= tgt) if side == 1 else (s.l[k] <= tgt)
            if hit_s:                              # ties lose
                done = (stop, "stop", k); break
            if hit_t:
                done = (tgt, "target", k); break
        if done is None:
            k = min(j + max_bars, len(s)) - 1
            done = (s.c[k], "time", k)
        px, why, k = done
        fill = px - side * (half + costs.slippage)
        r = ((fill - entry) * side - comm_px) / risk
        trades.append({"r": r, "why": why, "bars": k - j, "risk_atr": risk / a})
        busy_until = k
    return trades


STOPS = [0.5, 1.0, 1.5, 2.5]
TGTS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.5, None]
ZONES = [("piv1", 1), ("piv2", 2), ("piv3", 3)]


def tname(t):
    return "opp zone" if t is None else f"{t:.2f} ATR"


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    print("=" * 116)
    print("  E-068  WHERE DOES 80% LIVE?  The liquidity trigger, with the ZONE")
    print("  DEFINITION swept as well as the exit — because E-065 fixed it at the")
    print("  strictest possible reading and got 12 trades on GOLD 15m.")
    print("  win% is not a claim about money. Expectancy and profit factor decide.")
    print("  Ties lose. Costs charged both ends. Control = the same count of random")
    print("  bars with the same ATR geometry, so only the TRIGGER differs.")
    print("=" * 116)

    pooled, pooled_c = {}, {}
    for sym, tf in COMBOS:
        if only and only.upper() not in (sym + "_" + tf).upper():
            continue
        try:
            s = engine.load(sym, tf)
        except Exception:
            continue
        c = study.COSTS.get(sym, engine.Costs())
        for zname, mp in ZONES:
            ev = sweep_events(s, min_piv=mp)
            if len(ev) < 20:
                print(f"\n  ### {sym} {tf}  zone={zname}  only {len(ev)} sweeps — skipped")
                continue
            rv = random_events(s, len(ev))
            print(f"\n  ### {sym} {tf}  zone={zname}  {len(s)} bars  {len(ev)} sweeps"
                  f"  ({1000.0*len(ev)/len(s):.1f} per 1000 bars)")
            for em in ("close", "confirm", "retest"):
                print(f"\n   entry = {em}")
                print(f"   {'stop':>6} | " + " | ".join(f"{tname(t):>22}" for t in TGTS))
                for st_ in STOPS:
                    cells = []
                    for tg in TGTS:
                        key = (zname, em, st_, tg)
                        tr = run(s, c, ev, em, st_, tg)
                        pooled.setdefault(key, []).extend(tr)
                        pooled_c.setdefault(key, []).extend(run(s, c, rv, em, st_, tg))
                        a = stat(tr)
                        cells.append(f"{a['n']:>4} {a['win']:>5.1f}% {a['exp']:>+7.3f}R"
                                     if a["n"] else " " * 22)
                    print(f"   {st_:>5.1f}A | " + " | ".join(f"{x:>22}" for x in cells))

    print("\n" + "=" * 116)
    print("  POOLED ACROSS EVERY MARKET — sorted by EDGE OVER CONTROL, not by expectancy.")
    print("  A row that beats its own control by less than its control's own noise is a")
    print("  coincidence with a good haircut.")
    print("=" * 116)
    rows = []
    for key, tr in pooled.items():
        if len(tr) < 200:
            continue
        a = stat(tr); b = stat(pooled_c.get(key, []))
        rows.append((key, a, b))
    rows.sort(key=lambda r: -(r[1]["exp"] - r[2]["exp"]))
    print(f"\n  {'zone':<6}{'entry':<9}{'stop':>7}{'target':>11}{'n':>7}{'win%':>8}"
          f"{'expect':>10}{'PF':>7}{'t':>8}   {'ctrl n':>7}{'ctrl win%':>10}"
          f"{'ctrl exp':>10}{'edge':>9}")
    print("  " + "-" * 112)
    for (zn, em, st_, tg), a, b in rows[:25]:
        print(f"  {zn:<6}{em:<9}{st_:>6.1f}A{tname(tg):>11}{a['n']:>7}{a['win']:>7.1f}%"
              f"{a['exp']:>+9.3f}R{a['pf']:>7.2f}{a['t']:>+8.2f}   {b['n']:>7}"
              f"{b['win']:>9.1f}%{b['exp']:>+9.3f}R{a['exp']-b['exp']:>+8.3f}R")

    # ---- the actual question: which rows reach Veer's 80%, and do they pay?
    hi = [(k, a, b) for (k, a, b) in rows if a["win"] >= 75.0]
    print("\n  ROWS AT OR ABOVE A 75% WIN RATE — Veer's claim is 80%")
    print("  " + "-" * 112)
    if not hi:
        print("  none with n>=200.")
    else:
        hi.sort(key=lambda r: -r[1]["exp"])
        for (zn, em, st_, tg), a, b in hi:
            verdict = "PAYS" if a["exp"] > 0 and a["exp"] > b["exp"] else "LOSES"
            print(f"  {zn:<6}{em:<9}{st_:>6.1f}A{tname(tg):>11}{a['n']:>7}{a['win']:>7.1f}%"
                  f"{a['exp']:>+9.3f}R{a['pf']:>7.2f}{a['t']:>+8.2f}   {b['n']:>7}"
                  f"{b['win']:>9.1f}%{b['exp']:>+9.3f}R{a['exp']-b['exp']:>+8.3f}R   {verdict}")

    print("\n  READ THIS BEFORE BELIEVING ANY ROW ABOVE:")
    print("  * 3 zones x 3 entries x 4 stops x 7 targets = 252 cells per market. The best")
    print("    of 252 looks good on pure noise. The 'edge' column, not 'expect', is the")
    print("    only one with a defence against that, and even it is being maximised over.")
    print("  * A high win rate is trivially purchasable with a near target and a far stop.")
    print("    The question every row answers is whether it SURVIVES COSTS at that shape.")
    print("  * These are 15m and 1h bars. Veer trades M1/M5/M15. No M1 data is in the")
    print("    repo, so nothing here is a measurement of the timeframe he trades.")


if __name__ == "__main__":
    main()

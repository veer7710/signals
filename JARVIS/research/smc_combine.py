"""
E-080 — Putting it together, and refusing to fall for the same trap twice.

E-079 found two real things on GOLD 1h:
  * the structure BIAS filter lifts the top-tick entry from +0.378R to +0.563R
  * FVG and ORDER BLOCK work as triggers on their own (+0.943R on 44 trades,
    +0.498R on 70), both far clear of a random-entry control

E-074 is the reason this file exists. There, the highest-expectancy gate set
also made the LEAST money, because it only traded a quarter of the signals.
Expectancy per trade and money banked are different questions and the second
one is Veer's. So every row here reports POINTS, and the combinations are built
to ADD signals rather than remove them:

  base            E-077 top-tick alone
  base + bias     the filter. Fewer trades, better each. Does it bank more?
  base + FVG      the union - both entry types, one position at a time
  base + FVG + OB the full stack
  everything      plus iFVG, which is weak per trade but very frequent

A union is not free: two strategies sharing one account block each other, so
the union is simulated bar by bar with a single position, first signal wins.
That is the only honest way to add them and it is why this is not arithmetic.

Then the winner gets the full attack: OOS, walk-forward, 30-seed control,
Monte Carlo drawdown.

Run:  python3 JARVIS/research/smc_combine.py
"""
from __future__ import annotations
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from engine import Series
from liquidity import stat
from liq_validate import mc_drawdown
from toptick import zone_stream, entry_level
import smc
from smc import (smc_state, resolve, control, STOP_ATR, TGT_R, FRAC)


def all_signals(s: Series, costs, per_bar, A, st, use,
                warmup=250, arm_life=60, wait=20):
    """Every candidate entry from every enabled source, as (signal_bar, side,
    limit_level, source). Nothing is resolved yet - the union has to arbitrate
    first, because one account can hold one position.
    """
    half = costs.spread / 2.0
    cands = []

    if "toptick" in use:
        # A ZONE IS ONLY CONSUMED WHEN ITS ORDER IS ACTUALLY REACHED.
        # Marking it used the moment it first appears - which the first version
        # of this function did - burns the zone on a bar where price never came
        # near it, and the top-tick set collapsed from 491 trades to 26. The
        # order rests until it is touched or the zone dies; that is the whole
        # point of a resting order.
        used = set()
        for i in range(warmup, len(s) - 2):
            a = A[i]
            if a is None or a <= 0:
                continue
            for z in per_bar[i]:
                key = (z["born"], round(z["px"], 6), z["dir"])
                if key in used or i - z["born"] > arm_life:
                    continue
                lvl = entry_level(z, FRAC, a)
                side = -1 if z["dir"] == 1 else 1
                if (side == -1 and s.c[i] >= lvl) or (side == 1 and s.c[i] <= lvl):
                    continue
                k = i + 1
                if k >= len(s):
                    continue
                if not ((s.h[k] >= lvl) if side == -1 else (s.l[k] <= lvl)):
                    continue          # not reached on the next bar: still resting
                used.add(key)
                cands.append((i, side, lvl, a, "toptick", 1))
                break

    for kind, tag in (("FVG", "fvg"), ("order block", "ob"), ("iFVG", "ifvg")):
        if tag not in use:
            continue
        for i in range(warmup, len(s) - 2):
            a = A[i]
            if a is None or a <= 0:
                continue
            side, lvl = 0, None
            if kind == "order block":
                for b in st["ob"][i]:
                    mid = (b["top"] + b["bot"]) / 2.0
                    if b["dir"] == 1 and s.c[i] > mid:  side, lvl = 1, mid; break
                    if b["dir"] == -1 and s.c[i] < mid: side, lvl = -1, mid; break
            elif kind == "FVG":
                for g in st["fvg"][i]:
                    if g["inverted"]:
                        continue
                    mid = (g["top"] + g["bot"]) / 2.0
                    if g["dir"] == 1 and s.c[i] > mid:  side, lvl = 1, mid; break
                    if g["dir"] == -1 and s.c[i] < mid: side, lvl = -1, mid; break
            else:
                for g in st["fvg"][i]:
                    if not g["inverted"] or i - g["inv_bar"] > 20:
                        continue
                    d = -g["dir"]
                    mid = (g["top"] + g["bot"]) / 2.0
                    if d == 1 and s.c[i] > mid:  side, lvl = 1, mid; break
                    if d == -1 and s.c[i] < mid: side, lvl = -1, mid; break
            if side == 0 or lvl is None:
                continue
            cands.append((i, side, lvl, a, tag, wait))
    cands.sort(key=lambda x: x[0])
    return cands


def simulate(s, costs, cands, st, bias_filter=False, max_bars=200):
    """One account. Walk the candidates in time order; the first whose limit is
    touched while flat becomes the trade, and everything overlapping it is
    simply not taken - which is what actually happens."""
    half = costs.spread / 2.0
    out, busy = [], -1
    for (i, side, lvl, a, src, wait) in cands:
        if i <= busy:
            continue
        if bias_filter and st["bias"][i] != side:
            continue
        j = None
        for k in range(i + 1, min(i + 1 + wait, len(s))):
            if (side == 1 and s.l[k] <= lvl) or (side == -1 and s.h[k] >= lvl):
                j = k; break
        if j is None:
            continue
        entry = lvl + side * (half + costs.slippage)
        stop = entry - side * STOP_ATR * a
        if (entry - stop) * side <= 0:
            continue
        tgtpx = entry + side * TGT_R * (entry - stop) * side
        t = resolve(s, costs, j, side, entry, stop, tgtpx, max_bars)
        t["src"] = src
        out.append(t)
        busy = t["exit_bar"]
    return out


SETS = [
    ("base (E-077 top-tick)",      {"toptick"},                     False),
    ("base + structure bias",      {"toptick"},                     True),
    ("base + FVG",                 {"toptick", "fvg"},              False),
    ("base + FVG + order block",   {"toptick", "fvg", "ob"},        False),
    ("base + FVG + OB, bias-filtered", {"toptick", "fvg", "ob"},    True),
    ("everything incl iFVG",       {"toptick", "fvg", "ob", "ifvg"}, False),
    ("everything, bias-filtered",  {"toptick", "fvg", "ob", "ifvg"}, True),
]


def main():
    print("=" * 108)
    print("  E-080  THE SMC STACK, COMBINED — and judged on POINTS, not expectancy")
    print("  One account, one position, first signal wins. Same 0.60 ATR stop and")
    print("  2R target throughout, so only the SIGNAL SET changes. Ties lose.")
    print("=" * 108)

    store = {}
    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        A = engine.atr(s, 14)
        per_bar, _ = zone_stream(s)
        st = smc_state(s, A)
        print(f"\n  ### {sym} {tf}")
        print(f"   {'signal set':<34}{'n':>6}{'win%':>8}{'expect':>10}{'PF':>7}"
              f"{'t':>8}{'total R':>10}{'points':>10}")
        print("   " + "-" * 94)
        for name, use, bf in SETS:
            cands = all_signals(s, c, per_bar, A, st, use)
            tr = simulate(s, c, cands, st, bias_filter=bf)
            if len(tr) < 25:
                continue
            a_ = stat(tr)
            pts = sum(x["pts"] for x in tr)
            store[(sym, tf, name)] = tr
            print(f"   {name:<34}{a_['n']:>6}{a_['win']:>7.1f}%{a_['exp']:>+9.3f}R"
                  f"{a_['pf']:>7.2f}{a_['t']:>+8.2f}{a_['exp']*a_['n']:>+9.1f}R"
                  f"{pts:>+10.0f}")

        # what each source actually contributed in the fullest stack
        key = (sym, tf, "everything incl iFVG")
        if key in store:
            tr = store[key]
            print(f"\n   where those trades came from:")
            for src in ("toptick", "fvg", "ob", "ifvg"):
                sub = [x for x in tr if x["src"] == src]
                if not sub:
                    continue
                a_ = stat(sub)
                print(f"     {src:<10}{a_['n']:>6} trades{a_['win']:>7.1f}%"
                      f"{a_['exp']:>+9.3f}R{sum(x['pts'] for x in sub):>+9.0f} points")

    # ---------------- attack the best one
    print("\n" + "=" * 108)
    print("  THE BEST SET, ATTACKED")
    print("=" * 108)
    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        cand = [(k, v) for k, v in store.items() if k[0] == sym and k[1] == tf]
        if not cand:
            continue
        name, tr = max(cand, key=lambda kv: sum(x["pts"] for x in kv[1]))[0][2], \
                   max(cand, key=lambda kv: sum(x["pts"] for x in kv[1]))[1]
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        A = engine.atr(s, 14)
        a_ = stat(tr)
        rs = [x["r"] for x in tr]
        h = len(tr) // 2
        A1, B1 = stat(tr[:h]), stat(tr[h:])
        nb = 6
        bl = [tr[i * len(tr) // nb:(i + 1) * len(tr) // nb] for i in range(nb)]
        bs = [stat(b) for b in bl if len(b) >= 10]
        wf = sum(1 for x in bs if x["exp"] > 0)
        ce = [stat(control(s, c, A, len(tr), sd))["exp"] for sd in range(91, 121)]
        cm = sum(ce) / len(ce)
        csd = (sum((x - cm) ** 2 for x in ce) / len(ce)) ** 0.5
        se_o = abs(a_["exp"] / a_["t"]) if a_["t"] else 0.0
        se_c = csd / math.sqrt(len(ce))
        z = (a_["exp"] - cm) / math.sqrt(se_o ** 2 + se_c ** 2)
        dds = mc_drawdown(rs)
        v = study.verdict({"n": a_["n"], "expectancy_R": a_["exp"],
                           "t_stat": a_["t"]}, wf, len(bs), None)
        blk = "  ".join("%+.2f" % x["exp"] for x in bs)
        print(f"\n  ### {sym} {tf} — best by points: {name}")
        print(f"    n {a_['n']}  win {a_['win']:.1f}%  {a_['exp']:+.3f}R"
              f"  PF {a_['pf']:.2f}  t {a_['t']:+.2f}"
              f"  {sum(x['pts'] for x in tr):+.0f} points")
        print(f"    OOS      {A1['exp']:+.3f}R (n={A1['n']})  /  "
              f"{B1['exp']:+.3f}R (n={B1['n']})")
        print(f"    walk-fwd {wf}/{len(bs)}   [{blk}]")
        print(f"    control  {len(ce)} seeds {cm:+.3f}R  ->  {z:+.1f} sd")
        print(f"    drawdown median {dds[len(dds)//2]:.1f}R  95th {dds[int(len(dds)*0.95)]:.1f}R")
        print(f"    VERDICT  {v}")


if __name__ == "__main__":
    main()

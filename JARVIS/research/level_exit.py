"""
E-087 — Level-based TP and SL. Does the ping-pong between levels pay?

Veer: "for liquidity provide a real tp and sl based of levels like in the
screenshots i showed u you can see price reacting and also playing ping pong
with levels we need to catch it alllll".

That is a specific claim about structure: price does not travel an arbitrary
0.60 ATR and then 2R, it travels FROM one level TO the next and back. If true,
the target should be the next opposing level and the stop should sit just
beyond the level being traded from - not a multiple of ATR that knows nothing
about where the levels are.

E-068 did test "target = the opposite zone" and measured a 33% win rate. But
that was on the SWEEP-CLOSE entry, which E-076 later showed has no edge at all.
The question has never been asked of the entry that works - the limit resting
inside the zone. A far target behind a bad entry and a far target behind a good
one are different experiments.

WHAT IS COMPARED, all on the identical top-tick entries
  STOP     0.60 ATR (current)  ·  just beyond the level's far edge  ·  both,
           whichever is wider  ·  both, whichever is tighter
  TARGET   2R (current)  ·  the next opposing level  ·  the next opposing
           level capped at 4R  ·  halfway to it

Then the ping-pong itself: after a trade completes AT a level, does the return
journey pay? That is the "catch it alllll" question and it is separate.

Ties lose. Costs both ends. XAUUSD.

Run:  python3 JARVIS/research/level_exit.py
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from engine import Series
from liquidity import stat
from toptick import zone_stream, entry_level
from smc import smc_state, STOP_ATR, FRAC
from ea_parity import ea_best_level

GBP = 1.00 / 1.27


def all_levels(per_bar, st, i, gaps_ok=True):
    """Every price level the chart knows about at bar i, as plain numbers."""
    out = []
    for z in per_bar[i]:
        out.append(z["top"] if z["dir"] == 1 else z["bot"])
        out.append(z["px"])
    if gaps_ok:
        for g in st["fvg"][i]:
            if not g["inverted"]:
                out.append((g["top"] + g["bot"]) / 2.0)
        for b in st["ob"][i]:
            out.append((b["top"] + b["bot"]) / 2.0)
    return out


def next_level(levels, px, side, min_dist):
    """The nearest level in the trade's favour that is at least min_dist away."""
    best = None
    for L in levels:
        d = (L - px) * side
        if d < min_dist:
            continue
        if best is None or d < (best - px) * side:
            best = L
    return best


def run(s: Series, costs, per_bar, A, st, stop_mode, tgt_mode,
        warmup=250, arm_wait=60, max_bars=200):
    half = costs.spread / 2.0
    comm = costs.commission_per_lot / costs.value_per_point_per_lot
    out, busy, used = [], -1, set()
    arm = {1: None, -1: None}

    for i in range(warmup, len(s) - 2):
        a = A[i]
        if a is None or a <= 0:
            continue

        if i > busy:
            for dirn in (1, -1):
                if arm[dirn] is None:
                    continue
                lvl, src, aa, ab, edge = arm[dirn]
                hit = (s.l[i] <= lvl) if dirn > 0 else (s.h[i] >= lvl)
                if not hit:
                    continue
                entry = lvl + dirn * (half + costs.slippage)

                # ---- STOP
                atr_stop = entry - dirn * STOP_ATR * aa
                lvl_stop = edge - dirn * 0.15 * aa      # just beyond the level
                if stop_mode == "atr":      stop = atr_stop
                elif stop_mode == "level":  stop = lvl_stop
                elif stop_mode == "wider":  stop = min(atr_stop, lvl_stop) if dirn > 0 \
                                                   else max(atr_stop, lvl_stop)
                else:                       stop = max(atr_stop, lvl_stop) if dirn > 0 \
                                                   else min(atr_stop, lvl_stop)
                risk = (entry - stop) * dirn
                if risk <= 0.15 * aa:
                    arm[dirn] = None
                    continue

                # ---- TARGET
                if tgt_mode == "2R":
                    tgt = entry + dirn * 2.0 * risk
                else:
                    lv = all_levels(per_bar, st, i)
                    nxt = next_level(lv, entry, dirn, 0.5 * aa)
                    if nxt is None:
                        arm[dirn] = None
                        continue
                    if tgt_mode == "level":     tgt = nxt
                    elif tgt_mode == "level_cap":
                        cap = entry + dirn * 4.0 * risk
                        tgt = min(nxt, cap) if dirn > 0 else max(nxt, cap)
                    else:                        # halfway
                        tgt = entry + dirn * abs(nxt - entry) * 0.5
                    if (tgt - entry) * dirn <= 0.3 * aa:
                        arm[dirn] = None
                        continue

                done = None
                for k in range(i, min(i + max_bars, len(s))):
                    hs = (s.l[k] <= stop) if dirn > 0 else (s.h[k] >= stop)
                    ht = (s.h[k] >= tgt) if dirn > 0 else (s.l[k] <= tgt)
                    if hs: done = (stop, "stop", k); break     # ties lose
                    if ht: done = (tgt, "target", k); break
                if done is None:
                    k = min(i + max_bars, len(s)) - 1
                    done = (s.c[k], "time", k)
                px, why, k = done
                fill = px - dirn * (half + costs.slippage)
                out.append({"r": ((fill - entry) * dirn - comm) / risk,
                            "pts": (fill - entry) * dirn - comm, "why": why,
                            "risk_atr": risk / aa,
                            "tgt_atr": abs(tgt - entry) / aa,
                            "bars": k - i})
                busy = k
                used.add(round(lvl, 4))
                arm = {1: None, -1: None}
                break

        if i <= busy:
            arm = {1: None, -1: None}
            continue
        zb = [z for z in per_bar[i] if z["dir"] == 1 and i - z["born"] <= 60]
        zs = [z for z in per_bar[i] if z["dir"] == -1 and i - z["born"] <= 60]
        gaps = [g for g in st["fvg"][i] if not g["inverted"]]
        obs = st["ob"][i]
        for dirn in (1, -1):
            if arm[dirn] is not None and i - arm[dirn][3] <= arm_wait:
                continue
            lvl, src = ea_best_level(dirn, s.c[i], zs if dirn > 0 else zb,
                                     gaps, obs, a)
            if lvl is None or round(lvl, 4) in used:
                arm[dirn] = None
                continue
            # the level's own edge, for the level-based stop
            edge = lvl
            arm[dirn] = (lvl, src, a, i, edge)
    return out


STOPS = [("0.60 ATR (now)", "atr"), ("just past the level", "level"),
         ("whichever is wider", "wider"), ("whichever is tighter", "tighter")]
TGTS = [("2R (now)", "2R"), ("the next level", "level"),
        ("next level, capped 4R", "level_cap"), ("halfway to it", "half")]


def main():
    print("=" * 108)
    print("  E-087  LEVEL-BASED TP AND SL — does the ping-pong between levels pay?")
    print("  Identical top-tick entries in every cell. Only the stop and the target")
    print("  change. cell = n / win% / expectancy / points. Ties lose.")
    print("=" * 108)

    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        A = engine.atr(s, 14)
        per_bar, _ = zone_stream(s)
        st = smc_state(s, A)
        print(f"\n  ### {sym} {tf}")
        print(f"   {'stop':>22} |" + "".join(f"{t:>24}" for t, _ in TGTS))
        for sl, sm in STOPS:
            cells = []
            for tl, tm in TGTS:
                tr = run(s, c, per_bar, A, st, sm, tm)
                if len(tr) < 25:
                    cells.append(" " * 23); continue
                a_ = stat(tr)
                cells.append(f"{a_['n']:>4} {a_['win']:>4.0f}% {a_['exp']:>+6.2f}R "
                             f"{sum(x['pts'] for x in tr):>+6.0f}")
            print(f"   {sl:>22} |" + "".join(f"{x:>24}" for x in cells))

        # what the level target actually looks like when chosen
        tr = run(s, c, per_bar, A, st, "atr", "level")
        if tr:
            a_ = stat(tr)
            print(f"\n   with the LEVEL target: median distance "
                  f"{sorted(x['tgt_atr'] for x in tr)[len(tr)//2]:.2f} ATR, "
                  f"median hold {sorted(x['bars'] for x in tr)[len(tr)//2]} bars")
            for w in ("target", "stop", "time"):
                sub = [x for x in tr if x["why"] == w]
                if sub:
                    print(f"     {w:<8}{len(sub):>5} ({100.0*len(sub)/len(tr):.0f}%)"
                          f"  {stat(sub)['exp']:+.3f}R  {sum(x['pts'] for x in sub):+.0f} pts")


if __name__ == "__main__":
    main()

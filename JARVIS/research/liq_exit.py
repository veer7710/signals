"""
E-106 — THE LIQUIDITY EXIT. E-090 was applied to one EA and not the other.

Veer: "the signals don't use levels wisely they miss clear clear moves that
could've made us 40-200 pounds easily".

E-104/E-105 measured the first half and found it true: the shipped stack catches
16.3% of 40-point moves on GOLD 1h, leaving 84.7% of the available points in
legs never traded. But it also found the half that reframes the complaint - when
the stack DOES catch a 100-point move it banks about 14 points, because:

    shipped geometry: 0.60 ATR stop = 7.4 pts, 2R target = 14.8 pts
    at 0.01 lots (E-081, £0.787/pt):  a WIN IS £11.64. Maximum.

£40 needs 51 points captured. £200 needs 254. **The target caps him at £11.64
even at a 100% catch rate.** It is an exit problem wearing an entry problem's
clothes.

AND THE CAUSE IS AN UNAPPLIED FINDING OF OUR OWN. E-090: "A fixed 2R/3R target
was destroying the tail. Uncapped, the top 5% of trades carry 68% of gross
profit and the best is +28R." That was applied to SuperTrendSniper
(InpTargetR = 0) and NEVER to LiquiditySniper, which still ships InpTargetR = 2.0
and writes a hard broker TP at line 856. The research (smc.py TGT_R = 2.0)
measures the capped version too, so the whole liquidity result set is a 2R
target - a geometry E-090 already rejected on the other strategy.

This tests the exits head to head on the same entries, and reports WIN SIZE IN
POUNDS, because that is the thing he actually asked for.

Run:  python3 JARVIS/research/liq_exit.py
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from toptick import zone_stream
from smc import smc_state, STOP_ATR
from smc_combine import all_signals

GBP_PT = 0.787          # E-081: 0.01 lots, and it cannot be smaller
USE = {"toptick", "fvg", "ob"}


def resolve(s, costs, j, side, entry, stop, mode, a, tgt_r=2.0, trail=3.0,
            max_bars=200, arm=1.0):
    """One trade under one exit rule. Ties lose; costs charged both ends."""
    half = costs.spread / 2.0
    comm = costs.commission_per_lot / costs.value_per_point_per_lot
    risk = (entry - stop) * side
    tgt = entry + side * tgt_r * risk
    peak, mfe = entry, 0.0
    for k in range(j, min(j + max_bars, len(s))):
        hs = (s.l[k] <= stop) if side == 1 else (s.h[k] >= stop)
        if hs:
            px, why = stop, "stop"; break
        if mode == "fixed2R":
            ht = (s.h[k] >= tgt) if side == 1 else (s.l[k] <= tgt)
            if ht:
                px, why = tgt, "target"; break
        else:
            peak = max(peak, s.h[k]) if side > 0 else min(peak, s.l[k])
            mfe = max(mfe, side * (peak - entry) / risk)
            if mode in ("trail", "trail_gb"):
                t = peak - side * trail * a
                stop = max(stop, t) if side > 0 else min(stop, t)
            if mode == "trail_gb" and mfe >= arm:
                allow = 0.20 if mfe < 1.5 else (0.16 if mfe < 3.0 else 0.12)
                gb = entry + side * side * (peak - entry) * (1.0 - allow)
                stop = max(stop, gb) if side > 0 else min(stop, gb)
    else:
        k = min(j + max_bars, len(s)) - 1
        px, why = s.c[k], "time"
    fill = px - side * (half + costs.slippage)
    pts = (fill - entry) * side - comm
    return {"r": pts / risk, "pts": pts, "out": k, "why": why}


def run(s, costs, cands, mode, **kw):
    out, busy = [], -1
    for (i, side, lvl, a, src, wait) in cands:
        if i <= busy:
            continue
        j = None
        for k in range(i + 1, min(i + 1 + wait, len(s))):
            if (side == 1 and s.l[k] <= lvl) or (side == -1 and s.h[k] >= lvl):
                j = k; break
        if j is None:
            continue
        entry = lvl + side * (costs.spread / 2.0 + costs.slippage)
        stop = entry - side * STOP_ATR * a
        if (entry - stop) * side <= 0:
            continue
        t = resolve(s, costs, j, side, entry, stop, mode, a, **kw)
        out.append(t)
        busy = t["out"]
    return out


def main():
    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        c = study.COSTS[sym]
        A = engine.atr(s, 14)
        per_bar, _ = zone_stream(s)
        st = smc_state(s, A)
        cands = all_signals(s, c, per_bar, A, st, USE)
        print(f"\n{'='*104}\n  {sym} {tf} — same entries, four exits. "
              f"Win size in £ at 0.01 lots (E-081).\n{'='*104}")
        print(f"  {'exit':<30} {'n':>5} {'mean R':>8} {'points':>9} "
              f"{'avg win £':>10} {'best £':>8} {'wins>£40':>9} {'wins>£100':>10}")
        print("  " + "-" * 96)
        for name, mode, kw in (
            ("fixed 2R target (SHIPS)",   "fixed2R", {}),
            ("uncapped + 3 ATR trail",    "trail",   {}),
            ("uncapped + trail + give-back", "trail_gb", {}),
            ("uncapped + trail, arm 4R",  "trail_gb", {"arm": 4.0}),
        ):
            tr = run(s, c, cands, mode, **kw)
            if not tr:
                continue
            wins = [t["pts"] * GBP_PT for t in tr if t["pts"] > 0]
            m = sum(t["r"] for t in tr) / len(tr)
            print(f"  {name:<30} {len(tr):>5} {m:>+8.3f} "
                  f"{sum(t['pts'] for t in tr):>9.1f} "
                  f"{(sum(wins)/len(wins) if wins else 0):>10.2f} "
                  f"{(max(wins) if wins else 0):>8.2f} "
                  f"{sum(1 for w in wins if w >= 40):>9} "
                  f"{sum(1 for w in wins if w >= 100):>10}")


if __name__ == "__main__":
    main()

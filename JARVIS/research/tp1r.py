"""
E-172 — WHAT WIN RATE DO WE ACTUALLY GET AT A 1R TARGET?

Veer: "80% winrate at tp 1 btw rest is just luck icl as long as we hit
consistent profits that's all that matters means we can get payouts even if it
takes time."

That is a concrete, answerable question and it has never been asked with the
E-165-corrected entry fill. So: take the shipped sweep setup, put a fixed target
at N x risk, and report the win rate and the money side by side.

The arithmetic to hold in mind while reading it:
    at a 1.0R target you need 50% to break even before costs
    at 0.5R you need 67%
    at 0.25R you need 80%
Costs push all three up. A win rate is only worth having if the money follows.
"""
from __future__ import annotations
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, entry_fill, cost_scale
from liq_m1 import load, GBP
from sweep_winrate import pivots

TODAY = 7.38
GBP_PT = TODAY * GBP


def book(tf, tgtR, cap=1.2, buf=0.30, hold=240, cooldown=5):
    s, SP = load(tf)
    A = watr(s, 14)
    cs = cost_scale(SP, A)   # E-173: the M1 price, on every clock
    out, busy = [], -1
    for (kb, px, side) in pivots(s, 5):
        a = A[kb]
        if not a or a <= 0:
            continue
        t = -side
        need = px + side * 0.10 * a
        sw, ext = None, None
        for k in range(kb + 1, min(kb + 120, len(s))):
            if (s.h[k] >= need) if side > 0 else (s.l[k] <= need):
                sw, ext = k, (s.h[k] if side > 0 else s.l[k])
                break
        if sw is None:
            continue
        rng = s.h[sw] - s.l[sw]
        if (abs(s.c[sw] - s.o[sw]) / rng if rng > 0 else 1.0) > 0.646:
            continue
        j = None
        for k in range(sw + 1, min(sw + 120, len(s))):
            if (s.h[k] >= px) if t > 0 else (s.l[k] <= px):
                j = k
                break
            ext = max(ext, s.h[k]) if side > 0 else min(ext, s.l[k])
        if j is None:
            continue
        sl = ext - t * buf * a
        if not (0 < abs(px - sl) <= cap * a) or j <= busy:
            continue
        entry = entry_fill(px, s.o[j], t) + t * SP[j] * cs / 2.0
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        tgt = entry + t * tgtR * risk
        px_out, kk = None, None
        for k in range(j, min(j + hold, len(s))):
            # the stop is checked first: ties lose, which is the honest way round
            if (s.l[k] <= sl) if t > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k
                break
            # E-110: the entry bar may not book its own favourable extreme
            if k > j and ((s.h[k] >= tgt) if t > 0 else (s.l[k] <= tgt)):
                px_out, kk = tgt, k
                break
        if px_out is None:
            kk = min(j + hold, len(s) - 1)
            px_out = s.c[kk]
        out.append(t * ((px_out - t * SP[kk] * cs / 2.0) - entry))
        busy = kk + cooldown
    return out


def main():
    print("=" * 92)
    print("  E-172/E-173 — win rate at a fixed target, E-165 fills, E-173 cost")
    print("  break-even needs: 1.0R -> 50%   0.5R -> 67%   0.25R -> 80%   (before cost)")
    print("=" * 92)
    for tf in ("M1", "M5", "M15"):
        print(f"\n  ---- {tf} ----")
        print(f"  {'target':>8}{'n':>7}{'win%':>8}{'need':>7}{'points':>10}"
              f"{'per trade':>11}{'GBP @0.01':>11}")
        for tgtR in (0.25, 0.5, 1.0, 1.5, 2.0, 3.0):
            r = book(tf, tgtR)
            if len(r) < 30:
                continue
            w = 100.0 * sum(1 for x in r if x > 0) / len(r)
            need = 100.0 / (1.0 + tgtR)
            print(f"  {tgtR:>8.2f}{len(r):>7}{w:>7.1f}%{need:>6.0f}%"
                  f"{sum(r):>10.1f}{sum(r)/len(r):>+11.4f}"
                  f"{sum(r)*GBP_PT:>+11.0f}")


if __name__ == "__main__":
    main()

"""
E-134 — THE HIGH-WIN-RATE LIQUIDITY SWEEP, WHICH IS WHAT VEER ACTUALLY TRADES.

Him: "i literally run liquidity sweep strat myself and i have 80% winrate. i
wanted u using ict smc perfect and automate so i dont have to do analysis".

That is the most useful sentence in this project and nothing here has been
built to match it. Everything shipped is a LOW win rate, let-it-run design:
System A wins 57.1% and makes its money from a trail with no target. His is the
opposite shape - take the sweep, take a small target, be right most of the time.

The repo's answer to that shape is E-089, which concluded the edge "dies of
costs before it ever gets to M1's trade count". THAT CONCLUSION IS NOT
ADMISSIBLE HERE, for the same reason E-100's ping-pong rejection was not:

  - E-089 had NO M1 DATA. It took 1h and 15m bars and RAISED THE SIMULATED
    SPREAD until cost/stop matched what M1's was assumed to be. It never saw
    an M1 bar.
  - It used spread 0.46, eyeballed off his terminal. The tick data later
    measured 0.229 - it charged DOUBLE.
  - It predates the E-110 fill-convention fix.

There are now 157,051 real M1 bars from 18,816,940 bid/ask ticks with each
bar's own measured spread. The question gets asked again, properly.

THE SETUP, built the way the manual trade is actually described rather than the
way this repo's other level code happens to work:

  LEVEL   a confirmed swing pivot - the resting liquidity
  SWEEP   price trades THROUGH it by at least `sweep_atr` ATR. That is the
          stop-run: the wick that takes the orders out.
  ENTRY   a limit back AT the level. Not the sweep's close - E-130 measured
          that and it cost 97 of 97.1 points.
  STOP    beyond the SWEEP EXTREME plus a buffer. This is the classic ICT/SMC
          placement and it is the whole reason the win rate can be high: the
          stop sits where the setup is genuinely wrong, not at a fixed ATR.
  TARGET  a fixed multiple of that risk. Sweeping this is the point - the win
          rate and the money move in opposite directions and the question is
          whether ANY point on that curve pays.

E-110 IS ENFORCED: the bar that fills the limit may not also book the target.

WIN RATE IS NOT THE OBJECTIVE. E-074: the best per-trade gate set in this
project banked the LEAST money. An 80% win rate at 0.25R loses to a 40% win
rate at 3R. Both are printed for every cell so the trade-off is visible instead
of argued about.
"""
from __future__ import annotations
import os, sys, statistics, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr
from liq_m1 import load, GBP

TODAY = 7.38


def pivots(s, k):
    """Confirmed swing pivots: (bar_it_becomes_known, price, side).
    side +1 = a swing HIGH (sell-side liquidity above), -1 = a swing LOW."""
    out = []
    for i in range(k, len(s) - k):
        if s.h[i] == max(s.h[i - k:i + k + 1]):
            out.append((i + k, s.h[i], 1))
        if s.l[i] == min(s.l[i - k:i + k + 1]):
            out.append((i + k, s.l[i], -1))
    return out


def run(s, SP, A, cs, piv, sweep_atr, buf_atr, tgt_r, life=120, hold=240,
        cooldown=5):
    """Each pivot is watched for a sweep. On a sweep, a limit goes back at the
    level; the stop sits beyond the sweep extreme.

    Returns a list of (points, R, won)."""
    out, busy = [], -1
    for (kb, px, side) in piv:
        if kb <= busy:
            continue
        a = A[kb]
        if not a or a <= 0:
            continue
        # a swing HIGH is sell-side liquidity: the sweep goes UP through it and
        # the trade is SHORT back through the level.
        tside = -side
        need = px + side * sweep_atr * a
        sw, ext = None, None
        for k in range(kb + 1, min(kb + life, len(s))):
            hit = (s.h[k] >= need) if side > 0 else (s.l[k] <= need)
            if hit:
                sw = k
                ext = s.h[k] if side > 0 else s.l[k]
                break
        if sw is None:
            continue

        # THE RETURN TO THE LEVEL, and the direction of this test matters more
        # than anything else in the file. After a sweep the price is BEYOND the
        # level - below it on a swept low, above it on a swept high. The trade
        # is taken when price comes BACK to the level, so a long fills on a bar
        # whose HIGH reaches back up to it, not one whose low is under it. The
        # first version of this had both conditions inverted, which filled every
        # trade on the sweep bar itself at a price the market had already left,
        # and produced a uniformly negative table with a 45% win rate at a 0.25R
        # target. A 0.25R target cannot win 45% of the time against a 1R stop.
        # That impossibility is what exposed it.
        entry_lvl = px
        j = None
        for k in range(sw + 1, min(sw + life, len(s))):
            back = (s.h[k] >= entry_lvl) if tside > 0 else (s.l[k] <= entry_lvl)
            if back:
                j = k
                break
            # until we are filled the sweep can keep extending, and the stop
            # goes with it
            ext = max(ext, s.h[k]) if side > 0 else min(ext, s.l[k])
        if j is None:
            continue

        sp = SP[j] * cs
        entry = entry_lvl + tside * sp / 2.0
        sl = ext - tside * buf_atr * a
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        tp = entry + tside * tgt_r * risk

        # E-110: the bar that filled us may not also book the target. The stop
        # IS checked on the entry bar, because a sweep that runs on through us
        # is a real loss and pretending otherwise is the flattering direction.
        px_out, kk = None, None
        for k in range(j, min(j + hold, len(s))):
            hit_sl = (s.l[k] <= sl) if tside > 0 else (s.h[k] >= sl)
            if hit_sl:
                px_out, kk = sl, k
                break
            if k == j:
                continue
            hit_tp = (s.h[k] >= tp) if tside > 0 else (s.l[k] <= tp)
            if hit_tp:
                px_out, kk = tp, k
                break
        if px_out is None:
            kk = min(j + hold, len(s) - 1)
            px_out = s.c[kk]
        pts = tside * ((px_out - tside * SP[kk] * cs / 2.0) - entry)
        out.append((pts, pts / risk, pts > 0))
        busy = kk + cooldown
    return out


def main():
    print("=" * 104)
    print("  E-134 — the HIGH-WIN-RATE liquidity sweep, on real M1 ticks")
    print("  (E-089 rejected this shape using 1h/15m bars with M1's cost")
    print("   SIMULATED, at a spread of 0.46 when the real one is 0.229)")
    print("=" * 104)

    for tf, pk in (("M1", 5), ("M1", 10), ("M5", 5), ("M15", 3)):
        s, SP = load(tf)
        A = watr(s, 14)
        va = sorted(x for x in A[100:] if x)
        med_a = va[len(va) // 2]
        cs = 0.11 / (statistics.median(SP) / med_a)
        bpd = {"M1": 1440, "M5": 288, "M15": 96}[tf]
        days = len(s) / bpd
        piv = pivots(s, pk)

        print(f"\n  ---------- {tf}, pivot {pk}   ({len(piv)} pivots, "
              f"{days:.0f} days) ----------")
        print(f"  {'target':>7} {'sweep':>6} {'buf':>5} {'n':>6} {'/day':>6} "
              f"{'WIN%':>7} {'points':>9} {'per trade':>10} {'£ 0.01':>9}")
        print("  " + "-" * 76)

        for sweep_atr in (0.10, 0.25):
            for buf in (0.10, 0.30):
                for tgt in (0.25, 0.5, 1.0, 1.5, 2.0, 3.0):
                    r = run(s, SP, A, cs, piv, sweep_atr, buf, tgt)
                    if len(r) < 40:
                        continue
                    p = sum(x[0] for x in r)
                    w = 100.0 * sum(1 for x in r if x[2]) / len(r)
                    print(f"  {tgt:>6.2f}R {sweep_atr:>6.2f} {buf:>5.2f} "
                          f"{len(r):>6} {len(r)/days:>6.1f} {w:>6.1f}% "
                          f"{p:>9.1f} {p/len(r):>10.4f} {p*TODAY*GBP:>9.2f}")


if __name__ == "__main__":
    main()

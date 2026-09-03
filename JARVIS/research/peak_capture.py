"""
E-095 — PEAK CAPTURE ON SMALL MOVES.

Veer: he wants the peak of EVERY trade taken - big, small and chop - and the
current engines only protect a trade once it reaches 1R (E-086 puts the profit
stop at the broker from 1.0R of peak).

Before building anything, measure the PRIZE. For every trade: how far did it go
in our favour (MFE), and how much of that did we keep? If the money left on the
table by sub-1R trades is small, the honest answer is "there is nothing here"
and no rule should be shipped at all.

Two findings already constrain this and must not be re-broken:
  E-090  uncapped targets. The top 5% of trades carry 68% of gross profit.
         ANY rule that clips a winner early has to pay for that out of the tail.
  E-075  the give-back rule was never the problem - ARMING IT AT 0.6R was.
         Arming protection early is already known to lose money here.

So the only rule worth testing is one that acts on trades which DO NOT go on to
exceed 1R, and leaves every other trade untouched. That cannot be known at the
time, so any real rule is a bet, and the bet has to be priced.

Run:  python3 JARVIS/research/peak_capture.py
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
from engine import atr as watr
from pine_ea_parity import ea_supertrend_at, ea_dema_at

ATRL, MULT, DEMAL, WARM, SPREAD = 7, 1.2, 200, 400, 0.46
STOP_ATR, TRAIL, MAXBARS = 2.0, 3.0, 50


def paths(s):
    """Every EA trade, with its full bar-by-bar favourable/adverse path."""
    A = watr(s, ATRL)
    n = len(s)
    start = max(WARM + 10, DEMAL * 4 + 20)
    out, busy = [], -1
    for i in range(start, n - 1):
        if i <= busy:
            continue
        d, dp = ea_supertrend_at(s, i, ATRL, MULT, WARM)
        up, dn = d == -1 and dp == 1, d == 1 and dp == -1
        if not (up or dn):
            continue
        side = 1 if up else -1
        en, ep = ea_dema_at(s, i, DEMAL, 1), ea_dema_at(s, i, DEMAL, 3)
        if en is None or ep is None:
            continue
        if (side > 0 and en < ep) or (side < 0 and en > ep):
            continue
        a = A[i]
        if not a or a <= 0:
            continue
        entry = s.o[i + 1] + side * SPREAD / 2.0
        risk = STOP_ATR * a
        stop = entry - side * risk
        peak, i_out, px, mfe_r = entry, None, None, 0.0
        bars = []            # (bar, R at the bar's best, R at the bar's worst)
        for j in range(i + 1, min(i + 1 + MAXBARS, n)):
            best = s.h[j] if side > 0 else s.l[j]
            worst = s.l[j] if side > 0 else s.h[j]
            bars.append((j, side * (best - entry) / risk,
                         side * (worst - entry) / risk))
            if (side > 0 and s.l[j] <= stop) or (side < 0 and s.h[j] >= stop):
                i_out, px = j, stop - side * SPREAD / 2.0
                break
            peak = max(peak, s.h[j]) if side > 0 else min(peak, s.l[j])
            mfe_r = max(mfe_r, side * (peak - entry) / risk)
            # ---- the trail (InpUseTrail, 3.0 ATR, armed immediately)
            t = peak - side * TRAIL * a
            stop = max(stop, t) if side > 0 else min(stop, t)
            # ---- THE GIVE-BACK PROFIT STOP. E-086 puts it at the BROKER once
            # the peak passes InpProfitStopArmR = 1.0. Leaving it out was the
            # E-082 defect in miniature: with only the 3.0 ATR trail modelled,
            # a 2.0 ATR risk means the trail sits 1.5R below the peak and CANNOT
            # protect anything under 1.5R, so the 1-2R bucket looked like it gave
            # back 98% of its move. The EA does not do that. Tiers from
            # InpGbBase/Tier2/Tier3.
            if mfe_r >= 1.0:
                allow = 0.20
                if mfe_r >= 1.5:
                    allow = 0.16
                if mfe_r >= 3.0:
                    allow = 0.12
                keep = side * (peak - entry) * (1.0 - allow)
                gb = entry + side * keep
                stop = max(stop, gb) if side > 0 else min(stop, gb)
        if i_out is None:
            i_out = min(i + MAXBARS, n - 1)
            px = s.c[i_out] - side * SPREAD / 2.0
        got_r = side * (px - entry) / risk
        out.append({"i": i, "side": side, "entry": entry, "risk": risk,
                    "atr": a, "bars": bars, "mfe_r": mfe_r, "got_r": got_r,
                    "pts": side * (px - entry)})
        busy = i_out
    return out


def main():
    for sym, tf in (("GOLD", "15m"), ("GOLD", "1h")):
        s = engine.load(sym, tf)
        P = paths(s)
        tot = sum(p["pts"] for p in P)
        print(f"\n{'='*92}\n  {sym} {tf} — {len(P)} trades, {tot:+.1f} points\n{'='*92}")
        print(f"  {'MFE bucket':<16} {'n':>5} {'points':>10} {'mean MFE R':>11} "
              f"{'mean kept R':>12} {'kept %':>8} {'pts left':>10}")
        print("  " + "-" * 78)
        BUCKETS = [("never +0.25R", 0.0, 0.25), ("0.25 - 0.50R", 0.25, 0.50),
                   ("0.50 - 1.00R", 0.50, 1.00), ("1.00 - 2.00R", 1.00, 2.00),
                   ("2.00 - 4.00R", 2.00, 4.00), ("over 4R", 4.00, 1e9)]
        for name, lo, hi in BUCKETS:
            b = [p for p in P if lo <= p["mfe_r"] < hi]
            if not b:
                print(f"  {name:<16} {0:>5}")
                continue
            mf = sum(p["mfe_r"] for p in b) / len(b)
            gt = sum(p["got_r"] for p in b) / len(b)
            left = sum((p["mfe_r"] - p["got_r"]) * p["risk"] for p in b)
            print(f"  {name:<16} {len(b):>5} {sum(p['pts'] for p in b):>+10.1f} "
                  f"{mf:>11.3f} {gt:>12.3f} {100*gt/mf if mf else 0:>7.0f}% "
                  f"{left:>10.1f}")
        sub = [p for p in P if p["mfe_r"] < 1.0]
        big = [p for p in P if p["mfe_r"] >= 1.0]
        lsub = sum((p["mfe_r"] - p["got_r"]) * p["risk"] for p in sub)
        lbig = sum((p["mfe_r"] - p["got_r"]) * p["risk"] for p in big)
        print(f"\n  THE PRIZE. Points left on the table by trades that never reached 1R:")
        print(f"    below 1R : {len(sub):>4} trades, {lsub:>9.1f} points unclaimed")
        print(f"    at/above : {len(big):>4} trades, {lbig:>9.1f} points unclaimed")
        print(f"    those {len(sub)} sub-1R trades actually banked "
              f"{sum(p['pts'] for p in sub):+.1f} points in total.")


if __name__ == "__main__":
    main()

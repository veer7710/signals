"""
E-107 — THE STACK. Every surviving finding, combined and measured end to end.

Four things have survived their own attacks in this project and NONE of them has
ever been run with the others. They were reported as separate findings and left
sitting apart, which is why the shipped EA has none of them:

  E-106  uncapped exit + give-back stop, instead of the hard 2R broker TP.
         Confirmed on GOLD 1h, GOLD 15m and US500 1h; shorts score as well as
         or better than longs, so it is not the sample's drift.
  E-105  arm_life 60 -> 600. A zone stops being armable 60 bars after birth for
         no measured reason; 24.7% of all missed moves had a LIVE zone that had
         simply aged out.
  E-099  pullback re-entry inside a live trend. SUPPORTED on 1h (+130% points),
         UNPROVEN at 15m, so it is applied on 1h only.
  E-098  GOLD + US500, correlation +0.03, which halves drawdown for free.

This measures them one at a time in that order, so each row shows what that
finding is worth ON TOP of the ones above it - not in isolation, where
everything looks good.

Run:  python3 JARVIS/research/stacked.py
"""
from __future__ import annotations
import os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from toptick import zone_stream
from smc import smc_state, STOP_ATR
from smc_combine import all_signals
from liq_exit import resolve, USE, GBP_PT


def book(s, c, cands, mode="trail_gb", slots=1):
    """Walk candidates in time order under one exit rule."""
    out, busy = [], []
    for (i, side, lvl, a, src, wait) in cands:
        busy = [b for b in busy if b >= i]
        if len(busy) >= slots:
            continue
        j = None
        for k in range(i + 1, min(i + 1 + wait, len(s))):
            if (side == 1 and s.l[k] <= lvl) or (side == -1 and s.h[k] >= lvl):
                j = k; break
        if j is None:
            continue
        entry = lvl + side * (c.spread / 2.0 + c.slippage)
        stop = entry - side * STOP_ATR * a
        if (entry - stop) * side <= 0:
            continue
        t = resolve(s, c, j, side, entry, stop, mode, a)
        t["side"] = side
        t["ts"] = s.ts[t["out"]]
        out.append(t)
        busy.append(t["out"])
    return out


def curve(trades, w=1.0):
    ts = sorted(trades, key=lambda t: t["out"])
    eq = peak = dd = 0.0
    for t in ts:
        eq += t["r"] * w
        peak = max(peak, eq); dd = max(dd, peak - eq)
    return eq, dd


def stats(tr, w=1.0):
    if not tr:
        return 0, 0.0, 0.0, 0.0, 0.0, 0.0
    n = len(tr)
    m = sum(t["r"] for t in tr) / n
    eq, dd = curve(tr, w)
    pts = sum(t["pts"] for t in tr) * w
    wins = [t["pts"] * GBP_PT for t in tr if t["pts"] > 0]
    return n, m, pts, eq, dd, (sum(wins)/len(wins) if wins else 0.0)


def load(sym, tf, arm_life=60):
    s = engine.load(sym, tf)
    c = study.COSTS[sym]
    A = engine.atr(s, 14)
    per_bar, _ = zone_stream(s)
    st = smc_state(s, A)
    return s, c, all_signals(s, c, per_bar, A, st, USE, arm_life=arm_life)


def main():
    print("=" * 108)
    print("  E-107 — THE STACK. Each row ADDS one finding to the row above it.")
    print("  Money is per 0.01 lot (E-081, £0.787/point). Matched total risk.")
    print("=" * 108)
    rows = []

    # --- 1. what ships today
    s, c, cd = load("GOLD", "1h", 60)
    base = book(s, c, cd, "fixed2R")
    rows.append(("GOLD 1h, as it ships (2R target, arm_life 60)", base, 1.0))

    # --- 2. + the uncapped give-back exit
    gb = book(s, c, cd, "trail_gb")
    rows.append(("+ E-106 uncapped exit + give-back", gb, 1.0))

    # --- 3. + arm_life 600
    s2, c2, cd2 = load("GOLD", "1h", 600)
    gb2 = book(s2, c2, cd2, "trail_gb")
    rows.append(("+ E-105 arm_life 60 -> 600", gb2, 1.0))

    # --- 4. + US500 as a second, uncorrelated book
    s3, c3, cd3 = load("US500", "1h", 600)
    us = book(s3, c3, cd3, "trail_gb")
    both = [dict(t) for t in gb2] + [dict(t) for t in us]
    both.sort(key=lambda t: t["ts"])
    rows.append(("+ E-098 US500 as a second book", both, 0.5))

    print(f"  {'configuration':<46} {'n':>5} {'mean R':>8} {'points':>9} "
          f"{'total R':>8} {'maxDD':>7} {'R/DD':>6} {'avg win £':>10}")
    print("  " + "-" * 104)
    for name, tr, w in rows:
        n, m, pts, eq, dd, aw = stats(tr, w)
        print(f"  {name:<46} {n:>5} {m:>+8.3f} {pts:>9.1f} {eq:>+8.2f} "
              f"{dd:>7.2f} {(eq/dd if dd>0 else 0):>6.2f} {aw:>10.2f}")

    # --- what the final book looks like as an account
    tr = rows[-1][1]
    days = {}
    for t in tr:
        d = datetime.datetime.fromtimestamp(t["ts"], datetime.timezone.utc).date()
        days[d] = days.get(d, 0.0) + t["r"] * 0.5
    n, m, pts, eq, dd, aw = stats(tr, 0.5)
    print(f"\n  THE FINAL BOOK, as an account")
    print(f"    {len(tr)} trades over {len(days)} trading days "
          f"({len(tr)/len(days):.2f}/day)")
    print(f"    {eq:+.1f}R banked against a {dd:.2f}R worst drawdown "
          f"= {eq/dd if dd>0 else 0:.1f} : 1")
    print(f"    at 0.5% risk per trade that is "
          f"{100*((1+0.005*m)**len(tr)-1):.0f}% over the sample")
    wins = sorted((t["pts"]*GBP_PT for t in tr if t["pts"] > 0), reverse=True)
    print(f"    biggest wins per 0.01 lot: "
          f"{', '.join('£'+format(w,'.0f') for w in wins[:8])}")
    print(f"    wins over £40: {sum(1 for w in wins if w>=40)}   "
          f"over £100: {sum(1 for w in wins if w>=100)}")


if __name__ == "__main__":
    main()

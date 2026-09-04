"""
E-101 — THE HYBRID. Market on the flip, PLUS a level-limit re-entry in the run.

This is Veer's own design, tested as he described it rather than as a choice
between two options:

  "we catch trends from REAL birth ASAP"          -> market on the flip.
  "within a trend there's also multiple            -> a limit resting at a
   opportunities eg pullbacks"                        price-reacted level.
  "top tick entry... lower our risk of floating
   in drawdown and closing in loss"               -> the limit's better price.

WHY BOTH, MEASURED (E-100). A limit-only entry misses 60-80% of trends, because
most never come back to a level - 96 of 112 missed on GOLD 15m at the tightest
setting. That is why E-070 concluded "market beats every limit variant", and it
is right ON POINTS. But where the limit DID fill, mean adverse excursion was
0.702R against market's 0.808R - a 13% smaller drawdown per trade, which is
exactly the complaint. And on 15m the limit's per-trade expectancy BEAT market
(+0.195R vs +0.181R) while banking less than half the money (150.7 vs 431.3
points). That is E-074's trap in miniature: better per trade, less money.

So the answer is not to pick one. Take the market fill so no trend is missed,
and ADD a level-limit position when price returns - a second, better-priced
entry in a trend already proven to be running.

Sized so the pair carries the SAME total risk as one market entry, because two
positions in one direction at full size is 2x leverage, not a better strategy.

Run:  python3 JARVIS/research/hybrid_entry.py
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
from engine import atr as watr
from pine_ea_parity import ea_supertrend_at, ea_dema_at

ATRL, MULT, DEMAL, WARM, SPREAD = 7, 1.2, 200, 400, 0.46
STOP_ATR, TRAIL, MAXBARS = 2.0, 3.0, 50


def pivots(s, k=5):
    """Confirmed swings. k bars either side, so a pivot is only visible k bars
    AFTER it forms. No look-ahead."""
    hi, lo = [], []
    for i in range(k, len(s) - k):
        if s.h[i] == max(s.h[i - k:i + k + 1]): hi.append((i + k, s.h[i]))
        if s.l[i] == min(s.l[i - k:i + k + 1]): lo.append((i + k, s.l[i]))
    return hi, lo


def resolve(s, j, side, entry, a):
    n = len(s); risk = STOP_ATR * a; stop = entry - side * risk
    peak, mfe, mae = entry, 0.0, 0.0
    for k in range(j, min(j + MAXBARS, n)):
        mae = max(mae, side * (entry - (s.l[k] if side > 0 else s.h[k])) / risk)
        if (side > 0 and s.l[k] <= stop) or (side < 0 and s.h[k] >= stop):
            px = stop - side * SPREAD / 2.0
            return {"pts": side*(px-entry), "r": side*(px-entry)/risk, "out": k, "mae": mae}
        peak = max(peak, s.h[k]) if side > 0 else min(peak, s.l[k])
        mfe = max(mfe, side * (peak - entry) / risk)
        t = peak - side * TRAIL * a
        stop = max(stop, t) if side > 0 else min(stop, t)
        if mfe >= 1.0:
            allow = 0.20 if mfe < 1.5 else (0.16 if mfe < 3.0 else 0.12)
            gb = entry + side * side * (peak - entry) * (1.0 - allow)
            stop = max(stop, gb) if side > 0 else min(stop, gb)
    k = min(j + MAXBARS, n - 1); px = s.c[k] - side * SPREAD / 2.0
    return {"pts": side*(px-entry), "r": side*(px-entry)/risk, "out": k, "mae": mae}


def run(s, add_limit=True, wait=10, maxdist=1.5, split=True):
    A = watr(s, ATRL); n = len(s); start = max(WARM + 10, DEMAL * 4 + 20)
    hi, lo = pivots(s)
    tr, busy = [], -1
    for i in range(start, n - 1):
        if i <= busy: continue
        d, dp = ea_supertrend_at(s, i, ATRL, MULT, WARM)
        up, dn = d == -1 and dp == 1, d == 1 and dp == -1
        if not (up or dn): continue
        side = 1 if up else -1
        en, ep = ea_dema_at(s, i, DEMAL, 1), ea_dema_at(s, i, DEMAL, 3)
        if en is None or ep is None: continue
        if (side > 0 and en < ep) or (side < 0 and en > ep): continue
        a = A[i]
        if not a or a <= 0: continue

        w = 0.5 if (add_limit and split) else 1.0
        m = resolve(s, i + 1, side, s.o[i+1] + side*SPREAD/2.0, a)
        m["kind"] = "market"; m["w"] = w
        tr.append(m)
        last_out = m["out"]

        if add_limit:
            # the nearest reacted level on the entry side, visible at bar i
            L = [p for (b, p) in (lo if side > 0 else hi) if b <= i and b > i - 400]
            cand = [p for p in L
                    if (side > 0 and p < s.c[i] and s.c[i] - p <= maxdist * a)
                    or (side < 0 and p > s.c[i] and p - s.c[i] <= maxdist * a)]
            if cand:
                lvl = max(cand) if side > 0 else min(cand)
                for k in range(i + 1, min(i + 1 + wait, n)):
                    if (side > 0 and s.l[k] <= lvl) or (side < 0 and s.h[k] >= lvl):
                        t2 = resolve(s, k, side, lvl + side*SPREAD/2.0, a)
                        t2["kind"] = "limit"; t2["w"] = w
                        tr.append(t2)
                        last_out = max(last_out, t2["out"])
                        break
        busy = last_out
    return tr


def stat(tr, kind=None):
    b = [t for t in tr if kind is None or t["kind"] == kind]
    if not b: return None
    ts = sorted(b, key=lambda t: t["out"])
    eq = peak = dd = 0.0
    for t in ts:
        eq += t["r"] * t["w"]; peak = max(peak, eq); dd = max(dd, peak - eq)
    return (len(b), sum(t["r"] for t in b)/len(b), sum(t["pts"]*t["w"] for t in b),
            eq, dd, (eq/dd if dd > 0 else 0.0), sum(t["mae"] for t in b)/len(b))


def main():
    for sym, tf in (("GOLD", "15m"), ("GOLD", "1h")):
        s = engine.load(sym, tf)
        print(f"\n{'='*100}\n  {sym} {tf} — market only vs market + a level-limit "
              f"re-entry, MATCHED total risk\n{'='*100}")
        print(f"  {'configuration':<34} {'n':>6} {'mean R':>9} {'points':>10} "
              f"{'total R':>9} {'maxDD':>8} {'R/DD':>7} {'MAE':>7}")
        print("  " + "-" * 92)
        base = run(s, add_limit=False)
        n, m, p, eq, dd, rdd, mae = stat(base)
        print(f"  {'market only (ships today)':<34} {n:>6} {m:>+9.3f} {p:>10.1f} "
              f"{eq:>+9.2f} {dd:>8.2f} {rdd:>7.2f} {mae:>7.3f}")
        for wait in (5, 10, 20):
            tr = run(s, add_limit=True, wait=wait)
            n, m, p, eq, dd, rdd, mae = stat(tr)
            print(f"  {'+ level limit, '+str(wait)+'-bar wait':<34} {n:>6} "
                  f"{m:>+9.3f} {p:>10.1f} {eq:>+9.2f} {dd:>8.2f} {rdd:>7.2f} {mae:>7.3f}")
        tr = run(s, add_limit=True, wait=10)
        print(f"\n  {'leg':<12} {'n':>6} {'mean R':>9} {'points':>10} {'win%':>7} {'MAE':>7}")
        print("  " + "-" * 54)
        for k in ("market", "limit"):
            r = stat(tr, k)
            if not r: continue
            n, m, p, eq, dd, rdd, mae = r
            w = 100.0*sum(1 for t in tr if t["kind"]==k and t["pts"]>0)/n
            print(f"  {k:<12} {n:>6} {m:>+9.3f} {p:>10.1f} {w:>6.1f}% {mae:>7.3f}")


if __name__ == "__main__":
    main()

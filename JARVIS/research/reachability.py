"""
CAN THE TARGET PHYSICALLY BE REACHED? — a non-directional trade filter.

The chain of reasoning, each link measured rather than assumed:

  E-037  direction is unpredictable here. 40 variance-ratio tests, none
         significant. Every directional strategy in this repo failed, and that
         is why.
  E-038  VOLATILITY is predictable here. Absolute-return autocorrelation is far
         above two standard errors in 8 of 8 series while signed returns sit at
         zero, and on GOLD 1h one 20-bar range predicts the next with R^2 0.52.

So: WHERE price goes is unknowable, but HOW FAR it travels is substantially
knowable. That asymmetry has one obvious use.

  A trade with a 3R target needs price to travel 3 x the stop distance inside
  the holding window. If the range likely over that window is only 1.5 x the
  stop, the target CANNOT be hit - the trade will time out or stop out, and
  taking it is paying the spread for a lottery ticket with no prize behind it.

Skipping those is a trade-selection edge that requires NO directional
prediction. It cannot make a coin flip positive; it can stop you paying costs
on flips that could not have paid even if they landed right.

WHAT IS MEASURED
  Take the SuperTrend signals - deliberately, because they are known to be a
  coin flip, so any improvement is attributable to the filter and not to the
  entry. Predict the coming range from recent realised range, and compare
  expectancy on trades where the target was reachable against those where it
  was not. Chronological 70/30 split, OOS run once.

Run:  python3 JARVIS/research/reachability.py
"""
from __future__ import annotations
import os, sys, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, strategies as S
from engine import Series


def costs_for(sym): return study.COSTS.get(sym, engine.Costs())


def collect(s, sym, look=40, hold=50, stop_atr=1.5, rr=3.0):
    """Every SuperTrend+DEMA signal with (predicted travel / required travel)
    and the R it actually produced."""
    A = engine.atr(s, 14)
    D = S.dema(s.c, 200)
    d, _, _ = S.supertrend_dir(s, 7, 1.2)
    c = costs_for(sym)
    cost = c.spread + 2 * c.slippage
    out = []
    for i in range(max(300, look + 2), len(s) - 2):
        if d[i] == 0 or d[i - 1] == 0: continue
        up = d[i] == -1 and d[i - 1] == 1
        dn = d[i] == 1 and d[i - 1] == -1
        if not (up or dn): continue
        a = A[i]
        if a is None or a <= 0: continue
        if D[i] is None or D[i - 2] is None: continue
        if up and D[i] < D[i - 2]: continue
        if dn and D[i] > D[i - 2]: continue
        side = 1 if up else -1

        # PREDICTED travel: the realised range of the last `look` bars, scaled
        # to the holding window. Uses only closed bars - no future information.
        hi = max(s.h[i - look:i + 1]); lo = min(s.l[i - look:i + 1])
        recent = hi - lo
        predicted = recent * math.sqrt(hold / float(look))   # random-walk scaling

        risk = stop_atr * a
        required = rr * risk                  # what the target demands
        ratio = predicted / required if required > 0 else 0.0

        en = s.o[i + 1]
        stop = en - side * risk
        tgt = en + side * rr * risk
        r = 0.0
        for j in range(i + 1, min(i + 1 + hold, len(s))):
            hs_ = (s.l[j] <= stop) if side == 1 else (s.h[j] >= stop)
            ht_ = (s.h[j] >= tgt) if side == 1 else (s.l[j] <= tgt)
            if hs_: r = -1.0 - cost / risk; break
            if ht_: r = rr - cost / risk; break
        else:
            k = min(i + 1 + hold, len(s)) - 1
            r = ((s.c[k] - en) * side) / risk
        out.append((ratio, r))
    return out


def stats(rs):
    n = len(rs)
    if n == 0: return 0, 0.0, 0.0, 0.0
    m = sum(rs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in rs) / n) if n > 1 else 0.0
    t = m / (sd / math.sqrt(n)) if n > 1 and sd else 0.0
    w = 100.0 * sum(1 for x in rs if x > 0) / n
    return n, w, m, t


def split(s, frac=0.70):
    k = int(len(s) * frac)
    return (Series(s.ts[:k], s.o[:k], s.h[:k], s.l[:k], s.c[:k]),
            Series(s.ts[k:], s.o[k:], s.h[k:], s.l[k:], s.c[k:]))


def run(sym, tf, cut=1.0):
    s = engine.load(sym, tf)
    ins, oos = split(s)
    a, b = collect(ins, sym), collect(oos, sym)
    if len(a) < 40 or len(b) < 25:
        print(f"  {sym} {tf}: too few signals ({len(a)}/{len(b)})"); return None
    print(f"\n  {sym} {tf}")
    res = {}
    for label, rows in (("IN ", a), ("OOS", b)):
        reach = [r for ratio, r in rows if ratio >= cut]
        no    = [r for ratio, r in rows if ratio <  cut]
        n1, w1, m1, t1 = stats(reach)
        n0, w0, m0, t0 = stats(no)
        print(f"     {label}  reachable   n {n1:>4}  win {w1:>5.1f}%  exp {m1:>+7.3f}  t {t1:>+5.2f}")
        print(f"     {label}  unreachable n {n0:>4}  win {w0:>5.1f}%  exp {m0:>+7.3f}  t {t0:>+5.2f}")
        res[label] = (m1, m0, n1, n0)
    gap_oos = res["OOS"][0] - res["OOS"][1]
    print(f"     -> OOS gap {gap_oos:+.3f}R in favour of "
          f"{'REACHABLE' if gap_oos > 0 else 'unreachable'}")
    return gap_oos


if __name__ == "__main__":
    print(__doc__)
    gaps = []
    for sym in ("GOLD", "US500", "EURUSD", "GBPUSD"):
        for tf in ("15m", "1h"):
            try:
                g = run(sym, tf)
                if g is not None: gaps.append((f"{sym} {tf}", g))
            except FileNotFoundError:
                pass
    if gaps:
        pos = sum(1 for _, g in gaps if g > 0)
        print(f"\n{'='*70}\n  FILTER HELPED IN {pos} OF {len(gaps)} MARKETS\n{'='*70}")
        for nm, g in gaps:
            print(f"     {nm:<14}{g:+.3f}R")
        print("\n  4 of 8 is a coin flip. Only something near 7 or 8 of 8 is a")
        print("  filter worth putting in front of money.")

"""
LEVEL-TARGET REACHABILITY — where the confirmed finding meets a real target.

E-038 CONFIRMED that volatility is predictable here (8 of 8 series).
E-039 REJECTED using it to filter an ATR-scaled target, and the reason was
mechanical: the stop is `stop_atr x ATR`, the target is a multiple of the stop,
so required travel is proportional to ATR - and predicted travel, derived from
recent range, is proportional to ATR too. The ratio was constant by
construction and carried no information.

The fix that implies: use a target whose distance is NOT set by volatility.
A structural level is exactly that. The distance from price to the next swing
high is set by where that high happens to be - it can be 0.3 ATR away or 6 ATR
away, and it varies independently of current volatility. So the ratio

    predicted travel / distance to the level

actually varies, and can carry information.

THE QUESTION: when the coming range comfortably covers the distance to the next
level, is a trade toward that level worth more than when it does not?

This needs NO directional prediction beyond the entry already being taken. It is
a question about whether the target is physically achievable in the time
available.

CONTROL BUILT IN: the ratio's own variance is printed. If it is near-constant
like E-039's was, the test is uninformative and says so rather than pretending
a flat result is a negative one.

Run:  python3 JARVIS/research/level_reach.py
"""
from __future__ import annotations
import os, sys, math, statistics as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, strategies as S
from engine import Series


def costs_for(sym): return study.COSTS.get(sym, engine.Costs())


def swing_levels(s, n=5):
    """Confirmed swing highs/lows, published n bars late as they would be known."""
    hi, lo = [None] * len(s), [None] * len(s)
    for i in range(n, len(s) - n):
        if s.h[i] == max(s.h[i - n:i + n + 1]): hi[i + n] = s.h[i]
        if s.l[i] == min(s.l[i - n:i + n + 1]): lo[i + n] = s.l[i]
    return hi, lo


def collect(s, sym, look=40, hold=50, stop_atr=1.5, piv=5, keep=40):
    A = engine.atr(s, 14)
    D = S.dema(s.c, 200)
    d, _, _ = S.supertrend_dir(s, 7, 1.2)
    hiP, loP = swing_levels(s, piv)
    c = costs_for(sym); cost = c.spread + 2 * c.slippage

    live_hi, live_lo = [], []
    out = []
    for i in range(max(300, look + 2), len(s) - 2):
        if hiP[i] is not None: live_hi.append(hiP[i]); live_hi[:] = live_hi[-keep:]
        if loP[i] is not None: live_lo.append(loP[i]); live_lo[:] = live_lo[-keep:]
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

        # the STRUCTURAL target: nearest live level in the trade's direction
        px = s.c[i]
        cand = [p for p in (live_hi if side > 0 else live_lo)
                if (p > px if side > 0 else p < px)]
        if not cand: continue
        lvl = min(cand) if side > 0 else max(cand)
        dist = abs(lvl - px)
        if dist <= 0: continue

        hi = max(s.h[i - look:i + 1]); lo = min(s.l[i - look:i + 1])
        predicted = (hi - lo) * math.sqrt(hold / float(look))
        ratio = predicted / dist            # varies, unlike E-039

        # trade it TO the level, stop at ATR
        risk = stop_atr * a
        en = s.o[i + 1]
        stop = en - side * risk
        tgt = lvl - side * 0.1 * a          # park just inside the level
        if (tgt - en) * side <= 0: continue
        rr = abs(tgt - en) / risk
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
    if n == 0: return 0, 0.0, 0.0
    m = sum(rs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in rs) / n) if n > 1 else 0.0
    t = m / (sd / math.sqrt(n)) if n > 1 and sd else 0.0
    return n, m, t


def split(s, frac=0.70):
    k = int(len(s) * frac)
    return (Series(s.ts[:k], s.o[:k], s.h[:k], s.l[:k], s.c[:k]),
            Series(s.ts[k:], s.o[k:], s.h[k:], s.l[k:], s.c[k:]))


if __name__ == "__main__":
    print(__doc__)
    res = []
    for sym in ("GOLD", "US500", "EURUSD", "GBPUSD"):
        for tf in ("15m", "1h"):
            try: s = engine.load(sym, tf)
            except FileNotFoundError: continue
            _, oos = split(s)
            rows = collect(oos, sym)
            if len(rows) < 60:
                print(f"\n  {sym} {tf}: {len(rows)} signals, too few"); continue
            ratios = [x for x, _ in rows]
            cv = st.pstdev(ratios) / st.mean(ratios) if st.mean(ratios) else 0
            rows.sort(key=lambda x: x[0])
            q = len(rows) // 4
            b = [rows[0:q], rows[q:2*q], rows[2*q:3*q], rows[3*q:]]
            e = [stats([r for _, r in x])[1] for x in b]
            up = e[3] > e[0]
            res.append((f"{sym} {tf}", up, cv))
            print(f"\n  {sym} {tf}   {len(rows)} signals   ratio spread (CV) {cv:.2f}")
            print(f"     Q1 {e[0]:+.3f}   Q2 {e[1]:+.3f}   Q3 {e[2]:+.3f}   Q4 {e[3]:+.3f}"
                  f"   {'Q4>Q1' if up else 'no'}")
    if res:
        pos = sum(1 for _, u, _ in res if u)
        mcv = st.mean([c for _, _, c in res])
        print(f"\n{'='*70}\n  Q4 beat Q1 in {pos} of {len(res)}   "
              f"mean ratio CV {mcv:.2f}\n{'='*70}")
        if mcv < 0.25:
            print("  The ratio barely varies, so this repeats E-039's flaw and the")
            print("  result is UNINFORMATIVE rather than negative.")
        else:
            print("  The ratio does vary, so the test is informative. 4 of 8 is a")
            print("  coin flip; only near 7 or 8 of 8 is a usable filter.")

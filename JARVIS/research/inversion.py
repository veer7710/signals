"""
IS THE ENTRY ZERO-EDGE, OR NEGATIVE? — and does fading it work?

The live chart shows SuperTrend losing -0.58R per trade with zero take-profits
in twelve. Every backtest here says UNPROVEN. Nobody has asked the obvious
follow-up: is this entry WORTHLESS, or is it WRONG?

They are different and the difference is worth money:
  worthless -> expectancy is zero before costs, negative after. The inverse is
               also negative after costs. Nothing to do; abandon the entry.
  wrong     -> expectancy is negative BEFORE costs, meaning the signal carries
               real information pointed the wrong way. The inverse is then
               positive before costs and may survive them.

A systematic reason "wrong" is plausible: the entry fires on a displacement
candle, after the move. Buying the top of a thrust in a mean-reverting or
random series is a mechanically bad thing to do, and it would show up as a
consistent negative rather than a wash.

THE TEST
  Three arms on identical bars, identical exits, identical costs:
    LONG-AS-SIGNALLED   the strategy as built
    INVERTED            same signals, opposite direction
    RANDOM              same bar count, coin-flip direction - the zero baseline
  Plus a NO-COST run of each, because that is what separates "worthless" from
  "wrong". A signal that is negative before costs is carrying information.

Chronological 70/30, OOS run once. The random arm is seeded and repeated 20
times so its own noise is visible rather than assumed away.

Run:  python3 JARVIS/research/inversion.py
"""
from __future__ import annotations
import os, sys, math, random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, strategies as S
from engine import Series


def costs_for(sym): return study.COSTS.get(sym, engine.Costs())


def sig_bars(s):
    """(bar index, signalled side) for every SuperTrend+DEMA signal."""
    A = engine.atr(s, 14)
    D = S.dema(s.c, 200)
    d, _, _ = S.supertrend_dir(s, 7, 1.2)
    out = []
    for i in range(300, len(s) - 2):
        if d[i] == 0 or d[i - 1] == 0: continue
        up = d[i] == -1 and d[i - 1] == 1
        dn = d[i] == 1 and d[i - 1] == -1
        if not (up or dn): continue
        if A[i] is None or A[i] <= 0: continue
        if D[i] is None or D[i - 2] is None: continue
        if up and D[i] < D[i - 2]: continue
        if dn and D[i] > D[i - 2]: continue
        out.append((i, 1 if up else -1))
    return out, A


def play(s, bars, A, cost, flip=False, rnd=None, stop_atr=1.5, rr=3.0, hold=50):
    rs = []
    for i, side in bars:
        sd = side
        if flip: sd = -sd
        if rnd is not None: sd = 1 if rnd.random() < 0.5 else -1
        a = A[i]
        risk = stop_atr * a
        en = s.o[i + 1]
        stop = en - sd * risk
        tgt = en + sd * rr * risk
        r = 0.0
        for j in range(i + 1, min(i + 1 + hold, len(s))):
            hs_ = (s.l[j] <= stop) if sd == 1 else (s.h[j] >= stop)
            ht_ = (s.h[j] >= tgt) if sd == 1 else (s.l[j] <= tgt)
            if hs_: r = -1.0 - cost / risk; break
            if ht_: r = rr - cost / risk; break
        else:
            k = min(i + 1 + hold, len(s)) - 1
            r = ((s.c[k] - en) * sd) / risk
        rs.append(r)
    n = len(rs)
    if n == 0: return 0, 0.0, 0.0
    m = sum(rs) / n
    sd_ = math.sqrt(sum((x - m) ** 2 for x in rs) / n) if n > 1 else 0.0
    t = m / (sd_ / math.sqrt(n)) if n > 1 and sd_ else 0.0
    return n, m, t


def split(s, frac=0.70):
    k = int(len(s) * frac)
    return (Series(s.ts[:k], s.o[:k], s.h[:k], s.l[:k], s.c[:k]),
            Series(s.ts[k:], s.o[k:], s.h[k:], s.l[k:], s.c[k:]))


if __name__ == "__main__":
    print(__doc__)
    tally = {"as-signalled": 0, "inverted": 0}
    for sym in ("GOLD", "US500", "EURUSD", "GBPUSD"):
        for tf in ("15m", "1h"):
            try: s = engine.load(sym, tf)
            except FileNotFoundError: continue
            _, oos = split(s)
            bars, A = sig_bars(oos)
            if len(bars) < 40: continue
            c = costs_for(sym); cost = c.spread + 2 * c.slippage

            print(f"\n  {sym} {tf}   {len(bars)} OOS signals")
            print(f"     {'arm':<16}{'WITH cost':>22}{'NO cost':>22}")
            for label, kw in (("as-signalled", {}), ("inverted", {"flip": True})):
                n1, m1, t1 = play(oos, bars, A, cost, **kw)
                n0, m0, t0 = play(oos, bars, A, 0.0, **kw)
                print(f"     {label:<16}{m1:>+12.3f} (t{t1:>+5.2f}){m0:>+12.3f} (t{t0:>+5.2f})")
                if m1 > 0: tally[label] += 1
            ms = []
            for seed in range(20):
                _, m, _ = play(oos, bars, A, cost, rnd=random.Random(seed))
                ms.append(m)
            ms.sort()
            print(f"     {'random x20':<16}{sum(ms)/len(ms):>+12.3f} "
                  f"(5th {ms[1]:+.3f}, 95th {ms[-2]:+.3f})   <- the zero baseline")

    print(f"\n{'='*72}")
    print(f"  positive OOS with costs: as-signalled {tally['as-signalled']}, "
          f"inverted {tally['inverted']}")
    print("  If BOTH sit near the random band, the entry is WORTHLESS and there")
    print("  is nothing to invert. Only a no-cost expectancy clearly below the")
    print("  random band would mean the signal is WRONG rather than empty.")
    print("=" * 72)

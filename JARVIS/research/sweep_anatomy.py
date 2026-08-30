"""
sweep_anatomy.py — measure the ANATOMY of liquidity sweeps rather than
backtesting a rule. Answers: what fraction of sweeps reverse, what fraction
cascade, how nesting/trend/displacement/reclaim-speed change the odds, and
how big the cost is relative to bar range at each timeframe.

No strategy, no optimisation, no P&L. Pure conditional frequencies with a
SYMMETRIC barrier so a random walk scores 0.500 by construction. Any number
reported here is a measurement, not a claim of edge.

Run: python3 JARVIS/research/sweep_anatomy.py
"""
from __future__ import annotations
import os, sys, math, json, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine


def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0)
    p = k / n
    d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (c-h, c+h)


def pivots(s, k=3):
    """Confirmed swing highs/lows: extreme of a 2k+1 window, known at j+k."""
    lows, highs = [], []
    for j in range(k, len(s)-k):
        w_l = s.l[j-k:j+k+1]; w_h = s.h[j-k:j+k+1]
        if s.l[j] == min(w_l): lows.append(j)
        if s.h[j] == max(w_h): highs.append(j)
    return lows, highs


def atr(s, n=14):
    tr = [s.h[0]-s.l[0]]
    for i in range(1, len(s)):
        tr.append(max(s.h[i]-s.l[i], abs(s.h[i]-s.c[i-1]), abs(s.l[i]-s.c[i-1])))
    return engine._wilder(tr, n)


def barrier(s, i, ref, up, dn, horizon):
    """From CLOSE of bar i, which barrier is touched first over `horizon` bars?
    Returns 'up','dn','ambig' (same bar both) or None (neither)."""
    for j in range(i+1, min(i+1+horizon, len(s))):
        hi = s.h[j] >= ref+up
        lo = s.l[j] <= ref-dn
        if hi and lo: return 'ambig'
        if hi: return 'up'
        if lo: return 'dn'
    return None


def analyse(symbol, tf, k=3, lookback=60, horizon=24, mult=1.0):
    s = engine.load(symbol, tf)
    a = atr(s, 14)
    e50 = engine.ema(s.c, 50); e200 = engine.ema(s.c, 200)
    lows, highs = pivots(s, k)

    events = []   # dicts
    # ---- track each pivot low; find every bar that pierces it
    for (plist, side) in ((lows, 'low'), (highs, 'high')):
        for j in plist:
            lvl = s.l[j] if side == 'low' else s.h[j]
            first_valid = j + k + 1          # level only KNOWN k bars later
            nth = 0
            for i in range(first_valid, min(first_valid+lookback, len(s)-1)):
                pierced = (s.l[i] < lvl) if side=='low' else (s.h[i] > lvl)
                if not pierced: continue
                nth += 1
                if a[i] is None or a[i] <= 0 or e200[i] is None: continue
                A = a[i]
                closed_back = (s.c[i] > lvl) if side=='low' else (s.c[i] < lvl)
                pen = (lvl - s.l[i]) if side=='low' else (s.h[i] - lvl)
                rng = s.h[i]-s.l[i]
                # regime: trend if ema50 clearly away from ema200
                sep = (e50[i]-e200[i]) / A
                if side=='low':   # a sweep of a LOW; "with trend" = downtrend
                    with_trend = sep < -0.5
                    against_trend = sep > 0.5
                else:
                    with_trend = sep > 0.5
                    against_trend = sep < -0.5
                regime = 'trend_with' if with_trend else ('trend_against' if against_trend else 'range')
                # symmetric barrier from close of the sweep bar
                res = barrier(s, i, s.c[i], mult*A, mult*A, horizon)
                # 'reverse' = move AWAY from the pierce direction
                if res is None: outcome = None
                elif res == 'ambig': outcome = 'ambig'
                else:
                    rev = (res=='up') if side=='low' else (res=='dn')
                    outcome = 'reverse' if rev else 'continue'
                events.append(dict(i=i, side=side, nth=nth, closed_back=closed_back,
                                   pen_atr=pen/A, rng_atr=rng/A, regime=regime,
                                   outcome=outcome, hour=dt.datetime.utcfromtimestamp(s.ts[i]).hour,
                                   lvl=lvl))
                if nth >= 4: break
    return s, a, events


def rate(ev, label):
    d = [e for e in ev if e['outcome'] in ('reverse','continue')]
    amb = sum(1 for e in ev if e['outcome']=='ambig')
    n = len(d)
    if n < 25:
        return f"{label:38s} n={n:5d}  (too few)"
    r = sum(1 for e in d if e['outcome']=='reverse')
    lo, hi = wilson(r, n)
    return (f"{label:38s} n={n:5d}  P(reverse)={r/n:.3f}  "
            f"95%CI[{lo:.3f},{hi:.3f}]  ambig={amb}")


def main():
    for symbol, tf, horizon in (("GOLD","1h",24), ("GOLD","15m",24),
                                ("EURUSD","1h",24), ("US500","1h",24)):
        s, a, ev = analyse(symbol, tf, horizon=horizon)
        d0 = dt.datetime.utcfromtimestamp(s.ts[0]).date()
        d1 = dt.datetime.utcfromtimestamp(s.ts[-1]).date()
        print("="*78)
        print(f"{symbol} {tf}   {len(s)} bars  {d0} -> {d1}   {len(ev)} pierce events")
        print(f"  symmetric barrier = +/-1.0 x ATR14 from sweep-bar close, {horizon} bars")
        print("-"*78)
        print(rate(ev, "ALL pierces"))
        print(rate([e for e in ev if e['closed_back']], "closed back inside (naive sweep)"))
        print(rate([e for e in ev if not e['closed_back']], "closed beyond (no reclaim)"))
        print(rate([e for e in ev if e['nth']==1], "1st sweep of the level"))
        print(rate([e for e in ev if e['nth']==2], "2nd sweep (nested)"))
        print(rate([e for e in ev if e['nth']>=3], "3rd+ sweep (nested)"))
        for reg in ('trend_with','trend_against','range'):
            print(rate([e for e in ev if e['regime']==reg and e['closed_back']],
                       f"reclaim, {reg}"))
        print(rate([e for e in ev if e['closed_back'] and e['rng_atr']>1.5],
                   "reclaim + displacement bar >1.5 ATR"))
        print(rate([e for e in ev if e['closed_back'] and e['rng_atr']<=1.0],
                   "reclaim + small bar <=1.0 ATR"))
        print(rate([e for e in ev if e['closed_back'] and e['pen_atr']<0.15],
                   "reclaim + shallow pierce <0.15 ATR"))
        print(rate([e for e in ev if e['closed_back'] and e['pen_atr']>0.5],
                   "reclaim + deep pierce >0.5 ATR"))
        print(rate([e for e in ev if e['side']=='low' and e['closed_back']], "reclaim, LOW swept (long)"))
        print(rate([e for e in ev if e['side']=='high' and e['closed_back']], "reclaim, HIGH swept (short)"))
        if symbol=="GOLD" and tf=="1h":
            print("-"*78)
            print("  by UTC hour (reclaim events only):")
            for h in range(24):
                sub = [e for e in ev if e['closed_back'] and e['hour']==h]
                d = [e for e in sub if e['outcome'] in ('reverse','continue')]
                if len(d) >= 20:
                    r = sum(1 for e in d if e['outcome']=='reverse')
                    print(f"    {h:02d}:00 UTC  n={len(d):4d}  P(reverse)={r/len(d):.3f}")
    print("="*78)


if __name__ == "__main__":
    main()

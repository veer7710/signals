"""
"not buying or selling at peaks of trends"

Position-in-range said the opposite of his instinct: high in the range is the
BEST bucket. But "top of the 30-minute range" and "peak of the trend" are not
the same thing. The first means the trend is WORKING. The second means the move
is EXHAUSTED.

The variable that separates them is LEG MATURITY -- how far the current leg has
already travelled before you join it. That is what he is actually describing,
and it is measurable.
"""
import sys, numpy as np
sys.path.insert(0, "research")
import core, backtest as bt
from run_drift import detrend
from run_decisive import tstat, boot_ci

def leg_travel(d, swN=3):
    """ATR travelled since the last opposing swing = how mature this leg is."""
    a = core.atr(d, 14)
    ph, pl = core.pivots(d, swN, swN)
    out = np.full(d["n"], np.nan)
    lastLo = lastHi = np.nan
    for i in range(swN + 1, d["n"]):
        j = i - swN
        if j >= swN:
            if pl[j]: lastLo = d["l"][j]
            if ph[j]: lastHi = d["h"][j]
        if np.isnan(a[i]) or a[i] <= 0: continue
        e = core.ema(d["c"], 50)
        # measured against whichever swing the current direction started from
        if not np.isnan(lastLo) and d["c"][i] > lastLo:
            up = (d["c"][i] - lastLo) / a[i]
        else:
            up = np.nan
        if not np.isnan(lastHi) and d["c"][i] < lastHi:
            dn = (lastHi - d["c"][i]) / a[i]
        else:
            dn = np.nan
        out[i] = up if (np.isnan(dn) or (not np.isnan(up) and up < dn)) else dn
    return out

def trend_entries(d, ema_n=50, slope=3):
    e = core.ema(d["c"], ema_n)
    out = []
    for i in range(ema_n + slope + 2, d["n"] - 1):
        if np.isnan(e[i]) or np.isnan(e[i-slope]): continue
        if e[i] > e[i-slope]: out.append((i, 1))
        elif e[i] < e[i-slope]: out.append((i, -1))
    return out

for sym, tf in [("GOLD", "15m"), ("GOLD", "1h")]:
    d = detrend(core.load(sym, tf))
    lt = leg_travel(d)
    ents = trend_entries(d)
    print(f"\n{'='*94}")
    print(f"{sym} {tf} -- trend entries bucketed by HOW FAR THE LEG HAD ALREADY RUN")
    print(f"{'='*94}")
    print(f"  {'leg already travelled':<26}{'n':>5}{'win%':>7}{'$/trade':>10}{'t':>7}"
          f"{'PF':>7}{'CI95':>18}")
    for lo, hi, name in [(0.0,1.0,"under 1 ATR  (fresh)"), (1.0,2.0,"1-2 ATR"),
                         (2.0,3.5,"2-3.5 ATR"), (3.5,5.0,"3.5-5 ATR"),
                         (5.0,99.0,"over 5 ATR  (mature)")]:
        sel = [(i,sd) for i,sd in ents
               if not np.isnan(lt[i]) and lo <= lt[i] < hi]
        if len(sel) < 40:
            print(f"  {name:<26}{len(sel):>5}   too few"); continue
        thin = [sel[k] for k in range(0, len(sel), 4)]
        r = bt.run(d, thin, stop_fn=bt.stop_struct(0.25),
                   exit_cfg=dict(mode="trail_atr", trail=3.0), cost=0.15, max_bars=120)
        s = r.stats()
        if not s.get("n") or s["n"] < 25:
            print(f"  {name:<26}{s.get('n',0):>5}   too few"); continue
        pts=[x["pts"] for x in r.t]; l_,h_=boot_ci(pts)
        print(f"  {name:<26}{s['n']:>5}{100*s['win']:>7.1f}{s['pts']:>10.2f}"
              f"{tstat(pts):>7.2f}{s['pf']:>7.2f}  [{l_:>6.2f},{h_:>6.2f}]")

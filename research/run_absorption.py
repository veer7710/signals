"""
THE DECISIVE TEST from docs/SMC_SPEC.md.

A pool gets run. Three outcomes, resolved K bars later:
  ABSORPTION  pierced, failed to extend, closed back inside  -> tradeable?
  EXPANSION   decisive close beyond                          -> level dead
  UNRESOLVED  neither                                        -> a REAL third class,
              and everyone silently drops it, which is how the other two get
              flattered.

If ABSORPTION and EXPANSION do not separate beyond a best-of-N null, the whole
liquidity module is filters on a base rate that is not there, and it should not
be built. That is the stop rule and this script is the stop.
"""
import sys, numpy as np
sys.path.insert(0,"research")
import core, measure
from run_drift import detrend
from run_decisive import tstat, boot_ci

def classify(d, K=3, pierce=0.05, expand=0.35, left=3, right=3, max_live=3,
             tol_atr=0.10, buf=24):
    """One forward pass. Returns events: (bar, side, state, scalars)."""
    ph, pl = core.pivots(d, left, right)
    a = core.atr(d, 14); n = d["n"]
    highs, lows = [], []
    ev = []
    for i in range(n):
        if np.isnan(a[i]) or a[i] <= 0: continue
        tol = a[i]*tol_atr
        j = i - right
        if j >= left:
            if ph[j]:
                lv = d["h"][j]
                if highs and abs(highs[-1]["level"]-lv) <= tol:
                    highs[-1]["level"] = max(highs[-1]["level"], lv); highs[-1]["hits"] += 1
                else:
                    highs.append(dict(level=lv, hits=1, used=False))
                    if len(highs) > buf: highs.pop(0)
            if pl[j]:
                lv = d["l"][j]
                if lows and abs(lows[-1]["level"]-lv) <= tol:
                    lows[-1]["level"] = min(lows[-1]["level"], lv); lows[-1]["hits"] += 1
                else:
                    lows.append(dict(level=lv, hits=1, used=False))
                    if len(lows) > buf: lows.pop(0)
        if i + K >= n: continue
        c = d["c"][i]; pe = pierce*a[i]; exn = expand*a[i]
        # nearest-N eligibility (not deletion)
        dl = sorted(c-p["level"] for p in lows if not p["used"] and p["level"] < c)
        lo_cut = dl[min(max_live-1, len(dl)-1)] if dl else 0.0
        dh = sorted(p["level"]-c for p in highs if not p["used"] and p["level"] > c)
        hi_cut = dh[min(max_live-1, len(dh)-1)] if dh else 0.0
        for side, pool, cut in (("L", lows, lo_cut), ("H", highs, hi_cut)):
            if cut <= 0: continue
            for p in pool:
                if p["used"]: continue
                dd = (c-p["level"]) if side=="L" else (p["level"]-c)
                if dd <= 0 or dd > cut: continue
                pierced = (d["l"][i] <= p["level"]-pe) if side=="L" else (d["h"][i] >= p["level"]+pe)
                if not pierced: continue
                p["used"] = True
                # resolve over the NEXT K bars -- no look-ahead past i+K
                w = slice(i+1, i+1+K)
                if side=="L":
                    beyond = (d["c"][w] <= p["level"]-exn).any()
                    back   = d["c"][i+K] > p["level"]
                    depth  = (p["level"]-d["l"][i])/a[i]
                else:
                    beyond = (d["c"][w] >= p["level"]+exn).any()
                    back   = d["c"][i+K] < p["level"]
                    depth  = (d["h"][i]-p["level"])/a[i]
                state = "EXPANSION" if beyond else ("ABSORPTION" if back else "UNRESOLVED")
                ev.append(dict(bar=i+K, side=side, state=state, depth=depth,
                               hits=p["hits"]))
                break
    return ev

def score(d, events, state, side_to_dir, stop_atr=1.0, targ_atr=1.0, hold=40):
    a = core.atr(d,14); rows=[]
    for e in events:
        if e["state"] != state: continue
        j = e["bar"]+1
        if j >= d["n"]-hold-1 or np.isnan(a[e["bar"]]) or a[e["bar"]]<=0: continue
        dirn = side_to_dir(e["side"])
        r = measure.first_touch(d, j, dirn, stop_atr*a[e["bar"]], targ_atr*a[e["bar"]], hold)
        if r and r[0]!="timeout": rows.append(1 if r[0]=="win" else 0)
    return np.array(rows)

for sym,tf in [("GOLD","15m"),("GOLD","1h")]:
    d = detrend(core.load(sym,tf))
    ev = classify(d)
    n = len(ev)
    print(f"\n{'='*84}\n{sym} {tf} de-trended -- {n} pool-run events\n{'='*84}")
    for st in ("ABSORPTION","EXPANSION","UNRESOLVED"):
        k = sum(1 for e in ev if e["state"]==st)
        print(f"  {st:<12}{k:>5}  {100*k/max(n,1):>5.1f}%")
    base = measure.random_baseline(d, 200, 1.0, 1.0, 40, reps=120)
    bmean = base.mean()
    bon = measure.best_of_n_line(base, 6)
    print(f"\n  random baseline {100*bmean:.1f}%   best-of-6 null line {100*bon:.1f}%"
          f"  (lift {bon/bmean:.2f})")
    print(f"  {'arm':<34}{'n':>5}{'win%':>8}{'lift':>7}{'CI95':>18}")
    # ABSORPTION traded as REVERSAL (low swept -> long), EXPANSION as CONTINUATION
    arms = [
      ("ABSORPTION reversal",  "ABSORPTION", lambda s: 1 if s=="L" else -1),
      ("ABSORPTION continuation","ABSORPTION", lambda s: -1 if s=="L" else 1),
      ("EXPANSION continuation","EXPANSION",  lambda s: -1 if s=="L" else 1),
      ("EXPANSION reversal",   "EXPANSION",   lambda s: 1 if s=="L" else -1),
      ("UNRESOLVED reversal",  "UNRESOLVED",  lambda s: 1 if s=="L" else -1),
    ]
    res={}
    for name, st, f in arms:
        w = score(d, ev, st, f)
        if len(w) < 15: print(f"  {name:<34}{len(w):>5}   too few"); continue
        lo,hi = boot_ci(w)
        lift = w.mean()/bmean
        flag = "  CLEARS null" if lo/bmean > bon/bmean else ""
        print(f"  {name:<34}{len(w):>5}{100*w.mean():>8.1f}{lift:>7.2f}"
              f"  [{100*lo:>5.1f},{100*hi:>5.1f}]{flag}")
        res[name]=w
    if "ABSORPTION reversal" in res and "EXPANSION continuation" in res:
        A,B = res["ABSORPTION reversal"], res["EXPANSION continuation"]
        diff = A.mean()-B.mean()
        se = np.sqrt(A.var(ddof=1)/len(A) + B.var(ddof=1)/len(B))
        print(f"\n  SEPARATION absorption-reversal vs expansion-continuation:"
              f" {100*diff:+.1f} pts, t={diff/se if se>0 else 0:+.2f}")

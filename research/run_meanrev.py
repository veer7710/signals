import sys, numpy as np
sys.path.insert(0,"research")
import core, backtest as bt

def mr_signals(d, ema_n=50, k=1.5, need_reject=True):
    """FADE overextension. Event-counted: fires on the bar the stretch is
    first reached and then goes quiet until price comes back inside, so one
    stretch = one trade, not forty (E-073 rule)."""
    a = core.atr(d,14); e = core.ema(d["c"], ema_n); n=d["n"]; out=[]; armed=True
    for i in range(ema_n+15, n-1):
        if np.isnan(a[i]) or a[i]<=0 or np.isnan(e[i]): continue
        dev = (d["c"][i]-e[i])/a[i]
        if abs(dev) < k*0.5: armed = True
        if not armed or abs(dev) < k: continue
        sd = -1 if dev > 0 else 1
        if need_reject:
            # bar must close in the lower/upper third of its own range:
            # price already refusing the extreme
            rng = d["h"][i]-d["l"][i]
            if rng <= 0: continue
            pos = (d["c"][i]-d["l"][i])/rng
            if sd < 0 and pos > 0.40: continue
            if sd > 0 and pos < 0.60: continue
        out.append((i, sd)); armed = False
    return out

def split(d, frac=0.5):
    m = int(d["n"]*frac)
    a = {kk: (v[:m] if hasattr(v,"__len__") else v) for kk,v in d.items()}
    b = {kk: (v[m:] if hasattr(v,"__len__") else v) for kk,v in d.items()}
    a["n"]=m; b["n"]=d["n"]-m
    return a,b

def show(tag, r):
    s = r.stats()
    if not s.get("n"): print(f"  {tag:<34} no trades"); return None
    print(f"  {tag:<34}{s['n']:>5}{s['per_day']:>7.1f}{100*s['win']:>7.1f}"
          f"{s['pts']:>9.3f}{s['total']:>9.1f}{s['pf']:>7.2f}"
          f"{s['capture']:>8.2f}{s['maxdd_pts']:>8.1f}")
    return s

if __name__ == "__main__":
    HDR = f"  {'variant':<34}{'n':>5}{'/day':>7}{'win%':>7}{'$/trd':>9}{'tot$':>9}{'PF':>7}{'capt':>8}{'maxDD':>8}"

    for sym, tf, cost in [("GOLD","1h",0.15), ("GOLD","15m",0.15)]:
        d = core.load(sym, tf)
        ins, oos = split(d)
        print(f"\n{'='*96}\n{sym} {tf}  MEAN-REVERSION FADE  (cost ${cost}/side, "
              f"stop=struct+0.25ATR, one position at a time)\n{'='*96}")
        for label, dd in [("IN-SAMPLE (first half)", ins), ("OUT-OF-SAMPLE (2nd half)", oos)]:
            print(f"\n {label}: {dd['n']} bars")
            print(HDR)
            for k in (1.0, 1.5, 2.0):
                for rr in (1.0, 1.5, 2.0):
                    sig = mr_signals(dd, 50, k, True)
                    r = bt.run(dd, sig, stop_fn=bt.stop_struct(0.25),
                               exit_cfg=dict(mode="fixed", rr=rr), cost=cost,
                               max_bars=80)
                    show(f"stretch {k}ATR -> target {rr}R", r)
        # momentum control: same events, opposite direction
        print(f"\n CONTROL - same events traded the OTHER way (momentum):")
        print(HDR)
        for k in (1.5,):
            for rr in (1.0, 2.0):
                sig = [(i,-s) for i,s in mr_signals(d,50,k,True)]
                r = bt.run(d, sig, stop_fn=bt.stop_struct(0.25),
                           exit_cfg=dict(mode="fixed", rr=rr), cost=cost, max_bars=80)
                show(f"momentum {k}ATR -> {rr}R (full set)", r)

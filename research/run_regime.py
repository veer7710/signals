import sys, numpy as np, datetime as dt
sys.path.insert(0, "research")
import core

def variance_ratio(c, qs=(2,3,5,10,20,40)):
    """VR(q) = Var(q-bar return) / (q * Var(1-bar return)).
    VR > 1  -> moves persist (momentum family can work)
    VR < 1  -> moves revert (fade family can work)
    VR = 1  -> random walk; only cost-free strategies survive."""
    r = np.diff(np.log(c))
    v1 = r.var(ddof=1); out = {}
    for q in qs:
        m = len(r)//q*q
        rq = r[:m].reshape(-1, q).sum(1)
        vr = rq.var(ddof=1)/(q*v1)
        # Lo-MacKinlay heteroskedasticity-robust z
        n = len(r); z = (vr-1)*np.sqrt(n*q)/np.sqrt(2*(2*q-1)*(q-1)/(3*q))
        out[q] = (vr, z)
    return out

def autocorr(c, lags=(1,2,3,5,10)):
    r = np.diff(np.log(c)); n=len(r)
    return {k: (float(np.corrcoef(r[:-k], r[k:])[0,1]),
                float(np.corrcoef(r[:-k], r[k:])[0,1])*np.sqrt(n)) for k in lags}

def hour_profile(d):
    hrs = np.array([dt.datetime.utcfromtimestamp(int(t)).hour for t in d["t"]])
    rng = (d["h"]-d["l"])
    med = np.median(rng)
    rows=[]
    for hh in range(24):
        m = hrs==hh
        if m.sum()<20: continue
        rows.append((hh, m.sum(), np.median(rng[m])/med,
                     float(np.mean(np.sign(np.diff(d["c"],prepend=d["c"][0])[m])))))
    return rows

if __name__ == "__main__":
    for sym, tf in [("GOLD","15m"),("GOLD","1h"),("US500","15m"),("US500","1h")]:
        d = core.load(sym, tf)
        vr = variance_ratio(d["c"]); ac = autocorr(d["c"])
        print(f"\n=== {sym} {tf} ({d['n']} bars) ===")
        print("  variance ratio:", "  ".join(f"q={q}:{v:.3f}(z={z:+.1f})" for q,(v,z) in vr.items()))
        print("  autocorr      :", "  ".join(f"L{k}:{v:+.4f}(t={t:+.1f})" for k,(v,t) in ac.items()))

    d = core.load("GOLD","15m")
    print("\n=== GOLD 15m volatility by UTC hour (median range / overall median) ===")
    print("  hour   bars   volx   drift")
    for hh,n,vx,dr in hour_profile(d):
        bar = "#"*int(vx*20)
        print(f"  {hh:02d}:00 {n:>6} {vx:>6.2f}  {dr:+.3f}  {bar}")

"""Families NOT yet tested. De-trended, cost charged, matched null, best-of-N."""
import sys, numpy as np, datetime as dt
sys.path.insert(0,"research")
import core, backtest as bt
from run_drift import detrend
from run_decisive import tstat, boot_ci

def hrs(d): return np.array([dt.datetime.utcfromtimestamp(int(t)).hour for t in d["t"]])
def days(d): return np.array([int(t)//86400 for t in d["t"]])

# ---------- 1. ASIAN RANGE BREAK (the classic gold play, untested here)
def asia_break(d, a_start=23, a_end=7, trade_end=16, minR=0.5, maxR=4.0):
    h, dy, a = hrs(d), days(d), core.atr(d,14)
    out=[]; i=0; n=d["n"]
    cur=None; done=set()
    for i in range(50, n-1):
        inAsia = (h[i]>=a_start) or (h[i]<a_end)
        key = dy[i]+1 if h[i]>=a_start else dy[i]   # 23:00 belongs to the NEXT day's session
        if inAsia:
            if cur is None or cur[0]!=key: cur=[key, d["h"][i], d["l"][i]]
            else: cur[1]=max(cur[1],d["h"][i]); cur[2]=min(cur[2],d["l"][i])
            continue
        if cur is None or cur[0]!=dy[i] or dy[i] in done: continue
        if h[i]>=trade_end: continue
        if np.isnan(a[i]) or a[i]<=0: continue
        w=cur[1]-cur[2]
        if w < minR*a[i] or w > maxR*a[i]: continue
        if d["c"][i]>cur[1]: out.append((i, 1)); done.add(dy[i])
        elif d["c"][i]<cur[2]: out.append((i,-1)); done.add(dy[i])
    return out

# ---------- 2. MTF: HTF regime + LTF trigger (what Veer asks for)
def mtf_pullback(d, htf=4, ema_n=50, pull=0.6):
    """HTF trend from an aggregated series (no look-ahead: HTF bar k is only
    usable once all its sub-bars have closed), LTF pullback trigger."""
    a=core.atr(d,14); n=d["n"]
    H=core.resample(d,htf)
    he=core.ema(H["c"],ema_n)
    trend=np.zeros(n,dtype=np.int8)
    for k in range(ema_n+2, H["n"]):
        lo_=k*htf+htf-1                      # first LTF bar that may use it
        hi_=min((k+1)*htf+htf-1, n)
        if lo_>=n: break
        t = 1 if he[k]>he[k-2] else (-1 if he[k]<he[k-2] else 0)
        trend[lo_:hi_]=t
    e=core.ema(d["c"],ema_n); out=[]; armed=0
    for i in range(ema_n+20,n-1):
        if np.isnan(a[i]) or a[i]<=0 or trend[i]==0: continue
        dev=(d["c"][i]-e[i])/a[i]
        if trend[i]==1:
            if dev<0: armed=1
            elif armed==1 and d["c"][i]>d["h"][i-1]: out.append((i,1)); armed=0
        else:
            if dev>0: armed=-1
            elif armed==-1 and d["c"][i]<d["l"][i-1]: out.append((i,-1)); armed=0
    return out

# ---------- 3. SWEEP + HTF regime + volatility band (confluence stack)
def sweep_stack(d, htf=4, ema_n=50, atr_lo=0.4, atr_hi=0.95, agree=True):
    a=core.atr(d,14); n=d["n"]
    sig,wick=core.sweep_engine(d)
    H=core.resample(d,htf); he=core.ema(H["c"],ema_n)
    trend=np.zeros(n,dtype=np.int8)
    for k in range(ema_n+2,H["n"]):
        lo_=k*htf+htf-1; hi_=min((k+1)*htf+htf-1,n)
        if lo_>=n: break
        trend[lo_:hi_]= 1 if he[k]>he[k-2] else (-1 if he[k]<he[k-2] else 0)
    pct=np.full(n,np.nan)
    for i in range(200,n):
        w=a[i-200:i]; w=w[~np.isnan(w)]
        if len(w)>20: pct[i]=(w<a[i]).mean()
    out=[]
    for i in np.nonzero(sig)[0]:
        if np.isnan(pct[i]) or not (atr_lo<=pct[i]<=atr_hi): continue
        d_=-int(sig[i])                     # continuation reading
        if trend[i]==0: continue
        if agree and d_!=trend[i]: continue
        if not agree and d_==trend[i]: continue
        out.append((i,d_))
    return out

# ---------- 4. RANGE EXPANSION: quiet coil then break
def coil_break(d, look=20, quiet=0.6, minbars=6):
    a=core.atr(d,14); n=d["n"]; out=[]; armed=0
    rng=d["h"]-d["l"]
    for i in range(look+30,n-1):
        if np.isnan(a[i]) or a[i]<=0: continue
        hi=d["h"][i-look:i].max(); lo=d["l"][i-look:i].min()
        w=hi-lo
        if w < quiet*a[i]*np.sqrt(look):
            if d["c"][i]>hi: out.append((i,1))
            elif d["c"][i]<lo: out.append((i,-1))
    return out

FAMS={"asian range break":asia_break,
      "MTF htf-trend + ltf pullback":mtf_pullback,
      "sweep + htf + vol band (agree)":lambda dd: sweep_stack(dd,agree=True),
      "sweep + htf + vol band (fade)":lambda dd: sweep_stack(dd,agree=False),
      "coil -> expansion break":coil_break}

def matched_null(d,sigs,cfg,cost,reps=120,seed=11):
    rng=np.random.default_rng(seed); a=core.atr(d,14)
    ok=np.nonzero(~np.isnan(a)&(a>0))[0]; ok=ok[(ok>250)&(ok<d["n"]-160)]
    nL=sum(1 for _,s in sigs if s>0); nS=len(sigs)-nL
    res=[]
    for _ in range(reps):
        idx=rng.choice(ok,size=len(sigs),replace=True)
        dirs=np.array([1]*nL+[-1]*nS); rng.shuffle(dirs)
        r=bt.run(d,list(zip(idx.tolist(),dirs.tolist())),stop_fn=bt.stop_struct(0.25),
                 exit_cfg=cfg,cost=cost,max_bars=120,one_at_a_time=False)
        s=r.stats()
        if s.get("n"): res.append(s["pts"])
    return np.array(res)

EXIT=dict(mode="trail_atr",trail=3.0)          # the validated exit
print("="*112)
print("UNTESTED FAMILIES -- de-trended, cost $0.15/side, ATR-3 trail armed by the engine")
print("="*112)
for sym,tf in [("GOLD","1h"),("GOLD","15m")]:
    d=detrend(core.load(sym,tf))
    dys=(d["t"][-1]-d["t"][0])/86400*5/7
    print(f"\n--- {sym} {tf} ({d['n']} bars, {dys:.0f} trading days) ---")
    print(f"  {'family':<34}{'n':>5}{'/day':>7}{'win%':>7}{'$/trd':>8}{'t':>6}"
          f"{'null$':>8}{'edge':>8}{'CI95':>19}")
    for name,fn in FAMS.items():
        sig=fn(d)
        if len(sig)<25: 
            print(f"  {name:<34}{len(sig):>5}   too few"); continue
        r=bt.run(d,sig,stop_fn=bt.stop_struct(0.25),exit_cfg=EXIT,cost=0.15,max_bars=120)
        s=r.stats()
        if not s.get("n"): continue
        pts=[x["pts"] for x in r.t]; lo,hi=boot_ci(pts)
        nul=matched_null(d,sig,EXIT,0.15)
        print(f"  {name:<34}{s['n']:>5}{s['per_day']:>7.2f}{100*s['win']:>7.1f}"
              f"{s['pts']:>8.2f}{tstat(pts):>6.2f}{nul.mean():>8.2f}"
              f"{s['pts']-nul.mean():>8.2f}  [{lo:>6.2f},{hi:>6.2f}]")

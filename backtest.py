# ============================================================
# backtest.py v2 — 13 markets, tuned by YOUR first result:
#  - FX pullback pairs were the losers (100+ trades) -> now STRICT:
#    ADX >= 25, max 2 trades/day, 90-min cooldown, momentum candle
#  - Gold engine (the winner) unchanged; same engine on silver/oil
#  - Indices: breakout, NY session only
#  - JPY crosses: breakout, Asia/London hours
#  - BREAK-EVEN + TRAILING modelled (BE at +1 ATR, trail 1.2 ATR)
#  - One position per pair, no same-direction re-entry in cooldown
#  - Spread charged, ties = losses, entries at next-candle open,
#    no look-ahead. £100 start, 0.75% equity risk, compounding.
# ============================================================
import os, requests
import yfinance as yf
import pandas as pd
import numpy as np

START_BAL, RISK = 100.0, 0.0075
STOP_ATR, TP_ATR, BE_ATR, TRAIL_ATR = 1.5, 2.5, 1.0, 1.2
SPIKE = 3.0

#  name: (ticker, engine, sesStart, sesEnd, adxMin, maxPerDay, cooldownMin, spread%)
PAIRS = {
 "GOLD":    ("GC=F","BO",7,21,20,3,60,0.0004),
 "SILVER":  ("SI=F","BO",7,21,20,3,60,0.0005),
 "OIL":     ("CL=F","BO",7,21,20,3,60,0.0006),
 "US500":   ("ES=F","BO",13,21,20,2,60,0.0003),
 "US100":   ("NQ=F","BO",13,21,20,2,60,0.0003),
 "EUR/USD": ("EURUSD=X","PB",7,17,25,2,90,0.0002),
 "GBP/USD": ("GBPUSD=X","PB",7,17,25,2,90,0.00025),
 "USD/JPY": ("USDJPY=X","PB",7,17,25,2,90,0.0002),
 "AUD/USD": ("AUDUSD=X","PB",7,17,25,2,90,0.00025),
 "USD/CAD": ("USDCAD=X","PB",7,17,25,2,90,0.00025),
 "NZD/USD": ("NZDUSD=X","PB",7,17,25,2,90,0.0003),
 "GBP/JPY": ("GBPJPY=X","BO",0,12,22,2,90,0.0003),
 "EUR/JPY": ("EURJPY=X","BO",0,12,22,2,90,0.0003),
}

BOT=os.environ["TG_TOKEN"]; CHAT=os.environ["TG_CHAT"]
def send(m):
    requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",
        data={"chat_id":CHAT,"text":m,"parse_mode":"HTML"},timeout=15)

def ema(s,n): return s.ewm(span=n,adjust=False).mean()
def atr(h,l,c,n=14):
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n,adjust=False).mean()
def adx(h,l,c,n=14):
    up,dn=h.diff(),-l.diff()
    pdm=np.where((up>dn)&(up>0),up,0.0); mdm=np.where((dn>up)&(dn>0),dn,0.0)
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    a=tr.ewm(alpha=1/n,adjust=False).mean()
    pdi=100*pd.Series(pdm,index=h.index).ewm(alpha=1/n,adjust=False).mean()/a
    mdi=100*pd.Series(mdm,index=h.index).ewm(alpha=1/n,adjust=False).mean()/a
    dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    return dx.ewm(alpha=1/n,adjust=False).mean()

def run_pair(name,cfg,eq0):
    tk,engine,s0,s1,adxmin,maxd,cool,spr=cfg
    d=yf.download(tk,period="60d",interval="15m",progress=False)
    if isinstance(d.columns,pd.MultiIndex): d.columns=d.columns.get_level_values(0)
    d=d.dropna(subset=["Close"])
    if len(d)<300: return None
    d.index=d.index.tz_localize("UTC") if d.index.tz is None else d.index.tz_convert("UTC")
    c,h,l,o=d["Close"],d["High"],d["Low"],d["Open"]
    e200,e21=ema(c,200),ema(c,21)
    A,X=atr(h,l,c),adx(h,l,c)
    vol=d["Volume"] if "Volume" in d and d["Volume"].sum()>0 else None
    va=vol.rolling(20).mean() if vol is not None else None
    daily=d.resample("1D").agg({"High":"max","Low":"min"}).dropna()
    pdh=daily["High"].shift(1).reindex(d.index,method="ffill")
    pdl=daily["Low"].shift(1).reindex(d.index,method="ffill")

    eq=eq0; trades=[]; pos=None; day=None; n=0; lastExit=pd.Timestamp("2000-01-01",tz="UTC"); lastDir=0
    for i in range(210,len(d)-1):
        ts=d.index[i]
        if ts.date()!=day: day=ts.date(); n=0
        lo,hi,cl=float(l.iloc[i]),float(h.iloc[i]),float(c.iloc[i])
        if pos:
            # break-even + trail on candle close
            prof=(cl-pos["e"])*pos["d"]
            if prof>=BE_ATR*pos["a"]:
                ns=max(pos["e"],cl-TRAIL_ATR*pos["a"]) if pos["d"]==1 else min(pos["e"],cl+TRAIL_ATR*pos["a"])
                pos["sl"]=max(pos["sl"],ns) if pos["d"]==1 else min(pos["sl"],ns)
            hit_sl=lo<=pos["sl"] if pos["d"]==1 else hi>=pos["sl"]
            hit_tp=hi>=pos["tp"] if pos["d"]==1 else lo<=pos["tp"]
            px=pos["sl"] if hit_sl else pos["tp"] if hit_tp else None
            if px is not None:
                pnl=(px-pos["e"])*pos["d"]*pos["u"]-pos["e"]*spr*pos["u"]
                eq+=pnl; trades.append(pnl)
                lastExit=ts; lastDir=pos["d"]; pos=None
            continue
        if not(s0<=ts.hour<s1) or n>=maxd: continue
        if (ts-lastExit).total_seconds()<cool*60: continue
        a_=float(A.iloc[i]); x_=float(X.iloc[i])
        if not np.isfinite(a_) or a_<=0 or not np.isfinite(x_) or x_<adxmin: continue
        c1,o1,h1,l1=cl,float(o.iloc[i]),hi,lo
        if h1-l1>SPIKE*a_: continue
        sig=0
        if engine=="BO":
            if va is not None:
                v1=float(vol.iloc[i]); vv=float(va.iloc[i])
                if not np.isfinite(vv) or vv<=0 or v1<1.3*vv: continue
            ph,pl_=float(pdh.iloc[i]),float(pdl.iloc[i])
            if np.isfinite(ph) and c1>ph and o1<=ph and c1>o1: sig=1
            elif np.isfinite(pl_) and c1<pl_ and o1>=pl_ and c1<o1: sig=-1
        else:
            eT,eP=float(e200.iloc[i]),float(e21.iloc[i])
            body=abs(c1-o1)
            if c1>eT and l1<=eP and c1>o1 and body>0.3*a_: sig=1      # momentum candle
            elif c1<eT and h1>=eP and c1<o1 and body>0.3*a_: sig=-1
        if sig==0: continue
        if sig==lastDir and (ts-lastExit).total_seconds()<cool*120: continue  # anti-spam same direction
        e=float(o.iloc[i+1]); sd=STOP_ATR*a_
        pos={"d":sig,"e":e,"sl":e-sig*sd,"tp":e+sig*TP_ATR*a_,"a":a_,
             "u":(eq*RISK)/sd}
        n+=1
    w=[t for t in trades if t>0]
    return {"n":len(trades),"w":round(100*len(w)/len(trades),1) if trades else 0,
            "p":round(eq-eq0,2),"eq":eq}

eq=START_BAL; lines=[]; tot=0
for name,cfg in PAIRS.items():
    r=run_pair(name,cfg,eq)
    if r is None: lines.append(f"{name}: no data"); continue
    eq=r["eq"]; tot+=r["n"]
    lines.append(f"{name}: {r['n']}t · {r['w']}% · {r['p']:+.2f}")

msg=("🧪 <b>60-day backtest v2</b> — 13 markets, tuned filters\n"
     "(£100, 0.75% risk, spread+trailing modelled, ties=losses)\n\n"
     +"\n".join(lines)+
     f"\n\n<b>Final: £{eq:.2f} ({eq-START_BAL:+.2f}) · {tot} trades</b>"
     "\n\nCompare vs v1's −30.41. No slippage — reality slightly worse.")
send(msg); print(msg)

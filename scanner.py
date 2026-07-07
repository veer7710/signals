# ============================================================
# GOLD SCANNER v16 = v15 pip-target intraday + v14 daily swing
#
# INTRADAY (15m, the frequent engine — realistically 1-4/day):
#   1H trend gate · 15m EMA stack 9>21>50 · ADX>=20 rising + DI
#   RSI zone · pullback-to-EMA21-then-resume · ATR band · session
#   07-20 UTC · 30min cooldown · confidence score, only >=60% sent
#   SL ~25-30 pips, TP 40-60 pips. One intraday trade open at a time.
#
# SWING (daily, the rare big-move engine — expect ~1-3/month):
#   EMA20/50 daily cross + ADX(daily)>=20 + price confirmation
#   SL 1.5xATR(D), TP 4xATR(D) — held DAYS. One open max.
#   Sized at 0.01 lots in tracking (bigger = account-scale risk).
#
# BOTH: TP/SL pings, reversal warnings, Sunday report split by
# engine. Tracked on £110 · 0.01 lots (intraday 0.02 if conf>=80).
# Old-format log entries are ignored safely (no KeyError).
# ============================================================
import os, json, requests
from datetime import datetime, timezone, timedelta
import yfinance as yf
import pandas as pd
import numpy as np

TICKER="GC=F"; ACCOUNT=110.0; PIP=0.10; UPP001=0.10
TPMIN,TPMAX,MIN_CONF=40,60,60
SESS=(7,20); COOL_MIN=30
S_SL,S_TP=1.5,4.0
STATE_F,LOG_F="state.json","log.json"
BOT,CHAT=os.environ["TG_TOKEN"],os.environ["TG_CHAT"]

def send(m):
    r=requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",
        data={"chat_id":CHAT,"text":m,"parse_mode":"HTML"},timeout=15)
    return r.ok
def jload(p,d):
    try:
        with open(p) as f: return json.load(f)
    except Exception: return d
def jsave(p,o):
    with open(p,"w") as f: json.dump(o,f,indent=1)

def ema(s,n): return s.ewm(span=n,adjust=False).mean()
def rsi(s,n=14):
    d=s.diff()
    up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean()
    dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return 100-100/(1+up/dn)
def atr(h,l,c,n=14):
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n,adjust=False).mean()
def adx_di(h,l,c,n=14):
    up,dn=h.diff(),-l.diff()
    pdm=pd.Series(np.where((up>dn)&(up>0),up,0.0),index=h.index)
    mdm=pd.Series(np.where((dn>up)&(dn>0),dn,0.0),index=h.index)
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    a=tr.ewm(alpha=1/n,adjust=False).mean()
    pdi=100*pdm.ewm(alpha=1/n,adjust=False).mean()/a
    mdi=100*mdm.ewm(alpha=1/n,adjust=False).mean()/a
    dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    return dx.ewm(alpha=1/n,adjust=False).mean(),pdi,mdi

def fetch(interval,period):
    d=yf.download(TICKER,period=period,interval=interval,progress=False)
    if isinstance(d.columns,pd.MultiIndex): d.columns=d.columns.get_level_values(0)
    d=d.dropna(subset=["Close"])
    d.index=d.index.tz_localize("UTC") if d.index.tz is None else d.index.tz_convert("UTC")
    return d

state=jload(STATE_F,{}); log=jload(LOG_F,[])
if not isinstance(log,list): log=[]
log=[t for t in log if isinstance(t,dict) and t.get("v") in (15,16)]
for t in log: t.setdefault("eng","I"); t.setdefault("lots",0.01)
now=datetime.now(timezone.utc); out=[]

d15=fetch("15m","30d"); d1h=fetch("1h","60d"); dD=fetch("1d","1y")
if len(d15)<210 or len(d1h)<210 or len(dD)<210:
    print("insufficient data"); jsave(LOG_F,log); raise SystemExit

t1h=1 if ema(d1h["Close"],50).iloc[-2]>ema(d1h["Close"],200).iloc[-2] else -1
c,h,l,o=d15["Close"],d15["High"],d15["Low"],d15["Open"]
A=atr(h,l,c); Amed=A.rolling(50).median()
X,PDI,MDI=adx_di(h,l,c); R=rsi(c)
e9,e21,e50=ema(c,9),ema(c,21),ema(c,50)
i=-2; price=float(c.iloc[i]); a_=float(A.iloc[i])
cD,hD,lD=dD["Close"],dD["High"],dD["Low"]
e20d,e50d=ema(cD,20),ema(cD,50)
aD=float(atr(hD,lD,cD).iloc[-2]); Xd,_,_=adx_di(hD,lD,cD)

def stack(idx):
    if e9.iloc[idx]>e21.iloc[idx]>e50.iloc[idx] and PDI.iloc[idx]>MDI.iloc[idx]: return 1
    if e9.iloc[idx]<e21.iloc[idx]<e50.iloc[idx] and MDI.iloc[idx]>PDI.iloc[idx]: return -1
    return 0

# ---------- manage open trades ----------
for tr in log:
    if tr.get("status")!="open": continue
    src=d15 if tr["eng"]=="I" else dD
    since=src[src.index>datetime.fromisoformat(tr["time"])]
    res=None
    for _,row in since.iterrows():
        lo_,hi_=float(row["Low"]),float(row["High"])
        hs=lo_<=tr["sl"] if tr["side"]==1 else hi_>=tr["sl"]
        ht=hi_>=tr["tp"] if tr["side"]==1 else lo_<=tr["tp"]
        if hs: res=("loss",tr["sl"]); break
        if ht: res=("win",tr["tp"]); break
    if res:
        pips=(res[1]-tr["entry"])*tr["side"]/PIP
        pnl=pips*UPP001*(tr["lots"]/0.01)
        tr["status"],tr["pnl"],tr["closed_t"]=res[0],round(pnl,2),now.isoformat()
        ic="✅ TP hit" if res[0]=="win" else "❌ SL hit"
        eng="intraday" if tr["eng"]=="I" else "SWING"
        out.append(f"{ic} <b>GOLD {eng}</b> {'LONG' if tr['side']==1 else 'SHORT'} "
                   f"· {pips:+.0f} pips · {pnl:+.2f} USD")
    else:
        flip = (stack(i)==-tr["side"]) if tr["eng"]=="I" else \
               ((1 if e20d.iloc[-2]>e50d.iloc[-2] else -1)==-tr["side"])
        if flip and not tr.get("warned"):
            tr["warned"]=True
            eng="intraday" if tr["eng"]=="I" else "SWING"
            out.append(f"⚠️ <b>REVERSAL WARNING</b> — analysis flipped against your "
                       f"GOLD {eng} {'LONG' if tr['side']==1 else 'SHORT'} "
                       f"(entry {tr['entry']:.2f}, now {price:.2f}). Consider closing.")

open_i=any(t.get("status")=="open" and t["eng"]=="I" for t in log)
open_s=any(t.get("status")=="open" and t["eng"]=="S" for t in log)

# ---------- INTRADAY signal ----------
if not open_i:
    last_t=max((t["time"] for t in log if t["eng"]=="I"),
               default="2000-01-01T00:00:00+00:00")
    cooled=now-datetime.fromisoformat(last_t)>=timedelta(minutes=COOL_MIN)
    ts=d15.index[i]; am=float(Amed.iloc[i])
    env=(SESS[0]<=ts.hour<SESS[1] and np.isfinite(a_) and np.isfinite(am)
         and am>0 and 0.5*am<=a_<=2.5*am
         and (float(h.iloc[i])-float(l.iloc[i]))<=3*a_)
    if cooled and env:
        st=stack(i)
        if st!=0:
            adx_r=np.isfinite(X.iloc[i]) and X.iloc[i]>X.iloc[i-3]
            adx_s=np.isfinite(X.iloc[i]) and X.iloc[i]>=20
            c1,o1=price,float(o.iloc[i])
            ph,pl_=float(h.iloc[i-1]),float(l.iloc[i-1])
            rsi_ok=(st==1 and 45<=R.iloc[i]<=70) or (st==-1 and 30<=R.iloc[i]<=55)
            pull=(float(l.iloc[i-1])<=float(e21.iloc[i-1])) if st==1 else \
                 (float(h.iloc[i-1])>=float(e21.iloc[i-1]))
            resume=(c1>ph and c1>o1) if st==1 else (c1<pl_ and c1<o1)
            align=(st==t1h)
            score=(25 if align else 0)+(20 if adx_s else 0)+(15 if adx_r else 0)\
                 +(15 if rsi_ok else 0)+(15 if pull else 0)+(10 if resume else 0)
            if score>=MIN_CONF and align and resume:
                sl_p=max(25,round(1.2*a_/PIP))
                tp_p=min(TPMAX,max(TPMIN,round(2.0*a_/PIP)))
                sl=price-st*sl_p*PIP; tp=price+st*tp_p*PIP
                lots=0.02 if score>=80 else 0.01
                risk=sl_p*UPP001*(lots/0.01); rew=tp_p*UPP001*(lots/0.01)
                out.append(
                    f"{'🟢 LONG' if st==1 else '🔴 SHORT'} <b>GOLD</b> (15m) · "
                    f"confidence {score}%\nEntry ~{price:.2f}\n"
                    f"SL {sl:.2f} ({sl_p} pips) | TP {tp:.2f} ({tp_p} pips)\n"
                    f"Size: {lots} lots · risk ≈ ${risk:.2f} · reward ≈ ${rew:.2f}\n"
                    f"(trend ✅ · ADX {X.iloc[i]:.0f}{'↑' if adx_r else ''} · "
                    f"RSI {R.iloc[i]:.0f})")
                log.append({"v":16,"eng":"I","side":st,"entry":price,"sl":sl,
                            "tp":tp,"lots":lots,"conf":score,
                            "time":now.isoformat(),"status":"open"})

# ---------- SWING signal (daily) ----------
if not open_s:
    j=-2
    up_x=e20d.iloc[j]>e50d.iloc[j] and e20d.iloc[j-1]<=e50d.iloc[j-1]
    dn_x=e20d.iloc[j]<e50d.iloc[j] and e20d.iloc[j-1]>=e50d.iloc[j-1]
    pD=float(cD.iloc[j])
    if np.isfinite(aD) and aD>0 and np.isfinite(Xd.iloc[j]) and Xd.iloc[j]>=20:
        sg=1 if (up_x and pD>float(e50d.iloc[j])) else \
           -1 if (dn_x and pD<float(e50d.iloc[j])) else 0
        if sg:
            sl=pD-sg*S_SL*aD; tp=pD+sg*S_TP*aD
            r01=abs(pD-sl)/PIP*UPP001
            out.append(f"{'🟢 LONG' if sg==1 else '🔴 SHORT'} <b>GOLD SWING</b> (daily)\n"
                f"Entry ~{pD:.2f}\nSL {sl:.2f} | TP {tp:.2f} (4R — hold DAYS)\n"
                f"Size 0.01 lots · risk ≈ ${r01:.2f}\n"
                f"(EMA20/50 daily cross · ADX {Xd.iloc[j]:.0f})")
            log.append({"v":16,"eng":"S","side":sg,"entry":pD,"sl":sl,"tp":tp,
                        "lots":0.01,"conf":0,"time":now.isoformat(),"status":"open"})

# ---------- heartbeat + weekly ----------
today=now.strftime("%Y-%m-%d")
if state.get("hb")!=today and now.hour==7:
    wk=[t for t in log if datetime.fromisoformat(t["time"])>now-timedelta(days=7)]
    op=sum(1 for t in log if t.get("status")=="open")
    out.append(f"💓 Gold system alive · {len(wk)} signals this week · {op} open")
    state["hb"]=today
if state.get("wk")!=now.strftime("%Y-%W") and now.weekday()==6 and now.hour==20:
    done=[t for t in log if t.get("status") in ("win","loss")]
    if done:
        wins=[t for t in done if t["status"]=="win"]
        pnl=sum(t.get("pnl",0) for t in done); eq=ACCOUNT+pnl
        by={}
        for t in done:
            k="INTRA" if t["eng"]=="I" else "SWING"
            by.setdefault(k,[0,0]); by[k][0]+=1
            if t["status"]=="win": by[k][1]+=1
        split=" · ".join(f"{k} {v[1]}/{v[0]}" for k,v in by.items())
        out.append(f"📊 <b>Gold weekly</b>\n{len(done)} trades · "
                   f"{100*len(wins)/len(done):.0f}% win · {pnl:+.2f} USD\n"
                   f"Equity £{eq:.2f} · {split}")
    else:
        out.append("📊 Gold weekly: no closed trades yet.")
    state["wk"]=now.strftime("%Y-%W")

if out:
    if all(send(m) for m in out):
        jsave(STATE_F,state); jsave(LOG_F,log); print("sent",len(out))
    else: print("send failed")
else:
    jsave(STATE_F,state); jsave(LOG_F,log); print("quiet")

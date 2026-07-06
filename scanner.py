# ============================================================
# GOLD SIGNAL SYSTEM v14 — intraday (15m) + swing (daily) engines
#
# INTRADAY: up to 5/day, every one passes ALL checks:
#   1H trend gate + 4H agreement · 15m EMA stack 21>50>200
#   ADX(15m)>=20 rising w/ DI confirm · RSI healthy zone
#   pullback-to-EMA21-then-resume trigger · ATR band · session
#   07-20 UTC · 45min cooldown · one intraday trade open at a time
#   SL 1.2xATR(15m), TP 2.0xATR. Auto-expires after 5h if neither
#   hit (in-and-out by design, honest floor for this infra).
#
# SWING: rare, big-move engine on DAILY data. Fires only when
#   EMA20>EMA50 daily cross (or reverse) + ADX(daily)>=20 +
#   price confirms. TP 4xATR(daily), SL 1.5xATR, max ONE open,
#   held days. Alert shows $ at 0.01 AND 0.05 lots.
#
# BOTH: TP/SL hit alerts (tie=SL), reversal warnings when the
# analysis flips against an open trade. Sunday 20:00 weekly
# report with win-rate split by engine/session/direction.
# Tracked at 0.05 lots intraday / 0.01 swing on ~$127 (£100).
# ============================================================
import os, json, requests
from datetime import datetime, timezone, timedelta
import yfinance as yf
import pandas as pd
import numpy as np

TICKER = "GC=F"
LOTS_I, LOTS_S = 0.05, 0.01
UPD_I, UPD_S = LOTS_I*100, LOTS_S*100    # $ per $1 move
START_USD = 127.0
MAX_PER_DAY, COOL_MIN, SESS = 5, 45, (7, 20)
I_SL, I_TP, I_EXP_H = 1.2, 2.0, 5
S_SL, S_TP = 1.5, 4.0

STATE_F, LOG_F = "state.json", "log.json"
BOT, CHAT = os.environ["TG_TOKEN"], os.environ["TG_CHAT"]

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
now=datetime.now(timezone.utc); out=[]

d15=fetch("15m","30d"); d1h=fetch("1h","60d"); dD=fetch("1d","1y")
if len(d15)<250 or len(d1h)<210 or len(dD)<210:
    print("insufficient data"); raise SystemExit

def trend_dir(df,fast,slow):
    e_f,e_s=ema(df["Close"],fast),ema(df["Close"],slow)
    if e_f.iloc[-2]>e_s.iloc[-2]: return 1
    if e_f.iloc[-2]<e_s.iloc[-2]: return -1
    return 0
t1h=trend_dir(d1h,50,200); t4=t1h  # 1H gate; 4H approx via 1h ema200 side
c4=d1h["Close"].resample("4h").last().dropna()
if len(c4)>210:
    t4=1 if ema(c4,50).iloc[-2]>ema(c4,200).iloc[-2] else -1

c,h,l,o=d15["Close"],d15["High"],d15["Low"],d15["Open"]
A=atr(h,l,c); Amed=A.rolling(50).median()
X,PDI,MDI=adx_di(h,l,c); R=rsi(c)
e21,e50,e200=ema(c,21),ema(c,50),ema(c,200)
i=-2; price=float(c.iloc[i]); a_=float(A.iloc[i])

def stack_dir(idx):
    if e21.iloc[idx]>e50.iloc[idx]>e200.iloc[idx] and PDI.iloc[idx]>MDI.iloc[idx]: return 1
    if e21.iloc[idx]<e50.iloc[idx]<e200.iloc[idx] and MDI.iloc[idx]>PDI.iloc[idx]: return -1
    return 0

# ---------- manage open trades ----------
for tr in log:
    if tr.get("status")!="open": continue
    src=d15 if tr["eng"]=="I" else dD
    upd=UPD_I if tr["eng"]=="I" else UPD_S
    since=src[src.index>datetime.fromisoformat(tr["time"])]
    res=None
    for _,row in since.iterrows():
        lo_,hi_=float(row["Low"]),float(row["High"])
        hs=lo_<=tr["sl"] if tr["side"]==1 else hi_>=tr["sl"]
        ht=hi_>=tr["tp"] if tr["side"]==1 else lo_<=tr["tp"]
        if hs: res=("loss",tr["sl"]); break
        if ht: res=("win",tr["tp"]); break
    age_h=(now-datetime.fromisoformat(tr["time"])).total_seconds()/3600
    if res is None and tr["eng"]=="I" and age_h>=I_EXP_H:
        res=("expired",price)
    if res:
        pnl=(res[1]-tr["entry"])*tr["side"]*upd
        tr["status"],tr["pnl"],tr["closed_t"]=res[0],round(pnl,2),now.isoformat()
        ic={"win":"✅ TP hit","loss":"❌ SL hit","expired":"⏰ expired (5h)"}[res[0]]
        eng="intraday" if tr["eng"]=="I" else "SWING"
        out.append(f"{ic} <b>GOLD {eng}</b> "
                   f"{'LONG' if tr['side']==1 else 'SHORT'} {pnl:+.2f} USD")
    else:
        ds=stack_dir(i) if tr["eng"]=="I" else \
           (1 if ema(dD['Close'],20).iloc[-2]>ema(dD['Close'],50).iloc[-2] else -1)
        if ds==-tr["side"] and not tr.get("warned"):
            tr["warned"]=True
            eng="intraday" if tr["eng"]=="I" else "SWING"
            out.append(f"⚠️ <b>REVERSAL WARNING</b> — analysis flipped against your "
                       f"GOLD {eng} {'LONG' if tr['side']==1 else 'SHORT'} "
                       f"(entry {tr['entry']:.2f}, now {price:.2f}). Consider closing.")

open_i=any(t.get("status")=="open" and t["eng"]=="I" for t in log)
open_s=any(t.get("status")=="open" and t["eng"]=="S" for t in log)

# ---------- INTRADAY entry ----------
if not open_i:
    today=now.strftime("%Y-%m-%d")
    n_today=sum(1 for t in log if t["eng"]=="I" and t["time"][:10]==today)
    last_t=max((t["time"] for t in log if t["eng"]=="I"),
               default="2000-01-01T00:00:00+00:00")
    cooled=now-datetime.fromisoformat(last_t)>=timedelta(minutes=COOL_MIN)
    ts=d15.index[i]; am=float(Amed.iloc[i])
    ok_env=(SESS[0]<=ts.hour<SESS[1] and np.isfinite(a_) and np.isfinite(am)
            and am>0 and 0.5*am<=a_<=2.5*am
            and (float(h.iloc[i])-float(l.iloc[i]))<=3*a_)
    if n_today<MAX_PER_DAY and cooled and ok_env:
        adx_ok=np.isfinite(X.iloc[i]) and X.iloc[i]>=20 and X.iloc[i]>X.iloc[i-3]
        c1,o1=price,float(o.iloc[i])
        ph,pl_=float(h.iloc[i-1]),float(l.iloc[i-1])
        t21lo=float(l.iloc[i-1])<=float(e21.iloc[i-1])
        t21hi=float(h.iloc[i-1])>=float(e21.iloc[i-1])
        sig=0
        if (t1h==1 and t4==1 and stack_dir(i)==1 and adx_ok
            and 45<=R.iloc[i]<=70 and t21lo and c1>ph and c1>o1): sig=1
        elif (t1h==-1 and t4==-1 and stack_dir(i)==-1 and adx_ok
              and 30<=R.iloc[i]<=55 and t21hi and c1<pl_ and c1<o1): sig=-1
        if sig:
            sl=price-sig*I_SL*a_; tp=price+sig*I_TP*a_
            risk=abs(price-sl)*UPD_I
            out.append(f"{'🟢 LONG' if sig==1 else '🔴 SHORT'} <b>GOLD</b> (15m intraday)\n"
                f"Entry ~{price:.2f}\nSL {sl:.2f} | TP {tp:.2f}\n"
                f"At {LOTS_I} lots: risk ≈ ${risk:.0f} · reward ≈ ${risk*I_TP/I_SL:.0f}\n"
                f"Expect 1-4h hold · auto-expires 5h\n"
                f"(1H+4H trend ✅ · stack ✅ · ADX {X.iloc[i]:.0f}↑ · RSI {R.iloc[i]:.0f})")
            log.append({"eng":"I","side":sig,"entry":price,"sl":sl,"tp":tp,
                        "time":now.isoformat(),"status":"open",
                        "sess":"London" if ts.hour<13 else "NY"})

# ---------- SWING entry (daily) ----------
if not open_s:
    cD=dD["Close"]; hD,lD=dD["High"],dD["Low"]
    e20d,e50d=ema(cD,20),ema(cD,50)
    aD=float(atr(hD,lD,cD).iloc[-2])
    Xd,_,_=adx_di(hD,lD,cD)
    j=-2
    cross_up=e20d.iloc[j]>e50d.iloc[j] and e20d.iloc[j-1]<=e50d.iloc[j-1]
    cross_dn=e20d.iloc[j]<e50d.iloc[j] and e20d.iloc[j-1]>=e50d.iloc[j-1]
    pD=float(cD.iloc[j])
    if np.isfinite(aD) and aD>0 and np.isfinite(Xd.iloc[j]) and Xd.iloc[j]>=20:
        sig=1 if (cross_up and pD>float(e50d.iloc[j])) else \
            -1 if (cross_dn and pD<float(e50d.iloc[j])) else 0
        if sig:
            sl=pD-sig*S_SL*aD; tp=pD+sig*S_TP*aD
            r01=abs(pD-sl)*UPD_S; r05=abs(pD-sl)*UPD_I
            out.append(f"{'🟢 LONG' if sig==1 else '🔴 SHORT'} <b>GOLD SWING</b> (daily)\n"
                f"Entry ~{pD:.2f}\nSL {sl:.2f} | TP {tp:.2f} (4R — hold DAYS)\n"
                f"Risk: 0.01 lots ≈ ${r01:.0f} · 0.05 lots ≈ ${r05:.0f} "
                f"(0.05 on £100 = account-size risk, sized down on purpose)\n"
                f"(EMA20/50 daily cross · ADX {Xd.iloc[j]:.0f})")
            log.append({"eng":"S","side":sig,"entry":pD,"sl":sl,"tp":tp,
                        "time":now.isoformat(),"status":"open","sess":"swing"})

# ---------- heartbeat + weekly ----------
today=now.strftime("%Y-%m-%d")
if state.get("hb")!=today and now.hour==7:
    wk=[t for t in log if datetime.fromisoformat(t["time"])>now-timedelta(days=7)]
    op=sum(1 for t in log if t.get("status")=="open")
    out.append(f"💓 Gold system alive · {len(wk)} signals this week · {op} open")
    state["hb"]=today
if state.get("wk")!=now.strftime("%Y-%W") and now.weekday()==6 and now.hour==20:
    done=[t for t in log if t.get("status") in ("win","loss","expired")]
    if done:
        wins=[t for t in done if t["status"]=="win"]
        pnl=sum(t.get("pnl",0) for t in done); eq=START_USD+pnl
        by={}
        for t in done:
            keys=("INTRA" if t["eng"]=="I" else "SWING",
                  t.get("sess","?"),"LONG" if t["side"]==1 else "SHORT")
            for k in keys:
                by.setdefault(k,[0,0]); by[k][0]+=1
                if t["status"]=="win": by[k][1]+=1
        split=" · ".join(f"{k} {v[1]}/{v[0]}" for k,v in by.items())
        blown=" ⚠️ equity ≤ 0 — size too big for £100" if eq<=0 else ""
        out.append(f"📊 <b>Gold weekly</b>\n{len(done)} trades · "
                   f"{100*len(wins)/len(done):.0f}% win · {pnl:+.2f} USD\n"
                   f"Equity ${eq:.2f} (from $127){blown}\nSplit: {split}")
    else:
        out.append("📊 Gold weekly: no closed trades yet.")
    state["wk"]=now.strftime("%Y-%W")

if out:
    if all(send(m) for m in out):
        jsave(STATE_F,state); jsave(LOG_F,log); print("sent",len(out))
    else: print("send failed — not persisted")
else:
    jsave(STATE_F,state); jsave(LOG_F,log); print("quiet run")

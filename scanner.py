# ============================================================
# GOLD SCANNER v15 — short pip-target trades, confidence-scored
#
# Account: £110, 0.01 lots, 1:500 leverage. Gold pip = $0.10 move
# = ~$0.01 P&L per 0.01 lot per pip... (XAUUSD: 1 pip=0.1 price,
# 0.01 lot => $0.10 per pip). TP target ~40-60 pips, SL ~25-30.
#
# STRATEGY (short-hold momentum continuation, 15m):
#   1H trend gate -> 15m EMA stack 9>21>50 (reverse for short)
#   ADX(15m)>=20 rising + DI confirm · RSI 45-70 / 30-55
#   pullback to EMA9/21 then close beyond prior bar · ATR band
#   session 07-20 UTC · spike skip · cooldown 30m · 1 open max
#
# CONFIDENCE SCORE (0-100): each passed check adds weight; only
# signals scoring >=60 are sent. Higher score => suggests more
# size, but capped hard (see below). Score is descriptive, NOT a
# probability of winning — it just says how many filters aligned.
#
# TP/SL in PIPS and price. Position sizing suggestion is capped at
# 0.01-0.03 lots for a £110 account (anything more risks too much
# per trade — the app tells you but won't suggest reckless size).
#
# Tracks each signal at 0.01 lots, pings TP/SL hit + reversal
# warning, weekly win-rate report. Uses existing secrets/workflow.
# ============================================================
import os, json, requests
from datetime import datetime, timezone, timedelta
import yfinance as yf
import pandas as pd
import numpy as np

TICKER   = "GC=F"
ACCOUNT  = 110.0
PIP      = 0.10                 # XAUUSD: 1 pip = 0.10 price move
USD_PER_PIP_001 = 0.10          # ~$0.10 per pip at 0.01 lot
TP_PIPS_MIN, TP_PIPS_MAX = 40, 60
MIN_CONF = 60
SESS = (7, 20)
COOL_MIN = 30

STATE_F, LOG_F = "state.json", "log.json"
BOT, CHAT = os.environ["TG_TOKEN"], os.environ["TG_CHAT"]

def send(m):
    r=requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",
        data={"chat_id":CHAT,"text":m,"parse_mode":"HTML"},timeout=15)
    return r.ok
def jload(p,d):
    try:
        with open(p) as f:
            v=json.load(f); return v
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
# tolerate old-format entries: keep only v15 ones
log=[t for t in log if isinstance(t,dict) and t.get("v")==15]
now=datetime.now(timezone.utc); out=[]

d15=fetch("15m","30d"); d1h=fetch("1h","60d")
if len(d15)<210 or len(d1h)<210:
    print("insufficient data"); jsave(LOG_F,log); raise SystemExit

t1h = 1 if ema(d1h["Close"],50).iloc[-2]>ema(d1h["Close"],200).iloc[-2] else -1
c,h,l,o=d15["Close"],d15["High"],d15["Low"],d15["Open"]
A=atr(h,l,c); Amed=A.rolling(50).median()
X,PDI,MDI=adx_di(h,l,c); R=rsi(c)
e9,e21,e50=ema(c,9),ema(c,21),ema(c,50)
i=-2; price=float(c.iloc[i]); a_=float(A.iloc[i])

def stack(idx):
    if e9.iloc[idx]>e21.iloc[idx]>e50.iloc[idx] and PDI.iloc[idx]>MDI.iloc[idx]: return 1
    if e9.iloc[idx]<e21.iloc[idx]<e50.iloc[idx] and MDI.iloc[idx]>PDI.iloc[idx]: return -1
    return 0

# ---- manage open trade ----
open_tr=next((t for t in log if t.get("status")=="open"),None)
if open_tr:
    since=d15[d15.index>datetime.fromisoformat(open_tr["time"])]
    res=None
    for _,row in since.iterrows():
        lo_,hi_=float(row["Low"]),float(row["High"])
        hs=lo_<=open_tr["sl"] if open_tr["side"]==1 else hi_>=open_tr["sl"]
        ht=hi_>=open_tr["tp"] if open_tr["side"]==1 else lo_<=open_tr["tp"]
        if hs: res=("loss",open_tr["sl"]); break
        if ht: res=("win",open_tr["tp"]); break
    if res:
        pips=(res[1]-open_tr["entry"])*open_tr["side"]/PIP
        pnl=pips*USD_PER_PIP_001*(open_tr["lots"]/0.01)
        open_tr["status"],open_tr["pnl"]=res[0],round(pnl,2)
        open_tr["closed_t"]=now.isoformat()
        ic="✅ TP hit" if res[0]=="win" else "❌ SL hit"
        out.append(f"{ic} <b>GOLD</b> {'LONG' if open_tr['side']==1 else 'SHORT'} · "
                   f"{pips:+.0f} pips · {pnl:+.2f} USD")
        open_tr=None
    else:
        if stack(i)==-open_tr["side"] and not open_tr.get("warned"):
            open_tr["warned"]=True
            out.append(f"⚠️ <b>REVERSAL WARNING</b> — momentum flipped against your "
                       f"GOLD {'LONG' if open_tr['side']==1 else 'SHORT'} "
                       f"(entry {open_tr['entry']:.2f}, now {price:.2f}). Consider closing.")

# ---- new signal ----
if open_tr is None:
    today=now.strftime("%Y-%m-%d")
    last_t=max((t["time"] for t in log),default="2000-01-01T00:00:00+00:00")
    cooled=now-datetime.fromisoformat(last_t)>=timedelta(minutes=COOL_MIN)
    ts=d15.index[i]; am=float(Amed.iloc[i])
    env_ok=(SESS[0]<=ts.hour<SESS[1] and np.isfinite(a_) and np.isfinite(am)
            and am>0 and 0.5*am<=a_<=2.5*am
            and (float(h.iloc[i])-float(l.iloc[i]))<=3*a_)
    if cooled and env_ok:
        st=stack(i)
        adx_rising=np.isfinite(X.iloc[i]) and X.iloc[i]>X.iloc[i-3]
        adx_strong=np.isfinite(X.iloc[i]) and X.iloc[i]>=20
        c1,o1=price,float(o.iloc[i])
        ph,pl_=float(h.iloc[i-1]),float(l.iloc[i-1])
        rsi_ok = (st==1 and 45<=R.iloc[i]<=70) or (st==-1 and 30<=R.iloc[i]<=55)
        pull = (float(l.iloc[i-1])<=float(e21.iloc[i-1])) if st==1 else \
               (float(h.iloc[i-1])>=float(e21.iloc[i-1]))
        resume = (c1>ph and c1>o1) if st==1 else (c1<pl_ and c1<o1)
        trend_align = (st==t1h)

        if st!=0:
            # confidence score: weighted checks
            score=0
            score += 25 if trend_align else 0
            score += 20 if adx_strong else 0
            score += 15 if adx_rising else 0
            score += 15 if rsi_ok else 0
            score += 15 if pull else 0
            score += 10 if resume else 0
            if score>=MIN_CONF and trend_align and resume:
                # SL sized to ~ the greater of ATR-based or 25 pips, TP 40-60 pips
                sl_pips=max(25, round(1.2*a_/PIP))
                tp_pips=min(TP_PIPS_MAX, max(TP_PIPS_MIN, round(2.0*a_/PIP)))
                sl=price - st*sl_pips*PIP
                tp=price + st*tp_pips*PIP
                # sizing suggestion capped for £110
                lots = 0.01
                if score>=80: lots=0.02
                risk_usd=sl_pips*USD_PER_PIP_001*(lots/0.01)
                rew_usd =tp_pips*USD_PER_PIP_001*(lots/0.01)
                side="🟢 LONG" if st==1 else "🔴 SHORT"
                out.append(
                    f"{side} <b>GOLD</b> (15m) · confidence {score}%\n"
                    f"Entry ~{price:.2f}\n"
                    f"SL {sl:.2f} ({sl_pips} pips) | TP {tp:.2f} ({tp_pips} pips)\n"
                    f"Suggested size: {lots} lots ({'1' if lots<=0.01 else '1-2'} position)\n"
                    f"Risk ≈ ${risk_usd:.2f} · reward ≈ ${rew_usd:.2f}\n"
                    f"(trend {'✅' if trend_align else '⚠️'} · ADX {X.iloc[i]:.0f}"
                    f"{'↑' if adx_rising else ''} · RSI {R.iloc[i]:.0f})")
                log.append({"v":15,"side":st,"entry":price,"sl":sl,"tp":tp,
                            "lots":lots,"conf":score,"time":now.isoformat(),
                            "status":"open"})

# ---- weekly report Sun 20:00 ----
if state.get("wk")!=now.strftime("%Y-%W") and now.weekday()==6 and now.hour==20:
    done=[t for t in log if t.get("status") in ("win","loss")]
    if done:
        wins=[t for t in done if t["status"]=="win"]
        pnl=sum(t.get("pnl",0) for t in done); eq=ACCOUNT+pnl
        avgc=np.mean([t.get("conf",0) for t in done])
        out.append(f"📊 <b>Gold weekly</b>\n{len(done)} trades · "
                   f"{100*len(wins)/len(done):.0f}% win · {pnl:+.2f} USD\n"
                   f"Equity £{eq:.2f} · avg confidence {avgc:.0f}%")
    else:
        out.append("📊 Gold weekly: no closed trades yet.")
    state["wk"]=now.strftime("%Y-%W")

if out:
    if all(send(m) for m in out):
        jsave(STATE_F,state); jsave(LOG_F,log); print("sent",len(out))
    else: print("send failed")
else:
    jsave(STATE_F,state); jsave(LOG_F,log); print("quiet")

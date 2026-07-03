# ============================================================
# SIGNAL SCANNER v8 = v7 (unchanged) + AUTO PAPER-TRADER
#
# TWO ENGINES RUN SIDE BY SIDE:
#
#  A) SIGNALS TO YOU  — strict v7 rules, unchanged. Same alerts,
#     same A/B tiers, same resolution + weekly recap. This is
#     what you read and (later) trade for real.
#
#  B) PAPER ACCOUNT   — a self-running simulated account:
#     * starts at PAPER_START (£150)
#     * takes EVERY strict signal above (so you see those play out)
#       PLUS extra looser-filter signals for more frequency
#     * sizes each trade at PAPER_RISK (2%) off the ATR stop
#     * opens/closes itself against real prices, no input from you
#     * reports briefly EVERY HOUR: open trades, closed this hour,
#       wins/losses, and running balance
#
#  Frequency is loosened HONESTLY (lower score, no ADX floor,
#  shorter cooldown) — NOT by forcing a quota. Some hours will be
#  busy, some quiet. That's the real result.
#
#  NOTE: paper trades use next-candle prices and ignore spread/
#  slippage, so paper profit will look BETTER than live ever would.
#  Treat the balance as optimistic, and watch win-rate more than £.
#
# Requires yml that commits state.json, log.json, paper.json.
# ============================================================

import os, json, time, requests
from datetime import datetime, timezone, timedelta
import yfinance as yf
import pandas as pd
import numpy as np

SYMBOLS = {
    "Gold":      ("GC=F",     "METAL"),
    "Silver":    ("SI=F",     "METAL"),
    "Oil (WTI)": ("CL=F",     "ENERGY"),
    "Nat Gas":   ("NG=F",     "ENERGY"),
    "EUR/USD":   ("EURUSD=X", "FX"),
    "GBP/USD":   ("GBPUSD=X", "FX"),
    "USD/JPY":   ("USDJPY=X", "FX"),
    "AUD/USD":   ("AUDUSD=X", "FX"),
    "USD/CAD":   ("USDCAD=X", "FX"),
    "NZD/USD":   ("NZDUSD=X", "FX"),
    "US500":     ("ES=F",     "INDEX"),
    "US100":     ("NQ=F",     "INDEX"),
    "UK100":     ("^FTSE",    "INDEX"),
    "DE40":      ("^GDAXI",   "INDEX"),
    "Apple":     ("AAPL",     "STOCK"),
    "Microsoft": ("MSFT",     "STOCK"),
    "Nvidia":    ("NVDA",     "STOCK"),
    "Tesla":     ("TSLA",     "STOCK"),
    "Amazon":    ("AMZN",     "STOCK"),
}
MUST_INCLUDE = {"METAL":"BREAKOUT","ENERGY":"BREAKOUT","FX":"MOMENTUM",
                "INDEX":"TREND","STOCK":"TREND"}

# interval, period, conf_int, conf_per, hold, max_age, cooldown(strict), expiry_h
TIMEFRAMES = [
    ("15m","5d","1h","30d","close same day",45,120,24),
    ("1h","60d","1d","1y","swing 1-2 days",180,480,120),
]

# strict (signals to you)
MIN_SCORE, ADX_DEAD = 2, 15
# loose (paper only) — slightly less harsh, honestly
MIN_SCORE_P, ADX_DEAD_P, COOL_P = 2, 8, 45

STOP_ATR, TP_ATR, MIN_ATR_PCT, FRESH_FLIP = 1.5, 2.5, 0.0004, 3
PAPER_START, PAPER_RISK = 150.0, 0.02

STATE_FILE, LOG_FILE, PAPER_FILE = "state.json", "log.json", "paper.json"
BOT_TOKEN, CHAT_ID = os.environ["TG_TOKEN"], os.environ["TG_CHAT"]

def jload(p, d):
    try:
        with open(p) as f: return json.load(f)
    except Exception: return d
def jsave(p, o):
    with open(p, "w") as f: json.dump(o, f, indent=1)

def send(msg):
    r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id":CHAT_ID,"text":msg,"parse_mode":"HTML"}, timeout=15)
    if not r.ok: print("TG fail:", r.status_code, r.text[:150])
    return r.ok
def send_chunked(parts):
    ok, chunk, sz = True, [], 0
    for a in parts:
        if sz+len(a) > 3300 and chunk:
            ok &= send("\n\n".join(chunk)); chunk, sz = [], 0
        chunk.append(a); sz += len(a)
    if chunk: ok &= send("\n\n".join(chunk))
    return ok

_last = [0.0]
def get(t, p, i):
    w = 0.4 - (time.time()-_last[0])
    if w > 0: time.sleep(w)
    for _ in (1,2):
        d = yf.download(t, period=p, interval=i, progress=False)
        _last[0] = time.time()
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        d = d.dropna(subset=["Close"]) if len(d) else d
        if len(d): return d
        time.sleep(2)
    return d

def ema(s,n): return s.ewm(span=n,adjust=False).mean()
def rsi(s,n=14):
    d=s.diff(); up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean()
    dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return 100-100/(1+up/dn)
def stoch(h,l,c,n=14,d=3):
    lo,hi=l.rolling(n).min(),h.rolling(n).max()
    return (100*(c-lo)/(hi-lo).replace(0,np.nan)).rolling(d).mean()
def atr_s(h,l,c,n=14):
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

def votes_df(df):
    c,h,l=df["Close"],df["High"],df["Low"]; v=pd.DataFrame(index=df.index)
    e9,e21,e200=ema(c,9),ema(c,21),ema(c,200)
    macd=ema(c,12)-ema(c,26); macds=ema(macd,9)
    t1=np.where((e9>e21)&(c>e200),1,np.where((e9<e21)&(c<e200),-1,0))
    t2=np.where((macd>macds)&(macd>0),1,np.where((macd<macds)&(macd<0),-1,0))
    v["TREND"]=np.where((t1==1)&(t2==1),1,np.where((t1==-1)&(t2==-1),-1,0))
    r=rsi(c); k=stoch(h,l,c)
    m1=np.where(r>55,1,np.where(r<45,-1,0)); m2=np.nan_to_num(np.where(k>60,1,np.where(k<40,-1,0)))
    v["MOMENTUM"]=np.where(((m1==1)&(m2>=0))|((m2==1)&(m1>=0)),1,
                  np.where(((m1==-1)&(m2<=0))|((m2==-1)&(m1<=0)),-1,0))
    mid=c.rolling(20).mean(); sd=c.rolling(20).std()
    v["VOLATILITY"]=np.where(c>mid+2*sd,1,np.where(c<mid-2*sd,-1,0))
    hh,ll=h.rolling(20).max().shift(),l.rolling(20).min().shift()
    v["BREAKOUT"]=np.where(c>hh,1,np.where(c<ll,-1,0))
    return v

def htf(t,i,p):
    try:
        d=get(t,p,i)
        if len(d)<210: return 0
        c=d["Close"]; e50,e200=ema(c,50),ema(c,200)
        if e50.iloc[-1]>e200.iloc[-1] and c.iloc[-1]>e200.iloc[-1]: return 1
        if e50.iloc[-1]<e200.iloc[-1] and c.iloc[-1]<e200.iloc[-1]: return -1
    except Exception: pass
    return 0

def fmt(x,ref):
    dp=4 if ref<50 else 2 if ref<10000 else 1
    return f"{x:.{dp}f}"
def sess(dt):
    hh=dt.hour
    return "London" if 7<=hh<13 else "NY" if 13<=hh<21 else "Asia"

# ---------- resolve logged signals (strict, for weekly recap) ----------
def resolve(log, closer):
    changed=False; groups={}
    for s in log:
        if s["status"]=="open": groups.setdefault((s["ticker"],s["tf"]),[]).append(s)
    msgs=[]
    for (tk,tf),sigs in groups.items():
        try: d=get(tk,"5d" if tf=="15m" else "30d",tf)
        except Exception: continue
        if not len(d): continue
        if d.index.tz is None: d.index=d.index.tz_localize("UTC")
        for s in sigs:
            df=d[d.index>datetime.fromisoformat(s["time"])]
            if not len(df): continue
            r=None
            for _,row in df.iterrows():
                lo,hi=float(row["Low"]),float(row["High"])
                hs=(lo<=s["stop"]) if s["side"]==1 else (hi>=s["stop"])
                ht=(hi>=s["tp"]) if s["side"]==1 else (lo<=s["tp"])
                if hs: r=("loss",-abs(s["entry"]-s["stop"])); break
                if ht: r=("win",abs(s["tp"]-s["entry"])); break
            if r is None:
                age=(datetime.now(timezone.utc)-datetime.fromisoformat(s["time"])).total_seconds()/3600
                if age>=s["expiry_h"]:
                    r=("expired",(float(df["Close"].iloc[-1])-s["entry"])*s["side"])
            if r:
                s["status"],s["points"]=r[0],round(r[1],4); changed=True
                if closer: closer(s,r)
    return msgs, changed

def weekly(log):
    cut=datetime.now(timezone.utc)-timedelta(days=7)
    done=[s for s in log if s["status"] in("win","loss","expired")
          and datetime.fromisoformat(s["time"])>cut]
    if not done: return "📊 <b>Weekly recap</b>\nNo resolved signals yet."
    out=["📊 <b>Weekly recap</b> (7d)"]
    for tier in("A","B"):
        ts=[s for s in done if s["tier"]==tier]
        if not ts: continue
        w=sum(1 for s in ts if s["status"]=="win")
        out.append(f"[{tier}] {len(ts)} · {w}W ({100*w/len(ts):.0f}%)")
    return "\n".join(out)

# ================= PAPER ACCOUNT =================
def paper_resolve(book):
    """Close open trades in a book (loose or strict) vs real prices."""
    events=[]; groups={}
    for tr in book["open"]:
        groups.setdefault((tr["ticker"],tr["tf"]),[]).append(tr)
    for (tk,tf),trs in groups.items():
        try: d=get(tk,"5d" if tf=="15m" else "30d",tf)
        except Exception: continue
        if not len(d): continue
        if d.index.tz is None: d.index=d.index.tz_localize("UTC")
        for tr in trs:
            df=d[d.index>datetime.fromisoformat(tr["time"])]
            if not len(df): continue
            r=None
            for _,row in df.iterrows():
                lo,hi=float(row["Low"]),float(row["High"])
                hs=(lo<=tr["stop"]) if tr["side"]==1 else (hi>=tr["stop"])
                ht=(hi>=tr["tp"]) if tr["side"]==1 else (lo<=tr["tp"])
                if hs: r=("loss",tr["stop"]); break
                if ht: r=("win",tr["tp"]); break
            if r is None:
                age=(datetime.now(timezone.utc)-datetime.fromisoformat(tr["time"])).total_seconds()/3600
                if age>=tr["expiry_h"]:
                    r=("expired",float(df["Close"].iloc[-1]))
            if r:
                pnl=(r[1]-tr["entry"])*tr["side"]*tr["units"]
                book["balance"]=round(book["balance"]+pnl,2)
                tr["result"],tr["pnl"]=r[0],round(pnl,2)
                book["closed"].append(tr); events.append((tr,r[0],pnl))
    book["open"]=[t for t in book["open"] if "result" not in t]
    return events

# ==================== MAIN ====================
state=jload(STATE_FILE,{}); log=jload(LOG_FILE,[])
paper=jload(PAPER_FILE,{
    "loose":{"balance":PAPER_START,"open":[],"closed":[]},
    "strict":{"balance":PAPER_START,"open":[],"closed":[]},
    "start":PAPER_START,"last_hb":"","last_week":""})
now=datetime.now(timezone.utc)
alerts=[]; state_changes={}; log_changed=False

# resolve strict log (for your weekly recap)
_,log_changed=resolve(log,None)

# resolve BOTH paper books before opening new ones
loose_events=paper_resolve(paper["loose"])
strict_events=paper_resolve(paper["strict"])

# scan
for name,(tk,klass) in SYMBOLS.items():
    for interval,period,ci,cp,hold,max_age,cool,exp_h in TIMEFRAMES:
        key=f"{name}|{interval}"
        try:
            df=get(tk,period,interval)
            if len(df)<210: continue
            lt=df.index[-1]
            if lt.tzinfo is None: lt=lt.tz_localize("UTC")
            if (now-lt.tz_convert(timezone.utc)).total_seconds()/60>max_age: continue

            v=votes_df(df); score=v.sum(axis=1); idx=-2
            c,h,l=df["Close"],df["High"],df["Low"]
            price=float(c.iloc[idx]); a=float(atr_s(h,l,c).iloc[idx])
            if not np.isfinite(a) or a<price*MIN_ATR_PCT: continue
            adx_now=float(adx(h,l,c).iloc[idx])
            must=v.iloc[idx][MUST_INCLUDE[klass]]
            stop_d,tp_d=STOP_ATR*a,TP_ATR*a

            # ---- STRICT signal (to you) ----
            sig_strict=int(np.where(score.iloc[idx]>=MIN_SCORE,1,
                        np.where(score.iloc[idx]<=-MIN_SCORE,-1,0)))
            prev=state.get(key,{"sig":0,"t":"2000-01-01T00:00:00+00:00"})
            fired_dir=0
            if sig_strict!=0 and sig_strict!=prev["sig"] \
               and now-datetime.fromisoformat(prev["t"])>=timedelta(minutes=cool) \
               and (v.iloc[idx-FRESH_FLIP:idx][MUST_INCLUDE[klass]]!=sig_strict).any() \
               and must==sig_strict and (not np.isfinite(adx_now) or adx_now>=ADX_DEAD):
                h1=htf(tk,ci,cp)
                if h1!=-sig_strict:
                    vol_ok=True
                    if klass in("STOCK","INDEX") and "Volume" in df.columns:
                        v20=df["Volume"].rolling(20).mean().iloc[idx]
                        if np.isfinite(v20) and v20>0: vol_ok=df["Volume"].iloc[idx]>=v20
                    sc=int(abs(score.iloc[idx]))
                    tier="A" if(sc>=3 and h1==sig_strict and vol_ok) else "B"
                    stop=price-sig_strict*stop_d; tp=price+sig_strict*tp_d
                    sd_txt="🟢 LONG" if sig_strict==1 else "🔴 SHORT"
                    alerts.append(f"{sd_txt} <b>{name}</b> ({interval}) [{tier}] · {sess(now)}\n"
                        f"Entry ~{fmt(price,price)}\n"
                        f"Stop {fmt(stop,price)} (−{fmt(stop_d,price)}) | "
                        f"Target {fmt(tp,price)} (+{fmt(tp_d,price)})\n{hold}")
                    log.append({"name":name,"ticker":tk,"tf":interval,"tier":tier,
                        "side":sig_strict,"entry":price,"stop":stop,"tp":tp,
                        "expiry_h":exp_h,"time":now.isoformat(),
                        "session":sess(now),"status":"open"}); log_changed=True
                    state_changes[key]={"sig":sig_strict,"t":now.isoformat()}
                    fired_dir=sig_strict
                    # strict trade goes into BOTH paper books
                    for book in (paper["loose"], paper["strict"]):
                        if any(t["ticker"]==tk and t["tf"]==interval for t in book["open"]):
                            continue
                        rc=book["balance"]*PAPER_RISK
                        book["open"].append({"name":name,"ticker":tk,"tf":interval,
                            "side":sig_strict,"entry":price,"stop":stop,"tp":tp,
                            "units":rc/stop_d if stop_d>0 else 0,
                            "expiry_h":exp_h,"time":now.isoformat()})

            # ---- LOOSE signal (paper only) ----
            sig_p=int(np.where(score.iloc[idx]>=MIN_SCORE_P,1,
                     np.where(score.iloc[idx]<=-MIN_SCORE_P,-1,0)))
            pkey=f"P|{key}"
            pprev=state.get(pkey,{"sig":0,"t":"2000-01-01T00:00:00+00:00"})
            already=any(t["ticker"]==tk and t["tf"]==interval for t in paper["loose"]["open"])
            if sig_p!=0 and sig_p!=pprev["sig"] and not already \
               and now-datetime.fromisoformat(pprev["t"])>=timedelta(minutes=COOL_P) \
               and must==sig_p and (not np.isfinite(adx_now) or adx_now>=ADX_DEAD_P):
                stop=price-sig_p*stop_d; tp=price+sig_p*tp_d
                rc=paper["loose"]["balance"]*PAPER_RISK
                paper["loose"]["open"].append({"name":name,"ticker":tk,"tf":interval,
                    "side":sig_p,"entry":price,"stop":stop,"tp":tp,
                    "units":rc/stop_d if stop_d>0 else 0,
                    "expiry_h":exp_h,"time":now.isoformat()})
                state_changes[pkey]={"sig":sig_p,"t":now.isoformat()}
        except Exception as e:
            print(f"{key} failed: {e}")

# ---- assemble outbound ----
out=list(alerts)

def book_stats(book, hours=None):
    cl=book["closed"]
    if hours is not None:
        cut=now-timedelta(hours=hours)
        cl=[t for t in cl if datetime.fromisoformat(t["time"])>cut]
    n=len(cl); w=sum(1 for t in cl if t.get("result")=="win")
    wr=f"{100*w/n:.0f}%" if n else "—"
    return n, wr

# hourly report — split, minimal.
# Quiet hours: no hourly between 00:00-09:59; at 10:00 one combined report.
hb_key=now.strftime("%Y-%m-%dT%H")
quiet = 0 <= now.hour < 10
if paper.get("last_hb")!=hb_key and not quiet:
    L,S=paper["loose"],paper["strict"]
    window = 11 if now.hour==10 else 1   # 10am covers the overnight stretch
    lc,lwr=book_stats(L,window); sc,swr=book_stats(S,window)
    label = "overnight" if now.hour==10 else "hr"
    out.append(
        f"⏱ Paper ({label})\n"
        f"Loose £{L['balance']:.0f} · {lc} closed · {lwr} win\n"
        f"Strict £{S['balance']:.0f} · {sc} closed · {swr} win")
    paper["last_hb"]=hb_key

# weekly report — split, minimal (Sun 8pm)
wk_key=now.strftime("%Y-%W")
if paper.get("last_week")!=wk_key and now.weekday()==6 and now.hour==20:
    L,S=paper["loose"],paper["strict"]
    ln,lwr=book_stats(L); sn,swr=book_stats(S)
    lp=L["balance"]-paper["start"]; sp=S["balance"]-paper["start"]
    out.append(
        f"📊 Paper (week)\n"
        f"Loose £{L['balance']:.0f} ({lp:+.0f}) · {ln} trades · {lwr} win\n"
        f"Strict £{S['balance']:.0f} ({sp:+.0f}) · {sn} trades · {swr} win")
    paper["last_week"]=wk_key

# ---- send + persist ----
if out:
    if send_chunked(out):
        state.update(state_changes); jsave(STATE_FILE,state)
        if log_changed: jsave(LOG_FILE,log)
        jsave(PAPER_FILE,paper)
        print("Sent",len(out),"part(s)")
    else:
        print("send failed; not persisting")
else:
    state.update(state_changes); jsave(STATE_FILE,state)
    if log_changed: jsave(LOG_FILE,log)
    jsave(PAPER_FILE,paper)
    print("No new signals this run.")


# ============================================================
# backtest.py — on-demand walk-forward backtest, 4 pairs, 60 days
#
# HONESTY RULES BUILT IN (no cheating):
#  - Signals use ONLY closed candles (no look-ahead)
#  - Entry fills at the NEXT candle's open, spread cost charged
#  - If a candle touches both stop and target -> counted as LOSS
#  - £100 start, 0.75% of equity risked per trade, compounding
#  - Session hours + per-pair engine identical to MultiPairPro:
#      GOLD, GBP/JPY  -> breakout (prior-day high/low, ADX,
#                        volume confirm where volume data exists)
#      EUR/USD,GBP/USD-> EMA pullback (trend + dip + momentum)
#
# Runs via the manual "backtest" workflow. Sends one Telegram
# summary. Data source caps 15m history at ~60 days.
# ============================================================

import os, requests
import yfinance as yf
import pandas as pd
import numpy as np

START_BAL   = 100.0
RISK_PCT    = 0.0075
STOP_ATR    = 1.5
TP_ATR      = 2.5
ADX_MIN     = 20.0
VOL_MULT    = 1.3
MAX_PER_DAY = 3
SPREAD_PCT  = {"GOLD":0.0004,"GBP/JPY":0.0003,"EUR/USD":0.0002,"GBP/USD":0.00025}

PAIRS = {
    "GOLD":    ("GC=F",     "BREAKOUT", 7, 21),
    "GBP/JPY": ("GBPJPY=X", "BREAKOUT", 0, 12),
    "EUR/USD": ("EURUSD=X", "PULLBACK", 7, 17),
    "GBP/USD": ("GBPUSD=X", "PULLBACK", 7, 17),
}

BOT = os.environ["TG_TOKEN"]; CHAT = os.environ["TG_CHAT"]
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

def backtest_pair(name, ticker, engine, s0, s1, equity_start):
    d = yf.download(ticker, period="60d", interval="15m", progress=False)
    if isinstance(d.columns, pd.MultiIndex): d.columns=d.columns.get_level_values(0)
    d = d.dropna(subset=["Close"])
    if len(d) < 300: return None
    if d.index.tz is None: d.index = d.index.tz_localize("UTC")
    else: d.index = d.index.tz_convert("UTC")

    c,h,l,o = d["Close"],d["High"],d["Low"],d["Open"]
    e200, e21 = ema(c,200), ema(c,21)
    A, X = atr(h,l,c), adx(h,l,c)
    vol = d["Volume"] if "Volume" in d and d["Volume"].sum()>0 else None
    volavg = vol.rolling(20).mean() if vol is not None else None

    # prior-day high/low, shifted so candle i only sees YESTERDAY
    daily = d.resample("1D").agg({"High":"max","Low":"min"}).dropna()
    pdh = daily["High"].shift(1).reindex(d.index, method="ffill")
    pdl = daily["Low"].shift(1).reindex(d.index, method="ffill")

    eq = equity_start
    trades=[]; pos=None; day=None; n_today=0
    spread = SPREAD_PCT[name]

    for i in range(210, len(d)-1):
        ts = d.index[i]
        if ts.date()!=day: day=ts.date(); n_today=0

        # ---- manage open position against candle i ----
        if pos:
            lo,hi = float(l.iloc[i]), float(h.iloc[i])
            hit_sl = lo<=pos["sl"] if pos["dir"]==1 else hi>=pos["sl"]
            hit_tp = hi>=pos["tp"] if pos["dir"]==1 else lo<=pos["tp"]
            exit_px=None
            if hit_sl: exit_px=pos["sl"]          # tie -> loss (conservative)
            elif hit_tp: exit_px=pos["tp"]
            if exit_px is not None:
                pnl=(exit_px-pos["entry"])*pos["dir"]*pos["units"]
                pnl-=pos["entry"]*spread*pos["units"]
                eq+=pnl; trades.append(pnl); pos=None
            continue   # one position at a time; no same-candle re-entry

        # ---- entry signal from CLOSED candle i, fill at open of i+1 ----
        if not (s0 <= ts.hour < s1): continue
        if n_today >= MAX_PER_DAY: continue
        a_=float(A.iloc[i]); adx_=float(X.iloc[i])
        if not np.isfinite(a_) or a_<=0 or not np.isfinite(adx_) or adx_<ADX_MIN:
            continue
        c1,o1,h1,l1=float(c.iloc[i]),float(o.iloc[i]),float(h.iloc[i]),float(l.iloc[i])
        if h1-l1 > 3.0*a_: continue                      # spike filter

        sig=0
        if engine=="BREAKOUT":
            if volavg is not None:
                v1=float(vol.iloc[i]); va=float(volavg.iloc[i])
                if not np.isfinite(va) or va<=0 or v1 < VOL_MULT*va: continue
            ph,pl_=float(pdh.iloc[i]),float(pdl.iloc[i])
            if np.isfinite(ph) and c1>ph and o1<=ph and c1>o1: sig=1
            elif np.isfinite(pl_) and c1<pl_ and o1>=pl_ and c1<o1: sig=-1
        else:  # PULLBACK
            eT,eP=float(e200.iloc[i]),float(e21.iloc[i])
            if c1>eT and l1<=eP and c1>o1: sig=1
            elif c1<eT and h1>=eP and c1<o1: sig=-1

        if sig==0: continue
        entry=float(o.iloc[i+1])                          # next-candle open
        sl=entry - sig*STOP_ATR*a_
        tp=entry + sig*TP_ATR*a_
        risk_cash=eq*RISK_PCT
        stop_dist=abs(entry-sl)
        if stop_dist<=0: continue
        pos={"dir":sig,"entry":entry,"sl":sl,"tp":tp,
             "units":risk_cash/stop_dist}
        n_today+=1

    wins=[t for t in trades if t>0]
    return {"trades":len(trades),
            "win%": round(100*len(wins)/len(trades),1) if trades else 0,
            "pnl": round(eq-equity_start,2),
            "eq_out": eq}

# ---- run all four sequentially on ONE compounding £100 account ----
eq=START_BAL; lines=[]; total_trades=0
for name,(tk,eng,s0,s1) in PAIRS.items():
    r=backtest_pair(name,tk,eng,s0,s1,eq)
    if r is None:
        lines.append(f"{name}: no data"); continue
    eq=r["eq_out"]; total_trades+=r["trades"]
    lines.append(f"{name}: {r['trades']} trades · {r['win%']}% win · {r['pnl']:+.2f}")

msg=("🧪 <b>60-day walk-forward backtest</b> (£100 start, 0.75% risk,\n"
     "spread charged, ties = losses, no look-ahead)\n\n"
     + "\n".join(lines) +
     f"\n\n<b>Final: £{eq:.2f} ({eq-START_BAL:+.2f}) · {total_trades} trades</b>"
     "\n\nNo slippage modelled — real results would be slightly worse."
     "\nOne 60-day window ≠ proof. Re-run monthly and compare.")
send(msg)
print(msg)

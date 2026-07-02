# ============================================================
# SIGNAL SCANNER — checks gold + major currencies every run,
# sends a Telegram message when the ensemble flips long/short.
# Runs automatically on GitHub Actions (see workflow file).
# ============================================================

import os, requests
import yfinance as yf
import pandas as pd
import numpy as np

# ---- symbols to scan (yfinance tickers) ----
SYMBOLS = {
    "GOLD (XAU/USD)":  "GC=F",
    "SILVER (XAG/USD)":"SI=F",
    "EUR/USD":         "EURUSD=X",
    "GBP/USD":         "GBPUSD=X",
    "USD/JPY":         "USDJPY=X",
    "AUD/USD":         "AUDUSD=X",
}

INTERVAL  = "15m"
PERIOD    = "5d"
MIN_AGREE = 3

BOT_TOKEN = os.environ["TG_TOKEN"]
CHAT_ID   = os.environ["TG_CHAT"]

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
        timeout=15,
    )

def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)

def ensemble(df):
    c, h, l = df["Close"], df["High"], df["Low"]
    e9, e21, e200 = ema(c, 9), ema(c, 21), ema(c, 200)
    r = rsi(c)
    hh20, ll20 = h.rolling(20).max().shift(), l.rolling(20).min().shift()
    macd = ema(c, 12) - ema(c, 26)
    macds = ema(macd, 9)

    s1 = np.where((e9 > e21) & (c > e200), 1, np.where((e9 < e21) & (c < e200), -1, 0))
    s2 = np.where(r < 30, 1, np.where(r > 70, -1, 0))
    s3 = np.where(c > hh20, 1, np.where(c < ll20, -1, 0))
    s4 = np.where((macd > macds) & (macd > 0), 1, np.where((macd < macds) & (macd < 0), -1, 0))

    vote = s1 + s2 + s3 + s4
    sig = np.where(vote >= MIN_AGREE, 1, np.where(vote <= -MIN_AGREE, -1, 0))
    return pd.Series(sig, index=df.index)

alerts = []

for name, ticker in SYMBOLS.items():
    try:
        df = yf.download(ticker, period=PERIOD, interval=INTERVAL, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        if len(df) < 210:
            continue
        sig = ensemble(df)
        # use last CLOSED candle vs the one before it
        now, prev = sig.iloc[-2], sig.iloc[-3]
        price = df["Close"].iloc[-2]
        if now != 0 and now != prev:
            side = "🟢 LONG" if now == 1 else "🔴 SHORT"
            alerts.append(f"{side} <b>{name}</b> @ {price:.4f}")
    except Exception as e:
        print(f"{name} failed: {e}")

if alerts:
    msg = "⚡ <b>Ensemble signal (3+ strategies agree)</b>\n\n" + "\n".join(alerts)
    msg += "\n\n15m timeframe • data delayed a few min • not financial advice"
    send(msg)
    print("Sent:", alerts)
else:
    print("No new signals this run.")

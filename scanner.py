# ============================================================
# SIGNAL SCANNER v3 — multi-market confluence
#
# What's new vs v2:
#  - ~20 markets: metals, energy, FX majors, indices, mega-cap stocks
#  - TWO timeframes scanned: 15m (faster) and 1h (higher quality),
#    each confirmed against the timeframe above it (1h / daily)
#  - PER-MARKET-CLASS tuning: each asset class has a "must include"
#    strategy family that suits how that market behaves:
#      metals/energy  -> BREAKOUT must be one of the agreeing votes
#                        (commodities move in momentum bursts)
#      FX             -> MOMENTUM must agree (currencies grind/range)
#      indices/stocks -> TREND must agree (equities trend)
#  - Still harsh: 3 of 4 families + must-include + higher-TF agree
#    + volatility floor. Fewer signals per market, more markets.
#  - Every alert: price, ATR stop-loss, ATR target, vote breakdown.
#
# Same secrets (TG_TOKEN, TG_CHAT). Straight swap into scanner.py.
# ============================================================

import os, requests
import yfinance as yf
import pandas as pd
import numpy as np

# name: (ticker, class)  classes: METAL, ENERGY, FX, INDEX, STOCK
SYMBOLS = {
    "GOLD":        ("GC=F",     "METAL"),
    "SILVER":      ("SI=F",     "METAL"),
    "COPPER":      ("HG=F",     "METAL"),
    "PLATINUM":    ("PL=F",     "METAL"),
    "OIL (WTI)":   ("CL=F",     "ENERGY"),
    "NAT GAS":     ("NG=F",     "ENERGY"),
    "EUR/USD":     ("EURUSD=X", "FX"),
    "GBP/USD":     ("GBPUSD=X", "FX"),
    "USD/JPY":     ("USDJPY=X", "FX"),
    "AUD/USD":     ("AUDUSD=X", "FX"),
    "USD/CAD":     ("USDCAD=X", "FX"),
    "NZD/USD":     ("NZDUSD=X", "FX"),
    "S&P 500":     ("ES=F",     "INDEX"),
    "NASDAQ 100":  ("NQ=F",     "INDEX"),
    "FTSE 100":    ("^FTSE",    "INDEX"),
    "APPLE":       ("AAPL",     "STOCK"),
    "MICROSOFT":   ("MSFT",     "STOCK"),
    "NVIDIA":      ("NVDA",     "STOCK"),
    "TESLA":       ("TSLA",     "STOCK"),
    "AMAZON":      ("AMZN",     "STOCK"),
}

# which family MUST be among the agreeing votes, per class
MUST_INCLUDE = {
    "METAL":  "BREAKOUT",
    "ENERGY": "BREAKOUT",
    "FX":     "MOMENTUM",
    "INDEX":  "TREND",
    "STOCK":  "TREND",
}

# timeframes scanned: (interval, period, confirm_interval, confirm_period)
TIMEFRAMES = [
    ("15m", "5d",  "1h", "30d"),
    ("1h",  "60d", "1d", "1y"),
]

MIN_FAMILIES = 3
STOP_ATR     = 1.5
TP_ATR       = 2.5
MIN_ATR_PCT  = 0.0004

BOT_TOKEN = os.environ["TG_TOKEN"]
CHAT_ID   = os.environ["TG_CHAT"]

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
        timeout=15,
    )

def get(ticker, period, interval):
    d = yf.download(ticker, period=period, interval=interval, progress=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return d.dropna()

def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)

def stoch(h, l, c, n=14, d=3):
    lo, hi = l.rolling(n).min(), h.rolling(n).max()
    return (100 * (c - lo) / (hi - lo)).rolling(d).mean()

def atr(h, l, c, n=14):
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def family_votes(df):
    c, h, l = df["Close"], df["High"], df["Low"]
    v = pd.DataFrame(index=df.index)

    e9, e21, e200 = ema(c, 9), ema(c, 21), ema(c, 200)
    macd = ema(c, 12) - ema(c, 26); macds = ema(macd, 9)
    t1 = np.where((e9 > e21) & (c > e200), 1, np.where((e9 < e21) & (c < e200), -1, 0))
    t2 = np.where((macd > macds) & (macd > 0), 1, np.where((macd < macds) & (macd < 0), -1, 0))
    v["TREND"] = np.where((t1 == 1) & (t2 == 1), 1, np.where((t1 == -1) & (t2 == -1), -1, 0))

    r = rsi(c); k = stoch(h, l, c)
    m1 = np.where(r > 55, 1, np.where(r < 45, -1, 0))
    m2 = np.where(k > 60, 1, np.where(k < 40, -1, 0))
    v["MOMENTUM"] = np.where((m1 == 1) & (m2 == 1), 1, np.where((m1 == -1) & (m2 == -1), -1, 0))

    mid = c.rolling(20).mean(); sd = c.rolling(20).std()
    v["VOLATILITY"] = np.where(c > mid + 2 * sd, 1, np.where(c < mid - 2 * sd, -1, 0))

    hh, ll = h.rolling(20).max().shift(), l.rolling(20).min().shift()
    v["BREAKOUT"] = np.where(c > hh, 1, np.where(c < ll, -1, 0))
    return v

def higher_tf_trend(ticker, interval, period):
    try:
        d = get(ticker, period, interval)
        if len(d) < 210:
            return 0
        c = d["Close"]
        e50, e200 = ema(c, 50), ema(c, 200)
        if e50.iloc[-1] > e200.iloc[-1] and c.iloc[-1] > e200.iloc[-1]:
            return 1
        if e50.iloc[-1] < e200.iloc[-1] and c.iloc[-1] < e200.iloc[-1]:
            return -1
    except Exception:
        pass
    return 0

alerts = []

for name, (ticker, klass) in SYMBOLS.items():
    for interval, period, conf_int, conf_per in TIMEFRAMES:
        try:
            df = get(ticker, period, interval)
            if len(df) < 210:
                continue

            votes = family_votes(df)
            score = votes.sum(axis=1)
            sig = pd.Series(
                np.where(score >= MIN_FAMILIES, 1,
                np.where(score <= -MIN_FAMILIES, -1, 0)), index=df.index)

            now, prev = sig.iloc[-2], sig.iloc[-3]
            if now == 0 or now == prev:
                continue

            # class rule: the must-include family has to be voting with the signal
            if votes.iloc[-2][MUST_INCLUDE[klass]] != now:
                print(f"{name} {interval}: {MUST_INCLUDE[klass]} not agreeing, skipped")
                continue

            price = float(df["Close"].iloc[-2])
            a = float(atr(df["High"], df["Low"], df["Close"]).iloc[-2])
            if a < price * MIN_ATR_PCT:
                print(f"{name} {interval}: volatility too low, skipped")
                continue

            if higher_tf_trend(ticker, conf_int, conf_per) != now:
                print(f"{name} {interval}: higher TF disagrees, skipped")
                continue

            stop = price - now * STOP_ATR * a
            tp   = price + now * TP_ATR * a
            side = "🟢 LONG" if now == 1 else "🔴 SHORT"
            row = votes.iloc[-2]
            breakdown = " ".join(
                f"{fam[:4]}{'✅' if row[fam] == now else '⚪'}" for fam in votes.columns)
            alerts.append(
                f"{side} <b>{name}</b> ({interval})\n"
                f"Price: {price:.4f}\n"
                f"Stop: {stop:.4f} | Target: {tp:.4f}\n"
                f"Votes: {breakdown} | higher TF ✅")
        except Exception as e:
            print(f"{name} {interval} failed: {e}")

if alerts:
    msg = "⚡ <b>Confluence signals</b>\n\n" + "\n\n".join(alerts)
    msg += "\n\nATR-based levels • data delayed a few min • not financial advice"
    send(msg)
    print("Sent:", len(alerts), "alert(s)")
else:
    print("No new signals this run.")


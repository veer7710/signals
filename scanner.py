# ============================================================
# SIGNAL SCANNER v5 — bug fixes + 6 upgrades
#
# BUGS FOUND IN v4 (real ones, now fixed):
#  BUG 1 — duplicate alerts: the 3-candle catch-up window would
#    re-alert the SAME flip on consecutive runs (and on weekends,
#    stale data made the same alert repeat every 15 min forever).
#    FIX: a state file (state.json, committed back to the repo)
#    remembers what was last alerted per market+timeframe. Each
#    flip alerts exactly once. This is how real bots (freqtrade)
#    do it — they keep a database; ours is a tiny json.
#  BUG 2 — no stale-data guard: when markets are closed the last
#    candle is hours/days old, but the code treated it as live.
#    FIX: skip any market whose last candle is older than ~3x the
#    timeframe. Weekend silence is now enforced by design.
#  BUG 3 — Telegram messages could exceed the 4096-char limit
#    (20 markets x 2 TFs on a busy run) and fail silently.
#    FIX: alerts are chunked into multiple messages and delivery
#    is checked/logged.
#
# UPGRADES (the "5 more ways", implemented):
#  1. ADX REGIME FILTER — ADX(14) measures whether a market is
#     trending at all. Signals in dead chop (ADX < 15) are vetoed;
#     ADX > 25 is flagged "strong trend" in the alert. This is the
#     single most-cited false-signal reducer in algo-trading
#     communities.
#  2. VOLUME CONFIRMATION (stocks/indices) — a breakout on weak
#     volume is suspect. If signal-candle volume < its 20-bar
#     average, the setup is downgraded to B-tier.
#  3. COOLDOWN PROTECTION (freqtrade "protections" pattern) — after
#     alerting a market+TF, re-alerts are suppressed for 2h (15m)
#     / 8h (1h) even if the signal re-flips, killing chop spam.
#  4. POSITION-SIZE LINE — every alert shows the 1%-risk sizing
#     formula with the actual stop distance filled in.
#  5. A/B TIERS + HTF + hold-time guidance kept from v4, now with
#     ADX and volume feeding the tier, so "A-setup" means more.
#  6. Delivery hardening: state only updates if Telegram accepted
#     the message, so a failed send retries next run.
#
# REQUIRES the updated workflow yml (state commit step + write
# permission). Swap BOTH files.
# ============================================================

import os, json, requests
from datetime import datetime, timezone, timedelta
import yfinance as yf
import pandas as pd
import numpy as np

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

MUST_INCLUDE = {
    "METAL": "BREAKOUT", "ENERGY": "BREAKOUT",
    "FX": "MOMENTUM", "INDEX": "TREND", "STOCK": "TREND",
}

# (interval, period, confirm_interval, confirm_period, hold text,
#  max candle age minutes, cooldown minutes)
TIMEFRAMES = [
    ("15m", "5d",  "1h", "30d", "short-term — review within ~4h, close same day", 45,  120),
    ("1h",  "60d", "1d", "1y",  "swing — review within 1-2 days",                 180, 480),
]

MIN_SCORE   = 2
STOP_ATR    = 1.5
TP_ATR      = 2.5
MIN_ATR_PCT = 0.0004
ADX_DEAD    = 15     # below this = chop, veto
ADX_STRONG  = 25     # above this = strong trend, flag it

STATE_FILE = "state.json"
BOT_TOKEN = os.environ["TG_TOKEN"]
CHAT_ID   = os.environ["TG_CHAT"]

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=1)

def send(msg):
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
        timeout=15,
    )
    if not r.ok:
        print("Telegram send failed:", r.status_code, r.text[:200])
    return r.ok

def send_chunked(alerts, footer):
    ok_all = True
    chunk, size = [], 0
    for a in alerts:
        if size + len(a) > 3300 and chunk:
            ok_all &= send("⚡ <b>Signals</b>\n\n" + "\n\n".join(chunk) + footer)
            chunk, size = [], 0
        chunk.append(a); size += len(a)
    if chunk:
        ok_all &= send("⚡ <b>Signals</b>\n\n" + "\n\n".join(chunk) + footer)
    return ok_all

def get(ticker, period, interval):
    d = yf.download(ticker, period=period, interval=interval, progress=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return d.dropna(subset=["Close"])

def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)

def stoch(h, l, c, n=14, d=3):
    lo, hi = l.rolling(n).min(), h.rolling(n).max()
    rng = (hi - lo).replace(0, np.nan)
    return (100 * (c - lo) / rng).rolling(d).mean()

def atr_series(h, l, c, n=14):
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def adx(h, l, c, n=14):
    up, dn = h.diff(), -l.diff()
    plus_dm  = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr_ = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi = 100 * pd.Series(plus_dm, index=h.index).ewm(alpha=1/n, adjust=False).mean() / atr_
    mdi = 100 * pd.Series(minus_dm, index=h.index).ewm(alpha=1/n, adjust=False).mean() / atr_
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean()

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
    m2 = np.nan_to_num(m2)
    v["MOMENTUM"] = np.where(((m1 == 1) & (m2 >= 0)) | ((m2 == 1) & (m1 >= 0)), 1,
                    np.where(((m1 == -1) & (m2 <= 0)) | ((m2 == -1) & (m1 <= 0)), -1, 0))

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

state = load_state()
now_utc = datetime.now(timezone.utc)
alerts, state_changes = [], {}

for name, (ticker, klass) in SYMBOLS.items():
    for interval, period, conf_int, conf_per, hold, max_age_min, cooldown_min in TIMEFRAMES:
        key = f"{name}|{interval}"
        try:
            df = get(ticker, period, interval)
            if len(df) < 210:
                continue

            # BUG 2 fix: stale-data guard (closed markets, weekends)
            last_ts = df.index[-1]
            if last_ts.tzinfo is None:
                last_ts = last_ts.tz_localize("UTC")
            age_min = (now_utc - last_ts.tz_convert(timezone.utc)).total_seconds() / 60
            if age_min > max_age_min:
                continue

            votes = family_votes(df)
            score = votes.sum(axis=1)
            sig = pd.Series(
                np.where(score >= MIN_SCORE, 1,
                np.where(score <= -MIN_SCORE, -1, 0)), index=df.index)

            idx = -2  # last CLOSED candle
            now_sig = int(sig.iloc[idx])

            prev = state.get(key, {"sig": 0, "t": "2000-01-01T00:00:00+00:00"})
            # signal gone flat -> remember it so the next flip alerts
            if now_sig == 0:
                if prev["sig"] != 0:
                    state_changes[key] = {"sig": 0, "t": prev["t"]}
                continue
            # BUG 1 fix: alert only when direction differs from last alerted
            if now_sig == prev["sig"]:
                continue
            # UPGRADE 3: cooldown after any alert on this market+TF
            last_t = datetime.fromisoformat(prev["t"])
            if now_utc - last_t < timedelta(minutes=cooldown_min):
                print(f"{key}: in cooldown, skipped")
                continue

            if votes.iloc[idx][MUST_INCLUDE[klass]] != now_sig:
                continue

            c, h, l = df["Close"], df["High"], df["Low"]
            price = float(c.iloc[idx])
            a = float(atr_series(h, l, c).iloc[idx])
            if not np.isfinite(a) or a < price * MIN_ATR_PCT:
                continue

            # UPGRADE 1: ADX regime filter
            adx_now = float(adx(h, l, c).iloc[idx])
            if np.isfinite(adx_now) and adx_now < ADX_DEAD:
                print(f"{key}: ADX {adx_now:.0f} = chop, skipped")
                continue

            h1 = higher_tf_trend(ticker, conf_int, conf_per)
            if h1 == -now_sig:
                print(f"{key}: higher TF opposes, skipped")
                continue

            # UPGRADE 2: volume confirmation for stocks/indices
            vol_ok = True
            if klass in ("STOCK", "INDEX") and "Volume" in df.columns:
                v20 = df["Volume"].rolling(20).mean().iloc[idx]
                if np.isfinite(v20) and v20 > 0:
                    vol_ok = df["Volume"].iloc[idx] >= v20

            sc = int(abs(score.iloc[idx]))
            is_a = sc >= 3 and h1 == now_sig and vol_ok
            tier = "🅰️ A-setup" if is_a else "🅱️ B-setup"
            notes = []
            notes.append("higher TF ✅" if h1 == now_sig else "higher TF neutral ⚠️")
            if np.isfinite(adx_now):
                notes.append(f"ADX {adx_now:.0f}" + (" 🔥strong trend" if adx_now >= ADX_STRONG else ""))
            if not vol_ok:
                notes.append("volume weak ⚠️")

            stop = price - now_sig * STOP_ATR * a
            tp   = price + now_sig * TP_ATR * a
            be   = price + now_sig * a
            risk_dist = abs(price - stop)
            side = "🟢 LONG" if now_sig == 1 else "🔴 SHORT"
            row = votes.iloc[idx]
            breakdown = " ".join(
                f"{fam[:4]}{'✅' if row[fam] == now_sig else '⚪'}" for fam in votes.columns)

            alerts.append(
                f"{side} <b>{name}</b> ({interval}) — {tier}\n"
                f"Price: {price:.4f}\n"
                f"Stop: {stop:.4f} | Target: {tp:.4f}\n"
                f"At {be:.4f}: move stop to entry (risk-free)\n"
                f"Size for 1% risk: (1% of account) ÷ {risk_dist:.4f}\n"
                f"Hold: {hold}\n"
                f"Votes {sc}/4: {breakdown} | {' | '.join(notes)}")

            state_changes[key] = {"sig": now_sig, "t": now_utc.isoformat()}
        except Exception as e:
            print(f"{key} failed: {e}")

if alerts:
    footer = "\n\nATR levels • log A and B setups separately • not financial advice"
    # UPGRADE 6: only lock in state if Telegram actually accepted
    if send_chunked(alerts, footer):
        state.update(state_changes)
        save_state(state)
        print("Sent:", len(alerts), "alert(s)")
    else:
        print("Send failed — state NOT updated, will retry next run")
else:
    # still persist flat-resets so re-flips alert properly
    if state_changes:
        state.update(state_changes)
        save_state(state)
    print("No new signals this run.")

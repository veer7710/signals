# ============================================================
# SIGNAL SCANNER v7 — the self-grading edition
#
# Audit findings fixed (v6):
#  - FIX 1: stale-flip leak — a flip vetoed by filters could alert
#    hours later once filters eased, long after the move. Now a
#    flip must be fresh (within the last 3 closed candles).
#  - FIX 2: rate-limit fragility — 19 markets x multiple downloads
#    could get throttled by the data source and fail silently.
#    Now: small delay between downloads + one automatic retry.
#  - FIX 3: silence was ambiguous — you couldn't tell "no signals"
#    from "bot dead". Now a daily heartbeat (~7am UK) confirms
#    it's alive and reports the week so far.
#
# NEW — the big one — AUTOMATIC PERFORMANCE TRACKING:
#  * Every alert is saved to log.json in the repo.
#  * Every run, open signals are checked against price: did they
#    hit target, hit stop, or expire? (conservative rule: if one
#    candle touches both, it counts as a LOSS.)
#  * The moment a signal resolves you get a message:
#      "✅ Gold (15m) [B] hit target +17.9"  or
#      "❌ US500 (15m) [B] stopped −16.0"
#  * Sunday evening: weekly recap — win rate and net points
#    per tier (A vs B), so the bot GRADES ITSELF and you can see
#    whether A-setups actually beat B-setups with real numbers.
#  * Alerts now carry a session tag (Asia/London/NY) so the log
#    reveals which trading hours produce the good signals.
#
# Requires updated yml (commits log.json too). Swap BOTH files.
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

MUST_INCLUDE = {
    "METAL": "BREAKOUT", "ENERGY": "BREAKOUT",
    "FX": "MOMENTUM", "INDEX": "TREND", "STOCK": "TREND",
}

# (interval, period, confirm_int, confirm_period, hold text,
#  max candle age min, cooldown min, expiry hours)
TIMEFRAMES = [
    ("15m", "5d",  "1h", "30d", "close same day", 45,  120, 24),
    ("1h",  "60d", "1d", "1y",  "swing 1-2 days", 180, 480, 120),
]

MIN_SCORE   = 2
STOP_ATR    = 1.5
TP_ATR      = 2.5
MIN_ATR_PCT = 0.0004
ADX_DEAD    = 15
FRESH_FLIP  = 3        # flip must be within last N closed candles

STATE_FILE, LOG_FILE = "state.json", "log.json"
BOT_TOKEN = os.environ["TG_TOKEN"]
CHAT_ID   = os.environ["TG_CHAT"]

def jload(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default

def jsave(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)

def send(msg):
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
        timeout=15)
    if not r.ok:
        print("Telegram send failed:", r.status_code, r.text[:200])
    return r.ok

def send_chunked(parts):
    ok_all, chunk, size = True, [], 0
    for a in parts:
        if size + len(a) > 3300 and chunk:
            ok_all &= send("\n\n".join(chunk)); chunk, size = [], 0
        chunk.append(a); size += len(a)
    if chunk:
        ok_all &= send("\n\n".join(chunk))
    return ok_all

_last_dl = [0.0]
def get(ticker, period, interval):
    # FIX 2: pace requests + retry once
    wait = 0.4 - (time.time() - _last_dl[0])
    if wait > 0:
        time.sleep(wait)
    for attempt in (1, 2):
        d = yf.download(ticker, period=period, interval=interval, progress=False)
        _last_dl[0] = time.time()
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        d = d.dropna(subset=["Close"]) if len(d) else d
        if len(d):
            return d
        time.sleep(2)
    return d

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
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    a = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi = 100 * pd.Series(pdm, index=h.index).ewm(alpha=1/n, adjust=False).mean() / a
    mdi = 100 * pd.Series(mdm, index=h.index).ewm(alpha=1/n, adjust=False).mean() / a
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
    m2 = np.nan_to_num(np.where(k > 60, 1, np.where(k < 40, -1, 0)))
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

def fmt(x, ref):
    dp = 4 if ref < 50 else 2 if ref < 10000 else 1
    return f"{x:.{dp}f}"

def session(dt):
    hlon = (dt.hour + 0) % 24  # UTC ~ UK winter; close enough for tagging
    if 7 <= hlon < 13:  return "London"
    if 13 <= hlon < 21: return "NY"
    return "Asia"

# ---------------- resolve open logged signals ----------------
def resolve_open(log):
    msgs, changed = [], False
    open_sigs = [s for s in log if s["status"] == "open"]
    # group to avoid duplicate downloads
    groups = {}
    for s in open_sigs:
        groups.setdefault((s["ticker"], s["tf"]), []).append(s)
    for (ticker, tf), sigs in groups.items():
        period = "5d" if tf == "15m" else "30d"
        try:
            d = get(ticker, period, tf)
        except Exception:
            continue
        if not len(d):
            continue
        if d.index.tz is None:
            d.index = d.index.tz_localize("UTC")
        for s in sigs:
            t0 = datetime.fromisoformat(s["time"])
            df = d[d.index > t0]
            if not len(df):
                continue
            res = None
            for _, row in df.iterrows():
                lo, hi = float(row["Low"]), float(row["High"])
                if s["side"] == 1:
                    hit_stop, hit_tp = lo <= s["stop"], hi >= s["tp"]
                else:
                    hit_stop, hit_tp = hi >= s["stop"], lo <= s["tp"]
                if hit_stop:            # conservative: stop wins ties
                    res = ("loss", -abs(s["entry"] - s["stop"])); break
                if hit_tp:
                    res = ("win", abs(s["tp"] - s["entry"])); break
            if res is None:
                age_h = (datetime.now(timezone.utc) - t0).total_seconds() / 3600
                if age_h >= s["expiry_h"]:
                    px = float(df["Close"].iloc[-1])
                    pts = (px - s["entry"]) * s["side"]
                    res = ("expired", pts)
            if res:
                s["status"], s["points"] = res[0], round(res[1], 4)
                changed = True
                icon = "✅" if res[0] == "win" else "❌" if res[0] == "loss" else "⏰"
                word = {"win": "hit target", "loss": "stopped", "expired": "expired"}[res[0]]
                sign = "+" if res[1] >= 0 else "−"
                msgs.append(f"{icon} <b>{s['name']}</b> ({s['tf']}) [{s['tier']}] {word} "
                            f"{sign}{fmt(abs(res[1]), s['entry'])}")
    return msgs, changed

def weekly_recap(log):
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    done = [s for s in log
            if s["status"] in ("win", "loss", "expired")
            and datetime.fromisoformat(s["time"]) > cutoff]
    if not done:
        return "📊 <b>Weekly recap</b>\nNo resolved signals this week."
    lines = ["📊 <b>Weekly recap</b> (last 7 days)"]
    for tier in ("A", "B"):
        ts = [s for s in done if s["tier"] == tier]
        if not ts:
            continue
        wins = sum(1 for s in ts if s["status"] == "win")
        net = sum(s.get("points", 0) / s["entry"] * 100 for s in ts)
        lines.append(f"[{tier}] {len(ts)} signals · {wins} wins "
                     f"({100*wins/len(ts):.0f}%) · net {net:+.2f}% (sum of moves)")
    lines.append(f"Total resolved: {len(done)}")
    return "\n".join(lines)

# ============================ main ============================
state = jload(STATE_FILE, {})
log   = jload(LOG_FILE, [])
now_utc = datetime.now(timezone.utc)
alerts, state_changes = [], {}

# 1) resolve outcomes first
res_msgs, log_changed = resolve_open(log)

# 2) scan for new signals
for name, (ticker, klass) in SYMBOLS.items():
    for interval, period, conf_int, conf_per, hold, max_age, cool, exp_h in TIMEFRAMES:
        key = f"{name}|{interval}"
        try:
            df = get(ticker, period, interval)
            if len(df) < 210:
                continue
            last_ts = df.index[-1]
            if last_ts.tzinfo is None:
                last_ts = last_ts.tz_localize("UTC")
            if (now_utc - last_ts.tz_convert(timezone.utc)).total_seconds() / 60 > max_age:
                continue

            votes = family_votes(df)
            score = votes.sum(axis=1)
            sig = pd.Series(np.where(score >= MIN_SCORE, 1,
                            np.where(score <= -MIN_SCORE, -1, 0)), index=df.index)
            idx = -2
            now_sig = int(sig.iloc[idx])

            prev = state.get(key, {"sig": 0, "t": "2000-01-01T00:00:00+00:00"})
            if now_sig == 0:
                if prev["sig"] != 0:
                    state_changes[key] = {"sig": 0, "t": prev["t"]}
                continue
            if now_sig == prev["sig"]:
                continue
            if now_utc - datetime.fromisoformat(prev["t"]) < timedelta(minutes=cool):
                continue
            # FIX 1: flip must be fresh
            if not (sig.iloc[idx-FRESH_FLIP:idx] != now_sig).any():
                continue
            if votes.iloc[idx][MUST_INCLUDE[klass]] != now_sig:
                continue

            c, h, l = df["Close"], df["High"], df["Low"]
            price = float(c.iloc[idx])
            a = float(atr_series(h, l, c).iloc[idx])
            if not np.isfinite(a) or a < price * MIN_ATR_PCT:
                continue
            adx_now = float(adx(h, l, c).iloc[idx])
            if np.isfinite(adx_now) and adx_now < ADX_DEAD:
                continue
            h1 = higher_tf_trend(ticker, conf_int, conf_per)
            if h1 == -now_sig:
                continue
            vol_ok = True
            if klass in ("STOCK", "INDEX") and "Volume" in df.columns:
                v20 = df["Volume"].rolling(20).mean().iloc[idx]
                if np.isfinite(v20) and v20 > 0:
                    vol_ok = df["Volume"].iloc[idx] >= v20

            sc = int(abs(score.iloc[idx]))
            tier = "A" if (sc >= 3 and h1 == now_sig and vol_ok) else "B"
            stop_d, tp_d = STOP_ATR * a, TP_ATR * a
            stop, tp = price - now_sig * stop_d, price + now_sig * tp_d
            side_txt = "🟢 LONG" if now_sig == 1 else "🔴 SHORT"

            alerts.append(
                f"{side_txt} <b>{name}</b> ({interval}) [{tier}] · {session(now_utc)}\n"
                f"Entry ~{fmt(price, price)}\n"
                f"Stop {fmt(stop, price)} (−{fmt(stop_d, price)}) | "
                f"Target {fmt(tp, price)} (+{fmt(tp_d, price)})\n"
                f"{hold}")

            log.append({"name": name, "ticker": ticker, "tf": interval,
                        "tier": tier, "side": now_sig, "entry": price,
                        "stop": stop, "tp": tp, "expiry_h": exp_h,
                        "time": now_utc.isoformat(), "session": session(now_utc),
                        "status": "open"})
            log_changed = True
            state_changes[key] = {"sig": now_sig, "t": now_utc.isoformat()}
        except Exception as e:
            print(f"{key} failed: {e}")

# 3) heartbeat + weekly recap
out = res_msgs + alerts
today = now_utc.strftime("%Y-%m-%d")
if state.get("hb") != today and now_utc.hour == 7:
    open_n = sum(1 for s in log if s["status"] == "open")
    wk = [s for s in log if datetime.fromisoformat(s["time"]) >
          now_utc - timedelta(days=7)]
    out.append(f"💓 Bot alive · {open_n} open signals · {len(wk)} sent this week")
    state_changes["hb"] = today
if state.get("recap") != today and now_utc.weekday() == 6 and now_utc.hour == 20:
    out.append(weekly_recap(log))
    state_changes["recap"] = today

# 4) send + persist
if out:
    if send_chunked(out):
        state.update(state_changes)
        jsave(STATE_FILE, state)
        if log_changed:
            jsave(LOG_FILE, log)
        print("Sent", len(out), "message part(s)")
    else:
        print("Send failed — nothing persisted, will retry")
else:
    if state_changes:
        state.update(state_changes); jsave(STATE_FILE, state)
    if log_changed:
        jsave(LOG_FILE, log)
    print("No new signals this run.")

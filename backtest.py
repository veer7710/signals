# ============================================================
# backtest.py v3 — RESEARCH BACKTESTER (not a trading bot)
#
# Question it answers: "Would these engines have been profitable
# over the last 60 days AFTER realistic costs?"
#
# DESIGN (per spec):
#  - Per-market engines, no one-size-fits-all:
#      GOLD/SILVER  trend-continuation pullback (HTF trend + slope,
#                   momentum resumption, no expansion-candle entries)
#      INDICES      NY Opening-Range Breakout (volume + HTF + ADX
#                   rising w/ DI confirmation)
#      FX MAJORS    market structure: liquidity sweep of a swing low/
#                   high -> Break of Structure -> momentum entry.
#                   London open + NY overlap only, lunch skipped.
#      JPY CROSSES  Tokyo-range breakout, London continuation,
#                   HTF alignment
#      OIL          Donchian breakout, wide stops, HTF confirm
#  - Multi-timeframe: 1H trend (EMA50/200 + slope) gates every
#    entry. HTF values are lagged one full 1H bar (no look-ahead).
#  - Swing points confirmed 2 bars later before they can be used.
#  - Exits: 50% partial at +1R, stop -> breakeven, ATR trail on the
#    remainder. Per-market stop sizes.
#  - Volatility filter: ATR must sit within [0.4x, 2.5x] its 50-bar
#    median; expansion candles (>3x ATR) skipped.
#  - ADX: must be RISING (vs 3 bars ago) with DI agreement.
#  - RSI: confirmation only, never the trigger.
#  - Risk: trades are simulated in R-multiples, then replayed in
#    CLOSE-TIME order compounding 0.75% of equity per trade. This
#    keeps portfolio equity/maxDD chronologically honest.
#  - Costs: spread + conservative slippage (50% of spread extra),
#    charged in R terms on every trade. Ties (SL+TP same candle)
#    count as the STOP. Entries fill next candle's open.
#  - Per-market protections: max trades/day, 24h cooldown after 3
#    consecutive losses.
#  - Walk-forward-lite: results reported for first/second 30 days
#    separately, so one lucky fortnight can't hide.
#
# OMITTED, HONESTLY:
#  - News filter: no reliable free economic-calendar source is
#    available inside GitHub Actions without an API key. Rather
#    than fake one, it is omitted; the expansion-candle and ATR
#    band filters catch part of the same risk.
#  - Portfolio-level daily risk cap across markets: engines are
#    simulated per-market; a truly interleaved portfolio cap is
#    not modelled. Per-market caps are.
#
# Data: Yahoo Finance (swap get_data() to change provider).
# Output: one Telegram report. Runs headless on GitHub Actions.
# ============================================================

import os, time, requests
from datetime import timedelta
import yfinance as yf
import pandas as pd
import numpy as np

# ---------------- configuration ----------------
START_BAL   = 100.0
RISK_PCT    = 0.0075          # fraction of equity risked per trade
PARTIAL_AT  = 1.0             # take 50% at +1R, stop -> breakeven
SPIKE_ATR   = 3.0
ATR_BAND    = (0.4, 2.5)      # ATR vs its 50-bar median
CONSEC_LOSS_PAUSE = (3, 24)   # 3 losses in a row -> 24h off (per market)

#  name: (ticker, engine, spread_pct)
MARKETS = {
    "GOLD":    ("GC=F",     "GOLD",  0.0004),
    "SILVER":  ("SI=F",     "GOLD",  0.0005),
    "OIL":     ("CL=F",     "OIL",   0.0006),
    "US500":   ("ES=F",     "ORB",   0.0003),
    "US100":   ("NQ=F",     "ORB",   0.0003),
    "EUR/USD": ("EURUSD=X", "FX",    0.0002),
    "GBP/USD": ("GBPUSD=X", "FX",    0.00025),
    "AUD/USD": ("AUDUSD=X", "FX",    0.00025),
    "NZD/USD": ("NZDUSD=X", "FX",    0.0003),
    "USD/CAD": ("USDCAD=X", "FX",    0.00025),
    "USD/JPY": ("USDJPY=X", "JPY",   0.0002),
    "GBP/JPY": ("GBPJPY=X", "JPY",   0.0003),
    "EUR/JPY": ("EURJPY=X", "JPY",   0.0003),
}

# per-engine parameters: stop_atr, trail_atr, max/day, sessions (UTC)
ENGINE = {
    "GOLD": dict(stop=2.0, trail=2.0, per_day=2, sess=[(7, 21)]),
    "OIL":  dict(stop=2.5, trail=2.5, per_day=1, sess=[(7, 21)]),
    "ORB":  dict(stop=1.8, trail=1.5, per_day=1, sess=[(14, 19)]),
    "FX":   dict(stop=1.0, trail=1.2, per_day=2, sess=[(7, 10), (12, 16)]),
    "JPY":  dict(stop=1.2, trail=1.5, per_day=1, sess=[(7, 12)]),
}

BOT  = os.environ["TG_TOKEN"]
CHAT = os.environ["TG_CHAT"]

def send(msg):
    requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",
                  data={"chat_id": CHAT, "text": msg, "parse_mode": "HTML"},
                  timeout=20)

# ---------------- data ----------------
_last_call = [0.0]
def get_data(ticker):
    """Fetch 60d of 15m bars, UTC index. Swap this to change provider."""
    wait = 0.5 - (time.time() - _last_call[0])
    if wait > 0: time.sleep(wait)
    for _ in range(2):
        d = yf.download(ticker, period="60d", interval="5m", progress=False)
        _last_call[0] = time.time()
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        if len(d):
            d = d.dropna(subset=["Close"])
            d.index = (d.index.tz_localize("UTC") if d.index.tz is None
                       else d.index.tz_convert("UTC"))
            return d
        time.sleep(2)
    return pd.DataFrame()

# ---------------- indicators ----------------
def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)

def atr(h, l, c, n=14):
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def adx_di(h, l, c, n=14):
    up, dn = h.diff(), -l.diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=h.index)
    mdm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=h.index)
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    a = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi = 100 * pdm.ewm(alpha=1/n, adjust=False).mean() / a
    mdi = 100 * mdm.ewm(alpha=1/n, adjust=False).mean() / a
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean(), pdi, mdi

def htf_trend(d15):
    """1H trend from resampled data. Values lagged one full 1H bar,
    so a 15m bar only ever sees the last COMPLETED hour. Returns a
    Series of +1 / -1 / 0 aligned to the 15m index."""
    h1 = d15.resample("1h").agg({"High": "max", "Low": "min",
                                 "Close": "last"}).dropna()
    if len(h1) < 210:
        return pd.Series(0, index=d15.index)
    c = h1["Close"]
    e50, e200 = ema(c, 50), ema(c, 200)
    slope_up = e50 > e50.shift(5)
    up = (e50 > e200) & (c > e200) & slope_up
    dn = (e50 < e200) & (c < e200) & (~slope_up | (e50 < e50.shift(5)))
    t = pd.Series(np.where(up, 1, np.where(dn, -1, 0)), index=h1.index)
    t = t.shift(1)                                  # completed bars only
    return t.reindex(d15.index, method="ffill").fillna(0)

def swings(h, l, k=2):
    """Confirmed swing highs/lows. A swing at bar i is only usable
    from bar i+k onward (needs k bars each side)."""
    sh = pd.Series(np.nan, index=h.index)
    sl_ = pd.Series(np.nan, index=l.index)
    hv, lv = h.values, l.values
    for i in range(k, len(h) - k):
        if hv[i] == max(hv[i-k:i+k+1]): sh.iloc[i] = hv[i]
        if lv[i] == min(lv[i-k:i+k+1]): sl_.iloc[i] = lv[i]
    return sh, sl_

def in_session(hour, sess):
    return any(a <= hour < b for a, b in sess)

# ---------------- trade container ----------------
def simulate_trade(d, i_entry, direction, stop_dist, trail_mult, atr_at,
                   cost_pct, max_bars=12):   # 12 x 5m = 1 hour max hold
    """Walk forward from entry. Partial 50% at +1R -> stop to BE ->
    ATR trail on remainder. Ties resolve as the stop. Returns
    (net_R, bars_held) or None if data runs out immediately."""
    o, h, l, c = d["Open"], d["High"], d["Low"], d["Close"]
    if i_entry >= len(d): return None
    e = float(o.iloc[i_entry])
    sl = e - direction * stop_dist
    tp1 = e + direction * PARTIAL_AT * stop_dist       # partial level
    half_banked = False
    r_total = 0.0
    cost_R = (e * cost_pct) / stop_dist                # round-trip cost in R

    for j in range(i_entry, min(i_entry + max_bars, len(d))):
        lo, hi, cl = float(l.iloc[j]), float(h.iloc[j]), float(c.iloc[j])
        hit_sl = lo <= sl if direction == 1 else hi >= sl
        hit_p1 = (hi >= tp1 if direction == 1 else lo <= tp1)

        if hit_sl:                                     # stop first (ties=stop)
            r_exit = (sl - e) * direction / stop_dist
            r_total += r_exit * (0.5 if half_banked else 1.0)
            return r_total - cost_R, j - i_entry + 1

        if not half_banked and hit_p1:
            r_total += 0.5 * PARTIAL_AT                # bank half at +1R
            half_banked = True
            sl = e                                     # breakeven

        if half_banked:                                # trail the rest
            new_sl = (max(sl, cl - trail_mult * atr_at) if direction == 1
                      else min(sl, cl + trail_mult * atr_at))
            sl = new_sl

    # time exit at last close
    cl = float(c.iloc[min(i_entry + max_bars, len(d)) - 1])
    r_exit = (cl - e) * direction / stop_dist
    r_total += r_exit * (0.5 if half_banked else 1.0)
    return r_total - cost_R, max_bars

# ---------------- engines (each returns candidate entries) ----------------
def run_market(name, ticker, eng_key, spread):
    d = get_data(ticker)
    if len(d) < 400: return []
    p = ENGINE[eng_key]
    o, h, l, c = d["Open"], d["High"], d["Low"], d["Close"]
    A = atr(h, l, c)
    Amed = A.rolling(50).median()
    X, PDI, MDI = adx_di(h, l, c)
    R = rsi(c)
    T = htf_trend(d)
    e20 = ema(c, 20)
    vol = d["Volume"] if "Volume" in d and d["Volume"].sum() > 0 else None
    vavg = vol.rolling(20).mean() if vol is not None else None
    sh, sl_ = swings(h, l)
    don_hi = h.rolling(48).max().shift()
    don_lo = l.rolling(48).min().shift()

    trades = []
    day = None; n_today = 0
    consec = 0; pause_until = d.index[0]

    for i in range(210, len(d) - 2):
        ts = d.index[i]
        if ts.date() != day: day = ts.date(); n_today = 0
        if n_today >= p["per_day"]: continue
        if ts < pause_until: continue
        if not in_session(ts.hour, p["sess"]): continue

        a_ = float(A.iloc[i]); am = float(Amed.iloc[i])
        if not np.isfinite(a_) or a_ <= 0 or not np.isfinite(am) or am <= 0:
            continue
        if not (ATR_BAND[0] * am <= a_ <= ATR_BAND[1] * am): continue
        c1, o1 = float(c.iloc[i]), float(o.iloc[i])
        h1, l1 = float(h.iloc[i]), float(l.iloc[i])
        if h1 - l1 > SPIKE_ATR * a_: continue          # expansion candle
        t_ = int(T.iloc[i])
        if t_ == 0: continue
        adx_ok = (np.isfinite(X.iloc[i]) and X.iloc[i] > X.iloc[i-3] and
                  ((t_ == 1 and PDI.iloc[i] > MDI.iloc[i]) or
                   (t_ == -1 and MDI.iloc[i] > PDI.iloc[i])))
        body = abs(c1 - o1)
        sig = 0

        if eng_key == "GOLD":
            # pullback to EMA20 then momentum resumption with trend
            pulled = (l1 <= float(e20.iloc[i]) if t_ == 1
                      else h1 >= float(e20.iloc[i]))
            resumed = (c1 > float(h.iloc[i-1]) if t_ == 1
                       else c1 < float(l.iloc[i-1]))
            rsi_ok = (R.iloc[i] > 50) if t_ == 1 else (R.iloc[i] < 50)
            if pulled and resumed and rsi_ok and adx_ok and body < 1.8 * a_:
                sig = t_

        elif eng_key == "OIL":
            if adx_ok:
                if t_ == 1 and c1 > float(don_hi.iloc[i]) and c1 > o1: sig = 1
                elif t_ == -1 and c1 < float(don_lo.iloc[i]) and c1 < o1: sig = -1

        elif eng_key == "ORB":
            # opening range = 13:30-14:00 UTC (first two NY 15m bars)
            day_bars = d[(d.index.date == ts.date())]
            orb = day_bars[(day_bars.index.hour == 13) &
                           (day_bars.index.minute >= 30)]
            if len(orb) < 2: continue
            orb_h = float(orb["High"].max()); orb_l = float(orb["Low"].min())
            vol_ok = True
            if vavg is not None:
                va = float(vavg.iloc[i])
                vol_ok = np.isfinite(va) and va > 0 and float(vol.iloc[i]) >= 1.2 * va
            if adx_ok and vol_ok:
                if t_ == 1 and c1 > orb_h and c1 > o1: sig = 1
                elif t_ == -1 and c1 < orb_l and c1 < o1: sig = -1

        elif eng_key == "FX":
            # liquidity sweep of last confirmed swing, then BOS
            look = 40
            conf_sh = sh.iloc[max(0, i-look):i-1].dropna()
            conf_sl = sl_.iloc[max(0, i-look):i-1].dropna()
            if t_ == 1 and len(conf_sl) and len(conf_sh):
                swept = l1 < float(conf_sl.iloc[-1])           # sweep the low
                bos   = c1 > float(conf_sh.iloc[-1])           # break structure
                if swept and bos and c1 > o1 and body >= 0.4 * a_ and R.iloc[i] > 50:
                    sig = 1
            elif t_ == -1 and len(conf_sl) and len(conf_sh):
                swept = h1 > float(conf_sh.iloc[-1])
                bos   = c1 < float(conf_sl.iloc[-1])
                if swept and bos and c1 < o1 and body >= 0.4 * a_ and R.iloc[i] < 50:
                    sig = -1

        elif eng_key == "JPY":
            # Tokyo range (00-07 UTC) breakout during London
            day_bars = d[(d.index.date == ts.date()) & (d.index.hour < 7)]
            if len(day_bars) < 8: continue
            tk_h = float(day_bars["High"].max()); tk_l = float(day_bars["Low"].min())
            if adx_ok and body >= 0.4 * a_:
                if t_ == 1 and c1 > tk_h and c1 > o1: sig = 1
                elif t_ == -1 and c1 < tk_l and c1 < o1: sig = -1

        if sig == 0: continue

        stop_dist = p["stop"] * a_
        res = simulate_trade(d, i + 1, sig, stop_dist, p["trail"], a_,
                             spread * 1.5)             # spread + 50% slippage
        if res is None: continue
        net_R, bars = res
        n_today += 1
        consec = consec + 1 if net_R < 0 else 0
        if consec >= CONSEC_LOSS_PAUSE[0]:
            pause_until = ts + timedelta(hours=CONSEC_LOSS_PAUSE[1])
            consec = 0
        trades.append(dict(market=name, open_t=d.index[i+1],
                           close_t=d.index[min(i+1+bars, len(d)-1)],
                           R=net_R, bars=bars))
    return trades

# ---------------- portfolio replay & statistics ----------------
def replay(all_trades):
    """Compound trades in close-time order at RISK_PCT of equity."""
    eq = START_BAL
    curve = [(None, eq)]
    for t in sorted(all_trades, key=lambda x: x["close_t"]):
        pnl = eq * RISK_PCT * t["R"]
        eq += pnl
        t["pnl"] = pnl
        curve.append((t["close_t"], eq))
    return eq, curve

def stats(trades, curve, final_eq):
    if not trades:
        return "No trades taken in 60 days."
    rs   = [t["R"] for t in trades]
    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]; losses = [p for p in pnls if p <= 0]
    gp, gl = sum(wins), abs(sum(losses))
    pf  = gp / gl if gl > 0 else float("inf")
    exp = np.mean(rs)
    # max drawdown from equity curve
    peak, mdd = -1e9, 0.0
    for _, e in curve:
        peak = max(peak, e); mdd = max(mdd, (peak - e) / peak)
    # streaks
    ws = ls = cw = cl = 0
    for p in pnls:
        if p > 0: cw += 1; cl = 0
        else: cl += 1; cw = 0
        ws, ls = max(ws, cw), max(ls, cl)
    r_arr = np.array(rs)
    sd = r_arr.std(ddof=1) if len(r_arr) > 1 else 0
    sharpe = (r_arr.mean() / sd * np.sqrt(len(r_arr))) if sd > 0 else 0
    downside = r_arr[r_arr < 0]
    dsd = downside.std(ddof=1) if len(downside) > 1 else 0
    sortino = (r_arr.mean() / dsd * np.sqrt(len(r_arr))) if dsd > 0 else 0
    days = max(1, (trades[-1]["close_t"] - trades[0]["open_t"]).days)
    avg_dur_h = np.mean([t["bars"] for t in trades]) * 0.25
    # walk-forward-lite: split by midpoint date
    mid = trades[0]["open_t"] + (trades[-1]["close_t"] - trades[0]["open_t"]) / 2
    h1 = sum(t["pnl"] for t in trades if t["close_t"] <= mid)
    h2 = sum(t["pnl"] for t in trades if t["close_t"] > mid)
    return (f"Trades {len(trades)} · Win {100*len(wins)/len(trades):.0f}% · "
            f"PF {pf:.2f}\n"
            f"Expectancy {exp:+.2f}R · Sharpe~ {sharpe:.1f} · Sortino~ {sortino:.1f}\n"
            f"Net {final_eq-START_BAL:+.2f} ({100*(final_eq/START_BAL-1):+.1f}%) · "
            f"MaxDD {100*mdd:.1f}%\n"
            f"Avg win {np.mean(wins) if wins else 0:+.2f} · "
            f"avg loss {np.mean(losses) if losses else 0:+.2f} · "
            f"avg trade {np.mean(pnls):+.2f}\n"
            f"Best {max(pnls):+.2f} · worst {min(pnls):+.2f} · "
            f"streaks W{ws}/L{ls}\n"
            f"~{len(trades)/days:.1f} trades/day · avg hold {avg_dur_h:.1f}h\n"
            f"1st half {h1:+.2f} · 2nd half {h2:+.2f}  (consistency check)")

# ---------------- main ----------------
all_trades, per_market = [], []
for name, (tk, eng_key, spr) in MARKETS.items():
    try:
        tr = run_market(name, tk, eng_key, spr)
    except Exception as ex:
        per_market.append(f"{name}: error {ex}"); continue
    all_trades += tr
    if tr:
        w = sum(1 for t in tr if t["R"] > 0)
        per_market.append(f"{name}: {len(tr)}t · {100*w/len(tr):.0f}% · "
                          f"{sum(t['R'] for t in tr):+.1f}R")
    else:
        per_market.append(f"{name}: 0t (filters passed nothing)")

final_eq, curve = replay(all_trades)
report = ("🔬 <b>Research backtest v3</b> — 60d walk-forward\n"
          "(per-market engines · HTF gated · partials+BE+trail ·\n"
          "spread+slippage in R · ties=stop · entries next open)\n\n"
          + "\n".join(per_market)
          + "\n\n<b>PORTFOLIO (£100 @ 0.75% risk)</b>\n"
          + stats(all_trades, curve, final_eq)
          + "\n\nNews filter omitted (no free calendar in Actions) — "
            "expansion/ATR filters partially cover it.\n"
            "One 60d window ≠ proof. Positive here = worth re-testing "
            "monthly; negative here = trust it.")
send(report)
print(report)

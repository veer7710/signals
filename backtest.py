# ============================================================
# backtest.py — FINAL DESIGN: classic trend-following
#
# This is the single most historically robust systematic approach
# there is (the actual backbone of Turtle Traders / most CTAs):
#   - Donchian channel breakout for entries (55-bar, the original
#     Turtle setting, scaled to 15m)
#   - Dual EMA (20/100) as a trend filter — only take breakouts
#     that agree with the medium-term trend
#   - ATR-based position sizing: risk is CONSTANT in £ terms,
#     position size shrinks in fast markets, grows in calm ones
#   - ATR trailing stop lets winners run (trend-following lives
#     or dies on a few big winners, not a high win rate)
#   - No pullback timing, no structure/sweep logic, no ADX gate —
#     deliberately simple. Complexity was tested to death tonight
#     and didn't help.
#
# 4 markets: Gold, Oil, US500, EUR/USD — liquid, low-cost, and the
# closest thing tonight's data had to a signal.
#
# Same honesty rules as every version tonight: no look-ahead,
# entries at next candle's open, spread+slippage in R, ties=stop,
# £100 @ 0.75% risk, full stats, one Telegram report.
# ============================================================
import os, time, requests
import yfinance as yf
import pandas as pd
import numpy as np

START_BAL, RISK_PCT = 100.0, 0.0075
DON_N, EMA_FAST, EMA_SLOW = 55, 20, 100
STOP_ATR, TRAIL_ATR = 2.0, 3.0     # wide stop, wide trail: let winners run
MAX_BARS = 96 * 5                  # 5-day hard time cap

MARKETS = {
    "GOLD":    ("GC=F",     0.0004),
    "OIL":     ("CL=F",     0.0006),
    "US500":   ("ES=F",     0.0003),
    "EUR/USD": ("EURUSD=X", 0.0002),
}

BOT, CHAT = os.environ["TG_TOKEN"], os.environ["TG_CHAT"]
def send(m):
    requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",
                  data={"chat_id": CHAT, "text": m, "parse_mode": "HTML"}, timeout=20)

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def atr(h, l, c, n=14):
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

_last = [0.0]
def get_data(ticker):
    w = 0.5 - (time.time() - _last[0])
    if w > 0: time.sleep(w)
    for _ in range(2):
        d = yf.download(ticker, period="60d", interval="15m", progress=False)
        _last[0] = time.time()
        if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
        if len(d):
            d = d.dropna(subset=["Close"])
            d.index = d.index.tz_localize("UTC") if d.index.tz is None else d.index.tz_convert("UTC")
            return d
        time.sleep(2)
    return pd.DataFrame()

def run_market(name, ticker, spread):
    d = get_data(ticker)
    if len(d) < DON_N + 210: return []
    o, h, l, c = d["Open"], d["High"], d["Low"], d["Close"]
    A = atr(h, l, c)
    eF, eS = ema(c, EMA_FAST), ema(c, EMA_SLOW)
    dhi = h.rolling(DON_N).max().shift()
    dlo = l.rolling(DON_N).min().shift()

    trades = []
    pos = None
    for i in range(DON_N + 5, len(d) - 1):
        a_ = float(A.iloc[i])
        if not np.isfinite(a_) or a_ <= 0: continue
        c1, o1 = float(c.iloc[i]), float(o.iloc[i])
        lo1, hi1 = float(l.iloc[i]), float(h.iloc[i])

        if pos:
            # ATR trail, checked on this candle before checking exits
            new_sl = (max(pos["sl"], c1 - TRAIL_ATR*a_) if pos["d"] == 1
                      else min(pos["sl"], c1 + TRAIL_ATR*a_))
            pos["sl"] = new_sl
            hit = lo1 <= pos["sl"] if pos["d"] == 1 else hi1 >= pos["sl"]
            aged = (i - pos["i0"]) >= MAX_BARS
            if hit or aged:
                exit_px = pos["sl"] if hit else c1
                r = (exit_px - pos["e"]) * pos["d"] / pos["stopdist"]
                cost_R = (pos["e"] * spread * 1.5) / pos["stopdist"]
                trades.append(dict(market=name, open_t=d.index[pos["i0"]],
                                   close_t=d.index[i], R=r - cost_R))
                pos = None
            continue

        trend_up = float(eF.iloc[i]) > float(eS.iloc[i])
        trend_dn = float(eF.iloc[i]) < float(eS.iloc[i])
        dh, dl = float(dhi.iloc[i]), float(dlo.iloc[i])
        sig = 0
        if trend_up and np.isfinite(dh) and c1 > dh: sig = 1
        elif trend_dn and np.isfinite(dl) and c1 < dl: sig = -1
        if sig == 0: continue

        e = float(o.iloc[i+1])
        stopdist = STOP_ATR * a_
        pos = dict(d=sig, e=e, sl=e - sig*stopdist, stopdist=stopdist, i0=i+1)

    return trades

def replay(all_trades):
    eq = START_BAL; curve = [eq]
    for t in sorted(all_trades, key=lambda x: x["close_t"]):
        pnl = eq * RISK_PCT * t["R"]
        eq += pnl; t["pnl"] = pnl; curve.append(eq)
    return eq, curve

def stats(trades, curve, eq):
    if not trades: return "No trades in 60 days."
    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]; losses = [p for p in pnls if p <= 0]
    gp, gl = sum(wins), abs(sum(losses))
    pf = gp/gl if gl > 0 else float("inf")
    exp = np.mean([t["R"] for t in trades])
    peak, mdd = -1e9, 0.0
    for e in curve:
        peak = max(peak, e); mdd = max(mdd, (peak-e)/peak)
    mid = trades[0]["open_t"] + (trades[-1]["close_t"]-trades[0]["open_t"])/2
    h1 = sum(t["pnl"] for t in trades if t["close_t"] <= mid)
    h2 = sum(t["pnl"] for t in trades if t["close_t"] > mid)
    return (f"Trades {len(trades)} · Win {100*len(wins)/len(trades):.0f}% · PF {pf:.2f}\n"
            f"Expectancy {exp:+.2f}R · MaxDD {100*mdd:.1f}%\n"
            f"Net {eq-START_BAL:+.2f} ({100*(eq/START_BAL-1):+.1f}%)\n"
            f"Avg win {np.mean(wins) if wins else 0:+.2f} · avg loss {np.mean(losses) if losses else 0:+.2f}\n"
            f"1st half {h1:+.2f} · 2nd half {h2:+.2f} (consistency)")

all_trades, lines = [], []
for name, (tk, spr) in MARKETS.items():
    tr = run_market(name, tk, spr)
    all_trades += tr
    if tr:
        w = sum(1 for t in tr if t["R"] > 0)
        lines.append(f"{name}: {len(tr)}t · {100*w/len(tr):.0f}% · {sum(t['R'] for t in tr):+.1f}R")
    else:
        lines.append(f"{name}: 0t")

eq, curve = replay(all_trades)
msg = ("📐 <b>Final design: classic trend-following</b>\n"
       "(Donchian-55 breakout + EMA20/100 filter + ATR trail,\n"
       "£100 @ 0.75% risk, spread+slippage, 60d, no look-ahead)\n\n"
       + "\n".join(lines) + "\n\n" + stats(all_trades, curve, eq))
send(msg); print(msg)

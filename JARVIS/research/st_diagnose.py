"""
Where does SuperTrend Sniper win, and where does it lose?

Veer's question, answered by partition rather than opinion. Every trade the
strategy takes is bucketed by the condition it opened in, so the answer is
"these conditions pay, those bleed" rather than a single average that hides
both.

Run:  python3 JARVIS/research/st_diagnose.py [SYMBOL] [TF]
"""
from __future__ import annotations
import datetime as dt, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies as S, study, exits


def bucket(rows, label, keyfn, order=None):
    g = {}
    for t, k in rows:
        g.setdefault(keyfn(k), []).append(t.r)
    keys = order or sorted(g)
    print(f"\n  {label}")
    print(f"    {'bucket':<16}{'n':>6}{'win':>7}{'expectancy':>13}{'totalR':>9}")
    out = []
    for k in keys:
        v = g.get(k, [])
        if len(v) < 12:
            print(f"    {str(k):<16}{len(v):>6}   (too few)")
            continue
        e = sum(v) / len(v)
        w = sum(1 for x in v if x > 0) / len(v)
        out.append((k, len(v), e))
        print(f"    {str(k):<16}{len(v):>6}{100*w:>6.0f}%{e:>+12.3f}R{sum(v):>+8.1f}")
    if len(out) >= 2:
        b = max(out, key=lambda x: x[2]); w_ = min(out, key=lambda x: x[2])
        print(f"    best '{b[0]}' {b[2]:+.3f}R  vs  worst '{w_[0]}' {w_[2]:+.3f}R"
              f"   spread {b[2]-w_[2]:.3f}R")
    return out


def run(symbol="GOLD", tf="1h"):
    s = engine.load(symbol, tf)
    ctx = engine.build_context(s)
    costs = study.COSTS.get(symbol, engine.Costs())
    trades = engine.backtest(s, S.supertrend_sniper(s), costs, warmup=650)
    idx = {t: i for i, t in enumerate(s.ts)}
    rows = [(t, idx[t.ts_in]) for t in trades if t.ts_in in idx]

    base = engine.stats(trades)
    print("=" * 78)
    print(f"  SUPERTREND SNIPER DIAGNOSIS — {symbol} {tf}")
    print(f"  {base['n']} trades · {100*base['win_rate']:.0f}% win · "
          f"{base['expectancy_R']:+.3f}R · maxDD {100*base['max_dd']:.1f}%")
    print("=" * 78)

    A, MED, ADX = ctx["atr"], ctx["atr_med"], ctx["adx"]
    E50, E200 = ctx["ema50"], ctx["ema200"]

    bucket(rows, "BY VOLATILITY (ATR / its median)",
           lambda i: ("quiet <0.8" if (A[i] and MED[i] and A[i]/MED[i] < 0.8)
                      else "normal 0.8-1.2" if (A[i] and MED[i] and A[i]/MED[i] < 1.2)
                      else "wild >1.2"),
           ["quiet <0.8", "normal 0.8-1.2", "wild >1.2"])

    bucket(rows, "BY TREND STRENGTH (ADX)",
           lambda i: ("chop <20" if ADX[i] < 20 else
                      "trending 20-35" if ADX[i] < 35 else "strong >35"),
           ["chop <20", "trending 20-35", "strong >35"])

    bucket(rows, "BY BIG-PICTURE TREND (EMA50 vs EMA200)",
           lambda i: "with the trend" if (
               (E50[i] > E200[i] and _side(trades, rows, i) > 0) or
               (E50[i] < E200[i] and _side(trades, rows, i) < 0)) else "against it")

    bucket(rows, "BY SESSION (UTC hour)",
           lambda i: _sess(s.ts[i]),
           ["Asia 00-07", "London 07-13", "NY 13-20", "Late 20-24"])

    bucket(rows, "BY DIRECTION",
           lambda i: "long" if _side(trades, rows, i) > 0 else "short",
           ["long", "short"])

    # ---- which exit would have been best on THESE entries
    print("\n  EXIT COMPARISON on these exact entries")
    print(f"    {'rule':<24}{'n':>6}{'win':>7}{'expectancy':>13}")
    for name in ("fixed 1R", "fixed 2R", "fixed 3R", "trail 3xATR",
                 "BE@1R + trail 3ATR", "time 20 bars", "time 50 bars"):
        pol = exits.POLICIES[name]
        tr = exits.simulate(s, S.supertrend_sniper(s), pol, costs,
                            warmup=650, allow_overlap=True)
        if len(tr) < 20:
            continue
        rs = [x["r"] for x in tr]
        w = sum(1 for r in rs if r > 0) / len(rs)
        print(f"    {name:<24}{len(rs):>6}{100*w:>6.0f}%{sum(rs)/len(rs):>+12.3f}R")


def _side(trades, rows, i):
    for t, j in rows:
        if j == i:
            return t.side
    return 0


def _sess(ts):
    h = dt.datetime.fromtimestamp(ts, dt.timezone.utc).hour
    return ("Asia 00-07" if h < 7 else "London 07-13" if h < 13
            else "NY 13-20" if h < 20 else "Late 20-24")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "GOLD",
        sys.argv[2] if len(sys.argv) > 2 else "1h")

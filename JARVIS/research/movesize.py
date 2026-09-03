"""
Can we tell a BIG move from a SMALL one, at entry time?

Veer's diagnosis: "we catch every mini trend on M1, often they are small and
very short, we never know if they are small or massive... we see over 400
points of movement through the day, we just need to catch a lot of it."

That is a TRADE SELECTION problem, not a signal problem, and it is the right
problem. A system that enters the same way every time but only takes the
setups that RUN will beat one that enters better but takes everything.

This module asks one question: is there anything measurable BEFORE entry that
predicts how far the move will travel?

Every feature is computed from closed bars at or before the decision bar.
Forward MFE is the thing being predicted, never an input.
"""
from __future__ import annotations
import datetime as dt, os, statistics as stat, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine


def build_samples(symbol="GOLD", tf="15m", horizon=40, step=1):
    """
    One sample per bar: features known at that bar, plus how far price
    subsequently travelled in each direction, in ATR units.
    """
    s = engine.load(symbol, tf)
    ctx = engine.build_context(s)
    A, ADX, RSI = ctx["atr"], ctx["adx"], ctx["rsi"]
    med = ctx["atr_med"]
    out = []
    for i in range(300, len(s) - horizon - 1, step):
        a = A[i]; m = med[i]
        if not a or not m or a <= 0 or m <= 0:
            continue
        # ---- forward travel (the thing we want to predict)
        hi = max(s.h[i + 1:i + 1 + horizon])
        lo = min(s.l[i + 1:i + 1 + horizon])
        up = (hi - s.c[i]) / a
        dn = (s.c[i] - lo) / a
        best = max(up, dn)

        # ---- decision-time features only
        rng = max(s.h[i] - s.l[i], 1e-9)
        body = abs(s.c[i] - s.o[i])
        # efficiency: net progress vs total path over the last 20 bars.
        # High = trending cleanly, low = chopping.
        net = abs(s.c[i] - s.c[i - 20])
        path = sum(abs(s.c[j] - s.c[j - 1]) for j in range(i - 19, i + 1))
        eff = net / path if path > 0 else 0
        # squeeze: current ATR vs its own median. Low = compression.
        squeeze = a / m
        # recent range in ATR: how much room the market has been using
        rr20 = (max(s.h[i - 19:i + 1]) - min(s.l[i - 19:i + 1])) / a
        out.append({
            "i": i,
            "hour": dt.datetime.fromtimestamp(s.ts[i], dt.timezone.utc).hour,
            "eff": round(eff, 4),
            "squeeze": round(squeeze, 3),
            "adx": round(ADX[i], 1),
            "rsi": round(RSI[i], 1),
            "bar_atr": round(rng / a, 3),
            "body_frac": round(body / rng, 3),
            "range20_atr": round(rr20, 2),
            "mfe_up": round(up, 3),
            "mfe_dn": round(dn, 3),
            "mfe_best": round(best, 3),
        })
    return out, s


def bucket_report(rows, feature, edges, label, target="mfe_best", big=3.0):
    """Show how the predicted quantity varies across buckets of one feature."""
    buckets = {}
    for r in rows:
        v = r[feature]
        name = None
        for lo, hi in zip(edges, edges[1:]):
            if lo <= v < hi:
                name = f"{lo:g}-{hi:g}"; break
        if name is None:
            name = f">={edges[-1]:g}" if v >= edges[-1] else f"<{edges[0]:g}"
        buckets.setdefault(name, []).append(r[target])
    order = sorted(buckets, key=lambda k: (k.startswith("<"), k.startswith(">="), k))
    print(f"\n  {label}")
    print(f"    {'bucket':<12}{'n':>7}{'median':>10}{'mean':>9}"
          f"{'P(>'+str(big)+' ATR)':>14}{'P(>5 ATR)':>11}")
    stats = []
    for k in order:
        v = buckets[k]
        if len(v) < 40:
            continue
        m = stat.median(v)
        pb = sum(1 for x in v if x > big) / len(v)
        p5 = sum(1 for x in v if x > 5.0) / len(v)
        stats.append((k, len(v), m, pb))
        print(f"    {k:<12}{len(v):>7}{m:>10.2f}{sum(v)/len(v):>9.2f}"
              f"{100*pb:>13.0f}%{100*p5:>10.0f}%")
    if len(stats) >= 2:
        b = max(stats, key=lambda x: x[3]); w = min(stats, key=lambda x: x[3])
        print(f"    spread: best bucket {b[0]} at {100*b[3]:.0f}%  vs  "
              f"worst {w[0]} at {100*w[3]:.0f}%   "
              f"({100*(b[3]-w[3]):+.0f} points)")
    return stats


def run(symbol="GOLD", tf="15m", horizon=40):
    rows, s = build_samples(symbol, tf, horizon)
    base = [r["mfe_best"] for r in rows]
    print("=" * 78)
    print(f"  MOVE SIZE STUDY — {symbol} {tf}, {len(rows)} bars, "
          f"{horizon}-bar forward window")
    print("=" * 78)
    print(f"\n  How far does price travel in {horizon} bars? (ATR units, best direction)")
    q = lambda p: sorted(base)[int(p * (len(base) - 1))]
    print(f"    median {stat.median(base):.2f}   75th {q(.75):.2f}   "
          f"90th {q(.90):.2f}   99th {q(.99):.2f}   max {max(base):.2f}")
    print(f"    P(move > 3 ATR) = {100*sum(1 for x in base if x>3)/len(base):.0f}%"
          f"    P(move > 5 ATR) = {100*sum(1 for x in base if x>5)/len(base):.0f}%")
    print("\n  This is the baseline. A feature is only useful if it beats it.")

    bucket_report(rows, "eff", [0, .1, .2, .3, .4, .6],
                  "BY TREND EFFICIENCY (net move / total path, last 20 bars)")
    bucket_report(rows, "squeeze", [0, .6, .8, 1.0, 1.3, 2.0],
                  "BY VOLATILITY SQUEEZE (ATR / median ATR)")
    bucket_report(rows, "adx", [0, 15, 20, 25, 30, 40],
                  "BY ADX")
    bucket_report(rows, "range20_atr", [0, 3, 5, 7, 10, 15],
                  "BY RECENT 20-BAR RANGE (in ATR)")
    bucket_report(rows, "hour", list(range(0, 24, 2)),
                  "BY HOUR (UTC)")
    return rows


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "GOLD",
        sys.argv[2] if len(sys.argv) > 2 else "15m")

"""
E-108 — A STRATEGY TOURNAMENT. Ten named strategies, not two analysed to death.

Veer: "ur not being good enough use actual strategy's ur just doing random tests
... we aim for small profits consistently and liquidity helps catch insane
bangers ... test ur own logic".

He is right about the shape of the problem. `strategies.py` has FOUR entries in
its registry - minimal_trend, sweep_continuation, supertrend_sniper and its EA
variant - and the other eighty files in this directory are all analysis OF those.
Ninety experiments deep and the project has never run a broad hunt.

His own model is two engines and it is a sound design:
  ENGINE A  small profits, consistently. High hit rate, tight target, many trades.
  ENGINE B  liquidity catching the bangers. Low frequency, uncapped, fat tail.
So the field is built to those two shapes and each is judged on its own terms -
A on hit rate and points per day, B on the size of its top decile.

Every strategy here is a REAL, named, mechanically specific setup, not a
parameter sweep of an existing one. All share the same engine, the same costs
charged both ends, ties-lose, and next-bar-open fills, so only the LOGIC differs.

Run:  python3 JARVIS/research/tournament.py
"""
from __future__ import annotations
import os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from engine import Series, atr as watr, ema, rolling_max, rolling_min

# ---------------------------------------------------------------- helpers
def hour(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).hour


def day(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).date()


def prior_day_levels(s):
    """Previous day's high and low, usable only from the first bar of the NEXT
    day. Built forward, so no bar can see its own day's completed range."""
    hi, lo = {}, {}
    ch = cl = None
    cur = None
    out_h = [None] * len(s)
    out_l = [None] * len(s)
    for i in range(len(s)):
        d = day(s.ts[i])
        if cur is None:
            cur, ch, cl = d, s.h[i], s.l[i]
        elif d != cur:
            hi[d], lo[d] = ch, cl          # yesterday's completed range
            cur, ch, cl = d, s.h[i], s.l[i]
        else:
            ch = max(ch, s.h[i]); cl = min(cl, s.l[i])
        out_h[i], out_l[i] = hi.get(d), lo.get(d)
    return out_h, out_l


# ================================================================ ENGINE A
# small, frequent, high hit rate. Target 1.0R, stop 1.0 ATR.
def nr7_breakout(s, A, i, ctx):
    """The narrowest range in seven bars is a coiled spring; trade the break of
    that bar in whichever direction it goes."""
    if i < 8: return None
    rng = [s.h[j] - s.l[j] for j in range(i - 6, i + 1)]
    if rng[-1] != min(rng): return None
    if s.c[i] > s.h[i - 1]: return 1
    if s.c[i] < s.l[i - 1]: return -1
    return None


def inside_bar(s, A, i, ctx):
    """An inside bar is a pause. Trade the break of the bar that contained it."""
    if i < 3: return None
    if not (s.h[i - 1] <= s.h[i - 2] and s.l[i - 1] >= s.l[i - 2]): return None
    if s.c[i] > s.h[i - 2]: return 1
    if s.c[i] < s.l[i - 2]: return -1
    return None


def orb(s, A, i, ctx):
    """Opening range breakout: the first three bars after 07:00 UTC set a range;
    trade the first close outside it, once per day."""
    h = hour(s.ts[i])
    if not (8 <= h <= 16): return None
    d = day(s.ts[i])
    key = ("orb", d)
    if ctx.get(key) is not None: return None
    idx = [j for j in range(max(0, i - 40), i) if day(s.ts[j]) == d and hour(s.ts[j]) >= 7]
    if len(idx) < 3: return None
    o = idx[:3]
    hi = max(s.h[j] for j in o); lo = min(s.l[j] for j in o)
    if i <= o[-1]: return None
    if s.c[i] > hi: ctx[key] = 1; return 1
    if s.c[i] < lo: ctx[key] = -1; return -1
    return None


def ema_pullback(s, A, i, ctx):
    """Classic trend-following: EMA50 over EMA200 defines the trend, and the
    entry is the first close back above EMA20 after dipping below it."""
    e20, e50, e200 = ctx["e20"], ctx["e50"], ctx["e200"]
    if None in (e20[i], e50[i], e200[i], e20[i-1]): return None
    up = e50[i] > e200[i]
    if up and s.l[i] <= e20[i] and s.c[i] > e20[i] and s.c[i-1] < e20[i-1]: return 1
    if not up and s.h[i] >= e20[i] and s.c[i] < e20[i] and s.c[i-1] > e20[i-1]: return -1
    return None


def round_bounce(s, A, i, ctx):
    """Gold clusters orders at whole tens. A long wick through a round number
    that closes back on the original side is a rejection."""
    a = A[i]
    if not a or a <= 0: return None
    step = 10.0
    lvl = round(s.c[i] / step) * step
    tol = 0.30 * a
    rng = max(s.h[i] - s.l[i], 1e-9)
    dnw = (min(s.o[i], s.c[i]) - s.l[i]) / rng
    upw = (s.h[i] - max(s.o[i], s.c[i])) / rng
    if s.l[i] <= lvl + tol and s.c[i] > lvl and dnw >= 0.45: return 1
    if s.h[i] >= lvl - tol and s.c[i] < lvl and upw >= 0.45: return -1
    return None


# ================================================================ ENGINE B
# rarer, uncapped, meant to catch the bangers.
def pdh_pdl_sweep(s, A, i, ctx):
    """The real stop run: yesterday's high or low is taken out and price closes
    back inside the range. That is where the stops were."""
    ph, pl = ctx["pdh"][i], ctx["pdl"][i]
    if ph is None or pl is None: return None
    if s.h[i] > ph and s.c[i] < ph: return -1
    if s.l[i] < pl and s.c[i] > pl: return 1
    return None


def failed_breakout(s, A, i, ctx):
    """Price breaks an N-bar extreme and closes back inside within three bars.
    A break that does not hold is a trap, and the reversal is the trade."""
    N = 20
    if i < N + 4: return None
    hi = max(s.h[i - N:i - 3]); lo = min(s.l[i - N:i - 3])
    broke_up = any(s.h[j] > hi for j in range(i - 3, i))
    broke_dn = any(s.l[j] < lo for j in range(i - 3, i))
    if broke_up and s.c[i] < hi: return -1
    if broke_dn and s.c[i] > lo: return 1
    return None


def mtf_align(s, A, i, ctx):
    """Higher-timeframe trend, lower-timeframe entry: EMA200 sets direction and
    the trade is the first close through the prior bar in that direction after
    a three-bar pause against it."""
    e200 = ctx["e200"]
    if e200[i] is None or i < 6: return None
    up = s.c[i] > e200[i]
    if up:
        if all(s.c[j] < s.o[j] for j in (i-3, i-2, i-1)) and s.c[i] > s.h[i-1]: return 1
    else:
        if all(s.c[j] > s.o[j] for j in (i-3, i-2, i-1)) and s.c[i] < s.l[i-1]: return -1
    return None


def asian_fade(s, A, i, ctx):
    """The 00:00-06:00 UTC range is thin and its edges get run at the London
    open. Fade the first break back inside."""
    h = hour(s.ts[i])
    if not (7 <= h <= 12): return None
    d = day(s.ts[i])
    idx = [j for j in range(max(0, i - 60), i) if day(s.ts[j]) == d and hour(s.ts[j]) < 7]
    if len(idx) < 4: return None
    hi = max(s.h[j] for j in idx); lo = min(s.l[j] for j in idx)
    key = ("asia", d)
    if ctx.get(key) is not None: return None
    if s.h[i] > hi and s.c[i] < hi: ctx[key] = 1; return -1
    if s.l[i] < lo and s.c[i] > lo: ctx[key] = 1; return 1
    return None


def squeeze_expansion(s, A, i, ctx):
    """Volatility contracts before it expands. When ATR falls into the bottom
    fifth of its own recent distribution, trade the break of the quiet range."""
    if i < 60: return None
    a = A[i]
    if not a or a <= 0: return None
    win = [x for x in A[i - 50:i] if x]
    if len(win) < 30: return None
    if a > sorted(win)[len(win) // 5]: return None
    hi = max(s.h[i - 10:i]); lo = min(s.l[i - 10:i])
    if s.c[i] > hi: return 1
    if s.c[i] < lo: return -1
    return None


ENGINE_A = [("NR7 breakout", nr7_breakout), ("inside bar break", inside_bar),
            ("opening range break", orb), ("EMA20 pullback", ema_pullback),
            ("round-number bounce", round_bounce)]
ENGINE_B = [("prior-day sweep", pdh_pdl_sweep), ("failed breakout", failed_breakout),
            ("HTF align + pause", mtf_align), ("Asian range fade", asian_fade),
            ("squeeze expansion", squeeze_expansion)]


def run(s, costs, fn, ctx, A, stop_atr, tgt_r, trail, max_bars=120, warm=250):
    half = costs.spread / 2.0
    comm = costs.commission_per_lot / costs.value_per_point_per_lot
    out, busy = [], -1
    for i in range(warm, len(s) - 1):
        if i <= busy: continue
        side = fn(s, A, i, ctx)
        if not side: continue
        a = A[i]
        if not a or a <= 0: continue
        entry = s.o[i + 1] + side * (half + costs.slippage)
        risk = stop_atr * a
        stop = entry - side * risk
        tgt = entry + side * tgt_r * risk if tgt_r else None
        peak = entry
        px = why = None
        for k in range(i + 1, min(i + 1 + max_bars, len(s))):
            if (side > 0 and s.l[k] <= stop) or (side < 0 and s.h[k] >= stop):
                px, why = stop, "stop"; break
            if tgt and ((side > 0 and s.h[k] >= tgt) or (side < 0 and s.l[k] <= tgt)):
                px, why = tgt, "target"; break
            if trail:
                peak = max(peak, s.h[k]) if side > 0 else min(peak, s.l[k])
                t = peak - side * trail * a
                cand = max(stop, t) if side > 0 else min(stop, t)
                worst = s.l[k] if side > 0 else s.h[k]
                if cand != stop and ((side > 0 and worst <= cand) or
                                     (side < 0 and worst >= cand)):
                    px, why = cand, "trail"; break
                stop = cand
        if px is None:
            k = min(i + max_bars, len(s) - 1); px, why = s.c[k], "time"
        fill = px - side * (half + costs.slippage)
        pts = (fill - entry) * side - comm
        out.append({"r": pts / risk, "pts": pts, "out": k, "ts": s.ts[k]})
        busy = k
    return out


def report(name, tr, label):
    if len(tr) < 25:
        print(f"  {name:<24} {len(tr):>5}   too few trades")
        return
    n = len(tr)
    m = sum(t["r"] for t in tr) / n
    sd = (sum((t["r"] - m) ** 2 for t in tr) / (n - 1)) ** 0.5
    t_ = m / (sd / n ** 0.5)
    w = 100.0 * sum(1 for x in tr if x["pts"] > 0) / n
    pts = sum(x["pts"] for x in tr)
    days = len(set(day(x["ts"]) for x in tr))
    top = sorted((x["pts"] for x in tr), reverse=True)[:max(1, n // 10)]
    print(f"  {name:<24} {n:>5} {w:>6.1f}% {m:>+8.3f} {t_:>6.2f} {pts:>9.1f} "
          f"{pts/days:>8.2f} {sum(top):>9.1f}")


def main():
    for sym, tf in (("GOLD", "15m"), ("GOLD", "1h")):
        s = engine.load(sym, tf)
        c = study.COSTS[sym]
        A = watr(s, 14)
        pdh, pdl = prior_day_levels(s)
        base = {"e20": ema(s.c, 20), "e50": ema(s.c, 50), "e200": ema(s.c, 200),
                "pdh": pdh, "pdl": pdl}
        for label, field, kw in (
            ("ENGINE A — small and consistent (1.0 ATR stop, 1R target)",
             ENGINE_A, dict(stop_atr=1.0, tgt_r=1.0, trail=0.0)),
            ("ENGINE B — bangers (1.5 ATR stop, uncapped, 2 ATR trail)",
             ENGINE_B, dict(stop_atr=1.5, tgt_r=0.0, trail=2.0)),
        ):
            print(f"\n{'='*94}\n  {sym} {tf} — {label}\n{'='*94}")
            print(f"  {'strategy':<24} {'n':>5} {'win%':>7} {'mean R':>8} "
                  f"{'t':>6} {'points':>9} {'pts/day':>8} {'top 10%':>9}")
            print("  " + "-" * 88)
            for name, fn in field:
                ctx = dict(base)
                report(name, run(s, c, fn, ctx, A, **kw), label)


if __name__ == "__main__":
    main()

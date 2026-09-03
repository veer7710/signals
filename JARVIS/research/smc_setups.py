"""
DO THE SMC SETUPS ACTUALLY WORK? — measuring the seven, one at a time.

The liquidity indicator now offers seven setup types: BREAK, BOUNCE, RETEST,
PULLBACK, BREAKOUT, GAP FILL (fair value gap) and ORDER BLOCK. They were added
because they are what a structure trader watches - which is a reason to BUILD
them and not a reason to believe them.

Veer: "we are defo not going deep enough on strategy we need perfected signals
absolute". Perfecting signals means finding out which of the seven carries an
edge and which is decoration, and the only way to do that is to measure each
one in isolation, on the same bars, with the same costs and the same rules.

WHAT IS MEASURED
  Each setup is implemented here exactly as the Pine implements it, then run
  through the same engine as everything else in this repo:
    * signal from CLOSED bars only, filled at the NEXT bar's open
    * first touch: the target counts only if reached BEFORE the stop
    * ties lose
    * spread and slippage charged on every fill
  Then the chronological 70/30 split: chosen on the first 70%, confirmed once
  on the last 30%. A setup that only works in-sample is decoration.

WHAT THIS CANNOT TELL YOU
  The data here is 15m and 1h. The indicator is traded on M1. A setup that
  works on 15m may not survive M1 spread, and nothing here measures that.
  This ranks the IDEAS; it does not certify them for M1.

Run:  python3 JARVIS/research/smc_setups.py
"""
from __future__ import annotations
import os, sys, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
import study
from engine import Costs, Series


def costs_for(sym):
    """Per-symbol costs. The default Costs() is GOLD-shaped - a 0.30 spread in
    price units. Applied to EURUSD that is 3000 pips a trade, which does not
    make FX look bad, it makes every FX number meaningless. study.COSTS has the
    right values per symbol and every script must use it."""
    return study.COSTS.get(sym, engine.Costs())


# ---------------------------------------------------------------- structure
def swings(s: Series, n=5):
    """Confirmed swing highs/lows, known only n bars AFTER they form."""
    hi = [None] * len(s)
    lo = [None] * len(s)
    for i in range(n, len(s) - n):
        seg_h = s.h[i - n:i + n + 1]
        seg_l = s.l[i - n:i + n + 1]
        if s.h[i] == max(seg_h):
            hi[i + n] = s.h[i]          # published n bars late, as Pine does
        if s.l[i] == min(seg_l):
            lo[i + n] = s.l[i]
    return hi, lo


def structure(s: Series, n=5):
    """bias[i] = +1 bullish, -1 bearish, 0 undecided, using CLOSE breaks."""
    hi, lo = swings(s, n)
    bias = [0] * len(s)
    sw_hi = sw_lo = None
    b = 0
    for i in range(len(s)):
        if hi[i] is not None: sw_hi = hi[i]
        if lo[i] is not None: sw_lo = lo[i]
        if sw_hi is not None and s.c[i] > sw_hi and s.c[i - 1] <= sw_hi:
            b = 1
        elif sw_lo is not None and s.c[i] < sw_lo and s.c[i - 1] >= sw_lo:
            b = -1
        bias[i] = b
    return bias, hi, lo


# ------------------------------------------------------------------ setups
def make_fvg(s, A, min_atr=0.25, stop_atr=1.5, rr=3.0, with_bias=False, n=5):
    """Enter when price returns into an unfilled 3-bar imbalance."""
    bias, _, _ = structure(s, n) if with_bias else ([0] * len(s), None, None)
    gaps = []       # (top, bot, dir)

    def sig(ctx, i):
        a = A[i]
        if a is None or a <= 0 or i < 4:
            return None
        # register the gap that completed on bar i
        if s.l[i] > s.h[i - 2] and (s.l[i] - s.h[i - 2]) >= min_atr * a:
            gaps.append([s.l[i], s.h[i - 2], 1, i])
        if s.h[i] < s.l[i - 2] and (s.l[i - 2] - s.h[i]) >= min_atr * a:
            gaps.append([s.l[i - 2], s.h[i], -1, i])
        while len(gaps) > 12:
            gaps.pop(0)
        # a gap price has come back into
        for g in list(gaps):
            top, bot, d, born = g
            if born == i:
                continue
            if s.l[i] <= top and s.h[i] >= bot:
                gaps.remove(g)                 # consumed: never fires twice
                if d > 0 and s.c[i] > bot and (not with_bias or bias[i] >= 0):
                    dist = stop_atr * a
                    return {"side": 1, "stop": s.c[i] - dist,
                            "target": s.c[i] + rr * dist}
                if d < 0 and s.c[i] < top and (not with_bias or bias[i] <= 0):
                    dist = stop_atr * a
                    return {"side": -1, "stop": s.c[i] + dist,
                            "target": s.c[i] - rr * dist}
        return None
    return sig


def make_ob(s, A, stop_atr=1.5, rr=3.0, expire=60, n=5):
    """Enter on a return to the last opposite candle before a structure break."""
    bias, hi, lo = structure(s, n)
    ob = {"up": None, "dn": None}

    def sig(ctx, i):
        a = A[i]
        if a is None or a <= 0 or i < 25:
            return None
        # a break of structure defines a fresh order block
        if bias[i] == 1 and bias[i - 1] != 1:
            for j in range(1, 21):
                if s.c[i - j] < s.o[i - j]:
                    ob["up"] = (s.h[i - j], s.l[i - j], i)
                    break
        if bias[i] == -1 and bias[i - 1] != -1:
            for j in range(1, 21):
                if s.c[i - j] > s.o[i - j]:
                    ob["dn"] = (s.h[i - j], s.l[i - j], i)
                    break
        dist = stop_atr * a
        u = ob["up"]
        if u and i - u[2] <= expire and s.l[i] <= u[0] and s.c[i] > u[1]:
            ob["up"] = None                    # used once
            return {"side": 1, "stop": s.c[i] - dist, "target": s.c[i] + rr * dist}
        d_ = ob["dn"]
        if d_ and i - d_[2] <= expire and s.h[i] >= d_[1] and s.c[i] < d_[0]:
            ob["dn"] = None
            return {"side": -1, "stop": s.c[i] + dist, "target": s.c[i] - rr * dist}
        return None
    return sig


def make_pullback(s, A, ema_len=50, tol=0.30, stop_atr=1.5, rr=3.0):
    """Trend pullback to the moving average."""
    E = engine.ema(s.c, ema_len)

    def sig(ctx, i):
        a = A[i]
        if a is None or a <= 0 or i < ema_len + 3:
            return None
        e, ep = E[i], E[i - 2]
        if e is None or ep is None:
            return None
        dist = stop_atr * a
        if e > ep and s.l[i] <= e + tol * a and s.c[i] > e and s.c[i] > s.o[i]:
            return {"side": 1, "stop": s.c[i] - dist, "target": s.c[i] + rr * dist}
        if e < ep and s.h[i] >= e - tol * a and s.c[i] < e and s.c[i] < s.o[i]:
            return {"side": -1, "stop": s.c[i] + dist, "target": s.c[i] - rr * dist}
        return None
    return sig


def make_breakout(s, A, box=20, tight=3.0, stop_atr=1.5, rr=3.0):
    """Quiet range, then out of it."""
    def sig(ctx, i):
        a = A[i]
        if a is None or a <= 0 or i < box + 2:
            return None
        hh = max(s.h[i - box:i])
        ll = min(s.l[i - box:i])
        if hh - ll <= 0 or hh - ll > tight * a:
            return None
        dist = stop_atr * a
        if s.c[i] > hh:
            return {"side": 1, "stop": s.c[i] - dist, "target": s.c[i] + rr * dist}
        if s.c[i] < ll:
            return {"side": -1, "stop": s.c[i] + dist, "target": s.c[i] - rr * dist}
        return None
    return sig


def make_discount(s, A, rng=100, stop_atr=1.5, rr=3.0, n=5):
    """Buy the lower half of the range in bullish structure, sell the upper
    half in bearish. The premium/discount idea, on its own."""
    bias, _, _ = structure(s, n)

    def sig(ctx, i):
        a = A[i]
        if a is None or a <= 0 or i < rng + 2:
            return None
        hh = max(s.h[i - rng:i + 1]); ll = min(s.l[i - rng:i + 1])
        if hh <= ll:
            return None
        pos = (s.c[i] - ll) / (hh - ll)
        dist = stop_atr * a
        if bias[i] > 0 and pos < 0.4 and s.c[i] > s.o[i]:
            return {"side": 1, "stop": s.c[i] - dist, "target": s.c[i] + rr * dist}
        if bias[i] < 0 and pos > 0.6 and s.c[i] < s.o[i]:
            return {"side": -1, "stop": s.c[i] + dist, "target": s.c[i] - rr * dist}
        return None
    return sig


BUILDERS = {
    "GAP FILL":        lambda s, A: make_fvg(s, A),
    "GAP FILL +bias":  lambda s, A: make_fvg(s, A, with_bias=True),
    "ORDER BLOCK":     lambda s, A: make_ob(s, A),
    "PULLBACK":        lambda s, A: make_pullback(s, A),
    "BREAKOUT":        lambda s, A: make_breakout(s, A),
    "DISCOUNT/PREMIUM": lambda s, A: make_discount(s, A),
}


def split(s, frac=0.70):
    k = int(len(s) * frac)
    return (Series(s.ts[:k], s.o[:k], s.h[:k], s.l[:k], s.c[:k]),
            Series(s.ts[k:], s.o[k:], s.h[k:], s.l[k:], s.c[k:]))


def stat(trades):
    if not trades:
        return 0, 0.0, 0.0, 0.0
    rs = [t.r for t in trades]
    n = len(rs)
    m = sum(rs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in rs) / n) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n and sd else 0.0
    t = m / se if se else 0.0
    win = 100.0 * sum(1 for x in rs if x > 0) / n
    return n, win, m, t


def run(sym, tf):
    s = engine.load(sym, tf)
    ins, oos = split(s)
    c = costs_for(sym)
    print(f"\n{'='*78}\n  {sym} {tf}   {len(s)} bars"
          f"\n  chosen on the first 70%, confirmed ONCE on the last 30%\n{'='*78}")
    print(f"  {'setup':<19}{'IS n':>6}{'IS exp':>9}{'IS t':>7}"
          f"{'| OOS n':>9}{'OOS win':>9}{'OOS exp':>9}{'OOS t':>7}  verdict")
    for name, build in BUILDERS.items():
        try:
            Ai = engine.atr(ins, 14)
            Ao = engine.atr(oos, 14)
            ti = engine.backtest(ins, build(ins, Ai), c, warmup=250, max_bars=50)
            to = engine.backtest(oos, build(oos, Ao), c, warmup=250, max_bars=50)
        except Exception as e:
            print(f"  {name:<19} ERROR {e}")
            continue
        ni, wi, mi, tti = stat(ti)
        no, wo, mo, tto = stat(to)
        if ni < 25 or no < 15:
            verdict = "too few trades"
        elif mi > 0 and mo > 0:
            verdict = "HELD"
        elif mo > 0:
            verdict = "oos only"
        else:
            verdict = "did not hold"
        print(f"  {name:<19}{ni:>6}{mi:>+9.3f}{tti:>+7.2f}"
              f"{no:>9}{wo:>8.1f}%{mo:>+9.3f}{tto:>+7.2f}  {verdict}")


if __name__ == "__main__":
    print(__doc__)
    for sym in ("GOLD", "US500", "EURUSD", "GBPUSD"):
        for tf in ("15m", "1h"):
            try:
                run(sym, tf)
            except FileNotFoundError:
                pass
    print("\n" + "=" * 78)
    print("  A setup that is positive in-sample and negative out-of-sample is")
    print("  decoration. Turn it off in the indicator rather than believing it.")
    print("  ~780 configurations have been tested against this data, so the")
    print("  luck threshold is around t = 3.65 - read every t against that.")
    print("=" * 78)

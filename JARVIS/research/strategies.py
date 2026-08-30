"""
JARVIS strategy library.

Every strategy is a factory returning `sig(ctx, i) -> None | dict`, evaluated
using ONLY bars that have closed at or before `i`. The engine fills at the
open of bar i+1. Nothing in here may read s.c[i+1] or later — that is the
single rule that separates a backtest from a fantasy.

Each returns: {"side": +1/-1, "stop": price, "target": price, "meta": {...}}
"""
from __future__ import annotations
import datetime as _dt
from engine import Series, ema, resample


def hour_utc(ts):
    return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).hour


# ------------------------------------------------- higher-timeframe trend
def htf_trend(s: Series, factor: int, fast: int = 50, slow: int = 200):
    """+1/-1/0 per base bar from a higher timeframe, without look-ahead.

    At base bar i, the most recent COMPLETED higher-timeframe bar is
    (i // factor) - 1. Using (i // factor) would leak the future.
    """
    htf = resample(s, factor)
    ef, es = ema(htf.c, fast), ema(htf.c, slow)
    out = [0] * len(s)
    for i in range(len(s)):
        k = i // factor - 1
        if k < slow or k >= len(htf):
            continue
        out[i] = 1 if ef[k] > es[k] else -1
    return out


# --------------------------------------------------------- swing pivots
def swing_points(s: Series, left=3, right=3):
    """Confirmed pivot highs/lows.

    A pivot at bar j is only KNOWN at bar j+right. We return, for each bar i,
    the list of pivot prices confirmed by then — never a pivot from the future.
    """
    is_hi = [False] * len(s)
    is_lo = [False] * len(s)
    for j in range(left, len(s) - right):
        wh = s.h[j - left:j + right + 1]
        wl = s.l[j - left:j + right + 1]
        if s.h[j] == max(wh) and wh.count(s.h[j]) == 1:
            is_hi[j] = True
        if s.l[j] == min(wl) and wl.count(s.l[j]) == 1:
            is_lo[j] = True
    highs, lows = [], []          # per-bar: recent confirmed levels
    cur_h, cur_l = [], []
    for i in range(len(s)):
        j = i - right             # pivots confirmed as of bar i
        if j >= 0:
            if is_hi[j]: cur_h.append(s.h[j])
            if is_lo[j]: cur_l.append(s.l[j])
        highs.append(cur_h[-6:].copy())
        lows.append(cur_l[-6:].copy())
    return highs, lows


# ============================================================ STRATEGIES
def liquidity_sweep(s: Series, rr=2.0, htf_factor=4, use_trend=True,
                    session=None, buffer_atr=0.15, left=3, right=3,
                    close_back_frac=0.5):
    """
    LIQUIDITY SWEEP / STOP RUN.

    The idea being tested: resting stop orders sit just beyond obvious swing
    highs and lows. Price spikes through to trigger them, then immediately
    reverses because the move was liquidity-driven rather than trend-driven.

    Long setup:
      1. This bar's LOW trades below a confirmed swing low  (stops taken)
      2. This bar CLOSES back above that level              (sweep rejected)
      3. Close sits in the upper part of the bar's range    (real rejection)
    Stop goes under the sweep wick; target is a fixed multiple of that risk.

    This is a genuine hypothesis, not a guarantee. It is here to be tested
    and, if it fails, rejected.
    """
    highs, lows = swing_points(s, left, right)
    gate = htf_trend(s, htf_factor) if use_trend else [0] * len(s)

    def sig(ctx, i):
        a = ctx["atr"][i]
        if a is None or a <= 0:
            return None
        if session and not (session[0] <= hour_utc(s.ts[i]) < session[1]):
            return None
        rng = s.h[i] - s.l[i]
        if rng <= 0:
            return None

        # ---- long: swept a swing low and closed back above it
        for lvl in lows[i]:
            if s.l[i] < lvl <= s.c[i]:
                if (s.c[i] - s.l[i]) / rng < close_back_frac:
                    continue                      # weak rejection
                if use_trend and gate[i] != 1:
                    continue
                stop = s.l[i] - buffer_atr * a
                risk = s.c[i] - stop
                if risk <= 0:
                    continue
                return {"side": 1, "stop": stop, "target": s.c[i] + rr * risk,
                        "meta": {"level": lvl, "atr": a, "rr": rr}}

        # ---- short: swept a swing high and closed back below it
        for lvl in highs[i]:
            if s.h[i] > lvl >= s.c[i]:
                if (s.h[i] - s.c[i]) / rng < close_back_frac:
                    continue
                if use_trend and gate[i] != -1:
                    continue
                stop = s.h[i] + buffer_atr * a
                risk = stop - s.c[i]
                if risk <= 0:
                    continue
                return {"side": -1, "stop": stop, "target": s.c[i] - rr * risk,
                        "meta": {"level": lvl, "atr": a, "rr": rr}}
        return None
    return sig


def donchian_trend(s: Series, rr=3.0, stop_atr=2.0, fast="ema20", slow="ema100"):
    """Breakout trend-following. The most-replicated systematic edge there is,
    included as an honest BASELINE: any new idea must beat this to earn its
    complexity."""
    def sig(ctx, i):
        a = ctx["atr"][i]
        if a is None or a <= 0:
            return None
        dh, dl = ctx["don_hi"][i - 1], ctx["don_lo"][i - 1]
        if dh is None or dl is None:
            return None
        up = ctx[fast][i] > ctx[slow][i]
        dn = ctx[fast][i] < ctx[slow][i]
        st = 1 if (up and s.c[i] > dh) else (-1 if (dn and s.c[i] < dl) else 0)
        if st == 0:
            return None
        px, d = s.c[i], stop_atr * a
        return {"side": st, "stop": px - st * d, "target": px + st * rr * d,
                "meta": {"atr": a, "rr": rr}}
    return sig


def ema_pullback(s: Series, rr=2.0, htf_factor=4, stop_atr=1.2,
                 session=(7, 20), adx_min=20):
    """Trend-continuation: stacked EMAs, pull back to EMA21, resume.

    Structurally this is what the previous project traded — rebuilt here with
    a FIXED reward:risk instead of a capped target, because a capped target
    with an ATR-scaled stop silently destroys the risk/reward as volatility
    rises.
    """
    gate = htf_trend(s, htf_factor)

    def sig(ctx, i):
        a = ctx["atr"][i]; med = ctx["atr_med"][i]
        if a is None or med is None or med <= 0:
            return None
        if not (0.5 * med <= a <= 2.5 * med):
            return None
        if session and not (session[0] <= hour_utc(s.ts[i]) < session[1]):
            return None
        e9, e21, e50 = ctx["ema9"][i], ctx["ema21"][i], ctx["ema50"][i]
        pdi, mdi = ctx["pdi"][i], ctx["mdi"][i]
        if e9 > e21 > e50 and pdi > mdi:
            st = 1
        elif e9 < e21 < e50 and mdi > pdi:
            st = -1
        else:
            return None
        if st != gate[i] or ctx["adx"][i] < adx_min:
            return None
        pull = (s.l[i - 1] <= ctx["ema21"][i - 1]) if st == 1 else \
               (s.h[i - 1] >= ctx["ema21"][i - 1])
        resume = (s.c[i] > s.h[i - 1] and s.c[i] > s.o[i]) if st == 1 else \
                 (s.c[i] < s.l[i - 1] and s.c[i] < s.o[i])
        if not (pull and resume):
            return None
        px, d = s.c[i], stop_atr * a
        return {"side": st, "stop": px - st * d, "target": px + st * rr * d,
                "meta": {"atr": a, "rr": rr, "adx": ctx["adx"][i]}}
    return sig


def capped_target_trap(s: Series, htf_factor=4, tp_cap=6.0, tp_floor=4.0,
                       sl_floor=2.5, session=(7, 20)):
    """DELIBERATELY BROKEN CONTROL STRATEGY — do not trade this.

    Identical entries to `ema_pullback`, but the target is capped at a fixed
    price distance while the stop scales with ATR. As volatility rises the
    reward:risk collapses toward 0.3, so the system needs a ~75% win rate just
    to break even. Kept in the library as a regression test: if a future
    'improvement' ever scores near this, something has gone wrong.
    """
    gate = htf_trend(s, htf_factor)

    def sig(ctx, i):
        a = ctx["atr"][i]; med = ctx["atr_med"][i]
        if a is None or med is None or med <= 0:
            return None
        if not (0.5 * med <= a <= 2.5 * med):
            return None
        if session and not (session[0] <= hour_utc(s.ts[i]) < session[1]):
            return None
        e9, e21, e50 = ctx["ema9"][i], ctx["ema21"][i], ctx["ema50"][i]
        pdi, mdi = ctx["pdi"][i], ctx["mdi"][i]
        st = 1 if (e9 > e21 > e50 and pdi > mdi) else (-1 if (e9 < e21 < e50 and mdi > pdi) else 0)
        if st == 0 or st != gate[i]:
            return None
        resume = (s.c[i] > s.h[i - 1] and s.c[i] > s.o[i]) if st == 1 else \
                 (s.c[i] < s.l[i - 1] and s.c[i] < s.o[i])
        if not resume:
            return None
        px = s.c[i]
        sl_d = max(sl_floor, 1.2 * a)
        tp_d = min(tp_cap, max(tp_floor, 2.0 * a))      # <-- the trap
        return {"side": st, "stop": px - st * sl_d, "target": px + st * tp_d,
                "meta": {"atr": a, "rr": tp_d / sl_d}}
    return sig


REGISTRY = {
    "liquidity_sweep": liquidity_sweep,
    "donchian_trend": donchian_trend,
    "ema_pullback": ema_pullback,
    "capped_target_trap": capped_target_trap,
}


# ===================== ADDITIONAL HYPOTHESES (cross-market tests) ===========
def tsmom(s: Series, lookback=50, rr=3.0, stop_atr=2.0):
    """TIME-SERIES MOMENTUM — the most replicated systematic edge in finance
    (Moskowitz, Ooi & Pedersen 2012). Rule: if price is above where it was
    `lookback` bars ago, be long; below, be short. Nothing else.

    Included because it is nearly parameter-free and has decades of published
    out-of-sample evidence at the daily/monthly scale. The open question this
    tests is whether it survives INTRADAY, where costs bite.
    """
    def sig(ctx, i):
        a = ctx["atr"][i]
        if a is None or a <= 0 or i <= lookback:
            return None
        past = s.c[i - lookback]
        st = 1 if s.c[i] > past else -1
        # only act on the bar the state FLIPS, otherwise it re-enters endlessly
        prev = 1 if s.c[i - 1] > s.c[i - 1 - lookback] else -1
        if st == prev:
            return None
        px, d = s.c[i], stop_atr * a
        return {"side": st, "stop": px - st * d, "target": px + st * rr * d,
                "meta": {"atr": a, "rr": rr}}
    return sig


def ma_cross(s: Series, fast="ema20", slow="ema100", rr=3.0, stop_atr=2.0):
    """Moving-average crossover. The oldest trend rule there is, and a fair
    baseline: if a new idea cannot beat this, it has not earned its complexity."""
    def sig(ctx, i):
        a = ctx["atr"][i]
        if a is None or a <= 0:
            return None
        now = 1 if ctx[fast][i] > ctx[slow][i] else -1
        prev = 1 if ctx[fast][i - 1] > ctx[slow][i - 1] else -1
        if now == prev:
            return None
        px, d = s.c[i], stop_atr * a
        return {"side": now, "stop": px - now * d, "target": px + now * rr * d,
                "meta": {"atr": a, "rr": rr}}
    return sig


def mean_revert(s: Series, dev=2.5, rr=1.5, stop_atr=2.0, ma="ema50"):
    """MEAN REVERSION — fade price stretched `dev` x ATR from a moving average,
    targeting a move back toward it. The natural opposite of trend following.

    Tested because trend and mean reversion cannot both be right in the same
    regime, and knowing which one gold actually rewards is worth more than
    assuming.
    """
    def sig(ctx, i):
        a = ctx["atr"][i]
        if a is None or a <= 0:
            return None
        m = ctx[ma][i]
        stretch = (s.c[i] - m) / a
        st = 0
        if stretch >= dev:
            st = -1
        elif stretch <= -dev:
            st = 1
        if st == 0:
            return None
        prev = (s.c[i - 1] - ctx[ma][i - 1]) / (ctx["atr"][i - 1] or a)
        if (st == -1 and prev >= dev) or (st == 1 and prev <= -dev):
            return None                       # only on the bar it first stretches
        px, d = s.c[i], stop_atr * a
        return {"side": st, "stop": px - st * d, "target": px + st * rr * d,
                "meta": {"atr": a, "rr": rr}}
    return sig


def orb(s: Series, open_hour=7, range_bars=2, rr=2.0, stop_atr=1.0):
    """OPENING RANGE BREAKOUT. Define a range in the first `range_bars` bars
    after `open_hour` UTC (London), then trade a break of it that session.

    Session effects are one of the better-documented intraday regularities, so
    this tests whether gold's London open carries any.
    """
    def sig(ctx, i):
        a = ctx["atr"][i]
        if a is None or a <= 0:
            return None
        h = hour_utc(s.ts[i])
        start = open_hour + range_bars
        if not (start <= h < start + 4):      # only trade the hours after the range
            return None
        lo_i = i - (h - open_hour)
        if lo_i < 1:
            return None
        hi = max(s.h[lo_i:lo_i + range_bars]) if lo_i + range_bars <= i else None
        lo = min(s.l[lo_i:lo_i + range_bars]) if lo_i + range_bars <= i else None
        if hi is None or lo is None or hi <= lo:
            return None
        st = 1 if s.c[i] > hi else (-1 if s.c[i] < lo else 0)
        if st == 0:
            return None
        px, d = s.c[i], stop_atr * a
        return {"side": st, "stop": px - st * d, "target": px + st * rr * d,
                "meta": {"atr": a, "rr": rr}}
    return sig


REGISTRY.update({
    "tsmom": tsmom,
    "ma_cross": ma_cross,
    "mean_revert": mean_revert,
    "orb": orb,
})


def minimal_trend(s: Series, don=55, ema_f="ema50", ema_s="ema200",
                  stop_atr=2.5, rr=4.0):
    """
    MINIMAL TREND — 5 parameters, against the old EA's 748.

    PRE-REGISTERED. Every choice below was fixed BEFORE running it, from
    lessons already recorded, so this is a single honest test rather than
    another search. Searching would raise the multiple-testing bar again
    (E-012/E-013); one pre-specified test does not.

    Design, and the evidence behind each choice:
      * trend filter EMA50/EMA200   - trend following is the most replicated
                                      systematic edge (E-011)
      * Donchian-55 breakout entry  - simplest objective trend entry
      * stop 2.5 x ATR (wide)       - E-013: wider stops beat tight ones on
                                      every setting swept
      * target 4R (large)           - E-013: larger targets beat small ones
      * NO break-even, NO trailing  - E-008: early break-even was the WORST
                                      exit rule on all four markets
      * no session filter, no ADX, no confidence score, no volatility band
                                    - each would be a parameter that has not
                                      earned its place

    This is the shape a rebuild should take. It is NOT a recommendation to
    trade: it must still clear the multiple-testing bar and work on more than
    one market.
    """
    def sig(ctx, i):
        a = ctx["atr"][i]
        if a is None or a <= 0:
            return None
        hi = max(s.h[i - don:i]) if i >= don else None
        lo = min(s.l[i - don:i]) if i >= don else None
        if hi is None or lo is None:
            return None
        up = ctx[ema_f][i] > ctx[ema_s][i]
        st = 1 if (up and s.c[i] > hi) else (-1 if (not up and s.c[i] < lo) else 0)
        if st == 0:
            return None
        px, d = s.c[i], stop_atr * a
        return {"side": st, "stop": px - st * d, "target": px + st * rr * d,
                "meta": {"atr": a, "rr": rr}}
    return sig


REGISTRY["minimal_trend"] = minimal_trend


def sweep_continuation(s: Series, pivot_n=3, stop_atr=1.0, rr=2.0,
                       min_strength=0.0, window=6):
    """
    SWEEP CONTINUATION — trade WITH the liquidity break, not against it.

    From E-017/E-018: fading sweeps loses to a coin flip on every market
    tested (44.5% vs 49.2% on GOLD 15m), while following the break wins on
    5 of 5 markets and beats a plain 20-bar breakout by ~3 points.

    The mechanism is Osler's stop cascade, not the retail reversal narrative:
    a stop-loss to sell IS a market sell, so a cluster of stops beyond a level
    is fuel in the direction of the break.

    Signal fires at the DECISION BAR — the first bar at which the sweep was
    classifiable — and the engine fills at the next bar's open. Levels carry an
    explicit confirmation lag (a pivot with N bars either side is unknowable
    until N bars later), so nothing is credited to a bar that could not have
    known it.

    Four parameters. The EA this replaces had 748.
    """
    import sweeps as _sw
    levels = _sw.find_levels(s, pivot_n=pivot_n)
    events = _sw.detect_sweeps(s, levels, pivot_n=pivot_n, window=window,
                               min_strength=min_strength)
    # decision_bar -> (side, level price). side is FLIPPED to follow the break.
    book = {}
    for e in events:
        if e.side == 0:
            continue
        book.setdefault(e.decision_bar, (-e.side, e.level.price, e.stype))

    def sig(ctx, i):
        hit = book.get(i)
        if not hit:
            return None
        side, lvl, stype = hit
        a = ctx["atr"][i]
        if a is None or a <= 0:
            return None
        px = s.c[i]
        d = stop_atr * a
        return {"side": side, "stop": px - side * d, "target": px + side * rr * d,
                "meta": {"atr": a, "rr": rr, "sweep_type": stype, "level": lvl}}
    return sig


REGISTRY["sweep_continuation"] = sweep_continuation


def expansion_filter(ctx, i, max_squeeze=1.15, max_adx=25):
    """
    THE TRADE SELECTION FILTER (from E-019).

    Veer's problem: "we catch every mini trend... we never know if they are
    small or massive." This answers it. Measured on GOLD 15m AND 1h, over two
    independent periods, with near-identical results:

        ADX 0-15   -> 90-91% chance of a 3+ ATR move in the next 40 bars
        ADX >= 40  -> 66-68%
        ATR >= 2x its own median -> 25%

    The logic is volatility contraction preceding expansion: when ATR is
    already stretched and ADX is already high, the move has ALREADY happened
    and you are buying the end of it. When the market is quiet, the move is
    still ahead.

    This predicts move SIZE, not DIRECTION. It is a filter on when to act,
    not a signal.
    """
    a, m, adx = ctx["atr"][i], ctx["atr_med"][i], ctx["adx"][i]
    if a is None or m is None or m <= 0:
        return False
    return (a / m) <= max_squeeze and adx <= max_adx


def filtered(base_factory, **filt):
    """Wrap any strategy so it only fires when the expansion filter passes."""
    def make(s, **kw):
        inner = base_factory(s, **kw)
        def sig(ctx, i):
            if not expansion_filter(ctx, i, **filt):
                return None
            return inner(ctx, i)
        return sig
    return make


def supertrend_dir(s: Series, atr_len=7, mult=1.2):
    """
    SuperTrend direction per bar: -1 bullish, +1 bearish (Pine convention).

    Implemented to match ta.supertrend(mult, atr_len) and the MQL5 rebuild, so
    all three agree. The carry-forward rule on the final bands is what makes a
    SuperTrend a SuperTrend rather than a plain band — without it the line
    whipsaws on every bar.
    """
    from engine import atr as _atr
    A = _atr(s, atr_len)
    n = len(s)
    fu = [None] * n
    fl = [None] * n
    d = [0] * n
    for i in range(n):
        a = A[i]
        if a is None or a <= 0:
            continue
        mid = (s.h[i] + s.l[i]) / 2.0
        bu, bl = mid + mult * a, mid - mult * a
        if i == 0 or fu[i - 1] is None:
            fu[i], fl[i] = bu, bl
            d[i] = -1 if s.c[i] > bu else 1
            continue
        pu, pl_, pc = fu[i - 1], fl[i - 1], s.c[i - 1]
        fu[i] = bu if (bu < pu or pc > pu) else pu
        fl[i] = bl if (bl > pl_ or pc < pl_) else pl_
        d[i] = d[i - 1]
        if d[i - 1] == 1 and s.c[i] > fu[i]:
            d[i] = -1
        elif d[i - 1] == -1 and s.c[i] < fl[i]:
            d[i] = 1
    return d, fu, fl


def dema(vals, n):
    """DEMA = 2*EMA(n) - EMA(EMA(n)). Matches the Pine f_dema."""
    e1 = ema(vals, n)
    e2 = ema([v if v is not None else vals[0] for v in e1], n)
    return [None if (a is None or b is None) else 2 * a - b for a, b in zip(e1, e2)]


def supertrend_sniper(s: Series, atr_len=7, mult=1.2, dema_len=200,
                      use_dema=True, stop_atr=1.5, rr=3.0):
    """
    THE ACTUAL STRATEGY THE EA IMPLEMENTS — SuperTrend(7, 1.2) + DEMA filter.

    This had never been tested in this engine. Every prior experiment measured
    something else (Donchian, MA cross, sweeps), so the EA was written on an
    unmeasured signal. Correcting that is the point of this function.

    Entry on the SuperTrend flip, optionally filtered by DEMA slope, exactly as
    the Pine and the MQL5 do. Stop and target from ATR so it is comparable with
    everything else already measured.
    """
    from engine import atr as _atr
    d, fu, fl = supertrend_dir(s, atr_len, mult)
    A = _atr(s, atr_len)
    D = dema(s.c, dema_len) if use_dema else None

    def sig(ctx, i):
        if i < 3 or d[i] == 0 or d[i - 1] == 0:
            return None
        flip_up = d[i] == -1 and d[i - 1] == 1
        flip_dn = d[i] == 1 and d[i - 1] == -1
        if not (flip_up or flip_dn):
            return None
        a = A[i]
        if a is None or a <= 0:
            return None
        if use_dema and D is not None:
            dn, dp = D[i], D[i - 2]
            if dn is None or dp is None:
                return None
            if flip_up and dn < dp:
                return None
            if flip_dn and dn > dp:
                return None
        side = 1 if flip_up else -1
        px, dist = s.c[i], stop_atr * a
        return {"side": side, "stop": px - side * dist,
                "target": px + side * rr * dist,
                "meta": {"atr": a, "rr": rr}}
    return sig


REGISTRY["supertrend_sniper"] = supertrend_sniper

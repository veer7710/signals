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

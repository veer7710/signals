"""
ict.py -- the mechanical primitives every ICT/SMC model is assembled from,
written so each one is a single, testable, look-ahead-free function.

The point of splitting them out is that the models in the literature are all
the SAME four or five pieces in different orders:

    liquidity level  ->  sweep of it  ->  structure shift  ->  entry at an
    imbalance (FVG / order block / OTE) inside a time window

so if the pieces are right, every named model is a few lines of composition,
and the ones that disagree can be run side by side on identical bars.

Every function returns arrays aligned to d, and every value at index i is
computable from bars <= i. Anything that needs a bar in the future is NaN or
False until that bar exists.
"""
import numpy as np
import core, sessions as S

# ----------------------------------------------------------- swing structure

def swings(d, left=2, right=2):
    """Confirmed swing points. A swing high at i is only KNOWN at i+right,
    so `conf_at` is what a live system may use. Returns arrays of index."""
    n = d["n"]; h, l = d["h"], d["l"]
    sh = np.zeros(n, bool); sl = np.zeros(n, bool)
    for i in range(left, n - right):
        if h[i] == max(h[i-left:i+right+1]) and h[i] > h[i-1]: sh[i] = True
        if l[i] == min(l[i-left:i+right+1]) and l[i] < l[i-1]: sl[i] = True
    return sh, sl

def last_swing_series(d, left=2, right=2):
    """For every bar, the price and index of the most recent CONFIRMED swing
    high and swing low. Confirmation is delayed by `right` bars -- that delay
    is the honest cost of using swings at all and is not skipped here."""
    n = d["n"]; sh, sl = swings(d, left, right)
    SH = np.full(n, np.nan); SL = np.full(n, np.nan)
    SHi = np.full(n, -1, int); SLi = np.full(n, -1, int)
    ch = np.nan; cl = np.nan; chi = -1; cli = -1
    for i in range(n):
        j = i - right                      # the bar whose swing status is now known
        if j >= 0:
            if sh[j]: ch, chi = d["h"][j], j
            if sl[j]: cl, cli = d["l"][j], j
        SH[i], SL[i], SHi[i], SLi[i] = ch, cl, chi, cli
    return SH, SL, SHi, SLi

# --------------------------------------------------------------- liquidity

def equal_levels(d, left=2, right=2, tol_atr=0.10, lookback=50):
    """Equal highs / equal lows -- the resting liquidity ICT actually names.
    Two confirmed swings within tol_atr of each other. Returns, per bar, the
    nearest live EQH above and EQL below, or NaN."""
    n = d["n"]; a = core.atr(d, 14); sh, sl = swings(d, left, right)
    EQH = np.full(n, np.nan); EQL = np.full(n, np.nan)
    hs = []; ls = []
    for i in range(n):
        j = i - right
        if j >= 0:
            if sh[j]: hs.append((j, d["h"][j]))
            if sl[j]: ls.append((j, d["l"][j]))
        if np.isnan(a[i]) or a[i] <= 0: continue
        tol = tol_atr * a[i]
        rec_h = [p for k, p in hs if i - k <= lookback]
        rec_l = [p for k, p in ls if i - k <= lookback]
        best = np.nan
        for x in range(len(rec_h)):
            for y in range(x + 1, len(rec_h)):
                if abs(rec_h[x] - rec_h[y]) <= tol:
                    lvl = max(rec_h[x], rec_h[y])
                    if lvl > d["c"][i] and (np.isnan(best) or lvl < best): best = lvl
        EQH[i] = best
        best = np.nan
        for x in range(len(rec_l)):
            for y in range(x + 1, len(rec_l)):
                if abs(rec_l[x] - rec_l[y]) <= tol:
                    lvl = min(rec_l[x], rec_l[y])
                    if lvl < d["c"][i] and (np.isnan(best) or lvl > best): best = lvl
        EQL[i] = best
    return EQH, EQL

def sweep_of(d, level, dirn, close_back=True, pierce_atr=0.0):
    """A sweep of `level` (a per-bar array) on bar i: the bar TRADES THROUGH
    the level and CLOSES back on the original side. dirn=+1 means a sweep of
    a level ABOVE (a buy-side raid, which sets up a SELL).

    close_back=False turns this into a plain breach, which is how some sources
    define it. Both are kept because the two definitions disagree constantly
    and the difference is worth measuring rather than assuming."""
    n = d["n"]; a = core.atr(d, 14)
    out = np.zeros(n, bool)
    for i in range(n):
        lv = level[i]
        if np.isnan(lv) or np.isnan(a[i]): continue
        p = pierce_atr * a[i]
        if dirn > 0:
            if d["h"][i] > lv + p and (not close_back or d["c"][i] < lv): out[i] = True
        else:
            if d["l"][i] < lv - p and (not close_back or d["c"][i] > lv): out[i] = True
    return out

# ------------------------------------------------------- structure shift

def mss(d, left=2, right=2):
    """Market structure shift / CHoCH, in the one definition that is actually
    codeable: a CLOSE beyond the most recent confirmed swing in the opposite
    direction. +1 = shifted up, -1 = shifted down, 0 = nothing.

    The literature has at least three competing definitions (close vs wick,
    last swing vs last MAJOR swing, with or without a displacement
    requirement). This is the close-based one; `displacement_mss` below is the
    stricter variant, and they are tested against each other rather than one
    being assumed correct."""
    n = d["n"]; SH, SL, _, _ = last_swing_series(d, left, right)
    out = np.zeros(n, np.int8)
    for i in range(n):
        if not np.isnan(SH[i]) and d["c"][i] > SH[i]: out[i] = 1
        elif not np.isnan(SL[i]) and d["c"][i] < SL[i]: out[i] = -1
    return out

def displacement_mss(d, left=2, right=2, k=1.5, n_med=50):
    """MSS that also required a displacement candle -- ICT's own wording is
    that the break must be 'energetic'. Quantified as a body at least k times
    the median body of the last n_med bars, because 'energetic' is not a rule."""
    m = mss(d, left, right)
    body = np.abs(d["c"] - d["o"])
    med = np.full(d["n"], np.nan)
    for i in range(n_med, d["n"]):
        med[i] = np.median(body[i-n_med:i])
    ok = body >= k * med
    return np.where(ok, m, 0).astype(np.int8)

# ------------------------------------------------------------- imbalances

def fvg_zones(d, min_atr=0.0):
    """Fair value gaps as (formed_at, lo, hi, dir). A bullish FVG exists when
    low[i] > high[i-2]; it is only KNOWN once bar i has closed, so formed_at
    is i and no earlier."""
    a = core.atr(d, 14); out = []
    for i in range(2, d["n"]):
        if np.isnan(a[i]) or a[i] <= 0: continue
        if d["l"][i] > d["h"][i-2]:
            g = d["l"][i] - d["h"][i-2]
            if g >= min_atr * a[i]: out.append((i, d["h"][i-2], d["l"][i], 1))
        elif d["h"][i] < d["l"][i-2]:
            g = d["l"][i-2] - d["h"][i]
            if g >= min_atr * a[i]: out.append((i, d["h"][i], d["l"][i-2], -1))
    return out

def order_blocks(d, left=2, right=2, k=1.5, n_med=50):
    """The last opposite-colour candle before a displacement move that breaks
    structure. Returns (formed_at, lo, hi, dir) -- formed_at is the bar the
    BREAK happened on, not the OB candle, because that is when it is known."""
    n = d["n"]; m = displacement_mss(d, left, right, k, n_med); out = []
    for i in range(n):
        if m[i] == 0: continue
        want_down = m[i] > 0          # bullish break -> last DOWN candle
        for j in range(i, max(-1, i - 12), -1):
            down = d["c"][j] < d["o"][j]
            if down == want_down:
                out.append((i, d["l"][j], d["h"][j], int(m[i]))); break
    return out

def ote(lo, hi, dirn, a=0.62, b=0.79):
    """Optimal Trade Entry band of a leg. For a BUY (dirn=+1) the leg ran from
    lo to hi and the band is the 62-79% RETRACEMENT of it, i.e. measured down
    from the high."""
    rng = hi - lo
    if rng <= 0: return (np.nan, np.nan)
    return (hi - b * rng, hi - a * rng) if dirn > 0 else (lo + a * rng, lo + b * rng)

# --------------------------------------------------------------- composition

def sweep_mss_entries(d, f, level_hi, level_lo, *, window=None, confirm=8,
                      use_displacement=True, left=2, right=2,
                      close_back=True, pierce_atr=0.0):
    """THE core SMC entry, and the one nearly every named model reduces to:

        1. price sweeps a liquidity level
        2. within `confirm` bars, structure shifts AGAINST the sweep
        3. enter on the shift bar's close (acted on at the next open by the
           harness, per R1)

    `window` is a killzone name from sessions.KZ, or None for no time filter.
    Returns [(signal_bar, direction)]. Direction is OPPOSITE the sweep: a raid
    of buy-side liquidity is a SELL setup.
    """
    n = d["n"]
    m = displacement_mss(d, left, right) if use_displacement else mss(d, left, right)
    sw_hi = sweep_of(d, level_hi, +1, close_back, pierce_atr)   # -> SELL
    sw_lo = sweep_of(d, level_lo, -1, close_back, pierce_atr)   # -> BUY
    ok = S.in_window(f, window) if window else np.ones(n, bool)
    sig = []
    pend_hi = -1; pend_lo = -1
    for i in range(n):
        if sw_hi[i]: pend_hi = i
        if sw_lo[i]: pend_lo = i
        if pend_hi >= 0 and i - pend_hi <= confirm and m[i] == -1 and ok[i]:
            sig.append((i, -1)); pend_hi = -1; pend_lo = -1
        elif pend_lo >= 0 and i - pend_lo <= confirm and m[i] == 1 and ok[i]:
            sig.append((i, 1)); pend_hi = -1; pend_lo = -1
    return sig

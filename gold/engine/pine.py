"""
Pine-exact transcription of the indicators used by XAUUSD CLEAN.

Reference (TradingView's own published ta.supertrend implementation):

    pine_supertrend(factor, atrPeriod) =>
        src = hl2
        atr = ta.atr(atrPeriod)
        upperBand = src + factor * atr
        lowerBand = src - factor * atr
        prevLowerBand = nz(lowerBand[1])
        prevUpperBand = nz(upperBand[1])
        lowerBand := lowerBand > prevLowerBand or close[1] < prevLowerBand ? lowerBand : prevLowerBand
        upperBand := upperBand < prevUpperBand or close[1] > prevUpperBand ? upperBand : prevUpperBand
        int direction = na
        float superTrend = na
        prevSuperTrend = superTrend[1]
        if na(atr[1])
            direction := 1
        else if prevSuperTrend == prevUpperBand
            direction := close > upperBand ? -1 : 1
        else
            direction := close < lowerBand ? 1 : -1
        superTrend := direction == -1 ? lowerBand : upperBand
        [superTrend, direction]

DIRECTION CONVENTION: -1 == uptrend (superTrend sits below price, on lowerBand).
The Pine signal is therefore:  buy = dir==-1 and dir[1]==1 ;  sell = dir==1 and dir[1]==-1

Pine semantics replicated deliberately:
  * ta.tr(true) uses high-low on the first bar (previous close is na).
  * ta.rma(src,n) is na until bar n-1, where it seeds with SMA(src,n), then
    rma[i] = (rma[i-1]*(n-1) + src[i]) / n.
  * nz(x) -> 0.0, and ANY comparison involving na is False.
  * the band-ratchet comparison uses the PREVIOUS bar's finalised bands, while the
    direction test uses the CURRENT bar's freshly-ratcheted bands.
"""
import numpy as np

NA = np.nan


def pine_tr(high, low, close):
    """ta.tr(true) — first bar falls back to high-low because close[1] is na."""
    n = len(close)
    tr = np.empty(n, dtype=float)
    tr[0] = high[0] - low[0]
    if n > 1:
        pc = close[:-1]
        tr[1:] = np.maximum.reduce([high[1:] - low[1:],
                                    np.abs(high[1:] - pc),
                                    np.abs(low[1:] - pc)])
    return tr


def pine_rma(src, length):
    """ta.rma — na for bars < length-1, SMA seed at length-1, Wilder thereafter."""
    n = len(src)
    out = np.full(n, NA, dtype=float)
    if n < length or length < 1:
        return out
    out[length - 1] = float(np.mean(src[:length]))
    inv = 1.0 / length
    acc = out[length - 1]
    for i in range(length, n):
        acc = acc + inv * (src[i] - acc)          # == (acc*(n-1)+src)/n
        out[i] = acc
    return out


def pine_atr(high, low, close, length):
    return pine_rma(pine_tr(high, low, close), length)


def pine_ema(src, length):
    """ta.ema — na until length-1, SMA seed, then alpha=2/(n+1)."""
    n = len(src)
    out = np.full(n, NA, dtype=float)
    if n < length or length < 1:
        return out
    out[length - 1] = float(np.mean(src[:length]))
    a = 2.0 / (length + 1.0)
    acc = out[length - 1]
    for i in range(length, n):
        acc = a * src[i] + (1.0 - a) * acc
        out[i] = acc
    return out


def pine_dema(src, length):
    """2*EMA - EMA(EMA). Plotted only in CLEAN rebuilt; not a signal gate."""
    e1 = pine_ema(src, length)
    valid = ~np.isnan(e1)
    e2 = np.full(len(src), NA, dtype=float)
    if valid.any():
        first = int(np.argmax(valid))
        inner = pine_ema(e1[first:], length)
        e2[first:] = inner
    return 2.0 * e1 - e2


def pine_supertrend(high, low, close, factor, atr_period):
    """Returns (supertrend_level, direction). direction: -1 uptrend, +1 downtrend."""
    n = len(close)
    atr = pine_atr(high, low, close, atr_period)
    src = (np.asarray(high, dtype=float) + np.asarray(low, dtype=float)) / 2.0

    st = np.full(n, NA, dtype=float)
    direction = np.zeros(n, dtype=np.int8)
    upper_hist = np.full(n, NA, dtype=float)
    lower_hist = np.full(n, NA, dtype=float)

    prev_lb = 0.0          # nz(lowerBand[1]) on bar 0
    prev_ub = 0.0          # nz(upperBand[1]) on bar 0
    prev_st = NA

    for i in range(n):
        a = atr[i]
        if a != a:                       # na
            lb = NA
            ub = NA
        else:
            lb = src[i] - factor * a
            ub = src[i] + factor * a

        pc = close[i - 1] if i > 0 else NA

        # lowerBand := lb > prevLowerBand or close[1] < prevLowerBand ? lb : prevLowerBand
        cond_l = (lb == lb and lb > prev_lb) or (pc == pc and pc < prev_lb)
        new_lb = lb if cond_l else prev_lb
        # upperBand := ub < prevUpperBand or close[1] > prevUpperBand ? ub : prevUpperBand
        cond_u = (ub == ub and ub < prev_ub) or (pc == pc and pc > prev_ub)
        new_ub = ub if cond_u else prev_ub

        atr_prev_na = (i == 0) or (atr[i - 1] != atr[i - 1])
        if atr_prev_na:
            d = 1
        elif prev_st == prev_ub:         # prevSuperTrend == prevUpperBand, both as Pine sees them
            d = -1 if close[i] > new_ub else 1
        else:
            d = 1 if close[i] < new_lb else -1

        cur_st = new_lb if d == -1 else new_ub

        st[i] = cur_st
        direction[i] = d
        lower_hist[i] = new_lb
        upper_hist[i] = new_ub

        # CRITICAL: Pine reads prevLowerBand/prevUpperBand through nz(), which turns a
        # na carry into 0.0 on EVERY bar. Carrying the na forward instead makes every
        # later comparison False (na comparisons are always False), so the band can
        # never pick up a real value again and the two-band Supertrend silently
        # degenerates into a single-band crossover. That bug flipped ~197x/day instead
        # of ~8x/day. Caught by engine/parity_check.py.
        prev_lb = new_lb if new_lb == new_lb else 0.0
        prev_ub = new_ub if new_ub == new_ub else 0.0
        prev_st = cur_st

    return st, direction, upper_hist, lower_hist


def clean_signals(high, low, close, factor=1.2, atr_period=7):
    """
    The CLEAN rebuilt signal. Returns (dir, buy, sell, st).
    buy/sell are True on the CLOSED bar where the flip confirmed.
    """
    st, d, _, _ = pine_supertrend(high, low, close, factor, atr_period)
    buy = np.zeros(len(close), dtype=bool)
    sell = np.zeros(len(close), dtype=bool)
    buy[1:] = (d[1:] == -1) & (d[:-1] == 1)
    sell[1:] = (d[1:] == 1) & (d[:-1] == -1)
    return d, buy, sell, st


def ea_supertrend_windowed(high, low, close, factor, atr_period, window):
    """
    The EA's version: rebuilt from scratch each bar from a fixed `window` of bars,
    re-seeding direction on the oldest bar with  d = (close >= hl2) ? 1 : -1.
    Used only to MEASURE the parity defect vs the full-history Pine chain.
    Returns direction per bar (NaN-free int array; 0 where not computable).
    """
    n = len(close)
    out = np.zeros(n, dtype=np.int8)
    atr_full = pine_atr(high, low, close, atr_period)
    src = (np.asarray(high, float) + np.asarray(low, float)) / 2.0
    for end in range(n):
        s = end - window + 1
        if s < 0 or atr_full[s] != atr_full[s]:
            continue
        up = dn = 0.0
        d = 0
        for i in range(s, end + 1):
            a = atr_full[i]
            bu = src[i] - factor * a
            bd = src[i] + factor * a
            if i == s:
                up, dn = bu, bd
                d = 1 if close[i] >= src[i] else -1
            else:
                pc = close[i - 1]
                up = max(bu, up) if pc > up else bu
                dn = min(bd, dn) if pc < dn else bd
                if d == 1 and close[i] < up:
                    d = -1
                elif d == -1 and close[i] > dn:
                    d = 1
        out[end] = d
    return out


# ---------------------------------------------------------------- self-test
def _selftest():
    rng = np.random.default_rng(7)
    n = 3000
    # deterministic trend + cycle + noise, gold-like scale
    t = np.arange(n)
    mid = 4000 + 0.01 * t + 25 * np.sin(t / 90.0) + np.cumsum(rng.normal(0, 0.12, n))
    rngbar = np.abs(rng.normal(0, 0.5, n)) + 0.15
    high = mid + rngbar
    low = mid - rngbar
    close = mid + rng.normal(0, 0.2, n)
    close = np.clip(close, low, high)

    atr = pine_atr(high, low, close, 7)
    assert np.isnan(atr[:6]).all(), "ATR must be na for bars 0..n-2"
    assert not np.isnan(atr[6]), "ATR must seed at bar length-1"
    assert abs(atr[6] - np.mean(pine_tr(high, low, close)[:7])) < 1e-12, "ATR seed must equal SMA(tr,7)"
    # Wilder recursion check
    tr = pine_tr(high, low, close)
    assert abs(atr[7] - (atr[6] * 6 + tr[7]) / 7) < 1e-12, "Wilder step wrong"

    d, buy, sell, st = clean_signals(high, low, close, 1.2, 7)

    assert set(np.unique(d)).issubset({1, -1}), "direction must be +/-1 only"

    # invariant: in an uptrend the line sits at or below price; downtrend at or above
    ok_up = np.where((d == -1) & ~np.isnan(st))[0]
    ok_dn = np.where((d == 1) & ~np.isnan(st))[0]
    ok_up = ok_up[ok_up > 7]
    ok_dn = ok_dn[ok_dn > 7]
    assert (st[ok_up] <= close[ok_up] + 1e-9).all(), "uptrend line must be <= close"
    assert (st[ok_dn] >= close[ok_dn] - 1e-9).all(), "downtrend line must be >= close"

    # invariant: signals strictly alternate, and each coincides with a direction change
    sig_idx = np.where(buy | sell)[0]
    kinds = np.where(buy[sig_idx], 1, -1)
    assert (np.diff(kinds) != 0).all(), "signals must alternate buy/sell"
    assert (d[sig_idx] != d[sig_idx - 1]).all(), "every signal must sit on a direction change"
    assert (buy & sell).sum() == 0, "a bar cannot be both"

    # invariant: within a sustained trend the line ratchets monotonically (never loosens)
    worst = 0.0
    for a, b in zip(sig_idx[:-1], sig_idx[1:]):
        seg = st[a:b]
        if len(seg) < 3:
            continue
        if d[a] == -1:
            worst = min(worst, float(np.min(np.diff(seg))))   # should be >= 0
        else:
            worst = min(worst, float(-np.max(np.diff(seg))))
    assert worst > -1e-9, f"band ratchet loosened within a trend by {worst}"

    print(f"selftest OK  bars={n}  signals={len(sig_idx)}  "
          f"buys={int(buy.sum())} sells={int(sell.sum())}  "
          f"median_leg_bars={int(np.median(np.diff(sig_idx)))}")
    print(f"  ATR(7) mean={np.nanmean(atr):.3f}  band_dist=1.2*ATR mean={1.2*np.nanmean(atr):.3f}")


if __name__ == "__main__":
    _selftest()

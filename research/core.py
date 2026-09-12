"""
core.py -- data, indicators, fills, metrics.

Design rules enforced here (each one exists because getting it wrong
produces a backtest that looks good and loses money live):

  R1  No look-ahead. A signal computed from bar i is acted on at bar i+1's
      OPEN. Never at bar i's close.
  R2  A stop or a limit can never fill BETTER than its level. If a bar gaps
      through, it fills at that bar's open.
  R3  If a bar's range contains both the stop and the target, the STOP wins.
      Intrabar path is unknown; assume the bad one.
  R4  Costs are charged on every round trip, in price units, always.
  R5  Everything reported in PRICE POINTS as well as R. Expectancy in R
      flatters small stops.
"""
import json, math
import numpy as np

# ---------------------------------------------------------------- data

def load(symbol, tf, path="data"):
    rows = json.load(open(f"{path}/{symbol}_{tf}.json"))
    a = np.array(rows, dtype=np.float64)
    return dict(t=a[:, 0].astype(np.int64), o=a[:, 1], h=a[:, 2],
                l=a[:, 3], c=a[:, 4], n=len(a))

def resample(d, factor):
    """Aggregate `factor` bars into one. Only ever COARSENS (15m->30m etc).
    Drops a ragged tail so every output bar is complete."""
    n = d["n"] // factor * factor
    t = d["t"][:n].reshape(-1, factor)
    o = d["o"][:n].reshape(-1, factor)
    h = d["h"][:n].reshape(-1, factor)
    l = d["l"][:n].reshape(-1, factor)
    c = d["c"][:n].reshape(-1, factor)
    return dict(t=t[:, 0], o=o[:, 0], h=h.max(1), l=l.min(1), c=c[:, -1],
                n=n // factor)

# ---------------------------------------------------------- indicators

def rma(x, n):
    """Wilder's smoothing -- what Pine's ta.rma and MQL5's iATR both use.
    Seeded with an SMA so Pine / MQL5 / here agree bar for bar."""
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    out[n - 1] = x[:n].mean()
    a = 1.0 / n
    for i in range(n, len(x)):
        out[i] = out[i - 1] + a * (x[i] - out[i - 1])
    return out

def true_range(h, l, c):
    tr = np.empty(len(h))
    tr[0] = h[0] - l[0]
    tr[1:] = np.maximum(h[1:] - l[1:],
                        np.maximum(np.abs(h[1:] - c[:-1]),
                                   np.abs(l[1:] - c[:-1])))
    return tr

def atr(d, n=14):
    return rma(true_range(d["h"], d["l"], d["c"]), n)

def ema(x, n):
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    out[n - 1] = x[:n].mean()
    a = 2.0 / (n + 1)
    for i in range(n, len(x)):
        out[i] = out[i - 1] + a * (x[i] - out[i - 1])
    return out

def supertrend(d, period=10, mult=3.0):
    """Standard SuperTrend. Returns (dir, line) where dir is +1 long / -1 short.
    dir[i] is known at the CLOSE of bar i -> tradable at open of i+1."""
    a = atr(d, period)
    hl2 = (d["h"] + d["l"]) / 2.0
    up = hl2 - mult * a          # lower band (support in an uptrend)
    dn = hl2 + mult * a          # upper band (resistance in a downtrend)
    n = d["n"]
    fu = np.full(n, np.nan); fd = np.full(n, np.nan)
    dirn = np.zeros(n, dtype=np.int8)
    c = d["c"]
    for i in range(n):
        if np.isnan(a[i]):
            continue
        if np.isnan(fu[i - 1]) if i > 0 else True:
            fu[i], fd[i], dirn[i] = up[i], dn[i], 1
            continue
        fu[i] = max(up[i], fu[i - 1]) if c[i - 1] > fu[i - 1] else up[i]
        fd[i] = min(dn[i], fd[i - 1]) if c[i - 1] < fd[i - 1] else dn[i]
        if dirn[i - 1] == 1:
            dirn[i] = -1 if c[i] < fu[i] else 1
        else:
            dirn[i] = 1 if c[i] > fd[i] else -1
    line = np.where(dirn == 1, fu, fd)
    return dirn, line

def efficiency_ratio(c, n=20):
    """Kaufman ER: |net move| / sum|bar moves| over n bars.
    ~1.0 = clean trend, ~0.0 = chop. This is a REGIME classifier, not a
    leg-start marker -- a different claim from the SMC patterns."""
    out = np.full(len(c), np.nan)
    d1 = np.abs(np.diff(c, prepend=c[0]))
    for i in range(n, len(c)):
        denom = d1[i - n + 1:i + 1].sum()
        out[i] = abs(c[i] - c[i - n]) / denom if denom > 0 else 0.0
    return out

def adx(d, n=14):
    h, l, c = d["h"], d["l"], d["c"]
    up = np.diff(h, prepend=h[0]); dn = -np.diff(l, prepend=l[0])
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    a = rma(true_range(h, l, c), n)
    with np.errstate(invalid="ignore", divide="ignore"):
        pdi = 100 * rma(pdm, n) / a
        mdi = 100 * rma(mdm, n) / a
        dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    return rma(np.nan_to_num(dx), n), pdi, mdi

# ------------------------------------------------------ market structure

def pivots(d, left=3, right=3):
    """Fractal swing points. A pivot at i is only CONFIRMED at i+right, so
    confirm_idx is what any non-repainting system is allowed to use."""
    h, l, n = d["h"], d["l"], d["n"]
    ph = np.zeros(n, dtype=bool); pl = np.zeros(n, dtype=bool)
    for i in range(left, n - right):
        w = slice(i - left, i + right + 1)
        if h[i] == h[w].max() and (h[w] == h[i]).sum() == 1: ph[i] = True
        if l[i] == l[w].min() and (l[w] == l[i]).sum() == 1: pl[i] = True
    return ph, pl

def build_pools(d, left=3, right=3, max_live=3, tol_atr=0.10):
    """Liquidity pools = confirmed swing highs/lows, newest first, capped at
    `max_live` per side.

    Two rules that the handover says decide whether this works at all:
      - CONSUME a pool once it is run. One event per level, not one per bar
        that happens to touch it.
      - Only the nearest `max_live` pools are eligible. Scanning forty levels
        makes 'a level was run' true on most bars, which is the same as no
        signal at all.
    Equal highs/lows within tol_atr are merged into one pool (that is what
    makes a pool a pool rather than a single wick)."""
    ph, pl = pivots(d, left, right)
    a = atr(d, 14)
    n = d["n"]
    highs, lows = [], []          # live pools: dict(level, born, hits)
    out = [None] * n              # snapshot of live pools at each bar
    for i in range(n):
        # pools born from a pivot confirmed `right` bars ago
        j = i - right
        if j >= left:
            tol = (a[i] if not np.isnan(a[i]) else 0) * tol_atr
            if ph[j]:
                lv = d["h"][j]
                m = next((p for p in highs if abs(p["level"] - lv) <= tol), None)
                if m: m["level"] = max(m["level"], lv); m["hits"] += 1
                else: highs.insert(0, dict(level=lv, born=j, hits=1))
            if pl[j]:
                lv = d["l"][j]
                m = next((p for p in lows if abs(p["level"] - lv) <= tol), None)
                if m: m["level"] = min(m["level"], lv); m["hits"] += 1
                else: lows.insert(0, dict(level=lv, born=j, hits=1))
        # nearest-N eligibility, measured from current close
        highs.sort(key=lambda p: p["level"] - d["c"][i])
        lows.sort(key=lambda p: d["c"][i] - p["level"])
        highs[:] = [p for p in highs if p["level"] > d["c"][i]][:max_live]
        lows[:] = [p for p in lows if p["level"] < d["c"][i]][:max_live]
        out[i] = (list(highs), list(lows))
    return out

def sweeps(d, pools, pierce_atr=0.05):
    """A RUN of a pool: price pierces it by >= pierce_atr*ATR and CLOSES BACK
    INSIDE. A close beyond is a BREAK -- a different event, not this one.
    Returns sig[i] in {0,+1,-1}: +1 = low pool swept (bullish reversal cue).
    The pool is consumed on the bar it is run."""
    a = atr(d, 14); n = d["n"]
    sig = np.zeros(n, dtype=np.int8)
    lvl = np.full(n, np.nan); depth = np.full(n, np.nan)
    consumed = set()
    for i in range(n):
        if np.isnan(a[i]) or a[i] <= 0: continue
        pe = pierce_atr * a[i]
        hp, lp = pools[i]
        for p in lp:
            k = ("L", round(p["level"], 4))
            if k in consumed: continue
            if d["l"][i] <= p["level"] - pe and d["c"][i] > p["level"]:
                sig[i] = 1; lvl[i] = p["level"]
                depth[i] = (p["level"] - d["l"][i]) / a[i]
                consumed.add(k); break
        if sig[i] == 0:
            for p in hp:
                k = ("H", round(p["level"], 4))
                if k in consumed: continue
                if d["h"][i] >= p["level"] + pe and d["c"][i] < p["level"]:
                    sig[i] = -1; lvl[i] = p["level"]
                    depth[i] = (d["h"][i] - p["level"]) / a[i]
                    consumed.add(k); break
    return sig, lvl, depth

def fvg(d, min_atr=0.0):
    """Fair value gap: bar i-2 high < bar i low (bullish) or inverse.
    Confirmed at bar i. Included so its score can be MEASURED, not assumed."""
    a = atr(d, 14); n = d["n"]
    sig = np.zeros(n, dtype=np.int8)
    for i in range(2, n):
        if np.isnan(a[i]) or a[i] <= 0: continue
        g = min_atr * a[i]
        if d["l"][i] - d["h"][i - 2] > g: sig[i] = 1
        elif d["l"][i - 2] - d["h"][i] > g: sig[i] = -1
    return sig

def displacement(d, k=1.5, n_med=50):
    """Bar range >= k * median range. The 'big candle' Veer says the EA
    fires on. Flagged so we can measure what entering on it costs."""
    rng = d["h"] - d["l"]; n = d["n"]
    out = np.zeros(n, dtype=bool)
    for i in range(n_med, n):
        m = np.median(rng[i - n_med:i])
        if m > 0 and rng[i] >= k * m: out[i] = True
    return out


def sweep_engine(d, left=3, right=3, max_live=3, tol_atr=0.10,
                 pierce_atr=0.05, buf=24):
    """Single forward pass -- pools and sweeps together, exactly the way
    LiquidityEngine.mq5 and LIQUIDITY_ENGINE.pine run: state is carried
    bar to bar, never snapshotted.

    (An earlier version of this built a list of per-bar snapshots and stored
    a REFERENCE to the same mutable list on every bar, so every snapshot
    showed the final buffer state. It measured 48 sweeps on two different
    datasets -- 24 highs + 24 lows consumed once each -- which is what that
    class of bug looks like from the outside.)

    RULE 1  a pool is consumed when it is run: one event per level.
    RULE 2  only the nearest `max_live` pools are ELIGIBLE on a given bar.
            Eligibility, not deletion -- price moves and a pool can become
            eligible again.
    A run = pierce by pierce_atr*ATR and CLOSE BACK INSIDE. A close beyond
    is a break, and is not this event.
    """
    ph, pl = pivots(d, left, right)
    a = atr(d, 14)
    n = d["n"]
    highs, lows = [], []
    sig = np.zeros(n, dtype=np.int8)
    wick = np.full(n, np.nan)
    for i in range(n):
        if np.isnan(a[i]) or a[i] <= 0:
            continue
        tol = a[i] * tol_atr
        j = i - right
        if j >= left:
            if ph[j]:
                lv = d["h"][j]
                if highs and abs(highs[-1]["level"] - lv) <= tol:
                    highs[-1]["level"] = max(highs[-1]["level"], lv)
                    highs[-1]["hits"] += 1
                else:
                    highs.append(dict(level=lv, hits=1, used=False))
                    if len(highs) > buf: highs.pop(0)
            if pl[j]:
                lv = d["l"][j]
                if lows and abs(lows[-1]["level"] - lv) <= tol:
                    lows[-1]["level"] = min(lows[-1]["level"], lv)
                    lows[-1]["hits"] += 1
                else:
                    lows.append(dict(level=lv, hits=1, used=False))
                    if len(lows) > buf: lows.pop(0)

        c = d["c"][i]
        pe = pierce_atr * a[i]
        dl = sorted(c - p["level"] for p in lows if not p["used"] and p["level"] < c)
        lo_cut = dl[min(max_live - 1, len(dl) - 1)] if dl else 0.0
        if lo_cut > 0:
            for p in lows:
                if p["used"]: continue
                dd = c - p["level"]
                if dd <= 0 or dd > lo_cut: continue
                if d["l"][i] <= p["level"] - pe and c > p["level"]:
                    p["used"] = True; sig[i] = 1; wick[i] = d["l"][i]; break
        if sig[i] == 0:
            dh = sorted(p["level"] - c for p in highs if not p["used"] and p["level"] > c)
            hi_cut = dh[min(max_live - 1, len(dh) - 1)] if dh else 0.0
            if hi_cut > 0:
                for p in highs:
                    if p["used"]: continue
                    dd = p["level"] - c
                    if dd <= 0 or dd > hi_cut: continue
                    if d["h"][i] >= p["level"] + pe and c < p["level"]:
                        p["used"] = True; sig[i] = -1; wick[i] = d["h"][i]; break
    return sig, wick

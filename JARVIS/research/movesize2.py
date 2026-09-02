"""
E-064 — AT THE MOMENT A SUPERTREND FLIP FIRES, CAN YOU TELL A TINY MOVE FROM A
        HUGE ONE?

Veer, verbatim: "we catch 30-40 trends a day yes and thats all we need they
move anywhere from 0.1 to 20-30 points easily and thats the thing we wanna be
able to either make a smaller loss or capture as much profit as we can".

That is a *conditional forecasting* question, not a strategy question:

    HYPOTHESIS  At the bar a SuperTrend(7,1.2)+DEMA flip fires, information
    available from bars already CLOSED separates flips whose subsequent
    maximum favourable excursion is large (>= 4 ATR) from those whose MFE is
    tiny (< 0.5 ATR), by more than the same information separates them at
    randomly chosen bars.

    MECHANISM CLAIMED  a flip that occurs on an expanding-range bar closing at
    its extreme, in a market that has been coiling (ATR7/ATR50 low, efficiency
    ratio low) and that has just swept a swing point, is a flip where a large
    resting order imbalance has just been released, and released imbalance
    travels further than noise.

WHY THE RANDOM ARM IS THE WHOLE STUDY (E-050)
Volatility clustering is already CONFIRMED here (E-038, E-019): ANY bar in an
expanding market is followed by a bigger move than any bar in a dead market.
So a feature that "predicts move size" at flips may be predicting nothing
about the flip at all - it may just be reading the volatility regime, which
you could read at any bar whatsoever, without a signal. The only way to tell
those apart is to run the identical table at RANDOM bars with a RANDOM side
and see whether the separation survives the removal of the signal.
Everything the random arm also achieves is E-038, not a discovery.

THE OUTCOME
    MFE(N) = max over bars i+1..i+N of  side * (extreme - fill)  /  ATR14(i)
    fill   = open of bar i+1 moved against us by half-spread + slippage
             (the engine's own fill rule - the trade never sees a better price)
Bucketed: tiny < 0.5 ATR | small 0.5-1.5 | medium 1.5-4 | large 4+.
N tested: 20, 50, 120.

THE FEATURES - every one computed only from bars CLOSED at or before bar i.
There is a machine check of that claim: `verify_no_lookahead()` rebuilds every
feature from the TRUNCATED series s[0..i] and asserts the values are identical.
If a feature ever peeked at bar i+1 the truncated rebuild would differ.

Run:  python3 JARVIS/research/movesize2.py verify        (look-ahead check)
      python3 JARVIS/research/movesize2.py GOLD 1h       (one market, detail)
      python3 JARVIS/research/movesize2.py ALL           (the cross-market run)
"""
from __future__ import annotations
import math, os, random, sys, datetime as dt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies, study
from engine import Series

COMBOS = [("GOLD", "1h"), ("GOLD", "15m"),
          ("EURUSD", "1h"), ("EURUSD", "15m"),
          ("GBPUSD", "1h"), ("GBPUSD", "15m"),
          ("US500", "1h"), ("US500", "15m")]

HORIZONS = [20, 50, 120]
PRIMARY_H = 50            # pre-registered primary horizon
LARGE = 4.0               # ATR units
TINY = 0.5
MIN_CELL = 25             # a bucket smaller than this is not reported

# feature key, bucket edges, printed label
FEATURES = [
    ("barrange",  [0, 1.0, 1.5, 2.2, 3.2, 1e9], "flip bar range / ATR (displacement)"),
    ("closepos",  [0, .35, .6, .85, 1e9],       "close position in flip bar range (1 = closed at the extreme in trade direction)"),
    ("bodyfrac",  [0, .3, .5, .7, 1e9],         "body / range of the flip bar"),
    ("atrratio",  [0, .8, 1.0, 1.25, 1.6, 1e9], "ATR(7) / ATR(50)  (<1 = volatility contracting)"),
    ("er20",      [0, .10, .20, .35, .55, 1e9], "Kaufman efficiency ratio, 20 bars"),
    ("er50",      [0, .08, .15, .25, .40, 1e9], "Kaufman efficiency ratio, 50 bars"),
    ("runbars",   [0, 5, 15, 40, 100, 1e9],     "bars since the last opposite signal (run age, E-052)"),
    ("runmove",   [0, 1, 2, 4, 8, 1e9],         "distance travelled in this run, ATR (E-052)"),
    ("stretch",   [-1e9, -1, 0, 1, 2.5, 1e9],   "signed distance from DEMA200 in ATR (+ = already extended the trade's way)"),
    ("pos100",    [0, .25, .5, .75, .9, 1e9],   "position in the last 100 bars' range, trade-direction adjusted"),
    ("adx",       [0, 15, 20, 25, 35, 1e9],     "ADX at the flip"),
    ("adxslope",  [-1e9, -1, 1, 1e9],           "ADX minus ADX 3 bars ago (falling / flat / rising)"),
    ("swept",     [0, 1, 1e9],                  "flip bar took out the previous swing point (0 = no, 1 = sweep)"),
    ("hour",      [0, 4, 8, 12, 16, 20, 1e9],   "hour of day, UTC"),
    ("nflip20",   [0, 2, 3, 5, 1e9],            "SuperTrend flips in the last 20 bars (whipsaw density)"),
]


# --------------------------------------------------------------- helpers
def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def _pivots(s: Series, left=2, right=2):
    """Most recent CONFIRMED swing high / low as of each bar.

    A pivot centred at bar k is only confirmed once bar k+right has closed, so
    the arrays are filled at index k+right and never earlier. That is the
    entire anti-look-ahead argument for this feature.
    """
    n = len(s)
    hi = [None] * n
    lo = [None] * n
    cur_h = cur_l = None
    for i in range(n):
        k = i - right
        if k - left >= 0:
            w = range(k - left, k + right + 1)
            if all(s.h[k] >= s.h[j] for j in w):
                cur_h = s.h[k]
            if all(s.l[k] <= s.l[j] for j in w):
                cur_l = s.l[k]
        hi[i] = cur_h
        lo[i] = cur_l
    return hi, lo


def precompute(s: Series):
    """Every per-bar quantity the features need. All causal."""
    ctx = engine.build_context(s)
    a7 = engine.atr(s, 7)
    a50 = engine.atr(s, 50)
    d, _, _ = strategies.supertrend_dir(s, 7, 1.2)
    dema = strategies.dema(s.c, 200)
    # cumulative absolute close-to-close path, for the efficiency ratio
    path = [0.0] * len(s)
    for i in range(1, len(s)):
        path[i] = path[i - 1] + abs(s.c[i] - s.c[i - 1])
    swh, swl = _pivots(s)
    # flips in the trailing 20 bars
    flip = [0] * len(s)
    for i in range(1, len(s)):
        flip[i] = 1 if (d[i] != 0 and d[i - 1] != 0 and d[i] != d[i - 1]) else 0
    cflip = [0] * len(s)
    for i in range(1, len(s)):
        cflip[i] = cflip[i - 1] + flip[i]
    return {"ctx": ctx, "a7": a7, "a50": a50, "dir": d, "dema": dema,
            "path": path, "swh": swh, "swl": swl, "cflip": cflip}


def features_at(s: Series, P, i, side, runbars, runmove):
    """All features for bar i, a trade in direction `side`.

    READS ONLY: s.o/h/l/c[<= i] and arrays whose value at index i depends only
    on bars <= i. Nothing here indexes i+1 or later.
    """
    ctx = P["ctx"]
    a = ctx["atr"][i]
    if a is None or a <= 0:
        return None
    rng = s.h[i] - s.l[i]
    if rng <= 0:
        rng = 1e-9
    cp = (s.c[i] - s.l[i]) / rng
    if side == -1:
        cp = 1.0 - cp
    a7, a50 = P["a7"][i], P["a50"][i]
    if not a7 or not a50 or a50 <= 0:
        return None

    def er(n):
        if i < n:
            return 0.0
        net = abs(s.c[i] - s.c[i - n])
        p = P["path"][i] - P["path"][i - n]
        return (net / p) if p > 0 else 0.0

    dm = P["dema"][i]
    if dm is None:
        return None
    lo100 = min(s.l[max(0, i - 99):i + 1])
    hi100 = max(s.h[max(0, i - 99):i + 1])
    pos = (s.c[i] - lo100) / (hi100 - lo100) if hi100 > lo100 else 0.5
    if side == -1:
        pos = 1.0 - pos
    swh, swl = P["swh"][i], P["swl"][i]
    if side == 1:
        swept = 1 if (swl is not None and s.l[i] < swl) else 0
    else:
        swept = 1 if (swh is not None and s.h[i] > swh) else 0
    adx = ctx["adx"][i] or 0.0
    adx3 = ctx["adx"][i - 3] or 0.0
    j = max(0, i - 20)
    return {
        "barrange": rng / a,
        "closepos": cp,
        "bodyfrac": abs(s.c[i] - s.o[i]) / rng,
        "atrratio": a7 / a50,
        "er20": er(20),
        "er50": er(50),
        "runbars": runbars,
        "runmove": runmove,
        "stretch": side * (s.c[i] - dm) / a,
        "pos100": pos,
        "adx": adx,
        "adxslope": adx - adx3,
        "swept": swept,
        "hour": dt.datetime.fromtimestamp(s.ts[i], dt.timezone.utc).hour,
        "nflip20": P["cflip"][i] - P["cflip"][j],
    }


def mfe(s: Series, P, i, side, costs, horizons):
    """Forward maximum favourable excursion, in ATR(14)-at-signal units, from
    the engine's own fill (open of i+1 moved against us). THE ONLY PLACE THIS
    FILE LOOKS FORWARD, and it is the outcome, never an input."""
    a = P["ctx"]["atr"][i]
    half = costs.spread / 2.0
    fill = s.o[i + 1] + side * (half + costs.slippage)
    out = {}
    best = -1e18
    hmax = max(horizons)
    for n, j in enumerate(range(i + 1, min(i + 1 + hmax, len(s))), start=1):
        ex = s.h[j] if side == 1 else s.l[j]
        best = max(best, side * (ex - fill))
        if n in horizons:
            out[n] = best / a
    return out if len(out) == len(horizons) else None


def bucket_of(v, edges):
    for bi, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
        if lo <= v < hi:
            return bi
    return None


def label(lo, hi, unit=""):
    if lo <= -1e8:
        return f"<{hi:g}{unit}"
    if hi >= 1e8:
        return f"{lo:g}+{unit}"
    return f"{lo:g}-{hi:g}{unit}"


# ------------------------------------------------------------- collection
def collect_signals(s: Series, P, costs, warmup=300):
    """One row per SuperTrend Sniper EA signal."""
    sig = strategies.supertrend_sniper_ea(s)
    ctx = P["ctx"]
    rows = []
    last_side, run_start = 0, warmup
    for i in range(warmup, len(s) - 1):
        sg = sig(ctx, i)
        if not sg:
            continue
        side = sg["side"]
        if side != last_side:
            run_start = i
        last_side = side
        a = ctx["atr"][i]
        if a is None or a <= 0:
            continue
        runmove = abs(s.c[i] - s.c[run_start]) / a if run_start < i else 0.0
        f = features_at(s, P, i, side, i - run_start, runmove)
        if f is None:
            continue
        m = mfe(s, P, i, side, costs, HORIZONS)
        if m is None:
            continue
        f["i"] = i
        f["side"] = side
        f["ts"] = s.ts[i]
        for n in HORIZONS:
            f[f"mfe{n}"] = m[n]
        rows.append(f)
    return rows


def collect_random(s: Series, P, costs, count, seed, warmup=300):
    """THE CONTROL. Identical features, identical outcome, at randomly chosen
    bars with a randomly chosen side. No signal anywhere in it.

    run age / run distance are measured against the same gated-signal stream so
    the feature means the same thing; everything else is bar-local.
    """
    rng = random.Random(seed)
    sig = strategies.supertrend_sniper_ea(s)
    ctx = P["ctx"]
    # the signal stream, so run age is defined the same way at a random bar
    starts = []
    last_side, run_start = 0, warmup
    for i in range(warmup, len(s) - 1):
        sg = sig(ctx, i)
        if sg:
            if sg["side"] != last_side:
                run_start = i
            last_side = sg["side"]
        starts.append((i, run_start, last_side))
    smap = {i: (rs, ls) for i, rs, ls in starts}

    hi = len(s) - max(HORIZONS) - 2
    if hi <= warmup:
        return []
    rows = []
    tries = 0
    while len(rows) < count and tries < count * 40:
        tries += 1
        i = rng.randrange(warmup, hi)
        side = 1 if rng.random() < 0.5 else -1
        a = ctx["atr"][i]
        if a is None or a <= 0:
            continue
        rs, _ = smap.get(i, (i, 0))
        runmove = abs(s.c[i] - s.c[rs]) / a if rs < i else 0.0
        f = features_at(s, P, i, side, i - rs, runmove)
        if f is None:
            continue
        m = mfe(s, P, i, side, costs, HORIZONS)
        if m is None:
            continue
        f["i"] = i
        f["side"] = side
        f["ts"] = s.ts[i]
        for n in HORIZONS:
            f[f"mfe{n}"] = m[n]
        rows.append(f)
    return rows


# ------------------------------------------------------------ look-ahead
def verify_no_lookahead(symbol="GOLD", tf="1h", n_check=12):
    """Rebuild every feature from the TRUNCATED series s[0..i] and compare.

    If any feature read a bar after i, the truncated rebuild could not produce
    the same number. Wilder/EMA recursions are seeded from bar 0 in both runs,
    so they are identical by construction; the things this genuinely tests are
    the pivot confirmation lag, the rolling windows, the flip counter and the
    efficiency ratio.
    """
    s = engine.load(symbol, tf)
    costs = study.COSTS.get(symbol, engine.Costs())
    P = precompute(s)
    rows = collect_signals(s, P, costs)
    if not rows:
        print("no signals to check")
        return False
    step = max(1, len(rows) // n_check)
    checked = bad = 0
    for r in rows[::step][:n_check]:
        i = r["i"]
        sub = Series(s.ts[:i + 1], s.o[:i + 1], s.h[:i + 1],
                     s.l[:i + 1], s.c[:i + 1])
        P2 = precompute(sub)
        f2 = features_at(sub, P2, i, r["side"], r["runbars"], r["runmove"])
        checked += 1
        for k in FEATURES:
            key = k[0]
            v1, v2 = r[key], f2[key]
            if abs(v1 - v2) > 1e-9 * max(1.0, abs(v1)):
                print(f"  LOOK-AHEAD at bar {i}: {key} full={v1!r} truncated={v2!r}")
                bad += 1
    print(f"\n  LOOK-AHEAD CHECK  {symbol} {tf}: rebuilt all "
          f"{len(FEATURES)} features from truncated series at {checked} "
          f"signal bars.")
    print(f"  mismatches: {bad}   -> {'PASS' if bad == 0 else 'FAIL'}")
    return bad == 0


# ---------------------------------------------------------------- reports
def dist(rows, h):
    """Distribution over the four MFE buckets."""
    k = f"mfe{h}"
    n = len(rows)
    if n == 0:
        return (0, 0, 0, 0, 0)
    t = sum(1 for r in rows if r[k] < TINY)
    sm = sum(1 for r in rows if TINY <= r[k] < 1.5)
    md = sum(1 for r in rows if 1.5 <= r[k] < LARGE)
    lg = sum(1 for r in rows if r[k] >= LARGE)
    return (n, t / n, sm / n, md / n, lg / n)


def single_market(symbol, tf):
    s = engine.load(symbol, tf)
    costs = study.COSTS.get(symbol, engine.Costs())
    P = precompute(s)
    rows = collect_signals(s, P, costs)
    ctrl = collect_random(s, P, costs, len(rows), seed=0)
    d0 = dt.datetime.fromtimestamp(s.ts[0], dt.timezone.utc).date()
    d1 = dt.datetime.fromtimestamp(s.ts[-1], dt.timezone.utc).date()
    print("=" * 96)
    print(f"  E-064  MOVE SIZE AT THE FLIP — {symbol} {tf}   "
          f"{len(s)} bars   {d0} -> {d1}")
    print("=" * 96)
    print(f"\n  {len(rows)} SuperTrend Sniper EA signals.  "
          f"MFE measured in ATR(14)-at-signal units from the engine fill.")
    a = [P["ctx"]["atr"][r["i"]] for r in rows]
    if a:
        med_atr = sorted(a)[len(a) // 2]
        print(f"  median ATR(14) at signal = {med_atr:.5f} price units, so "
              f"1 ATR = {med_atr:.3g} and 4 ATR = {4*med_atr:.3g}.")
    print(f"\n  UNCONDITIONAL MFE DISTRIBUTION (the base rates every cell "
          f"below is measured against)")
    print(f"    {'horizon':<10}{'n':>7}{'tiny<0.5':>11}{'small.5-1.5':>13}"
          f"{'med1.5-4':>11}{'LARGE4+':>10}{'median MFE':>12}")
    for h in HORIZONS:
        n, t, sm, md, lg = dist(rows, h)
        med = sorted(r[f"mfe{h}"] for r in rows)[n // 2]
        print(f"    {h:<10}{n:>7}{100*t:>10.1f}%{100*sm:>12.1f}%"
              f"{100*md:>10.1f}%{100*lg:>9.1f}%{med:>12.2f}")
    print(f"\n  SAME, AT {len(ctrl)} RANDOM BARS WITH A RANDOM SIDE (the control)")
    for h in HORIZONS:
        n, t, sm, md, lg = dist(ctrl, h)
        med = sorted(r[f"mfe{h}"] for r in ctrl)[n // 2] if n else 0
        print(f"    {h:<10}{n:>7}{100*t:>10.1f}%{100*sm:>12.1f}%"
              f"{100*md:>10.1f}%{100*lg:>9.1f}%{med:>12.2f}")

    h = PRIMARY_H
    base = dist(rows, h)[4]
    print(f"\n  CONDITIONAL P(LARGE, MFE >= {LARGE} ATR in {h} bars). "
          f"Base rate {100*base:.1f}%.  '*' = 95% interval excludes the base.")
    for key, edges, lab in FEATURES:
        print(f"\n  by {lab}")
        print(f"    {'bucket':<14}{'n':>6}{'P(large)':>10}{'95% interval':>18}"
              f"{'vs base':>9}{'P(tiny)':>10}{'med MFE':>9}")
        for lo, hi in zip(edges[:-1], edges[1:]):
            sel = [r for r in rows if lo <= r[key] < hi]
            lb = label(lo, hi)
            if len(sel) < MIN_CELL:
                print(f"    {lb:<14}{len(sel):>6}{'too few':>10}")
                continue
            k = sum(1 for r in sel if r[f"mfe{h}"] >= LARGE)
            p = k / len(sel)
            l, u = wilson(k, len(sel))
            pt = sum(1 for r in sel if r[f"mfe{h}"] < TINY) / len(sel)
            mm = sorted(r[f"mfe{h}"] for r in sel)[len(sel) // 2]
            star = " *" if (l > base or u < base) else ""
            print(f"    {lb:<14}{len(sel):>6}{100*p:>9.1f}%"
                  f"{f'{100*l:.1f}-{100*u:.1f}%':>18}{100*(p-base):>+9.1f}"
                  f"{100*pt:>9.1f}%{mm:>9.2f}{star}")
    return rows, ctrl


# ------------------------------------------------------- cross-market run
def cross_table(store, key, edges, lab, h, arm):
    """One feature, all 8 markets, cells = P(large) minus that market's own
    base rate, in percentage points."""
    labs = [label(lo, hi) for lo, hi in zip(edges[:-1], edges[1:])]
    print(f"\n  --- {key}: {lab}")
    print(f"    {'market':<14}" + "".join(f"{l:>11}" for l in labs))
    pos = [0] * len(labs)
    seen = [0] * len(labs)
    tot = [0.0] * len(labs)
    for name, arms in store.items():
        rows = arms[arm]
        if not rows:
            continue
        base = dist(rows, h)[4]
        cells = []
        for bi, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
            sel = [r for r in rows if lo <= r[key] < hi]
            if len(sel) < MIN_CELL:
                cells.append(f"{'-':>11}")
                continue
            p = sum(1 for r in sel if r[f"mfe{h}"] >= LARGE) / len(sel)
            d = 100 * (p - base)
            cells.append(f"{d:>+11.1f}")
            seen[bi] += 1
            tot[bi] += d
            if d > 0:
                pos[bi] += 1
        print(f"    {name:<14}" + "".join(cells))
    print(f"    {'ABOVE base':<14}"
          + "".join(f"{(f'{pos[b]}/{seen[b]}' if seen[b] else '-'):>11}"
                    for b in range(len(labs))))
    print(f"    {'mean pts':<14}"
          + "".join(f"{(f'{tot[b]/seen[b]:+.1f}' if seen[b] else '-'):>11}"
                    for b in range(len(labs))))
    return [(key, labs[b], pos[b], seen[b], tot[b] / seen[b] if seen[b] else 0.0)
            for b in range(len(labs))]


# ------------------------------------------------ out-of-sample separability
def auc(rows, score_key, h):
    """P(a randomly chosen LARGE-MFE row scores above a randomly chosen
    TINY-MFE row). 0.5 = the score carries no information."""
    pos = [r[score_key] for r in rows if r[f"mfe{h}"] >= LARGE]
    neg = [r[score_key] for r in rows if r[f"mfe{h}"] < TINY]
    if len(pos) < 10 or len(neg) < 10:
        return None, len(pos), len(neg)
    allv = sorted(pos + neg)
    ranks = {}
    i = 0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1] == allv[i]:
            j += 1
        r = (i + j) / 2.0 + 1
        ranks[allv[i]] = r
        i = j + 1
    rp = sum(ranks[v] for v in pos)
    u = rp - len(pos) * (len(pos) + 1) / 2.0
    return u / (len(pos) * len(neg)), len(pos), len(neg)


NUMERIC = [f[0] for f in FEATURES if f[0] not in ("hour",)]


def fit_score(train, h):
    """Dead simple, deliberately: standardise each numeric feature on the
    TRAINING rows only, give it the sign of its own training correlation with
    'was large', and sum. No weights are tuned, nothing is selected on the
    test data. A more powerful model would only make the overfitting worse."""
    mu, sd, sign = {}, {}, {}
    y = [1.0 if r[f"mfe{h}"] >= LARGE else 0.0 for r in train]
    ybar = sum(y) / len(y)
    for k in NUMERIC:
        v = [r[k] for r in train]
        m = sum(v) / len(v)
        s2 = sum((x - m) ** 2 for x in v) / max(1, len(v) - 1)
        sdv = math.sqrt(s2) or 1e-9
        mu[k], sd[k] = m, sdv
        cov = sum((v[t] - m) * (y[t] - ybar) for t in range(len(v))) / len(v)
        sign[k] = 1.0 if cov >= 0 else -1.0
    def apply(rows):
        for r in rows:
            r["score"] = sum(sign[k] * (r[k] - mu[k]) / sd[k] for k in NUMERIC)
    return apply


def oos_separability(store, h):
    """The decisive test. Fit the score on the first 70% of each market's rows,
    measure separation on the last 30% it has never seen, and do the identical
    thing to the random arm."""
    print("\n" + "=" * 96)
    print(f"  OUT-OF-SAMPLE SEPARABILITY, horizon {h} bars")
    print("  Score fitted on the first 70% of rows, scored on the last 30%.")
    print("  AUC = P(a LARGE-MFE entry outranks a TINY-MFE entry). 0.50 = no "
          "information at all.")
    print("=" * 96)
    print(f"    {'market':<14}{'arm':>9}{'n test':>8}{'nLarge':>8}{'nTiny':>7}"
          f"{'AUC':>8}{'topQ P(lg)':>12}{'botQ P(lg)':>12}{'base':>8}")
    out = {"signal": [], "random": []}
    for name, arms in store.items():
        for arm in ("signal", "random"):
            rows = sorted(arms[arm], key=lambda r: r["ts"])
            if len(rows) < 80:
                continue
            cut = int(len(rows) * 0.7)
            tr, te = rows[:cut], rows[cut:]
            apply = fit_score(tr, h)
            apply(te)
            a, np_, nn = auc(te, "score", h)
            if a is None:
                print(f"    {name:<14}{arm:>9}{len(te):>8}{np_:>8}{nn:>7}"
                      f"{'too few':>8}")
                continue
            te2 = sorted(te, key=lambda r: r["score"])
            q = max(5, len(te2) // 5)
            top = te2[-q:]
            bot = te2[:q]
            ptop = sum(1 for r in top if r[f"mfe{h}"] >= LARGE) / len(top)
            pbot = sum(1 for r in bot if r[f"mfe{h}"] >= LARGE) / len(bot)
            base = sum(1 for r in te if r[f"mfe{h}"] >= LARGE) / len(te)
            out[arm].append((a, ptop - base))
            print(f"    {name:<14}{arm:>9}{len(te):>8}{np_:>8}{nn:>7}"
                  f"{a:>8.3f}{100*ptop:>11.1f}%{100*pbot:>11.1f}%"
                  f"{100*base:>7.1f}%")
    for arm in ("signal", "random"):
        v = out[arm]
        if v:
            print(f"    {arm.upper():<14} mean AUC {sum(x[0] for x in v)/len(v):.3f}"
                  f"   AUC > 0.5 in {sum(1 for x in v if x[0] > 0.5)}/{len(v)}"
                  f"   mean topQ lift {100*sum(x[1] for x in v)/len(v):+.1f} pts")
    return out


def auc_vs_rest(rows, score_key, h):
    """LARGE versus EVERYTHING ELSE, which is the decision actually faced:
    'is this the one to hold?'. The tiny-vs-large AUC above is thin at long
    horizons because almost nothing stays under 0.5 ATR for 50 bars."""
    pos = [r[score_key] for r in rows if r[f"mfe{h}"] >= LARGE]
    neg = [r[score_key] for r in rows if r[f"mfe{h}"] < LARGE]
    if len(pos) < 10 or len(neg) < 10:
        return None, len(pos), len(neg)
    allv = sorted(pos + neg)
    ranks = {}
    i = 0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1] == allv[i]:
            j += 1
        ranks[allv[i]] = (i + j) / 2.0 + 1
        i = j + 1
    u = sum(ranks[v] for v in pos) - len(pos) * (len(pos) + 1) / 2.0
    return u / (len(pos) * len(neg)), len(pos), len(neg)


def oos_large_vs_rest(store, h):
    print("\n" + "=" * 96)
    print(f"  OUT-OF-SAMPLE: LARGE (>= {LARGE} ATR) vs EVERYTHING ELSE, "
          f"horizon {h}. 70/30 chronological split.")
    print("  Both arms get the identical fitting procedure. Only the "
          "difference between them is evidence.")
    print("=" * 96)
    print(f"    {'market':<13}{'arm':>8}{'nTest':>7}{'nLarge':>8}{'AUC':>8}"
          f"{'topQ':>9}{'botQ':>9}{'base':>8}{'lift':>8}")
    agg = {"signal": [], "random": []}
    for name, arms in store.items():
        for arm in ("signal", "random"):
            rows = sorted(arms[arm], key=lambda r: r["ts"])
            if len(rows) < 80:
                continue
            cut = int(len(rows) * 0.7)
            tr, te = rows[:cut], rows[cut:]
            fit_score(tr, h)(te)
            a, np_, nn = auc_vs_rest(te, "score", h)
            if a is None:
                print(f"    {name:<13}{arm:>8}{len(te):>7}{np_:>8}{'thin':>8}")
                continue
            te2 = sorted(te, key=lambda r: r["score"])
            q = max(5, len(te2) // 5)
            pt = sum(1 for r in te2[-q:] if r[f"mfe{h}"] >= LARGE) / q
            pb = sum(1 for r in te2[:q] if r[f"mfe{h}"] >= LARGE) / q
            base = np_ / len(te)
            agg[arm].append((a, pt - base))
            print(f"    {name:<13}{arm:>8}{len(te):>7}{np_:>8}{a:>8.3f}"
                  f"{100*pt:>8.1f}%{100*pb:>8.1f}%{100*base:>7.1f}%"
                  f"{100*(pt-base):>+8.1f}")
    for arm in ("signal", "random"):
        v = agg[arm]
        if v:
            print(f"    {arm.upper():<11} mean AUC "
                  f"{sum(x[0] for x in v)/len(v):.3f}   AUC>0.5 in "
                  f"{sum(1 for x in v if x[0] > 0.5)}/{len(v)}   mean topQ lift "
                  f"{100*sum(x[1] for x in v)/len(v):+.1f} pts")


def multiseed_control(store, key="atrratio", lo=0.0, hi=0.8, h=PRIMARY_H,
                      seeds=20):
    """One seed of a random arm is itself a coin flip. Repeat it."""
    print("\n" + "=" * 96)
    print(f"  MULTI-SEED RANDOM CONTROL for the strongest signal-arm cell: "
          f"{key} {lo:g}-{hi:g}, P(large@{h})")
    print("=" * 96)
    import statistics as _st
    res = []
    for seed in range(seeds):
        ab = se = 0
        tot = 0.0
        for name, arms in store.items():
            rows = collect_random(arms["s"], arms["P"], arms["c"],
                                  len(arms["signal"]), seed=seed)
            base = dist(rows, h)[4]
            sel = [r for r in rows if lo <= r[key] < hi]
            if len(sel) < MIN_CELL:
                continue
            p = sum(1 for r in sel if r[f"mfe{h}"] >= LARGE) / len(sel)
            se += 1
            tot += 100 * (p - base)
            if p > base:
                ab += 1
        res.append((ab, se, tot / se if se else 0.0))
        print(f"    seed {seed:>2}: {ab}/{se} markets above base, "
              f"mean {res[-1][2]:+.1f} pts")
    print(f"    ACROSS {seeds} SEEDS: median "
          f"{_st.median(x[0] for x in res):.1f}/8 above base, mean effect "
          f"{_st.mean(x[2] for x in res):+.1f} pts, range "
          f"{min(x[2] for x in res):+.1f} to {max(x[2] for x in res):+.1f}")


def denominator_check(store, key="atrratio", lo=0.0, hi=0.8, h=PRIMARY_H):
    """THE CHECK THAT KILLED THE HEADLINE.

    MFE is reported in units of ATR(14)-at-signal. atrratio = ATR(7)/ATR(50)
    is LOW exactly when short-horizon volatility, and therefore ATR(14)
    itself, is depressed relative to the market's slower level. Dividing a
    forward move by a temporarily-small denominator makes it look large
    whether or not the move is large. So re-normalise the SAME forward moves
    by ATR(50)-at-signal, which the feature does not depress, and see whether
    anything is left.
    """
    import statistics as _st
    print("\n" + "=" * 96)
    print(f"  DENOMINATOR ROBUSTNESS: is '{key} {lo:g}-{hi:g} predicts a big "
          f"move' an artifact of dividing")
    print("  MFE by ATR(14)-at-signal - a denominator this very feature helps "
          "define? Re-normalise the")
    print("  IDENTICAL forward moves by ATR(50)-at-signal, a slow denominator, "
          "and re-read the cell.")
    print("=" * 96)
    print(f"    {'market':<13}{'arm':>8}{'base/ATR14':>12}{'cell/ATR14':>12}"
          f"{'base/ATR50':>12}{'cell/ATR50':>12}")
    d14 = {"signal": [], "random": []}
    d50 = {"signal": [], "random": []}
    for name, arms in store.items():
        P = arms["P"]
        for arm in ("signal", "random"):
            rows = arms[arm]
            for r in rows:
                r["alt"] = r[f"mfe{h}"] * P["ctx"]["atr"][r["i"]] / P["a50"][r["i"]]
            b14 = sum(1 for r in rows if r[f"mfe{h}"] >= LARGE) / len(rows)
            b50 = sum(1 for r in rows if r["alt"] >= LARGE) / len(rows)
            sel = [r for r in rows if lo <= r[key] < hi]
            if len(sel) < MIN_CELL:
                continue
            c14 = sum(1 for r in sel if r[f"mfe{h}"] >= LARGE) / len(sel)
            c50 = sum(1 for r in sel if r["alt"] >= LARGE) / len(sel)
            d14[arm].append(100 * (c14 - b14))
            d50[arm].append(100 * (c50 - b50))
            print(f"    {name:<13}{arm:>8}{100*b14:>11.1f}%{100*c14:>11.1f}%"
                  f"{100*b50:>11.1f}%{100*c50:>11.1f}%")
    print()
    for lab, d in (("MFE / ATR14", d14), ("MFE / ATR50", d50)):
        print(f"    {key} {lo:g}-{hi:g} effect, {lab}:  "
              f"signal mean {_st.mean(d['signal']):+.1f} pts "
              f"({sum(1 for x in d['signal'] if x > 0)}/{len(d['signal'])} "
              f"positive)   random mean {_st.mean(d['random']):+.1f} pts "
              f"({sum(1 for x in d['random'] if x > 0)}/{len(d['random'])})")


def direction_split(store, h=PRIMARY_H):
    """GOLD is the only instrument whose signal arm beats its own random arm.
    Gold trended hard over this sample. Split by side: if the gap is longs
    only, it is the trend, not the signal."""
    print("\n" + "=" * 96)
    print(f"  LONG/SHORT SPLIT of P(large@{h}) — the gold gap, tested")
    print("=" * 96)
    print(f"    {'market':<13}{'side':<7}{'signal':>18}{'random':>18}{'gap':>8}")
    for name, arms in store.items():
        for sd, lbl in ((1, "long"), (-1, "short")):
            cells = {}
            for arm in ("signal", "random"):
                sub = [r for r in arms[arm] if r["side"] == sd]
                cells[arm] = (len(sub),
                              sum(1 for r in sub if r[f"mfe{h}"] >= LARGE) / len(sub)
                              if sub else 0.0)
            ns, ps = cells["signal"]
            nr, pr = cells["random"]
            g = 100 * (ps - pr)
            scell = f"{100*ps:.1f}% (n={ns})"
            rcell = f"{100*pr:.1f}% (n={nr})"
            print(f"    {name:<13}{lbl:<7}{scell:>18}{rcell:>18}{g:>+8.1f}")


def run_all(seed=0):
    print("=" * 96)
    print("  E-064  CAN YOU TELL A 0.1-POINT MOVE FROM A 20-POINT MOVE AT THE "
          "FLIP?")
    print(f"  Outcome: MFE in ATR(14) units. LARGE = {LARGE}+ ATR, "
          f"TINY = <{TINY} ATR.")
    print("  Every cell = P(large) MINUS that market's own base rate, in "
          "percentage points.")
    print("  A feature that works has the SAME SIGN across a whole row. Mixed "
          "signs are noise.")
    print("=" * 96)

    store = {}
    print("\n  SAMPLES AND BASE RATES")
    print(f"    {'market':<14}{'signals':>9}{'random':>8}"
          + "".join(f"{'P(lg)@'+str(h):>11}" for h in HORIZONS)
          + "".join(f"{'rnd@'+str(h):>10}" for h in HORIZONS))
    for sym, tf in COMBOS:
        s = engine.load(sym, tf)
        costs = study.COSTS.get(sym, engine.Costs())
        P = precompute(s)
        sig_rows = collect_signals(s, P, costs)
        rnd_rows = collect_random(s, P, costs, len(sig_rows), seed=seed)
        name = f"{sym} {tf}"
        store[name] = {"signal": sig_rows, "random": rnd_rows,
                       "s": s, "P": P, "c": costs}
        print(f"    {name:<14}{len(sig_rows):>9}{len(rnd_rows):>8}"
              + "".join(f"{100*dist(sig_rows,h)[4]:>10.1f}%" for h in HORIZONS)
              + "".join(f"{100*dist(rnd_rows,h)[4]:>9.1f}%" for h in HORIZONS))

    h = PRIMARY_H
    print("\n\n" + "#" * 96)
    print(f"#  ARM 1 — THE SIGNAL.  {len(FEATURES)} features at "
          f"SuperTrend flips, horizon {h} bars")
    print("#" * 96)
    cells_sig = []
    for key, edges, lab in FEATURES:
        cells_sig += cross_table(store, key, edges, lab, h, "signal")

    print("\n\n" + "#" * 96)
    print(f"#  ARM 2 — THE RANDOM CONTROL.  identical tables at RANDOM bars, "
          f"RANDOM side, matched n")
    print("#  Anything the control also achieves is volatility clustering "
          "(E-038), not signal quality.")
    print("#" * 96)
    cells_rnd = []
    for key, edges, lab in FEATURES:
        cells_rnd += cross_table(store, key, edges, lab, h, "random")

    # ---- the honest scoreboard
    print("\n\n" + "=" * 96)
    print("  SCOREBOARD — every cell with >= 7 of 8 markets on the same side, "
          "both arms")
    print("=" * 96)
    def strong(cells):
        out = []
        for key, lab, pos, seen, mean in cells:
            if seen < 6:
                continue
            if pos >= seen - 1 or pos <= 1:
                out.append((key, lab, pos, seen, mean))
        return out
    ss, sr = strong(cells_sig), strong(cells_rnd)
    print(f"\n  SIGNAL arm: {len(ss)} such cells out of "
          f"{sum(1 for c in cells_sig if c[3] >= 6)} testable")
    for key, lab, pos, seen, mean in sorted(ss, key=lambda x: -abs(x[4])):
        print(f"    {key:<12}{lab:>12}   {pos}/{seen} above base   "
              f"mean {mean:+.1f} pts")
    print(f"\n  RANDOM arm: {len(sr)} such cells out of "
          f"{sum(1 for c in cells_rnd if c[3] >= 6)} testable")
    for key, lab, pos, seen, mean in sorted(sr, key=lambda x: -abs(x[4])):
        print(f"    {key:<12}{lab:>12}   {pos}/{seen} above base   "
              f"mean {mean:+.1f} pts")

    # ---- side-by-side for the cells that survived in the signal arm
    if ss:
        print("\n  SIDE BY SIDE — does the random arm do it too?")
        print(f"    {'cell':<26}{'signal':>18}{'random':>18}")
        rmap = {(k, l): (p, s2, m) for k, l, p, s2, m in cells_rnd}
        for key, lab, pos, seen, mean in sorted(ss, key=lambda x: -abs(x[4])):
            r = rmap.get((key, lab))
            rs = f"{r[0]}/{r[1]}  {r[2]:+.1f}" if r and r[1] else "-"
            print(f"    {key+' '+lab:<26}{f'{pos}/{seen}  {mean:+.1f}':>18}{rs:>18}")

    # ---- multiple testing
    testable = sum(1 for c in cells_sig if c[3] >= 6)
    p7 = 2 * 9 / 256.0
    p8 = 2 / 256.0
    print("\n" + "=" * 96)
    print("  MULTIPLE TESTING — read this before quoting any cell above")
    print("=" * 96)
    print(f"  Feature/bucket cells examined at horizon {h}: {len(cells_sig)}; "
          f"{testable} had >= 6 markets with enough data to score.")
    print(f"  Under the null (each market a coin flip), P(a cell lands >= 7 of "
          f"8 on one side) = {100*p7:.1f}%,")
    print(f"  and P(8 of 8) = {100*p8:.2f}%. So among {testable} testable "
          f"cells the null EXPECTS about {testable*p7:.1f} cells")
    print(f"  at the 7-of-8 level and {testable*p8:.2f} at 8-of-8.")
    print(f"  Observed in the SIGNAL arm: {len(ss)}.  Observed in the RANDOM "
          f"arm: {len(sr)}.")
    print("  These markets are NOT independent (GOLD 15m overlaps GOLD 1h; "
          "EURUSD and GBPUSD correlate")
    print("  ~0.9, E-015), so the true expected count is HIGHER than the "
          "figure above, not lower.")
    print(f"  All three horizons ({HORIZONS}) were computed, which multiplies "
          f"the cell count by 3 if")
    print("  any horizon other than the pre-registered "
          f"{PRIMARY_H} is quoted.")

    # ---- horizon robustness for the surviving cells
    print("\n" + "=" * 96)
    print("  HORIZON ROBUSTNESS for the signal-arm survivors")
    print("=" * 96)
    print(f"    {'cell':<26}" + "".join(f"{'N='+str(x):>16}" for x in HORIZONS))
    for key, lab, pos, seen, mean in sorted(ss, key=lambda x: -abs(x[4])):
        cols = []
        for hh in HORIZONS:
            p2 = s2 = 0
            tt = 0.0
            for name, arms in store.items():
                rows = arms["signal"]
                base = dist(rows, hh)[4]
                edges = dict((f[0], f[1]) for f in FEATURES)[key]
                labs = [label(lo, hi) for lo, hi in zip(edges[:-1], edges[1:])]
                bi = labs.index(lab)
                lo, hi = edges[bi], edges[bi + 1]
                sel = [r for r in rows if lo <= r[key] < hi]
                if len(sel) < MIN_CELL:
                    continue
                p = sum(1 for r in sel if r[f"mfe{hh}"] >= LARGE) / len(sel)
                s2 += 1
                tt += 100 * (p - base)
                if p > base:
                    p2 += 1
            cols.append(f"{p2}/{s2}  {tt/s2:+.1f}" if s2 else "-")
        print(f"    {key+' '+lab:<26}" + "".join(f"{c:>16}" for c in cols))

    oos_separability(store, h)
    oos_large_vs_rest(store, h)
    oos_large_vs_rest(store, 20)
    multiseed_control(store)
    denominator_check(store)
    direction_split(store)

    # -- MFE in the instrument's own price units, which is how Veer states it
    print("\n" + "=" * 96)
    print("  THE SPREAD OF OUTCOMES IN PRICE POINTS (Veer's units), signal arm")
    print("  This is the size of the problem: the gap between a dud flip and a "
          "runner, before any")
    print("  attempt to predict it.")
    print("=" * 96)
    print(f"    {'market':<13}{'H':>5}{'n':>6}{'p10':>9}{'p25':>9}{'median':>9}"
          f"{'p75':>9}{'p90':>9}{'max':>10}{'p90/p10':>9}")
    for name, arms in store.items():
        P = arms["P"]
        for hh in HORIZONS:
            pts = sorted(r[f"mfe{hh}"] * P["ctx"]["atr"][r["i"]]
                         for r in arms["signal"])
            q = lambda pr: pts[int(pr * (len(pts) - 1))]
            print(f"    {name:<13}{hh:>5}{len(pts):>6}{q(.1):>9.3g}{q(.25):>9.3g}"
                  f"{q(.5):>9.3g}{q(.75):>9.3g}{q(.9):>9.3g}{pts[-1]:>10.4g}"
                  f"{q(.9)/max(q(.1),1e-9):>8.1f}x")
    return store


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "ALL"
    if arg.lower() == "verify":
        ok = verify_no_lookahead("GOLD", "1h")
        ok = verify_no_lookahead("GOLD", "15m") and ok
        sys.exit(0 if ok else 1)
    if arg.upper() == "ALL":
        run_all()
    else:
        single_market(arg, sys.argv[2] if len(sys.argv) > 2 else "1h")

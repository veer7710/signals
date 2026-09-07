"""
LEG ORIGINS — which swing extremes START a big move, and what is knowable AT it.

THIS IS NOT A P&L STUDY. Every previous study in this repo asked "does this
entry make money net of cost" and the answer was no. Veer's complaint is a
DIFFERENT one: "our signals aren't catching top to bottom or bottom to top".
He wants the CHART to mark the extremes that begin a leg worth trading; he
takes the trade himself. So the question here is a CLASSIFICATION question:

    Of all swing extremes, which ones start a large leg, and does anything
    knowable at (or within a few bars of) the extreme separate them?

PRE-REGISTRATION (fixed before any number was read)
---------------------------------------------------
* Population: every zigzag extreme on XAUUSD, k=3 fractal, on M1/M5/M15
  resampled from GOLD_M1_2018.json (the only file with a MEASURED spread).
  The vendor M5/M15 files are exact aggregations of M1 (E-165), so they are
  NOT independent samples and are never quoted as replication.
* A LEG runs from one zigzag extreme to the next opposite extreme.
* LABEL A (full leg): |terminal - origin| / ATR(14) at the origin bar.
* LABEL P (points):   |terminal - origin| in points. Label A divides by a
  quantity that is itself a feature, so `atr_pts` and `atr_regime` are inside
  it; label P has no ATR in it at all. Both are reported because they answer
  different questions and they disagree.
* LABEL B (capturable): the part still available to someone who can only act
  after the pivot is CONFIRMED, i.e. from close[p+k] to the terminal price,
  in ATR. Label B is the honest one for an indicator; label A is what "top to
  bottom" means in plain English.
* "BIG LEG" = the top 5% of legs by the label, with the cut taken from the
  FIRST HALF ONLY and applied to the second. Quantile rather than a fixed ATR
  cut so that the real sample and the null sample carry the SAME base rate --
  see THE CORRECTION below.
* FLAG TIME: a k=3 fractal pivot at bar p is not knowable until bar p+3 has
  closed. So every feature is computed from bars <= p+3 ONLY, and the
  indicator can only paint at p+3. This is stated, not hidden.
* 20 numeric features + session, listed in FEATURES below, all written down
  before any AUC was computed. 14 of them are computable ON bar p (AT_EXTREME)
  and 6 read bars p+1..p+3 (POST).
* Choose on the FIRST HALF of the sample, report on the SECOND half.
* Costs: the file's own measured spread column, in price units, unscaled.
  E-165 showed the old per-timeframe `cs` rescaling charged M5/M15 2.5-4.6x
  too much. Volume is TICK volume and is broker-dependent (E-167).

THE CORRECTION THAT THIS FILE EXISTS TO CARRY (E-170 records it)
---------------------------------------------------------------
The first run of this study caught its own defect before it was finished:

    "The null is NOT flat -- it produces lift too, because the post-extreme
     features overlap the label."

A feature measured a few bars AFTER the extreme -- displacement off the low,
the first bars' range, the volume on the way out -- PARTLY CONTAINS the leg it
is supposed to predict. On a driftless random walk it still shows lift, because
a big first move mechanically implies a bigger measured leg. Measured here:
`disp3` scores AUC 0.67-0.72 ON A RANDOM WALK. So:

  * every feature's separation is computed on the REAL data AND on the null
    with identical code, and the reported number is REAL MINUS NULL;
  * the null is 6 seeds, not 1, so the null's own sampling error is visible;
  * labels are quantiles so the two base rates match and lift-vs-lift is fair;
  * features that read bars after p are marked * and are judged only against
    the null, and only label B (which starts at close[p+3]) is clean for them;
  * the features that CANNOT overlap the label -- anything computed on bar p
    or earlier -- are the ones an indicator can actually be built from, and
    they are reported separately (`surv`).

THE NULL RUNS FIRST. A driftless random walk with the real timestamps, the
real spread column and the real volume column, through the identical code.

Usage:

    python3 JARVIS/research/leg_origins.py null
    python3 JARVIS/research/leg_origins.py dist
    python3 JARVIS/research/leg_origins.py feat
    python3 JARVIS/research/leg_origins.py pr
    python3 JARVIS/research/leg_origins.py surv
    python3 JARVIS/research/leg_origins.py lat
    python3 JARVIS/research/leg_origins.py modern
    python3 JARVIS/research/leg_origins.py trade
    python3 JARVIS/research/leg_origins.py all
"""
from __future__ import annotations
import os, sys, json, math, random, statistics, bisect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Series, atr as watr, ema, entry_fill, trail_level

DATA = "/home/user/signals/data"
TZOFF = 3600           # the 2018 feed's broker day starts at 23:00 UTC
K = 3                  # fractal half-width -> confirmation latency of 3 bars
TFMULT = {"M1": 1, "M5": 5, "M15": 15}
GBP = 0.787            # E-081: 0.01 lots on XAUUSD = GBP 0.787 per point
NULL_SEEDS = (11, 12, 13, 14, 15, 16)


# ------------------------------------------------------------------ data
def load_m1():
    rows = json.load(open(f"{DATA}/GOLD_M1_2018.json"))
    rows.sort(key=lambda r: r[0])
    out, seen = [], set()
    for r in rows:
        if r[0] in seen:
            continue
        seen.add(r[0]); out.append(r)
    s = Series([r[0] for r in out], [r[1] for r in out], [r[2] for r in out],
               [r[3] for r in out], [r[4] for r in out])
    return s, [r[5] for r in out], [r[7] for r in out]


def resample(s, sp, vol, mult):
    """Clock-aligned aggregation from M1 (reproduces the vendor files)."""
    if mult == 1:
        return s, list(sp), list(vol)
    keys, buck = [], {}
    w = 60 * mult
    for i in range(len(s)):
        k = (s.ts[i] + TZOFF) // w
        b = buck.get(k)
        if b is None:
            buck[k] = [s.ts[i], s.o[i], s.h[i], s.l[i], s.c[i], sp[i], 1, vol[i]]
            keys.append(k)
        else:
            b[2] = max(b[2], s.h[i]); b[3] = min(b[3], s.l[i])
            b[4] = s.c[i]; b[5] += sp[i]; b[6] += 1; b[7] += vol[i]
    rs = [buck[k] for k in keys]
    out = Series([r[0] for r in rs], [r[1] for r in rs], [r[2] for r in rs],
                 [r[3] for r in rs], [r[4] for r in rs])
    return out, [r[5] / r[6] for r in rs], [r[7] for r in rs]


def ndays(s):
    return len({(t + TZOFF) // 86400 for t in s.ts})


# --------------------------------------------------------------- synthetic
def synth_like(s, sp, vol, seed, ticks=120):
    """Driftless random walk on the REAL timestamps, carrying the REAL spread
    and REAL tick-volume columns. Calibrated so the median bar range matches."""
    rr = sorted(s.h[i] - s.l[i] for i in range(len(s)))
    med_rng = rr[len(rr) // 2]
    sig = med_rng / (2.0 * math.sqrt(ticks))
    for _ in range(12):
        t = _walk(s.ts[:20000], sig, ticks, seed)
        m = sorted(t.h[i] - t.l[i] for i in range(len(t)))[10000]
        sig *= (med_rng / m) ** 0.5
    out = _walk(s.ts, sig, ticks, seed)
    return out, list(sp), list(vol), med_rng


def _walk(ts, sigma_tick, ticks, seed, p0=1300.0):
    rng = random.Random(seed)
    o, h, l, c = [], [], [], []
    p = p0
    for _ in range(len(ts)):
        op = p; hi = lo = p
        for _ in range(ticks):
            p += rng.gauss(0.0, sigma_tick)
            if p > hi: hi = p
            if p < lo: lo = p
        o.append(op); h.append(hi); l.append(lo); c.append(p)
    return Series(list(ts), o, h, l, c)


# ------------------------------------------------------------------ legs
def fractals(s, k):
    """(idx, price, side). side +1 swing high, -1 swing low. Confirmed at idx+k."""
    out = []
    for p in range(k, len(s) - k):
        hi = s.h[p]; lo = s.l[p]
        ish = islo = True
        for j in range(p - k, p + k + 1):
            if j == p: continue
            if s.h[j] > hi: ish = False
            if s.l[j] < lo: islo = False
            if not ish and not islo: break
        if ish: out.append((p, hi, +1))
        if islo: out.append((p, lo, -1))
    out.sort()
    return out


def zigzag(piv):
    """Alternating extremes. Consecutive same-side pivots collapse to the
    more extreme one. Purely a function of the pivot list; no look-ahead
    beyond the k bars already needed to confirm each pivot."""
    zz = []
    for (i, px, sd) in piv:
        if zz and zz[-1][2] == sd:
            j, q, _ = zz[-1]
            if (sd == +1 and px >= q) or (sd == -1 and px <= q):
                zz[-1] = (i, px, sd)
        else:
            zz.append((i, px, sd))
    return zz


def legs(s, k):
    """[(origin_idx, origin_px, dir, term_idx, term_px)]  dir +1 = up leg."""
    zz = zigzag(fractals(s, k))
    out = []
    for a in range(len(zz) - 1):
        i0, p0, s0 = zz[a]
        i1, p1, s1 = zz[a + 1]
        out.append((i0, p0, -s0, i1, p1))   # a swing LOW (-1) starts an UP leg
    return out


# -------------------------------------------------------------- features
FEATURES = [
    "sweep_atr",      # overshoot beyond the nearest prior same-side level, ATR
    "swept",          # 1/0 did it take out any prior same-side level
    "n_swept",        # how many prior levels it took out
    "wick_atr",       # extreme bar's wick beyond its body, in ATR
    "body_frac",      # |c-o| / range of the extreme bar
    "close_pos",      # reversal-favouring close position within the extreme bar
    "disp1",          # signed move to close[p+1], ATR   (uses bars after p)
    "disp3",          # signed move to close[p+3], ATR   (uses bars after p)
    "range3",         # summed true range of p+1..p+3, ATR
    "engulf3",        # 1/0 extreme bar fully taken out within 3 bars
    "fvg3",           # 1/0 displacement gap in p+1..p+3
    "vol_ratio",      # tick volume at p / median of prior 50
    "vol_ratio3",     # mean tick volume p..p+3 / median of prior 50
    "atr_regime",     # ATR(14) at p / median ATR of prior 200
    "atr_pts",        # raw ATR(14) at p, in points
    "dist_ema200",    # (extreme - EMA200)/ATR, +ve = extended past the mean
    "took_pd",        # 1/0 extreme exceeded the prior day's high/low
    "compress",       # (max h - min l) of the 20 bars before p, in ATR
    "prior_leg_atr",  # size of the leg INTO this origin, in ATR
    "room_atr",       # distance to the nearest opposing prior level, in ATR
]


def build(s, sp, vol, mult, k=K):
    """One row per leg origin. Every feature uses bars <= p+k only."""
    A = watr(s, 14)
    E = ema(s.c, 200)
    piv = fractals(s, k)
    piv_conf = [(i + k, px, sd) for (i, px, sd) in piv]   # (available_at, px, side)
    piv_conf.sort()
    conf_idx = [x[0] for x in piv_conf]

    # prior-day high/low, available from the first bar of the next day
    dayk = [(t + TZOFF) // 86400 for t in s.ts]
    dhi, dlo = {}, {}
    for i in range(len(s)):
        d = dayk[i]
        dhi[d] = max(dhi.get(d, -1e18), s.h[i])
        dlo[d] = min(dlo.get(d, 1e18), s.l[i])

    L = legs(s, k)
    rows = []
    prev_leg_atr = None
    for (p, px, d, ti, tpx) in L:
        if p < 260 or p + k >= len(s) - 2:
            prev_leg_atr = abs(tpx - px) / (A[p] or 1e-9)
            continue
        a = A[p] or 1e-9
        f = {}

        # ---- prior confirmed levels, available strictly before bar p
        hi_end = bisect.bisect_right(conf_idx, p - 1)
        lo_start = bisect.bisect_left(conf_idx, p - 400)
        same = []      # levels on the same side as this extreme
        opp = []
        for (av, lpx, sd) in piv_conf[lo_start:hi_end]:
            if sd == -d:      # a LOW (-1) is the same side as an UP-leg origin
                same.append(lpx)
            else:
                opp.append(lpx)
        # for an up leg (d=+1) the origin is a LOW: it sweeps levels ABOVE it
        if d == +1:
            taken = [x for x in same if x > px and x - px < 4 * a]
            over = max((x - px for x in taken), default=0.0)
            up_lv = [x for x in opp if x > px]
            room = (min(up_lv) - px) / a if up_lv else float("nan")
            f["took_pd"] = 1.0 if any(px < dlo.get(dd, 1e18) for dd in (dayk[p] - 1,)) else 0.0
        else:
            taken = [x for x in same if x < px and px - x < 4 * a]
            over = max((px - x for x in taken), default=0.0)
            dn_lv = [x for x in opp if x < px]
            room = (px - max(dn_lv)) / a if dn_lv else float("nan")
            f["took_pd"] = 1.0 if any(px > dhi.get(dd, -1e18) for dd in (dayk[p] - 1,)) else 0.0
        f["sweep_atr"] = over / a
        f["swept"] = 1.0 if taken else 0.0
        f["n_swept"] = float(len(taken))
        f["room_atr"] = room

        # ---- the extreme bar's own shape
        rng = (s.h[p] - s.l[p]) or 1e-9
        f["body_frac"] = abs(s.c[p] - s.o[p]) / rng
        if d == +1:
            f["wick_atr"] = (min(s.o[p], s.c[p]) - s.l[p]) / a
            f["close_pos"] = (s.c[p] - s.l[p]) / rng
        else:
            f["wick_atr"] = (s.h[p] - max(s.o[p], s.c[p])) / a
            f["close_pos"] = (s.h[p] - s.c[p]) / rng

        # ---- the first 1-3 bars off the extreme  (uses bars p+1..p+3)
        f["disp1"] = d * (s.c[p + 1] - px) / a
        f["disp3"] = d * (s.c[p + k] - px) / a
        tr = 0.0
        for j in range(p + 1, p + k + 1):
            tr += max(s.h[j] - s.l[j], abs(s.h[j] - s.c[j - 1]), abs(s.l[j] - s.c[j - 1]))
        f["range3"] = tr / a
        eng = 0.0
        for j in range(p + 1, p + k + 1):
            if (d == +1 and s.c[j] > s.h[p]) or (d == -1 and s.c[j] < s.l[p]):
                eng = 1.0
        f["engulf3"] = eng
        fv = 0.0
        if k >= 2:
            for j in range(p + 2, p + k + 1):
                if d == +1 and s.l[j] > s.h[j - 2]: fv = 1.0
                if d == -1 and s.h[j] < s.l[j - 2]: fv = 1.0
        f["fvg3"] = fv

        # ---- volume (TICK volume; broker-dependent)
        w = sorted(vol[p - 50:p])
        mv = w[len(w) // 2] or 1.0
        f["vol_ratio"] = vol[p] / mv
        f["vol_ratio3"] = (sum(vol[p:p + k + 1]) / (k + 1.0)) / mv

        # ---- regime / context
        wa = sorted(x for x in A[p - 200:p] if x)
        f["atr_regime"] = a / (wa[len(wa) // 2] or 1e-9)
        f["atr_pts"] = a
        f["dist_ema200"] = d * (E[p] - px) / a      # +ve: extreme is beyond the EMA
        f["compress"] = (max(s.h[p - 20:p]) - min(s.l[p - 20:p])) / a
        f["prior_leg_atr"] = prev_leg_atr if prev_leg_atr is not None else float("nan")

        # ---- labels
        full_atr = abs(tpx - px) / a
        cap_atr = d * (tpx - s.c[p + k]) / a
        rows.append({
            "i": p, "k_i": p + k, "d": d, "px": px, "ti": ti, "tpx": tpx,
            "ts": s.ts[p], "hour": ((s.ts[p] + TZOFF) % 86400) // 3600,
            "atr": a, "sp": sp[p],
            "full_atr": full_atr, "cap_atr": cap_atr,
            "full_pts": abs(tpx - px), "bars": ti - p, "f": f,
        })
        prev_leg_atr = full_atr
    return rows, A


# ------------------------------------------------------------ statistics
def auc(vals, lab):
    """Mann-Whitney AUC of `vals` for separating lab==1 from lab==0."""
    pairs = [(v, y) for v, y in zip(vals, lab) if v == v]
    if not pairs: return float("nan"), 0, 0
    pairs.sort()
    n = len(pairs)
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for t in range(i, j + 1):
            ranks[t] = r
        i = j + 1
    n1 = sum(1 for _, y in pairs if y == 1)
    n0 = n - n1
    if n1 == 0 or n0 == 0: return float("nan"), n1, n0
    r1 = sum(r for r, (_, y) in zip(ranks, pairs) if y == 1)
    a = (r1 - n1 * (n1 + 1) / 2.0) / (n1 * n0)
    return a, n1, n0


def auc_z(a, n1, n0):
    if a != a or n1 == 0 or n0 == 0: return float("nan")
    se = math.sqrt((n1 + n0 + 1.0) / (12.0 * n1 * n0))
    return (a - 0.5) / se


def spearman(x, y):
    pairs = [(a, b) for a, b in zip(x, y) if a == a and b == b]
    if len(pairs) < 10: return float("nan")
    def rk(v):
        idx = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v); i = 0
        while i < len(idx):
            j = i
            while j + 1 < len(idx) and v[idx[j + 1]] == v[idx[i]]: j += 1
            rr = (i + j) / 2.0 + 1
            for t in range(i, j + 1): r[idx[t]] = rr
            i = j + 1
        return r
    rx = rk([p[0] for p in pairs]); ry = rk([p[1] for p in pairs])
    mx = sum(rx) / len(rx); my = sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")


def med(v):
    v = [x for x in v if x == x]
    return statistics.median(v) if v else float("nan")


def quart_split(rows, name, lab_key):
    """Median label in the feature's top vs bottom quartile.

    The sort key is the FEATURE ONLY. Sorting on the (value, label) tuple --
    which is what this did first -- breaks ties by the label, so any feature
    with ties (every binary one) got handed a fake separation: `swept` read
    5.46 vs 1.59 while its AUC was 0.508."""
    v = [(r["f"][name], r[lab_key]) for r in rows if r["f"][name] == r["f"][name]]
    if len(v) < 40: return float("nan"), float("nan")
    v.sort(key=lambda x: x[0])
    q = len(v) // 4
    return med([x[1] for x in v[-q:]]), med([x[1] for x in v[:q]])


# ------------------------------------------------------------------ runs
def hdr(t):
    print("\n" + "=" * 78); print("  " + t); print("=" * 78)


_CACHE = {}
_ROWS = {}


def prep(tf, synthetic=None):
    rk = (tf, synthetic)
    if rk in _ROWS:
        return _ROWS[rk]
    key = ("real" if synthetic is None else f"synth{synthetic}")
    if key not in _CACHE:
        s0, sp0, v0 = load_m1()
        if synthetic is not None:
            s0, sp0, v0, _ = synth_like(s0, sp0, v0, synthetic)
        _CACHE[key] = (s0, sp0, v0)
    s0, sp0, v0 = _CACHE[key]
    s, sp, vol = resample(s0, sp0, v0, TFMULT[tf])
    rows, A = build(s, sp, vol, TFMULT[tf])
    _ROWS[rk] = (s, sp, vol, rows)
    return _ROWS[rk]


# ------------------------------------------------------- quantile labelling
#
# WHY A QUANTILE LABEL AND NOT A FIXED ATR CUT.
# A driftless random walk makes far fewer 10-ATR legs than the real market
# (0.62% vs the real base rate), so a fixed cut compares a real AUC built on
# ~600 positives against a null AUC built on ~30. The null estimate is then so
# noisy that "real minus null" is dominated by the null's own sampling error --
# on M5 seed 11 vs seed 12 the same feature moved 0.28 of AUC. Labelling the
# top Q fraction of legs BY SIZE instead makes the two base rates identical by
# construction, so lift is compared against lift on equal terms. Both labels
# are reported; the fixed-ATR one is kept because it is what "a 10-ATR leg"
# means in English.
#
QFRAC = 0.05           # "a big leg" = the top 5% of legs on this timeframe


def qthresh(rows, key, q=QFRAC):
    v = sorted(r[key] for r in rows if r[key] == r[key])
    if not v: return float("inf")
    return v[int((1.0 - q) * len(v))]


def mklab(rows, key, thr):
    return [1 if r[key] >= thr else 0 for r in rows]


# ---------------------------------------------------------------- 1. null
def cmd_null():
    hdr("THE NULL, RUN FIRST — driftless random walk, real timestamps, "
        "real spread, real tick volume")
    s0, sp0, v0 = load_m1()
    rr = sorted(s0.h[i] - s0.l[i] for i in range(len(s0)))
    print(f"  real M1 median bar range {rr[len(rr)//2]:.4f}   "
          f"real median spread {statistics.median(sp0):.5f} points")
    for tf in ("M1", "M5"):
        for seed in (11, 12):
            s, sp, vol, rows = prep(tf, synthetic=seed)
            r2 = sorted(s.h[i] - s.l[i] for i in range(len(s)))
            thr = 10.0
            lab = [1 if r["full_atr"] >= thr else 0 for r in rows]
            base = sum(lab) / len(lab)
            print(f"\n  --- NULL {tf} seed {seed}: {len(rows)} legs, "
                  f"synth median range {r2[len(r2)//2]:.4f}, "
                  f"P(leg >= {thr:.0f} ATR) = {base:.4f}")
            out = []
            for nm in FEATURES:
                v = [r["f"][nm] for r in rows]
                a, n1, n0 = auc(v, lab)
                out.append((abs(a - 0.5) if a == a else -1, nm, a, auc_z(a, n1, n0)))
            out.sort(reverse=True)
            print("     feature        AUC(full)     z        AUC(cap)     z")
            labc = [1 if r["cap_atr"] >= thr else 0 for r in rows]
            for _, nm, a, z in out:
                v = [r["f"][nm] for r in rows]
                a2, m1, m0 = auc(v, labc)
                print(f"     {nm:<14} {a:7.4f} {z:8.2f}     {a2:7.4f} {auc_z(a2,m1,m0):8.2f}")


# ------------------------------------------------------- 2. distribution
def cmd_dist():
    hdr("LEG-SIZE DISTRIBUTION — how many 'bangers' actually exist to be caught")
    s0, sp0, v0 = load_m1()
    print(f"  GOLD_M1_2018.json  {len(s0)} M1 bars, {ndays(s0)} trading days, "
          f"2018-01-01 to 2018-06-19")
    print("  (M5/M15 are resampled from it — one sample, not three)\n")
    for tf in ("M1", "M5", "M15"):
        s, sp, vol = resample(s0, sp0, v0, TFMULT[tf])
        nd = ndays(s)
        print(f"  --- {tf}: {len(s)} bars, {nd} days, "
              f"median ATR14 {med([x for x in watr(s,14)[100:] if x]):.4f} pts, "
              f"median spread {statistics.median(sp):.4f} pts")
        for k in (2, 3, 5):
            L = legs(s, k)
            A = watr(s, 14)
            sz = [abs(tp - p) / (A[i] or 1e-9) for (i, p, d, ti, tp) in L if i > 260]
            pts = [abs(tp - p) for (i, p, d, ti, tp) in L if i > 260]
            dur = [ti - i for (i, p, d, ti, tp) in L if i > 260]
            if not sz: continue
            ss = sorted(sz)
            line = (f"    k={k}: {len(sz):6d} legs = {len(sz)/nd:6.1f}/day | "
                    f"median {ss[len(ss)//2]:5.2f} ATR / "
                    f"{sorted(pts)[len(pts)//2]:5.2f} pts, "
                    f"p90 {ss[int(.9*len(ss))]:6.2f} ATR, "
                    f"max {ss[-1]:6.1f} ATR, med dur {sorted(dur)[len(dur)//2]:3d} bars")
            print(line)
            cnt = "         legs/day >= ATR:  "
            for t in (3, 5, 10, 20, 30):
                n = sum(1 for x in sz if x >= t)
                cnt += f"{t:>2}A {n/nd:6.2f}(n={n:5d})  "
            print(cnt)
            cntp = "         legs/day >= pts:  "
            for t in (1, 2, 5, 10, 20):
                n = sum(1 for x in pts if x >= t)
                cntp += f"{t:>2}p {n/nd:6.2f}(n={n:5d})  "
            print(cntp)
            # the same thing in money at the minimum tradeable size
            zz = sorted(zip(sz, pts))
            print(f"         median leg = {GBP*sorted(pts)[len(pts)//2]:6.2f} GBP at 0.01 lots, "
                  f"p90 {GBP*sorted(pts)[int(.9*len(pts))]:6.2f}, "
                  f"p99 {GBP*sorted(pts)[int(.99*len(pts))]:7.2f}, "
                  f"max {GBP*max(pts):7.2f}; round-turn spread costs "
                  f"{GBP*statistics.median(sp):.2f} GBP")
            for t in (3, 5, 10, 20):
                sel = [p for a, p in zz if a >= t]
                if len(sel) < 5: continue
                print(f"           legs >= {t:>2} ATR: n={len(sel):5d} "
                      f"({len(sel)/nd:5.2f}/day)  median {statistics.median(sel):6.2f} pts "
                      f"= {GBP*statistics.median(sel):7.2f} GBP  "
                      f"gross/spread {statistics.median(sel)/statistics.median(sp):5.1f}x")
        print()


# -------------------------------------------------------- 3. separation
LABELS = [
    ("full_atr", "A  full leg / ATR at origin   (top-to-bottom, what Veer means)"),
    ("full_pts", "P  full leg in POINTS         (no ATR in the label at all)"),
    ("cap_atr",  "B  leg REMAINING after the fractal confirms at p+3, / ATR"),
]


def null_auc_table(tf, key, thr_mode="q", fixed=10.0):
    """Mean and spread of every feature's AUC on the driftless random walk,
    through the identical code path. Threshold picked on the null's own first
    half exactly as the real one is, so the base rates match."""
    per = {nm: [] for nm in FEATURES}
    base = []
    for seed in NULL_SEEDS:
        _, _, _, nr = prep(tf, synthetic=seed)
        nh = len(nr) // 2
        NA, NB = nr[:nh], nr[nh:]
        t = qthresh(NA, key) if thr_mode == "q" else fixed
        lb = mklab(NB, key, t)
        if sum(lb) < 10 or sum(lb) == len(lb):
            continue
        base.append(sum(lb) / len(lb))
        for nm in FEATURES:
            a, _, _ = auc([r["f"][nm] for r in NB], lb)
            if a == a:
                per[nm].append(a)
    out = {}
    for nm in FEATURES:
        v = per[nm]
        if not v:
            out[nm] = (float("nan"), float("nan"), 0)
        else:
            out[nm] = (sum(v) / len(v),
                       statistics.pstdev(v) if len(v) > 1 else float("nan"), len(v))
    return out, (sum(base) / len(base) if base else float("nan"))


def cmd_feat():
    hdr(f"FEATURE SEPARATION — REAL lift minus NULL lift, for each of 3 labels")
    print("  Selection sample = FIRST HALF. Every reported number = SECOND HALF (unseen).")
    print("  'big leg' = the top 5% of legs by that label, threshold taken from the")
    print("  FIRST half only. The same quantile is used on the null, so the two base")
    print("  rates are identical and AUC-vs-AUC is a fair comparison.")
    print()
    print("  LABELS")
    for k, d in LABELS:
        print(f"    {d}")
    print()
    print("  COLUMNS  is    = AUC on the first half (selection)")
    print("           oos   = AUC on the unseen half")
    print("           null  = mean AUC of the SAME feature on 6 driftless random walks")
    print("           exc   = oos - null   <-- the only honest column")
    print("           t     = exc / sqrt(se(oos)^2 + se(null mean)^2)")
    print("  Features marked * use bars p+1..p+3 and therefore OVERLAP labels A and P")
    print("  mechanically; they are meaningful only on label B, and only vs the null.")
    print(f"  Multiple comparisons: 20 features x 3 timeframes x 3 labels = 180 tests.")
    print(f"  Bonferroni two-sided |t| for 180 tests = 3.44.\n")

    for tf in ("M1", "M5", "M15"):
        _, sp, vol, rows = prep(tf)
        half = len(rows) // 2
        A_, B_ = rows[:half], rows[half:]
        days = len({(r["ts"] + TZOFF) // 86400 for r in B_})
        bigA = qthresh(A_, "full_atr")
        bigs = [r for r in B_ if r["full_atr"] >= bigA]
        dead = sum(1 for r in B_ if r["cap_atr"] <= 0) / len(B_)
        bigdead = (sum(1 for r in bigs if r["cap_atr"] <= 0) / len(bigs)) if bigs else float("nan")
        print("\n" + "-" * 78)
        print(f"  {tf}: {len(rows)} leg origins, {len(A_)} in-sample / {len(B_)} unseen "
              f"over {days} days ({len(B_)/days:.1f} extremes/day)")
        print(f"      top-5% cut taken on the first half = {bigA:.2f} ATR "
              f"({len(bigs)} unseen positives)")
        print(f"      of ALL unseen legs {dead:.1%} are already over by the confirm bar p+3; "
              f"of the top-5% ones {bigdead:.1%} are")
        print(f"      median share of a top-5% leg still available at p+3: "
              f"{med([r['cap_atr']/r['full_atr'] for r in bigs]):.2f}")

        for key, desc in LABELS:
            nul, nbase = null_auc_table(tf, key)
            t_ = qthresh(A_, key)
            labA = mklab(A_, key, t_)
            labB = mklab(B_, key, t_)
            if sum(labB) < 10:
                print(f"    label {key}: only {sum(labB)} unseen positives, skipped")
                continue
            n1_ = sum(labB); n0_ = len(labB) - n1_
            se_ = math.sqrt((n1_ + n0_ + 1.0) / (12.0 * n1_ * n0_))
            print(f"\n    LABEL {key}  cut {t_:.3f}  unseen positives {n1_} "
                  f"(base {n1_/len(labB):.4f}); null base {nbase:.4f}")
            print(f"      POWER LIMIT: se(AUC) = {se_:.4f}, so this cell can only "
                  f"resolve an excess of {2*se_:.4f} at t=2 and {3.44*se_:.4f} "
                  f"Bonferroni-corrected. Smaller true effects are invisible here.")
            res = []
            for nm in FEATURES:
                a1, _, _ = auc([r["f"][nm] for r in A_], labA)
                a2, n1, n0 = auc([r["f"][nm] for r in B_], labB)
                nm_, nsd, nseed = nul[nm]
                se = math.sqrt((n1 + n0 + 1.0) / (12.0 * n1 * n0)) if n1 and n0 else float("nan")
                sen = (nsd / math.sqrt(nseed)) if nseed > 1 and nsd == nsd else 0.0
                ex = a2 - nm_
                tt = ex / math.sqrt(se * se + sen * sen) if se == se else float("nan")
                res.append((abs(ex) if ex == ex else -1, nm, a1, a2, nm_, nsd, ex, tt))
            res.sort(reverse=True)
            print("       feature            is    oos    null  nullsd     exc       t")
            for _, nm, a1, a2, nmn, nsd, ex, tt in res:
                star = "*" if nm in POST else " "
                print(f"      {star}{nm:<16} {a1:6.3f} {a2:6.3f} {nmn:7.3f} {nsd:7.3f} "
                      f"{ex:+7.3f} {tt:+7.2f}")
        # session, on the honest label
        print("\n    median full leg (ATR) by hour of the broker day, unseen half:")
        byh = {}
        for r in B_:
            byh.setdefault(r["hour"], []).append(r["full_atr"])
        line = "      "
        for i, h in enumerate(sorted(byh)):
            if len(byh[h]) >= 30:
                line += f"{h:02d}h {med(byh[h]):4.1f} "
            if i % 8 == 7:
                line += "\n      "
        print(line)



# ------------------------------------------------------ 4. precision/recall
def score_rows(rows, names, mu, sd, signs):
    out = []
    for r in rows:
        z = 0.0; ok = True
        for nm in names:
            v = r["f"][nm]
            if v != v: ok = False; break
            z += signs[nm] * (v - mu[nm]) / (sd[nm] or 1e-9)
        out.append(z if ok else float("nan"))
    return out


# Features knowable AT the extreme bar itself (bars <= p). An indicator built
# only from these could in principle paint on the extreme bar; everything else
# needs the three confirmation bars anyway.
AT_EXTREME = ["sweep_atr", "swept", "n_swept", "wick_atr", "body_frac",
              "close_pos", "vol_ratio", "atr_regime", "atr_pts", "dist_ema200",
              "took_pd", "compress", "prior_leg_atr", "room_atr"]
POST = ["disp1", "disp3", "range3", "engulf3", "fvg3", "vol_ratio3"]


def label_of(r, thr, mode):
    if mode == "atr":
        return 1 if r["full_atr"] >= thr else 0
    if mode == "cap":
        return 1 if r["cap_atr"] >= thr else 0
    return 1 if r["full_pts"] >= thr else 0


def choose(A_, labA, pool, ntop=3):
    rank = []
    for nm in pool:
        a, n1, n0 = auc([r["f"][nm] for r in A_], labA)
        if a == a:
            rank.append((abs(a - 0.5), nm, 1.0 if a > 0.5 else -1.0))
    rank.sort(reverse=True)
    picks = [(nm, sg) for _, nm, sg in rank[:ntop]]
    names = [nm for nm, _ in picks]
    signs = {nm: sg for nm, sg in picks}
    mu, sd = {}, {}
    for nm in names:
        v = [r["f"][nm] for r in A_ if r["f"][nm] == r["f"][nm]]
        mu[nm] = sum(v) / len(v); sd[nm] = statistics.pstdev(v)
    return names, signs, mu, sd


FRACS = (0.01, 0.02, 0.05, 0.10, 0.20, 0.33, 0.50)


def pr_stats(labB, sc, days):
    """Precision, recall, lift and false flags per day at each cutoff.

    LIFT = precision / base rate. It is the comparable quantity: the null and
    the real sample carry the same base rate by construction (both label the
    top 5% of their own legs), so lift-vs-lift is like for like."""
    order = sorted(((v, i) for i, v in enumerate(sc) if v == v), reverse=True)
    nb = max(1, sum(labB))
    base = sum(labB) / max(1, len(labB))
    out = []
    for frac in FRACS:
        nsel = max(1, int(frac * len(order)))
        sel = [i for _, i in order[:nsel]]
        tp = sum(labB[i] for i in sel)
        pr = tp / nsel
        out.append((frac, pr, tp / nb, pr / base if base else float("nan"),
                    (nsel - tp) / days, nsel, tp))
    return out


def pr_print(tag, st):
    print(f"      {tag:<24}", end="")
    for (fr, p, r, l, fd, n, tp) in st:
        print(f" |{int(fr*100):>2}% P{p:.3f} R{r:.3f} L{l:4.2f} F/d{fd:5.1f}", end="")
    print()


def cmd_pr():
    hdr("PRECISION / RECALL — flag the top N% of extremes by score; what share "
        "of the big legs is caught, and how many false flags a day?")
    print("  'big leg' = top 5% of legs by the label, cut taken on the FIRST half.")
    print("  Features and signs chosen on the FIRST half; every number is the SECOND.")
    print("  'at-extreme' uses only the 14 features computable on bar p itself.")
    print("  'all 20' may use the 6 that need bars p+1..p+3 and overlap labels A/P.")
    print("  NULL = the identical procedure on 6 driftless random walks; the null's")
    print("  base rate is the same 5% by construction, so LIFT is directly comparable.")
    print("  L = precision / base rate.  A real result counts only if L beats null L.\n")
    for tf in ("M1", "M5", "M15"):
        _, _, _, rows = prep(tf)
        half = len(rows) // 2
        A_, B_ = rows[:half], rows[half:]
        days = len({(r["ts"] + TZOFF) // 86400 for r in B_})
        for key in ("full_atr", "full_pts", "cap_atr"):
            t_ = qthresh(A_, key)
            labA = mklab(A_, key, t_); labB = mklab(B_, key, t_)
            if sum(labB) < 10:
                continue
            print(f"  --- {tf}  label {key}  cut {t_:.3f}  unseen {len(B_)} origins / "
                  f"{days} days ({len(B_)/days:.1f}/day), {sum(labB)} positives, "
                  f"base {sum(labB)/len(labB):.4f}")
            for tag, pool in (("REAL all 20", FEATURES),
                              ("REAL at-extreme", AT_EXTREME)):
                names, signs, mu, sd = choose(A_, labA, pool)
                st = pr_stats(labB, score_rows(B_, names, mu, sd, signs), days)
                pr_print(tag, st)
                print("        chosen: " + ",".join(
                    nm + ("+" if signs[nm] > 0 else "-") for nm in names))
                # the null, same pool, same procedure, averaged over seeds
                acc = []
                for seed in NULL_SEEDS:
                    _, _, _, nr = prep(tf, synthetic=seed)
                    nh = len(nr) // 2
                    NA, NB = nr[:nh], nr[nh:]
                    tn = qthresh(NA, key)
                    nlA = mklab(NA, key, tn); nlB = mklab(NB, key, tn)
                    if sum(nlB) < 10: continue
                    nd = len({(r["ts"] + TZOFF) // 86400 for r in NB})
                    nn, sg, m2, s2 = choose(NA, nlA, pool)
                    acc.append(pr_stats(nlB, score_rows(NB, nn, m2, s2, sg), nd))
                if acc:
                    mean = [(FRACS[i],
                             sum(a[i][1] for a in acc) / len(acc),
                             sum(a[i][2] for a in acc) / len(acc),
                             sum(a[i][3] for a in acc) / len(acc),
                             sum(a[i][4] for a in acc) / len(acc), 0, 0)
                            for i in range(len(FRACS))]
                    pr_print(f"NULL x{len(acc)} mean", mean)
                    sds = "        null L sd:              "
                    for i in range(len(FRACS)):
                        v = [a[i][3] for a in acc]
                        sds += f" |{int(FRACS[i]*100):>2}%              {statistics.pstdev(v):4.2f}      "
                    print(sds)
                    exc = "        REAL - NULL lift:       "
                    for i in range(len(FRACS)):
                        v = [a[i][3] for a in acc]
                        d = st[i][3] - (sum(v) / len(v))
                        exc += f" |{int(FRACS[i]*100):>2}%        {d:+6.2f}          "
                    print(exc)
            print()





# ---------------------------------------------------- 4b. the survivors, alone
def strat_auc(rows, valname, lab, byname, nq=5):
    """AUC of `valname` computed WITHIN quintiles of `byname` and pooled by
    n1*n0. This is the control for 'the feature is only a proxy for the
    volatility regime': if tick volume at the extreme only works because busy
    bars happen in volatile hours, holding the ATR regime fixed kills it."""
    v = sorted(r["f"][byname] for r in rows if r["f"][byname] == r["f"][byname])
    if len(v) < 100: return float("nan"), 0
    cuts = [v[int((i + 1) * len(v) / nq)] for i in range(nq - 1)]
    buckets = [[] for _ in range(nq)]
    for r, y in zip(rows, lab):
        b = r["f"][byname]
        if b != b: continue
        k = 0
        while k < nq - 1 and b > cuts[k]:
            k += 1
        buckets[k].append((r["f"][valname], y))
    num = den = 0.0; tot = 0
    for bk in buckets:
        if len(bk) < 40: continue
        a, n1, n0 = auc([x for x, _ in bk], [y for _, y in bk])
        if a != a or n1 == 0 or n0 == 0: continue
        w = n1 * n0
        num += a * w; den += w; tot += n1
    return (num / den if den else float("nan")), tot


def cmd_surv():
    hdr("THE SURVIVORS, ISOLATED — is tick volume at the extreme bar anything "
        "more than the volatility regime wearing a hat?")
    print("  Only features computable ON bar p are eligible here; nothing that")
    print("  reads p+1..p+3 can be in an indicator that paints at the extreme.")
    print("  Every cell: real, then the same code on 6 driftless random walks.")
    print("  Label = top 5% of legs by full_atr, cut from the FIRST half.\n")
    for tf in ("M1", "M5", "M15"):
        _, _, _, rows = prep(tf)
        half = len(rows) // 2
        A_, B_ = rows[:half], rows[half:]
        t_ = qthresh(A_, "full_atr")
        labB = mklab(B_, "full_atr", t_)
        days = len({(r["ts"] + TZOFF) // 86400 for r in B_})
        print(f"  --- {tf}: {len(B_)} unseen origins, {sum(labB)} positives, "
              f"base {sum(labB)/len(labB):.4f}, cut {t_:.2f} ATR")

        # (1) plain deciles of vol_ratio against the leg that follows
        v = [(r["f"]["vol_ratio"], r) for r in B_ if r["f"]["vol_ratio"] == r["f"]["vol_ratio"]]
        v.sort(key=lambda x: x[0])
        q = len(v) // 10
        print("      vol_ratio decile |  median leg ATR |  median leg pts |  P(top5%)")
        for i in range(10):
            ch = [r for _, r in v[i * q:(i + 1) * q]] if i < 9 else [r for _, r in v[9 * q:]]
            if not ch: continue
            pt = sum(1 for r in ch if r["full_atr"] >= t_) / len(ch)
            print(f"        {i+1:2d}  ({med([x for x,_ in v[i*q:(i+1)*q]]):5.2f}x) "
                  f"    {med([r['full_atr'] for r in ch]):6.2f}      "
                  f"    {med([r['full_pts'] for r in ch]):6.3f}      "
                  f"   {pt:.4f}")

        # (2) raw vs volatility-stratified AUC, real and null
        for nm in ("vol_ratio", "wick_atr", "atr_pts", "sweep_atr"):
            a_raw, n1, n0 = auc([r["f"][nm] for r in B_], labB)
            a_str, tot = strat_auc(B_, nm, labB, "atr_regime")
            nr_raw, nr_str = [], []
            for seed in NULL_SEEDS:
                _, _, _, nr = prep(tf, synthetic=seed)
                nh = len(nr) // 2
                NA, NB = nr[:nh], nr[nh:]
                tn = qthresh(NA, "full_atr")
                nl = mklab(NB, "full_atr", tn)
                if sum(nl) < 10: continue
                x, _, _ = auc([r["f"][nm] for r in NB], nl)
                y, _ = strat_auc(NB, nm, nl, "atr_regime")
                if x == x: nr_raw.append(x)
                if y == y: nr_str.append(y)
            mr = sum(nr_raw) / len(nr_raw) if nr_raw else float("nan")
            ms = sum(nr_str) / len(nr_str) if nr_str else float("nan")
            print(f"      {nm:<12} AUC raw {a_raw:6.3f} (null {mr:5.3f}, exc "
                  f"{a_raw-mr:+.3f}) | ATR-regime-stratified {a_str:6.3f} "
                  f"(null {ms:5.3f}, exc {a_str-ms:+.3f})")

        # (3a) does it work in BOTH directions, or is it one-sided?
        for dd, dn in ((+1, "up legs  (swept LOW origins)"),
                       (-1, "down legs(swept HIGH origins)")):
            sub = [(r, y) for r, y in zip(B_, labB) if r["d"] == dd]
            if len(sub) < 100: continue
            a, n1, n0 = auc([r["f"]["vol_ratio"] for r, _ in sub],
                            [y for _, y in sub])
            nv = []
            for seed in NULL_SEEDS:
                _, _, _, nr = prep(tf, synthetic=seed)
                nh = len(nr) // 2
                NA, NB = nr[:nh], nr[nh:]
                tn = qthresh(NA, "full_atr")
                nl = mklab(NB, "full_atr", tn)
                sb = [(r, y) for r, y in zip(NB, nl) if r["d"] == dd]
                if sum(y for _, y in sb) < 10: continue
                x, _, _ = auc([r["f"]["vol_ratio"] for r, _ in sb],
                              [y for _, y in sb])
                if x == x: nv.append(x)
            mn = sum(nv) / len(nv) if nv else float("nan")
            print(f"      vol_ratio {dn:<28} AUC {a:6.3f} (null {mn:5.3f}, "
                  f"exc {a-mn:+.3f}, n={len(sub)}, positives {n1}, "
                  f"z {auc_z(a,n1,n0):+5.2f})")

        # (3) is it stable month by month?
        bym = {}
        for r, y in zip(B_, labB):
            mth = ((r["ts"] + TZOFF) // 86400) // 30
            bym.setdefault(mth, []).append((r["f"]["vol_ratio"], y))
        line = "      vol_ratio AUC by ~month of the unseen half: "
        for mth in sorted(bym):
            bk = bym[mth]
            if len(bk) < 200: continue
            a, n1, n0 = auc([x for x, _ in bk], [y for _, y in bk])
            line += f"{a:.3f}(n1={n1}) "
        print(line)

        # (4) vol_ratio ALONE as the flag, real vs null
        sc = [r["f"]["vol_ratio"] if r["f"]["vol_ratio"] == r["f"]["vol_ratio"]
              else float("nan") for r in B_]
        pr_print("REAL vol_ratio alone", pr_stats(labB, sc, days))
        acc = []
        for seed in NULL_SEEDS:
            _, _, _, nr = prep(tf, synthetic=seed)
            nh = len(nr) // 2
            NA, NB = nr[:nh], nr[nh:]
            tn = qthresh(NA, "full_atr")
            nl = mklab(NB, "full_atr", tn)
            if sum(nl) < 10: continue
            nd = len({(r["ts"] + TZOFF) // 86400 for r in NB})
            acc.append(pr_stats(nl, [r["f"]["vol_ratio"] for r in NB], nd))
        if acc:
            pr_print(f"NULL x{len(acc)} mean", [
                (FRACS[i], sum(a[i][1] for a in acc) / len(acc),
                 sum(a[i][2] for a in acc) / len(acc),
                 sum(a[i][3] for a in acc) / len(acc),
                 sum(a[i][4] for a in acc) / len(acc), 0, 0)
                for i in range(len(FRACS))])
        print()


# ------------------------------------------- 4c. what confirmation latency costs
def cmd_lat():
    hdr("WHAT THE CONFIRMATION LATENCY COSTS — the ceiling on ANY non-repainting "
        "swing flag")
    print("  A k-bar fractal at bar p is not knowable until bar p+k has closed.")
    print("  So an indicator that does not repaint can only mark the extreme k")
    print("  bars late, and the part of the leg between p and p+k is gone. This")
    print("  is arithmetic, not strategy: it bounds every result in this study.\n")
    s0, sp0, v0 = load_m1()
    print("   tf   k |  legs/day | mean leg | left at p+k |  % left | spread | "
          "perfect net | GBP@0.01")
    for tf in ("M1", "M5", "M15"):
        s, sp, vol = resample(s0, sp0, v0, TFMULT[tf])
        A = watr(s, 14)
        nd = ndays(s)
        for k in (1, 2, 3, 5):
            L = legs(s, k)
            full, left, spl = [], [], []
            for (p, px, d, ti, tpx) in L:
                if p < 260 or p + k >= len(s) - 2: continue
                full.append(abs(tpx - px))
                left.append(max(0.0, d * (tpx - s.c[p + k])))
                spl.append(sp[p])
            if len(full) < 50: continue
            mf = sum(full) / len(full); ml = sum(left) / len(left)
            ms = sum(spl) / len(spl)
            print(f"  {tf:>3} {k:3d} | {len(full)/nd:9.1f} | {mf:8.4f} | "
                  f"{ml:11.4f} | {100*ml/mf:6.0f}% | {ms:6.4f} | "
                  f"{ml-ms:+11.4f} | {GBP*(ml-ms):+8.3f}")
    print("\n  'perfect net' assumes an ORACLE exit at the leg's terminal extreme")
    print("  and one round-turn spread. Nothing tradeable can beat it.")


# ------------------------------- 4d. the one independent sample we actually have
NOVOL = [f for f in AT_EXTREME if f not in ("vol_ratio",)]


def cmd_modern():
    hdr("INDEPENDENT SAMPLE — GOLD_1h.json, 2024-2026. Does anything replicate?")
    print("  GOLD_M1_2018 covers 135 days of ONE regime and M5/M15 are exact")
    print("  aggregations of it, so the whole study above is one sample. GOLD_1h")
    print("  is a different broker, a different two years and a different clock.")
    print("  It carries NO spread column and NO volume column, so:")
    print("    * no P&L is quoted here, and")
    print("    * vol_ratio -- the one at-extreme feature that survived the null")
    print("      on 2018 -- CANNOT BE TESTED HERE AT ALL. That is a real hole.")
    print("  What can be checked: the structural facts and the 13 non-volume")
    print("  at-extreme features, same code, same first-half/second-half rule.\n")
    rows0 = json.load(open(f"{DATA}/GOLD_1h.json"))
    rows0.sort(key=lambda r: r[0])
    seen, out = set(), []
    for r in rows0:
        if r[0] in seen: continue
        seen.add(r[0]); out.append(r)
    s = Series([r[0] for r in out], [r[1] for r in out], [r[2] for r in out],
               [r[3] for r in out], [r[4] for r in out])
    sp = [0.0] * len(s); vol = [1.0] * len(s)
    nd = ndays(s)
    print(f"  {len(s)} H1 bars over {nd} calendar days "
          f"({out[0][0]} .. {out[-1][0]}), median ATR14 "
          f"{med([x for x in watr(s,14)[100:] if x]):.3f} pts")
    A = watr(s, 14)
    for k in (2, 3, 5):
        L = legs(s, k)
        full = [abs(tp - p) for (i, p, d, ti, tp) in L if i > 260]
        left = [max(0.0, d * (tp - s.c[i + k])) for (i, p, d, ti, tp) in L if i > 260]
        sz = [abs(tp - p) / (A[i] or 1e-9) for (i, p, d, ti, tp) in L if i > 260]
        ss = sorted(sz)
        print(f"    k={k}: {len(full)} legs, median {ss[len(ss)//2]:.2f} ATR / "
              f"{statistics.median(full):.2f} pts; mean leg {sum(full)/len(full):.3f}, "
              f"left at p+k {sum(left)/len(left):.3f} "
              f"({100*sum(left)/sum(full):.0f}%); "
              f">=10 ATR {sum(1 for x in sz if x>=10)} "
              f"({sum(1 for x in sz if x>=10)/nd:.3f}/day)")
    rows, _ = build(s, sp, vol, 60)
    half = len(rows) // 2
    A_, B_ = rows[:half], rows[half:]
    for key in ("full_atr", "full_pts", "cap_atr"):
        t_ = qthresh(A_, key)
        labA = mklab(A_, key, t_); labB = mklab(B_, key, t_)
        if sum(labB) < 10: continue
        print(f"\n    LABEL {key}  cut {t_:.3f}  {len(B_)} unseen, "
              f"{sum(labB)} positives (base {sum(labB)/len(labB):.4f})")
        res = []
        for nm in NOVOL:
            a1, _, _ = auc([r["f"][nm] for r in A_], labA)
            a2, n1, n0 = auc([r["f"][nm] for r in B_], labB)
            z = auc_z(a2, n1, n0)
            res.append((abs(a2 - 0.5) if a2 == a2 else -1, nm, a1, a2, z))
        res.sort(reverse=True)
        print("       feature            is    oos       z")
        for _, nm, a1, a2, z in res:
            print(f"       {nm:<16} {a1:6.3f} {a2:6.3f} {z:+7.2f}")
    print("\n  NOTE: no null is run on this file. The null's job on 2018 was to")
    print("  price in the label overlap of the p+1..p+3 features; none of the 13")
    print("  features above reads a bar after p, so none of them can overlap the")
    print("  label. Their z is against 0.5 directly. n1 is small: read with care.")


# ------------------------------------------------------------- 5. trade
def _book(s, B_, ids, give=0.5, maxbars=400):
    """Two books from the same flags. ORACLE holds to the leg's own terminal
    extreme -- nobody can trade it, it is the ceiling. TRAIL is the shipped
    give-back, routed through engine.trail_level()."""
    book_o, book_t = [], []
    for idx in ids:
        r = B_[idx]
        p = r["k_i"]                       # the fractal is not knowable before p+k
        if p + 1 >= len(s) - 1: continue
        d = r["d"]
        fill = entry_fill(s.o[p + 1], s.o[p + 1], d)
        spr = r["sp"]
        ent = fill + d * spr / 2.0
        book_o.append(d * ((r["tpx"] - d * spr / 2.0) - ent))
        stop = r["px"] - d * 0.1 * r["atr"]
        peak = ent; out = None
        for j in range(p + 1, min(p + 1 + maxbars, len(s))):
            if (d == 1 and s.l[j] <= stop) or (d == -1 and s.h[j] >= stop):
                out = stop - d * spr / 2.0; break
            peak = max(peak, s.h[j]) if d == 1 else min(peak, s.l[j])
            nl = trail_level(ent, stop, peak, s.c[j], d, give)
            if nl is None:
                out = s.c[j] - d * spr / 2.0; break
            stop = nl
        if out is None: out = s.c[min(p + maxbars, len(s) - 1)] - d * spr / 2.0
        book_t.append(d * (out - ent))
    return book_o, book_t


def _rep(tf, tag, nm, bk, days):
    if len(bk) < 5: return
    m = sum(bk) / len(bk)
    sdv = statistics.pstdev(bk) or 1e-9
    t = m / (sdv / math.sqrt(len(bk)))
    print(f"  {tf:>3} {tag:<20} {nm:<18} n={len(bk):5d}  "
          f"total {sum(bk):+9.1f} pts = {GBP*sum(bk):+9.2f} GBP  "
          f"per trade {m:+.4f} pts  t {t:+6.2f}  "
          f"win {sum(1 for x in bk if x>0)/len(bk):.1%}  "
          f"{len(bk)/days:5.2f} trades/day")


def cmd_trade(frac=0.10):
    hdr("ONLY AFTER THE CLASSIFICATION — what a trade from a flagged origin "
        "would have made, net of the measured spread")
    print("  This is reported LAST and on purpose. The study's question was")
    print("  classification, not P&L; this cell only says what the classifier")
    print("  would have been worth if traded mechanically.")
    print("  Entry: market at the open of the bar AFTER the flag bar p+3,")
    print("  routed through engine.entry_fill(). Cost: that bar's own MEASURED")
    print("  spread, half in and half out. ORACLE = hold to the leg's terminal")
    print("  extreme, an upper bound nobody can trade. TRAIL = the shipped")
    print("  give-back through engine.trail_level(give=0.5), stop at the origin.")
    print("  Flags chosen on the FIRST half, traded on the SECOND. GBP at 0.01")
    print(f"  lots = {GBP} per point (E-081).\n")
    for tf in ("M1", "M5", "M15"):
        s, sp, vol, rows = prep(tf)
        half = len(rows) // 2
        A_, B_ = rows[:half], rows[half:]
        days = len({(r["ts"] + TZOFF) // 86400 for r in B_})
        t_ = qthresh(A_, "full_atr")
        labA = mklab(A_, "full_atr", t_)
        # THE CEILING, before any flag: how much of the average leg is left
        # once the fractal has confirmed, and what does the spread take?
        mf = sum(r["full_pts"] for r in B_) / len(B_)
        mc = sum(abs(r["cap_atr"]) * r["atr"] for r in B_) / len(B_)
        msp = sum(r["sp"] for r in B_) / len(B_)
        print(f"  {tf:>3} CEILING: mean leg {mf:.4f} pts; still there at the "
              f"confirm bar p+3 {mc:.4f} pts ({100*mc/mf:.0f}%); round-turn "
              f"spread {msp:.4f} pts ({100*msp/mc:.0f}% of it); "
              f"perfect-exit net {mc-msp:+.4f} pts = {GBP*(mc-msp):+.3f} GBP")
        for tag, pool in (("flagged all-20", FEATURES),
                          ("flagged at-extreme", AT_EXTREME),
                          ("flagged vol_ratio", ["vol_ratio"])):
            names, signs, mu, sd = choose(A_, labA, pool, ntop=min(3, len(pool)))
            sc = score_rows(B_, names, mu, sd, signs)
            order = sorted(((v, i) for i, v in enumerate(sc) if v == v), reverse=True)
            sel = [i for _, i in order[:max(1, int(frac * len(order)))]]
            bo, bt = _book(s, B_, sel)
            _rep(tf, f"{tag} top10%", "oracle-to-leg-end", bo, days)
            _rep(tf, f"{tag} top10%", "giveback-trail", bt, days)
        bo, bt = _book(s, B_, list(range(len(B_))))
        _rep(tf, "every extreme", "oracle-to-leg-end", bo, days)
        _rep(tf, "every extreme", "giveback-trail", bt, days)
        print()



def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("null", "all"): cmd_null()
    if cmd in ("dist", "all"): cmd_dist()
    if cmd in ("feat", "all"): cmd_feat()
    if cmd in ("pr", "all"): cmd_pr()
    if cmd in ("surv", "all"): cmd_surv()
    if cmd in ("lat", "all"): cmd_lat()
    if cmd in ("modern", "all"): cmd_modern()
    if cmd in ("trade", "all"): cmd_trade()


main()

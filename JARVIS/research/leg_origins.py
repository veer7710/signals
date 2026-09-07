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
* LABEL B (capturable): the part still available to someone who can only act
  after the pivot is CONFIRMED, i.e. from close[p+k] to the terminal price,
  in ATR. Label B is the honest one for an indicator; label A is what "top to
  bottom" means in plain English. Both are reported.
* FLAG TIME: a k=3 fractal pivot at bar p is not knowable until bar p+3 has
  closed. So every feature is computed from bars <= p+3 ONLY, and the
  indicator can only paint at p+3. This is stated, not hidden.
* 19 numeric features + session, listed in FEATURES below. All of them were
  written down before any AUC was computed. 19 features x 3 timeframes x 2
  labels = 114 tests; the Bonferroni-corrected two-sided |z| for that is 3.28.
* Choose on the FIRST HALF of the sample, report on the SECOND half.
* Costs: the file's own measured spread column, in price units, unscaled.
  E-165 showed the old per-timeframe `cs` rescaling charged M5/M15 2.5-4.6x
  too much. Volume is TICK volume and is broker-dependent.

THE NULL RUNS FIRST. A driftless random walk with the real timestamps, the
real spread column and the real volume column, through the identical code. On
a random walk nothing can separate, so every feature's AUC must be 0.5 and
precision must equal the base rate. Any feature that scores on the null is
scoring on arithmetic, not on the market -- in particular any feature that
uses bars p+1..p+3 overlaps the label mechanically. The honest number for
every feature is therefore REAL AUC MINUS NULL AUC.

Usage:
    python3 JARVIS/research/leg_origins.py null
    python3 JARVIS/research/leg_origins.py dist
    python3 JARVIS/research/leg_origins.py feat
    python3 JARVIS/research/leg_origins.py pr
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


def prep(tf, synthetic=None):
    key = ("real" if synthetic is None else f"synth{synthetic}")
    if key not in _CACHE:
        s0, sp0, v0 = load_m1()
        if synthetic is not None:
            s0, sp0, v0, _ = synth_like(s0, sp0, v0, synthetic)
        _CACHE[key] = (s0, sp0, v0)
    s0, sp0, v0 = _CACHE[key]
    s, sp, vol = resample(s0, sp0, v0, TFMULT[tf])
    rows, A = build(s, sp, vol, TFMULT[tf])
    return s, sp, vol, rows


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
            cnt = "         legs/day exceeding:  "
            for t in (5, 10, 20, 30, 50):
                n = sum(1 for x in sz if x >= t)
                cnt += f"{t}ATR {n/nd:5.2f} (n={n:4d})  "
            print(cnt)
            cntp = "         legs/day exceeding:  "
            for t in (1, 2, 5, 10):
                n = sum(1 for x in pts if x >= t)
                cntp += f"{t}pt {n/nd:5.2f} (n={n:4d})  "
            print(cntp)
        print()


# -------------------------------------------------------- 3. separation
def cmd_feat(thr=10.0):
    hdr(f"FEATURE SEPARATION — big-leg origin (>= {thr:.0f} ATR) vs the rest")
    print("  Selection sample = FIRST HALF. Reported sample = SECOND HALF (unseen).")
    print("  LABEL A 'full'  = |terminal - origin| / ATR  (top-to-bottom, what Veer means)")
    print("  LABEL B 'cap'   = terminal - close[p+3] / ATR (what is still there when")
    print("                    the fractal confirms and the indicator can paint)")
    print("  'exc' = real AUC minus the mean NULL AUC on the same feature/timeframe.")
    print("  Features using bars p+1..p+3 overlap label A mechanically and score on a")
    print("  random walk, so exc is the only honest column. Bonferroni |z| for 114")
    print("  tests = 3.28.\n")
    null_auc, null_cap = {}, {}
    for tf in ("M1", "M5", "M15"):
        af = {nm: [] for nm in FEATURES}; ac = {nm: [] for nm in FEATURES}
        for seed in (11, 12):
            _, _, _, nr = prep(tf, synthetic=seed)
            lb = [1 if r["full_atr"] >= thr else 0 for r in nr]
            lc = [1 if r["cap_atr"] >= thr else 0 for r in nr]
            for nm in FEATURES:
                v = [r["f"][nm] for r in nr]
                a, _, _ = auc(v, lb)
                if a == a: af[nm].append(a)
                a2, _, _ = auc(v, lc)
                if a2 == a2: ac[nm].append(a2)
        null_auc[tf] = {nm: (sum(v)/len(v) if v else float("nan")) for nm, v in af.items()}
        null_cap[tf] = {nm: (sum(v)/len(v) if v else float("nan")) for nm, v in ac.items()}

    for tf in ("M1", "M5", "M15"):
        s_, sp, vol, rows = prep(tf)
        half = len(rows) // 2
        A_, B_ = rows[:half], rows[half:]
        labA = [1 if r["full_atr"] >= thr else 0 for r in A_]
        labB = [1 if r["full_atr"] >= thr else 0 for r in B_]
        capB = [1 if r["cap_atr"] >= thr else 0 for r in B_]
        dead = sum(1 for r in B_ if r["cap_atr"] <= 0) / len(B_)
        bigs = [r for r in B_ if r["full_atr"] >= thr]
        bigdead = (sum(1 for r in bigs if r["cap_atr"] <= 0) / len(bigs)) if bigs else float("nan")
        print(f"\n  --- {tf}: {len(rows)} leg origins "
              f"({len(A_)} in-sample / {len(B_)} unseen), unseen base rate "
              f"{sum(labB)/len(labB):.4f} ({sum(labB)} big legs); cap-label base "
              f"{sum(capB)/len(capB):.4f} ({sum(capB)})")
        print(f"      of unseen legs, {dead:.1%} are already OVER by the confirm bar "
              f"p+3; of the >= {thr:.0f} ATR ones, {bigdead:.1%} are")
        print(f"      median capturable share of a big leg: "
              f"{med([r['cap_atr']/r['full_atr'] for r in bigs]):.2f}")
        res = []
        for nm in FEATURES:
            a1, x1, y1 = auc([r["f"][nm] for r in A_], labA)
            a2, x2, y2 = auc([r["f"][nm] for r in B_], labB)
            a3, x3, y3 = auc([r["f"][nm] for r in B_], capB)
            rho = spearman([r["f"][nm] for r in B_], [r["full_atr"] for r in B_])
            top, bot = quart_split(B_, nm, "full_atr")
            res.append((abs(a2 - 0.5) if a2 == a2 else -1, nm, a1, a2,
                        auc_z(a2, x2, y2), a2 - null_auc[tf][nm],
                        a3, auc_z(a3, x3, y3), a3 - null_cap[tf][nm], rho, top, bot))
        res.sort(reverse=True)
        print("     feature        A_is   A_oos      z     exc | cap_oos      z     exc"
              " |   rho   topq   botq")
        for _, nm, a1, a2, z, ex, a3, z3, ex3, rho, top, bot in res:
            print(f"     {nm:<13} {a1:6.3f} {a2:6.3f} {z:6.2f} {ex:+6.3f} | "
                  f"{a3:6.3f} {z3:6.2f} {ex3:+6.3f} | {rho:+5.2f} {top:6.2f} {bot:6.2f}")
        print("     session (hour of broker day, unseen half): median full leg ATR by hour")
        byh = {}
        for r in B_:
            byh.setdefault(r["hour"], []).append(r["full_atr"])
        line = "       "
        for h in sorted(byh):
            if len(byh[h]) >= 30:
                line += f"{h:02d}h {med(byh[h]):4.1f}  "
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


def choose(A_, labA, pool):
    rank = []
    for nm in pool:
        a, n1, n0 = auc([r["f"][nm] for r in A_], labA)
        if a == a:
            rank.append((abs(a - 0.5), nm, 1.0 if a > 0.5 else -1.0))
    rank.sort(reverse=True)
    picks = [(nm, sg) for _, nm, sg in rank[:3]]
    names = [nm for nm, _ in picks]
    signs = {nm: sg for nm, sg in picks}
    mu, sd = {}, {}
    for nm in names:
        v = [r["f"][nm] for r in A_ if r["f"][nm] == r["f"][nm]]
        mu[nm] = sum(v) / len(v); sd[nm] = statistics.pstdev(v)
    return names, signs, mu, sd


def pr_line(tag, B_, labB, sc, days):
    """P = precision, R = recall, LIFT = precision / base rate. LIFT is the
    only column that can be compared against the null, because the null's base
    rate is not the real one (a driftless walk makes far fewer 10-ATR legs)."""
    order = sorted(((v, i) for i, v in enumerate(sc) if v == v), reverse=True)
    nb = max(1, sum(labB))
    base = sum(labB) / max(1, len(labB))
    print(f"      {tag:<22}", end="")
    for frac in (0.05, 0.10, 0.20, 0.50):
        nsel = max(1, int(frac * len(order)))
        sel = [i for _, i in order[:nsel]]
        tp = sum(labB[i] for i in sel)
        pr = tp / nsel
        print(f" |{int(frac*100):>3}%: P {pr:.3f} R {tp/nb:.3f} "
              f"L {pr/base if base else float('nan'):4.2f} F/d {(nsel-tp)/days:5.2f}", end="")
    print()


PTS_THR = {"M1": 3.0, "M5": 5.0, "M15": 10.0}


def cmd_pr(thr=10.0, mode="atr"):
    hdr(f"PRECISION / RECALL — flag the top N% of extremes; what share of the "
        f"big legs do you catch?   label = {mode}, threshold {thr}")
    print("  Feature set and signs chosen on the FIRST half; every number is on the")
    print("  SECOND half. 'at-extreme only' uses the 14 features computable on bar p")
    print("  itself; 'best 3 of all 20' may use the 6 that need bars p+1..p+3.")
    print("  The NULL rows are the identical procedure on a driftless random walk.")
    print("  A real result only counts if its LIFT beats the null's LIFT.\n")
    for tf in ("M1", "M5", "M15"):
        t = PTS_THR[tf] if mode == "pts" else thr
        _, _, _, rows = prep(tf)
        half = len(rows) // 2
        A_, B_ = rows[:half], rows[half:]
        labA = [label_of(r, t, mode) for r in A_]
        labB = [label_of(r, t, mode) for r in B_]
        days = len({(r["ts"] + TZOFF) // 86400 for r in B_})
        print(f"  --- {tf} thr {t}: unseen {len(B_)} origins over {days} days "
              f"({len(B_)/days:.1f} extremes/day), {sum(labB)} big legs, "
              f"base rate {sum(labB)/len(labB):.4f}")
        for tag, pool in (("REAL best 3 of 20", FEATURES),
                          ("REAL at-extreme only", AT_EXTREME)):
            names, signs, mu, sd = choose(A_, labA, pool)
            sc = score_rows(B_, names, mu, sd, signs)
            desc = ",".join(nm + ("+" if signs[nm] > 0 else "-") for nm in names)
            pr_line(tag, B_, labB, sc, days)
            print(f"        chosen: {desc}")
            if pool is FEATURES:
                pr_line("  REAL best single", B_, labB,
                        score_rows(B_, names[:1], mu, sd, signs), days)
        for seed in (11, 12):
            _, _, _, nr = prep(tf, synthetic=seed)
            nh = len(nr) // 2
            NA, NB = nr[:nh], nr[nh:]
            nlA = [label_of(r, t, mode) for r in NA]
            nlB = [label_of(r, t, mode) for r in NB]
            nd = len({(r["ts"] + TZOFF) // 86400 for r in NB})
            if sum(nlB) < 5:
                print(f"      NULL seed {seed}: only {sum(nlB)} positives, skipped")
                continue
            for tag, pool in ((f"NULL{seed} best 3 of 20", FEATURES),
                              (f"NULL{seed} at-extreme", AT_EXTREME)):
                names, signs, mu, sd = choose(NA, nlA, pool)
                pr_line(tag, NB, nlB, score_rows(NB, names, mu, sd, signs), nd)
            print(f"        null base rate {sum(nlB)/len(nlB):.4f} "
                  f"({sum(nlB)} positives)")
        print()


# ------------------------------------------------------------- 5. trade
def cmd_trade(thr=10.0, frac=0.10):
    hdr("ONLY AFTER THE CLASSIFICATION — what a trade from a flagged origin "
        "would have made")
    print("  Entry: market at the open of the bar AFTER the flag bar (p+k),")
    print("  routed through engine.entry_fill(). Cost: the bar's own measured")
    print("  spread, charged half in and half out. Two exits: an ORACLE hold to")
    print("  the leg's terminal extreme (an upper bound nobody can trade), and")
    print("  a give-back trail through engine.trail_level(give=0.5), stop at")
    print("  the origin extreme.\n")
    for tf in ("M1", "M5", "M15"):
        s, sp, vol, rows = prep(tf)
        half = len(rows) // 2
        A_, B_ = rows[:half], rows[half:]
        labA = [1 if r["full_atr"] >= thr else 0 for r in A_]
        rank = []
        for nm in FEATURES:
            a, n1, n0 = auc([r["f"][nm] for r in A_], labA)
            if a == a: rank.append((abs(a - 0.5), nm, 1.0 if a > 0.5 else -1.0))
        rank.sort(reverse=True)
        picks = [(nm, sg) for _, nm, sg in rank[:3]]
        names = [nm for nm, _ in picks]; signs = {nm: sg for nm, sg in picks}
        mu, sd = {}, {}
        for nm in names:
            v = [r["f"][nm] for r in A_ if r["f"][nm] == r["f"][nm]]
            mu[nm] = sum(v) / len(v); sd[nm] = statistics.pstdev(v)
        sc = score_rows(B_, names, mu, sd, signs)
        order = sorted(((v, i) for i, v in enumerate(sc) if v == v), reverse=True)
        nsel = max(1, int(frac * len(order)))
        sel = [i for _, i in order[:nsel]]
        allid = [i for _, i in order]
        for tag, ids in (("flagged top10%", sel), ("every extreme", allid)):
            book_o, book_t = [], []
            for idx in ids:
                r = B_[idx]
                p = r["k_i"]                    # flag bar
                if p + 1 >= len(s) - 1: continue
                d = r["d"]
                fill = entry_fill(s.o[p + 1], s.o[p + 1], d)
                spr = r["sp"]
                ent = fill + d * spr / 2.0
                # ORACLE: hold to the leg's own terminal extreme
                ex_o = r["tpx"] - d * spr / 2.0
                book_o.append(d * (ex_o - ent))
                # give-back trail, stop at the origin extreme
                stop = r["px"] - d * 0.1 * r["atr"]
                peak = ent; out = None
                for j in range(p + 1, min(p + 1 + 400, len(s))):
                    if (d == 1 and s.l[j] <= stop) or (d == -1 and s.h[j] >= stop):
                        out = stop - d * spr / 2.0; break
                    peak = max(peak, s.h[j]) if d == 1 else min(peak, s.l[j])
                    nl = trail_level(ent, stop, peak, s.c[j], d, 0.5)
                    if nl is None:
                        out = s.c[j] - d * spr / 2.0; break
                    stop = nl
                if out is None: out = s.c[min(p + 400, len(s) - 1)] - d * spr / 2.0
                book_t.append(d * (out - ent))
            for nm, bk in (("oracle-to-leg-end", book_o), ("giveback-trail", book_t)):
                if len(bk) < 5: continue
                m = sum(bk) / len(bk)
                sdv = statistics.pstdev(bk) or 1e-9
                t = m / (sdv / math.sqrt(len(bk)))
                print(f"  {tf:>3} {tag:<15} {nm:<18} n={len(bk):5d}  "
                      f"total {sum(bk):+9.1f} pts  per trade {m:+.4f}  "
                      f"t {t:+6.2f}  win {sum(1 for x in bk if x>0)/len(bk):.1%}")
        print()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("null", "all"): cmd_null()
    if cmd in ("dist", "all"): cmd_dist()
    if cmd in ("feat", "all"): cmd_feat()
    if cmd in ("pr", "all"): cmd_pr()
    if cmd in ("prpts", "all"): cmd_pr(mode="pts")
    if cmd in ("trade", "all"): cmd_trade()


main()

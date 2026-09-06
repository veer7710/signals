"""
SWEEP x TREND CONTEXT  —  is the pooled zero an averaging artefact?

THE HYPOTHESIS, falsifiable, with its mechanism:
    A sweep of a swing LOW taken LONG while the higher timeframe is in an
    UPTREND, and a sweep of a swing HIGH taken SHORT while the higher
    timeframe is in a DOWNTREND, are profitable; their mirror images (long
    into a downtrend, short into an uptrend) are unprofitable by a similar
    amount; and every previous test in this repo took both blind, so the two
    halves cancelled and produced E-169's near-zero pooled number.
    Mechanism claimed: the sweep clears resting stops and supplies the
    counterparty that lets the PREVAILING move continue, so the fade only
    works when it is aligned with where the higher timeframe is already
    going. Falsified if the with-trend and against-trend cells have the SAME
    sign, or if neither is distinguishable from its matched control.

WHAT IS REUSED, AND WHY NOTHING IS RE-IMPLEMENTED
    Everything structural is imported from htf_levels.py (E-169) unchanged:
    the M1 loader with its MEASURED spread column, the clock-aligned
    resampler that reproduces the vendor's M5/M15 files bar-for-bar, the
    causal HTF pivot levels, the sweep finder, the limit fill, the simulator
    (which routes stops through engine.entry_fill and trails through
    engine.trail_level), the driftless-random-walk null generator and the
    exit-free forward-return diagnostic. This file adds exactly one thing:
    a CAUSAL higher-timeframe trend label attached to each sweep, and the
    2x2 split it implies. No existing file is modified.

NO LOOK-AHEAD IN THE LABEL
    A trend label for LTF bar j may only use HTF bars whose CLOSE TIME is at
    or before the close time of bar j. map_state() enforces that with the
    same close_ts() htf_levels uses for level availability. The label is
    read at the SWEEP bar - the moment the decision is made - never at the
    fill bar and never later.

Usage (each section is independent and reproducible):
    python3 JARVIS/research/sweep_trend.py null
    python3 JARVIS/research/sweep_trend.py facts
    python3 JARVIS/research/sweep_trend.py grid
    python3 JARVIS/research/sweep_trend.py edge
    python3 JARVIS/research/sweep_trend.py oos
    python3 JARVIS/research/sweep_trend.py control
    python3 JARVIS/research/sweep_trend.py modern
    python3 JARVIS/research/sweep_trend.py power
"""
from __future__ import annotations
import os, sys, math, random, statistics

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Series, atr as watr, ema
from strategies import supertrend_dir
import htf_levels as HL
from htf_levels import (load_m1, resample, close_ts, ndays, TFMIN, build,
                        build_min, load_plain, simulate, summ, forward,
                        tstat, synth_m1, line, HDR)


# ===================================================================== labels
def map_state(sl: Series, ltf_mult: int, sh: Series, htf_mult: int, vals):
    """For every LTF bar j, the most recent HTF value that had already been
    published when bar j closed. `vals[p]` must be computable from HTF bars
    <= p. Returns None before the first HTF bar has closed."""
    out = [None] * len(sl)
    p = 0
    for j in range(len(sl)):
        dt = close_ts(sl, j, ltf_mult)
        while p < len(sh) and close_ts(sh, p, htf_mult) <= dt:
            p += 1
        out[j] = vals[p - 1] if p >= 1 else None
    return out


# Each builder returns a per-HTF-bar list of states; each labeller turns a
# state plus the LTF bar into -1 (downtrend) / 0 (neutral) / +1 (uptrend).

def b_st(sh, AH, atr_len=10, mult=3.0):
    """(1a) HTF SuperTrend direction. supertrend_dir is Pine convention:
    -1 bullish, +1 bearish. Flip it so +1 means UP."""
    d, _, _ = supertrend_dir(sh, atr_len, mult)
    return [(-x if x else 0) for x in d]


def b_emaslope(sh, AH, n=50, band=0.05):
    """(1b) HTF EMA slope, with a neutral band of `band` * HTF ATR."""
    e = ema(sh.c, n)
    out = [0] * len(sh)
    for p in range(1, len(sh)):
        a = AH[p] or 0.0
        dv = e[p] - e[p - 1]
        out[p] = 0 if abs(dv) < band * a else (1 if dv > 0 else -1)
    return out


def b_pma(sh, AH, n=50, band=0.25):
    """(2) HTF moving-average LEVEL, carried to the LTF so the comparison
    uses the price AT THE MOMENT OF THE SWEEP, not the HTF close."""
    e = ema(sh.c, n)
    return [(e[p], AH[p] or 0.0, band) for p in range(len(sh))]


def b_bos(sh, AH, k=2):
    """(3) HTF market structure. A swing at bar q is confirmed only once bar
    q+k has closed, so at bar p we may only use swings with q <= p-k. The
    label is the direction of the last confirmed break of one of them."""
    out = [0] * len(sh)
    cur, hi, lo = 0, None, None
    for p in range(len(sh)):
        q = p - k
        if q >= k and q + k < len(sh):
            if sh.h[q] == max(sh.h[q - k:q + k + 1]):
                hi = sh.h[q]
            if sh.l[q] == min(sh.l[q - k:q + k + 1]):
                lo = sh.l[q]
        if hi is not None and sh.c[p] > hi:
            cur = +1
        elif lo is not None and sh.c[p] < lo:
            cur = -1
        out[p] = cur
    return out


def b_mom(sh, AH, n=20, band=0.5):
    """(4) The simplest one: is the HTF close above its own close n bars ago,
    by more than `band` * HTF ATR."""
    out = [0] * len(sh)
    for p in range(n, len(sh)):
        a = AH[p] or 0.0
        dv = sh.c[p] - sh.c[p - n]
        out[p] = 0 if abs(dv) < band * a else (1 if dv > 0 else -1)
    return out


def lab_sign(state, sl, j):
    return 0 if state is None else int(state)


def lab_pma(state, sl, j):
    if state is None or state[0] is None:
        return 0
    e, a, band = state
    dv = sl.c[j] - e
    return 0 if abs(dv) < band * a else (1 if dv > 0 else -1)


CTX = {
    "supertrend": (b_st, lab_sign, "HTF SuperTrend(10,3.0) direction"),
    "emaslope":   (b_emaslope, lab_sign, "HTF EMA(50) slope, +-0.05 ATR band"),
    "priceMA":    (b_pma, lab_pma, "sweep-bar price vs HTF EMA(50), +-0.25 ATR"),
    "structure":  (b_bos, lab_sign, "last confirmed HTF BOS/CHoCH"),
    "momentum":   (b_mom, lab_sign, "HTF close vs close 20 bars ago, +-0.5 ATR"),
}
CTXORDER = ["supertrend", "emaslope", "priceMA", "structure", "momentum"]


def labels_for(sm1, spm1, ltf, ctxtf, name):
    """Per-LTF-bar trend label, causal."""
    sl, _ = resample(sm1, spm1, TFMIN[ltf])
    sh, _ = resample(sm1, spm1, TFMIN[ctxtf])
    AH = watr(sh, 14)
    bld, lab, _ = CTX[name]
    states = map_state(sl, TFMIN[ltf], sh, TFMIN[ctxtf], bld(sh, AH))
    return [lab(states[j], sl, j) for j in range(len(sl))]


# ================================================================ the 2x2
# d = +1 is a LONG, which by construction is the fade of a swept LOW.
# d = -1 is a SHORT, the fade of a swept HIGH.
CELLDEF = [
    ("LOW swept / UP    WITH  ", +1, +1),
    ("HIGH swept/ DOWN  WITH  ", -1, -1),
    ("LOW swept / DOWN  AGAINST", +1, -1),
    ("HIGH swept/ UP    AGAINST", -1, +1),
    ("LOW swept / neutral     ", +1, 0),
    ("HIGH swept/ neutral     ", -1, 0),
]


def split_orders(orders, lab):
    """Partition the RETURN-entry order book by (direction, trend label at the
    sweep bar). Each partition is then simulated as its own book, so each
    cell's one-position-at-a-time gate is its own."""
    out = {k: [] for k in range(-1, 2)}
    buckets = {}
    for od in orders:
        arm, d = od[0], od[3]
        L = lab[arm] if arm < len(lab) else 0
        buckets.setdefault((d, L), []).append(od)
    return buckets


def pool(recs):
    return [x for r in recs for x in r]


def power(recs, sp):
    """Smallest per-trade NET edge this cell can resolve at t = 2."""
    n = len(recs)
    if n < 2:
        return float("nan")
    p = [x["net"] for x in recs]
    m = sum(p) / n
    sd = (sum((x - m) ** 2 for x in p) / (n - 1)) ** 0.5
    return 2.0 * sd / math.sqrt(n)


# CELLS: level timeframe -> execution timeframe. Same list E-169 used, so the
# comparison against its pooled numbers is like for like.
GRIDCELLS = HL.CELLS
EXECS = ["M1", "M5", "M15", "M30", "H1"]
CTXOF = {"M1": "M15", "M5": "H1", "M15": "H1", "M30": "H1", "H1": "H1"}


def run_books(sm1, spm1, ctxname, cells=None, lo=0.0, hi=1.0, cache=None,
              labcache=None, **kw):
    """For every (level TF, exec TF) cell, split the sweep book by trend
    context and simulate each partition. Returns
        pooled[(exec, d, L)] -> list of records
        per_book[(htf, ltf, d, L)] -> stats
    """
    cache = {} if cache is None else cache
    labcache = {} if labcache is None else labcache
    pooled, per_book, days, spreads = {}, {}, {}, {}
    for (htf, ltf) in (cells or GRIDCELLS):
        key = (htf, ltf)
        if key not in cache:
            cache[key] = build(sm1, spm1, ltf, htf, **kw)
        sl, SP, A, o, nsw, nlv = cache[key]
        lk = (ltf, CTXOF[ltf], ctxname)
        if lk not in labcache:
            labcache[lk] = labels_for(sm1, spm1, ltf, CTXOF[ltf], ctxname)
        lab = labcache[lk]
        n = len(sl); a, b = int(lo * n), int(hi * n)
        days[ltf] = len({(sl.ts[i] + HL.TZOFF) // 86400 for i in range(a, b)})
        spreads[ltf] = statistics.median(SP)
        orders = [x for x in o["return"] if a <= x[0] < b]
        for (d, L), sub in split_orders(orders, lab).items():
            r, gt = simulate(sl, SP, A, sub)
            pooled.setdefault((ltf, d, L), []).extend(r)
            per_book[(htf, ltf, d, L)] = r
    return pooled, per_book, days, spreads, cache, labcache


def print_2x2(title, pooled, days, spreads, execs=None):
    for ex in (execs or EXECS):
        rows = [(lbl, pooled.get((ex, d, L), [])) for (lbl, d, L) in CELLDEF]
        if sum(len(r) for _, r in rows) == 0:
            continue
        print("=" * 137)
        print(f"  {title}   exec {ex}   ctx {CTXOF[ex]}   "
              f"median spread {spreads.get(ex, 0):.4f} pts")
        print("=" * 137)
        print(HDR + f"{'t=2 power':>11}")
        wt, ag = [], []
        for (lbl, d, L) in CELLDEF:
            r = pooled.get((ex, d, L), [])
            z = summ(r, days.get(ex, 1))
            if z is None:
                print(f"  {lbl:<26}   no trades"); continue
            sys.stdout.write("")
            _line_with_power(lbl, z, power(r, spreads.get(ex, 0)))
            if L != 0:
                (wt if d == L else ag).append(r)
        for lbl, grp in (("  >> WITH-TREND both dirs", wt),
                         ("  >> AGAINST both dirs", ag)):
            rr = pool(grp)
            z = summ(rr, days.get(ex, 1))
            if z is not None:
                _line_with_power(lbl, z, power(rr, spreads.get(ex, 0)))
        allr = pool([pooled.get((ex, d, L), []) for (_, d, L) in CELLDEF])
        z = summ(allr, days.get(ex, 1))
        if z is not None:
            _line_with_power("  >> POOLED (E-169 view)", z,
                             power(allr, spreads.get(ex, 0)))
        print()


def _line_with_power(lbl, z, pw):
    sh = ("gross<=0" if z["share"] != z["share"] else f"{100*z['share']:.1f}%")
    print(f"  {lbl:<26}{z['n']:>5}{z['per_day']:>6.2f}{z['win']:>6.1f}"
          f"{z['gross']:>9.1f}{z['cost']:>8.1f}{z['net']:>9.1f}"
          f"{z['gper']:>+10.4f}{z['per']:>+10.4f}{z['t']:>7.2f}"
          f"{z['mdd']:>8.1f}{z['worst']:>7.2f}{sh:>12}{pw:>11.4f}")


# ==================================================================== null
def cmd_null(seeds=(101, 102, 103)):
    """RUN FIRST. Driftless random walk, real timestamps, real measured
    spread column, identical code path. Every cell of the 2x2 must come out
    at gross ~ 0 and net ~ -1 spread. If any cell makes money here the whole
    study is measuring itself."""
    sm1, spm1 = load_m1()
    cells = [("M15", "M5"), ("H1", "M15"), ("M15", "M1")]
    print("  NULL — driftless random walk, real ts, real spreads, same path.")
    print("  A martingale split by a trend label must still pay one spread")
    print("  in EVERY cell. A trend label cannot create an edge on a walk.\n")
    agg = {}
    for sd in seeds:
        ss, ssp, medr, syr = synth_m1(sm1, spm1, sd)
        print(f"  seed {sd}: real median M1 range {medr:.4f} -> "
              f"synthetic {syr:.4f}")
        cache, labcache = {}, {}
        for ctxname in ("supertrend", "momentum"):
            pooled, pb, days, sprd, cache, labcache = run_books(
                ss, ssp, ctxname, cells=cells, cache=cache, labcache=labcache)
            print_2x2(f"NULL seed {sd} ctx={ctxname}", pooled, days, sprd,
                      execs=["M1", "M5", "M15"])
            for k, v in pooled.items():
                agg.setdefault((ctxname,) + k, []).extend(v)
    print("=" * 137)
    print("  NULL, pooled over all seeds and both context definitions")
    print("=" * 137)
    print(f"  {'cell':<26}{'n':>7}{'gross/tr':>12}{'t(gross)':>10}"
          f"{'net/tr':>12}{'t(net)':>10}")
    for (lbl, d, L) in CELLDEF:
        rr = [x for k, v in agg.items() if k[2] == d and k[3] == L for x in v]
        if not rr:
            continue
        ng, mg, tg = tstat([x["gross"] for x in rr])
        nn, mn, tn = tstat([x["net"] for x in rr])
        print(f"  {lbl:<26}{ng:>7}{mg:>+12.4f}{tg:>10.2f}{mn:>+12.4f}{tn:>10.2f}")
    rr = [x for v in agg.values() for x in v]
    ng, mg, tg = tstat([x["gross"] for x in rr])
    nn, mn, tn = tstat([x["net"] for x in rr])
    cs = statistics.mean([x["cost"] for x in rr])
    print(f"  {'ALL NULL CELLS':<26}{ng:>7}{mg:>+12.4f}{tg:>10.2f}"
          f"{mn:>+12.4f}{tn:>10.2f}   mean cost charged {cs:.4f}")


# =================================================================== facts
def cmd_facts():
    """How the sweeps distribute across the buckets. If a label puts 90% of
    trades on one side it is not a 2x2, it is a relabelled baseline."""
    sm1, spm1 = load_m1()
    cache, labcache = {}, {}
    for ctxname in CTXORDER:
        print("=" * 100)
        print(f"  {ctxname}: {CTX[ctxname][2]}")
        print("=" * 100)
        print(f"  {'levels':<8}{'exec':<6}{'ctx':<6}{'sweeps':>8}{'up%':>8}"
              f"{'neut%':>8}{'down%':>8}{'lows':>8}{'highs':>8}{'WITH':>8}"
              f"{'AGST':>8}")
        for (htf, ltf) in GRIDCELLS:
            key = (htf, ltf)
            if key not in cache:
                cache[key] = build(sm1, spm1, ltf, htf)
            sl, SP, A, o, nsw, nlv = cache[key]
            lk = (ltf, CTXOF[ltf], ctxname)
            if lk not in labcache:
                labcache[lk] = labels_for(sm1, spm1, ltf, CTXOF[ltf], ctxname)
            lab = labcache[lk]
            oo = o["return"]
            if not oo:
                continue
            n = len(oo)
            up = sum(1 for x in oo if lab[x[0]] > 0)
            dn = sum(1 for x in oo if lab[x[0]] < 0)
            ne = n - up - dn
            lo_ = sum(1 for x in oo if x[3] > 0)
            wi = sum(1 for x in oo if lab[x[0]] != 0 and lab[x[0]] == x[3])
            ag = sum(1 for x in oo if lab[x[0]] != 0 and lab[x[0]] == -x[3])
            print(f"  {htf:<8}{ltf:<6}{CTXOF[ltf]:<6}{n:>8}{100*up/n:>8.1f}"
                  f"{100*ne/n:>8.1f}{100*dn/n:>8.1f}{lo_:>8}{n-lo_:>8}"
                  f"{wi:>8}{ag:>8}")
        print()


# ==================================================================== grid
def cmd_grid(ctxs=None, lo=0.0, hi=1.0, tag="REAL"):
    sm1, spm1 = load_m1()
    cache, labcache = {}, {}
    for ctxname in (ctxs or CTXORDER):
        print("#" * 137)
        print(f"#  CONTEXT: {ctxname} — {CTX[ctxname][2]}")
        print("#" * 137)
        pooled, pb, days, sprd, cache, labcache = run_books(
            sm1, spm1, ctxname, lo=lo, hi=hi, cache=cache, labcache=labcache)
        print_2x2(f"{tag} ctx={ctxname}", pooled, days, sprd)


def cmd_perbook(ctxname="supertrend"):
    """The same split without pooling across level timeframes, because the
    pooled t-statistics are inflated by overlapping trades."""
    sm1, spm1 = load_m1()
    pooled, pb, days, sprd, _, _ = run_books(sm1, spm1, ctxname)
    print("=" * 120)
    print(f"  PER BOOK, no pooling — ctx={ctxname}. WITH-trend vs AGAINST, "
          f"net points per trade.")
    print("=" * 120)
    print(f"  {'levels':<8}{'exec':<6}{'nWITH':>7}{'WITH/tr':>10}{'t':>7}"
          f"{'nAGST':>7}{'AGST/tr':>10}{'t':>7}{'same sign?':>12}")
    for (htf, ltf) in GRIDCELLS:
        w = pb.get((htf, ltf, +1, +1), []) + pb.get((htf, ltf, -1, -1), [])
        a = pb.get((htf, ltf, +1, -1), []) + pb.get((htf, ltf, -1, +1), [])
        nw, mw, tw = tstat([x["net"] for x in w])
        na, ma, ta = tstat([x["net"] for x in a])
        same = "yes" if (mw * ma) > 0 else "NO"
        print(f"  {htf:<8}{ltf:<6}{nw:>7}{mw:>+10.4f}{tw:>7.2f}"
              f"{na:>7}{ma:>+10.4f}{ta:>7.2f}{same:>12}")


# ===================================================== exit-free diagnostic
def cmd_edge(ctxs=None):
    """E-169's cleanest measurement, split by trend context. Fill every
    order, no gate, no stop, no cost; measure the raw directional move to the
    close H bars later. This judges the ENTRY apart from the exit."""
    sm1, spm1 = load_m1()
    HZ = (1, 5, 20, 50)
    cache, labcache = {}, {}
    for ctxname in (ctxs or CTXORDER):
        print("#" * 118)
        print(f"#  EXIT-FREE, ctx={ctxname} — {CTX[ctxname][2]}")
        print("#  gross move fill->close H bars later. no exit, no cost. "
              f"t in brackets.")
        print("#" * 118)
        agg = {}
        for (htf, ltf) in GRIDCELLS:
            key = (htf, ltf)
            if key not in cache:
                cache[key] = build(sm1, spm1, ltf, htf)
            sl, SP, A, o, nsw, nlv = cache[key]
            lk = (ltf, CTXOF[ltf], ctxname)
            if lk not in labcache:
                labcache[lk] = labels_for(sm1, spm1, ltf, CTXOF[ltf], ctxname)
            lab = labcache[lk]
            for (d, L), sub in split_orders(o["return"], lab).items():
                rows, fills, gt = forward(sl, A, sub, horizons=HZ)
                for h in HZ:
                    agg.setdefault((ltf, d, L, h), []).extend(rows[h])
        for ex in EXECS:
            if not any(k[0] == ex for k in agg):
                continue
            print(f"  --- exec {ex}, spread "
                  f"{statistics.median(cache[(GRIDCELLS[0][0], ex)][1]) if (GRIDCELLS[0][0], ex) in cache else float('nan'):.4f} ---"
                  if False else f"  --- exec {ex} ---")
            print(f"  {'cell':<26}{'fills':>7}" +
                  "".join(f"{'H=' + str(h):>16}" for h in HZ))
            for (lbl, d, L) in CELLDEF:
                cells, f0 = [], 0
                for h in HZ:
                    v = agg.get((ex, d, L, h), [])
                    nn, m, t = tstat(v)
                    f0 = max(f0, nn)
                    cells.append(f"{m:+.4f}({t:+.2f})" if nn > 1 else "  -  ")
                if f0 == 0:
                    continue
                print(f"  {lbl:<26}{f0:>7}" + "".join(f"{c:>16}" for c in cells))
            for nm, sel in (("  >> WITH-TREND", lambda d, L: L != 0 and d == L),
                            ("  >> AGAINST", lambda d, L: L != 0 and d == -L)):
                cells, f0 = [], 0
                for h in HZ:
                    v = [x for (e, d, L, hh), vv in agg.items()
                         if e == ex and hh == h and sel(d, L) for x in vv]
                    nn, m, t = tstat(v)
                    f0 = max(f0, nn)
                    cells.append(f"{m:+.4f}({t:+.2f})" if nn > 1 else "  -  ")
                print(f"  {nm:<26}{f0:>7}" + "".join(f"{c:>16}" for c in cells))
            print()


# ================================================================= halves
def cmd_oos(ctxs=None):
    """Time split of the EXEC series at its midpoint. The cut is fixed in
    advance (the midpoint), not searched. A cell only counts if the second
    half carries at least 100 trades."""
    sm1, spm1 = load_m1()
    cache, labcache = {}, {}
    for ctxname in (ctxs or CTXORDER):
        A_, pbA, dA, spA, cache, labcache = run_books(
            sm1, spm1, ctxname, lo=0.0, hi=0.5, cache=cache, labcache=labcache)
        B_, pbB, dB, spB, cache, labcache = run_books(
            sm1, spm1, ctxname, lo=0.5, hi=1.0, cache=cache, labcache=labcache)
        print("=" * 120)
        print(f"  HALVES — ctx={ctxname}. net points per trade.")
        print("=" * 120)
        print(f"  {'exec':<6}{'cell':<26}{'n1':>6}{'1st/tr':>10}{'t1':>7}"
              f"{'n2':>6}{'2nd/tr':>10}{'t2':>7}{'flip?':>8}{'n2>=100':>9}")
        for ex in EXECS:
            grp = [(lbl, [(d, L)]) for (lbl, d, L) in CELLDEF]
            grp.append(("WITH-TREND both", [(+1, +1), (-1, -1)]))
            grp.append(("AGAINST both", [(+1, -1), (-1, +1)]))
            for lbl, keys in grp:
                r1 = pool([A_.get((ex, d, L), []) for (d, L) in keys])
                r2 = pool([B_.get((ex, d, L), []) for (d, L) in keys])
                if not r1 and not r2:
                    continue
                n1, m1, t1 = tstat([x["net"] for x in r1])
                n2, m2, t2 = tstat([x["net"] for x in r2])
                fl = "FLIP" if m1 * m2 < 0 else "-"
                print(f"  {ex:<6}{lbl:<26}{n1:>6}{m1:>+10.4f}{t1:>7.2f}"
                      f"{n2:>6}{m2:>+10.4f}{t2:>7.2f}{fl:>8}"
                      f"{('yes' if n2 >= 100 else 'no'):>9}")
            print()


# ================================================================ control
def cmd_control(ctxname="supertrend", reps=12, seed=90210):
    """Matched control. For every real trade in a cell: same direction, same
    holding time in bars, a RANDOM entry bar, the same measured spread. If
    the real cell is not clear of this, the label is describing the market's
    drift, not the sweep."""
    sm1, spm1 = load_m1()
    rng = random.Random(seed)
    cache, labcache = {}, {}
    pooled, pb, days, sprd, cache, labcache = run_books(
        sm1, spm1, ctxname, cache=cache, labcache=labcache)
    # per-exec series for the control draws
    ser = {}
    for (htf, ltf) in GRIDCELLS:
        if ltf not in ser:
            sl, SP, A, o, _, _ = cache[(htf, ltf)]
            ser[ltf] = (sl, SP)
    print("=" * 118)
    print(f"  MATCHED CONTROL — ctx={ctxname}, {reps} reps, same directions,")
    print(f"  same holding times, random entry bars, same measured spread.")
    print("=" * 118)
    print(f"  {'exec':<6}{'cell':<26}{'n':>6}{'real/tr':>10}"
          f"{'ctrl/tr':>10}{'ctrl sd':>9}{'real-ctrl':>11}{'se above':>10}")
    for ex in EXECS:
        if ex not in ser:
            continue
        sl, SP = ser[ex]
        N = len(sl)
        grp = [(lbl, [(d, L)]) for (lbl, d, L) in CELLDEF]
        grp.append(("WITH-TREND both", [(+1, +1), (-1, -1)]))
        grp.append(("AGAINST both", [(+1, -1), (-1, +1)]))
        for lbl, keys in grp:
            r = pool([pooled.get((ex, d, L), []) for (d, L) in keys])
            if len(r) < 20:
                continue
            n, m, t = tstat([x["net"] for x in r])
            means = []
            for _ in range(reps):
                v = []
                for x in r:
                    hold = max(1, x["kk"] - x["j"])
                    k = rng.randrange(60, max(61, N - hold - 1))
                    d = x["d"]
                    g = d * (sl.c[k + hold] - sl.c[k])
                    v.append(g - (SP[k] + SP[k + hold]) / 2.0)
                means.append(sum(v) / len(v))
            cm = statistics.mean(means)
            csd = statistics.pstdev(means) if reps > 1 else 0.0
            own = (statistics.pstdev([x["net"] for x in r]) / math.sqrt(n)) if n else 0
            se = (m - cm) / own if own > 0 else float("nan")
            print(f"  {ex:<6}{lbl:<26}{n:>6}{m:>+10.4f}{cm:>+10.4f}"
                  f"{csd:>9.4f}{m - cm:>+11.4f}{se:>10.2f}")
        print()


# ================================================================= modern
MODCELLS = [("H4/H1", 240, 60, False, 1440),
            ("D1/H1", 1440, 60, True, 10080),
            ("D1/H4", 1440, 240, True, 10080)]


def cmd_modern(ctxname="momentum", spreads=(0.35,)):
    """GOLD_1h, 2024-04 -> 2026-08. An INDEPENDENT modern sample. Its cost is
    ASSUMED, so it is swept. Context timeframe is the third column."""
    sb, _ = load_plain("GOLD_1h", 0.35)
    print(f"  GOLD_1h: {len(sb)} bars  {sb.ts[0]} -> {sb.ts[-1]}  "
          f"{ndays(sb)} days   ASSUMED cost, swept {spreads}")
    for sp in spreads:
        spb = [sp] * len(sb)
        for (nm, htf_m, ltf_m, daily, ctx_m) in MODCELLS:
            sl, SP, A, o, nsw, nlv = build_min(sb, spb, ltf_m, htf_m,
                                               daily=daily)
            sh, _ = resample(sb, spb, ctx_m)
            AH = watr(sh, 14)
            bld, lab, _ = CTX[ctxname]
            st = map_state(sl, ltf_m, sh, ctx_m, bld(sh, AH))
            L = [lab(st[j], sl, j) for j in range(len(sl))]
            d_ = ndays(sl)
            print("=" * 137)
            print(f"  MODERN GOLD_1h  {nm}  ctx {ctx_m}min  ctx={ctxname}  "
                  f"assumed spread {sp}   ({nsw} sweeps)")
            print("=" * 137)
            print(HDR + f"{'t=2 power':>11}")
            buckets = split_orders(o["return"], L)
            recs = {}
            for (dd, LL), sub in buckets.items():
                r, gt = simulate(sl, SP, A, sub)
                recs[(dd, LL)] = r
            for (lbl, dd, LL) in CELLDEF:
                r = recs.get((dd, LL), [])
                z = summ(r, d_)
                if z is None:
                    continue
                _line_with_power(lbl, z, power(r, sp))
            for lbl, keys in (("  >> WITH-TREND both", [(+1, +1), (-1, -1)]),
                              ("  >> AGAINST both", [(+1, -1), (-1, +1)]),
                              ("  >> POOLED", [k for k in recs])):
                rr = pool([recs.get(k, []) for k in keys])
                z = summ(rr, d_)
                if z is not None:
                    _line_with_power(lbl, z, power(rr, sp))
            print()


# ================================================================== power
def cmd_power(ctxname="supertrend"):
    sm1, spm1 = load_m1()
    pooled, pb, days, sprd, _, _ = run_books(sm1, spm1, ctxname)
    print("=" * 100)
    print("  POWER. Smallest per-trade NET edge resolvable at t=2, against")
    print("  the median measured spread that cell is charged.")
    print("=" * 100)
    print(f"  {'exec':<6}{'cell':<26}{'n':>6}{'sd/trade':>10}"
          f"{'min |edge| @t=2':>17}{'spread':>9}{'verdict':>28}")
    for ex in EXECS:
        grp = [(lbl, [(d, L)]) for (lbl, d, L) in CELLDEF]
        grp.append(("WITH-TREND both", [(+1, +1), (-1, -1)]))
        grp.append(("AGAINST both", [(+1, -1), (-1, +1)]))
        for lbl, keys in grp:
            r = pool([pooled.get((ex, d, L), []) for (d, L) in keys])
            if len(r) < 2:
                continue
            v = [x["net"] for x in r]
            n = len(v)
            sd = statistics.stdev(v)
            mn = 2 * sd / math.sqrt(n)
            sp = sprd[ex]
            vd = ("powered" if mn < sp else "NO INFORMATION (res > spread)")
            print(f"  {ex:<6}{lbl:<26}{n:>6}{sd:>10.4f}{mn:>17.4f}"
                  f"{sp:>9.4f}{vd:>28}")
        print()


CMDS = {"null": cmd_null, "facts": cmd_facts, "grid": cmd_grid,
        "perbook": cmd_perbook, "edge": cmd_edge, "oos": cmd_oos,
        "control": cmd_control, "modern": cmd_modern, "power": cmd_power}

if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "facts"
    CMDS[c](*sys.argv[2:])

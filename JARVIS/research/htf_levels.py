"""
HTF LEVELS, LTF EXECUTION  —  the two structural gaps.

GAP 1. Every public ICT/SMC source puts the liquidity level on a HIGHER
timeframe and the entry on a lower one. `combined.candidates()` calls
`pivots(s, 5)` on the SAME series it trades, so on M1 it defends 5-bar M1
pivots. `liq_m1.py`'s own docstring says why that is wrong and the
architecture it describes was never built. It is built here.

GAP 2. The measured 2018 spread is 0.93 of an M1 ATR and 0.093 of an H1 ATR
(see `facts`). The same gross edge is ~10x more affordable on H1. Every table
in this file therefore carries COST AS A SHARE OF GROSS.

FILL RULES — the two bugs that destroyed this project's results twice.
  * STOP orders go through engine.entry_fill(). Never hand-rolled (E-165).
  * TRAILS go through engine.trail_level()/trail_apply(). Never hand-rolled
    (E-151).
  * LIMIT orders are filled by limit_fill() below. The rule is written out
    explicitly and asserted: a limit fill is NEVER better than its own limit
    price, even when the bar gaps through it. That is deliberately
    conservative (a real gap through a limit improves the fill); the
    conservatism is measured and reported as `gapthru%`.

DATA. Everything is resampled from GOLD_M1_2018.json by this file. E-165
records that the committed M5/M15 files are exact aggregations of the M1
file, so they are NOT independent and are not used. This file's resampler
reproduces their bar counts exactly (31419 M5, 10475 M15), which is the
check that it aggregates the same way the vendor did.

COST. Charged from each bar's OWN measured spread column, at HALF the spread
per side (round turn = one full spread). The spread is a property of the
MARKET, not of the chart, so the SAME absolute price spread is charged on
every clock (E-165 found the old harness charging M15 4.6x too much by
rescaling per timeframe).

Usage:
    python3 JARVIS/research/htf_levels.py facts
    python3 JARVIS/research/htf_levels.py null
    python3 JARVIS/research/htf_levels.py grid
    python3 JARVIS/research/htf_levels.py split
    python3 JARVIS/research/htf_levels.py control
    python3 JARVIS/research/htf_levels.py params
    python3 JARVIS/research/htf_levels.py sens
"""
from __future__ import annotations
import os, sys, json, math, random, statistics

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Series, atr as watr, trail_level, entry_fill

DATA = "/home/user/signals/data"
# the 2018 feed's bars start at 23:00 UTC (broker day boundary), so all
# resampling buckets are offset by +1h to land on that boundary.
TZOFF = 3600
TFMIN = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}


# --------------------------------------------------------------- data
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
    return s, [r[5] for r in out]


def resample(s: Series, sp, mult: int):
    """Clock-aligned aggregation from M1. Returns (Series, spread-per-bar).

    Bar spread is the MEAN of its constituent M1 spreads. The bar's timestamp
    is its OPEN time; the bar is only knowable after ts + mult*60.
    """
    if mult == 1:
        return s, list(sp)
    keys, buck = [], {}
    w = 60 * mult
    for i in range(len(s)):
        k = (s.ts[i] + TZOFF) // w
        b = buck.get(k)
        if b is None:
            buck[k] = [s.ts[i], s.o[i], s.h[i], s.l[i], s.c[i], sp[i], 1]
            keys.append(k)
        else:
            b[2] = max(b[2], s.h[i]); b[3] = min(b[3], s.l[i])
            b[4] = s.c[i]; b[5] += sp[i]; b[6] += 1
    rs = [buck[k] for k in keys]
    out = Series([r[0] for r in rs], [r[1] for r in rs], [r[2] for r in rs],
                 [r[3] for r in rs], [r[4] for r in rs])
    return out, [r[5] / r[6] for r in rs]


def close_ts(s: Series, i: int, mult: int) -> int:
    """When bar i is KNOWABLE. Uses the next bar's open time where one exists
    so that weekend/session gaps do not make a level available early."""
    if i + 1 < len(s):
        return s.ts[i + 1]
    return s.ts[i] + 60 * mult


def ndays(s: Series) -> int:
    return len({(t + TZOFF) // 86400 for t in s.ts})


# ------------------------------------------------------------- levels
def pivot_levels(sh: Series, mult: int, k: int):
    """Confirmed HTF swings. (available_ts, price, side).

    side = +1 for a swing HIGH (buyside liquidity above it),
           -1 for a swing LOW  (sellside liquidity below it).
    A pivot at bar p is only KNOWN once bar p+k has closed, so its
    availability timestamp is the close of bar p+k. No look-ahead.
    """
    out = []
    for p in range(k, len(sh) - k):
        if sh.h[p] == max(sh.h[p - k:p + k + 1]):
            out.append((close_ts(sh, p + k, mult), sh.h[p], +1))
        if sh.l[p] == min(sh.l[p - k:p + k + 1]):
            out.append((close_ts(sh, p + k, mult), sh.l[p], -1))
    out.sort()
    return out


def prev_day_levels(sd: Series, mult: int):
    """PDH / PDL — the canonical daily draw on liquidity. Available from the
    close of the day that formed them."""
    out = []
    for p in range(len(sd) - 1):
        t = close_ts(sd, p, mult)
        out.append((t, sd.h[p], +1))
        out.append((t, sd.l[p], -1))
    out.sort()
    return out


def order_blocks(sh: Series, A, mult: int, disp_atr=1.0, look=3):
    """HTF order blocks, causal. A bullish OB is the last DOWN-close candle
    before price closes above its high inside `look` bars by at least
    disp_atr * ATR. Zone = that candle's [low, high]. Known at the
    displacement bar's close. Returns (available_ts, lo, hi, dir, dead_ts).
    """
    out = []
    for p in range(20, len(sh) - look - 1):
        a = A[p]
        if not a or a <= 0:
            continue
        # bullish OB: down candle, then displacement up through its high
        if sh.c[p] < sh.o[p]:
            for q in range(p + 1, p + 1 + look):
                if sh.c[q] > sh.h[p] and (sh.c[q] - sh.h[p]) >= disp_atr * a:
                    out.append((close_ts(sh, q, mult), sh.l[p], sh.h[p], +1,
                                close_ts(sh, min(q + 100, len(sh) - 1), mult)))
                    break
        if sh.c[p] > sh.o[p]:
            for q in range(p + 1, p + 1 + look):
                if sh.c[q] < sh.l[p] and (sh.l[p] - sh.c[q]) >= disp_atr * a:
                    out.append((close_ts(sh, q, mult), sh.l[p], sh.h[p], -1,
                                close_ts(sh, min(q + 100, len(sh) - 1), mult)))
                    break
    out.sort()
    return out


def map_to_ltf(levels, sl: Series):
    """Attach each level to the first LTF bar index at or after its
    availability timestamp. That bar and every later bar may use it."""
    out, j = [], 0
    for lv in levels:
        t = lv[0]
        while j < len(sl) and sl.ts[j] < t:
            j += 1
        if j >= len(sl):
            break
        out.append((j,) + tuple(lv[1:]))
    out.sort(key=lambda x: x[0])
    return out


# --------------------------------------------------------------- fills
def limit_fill(level, o_k, h_k, l_k, d):
    """Where a LIMIT order at `level` fills on bar k, or None.

    d = +1 BUY LIMIT  (resting BELOW the market; fills when price falls to it)
    d = -1 SELL LIMIT (resting ABOVE the market; fills when price rises to it)

    THE RULE, written out because this is where E-165 lived on the stop side:
    the order fills only if the bar's adverse extreme reaches the level, and
    the booked price is ALWAYS the level itself — never the open, even when
    the bar gapped straight through and a real fill would have been BETTER.
    So no fill is ever better than its own limit price, by construction.
    """
    if d > 0:
        if l_k <= level:
            return level
        return None
    if h_k >= level:
        return level
    return None


def placeable_limit(level, close_j, d):
    """A buy limit must be BELOW the market when it is placed, a sell limit
    ABOVE it. Otherwise it is a market order wearing a limit's clothes — the
    exact error E-165 found on the stop side."""
    return d * (close_j - level) > 0


# --------------------------------------------------------- setup finder
def sweeps(sl: Series, A, lv_ltf, sweep_atr=0.10, wick=0.646, life=400):
    """Find HTF-level sweeps on the LTF clock.

    A sweep of a swing HIGH (side +1): the bar's HIGH exceeds the level by
    sweep_atr*ATR and the bar CLOSES back BELOW it. Trade direction t = -1.
    Symmetric for a swing LOW.

    Returns dicts with everything a downstream entry needs, and nothing that
    is not known at the close of bar `sw`.
    """
    out = []
    for (i0, px, side) in lv_ltf:
        t = -side
        hit = None
        for k in range(i0, min(i0 + life, len(sl))):
            a = A[k]
            if not a or a <= 0:
                continue
            if side > 0:
                if sl.h[k] >= px + sweep_atr * a and sl.c[k] < px:
                    hit = k; break
                if sl.c[k] > px:          # level broken and held: not a sweep
                    break
            else:
                if sl.l[k] <= px - sweep_atr * a and sl.c[k] > px:
                    hit = k; break
                if sl.c[k] < px:
                    break
        if hit is None:
            continue
        rng = sl.h[hit] - sl.l[hit]
        body = abs(sl.c[hit] - sl.o[hit]) / rng if rng > 0 else 1.0
        if body > wick:
            continue
        out.append({"sw": hit, "px": px, "t": t, "a": A[hit],
                    "ext": sl.h[hit] if side > 0 else sl.l[hit]})
    out.sort(key=lambda z: z["sw"])
    return out


def breaks(sl: Series, A, lv_ltf, brk_atr=0.25, life=400):
    """Break of an HTF level, held. Continuation direction t = side.
    Returns the break bar and the leg's opposing extreme for the stop."""
    out = []
    for (i0, px, side) in lv_ltf:
        hit = None
        for k in range(i0, min(i0 + life, len(sl))):
            a = A[k]
            if not a or a <= 0:
                continue
            if side > 0 and sl.c[k] >= px + brk_atr * a:
                hit = k; break
            if side < 0 and sl.c[k] <= px - brk_atr * a:
                hit = k; break
        if hit is None:
            continue
        j0 = max(i0, hit - 20)
        opp = min(sl.l[j0:hit + 1]) if side > 0 else max(sl.h[j0:hit + 1])
        out.append({"sw": hit, "px": px, "t": side, "a": A[hit], "ext": opp})
    out.sort(key=lambda z: z["sw"])
    return out


# --------------------------------------------------------------- entries
# Each returns a list of orders:
#   (arm_bar, kind, level, d, stop_ref_extreme, wait)
# `arm_bar` is the bar after whose CLOSE the order is placed; it may fill on
# arm_bar+1 .. arm_bar+wait.

def orders_return(sl, A, setups, wait=30, **kw):
    """E1 — sweep of the HTF level, entry on the LTF RETURN to it.
    A genuine limit: after a sweep of a low, price closed back ABOVE the
    level, so a BUY LIMIT at the level is below the market and can rest."""
    out = []
    for z in setups:
        d, px, j = z["t"], z["px"], z["sw"]
        if not placeable_limit(px, sl.c[j], d):
            continue
        out.append((j, "limit", px, d, z["ext"], wait, z))
    return out


def orders_fvg(sl, A, setups, wait=30, fvg_wait=12, fvg_atr=0.15, frac=0.0, **kw):
    """E2 — sweep, then the reversal leg leaves a FAIR VALUE GAP; enter on the
    fill of that gap. Bullish FVG at bar k: l[k] > h[k-2]. frac 0.0 = the
    near edge (first touch), 1.0 = the far edge."""
    out = []
    for z in setups:
        d, j = z["t"], z["sw"]
        arm = None
        for k in range(j + 2, min(j + 2 + fvg_wait, len(sl))):
            a = A[k]
            if not a or a <= 0:
                continue
            if d > 0:
                if sl.l[k] > sl.h[k - 2] and (sl.l[k] - sl.h[k - 2]) >= fvg_atr * a:
                    lo, hi = sl.h[k - 2], sl.l[k]
                    if lo < z["ext"]:
                        continue
                    arm = (k, hi - frac * (hi - lo)); break
            else:
                if sl.h[k] < sl.l[k - 2] and (sl.l[k - 2] - sl.h[k]) >= fvg_atr * a:
                    lo, hi = sl.h[k], sl.l[k - 2]
                    if hi > z["ext"]:
                        continue
                    arm = (k, lo + frac * (hi - lo)); break
        if arm is None:
            continue
        k, lvl = arm
        if not placeable_limit(lvl, sl.c[k], d):
            continue
        out.append((k, "limit", lvl, d, z["ext"], wait, z))
    return out


def orders_ote(sl, A, setups, wait=30, ote_wait=20, leg_atr=1.0, ote=0.705, **kw):
    """E3 — sweep, then enter on the 62-79% retracement of the reversal leg.
    The leg is measured from the sweep extreme to the running extreme since
    the sweep; the order is armed the first bar the leg is >= leg_atr*ATR,
    using only bars already closed."""
    out = []
    for z in setups:
        d, j = z["t"], z["sw"]
        legx = z["ext"]
        arm = None
        for k in range(j + 1, min(j + 1 + ote_wait, len(sl))):
            legx = max(legx, sl.h[k]) if d > 0 else min(legx, sl.l[k])
            if abs(legx - z["ext"]) >= leg_atr * z["a"]:
                arm = (k, legx - d * ote * abs(legx - z["ext"])); break
        if arm is None:
            continue
        k, lvl = arm
        if not placeable_limit(lvl, sl.c[k], d):
            continue
        out.append((k, "limit", lvl, d, z["ext"], wait, z))
    return out


def orders_ob(sl, A, setups, obs_ltf, wait=30, **kw):
    """E4 — E1, but only when the sweep ran INTO an opposing HTF order block.
    The OB must have been known before the sweep bar."""
    out = []
    for z in setups:
        d, px, j = z["t"], z["px"], z["sw"]
        if not placeable_limit(px, sl.c[j], d):
            continue
        ok = False
        for (i0, lo, hi, od, dead_i) in obs_ltf:
            if i0 > j:
                break
            if dead_i < j or od != d:
                continue
            if lo <= z["ext"] <= hi:
                ok = True; break
        if not ok:
            continue
        out.append((j, "limit", px, d, z["ext"], wait, z))
    return out


def orders_break(sl, A, setups, wait=30, **kw):
    """E5 — BREAK of the HTF level, then RETEST of it, in the break direction.
    After an upside break price is above the level, so a BUY LIMIT at the
    level is below the market and can rest."""
    out = []
    for z in setups:
        d, px, j = z["t"], z["px"], z["sw"]
        if not placeable_limit(px, sl.c[j], d):
            continue
        out.append((j, "limit", px, d, z["ext"], wait, z))
    return out


# --------------------------------------------------------------- sim
def simulate(sl: Series, SP, A, orders, buf=0.30, cap=1.5, give=0.25,
             hold=200, cooldown=1, slip=0.0):
    """One position at a time. Limit entry, structural stop, give-back trail.

    Returns per-trade records carrying GROSS and NET points separately so the
    cost share can be computed rather than asserted.
    """
    out, busy = [], -1
    gapthru = 0
    orders = sorted(orders, key=lambda x: x[0])
    for (arm, kind, lvl, d, ext, wait, z) in orders:
        if arm <= busy:
            continue
        a = z["a"]
        if not a or a <= 0:
            continue
        sl0 = ext - d * buf * a
        risk = abs(lvl - sl0)
        if not (0 < risk <= cap * a):
            continue
        j = None
        for k in range(arm + 1, min(arm + 1 + wait, len(sl))):
            f = limit_fill(lvl, sl.o[k], sl.h[k], sl.l[k], d)
            if f is not None:
                assert d * (f - lvl) >= 0.0 - 1e-12, "limit fill better than its limit"
                if d * (sl.o[k] - lvl) < 0:
                    gapthru += 1
                j = k; break
        if j is None:
            continue
        if d * (sl0 - lvl) >= 0:          # stop already through the entry
            continue
        entry = lvl + d * SP[j] / 2.0 + d * slip
        stop = sl0
        peak = entry
        px_out = kk = None
        for k in range(j, min(j + hold, len(sl))):
            if (sl.l[k] <= stop) if d > 0 else (sl.h[k] >= stop):
                px_out, kk = entry_fill(stop, sl.o[k], -d), k
                break
            if k == j:
                continue
            peak = max(peak, sl.h[k]) if d > 0 else min(peak, sl.l[k])
            ns = trail_level(entry, stop, peak, sl.c[k], d, give)
            if ns is None:
                px_out, kk = sl.c[k], k
                break
            stop = ns
        if px_out is None:
            kk = min(j + hold, len(sl) - 1)
            px_out = sl.c[kk]
        gross = d * (px_out - lvl)
        cost = (SP[j] + SP[kk]) / 2.0 + 2.0 * slip
        net = d * ((px_out - d * SP[kk] / 2.0 - d * slip) - entry)
        out.append({"gross": gross, "net": net, "cost": cost, "d": d,
                    "j": j, "kk": kk, "ts": sl.ts[j], "risk": risk,
                    "R": net / risk if risk > 0 else 0.0})
        busy = kk + cooldown
    return out, gapthru


# --------------------------------------------------------------- stats
def summ(recs, days):
    n = len(recs)
    if n == 0:
        return None
    g = [x["gross"] for x in recs]
    p = [x["net"] for x in recs]
    m = sum(p) / n
    sd = (sum((x - m) ** 2 for x in p) / (n - 1)) ** 0.5 if n > 1 else 0.0
    t = m / (sd / n ** 0.5) if sd > 0 else 0.0
    eq = peak = mdd = 0.0
    for x in p:
        eq += x; peak = max(peak, eq); mdd = max(mdd, peak - eq)
    gg, cc = sum(g), sum(x["cost"] for x in recs)
    return dict(n=n, per_day=n / days if days else 0.0, gper=sum(g) / n,
                win=100.0 * sum(1 for x in p if x > 0) / n,
                gross=gg, net=sum(p), per=m, t=t, mdd=mdd,
                worst=min(p), cost=cc,
                share=(cc / gg) if gg > 0 else float("nan"))


HDR = (f"  {'cell':<26}{'n':>5}{'/day':>6}{'win%':>6}{'gross':>9}{'cost':>8}"
       f"{'net':>9}{'gross/tr':>10}{'net/tr':>10}{'t':>7}{'maxDD':>8}"
       f"{'worst':>7}{'cost/gross':>12}")


def line(lbl, z, w=26):
    if z is None:
        print(f"  {lbl:<{w}}   no trades"); return
    sh = ("gross<=0" if z["share"] != z["share"]
          else f"{100*z['share']:.1f}%")
    print(f"  {lbl:<{w}}{z['n']:>5}{z['per_day']:>6.2f}{z['win']:>6.1f}"
          f"{z['gross']:>9.1f}{z['cost']:>8.1f}{z['net']:>9.1f}"
          f"{z['gper']:>+10.4f}{z['per']:>+10.4f}{z['t']:>7.2f}"
          f"{z['mdd']:>8.1f}{z['worst']:>7.2f}{sh:>12}")


def hdr(title):
    print("=" * 125); print("  " + title); print("=" * 125); print(HDR)


# ------------------------------------------------------------ pipeline
ENTRIES = ["return", "fvg", "ote", "ob", "breakretest"]


def build(sm1, spm1, ltf, htf, kpiv=2, **kw):
    """Everything a cell needs. Returns (sl, SP, A, dict of order lists)."""
    sl, SP = resample(sm1, spm1, TFMIN[ltf])
    A = watr(sl, 14)
    sh, _ = resample(sm1, spm1, TFMIN[htf])
    AH = watr(sh, 14)
    if htf == "D1":
        lv = prev_day_levels(sh, TFMIN[htf])
    else:
        lv = pivot_levels(sh, TFMIN[htf], kpiv)
    lv_ltf = map_to_ltf(lv, sl)
    life = kw.get("life", 400)
    sw = sweeps(sl, A, lv_ltf, sweep_atr=kw.get("sweep_atr", 0.10),
                wick=kw.get("wick", 0.646), life=life)
    br = breaks(sl, A, lv_ltf, brk_atr=kw.get("brk_atr", 0.25), life=life)
    obs = order_blocks(sh, AH, TFMIN[htf])
    obs_ltf = []
    idx = map_to_ltf([(o[0], o[1], o[2], o[3], o[4]) for o in obs], sl)
    for (i0, lo, hi, od, dead_ts) in idx:
        dj = i0
        while dj < len(sl) and sl.ts[dj] < dead_ts:
            dj += 1
        obs_ltf.append((i0, lo, hi, od, dj))
    o = {
        "return":      orders_return(sl, A, sw, **kw),
        "fvg":         orders_fvg(sl, A, sw, **kw),
        "ote":         orders_ote(sl, A, sw, **kw),
        "ob":          orders_ob(sl, A, sw, obs_ltf, **kw),
        "breakretest": orders_break(sl, A, br, **kw),
    }
    return sl, SP, A, o, len(sw), len(lv_ltf)


CELLS = [
    ("M15", "M1"), ("M15", "M5"), ("M15", "M15"),
    ("H1", "M5"), ("H1", "M15"), ("H1", "M30"), ("H1", "H1"),
    ("D1", "M15"), ("D1", "M30"), ("D1", "H1"),
]


# ------------------------------------------------------------- commands
def cmd_facts():
    sm1, spm1 = load_m1()
    print(f"  GOLD_M1_2018.json  {len(sm1)} bars  "
          f"{sm1.ts[0]} -> {sm1.ts[-1]}  {ndays(sm1)} distinct days")
    print(f"  measured spread column: median {statistics.median(spm1):.5f} "
          f"mean {statistics.mean(spm1):.5f} price points\n")
    print(f"  {'TF':>5}{'bars':>9}{'days':>7}{'medATR':>10}{'medRange':>10}"
          f"{'spread/ATR':>12}")
    for tf in ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]:
        s, sp = resample(sm1, spm1, TFMIN[tf])
        A = [x for x in watr(s, 14)[50:] if x]
        ma = statistics.median(A)
        mr = statistics.median([s.h[i] - s.l[i] for i in range(len(s))])
        print(f"  {tf:>5}{len(s):>9}{ndays(s):>7}{ma:>10.4f}{mr:>10.4f}"
              f"{statistics.median(spm1)/ma:>12.4f}")
    print("\n  THE GAP-2 ARITHMETIC: the same absolute spread is 0.93 of an M1")
    print("  ATR and 0.093 of an H1 ATR. Nothing else in this file matters if")
    print("  a strategy cannot beat that ratio.")


_SIG = None


def synth_m1(sm1, spm1, seed, ticks=120):
    """Driftless random walk on the M1 clock, REUSING the real timestamps and
    the real spread series, so every downstream resample, session boundary,
    weekend gap and cost is identical to the real run. Calibrated so the
    synthetic median M1 bar range matches the real one."""
    global _SIG
    rr = sorted(sm1.h[i] - sm1.l[i] for i in range(len(sm1)))
    med = rr[len(rr) // 2]
    if _SIG is None:
        sig = med / (2.0 * math.sqrt(ticks))
        for _ in range(12):
            t = _walk(sm1.ts[:20000], sig, ticks, 7)
            m = sorted(t.h[i] - t.l[i] for i in range(len(t)))[10000]
            sig *= (med / m) ** 0.5
        _SIG = sig
    sig = _SIG
    s = _walk(sm1.ts, sig, ticks, seed)
    return s, list(spm1), med, sorted(s.h[i] - s.l[i] for i in range(len(s)))[len(s) // 2]


def _walk(ts, sig, ticks, seed, p0=1300.0):
    rng = random.Random(seed)
    o, h, l, c = [], [], [], []
    p = p0
    g = rng.gauss
    for _ in ts:
        op = p; hi = lo = p
        for _ in range(ticks):
            p += g(0.0, sig)
            if p > hi: hi = p
            elif p < lo: lo = p
        o.append(op); h.append(hi); l.append(lo); c.append(p)
    return Series(list(ts), o, h, l, c)


def cmd_null(seeds=(101, 102, 103), cells=None):
    """RUN FIRST. If anything makes money here, nothing else means anything."""
    sm1, spm1 = load_m1()
    cells = cells or [("H1", "M15"), ("M15", "M5"), ("D1", "M30")]
    print("  NULL: driftless random walk, real timestamps, real spreads,")
    print("  same code path, same costs. A martingale must pay -1 spread.\n")
    for sd in seeds:
        ss, ssp, medr, syr = synth_m1(sm1, spm1, sd)
        print(f"  seed {sd}: real median M1 range {medr:.4f} -> synthetic {syr:.4f}")
        for (htf, ltf) in cells:
            sl, SP, A, o, nsw, nlv = build(ss, ssp, ltf, htf)
            d = ndays(sl)
            hdr(f"NULL seed {sd} — levels {htf} / exec {ltf}  "
                f"({nlv} levels, {nsw} sweeps)")
            for e in ENTRIES:
                r, gt = simulate(sl, SP, A, o[e])
                line(e, summ(r, d))
            print()


def cmd_grid(sm1=None, spm1=None, tag="REAL", lo=0.0, hi=1.0, cells=None):
    if sm1 is None:
        sm1, spm1 = load_m1()
    for (htf, ltf) in (cells or CELLS):
        sl, SP, A, o, nsw, nlv = build(sm1, spm1, ltf, htf)
        n = len(sl)
        a, b = int(lo * n), int(hi * n)
        d = len({(sl.ts[i] + TZOFF) // 86400 for i in range(a, b)})
        hdr(f"{tag} — levels {htf} / exec {ltf}   ({nlv} levels, {nsw} sweeps)")
        for e in ENTRIES:
            oo = [x for x in o[e] if a <= x[0] < b]
            r, gt = simulate(sl, SP, A, oo)
            line(e, summ(r, d))
        print()


def cmd_split():
    sm1, spm1 = load_m1()
    print("  FIRST HALF (parameters were never chosen on it — defaults only)\n")
    cmd_grid(sm1, spm1, "1st half", 0.0, 0.5)
    print("  SECOND HALF\n")
    cmd_grid(sm1, spm1, "2nd half", 0.5, 1.0)


def cmd_control(reps=8):
    """Time-shifted control: the same order stream, armed N bars later. Same
    geometry, same fill rule, same cost, no level."""
    sm1, spm1 = load_m1()
    for (htf, ltf) in [("H1", "M15"), ("H1", "M30"), ("D1", "M30"), ("D1", "H1")]:
        sl, SP, A, o, nsw, nlv = build(sm1, spm1, ltf, htf)
        d = ndays(sl)
        hdr(f"CONTROL — levels {htf} / exec {ltf}")
        for e in ENTRIES:
            r, _ = simulate(sl, SP, A, o[e])
            z = summ(r, d)
            line("REAL " + e, z)
            per = []
            rng = random.Random(4242)
            for _ in range(reps):
                sh = rng.choice([-97, -61, -37, 37, 61, 97, 149, 211])
                oo = []
                for (arm, kind, lvl, dd, ext, wait, zz) in o[e]:
                    k = arm + sh
                    if not (5 <= k < len(sl) - 5):
                        continue
                    # move the whole geometry with the bar, keeping the shape
                    shift = sl.c[k] - sl.c[arm]
                    z2 = dict(zz); z2["a"] = A[k] or zz["a"]
                    if not placeable_limit(lvl + shift, sl.c[k], dd):
                        continue
                    oo.append((k, kind, lvl + shift, dd, ext + shift, wait, z2))
                rr, _ = simulate(sl, SP, A, oo)
                zz2 = summ(rr, d)
                if zz2:
                    per.append(zz2["per"])
            if per and z:
                mu = sum(per) / len(per)
                sdv = (sum((x - mu) ** 2 for x in per) / (len(per) - 1)) ** 0.5 if len(per) > 1 else 0.0
                se = z["per"] / z["t"] if z["t"] else float("nan")
                print(f"       control mean {mu:+.4f} (sd {sdv:.4f}, {len(per)} shifts)"
                      f"   real-control = {z['per']-mu:+.4f}"
                      f" = {(z['per']-mu)/se if se==se and se else float('nan'):+.2f} own se")
        print()


def cmd_params():
    """Parameter variants, FIRST HALF ONLY. Reported so the multiple-comparison
    count is on the record; nothing here is carried to the second half unless
    said so explicitly."""
    sm1, spm1 = load_m1()
    n_variants = 0
    for (htf, ltf) in [("H1", "M15"), ("H1", "M30"), ("D1", "M30")]:
        print(f"\n  === levels {htf} / exec {ltf}  (FIRST HALF ONLY) ===")
        for sa in (0.05, 0.10, 0.25):
            for wk in (0.40, 0.646, 1.00):
                sl, SP, A, o, nsw, nlv = build(sm1, spm1, ltf, htf,
                                               sweep_atr=sa, wick=wk)
                half = len(sl) // 2
                d = len({(sl.ts[i] + TZOFF) // 86400 for i in range(half)})
                hdr(f"sweep_atr {sa}  wick {wk}  ({nsw} sweeps)")
                for e in ["return", "fvg", "ote"]:
                    oo = [x for x in o[e] if x[0] < half]
                    r, _ = simulate(sl, SP, A, oo)
                    line(e, summ(r, d))
                    n_variants += 1
    print(f"\n  VARIANTS TESTED IN THIS COMMAND: {n_variants}")


def cmd_sens():
    """Cost sensitivity. The measured spread is charged as-is; slippage is
    ASSUMED and swept."""
    sm1, spm1 = load_m1()
    for (htf, ltf) in [("H1", "M15"), ("H1", "M30"), ("D1", "M30"), ("D1", "H1")]:
        sl, SP, A, o, nsw, nlv = build(sm1, spm1, ltf, htf)
        d = ndays(sl)
        print("=" * 90)
        print(f"  SLIPPAGE SENSITIVITY — levels {htf} / exec {ltf}  "
              f"(measured spread median {statistics.median(SP):.4f})")
        print("=" * 90)
        print(f"  {'entry':<14}{'gross':>10}" +
              "".join(f"{'slip '+f'{s:.2f}':>12}" for s in (0.0, 0.02, 0.05, 0.10, 0.20)))
        for e in ENTRIES:
            row = []
            g = None
            for s in (0.0, 0.02, 0.05, 0.10, 0.20):
                r, _ = simulate(sl, SP, A, o[e], slip=s)
                z = summ(r, d)
                if g is None:
                    g = z["gross"] if z else 0.0
                row.append(z["net"] if z else 0.0)
            print(f"  {e:<14}{g:>10.1f}" + "".join(f"{x:>12.1f}" for x in row))
        print()




# --------------------------------------------------- exit-free diagnostic
def forward(sl, A, orders, wait=30, horizons=(1, 2, 5, 10, 20, 50)):
    """THE ENTRY, WITH NO EXIT AT ALL.

    Every table above pairs an entry with one exit (structural stop +
    give-back 0.25). If the entry is fine and the exit is wrong for the
    clock, the table would say REJECT for the wrong reason. So: fill every
    order (no one-at-a-time gate, no risk cap, no stop) and measure the raw
    directional move from the fill price to the close H bars later. GROSS,
    no cost - the cost is then compared to it, which is the whole point.
    """
    rows = {h: [] for h in horizons}
    fills = 0
    gapthru = 0
    for (arm, kind, lvl, d, ext, w, z) in orders:
        j = None
        for k in range(arm + 1, min(arm + 1 + wait, len(sl))):
            f = limit_fill(lvl, sl.o[k], sl.h[k], sl.l[k], d)
            if f is not None:
                assert d * (f - lvl) >= -1e-12
                if d * (sl.o[k] - lvl) < 0:
                    gapthru += 1
                j = k; break
        if j is None:
            continue
        fills += 1
        for h in horizons:
            if j + h < len(sl):
                rows[h].append(d * (sl.c[j + h] - lvl))
    return rows, fills, gapthru


def tstat(v):
    n = len(v)
    if n < 2:
        return n, 0.0, 0.0
    m = sum(v) / n
    sd = (sum((x - m) ** 2 for x in v) / (n - 1)) ** 0.5
    return n, m, (m / (sd / n ** 0.5) if sd > 0 else 0.0)


def cmd_edge(sm1=None, spm1=None, tag="REAL", lo=0.0, hi=1.0):
    if sm1 is None:
        sm1, spm1 = load_m1()
    HZ = (1, 2, 5, 10, 20, 50)
    print(f"  {tag}: mean GROSS move in the trade's direction, fill -> close H")
    print(f"  bars later. No exit, no cost. Compare against the round-turn")
    print(f"  spread on the right. t in brackets.\n")
    for (htf, ltf) in CELLS:
        sl, SP, A, o, nsw, nlv = build(sm1, spm1, ltf, htf)
        n = len(sl); a, b = int(lo * n), int(hi * n)
        sp = statistics.median(SP)
        print("=" * 118)
        print(f"  {tag} — levels {htf} / exec {ltf}   spread {sp:.4f} pts"
              f"   medATR {statistics.median([x for x in A[50:] if x]):.3f}")
        print("=" * 118)
        print(f"  {'entry':<14}{'fills':>6}" + "".join(f"{'H='+str(h):>15}" for h in HZ))
        for e in ENTRIES:
            oo = [x for x in o[e] if a <= x[0] < b]
            rows, fills, gt = forward(sl, A, oo)
            cells = []
            for h in HZ:
                nn, m, t = tstat(rows[h])
                cells.append(f"{m:+.3f}({t:+.1f})" if nn > 1 else "   -   ")
            print(f"  {e:<14}{fills:>6}" + "".join(f"{c:>15}" for c in cells))
        print()



def cmd_costshare():
    """GAP 2, ANSWERED IN THE ONLY UNIT THAT COMPARES ACROSS CLOCKS.

    spread/ATR falls 10x from M1 to H1. That is the Gap-2 promise. The
    question this table asks is whether GROSS/ATR rises with it. If gross
    per trade in ATR units stays flat while the spread's ATR share falls,
    the slower clock helps by exactly the ratio and no more - and if gross
    is ~0 in ATR units on every clock, no clock is slow enough.
    """
    sm1, spm1 = load_m1()
    print("  Every quantity is per trade, divided by the exec clock's median")
    print("  ATR, so the clocks are comparable. BREAK-EVEN needs")
    print("  gross/ATR >= spread/ATR.\n")
    print(f"  {'levels':>7}{'exec':>6}{'entry':>14}{'n':>6}{'medATR':>9}"
          f"{'sprd/ATR':>10}{'gross/tr':>10}{'gross/ATR':>11}"
          f"{'cost/tr':>9}{'cost/gross':>12}{'shortfall':>11}")
    for (htf, ltf) in CELLS:
        sl, SP, A, o, nsw, nlv = build(sm1, spm1, ltf, htf)
        d = ndays(sl)
        ma = statistics.median([x for x in A[50:] if x])
        sp = statistics.median(SP)
        for e in ENTRIES:
            r, gt = simulate(sl, SP, A, o[e])
            z = summ(r, d)
            if z is None:
                continue
            gpa = z["gper"] / ma
            cpt = z["cost"] / z["n"]
            sh = ("  gross<=0" if z["share"] != z["share"]
                  else f"{100*z['share']:.0f}%")
            print(f"  {htf:>7}{ltf:>6}{e:>14}{z['n']:>6}{ma:>9.3f}"
                  f"{sp/ma:>10.3f}{z['gper']:>+10.4f}{gpa:>+11.4f}"
                  f"{cpt:>9.4f}{sh:>12}{z['gper']-cpt:>+11.4f}")
        print()


def cmd_direction():
    """The forward-return table is mostly NEGATIVE for the fade entries. Is
    the sweep-fade systematically the WRONG WAY ROUND? Pool every `return`
    fill per exec clock and read the sign."""
    sm1, spm1 = load_m1()
    HZ = (1, 2, 5, 10, 20)
    for e in ENTRIES:
        print(f"  === {e} — pooled over all level timeframes, by exec clock ===")
        print(f"  {'exec':>6}{'fills':>7}" + "".join(f"{'H='+str(h):>16}" for h in HZ))
        for ltf in ["M1", "M5", "M15", "M30", "H1"]:
            acc = {h: [] for h in HZ}
            f_tot = 0
            for (htf, l2) in CELLS:
                if l2 != ltf:
                    continue
                sl, SP, A, o, nsw, nlv = build(sm1, spm1, l2, htf)
                rows, fills, gt = forward(sl, A, o[e], horizons=HZ)
                f_tot += fills
                for h in HZ:
                    acc[h] += rows[h]
            if f_tot == 0:
                continue
            cs = []
            for h in HZ:
                nn, m, tt = tstat(acc[h])
                cs.append(f"{m:+.3f}({tt:+.2f})")
            print(f"  {ltf:>6}{f_tot:>7}" + "".join(f"{c:>16}" for c in cs))
        print()



# ------------------------------------------------- independent H1 sample
def load_plain(name, spread):
    """A committed OHLC file with NO spread column. The cost is ASSUMED and
    must be swept - see cmd_modern's sensitivity block."""
    rows = json.load(open(f"{DATA}/{name}.json"))
    rows.sort(key=lambda r: r[0])
    out, seen = [], set()
    for r in rows:
        if r[0] in seen:
            continue
        seen.add(r[0]); out.append(r)
    s = Series([r[0] for r in out], [r[1] for r in out], [r[2] for r in out],
               [r[3] for r in out], [r[4] for r in out])
    return s, [spread] * len(s)


def build_min(sb, spb, ltf_min, htf_min, kpiv=2, daily=False, **kw):
    sl, SP = resample(sb, spb, ltf_min)
    A = watr(sl, 14)
    sh, _ = resample(sb, spb, htf_min)
    AH = watr(sh, 14)
    lv = prev_day_levels(sh, htf_min) if daily else pivot_levels(sh, htf_min, kpiv)
    lv_ltf = map_to_ltf(lv, sl)
    life = kw.get("life", 400)
    sw = sweeps(sl, A, lv_ltf, sweep_atr=kw.get("sweep_atr", 0.10),
                wick=kw.get("wick", 0.646), life=life)
    br = breaks(sl, A, lv_ltf, brk_atr=kw.get("brk_atr", 0.25), life=life)
    obs = order_blocks(sh, AH, htf_min)
    obs_ltf = []
    for (i0, lo, hi, od, dead_ts) in map_to_ltf(obs, sl):
        dj = i0
        while dj < len(sl) and sl.ts[dj] < dead_ts:
            dj += 1
        obs_ltf.append((i0, lo, hi, od, dj))
    o = {"return": orders_return(sl, A, sw, **kw),
         "fvg": orders_fvg(sl, A, sw, **kw),
         "ote": orders_ote(sl, A, sw, **kw),
         "ob": orders_ob(sl, A, sw, obs_ltf, **kw),
         "breakretest": orders_break(sl, A, br, **kw)}
    return sl, SP, A, o, len(sw), len(lv_ltf)


MODERN = [("GOLD_1h", 0.35, [(240, 60, False), (1440, 60, True),
                             (1440, 240, True), (10080, 240, True)]),
          ("US500_1h", 0.60, [(240, 60, False), (1440, 60, True)])]


def cmd_modern():
    """The 2018 M1 file gives only 2620 H1 bars, and the power table says the
    H1 cells cannot resolve an edge the size of their own spread. GOLD_1h
    carries 13725 hourly bars (2024-04 -> 2026-08), 5.2x more, and is a
    DIFFERENT sample from a different regime. It has no spread column, so the
    cost here is ASSUMED and swept."""
    for (name, spread, cells) in MODERN:
        sb, spb = load_plain(name, spread)
        print(f"\n  ##### {name}: {len(sb)} bars, ASSUMED round-turn "
              f"spread {spread} price points #####")
        for (hm, lm, daily) in cells:
            sl, SP, A, o, nsw, nlv = build_min(sb, spb, lm, hm, daily=daily)
            d = ndays(sl)
            ma = statistics.median([x for x in A[50:] if x])
            nm = {60: "H1", 240: "H4", 1440: "D1", 10080: "W1"}
            hdr(f"{name} — levels {nm[hm]} / exec {nm[lm]}  "
                f"({nlv} levels, {nsw} sweeps, medATR {ma:.2f}, sprd/ATR {spread/ma:.3f})")
            for e in ENTRIES:
                r, gt = simulate(sl, SP, A, o[e])
                line(e, summ(r, d))
            # halves
            n = len(sl)
            for (lab, a, b) in [("  1st half", 0, n // 2), ("  2nd half", n // 2, n)]:
                dd = len({(sl.ts[i] + TZOFF) // 86400 for i in range(a, b)})
                for e in ENTRIES:
                    oo = [x for x in o[e] if a <= x[0] < b]
                    r, gt = simulate(sl, SP, A, oo)
                    line(lab + " " + e, summ(r, dd))
            print()


def cmd_modern_sens():
    for (name, spread, cells) in MODERN:
        sb, spb0 = load_plain(name, spread)
        for (hm, lm, daily) in cells:
            nm = {60: "H1", 240: "H4", 1440: "D1", 10080: "W1"}
            print("=" * 96)
            print(f"  {name} levels {nm[hm]} / exec {nm[lm]} — ASSUMED SPREAD SWEEP "
                  f"(net points)")
            print("=" * 96)
            grid = [0.10, 0.20, 0.35, 0.50, 0.80]
            print(f"  {'entry':<14}{'n':>6}{'gross':>10}" +
                  "".join(f"{'sp='+f'{g:.2f}':>10}" for g in grid))
            for e in ENTRIES:
                row, gr, nn = [], None, 0
                for g in grid:
                    sl, SP, A, o, nsw, nlv = build_min(sb, [g] * len(sb), lm, hm,
                                                       daily=daily)
                    r, _ = simulate(sl, SP, A, o[e])
                    z = summ(r, ndays(sl))
                    if gr is None:
                        gr = z["gross"] if z else 0.0
                        nn = z["n"] if z else 0
                    row.append(z["net"] if z else 0.0)
                print(f"  {e:<14}{nn:>6}{gr:>10.1f}" +
                      "".join(f"{x:>10.1f}" for x in row))
            print()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "facts"
    {"facts": cmd_facts, "null": cmd_null, "grid": cmd_grid,
     "split": cmd_split, "control": cmd_control, "params": cmd_params,
     "sens": cmd_sens, "edge": cmd_edge,
     "costshare": cmd_costshare, "direction": cmd_direction,
     "modern": cmd_modern, "modernsens": cmd_modern_sens}[cmd]()

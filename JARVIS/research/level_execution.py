"""
E-054 — GIVEN that price has arrived at a level, HOW should it be traded?

The companion question (does a level react at all, and which levels) belongs
to `level_reaction.py`. This script assumes the level and asks only about the
EXECUTION RULE: touch, rejection, break-and-retest, break-follow — against a
count-matched random control, because E-050 established that a payoff
structure alone produces a positive number and that every claim here must be
reported beside a random arm on the same bars with the same exits.

--------------------------------------------------------------------------
HYPOTHESES, FALSIFIABLE, WITH MECHANISMS
--------------------------------------------------------------------------
H1 (patience) Waiting for a REJECTION close — a bar that pierces the level
   and closes back on the side it came from — produces a higher
   P(+1R before -1R) and a higher after-cost expectancy than entering on
   first TOUCH, because a rejection close is evidence that resting orders
   at the level absorbed the approach, whereas a touch is only evidence
   that price arrived.
   FALSIFIED IF rejection does not beat touch in a majority of markets.

H2 (direction) After a close through the level, trading WITH the break
   (FOLLOW, or RETEST) beats fading it, because a level that fails has had
   its resting liquidity consumed and the stops behind it become fuel.
   FALSIFIED IF break-direction rules do not beat fade rules.

H3 (stop) A stop placed just beyond the level (+0.25 ATR) beats a fixed
   1.5 ATR stop, because it puts the stop where the trade thesis is
   actually wrong instead of at an arbitrary distance.
   COUNTER-MECHANISM, from E-053: a tighter stop raises round-trip cost as
   a fraction of risk, and that ratio ordered the winning and losing
   markets almost perfectly. So H3 may be true about information and false
   about money. Both are measured: cost/stop is reported for every cell.

H0 (the one that matters) NONE of these rules beats a count-matched random
   entry with an identical stop/target structure on the same bars.
   This is the null E-050 forces. It is the default conclusion.

--------------------------------------------------------------------------
WHOSE SETUP THIS IS — READ BEFORE QUOTING ANY NUMBER
--------------------------------------------------------------------------
Veer trades M15 -> M5 -> M1 and does not act on H1 (D-010). This repo holds
15m and 1h only. The closest available ANALOGUE of his cascade is a level
defined on 1h and traded on 15m (`--cascade`). It is an analogue, not his
setup. Nothing here measures M5 or M1.

--------------------------------------------------------------------------
LEVEL DEFINITION — HELD CONSTANT, NEVER VARIED
--------------------------------------------------------------------------
LEVEL     a confirmed pivot: bar p whose high is strictly greater than the
          `len`=5 highs to its left and >= the 5 highs to its right (pivot
          high), or the mirror for a pivot low.
CONFIRMED the level EXISTS ONLY FROM BAR p+len ONWARDS. A decision taken at
          bar i may use a level only if p+len <= i. `selftest_lookahead()`
          re-derives every trigger on a truncated series and asserts the
          triggers are identical, which is the actual test for look-ahead —
          not a code reading.
ACTIVE    a level stays on the book for `maxage`=500 bars after its pivot,
          then drops off. Pivot highs and pivot lows are both just "levels";
          the reference level at bar i is the nearest active level at or
          above close[i-1] (resistance) and the nearest at or below it
          (support). This is a CHOICE, held constant across every rule so
          that the comparison is about execution and nothing else.

--------------------------------------------------------------------------
EXECUTION RULES — the only thing that varies
--------------------------------------------------------------------------
tol = tolband * ATR[i], zone = [L-tol, L+tol]. Decision at bar i uses bars
<= i; the fill is bar i+1's open, moved against us by half-spread+slippage.

TOUCH      h[i] >= R-tol (price entered the zone) and h[i-1] < R-tol (a
           fresh arrival, so one approach is not counted many times) and
           c[i] <= R+tol (not already gone). Enter SHORT — fading it.
REJECTION  h[i] > R+tol (wick clean through the zone) and c[i] < R-tol
           (closed back on the side it came from). Enter SHORT.
           This is the LuxAlgo "wick sweep" idea.
BREAK      c[i] > R+tol and c[i-1] <= R+tol. The trigger for both:
FOLLOW     enter LONG at the break, in the break direction.
RETEST     wait; enter LONG when a later bar j (within 50) trades back into
           the zone (l[j] <= R+tol) without any close back below R-tol.
Every rule has the mirrored short/long form at the support level.

STOPS      atr    : 1.5 * ATR[i] from close[i]
           level  : just beyond the ZONE, plus 0.25 ATR, on the far side of
                    the level from the trade
TARGETS    2R, 3R (from close[i], risk = |close[i] - stop|), or
           level : the next active level beyond close[i] in the trade's
                   direction (>= 0.1 ATR away). Events with no such level
                   are dropped from that cell and the drop is reported.

CONTROL    a pool of random (bar, side) entries on the same series, with the
           identical stop/target construction anchored to whatever level was
           nearest at that random bar. The comparison is side-matched: a
           rule with 70% shorts is compared against a control drawn 70%
           short. Reported as the 5th-95th band of the mean of n matched
           draws, exactly as E-050 reports it.

OUTCOMES   n triggers, P(+1R before -1R) with a Wilson 95% interval,
           expectancy in R after costs, cost/stop fraction (E-053), and the
           control's figures beside them. A bar that spans stop and target
           is scored a LOSS (L-012) — OHLC cannot say which came first.

Run:  python3 JARVIS/research/level_execution.py ALL
      python3 JARVIS/research/level_execution.py GOLD 1h
      python3 JARVIS/research/level_execution.py CASCADE     (1h level -> 15m)
      python3 JARVIS/research/level_execution.py SELFTEST
"""
from __future__ import annotations
import os, sys, math, json, random, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from engine import Series

COMBOS = [("GOLD", "1h"), ("GOLD", "15m"), ("EURUSD", "1h"), ("EURUSD", "15m"),
          ("GBPUSD", "1h"), ("GBPUSD", "15m"), ("US500", "1h"), ("US500", "15m")]

PIVOT_LEN = 5
MAXAGE    = 500      # bars a level stays on the book after its pivot
WARMUP    = 300
MAXBARS   = 100      # time cap on a trade, in bars
RETEST_WINDOW = 50   # bars a break stays retestable

RULES   = ["touch", "rejection", "retest", "follow"]
TOLS    = [0.10, 0.25, 0.50]
STOPS   = ["atr", "level"]
TARGETS = ["2R", "3R", "level"]

POOL_N  = 3000       # random control entries per market per stop variant
SEED    = 20260901


# ------------------------------------------------------------------ stats
def wilson(k, n, z=1.96):
    """95% interval for a proportion. 62% on 11 trades and 62% on 300 trades
    are not the same statement and must not print the same."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def meansd(xs):
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    m = sum(xs) / n
    if n < 2:
        return m, 0.0
    v = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, math.sqrt(v)


# ----------------------------------------------------------------- levels
def pivots(s: Series, ln=PIVOT_LEN):
    """Confirmed pivots. `confirm` is the FIRST bar index at which the pivot
    is knowable: p+ln. Nothing may reference the level before then."""
    out = []
    n = len(s)
    for p in range(ln, n - ln):
        hp = s.h[p]
        if all(hp > s.h[p - k] for k in range(1, ln + 1)) and \
           all(hp >= s.h[p + k] for k in range(1, ln + 1)):
            out.append({"i": p, "price": hp, "kind": "H", "confirm": p + ln})
        lp = s.l[p]
        if all(lp < s.l[p - k] for k in range(1, ln + 1)) and \
           all(lp <= s.l[p + k] for k in range(1, ln + 1)):
            out.append({"i": p, "price": lp, "kind": "L", "confirm": p + ln})
    out.sort(key=lambda d: (d["confirm"], d["i"]))
    return out


def level_refs(s: Series, levs, maxage=MAXAGE):
    """Per-bar nearest active level above/below close[i-1] (the reference
    level for the approach), and the nearest target level beyond close[i].
    Everything here is computed from bars <= i by construction: a level
    enters the book at its `confirm` index and never before."""
    n = len(s)
    res = [None] * n; sup = [None] * n
    tup = [None] * n; tdn = [None] * n
    a = engine.atr(s, 14)
    active = []
    li = 0
    for i in range(n):
        while li < len(levs) and levs[li]["confirm"] <= i:
            active.append(levs[li]); li += 1
        if active and i - active[0]["i"] > maxage:
            active = [L for L in active if i - L["i"] <= maxage]
        if i == 0 or not active:
            continue
        prices = sorted(L["price"] for L in active)
        p = s.c[i - 1]
        # nearest at/above and at/below the previous close
        lo, hi = 0, len(prices)
        while lo < hi:
            m = (lo + hi) // 2
            if prices[m] < p: lo = m + 1
            else: hi = m
        if lo < len(prices): res[i] = prices[lo]
        if lo > 0:           sup[i] = prices[lo - 1]
        # target levels: beyond close[i] by at least 0.1 ATR
        at = a[i] or 0.0
        cu, cd = s.c[i] + 0.1 * at, s.c[i] - 0.1 * at
        for pr in prices:
            if pr >= cu:
                tup[i] = pr; break
        for pr in reversed(prices):
            if pr <= cd:
                tdn[i] = pr; break
    return res, sup, tup, tdn


# ----------------------------------------------------------------- events
def find_events(s: Series, refs, rule, tol_atr, atrs, lo_bar=WARMUP, hi_bar=None):
    """Every trigger of one execution rule. An event is a decision taken at
    bar `i` from bars <= i; the fill is bar i+1's open.

    Returns list of dicts: i (decision bar), side, level, tol.
    """
    res, sup, tup, tdn = refs
    n = len(s) if hi_bar is None else hi_bar
    ev = []
    if rule in ("touch", "rejection"):
        for i in range(lo_bar, n - 1):
            at = atrs[i]
            if not at:
                continue
            tol = tol_atr * at
            R, S = res[i], sup[i]
            if R is not None:
                if rule == "touch":
                    ok = (s.h[i] >= R - tol and s.h[i - 1] < R - tol
                          and s.c[i] <= R + tol)
                else:
                    ok = (s.h[i] > R + tol and s.c[i] < R - tol)
                if ok:
                    ev.append({"i": i, "side": -1, "level": R, "tol": tol})
            if S is not None:
                if rule == "touch":
                    ok = (s.l[i] <= S + tol and s.l[i - 1] > S + tol
                          and s.c[i] >= S - tol)
                else:
                    ok = (s.l[i] < S - tol and s.c[i] > S + tol)
                if ok:
                    ev.append({"i": i, "side": +1, "level": S, "tol": tol})
    else:
        # break-based rules
        for i in range(lo_bar, n - 1):
            at = atrs[i]
            if not at:
                continue
            tol = tol_atr * at
            R, S = res[i], sup[i]
            up = R is not None and s.c[i] > R + tol and s.c[i - 1] <= R + tol
            dn = S is not None and s.c[i] < S - tol and s.c[i - 1] >= S - tol
            for brk, side, L in ((up, +1, R), (dn, -1, S)):
                if not brk:
                    continue
                if rule == "follow":
                    ev.append({"i": i, "side": side, "level": L, "tol": tol})
                    continue
                # retest: wait for price to come back into the zone
                for j in range(i + 1, min(i + 1 + RETEST_WINDOW, n - 1)):
                    aj = atrs[j]
                    if not aj:
                        break
                    tj = tol_atr * aj
                    if side == 1:
                        if s.c[j] < L - tj:            # break failed
                            break
                        if s.l[j] <= L + tj:
                            ev.append({"i": j, "side": +1, "level": L, "tol": tj})
                            break
                    else:
                        if s.c[j] > L + tj:
                            break
                        if s.h[j] >= L - tj:
                            ev.append({"i": j, "side": -1, "level": L, "tol": tj})
                            break
    ev.sort(key=lambda d: (d["i"], d["side"]))
    return ev


def geometry(s, atrs, refs, e, stop_mode, target_mode, fade):
    """Stop and target PRICES for one event, from bar i only.

    `fade` says which side of the level the trade is on: for a fade the far
    side is beyond the level in the approach direction; for a break trade it
    is back through the level. Either way the level stop sits beyond the
    ZONE plus 0.25 ATR, on the side that would prove the trade wrong.
    """
    i, side, L, tol = e["i"], e["side"], e["level"], e["tol"]
    at = atrs[i]
    ref = s.c[i]
    if stop_mode == "atr":
        stop = ref - side * 1.5 * at
    else:
        stop = L - side * (tol + 0.25 * at)
    risk = abs(ref - stop)
    if risk <= 0:
        return None
    if target_mode == "2R":
        tgt = ref + side * 2.0 * risk
    elif target_mode == "3R":
        tgt = ref + side * 3.0 * risk
    else:
        tup, tdn = refs[2][i], refs[3][i]
        tgt = tup if side == 1 else tdn
        if tgt is None:
            return None
    if (side == 1 and (stop >= ref or tgt <= ref)) or \
       (side == -1 and (stop <= ref or tgt >= ref)):
        return None
    return stop, tgt, risk


def simulate(s, i, side, stop, targets, costs, max_bars=MAXBARS):
    """One forward pass from the fill bar i+1.

    Mirrors engine.backtest exactly: fill at open[i+1] moved against us,
    STOP CHECKED BEFORE TARGET so a bar spanning both is a LOSS (L-012),
    exit fill moved against us, commission converted to price units.

    Returns (r_by_target, barrier_win, entry, risk_after_fill, exit_bar) or
    None. `exit_bar` is the bar the LAST target resolved on, which is what
    engine.backtest uses to decide when it may look for the next signal.
    """
    half = costs.spread / 2.0
    raw = s.o[i + 1]
    entry = raw + side * (half + costs.slippage)
    if (side == 1 and stop >= entry) or (side == -1 and stop <= entry):
        return None
    risk = abs(entry - stop)
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot
    up_b = entry + side * risk          # +1R barrier
    dn_b = stop                         # -1R barrier == the stop

    def close_at(px):
        fill = px - side * (half + costs.slippage)
        return ((fill - entry) * side - comm_px) / risk

    pend = {k: v for k, v in targets.items() if v is not None}
    out = {}
    barrier = None
    j = i + 1
    # engine.backtest ages a position when (bar - fill_bar) >= max_bars, and
    # the fill bar is i+1, so the last bar a trade can live on is i+1+max_bars.
    end = min(len(s) - 1, i + 1 + max_bars)
    last = j
    while j <= end:
        hit_stop = (s.l[j] <= stop) if side == 1 else (s.h[j] >= stop)
        if barrier is None:
            hit_dn = (s.l[j] <= dn_b) if side == 1 else (s.h[j] >= dn_b)
            hit_up = (s.h[j] >= up_b) if side == 1 else (s.l[j] <= up_b)
            if hit_dn:
                barrier = 0                # ties lose
            elif hit_up:
                barrier = 1
        last = j
        if hit_stop:
            for k in list(pend):
                out[k] = close_at(stop)
            pend.clear()
            break
        for k in list(pend):
            t = pend[k]
            hit_t = (s.h[j] >= t) if side == 1 else (s.l[j] <= t)
            if hit_t:
                out[k] = close_at(t)
                del pend[k]
        if not pend and barrier is not None:
            break
        j += 1
    if pend:                                # time cap
        last = min(j, end)
        px = s.c[last]
        for k in pend:
            out[k] = close_at(px)
    if barrier is None:
        barrier = -1                        # unresolved within the cap
    return out, barrier, entry, risk, last


# ------------------------------------------------------------ evaluation
def evaluate(s, atrs, refs, events, stop_mode, costs, sequential=False):
    """Evaluate every event under one stop and all three targets at once.

    sequential=True reproduces engine.backtest's one-position-at-a-time
    behaviour and exists so the parity check can prove this evaluator
    agrees with the audited engine.
    """
    rows = []
    busy_until = -1          # decision bars strictly below this are blocked
    for e in events:
        i = e["i"]
        if sequential and i < busy_until:
            continue
        tg = {}
        stops = {}
        for tm in TARGETS:
            g = geometry(s, atrs, refs, e, stop_mode, tm, True)
            if g is None:
                tg[tm] = None; stops[tm] = None
            else:
                st, t, _ = g
                tg[tm] = t; stops[tm] = st
        st = next((v for v in stops.values() if v is not None), None)
        if st is None:
            continue
        sim = simulate(s, i, e["side"], st, tg, costs)
        if sim is None:
            continue
        rr, barrier, entry, risk, exit_bar = sim
        comm_px = costs.commission_per_lot / costs.value_per_point_per_lot
        cost_px = costs.spread + 2 * costs.slippage + comm_px
        rows.append({"i": i, "side": e["side"], "r": rr, "barrier": barrier,
                     "costfrac": cost_px / risk if risk > 0 else None,
                     "n_drop": sum(1 for v in tg.values() if v is None)})
        if sequential:
            # engine.backtest closes on `exit_bar` and then evaluates a new
            # signal on that SAME bar, so exit_bar itself is available.
            busy_until = exit_bar
    return rows


def control_pool(s, atrs, refs, stop_mode, tol_atr, costs, n=POOL_N, seed=SEED):
    """Random (bar, side) entries with the identical stop/target machinery,
    anchored to whatever level was nearest at that random bar. This is the
    arm E-050 says every claim must be reported beside."""
    rng = random.Random(seed)
    res, sup, tup, tdn = refs
    lo, hi = WARMUP, len(s) - 2
    rows = []
    tries = 0
    while len(rows) < n and tries < n * 20:
        tries += 1
        i = rng.randrange(lo, hi)
        side = 1 if rng.random() < 0.5 else -1
        at = atrs[i]
        if not at:
            continue
        L = sup[i] if side == 1 else res[i]
        if L is None:
            continue
        e = {"i": i, "side": side, "level": L, "tol": tol_atr * at}
        r = evaluate(s, atrs, refs, [e], stop_mode, costs)
        if r:
            rows.append(r[0])
    return rows


# ------------------------------------------------------------- reporting
def summarise(rows, target):
    """P(+1R first), expectancy under one target, cost/stop."""
    rs = [r["r"][target] for r in rows if target in r["r"]]
    bs = [r["barrier"] for r in rows if r["barrier"] >= 0]
    cf = sorted(r["costfrac"] for r in rows if r["costfrac"])
    m, sd = meansd(rs)
    k = sum(bs)
    lo, hi = wilson(k, len(bs)) if bs else (0, 0)
    return {"n": len(rs), "exp": m, "sd": sd,
            "t": (m / (sd / math.sqrt(len(rs)))) if sd > 0 and len(rs) > 1 else 0.0,
            "nb": len(bs), "p1r": (k / len(bs)) if bs else 0.0,
            "p_lo": lo, "p_hi": hi,
            "costfrac": cf[len(cf) // 2] if cf else 0.0,
            "long": sum(1 for r in rows if r["side"] == 1),
            "short": sum(1 for r in rows if r["side"] == -1)}


def matched_control(pool_rows, target, n_long, n_short):
    """Side-matched random band, E-050 style. The mean of n draws (n_long
    from the long pool, n_short from the short pool) has closed-form
    variance, so the 5th-95th band is exact under the normal approximation
    and costs nothing to compute."""
    n = n_long + n_short
    if n == 0:
        return None
    out = {}
    cfs = sorted(r["costfrac"] for r in pool_rows if r["costfrac"])
    for side, cnt in ((1, n_long), (-1, n_short)):
        rs = [r["r"][target] for r in pool_rows
              if r["side"] == side and target in r["r"]]
        bs = [r["barrier"] for r in pool_rows
              if r["side"] == side and r["barrier"] >= 0]
        out[side] = (meansd(rs), len(rs), (sum(bs), len(bs)))
    (ml, sl), nl, (kl, bl) = out[1]
    (ms, ss), ns, (ks, bs_) = out[-1]
    if (n_long and nl < 30) or (n_short and ns < 30):
        return None
    mean = (n_long * ml + n_short * ms) / n
    var = (n_long * sl * sl + n_short * ss * ss) / (n * n)
    sdm = math.sqrt(var) if var > 0 else 0.0
    pl = (kl / bl) if bl else 0.0
    ps = (ks / bs_) if bs_ else 0.0
    p = (n_long * pl + n_short * ps) / n
    psd = math.sqrt(p * (1 - p) / n) if 0 < p < 1 else 0.0
    return {"exp": mean, "lo": mean - 1.645 * sdm, "hi": mean + 1.645 * sdm,
            "p1r": p, "p_lo": p - 1.645 * psd, "p_hi": p + 1.645 * psd,
            "costfrac": cfs[len(cfs) // 2] if cfs else 0.0}


def level_density(s, refs, atrs, lo=WARMUP):
    """How far away is the nearest level, in ATRs? With len=5 pivots the book
    is dense, and a dense book means "price is always near a level" — which
    is exactly what would make a level rule indistinguishable from random.
    This number belongs in the writeup, not in a footnote."""
    res, sup, _, _ = refs
    du, dd, gap = [], [], []
    for i in range(lo, len(s) - 1):
        at = atrs[i]
        if not at:
            continue
        if res[i] is not None:
            du.append((res[i] - s.c[i - 1]) / at)
        if sup[i] is not None:
            dd.append((s.c[i - 1] - sup[i]) / at)
        if res[i] is not None and sup[i] is not None:
            gap.append((res[i] - sup[i]) / at)
    med = lambda a: sorted(a)[len(a) // 2] if a else float("nan")
    return {"to_res": med(du), "to_sup": med(dd), "gap": med(gap),
            "n": len(gap)}


# -------------------------------------------------------------- self-test
def selftest_lookahead(sym="GOLD", tf="1h", verbose=True):
    """THE look-ahead test. Re-derive every trigger on a series truncated at
    bar T and assert the triggers below T-60 are byte-identical to those
    found on the full series. If any rule peeked at a future bar — including
    through the pivot confirmation or the level book — this fails."""
    s = engine.load(sym, tf)
    T = 4000
    sub = Series(s.ts[:T], s.o[:T], s.h[:T], s.l[:T], s.c[:T])
    ok = True
    for series, tag in ((s, "full"), (sub, "trunc")):
        pass
    a_full = engine.atr(s, 14)
    a_sub = engine.atr(sub, 14)
    r_full = level_refs(s, pivots(s))
    r_sub = level_refs(sub, pivots(sub))
    for rule in RULES:
        for tol in TOLS:
            ef = [(e["i"], e["side"], round(e["level"], 8))
                  for e in find_events(s, r_full, rule, tol, a_full, hi_bar=T - 60)]
            es = [(e["i"], e["side"], round(e["level"], 8))
                  for e in find_events(sub, r_sub, rule, tol, a_sub, hi_bar=T - 60)]
            if ef != es:
                ok = False
                if verbose:
                    print(f"  FAIL look-ahead: {rule} tol={tol} "
                          f"{len(ef)} vs {len(es)} triggers differ")
            elif verbose:
                print(f"  PASS {rule:<10} tol {tol:<5} {len(ef):>5} triggers "
                      f"identical on a truncated series")
    # pivots must never be usable before confirm
    for L in pivots(s)[:2000]:
        if L["confirm"] != L["i"] + PIVOT_LEN:
            ok = False; print("  FAIL confirm index")
    return ok


def selftest_parity(sym="GOLD", tf="1h", verbose=True):
    """Parity with the audited engine. Drive engine.backtest with a signal
    function that fires on exactly the same events, and compare trade-by-
    trade R against this file's evaluator in sequential mode. If they
    disagree, this file's numbers are not the engine's numbers."""
    s = engine.load(sym, tf)
    costs = study.COSTS[sym]
    a = engine.atr(s, 14)
    refs = level_refs(s, pivots(s))
    ev = find_events(s, refs, "rejection", 0.25, a)
    by_bar = {}
    for e in ev:
        by_bar.setdefault(e["i"], e)

    def sig(ctx, i):
        e = by_bar.get(i)
        if e is None:
            return None
        g = geometry(s, a, refs, e, "atr", "3R", True)
        if g is None:
            return None
        st, tg, _ = g
        return {"side": e["side"], "stop": st, "target": tg}

    tr = engine.backtest(s, sig, costs, warmup=WARMUP, max_bars=MAXBARS)
    mine = evaluate(s, a, refs,
                    [by_bar[k] for k in sorted(by_bar) if k >= WARMUP],
                    "atr", costs, sequential=True)
    er = [round(t.r, 9) for t in tr]
    mr = [round(r["r"]["3R"], 9) for r in mine]
    ok = er == mr
    if verbose:
        print(f"  {'PASS' if ok else 'FAIL'} parity with engine.backtest: "
              f"{len(er)} engine trades vs {len(mr)} here, "
              f"totalR {sum(er):+.4f} vs {sum(mr):+.4f}")
        if not ok:
            for k, (x, y) in enumerate(zip(er, mr)):
                if x != y:
                    print(f"    first mismatch at trade {k}: {x} vs {y}")
                    break
    return ok


def selftest_ties(verbose=True):
    """A bar that spans stop and target must be a LOSS."""
    s = Series([0, 1, 2], [100.0, 100.0, 100.0], [100.0, 110.0, 100.0],
               [100.0, 90.0, 100.0], [100.0, 100.0, 100.0])
    c = engine.Costs(spread=0.0, slippage=0.0, commission_per_lot=0.0,
                     value_per_point_per_lot=1.0)
    out = simulate(s, 0, 1, 95.0, {"2R": 110.0}, c, max_bars=5)
    r, barrier, entry, risk, _ = out
    ok = r["2R"] < 0 and barrier == 0
    if verbose:
        print(f"  {'PASS' if ok else 'FAIL'} a bar spanning stop and target "
              f"scores a LOSS (r={r['2R']:+.2f}, barrier={barrier})")
    return ok


def run_selftests():
    print("=" * 78)
    print("  SELF-TESTS — nothing below is meaningful if any of these fail")
    print("=" * 78)
    a = selftest_ties()
    print()
    b = selftest_parity()
    print()
    c = selftest_lookahead()
    print()
    print("  ALL SELF-TESTS PASSED" if (a and b and c) else "  *** SELF-TEST FAILURE ***")
    return a and b and c


# ------------------------------------------------------------------ study
def analyse(sym, tf, cascade=False, verbose=True):
    """Full grid for one market. Returns {(rule,tol,stop,target): cell}."""
    s = engine.load(sym, tf)
    costs = study.COSTS[sym]
    a = engine.atr(s, 14)
    if cascade:
        htf = engine.load(sym, "1h")
        levs = pivots(htf)
        # map an HTF level onto the LTF bar at which it first becomes known:
        # the confirming HTF bar must have CLOSED, so the level is usable
        # from the first LTF bar whose timestamp is after that HTF bar's end.
        bar_secs = htf.ts[1] - htf.ts[0]
        mapped = []
        for L in levs:
            t_known = htf.ts[L["confirm"]] + bar_secs
            j = 0
            lo, hi = 0, len(s)
            while lo < hi:
                m = (lo + hi) // 2
                if s.ts[m] < t_known: lo = m + 1
                else: hi = m
            j = lo
            if j >= len(s):
                continue
            mapped.append({"i": j, "price": L["price"], "kind": L["kind"],
                           "confirm": j})
        mapped.sort(key=lambda d: (d["confirm"], d["i"]))
        levs = mapped
    else:
        levs = pivots(s)
    refs = level_refs(s, levs)

    pools = {}
    for sm in STOPS:
        for tol in (TOLS if sm == "level" else [TOLS[0]]):
            pools[(sm, tol)] = control_pool(s, a, refs, sm, tol, costs)

    cells = {}
    for rule in RULES:
        for tol in TOLS:
            ev = find_events(s, refs, rule, tol, a)
            for sm in STOPS:
                rows = evaluate(s, a, refs, ev, sm, costs)
                pool = pools[(sm, tol if sm == "level" else TOLS[0])]
                srows = evaluate(s, a, refs, ev, sm, costs, sequential=True)
                for tm in TARGETS:
                    st = summarise(rows, tm)
                    sq = summarise(srows, tm)
                    ct = matched_control(pool, tm, st["long"], st["short"])
                    cs = matched_control(pool, tm, sq["long"], sq["short"])
                    cells[(rule, tol, sm, tm)] = {"rule": st, "ctrl": ct,
                                                  "seq": sq, "seqctrl": cs,
                                                  "n_events": len(ev)}
    return cells, len(s), level_density(s, refs, a)


def print_market(sym, tf, cells, nbars, dens, tag=""):
    print()
    print("=" * 78)
    print(f"  {sym} {tf}{tag}   {nbars} bars   costs: spread {study.COSTS[sym].spread}"
          f" slip {study.COSTS[sym].slippage} comm {study.COSTS[sym].commission_per_lot}")
    print("=" * 78)
    print(f"  LEVEL BOOK DENSITY: median distance from close to the nearest level"
          f" above {dens['to_res']:.2f} ATR, below {dens['to_sup']:.2f} ATR;"
          f"\n                      median support-resistance gap "
          f"{dens['gap']:.2f} ATR")
    print("  TRIGGER COUNTS (raw events, before stop/target usability)")
    print(f"  {'rule':<10} " + "".join(f"tol{t:<8.2f}" for t in TOLS))
    for rule in RULES:
        row = "".join(f"{cells[(rule, t, 'atr', '2R')]['n_events']:<11}" for t in TOLS)
        print(f"  {rule:<10} {row}")
    print()
    print(f"  {'rule':<10}{'tol':>5}{'stop':>7}{'tgt':>6}{'n':>6}"
          f"{'P(+1R)':>8}{'  95% CI':>16}{'exp R':>9}{'t':>7}"
          f"{'ctrlP':>8}{'ctrlR':>8}{'ctrl 5-95%':>18}{'cost/stop':>10}{'ctrlC/S':>9}"
          f"{'nOvN':>7}{'nOvExp':>8}{'nOvT':>7}")
    for rule in RULES:
        for tol in TOLS:
            for sm in STOPS:
                for tm in TARGETS:
                    c = cells[(rule, tol, sm, tm)]
                    r, ct = c["rule"], c["ctrl"]
                    if r["n"] == 0:
                        continue
                    ci = f"[{100*r['p_lo']:.1f},{100*r['p_hi']:.1f}]"
                    if ct:
                        cs = f"[{ct['lo']:+.3f},{ct['hi']:+.3f}]"
                        cp = f"{100*ct['p1r']:.1f}"
                        cr = f"{ct['exp']:+.3f}"
                        cc = f"{ct['costfrac']:.3f}"
                    else:
                        cs, cp, cr, cc = "n/a", "n/a", "n/a", "n/a"
                    q = c["seq"]
                    print(f"  {rule:<10}{tol:>5.2f}{sm:>7}{tm:>6}{r['n']:>6}"
                          f"{100*r['p1r']:>7.1f}%{ci:>16}{r['exp']:>+9.3f}{r['t']:>+7.2f}"
                          f"{cp:>8}{cr:>8}{cs:>18}{r['costfrac']:>10.3f}{cc:>9}"
                          f"{q['n']:>7}{q['exp']:>+8.3f}{q['t']:>+7.2f}")


def aggregate(all_cells, label):
    """The only table that can support a conclusion: how many of the markets
    agree. A rule that wins on one market is a story."""
    mkts = list(all_cells)
    K = len(mkts)
    print()
    print("=" * 78)
    print(f"  CROSS-MARKET AGGREGATE — {label} ({K} markets)")
    print("=" * 78)
    print(f"  {'rule':<10}{'tol':>5}{'stop':>7}{'tgt':>6}"
          f"{'trig/mkt':>10}{'meanExp':>9}{'>0':>5}{'>ctrl':>7}{'>ctrl95':>9}"
          f"{'meanP-ctrlP':>13}{'cost/stop':>10}"
          f"{'nOvlpN':>8}{'nOvlpE':>8}{'>0':>7}{'>c95':>7}")
    print("  (nOvlp* = the same rule with overlapping trades removed, "
          "one position at a\n   time exactly as engine.backtest runs it — "
          "the only arm whose n is independent)")
    rows = []
    for rule in RULES:
        for tol in TOLS:
            for sm in STOPS:
                for tm in TARGETS:
                    exps, pos, beat, beat95, dp, cf, ns = [], 0, 0, 0, [], [], []
                    sq_n, sq_e, sq_pos, sq_b95 = [], [], 0, 0
                    for m in mkts:
                        c = all_cells[m].get((rule, tol, sm, tm))
                        if not c or c["rule"]["n"] < 20:
                            continue
                        r, ct = c["rule"], c["ctrl"]
                        exps.append(r["exp"]); ns.append(r["n"]); cf.append(r["costfrac"])
                        if r["exp"] > 0: pos += 1
                        if ct:
                            if r["exp"] > ct["exp"]: beat += 1
                            if r["exp"] > ct["hi"]:  beat95 += 1
                            dp.append(100 * (r["p1r"] - ct["p1r"]))
                        q, qc = c["seq"], c["seqctrl"]
                        if q["n"] >= 30:
                            sq_n.append(q["n"]); sq_e.append(q["exp"])
                            if q["exp"] > 0: sq_pos += 1
                            if qc and q["exp"] > qc["hi"]: sq_b95 += 1
                    if not exps:
                        continue
                    me = sum(exps) / len(exps)
                    rows.append({"rule": rule, "tol": tol, "stop": sm, "tgt": tm,
                                 "k": len(exps), "meanExp": me, "pos": pos,
                                 "beat": beat, "beat95": beat95,
                                 "dp": (sum(dp) / len(dp)) if dp else 0.0,
                                 "trig": sum(ns) / len(ns),
                                 "cf": sum(cf) / len(cf),
                                 "sk": len(sq_e), "sq_pos": sq_pos,
                                 "sq_b95": sq_b95,
                                 "sq_n": (sum(sq_n) / len(sq_n)) if sq_n else 0,
                                 "sq_e": (sum(sq_e) / len(sq_e)) if sq_e else 0.0})
                    print(f"  {rule:<10}{tol:>5.2f}{sm:>7}{tm:>6}"
                          f"{rows[-1]['trig']:>10.0f}{me:>+9.3f}"
                          f"{pos:>3}/{len(exps):<2}{beat:>5}/{len(exps):<2}"
                          f"{beat95:>7}/{len(exps):<2}"
                          f"{rows[-1]['dp']:>+13.1f}{rows[-1]['cf']:>10.3f}"
                          f"{rows[-1]['sq_n']:>8.0f}{rows[-1]['sq_e']:>+8.3f}"
                          f"{sq_pos:>4}/{len(sq_e):<2}{sq_b95:>4}/{len(sq_e):<2}")
    return rows, K


def marginals(rows, K):
    print()
    print("  MARGINALS — averaging over everything else in the grid")
    for field, vals in (("rule", RULES), ("tol", TOLS),
                        ("stop", STOPS), ("tgt", TARGETS)):
        print(f"  by {field}:")
        for v in vals:
            sel = [r for r in rows if r[field] == v]
            if not sel:
                continue
            me = sum(r["meanExp"] for r in sel) / len(sel)
            bp = sum(r["pos"] for r in sel); bt = sum(r["k"] for r in sel)
            b95 = sum(r["beat95"] for r in sel)
            bc = sum(r["beat"] for r in sel)
            dp = sum(r["dp"] for r in sel) / len(sel)
            cf = sum(r["cf"] for r in sel) / len(sel)
            sk = sum(r["sk"] for r in sel)
            sqp = sum(r["sq_pos"] for r in sel)
            sq95 = sum(r["sq_b95"] for r in sel)
            sqe = sum(r["sq_e"] * r["sk"] for r in sel) / sk if sk else 0.0
            print(f"    {str(v):<10} meanExp {me:+.3f}   exp>0 {bp}/{bt}"
                  f"   >ctrl {bc}/{bt}   >ctrl95 {b95}/{bt}"
                  f"   P(+1R)-ctrl {dp:+.1f}pts   cost/stop {cf:.3f}")
            print(f"    {'':<10} non-overlapping: meanExp {sqe:+.3f}"
                  f"   exp>0 {sqp}/{sk}   >ctrl95 {sq95}/{sk}")


def head_to_head(all_cells):
    """H1 and H2 answered as an 8-market vote instead of a single average.
    For each market, average expectancy over the 18 (tol, stop, target)
    variants for each rule, then count which rule wins that market. Also
    reported: how often each rule beats its OWN matched random control, and
    the control's cost/stop, so a cell that 'beats the control' can be
    audited for whether it merely had a cheaper stop."""
    print()
    print("  HEAD-TO-HEAD BY MARKET (mean expectancy over the 18 exit variants)")
    hdr = "  {:<14}".format("market") + "".join(f"{r:>11}" for r in RULES) + "   winner"
    print(hdr)
    wins = {r: 0 for r in RULES}
    per = {}
    for m, cells in all_cells.items():
        row = {}
        for rule in RULES:
            es = [cells[(rule, t, s_, g)]["rule"]["exp"]
                  for t in TOLS for s_ in STOPS for g in TARGETS
                  if cells[(rule, t, s_, g)]["rule"]["n"] >= 20]
            row[rule] = sum(es) / len(es) if es else float("nan")
        best = max(RULES, key=lambda r: row[r])
        wins[best] += 1
        per[m] = row
        print("  {:<14}".format(f"{m[0]} {m[1]}")
              + "".join(f"{row[r]:>+11.3f}" for r in RULES) + f"   {best}")
    print("  rule wins: " + ", ".join(f"{r} {wins[r]}/{len(all_cells)}" for r in RULES))
    print()
    print("  PAIRWISE (markets in which the row rule beats the column rule)")
    print("  {:<12}".format("") + "".join(f"{r:>11}" for r in RULES))
    for a in RULES:
        line = "  {:<12}".format(a)
        for b in RULES:
            if a == b:
                line += f"{'-':>11}"
            else:
                k = sum(1 for m in per if per[m][a] > per[m][b])
                line += f"{str(k) + '/' + str(len(per)):>11}"
        print(line)
    return wins


def entry_quality(all_cells, stop_mode="atr"):
    """The exit-free view. P(+1R before -1R) is a property of the ENTRY only;
    it does not depend on the target. Reported as (rule P) - (control P) in
    percentage points, per market, so a rule that merely reshapes the payoff
    cannot hide inside an expectancy number. Base rates are the control's,
    never 50%."""
    print()
    print(f"  ENTRY QUALITY — P(+1R before -1R) MINUS the matched random control,")
    print(f"  in percentage points, with the {stop_mode} stop. + means the rule")
    print(f"  reached its target-side 1R first more often than a random entry did.")
    mkts = list(all_cells)
    print("  {:<14}".format("market") + "".join(
        f"{r[:4] + str(t):>12}" for r in RULES for t in TOLS))
    tot = {}
    for m in mkts:
        line = "  {:<14}".format(f"{m[0]} {m[1]}")
        for r in RULES:
            for t in TOLS:
                c = all_cells[m][(r, t, stop_mode, "2R")]
                rr, ct = c["rule"], c["ctrl"]
                if rr["nb"] < 30 or not ct:
                    line += f"{'-':>12}"; continue
                d = 100 * (rr["p1r"] - ct["p1r"])
                sig = "*" if (rr["p_lo"] > ct["p1r"] or rr["p_hi"] < ct["p1r"]) else " "
                tot.setdefault((r, t), []).append(d)
                line += f"{d:>+11.1f}{sig}"
        print(line)
    print("  {:<14}".format("mean") + "".join(
        f"{(sum(tot[(r, t)]) / len(tot[(r, t)])):>+11.1f} " if (r, t) in tot
        else f"{'-':>12}" for r in RULES for t in TOLS))
    print("  {:<14}".format("markets > 0") + "".join(
        f"{sum(1 for x in tot[(r, t)] if x > 0)}/{len(tot[(r, t)])!s:<8}".rjust(12)
        if (r, t) in tot else f"{'-':>12}" for r in RULES for t in TOLS))
    print("  * = the rule's Wilson 95% interval excludes the control's rate")
    return tot


def multiple_testing(rows, K):
    n_cfg = len(RULES) * len(TOLS) * len(STOPS) * len(TARGETS)
    print()
    print("  MULTIPLE TESTING — do the arithmetic before quoting a cell")
    print(f"  configurations examined: {len(RULES)} rules x {len(TOLS)} tolerances"
          f" x {len(STOPS)} stops x {len(TARGETS)} targets = {n_cfg}")
    print(f"  each evaluated on {K} markets, plus a matched random control.")
    for thr in range(K, max(K - 3, 0), -1):
        # P(at least thr of K land on one side) under a fair coin
        p = sum(math.comb(K, j) for j in range(thr, K + 1)) / (2 ** K)
        print(f"    P(a config is positive in >= {thr} of {K} markets by chance) "
              f"= {100*p:.2f}%  ->  expected such configs among {n_cfg}: "
              f"{n_cfg * p:.2f}")
    best = max(rows, key=lambda r: r["meanExp"]) if rows else None
    if best:
        print(f"  best cell by mean expectancy: {best['rule']} tol {best['tol']} "
              f"{best['stop']} {best['tgt']}  {best['meanExp']:+.3f}R, "
              f"positive in {best['pos']}/{best['k']}, beats control 95% band in "
              f"{best['beat95']}/{best['k']}")
        print("  A best-of-%d cell is expected to look good. The number that "
              "matters is\n  the agreement count, not the headline." % n_cfg)


def main(argv):
    arg = (argv[1] if len(argv) > 1 else "ALL").upper()
    if arg == "SELFTEST":
        run_selftests(); return
    ok = run_selftests()
    if not ok:
        print("\nABORTING: self-tests failed, every number below would be meaningless.")
        return
    cascade = (arg == "CASCADE")
    if cascade:
        combos = [(sym, "15m") for sym in ("GOLD", "EURUSD", "GBPUSD", "US500")]
        label = "CASCADE ANALOGUE: 1h levels traded on 15m"
    elif arg == "ALL":
        combos = COMBOS
        label = "level and execution on the SAME timeframe"
    else:
        combos = [(arg, argv[2] if len(argv) > 2 else "1h")]
        label = "single market"
    allc = {}
    for sym, tf in combos:
        cells, nb, dens = analyse(sym, tf, cascade=cascade)
        allc[(sym, tf)] = cells
        print_market(sym, tf, cells, nb, dens,
                     tag=" (1h levels)" if cascade else "")
    rows, K = aggregate(allc, label)
    marginals(rows, K)
    head_to_head(allc)
    entry_quality(allc, "atr")
    entry_quality(allc, "level")
    multiple_testing(rows, K)
    out = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "reports",
                                        f"level_execution_{arg}.json"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({f"{m[0]}_{m[1]}": {"|".join(str(x) for x in k): v
                                      for k, v in c.items()}
                   for m, c in allc.items()}, f, indent=1, default=str)
    print(f"\nsaved -> {out}")


if __name__ == "__main__":
    main(sys.argv)

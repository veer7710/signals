"""
E-053 — DO MARKED LEVELS PRODUCE A REACTION AT ALL?

Veer's question, verbatim in substance: his indicator should mark every level
that still matters, INCLUDING OLD ONES, and he wants to know whether previous
prices that price once reacted to keep mattering.

Nobody in this repo has ever measured whether a marked level produces a
reaction at all. This script measures it, and — following E-050, the
experiment where a RANDOM entry scored +0.202R against the signal's +0.321R
and retracted the project's headline result — it measures it AGAINST A
MATCHED RANDOM CONTROL. A reaction rate with no control is not a result.

--------------------------------------------------------------------------
THE HYPOTHESIS, FALSIFIABLE, WITH ITS MECHANISM
--------------------------------------------------------------------------
H: Price that returns to a previously-marked pivot level reacts away from it
   MORE OFTEN than it reacts away from an arbitrary price at the same
   distance, because resting orders and stops accumulate at prices market
   participants can see, and that accumulated liquidity absorbs the approach.

FALSIFIED IF: the reaction rate at real pivot levels is not distinguishable
from the reaction rate at matched random levels, in which case the marked
level is decoration.

--------------------------------------------------------------------------
DEFINITIONS — all objective, all coded below, none tuned after the fact
--------------------------------------------------------------------------
LEVEL     a pivot high (bar whose high is the highest of the `len` bars
          either side) or a pivot low. CONFIRMED at pivot_bar + len. It does
          not exist, and cannot be touched, before pivot_bar + len + 1.

CLUSTER   the LuxAlgo "Buyside & Sellside Liquidity" idea Veer runs: a zone
          is only drawn when THREE OR MORE pivots sit within +-(ATR/margin)
          of each other, margin 1.45 (their default is 10/6.9 = 1.449).
          Implemented here as: a newly-confirmed pivot JOINS the nearest
          active same-type level whose band contains it, otherwise it
          creates a new level. Cluster size at bar i = the number of member
          pivots CONFIRMED ON OR BEFORE bar i-1. Cluster size 1 is a bare
          pivot, which LuxAlgo would not draw.

TOUCH     bar i's range intersects the band [P-T, P+T] (P = level price,
          T = its tolerance), AND close[i-1] was strictly OUTSIDE that band
          (so we know which side price approached from), AND no touch of the
          SAME level was registered in the previous K=20 bars (so one
          approach is not counted as twenty touches).

REACTION  the direction price came FROM is the rejection direction. Within N
          bars AFTER the touch bar, price moves at least X*ATR AWAY from the
          level in that direction, WITHOUT FIRST closing beyond the level by
          more than Y*ATR (Y = 0.25).
          A bar that does both is scored as the BAD outcome — invalidation is
          checked first on every bar — because OHLC cannot say which came
          first and assuming the good one is free money (L-012).
          Neither happening inside N bars is also scored as NO REACTION.
          ATR is the ATR at the touch bar, known at its close.

--------------------------------------------------------------------------
THE CONTROL — the point of the whole study
--------------------------------------------------------------------------
For every real level a MATCHED RANDOM level is created that is identical in
every respect except WHERE IT IS:
  * same first-member confirmation bar, so the same age at any bar i
  * the same list of member confirmation bars, so an identical cluster-size
    trajectory (a random level "of cluster size 3" exists to compare against
    a real cluster of 3)
  * the same tolerance band width
  * its price is drawn by SHUFFLING the pool of real offsets
    (level_price - close[confirm_bar]) / ATR[confirm_bar]
    across levels of the same type, so a random buyside level sits above the
    market by a realistic ATR-scaled distance, at an arbitrary price.
  * touches, prior-touch counts, swept/broken state are then detected on it
    by exactly the same code path, on the same bars.
Three independent replicates (seeds 0,1,2) are pooled.

If real levels react 55% of the time and matched random levels react 54% of
the time, the level is DECORATION and this script says so in those words.

--------------------------------------------------------------------------
NO LOOK-AHEAD — checked explicitly, see selfcheck()
--------------------------------------------------------------------------
1. A level is activated at confirm_bar + 1. Asserted for every touch.
2. Cluster size at bar i counts only members confirmed <= i-1. Asserted.
3. Swept/broken state is updated with bar i's close AFTER bar i's touches
   have been recorded, so the state attached to a touch is as of i-1.
   Asserted by construction and re-checked.
4. The reaction window starts at i+1. The touch bar's own high/low is used
   ONLY to say the touch happened, never to score the reaction. Asserted.
5. RANDOM-WALK NULL: the entire pipeline is run on a driftless random walk,
   where pivots carry no information. Real-minus-random there must be ~0.
   Whatever it is, is the machinery's own bias and is printed.

Run:  python3 JARVIS/research/level_reaction.py SELFCHECK
      python3 JARVIS/research/level_reaction.py GOLD 1h
      python3 JARVIS/research/level_reaction.py ALL
"""
from __future__ import annotations
import os, sys, math, random, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from engine import Series

# ----------------------------------------------------------------- config
MARGIN   = 1.45     # LuxAlgo default 10/6.9; CLUSTER band half-width = ATR/MARGIN
CLU_PIV  = 20       # LuxAlgo scans a bounded set of recent pivots, not all history
TOUCH_TOL = 0.15    # touch tolerance in ATR -- see note below
K_COOL   = 20       # bars before the same level can be touched again
Y_INVAL  = 0.25     # close beyond the level by this many ATR = invalidated
WARMUP   = 250      # no touch is recorded before this bar
TREND_N  = 50       # simple 50-bar trend for the with/against split
REPLICAS = 3        # random control replicates

PRIMARY  = dict(ln=5, N=10, X=1.0)   # the config the bucket tables use
GRID_LEN = [3, 5, 7, 10]
GRID_TOL = [0.05, 0.15, 0.30, 0.69]   # sensitivity on the touch tolerance
GRID_N   = [5, 10, 20]
GRID_X   = [0.5, 1.0, 1.5]

COMBOS = [("GOLD", "1h"), ("GOLD", "15m"), ("EURUSD", "1h"), ("EURUSD", "15m"),
          ("GBPUSD", "1h"), ("GBPUSD", "15m"), ("US500", "1h"), ("US500", "15m")]


# ------------------------------------------------------------ statistics
def wilson(k, n, z=1.96):
    """95% interval for a proportion. Printed on every proportion because
    55% on 30 touches and 55% on 3000 touches are not the same statement."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def two_prop_z(k1, n1, k2, n2):
    """z for the difference of two independent proportions. The control is
    3 pooled replicates of the same bars, so its effective n is smaller than
    n2 and this z is OPTIMISTIC. It is printed as a rough guide only."""
    if n1 == 0 or n2 == 0:
        return 0.0
    p1, p2 = k1 / n1, k2 / n2
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return (p1 - p2) / se if se > 0 else 0.0


# ---------------------------------------------------------------- pivots
def find_pivots(s: Series, ln: int):
    """(pivot_bar, typ, price, confirm_bar). typ +1 = pivot high (buyside),
    -1 = pivot low (sellside). A pivot at bar p is UNKNOWABLE until p+ln."""
    out = []
    n = len(s)
    for p in range(ln, n - ln):
        hp = s.h[p]
        if hp == max(s.h[p - ln:p + ln + 1]) and hp > max(s.h[p - ln:p]) \
           and hp >= max(s.h[p + 1:p + ln + 1]):
            out.append((p, +1, hp, p + ln))
        lp = s.l[p]
        if lp == min(s.l[p - ln:p + ln + 1]) and lp < min(s.l[p - ln:p]) \
           and lp <= min(s.l[p + 1:p + ln + 1]):
            out.append((p, -1, lp, p + ln))
    out.sort(key=lambda r: (r[3], r[0]))
    return out


def build_levels(s: Series, A, ln: int, margin=MARGIN, clu_piv=CLU_PIV):
    """Turn confirmed pivots into level objects, clustering as LuxAlgo does.

    A pivot joins the nearest same-type level whose CLUSTER band (+-ATR/margin,
    the LuxAlgo margin) contains it, PROVIDED that level's most recent member
    is within the last `clu_piv` confirmed pivots of that type. LuxAlgo scans a
    bounded set of recent pivots, not all of history; without that bound every
    price on the chart eventually merges into a handful of mega-clusters and
    both the age and the cluster-size analyses become meaningless.

    Everything is done in confirmation order, so no level ever knows about a
    pivot from its future. The anchor price is the FIRST member's price and is
    never revised, so a level's location never changes after it is drawn.
    """
    piv = find_pivots(s, ln)
    levels = []
    byty = {+1: ([], []), -1: ([], [])}   # sorted prices, parallel objects
    rank = {+1: 0, -1: 0}
    for (p, typ, price, conf) in piv:
        a = A[conf]
        if a is None or a <= 0:
            continue
        rank[typ] += 1
        r = rank[typ]
        cb = a / margin                      # cluster band half-width
        prices, objs = byty[typ]
        best, bestd = None, None
        lo = bisect.bisect_left(prices, price - 5 * cb)
        hi = bisect.bisect_right(prices, price + 5 * cb)
        for k in range(lo, hi):
            L = objs[k]
            if L["conf"] >= conf:            # not yet active: cannot be joined
                continue
            if r - L["rank"] > clu_piv:      # too far back in the pivot list
                continue
            d = abs(L["p"] - price)
            if d <= L["cb"] and (bestd is None or d < bestd):
                best, bestd = L, d
        if best is not None:
            best["mb"].append(conf)          # cluster grows; anchor unchanged
            best["rank"] = r
            continue
        L = {"p": price, "cb": cb, "typ": typ, "pivot": p, "conf": conf,
             "mb": [conf], "rank": r, "id": len(levels)}
        levels.append(L)
        idx = bisect.bisect_left(prices, price)
        prices.insert(idx, price); objs.insert(idx, L)
    return levels


def randomise(levels, A, s: Series, seed: int):
    """The matched control. Identical objects; only the PRICE moves.

    The offset (price - close[conf]) / ATR[conf] is shuffled among levels of
    the same type, which preserves the ATR-scaled distance-from-market
    distribution and destroys the fact that the price was ever a pivot.
    A pivot high always sits above close[conf] by construction (the `ln` bars
    after it all have lower highs), so the sign of the offset is preserved
    automatically and a random buyside level is still above the market.
    """
    rng = random.Random(seed)
    out = []
    for typ in (+1, -1):
        grp = [L for L in levels if L["typ"] == typ]
        offs = [(L["p"] - s.c[L["conf"]]) / A[L["conf"]] for L in grp]
        rng.shuffle(offs)
        for L, off in zip(grp, offs):
            out.append({"p": s.c[L["conf"]] + off * A[L["conf"]],
                        "cb": L["cb"], "typ": typ, "pivot": L["pivot"],
                        "conf": L["conf"], "mb": list(L["mb"]),
                        "rank": L["rank"], "id": L["id"]})
    out.sort(key=lambda L: L["conf"])
    return out


# ---------------------------------------------------------------- touches
def scan_touches(s: Series, A, levels, warmup=WARMUP, K=K_COOL,
                 tol_atr=TOUCH_TOL):
    """One forward pass. At bar i: activate levels confirmed at i-1, record
    touches using state as of i-1, THEN update swept/broken with bar i.

    The touch tolerance is tol_atr * ATR[i] -- deliberately NOT the LuxAlgo
    cluster band. The cluster band is +-0.69 ATR wide, so a bar merely entering
    it need not have come anywhere near the level, and "move 1 ATR away from
    the level" would then be satisfied by a 0.31 ATR drift. A touch has to mean
    price actually arrived at the level.
    """
    n = len(s)
    by_conf = {}
    for L in levels:
        by_conf.setdefault(L["conf"], []).append(L)
    prices, objs = [], []
    state = {}          # id -> 0 intact, 1 swept, 2 broken
    ntouch = {}         # id -> touches so far
    lastt = {}          # id -> bar of last registered touch
    touches = []

    for i in range(1, n):
        for L in by_conf.get(i - 1, ()):
            idx = bisect.bisect_left(prices, L["p"])
            prices.insert(idx, L["p"]); objs.insert(idx, L)
            state[L["id"]] = 0; ntouch[L["id"]] = 0; lastt[L["id"]] = None
        if not prices:
            continue
        hi, lo, pc = s.h[i], s.l[i], s.c[i - 1]
        a = A[i]
        if a is None or a <= 0:
            continue
        T = tol_atr * a
        q0 = bisect.bisect_left(prices, lo - T)
        q1 = bisect.bisect_right(prices, hi + T)
        record = (i >= warmup and i >= TREND_N + 1)
        trend = 0
        if record:
            d = s.c[i] - s.c[i - TREND_N]
            trend = 1 if d > 0 else (-1 if d < 0 else 0)
        for k in range(q0, q1):
            L = objs[k]; P = L["p"]; lid = L["id"]
            if record and hi >= P - T and lo <= P + T:
                ad = 1 if pc < P - T else (-1 if pc > P + T else 0)
                lt = lastt[lid]
                if ad != 0 and (lt is None or i - lt >= K):
                    cs = bisect.bisect_right(L["mb"], i - 1)
                    touches.append({
                        "i": i, "id": lid, "typ": L["typ"], "P": P, "T": T,
                        "a": a, "ad": ad,
                        "age": i - L["pivot"],
                        "clu": cs,
                        "prior": ntouch[lid],
                        "state": state[lid],
                        "withtr": 1 if ad == trend else 0,
                    })
                    ntouch[lid] += 1
                    lastt[lid] = i
            # ---- state update with bar i, used only by LATER bars
            st = state[lid]
            if st != 2:
                if L["typ"] == 1:
                    if s.c[i] > P:
                        state[lid] = 2
                    elif hi > P:
                        state[lid] = max(st, 1)
                else:
                    if s.c[i] < P:
                        state[lid] = 2
                    elif lo < P:
                        state[lid] = max(st, 1)
    return touches


def score(s: Series, touches, N: int, X: float, Y: float = Y_INVAL):
    """1 = reacted, 0 = did not. Invalidation is tested FIRST on every bar,
    so a bar doing both is the BAD outcome (L-012)."""
    n = len(s)
    out = []
    for t in touches:
        i, P, a, ad = t["i"], t["P"], t["a"], t["ad"]
        # ad = +1 approached from BELOW  -> rejection is DOWN
        # ad = -1 approached from ABOVE  -> rejection is UP
        good = P - ad * X * a
        bad_close = P + ad * Y * a
        res = 0
        for j in range(i + 1, min(i + 1 + N, n)):
            if (s.c[j] > bad_close) if ad == 1 else (s.c[j] < bad_close):
                res = 0; break
            if (s.l[j] <= good) if ad == 1 else (s.h[j] >= good):
                res = 1; break
        out.append(res)
    return out


# ------------------------------------------------------------ collection
def collect(s: Series, ln: int, seeds=REPLICAS):
    """Real touches, and REPLICAS sets of matched-random touches."""
    A = engine.atr(s, 14)
    levels = build_levels(s, A, ln)
    real = scan_touches(s, A, levels)
    ctrl = []
    for r in range(seeds):
        ctrl.append(scan_touches(s, A, randomise(levels, A, s, 1000 + r)))
    return A, levels, real, ctrl


# ------------------------------------------------------------- bucketing
BUCKETS = {
    "age": ("AGE of level at touch (bars)",
            [(0, 20, "0-20"), (20, 50, "20-50"), (50, 200, "50-200"),
             (200, 1000, "200-1000"), (1000, 10 ** 9, "1000+")],
            lambda t: t["age"]),
    "clu": ("CLUSTER SIZE (LuxAlgo draws only at 3+)",
            [(1, 2, "1"), (2, 3, "2"), (3, 4, "3"), (4, 10 ** 9, "4+")],
            lambda t: t["clu"]),
    "prior": ("PRIOR TOUCHES of this level",
              [(0, 1, "0"), (1, 2, "1"), (2, 3, "2"), (3, 10 ** 9, "3+")],
              lambda t: t["prior"]),
    "state": ("PRIOR STATE: intact / swept / broken",
              [(0, 1, "intact"), (1, 2, "swept"), (2, 3, "broken")],
              lambda t: t["state"]),
    "withtr": ("approach WITH (1) or AGAINST (0) the 50-bar trend",
               [(0, 1, "against"), (1, 2, "with")],
               lambda t: t["withtr"]),
}


def tally(touches, res, edges, keyf):
    """-> list of (label, n, k) per bucket."""
    out = []
    for lo, hi, lab in edges:
        k = n = 0
        for t, r in zip(touches, res):
            v = keyf(t)
            if lo <= v < hi:
                n += 1; k += r
        out.append((lab, n, k))
    return out


def market_rows(sym, tf, ln, N, X):
    s = engine.load(sym, tf)
    A, levels, real, ctrl = collect(s, ln)
    rres = score(s, real, N, X)
    cres = [score(s, c, N, X) for c in ctrl]
    return s, levels, real, rres, ctrl, cres


# ------------------------------------------------------------ single mkt
def run(sym="GOLD", tf="1h"):
    ln, N, X = PRIMARY["ln"], PRIMARY["N"], PRIMARY["X"]
    s, levels, real, rres, ctrl, cres = market_rows(sym, tf, ln, N, X)
    kr, nr = sum(rres), len(rres)
    kc = sum(sum(c) for c in cres); nc = sum(len(c) for c in cres)

    print("=" * 86)
    print(f"  E-053  DO MARKED LEVELS REACT? — {sym} {tf}   {len(s)} bars")
    print(f"  level = pivot len {ln} | reaction = {X} ATR away within {N} bars, "
          f"no close {Y_INVAL} ATR beyond")
    print(f"  {len(levels)} level objects built | control = {REPLICAS} "
          f"matched random replicates")
    print("=" * 86)
    lr = wilson(kr, nr); lc = wilson(kc, nc)
    print(f"\n  REAL   levels: {kr:>6} of {nr:>6} touches reacted = "
          f"{100*kr/max(nr,1):5.1f}%  (95% {100*lr[0]:.1f}-{100*lr[1]:.1f}%)")
    print(f"  RANDOM levels: {kc:>6} of {nc:>6} touches reacted = "
          f"{100*kc/max(nc,1):5.1f}%  (95% {100*lc[0]:.1f}-{100*lc[1]:.1f}%)")
    print(f"  DIFFERENCE   : {100*(kr/max(nr,1) - kc/max(nc,1)):+5.1f} points"
          f"   (optimistic z {two_prop_z(kr,nr,kc,nc):+.2f})")

    for key, (title, edges, keyf) in BUCKETS.items():
        print(f"\n  by {title}")
        print(f"    {'bucket':<12}{'n real':>8}{'real %':>9}"
              f"{'95% interval':>16}{'n rand':>8}{'rand %':>9}{'diff':>8}")
        tr = tally(real, rres, edges, keyf)
        tc = [(0, 0, 0)] * len(edges)
        acc = {lab: [0, 0] for _, _, lab in edges}
        for c, cr in zip(ctrl, cres):
            for lab, n, k in tally(c, cr, edges, keyf):
                acc[lab][0] += n; acc[lab][1] += k
        for lab, n, k in tr:
            cn, ck = acc[lab]
            if n < 25 or cn < 25:
                print(f"    {lab:<12}{n:>8}{'too few':>9}")
                continue
            p = k / n; q = ck / cn
            l, u = wilson(k, n)
            print(f"    {lab:<12}{n:>8}{100*p:>8.1f}%"
                  f"{f'{100*l:.1f}-{100*u:.1f}%':>16}{cn:>8}{100*q:>8.1f}%"
                  f"{100*(p-q):>+8.1f}")
    return


# ------------------------------------------------------------- the grid
def run_grid():
    """Every len x N x X combination, real minus random, on all 8 markets.
    Printed in full so that no single flattering cell can be quoted as the
    result. 4 x 3 x 3 = 36 configurations."""
    print("=" * 100)
    print("  E-053  PARAMETER GRID — cell = (real reaction %) minus "
          "(matched-random reaction %), in points")
    print("  A real effect is POSITIVE and the SAME SIGN across a row. "
          "Mixed signs are noise.")
    print("=" * 100)
    cache = {}
    for sym, tf in COMBOS:
        s = engine.load(sym, tf)
        for ln in GRID_LEN:
            cache[(sym, tf, ln)] = (s,) + collect(s, ln)[1:]
    hdr = "".join(f"{sym[:4]+tf:>11}" for sym, tf in COMBOS)
    print(f"\n  {'len  N    X':<14}{hdr}{'  mean':>9}{' pos':>6}")
    rows = []
    for ln in GRID_LEN:
        for N in GRID_N:
            for X in GRID_X:
                cells, npos, tot, diffs = [], 0, 0, []
                for sym, tf in COMBOS:
                    s, levels, real, ctrl = cache[(sym, tf, ln)]
                    rres = score(s, real, N, X)
                    kr, nr = sum(rres), len(rres)
                    kc = nc = 0
                    for c in ctrl:
                        cr = score(s, c, N, X)
                        kc += sum(cr); nc += len(cr)
                    if nr < 30 or nc < 30:
                        cells.append(f"{'-':>11}"); continue
                    d = 100 * (kr / nr - kc / nc)
                    diffs.append(d); tot += 1
                    if d > 0: npos += 1
                    cells.append(f"{d:>+11.1f}")
                m = sum(diffs) / len(diffs) if diffs else 0.0
                rows.append((ln, N, X, m, npos, tot))
                print(f"  {ln:<5}{N:<5}{X:<4}" + "".join(cells)
                      + f"{m:>+9.1f}{f'{npos}/{tot}':>6}")
    allm = [r[3] for r in rows]
    print(f"\n  36 configurations. mean over all: {sum(allm)/len(allm):+.2f} points."
          f"  best {max(allm):+.2f}   worst {min(allm):+.2f}")
    print(f"  configurations where real beat random on >=6 of 8 markets: "
          f"{sum(1 for r in rows if r[4] >= 6)} of {len(rows)}")
    return rows


# ------------------------------------------------------- cross-market
def run_all():
    ln, N, X = PRIMARY["ln"], PRIMARY["N"], PRIMARY["X"]
    print("=" * 100)
    print("  E-053  DO MARKED LEVELS REACT? — CROSS-MARKET")
    print(f"  PRIMARY CONFIG: pivot len {ln}, reaction {X} ATR within {N} bars,"
          f" invalidation close {Y_INVAL} ATR beyond,")
    print(f"  cluster margin ATR/{MARGIN}, touch cooldown {K_COOL} bars, "
          f"{REPLICAS} matched-random replicates.")
    print("=" * 100)

    store = {}
    print(f"\n  {'market':<14}{'bars':>7}{'levels':>8}{'touches':>9}"
          f"{'REAL %':>9}{'95% int':>15}{'RAND %':>9}{'diff':>8}{'z':>7}")
    for sym, tf in COMBOS:
        s, levels, real, rres, ctrl, cres = market_rows(sym, tf, ln, N, X)
        kr, nr = sum(rres), len(rres)
        kc = sum(sum(c) for c in cres); nc = sum(len(c) for c in cres)
        if nr < 30:
            print(f"  {sym+' '+tf:<14}{len(s):>7}{len(levels):>8}{nr:>9}"
                  f"{'too few':>9}")
            continue
        store[f"{sym} {tf}"] = (real, rres, ctrl, cres)
        l, u = wilson(kr, nr)
        print(f"  {sym+' '+tf:<14}{len(s):>7}{len(levels):>8}{nr:>9}"
              f"{100*kr/nr:>8.1f}%{f'{100*l:.1f}-{100*u:.1f}%':>15}"
              f"{100*kc/nc:>8.1f}%{100*(kr/nr-kc/nc):>+8.1f}"
              f"{two_prop_z(kr,nr,kc,nc):>+7.2f}")

    nbuckets = 0
    for key, (title, edges, keyf) in BUCKETS.items():
        print(f"\n  --- {title} " + "-" * max(0, 60 - len(title)))
        print("  cell = real % minus matched-random % IN THE SAME BUCKET, points")
        labs = [lab for _, _, lab in edges]
        print(f"    {'market':<14}" + "".join(f"{l:>12}" for l in labs))
        pos = [0] * len(labs); seen = [0] * len(labs)
        realpct = [[] for _ in labs]
        for name, (real, rres, ctrl, cres) in store.items():
            tr = tally(real, rres, edges, keyf)
            acc = {lab: [0, 0] for lab in labs}
            for c, cr in zip(ctrl, cres):
                for lab, n, k in tally(c, cr, edges, keyf):
                    acc[lab][0] += n; acc[lab][1] += k
            cells = []
            for bi, (lab, n, k) in enumerate(tr):
                cn, ck = acc[lab]
                if n < 25 or cn < 25:
                    cells.append(f"{'-':>12}"); continue
                d = 100 * (k / n - ck / cn)
                realpct[bi].append(100 * k / n)
                cells.append(f"{d:>+12.1f}")
                seen[bi] += 1
                if d > 0: pos[bi] += 1
            print(f"    {name:<14}" + "".join(cells))
        print(f"    {'real ABOVE rand':<14}"
              + "".join(f"{f'{pos[b]}/{seen[b]}':>12}" for b in range(len(labs))))
        print(f"    {'mean real %':<14}"
              + "".join(f"{(sum(realpct[b])/len(realpct[b]) if realpct[b] else 0):>12.1f}"
                        for b in range(len(labs))))
        nbuckets += sum(1 for b in range(len(labs)) if seen[b] > 0)

    print("\n" + "=" * 100)
    print(f"  MULTIPLE TESTING: {nbuckets} buckets examined in the tables above,")
    print(f"  plus 36 parameter configurations in run_grid(). Under the null a "
          f"bucket lands")
    print(f"  >=7 of 8 on one side with probability 2*9/256 = 7.0%, so about "
          f"{nbuckets*0.070:.1f} such")
    print(f"  cells are expected BY CHANCE ALONE among {nbuckets} buckets. "
          f"Count the ones found")
    print(f"  before believing any of them.")
    print("=" * 100)


# --------------------------------------------------------------- checks
def _rw(n=14000, seed=7, s0=2000.0, vol=0.004):
    """Driftless random walk in OHLC form. Pivots here mean nothing."""
    rng = random.Random(seed)
    ts, o, h, l, c = [], [], [], [], []
    px = s0
    for i in range(n):
        op = px
        steps = [px]
        for _ in range(4):
            px *= math.exp(rng.gauss(0, vol))
            steps.append(px)
        ts.append(i * 3600); o.append(op)
        h.append(max(steps)); l.append(min(steps)); c.append(px)
    return Series(ts, o, h, l, c)


def selfcheck():
    print("=" * 86)
    print("  E-053 SELF-CHECK — look-ahead audit and random-walk null")
    print("=" * 86)
    s = engine.load("GOLD", "1h")
    A = engine.atr(s, 14)
    ln = PRIMARY["ln"]
    levels = build_levels(s, A, ln)
    byid = {L["id"]: L for L in levels}
    real = scan_touches(s, A, levels)

    fails = 0

    # 1. every touch happens strictly after the level's confirmation bar
    bad = [t for t in real if t["i"] <= byid[t["id"]]["conf"]]
    print(f"  [{'PASS' if not bad else 'FAIL'}]  every touch bar > level "
          f"confirm bar  ({len(bad)} violations)")
    fails += bool(bad)

    # 2. every touch happens at least ln+1 bars after the PIVOT bar
    bad = [t for t in real if t["age"] < ln + 1]
    print(f"  [{'PASS' if not bad else 'FAIL'}]  every touch age >= len+1 "
          f"= {ln+1} bars  ({len(bad)} violations)")
    fails += bool(bad)

    # 3. cluster size counts only members confirmed <= i-1
    bad = 0
    for t in real:
        mb = byid[t["id"]]["mb"]
        if t["clu"] != sum(1 for b in mb if b <= t["i"] - 1):
            bad += 1
    print(f"  [{'PASS' if not bad else 'FAIL'}]  cluster size uses only "
          f"members confirmed by i-1  ({bad} violations)")
    fails += bool(bad)

    # 4. touch cooldown honoured
    seenn = {}
    bad = 0
    for t in sorted(real, key=lambda x: x["i"]):
        p = seenn.get(t["id"])
        if p is not None and t["i"] - p < K_COOL:
            bad += 1
        seenn[t["id"]] = t["i"]
    print(f"  [{'PASS' if not bad else 'FAIL'}]  no level touched twice "
          f"within {K_COOL} bars  ({bad} violations)")
    fails += bool(bad)

    # 5. the scoring window never reads bar i or earlier.
    #    Proven by construction (range starts at i+1); re-proven empirically by
    #    scoring with the touch bar's own data blanked out.
    import copy
    s2 = Series(list(s.ts), list(s.o), list(s.h), list(s.l), list(s.c))
    base = score(s, real, PRIMARY["N"], PRIMARY["X"])
    for t in real:
        i = t["i"]
        s2.h[i] = s2.l[i] = s2.c[i] = s2.o[i] = float("nan")
    alt = score(s2, real, PRIMARY["N"], PRIMARY["X"])
    same = sum(1 for a, b in zip(base, alt) if a == b)
    print(f"  [{'PASS' if same == len(base) else 'FAIL'}]  blanking the touch "
          f"bar's own OHLC changes 0 outcomes  ({len(base)-same} changed)")
    fails += (same != len(base))

    # 6. state at touch is as of i-1: recompute state independently
    bad = 0
    for t in real[:4000]:
        L = byid[t["id"]]; P = L["p"]; st = 0
        for j in range(L["conf"] + 1, t["i"]):
            if st == 2: break
            if L["typ"] == 1:
                if s.c[j] > P: st = 2
                elif s.h[j] > P: st = max(st, 1)
            else:
                if s.c[j] < P: st = 2
                elif s.l[j] < P: st = max(st, 1)
        if st != t["state"]:
            bad += 1
    print(f"  [{'PASS' if not bad else 'FAIL'}]  swept/broken state at a touch "
          f"is reproducible from bars < i  ({bad} of {min(4000,len(real))} differ)")
    fails += bool(bad)

    # 7. RANDOM-WALK NULL — the important one
    print("\n  RANDOM-WALK NULL (driftless GBM, 3 seeds). Pivots there carry no")
    print("  information, so real-minus-random MUST be ~0. Whatever it is, is")
    print("  the bias of this machinery and every real number must be read")
    print("  against it, not against zero.")
    print(f"    {'seed':<8}{'n real':>9}{'real %':>9}{'n rand':>9}"
          f"{'rand %':>9}{'diff':>8}")
    ds = []
    for sd in (7, 8, 9):
        rs = _rw(seed=sd)
        RA = engine.atr(rs, 14)
        lv = build_levels(rs, RA, ln)
        rt = scan_touches(rs, RA, lv)
        rr = score(rs, rt, PRIMARY["N"], PRIMARY["X"])
        kc = nc = 0
        for r in range(REPLICAS):
            ct = scan_touches(rs, RA, randomise(lv, RA, rs, 500 + r))
            cr = score(rs, ct, PRIMARY["N"], PRIMARY["X"])
            kc += sum(cr); nc += len(cr)
        d = 100 * (sum(rr) / len(rr) - kc / nc)
        ds.append(d)
        print(f"    {sd:<8}{len(rr):>9}{100*sum(rr)/len(rr):>8.1f}%"
              f"{nc:>9}{100*kc/nc:>8.1f}%{d:>+8.1f}")
    print(f"    mean null offset: {sum(ds)/len(ds):+.2f} points")

    print("\n  " + ("ALL LOOK-AHEAD CHECKS PASSED" if fails == 0
                    else f"{fails} CHECK(S) FAILED — DO NOT TRUST ANY NUMBER"))
    return fails


if __name__ == "__main__":
    a = sys.argv[1].upper() if len(sys.argv) > 1 else "ALL"
    if a == "SELFCHECK":
        sys.exit(1 if selfcheck() else 0)
    elif a == "GRID":
        run_grid()
    elif a == "ALL":
        run_all()
    else:
        run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "1h")

"""
E-099 — DID THE STACK MISS THE BIG MOVES? Measuring the owner's complaint.

Veer: "the liquidity ea and pine are not good enough the signals don't use
levels wisely they miss clear clear moves that could've made us 40-200 pounds
easily ... we need bsl ssl liquidity sweeps rejection zones support resistance
play ping pong".

That is a complaint about MISSED MOVES, not about bad trades. Nothing in this
repository has ever measured it: every experiment scores the trades that were
TAKEN. This file scores the trades that were NOT.

THE MEASUREMENT
  BIG MOVE   a zigzag leg of at least X points (X = 40 and, separately, 100),
             from the turning point that started it. 0.01 lots of XAUUSD is
             GBP0.787 per point, so 40 points ~ GBP31 and 100 points ~ GBP79 -
             which is the range Veer named.
  CAUGHT     the shipped stack (E-080: toptick + FVG + order block, one
             position, first touched wins) entered a trade in the SAME
             DIRECTION with entry bar within N bars of the turning point.
  MISSED     everything else.

Then, for the misses only, WHY. Each miss is assigned exactly one cause, in
priority order, by re-running the candidate generator with instrumentation.

NO LOOK-AHEAD ANYWHERE IN THE TRADING PATH. The zigzag itself is computed with
hindsight - that is deliberate and it is not a signal, it is the SCOREBOARD.
It defines what was there to be caught. Nothing reads it.

XAUUSD only, 15m and 1h. There is no M1/M5 data in this repository and it
cannot be fetched, so nothing here measures the timeframes Veer trades.

Run:  python3 JARVIS/research/missed_moves.py
"""
from __future__ import annotations
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from engine import Series
from liquidity import pivots, stat
from toptick import zone_stream, entry_level
from smc import smc_state, resolve, STOP_ATR, TGT_R, FRAC
from smc_combine import all_signals, simulate

COMBOS = [("GOLD", "15m"), ("GOLD", "1h")]
USE = {"toptick", "fvg", "ob"}
WARMUP, ARM_LIFE = 250, 60


# ------------------------------------------------------------- the scoreboard
def zigzag(s: Series, thresh: float):
    """Alternating turning points, confirmed by a `thresh` point retracement.

    Returns legs as (t0, t1, direction, magnitude). t0 is the bar of the
    turning point the move STARTED from; t1 the bar it ended on. Uses the whole
    series - it is the scoreboard, not a signal. Nothing trading reads it.
    """
    n = len(s)
    if n < 3:
        return []
    piv = []                       # (bar, price, kind) kind +1 = high, -1 = low
    dirn = 0
    hi_i, hi_p = 0, s.h[0]
    lo_i, lo_p = 0, s.l[0]
    for i in range(1, n):
        if s.h[i] > hi_p: hi_i, hi_p = i, s.h[i]
        if s.l[i] < lo_p: lo_i, lo_p = i, s.l[i]
        if dirn >= 0 and s.l[i] <= hi_p - thresh:
            piv.append((hi_i, hi_p, 1))
            dirn = -1
            lo_i = min(range(hi_i, i + 1), key=lambda k: s.l[k])
            lo_p = s.l[lo_i]
        elif dirn <= 0 and s.h[i] >= lo_p + thresh:
            piv.append((lo_i, lo_p, -1))
            dirn = 1
            hi_i = max(range(lo_i, i + 1), key=lambda k: s.h[k])
            hi_p = s.h[hi_i]
    legs = []
    for a, b in zip(piv, piv[1:]):
        (ia, pa, ka), (ib, pb, kb) = a, b
        if ka == kb or ib <= ia:
            continue
        d = 1 if ka == -1 else -1          # an up-leg starts from a LOW
        mag = abs(pb - pa)
        if mag >= thresh:
            legs.append((ia, ib, d, mag))
    return legs


# ------------------------------------------------- instrumented zone tracking
def zone_diag(s: Series, per_bar, A, warmup=WARMUP, arm_life=ARM_LIFE):
    """Re-run the toptick candidate loop, recording per bar WHY each live zone
    did not produce a candidate. Identical logic to smc_combine.all_signals -
    if it diverges the counts below are meaningless, so it is written as a copy
    with a recorder rather than a reimplementation.
    """
    diag = [dict() for _ in range(len(s))]     # bar -> {side: reason}
    used = set()
    for i in range(warmup, len(s) - 2):
        a = A[i]
        if a is None or a <= 0:
            continue
        fired = False
        for z in per_bar[i]:
            side = -1 if z["dir"] == 1 else 1
            key = (z["born"], round(z["px"], 6), z["dir"])
            lvl = entry_level(z, FRAC, a)
            if key in used:
                diag[i].setdefault(side, ("zone already used", lvl, z)); continue
            if i - z["born"] > arm_life:
                diag[i].setdefault(side, ("zone too old to arm", lvl, z)); continue
            if (side == -1 and s.c[i] >= lvl) or (side == 1 and s.c[i] <= lvl):
                diag[i].setdefault(side, ("price already past the limit", lvl, z)); continue
            k = i + 1
            if k >= len(s):
                continue
            if not ((s.h[k] >= lvl) if side == -1 else (s.l[k] <= lvl)):
                diag[i].setdefault(side, ("limit not reached", lvl, z)); continue
            if fired:
                diag[i].setdefault(side, ("another zone fired first", lvl, z)); continue
            used.add(key)
            diag[i][side] = ("CANDIDATE", lvl, z)
            fired = True
            break
    return diag


def prior_levels(s: Series, A, pv_len=7, lookback=400):
    """Every confirmed pivot extreme, indexed by the bar it becomes KNOWN."""
    hi, lo = pivots(s, pv_len)
    known = [[] for _ in range(len(s))]        # bar -> list of (px, dir, born)
    liveH, liveL = [], []
    for i in range(len(s)):
        j = i - pv_len
        if j >= 0:
            if hi[j] is not None: liveH.append((hi[j], j))
            if lo[j] is not None: liveL.append((lo[j], j))
        liveH = [x for x in liveH if i - x[1] <= lookback]
        liveL = [x for x in liveL if i - x[1] <= lookback]
        known[i] = [(p, 1, b) for p, b in liveH] + [(p, -1, b) for p, b in liveL]
    return known


def classify(s, A, per_bar, diag, known, cands_by_bar, taken_by_bar, t0, d, N):
    """One cause for one missed move, priority ordered. Exactly one cause per
    move, so the counts add to the number of missed moves."""
    win = range(max(0, t0 - N), min(len(s) - 1, t0 + N + 1))
    a = A[t0] or 1e-9
    ext = s.l[t0] if d == 1 else s.h[t0]

    # --- did a matching CANDIDATE exist near the turn at all?
    hits = []
    for i in win:
        for cd in cands_by_bar.get(i, []):
            if cd["side"] == d:
                hits.append(cd)
    if hits:
        taken_late = [h for h in hits if h["taken_j"] is not None]
        if taken_late:
            return ("A. signal existed and WAS TAKEN, but filled too late",
                    taken_late[0]["src"])
        fillable = [h for h in hits if h["fill_j"] is not None]
        if fillable:
            return ("B. signal existed and was fillable, account was BUSY",
                    fillable[0]["src"])
        near = min(hits, key=lambda h: abs(ext - h["lvl"]))
        return ("C. signal existed, limit NEVER FILLED inside its wait window",
                (near["src"], abs(ext - near["lvl"]) / a))

    # zone-level causes
    reasons = []
    for i in win:
        r = diag[i].get(d)
        if r:
            reasons.append(r)
    order = ["limit not reached", "price already past the limit",
             "zone already used", "zone too old to arm", "another zone fired first"]
    for want in order:
        for (why, lvl, z) in reasons:
            if why == want:
                if want == "limit not reached":
                    short = abs(ext - lvl) / a
                    return ("D. zone LIVE, resting limit NEVER REACHED "
                            "(0.25 ATR past the far edge)", short)
                if want == "price already past the limit":
                    return ("E. zone LIVE but price was already past the limit", None)
                if want == "zone already used":
                    return ("F. zone BLACKLISTED as already used", None)
                if want == "zone too old to arm":
                    return ("G. zone LIVE but older than arm_life=60 bars", None)
                return ("H. another zone fired first on that bar", None)

    # H. no zone of the right kind at all. Was a prior swing SWEPT here?
    lv = known[t0]
    tol = a / 6.9
    swept = False
    for (p, kd, b) in lv:
        if b >= t0 - 1:
            continue
        if d == 1 and kd == -1 and s.l[t0] < p and s.c[t0] > p:
            swept = True; break
        if d == -1 and kd == 1 and s.h[t0] > p and s.c[t0] < p:
            swept = True; break
    if swept:
        return ("I. NO ZONE - but a prior swing WAS swept at the turn", None)

    # I. no zone, no sweep, but the price had been visited before
    touches = 0
    for k in range(max(0, t0 - 400), t0 - 5):
        px = s.l[k] if d == 1 else s.h[k]
        if abs(px - ext) <= tol:
            touches += 1
    if touches >= 2:
        return ("J. NO ZONE - but the level had been touched before", touches)

    return ("K. no level of any kind at the turn", None)


def pools(s: Series, A, pv_len=5, tol_atr=0.10, life=400, min_n=2):
    """BSL/SSL: >= min_n confirmed pivot extremes within tol_atr of each other.
    Per-bar list of (price, dir, count). Confirmed pivots only, so a pool at
    bar i uses nothing that was not already on the chart at bar i."""
    hi, lo = pivots(s, pv_len)
    out = [[] for _ in range(len(s))]
    liveH, liveL = [], []
    for i in range(len(s)):
        j = i - pv_len
        if j >= 0:
            if hi[j] is not None: liveH.append((hi[j], j))
            if lo[j] is not None: liveL.append((lo[j], j))
        liveH = [x for x in liveH if i - x[1] <= life]
        liveL = [x for x in liveL if i - x[1] <= life]
        a = A[i]
        if not a or a <= 0:
            continue
        tol = tol_atr * a
        res = []
        for store, d in ((liveH, 1), (liveL, -1)):
            for (p, b) in store:
                grp = [q for (q, bb) in store if abs(q - p) <= tol]
                if len(grp) >= min_n:
                    res.append((sum(grp) / len(grp), d, len(grp)))
        out[i] = res
    return out


def proximity(s, A, per_bar, st, known, pool_bars, t0, d):
    """How far, in ATR, was the turning point from the NEAREST level of each
    kind that the chart already knew about? Direction-matched: an up-move needs
    a sellside/bullish level, a down-move a buyside/bearish one."""
    a = A[t0] or 1e-9
    ext = s.l[t0] if d == 1 else s.h[t0]
    want_zone = -1 if d == 1 else 1          # toptick dir: -1 sellside -> BUY
    r = {}
    zs = [z for z in per_bar[t0] if z["dir"] == want_zone]
    r["toptick zone edge"] = min((abs(ext - (z["bot"] if want_zone == -1 else z["top"]))
                                  for z in zs), default=None)
    r["toptick resting limit"] = min((abs(ext - entry_level(z, FRAC, a)) for z in zs),
                                     default=None)
    r["FVG mid"] = min((abs(ext - (g["top"] + g["bot"]) / 2.0)
                        for g in st["fvg"][t0] if g["dir"] == d and not g["inverted"]),
                       default=None)
    r["order block mid"] = min((abs(ext - (b["top"] + b["bot"]) / 2.0)
                                for b in st["ob"][t0] if b["dir"] == d), default=None)
    r["any prior swing pivot"] = min((abs(ext - p) for (p, kd, b) in known[t0]
                                      if kd == -d and b < t0 - 1), default=None)
    r["equal-hi/lo pool (>=2)"] = min((abs(ext - p) for (p, kd, cnt) in pool_bars[t0]
                                       if kd == -d), default=None)
    any_ = [v for v in (r["toptick resting limit"], r["FVG mid"],
                        r["order block mid"]) if v is not None]
    r["ANY stack resting order"] = min(any_) if any_ else None
    return {k: (v / a if v is not None else None) for k, v in r.items()}


def analyse(sym, tf, N=3, threshes=(40.0, 100.0)):
    s = engine.load(sym, tf)
    c = study.COSTS[sym]
    A = engine.atr(s, 14)
    per_bar, _ = zone_stream(s)
    st = smc_state(s, A)
    cands = all_signals(s, c, per_bar, A, st, USE)
    trades = simulate(s, c, cands, st)

    # index candidates by signal bar, recording for EACH candidate whether its
    # limit would have been reachable at all (ignoring the busy filter) and
    # whether the account actually took it. Those are different failures.
    half = c.spread / 2.0
    cands_by_bar = {}
    taken, busy = [], -1
    for (i, side, lvl, aa, src_, wait) in cands:
        fill_j = None
        for k in range(i + 1, min(i + 1 + wait, len(s))):
            if (side == 1 and s.l[k] <= lvl) or (side == -1 and s.h[k] >= lvl):
                fill_j = k; break
        rec = {"i": i, "side": side, "lvl": lvl, "a": aa, "src": src_,
               "wait": wait, "fill_j": fill_j, "taken_j": None}
        cands_by_bar.setdefault(i, []).append(rec)
        if i <= busy or fill_j is None:
            continue
        entry = lvl + side * (half + c.slippage)
        stop = entry - side * STOP_ATR * aa
        if (entry - stop) * side <= 0:
            continue
        tgtpx = entry + side * TGT_R * (entry - stop) * side
        t = resolve(s, c, fill_j, side, entry, stop, tgtpx, 200)
        rec["taken_j"] = fill_j
        taken.append({"i": i, "j": fill_j, "side": side, "src": src_,
                      "exit": t["exit_bar"], "r": t["r"], "pts": t["pts"]})
        busy = t["exit_bar"]
    # the replay above must reproduce smc_combine.simulate exactly, or every
    # cause count below is describing a different strategy than the shipped one
    assert len(taken) == len(trades), (len(taken), len(trades))
    for x, y in zip(taken, trades):
        assert abs(x["r"] - y["r"]) < 1e-9
    taken_by_bar = {t["i"]: t for t in taken}
    diag = zone_diag(s, per_bar, A)
    pool_bars = pools(s, A)
    known = prior_levels(s, A)

    out = {"sym": sym, "tf": tf, "bars": len(s), "n_trades": len(taken),
           "levels": {}}
    out["_ctx"] = (s, A, per_bar, st, known, pool_bars)
    for X in threshes:
        legs = [L for L in zigzag(s, X) if L[0] >= WARMUP + 20
                and L[1] < len(s) - 2]
        caught, missed, positioned = [], [], 0
        for (t0, t1, d, mag) in legs:
            hit = None
            for t in taken:
                if t["side"] == d and abs(t["j"] - t0) <= N:
                    hit = t; break
            if hit:
                caught.append((t0, t1, d, mag, hit))
            else:
                # were we at least positioned the right way during the leg?
                for t in taken:
                    if t["side"] == d and t["j"] <= t1 and t["exit"] >= t0:
                        positioned += 1
                        break
                missed.append((t0, t1, d, mag))
        # signal-level catch (before the one-position filter)
        sig_caught = 0
        for (t0, t1, d, mag) in legs:
            found = False
            for i in range(max(0, t0 - N), min(len(s), t0 + N + 1)):
                for cd in cands_by_bar.get(i, []):
                    if cd["side"] == d:
                        found = True; break
                if found: break
            if found:
                sig_caught += 1
        rng = random.Random(4242)
        pool_idx = [i for i in range(WARMUP + 20, len(s) - 2) if A[i]]
        rand_bars = [(rng.choice(pool_idx), rng.choice((1, -1)))
                     for _ in range(1500)]
        causes, cause_pts, srcs = {}, {}, {}
        shortfalls, cshort = [], []
        for (t0, t1, d, mag) in missed:
            cz, extra = classify(s, A, per_bar, diag, known, cands_by_bar,
                                 taken_by_bar, t0, d, N)
            causes[cz] = causes.get(cz, 0) + 1
            cause_pts[cz] = cause_pts.get(cz, 0.0) + mag
            if cz.startswith("D.") and isinstance(extra, float):
                shortfalls.append(extra)
            if cz.startswith("C.") and isinstance(extra, tuple):
                srcs[extra[0]] = srcs.get(extra[0], 0) + 1
                cshort.append(extra[1])
        out["levels"][X] = {
            "legs": legs, "caught": caught, "missed": missed,
            "positioned": positioned, "sig_caught": sig_caught,
            "causes": causes, "shortfalls": shortfalls,
            "cause_pts": cause_pts, "c_srcs": srcs, "c_short": cshort,
            "prox_miss": [proximity(s, A, per_bar, st, known, pool_bars, L[0], L[2])
                          for L in missed],
            "prox_rand": [proximity(s, A, per_bar, st, known, pool_bars, b, dd)
                          for (b, dd) in rand_bars],
            "prox_catch": [proximity(s, A, per_bar, st, known, pool_bars,
                                     L[0], L[2]) for L in caught]}
    return out, s, A, taken


def main():
    N = 3
    print("=" * 100)
    print("  E-099  THE MISSED MOVES — is the owner's complaint true?")
    print("  BIG MOVE = a zigzag leg of >= X points. CAUGHT = the shipped stack")
    print("  (toptick + FVG + order block, one position) entered the SAME WAY")
    print(f"  within {N} bars of the turning point. GOLD only; no M1/M5 data exists.")
    print("=" * 100)

    for sym, tf in COMBOS:
        res, s, A, taken = analyse(sym, tf, N=N)
        inmkt = sum(t["exit"] - t["j"] + 1 for t in taken)
        print(f"\n  ### {sym} {tf}   {res['bars']} bars   "
              f"stack took {res['n_trades']} trades, in the market "
              f"{100*inmkt/res['bars']:.1f}% of bars")
        for X, d in res["levels"].items():
            legs, ca, mi = d["legs"], d["caught"], d["missed"]
            if not legs:
                continue
            pts_all = sum(L[3] for L in legs)
            pts_miss = sum(L[3] for L in mi)
            print(f"\n   moves >= {X:.0f} points: {len(legs)}    "
                  f"CAUGHT {len(ca)} ({100*len(ca)/len(legs):.1f}%)    "
                  f"MISSED {len(mi)} ({100*len(mi)/len(legs):.1f}%)")
            print(f"     points on the table {pts_all:>8.0f}   "
                  f"in missed legs {pts_miss:>8.0f} "
                  f"({100*pts_miss/pts_all:.1f}%)")
            print(f"     signal existed near the turn (before the one-position "
                  f"filter): {d['sig_caught']} ({100*d['sig_caught']/len(legs):.1f}%)")
            print(f"     missed but at least POSITIONED the right way during "
                  f"the leg: {d['positioned']}")
            if d["caught"]:
                cr = [h[4]["r"] for h in d["caught"]]
                cp = [h[4]["pts"] for h in d["caught"]]
                print(f"     what the caught ones actually paid: "
                      f"{sum(cr)/len(cr):+.3f}R  {sum(cp):+.0f} points total, "
                      f"{sum(cp)/len(cp):+.1f} each")
            print(f"     WHY THE MISSES HAPPENED (one cause each, ranked):")
            tp = sum(d["cause_pts"].values()) or 1.0
            for k, v in sorted(d["causes"].items(), key=lambda kv: -kv[1]):
                print(f"       {v:>5}  ({100*v/len(mi):>5.1f}% of misses, "
                      f"{100*d['cause_pts'][k]/tp:>5.1f}% of missed points)  {k}")
            if d["c_short"]:
                cs = sorted(d["c_short"])
                bysrc = ", ".join(f"{k} {v}" for k, v in
                                  sorted(d["c_srcs"].items(), key=lambda kv: -kv[1]))
                print(f"       -> those unfilled signals came from: {bysrc}")
                print(f"          the turn stopped short of the nearest such limit by "
                      f"median {cs[len(cs)//2]:.2f} ATR, p25 {cs[len(cs)//4]:.2f}, "
                      f"p75 {cs[3*len(cs)//4]:.2f}")
            print(f"     WAS THERE A LEVEL AT THE TURN AT ALL? distance from the")
            print(f"     turning point to the NEAREST known level of each kind,")
            print(f"     missed moves (n={len(mi)}) vs caught (n={len(ca)}):")
            keys = ["toptick zone edge", "toptick resting limit", "FVG mid",
                    "order block mid", "ANY stack resting order",
                    "any prior swing pivot", "equal-hi/lo pool (>=2)"]
            print(f"       {'level kind':<24}{'miss med':>10}{'<0.5A':>8}"
                  f"{'<1.0A':>8}   |{'catch med':>11}{'<0.5A':>8}{'<1.0A':>8}"
                  f"   |{'RANDOM med':>12}{'<0.5A':>8}{'<1.0A':>8}")
            for kk in keys:
                row = []
                for arr in (d["prox_miss"], d["prox_catch"], d["prox_rand"]):
                    vs = sorted(x[kk] for x in arr if x[kk] is not None)
                    if not vs:
                        row.append(("  n/a", "  n/a", "  n/a")); continue
                    tot = len(arr)
                    row.append((f"{vs[len(vs)//2]:.2f}A",
                                f"{100*sum(1 for v in vs if v<0.5)/tot:.0f}%",
                                f"{100*sum(1 for v in vs if v<1.0)/tot:.0f}%"))
                print(f"       {kk:<24}{row[0][0]:>10}{row[0][1]:>8}{row[0][2]:>8}"
                      f"   |{row[1][0]:>11}{row[1][1]:>8}{row[1][2]:>8}"
                      f"   |{row[2][0]:>12}{row[2][1]:>8}{row[2][2]:>8}")
            if d["shortfalls"]:
                sf = sorted(d["shortfalls"])
                print(f"       -> of the 'limit not reached' misses, the turning "
                      f"point stopped short of the resting limit by")
                print(f"          median {sf[len(sf)//2]:.2f} ATR, "
                      f"p25 {sf[len(sf)//4]:.2f}, p75 {sf[3*len(sf)//4]:.2f} "
                      f"(n={len(sf)})")

    print("\n" + "=" * 100)
    print("  SENSITIVITY OF THE HEADLINE TO THE WINDOW N")
    print("=" * 100)
    for sym, tf in COMBOS:
        for n in (1, 3, 5, 10, 20):
            res, _, _, _ = analyse(sym, tf, N=n, threshes=(40.0,))
            d = res["levels"][40.0]
            print(f"   {sym} {tf}  N={n:<3}  caught "
                  f"{len(d['caught'])}/{len(d['legs'])} "
                  f"({100*len(d['caught'])/max(len(d['legs']),1):.1f}%)   "
                  f"signal-level {100*d['sig_caught']/max(len(d['legs']),1):.1f}%")




# --------------------------------------------------- the two levers the causes name
def lever_sweep(N=3, thresh=40.0):
    """The cause ranking names two knobs. Turn them and see what happens to the
    CATCH RATE and to the MONEY at the same time.

      arm_life  a zone stops arming an order 60 bars after it is born. That is
                cause G, the second largest.
      FRAC      the resting limit sits 0.25 ATR PAST the far edge
                (InpEntryPast). That is cause D.

    A knob earns a change only if the trades it ADDS are not worse than the
    ones already there - E-074's rule. So every row reports n, expectancy,
    POINTS and catch rate together.
    """
    import smc_combine as SC
    print("\n" + "=" * 112)
    print("  THE TWO LEVERS THE CAUSE RANKING NAMES, turned")
    print("  FRAC < 0 rests the limit that many ATR PAST the far edge; FRAC 1.0")
    print("  is ON the far edge, 0.0 the near edge. arm_life is in bars.")
    print(f"  catch% is of moves >= {thresh:.0f} points, entry within {N} bars of the turn.")
    print("=" * 112)
    orig = SC.FRAC
    for sym, tf in COMBOS:
        s = engine.load(sym, tf)
        c = study.COSTS[sym]
        A = engine.atr(s, 14)
        per_bar, _ = zone_stream(s)
        st = smc_state(s, A)
        legs = [L for L in zigzag(s, thresh) if L[0] >= WARMUP + 20
                and L[1] < len(s) - 2]
        print(f"\n  ### {sym} {tf}   {len(legs)} moves >= {thresh:.0f} points")
        print(f"   {'FRAC':>7}{'arm_life':>10}{'n':>7}{'win%':>8}{'expect':>10}"
              f"{'t':>8}{'points':>10}{'caught':>9}{'catch%':>9}")
        print("   " + "-" * 78)
        for frac in (1.0, 0.5, 0.0, -0.25, -0.50):
            for al in (60, 180, 600):
                SC.FRAC = frac
                cands = SC.all_signals(s, c, per_bar, A, st, USE, arm_life=al)
                tr = SC.simulate(s, c, cands, st)
                if not tr:
                    continue
                # entry bars, replayed the same way simulate takes them
                ent, busy = [], -1
                for (i, side, lvl, aa, src, wait) in cands:
                    if i <= busy:
                        continue
                    j = None
                    for k in range(i + 1, min(i + 1 + wait, len(s))):
                        if (side == 1 and s.l[k] <= lvl) or (side == -1 and s.h[k] >= lvl):
                            j = k; break
                    if j is None:
                        continue
                    half = c.spread / 2.0
                    entry = lvl + side * (half + c.slippage)
                    stop = entry - side * STOP_ATR * aa
                    if (entry - stop) * side <= 0:
                        continue
                    t = resolve(s, c, j, side, entry, stop,
                                entry + side * TGT_R * (entry - stop) * side, 200)
                    ent.append((j, side))
                    busy = t["exit_bar"]
                bybar = {}
                for (j, side) in ent:
                    bybar.setdefault(j, set()).add(side)
                caught = 0
                for (t0, t1, d, mag) in legs:
                    if any(d in bybar.get(b, ()) for b in
                           range(max(0, t0 - N), min(len(s), t0 + N + 1))):
                        caught += 1
                a_ = stat(tr)
                pts = sum(x["pts"] for x in tr)
                mark = "  <- shipped" if (frac == -0.25 and al == 60) else ""
                print(f"   {frac:>+7.2f}{al:>10}{a_['n']:>7}{a_['win']:>7.1f}%"
                      f"{a_['exp']:>+9.3f}R{a_['t']:>+8.2f}{pts:>+10.0f}"
                      f"{caught:>9}{100*caught/max(len(legs),1):>8.1f}%{mark}")
    SC.FRAC = orig




def arm_life_validate(frac=-0.25, base_al=60, new_al=600):
    """The cause ranking's largest ACTIONABLE finding, attacked.

    E-074's rule: a change earns its place only if the trades it ADDS are not
    worse than the ones already there. So the added trades are isolated and
    scored on their own, and the whole variant then gets OOS, walk-forward, a
    20-seed control and a Monte Carlo drawdown.
    """
    import smc_combine as SC
    from liq_validate import mc_drawdown
    from smc import control as smc_control
    print("\n" + "=" * 100)
    print(f"  arm_life {base_al} -> {new_al} AT THE SHIPPED FRAC {frac:+.2f}, ATTACKED")
    print("=" * 100)
    orig = SC.FRAC
    SC.FRAC = frac
    for sym, tf in COMBOS:
        s = engine.load(sym, tf)
        c = study.COSTS[sym]
        A = engine.atr(s, 14)
        per_bar, _ = zone_stream(s)
        st = smc_state(s, A)
        runs = {}
        for al in (base_al, new_al):
            cands = SC.all_signals(s, c, per_bar, A, st, USE, arm_life=al)
            runs[al] = SC.simulate(s, c, cands, st)
        base, new = runs[base_al], runs[new_al]
        bkeys = {(t["exit_bar"], t["src"], round(t["r"], 6)) for t in base}
        added = [t for t in new if (t["exit_bar"], t["src"], round(t["r"], 6)) not in bkeys]
        ab, an = stat(base), stat(new)
        aa_ = stat(added)
        print(f"\n  ### {sym} {tf}")
        print(f"    base  arm_life {base_al:<4} n {ab['n']:<5} win {ab['win']:.1f}%"
              f"  {ab['exp']:+.3f}R  t {ab['t']:+.2f}"
              f"  {sum(x['pts'] for x in base):+.0f} points")
        print(f"    new   arm_life {new_al:<4} n {an['n']:<5} win {an['win']:.1f}%"
              f"  {an['exp']:+.3f}R  t {an['t']:+.2f}"
              f"  {sum(x['pts'] for x in new):+.0f} points")
        print(f"    THE TRADES IT ADDS (E-074's test): n {aa_['n']:<5}"
              f" win {aa_['win']:.1f}%  {aa_['exp']:+.3f}R  t {aa_['t']:+.2f}"
              f"  {sum(x['pts'] for x in added):+.0f} points")
        if aa_["n"] >= 30:
            se = abs(aa_["exp"] / aa_["t"]) if aa_["t"] else 0.0
            se_b = abs(ab["exp"] / ab["t"]) if ab["t"] else 0.0
            dz = (aa_["exp"] - ab["exp"]) / math.sqrt(se ** 2 + se_b ** 2) \
                if (se or se_b) else 0.0
            print(f"      added vs base: {aa_['exp'] - ab['exp']:+.3f}R,"
                  f" {dz:+.1f} sd — {'BETTER' if dz > 2 else ('WORSE' if dz < -2 else 'not distinguishable')}")
        h = len(new) // 2
        A1, B1 = stat(new[:h]), stat(new[h:])
        nb = 6
        bl = [new[i * len(new) // nb:(i + 1) * len(new) // nb] for i in range(nb)]
        bs = [stat(b) for b in bl if len(b) >= 10]
        wf = sum(1 for x in bs if x["exp"] > 0)
        ce = [stat(smc_control(s, c, A, an["n"], sd))["exp"] for sd in range(301, 321)]
        cm = sum(ce) / len(ce)
        csd = (sum((x - cm) ** 2 for x in ce) / len(ce)) ** 0.5
        se_o = abs(an["exp"] / an["t"]) if an["t"] else 0.0
        se_c = csd / math.sqrt(len(ce))
        z = (an["exp"] - cm) / math.sqrt(se_o ** 2 + se_c ** 2)
        dds = mc_drawdown([x["r"] for x in new])
        print(f"    OOS      {A1['exp']:+.3f}R (n={A1['n']})  /  {B1['exp']:+.3f}R (n={B1['n']})")
        print(f"    walk-fwd {wf}/{len(bs)}   ["
              + "  ".join("%+.2f" % x["exp"] for x in bs) + "]")
        print(f"    control  20 seeds {cm:+.3f}R  ->  {z:+.1f} sd")
        print(f"    drawdown median {dds[len(dds)//2]:.1f}R  "
              f"95th {dds[int(len(dds)*0.95)]:.1f}R")
        print(f"    VERDICT  " + study.verdict(
            {"n": an["n"], "expectancy_R": an["exp"], "t_stat": an["t"]},
            wf, len(bs), None))
    SC.FRAC = orig


if __name__ == "__main__":
    main()
    lever_sweep()
    arm_life_validate()

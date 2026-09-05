"""
E-115 — DOES THE LIQUIDITY MECHANISM EXIST AT M1 AND M5?

THE QUESTION, and it is the one that decides the live system's architecture:
the E-080 stack (top-tick zone limit + FVG + order block, corrected by E-110 to
+0.205R on GOLD 1h and +0.267R on US500 1h against a fill-convention-matched
control) has NEVER been measured below 15m. E-081 says a GBP40 account must
trade M1. E-111 finally produced real M1 bars. So: does the mechanism survive
at M1/M5 resolution, or is it a funded-account-only strategy?

WHAT THIS FILE DOES DIFFERENTLY FROM smc_combine.py

1. REAL PER-BAR SPREAD. Every fill is charged from that bar's own measured
   `spread_mean` (E-111), not `Costs.spread`. The cost is then rescaled to a
   named regime by a single multiplier on the whole spread series, so the
   per-bar SHAPE of the cost is preserved while its LEVEL is set to today's
   (2018 gold ran spread/ATR 0.93; today's estimate is 0.11 ECN to 0.25
   standard - DATA_QUALITY.md).

2. PARAMETERS SCALED BY BAR COUNT. A 7-bar pivot is 7 HOURS on 1h and 7
   MINUTES on M1. Every lookback (pivot length, zone life, arming window, gap
   life, order-block life, the limit's wait window, the maximum hold) is
   multiplied by the bar-count ratio so the LOOKBACK IN TIME is comparable:
   x60 on M1, x12 on M5. The unscaled version (x1) is run beside it so the
   difference is visible rather than assumed. An intermediate x12 / x3 is run
   too, because "the same number of minutes" and "the same number of bars" are
   both defensible and neither is obviously right.

   The ATR that sets the GEOMETRY is deliberately NOT scaled: it stays ATR(14)
   of the traded timeframe, because that is what makes an M1 trade an M1-sized
   bet (E-081's whole argument). So a scaled cell rests a minute-sized stop
   against an hour-sized level, which is precisely the "small stop, big level"
   trade Veer described in E-076.

3. A STREAMING STATE MACHINE. `smc.fvgs` stores a per-bar deep copy of every
   live gap; at 157,051 bars with a scaled life that is millions of dicts. The
   state here is maintained in one forward pass and candidates are emitted as
   they occur, which is also structurally incapable of the E-110 shallow-copy
   leak. The live books are capped at the 64 most recent objects: the 1h chart
   carries 29 live gaps on average and 46 at most, so the cap never binds at 1h
   (verified) and it stops a scaled M1 book growing to thousands of gaps that
   no one would ever watch.

4. THE CONTROL IS MATCHED ON FILL CONVENTION (E-110's rule, which is why six
   earlier attacks all failed). Same number of candidates, at random bars, with
   a random side, resting at a distance drawn from the STRATEGY'S OWN empirical
   distance-from-close distribution, the same wait window, the same stop, the
   same exit, and the same one-position-at-a-time arbitration. >= 12 seeds, and
   the comparison is against the standard error of the control MEAN.

Ties lose. Costs both ends. One vote per trade, never per bar.

Run:  python3 JARVIS/research/liq_m1.py           (full study)
      python3 JARVIS/research/liq_m1.py parity    (parity check only)
"""
from __future__ import annotations
import os, sys, math, json, random, statistics, datetime
from collections import deque
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
from engine import Series

GBP_PT = 0.787           # E-081: 0.01 lots XAUUSD, and it cannot be smaller
BOOK_CAP = 64            # see docstring point 3
FRAC = -0.25             # E-077: the limit rests 0.25 ATR past the zone's far edge
MAR_DIV = 6.9            # zone half-width = ATR / 6.9 (unchanged: ATR-relative)
DISP_MULT = 1.0          # displacement body >= 1.0 ATR (unchanged: ATR-relative)
FVG_MIN_ATR = 0.10       # gap >= 0.10 ATR (unchanged: ATR-relative)


# ----------------------------------------------------------------- data
def load_with_spread(tf):
    rows = json.load(open(f"/home/user/signals/data/GOLD_{tf}.json"))
    rows.sort(key=lambda r: r[0])
    s = Series([r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows],
               [r[3] for r in rows], [r[4] for r in rows])
    return s, [r[5] for r in rows]


# ------------------------------------------------------------- structure
def _sliding_extreme(vals, w, want_max):
    """m[i] = max/min of vals[i-w+1 .. i]. Monotonic deque, O(n)."""
    out = [None] * len(vals)
    dq = deque()
    for i, v in enumerate(vals):
        if want_max:
            while dq and vals[dq[-1]] <= v: dq.pop()
        else:
            while dq and vals[dq[-1]] >= v: dq.pop()
        dq.append(i)
        while dq[0] <= i - w: dq.popleft()
        if i >= w - 1: out[i] = vals[dq[0]]
    return out


def fast_pivots(s: Series, n: int):
    """Identical semantics to liquidity.pivots (h[i] >= every neighbour within
    n bars), computed in O(len) so a 420-bar pivot is affordable. hi[i] is the
    value AT the pivot bar; every consumer must wait n bars to use it."""
    w = 2 * n + 1
    mx = _sliding_extreme(s.h, w, True)
    mn = _sliding_extreme(s.l, w, False)
    hi = [None] * len(s); lo = [None] * len(s)
    for i in range(n, len(s) - n):
        if mx[i + n] is not None and s.h[i] >= mx[i + n]: hi[i] = s.h[i]
        if mn[i + n] is not None and s.l[i] <= mn[i + n]: lo[i] = s.l[i]
    return hi, lo


def entry_level(z, frac, a):
    """Where the resting order sits (toptick.entry_level, unchanged)."""
    if z["dir"] == 1:
        if frac < 0: return z["top"] - frac * a
        return z["bot"] + frac * (z["top"] - z["bot"])
    if frac < 0: return z["bot"] + frac * a
    return z["top"] - frac * (z["top"] - z["bot"])


# ------------------------------------------------------------ candidates
class Cfg:
    """Every parameter that has a TIME dimension, and its 1h-native value."""
    def __init__(self, mult):
        self.mult = mult
        self.pv_len    = max(2, int(round(7   * mult)))
        self.zone_life = int(round(600 * mult))
        self.arm_life  = int(round(60  * mult))
        self.fvg_life  = int(round(200 * mult))
        self.ob_life   = int(round(200 * mult))
        self.ob_look   = max(3, int(round(8   * mult)))
        self.wait      = max(2, int(round(20  * mult)))
        self.max_bars  = int(round(200 * mult))
        self.warmup    = max(250, self.pv_len * 3)

    def __repr__(self):
        return (f"x{self.mult:g} pivot {self.pv_len} zone_life {self.zone_life} "
                f"arm {self.arm_life} gap_life {self.fvg_life} wait {self.wait} "
                f"hold {self.max_bars}")


def candidates(s: Series, A, cfg: Cfg, use=("toptick", "fvg", "ob")):
    """One forward pass. Emits (bar, side, limit_level, atr, source) exactly as
    smc_combine.all_signals does, but without storing per-bar snapshots."""
    hi, lo = fast_pivots(s, cfg.pv_len)
    zones, recentH, recentL = [], [], []
    gaps, obs = [], []
    out_tt, out_fv, out_ob = [], [], []
    used = set()
    n = len(s)
    for i in range(n):
        a = A[i]
        if a is None or a <= 0:
            continue
        mar = a / MAR_DIV

        # ---- zones (toptick.zone_stream, streamed) -----------------------
        j = i - cfg.pv_len
        if j >= 0:
            for (arr, d, store) in ((hi, 1, recentH), (lo, -1, recentL)):
                if arr[j] is None:
                    continue
                store.append(arr[j]); del store[:-50]
                grp = [p for p in store if abs(p - arr[j]) <= mar]
                c0 = (min(grp) + max(grp)) / 2.0
                if not any(z["dir"] == d and not z["dead"] and abs(z["px"] - c0) <= mar
                           for z in zones):
                    zones.append({"px": c0, "top": c0 + mar, "bot": c0 - mar,
                                  "born": i, "dir": d, "dead": False})
        zones = [z for z in zones if i - z["born"] <= cfg.zone_life and not z["dead"]]
        for z in zones:
            if (z["dir"] == 1 and s.c[i] > z["top"]) or \
               (z["dir"] == -1 and s.c[i] < z["bot"]):
                z["dead"] = True
        zones = [z for z in zones if not z["dead"]][-BOOK_CAP:]

        # ---- fair value gaps (smc.fvgs, streamed) ------------------------
        keep = []
        for g in gaps:
            if i - g["born"] > cfg.fvg_life:
                continue
            if not g["inverted"]:
                through = (s.c[i] < g["bot"]) if g["dir"] == 1 else (s.c[i] > g["top"])
                if through:
                    g["inverted"] = True; g["inv_bar"] = i
            keep.append(g)
        gaps = keep
        if i >= 2:
            if s.h[i-2] < s.l[i] and (s.l[i] - s.h[i-2]) >= FVG_MIN_ATR * a:
                gaps.append({"dir": 1, "bot": s.h[i-2], "top": s.l[i],
                             "born": i, "inverted": False, "inv_bar": -1})
            if s.l[i-2] > s.h[i] and (s.l[i-2] - s.h[i]) >= FVG_MIN_ATR * a:
                gaps.append({"dir": -1, "bot": s.h[i], "top": s.l[i-2],
                             "born": i, "inverted": False, "inv_bar": -1})
        gaps = gaps[-BOOK_CAP:]

        # ---- order blocks (smc.order_blocks, streamed) -------------------
        obs = [b for b in obs if i - b["born"] <= cfg.ob_life and not b["dead"]]
        for b in obs:
            if (b["dir"] == 1 and s.c[i] < b["bot"]) or \
               (b["dir"] == -1 and s.c[i] > b["top"]):
                b["dead"] = True
        body = s.c[i] - s.o[i]
        if abs(body) >= DISP_MULT * a:
            d = 1 if body > 0 else -1
            for k in range(i - 1, max(i - cfg.ob_look, 0), -1):
                opp = (s.c[k] < s.o[k]) if d > 0 else (s.c[k] > s.o[k])
                if opp:
                    obs.append({"dir": d, "top": max(s.o[k], s.c[k]),
                                "bot": min(s.o[k], s.c[k]), "born": i,
                                "dead": False})
                    break
        obs = [b for b in obs if not b["dead"]][-BOOK_CAP:]

        if i < cfg.warmup or i >= n - 2:
            continue

        # ---- emissions ---------------------------------------------------
        if "toptick" in use:
            for z in zones:
                key = (z["born"], round(z["px"], 6), z["dir"])
                if key in used or i - z["born"] > cfg.arm_life:
                    continue
                lvl = entry_level(z, FRAC, a)
                side = -1 if z["dir"] == 1 else 1
                if (side == -1 and s.c[i] >= lvl) or (side == 1 and s.c[i] <= lvl):
                    continue
                k = i + 1
                if not ((s.h[k] >= lvl) if side == -1 else (s.l[k] <= lvl)):
                    continue                    # not reached next bar: still resting
                used.add(key)
                out_tt.append((i, side, lvl, a, "toptick", 1))
                break
        if "fvg" in use:
            for g in gaps:
                if g["inverted"]:
                    continue
                mid = (g["top"] + g["bot"]) / 2.0
                if g["dir"] == 1 and s.c[i] > mid:
                    out_fv.append((i, 1, mid, a, "fvg", cfg.wait)); break
                if g["dir"] == -1 and s.c[i] < mid:
                    out_fv.append((i, -1, mid, a, "fvg", cfg.wait)); break
        if "ob" in use:
            for b in obs:
                mid = (b["top"] + b["bot"]) / 2.0
                if b["dir"] == 1 and s.c[i] > mid:
                    out_ob.append((i, 1, mid, a, "ob", cfg.wait)); break
                if b["dir"] == -1 and s.c[i] < mid:
                    out_ob.append((i, -1, mid, a, "ob", cfg.wait)); break

    cands = out_tt + out_fv + out_ob
    cands.sort(key=lambda x: x[0])              # stable: toptick, fvg, ob
    return cands


def fill_bars(s: Series, cands):
    """First bar in (i, i+wait] whose ADVERSE extreme reaches the limit, or
    None. Depends only on the level and the wait window, so it is computed once
    and reused across every stop / exit / cost cell."""
    n = len(s)
    out = []
    for (i, side, lvl, a, src, wait) in cands:
        j = None
        for k in range(i + 1, min(i + 1 + wait, n)):
            if (side == 1 and s.l[k] <= lvl) or (side == -1 and s.h[k] >= lvl):
                j = k; break
        out.append(j)
    return out


# ----------------------------------------------------------------- exits
def resolve(s, SP, slip, j, side, entry, stop, mode, a, tgt_r=2.0, trail=3.0,
            max_bars=200, arm=1.0):
    """liq_exit.resolve, with the cost taken from each bar's OWN spread.

    E-110's correction is kept verbatim: bar `j` is the bar the limit was
    TOUCHED on, evidenced by its ADVERSE extreme, so its favourable extreme is
    not ours to book unless the bar OPENED beyond the entry - the one case
    where the fill provably happened at the open."""
    risk = (entry - stop) * side
    tgt = entry + side * tgt_r * risk
    peak, mfe = entry, 0.0
    post = ((s.o[j] <= entry) if side > 0 else (s.o[j] >= entry))
    for k in range(j, min(j + max_bars, len(s))):
        fav_ok = (k > j) or post
        hs = (s.l[k] <= stop) if side == 1 else (s.h[k] >= stop)
        if hs:
            px, why = stop, "stop"; break                    # ties lose
        if mode == "fixed2R":
            if fav_ok and ((s.h[k] >= tgt) if side == 1 else (s.l[k] <= tgt)):
                px, why = tgt, "target"; break
        else:
            if not fav_ok:
                continue
            newpeak = max(peak, s.h[k]) if side > 0 else min(peak, s.l[k])
            newmfe = max(mfe, side * (newpeak - entry) / risk)
            cand = stop
            t = newpeak - side * trail * a
            cand = max(cand, t) if side > 0 else min(cand, t)
            if mode == "trail_gb" and newmfe >= arm:
                allow = 0.20 if newmfe < 1.5 else (0.16 if newmfe < 3.0 else 0.12)
                gb = entry + side * side * (newpeak - entry) * (1.0 - allow)
                cand = max(cand, gb) if side > 0 else min(cand, gb)
            worst = s.l[k] if side > 0 else s.h[k]
            if cand != stop and ((side > 0 and worst <= cand)
                                 or (side < 0 and worst >= cand)):
                px, why = cand, "giveback"; break
            peak, mfe, stop = newpeak, newmfe, cand
    else:
        k = min(j + max_bars, len(s)) - 1
        px, why = s.c[k], "time"
    fill = px - side * (SP[k] / 2.0 + slip)
    pts = (fill - entry) * side
    return {"r": pts / risk, "pts": pts, "out": k, "why": why, "in": j,
            "side": side, "why_": why}


def simulate(s, SP, slip, cands, fills, stop_atr, mode, max_bars, **kw):
    """One account, one position. First candidate whose limit is touched while
    flat becomes the trade; everything overlapping it is simply not taken."""
    out, busy = [], -1
    for idx, (i, side, lvl, a, src, wait) in enumerate(cands):
        if i <= busy:
            continue
        j = fills[idx]
        if j is None or j <= busy:
            continue
        entry = lvl + side * (SP[j] / 2.0 + slip)
        stop = entry - side * stop_atr * a
        if (entry - stop) * side <= 0:
            continue
        t = resolve(s, SP, slip, j, side, entry, stop, mode, a,
                    max_bars=max_bars, **kw)
        t["src"] = src
        out.append(t)
        busy = t["out"]
    return out


# --------------------------------------------------------------- control
def control_cands(s, A, cands, seed, warmup):
    """E-110's rule, tightened: same NUMBER of candidates, random bar, random
    side, and a distance-from-close drawn from the STRATEGY'S OWN empirical
    distribution (in ATR), with the same wait window. Matched on fill
    convention, geometry, frequency and resting distance."""
    rng = random.Random(seed)
    dists = [abs(lvl - s.c[i]) / a for (i, side, lvl, a, src, w) in cands if a > 0]
    waits = [w for (_, _, _, _, _, w) in cands]
    n = len(s)
    idx = sorted(rng.randrange(warmup, n - 3) for _ in range(len(cands)))
    out = []
    for k, i in enumerate(idx):
        a = A[i]
        if a is None or a <= 0:
            continue
        side = 1 if rng.random() < 0.5 else -1
        d = dists[rng.randrange(len(dists))] * a
        lvl = s.c[i] - side * d                 # a LIMIT: it rests on the far side
        out.append((i, side, lvl, a, "ctl", waits[rng.randrange(len(waits))]))
    return out


# ------------------------------------------------------------ statistics
def stat(tr):
    if not tr:
        return None
    rs = [t["r"] for t in tr]
    n = len(rs); e = sum(rs) / n
    sd = (sum((r - e) ** 2 for r in rs) / n) ** 0.5 if n > 1 else 0.0
    se = sd / math.sqrt(n) if sd > 0 else 0.0
    gp = sum(r for r in rs if r > 0); gl = -sum(r for r in rs if r < 0)
    pts = sum(t["pts"] for t in tr)
    return {"n": n, "exp": e, "se": se, "t": (e / se if se else 0.0),
            "win": 100.0 * sum(1 for r in rs if r > 0) / n,
            "pf": (gp / gl if gl > 0 else 0.0), "pts": pts, "gbp": pts * GBP_PT}


def regime_spread(SP, A, target_ratio):
    """Rescale the whole per-bar spread series so its MEDIAN spread/ATR equals
    `target_ratio`, preserving the per-bar shape. 2018's own ratio is ~0.93."""
    va = sorted(x for x in A if x and x > 0)
    med_a = va[len(va) // 2]
    med_s = statistics.median(SP)
    cur = med_s / med_a
    f = target_ratio / cur
    return [x * f for x in SP], f, cur


# --------------------------------------------------------------- parity
def parity_check():
    """My per-bar-spread resolve must reproduce liq_exit.resolve EXACTLY when
    the spread series is constant. If it does not, nothing below is comparable
    to E-110 and the run stops."""
    import study, liq_exit
    from toptick import zone_stream
    from smc import smc_state
    from smc_combine import all_signals
    s = engine.load("GOLD", "1h")
    c = study.COSTS["GOLD"]
    A = engine.atr(s, 14)
    pb, _ = zone_stream(s)
    st = smc_state(s, A)
    ref_c = all_signals(s, c, pb, A, st, {"toptick", "fvg", "ob"})
    mine = candidates(s, A, Cfg(1.0))
    same_c = (len(ref_c) == len(mine) and
              all(abs(a[2] - b[2]) < 1e-9 and a[0] == b[0] and a[1] == b[1]
                  for a, b in zip(ref_c, mine)))
    SP = [c.spread] * len(s)
    fl = fill_bars(s, mine)
    for mode in ("fixed2R", "trail_gb"):
        ref = liq_exit.run(s, c, ref_c, mode)
        got = simulate(s, SP, c.slippage, mine, fl, 0.60, mode, 200)
        ok = (len(ref) == len(got) and
              all(abs(x["r"] - y["r"]) < 1e-9 for x, y in zip(ref, got)))
        print(f"  PARITY {mode:<10} candidates match {same_c}   "
              f"ref n={len(ref)} mine n={len(got)}  identical R: {ok}")
        if not (same_c and ok):
            return False
    return True


# ------------------------------------------------------------------ main
REGIMES = [("2018 as measured", None), ("today ECN  0.11", 0.11),
           ("today mid  0.17", 0.17), ("today std  0.25", 0.25),
           ("zero cost", 0.0)]


def hour_of(ts):
    return datetime.datetime.utcfromtimestamp(ts).hour


def main():
    print("=" * 108)
    print("  E-115 — THE LIQUIDITY STACK AT M1 AND M5, ON REAL TICK-DERIVED BARS")
    print("  E-080 signal set {toptick, FVG, order block}; E-110's corrected fill")
    print("  convention; cost from each bar's OWN measured spread. Ties lose.")
    print("=" * 108)
    print("\n  PARITY AGAINST THE 1h CODE THIS REPLACES")
    if not parity_check():
        print("  PARITY FAILED — stopping. Nothing below would be comparable.")
        return
    print("  Parity holds: the streamed generator and the per-bar-spread exit")
    print("  reproduce smc_combine + liq_exit exactly on GOLD 1h.")

    for tf, mults in (("M5_2018", (1.0, 3.0, 12.0)), ("M1_2018", (1.0, 12.0, 60.0))):
        s, SP0 = load_with_spread(tf)
        A = engine.atr(s, 14)
        va = sorted(x for x in A if x and x > 0)
        med_a = va[len(va) // 2]
        print("\n" + "=" * 108)
        print(f"  ### GOLD {tf}   {len(s):,} bars   "
              f"{datetime.datetime.utcfromtimestamp(s.ts[0]).date()} -> "
              f"{datetime.datetime.utcfromtimestamp(s.ts[-1]).date()}")
        print(f"  median ATR(14) {med_a:.3f} pts   median spread "
              f"{statistics.median(SP0):.3f} pts   spread/ATR "
              f"{statistics.median(SP0)/med_a:.2f}")
        print("=" * 108)

        SP, f, cur = regime_spread(SP0, A, 0.11)
        store = {}
        for mult in mults:
            cfg = Cfg(mult)
            cd = candidates(s, A, cfg)
            fl = fill_bars(s, cd)
            nf = sum(1 for x in fl if x is not None)
            print(f"\n  -- scaling {cfg}")
            print(f"     candidates {len(cd):,}  ({nf:,} would fill)   "
                  f"sources: " + ", ".join(
                      f"{k} {sum(1 for c_ in cd if c_[4]==k):,}"
                      for k in ("toptick", "fvg", "ob")))
            store[mult] = (cfg, cd, fl)
            print(f"     {'stop':>7}{'exit':>10}{'n':>7}{'win%':>7}{'expect':>10}"
                  f"{'PF':>7}{'t':>8}{'points':>10}{'GBP/0.01':>10}"
                  f"  (cost regime: today ECN 0.11)")
            for stop_atr in (0.60, 1.50, 3.00):
                for mode in ("fixed2R", "trail_gb"):
                    tr = simulate(s, SP, 0.0, cd, fl, stop_atr, mode, cfg.max_bars)
                    a_ = stat(tr)
                    if not a_ or a_["n"] < 30:
                        print(f"     {stop_atr:>6.2f}A{mode:>10}{len(tr):>7}"
                              f"   fewer than 30 trades — UNPROVEN by rule")
                        continue
                    print(f"     {stop_atr:>6.2f}A{mode:>10}{a_['n']:>7}"
                          f"{a_['win']:>6.1f}%{a_['exp']:>+9.4f}R{a_['pf']:>7.2f}"
                          f"{a_['t']:>+8.2f}{a_['pts']:>+10.1f}{a_['gbp']:>+10.0f}")
        yield_store(s, SP0, A, store, tf, med_a)


def yield_store(s, SP0, A, store, tf, med_a):
    """Controls, cost regimes, walk-forward and session split for every cell."""
    print("\n  " + "-" * 104)
    print("  THE TEST THAT MATTERS: vs a fill-convention-matched control, "
          f"{CTL_SEEDS} seeds, se of the control MEAN")
    print("  " + "-" * 104)
    print(f"  {'scaling':>9}{'stop':>7}{'exit':>10}{'n':>7}{'strategy':>11}"
          f"{'control':>11}{'ctl se':>9}{'edge':>10}{'ctl se':>9}{'points':>10}")
    best = None
    for mult, (cfg, cd, fl) in store.items():
        ctl_sets = []
        for sd in range(CTL_SEEDS):
            cc = control_cands(s, A, cd, 500 + sd, cfg.warmup)
            ctl_sets.append((cc, fill_bars(s, cc)))
        SP, _, _ = regime_spread(SP0, A, 0.11)
        for stop_atr in (0.60, 1.50, 3.00):
            for mode in ("fixed2R", "trail_gb"):
                tr = simulate(s, SP, 0.0, cd, fl, stop_atr, mode, cfg.max_bars)
                a_ = stat(tr)
                if not a_ or a_["n"] < 30:
                    continue
                ms = []
                for cc, cfl in ctl_sets:
                    ct = simulate(s, SP, 0.0, cc, cfl, stop_atr, mode, cfg.max_bars)
                    cs = stat(ct)
                    if cs and cs["n"] >= 10:
                        ms.append(cs["exp"])
                if len(ms) < 3:
                    continue
                cm = sum(ms) / len(ms)
                csd = (sum((x - cm) ** 2 for x in ms) / (len(ms) - 1)) ** 0.5
                cse = csd / math.sqrt(len(ms))
                z = (a_["exp"] - cm) / cse if cse > 0 else 0.0
                print(f"  {'x%g'%mult:>9}{stop_atr:>6.2f}A{mode:>10}{a_['n']:>7}"
                      f"{a_['exp']:>+10.4f}R{cm:>+10.4f}R{cse:>9.4f}"
                      f"{a_['exp']-cm:>+9.4f}R{z:>+8.1f}se{a_['pts']:>+10.1f}")
                if best is None or z > best[0]:
                    best = (z, mult, stop_atr, mode, a_, cm, cse)
    if best is None:
        print("  no cell reached 30 trades.")
        return
    z, mult, stop_atr, mode, a_, cm, cse = best
    cfg, cd, fl = store[mult]
    print(f"\n  BEST CELL BY CONTROL SE: scaling x{mult:g}, stop {stop_atr:.2f} ATR, "
          f"exit {mode}  ->  {z:+.1f} control se")
    deep_dive(s, SP0, A, cfg, cd, fl, stop_atr, mode, tf)


def deep_dive(s, SP0, A, cfg, cd, fl, stop_atr, mode, tf):
    # ---- cost regimes
    print(f"\n  COST SENSITIVITY (per-bar spread rescaled to each regime's "
          f"median spread/ATR)")
    print(f"  {'regime':<20}{'spread':>9}{'cost/stop':>11}{'n':>7}{'expect':>10}"
          f"{'t':>8}{'points':>10}{'GBP/0.01':>10}")
    va = sorted(x for x in A if x and x > 0); med_a = va[len(va) // 2]
    for name, ratio in REGIMES:
        if ratio is None:
            SP = list(SP0)
        else:
            SP, _, _ = regime_spread(SP0, A, ratio)
        tr = simulate(s, SP, 0.0, cd, fl, stop_atr, mode, cfg.max_bars)
        a_ = stat(tr)
        if not a_:
            continue
        ms = statistics.median(SP)
        print(f"  {name:<20}{ms:>9.3f}{ms/(stop_atr*med_a):>11.2f}{a_['n']:>7}"
              f"{a_['exp']:>+9.4f}R{a_['t']:>+8.2f}{a_['pts']:>+10.1f}"
              f"{a_['gbp']:>+10.0f}")

    # ---- walk-forward and sessions at the ECN regime
    SP, _, _ = regime_spread(SP0, A, 0.11)
    tr = simulate(s, SP, 0.0, cd, fl, stop_atr, mode, cfg.max_bars)
    nb = 6
    print(f"\n  WALK-FORWARD, {nb} equal blocks of the six months (ECN regime)")
    ok = 0
    for b in range(nb):
        sub = [t for t in tr if b * len(s) // nb <= t["in"] < (b + 1) * len(s) // nb]
        a_ = stat(sub)
        if not a_:
            print(f"    block {b+1}: no trades"); continue
        d0 = datetime.datetime.utcfromtimestamp(s.ts[b * len(s) // nb]).date()
        ok += 1 if a_["exp"] > 0 else 0
        print(f"    block {b+1} from {d0}  n={a_['n']:>5}  {a_['exp']:>+8.4f}R"
              f"  {a_['pts']:>+9.1f} pts")
    print(f"    blocks positive: {ok}/{nb}")

    print(f"\n  BY SESSION (UTC hour of the FILL bar)")
    buckets = [("Asia 22-06", range(22, 24)), ("Asia 22-06", range(0, 7)),
               ("London 07-11", range(7, 12)), ("NY overlap 12-16", range(12, 17)),
               ("NY late 17-21", range(17, 22))]
    agg = {}
    for name, rng_ in buckets:
        agg.setdefault(name, set()).update(rng_)
    for name, hrs in agg.items():
        sub = [t for t in tr if hour_of(s.ts[t["in"]]) in hrs]
        a_ = stat(sub)
        if not a_ or a_["n"] < 30:
            print(f"    {name:<18} n={len(sub):>5}   fewer than 30 — UNPROVEN")
            continue
        print(f"    {name:<18} n={a_['n']:>5}  {a_['exp']:>+8.4f}R  t={a_['t']:>+6.2f}"
              f"  {a_['pts']:>+9.1f} pts  {a_['gbp']:>+8.0f} GBP")

    print(f"\n  LONG / SHORT")
    for nm, sd_ in (("long", 1), ("short", -1)):
        sub = [t for t in tr if t["side"] == sd_]
        a_ = stat(sub)
        if not a_ or a_["n"] < 30:
            print(f"    {nm:<6} n={len(sub)} — fewer than 30"); continue
        print(f"    {nm:<6} n={a_['n']:>5}  {a_['exp']:>+8.4f}R  t={a_['t']:>+6.2f}"
              f"  {a_['pts']:>+9.1f} pts")

    print(f"\n  BY SOURCE")
    for src in ("toptick", "fvg", "ob"):
        sub = [t for t in tr if t["src"] == src]
        a_ = stat(sub)
        if not a_:
            continue
        print(f"    {src:<8} n={a_['n']:>5}  {a_['exp']:>+8.4f}R  "
              f"{a_['pts']:>+9.1f} pts")


CTL_SEEDS = 12

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "parity":
        parity_check()
    else:
        main()

"""
E-100 — THE FOUR LEVEL CONCEPTS VEER NAMED, tested as standalone triggers.

Veer: "we need bsl ssl liquidity sweeps rejection zones support resistance play
ping pong". None of these four are in the shipped stack. Each is a falsifiable
claim about the future, so each is built here and measured.

  (a) BSL / SSL POOL     two or more confirmed pivot extremes within a small
                         ATR tolerance are a liquidity POOL. Enter on the SWEEP
                         of the pool: a bar whose wick goes through it and whose
                         CLOSE comes back inside. Buyside pool swept -> SELL.
  (b) REJECTION ZONE     a bar whose wick is >= 60% of its range, and whose wick
                         reached a prior level. Enter on the close back inside.
  (c) S/R FLIP           a level that was resistance, was broken by a CLOSE, and
                         is then re-approached from above and held. Enter long.
                         Mirror for support broken downward.
  (d) PING PONG          a range defined from CLOSED bars only, with at least two
                         touches of each edge. Enter at each edge targeting the
                         other.

GEOMETRY, identical for all four and identical to E-077/E-079 so the numbers are
comparable: entry at the NEXT bar's open, stop 0.60 ATR, ONE position at a time.
Two exit rules are reported: NO FIXED TARGET (time exit, the brief's rule) and
the 2R target the shipped stack uses. Ping-pong additionally reports its own
rule, the opposite edge.

Ties lose. Costs both ends (study.COSTS["GOLD"], spread 0.46 measured off Veer's
terminal). One vote per TRADE. Every concept is scored against a random-entry
control of 20 seeds with matched geometry, and the separation is measured
against the STANDARD ERROR OF THE CONTROL MEAN (E-064), not the per-seed sd.

GOLD 15m and 1h only. There is no M1/M5 data in this repository.

Run:  python3 JARVIS/research/level_concepts.py
"""
from __future__ import annotations
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from engine import Series
from liquidity import pivots, stat

COMBOS = [("GOLD", "15m"), ("GOLD", "1h")]
STOP_ATR = 0.60
MAX_BARS = 200
WARMUP = 250
SEEDS = 20


# ------------------------------------------------------------------ plumbing
def resolve(s, costs, j, side, entry, stop, tgtpx=None, max_bars=MAX_BARS):
    """Stop checked BEFORE target on every bar: ties lose. tgtpx None = no
    fixed target, exit on time at the close of the last bar of the window."""
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot
    risk = (entry - stop) * side
    px = why = None
    for k in range(j, min(j + max_bars, len(s))):
        if (s.l[k] <= stop) if side == 1 else (s.h[k] >= stop):
            px, why = stop, "stop"; break
        if tgtpx is not None and ((s.h[k] >= tgtpx) if side == 1 else (s.l[k] <= tgtpx)):
            px, why = tgtpx, "target"; break
    else:
        k = min(j + max_bars, len(s)) - 1
        px, why = s.c[k], "time"
    if px is None:
        k = min(j + max_bars, len(s)) - 1
        px, why = s.c[k], "time"
    fill = px - side * (half + costs.slippage)
    return {"r": ((fill - entry) * side - comm_px) / risk, "why": why,
            "pts": (fill - entry) * side - comm_px, "exit_bar": k,
            "in_bar": j, "side": side, "risk_pts": risk}


def take(s, costs, sigs, A, tgt_mode, max_bars=MAX_BARS):
    """sigs: list of (signal_bar, side, target_price_or_None).
    Entry is the NEXT bar's open. One position at a time; a signal arriving
    while a trade is open is not taken, which is what actually happens."""
    half = costs.spread / 2.0
    out, busy = [], -1
    for (i, side, tgt_level) in sigs:
        if i <= busy or i + 1 >= len(s):
            continue
        a = A[i]
        if not a or a <= 0:
            continue
        entry = s.o[i + 1] + side * (half + costs.slippage)
        stop = entry - side * STOP_ATR * a
        risk = (entry - stop) * side
        if risk <= 0:
            continue
        if tgt_mode == "none":
            tp = None
        elif tgt_mode == "2R":
            tp = entry + side * 2.0 * risk
        else:                                    # "level" - the opposite edge
            if tgt_level is None:
                continue
            tp = tgt_level
            if (tp - entry) * side <= 0:
                continue
        t = resolve(s, costs, i + 1, side, entry, stop, tp, max_bars)
        t["sig_bar"] = i
        t["tgt_atr"] = (abs(tp - entry) / a) if tp is not None else None
        out.append(t)
        busy = t["exit_bar"]
    return out


def control(s, costs, A, n_want, seed, tgt_mode, tgt_atr_pool=None,
            max_bars=MAX_BARS):
    """Random bar, random side, SAME stop and SAME exit rule. For the 'level'
    exit rule the target distance is drawn from the concept's own distribution,
    so the control is matched on payoff shape as well as on risk."""
    rng = random.Random(seed)
    idx = [i for i in range(WARMUP, len(s) - 2) if A[i] and A[i] > 0]
    sigs = []
    for _ in range(n_want * 6):
        i = rng.choice(idx)
        side = 1 if rng.random() < 0.5 else -1
        tl = None
        if tgt_mode == "level" and tgt_atr_pool:
            tl = s.o[i + 1] + side * rng.choice(tgt_atr_pool) * A[i]
        sigs.append((i, side, tl))
    sigs.sort(key=lambda x: x[0])
    tr = take(s, costs, sigs, A, tgt_mode, max_bars)
    return tr


def attack(name, tr, s, costs, A, tgt_mode, tgt_atr_pool=None,
           max_bars=MAX_BARS):
    a = stat(tr)
    pts = sum(x["pts"] for x in tr)
    nb = 6
    bl = [tr[i * len(tr) // nb:(i + 1) * len(tr) // nb] for i in range(nb)]
    bs = [stat(b) for b in bl if len(b) >= 8]
    wf = sum(1 for x in bs if x["exp"] > 0)
    ce = []
    for sd in range(501, 501 + SEEDS):
        c = control(s, costs, A, max(len(tr), 40), sd, tgt_mode, tgt_atr_pool,
                    max_bars)
        if c:
            ce.append(stat(c)["exp"])
    cm = sum(ce) / len(ce)
    csd = (sum((x - cm) ** 2 for x in ce) / len(ce)) ** 0.5
    se_c = csd / math.sqrt(len(ce))
    se_o = abs(a["exp"] / a["t"]) if a["t"] else 0.0
    z = (a["exp"] - cm) / math.sqrt(se_o ** 2 + se_c ** 2) if (se_o or se_c) else 0.0
    lg = [x for x in tr if x["side"] == 1]
    sh = [x for x in tr if x["side"] == -1]
    return {"name": name, "n": a["n"], "win": a["win"], "exp": a["exp"],
            "pf": a["pf"], "t": a["t"], "pts": pts, "wf": wf, "wfn": len(bs),
            "ctrl": cm, "z": z, "blocks": [x["exp"] for x in bs],
            "long": stat(lg), "short": stat(sh)}


def verdict(r):
    if r["n"] < 30:
        return "UNPROVEN (fewer than 30 trades)"
    if r["exp"] <= 0:
        return "REJECTED (negative expectancy after costs)"
    if r["t"] < 2.0:
        return "UNPROVEN (t below 2)"
    if r["wfn"] and r["wf"] < r["wfn"] * 0.6:
        return "REJECTED (fails more than 40% of walk-forward folds)"
    if r["z"] < 2.0:
        return "UNPROVEN (not 2 sd clear of the random control)"
    return "PROMISING (survived; not proof of future profit)"


# ------------------------------------------------------------ the four concepts
def known_pivots(s, A, pv=5, life=400):
    hi, lo = pivots(s, pv)
    out = [[] for _ in range(len(s))]
    liveH, liveL = [], []
    for i in range(len(s)):
        j = i - pv
        if j >= 0:
            if hi[j] is not None: liveH.append((hi[j], j))
            if lo[j] is not None: liveL.append((lo[j], j))
        liveH = [x for x in liveH if i - x[1] <= life]
        liveL = [x for x in liveL if i - x[1] <= life]
        out[i] = [(p, 1, b) for p, b in liveH] + [(p, -1, b) for p, b in liveL]
    return out


def sig_bsl_ssl(s, A, kp, tol_atr=0.10, min_n=2):
    """(a) Sweep of an equal-highs / equal-lows POOL. A pool is consumed once."""
    sigs, used = [], set()
    for i in range(WARMUP, len(s) - 2):
        a = A[i]
        if not a or a <= 0:
            continue
        tol = tol_atr * a
        for d in (1, -1):
            pts = [p for (p, kd, b) in kp[i] if kd == d and b < i]
            if not pts:
                continue
            for p in pts:
                grp = [q for q in pts if abs(q - p) <= tol]
                if len(grp) < min_n:
                    continue
                edge = max(grp) if d == 1 else min(grp)
                key = (d, round(edge, 2))
                if key in used:
                    continue
                if d == 1 and s.h[i] > edge and s.c[i] < edge:
                    used.add(key); sigs.append((i, -1, None)); break
                if d == -1 and s.l[i] < edge and s.c[i] > edge:
                    used.add(key); sigs.append((i, 1, None)); break
    sigs.sort(key=lambda x: x[0])
    return sigs


def sig_rejection(s, A, kp, wick_share=0.60):
    """(b) A large wick INTO a prior level, closing back inside."""
    sigs = []
    for i in range(WARMUP, len(s) - 2):
        a = A[i]
        if not a or a <= 0:
            continue
        rng_ = s.h[i] - s.l[i]
        if rng_ <= 0:
            continue
        body_hi, body_lo = max(s.o[i], s.c[i]), min(s.o[i], s.c[i])
        up_w, dn_w = s.h[i] - body_hi, body_lo - s.l[i]
        if up_w / rng_ >= wick_share:
            if any(kd == 1 and b < i and body_hi <= p <= s.h[i]
                   for (p, kd, b) in kp[i]):
                sigs.append((i, -1, None)); continue
        if dn_w / rng_ >= wick_share:
            if any(kd == -1 and b < i and s.l[i] <= p <= body_lo
                   for (p, kd, b) in kp[i]):
                sigs.append((i, 1, None))
    return sigs


def sig_flip(s, A, kp, tol_atr=0.15, since=100):
    """(c) Resistance broken by a CLOSE, then re-approached from above and held."""
    sigs = []
    broken = []                    # (price, dir_of_original_level, break_bar)
    seen = set()
    for i in range(WARMUP, len(s) - 2):
        a = A[i]
        if not a or a <= 0:
            continue
        for (p, kd, b) in kp[i]:
            if b >= i:
                continue
            key = (kd, round(p, 2))
            if key in seen:
                continue
            if kd == 1 and s.c[i] > p:
                seen.add(key); broken.append((p, 1, i))
            elif kd == -1 and s.c[i] < p:
                seen.add(key); broken.append((p, -1, i))
        broken = [x for x in broken if i - x[2] <= since]
        tol = tol_atr * a
        for (p, kd, bb) in broken:
            if bb >= i:
                continue
            if kd == 1 and s.l[i] <= p + tol and s.c[i] > p:
                sigs.append((i, 1, None)); break
            if kd == -1 and s.h[i] >= p - tol and s.c[i] < p:
                sigs.append((i, -1, None)); break
    return sigs


def sig_pingpong(s, A, look=40, min_w=1.5, max_w=6.0, touch_tol=0.15,
                 min_touch=2):
    """(d) A range built from CLOSED bars only: hi/lo of the last `look` bars,
    width between min_w and max_w ATR, at least `min_touch` touches of EACH
    edge. Buy the lower edge targeting the upper, and the mirror."""
    sigs = []
    for i in range(max(WARMUP, look), len(s) - 2):
        a = A[i]
        if not a or a <= 0:
            continue
        w = s.h[i - look + 1:i + 1]
        v = s.l[i - look + 1:i + 1]
        hi, lo = max(w), min(v)
        width = hi - lo
        if width <= 0 or not (min_w * a <= width <= max_w * a):
            continue
        tol = touch_tol * width
        th = sum(1 for x in w if x >= hi - tol)
        tl = sum(1 for x in v if x <= lo + tol)
        if th < min_touch or tl < min_touch:
            continue
        if s.c[i] <= lo + tol:
            sigs.append((i, 1, hi - tol))
        elif s.c[i] >= hi - tol:
            sigs.append((i, -1, lo + tol))
    return sigs


CONCEPTS = [
    ("a. BSL/SSL pool sweep", sig_bsl_ssl, True),
    ("b. rejection zone",     sig_rejection, True),
    ("c. S/R flip",           sig_flip, True),
    ("d. ping pong",          sig_pingpong, False),
]


def main():
    print("=" * 118)
    print("  E-100  THE FOUR LEVEL CONCEPTS — BSL/SSL, rejection, S/R flip, ping pong")
    print("  Standalone triggers. Entry next open, stop 0.60 ATR, one position at a")
    print("  time, ties lose, costs both ends. Control = 20 random-entry seeds with")
    print("  matched geometry; z is against the STANDARD ERROR OF THE CONTROL MEAN.")
    print("  GOLD only. No M1/M5 data exists in this repository.")
    print("=" * 118)

    store = {}
    for sym, tf in COMBOS:
        s = engine.load(sym, tf)
        c = study.COSTS[sym]
        A = engine.atr(s, 14)
        kp = known_pivots(s, A)
        print(f"\n  ### {sym} {tf}   {len(s)} bars")
        print(f"   {'concept':<26}{'exit':<9}{'n':>6}{'win%':>7}{'expect':>10}"
              f"{'PF':>7}{'t':>7}{'points':>9}{'wf':>7}{'ctrl':>9}{'z':>7}"
              f"   verdict")
        print("   " + "-" * 112)
        for cname, fn, uses_pivots in CONCEPTS:
            sigs = fn(s, A, kp) if uses_pivots else fn(s, A)
            modes = [("none", MAX_BARS), ("none", 20), ("2R", MAX_BARS)] + \
                    ([("level", MAX_BARS)] if cname.startswith("d.") else [])
            for m, mb in modes:
                tr = take(s, c, sigs, A, m, mb)
                if not tr:
                    continue
                pool = None
                if m == "level":
                    # the control's targets are drawn from the concept's OWN
                    # target-distance distribution, so payoff shape is matched
                    pool = [x["tgt_atr"] for x in tr if x["tgt_atr"]] or None
                r = attack(cname, tr, s, c, A, m, pool, mb)
                store[(sym, tf, cname, m + ("/20b" if mb == 20 else ""))] = (tr, r)
                lbl = {"none": "no tgt", "2R": "2R", "level": "opp edge"}[m]
                if mb != MAX_BARS:
                    lbl += f"/{mb}b"
                print(f"   {cname:<26}{lbl:<9}{r['n']:>6}{r['win']:>6.1f}%"
                      f"{r['exp']:>+9.3f}R{r['pf']:>7.2f}{r['t']:>+7.2f}"
                      f"{r['pts']:>+9.0f}{str(r['wf'])+'/'+str(r['wfn']):>7}"
                      f"{r['ctrl']:>+8.3f}R{r['z']:>+7.1f}   {verdict(r)}")

        print(f"\n   long / short split (the 'one direction only' check):")
        for (k, (tr, r)) in store.items():
            if k[0] != sym or k[1] != tf:
                continue
            print(f"     {k[2]:<26}{k[3]:<9} long n={r['long']['n']:<5}"
                  f"{r['long']['exp']:>+7.3f}R   short n={r['short']['n']:<5}"
                  f"{r['short']['exp']:>+7.3f}R")
        print(f"\n   walk-forward block expectancies:")
        for (k, (tr, r)) in store.items():
            if k[0] != sym or k[1] != tf:
                continue
            print(f"     {k[2]:<26}{k[3]:<9}"
                  + "  ".join(f"{x:+.2f}" for x in r["blocks"]))

    print("\n" + "=" * 118)
    print("  VARIANTS TESTED, declared: 4 concepts x 2 exit rules (+1 for ping pong)")
    print("  and 2 horizons for the no-target rule, x 2 timeframes = 26 cells.")
    print("  ONE parameter set per concept, fixed in")
    print("  advance from Veer's own description. No parameter search was run, so")
    print("  no cell here is the best of a grid.")
    print("=" * 118)
    return store




# ------------------------------------------------------------ the catch test
def catch_test(N=3, thresh=40.0, seeds=16):
    """The question that actually matters: even if a concept does not PAY,
    does it FIRE at the turning points the shipped stack missed?

    A concept that fires often catches turns by luck alone, so every catch rate
    below is printed beside a control that keeps the SAME NUMBER of signals and
    the same side mix but scatters their bars uniformly at random, 16 seeds.
    The comparison is against the standard error of the control MEAN.
    """
    import missed_moves as mm
    print("\n" + "=" * 118)
    print("  DO THE FOUR CONCEPTS CATCH THE MOVES THE STACK MISSED?")
    print(f"  A concept CATCHES a move if it fires the right way within {N} bars")
    print(f"  of the turning point. Moves >= {thresh:.0f} points. Control = same")
    print("  signal count, same side mix, bars scattered at random, 16 seeds.")
    print("=" * 118)
    for sym, tf in COMBOS:
        s = engine.load(sym, tf)
        c = study.COSTS[sym]
        A = engine.atr(s, 14)
        kp = known_pivots(s, A)
        res, _, _, _ = mm.analyse(sym, tf, N=N, threshes=(thresh,))
        d = res["levels"][thresh]
        legs, missed = d["legs"], d["missed"]
        print(f"\n  ### {sym} {tf}   {len(legs)} moves, stack caught "
              f"{len(d['caught'])} ({100*len(d['caught'])/len(legs):.1f}%), "
              f"missed {len(missed)}")
        print(f"   {'concept':<26}{'signals':>9}{'catches ALL':>13}"
              f"{'catches MISSED':>16}{'scatter ctrl':>16}{'z':>7}"
              f"{'time-shift ctrl':>17}{'z':>7}")
        print("   " + "-" * 112)
        for cname, fn, uses_pivots in CONCEPTS:
            sigs = fn(s, A, kp) if uses_pivots else fn(s, A)
            if not sigs:
                continue
            by_bar = {}
            for (i, side, _t) in sigs:
                by_bar.setdefault(i, set()).add(side)

            def rate(legset, table):
                hit = 0
                for (t0, t1, dd, mag) in legset:
                    for b in range(max(0, t0 - N), min(len(s), t0 + N + 1)):
                        if dd in table.get(b, ()):
                            hit += 1; break
                return hit

            all_hit = rate(legs, by_bar)
            miss_hit = rate(missed, by_bar)
            idx = [i for i in range(WARMUP, len(s) - 2) if A[i]]
            sides = [x[1] for x in sigs]
            lo_i, hi_i = WARMUP, len(s) - 3
            span = hi_i - lo_i

            def zscore(samples):
                m = sum(samples) / len(samples)
                sd_ = (sum((x - m) ** 2 for x in samples) / len(samples)) ** 0.5
                se_ = sd_ / math.sqrt(len(samples)) if sd_ else 1e-9
                return m, (miss_hit - m) / se_

            # control 1: scatter uniformly. Maximal coverage for a given count,
            # so it is BIASED AGAINST any clustered signal - stated, not hidden.
            cr = []
            for sd in range(701, 701 + seeds):
                rng = random.Random(sd)
                tb = {}
                for side in sides:
                    tb.setdefault(rng.choice(idx), set()).add(side)
                cr.append(rate(missed, tb))
            cm, z1 = zscore(cr)
            # control 2: shift the WHOLE signal train circularly. Spacing and
            # clustering are preserved exactly; only the alignment with price
            # turns is destroyed. This is the fair control.
            sr = []
            for sd in range(801, 801 + seeds):
                rng = random.Random(sd)
                off = rng.randrange(span)
                tb = {}
                for (i, side, _t) in sigs:
                    tb.setdefault(lo_i + (i - lo_i + off) % span, set()).add(side)
                sr.append(rate(missed, tb))
            sm, z2 = zscore(sr)
            print(f"   {cname:<26}{len(sigs):>9}"
                  f"{all_hit:>7} ({100*all_hit/len(legs):>4.1f}%)"
                  f"{miss_hit:>9} ({100*miss_hit/max(len(missed),1):>4.1f}%)"
                  f"{cm:>10.1f} ({100*cm/max(len(missed),1):>4.1f}%){z1:>7.1f}"
                  f"{sm:>10.1f} ({100*sm/max(len(missed),1):>4.1f}%){z2:>7.1f}")


if __name__ == "__main__":
    main()
    catch_test()

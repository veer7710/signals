"""
E-166 (research) — BREAK AND RETEST: "after a pullback we LOOK FOR entry,
                   NOT always entry."

Veer's correction to E-144. E-144 measured "enter on EVERY retest resumption"
and got -0.0095/trade on M1. His hand rule has a SELECTION step after the
pullback that the backtest never had. This file asks whether any confirmation
KNOWABLE AT THE RETEST BAR separates the retests worth taking from the rest.

CLAUDE.md's filter rule is the only thing that counts here:
  a filter earns its place ONLY if the trades it REFUSES are worse than the
  ones it allows.
So every candidate filter is reported as allowed-vs-refused, on the SAME book.

PROTOCOL (in this order, non-negotiable, from FAILURE_LOG 2026-09-06):
  0. NULL FIRST. Driftless random walk, same code, same geometry, same cost.
     If the pipeline makes money there, nothing downstream means anything.
  1. engine.entry_fill() for the stop entry, engine.trail_level() for the
     trail. No hand-rolled fills (E-151, E-165).
  2. Quartile every feature on the FIRST HALF only. Apply the chosen cut to
     the SECOND half, which the choice has never seen. >= 100 unseen trades
     or the answer is UNPROVEN.
  3. Points as well as per-trade (E-074), plus maxDD, worst trade, longest
     losing run, win rate, and the per-trade of the REFUSED trades.
  4. Time-shifted control.

Reads existing modules; writes nothing; modifies nothing.
"""
from __future__ import annotations
import os, sys, math, random, statistics, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Series, atr as watr, ema, trail_level, entry_fill
from liq_m1 import load
from sweep_winrate import pivots

GBP = 0.787
BPD = {"M1": 1440, "M5": 288}

# ---- the BR parameter set, FIXED at E-144/combined.py defaults. Not tuned here.
PK, BRK, TOL, WAIT, BUF, CAP = 5, 0.10, 0.20, 60, 0.30, 1.2
GIVE, HOLD, COOLDOWN = 0.25, 240, 5


# --------------------------------------------------------------------------
#  CANDIDATES — combined.candidates(), BR branch, byte-for-byte in its logic,
#  plus the features. NOTHING in a feature may read a bar after `rt`.
# --------------------------------------------------------------------------
def br_candidates(s, A, V, SPC, E20, verbose=False):
    n = len(s)
    piv = pivots(s, PK)                      # (known_at_bar, price, side)
    # active-pivot sweep for the "room to run" feature
    piv_sorted = sorted(piv, key=lambda x: x[0])
    out = []
    for (kb, px, side) in piv_sorted:
        a = A[kb]
        if not a or a <= 0:
            continue
        d = side
        bb = None
        for k in range(kb + 1, min(kb + WAIT, n)):
            if (s.c[k] > px + BRK * a) if d > 0 else (s.c[k] < px - BRK * a):
                bb = k
                break
        if bb is None:
            continue
        rt = None
        for k in range(bb + 1, min(bb + WAIT, n)):
            if (s.c[k] < px - TOL * a) if d > 0 else (s.c[k] > px + TOL * a):
                break
            touched = (s.l[k] <= px + TOL * a) if d > 0 else (s.h[k] >= px - TOL * a)
            held = (s.c[k] > px) if d > 0 else (s.c[k] < px)
            if touched and held:
                rt = k
                break
        if rt is None:
            continue
        trig = s.h[rt] if d > 0 else s.l[rt]
        sl = (s.l[rt] if d > 0 else s.h[rt]) - d * BUF * a
        if not (0 < abs(trig - sl) <= CAP * a):
            continue
        j = None
        for k in range(rt + 1, min(rt + WAIT, n)):
            if (s.h[k] >= trig) if d > 0 else (s.l[k] <= trig):
                j = k
                break
            if (s.c[k] < px - TOL * a) if d > 0 else (s.c[k] > px + TOL * a):
                break
        if j is None:
            continue
        # E-165: a STOP at `trig`. If the bar already opened past it, the fill
        # is the open. engine.entry_fill is the ONLY place that decides this.
        bf = entry_fill(trig, s.o[j], d)
        entry = bf + d * SPC[j] / 2.0
        out.append({"j": j, "d": d, "entry": entry, "sl": sl,
                    "kb": kb, "bb": bb, "rt": rt, "px": px, "a": a, "trig": trig,
                    "f": features(s, A, V, E20, piv_sorted, kb, bb, rt, px, d, a, trig, sl)})
    out.sort(key=lambda x: (x["j"],))
    return out


def _room(piv_sorted, rt, price, d, a, look=1000):
    """Nearest OPPOSING swing level already known at bar rt, in ATR. For a long
    that is the nearest confirmed swing HIGH above `price`."""
    best = None
    for (kn, p, sd) in piv_sorted:
        if kn > rt:
            break
        if kn < rt - look:
            continue
        if sd != d:                 # opposing: long wants swing highs (side +1)
            continue
        if d * (p - price) > 0:
            v = d * (p - price)
            if best is None or v < best:
                best = v
    return (best / a) if best is not None else 99.0


def features(s, A, V, E20, piv_sorted, kb, bb, rt, px, d, a, trig, sl):
    # 1. pullback DEPTH past the level, in ATR (>0 = pushed through it)
    ext = min(s.l[bb + 1:rt + 1]) if d > 0 else max(s.h[bb + 1:rt + 1])
    depth = d * (px - ext) / a
    # 2. how many bars the pullback took
    pbbars = float(rt - bb)
    # 3. the retest bar's own shape
    rng = s.h[rt] - s.l[rt]
    body = (abs(s.c[rt] - s.o[rt]) / rng) if rng > 0 else 0.0
    clspos = (((s.c[rt] - s.l[rt]) if d > 0 else (s.h[rt] - s.c[rt])) / rng) if rng > 0 else 0.5
    # 4. displacement on the BREAK leg
    disp = d * (s.c[bb] - s.o[bb]) / a              # break bar body, signed, ATR
    legrng = (max(s.h[kb:bb + 1]) - min(s.l[kb:bb + 1])) / a
    # 5. how far the break CLOSED beyond the level
    brkd = d * (s.c[bb] - px) / a
    # 6. volume (TICK volume - see DEFINITIONS.md; broker dependent)
    vb = V[bb] if V else 0.0
    vpb = statistics.mean(V[bb + 1:rt + 1]) if (V and rt > bb) else 0.0
    volr = (vb / vpb) if vpb > 0 else 0.0
    base = statistics.median(V[max(0, bb - 50):bb]) if (V and bb > 5) else 0.0
    volbrk = (vb / base) if base > 0 else 0.0
    # 7. does the retest hold above a short EMA / the break candle's midpoint
    emah = d * (s.c[rt] - E20[rt]) / a if E20[rt] is not None else 0.0
    mid = (s.h[bb] + s.l[bb]) / 2.0
    midh = d * (s.c[rt] - mid) / a
    # 8. room to the next opposing level
    room = _room(piv_sorted, rt, trig, d, a)
    # 9. regime + clock
    win = [x for x in A[max(0, rt - 500):rt] if x]
    areg = (a / statistics.median(win)) if win else 1.0
    hour = datetime.datetime.utcfromtimestamp(s.ts[rt]).hour
    risk = abs(trig - sl) / a
    return {"depth": depth, "pbbars": pbbars, "body": body, "clspos": clspos,
            "disp": disp, "legrng": legrng, "brkd": brkd, "volr": volr,
            "volbrk": volbrk, "emah": emah, "midh": midh, "room": room,
            "areg": areg, "hour": float(hour), "risk": risk,
            "wait": float(0)}


FEATS = ["depth", "pbbars", "body", "clspos", "disp", "legrng", "brkd",
         "volr", "volbrk", "emah", "midh", "room", "areg", "risk"]
FLABEL = {
    "depth":  "1 pullback depth past level (ATR)",
    "pbbars": "2 bars taken by the pullback",
    "body":   "3a retest bar body/range",
    "clspos": "3b retest bar close strength back",
    "disp":   "4a break bar body (ATR, signed)",
    "legrng": "4b break leg range (ATR)",
    "brkd":   "5 break close beyond level (ATR)",
    "volr":   "6a break tickvol / pullback tickvol",
    "volbrk": "6b break tickvol / prior-50 median",
    "emah":   "7a retest close vs EMA20 (ATR)",
    "midh":   "7b retest close vs break-bar mid (ATR)",
    "room":   "8 room to next opposing level (ATR)",
    "areg":   "9a ATR vs its own 500-bar median",
    "risk":   "  stop distance (ATR)",
}


# --------------------------------------------------------------------------
#  SIMULATE — combined.simulate(), one position at a time, engine.trail_level
# --------------------------------------------------------------------------
def simulate(s, SPC, cand, slip=0.0):
    out, busy = [], -1
    for c in cand:
        j, d, entry, sl0 = c["j"], c["d"], c["entry"], c["sl"]
        if j <= busy:
            continue
        sl = sl0
        peak = entry
        px_out = kk = None
        for k in range(j, min(j + HOLD, len(s))):
            if (s.l[k] <= sl) if d > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k
                break
            if k == j:
                continue
            peak = max(peak, s.h[k]) if d > 0 else min(peak, s.l[k])
            nsl = trail_level(entry, sl, peak, s.c[k], d, GIVE)
            if nsl is None:                      # E-151: unplaceable -> close
                px_out, kk = s.c[k], k
                break
            sl = nsl
        if px_out is None:
            kk = min(j + HOLD, len(s) - 1)
            px_out = s.c[kk]
        pts = d * ((px_out - d * SPC[kk] / 2.0) - entry) - slip
        r = dict(c)
        r["pts"] = pts
        r["kk"] = kk
        out.append(r)
        busy = kk + COOLDOWN
    return out


def summ(r):
    n = len(r)
    if n == 0:
        return None
    p = [x["pts"] for x in r]
    m = sum(p) / n
    sd = (sum((x - m) ** 2 for x in p) / (n - 1)) ** 0.5 if n > 1 else 0.0
    t = m / (sd / n ** 0.5) if sd > 0 else 0.0
    eq = peak = mdd = 0.0
    streak = worst = 0
    for x in p:
        eq += x; peak = max(peak, eq); mdd = max(mdd, peak - eq)
        streak = streak + 1 if x <= 0 else 0
        worst = max(worst, streak)
    return dict(n=n, pts=sum(p), per=m, t=t,
                win=100.0 * sum(1 for x in p if x > 0) / n,
                mdd=mdd, worst=min(p), lose_run=worst, sd=sd)


W = 40
def hdr(title):
    print("=" * (W + 62)); print("  " + title); print("=" * (W + 62))
    print(f"  {'cell':<{W}}{'n':>6}{'win%':>7}{'points':>9}{'per trade':>11}"
          f"{'t':>7}{'maxDD':>8}{'worst':>8}{'Lrun':>6}")


def line(lbl, r):
    z = summ(r)
    if z is None:
        print(f"  {lbl:<{W}}   no trades"); return
    print(f"  {lbl:<{W}}{z['n']:>6}{z['win']:>6.1f}%{z['pts']:>9.1f}"
          f"{z['per']:>+11.4f}{z['t']:>7.2f}{z['mdd']:>8.1f}{z['worst']:>8.2f}"
          f"{z['lose_run']:>6}")


# --------------------------------------------------------------------------
#  0. THE NULL — driftless random walk, same code, same cost
# --------------------------------------------------------------------------
def synth(n, sigma_tick, ticks, seed, p0=1300.0, step=60):
    rng = random.Random(seed)
    ts, o, h, l, c = [], [], [], [], []
    p = p0
    t0 = 1514847600
    for i in range(n):
        op = p; hi = lo = p
        for _ in range(ticks):
            p += rng.gauss(0.0, sigma_tick)
            if p > hi: hi = p
            if p < lo: lo = p
        ts.append(t0 + step * i); o.append(op); h.append(hi); l.append(lo); c.append(p)
    return Series(ts, o, h, l, c)


def calibrate(s, ticks=120):
    rr = sorted(s.h[i] - s.l[i] for i in range(len(s)))
    med_rng = rr[len(rr) // 2]
    sig = med_rng / (2.0 * math.sqrt(ticks))
    for _ in range(14):
        t = synth(20000, sig, ticks, 1)
        m = sorted(t.h[i] - t.l[i] for i in range(len(t)))[10000]
        sig *= (med_rng / m) ** 0.5
    return sig, med_rng


def ctx(tf):
    s, SP = load(tf)
    A = watr(s, 14)
    va = sorted(x for x in A[100:] if x)
    cs = 0.11 / (statistics.median(SP) / va[len(va) // 2])
    SPC = [x * cs for x in SP]
    return s, SP, A, cs, SPC


def run_null(tf, seeds=6):
    s, SP, A, cs, SPC = ctx(tf)
    V = [0.0] * len(s)
    sig, med_rng = calibrate(s)
    med_sp = statistics.median(SPC)
    t = synth(30000, sig, 120, 1)
    print(f"\n  calibration {tf}: real median bar range {med_rng:.4f}  "
          f"synth {sorted(t.h[i]-t.l[i] for i in range(len(t)))[15000]:.4f}")
    print(f"  flat spread charged = real median charged spread {med_sp:.5f} pts\n")
    hdr(f"NULL FIRST — BREAK+RETEST on a DRIFTLESS RANDOM WALK ({tf} geometry)")
    pers = []
    N = min(len(s), 60000)
    for sd in range(seeds):
        ss = synth(N, sig, 120, 700 + sd)
        AA = watr(ss, 14)
        SPCn = [med_sp] * len(ss)
        E20 = ema(ss.c, 20)
        VV = [1.0] * len(ss)
        cc = br_candidates(ss, AA, VV, SPCn, E20)
        rr = simulate(ss, SPCn, cc)
        z = summ(rr)
        if z: pers.append(z["per"])
        line(f"driftless walk seed {sd}", rr)
    if pers:
        m = sum(pers) / len(pers)
        print(f"\n  null mean per trade {m:+.5f} over {len(pers)} seeds "
              f"(spread charged {med_sp:.5f}; a null must pay about -half to -1 spread)")
        print(f"  seeds POSITIVE: {sum(1 for x in pers if x > 0)}/{len(pers)}")
    return pers


# --------------------------------------------------------------------------
#  time-shifted control: same direction, same risk, entry K bars later
# --------------------------------------------------------------------------
def shifted(cand, s, SPC, K):
    out = []
    for c in cand:
        j2 = c["j"] + K
        if j2 >= len(s) - 2:
            continue
        d = c["d"]
        risk = abs(c["entry"] - c["sl"])
        e = s.o[j2] + d * SPC[j2] / 2.0
        c2 = dict(c); c2["j"] = j2; c2["entry"] = e; c2["sl"] = e - d * risk
        out.append(c2)
    out.sort(key=lambda x: x["j"])
    return out


# --------------------------------------------------------------------------
#  the study
# --------------------------------------------------------------------------
def quartiles(vals):
    v = sorted(vals)
    n = len(v)
    return [v[int(q * (n - 1))] for q in (0.25, 0.50, 0.75)]


def run_tf(tf):
    s, SP, A, cs, SPC = ctx(tf)
    V = [0.0] * len(s)
    import json
    rows = json.load(open(f"/home/user/signals/data/GOLD_{tf}_2018.json"))
    rows.sort(key=lambda r: r[0])
    V = [float(r[7]) for r in rows]
    assert len(V) == len(s), (len(V), len(s))
    E20 = ema(s.c, 20)
    print("\n" + "#" * (W + 62))
    print(f"#  XAUUSD {tf}  —  {len(s)} bars, {len(s)/BPD[tf]:.0f} days, "
          f"charged spread median {statistics.median(SPC):.4f} pts")
    print("#" * (W + 62))
    nz = sum(1 for x in V if x > 0)
    print(f"  tick-volume column: {nz}/{len(V)} bars non-zero, "
          f"median {statistics.median(V):.0f}  -> USABLE (tick volume, not traded volume)")
    hh = sorted({datetime.datetime.utcfromtimestamp(t).hour for t in s.ts})
    print(f"  UTC hours present in the feed: {hh}")

    cand = br_candidates(s, A, V, SPC, E20)
    book = simulate(s, SPC, cand)
    hdr(f"BASELINE — every retest resumption taken ({tf}), E-144's rule")
    line("ALL retests (the book)", book)
    for K in (23, 61, 137):
        line(f"time-shifted control +{K} bars", simulate(s, SPC, shifted(cand, s, SPC, K)))
    line("LONG only", [x for x in book if x["d"] > 0])
    line("SHORT only", [x for x in book if x["d"] < 0])
    print(f"  candidates generated {len(cand)}, scheduled into the one-position "
          f"book {len(book)}")

    half = len(book) // 2
    A1, A2 = book[:half], book[half:]
    hdr("THE TWO HALVES (chronological split of the same book)")
    line("first half  (features chosen HERE)", A1)
    line("second half (never seen by the choice)", A2)

    # ---------------- quartile ladders on the FIRST HALF only
    print("\n" + "=" * (W + 62))
    print(f"  QUARTILE LADDERS — FIRST HALF ONLY, n={len(A1)}. "
          f"{len(FEATS)} features tested (multiple comparisons).")
    print("=" * (W + 62))
    print(f"  {'feature':<{W}}{'Q1':>10}{'Q2':>10}{'Q3':>10}{'Q4':>10}   {'monotone?':>9}")
    ladders = {}
    for f in FEATS:
        vals = [x["f"][f] for x in A1]
        cuts = quartiles(vals)
        qs = [[], [], [], []]
        for x in A1:
            v = x["f"][f]
            qi = 0 if v <= cuts[0] else 1 if v <= cuts[1] else 2 if v <= cuts[2] else 3
            qs[qi].append(x)
        pers = [(summ(q)["per"] if q else 0.0) for q in qs]
        up = all(pers[i] < pers[i + 1] for i in range(3))
        dn = all(pers[i] > pers[i + 1] for i in range(3))
        mono = "UP" if up else "DOWN" if dn else "-"
        ladders[f] = (cuts, pers, mono, [len(q) for q in qs])
        print(f"  {FLABEL[f]:<{W}}" + "".join(f"{p:>+10.4f}" for p in pers)
              + f"   {mono:>9}")
    # hour is categorical, shown separately
    print("\n  by UTC hour (first half) — n / per-trade:")
    byh = {}
    for x in A1:
        byh.setdefault(int(x["f"]["hour"]), []).append(x)
    print("   " + "  ".join(f"{h:02d}:{len(v):>3}/{summ(v)['per']:+.3f}"
                            for h, v in sorted(byh.items())))

    # ---------------- TEST A (strict, pre-registered): monotone ladders only
    print("\n" + "=" * (W + 62))
    print("  TEST A (strict) — only features with a MONOTONE first-half ladder")
    print("  earn a filter. THE FILTER RULE: allowed vs REFUSED on the UNSEEN half.")
    print("=" * (W + 62))
    mono_feats = [f for f in FEATS if ladders[f][2] != "-"]
    print(f"  monotone in the first half: {len(mono_feats)}/{len(FEATS)} features"
          + (f"  -> {mono_feats}" if mono_feats else ""))
    if mono_feats:
        print(f"  {'filter (keep ...)':<{W}}{'n':>5}{'per':>9}{'pts':>8}{'win%':>7}"
              f" | {'nref':>5}{'refused per':>12}{'refused pts':>12}  {'better?':>8}")
    for f in mono_feats:
        cuts, pers, mono, ns = ladders[f]
        opts = ([(f"{f} > Q2 (keep high)", cuts[1], True),
                 (f"{f} > Q3 (keep high)", cuts[2], True)] if mono == "UP" else
                [(f"{f} < Q2 (keep low)", cuts[1], False),
                 (f"{f} < Q1 (keep low)", cuts[0], False)])
        for name, thr, keep_hi in opts:
            allow, refuse = split(A2, f, thr, keep_hi)
            report_split(name, allow, refuse)

    # ---------------- TEST B (generous): median split, best side chosen IS
    print("\n" + "=" * (W + 62))
    print("  TEST B (generous) — EVERY feature gets a filter: split the first")
    print("  half at its own median, keep whichever side paid better IN SAMPLE,")
    print("  then apply that to the unseen half. 14 variants; if these are noise")
    print("  about 7 of 14 hold their sign by chance alone.")
    print("=" * (W + 62))
    print(f"  {'filter (keep ...)':<{W}}{'n':>5}{'per':>9}{'pts':>8}{'win%':>7}"
          f" | {'nref':>5}{'refused per':>12}{'refused pts':>12}  {'better?':>8}")
    held = 0
    for f in FEATS:
        cuts = ladders[f][0]
        thr = cuts[1]
        hi, lo = split(A1, f, thr, True)
        keep_hi = summ(hi) is not None and summ(lo) is not None and summ(hi)["per"] > summ(lo)["per"]
        allow, refuse = split(A2, f, thr, keep_hi)
        if report_split(f"{f} {'>' if keep_hi else '<'} median", allow, refuse):
            held += 1
    print(f"  held on unseen data: {held}/{len(FEATS)}  "
          f"(chance alone gives about {len(FEATS)/2:.0f}/{len(FEATS)})")

    # ---------------- TEST C (most generous): best of 14 x 4 quartiles
    print("\n" + "=" * (W + 62))
    print("  TEST C (most generous) — take the SINGLE BEST first-half quartile out")
    print(f"  of {len(FEATS)}x4 = {len(FEATS)*4} cells and see what it does unseen.")
    print("  This is the largest multiple-comparison possible here; the best of")
    print(f"  {len(FEATS)*4} random cells always looks good in sample.")
    print("=" * (W + 62))
    bestq = None
    for f in FEATS:
        cuts, pers, mono, ns = ladders[f]
        for qi in range(4):
            if ns[qi] < 60:
                continue
            if bestq is None or pers[qi] > bestq[0]:
                bestq = (pers[qi], f, qi, cuts, ns[qi])
    if bestq:
        _, f, qi, cuts, nq = bestq
        lo = -1e18 if qi == 0 else cuts[qi - 1]
        hiv = 1e18 if qi == 3 else cuts[qi]
        allow = [x for x in A2 if lo < x["f"][f] <= hiv]
        refuse = [x for x in A2 if not (lo < x["f"][f] <= hiv)]
        hdr(f"best in-sample cell: {FLABEL[f]} Q{qi+1}  ({lo:.4f}, {hiv:.4f}]")
        line("first half, ALLOWED (in sample)",
             [x for x in A1 if lo < x["f"][f] <= hiv])
        line("SECOND HALF, ALLOWED (unseen)", allow)
        line("SECOND HALF, REFUSED (unseen)", refuse)
        line("SECOND HALF, everything", A2)
        if len(allow) < 100:
            print(f"  *** {len(allow)} unseen trades, below the 100 minimum -> UNPROVEN.")

    # ---------------- TEST D: the hand-trader's stack, all three at once
    print("\n" + "=" * (W + 62))
    print("  TEST D — the confirmations STACKED, as a human would read them:")
    print("  a violent break (disp above median) AND a shallow tag rather than a")
    print("  deep push (depth below median) AND a strong close back (clspos above")
    print("  median). Cuts are first-half medians; sides are the ones a trader")
    print("  would state in advance, not fitted.")
    print("=" * (W + 62))
    md = {f: ladders[f][0][1] for f in FEATS}
    def stack(x):
        return (x["f"]["disp"] > md["disp"] and x["f"]["depth"] < md["depth"]
                and x["f"]["clspos"] > md["clspos"])
    for lbl, bk in (("first half", A1), ("SECOND half (unseen)", A2)):
        a = [x for x in bk if stack(x)]
        r = [x for x in bk if not stack(x)]
        hdr(f"stacked confirmation — {lbl}")
        line("ALLOWED", a); line("REFUSED", r)

    # ---------------- TEST E: hours picked in sample
    print("\n" + "=" * (W + 62))
    print("  TEST E — hours that paid in the first half, applied to the second.")
    print("  (this feed is MISSING the 00:00 UTC hour; timestamps are SECONDS)")
    print("=" * (W + 62))
    good = {h for h, v in byh.items() if summ(v)["per"] > 0}
    a = [x for x in A2 if int(x["f"]["hour"]) in good]
    r = [x for x in A2 if int(x["f"]["hour"]) not in good]
    print(f"  hours kept: {sorted(good)}")
    hdr("hours chosen on the first half")
    line("SECOND HALF, ALLOWED (unseen)", a)
    line("SECOND HALF, REFUSED (unseen)", r)
    return book, A1, A2, ladders


def split(bk, f, thr, keep_hi):
    a = [x for x in bk if (x["f"][f] > thr if keep_hi else x["f"][f] <= thr)]
    r = [x for x in bk if not (x["f"][f] > thr if keep_hi else x["f"][f] <= thr)]
    return a, r


def report_split(name, allow, refuse):
    za, zr = summ(allow), summ(refuse)
    if za is None or zr is None:
        print(f"  {name:<{W}}  degenerate split"); return False
    # Welch t on the difference allowed - refused
    va = za["sd"] ** 2 / za["n"]; vr = zr["sd"] ** 2 / zr["n"]
    tw = (za["per"] - zr["per"]) / math.sqrt(va + vr) if (va + vr) > 0 else 0.0
    ok = za["per"] > zr["per"]
    flag = ("YES" if ok else "no") + ("" if za["n"] >= 100 else " n<100")
    print(f"  {name:<{W}}{za['n']:>5}{za['per']:>+9.4f}{za['pts']:>8.1f}"
          f"{za['win']:>6.1f}% | {zr['n']:>5}{zr['per']:>+12.4f}"
          f"{zr['pts']:>12.1f}  {flag:>8}  dt {tw:+.2f}")
    return ok


def main():
    print("=" * (W + 62))
    print("  E-166 — DOES ANY CONFIRMATION AT THE RETEST SEPARATE THE GOOD ONES?")
    print("  Step 0 is the null. Nothing below it is read until it comes back flat.")
    print("=" * (W + 62))
    for tf in ("M1", "M5"):
        run_null(tf, seeds=6)
    for tf in ("M1", "M5"):
        run_tf(tf)


if __name__ == "__main__":
    main()

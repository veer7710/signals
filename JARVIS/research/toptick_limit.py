"""
E-166 — THE TOP-TICK ENTRY: a LIMIT back at the sweep extreme.

  NOTE ON THE FILENAME. This was asked for as `toptick.py`. That name is taken
  by E-076/E-077 (a limit resting INSIDE a liquidity zone on 15m/1h, filled BY
  the sweep). This is a different trade and that file was not touched.

THE HYPOTHESIS, falsifiable, with its mechanism
  After a swing HIGH is swept, price has run UP through the level and closed
  back DOWN below it. A SELL STOP at the level is therefore unplaceable - which
  is E-165, which killed the sweep. But a SELL LIMIT sitting back UP at (or near)
  the SWEEP BAR'S HIGH is placeable, because the market is below it. Mechanism
  claimed: the sweep extreme is where the last buy stops were filled, so a
  retest of it is met by supply; and the stop, sitting just beyond that extreme,
  is far tighter than a stop measured from the level, so the same adverse move
  costs less. PREDICTION: mean points per trade > 0 net of each bar's own
  measured spread, and materially above a matched-geometry random control and
  above a driftless random walk.

  Falsified if per-trade points <= 0, or t < 2, or the walk-forward second half
  does not confirm a first-half choice on >= 100 unseen trades.

ORDER SEMANTICS, WRITTEN OUT, BECAUSE TWO FILL BUGS KILLED THIS PROJECT TODAY
  E-151: a trail filled where no order could rest.  E-165: an entry STOP filled
  at a level the market had already left, on 75% of setups.

  A LIMIT has the OPPOSITE rule to a STOP:
    * a SELL LIMIT is placed ABOVE the market and fills when price rises TO it;
    * a BUY  LIMIT is placed BELOW the market and fills when price falls TO it.
  So:
    ARMING   is refused unless d * (E - ref) < 0, i.e. a sell limit (d=-1) is
             strictly above the arming close and a buy limit (d=+1) strictly
             below it. If it is not, the order would fill instantly at market -
             the exact error E-165 punished, mirrored.
    FILLING  happens on the first bar whose extreme reaches E. The fill price is
             E. If the bar OPENS through E the real fill would be BETTER than E
             (genuine limit price improvement) - we deliberately book E anyway,
             which is conservative, and count how often it happens.
    NEVER    is a limit booked at a price better than its own limit price. That
             is asserted on every single fill (LIMIT_VIOLATIONS).
  Exits use engine.entry_fill() (a stop order: it CAN gap through, and then the
  open is the honest price) and engine.trail_level() (E-151). Neither is
  hand-rolled here.

PROTOCOL, IN THIS ORDER
  0. engine tests.
  1. THE NULL FIRST. Driftless tick-level random walk, bar range calibrated to
     the real M1 median. Zero cost: the answer MUST be 0. With cost: it MUST be
     about minus the spread. If it pays, the test is broken and nothing else in
     this file means anything.
  2. Fill-rate sweep over the entry offset f (fraction of the way from the level
     back to the sweep extreme; f=1 is the true top tick).
  3. Stop buffer beyond the extreme, 0.10/0.20/0.30/0.50 ATR.
  4. Choose on the FIRST HALF only, report on the SECOND half, >= 100 trades.
  5. Matched-geometry random control, 12 seeds, and a time-shifted control.

Cost: each bar's own measured spread x cs, half in and half out, as combined.py.

Run:  python3 JARVIS/research/toptick_limit.py
      python3 JARVIS/research/toptick_limit.py null      (just step 1)
"""
from __future__ import annotations
import os, sys, math, random, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import adv_harness as H
from adv_null import synth
from engine import atr as watr, trail_level, entry_fill
from sweep_winrate import pivots

GBP = 0.787

# every fill is checked against its own limit price; this must stay empty
LIMIT_VIOLATIONS = []
GAP_THROUGH = [0, 0]        # [fills where the bar opened through E, total fills]


# --------------------------------------------------------------- candidates
def toptick_candidates(s, A, SPC, f, buf, pk=5, sweep_atr=0.10, wick=0.6460,
                       cap=1.2, life=120, maxwait=120):
    """Every top-tick LIMIT order the rule would ever place.

    Returns (arm_bar, d, E, S, level, ext, kb, sw) with E the LIMIT PRICE
    BEFORE cost (cost is charged at fill time, where the bar is known).

    Nothing here reads a bar later than `sw`, the sweep bar, which has closed.
    """
    out = []
    for (kb, px, side) in pivots(s, pk):
        a = A[kb]
        if not a or a <= 0:
            continue
        d = -side                      # swept HIGH (side +1) -> SHORT
        need = px + side * sweep_atr * a
        sw = ext = None
        for k in range(kb + 1, min(kb + life, len(s))):
            if (s.h[k] >= need) if side > 0 else (s.l[k] <= need):
                sw, ext = k, (s.h[k] if side > 0 else s.l[k])
                break
        if sw is None:
            continue
        rng = s.h[sw] - s.l[sw]
        if (abs(s.c[sw] - s.o[sw]) / rng if rng > 0 else 1.0) > wick:
            continue
        # the limit: f of the way from the LEVEL back to the SWEEP EXTREME
        E = px + f * (ext - px)
        # the stop: buf ATR BEYOND the extreme
        S = ext - d * buf * a
        risk = abs(E - S)
        if not (0 < risk <= cap * a):
            continue
        # ARMING CHECK. A sell limit must be strictly above the arming close,
        # a buy limit strictly below it. Otherwise it is a market order.
        if d * (E - s.c[sw]) >= 0:
            continue
        out.append((sw, d, E, S, px, ext, kb, maxwait))
    out.sort(key=lambda x: x[0])
    return out


# --------------------------------------------------------------- simulation
def limit_fill(E, o_k, d):
    """Where a LIMIT at E fills on bar k. The mirror of engine.entry_fill.

    A limit NEVER fills better than its own price in this backtest: if the bar
    opened through E the real fill would be better and we refuse the gift.
    """
    if d * (o_k - E) < 0:          # short: open ABOVE E / long: open BELOW E
        GAP_THROUGH[0] += 1        # would have been price improvement
    return E


def simulate(s, SPC, A, cand, give=0.25, hold=240, cooldown=5, slip=0.0):
    """ONE POSITION AT A TIME, orders armed only while flat.

    Returns full trade records plus (armed, filled) for the fill rate.
    """
    out, busy = [], -1
    armed = filled = 0
    for (sw, d, E, S, px, ext, kb, maxwait) in cand:
        if sw <= busy:
            continue
        armed += 1
        # ---- wait for the limit to be reached. Order rests from sw+1.
        j = None
        for k in range(sw + 1, min(sw + 1 + maxwait, len(s))):
            reached = (s.h[k] >= E) if d < 0 else (s.l[k] <= E)
            if reached:
                j = k
                break
        if j is None:
            continue
        filled += 1
        GAP_THROUGH[1] += 1
        fill = limit_fill(E, s.o[j], d)
        if d < 0 and fill > E + 1e-12:
            LIMIT_VIOLATIONS.append((j, fill, E))
        if d > 0 and fill < E - 1e-12:
            LIMIT_VIOLATIONS.append((j, fill, E))
        entry = fill + d * SPC[j] / 2.0      # cost: half spread in
        sl = S
        peak = entry
        px_out = kk = None
        for k in range(j, min(j + hold, len(s))):
            hit = (s.l[k] <= sl) if d > 0 else (s.h[k] >= sl)
            if hit:
                # a STOP can gap through: engine.entry_fill gives the honest px
                px_out, kk = entry_fill(sl, s.o[k], -d), k
                break
            if k == j:
                continue           # E-151/E-110: the fill bar arms no trail
            peak = max(peak, s.h[k]) if d > 0 else min(peak, s.l[k])
            nsl = trail_level(entry, sl, peak, s.c[k], d, give)
            if nsl is None:
                px_out, kk = s.c[k], k
                break
            sl = nsl
        if px_out is None:
            kk = min(j + hold, len(s) - 1)
            px_out = s.c[kk]
        pts = d * ((px_out - d * SPC[kk] / 2.0) - entry) - slip
        out.append({"pts": pts, "d": d, "j": j, "kk": kk, "ts": s.ts[j],
                    "risk": abs(entry - S), "sw": sw})
        busy = kk + cooldown
    return out, armed, filled


# --------------------------------------------------------------- statistics
def summ(r):
    n = len(r)
    if n == 0:
        return None
    p = [x["pts"] for x in r]
    m = sum(p) / n
    sd = (sum((x - m) ** 2 for x in p) / (n - 1)) ** 0.5 if n > 1 else 0.0
    t = m / (sd / n ** 0.5) if sd > 0 else 0.0
    eq = peak = mdd = 0.0
    for x in p:
        eq += x
        peak = max(peak, eq)
        mdd = max(mdd, peak - eq)
    run = worst = 0
    for x in p:
        run = run + 1 if x <= 0 else 0
        worst = max(worst, run)
    return dict(n=n, pts=sum(p), per=m, t=t,
                win=100.0 * sum(1 for x in p if x > 0) / n,
                mdd=mdd, sd=sd, worst=min(p), losing_run=worst,
                risk=sum(x["risk"] for x in r) / n)


HDR = (f"  {'cell':<30}{'n':>6}{'fill%':>7}{'win%':>7}{'points':>9}"
       f"{'per tr':>9}{'t':>7}{'maxDD':>8}{'worst':>8}{'Lrun':>6}{'risk':>7}")


def line(lbl, r, armed=None, filled=None, w=30):
    z = summ(r)
    if z is None:
        fr = (100.0 * filled / armed) if armed else 0.0
        print(f"  {lbl:<{w}}{0:>6}{fr:>6.1f}%      no trades")
        return
    fr = (100.0 * filled / armed) if armed else float("nan")
    print(f"  {lbl:<{w}}{z['n']:>6}{fr:>6.1f}%{z['win']:>6.1f}%{z['pts']:>9.1f}"
          f"{z['per']:>+9.4f}{z['t']:>7.2f}{z['mdd']:>8.1f}{z['worst']:>+8.2f}"
          f"{z['losing_run']:>6}{z['risk']:>7.3f}")


# --------------------------------------------------------------- STEP 1: NULL
def run_null(seeds=(1, 2, 3), nbars=200000, f=1.0, buf=0.30, charge=True):
    s0, SP0, A0, cs0 = H.ctx("M1")
    rr = sorted(s0.h[i] - s0.l[i] for i in range(len(s0)))
    med_rng = rr[len(rr) // 2]
    med_sp = statistics.median([x * cs0 for x in SP0])
    ticks = 120
    sig = med_rng / (2.0 * math.sqrt(ticks))
    for _ in range(14):
        t = synth(20000, sig, ticks, 1)
        m = sorted(t.h[i] - t.l[i] for i in range(20000))[10000]
        sig *= (med_rng / m) ** 0.5
    res = []
    for sd in seeds:
        ss = synth(nbars, sig, ticks, 900 + sd)
        AA = watr(ss, 14)
        SPC = [med_sp if charge else 0.0] * len(ss)
        c = toptick_candidates(ss, AA, SPC, f, buf)
        r, a, fl = simulate(ss, SPC, AA, c)
        res.append((sd, r, a, fl))
    return res, med_rng, med_sp, sig


# ------------------------------------------------- matched-geometry control
def random_control(s, SPC, A, cand, seed, give=0.25):
    """Same shape, no level. For each real setup, drop the identical geometry
    (E and S in ATR units relative to the bar's close, same direction) at a
    RANDOM bar. Matched on FILL CONVENTION - a limit control for a limit
    strategy (the E-107/E-110 lesson)."""
    rng = random.Random(seed)
    fake = []
    lo, hi = 300, len(s) - 400
    for (sw, d, E, S, px, ext, kb, maxwait) in cand:
        a = A[sw]
        if not a or a <= 0:
            continue
        de = (E - s.c[sw]) / a
        ds = (S - s.c[sw]) / a
        r = rng.randrange(lo, hi)
        ar = A[r]
        if not ar or ar <= 0:
            continue
        E2 = s.c[r] + de * ar
        S2 = s.c[r] + ds * ar
        if d * (E2 - s.c[r]) >= 0:
            continue
        fake.append((r, d, E2, S2, 0.0, 0.0, r, maxwait))
    fake.sort(key=lambda x: x[0])
    return simulate(s, SPC, A, fake, give=give)


def time_shift_control(s, SPC, A, f, buf, shift, give=0.25):
    """The setups computed on the real series, then EXECUTED `shift` bars later.
    The geometry is re-expressed in ATR units off the shifted arming close, so
    the order is still placeable; only the LEVEL's information is destroyed."""
    c = toptick_candidates(s, A, SPC, f, buf)
    moved = []
    for (sw, d, E, S, px, ext, kb, maxwait) in c:
        r = sw + shift
        if r >= len(s) - 300:
            continue
        a = A[sw]
        ar = A[r]
        if not a or a <= 0 or not ar or ar <= 0:
            continue
        de = (E - s.c[sw]) / a
        ds = (S - s.c[sw]) / a
        E2 = s.c[r] + de * ar
        S2 = s.c[r] + ds * ar
        if d * (E2 - s.c[r]) >= 0:
            continue
        moved.append((r, d, E2, S2, 0.0, 0.0, r, maxwait))
    moved.sort(key=lambda x: x[0])
    return simulate(s, SPC, A, moved, give=give)


# --------------------------------------------------------------------- main
OFFSETS = [1.00, 0.90, 0.75, 0.50, 0.25, 0.00]
BUFS = [0.10, 0.20, 0.30, 0.50]


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else ""

    # ================================================== 1. THE NULL, FIRST
    print("=" * 110)
    print("  STEP 1 — THE NULL. Driftless random walk, real M1 bar geometry.")
    print("  A martingale has no edge. Zero cost MUST give 0. With cost it MUST")
    print("  give about minus the spread. If it pays, the TEST is broken.")
    print("=" * 110)
    for charge in (False, True):
        res, med_rng, med_sp, sig = run_null(charge=charge)
        tag = "COST CHARGED" if charge else "ZERO COST"
        print(f"\n  {tag}   (synthetic sigma/tick {sig:.5f}, real median bar "
              f"range {med_rng:.4f}, flat spread {med_sp:.5f})")
        print(HDR)
        allr = []
        for (sd, r, a, fl) in res:
            line(f"null seed {sd}, f=1.00 buf=0.30", r, a, fl)
            allr += r
        line("POOLED", allr, sum(x[2] for x in res), sum(x[3] for x in res))
    print(f"\n  limit-price violations so far: {len(LIMIT_VIOLATIONS)}  "
          f"(must be 0)")
    print(f"  fills where the bar opened THROUGH the limit (we refused the "
          f"price improvement): {GAP_THROUGH[0]}/{GAP_THROUGH[1]} "
          f"= {100.0*GAP_THROUGH[0]/max(1,GAP_THROUGH[1]):.1f}%")

    # a second null cell: the offset the real data might like
    print("\n  NULL, other offsets (zero cost, must all be ~0):")
    print(HDR)
    for f in (0.75, 0.25):
        res, _, _, _ = run_null(seeds=(1, 2), f=f, charge=False)
        allr = []
        for (sd, r, a, fl) in res:
            allr += r
        line(f"null f={f:.2f} buf=0.30", allr, sum(x[2] for x in res),
             sum(x[3] for x in res))
    print()
    if only == "null":
        return

    # ================================================== 2/3. THE REAL GRID
    for tf in ("M1", "M5"):
        s, SP, A, cs = H.ctx(tf)
        SPC = [x * cs for x in SP]
        n = len(s)
        mid = n // 2
        print("=" * 110)
        print(f"  {tf} XAUUSD — top-tick LIMIT. {n} bars, split at bar {mid}.")
        print(f"  {len(OFFSETS)} offsets x {len(BUFS)} stop buffers "
              f"= {len(OFFSETS)*len(BUFS)} variants tested on this timeframe.")
        print("=" * 110)
        print(HDR)
        grid = {}
        for f in OFFSETS:
            for buf in BUFS:
                c = toptick_candidates(s, A, SPC, f, buf)
                r, a, fl = simulate(s, SPC, A, c)
                grid[(f, buf)] = (r, a, fl)
                line(f"f={f:.2f}  buf={buf:.2f}A", r, a, fl)
            print()

        # ---------------- 4. CHOOSE ON HALF ONE, REPORT ON HALF TWO
        print(f"  --- {tf}: chosen on the FIRST half only, reported on the "
              f"SECOND half (unseen) ---")
        best = None
        for (f, buf), (r, a, fl) in grid.items():
            r1 = [x for x in r if x["j"] < mid]
            z = summ(r1)
            if z is None or z["n"] < 30:
                continue
            if best is None or z["per"] > best[1]:
                best = ((f, buf), z["per"], z)
        if best is None:
            print("    no variant reached 30 trades in the first half.\n")
            continue
        (bf, bb), bper, bz = best
        print(f"    first-half winner: f={bf:.2f} buf={bb:.2f}A  "
              f"n={bz['n']}  {bz['per']:+.4f}/trade  t={bz['t']:.2f}")
        print(HDR)
        for (f, buf) in [(bf, bb)] + [(1.00, 0.30), (0.50, 0.30), (0.00, 0.30)]:
            r = grid[(f, buf)][0]
            r1 = [x for x in r if x["j"] < mid]
            r2 = [x for x in r if x["j"] >= mid]
            tag = "PICK " if (f, buf) == (bf, bb) else "     "
            line(f"{tag}f={f:.2f} buf={buf:.2f} 1st half", r1)
            line(f"{tag}f={f:.2f} buf={buf:.2f} 2nd HALF", r2)
        r2n = len([x for x in grid[(bf, bb)][0] if x["j"] >= mid])
        if r2n < 100:
            print(f"    !! the unseen half has only {r2n} trades. "
                  f"Under the 100 minimum: UNPROVEN by protocol.")

        # ---------------- 5. CONTROLS
        print(f"\n  --- {tf}: controls for f={bf:.2f} buf={bb:.2f} ---")
        print(HDR)
        real = grid[(bf, bb)]
        line("REAL", real[0], real[1], real[2])
        c = toptick_candidates(s, A, SPC, bf, bb)
        pers = []
        allc = []
        for sd in range(12):
            rc, ac, fc = random_control(s, SPC, A, c, 5000 + sd)
            z = summ(rc)
            if z:
                pers.append(z["per"])
                allc += rc
        line("random-geometry ctrl x12", allc)
        if pers:
            cm = sum(pers) / len(pers)
            csd = (sum((x - cm) ** 2 for x in pers) / max(1, len(pers) - 1)) ** 0.5
            print(f"    control per-trade across 12 seeds: mean {cm:+.4f} "
                  f"sd {csd:.4f}")
        for sh in (500, 1500, 4000):
            rt, at, ft = time_shift_control(s, SPC, A, bf, bb, sh)
            line(f"time-shift +{sh} bars", rt, at, ft)

        # ---------------- 6. COST SENSITIVITY + DIRECTION SPLIT
        print(f"\n  --- {tf}: slippage and direction, f={bf:.2f} buf={bb:.2f} ---")
        print(HDR)
        for sl in (0.0, 0.02, 0.05, 0.10):
            r, a, fl = simulate(s, SPC, A, c, slip=sl)
            line(f"slip {sl:.2f} pts", r, a, fl)
        r = real[0]
        line("LONGS only", [x for x in r if x["d"] > 0])
        line("SHORTS only", [x for x in r if x["d"] < 0])

        # ---------------- 7. WALK-FORWARD FOLDS
        print(f"\n  --- {tf}: 6 chronological folds, f={bf:.2f} buf={bb:.2f} ---")
        edges = [int(n * k / 6) for k in range(7)]
        pos = 0
        for k in range(6):
            fr = [x for x in r if edges[k] <= x["j"] < edges[k + 1]]
            z = summ(fr)
            if z:
                pos += 1 if z["per"] > 0 else 0
                print(f"    fold {k+1}: n={z['n']:>4}  {z['pts']:>+8.1f} pts "
                      f"{z['per']:>+9.4f}/tr  t={z['t']:>6.2f}  "
                      f"win {z['win']:.1f}%")
        print(f"    positive folds: {pos}/6")

        print(f"\n  pounds at 0.01 lots (x{GBP} today-scale ignored, 2018 pts): "
              f"{summ(r)['pts']*GBP:+.2f} GBP over {len(r)} trades\n")

    print("=" * 110)
    print(f"  limit-price violations, whole run: {len(LIMIT_VIOLATIONS)} "
          f"(any non-zero invalidates everything above)")
    print(f"  fills refused price improvement: {GAP_THROUGH[0]}/{GAP_THROUGH[1]}"
          f" = {100.0*GAP_THROUGH[0]/max(1,GAP_THROUGH[1]):.1f}% "
          f"(this makes the result CONSERVATIVE, not optimistic)")
    print("=" * 110)


if __name__ == "__main__":
    main()

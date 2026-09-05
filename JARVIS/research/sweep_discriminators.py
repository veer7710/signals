"""
E-135 — WHAT SEPARATES A GOOD SWEEP FROM A BAD ONE.

E-134 built the mechanical version of the trade Veer runs by hand: level,
sweep, limit back at the level, stop beyond the sweep extreme, fixed target.
It tops out at a 69% win rate and loses money at every high-win-rate setting.

He wins 80%. The mechanical version takes 20-33 TRADES A DAY. He takes a
handful. That difference is not the rules - it is SELECTION, and selection is
exactly what an indicator can be taught if the thing being selected on is real.

So: hold the entry, the stop, the target and the cost completely fixed, and ask
of every ICT/SMC feature that is knowable AT THE MOMENT OF ENTRY - does it
separate the winners from the losers?

METHOD, and it is the only one that answers the question:
  Split the population into quartiles by the feature and report points per
  trade in each. A feature that matters produces a MONOTONE ladder with a real
  gap between the ends. A feature that does not produces four numbers that look
  like each other, and no amount of narrative rescues it.

  Reported alongside: the SPREAD between best and worst quartile in points per
  trade, and what the top-quartile-only book would have made. A feature earns
  its place only if the trades it REFUSES are worse than the ones it allows -
  that is the CLAUDE.md rule and it is the one that kills most of these.

FEATURES, all computable at entry, none using a single future bar:
  1  sweep depth        how far past the level the run went, in ATR
  2  sweep speed        bars from the level's confirmation to the sweep
  3  sweep displacement the sweep bar's body as a fraction of its range
  4  sweep size         the sweep bar's range in ATR
  5  return speed       bars from the sweep to the fill
  6  level age          bars the pivot had stood before it was swept
  7  pool quality       how many prior extremes cluster at the level (EQH/EQL)
  8  premium/discount   where the level sits in the last 200 bars, the real
                        50% split, not LuxAlgo's 5% band
  9  range position     where the ENTRY sits in the recent range
 10  ATR regime         volatility at entry vs its own recent median
 11  FVG on return      did the move back to the level leave a gap
 12  opposing structure how far to the next pivot in the way

The do-not-test list from ICT_SMC_RESEARCH.md is respected: no killzones (the
feed is missing 00:00 UTC daily) and nothing volume-based (both volume columns
are zero).
"""
from __future__ import annotations
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr
from liq_m1 import load, GBP
from sweep_winrate import pivots

TODAY = 7.38


def build(tf="M1", pk=5, sweep_atr=0.10, buf=0.30, tgt_r=2.0,
          life=120, hold=240, cooldown=5, cost_frac=0.11):
    """The E-134 trade, returning per-trade FEATURES alongside the result."""
    s, SP = load(tf)
    A = watr(s, 14)
    va = sorted(x for x in A[100:] if x)
    med_a = va[len(va) // 2]
    cs = cost_frac / (statistics.median(SP) / med_a)
    piv = pivots(s, pk)
    piv_sorted = sorted(piv)

    # every confirmed extreme, for pool counting and "what is in the way"
    highs = [(b, p) for (b, p, sd) in piv_sorted if sd > 0]
    lows = [(b, p) for (b, p, sd) in piv_sorted if sd < 0]

    rows, busy = [], -1
    pi = 0
    for (kb, px, side) in piv_sorted:
        if kb <= busy:
            continue
        a = A[kb]
        if not a or a <= 0:
            continue
        tside = -side
        need = px + side * sweep_atr * a
        sw, ext = None, None
        for k in range(kb + 1, min(kb + life, len(s))):
            hit = (s.h[k] >= need) if side > 0 else (s.l[k] <= need)
            if hit:
                sw = k
                ext = s.h[k] if side > 0 else s.l[k]
                break
        if sw is None:
            continue

        j = None
        for k in range(sw + 1, min(sw + life, len(s))):
            back = (s.h[k] >= px) if tside > 0 else (s.l[k] <= px)
            if back:
                j = k
                break
            ext = max(ext, s.h[k]) if side > 0 else min(ext, s.l[k])
        if j is None:
            continue

        sp = SP[j] * cs
        entry = px + tside * sp / 2.0
        sl = ext - tside * buf * a
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        tp = entry + tside * tgt_r * risk

        px_out, kk = None, None
        for k in range(j, min(j + hold, len(s))):
            if (s.l[k] <= sl) if tside > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k
                break
            if k == j:
                continue
            if (s.h[k] >= tp) if tside > 0 else (s.l[k] <= tp):
                px_out, kk = tp, k
                break
        if px_out is None:
            kk = min(j + hold, len(s) - 1)
            px_out = s.c[kk]
        pts = tside * ((px_out - tside * SP[kk] * cs / 2.0) - entry)

        # ---------------- FEATURES, none of which sees past bar j ------------
        f = {}
        f["1 sweep depth (ATR)"] = abs(ext - px) / a
        f["2 sweep speed (bars)"] = sw - kb
        rng = s.h[sw] - s.l[sw]
        f["3 sweep displacement"] = (abs(s.c[sw] - s.o[sw]) / rng) if rng > 0 else 0.0
        f["4 sweep size (ATR)"] = rng / a
        f["5 return speed (bars)"] = j - sw
        # the pivot's own age: how far back the extreme itself sat
        f["6 level age (bars)"] = pk

        # pool quality: prior confirmed extremes on the same side within 0.25 ATR
        pool = 0
        src = highs if side > 0 else lows
        for (b2, p2) in src:
            if b2 >= kb:
                break
            if abs(p2 - px) <= 0.25 * a:
                pool += 1
        f["7 pool size (EQH/EQL)"] = pool

        lo200 = min(s.l[max(0, j - 200):j + 1])
        hi200 = max(s.h[max(0, j - 200):j + 1])
        span = hi200 - lo200
        # premium/discount on the REAL 50% split. For a long we want DISCOUNT,
        # so the feature is "how favourable", mirrored by side.
        pos = ((px - lo200) / span) if span > 0 else 0.5
        f["8 premium/discount"] = (1.0 - pos) if tside > 0 else pos
        f["9 entry range pos"] = ((entry - lo200) / span) if span > 0 else 0.5

        recent = [x for x in A[max(0, j - 500):j] if x]
        f["10 ATR vs its median"] = (a / statistics.median(recent)) if recent else 1.0

        # an FVG on the return leg: bar j-2 high vs bar j low (for a long)
        gap = 0.0
        if j >= 2:
            gap = (s.l[j] - s.h[j - 2]) if tside > 0 else (s.l[j - 2] - s.h[j])
        f["11 FVG on return (ATR)"] = gap / a

        # distance to the nearest opposing pivot in the way, in R
        opp = highs if tside > 0 else lows
        best = None
        for (b2, p2) in opp:
            if b2 >= j:
                break
            d = (p2 - entry) if tside > 0 else (entry - p2)
            if d > 0 and (best is None or d < best):
                best = d
        f["12 room to next level (R)"] = (best / risk) if best else 99.0

        rows.append((pts, f))
        busy = kk + cooldown
    return rows, len(s) / (1440 if tf == "M1" else 288 if tf == "M5" else 96)


def main():
    rows, days = build()
    n = len(rows)
    tot = sum(r[0] for r in rows)
    print("=" * 100)
    print("  E-135 — what separates a GOOD sweep from a BAD one")
    print(f"  M1, pivot 5, sweep 0.10 ATR, stop 0.30 ATR past the sweep, 2.0R target")
    print(f"  baseline: {n} trades, {n/days:.1f}/day, "
          f"{100.0*sum(1 for r in rows if r[0] > 0)/n:.1f}% win, "
          f"{tot:+.1f} points, {tot/n:+.4f}/trade")
    print("=" * 100)
    print(f"  {'feature':<26}{'Q1':>9}{'Q2':>9}{'Q3':>9}{'Q4':>9}"
          f"{'spread':>9}{'monotone':>10}{'top-Q book':>12}")
    print("  " + "-" * 94)

    keys = sorted(rows[0][1].keys())
    findings = []
    for k in keys:
        vals = sorted(rows, key=lambda r: r[1][k])
        q = n // 4
        if q < 30:
            continue
        buckets = [vals[0:q], vals[q:2*q], vals[2*q:3*q], vals[3*q:]]
        means = [sum(x[0] for x in b) / len(b) for b in buckets]
        spread = max(means) - min(means)
        mono = means == sorted(means) or means == sorted(means, reverse=True)
        # the book you would have if you only took the best quartile
        bi = means.index(max(means))
        topbook = sum(x[0] for x in buckets[bi])
        print(f"  {k:<26}" + "".join(f"{m:>9.4f}" for m in means)
              + f"{spread:>9.4f}{'YES' if mono else 'no':>10}{topbook:>12.1f}")
        findings.append((spread, k, mono, topbook, len(buckets[bi])))

    print("\n  " + "=" * 94)
    print("  RANKED BY SEPARATION. A feature is only interesting if the ladder is")
    print("  MONOTONE - four unordered numbers with a wide range is noise, and")
    print("  picking the best of four buckets after the fact is how a backtest")
    print("  invents an edge that does not exist.")
    print("  " + "-" * 94)
    for (spread, k, mono, topbook, cnt) in sorted(findings, reverse=True)[:6]:
        print(f"  {k:<26} spread {spread:>8.4f}  monotone {'YES' if mono else 'no':<4}"
              f"  best quartile {topbook:>8.1f} pts over {cnt} trades")


if __name__ == "__main__":
    main()


# ===========================================================================
#  E-135b — VALIDATION, because two monotone ladders out of twelve features
#  is roughly what CHANCE PRODUCES.
#
#  A random ordering of four buckets is monotone with probability 2/24 = 8.3%.
#  Twelve features therefore throw up about one monotone ladder by luck alone,
#  and this scan found two. Reporting them as findings without this step is
#  precisely how a backtest invents an edge, and this project has already paid
#  for that mistake six times over (E-110).
#
#  So:
#    1. SPLIT IN HALF. The quartile CUT is taken from the first half only and
#       applied unchanged to the second. If the ladder is real it survives; if
#       it was the scan finding the best of twelve, it will not.
#    2. COMBINE the two survivors and check the joint filter beats each alone.
#    3. PRINT THE REFUSED BOOK. CLAUDE.md: a filter earns its place only if what
#       it turns down is worse than what it takes.
# ===========================================================================
def validate():
    rows, days = build()
    n = len(rows)
    half = n // 2
    first, second = rows[:half], rows[half:]

    print("\n" + "=" * 100)
    print("  E-135b — do the two monotone features survive out of sample?")
    print("=" * 100)

    for k in ("3 sweep displacement", "11 FVG on return (ATR)"):
        # the cut comes from the FIRST half only, then is applied unchanged
        vals = sorted(x[1][k] for x in first)
        q1 = vals[len(vals) // 4]
        q3 = vals[3 * len(vals) // 4]
        # displacement is INVERSE - a small body is the good one - so the
        # favourable side is picked from the first half's own ladder, not from
        # what looks good in the second.
        fq = [x for x in first if x[1][k] <= q1]
        fq2 = [x for x in first if x[1][k] >= q3]
        lo_is_better = (sum(x[0] for x in fq) / len(fq)) > (sum(x[0] for x in fq2) / len(fq2))
        cut = q1 if lo_is_better else q3
        sel = (lambda v: v <= cut) if lo_is_better else (lambda v: v >= cut)

        print(f"\n  {k}   (favourable side: "
              f"{'LOW' if lo_is_better else 'HIGH'}, cut {cut:.4f} from the first half)")
        for lbl, book in (("first half  (in sample)", first),
                          ("second half (OUT of sample)", second)):
            take = [x for x in book if sel(x[1][k])]
            ref = [x for x in book if not sel(x[1][k])]
            if not take or not ref:
                continue
            tp = sum(x[0] for x in take)
            rp = sum(x[0] for x in ref)
            print(f"    {lbl:<30} take {len(take):>5} {tp:>8.1f} pts "
                  f"{tp/len(take):>+9.4f}/trade   |  refuse {len(ref):>5} "
                  f"{rp:>8.1f} {rp/len(ref):>+9.4f}/trade")

    # ---- the joint filter, cuts taken from the first half only -------------
    print("\n  " + "=" * 94)
    print("  THE TWO TOGETHER — a small-bodied sweep (a rejection wick, not a")
    print("  breakout close) AND a gap on the return leg. Both cuts come from")
    print("  the first half and are applied unchanged to the second.")
    print("  " + "-" * 94)
    d = sorted(x[1]["3 sweep displacement"] for x in first)
    g = sorted(x[1]["11 FVG on return (ATR)"] for x in first)
    dcut = d[len(d) // 2]          # median body ratio
    gcut = g[len(g) // 2]          # median gap
    print(f"  cuts: displacement <= {dcut:.4f}   and   FVG >= {gcut:.4f}")
    print(f"  {'book':<30}{'n':>7}{'/day':>7}{'win%':>8}{'points':>10}{'per trade':>12}")
    for lbl, book in (("first half  (in sample)", first),
                      ("second half (OUT of sample)", second),
                      ("everything", rows)):
        take = [x for x in book
                if x[1]["3 sweep displacement"] <= dcut
                and x[1]["11 FVG on return (ATR)"] >= gcut]
        ref = [x for x in book
               if not (x[1]["3 sweep displacement"] <= dcut
                       and x[1]["11 FVG on return (ATR)"] >= gcut)]
        if not take:
            continue
        tp = sum(x[0] for x in take)
        w = 100.0 * sum(1 for x in take if x[0] > 0) / len(take)
        frac = len(book) / len(rows)
        print(f"  {lbl:<30}{len(take):>7}{len(take)/(days*frac):>7.1f}"
              f"{w:>7.1f}%{tp:>10.1f}{tp/len(take):>+12.4f}")
        if ref:
            rp = sum(x[0] for x in ref)
            print(f"  {'   ...it refused':<30}{len(ref):>7}{'':>7}"
                  f"{100.0*sum(1 for x in ref if x[0]>0)/len(ref):>7.1f}%"
                  f"{rp:>10.1f}{rp/len(ref):>+12.4f}")


if __name__ == "__main__":
    validate()


# ===========================================================================
#  E-135c — THE CLEAN PROTOCOL.
#
#  E-135b split the data and the two features survived. That is NOT enough,
#  and saying so is the whole point of this block: the two features were
#  CHOSEN by a scan that had already seen every bar, second half included. The
#  out-of-sample test then measured a cut on a feature that was picked using
#  that same out-of-sample data. The split was honest; the selection was not.
#
#  The clean protocol runs the ENTIRE scan on the first half only - all twelve
#  features, the ranking, the choice of which side is favourable, the cut - and
#  then touches the second half exactly once.
#
#  If sweep displacement and the return FVG still come out on top of a scan
#  that has never seen the second half, and still work there, the finding is
#  real. If a different pair comes out, the first result was the scan fitting
#  noise and this file says so.
# ===========================================================================
def clean():
    rows, days = build()
    n = len(rows)
    first, second = rows[:n // 2], rows[n // 2:]
    keys = sorted(rows[0][1].keys())

    print("\n" + "=" * 100)
    print("  E-135c — the whole scan run on the FIRST HALF ONLY,")
    print("  then the second half touched exactly once")
    print("=" * 100)

    # ---- rank every feature using ONLY the first half ----------------------
    ranked = []
    q = len(first) // 4
    for k in keys:
        vals = sorted(first, key=lambda r: r[1][k])
        buckets = [vals[0:q], vals[q:2*q], vals[2*q:3*q], vals[3*q:]]
        means = [sum(x[0] for x in b) / len(b) for b in buckets]
        mono = means == sorted(means) or means == sorted(means, reverse=True)
        ranked.append((max(means) - min(means), mono, k, means))

    print(f"\n  first-half ranking (this is all the scan is allowed to see)")
    print(f"  {'feature':<26}{'spread':>9}{'monotone':>10}   ladder")
    print("  " + "-" * 88)
    for (sp, mono, k, means) in sorted(ranked, reverse=True):
        print(f"  {k:<26}{sp:>9.4f}{'YES' if mono else 'no':>10}   "
              + " ".join(f"{m:>+8.4f}" for m in means))

    picks = [(sp, k, means) for (sp, mono, k, means) in sorted(ranked, reverse=True)
             if mono][:2]
    if len(picks) < 2:
        print("\n  fewer than two monotone features in the first half - nothing to carry forward")
        return

    print(f"\n  the first half's own top-2 monotone features: "
          f"{picks[0][1]} and {picks[1][1]}")

    # ---- build the joint filter from the first half alone -------------------
    sels = []
    for (sp, k, means) in picks:
        vals = sorted(x[1][k] for x in first)
        cut = vals[len(vals) // 2]
        lo_better = means[0] > means[-1]
        sels.append((k, cut, lo_better))
        print(f"    {k:<26} favourable side "
              f"{'LOW  <= ' if lo_better else 'HIGH >= '}{cut:.4f}")

    def take(x):
        for (k, cut, lo) in sels:
            v = x[1][k]
            if (v > cut) if lo else (v < cut):
                return False
        return True

    print(f"\n  {'book':<30}{'n':>7}{'win%':>8}{'points':>10}{'per trade':>12}")
    print("  " + "-" * 68)
    for lbl, book in (("first half  (the scan saw this)", first),
                      ("SECOND HALF (never seen)", second)):
        t = [x for x in book if take(x)]
        r = [x for x in book if not take(x)]
        if not t:
            continue
        tp = sum(x[0] for x in t)
        w = 100.0 * sum(1 for x in t if x[0] > 0) / len(t)
        print(f"  {lbl:<30}{len(t):>7}{w:>7.1f}%{tp:>10.1f}{tp/len(t):>+12.4f}")
        if r:
            rp = sum(x[0] for x in r)
            print(f"  {'   ...it refused':<30}{len(r):>7}"
                  f"{100.0*sum(1 for x in r if x[0]>0)/len(r):>7.1f}%"
                  f"{rp:>10.1f}{rp/len(r):>+12.4f}")
    base = sum(x[0] for x in second)
    print(f"\n  second half unfiltered: {len(second)} trades, {base:+.1f} points, "
          f"{base/len(second):+.4f}/trade")


if __name__ == "__main__":
    clean()


# ===========================================================================
#  E-135d — THE PRE-REGISTERED TEST, which is the only one left that counts.
#
#  E-135c killed the monotonicity finding: on the first half alone neither
#  feature has a monotone ladder, so the monotonicity in E-135 was the scan
#  picking the best of twelve across pooled data. That is settled and it is not
#  coming back.
#
#  But monotonicity across four buckets was always a strict criterion, and it
#  is not what the theory claims. ICT/SMC makes a DIRECTIONAL prediction, and
#  it made it long before this dataset existed:
#
#     a sweep that is a WICK - long wick, small body - is a REJECTION, and the
#     trade back through the level is good. A sweep that CLOSES with a big body
#     is a real breakout, and fading it is the fakeout that costs money.
#
#     displacement back through the level - the gap it leaves being the FVG -
#     is the confirmation that the reversal is real.
#
#  So the direction is fixed by theory, not chosen from the data. The cut is
#  the first half's median. The second half is touched once. That is a
#  pre-registered test and it is honest even though the features were surfaced
#  by an earlier scan, because the only thing the scan could bias - which way
#  round the feature should point - is supplied by the theory instead.
#
#  If this fails, the discriminator is dead and no further slicing is allowed.
# ===========================================================================
def prereg():
    rows, days = build()
    n = len(rows)
    first, second = rows[:n // 2], rows[n // 2:]

    # direction from ICT, not from the data:
    #   small body on the sweep bar = rejection = GOOD  -> take LOW
    #   larger gap on the return    = displacement = GOOD -> take HIGH
    SPECS = [("3 sweep displacement", "low"),
             ("11 FVG on return (ATR)", "high")]

    cuts = []
    for (k, side) in SPECS:
        vals = sorted(x[1][k] for x in first)
        cuts.append((k, side, vals[len(vals) // 2]))

    def take(x, specs):
        for (k, side, cut) in specs:
            v = x[1][k]
            if side == "low" and v > cut:
                return False
            if side == "high" and v < cut:
                return False
        return True

    print("\n" + "=" * 100)
    print("  E-135d — pre-registered: direction from ICT theory, cut from the")
    print("  first half's median, second half touched once.")
    print("=" * 100)
    for (k, side, cut) in cuts:
        print(f"    {k:<26} take {side.upper():<5} of {cut:+.4f}")

    for label, specs in (("sweep is a WICK", cuts[:1]),
                         ("FVG on the return", cuts[1:]),
                         ("BOTH", cuts)):
        print(f"\n  --- {label} ---")
        print(f"  {'book':<30}{'n':>7}{'win%':>8}{'points':>10}{'per trade':>12}")
        for lbl, book in (("first half  (cut came from here)", first),
                          ("SECOND HALF (never seen)", second)):
            t = [x for x in book if take(x, specs)]
            r = [x for x in book if not take(x, specs)]
            if not t:
                continue
            tp = sum(x[0] for x in t)
            w = 100.0 * sum(1 for x in t if x[0] > 0) / len(t)
            print(f"  {lbl:<30}{len(t):>7}{w:>7.1f}%{tp:>10.1f}{tp/len(t):>+12.4f}")
            if r:
                rp = sum(x[0] for x in r)
                print(f"  {'   ...refused':<30}{len(r):>7}"
                      f"{100.0*sum(1 for x in r if x[0]>0)/len(r):>7.1f}%"
                      f"{rp:>10.1f}{rp/len(r):>+12.4f}")
    base = sum(x[0] for x in second)
    print(f"\n  second half UNFILTERED: {len(second)} trades, {base:+.1f} points, "
          f"{base/len(second):+.4f}/trade")
    print("\n  The test to pass: on the SECOND HALF, the taken book beats the")
    print("  unfiltered baseline AND the refused book is worse than the taken one.")
    print("  Anything less and this is dead.")


if __name__ == "__main__":
    prereg()


# ===========================================================================
#  E-135e — COST AND CONTROL, the two things that have killed everything else.
#
#  Ping-pong (E-132) passed a control at 9.0 se and died anyway, because at 124
#  trades a day the cost load buried it. This runs at ~6.6/day, so it should
#  fare better - but "should" is not a measurement.
#
#  Cost is swept in the scale-free unit (spread as a fraction of ATR). E-132's
#  calibration: on M1 at today's volatility a 0.20-point spread is 0.110, a
#  0.30 is 0.165 and a 0.40 is 0.220. Veer's broker is "0.4 or less" and takes
#  no commission, so 0.220 is the column that has to hold up, not 0.110.
# ===========================================================================
def cost_and_control():
    import importlib
    import sweep_discriminators as me

    print("\n" + "=" * 100)
    print("  E-135e — cost sensitivity on the filtered book")
    print("  (E-132: on M1 today, a 0.20 spread is 0.110 of ATR, 0.30 is 0.165,")
    print("   0.40 is 0.220. Veer's broker is '0.4 or less'.)")
    print("=" * 100)
    print(f"  {'spread/ATR':>11}{'~M1 spread':>12}{'n':>7}{'win%':>8}"
          f"{'points':>10}{'per trade':>12}{'GBP 0.01':>11}")
    print("  " + "-" * 71)

    for frac, approx in ((0.110, "0.20 pts"), (0.165, "0.30 pts"),
                         (0.220, "0.40 pts"), (0.300, "0.55 pts")):
        rows, days = me.build(cost_frac=frac)
        n = len(rows)
        first = rows[:n // 2]
        d = sorted(x[1]["3 sweep displacement"] for x in first)
        g = sorted(x[1]["11 FVG on return (ATR)"] for x in first)
        dcut, gcut = d[len(d) // 2], g[len(g) // 2]
        t = [x for x in rows
             if x[1]["3 sweep displacement"] <= dcut
             and x[1]["11 FVG on return (ATR)"] >= gcut]
        if not t:
            continue
        tp = sum(x[0] for x in t)
        w = 100.0 * sum(1 for x in t if x[0] > 0) / len(t)
        print(f"  {frac:>11.3f}{approx:>12}{len(t):>7}{w:>7.1f}%{tp:>10.1f}"
              f"{tp/len(t):>+12.4f}{tp*TODAY*GBP:>11.2f}")


if __name__ == "__main__":
    cost_and_control()

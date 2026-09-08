"""
E-185 — DOES THE HIGHER TIMEFRAME MAKE THE LEG CATCHER BETTER?

Veer, showing H1 and 15m charts of the same move: "in terms of liquidity here
you can see the move and the tons of potential for scalps especially m1 m15 h1
use bias wisely if u can". And earlier, repeatedly: "a h1 down trend we look for
that buy entry on m15", "m15 changes from m5 which changes from m1".

E-133 already tested higher-timeframe DIRECTION as a filter and found nothing
beat reading direction off the traded clock. That test is not this one, and it
is also suspect now:
  * it ran on Jan-Jun 2018 only, which E-176 showed is the wrong regime
  * it asked "must the H1 trend AGREE" - a trend-following question
  * it predates the leg-start framing entirely

E-184 found the leg catcher is a MEAN-REVERSION stack. For that, the useful HTF
question is not "does H1 agree with my direction" but "am I at an extreme of the
HIGHER timeframe's range" - which is exactly what Veer's screenshots show: H1
supply and demand zones, with the scalps taken as price reaches them.

So five HTF contexts, each layered on the SAME leg catcher, scored the same way
as E-184 - catch rate against a time-shifted control:

  1  HTF premium/discount agrees with the signal
  2  HTF is STRETCHED from its own mean, the signal's way
  3  price is AT an HTF swing level (within 0.5 HTF ATR)
  4  the HTF trend AGREES (E-133's question, re-asked properly)
  5  the HTF trend OPPOSES (Veer's own model: an H1 downtrend is where the
     M15 buy lives)

Contexts 4 and 5 are deliberately opposites, so one of them being better than
nothing is not a foregone conclusion - if both land on 1.0 the HTF adds nothing
either way, and that is a real answer.
"""
from __future__ import annotations
import os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, ema, Series
from regime import load_plain, resample
from liq_m1 import load as load_spread
from legcatch import legs, features, score


def htf_map(s, factor):
    """For each base bar, the index of the last CLOSED higher-timeframe bar.

    lookahead_off, done by hand: bar i maps to HTF bar (i // factor) - 1, so a
    forming HTF bar is never read. Reading the forming one is the single
    easiest way to fake a multi-timeframe result and it is what most published
    MTF indicators do.
    """
    return [max(0, (i // factor) - 1) for i in range(len(s))]


def htf_ctx(s, factor):
    """The HTF's own premium/discount, stretch, trend and swing levels."""
    H = resample(s, factor)
    AH = watr(H, 14)
    EH = ema(H.c, 50)
    m = htf_map(s, factor)
    n = len(s)
    prem = [0]*n; stre = [0]*n; trend = [0]*n; atlvl = [0]*n

    piv = []
    pv = 3
    for i in range(pv, len(H) - pv):
        if H.h[i] == max(H.h[i-pv:i+pv+1]):
            piv.append((i + pv, H.h[i]))
        if H.l[i] == min(H.l[i-pv:i+pv+1]):
            piv.append((i + pv, H.l[i]))
    lv = {}
    for (b, p) in piv:
        lv.setdefault(b, []).append(p)

    live = []
    seen = 0
    for i in range(n):
        j = m[i]
        if j >= len(H) or j < 60:
            continue
        while seen <= j:
            live.extend(lv.get(seen, []))
            seen += 1
        live = live[-30:]
        a = AH[j]
        if not a or a <= 0:
            continue
        hh, ll = max(H.h[j-60:j]), min(H.l[j-60:j])
        if hh > ll:
            pos = (H.c[j]-ll)/(hh-ll)
            prem[i] = 1 if pos < 0.35 else (-1 if pos > 0.65 else 0)
        if EH[j]:
            d = (H.c[j]-EH[j])/a
            stre[i] = 1 if d <= -1.5 else (-1 if d >= 1.5 else 0)
            trend[i] = 1 if d > 0 else -1
        for p in live:
            if abs(s.c[i] - p) <= 0.5 * a:
                atlvl[i] = 1
                break
    return prem, stre, trend, atlvl


def catcher(s, A, V=None, need=3):
    """E-184's stack, unchanged, so this measures the HTF and nothing else."""
    F = features(s, A, V)
    keep = ["stretched from 50 EMA", "premium / discount",
            "60%+ rejection wick", "equal highs taken", "equal lows taken"]
    if V:
        keep.append("volume x2 at the bar")
    keep = [k for k in keep if k in F]
    n = len(s)
    out = [0]*n
    for i in range(n):
        up = sum(1 for k in keep if F[k][i] > 0)
        dn = sum(1 for k in keep if F[k][i] < 0)
        if up >= need and up > dn:
            out[i] = 1
        elif dn >= need and dn > up:
            out[i] = -1
    return out


def run(label, s, factor, htfName, V=None, need=3, minAtr=2.0):
    A = watr(s, 14)
    lg = legs(s, A, pv=3, minAtr=minAtr)
    base = catcher(s, A, V, need)
    prem, stre, trend, atlvl = htf_ctx(s, factor)
    n = len(s)

    tests = [("the leg catcher alone", base),
             (f"+ {htfName} premium/discount agrees",
              [base[i] if base[i] != 0 and prem[i] == base[i] else 0 for i in range(n)]),
             (f"+ {htfName} stretched the same way",
              [base[i] if base[i] != 0 and stre[i] == base[i] else 0 for i in range(n)]),
             (f"+ at a {htfName} swing level",
              [base[i] if base[i] != 0 and atlvl[i] else 0 for i in range(n)]),
             (f"+ {htfName} trend AGREES",
              [base[i] if base[i] != 0 and trend[i] == base[i] else 0 for i in range(n)]),
             (f"+ {htfName} trend OPPOSES",
              [base[i] if base[i] != 0 and trend[i] == -base[i] else 0 for i in range(n)])]

    print(f"\n  ---- {label} — {len(lg)} legs, catcher needs {need} ----")
    print(f"  {'context':<36}{'fires':>7}{'catches':>9}{'control':>9}{'LIFT':>7}")
    print("  " + "-" * 68)
    for nm, ser in tests:
        rows, _, _ = score({"x": ser}, lg, n, slack=3)
        (_, fired, rate, ctrl, lift, _avg) = rows[0]
        if fired < 30:
            print(f"  {nm:<36}{fired:>7}   too rare to score")
            continue
        star = " <<<" if lift >= 1.60 else ""
        print(f"  {nm:<36}{fired:>7}{100*rate:>8.1f}%{100*ctrl:>8.1f}%"
              f"{lift:>7.2f}{star}")


def main():
    print("=" * 84)
    print("  E-185 — the higher timeframe, layered on E-184's leg catcher")
    print("  lookahead_off by hand: bar i reads HTF bar (i//factor) - 1, never")
    print("  the one still forming.")
    print("=" * 84)

    s1, _ = load_spread("M1")
    V = None
    try:
        import json
        rows = json.load(open("/home/user/signals/data/GOLD_M1_2018.json"))
        rows.sort(key=lambda r: r[0])
        V = [r[7] for r in rows] if len(rows[0]) > 7 else None
    except Exception:
        pass
    run("M1 legs, M15 context", s1, 15, "M15", V=V)
    run("M1 legs, H1 context",  s1, 60, "H1",  V=V)

    h1 = load_plain("GOLD_1h.json")
    run("1h legs, 4h context",  h1, 4, "4h")
    run("1h legs, daily context", h1, 24, "1D")

    g15 = load_plain("GOLD_15m.json")
    run("15m legs, 1h context", g15, 4, "1h")




def targets(label, s, factor, htfName, V=None, need=3, minAtr=2.0):
    """IF the HTF is useless as a FILTER, is it useful as a TARGET?

    Veer's real complaint is not entry quality any more - it is "the good
    signals we did get that could've caught 20-30 points just didn't hold out".
    That is a target question, and his screenshots answer it in pictures: price
    leaves one H1 zone and travels to the next one.

    So: for every leg the catcher fires on, measure how far it actually ran
    against the distance to the NEXT higher-timeframe swing level in that
    direction. If legs reliably reach that level it is a target worth holding
    for; if they stop at some fraction of it, that fraction is the honest
    take-profit and "hold to the next zone" is a story.
    """
    A = watr(s, 14)
    lg = legs(s, A, pv=3, minAtr=minAtr)
    base = catcher(s, A, V, need)
    H = resample(s, factor)
    AH = watr(H, 14)
    m = htf_map(s, factor)
    pv = 3
    lv = {}
    for i in range(pv, len(H) - pv):
        if H.h[i] == max(H.h[i-pv:i+pv+1]):
            lv.setdefault(i + pv, []).append(H.h[i])
        if H.l[i] == min(H.l[i-pv:i+pv+1]):
            lv.setdefault(i + pv, []).append(H.l[i])

    starts = {}
    for (b0, b1, d, size) in lg:
        starts.setdefault(b0, []).append((d, size, b1))

    reach, frac, hits = [], [], 0
    live, seen = [], 0
    for i in range(len(s)):
        j = m[i]
        while seen <= j:
            live.extend(lv.get(seen, []))
            seen += 1
        live = live[-30:]
        if base[i] == 0 or not live:
            continue
        d = base[i]
        got = None
        for k in range(i, min(i + 4, len(s))):
            for (dd, size, b1) in starts.get(k, []):
                if dd == d:
                    got = (k, size, b1)
                    break
            if got:
                break
        if not got:
            continue
        k, size, b1 = got
        a = A[k] if A[k] else 0.0
        if a <= 0:
            continue
        # the next HTF level in the trade's direction, above for a long
        cand = [p for p in live if (p > s.c[i]) if d > 0] if d > 0 \
               else [p for p in live if p < s.c[i]]
        if not cand:
            continue
        lvl = min(cand) if d > 0 else max(cand)
        dist = abs(lvl - s.c[i]) / a
        if dist <= 0.2 or dist > 20:
            continue
        ran = size                      # the leg's own size, in ATR
        reach.append(dist)
        frac.append(ran / dist)
        hits += 1 if ran >= dist else 0

    if len(frac) < 30:
        print(f"\n  {label}: only {len(frac)} measurable, skipping")
        return
    frac.sort()
    print(f"\n  ---- {label}: do caught legs REACH the next {htfName} level? ----")
    print(f"  {len(frac)} caught legs with a level ahead of them")
    print(f"  median distance to that level   {statistics.median(reach):.2f} ATR")
    print(f"  reached it                      {100.0*hits/len(frac):.1f}% of the time")
    print(f"  leg size as a FRACTION of that distance:")
    for q, nm in ((0.25, "25th pct"), (0.5, "median"), (0.75, "75th pct")):
        print(f"      {nm:<10}{frac[int(q*(len(frac)-1))]:.2f}")
    print(f"  => holding for the full level is right {100.0*hits/len(frac):.0f}% of the time;")
    print(f"     the median leg gets {100.0*frac[len(frac)//2]:.0f}% of the way there.")


def main2():
    print("\n" + "=" * 84)
    print("  E-185 PART 2 — the HTF as a TARGET rather than a filter")
    print("=" * 84)
    s1, _ = load_spread("M1")
    V = None
    try:
        import json
        rows = json.load(open("/home/user/signals/data/GOLD_M1_2018.json"))
        rows.sort(key=lambda r: r[0])
        V = [r[7] for r in rows] if len(rows[0]) > 7 else None
    except Exception:
        pass
    targets("M1 legs -> M15 levels", s1, 15, "M15", V=V)
    targets("M1 legs -> H1 levels", s1, 60, "H1", V=V)
    targets("15m legs -> 1h levels", load_plain("GOLD_15m.json"), 4, "1h")
    targets("1h legs -> 4h levels", load_plain("GOLD_1h.json"), 4, "4h")


if __name__ == "__main__":
    main()
    main2()

"""
E-178 — EVERY ENTRY GATE, JUDGED BY THE RULE THIS REPO ALREADY HAS.

Veer, three times now: "entries are just shit", "we catch every trend not ever
volume candle", "only errors in entry exit now youve missed it all up and not
improved the errors". He is right that I kept answering with research instead of
looking at the entry path. So I looked at it, and TryEntry() in
SuperTrendSniper.mq5 has ELEVEN separate ways to refuse a valid flip and three
more to shrink it:

    HasPending, RiskAllowsEntry, DEMA slope, ADX ceiling, no-fade candle,
    re-entry cooldown, StackAllows, chop efficiency, chop flip count, session,
    cost gate, no-room-to-the-level      ... then TrendRisk, RegimeSize,
    MidRange all cut the lot size, and MidRange can refuse outright.

That is the mechanical explanation for "we miss trends": a trend that begins on
a bar where any one of eleven conditions is unhappy is simply never entered.

CLAUDE.md, the standing rule: **a filter earns its place only if the trades it
REFUSES are worse than the ones it allows.** Not one of these has been measured
that way on the market Veer actually trades. This file measures all of them, on
2024-2026 gold, per clock.

Read the REFUSED column, not the TAKEN column. A gate that refuses trades worth
MORE than it keeps is costing money on every signal it blocks, and several of
these were carried over from measurements on 15m data from a different era.

WHAT THIS CANNOT DO: there is no recent M1 gold in this repo, so M1 is absent
below. Veer trades M1. Exporting recent M1 from MT5 is the one thing that would
let these same gates be settled on the clock that matters.
"""
from __future__ import annotations
import os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, ema
from supertrend_rescue import st_state
from st_churn import flips
from regime import load_plain, resample, dema_of

COST_ATR = 0.02


def adx(s, n=14):
    """Wilder ADX, the same one the EA reads."""
    L = len(s)
    tr, pdm, ndm = [0.0]*L, [0.0]*L, [0.0]*L
    for i in range(1, L):
        up, dn = s.h[i]-s.h[i-1], s.l[i-1]-s.l[i]
        pdm[i] = up if (up > dn and up > 0) else 0.0
        ndm[i] = dn if (dn > up and dn > 0) else 0.0
        tr[i] = max(s.h[i]-s.l[i], abs(s.h[i]-s.c[i-1]), abs(s.l[i]-s.c[i-1]))
    def wil(v):
        out = [None]*L
        acc = 0.0
        for i in range(1, L):
            acc = v[i] if i <= n else acc - acc/n + v[i]
            if i >= n:
                out[i] = acc
        return out
    TR, PD, ND = wil(tr), wil(pdm), wil(ndm)
    dx = [None]*L
    for i in range(L):
        if TR[i] and TR[i] > 0:
            p, m = 100*PD[i]/TR[i], 100*ND[i]/TR[i]
            dx[i] = 100*abs(p-m)/max(p+m, 1e-9)
    out, acc = [None]*L, 0.0
    cnt = 0
    for i in range(L):
        if dx[i] is None:
            continue
        cnt += 1
        acc = dx[i] if cnt <= n else acc - acc/n + dx[i]
        if cnt >= n:
            out[i] = acc/n if cnt == n else acc/n
    return out


def eff(s, i, n):
    if i < n:
        return 0.5
    seg = s.c[i-n:i+1]
    path = sum(abs(seg[k]-seg[k-1]) for k in range(1, len(seg)))
    return abs(seg[-1]-seg[0])/path if path > 0 else 0.0


def rangepos(s, i, n=100):
    if i < n:
        return 0.5
    hi, lo = max(s.h[i-n:i]), min(s.l[i-n:i])
    return (s.c[i]-lo)/(hi-lo) if hi > lo else 0.5


def population(s, dLen, stopAtr=2.0):
    """Every SuperTrend flip with its outcome and the state of every gate at
    the moment it fired. Outcome = flip-in / opposite-flip-out, in ATR."""
    d, _, _ = st_state(s, 7, 1.2)
    A = watr(s, 14)
    D = dema_of(s.c, dLen)
    AD = adx(s)
    fl = flips(s, d)
    rows = []
    for k, (i, t) in enumerate(fl):
        if i + 1 >= len(s) or i < 60:
            continue
        a = A[i]
        if not a or a <= 0 or D[i] is None or D[i-2] is None:
            continue
        j = fl[k+1][0] if k+1 < len(fl) else len(s)-1
        r = t*(s.o[min(j+1, len(s)-1)] - s.o[i+1])/a - COST_ATR

        slope = D[i]-D[i-2]
        demaOk = (slope >= 0) if t > 0 else (slope <= 0)
        adxv = AD[i] if AD[i] else 0.0
        # no-fade: a >=3 ATR candle the OTHER way in the last 3 bars
        fade = False
        for b in range(1, 4):
            if i-b < 0:
                break
            rng = s.h[i-b]-s.l[i-b]
            if rng >= 3.0*a:
                idir = 1 if s.c[i-b] > s.o[i-b] else -1
                if idir != t:
                    fade = True
        # re-entry cooldown: same direction as the previous flip within 3 bars
        cool = False
        if k > 0:
            pi, pt = fl[k-1]
            if pt == t and i - pi < 3:
                cool = True
        nflip = sum(1 for (x, _) in fl if i-20 <= x < i)
        rows.append(dict(r=r, dema=demaOk, adx=adxv, fade=fade, cool=cool,
                         er=eff(s, i, 50), nflip=nflip, rp=rangepos(s, i),
                         t=t))
    return rows


def judge(name, rows, keep):
    took = [x["r"] for x in rows if keep(x)]
    ref  = [x["r"] for x in rows if not keep(x)]
    if len(took) < 20 or len(ref) < 10:
        return None
    mt, mr = statistics.fmean(took), statistics.fmean(ref)
    tt = mt/(statistics.pstdev(took)/len(took)**0.5)
    return (name, len(took), mt, tt, len(ref), mr, mr < mt)


def report(label, s, dLen):
    rows = population(s, dLen)
    if len(rows) < 60:
        print(f"\n  {label}: only {len(rows)} signals, not enough to judge")
        return
    allm = statistics.fmean(x["r"] for x in rows)
    print(f"\n  ---- {label} — {len(rows)} signals, ungated {allm:+.3f} ATR/trade ----")
    print(f"  {'gate (as the EA ships it)':<34}{'kept':>6}{'ATR/trd':>9}{'t':>7}"
          f"{'refused':>9}{'ATR/trd':>9}   earns its place?")
    print("  " + "-" * 96)
    tests = [
        ("DEMA slope must agree",        lambda x: x["dema"]),
        ("ADX <= 35 (off by default)",   lambda x: x["adx"] <= 35.0),
        ("no fade after a 3 ATR candle", lambda x: not x["fade"]),
        ("re-entry cooldown 3 bars",     lambda x: not x["cool"]),
        ("efficiency >= 0.08 (off)",     lambda x: x["er"] >= 0.08),
        ("fewer than 5 flips in 20 (off)", lambda x: x["nflip"] < 5),
        ("skip mid-range 0.35-0.70",     lambda x: not (0.35 <= x["rp"] <= 0.70)),
    ]
    for nm, fn in tests:
        v = judge(nm, rows, fn)
        if not v:
            print(f"  {nm:<34}   too few on one side to judge")
            continue
        (_, nk, mk, tk, nr, mr, ok) = v
        print(f"  {nm:<34}{nk:>6}{mk:>+9.3f}{tk:>+7.2f}{nr:>9}{mr:>+9.3f}"
              f"   {'YES' if ok else 'NO - it refuses the BETTER trades'}")


def main():
    print("=" * 108)
    print("  E-178 — every entry gate against CLAUDE.md's own rule:")
    print("  a filter earns its place ONLY if the trades it REFUSES are worse"
          " than the ones it allows.")
    print("=" * 108)
    h1 = load_plain("GOLD_1h.json")
    g15 = load_plain("GOLD_15m.json")
    report("2024-2026  1h", h1, 200)
    report("2024-2026  4h", resample(h1, 4), 200)
    report("2026 Jun-Aug  15m", g15, 200)
    print("\n  M1 IS ABSENT: there is no recent M1 gold in this repo, and M1 is"
          " the clock Veer trades.")




def oos():
    """The same gates, chosen on the first half and judged on the second.

    E-150's rule, and E-177's finding that this market's halves are very
    different, together mean a gate that looks good over the whole 2024-2026
    range may only have looked good in the trending half. A gate is only worth
    changing a default for if its refusals are worse in BOTH halves - that is a
    much harder test than "worse overall" and it is the right one.
    """
    from engine import Series
    print("\n" + "=" * 108)
    print("  E-178 OUT OF SAMPLE — a gate must refuse the worse trades in BOTH"
          " halves, not just overall")
    print("=" * 108)
    tests = [("DEMA slope",            lambda x: x["dema"]),
             ("ADX <= 35",             lambda x: x["adx"] <= 35.0),
             ("efficiency >= 0.08",    lambda x: x["er"] >= 0.08),
             ("skip mid-range",        lambda x: not (0.35 <= x["rp"] <= 0.70))]
    for label, s, dLen in (("2024-2026 1h", load_plain("GOLD_1h.json"), 200),
                           ("2026 15m", load_plain("GOLD_15m.json"), 200)):
        n = len(s.c) // 2
        a = Series(s.ts[:n], s.o[:n], s.h[:n], s.l[:n], s.c[:n])
        b = Series(s.ts[n:], s.o[n:], s.h[n:], s.l[n:], s.c[n:])
        ra, rb = population(a, dLen), population(b, dLen)
        print(f"\n  ---- {label} ----")
        print(f"  {'gate':<22}{'H1 kept':>9}{'H1 ref':>9}{'  ':>2}"
              f"{'H2 kept':>9}{'H2 ref':>9}   verdict")
        print("  " + "-" * 84)
        for nm, fn in tests:
            va, vb = judge(nm, ra, fn), judge(nm, rb, fn)
            if not (va and vb):
                print(f"  {nm:<22}   too few on one side in one half")
                continue
            both = va[6] and vb[6]
            print(f"  {nm:<22}{va[2]:>+9.3f}{va[5]:>+9.3f}  "
                  f"{vb[2]:>+9.3f}{vb[5]:>+9.3f}   "
                  f"{'KEEP - worse in both halves' if both else 'NOT RELIABLE - only one half'}")


if __name__ == "__main__":
    main()
    oos()

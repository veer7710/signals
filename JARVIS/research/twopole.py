"""
E-180 — THE TWO-POLE OSCILLATOR. Veer: "where's two pole oscillator gone from
super trend sniper".

It never went anywhere: I never put it in. His original XAUUSD_QUAD v19.18 names
THREE pillars - Supertrend + DEMA + Two-Pole - and the SuperTrendSniper I built
has two. That is a regression from his own EA and he is right to notice.

Before porting it back, the same test everything else gets: does it refuse the
worse trades? Ported exactly from his v19.18 TwoPoleValue():

    dev    = close - SMA(close, len)
    p1     = EMA(dev, alpha),  p2 = EMA(p1, alpha),  alpha = 2/(smooth+1)
    raw    = p2 / stdev(close, len)
    tp     = SMA(raw, 3)

and the three reads his EA actually uses:
    AGREES   tp[0] > tp[1]                                  (for a long)
    OPPOSES  tp[0] - tp[1] < -vetoSlope                     (a VETO, not a demand)
    LED      tp rising, tp[1] <= tp[2], and tp still < 0.2   (the turn itself)

His v17.98 note is the interesting one and it is worth testing rather than
assuming: demanding a 20-length DOUBLE-SMOOTHED oscillator has ALREADY turned at
the birth of a flip is asking the slowest reader in the file to be the earliest,
so AGREES may be systematically late where OPPOSES-as-veto is not.
"""
from __future__ import annotations
import os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr
from supertrend_rescue import st_state
from st_churn import flips
from regime import load_plain, resample, dema_of
from gates import COST_ATR


def two_pole(c, length=20, smooth=4.0):
    """His exact recursion, bar by bar. Returns the SMA(3) series."""
    n = len(c)
    raw = [None]*n
    alpha = 2.0/(smooth+1.0)
    p1 = p2 = None
    for i in range(n):
        if i < length:
            continue
        w = c[i-length+1:i+1]
        sma = sum(w)/length
        var = sum((x-sma)**2 for x in w)/length
        sd = var**0.5
        dev = c[i]-sma
        if p1 is None:
            p1 = dev; p2 = p1
        else:
            p1 = p1 + alpha*(dev-p1)
            p2 = p2 + alpha*(p1-p2)
        raw[i] = (p2/sd) if sd > 0 else 0.0
    tp = [None]*n
    for i in range(n):
        if i >= 2 and None not in (raw[i], raw[i-1], raw[i-2]):
            tp[i] = (raw[i]+raw[i-1]+raw[i-2])/3.0
    return tp


def population(s, dLen=200, veto=0.02):
    d, _, _ = st_state(s, 7, 1.2)
    A = watr(s, 14)
    D = dema_of(s.c, dLen)
    TP = two_pole(s.c)
    fl = flips(s, d)
    rows = []
    for k, (i, t) in enumerate(fl):
        if i+1 >= len(s) or i < 60:
            continue
        a = A[i]
        if not a or a <= 0 or D[i] is None or D[i-2] is None:
            continue
        if None in (TP[i], TP[i-1], TP[i-2]):
            continue
        j = fl[k+1][0] if k+1 < len(fl) else len(s)-1
        r = t*(s.o[min(j+1, len(s)-1)] - s.o[i+1])/a - COST_ATR
        slope = D[i]-D[i-2]
        demaOk = (slope >= 0) if t > 0 else (slope <= 0)
        dtp = TP[i]-TP[i-1]
        agrees = (dtp > 0) if t > 0 else (dtp < 0)
        opposes = (dtp < -veto) if t > 0 else (dtp > veto)
        led = ((dtp > 0 and TP[i-1] <= TP[i-2] and TP[i] < 0.2) if t > 0
               else (dtp < 0 and TP[i-1] >= TP[i-2] and TP[i] > -0.2))
        rows.append(dict(r=r, dema=demaOk, agrees=agrees, opposes=opposes,
                         led=led))
    return rows


def judge(rows, keep):
    took = [x["r"] for x in rows if keep(x)]
    ref = [x["r"] for x in rows if not keep(x)]
    if len(took) < 20 or len(ref) < 10:
        return None
    mt, mr = statistics.fmean(took), statistics.fmean(ref)
    return (len(took), mt, mt/(statistics.pstdev(took)/len(took)**0.5),
            len(ref), mr, mr < mt)


def report(label, s):
    rows = population(s)
    if len(rows) < 60:
        print(f"\n  {label}: {len(rows)} signals, too few")
        return
    base = [x["r"] for x in rows if x["dema"]]
    print(f"\n  ---- {label} — {len(rows)} flips, DEMA-only baseline "
          f"{statistics.fmean(base):+.3f} on {len(base)} ----")
    print(f"  {'two-pole read, ON TOP of the DEMA filter':<44}{'kept':>6}"
          f"{'ATR/trd':>9}{'t':>7}{'refused':>9}{'ATR/trd':>9}   earns it?")
    print("  " + "-" * 100)
    tests = [("AGREES: it must already be turning", lambda x: x["dema"] and x["agrees"]),
             ("VETO: refuse only if moving AGAINST", lambda x: x["dema"] and not x["opposes"]),
             ("LED: the turn itself, still modest", lambda x: x["dema"] and x["led"])]
    for nm, fn in tests:
        # judge only within the DEMA-passing population, which is what shipping
        # it on top of the DEMA filter would actually do
        sub = [x for x in rows if x["dema"]]
        v = judge(sub, fn)
        if not v:
            print(f"  {nm:<44}   too few on one side")
            continue
        nk, mk, tk, nr, mr, ok = v
        print(f"  {nm:<44}{nk:>6}{mk:>+9.3f}{tk:>+7.2f}{nr:>9}{mr:>+9.3f}"
              f"   {'YES' if ok else 'NO - refuses the BETTER trades'}")


def main():
    print("=" * 112)
    print("  E-180 — the Two-Pole Oscillator, the third pillar of his own v19.18"
          " that I never ported")
    print("=" * 112)
    h1 = load_plain("GOLD_1h.json")
    report("2024-2026  1h", h1)
    report("2024-2026  4h", resample(h1, 4))
    report("2026 Jun-Aug  15m", load_plain("GOLD_15m.json"))




def oos():
    """Chosen on the first half, judged on the second - E-150's rule."""
    from engine import Series
    print("\n" + "=" * 100)
    print("  E-180 OUT OF SAMPLE — the read must refuse the worse trades in"
          " BOTH halves")
    print("=" * 100)
    tests = [("AGREES", lambda x: x["dema"] and x["agrees"]),
             ("VETO",   lambda x: x["dema"] and not x["opposes"]),
             ("LED",    lambda x: x["dema"] and x["led"])]
    for label, s in (("2024-2026 1h", load_plain("GOLD_1h.json")),
                     ("2026 15m", load_plain("GOLD_15m.json"))):
        n = len(s.c)//2
        a = Series(s.ts[:n], s.o[:n], s.h[:n], s.l[:n], s.c[:n])
        b = Series(s.ts[n:], s.o[n:], s.h[n:], s.l[n:], s.c[n:])
        ra = [x for x in population(a) if x["dema"]]
        rb = [x for x in population(b) if x["dema"]]
        print(f"\n  ---- {label} ----")
        print(f"  {'read':<10}{'H1 kept':>9}{'H1 ref':>9}   {'H2 kept':>9}"
              f"{'H2 ref':>9}   verdict")
        print("  " + "-" * 74)
        for nm, fn in tests:
            va, vb = judge(ra, fn), judge(rb, fn)
            if not (va and vb):
                print(f"  {nm:<10}   too few on one side in one half")
                continue
            both = va[5] and vb[5]
            print(f"  {nm:<10}{va[1]:>+9.3f}{va[4]:>+9.3f}   {vb[1]:>+9.3f}"
                  f"{vb[4]:>+9.3f}   "
                  f"{'KEEP - holds in both' if both else 'one half only'}")


if __name__ == "__main__":
    main()
    oos()

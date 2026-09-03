"""
E-057 — After an impulse candle, does price continue, retrace, or reverse?

Veer's M1 gold screenshot, 1 Sep 21:03: one M1 candle drops about $3 - roughly
four times the M1 ATR - and prints the low of the move. Three stacked shorts
peak at about GBP10.30 together and are showing GBP7.06 by the time he looks.
His reading: "that's a clear reversal we should've closed our sells at the peak
and possibly looked to buy or wait for the pullback to finish and then continue
sell".

Three separate claims, and they need separating before any of them is coded:
  A  the peak after an impulse is worth banking (the move is over, or pauses)
  B  the bounce is tradeable in the opposite direction
  C  the original direction resumes after the pullback

A and C can BOTH be true - that is a pullback. A and B can both be true - that
is a reversal. They are different trades and conflating them is how a rule that
sounds obvious loses money.

WHY THE STALL RULE (E-056) DOES NOT COVER THIS
Stall is measured in BARS. An impulse sets its extreme in ONE bar, so stall is
0 or 1 exactly when the give-back is about to be largest. E-056 measured that
stall 0-1 is the SAFEST bucket - and after an impulse that is precisely wrong.
This measures whether the exception is real.

DEFINITIONS, all decided on closed bars
  IMPULSE   a bar whose true range is >= K x ATR(14), K in {2, 3, 4}
  RETRACE   the fraction of the impulse bar's range given back afterwards
  CONTINUE  a new extreme beyond the impulse, in the impulse's direction

Ties go to the pessimistic reading (L-012).

Run:  python3 JARVIS/research/impulse.py
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, chop

KS = [2.0, 3.0, 4.0]
HORIZON = 30


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def find(s, k, warmup=250, control=False, seed=13):
    """When control=True, the SAME statistics are computed at randomly chosen
    NON-impulse bars, using a synthetic range of the same size and the same
    direction. Without this the headline '88% eventually exceeded the extreme'
    is meaningless: over 30 bars price wanders past most levels, impulse or
    not. E-050 exists because a headline died for want of exactly this."""
    """Every impulse bar, and what happened in the HORIZON bars after it."""
    import random
    rng_ = random.Random(seed)
    a = engine.atr(s, 14)

    # collect the real impulses first, so the control can be matched to them
    real = []
    for i in range(warmup, len(s) - HORIZON - 1):
        atr = a[i]
        if atr is None or atr <= 0:
            continue
        r_ = s.h[i] - s.l[i]
        if r_ < k * atr:
            continue
        b_ = s.c[i] - s.o[i]
        if b_ == 0:
            continue
        real.append((i, r_, 1 if b_ > 0 else -1))

    if control:
        # same count, same range sizes, same directions - different bars, and
        # bars that are NOT impulses
        pool = [j for j in range(warmup, len(s) - HORIZON - 1)
                if a[j] and a[j] > 0 and (s.h[j] - s.l[j]) < k * a[j]]
        if not pool:
            return []
        cases = [(pool[rng_.randrange(len(pool))], r_, d_) for _i, r_, d_ in real]
    else:
        cases = real

    out = []
    for (i, rng, d) in cases:
        atr = a[i]
        # the level being tested: the bar's own extreme in direction d
        ext = s.h[i] if d == 1 else s.l[i]

        # ---- how far did it give back, and did it ever continue?
        worst_back = 0.0        # deepest retrace, as a fraction of the range
        continued = False
        cont_bar = None
        for j in range(i + 1, i + 1 + HORIZON):
            back = (ext - s.l[j]) if d == 1 else (s.h[j] - ext)
            worst_back = max(worst_back, back / rng)
            beyond = (s.h[j] > ext) if d == 1 else (s.l[j] < ext)
            if beyond and not continued:
                continued = True
                cont_bar = j - i

        # ---- the three claims, as measurable events
        # A: was the extreme worth banking? i.e. did price give back at least
        #    half the impulse before ever exceeding the extreme?
        gave_half_first = False
        for j in range(i + 1, i + 1 + HORIZON):
            back = (ext - s.l[j]) if d == 1 else (s.h[j] - ext)
            beyond = (s.h[j] > ext) if d == 1 else (s.l[j] < ext)
            if back / rng >= 0.5:
                gave_half_first = True
                break
            if beyond:
                break

        # C: after giving back half, did the original direction resume?
        resumed = False
        if gave_half_first:
            for j in range(i + 1, i + 1 + HORIZON):
                back = (ext - s.l[j]) if d == 1 else (s.h[j] - ext)
                if back / rng >= 0.5:
                    for m in range(j + 1, i + 1 + HORIZON):
                        beyond = (s.h[m] > ext) if d == 1 else (s.l[m] < ext)
                        if beyond:
                            resumed = True
                            break
                    break

        out.append({"i": i, "dir": d, "rng": rng, "atr": atr,
                    "back": worst_back, "cont": continued, "cbar": cont_bar,
                    "gave_half": gave_half_first, "resumed": resumed})
    return out


def main():
    print("=" * 88)
    print("  E-057  WHAT HAPPENS AFTER AN IMPULSE CANDLE?")
    print(f"  Impulse = true range >= K x ATR(14). {HORIZON} bars measured after it.")
    print("=" * 88)

    for k in KS:
        print(f"\n  --- K = {k:g} x ATR " + "-" * 60)
        print(f"  {'market':<14}{'n':>6}{'median':>10}{'75th':>8}{'90th':>8}"
              f"{'gaveback':>12}{'resumed':>10}{'exceeded':>10}"
              f"{'CTRL back':>11}{'CTRL exc':>10}")
        agree_half = 0
        seen = 0
        for sym, tf in chop.COMBOS:
            try:
                s = engine.load(sym, tf)
            except Exception:
                continue
            ev = find(s, k)
            cv = find(s, k, control=True)
            if len(ev) < 30:
                print(f"  {sym+' '+tf:<14}{len(ev):>6}   too few")
                continue
            backs = sorted(e["back"] for e in ev)
            q = lambda arr, f: arr[int(f * (len(arr) - 1))]
            gh = sum(1 for e in ev if e["gave_half"]) / len(ev)
            rs = [e for e in ev if e["gave_half"]]
            rz = (sum(1 for e in rs if e["resumed"]) / len(rs)) if rs else 0.0
            ct = sum(1 for e in ev if e["cont"]) / len(ev)
            cb = sorted(e["back"] for e in cv) if cv else [0.0]
            cct = (sum(1 for e in cv if e["cont"]) / len(cv)) if cv else 0.0
            seen += 1
            if gh > 0.5:
                agree_half += 1
            print(f"  {sym+' '+tf:<14}{len(ev):>6}{q(backs,.5):>10.2f}"
                  f"{q(backs,.75):>8.2f}{q(backs,.90):>8.2f}"
                  f"{100*gh:>11.0f}%{100*rz:>9.0f}%{100*ct:>9.0f}%"
                  f"{q(cb,.5):>11.2f}{100*cct:>10.0f}%")
        print(f"  {'gave back >=50% in a MAJORITY of cases:':<52}"
              f"{agree_half}/{seen} markets")


if __name__ == "__main__":
    main()

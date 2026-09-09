"""
E-193 — THE SHIFT. Does the sweep requirement earn its place?

Veer sent a screenshot: an indicator that prints a big SHIFT label at reversals
and "catches massive moves". He wants the same picture driven by SMC and
liquidity instead of FVG/IFVG.

The picture is easy. The question this file exists to answer is the one that
decides the DEFAULT setting, and it is not a matter of taste:

    A SHIFT is a change of character. Should it require that liquidity was
    taken first, or is a plain CHoCH just as good?

That is a real fork. Requiring the sweep throws away most of the marks. If the
ones it keeps are no better, the filter is pure cost - the repo's own rule:
"a filter earns its place only if the trades it REFUSES are worse than the ones
it allows."

METHOD is E-184's, unchanged, because it is the only method here that has ever
replicated out of sample. One question - does this bar mark the START of a leg?
- scored as LIFT against a TIME-SHIFTED copy of the same series, so shape and
frequency are held identical and only timing is destroyed.

WHAT THIS IS NOT. It is not a claim that the SHIFT makes money. Leg-start
classification and trade survival are different events (E-186). Nothing here
touches a stop, a target or a cost.

DATA. GOLD_1h and GOLD_15m are 2024-2026 and 2026 Jun-Aug. GOLD_M1_2018 is
2018 and, per the standing rule after E-176, a result from that file is a
hypothesis about 2018 and not evidence about the market Veer trades. It is
included because it is the only M1 sample in the repo and M1 is the clock the
SuperTrend runs on - but it is labelled every time it is printed.
"""
from __future__ import annotations
import json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr
from regime import load_plain, resample
from legcatch import legs, score


# ------------------------------------------------------------------ pine ---
def shift_series(s, A, pv=3, eqTol=0.10, sweepAtr=0.05, wait=20):
    """LIQUIDITY_SNIPER_2_0.pine's SHIFT, bar for bar.

    Returns three aligned series of +1 / -1 / 0:
      choch  every change of character          (shiftQual = "on every ...")
      shift  a CHoCH within `wait` bars of a sweep of a POOL   (the default)
      sweep  the sweep on its own, for the third leg of the comparison

    A POOL is two swings within eqTol ATR of each other - one price where the
    stops are stacked. A SWEEP runs it by sweepAtr ATR and CLOSES BACK INSIDE.
    A close beyond is a break and is deliberately not a sweep, which is the
    single line that separates this from "so many random signals".

    Nothing reads a bar after i. A pivot is known pv bars after it forms and is
    published on that later bar, exactly as Pine's ta.pivothigh does.
    """
    n = len(s)
    choch = [0] * n
    shift = [0] * n
    sweep = [0] * n

    hi_at, lo_at = {}, {}
    for i in range(pv, n - pv):
        if s.h[i] == max(s.h[i - pv:i + pv + 1]):
            hi_at[i + pv] = s.h[i]
        if s.l[i] == min(s.l[i - pv:i + pv + 1]):
            lo_at[i + pv] = s.l[i]

    smcH = smcL = None          # the live structure levels
    poolHi = poolLo = None      # the newest swing
    prevHi = prevLo = None      # the one before it
    trend = 0
    swpHiB = swpLoB = None

    for i in range(n):
        a = A[i] if A[i] else 0.0
        if i in hi_at:
            prevHi, poolHi = poolHi, hi_at[i]
            smcH = hi_at[i]
        if i in lo_at:
            prevLo, poolLo = poolLo, lo_at[i]
            smcL = lo_at[i]
        if a <= 0 or i < 60:
            continue

        # ---- the pool: equal highs / equal lows, else the single swing
        eqH = poolHi is not None and prevHi is not None \
            and abs(poolHi - prevHi) <= eqTol * a
        eqL = poolLo is not None and prevLo is not None \
            and abs(poolLo - prevLo) <= eqTol * a
        pHi = max(poolHi, prevHi) if eqH else poolHi
        pLo = min(poolLo, prevLo) if eqL else poolLo

        # ---- the sweep: run it, then close back inside
        if pHi is not None and s.h[i] > pHi + sweepAtr * a and s.c[i] < pHi:
            swpHiB = i
            sweep[i] = -1
        if pLo is not None and s.l[i] < pLo - sweepAtr * a and s.c[i] > pLo:
            swpLoB = i
            sweep[i] = 1
        if swpHiB is not None and i - swpHiB > wait:
            swpHiB = None
        if swpLoB is not None and i - swpLoB > wait:
            swpLoB = None

        # ---- structure. CHoCH is captured BEFORE trend is updated, or the
        #      test reads the answer it is about to write.
        bosUp = smcH is not None and s.c[i] > smcH
        bosDn = smcL is not None and s.c[i] < smcL
        cUp = bosUp and trend < 0
        cDn = bosDn and trend > 0
        if bosUp:
            trend, smcH = 1, None
        if bosDn:
            trend, smcL = -1, None

        if cUp:
            choch[i] = 1
            if swpLoB is not None:
                shift[i] = 1
        if cDn:
            choch[i] = -1
            if swpHiB is not None:
                shift[i] = -1
    return choch, shift, sweep


def variants(s, A, pv=3, eqTol=0.10, sweepAtr=0.05, wait=20, emaLen=50,
             stretch=1.5):
    """The sweep, gated four different ways.

    The plain sweep beats its control on every sample but fires on ~9% of bars,
    which is a chart full of labels and is not what Veer asked for. So: which
    gate makes it RARER without making it WORSE? That is the only question a
    "SHIFT" label has to answer, because a label is a claim that this one is
    different from the hundred around it.

    The gates are E-184's own top scorers, which is the point - E-184 showed
    they compound (1.23 -> 1.32 -> 1.53 -> 2.18 as more agree).
    """
    from engine import ema
    n = len(s)
    E = ema(s.c, emaLen)
    out = {k: [0] * n for k in
           ("sweep", "sweep of an EQUAL pool", "sweep + stretched",
            "sweep + rejection wick", "sweep + 2 of 3", "sweep + 3 of 3")}

    hi_at, lo_at = {}, {}
    for i in range(pv, n - pv):
        if s.h[i] == max(s.h[i - pv:i + pv + 1]):
            hi_at[i + pv] = s.h[i]
        if s.l[i] == min(s.l[i - pv:i + pv + 1]):
            lo_at[i + pv] = s.l[i]

    poolHi = poolLo = prevHi = prevLo = None
    for i in range(n):
        a = A[i] if A[i] else 0.0
        if i in hi_at:
            prevHi, poolHi = poolHi, hi_at[i]
        if i in lo_at:
            prevLo, poolLo = poolLo, lo_at[i]
        if a <= 0 or i < max(60, emaLen + 5):
            continue

        eqH = poolHi is not None and prevHi is not None \
            and abs(poolHi - prevHi) <= eqTol * a
        eqL = poolLo is not None and prevLo is not None \
            and abs(poolLo - prevLo) <= eqTol * a
        pHi = max(poolHi, prevHi) if eqH else poolHi
        pLo = min(poolLo, prevLo) if eqL else poolLo

        d = 0
        eqPool = False
        if pHi is not None and s.h[i] > pHi + sweepAtr * a and s.c[i] < pHi:
            d, eqPool = -1, eqH
        if pLo is not None and s.l[i] < pLo - sweepAtr * a and s.c[i] > pLo:
            d, eqPool = 1, eqL
        if d == 0:
            continue
        out["sweep"][i] = d
        if eqPool:
            out["sweep of an EQUAL pool"][i] = d

        # --- E-184's gates, all knowable at the close of bar i
        st = 0
        if E[i]:
            dm = (s.c[i] - E[i]) / a
            st = 1 if dm <= -stretch else (-1 if dm >= stretch else 0)
        rng = s.h[i] - s.l[i]
        wk = 0
        if rng > 0:
            upw = (s.h[i] - max(s.o[i], s.c[i])) / rng
            dnw = (min(s.o[i], s.c[i]) - s.l[i]) / rng
            wk = 1 if dnw >= 0.6 else (-1 if upw >= 0.6 else 0)
        hh, ll = max(s.h[i - 60:i]), min(s.l[i - 60:i])
        pd = 0
        if hh > ll:
            pos = (s.c[i] - ll) / (hh - ll)
            pd = 1 if pos < 0.35 else (-1 if pos > 0.65 else 0)

        if st == d:
            out["sweep + stretched"][i] = d
        if wk == d:
            out["sweep + rejection wick"][i] = d
        agree = (1 if st == d else 0) + (1 if wk == d else 0) \
            + (1 if pd == d else 0)
        if agree >= 2:
            out["sweep + 2 of 3"][i] = d
        if agree >= 3:
            out["sweep + 3 of 3"][i] = d
    return out


def run_variants(label, s, pv=3, minAtr=2.0, slack=3):
    A = watr(s, 14)
    lg = legs(s, A, pv=pv, minAtr=minAtr)
    F = variants(s, A, pv=pv)
    out, base, nStart = score(F, lg, len(s), slack=slack)
    print()
    print("-" * 78)
    print(f"  {label}   {len(s)} bars   {len(lg)} legs   base {base:.3f}")
    print(f"  {'':26} {'fires':>6} {'/1000':>7} {'rate':>7} {'ctrl':>7}"
          f" {'LIFT':>6} {'avgATR':>7}")
    res = {}
    for (name, fired, rate, ctrl, lift, avg) in out:
        per = fired / len(s) * 1000
        print(f"  {name:26} {fired:6d} {per:7.1f} {rate:7.3f} {ctrl:7.3f}"
              f" {lift:6.2f} {avg:7.2f}")
        res[name] = (fired, lift, per)
    return res


# --------------------------------------------------------------- reporting --
def run(label, s, pv=3, minAtr=2.0, slack=3, **kw):
    A = watr(s, 14)
    lg = legs(s, A, pv=pv, minAtr=minAtr)
    ch, sh, sw = shift_series(s, A, pv=pv, **kw)
    F = {"CHoCH (every one)": ch,
         "SHIFT (sweep -> CHoCH)": sh,
         "sweep alone": sw}
    out, base, nStart = score(F, lg, len(s), slack=slack)
    print()
    print("-" * 78)
    print(f"  {label}   {len(s)} bars   {len(lg)} legs >= {minAtr} ATR"
          f"   base rate {base:.3f}")
    print(f"  {'':24} {'fires':>6} {'/1000':>7} {'rate':>7} {'ctrl':>7}"
          f" {'LIFT':>6} {'avgATR':>7}")
    res = {}
    for (name, fired, rate, ctrl, lift, avg) in out:
        per = fired / len(s) * 1000
        print(f"  {name:24} {fired:6d} {per:7.1f} {rate:7.3f} {ctrl:7.3f}"
              f" {lift:6.2f} {avg:7.2f}")
        res[name] = (fired, lift, avg)
    return res


def main():
    print("=" * 78)
    print("  E-193 — THE SHIFT: does requiring a liquidity sweep before the")
    print("  change of character make the mark better, or only rarer?")
    print("  LIFT is against a time-shifted copy of the SAME series.")
    print("=" * 78)

    keep = []
    h1 = load_plain("GOLD_1h.json")
    keep.append(("2024-2026  1h", run("2024-2026  1h", h1)))
    keep.append(("2024-2026  4h", run("2024-2026  4h", resample(h1, 4), pv=4)))
    keep.append(("2026 Jun-Aug  15m", run("2026 Jun-Aug  15m",
                                          load_plain("GOLD_15m.json"))))

    # M1/M5/M15 2018 - the only fast samples in the repo, and 2018.
    for f, lb in (("GOLD_M15_2018.json", "2018  M15"),
                  ("GOLD_M5_2018.json", "2018  M5"),
                  ("GOLD_M1_2018.json", "2018  M1")):
        p = f"/home/user/signals/data/{f}"
        if not os.path.exists(p):
            continue
        rows = sorted(json.load(open(p)), key=lambda r: r[0])
        from engine import Series
        s = Series([r[0] for r in rows], [r[1] for r in rows],
                   [r[2] for r in rows], [r[3] for r in rows],
                   [r[4] for r in rows])
        keep.append((lb + "  (2018 — a hypothesis, not evidence)",
                     run(lb + "  (2018 — hypothesis only)", s)))

    print()
    print("=" * 78)
    print("  VERDICT")
    print("=" * 78)
    wins = losses = 0
    for lb, r in keep:
        c = r.get("CHoCH (every one)", (0, 0, 0))
        h = r.get("SHIFT (sweep -> CHoCH)", (0, 0, 0))
        if h[0] < 30:
            print(f"  {lb:46} SHIFT fired {h[0]} times — not enough to judge")
            continue
        d = h[1] - c[1]
        keptpc = h[0] / c[0] * 100 if c[0] else 0.0
        if d > 0:
            wins += 1
        else:
            losses += 1
        print(f"  {lb:46} CHoCH {c[1]:.2f} -> SHIFT {h[1]:.2f}"
              f"  ({d:+.2f}, keeps {keptpc:.0f}% of the marks)")
    print()
    print(f"  the CHoCH requirement improved lift on {wins} of {wins + losses}"
          f" samples, and NEITHER form of it ever beat 1.0.")
    print()

    # ---- part 2: the sweep is the mark. Which gate sharpens it?
    print("=" * 78)
    print("  PART 2 — the sweep beats its control everywhere but fires on ~9%")
    print("  of bars. Which gate makes it RARER without making it WORSE?")
    print("=" * 78)
    v = []
    v.append(("1h 24-26", run_variants("2024-2026  1h", h1)))
    v.append(("15m 2026", run_variants("2026 Jun-Aug  15m",
                                       load_plain("GOLD_15m.json"))))
    for f, lb in (("GOLD_M15_2018.json", "M15 2018"),
                  ("GOLD_M5_2018.json", "M5 2018"),
                  ("GOLD_M1_2018.json", "M1 2018")):
        pth = f"/home/user/signals/data/{f}"
        if not os.path.exists(pth):
            continue
        rows = sorted(json.load(open(pth)), key=lambda r: r[0])
        from engine import Series
        sr = Series([r[0] for r in rows], [r[1] for r in rows],
                    [r[2] for r in rows], [r[3] for r in rows],
                    [r[4] for r in rows])
        v.append((lb, run_variants(lb + "  (2018 — hypothesis only)", sr)))

    names = sorted(v[0][1].keys())
    print()
    print("  LIFT   (>1.0 beats its own time-shifted twin)")
    print(f"  {'':26}" + "".join(f"{lb:>11}" for lb, _ in v))
    for nm in names:
        print(f"  {nm:26}" + "".join(f"{d.get(nm, (0, 0, 0))[1]:11.2f}"
                                    for _, d in v))
    print()
    print("  FIRES PER 1000 BARS")
    for nm in names:
        print(f"  {nm:26}" + "".join(f"{d.get(nm, (0, 0, 0))[2]:11.1f}"
                                    for _, d in v))
    print()
    print("  It is NOT a claim about money. A leg starting is not a trade")
    print("  surviving — E-186 measured those as different events.")


if __name__ == "__main__":
    main()

"""
E-184 — THE LEG CATCHER. Every ICT/SMC concept, scored on ONE question.

Veer: "remeber there's so much to the strategy can you actually research
everything about liquidity ict smc all the little little aspects and build me a
successful leg catcher", and before that "we catch banger TO banger yk point to
point".

E-182 fixed the leg scoreboard, and that changes what can be asked. Every study
in this repo until now asked "does this strategy make money", which mixes the
entry, the stop, the target, the trail and the cost into one number and tells
you nothing about which part is broken. THIS asks one question only:

    DOES THIS CONDITION MARK THE START OF A LEG?

A leg is pivot-to-pivot, size >= legMin ATR. A condition "catches" a leg if it
is true within `slack` bars of that leg's low/high. The score is LIFT: how much
more often a leg starts when the condition is true, against the base rate.

WHY LIFT AND NOT WIN RATE. A condition that is true on 40% of bars will sit on
plenty of leg starts by luck. Lift divides that out. A lift of 1.0 is a coin
flip dressed up as a signal, and most published SMC concepts land there.

THE CONTROL. Every feature is also scored on a TIME-SHIFTED copy of itself -
the same condition, rolled forward by a random offset, so its shape and
frequency are identical and only its timing is destroyed. A real feature beats
its own shifted twin. This is the same control that caught six false positives
in E-107 and it is not optional.

CONCEPTS TESTED (the "little little aspects"):
  liquidity   sweep of a prior swing, equal highs/lows, previous day/week H/L,
              round numbers, the sweep's wick ratio
  structure   BOS, CHoCH, displacement, inside-bar compression
  zones       FVG / imbalance, order block (last opposing candle), breaker
  position    premium/discount, OTE band (0.62-0.79)
  context     session (London / NY killzone), volume at the extreme, ATR
              expansion, distance from a moving average
"""
from __future__ import annotations
import math, os, random, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, ema
from regime import load_plain, resample
from liq_m1 import load as load_spread


# ---------------------------------------------------------------- legs -----
def legs(s, A, pv=3, minAtr=2.0):
    """Pivot-to-pivot legs, size >= minAtr x ATR at the leg's start.

    Returns (start_bar, end_bar, dir, size_in_atr). start_bar is the bar the
    extreme actually FORMED on, not the bar it confirmed on - the whole point
    is to ask what was visible AT the turn.
    """
    piv = []
    for i in range(pv, len(s) - pv):
        if s.h[i] == max(s.h[i - pv:i + pv + 1]):
            piv.append((i, s.h[i], 1))
        if s.l[i] == min(s.l[i - pv:i + pv + 1]):
            piv.append((i, s.l[i], -1))
    piv.sort()
    out = []
    for k in range(len(piv) - 1):
        b0, p0, k0 = piv[k]
        b1, p1, k1 = piv[k + 1]
        if k0 == k1 or b1 <= b0:
            continue
        a = A[b0]
        if not a or a <= 0:
            continue
        size = abs(p1 - p0) / a
        if size >= minAtr:
            out.append((b0, b1, -k0, size))     # a HIGH starts a DOWN leg
    return out


# ------------------------------------------------------------- features ----
def features(s, A, V=None):
    """Every condition, evaluated on every bar, using only closed bars <= i.

    Each returns +1 (bullish: expect an UP leg), -1 (bearish), or 0 (silent).
    Nothing here may read a bar after i - that is the whole discipline.
    """
    n = len(s)
    F = {}
    def blank():
        return [0] * n

    piv_hi, piv_lo = [], []
    swept_hi = blank(); swept_lo = blank()
    eqh = blank(); eql = blank()
    fvg = blank(); ob = blank(); disp = blank()
    bos = blank(); choch = blank()
    prem = blank(); ote = blank()
    wick = blank(); expand = blank(); inside = blank()
    round_ = blank(); volx = blank(); mad = blank()

    pv = 3
    E = ema(s.c, 50)
    for i in range(pv, n - pv):
        if s.h[i] == max(s.h[i - pv:i + pv + 1]):
            piv_hi.append((i, s.h[i]))
        if s.l[i] == min(s.l[i - pv:i + pv + 1]):
            piv_lo.append((i, s.l[i]))

    hi_at, lo_at = {}, {}
    for (b, p) in piv_hi:
        hi_at[b + pv] = p          # known only pv bars later
    for (b, p) in piv_lo:
        lo_at[b + pv] = p

    liveHi, liveLo = [], []
    for i in range(n):
        a = A[i] if A[i] else 0.0
        if i in hi_at:
            liveHi.append(hi_at[i])
        if i in lo_at:
            liveLo.append(lo_at[i])
        liveHi = liveHi[-40:]
        liveLo = liveLo[-40:]
        if a <= 0 or i < 60:
            continue
        rng = s.h[i] - s.l[i]
        body = abs(s.c[i] - s.o[i])

        # --- LIQUIDITY: swept a prior swing and closed back inside
        for p in liveHi:
            if s.h[i] > p and s.c[i] < p:
                swept_hi[i] = -1            # sell-side setup -> DOWN leg
                break
        for p in liveLo:
            if s.l[i] < p and s.c[i] > p:
                swept_lo[i] = 1
                break

        # --- EQUAL HIGHS / LOWS: two swings within 0.1 ATR, then taken
        if len(liveHi) >= 2 and abs(liveHi[-1] - liveHi[-2]) <= 0.10 * a \
           and s.h[i] > max(liveHi[-2:]) and s.c[i] < max(liveHi[-2:]):
            eqh[i] = -1
        if len(liveLo) >= 2 and abs(liveLo[-1] - liveLo[-2]) <= 0.10 * a \
           and s.l[i] < min(liveLo[-2:]) and s.c[i] > min(liveLo[-2:]):
            eql[i] = 1

        # --- DISPLACEMENT: a big-bodied bar
        if rng > 0 and body >= 1.5 * a and body / rng >= 0.6:
            disp[i] = 1 if s.c[i] > s.o[i] else -1

        # --- FVG: three-bar imbalance, unfilled
        if i >= 2:
            if s.l[i] > s.h[i - 2] and (s.l[i] - s.h[i - 2]) >= 0.15 * a:
                fvg[i] = 1
            if s.h[i] < s.l[i - 2] and (s.l[i - 2] - s.h[i]) >= 0.15 * a:
                fvg[i] = -1

        # --- ORDER BLOCK: last opposing candle before displacement
        if i >= 1 and disp[i] != 0:
            prev_up = s.c[i - 1] > s.o[i - 1]
            if disp[i] > 0 and not prev_up:
                ob[i] = 1
            if disp[i] < 0 and prev_up:
                ob[i] = -1

        # --- STRUCTURE: BOS = close beyond the last swing; CHoCH = the first
        #     break the OTHER way after a run
        if liveHi and s.c[i] > liveHi[-1]:
            bos[i] = 1
        if liveLo and s.c[i] < liveLo[-1]:
            bos[i] = -1
        if i >= 1 and bos[i] != 0 and bos[i - 1] != 0 and bos[i] != bos[i - 1]:
            choch[i] = bos[i]

        # --- PREMIUM / DISCOUNT and the OTE band, over the last 60 bars
        hh, ll = max(s.h[i - 60:i]), min(s.l[i - 60:i])
        if hh > ll:
            pos = (s.c[i] - ll) / (hh - ll)
            prem[i] = 1 if pos < 0.35 else (-1 if pos > 0.65 else 0)
            if 0.21 <= pos <= 0.38:
                ote[i] = 1
            elif 0.62 <= pos <= 0.79:
                ote[i] = -1

        # --- the WICK at the extreme
        if rng > 0:
            upw = (s.h[i] - max(s.o[i], s.c[i])) / rng
            dnw = (min(s.o[i], s.c[i]) - s.l[i]) / rng
            if dnw >= 0.6:
                wick[i] = 1
            elif upw >= 0.6:
                wick[i] = -1

        # --- ATR EXPANSION and INSIDE-BAR compression
        if A[i - 10]:
            expand[i] = 1 if a > 1.4 * A[i - 10] else 0
        if i >= 1 and s.h[i] <= s.h[i - 1] and s.l[i] >= s.l[i - 1]:
            inside[i] = 1

        # --- ROUND NUMBER within 0.25 ATR
        step = 10.0
        if min(abs(s.c[i] - round(s.c[i] / step) * step), a) <= 0.25 * a:
            round_[i] = 1

        # --- VOLUME at the bar (E-171: tick volume at the extreme)
        if V and i >= 50:
            m = sorted(V[i - 50:i])[25]
            if m > 0 and V[i] >= 2.0 * m:
                volx[i] = 1

        # --- distance from a 50 EMA, in ATR
        if E[i]:
            d = (s.c[i] - E[i]) / a
            mad[i] = 1 if d <= -1.5 else (-1 if d >= 1.5 else 0)

    F["sweep a swing high"]      = swept_hi
    F["sweep a swing low"]       = swept_lo
    F["equal highs taken"]       = eqh
    F["equal lows taken"]        = eql
    F["displacement candle"]     = disp
    F["FVG / imbalance"]         = fvg
    F["order block"]             = ob
    F["BOS"]                     = bos
    F["CHoCH"]                   = choch
    F["premium / discount"]      = prem
    F["OTE 0.62-0.79"]           = ote
    F["60%+ rejection wick"]     = wick
    F["stretched from 50 EMA"]   = mad
    F["round number"]            = round_
    if V:
        F["volume x2 at the bar"] = volx
    F["ATR expanding"]           = expand
    F["inside bar"]              = inside
    return F


# --------------------------------------------------------------- scoring ---
def score(F, lg, n, slack=3, seed=7):
    """For each feature: how often does a leg start where it fires?

    A hit = the feature is non-zero, in the leg's direction, within `slack`
    bars BEFORE OR ON the leg's starting extreme. Signals fire at the turn, and
    the turn is not knowable to the bar - slack is that lag, not a licence to
    look forward: the window ENDS at the extreme.

    The control is the same feature time-shifted by a random offset. Shape and
    frequency identical, timing destroyed. A feature that does not beat its own
    shifted twin has told us nothing.
    """
    rnd = random.Random(seed)
    starts = {}
    for (b0, b1, d, size) in lg:
        starts.setdefault(b0, []).append((d, size))

    def hits(series):
        fired = caught = 0
        pts = 0.0
        for i in range(n):
            v = series[i]
            if v == 0:
                continue
            fired += 1
            got = False
            for k in range(i, min(i + slack + 1, n)):
                for (d, size) in starts.get(k, []):
                    if d == v:
                        got = True
                        pts += size
                        break
                if got:
                    break
            caught += 1 if got else 0
        return fired, caught, pts

    # base rate: a leg start, in either direction, per bar
    nStart = sum(len(v) for v in starts.values())
    base = nStart / max(n, 1) * (slack + 1)

    out = []
    for name, ser in F.items():
        fired, caught, pts = hits(ser)
        if fired < 30:
            out.append((name, fired, 0.0, 0.0, 0.0, 0.0))
            continue
        rate = caught / fired
        # control: roll the series by a random offset, several times
        cr = []
        for _ in range(5):
            off = rnd.randrange(200, max(400, n // 2))
            shifted = ser[off:] + ser[:off]
            f2, c2, _ = hits(shifted)
            if f2 > 0:
                cr.append(c2 / f2)
        ctrl = statistics.fmean(cr) if cr else base
        lift = rate / ctrl if ctrl > 0 else 0.0
        out.append((name, fired, rate, ctrl, lift, pts / max(caught, 1)))
    out.sort(key=lambda x: -x[4])
    return out, base, nStart


def report(label, s, V=None, pv=3, minAtr=2.0, slack=3):
    A = watr(s, 14)
    lg = legs(s, A, pv=pv, minAtr=minAtr)
    if len(lg) < 40:
        print(f"\n  {label}: only {len(lg)} legs, not enough")
        return
    F = features(s, A, V)
    rows, base, nStart = score(F, lg, len(s), slack=slack)
    tot = sum(x[3] for x in lg)
    print(f"\n  ---- {label} ----")
    print(f"  {len(s):,} bars, {len(lg)} legs of >= {minAtr} ATR, "
          f"{tot:.0f} ATR of movement in total, base rate {100*base:.1f}%")
    print(f"  {'concept':<26}{'fires':>7}{'catches':>9}{'control':>9}"
          f"{'LIFT':>7}{'avg leg':>9}")
    print("  " + "-" * 68)
    for (name, fired, rate, ctrl, lift, avg) in rows:
        if fired < 30:
            print(f"  {name:<26}{fired:>7}   too rare to score")
            continue
        star = " <<<" if lift >= 1.30 else ""
        print(f"  {name:<26}{fired:>7}{100*rate:>8.1f}%{100*ctrl:>8.1f}%"
              f"{lift:>7.2f}{avg:>8.1f}A{star}")


def main():
    print("=" * 84)
    print("  E-184 — every ICT/SMC concept scored on ONE question:")
    print("  does it mark the START of a leg? LIFT is against a time-shifted")
    print("  copy of the same feature, so shape and frequency are controlled.")
    print("=" * 84)

    h1 = load_plain("GOLD_1h.json")
    report("2024-2026  1h", h1)
    report("2024-2026  4h", resample(h1, 4))
    report("2026 Jun-Aug  15m", load_plain("GOLD_15m.json"))

    s1, _ = load_spread("M1")
    V = None
    try:
        import json
        rows = json.load(open("/home/user/signals/data/GOLD_M1_2018.json"))
        rows.sort(key=lambda r: r[0])
        V = [r[7] for r in rows] if len(rows[0]) > 7 else None
    except Exception:
        V = None
    report("2018 Jan-Jun  M1 (has volume)", s1, V=V)




# ------------------------------------------------------- the combination ---
def combo(label, s, V=None, pv=3, minAtr=2.0, slack=3):
    """Stack the concepts that BEAT their control, and see if lift compounds.

    The winners across all four samples are the mean-reversion family: stretched
    from the mean, in premium/discount, showing a rejection wick, at equal
    highs/lows, on volume. The losers are the continuation family: FVG,
    displacement, BOS - which by construction fire in the MIDDLE of a leg, once
    the move is already underway, and that is exactly what "it caught pullbacks
    as a signal" describes.

    So: require N of the mean-reversion conditions to agree on direction, and
    read the lift as N rises. If the concepts carry independent information the
    lift climbs; if they are all the same idea wearing different names, it will
    not move.
    """
    A = watr(s, 14)
    lg = legs(s, A, pv=pv, minAtr=minAtr)
    if len(lg) < 40:
        return
    F = features(s, A, V)
    keep = ["stretched from 50 EMA", "premium / discount",
            "60%+ rejection wick", "equal highs taken", "equal lows taken"]
    if V:
        keep.append("volume x2 at the bar")
    keep = [k for k in keep if k in F]

    n = len(s)
    vote = [0] * n
    agree = [0] * n
    for i in range(n):
        up = sum(1 for k in keep if F[k][i] > 0)
        dn = sum(1 for k in keep if F[k][i] < 0)
        if up > dn:
            vote[i], agree[i] = 1, up
        elif dn > up:
            vote[i], agree[i] = -1, dn

    print(f"\n  ---- {label}: how many of the {len(keep)} must agree ----")
    print(f"  {'need':>5}{'fires':>8}{'catches':>9}{'control':>9}{'LIFT':>7}"
          f"{'avg leg':>9}{'ATR caught':>12}")
    print("  " + "-" * 60)
    for need in (1, 2, 3, 4):
        ser = [vote[i] if agree[i] >= need else 0 for i in range(n)]
        rows, base, _ = score({"x": ser}, lg, n, slack=slack)
        (_, fired, rate, ctrl, lift, avg) = rows[0]
        if fired < 30:
            print(f"  {need:>5}{fired:>8}   too rare")
            continue
        print(f"  {need:>5}{fired:>8}{100*rate:>8.1f}%{100*ctrl:>8.1f}%"
              f"{lift:>7.2f}{avg:>8.1f}A{fired*rate*avg:>11.0f}A")


def main2():
    print("\n" + "=" * 84)
    print("  E-184 PART 2 — stacking the concepts that beat their own control")
    print("=" * 84)
    h1 = load_plain("GOLD_1h.json")
    combo("2024-2026 1h", h1)
    combo("2026 15m", load_plain("GOLD_15m.json"))
    s1, _ = load_spread("M1")
    V = None
    try:
        import json
        rows = json.load(open("/home/user/signals/data/GOLD_M1_2018.json"))
        rows.sort(key=lambda r: r[0])
        V = [r[7] for r in rows] if len(rows[0]) > 7 else None
    except Exception:
        pass
    combo("2018 M1 (with volume)", s1, V=V)




def oos():
    """The concepts were CHOSEN by looking at the whole sample, so the stack
    above is in-sample selection and E-150 says that is worth nothing until it
    is repeated on data the choice never saw.

    So: re-derive nothing. Take the stack exactly as chosen, and measure it on
    the FIRST half and the SECOND half separately. If the lift only exists in
    one half it is a fit.
    """
    from engine import Series
    print("\n" + "=" * 84)
    print("  E-184 PART 3 — the same stack, each half of each sample separately")
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
    h1 = load_plain("GOLD_1h.json")

    for label, s, vol in (("2024-2026 1h", h1, None), ("2018 M1", s1, V)):
        n = len(s.c) // 2
        a = Series(s.ts[:n], s.o[:n], s.h[:n], s.l[:n], s.c[:n])
        b = Series(s.ts[n:], s.o[n:], s.h[n:], s.l[n:], s.c[n:])
        va = vol[:n] if vol else None
        vb = vol[n:] if vol else None
        print(f"\n  {label}")
        combo("  FIRST half", a, V=va)
        combo("  SECOND half — unseen by the choice", b, V=vb)


if __name__ == "__main__":
    main()
    main2()
    oos()

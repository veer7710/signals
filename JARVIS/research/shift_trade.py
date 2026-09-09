"""
E-194 — DOES THE SHIFT CATCH THE TRADE? Every clock, structural stop, three TPs.

Veer: "bro the point is on any timeframe we should catch the trade dude using
liquidity smc bro reversals everything and anything just make it possible dude
the ss was from random".

Fair. E-193 answered a narrower question than he asked - it showed the sweep
marks where legs BEGIN at 1.8-2.8x the base rate. That is not the same as
catching a trade, and E-186 already measured those as different events. This
asks the question he actually asked:

    ENTER on the SHIFT. STOP past the sweep wick. THREE TPs, THREE PARTIALS.
    On M1, M5, M15, M30, 1h, 2h, 4h. What does it bank, per clock, after cost?

WHAT IS DIFFERENT FROM E-188, which found nothing:
  - the ENTRY is the sweep, which E-193 measured at 1.8-2.8x lift. E-188 used a
    stack of five reads with no liquidity anchor at all.
  - the STOP is STRUCTURAL - past the wick that ran the stops - not a fixed ATR
    multiple. That is Veer's "safe sl", and it also means the stop is TIGHT
    exactly where the setup is clean, which is the whole argument for entering
    at a sweep instead of a break.
  - the TP ladder is measured in R off that structural stop AND in ATR, because
    those are different animals once the stop varies per trade.

WHAT IS THE SAME, deliberately: the booking machinery is partials.book(), which
already gets the things that invalidated earlier work right - the stop is
tested FIRST on every bar so ties lose, no TP can be hit on the entry bar
(E-110), and "breakeven" is entry plus the cost, not entry.

Cost is 0.02 ATR per trade by default, the same figure E-188 used.

DATA. Recent: GOLD_1h (2024-2026) and GOLD_15m (2026 Jun-Aug), resampled up.
Fast: M1/M5/M15 2018, resampled up to M30 - and per the standing rule after
E-176, a result from the 2018 file is a hypothesis about 2018. Both are printed
and both are labelled, because Veer trades M1 and 2018 is the only M1 there is.
"""
from __future__ import annotations
import json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, Series, trail_level, stop_fill
from regime import load_plain, resample
from bias_run import bias_series
from shift import shift_series
from partials import stats as pstats

# E-194-RT killed the 0.02 flat charge, and the first attempt to replace it
# was wrong in the other direction. Charging the 2018 file its OWN recorded
# spread/ATR gives 0.93 ATR per side - because 2018 gold traded at 1300 with an
# M1 ATR of 0.25 points, so a 0.23 spread really was most of a bar. Veer does
# not trade 2018. E-173 is explicit: use the spread you pay TODAY.
#
# Today: M1 spread is COST_M1_SPREAD_ATR = 0.11 of the M1 ATR (E-132). The
# spread is a fixed PRICE and ATR grows as roughly sqrt(time), so the cost in
# ATR falls as 1/sqrt(minutes-per-bar). Checked against the 2018 file's own
# measured ATR ratios - M5/M1 = 2.49 against sqrt(5) = 2.24, M15/M1 = 4.65
# against sqrt(15) = 3.87 - the sqrt model OVERCHARGES the slow clocks, which
# is the safe direction to be wrong in.
SPREAD_ATR_M1 = 0.11       # E-132, today's M1 spread as a fraction of M1 ATR
SLIP_ATR_M1 = 0.048        # 0.10pt round trip against an M1 ATR of ~2.1pt
COST = 0.02                # the OLD flat charge, kept only to reproduce E-194


def cost_atr(minutes):
    """Round-trip cost on a clock of `minutes` per bar, expressed in ATR.

    M1 0.158, M5 0.071, M15 0.041, M30 0.029, H1 0.020, H4 0.010.
    """
    return (SPREAD_ATR_M1 + SLIP_ATR_M1) / (max(minutes, 1) ** 0.5)


# ------------------------------------------------------------------ signal --
def shift_signals(s, A, pv=3, eqTol=0.10, sweepAtr=0.05, need=3,
                  emaLen=50, stretch=1.5):
    """The Pine SHIFT, returning (bar, dir, stop_price) per fire.

    The stop price is carried WITH the signal because it is structural: the
    extreme of the wick that ran the pool. A fixed-ATR stop would throw away
    the one thing the sweep gives you.
    """
    from engine import ema
    n = len(s)
    E = ema(s.c, emaLen)
    hi_at, lo_at = {}, {}
    for i in range(pv, n - pv):
        if s.h[i] == max(s.h[i - pv:i + pv + 1]):
            hi_at[i + pv] = s.h[i]
        if s.l[i] == min(s.l[i - pv:i + pv + 1]):
            lo_at[i + pv] = s.l[i]

    poolHi = poolLo = prevHi = prevLo = None
    out = []
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
        if pHi is not None and s.h[i] > pHi + sweepAtr * a and s.c[i] < pHi:
            d = -1
        if pLo is not None and s.l[i] < pLo - sweepAtr * a and s.c[i] > pLo:
            d = 1
        if d == 0:
            continue

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
        agree = (1 if st == d else 0) + (1 if wk == d else 0) \
            + (1 if pd == d else 0)
        if agree < need:
            continue
        ext = s.l[i] if d > 0 else s.h[i]
        out.append((i, d, ext))
    return out


# ------------------------------------------------------------------- book ---
def book(s, A, sig, bias, side, stopBuf, tps, unit="R", beAfterTp1=True,
         hold=400, cool=5, cost=COST, maxStopAtr=3.0):
    """Trade the SHIFT with a STRUCTURAL stop.

    tps are three distances, in R (multiples of the structural stop) if
    unit=="R", or in ATR if unit=="ATR".

    Returns (results in ATR per trade, how many reached each TP, mean stop
    distance in ATR, how many were refused for too wide a stop).
    """
    out, busy = [], -1
    reach = [0, 0, 0]
    stopsA, wide = [], 0
    for (i, t, ext) in sig:
        if i <= busy or i + 1 >= len(s):
            continue
        b = bias[i]
        if side == "with" and b != t:
            continue
        if side == "against" and b != -t:
            continue
        a = A[i]
        if not a or a <= 0:
            continue
        entry = s.o[i + 1]
        sl = ext - t * stopBuf * a
        risk = t * (entry - sl)
        if risk <= 0:
            continue
        if risk / a > maxStopAtr:       # a stop this wide is a different trade
            wide += 1
            continue
        stopsA.append(risk / a)
        step = risk if unit == "R" else a
        lv = [entry + t * x * step for x in tps]
        left, got, hitN, kk = 1.0, 0.0, 0, None
        for k in range(i + 1, min(i + 1 + hold, len(s))):
            hitSl = (s.l[k] <= sl) if t > 0 else (s.h[k] >= sl)
            if hitSl:
                fx = stop_fill(sl, s.o[k], t)     # E-194-RT: gaps fill worse
                got += left * t * (fx - entry) / a
                left = 0.0
                kk = k
                break
            if k == i + 1:
                continue                      # E-110: not on the entry bar
            for n in range(hitN, 3):
                hit = (s.h[k] >= lv[n]) if t > 0 else (s.l[k] <= lv[n])
                if not hit:
                    break
                part = 1.0 / 3.0 if n < 2 else left
                got += part * t * (lv[n] - entry) / a
                left -= part
                hitN = n + 1
                reach[n] += 1
                if n == 0 and beAfterTp1:
                    be = entry + t * cost * a
                    if (be > sl) if t > 0 else (be < sl):
                        sl = be
            if left <= 1e-9:
                kk = k
                break
        if left > 1e-9:
            kk = min(i + 1 + hold, len(s) - 1)
            got += left * t * (s.c[kk] - entry) / a
        out.append(got - cost)
        busy = kk + cool
    ms = statistics.fmean(stopsA) if stopsA else 0.0
    return out, reach, ms, wide


# ------------------------------------------------------------------- trail --
# THE EXIT THAT ACTUALLY MATTERS.
#
# Every fixed-target arrangement above loses. A leg-start signal has a
# POSITIVE-SKEW payoff - it is right about direction more often than chance and
# says nothing about distance - and a fixed target is the one exit shape that
# throws that away: it caps the tail that pays for the losers. So the same
# signal is booked again with a give-back trail and no target at all.
#
# trail_level() is engine.py's, which is the only correct give-back trail in
# this repo. E-151: a stop derived from the current bar's extreme cannot be
# resting on the far side of that bar's close, and filling it there books the
# bar's own favourable extreme. Twelve files had that bug.

def trail_book(s, A, sig, bias, side, stopBuf, give, arm, hold=240, cool=1,
               cost=COST, maxStopAtr=3.0, tp1=None):
    """Enter on the SHIFT, stop past the sweep wick, then trail.

    give = fraction of the best excursion handed back. give >= 1.0 disables the
           trail entirely and holds to `hold`, which is the control that says
           whether the trail is doing anything at all.
    arm  = the trade must be this many R in front before the trail starts.
    tp1  = optionally bank a third at tp1 R first (Veer's partials), rest trails.

    Returns a list of (result in ATR, direction).
    """
    out, busy = [], -1
    for (i, t, ext) in sig:
        if i <= busy or i + 1 >= len(s):
            continue
        b = bias[i]
        if side == "with" and b != t:
            continue
        if side == "against" and b != -t:
            continue
        a = A[i]
        if not a or a <= 0:
            continue
        entry = s.o[i + 1]
        sl = ext - t * stopBuf * a
        risk = t * (entry - sl)
        if risk <= 0 or risk / a > maxStopAtr:
            continue
        peak, got, left, kk, done, banked = entry, 0.0, 1.0, None, False, False
        for k in range(i + 1, min(i + 1 + hold, len(s))):
            if (s.l[k] <= sl) if t > 0 else (s.h[k] >= sl):
                # E-194-RT: a bar that GAPS through the stop fills at the open,
                # not at the stop. Booking the level flatters every loser.
                fx = stop_fill(sl, s.o[k], t)
                got += left * t * (fx - entry) / a
                kk, done = k, True
                break
            if k == i + 1:
                continue                      # E-110: not on the entry bar
            peak = max(peak, s.h[k]) if t > 0 else min(peak, s.l[k])
            if tp1 is not None and not banked:
                lv = entry + t * tp1 * risk
                if (s.h[k] >= lv) if t > 0 else (s.l[k] <= lv):
                    got += (1.0 / 3.0) * t * (lv - entry) / a
                    left -= 1.0 / 3.0
                    banked = True
            if give < 1.0 and t * (peak - entry) >= arm * risk:
                nl = trail_level(entry, sl, peak, s.c[k], t, give)
                if nl is None:                # unplaceable: exit at this close
                    got += left * t * (s.c[k] - entry) / a
                    kk, done = k, True
                    break
                sl = nl
        if not done:
            kk = min(i + 1 + hold, len(s) - 1)
            got += left * t * (s.c[kk] - entry) / a
        out.append((got - cost, t))
        busy = kk + cool
    return out


# ---------------------------------------------------------------- reporting -
LADDERS_R = ([1.0, 2.0, 3.0], [1.0, 1.5, 2.5], [0.75, 1.5, 3.0])
LADDERS_A = ([0.3, 0.6, 1.2], [0.5, 1.0, 2.0], [1.0, 2.0, 3.0])


def load2018(name):
    rows = sorted(json.load(open(f"/home/user/signals/data/{name}")),
                  key=lambda r: r[0])
    return Series([r[0] for r in rows], [r[1] for r in rows],
                  [r[2] for r in rows], [r[3] for r in rows],
                  [r[4] for r in rows])


def clocks():
    """Every clock available. `need` is set per clock, and it is set from the
    TRADE COUNT and nothing else - see need_table(). factor is always 4, so
    the bias clock is always 4x the trading clock."""
    out = []
    h1 = load_plain("GOLD_1h.json")
    g15 = load_plain("GOLD_15m.json")
    out.append(("15m  2026", g15, 4, 3, 2))
    out.append(("30m  2026", resample(g15, 2), 4, 3, 2))
    out.append(("1h   2024-26", h1, 4, 3, 1))
    out.append(("2h   2024-26", resample(h1, 2), 4, 3, 1))
    out.append(("4h   2024-26", resample(h1, 4), 4, 4, 1))
    for f, lb, pv, nd in (("GOLD_M1_2018.json", "M1   2018", 3, 3),
                          ("GOLD_M5_2018.json", "M5   2018", 3, 3),
                          ("GOLD_M15_2018.json", "M15  2018", 3, 2)):
        if os.path.exists(f"/home/user/signals/data/{f}"):
            out.append((lb, load2018(f), 4, pv, nd))
    m1 = next((s for (l, s, _, _, _) in out if l.startswith("M1 ")), None)
    if m1 is not None:
        out.append(("M30  2018", resample(m1, 30), 4, 3, 1))
    return out


def prep(C):
    out = []
    for (lb, s, f, pv, nd) in C:
        A = watr(s, 14)
        out.append((lb, s, A, shift_signals(s, A, pv=pv, need=nd),
                    bias_series(s, f), nd, f, pv))
    return out


def per_day(s, n):
    span = (s.ts[-1] - s.ts[0]) / 86400.0
    return n / span if span > 0 else 0.0


# ============================ THE FOUR QUESTIONS ============================
def q1_need_table():
    """Veer: 'on any timeframe we should catch the trade'.

    The 3-of-3 gate holds the fire rate constant PER BAR. A trade is a rate per
    DAY, and a day is 1440 M1 bars and 6 four-hourly ones. Same rate per bar
    means 6 trades a day on M1 and 0.02 on 4h - which is why the E-193 gate
    produced 986 SHIFTs on M1 2018 and SEVEN on 4h 2024-2026.

    So `need` falls as the clock slows. It is chosen from the TRADE COUNT only,
    never from the returns: the strictest gate still giving 1-8 trades a day.
    """
    print()
    print("=" * 92)
    print("  Q1 — WHY IT ONLY 'WORKED' ON M1: the gate is a rate per BAR and a")
    print("  trade is a rate per DAY. Trades/day at each gate:")
    print("=" * 92)
    print(f"  {'clock':<14}{'bars':>8}{'days':>6}"
          + "".join(f"{'need=' + str(k):>12}" for k in (3, 2, 1, 0)))
    print("  " + "-" * 76)
    for (lb, s, f, pv, nd) in clocks():
        A = watr(s, 14)
        cells = []
        for k in (3, 2, 1, 0):
            n = len(shift_signals(s, A, pv=pv, need=k))
            cells.append(f"{per_day(s, n):>12.1f}")
        print(f"  {lb:<14}{len(s):>8}{(s.ts[-1] - s.ts[0]) / 86400:>6.0f}"
              + "".join(cells) + f"   -> need={nd}")
    print()
    print("  Chosen: the strictest gate still giving 1-8 trades a day. Fitted")
    print("  to the trade COUNT, which is a property of the clock, never to")
    print("  the returns.")


def q2_fixed_targets(P):
    """Does the three-TP, three-partial structure Veer trades work here?"""
    print()
    print("=" * 92)
    print("  Q2 — THREE TPs, THREE PARTIALS, STRUCTURAL STOP. Pooled over every")
    print("  clock, every geometry. This is what Veer says he trades.")
    print("=" * 92)
    print(f"  {'buf':>5}{'ladder':>14}{'n':>7}{'banked':>8}{'ATR/trd':>10}{'t':>7}")
    print("  " + "-" * 51)
    rows = []
    for buf in (0.10, 0.30, 0.60, 1.00):
        for unit, lads in (("ATR", LADDERS_A), ("R", LADDERS_R)):
            for tps in lads:
                pooled = []
                for (lb, s, A, sig, bias, nd, f, pv) in P:
                    r, _, _, _ = book(s, A, sig, bias, "all", buf, list(tps),
                                      unit=unit)
                    pooled.extend(r)
                v = pstats(pooled)
                if v:
                    lad = "/".join(f"{x:g}" for x in tps) + unit
                    rows.append((v[2], buf, lad, v[0], v[1], v[3]))
    rows.sort(key=lambda x: -x[0])
    for (m, buf, lad, n, bank, t) in rows:
        print(f"  {buf:>5.2f}{lad:>14}{n:>7}{bank:>7.1f}%{m:>+10.4f}{t:>+7.2f}")
    print()
    print("  EVERY ONE IS NEGATIVE, and the pattern is the giveaway: the closer")
    print("  the ladder, the higher the banked % and the WORSE the expectancy.")
    print("  That is what a driftless walk plus a cost does. A leg-start signal")
    print("  knows DIRECTION, not DISTANCE, and a fixed target is the one exit")
    print("  that throws the tail away.")


def q3_trail(P):
    """The same signal with a give-back trail and no target."""
    print()
    print("=" * 92)
    print("  Q3 — THE SAME SIGNAL, TRAILED INSTEAD. give=1.0 is the CONTROL:")
    print("  no trail at all, hold to the limit. If 1.0 wins, the trail is")
    print("  doing nothing and the finding is drift, not a trail.")
    print("=" * 92)
    print(f"  {'hold':>6}" + "".join(f"{'give=' + str(g):>14}"
                                     for g in (0.3, 0.5, 0.7, 0.9, 1.0)))
    print(f"  {'':>6}" + "".join(f"{'ATR/t      t':>14}" for _ in range(5)))
    print("  " + "-" * 76)
    for hold in (30, 60, 120, 240, 400):
        cells = []
        for give in (0.3, 0.5, 0.7, 0.9, 1.0):
            pooled = []
            for (lb, s, A, sig, bias, nd, f, pv) in P:
                pooled.extend(x for x, _ in
                              trail_book(s, A, sig, bias, "all", 0.10, give,
                                         2.0, hold=hold))
            v = pstats(pooled)
            cells.append(f"{v[2]:>+9.4f}{v[3]:>+5.2f}" if v else "       n<30  ")
        print(f"  {hold:>6}" + "".join(cells))
    print()
    print("  give=0.7 is an INTERIOR optimum - 0.5 is worse and 1.0 is worse -")
    print("  so the trail is doing real work and this is not the E-151 leak,")
    print("  where the best value ran to the tightest edge of every range.")
    print()
    print("  And the partial: taking a third at 1R and trailing the rest.")
    print(f"  {'':<22}{'n':>7}{'banked':>8}{'ATR/trd':>10}{'t':>7}")
    for tp1, nm in ((None, "trail only"), (1.0, "third at 1R, then trail")):
        pooled = []
        for (lb, s, A, sig, bias, nd, f, pv) in P:
            pooled.extend(x for x, _ in
                          trail_book(s, A, sig, bias, "all", 0.10, 0.7, 2.0,
                                     hold=240, tp1=tp1))
        v = pstats(pooled)
        if v:
            print(f"  {nm:<22}{v[0]:>7}{v[1]:>7.1f}%{v[2]:>+10.4f}{v[3]:>+7.2f}")
    print("  The partial COSTS money here. It caps the same tail the fixed")
    print("  target did, just later.")


def q4_long_short(P):
    """THE CHECK THAT DECIDES IT. Gold ran +90% over the recent sample."""
    print()
    print("=" * 92)
    print("  Q4 — LONG vs SHORT. Gold ran +90% across the 2024-2026 file. A")
    print("  long-hold strategy on a market that went straight up will look")
    print("  good for a reason that has nothing to do with the signal.")
    print("=" * 92)
    print(f"  {'clock':<14}{'move':>7}{'LONG n':>8}{'ATR/t':>9}{'t':>7}"
          f"{'SHORT n':>9}{'ATR/t':>9}{'t':>7}")
    print("  " + "-" * 71)
    allL, allS, flatL, flatS = [], [], [], []
    for (lb, s, A, sig, bias, nd, f, pv) in P:
        r = trail_book(s, A, sig, bias, "all", 0.10, 0.7, 2.0, hold=240)
        L = [x for x, t in r if t > 0]
        S = [x for x, t in r if t < 0]
        allL += L
        allS += S
        if "2018" in lb:
            flatL += L
            flatS += S
        mv = 100.0 * (s.c[-1] - s.c[0]) / s.c[0]
        vl, vs = pstats(L), pstats(S)
        fl = f"{vl[2]:>+9.4f}{vl[3]:>+7.2f}" if vl else f"{'n<30':>16}"
        fs = f"{vs[2]:>+9.4f}{vs[3]:>+7.2f}" if vs else f"{'n<30':>16}"
        print(f"  {lb:<14}{mv:>+6.0f}%{len(L):>8}{fl}{len(S):>9}{fs}")
    print("  " + "-" * 71)
    for nm, L, S in (("POOLED, all", allL, allS),
                     ("2018 only (flat market)", flatL, flatS)):
        vl, vs = pstats(L), pstats(S)
        if vl and vs:
            print(f"  {nm:<26}long {vl[0]:>5}{vl[2]:>+9.4f}{vl[3]:>+6.2f}"
                  f"     short {vs[0]:>5}{vs[2]:>+9.4f}{vs[3]:>+6.2f}")
    print()
    print("  THE SPLIT IS THE ANSWER. On 2024-2026, where gold rose 90%, the")
    print("  longs pay and the shorts LOSE SIGNIFICANTLY (t = -2.1 to -3.0).")
    print("  That is the bull market, not the signal.")
    print()
    print("  On 2018, where gold ended where it started, BOTH sides are")
    print("  positive. That is the only sample here in which the drift is not")
    print("  doing the work - and it is one six-month window, so per the rule")
    print("  after E-176 it is a HYPOTHESIS about 2018, not evidence.")


def main():
    C = clocks()
    P = prep(C)
    print("=" * 92)
    print("  E-194 — CAN THE SHIFT BE TRADED, ON ANY CLOCK?")
    print("  Veer: 'on any timeframe we should catch the trade dude using")
    print("  liquidity smc bro reversals everything and anything'.")
    print("  Results in ATR per trade so clocks compare. Cost 0.02 ATR/trade.")
    print("=" * 92)
    q1_need_table()
    q2_fixed_targets(P)
    q3_trail(P)
    q4_long_short(P)
    print()
    print("=" * 92)
    print("  VERDICT: REJECTED. See E-194-RT.")
    print("  Fixed targets lose on every geometry tested - that part stands.")
    print("  The TRAILED form was reported as PROMISING and retracted the")
    print("  same day: its t was the best cell of the 5x5 grid printed in Q3,")
    print("  a skill-free signal searching that grid does as well 7.5% of the")
    print("  time, the direction-randomised null pays +0.098 ATR/trade, and")
    print("  dropping ten trades out of 2048 makes the whole thing negative.")
    print("  Numbers above still use the OLD flat 0.02 cost so E-194 can be")
    print("  reproduced; cost_atr() has the honest per-clock charge.")
    print("=" * 92)


if __name__ == "__main__":
    main()

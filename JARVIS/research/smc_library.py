"""
E-195 — THE FULL SMC / ICT / LIQUIDITY CONCEPT LIBRARY.

Veer: "just build me based of ict smc liquidity concepts so research each and
check every part of them eg smc has so many diffrent structures or liquidity
has high resistance low distances sweeps bsl ssl bla bla".

E-184 scored seventeen concepts. This adds the rest of the vocabulary - the
ones that get talked about constantly and have never been measured here:
inducement, breaker / mitigation / propulsion / rejection blocks, IFVG, BPR,
volume imbalance, consequent encroachment, the unicorn, high- versus
low-resistance liquidity runs, trendline liquidity, previous day/week levels,
the Asia range, the killzones, the silver bullet hour, power of 3, the judas
swing, and SMT divergence against a second market.

EVERY FEATURE RETURNS +1 (expect an UP leg), -1 (a DOWN leg) or 0 (silent),
on every bar, using only bars <= i. That is the same contract as
legcatch.features() so the two libraries can be scored side by side.

THE RULE THAT MATTERS FOR THIS FILE. Scoring forty features and reporting the
best one is the exact mistake E-194-RT caught: the best of forty beats its own
time-shifted twin by luck alone. smc_score.py therefore reports the
BEST-OF-N NULL - the distribution of the maximum lift over the same number of
SHUFFLED features - and nothing below that line is a finding, however good it
looks on its own.
"""
from __future__ import annotations
import datetime as _dt
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import ema


def _utc(ts):
    return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc)


def _pivots(s, pv):
    """(published_bar -> price). A centred pivot is only KNOWN pv bars later,
    and that is the bar it is published on. Every level below is built from
    these, so nothing here can see the future."""
    hi, lo = {}, {}
    for i in range(pv, len(s) - pv):
        if s.h[i] == max(s.h[i - pv:i + pv + 1]):
            hi[i + pv] = s.h[i]
        if s.l[i] == min(s.l[i - pv:i + pv + 1]):
            lo[i + pv] = s.l[i]
    return hi, lo


def _sessions(s):
    """Previous day/week high-low, and the Asia range, all closed-only.

    A 'previous day high' that includes today is a level that moves under you.
    These are frozen at the rollover and never touched again.
    """
    n = len(s)
    pdh = [None] * n; pdl = [None] * n
    pwh = [None] * n; pwl = [None] * n
    ash = [None] * n; asl = [None] * n
    dayH = dayL = None
    curDay = None
    lastDayH = lastDayL = None
    wkH = wkL = None
    curWk = None
    lastWkH = lastWkL = None
    asiaH = asiaL = None
    lastAsiaH = lastAsiaL = None
    for i in range(n):
        d = _utc(s.ts[i])
        key = d.toordinal()
        wk = d.isocalendar()[:2]
        if curDay is None:
            curDay, dayH, dayL = key, s.h[i], s.l[i]
        elif key != curDay:
            lastDayH, lastDayL = dayH, dayL
            lastAsiaH, lastAsiaL = asiaH, asiaL
            asiaH = asiaL = None
            curDay, dayH, dayL = key, s.h[i], s.l[i]
        else:
            dayH = max(dayH, s.h[i]); dayL = min(dayL, s.l[i])
        if curWk is None:
            curWk, wkH, wkL = wk, s.h[i], s.l[i]
        elif wk != curWk:
            lastWkH, lastWkL = wkH, wkL
            curWk, wkH, wkL = wk, s.h[i], s.l[i]
        else:
            wkH = max(wkH, s.h[i]); wkL = min(wkL, s.l[i])
        if 0 <= d.hour < 6:                     # the Asia range, 00:00-06:00 UTC
            asiaH = s.h[i] if asiaH is None else max(asiaH, s.h[i])
            asiaL = s.l[i] if asiaL is None else min(asiaL, s.l[i])
        pdh[i], pdl[i] = lastDayH, lastDayL
        pwh[i], pwl[i] = lastWkH, lastWkL
        # today's Asia range is usable AFTER 06:00; before that, yesterday's
        ash[i] = asiaH if d.hour >= 6 and asiaH is not None else lastAsiaH
        asl[i] = asiaL if d.hour >= 6 and asiaL is not None else lastAsiaL
    return pdh, pdl, pwh, pwl, ash, asl


def _run(px_hi, px_lo, s, i, a, clear=0.02):
    """A LEVEL RUN: price trades through the level and CLOSES BACK INSIDE.
    Returns +1 (a low was run -> expect up), -1 (a high was run), 0.
    This is the sweep test used everywhere in this repo: a close BEYOND is a
    break, not a run, and the two are different events."""
    if px_hi is not None and s.h[i] > px_hi + clear * a and s.c[i] < px_hi:
        return -1
    if px_lo is not None and s.l[i] < px_lo - clear * a and s.c[i] > px_lo:
        return 1
    return 0


# ===========================================================================
def features(s, A, V=None, pv=3, tol=0.10, other=None):
    """Every concept E-184 did not cover. `other` is a second market's Series
    aligned by timestamp, used only for SMT divergence.

    Nothing reads a bar after i. Where a concept needs a level, the level comes
    from _pivots() or _sessions(), both of which publish only closed history.
    """
    n = len(s)
    F = {}
    def blank():
        return [0] * n
    K = ("PDH/PDL run", "PWH/PWL run", "Asia range run",
         "relatively equal (3+) run", "high-resistance run",
         "low-resistance run", "trendline liquidity run",
         "inducement taken", "protected level broken", "MSS + displacement",
         "internal structure break", "breaker block", "mitigation block",
         "propulsion block", "rejection block", "IFVG", "BPR",
         "volume imbalance", "consequent encroachment", "unicorn",
         "London killzone", "NY killzone", "silver bullet hour",
         "judas swing", "power of 3", "SMT divergence", "liquidity void")
    for k in K:
        F[k] = blank()

    hi_at, lo_at = _pivots(s, pv)
    pdh, pdl, pwh, pwl, ash, asl = _sessions(s)
    E = ema(s.c, 50)

    # --- rolling state -----------------------------------------------------
    liveHi, liveLo = [], []          # (price, times_tested)
    obBull, obBear = [], []          # (top, bottom, bar, broken?)
    fvgBull, fvgBear = [], []        # (top, bottom, bar, inverted?)
    dayOpen = None; curDay = None; dayDir = 0
    lastMinorHi = lastMinorLo = None
    protHi = protLo = None
    trend = 0
    smcH = smcL = None

    om = {}
    if other is not None:
        om = {t: k for k, t in enumerate(other.ts)}

    for i in range(n):
        a = A[i] if A[i] else 0.0
        d = _utc(s.ts[i])
        key = d.toordinal()
        if key != curDay:
            curDay, dayOpen = key, s.o[i]
        # publish pivots, and count how many times each level has been TESTED -
        # that is what makes liquidity high- or low-resistance
        if i in hi_at:
            p = hi_at[i]
            hit = next((x for x in liveHi if abs(x[0] - p) <= tol * max(a, 1e-9)), None)
            if hit:
                liveHi.remove(hit)
                liveHi.append((max(hit[0], p), hit[1] + 1))
            else:
                liveHi.append((p, 1))
            lastMinorHi = p
            smcH = p
            liveHi = liveHi[-40:]
        if i in lo_at:
            p = lo_at[i]
            hit = next((x for x in liveLo if abs(x[0] - p) <= tol * max(a, 1e-9)), None)
            if hit:
                liveLo.remove(hit)
                liveLo.append((min(hit[0], p), hit[1] + 1))
            else:
                liveLo.append((p, 1))
            lastMinorLo = p
            smcL = p
            liveLo = liveLo[-40:]

        if a <= 0 or i < 80:
            continue
        rng = s.h[i] - s.l[i]
        body = abs(s.c[i] - s.o[i])
        disp = rng > 0 and body >= 1.5 * a and body / rng >= 0.6

        # ---- LIQUIDITY: the named pools ----------------------------------
        F["PDH/PDL run"][i] = _run(pdh[i], pdl[i], s, i, a)
        F["PWH/PWL run"][i] = _run(pwh[i], pwl[i], s, i, a)
        F["Asia range run"][i] = _run(ash[i], asl[i], s, i, a)

        # RELATIVELY EQUAL: three or more swings at one price. More stops.
        eqH = [x for x in liveHi if x[1] >= 3]
        eqL = [x for x in liveLo if x[1] >= 3]
        if eqH and _run(max(x[0] for x in eqH), None, s, i, a) == -1:
            F["relatively equal (3+) run"][i] = -1
        if eqL and _run(None, min(x[0] for x in eqL), s, i, a) == 1:
            F["relatively equal (3+) run"][i] = 1

        # HIGH vs LOW RESISTANCE. ICT's distinction, and the one Veer named.
        # HIGH resistance: the path to the pool is littered with opposing
        # arrays - the level has been defended 3+ times. LOW resistance: the
        # level was made once and there is clean air to it.
        # ONLY THE NEAREST FEW LEVELS. Scanning all 40 made "a level was run"
        # true on 61% of bars, because with forty levels on the chart price is
        # always running one. The pool that matters is the one just overhead.
        # LIQUIDITY IS TAKEN ONCE. Without consuming the level this stayed
        # true on 60% of bars: three live pools either side, every one of them
        # re-scored on every bar price wicked near it. A pool that has been
        # run is gone - that is what "the stops came out" means - so it is
        # removed here and can never fire again.
        for (p, k) in sorted(liveHi, key=lambda x: abs(x[0] - s.c[i]))[:3]:
            if _run(p, None, s, i, a) == -1:
                F["high-resistance run" if k >= 3 else "low-resistance run"][i] = -1
                liveHi.remove((p, k))
                break
        for (p, k) in sorted(liveLo, key=lambda x: abs(x[0] - s.c[i]))[:3]:
            if _run(None, p, s, i, a) == 1:
                F["high-resistance run" if k >= 3 else "low-resistance run"][i] = 1
                liveLo.remove((p, k))
                break
        # a level price has CLOSED decisively through is also gone - it was a
        # break, not a run, and there are no stops left behind it
        liveHi = [x for x in liveHi if s.c[i] <= x[0] + 0.5 * a]
        liveLo = [x for x in liveLo if s.c[i] >= x[0] - 0.5 * a]

        # TRENDLINE LIQUIDITY: three DESCENDING highs (a drawn trendline) and
        # price runs the newest one. Stops sit along a slope, not a price.
        if len(liveHi) >= 3:
            a1, a2, a3 = liveHi[-3][0], liveHi[-2][0], liveHi[-1][0]
            if a1 > a2 > a3 and _run(a3, None, s, i, a) == -1:
                F["trendline liquidity run"][i] = -1
        if len(liveLo) >= 3:
            b1, b2, b3 = liveLo[-3][0], liveLo[-2][0], liveLo[-1][0]
            if b1 < b2 < b3 and _run(None, b3, s, i, a) == 1:
                F["trendline liquidity run"][i] = 1

        # LIQUIDITY VOID: a bar whose range is 3x ATR with almost no overlap
        # into the next - the gap price is said to return and fill.
        if i >= 1 and rng >= 3.0 * a:
            F["liquidity void"][i] = 1 if s.c[i] < s.o[i] else -1

        # ---- STRUCTURE ---------------------------------------------------
        # INDUCEMENT: the minor pullback high BELOW the major pool. Price is
        # induced to buy there, then that low is taken before the real move.
        if lastMinorLo is not None and len(liveLo) >= 2:
            major = min(x[0] for x in liveLo[-4:])
            if lastMinorLo > major and s.l[i] < lastMinorLo and s.c[i] > lastMinorLo:
                F["inducement taken"][i] = 1
        if lastMinorHi is not None and len(liveHi) >= 2:
            major = max(x[0] for x in liveHi[-4:])
            if lastMinorHi < major and s.h[i] > lastMinorHi and s.c[i] < lastMinorHi:
                F["inducement taken"][i] = -1

        # PROTECTED LEVEL: the swing that CAUSED the last structure break. Its
        # violation is the trend being over, not a pullback.
        bosUp = smcH is not None and s.c[i] > smcH
        bosDn = smcL is not None and s.c[i] < smcL
        if bosUp:
            protLo = lastMinorLo
            if trend < 0:
                F["MSS + displacement"][i] = 1 if disp else 0
            trend, smcH = 1, None
        if bosDn:
            protHi = lastMinorHi
            if trend > 0:
                F["MSS + displacement"][i] = -1 if disp else 0
            trend, smcL = -1, None
        if protLo is not None and s.c[i] < protLo:
            F["protected level broken"][i] = -1
            protLo = None
        if protHi is not None and s.c[i] > protHi:
            F["protected level broken"][i] = 1
            protHi = None

        # INTERNAL structure: a break of the most recent minor swing while
        # price is still inside the wider 60-bar range. External is the range
        # itself breaking, which BOS above already covers.
        hh, ll = max(s.h[i - 60:i]), min(s.l[i - 60:i])
        inside = ll < s.c[i] < hh
        # ONLY THE BAR THAT BREAKS IT. Without the [i-1] test this stayed
        # true for every bar price spent above the level - 278 per 1000 - and
        # a state is not an event.
        if inside and lastMinorHi is not None and s.c[i] > lastMinorHi \
           and s.c[i - 1] <= lastMinorHi:
            F["internal structure break"][i] = 1
        if inside and lastMinorLo is not None and s.c[i] < lastMinorLo \
           and s.c[i - 1] >= lastMinorLo:
            F["internal structure break"][i] = -1

        # ---- PD ARRAYS: the zones ----------------------------------------
        # ORDER BLOCK, kept only so the derived blocks below have parents: the
        # last opposing candle before a displacement bar.
        if i >= 1 and disp:
            prevUp = s.c[i - 1] > s.o[i - 1]
            if s.c[i] > s.o[i] and not prevUp:
                obBull.append([s.h[i - 1], s.l[i - 1], i, False])
            if s.c[i] < s.o[i] and prevUp:
                obBear.append([s.h[i - 1], s.l[i - 1], i, False])
        obBull, obBear = obBull[-30:], obBear[-30:]

        # BREAKER: a bullish order block that FAILED - price closed below it -
        # and price now returns to it from underneath. The failed demand
        # becomes supply. This is the concept people call the highest-quality
        # entry and it has never been measured here.
        for z in obBull[-8:]:
            if not z[3] and s.c[i] < z[1]:
                z[3] = True
            elif z[3] and i - z[2] <= 60 and z[1] <= s.h[i] <= z[0] and s.c[i] < z[1]:
                F["breaker block"][i] = -1
                break
        for z in obBear[-8:]:
            if not z[3] and s.c[i] > z[0]:
                z[3] = True
            elif z[3] and i - z[2] <= 60 and z[1] <= s.l[i] <= z[0] and s.c[i] > z[0]:
                F["breaker block"][i] = 1
                break

        # MITIGATION: price returns to an order block that is still INTACT -
        # it never failed - and reacts. The difference from a breaker is only
        # whether the block was violated first, so scoring them apart is the
        # whole point.
        for z in obBull[-6:]:
            if not z[3] and z[2] < i and z[1] <= s.l[i] <= z[0] and s.c[i] > z[1]:
                F["mitigation block"][i] = 1
                break
        for z in obBear[-6:]:
            if not z[3] and z[2] < i and z[1] <= s.h[i] <= z[0] and s.c[i] < z[0]:
                F["mitigation block"][i] = -1
                break

        # PROPULSION: a block that sits ON a previous block - the second
        # reaction from the same area, said to propel rather than reverse.
        for z in obBull[-6:]:
            for w in obBull[-12:-1]:
                if w is not z and z[1] <= w[0] and z[0] >= w[1] and z[2] == i - 1:
                    F["propulsion block"][i] = 1
                    break

        # REJECTION BLOCK: a cluster of long wicks at one price. The block is
        # the WICKS, not the bodies.
        if i >= 3 and rng > 0:
            up = [(s.h[k] - max(s.o[k], s.c[k])) / max(s.h[k] - s.l[k], 1e-9)
                  for k in range(i - 3, i + 1)]
            dn = [(min(s.o[k], s.c[k]) - s.l[k]) / max(s.h[k] - s.l[k], 1e-9)
                  for k in range(i - 3, i + 1)]
            hs = [s.h[k] for k in range(i - 3, i + 1)]
            ls = [s.l[k] for k in range(i - 3, i + 1)]
            if sum(1 for x in up if x >= 0.5) >= 3 and max(hs) - min(hs) <= 0.5 * a:
                F["rejection block"][i] = -1
            if sum(1 for x in dn if x >= 0.5) >= 3 and max(ls) - min(ls) <= 0.5 * a:
                F["rejection block"][i] = 1

        # FVG, then the things built ON it.
        if i >= 2:
            if s.l[i] > s.h[i - 2] and (s.l[i] - s.h[i - 2]) >= 0.15 * a:
                fvgBull.append([s.l[i], s.h[i - 2], i, False])
            if s.h[i] < s.l[i - 2] and (s.l[i - 2] - s.h[i]) >= 0.15 * a:
                fvgBear.append([s.l[i - 2], s.h[i], i, False])
        fvgBull, fvgBear = fvgBull[-30:], fvgBear[-30:]

        # IFVG: a gap price CLOSED THROUGH. The unfilled gap flips polarity and
        # is traded from the other side.
        for z in fvgBull[-8:]:
            if not z[3] and s.c[i] < z[1]:
                z[3] = True
            elif z[3] and i - z[2] <= 60 and z[1] <= s.h[i] <= z[0] and s.c[i] < z[1]:
                F["IFVG"][i] = -1
                break
        for z in fvgBear[-8:]:
            if not z[3] and s.c[i] > z[0]:
                z[3] = True
            elif z[3] and i - z[2] <= 60 and z[1] <= s.l[i] <= z[0] and s.c[i] > z[0]:
                F["IFVG"][i] = 1
                break

        # CONSEQUENT ENCROACHMENT: the 50% line of an unfilled gap, which is
        # where the entry is supposed to go rather than the gap edge.
        for z in fvgBull[-6:]:
            if not z[3] and z[2] < i:
                ce = (z[0] + z[1]) / 2.0
                if s.l[i] <= ce <= s.h[i] and s.c[i] > ce:
                    F["consequent encroachment"][i] = 1
                    break
        for z in fvgBear[-6:]:
            if not z[3] and z[2] < i:
                ce = (z[0] + z[1]) / 2.0
                if s.l[i] <= ce <= s.h[i] and s.c[i] < ce:
                    F["consequent encroachment"][i] = -1
                    break

        # BPR: a bullish and a bearish gap that OVERLAP. The overlap is the
        # array; it is meant to be far stronger than either gap alone.
        for zb in fvgBull[-8:]:
            for zs in fvgBear[-8:]:
                lo = max(min(zb), min(zs[:2]))
                hi = min(max(zb[:2]), max(zs[:2]))
                if hi - lo >= 0.10 * a and lo <= s.l[i] and s.h[i] <= hi * 1.001 \
                   and lo <= s.c[i] <= hi:
                    F["BPR"][i] = 1 if s.c[i] > s.o[i] else -1
                    break

        # UNICORN: a breaker and an FVG occupying the same price. The
        # much-published "highest probability" array.
        if F["breaker block"][i] != 0:
            dirn = F["breaker block"][i]
            src = fvgBear if dirn > 0 else fvgBull
            for z in src[-8:]:
                if min(z[:2]) <= s.c[i] <= max(z[:2]):
                    F["unicorn"][i] = dirn
                    break

        # VOLUME IMBALANCE: a gap between two BODIES whose wicks still overlap.
        if i >= 1:
            # A GAP NEEDS A SIZE. Without one this fired on 86% of bars,
            # which is not a concept, it is a description of tick data.
            if s.o[i] - s.c[i - 1] >= 0.10 * a and s.l[i] <= s.h[i - 1]:
                F["volume imbalance"][i] = 1
            if s.c[i - 1] - s.o[i] >= 0.10 * a and s.h[i] >= s.l[i - 1]:
                F["volume imbalance"][i] = -1

        # ---- TIME --------------------------------------------------------
        # A killzone is not directional on its own, so it is scored in the
        # direction of the bar that closed inside it. If that reads as noise
        # in the results, that IS the finding - a time window is a filter, not
        # a signal, and this is what testing it as a signal looks like.
        hr = d.hour
        binv = 1 if s.c[i] > s.o[i] else -1
        if 7 <= hr < 10:
            F["London killzone"][i] = binv
        if 12 <= hr < 15:
            F["NY killzone"][i] = binv
        if hr == 15:
            F["silver bullet hour"][i] = binv

        # JUDAS SWING: the first move out of the Asia range after London opens
        # that is then rejected - the false start before the real direction.
        if 7 <= hr < 11 and ash[i] is not None and asl[i] is not None:
            r = _run(ash[i], asl[i], s, i, a)
            if r != 0:
                F["judas swing"][i] = r

        # POWER OF 3 / AMD: manipulation below the day's open in the morning,
        # then distribution up. Scored as: price is on the wrong side of the
        # true day open during the killzone and closes back across it.
        if dayOpen is not None and 7 <= hr < 15:
            if s.l[i] < dayOpen and s.c[i] > dayOpen:
                F["power of 3"][i] = 1
            if s.h[i] > dayOpen and s.c[i] < dayOpen:
                F["power of 3"][i] = -1

        # ---- SMT DIVERGENCE ----------------------------------------------
        # This market makes a new 20-bar extreme and the correlated one does
        # NOT. The classic non-confirmation.
        if other is not None and i >= 20:
            j = om.get(s.ts[i])
            if j is not None and j >= 20:
                mineHi = s.h[i] >= max(s.h[i - 20:i])
                mineLo = s.l[i] <= min(s.l[i - 20:i])
                thHi = other.h[j] >= max(other.h[j - 20:j])
                thLo = other.l[j] <= min(other.l[j - 20:j])
                if mineHi and not thHi:
                    F["SMT divergence"][i] = -1
                if mineLo and not thLo:
                    F["SMT divergence"][i] = 1
    return F


# ===========================================================================
# E-196 — THE CORRECTIONS SMC_SPEC.md FORCED.
#
# Two of E-195's features were implemented from my reading rather than from a
# published source, and the spec agent's survey of ~45 indicator sources says
# both readings were wrong in a way that is testable:
#
# 1. HIGH/LOW-RESISTANCE LIQUIDITY. I counted how many SWINGS FORMED at the
#    level - the size of the equal-highs cluster. Every prose source measures
#    something else: how many UNSWEPT OPPOSING SWINGS sit BETWEEN price and
#    the target pool. The two are different numbers and only one of them is
#    what ICT means. Since "low-resistance run" is E-195's strongest single
#    finding, the canonical version has to be scored or the finding is mine
#    and not the concept's.
#
# 2. KILLZONES. I used 07:00-10:00 and 12:00-15:00 UTC. The spec's table of
#    six published scripts says the majority define them in America/New_York,
#    which in EDT is 06:00-09:00 and 11:00-14:00 UTC - so my windows were an
#    HOUR LATE for the ~8 months a year the US is on DST. They scored
#    0.45-0.81. A window an hour off is a good reason for that, and it has to
#    be ruled out before "killzones do not mark leg starts" can stand.
# ===========================================================================
def features_v2(s, A, pv=3, tol=0.10, clear=0.05, hrlrN=2):
    """The corrected pair, plus the honest renaming of the originals."""
    try:
        from zoneinfo import ZoneInfo
        NY = ZoneInfo("America/New_York")
    except Exception:
        NY = None
    n = len(s)
    K = ("LRLR (clean path)", "HRLR (2+ in the way)",
         "pool defended once", "pool defended 3+",
         "London open KZ (tz-correct)", "NY AM narrow KZ (tz-correct)",
         "NY AM wide KZ (tz-correct)", "NY PM KZ (tz-correct)",
         "silver bullet (tz-correct)")
    F = {k: [0] * n for k in K}

    hi_at, lo_at = _pivots(s, pv)
    liveHi, liveLo = [], []          # (price, swings_that_formed_here)
    for i in range(n):
        a = A[i] if A[i] else 0.0
        if i in hi_at:
            p = hi_at[i]
            m = next((x for x in liveHi if abs(x[0] - p) <= tol * max(a, 1e-9)), None)
            if m:
                liveHi.remove(m)
                liveHi.append((max(m[0], p), m[1] + 1))
            else:
                liveHi.append((p, 1))
            liveHi = liveHi[-40:]
        if i in lo_at:
            p = lo_at[i]
            m = next((x for x in liveLo if abs(x[0] - p) <= tol * max(a, 1e-9)), None)
            if m:
                liveLo.remove(m)
                liveLo.append((min(m[0], p), m[1] + 1))
            else:
                liveLo.append((p, 1))
            liveLo = liveLo[-40:]
        if a <= 0 or i < 80:
            continue

        # ---- THE RUN, identical to E-195's so only the LABEL differs -----
        d = 0
        cnt = 0
        for (p, k) in sorted(liveHi, key=lambda x: abs(x[0] - s.c[i]))[:3]:
            if s.h[i] > p + clear * a and s.c[i] < p:
                d, cnt = -1, k
                liveHi.remove((p, k))
                break
        if d == 0:
            for (p, k) in sorted(liveLo, key=lambda x: abs(x[0] - s.c[i]))[:3]:
                if s.l[i] < p - clear * a and s.c[i] > p:
                    d, cnt = 1, k
                    liveLo.remove((p, k))
                    break
        liveHi = [x for x in liveHi if s.c[i] <= x[0] + 0.5 * a]
        liveLo = [x for x in liveLo if s.c[i] >= x[0] - 0.5 * a]

        if d != 0:
            # E-195's labels, renamed to what they ACTUALLY measure. "Defended
            # once" is the size of the equal-highs cluster at the level, not
            # the resistance on the path to it.
            F["pool defended 3+" if cnt >= 3 else "pool defended once"][i] = d

            # THE CANONICAL VERSION. Target = the opposing pool. Resistance =
            # the count of UNSWEPT opposing swings strictly BETWEEN price and
            # that target. Zero in the way is LRLR; two or more is HRLR.
            if d > 0 and liveHi:
                tgt = max(x[0] for x in liveHi)
                res = sum(1 for (p, _) in liveHi if s.c[i] < p < tgt)
            elif d < 0 and liveLo:
                tgt = min(x[0] for x in liveLo)
                res = sum(1 for (p, _) in liveLo if tgt < p < s.c[i])
            else:
                res = None
            if res is not None:
                if res == 0:
                    F["LRLR (clean path)"][i] = d
                elif res >= hrlrN:
                    F["HRLR (2+ in the way)"][i] = d

        # ---- KILLZONES, converted from New York with real DST ------------
        if NY is not None:
            t = _dt.datetime.fromtimestamp(s.ts[i], NY)
            mins = t.hour * 60 + t.minute
            bi = 1 if s.c[i] > s.o[i] else -1
            if 2 * 60 <= mins < 5 * 60:
                F["London open KZ (tz-correct)"][i] = bi
            if 8 * 60 + 30 <= mins < 11 * 60:
                F["NY AM narrow KZ (tz-correct)"][i] = bi
            if 7 * 60 <= mins < 10 * 60:
                F["NY AM wide KZ (tz-correct)"][i] = bi
            if 13 * 60 + 30 <= mins < 16 * 60:
                F["NY PM KZ (tz-correct)"][i] = bi
            if 10 * 60 <= mins < 11 * 60:
                F["silver bullet (tz-correct)"][i] = bi
    return F

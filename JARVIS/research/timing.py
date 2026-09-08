"""
DOES THE CLOCK PREDICT WHERE LEGS START, AND HOW BIG THEY ARE?

The one dimension this project has never tested. E-184 asked WHAT marks a leg
start (mean reversion at an extreme: 1.2-2.2x lift). E-185 asked WHERE it is
going. Neither asked WHEN.

METHOD. Identical machinery to E-184 and deliberately so - `legs()`,
`features()` and `score()` are imported from legcatch.py unchanged. A clock
bucket (an hour, a killzone, a weekday) is turned into a feature series that
fires on every bar inside the bucket, and is scored with `score()` against a
TIME-SHIFTED copy of itself. The shift preserves the bucket's shape and
frequency and destroys only its alignment to the clock, so the control is
"the same number of bars, at other times of day".

TWO DEVIATIONS FROM E-184, both stated up front:

1. slack = 0 for clock buckets. E-184 allowed a signal to fire up to 3 bars
   before the extreme, because a signal lags the turn it is trying to call.
   A clock does not lag anything - it is known in advance - and slack=3 on a
   1h chart would smear "hour 7" across 07:00-10:00, which is the very thing
   under test. So a clock bucket catches a leg only if the leg's starting
   extreme forms INSIDE the bucket. Q7 (the E-184 catcher split by hour) uses
   slack=3, because there the signal is the catcher and the clock is only a
   filter on it.

2. Clock buckets have no direction. E-184's features are +1/-1 and `score()`
   only counts a catch when the leg direction matches. So each bucket is
   scored TWICE - once as an all-+1 mask (up legs), once as an all--1 mask
   (down legs) - and the two are pooled. `score()` itself is untouched.

TIMEZONES, and this matters more than anything else in the file. All three
files were VERIFIED against two independent physical anchors before any hour
was scored, because a timing study on mislabelled hours is worse than no study.

  ANCHOR 1, the CME daily break (17:00 New York, so 21:00 UTC under US DST
  and 22:00 UTC outside it). GOLD_1h.json is missing hour 21 in Mar-Oct and
  hour 22 in Nov-Feb. GOLD_M1_2018.json is missing hour 22 on 42 of 42
  Jan-Feb days and hour 21 on 55 of 55 Apr-Jun days, switching during March -
  US DST began 11 Mar 2018.

  ANCHOR 2, the 08:30 New York data releases, visible on M1 as the single
  largest minute of the day. In GOLD_M1_2018.json that minute is 13:30 in
  Jan-Mar and 12:30 in Apr-Jun - i.e. 08:30 ET both times. The London PM fix
  lands at 15:00 and 14:00 the same way.

  ALL THREE FILES ARE TRUE UTC. An earlier draft of this file "corrected"
  GOLD_M1_2018.json by -2/-3h on the theory that its empty 00:00 hour was an
  MT5 EET server break. Both anchors say that was wrong: 00:00-01:00 UTC is
  simply ABSENT FROM THE EXPORT on every single day of that file, and the
  real break sits where UTC says it should. The correction has been removed.
  It is recorded here because it would have moved every 2018 hour label by
  two hours - the difference between "London open" and "Frankfurt open" - and
  the only reason it did not survive is that it was checked against an event
  whose clock is known independently.

The 2018 M1 sample is SECONDARY ONLY (E-188's rule: a result from that file is
a hypothesis about 2018). Anything that appears only there is reported as
worthless.
"""
from __future__ import annotations
import datetime as dt
import json, math, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Series, atr as watr
from regime import load_plain, resample
from legcatch import legs, features, score

SEEDS = (7, 11, 13)          # 3 x 5 = 15 time-shifted control draws per cell
CELLS = 0                    # every scored cell is counted, for multiplicity


# ------------------------------------------------------------- the clock ---
def clock(s):
    """Hour and weekday, UTC. Every file in this study is UTC - see the
    header for the two anchors that establish it. There is deliberately no
    timezone-correction parameter any more: the one that used to be here was
    wrong, and an unused knob is an invitation to be wrong again."""
    hh, dw = [], []
    for t in s.ts:
        d = dt.datetime.utcfromtimestamp(t)
        hh.append(d.hour)
        dw.append(d.weekday())
    return hh, dw


# ------------------------------------------------- clock verification ------
def verify_clock():
    """The two anchors, computed rather than asserted. Nothing downstream is
    meaningful if these do not line up, so they run first, every time."""
    print("\n  ---- clock verification: is every file really UTC? ----")
    for name in ("GOLD_1h.json", "GOLD_M1_2018.json"):
        rows = json.load(open(f"/home/user/signals/data/{name}"))
        have = {}
        for r in rows:
            d = dt.datetime.utcfromtimestamp(r[0])
            have.setdefault(d.date(), set()).add(d.hour)
        miss = {}
        for d, hs in have.items():
            if len(hs) > 18:
                key = "US-DST (Mar-Oct)" if 3 <= d.month <= 10 else "no DST"
                m = miss.setdefault(key, [0, 0, 0])
                m[0] += 1
                m[1] += 0 if 21 in hs else 1
                m[2] += 0 if 22 in hs else 1
        print(f"  {name}: CME break (17:00 New York) should be 21:00 UTC "
              f"under US DST, else 22:00")
        for k, (n, a, b) in miss.items():
            print(f"     {k:<18} {n:>4} days: hour21 missing {a:>4}, "
                  f"hour22 missing {b:>4}")
    rows = json.load(open("/home/user/signals/data/GOLD_M1_2018.json"))
    print("  GOLD_M1_2018: biggest minute of the day = 08:30 New York?")
    for tag, lo, hi in (("Jan-Mar (EST, 08:30ET = 13:30 UTC)",
                         dt.datetime(2018, 1, 1), dt.datetime(2018, 3, 11)),
                        ("Apr-Jun (EDT, 08:30ET = 12:30 UTC)",
                         dt.datetime(2018, 3, 12), dt.datetime(2018, 7, 1))):
        acc = {}
        for r in rows:
            d = dt.datetime.utcfromtimestamp(r[0])
            if lo <= d < hi and d.weekday() < 5:
                acc.setdefault(d.hour * 60 + d.minute, []).append(r[2] - r[3])
        m = {k: statistics.fmean(v) for k, v in acc.items() if len(v) > 20}
        top = sorted(m.items(), key=lambda kv: -kv[1])[:3]
        print(f"     {tag}: " + ", ".join(f"{k//60:02d}:{k%60:02d}={v:.2f}"
                                          for k, v in top))


# ---------------------------------------------------------------- scoring --
def cell(mask, lg, n, slack=0):
    """Pool the up-scored and down-scored halves of one directionless mask.

    Returns (fired, legs_caught, rate, ctrl, lift, z, mean_leg_atr).
    `rate` is leg starts per bar inside the bucket; `ctrl` is the same for the
    time-shifted twin. z treats bars as independent, which is optimistic - the
    half-split, not z, is what a claim has to survive.
    """
    global CELLS
    CELLS += 1
    fired = sum(1 for v in mask if v)
    if fired < 30:
        return fired, 0, 0.0, 0.0, 0.0, 0.0, 0.0
    up = [1 if v else 0 for v in mask]
    dn = [-1 if v else 0 for v in mask]
    R = {"u": 0.0, "d": 0.0}
    C = {"u": 0.0, "d": 0.0}
    P = {"u": 0.0, "d": 0.0}
    for sd in SEEDS:
        rows, base, _ = score({"u": up, "d": dn}, lg, n, slack=slack, seed=sd)
        for (name, f, rate, ctrl, lift, avg) in rows:
            R[name] = rate
            C[name] += ctrl / len(SEEDS)
            P[name] = avg
    rate = R["u"] + R["d"]
    ctrl = C["u"] + C["d"]
    caught = int(round(rate * fired))
    cu, cd = R["u"] * fired, R["d"] * fired
    avg = (P["u"] * cu + P["d"] * cd) / max(cu + cd, 1e-9)
    lift = rate / ctrl if ctrl > 0 else 0.0
    z = 0.0
    if 0 < ctrl < 1:
        z = (rate - ctrl) * fired / math.sqrt(fired * ctrl * (1 - ctrl))
    return fired, caught, rate, ctrl, lift, z, avg


def table(title, s, lg, n, buckets, slack=0, note=""):
    print(f"\n  {title}{note}")
    print(f"  {'bucket':<26}{'bars':>7}{'legs':>7}{'rate':>8}{'ctrl':>8}"
          f"{'LIFT':>7}{'z':>7}{'meanleg':>9}")
    print("  " + "-" * 79)
    out = {}
    for name, mask in buckets:
        f, c, r, ct, lf, z, a = cell(mask, lg, n, slack=slack)
        out[name] = (f, c, lf, z, a)
        if c < 40:
            print(f"  {name:<26}{f:>7}{c:>7}   too few")
            continue
        star = " <<<" if lf >= 1.25 and z >= 2 else ""
        print(f"  {name:<26}{f:>7}{c:>7}{100*r:>7.1f}%{100*ct:>7.1f}%"
              f"{lf:>7.2f}{z:>7.1f}{a:>8.2f}A{star}")
    return out


# --------------------------------------------------------------- buckets ---
KZ = {"Asian 00-05": range(0, 5),
      "London 07-10": range(7, 10),
      "NY AM 12-15": range(12, 15),
      "NY PM 18-20": range(18, 20)}
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def hour_buckets(hh):
    return [(f"hour {h:02d} UTC", [1 if x == h else 0 for x in hh])
            for h in range(24)]


def kz_buckets(hh):
    b = [(k, [1 if x in v else 0 for x in hh]) for k, v in KZ.items()]
    allkz = set()
    for v in KZ.values():
        allkz |= set(v)
    b.append(("outside all killzones", [1 if x not in allkz else 0 for x in hh]))
    return b


def dow_buckets(dw):
    return [(DOW[d], [1 if x == d else 0 for x in dw]) for d in range(5)]


def open_buckets(hh):
    return [("Asia  first hour  00", [1 if x == 0 else 0 for x in hh]),
            ("Asia  rest     01-04", [1 if 1 <= x <= 4 else 0 for x in hh]),
            ("Lon   first hour  07", [1 if x == 7 else 0 for x in hh]),
            ("Lon   rest     08-09", [1 if 8 <= x <= 9 else 0 for x in hh]),
            ("NYAM  first hour  12", [1 if x == 12 else 0 for x in hh]),
            ("NYAM  rest     13-14", [1 if 13 <= x <= 14 else 0 for x in hh]),
            ("NYPM  first hour  18", [1 if x == 18 else 0 for x in hh]),
            ("NYPM  rest        19", [1 if x == 19 else 0 for x in hh])]


def overlap_buckets(hh):
    return [("OVERLAP Lon+NY 12-15", [1 if 12 <= x <= 14 else 0 for x in hh]),
            ("London only    07-11", [1 if 7 <= x <= 11 else 0 for x in hh]),
            ("NY only        15-20", [1 if 15 <= x <= 20 else 0 for x in hh]),
            ("Asia only      00-06", [1 if x <= 6 else 0 for x in hh])]


# ------------------------------------------------------- descriptive only --
def describe(label, s, A, hh, lg):
    """NOT a result. Bars, mean true range and leg-start count per hour, so
    the reader can see what the sample IS before any lift is claimed."""
    n = len(s)
    st = {}
    for (b0, b1, d, sz) in lg:
        st.setdefault(b0, []).append(sz)
    print(f"\n  ---- {label}: what the clock looks like (descriptive) ----")
    print(f"  {'h':>3}{'bars':>7}{'rangeATR':>10}{'legstarts':>11}"
          f"{'per100bar':>11}{'meanleg':>9}")
    for h in range(24):
        idx = [i for i in range(n) if hh[i] == h and A[i]]
        if not idx:
            continue
        rng = statistics.fmean((s.h[i] - s.l[i]) / A[i] for i in idx)
        ls = [z for i in idx for z in st.get(i, [])]
        m = statistics.fmean(ls) if ls else 0.0
        print(f"  {h:>3}{len(idx):>7}{rng:>10.2f}{len(ls):>11}"
              f"{100*len(ls)/len(idx):>11.1f}{m:>9.2f}A")


# ------------------------------------------------- Q4: the judas swing -----
def asian_levels(s, hh):
    """Per UTC day, the 00:00-05:00 high/low, usable only from 05:00 on."""
    n = len(s)
    day = [dt.datetime.utcfromtimestamp(t).date() for t in s.ts]
    hi, lo = {}, {}
    for i in range(n):
        if hh[i] < 5:
            d = day[i]
            hi[d] = max(hi.get(d, -1e18), s.h[i])
            lo[d] = min(lo.get(d, 1e18), s.l[i])
    return day, hi, lo


def judas(s, hh, window):
    """Sweep of the Asian range, closing back inside, during `window` hours.
    +1 = swept the LOW and closed back above (expect an UP leg).
    -1 = swept the HIGH and closed back below (expect a DOWN leg).
    """
    n = len(s)
    day, hi, lo = asian_levels(s, hh)
    out = [0] * n
    for i in range(n):
        if hh[i] not in window or hh[i] < 5:
            continue
        d = day[i]
        if d not in hi:
            continue
        if s.h[i] > hi[d] and s.c[i] < hi[d]:
            out[i] = -1
        elif s.l[i] < lo[d] and s.c[i] > lo[d]:
            out[i] = 1
    return out


def directional(title, F, lg, n, slack=3):
    """Directional features (judas etc) go through score() as they are."""
    global CELLS
    print(f"\n  {title}")
    print(f"  {'feature':<30}{'fires':>7}{'catch':>8}{'ctrl':>8}"
          f"{'LIFT':>7}{'legs':>7}{'meanleg':>9}")
    print("  " + "-" * 76)
    acc = {}
    for k in F:
        acc[k] = [0.0, 0.0, 0.0, 0]
    for sd in SEEDS:
        rows, base, _ = score(F, lg, n, slack=slack, seed=sd)
        for (name, f, rate, ctrl, lift, avg) in rows:
            acc[name][0] = rate
            acc[name][1] += ctrl / len(SEEDS)
            acc[name][2] = avg
            acc[name][3] = f
    for name, (rate, ctrl, avg, f) in acc.items():
        CELLS += 1
        c = int(round(rate * f))
        if f < 30 or c < 40:
            print(f"  {name:<30}{f:>7}{c:>8}   too few")
            continue
        lift = rate / ctrl if ctrl else 0.0
        print(f"  {name:<30}{f:>7}{100*rate:>7.1f}%{100*ctrl:>7.1f}%"
              f"{lift:>7.2f}{c:>7}{avg:>8.2f}A")


# --------------------------------------- Q7: the E-184 catcher, by clock ---
def catcher(s, A, V=None, need=2):
    """E-184's mean-reversion stack, rebuilt exactly as legcatch.combo does."""
    F = features(s, A, V)
    keep = ["stretched from 50 EMA", "premium / discount",
            "60%+ rejection wick", "equal highs taken", "equal lows taken"]
    if V:
        keep.append("volume x2 at the bar")
    keep = [k for k in keep if k in F]
    n = len(s)
    out = [0] * n
    for i in range(n):
        up = sum(1 for k in keep if F[k][i] > 0)
        dn = sum(1 for k in keep if F[k][i] < 0)
        if up > dn and up >= need:
            out[i] = 1
        elif dn > up and dn >= need:
            out[i] = -1
    return out


def catcher_by_clock(label, s, A, lg, hh, V=None, need=2):
    n = len(s)
    sig = catcher(s, A, V, need=need)
    F = {"catcher, ALL hours": sig}
    for k, v in KZ.items():
        F[f"catcher in {k}"] = [sig[i] if hh[i] in v else 0 for i in range(n)]
    allkz = set()
    for v in KZ.values():
        allkz |= set(v)
    F["catcher outside killzones"] = [sig[i] if hh[i] not in allkz else 0
                                      for i in range(n)]
    F["catcher in overlap 12-15"] = [sig[i] if 12 <= hh[i] <= 14 else 0
                                     for i in range(n)]
    directional(f"---- {label}: E-184 catcher (need>={need}) split by clock, "
                f"slack=3 ----", F, lg, n, slack=3)


# ------------------------------------------------------------ the driver ---
def run(label, s, V=None, do_desc=True, do_catcher=True, need=2):
    hh, dw = clock(s)
    A = watr(s, 14)
    lg = legs(s, A, pv=3, minAtr=2.0)
    n = len(s)
    nst = len(lg)
    print("\n" + "=" * 84)
    print(f"  {label}   {n:,} bars, {nst} legs of >=2 ATR, "
          f"base {100*nst/n:.1f} leg starts per 100 bars")
    print("=" * 84)
    if len(lg) < 60:
        print("  too few legs in this sample, skipping")
        return
    if do_desc:
        describe(label, s, A, hh, lg)
    table("---- Q1  hour of day (UTC) ----", s, lg, n, hour_buckets(hh))
    table("---- Q2  ICT killzones ----", s, lg, n, kz_buckets(hh))
    table("---- Q3  day of week ----", s, lg, n, dow_buckets(dw))
    table("---- Q5  first hour of a session vs the rest ----",
          s, lg, n, open_buckets(hh))
    table("---- Q6  session overlap vs single session ----",
          s, lg, n, overlap_buckets(hh))
    J = {"judas: Asia swept 07-10": judas(s, hh, set(range(7, 10))),
         "Asia swept 10-12": judas(s, hh, set(range(10, 12))),
         "Asia swept 12-15": judas(s, hh, set(range(12, 15))),
         "Asia swept 15-21": judas(s, hh, set(range(15, 21))),
         "Asia swept any hour 05+": judas(s, hh, set(range(5, 24)))}
    directional("---- Q4  Asian-range sweep / judas swing, slack=3 ----",
                J, lg, n, slack=3)
    if do_catcher:
        catcher_by_clock(label, s, A, lg, hh, V=V, need=need)


def halves(label, s, buckets=("kz", "dow", "overlap")):
    """Anything that looked good gets re-run on each half of its own sample."""
    n2 = len(s) // 2
    for tag, seg in (("FIRST half", Series(s.ts[:n2], s.o[:n2], s.h[:n2],
                                           s.l[:n2], s.c[:n2])),
                     ("SECOND half", Series(s.ts[n2:], s.o[n2:], s.h[n2:],
                                            s.l[n2:], s.c[n2:]))):
        hh, dw = clock(seg)
        A = watr(seg, 14)
        lg = legs(seg, A, pv=3, minAtr=2.0)
        n = len(seg)
        d0 = dt.datetime.utcfromtimestamp(seg.ts[0]).date()
        d1 = dt.datetime.utcfromtimestamp(seg.ts[-1]).date()
        print(f"\n  ~~~~ {label} {tag}  {d0} to {d1}  "
              f"{n:,} bars {len(lg)} legs ~~~~")
        if len(lg) < 60:
            print("  too few legs")
            continue
        if "kz" in buckets:
            table("Q2 killzones", seg, lg, n, kz_buckets(hh))
        if "dow" in buckets:
            table("Q3 day of week", seg, lg, n, dow_buckets(dw))
        if "overlap" in buckets:
            table("Q6 overlap", seg, lg, n, overlap_buckets(hh))
        if "hour" in buckets:
            table("Q1 hour of day", seg, lg, n, hour_buckets(hh))


def load_m1_2018():
    rows = json.load(open("/home/user/signals/data/GOLD_M1_2018.json"))
    rows.sort(key=lambda r: r[0])
    s = Series([r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows],
               [r[3] for r in rows], [r[4] for r in rows])
    V = [r[7] for r in rows] if len(rows[0]) > 7 else None
    return s, V


def main():
    print("=" * 84)
    print("  WHEN do legs start? Clock buckets scored with legcatch.score(),")
    print("  every one against a TIME-SHIFTED copy of itself. slack=0 for")
    print("  clock buckets (a clock does not lag), slack=3 for signals.")
    print("=" * 84)
    verify_clock()

    h1 = load_plain("GOLD_1h.json")
    run("PRIMARY  GOLD 1h  Apr2024-Aug2026 (UTC)", h1)

    m15 = load_plain("GOLD_15m.json")
    run("GOLD 15m  Jun-Aug 2026 (UTC)", m15, do_desc=False)

    m1, V = load_m1_2018()
    run("SECONDARY (2018 ONLY, E-188 rule) GOLD M1 Jan-Jun 2018 UTC "
        "(00:00-01:00 absent from the export)", m1, V=V, do_desc=True)

    print("\n" + "=" * 84)
    print("  OUT OF SAMPLE — every sample split in half, same buckets")
    print("=" * 84)
    halves("1h", h1, buckets=("kz", "dow", "overlap", "hour"))
    halves("15m", m15)
    halves("M1 2018", m1)

    print(f"\n  CELLS SCORED IN TOTAL: {CELLS}")




# ==========================================================================
#  PART 2 — IS IT THE CLOCK, OR IS IT THE YARDSTICK?
#
#  Part 1 found leg starts piled into 12:00-15:00 UTC on 1h and 15m data and
#  found NOTHING on 2018 M1. Two explanations, and they are not the same fact:
#
#   (a) REGIME. Gold in 2024-2026 is driven by the US session; gold in 2018
#       was a quiet range. Then the effect is real and modern.
#   (b) YARDSTICK. A leg must be >= 2 x ATR(14). On 1h that ATR spans 14
#       HOURS, so it is a daily average and cannot know that 13:00 moves
#       2.5x as fast as 04:00 - every fast hour clears the bar easily. On M1
#       ATR(14) spans 14 MINUTES and tracks the intraday volatility cycle
#       almost perfectly, so it normalises the clock away by construction.
#       Then the finding is "moves are BIGGER in NY AM", not "turns happen
#       there", and those imply different indicators.
#
#  Four tests that separate them. None of them is optional, because (b) would
#  make the headline number an artefact of a measurement choice.
# ==========================================================================
def hourly_points(label, s, hh):
    """Movement in POINTS by hour - no leg definition, no ATR, no control.
    CLAUDE.md E-074: expectancy is not money. This is the raw fact in the
    unit that pays, split in half so its stability is visible."""
    n = len(s)
    half = n // 2
    print(f"\n  ---- {label}: mean bar range in POINTS by hour (descriptive) ----")
    print(f"  {'h':>3}{'bars':>7}{'points':>9}{'1st half':>10}{'2nd half':>10}"
          f"{'x median hr':>13}")
    allr = []
    per = {}
    for h in range(24):
        a = [s.h[i] - s.l[i] for i in range(n) if hh[i] == h]
        b1 = [s.h[i] - s.l[i] for i in range(half) if hh[i] == h]
        b2 = [s.h[i] - s.l[i] for i in range(half, n) if hh[i] == h]
        if len(a) < 30:
            continue
        per[h] = (len(a), statistics.fmean(a),
                  statistics.fmean(b1) if len(b1) > 10 else float("nan"),
                  statistics.fmean(b2) if len(b2) > 10 else float("nan"))
        allr.append(statistics.fmean(a))
    med = statistics.median(allr)
    for h, (c, m, m1, m2) in per.items():
        print(f"  {h:>3}{c:>7}{m:>9.2f}{m1:>10.2f}{m2:>10.2f}{m/med:>13.2f}")


def pivot_rate(label, s, hh):
    """The same buckets, but a 'leg' is ANY pivot-to-pivot swing, no size
    filter at all. A pivot is scale-free: a 7-bar extreme is a 7-bar extreme
    whatever the volatility. If turning points themselves cluster by hour this
    stays lifted; if only SIZE clusters, this goes flat."""
    A = watr(s, 14)
    lg = legs(s, A, pv=3, minAtr=0.0)
    print(f"\n  ---- {label}: turning points with NO size filter "
          f"({len(lg)} pivots) ----")
    table("Q2 killzones, minAtr=0", s, lg, len(s), kz_buckets(hh))


def hour_factor(s, A, hh, upto=None):
    """Relative volatility of each hour: mean (bar range / ATR14), scaled to
    average 1.0. Estimated on bars [0, upto) only, so it can be fitted on one
    half and applied to the other."""
    n = upto if upto else len(s)
    acc = {}
    for i in range(20, n):
        if A[i]:
            acc.setdefault(hh[i], []).append((s.h[i] - s.l[i]) / A[i])
    f = {h: statistics.fmean(v) for h, v in acc.items() if len(v) >= 20}
    m = statistics.fmean(f.values())
    return {h: v / m for h, v in f.items()}


def normed(label, s, hh, fit_upto=None, tag=""):
    """Legs measured against an hour-of-day-NORMALISED yardstick: 2 ATR at
    04:00 UTC now means 'twice as big as 04:00 usually is', not 'twice the
    daily average'. This asks whether NY AM starts more legs THAT ARE BIG FOR
    THEIR OWN HOUR."""
    A = watr(s, 14)
    f = hour_factor(s, A, hh, upto=fit_upto)
    An = [A[i] * f.get(hh[i], 1.0) if A[i] else A[i] for i in range(len(s))]
    lg = legs(s, An, pv=3, minAtr=2.0)
    print(f"\n  ---- {label}: hour-NORMALISED yardstick{tag} "
          f"({len(lg)} legs) ----")
    print("  factors: " + " ".join(f"{h}:{f.get(h,float('nan')):.2f}"
                                   for h in range(24)))
    table("Q2 killzones, normalised ATR", s, lg, len(s), kz_buckets(hh))
    table("Q1 hour, normalised ATR", s, lg, len(s), hour_buckets(hh))


def main2():
    print("\n" + "=" * 84)
    print("  PART 2 — is the NY AM result the CLOCK or the YARDSTICK?")
    print("=" * 84)

    h1 = load_plain("GOLD_1h.json")
    hh1, _ = clock(h1)
    m15 = load_plain("GOLD_15m.json")
    hh15, _ = clock(m15)
    m1, V = load_m1_2018()
    m1u = m1
    hhm1, _ = clock(m1u)

    print("\n### TEST A — the raw movement, in points, by hour")
    hourly_points("1h 2024-2026", h1, hh1)
    hourly_points("15m 2026", m15, hh15)
    hourly_points("M1 2018 (secondary)", m1u, hhm1)

    print("\n### TEST B — turning points with no size filter")
    pivot_rate("1h 2024-2026", h1, hh1)
    pivot_rate("15m 2026", m15, hh15)
    pivot_rate("M1 2018 (secondary)", m1u, hhm1)

    print("\n### TEST C — legs measured on an hour-normalised yardstick")
    normed("1h 2024-2026", h1, hh1, tag=" (factors from WHOLE sample)")
    n2 = len(h1) // 2
    normed("1h 2024-2026", h1, hh1, fit_upto=n2,
           tag=" (factors from FIRST half only)")
    normed("15m 2026", m15, hh15, tag=" (factors from WHOLE sample)")

    print("\n### TEST D — 2018 M1 RESAMPLED to 15m and 1h.")
    print("  Same bars, same year, only the yardstick's horizon changes.")
    print("  If NY AM lifts here, the 2024-26 result is about MEASUREMENT")
    print("  SCALE. If it stays flat, the 2024-26 result is about the REGIME.")
    for fac, name in ((15, "15m"), (60, "1h")):
        r = resample(m1u, fac)
        hh, dw = clock(r)
        A = watr(r, 14)
        lg = legs(r, A, pv=3, minAtr=2.0)
        print(f"\n  ---- M1 2018 resampled to {name}: {len(r):,} bars, "
              f"{len(lg)} legs ----")
        if len(lg) < 60:
            print("  too few legs")
            continue
        table(f"Q2 killzones, 2018 @ {name}", r, lg, len(r), kz_buckets(hh))
        table(f"Q6 overlap, 2018 @ {name}", r, lg, len(r),
              overlap_buckets(hh))
    print(f"\n  CELLS SCORED IN TOTAL (parts 1+2): {CELLS}")




# ==========================================================================
#  PART 3 — the two cells that survived Part 2, split in half
#
#  Part 2 killed most of Part 1: normalise the yardstick for the hour of day
#  and NY AM's 1.90 collapses to 1.01-1.12. Two things did not die and they
#  are the only ones that get a half-split, because a half-split is expensive
#  and running it on everything is how you launder noise into a result.
#
#   1. Q7 - the E-184 catcher fires better inside 12:00-15:00 UTC (1.52 on
#      1h, 2.13 on 15m). If it holds in both halves it is the one clock fact
#      with a use.
#   2. Test C's hour-12 cell - the only hour that kept a lift after the
#      yardstick was normalised. Cross-fitted here: the hour factors are
#      estimated on ONE half and the legs are scored on the OTHER, so the
#      normalisation cannot see the data it is judged on.
# ==========================================================================
def main3():
    print("\n" + "=" * 84)
    print("  PART 3 — the survivors of Part 2, on each half separately")
    print("=" * 84)

    for name, s in (("1h 2024-2026", load_plain("GOLD_1h.json")),
                    ("15m 2026", load_plain("GOLD_15m.json"))):
        n2 = len(s) // 2
        for tag, seg in (("FIRST half", Series(s.ts[:n2], s.o[:n2], s.h[:n2],
                                               s.l[:n2], s.c[:n2])),
                         ("SECOND half", Series(s.ts[n2:], s.o[n2:], s.h[n2:],
                                                s.l[n2:], s.c[n2:]))):
            hh, _ = clock(seg)
            A = watr(seg, 14)
            lg = legs(seg, A, pv=3, minAtr=2.0)
            if len(lg) < 60:
                print(f"\n  {name} {tag}: only {len(lg)} legs")
                continue
            catcher_by_clock(f"{name} {tag}", seg, A, lg, hh)

    print("\n  ---- Test C cross-fitted: hour factors from the OTHER half ----")
    s = load_plain("GOLD_1h.json")
    hh, _ = clock(s)
    A = watr(s, 14)
    n2 = len(s) // 2
    fa = hour_factor(s, A, hh, upto=n2)
    accB = {}
    for i in range(n2, len(s)):
        if A[i]:
            accB.setdefault(hh[i], []).append((s.h[i] - s.l[i]) / A[i])
    fb = {h: statistics.fmean(v) for h, v in accB.items() if len(v) >= 20}
    mb = statistics.fmean(fb.values())
    fb = {h: v / mb for h, v in fb.items()}
    for tag, lo, hi, f in (("FIRST half scored with SECOND half's factors",
                            0, n2, fb),
                           ("SECOND half scored with FIRST half's factors",
                            n2, len(s), fa)):
        seg = Series(s.ts[lo:hi], s.o[lo:hi], s.h[lo:hi], s.l[lo:hi],
                     s.c[lo:hi])
        h2, _ = clock(seg)
        A2 = watr(seg, 14)
        An = [A2[i] * f.get(h2[i], 1.0) if A2[i] else A2[i]
              for i in range(len(seg))]
        lg = legs(seg, An, pv=3, minAtr=2.0)
        print(f"\n  {tag}: {len(lg)} legs")
        table("Q1 hour, cross-fitted normalised ATR", seg, lg, len(seg),
              hour_buckets(h2))
        table("Q2 killzones, cross-fitted normalised ATR", seg, lg, len(seg),
              kz_buckets(h2))
    print(f"\n  CELLS SCORED IN TOTAL (parts 1+2+3): {CELLS}")




# ==========================================================================
#  PART 4 — does the clock add anything TO the catcher, or the catcher to
#  the clock? Neither shift-control can answer this, because each one is
#  scored against a twin of ITSELF. Here time of day is held FIXED and the
#  only thing that varies is whether the catcher fired - so the control is
#  the other bars of the same hour, which is the strictest control there is
#  for a clock claim.
#
#  Read it as: inside this bucket, of every bar, how often did a leg start
#  within 3 bars? And of the bars where the catcher fired, how often then?
# ==========================================================================
def within(label, s, V=None, need=2, slack=3):
    hh, _ = clock(s)
    A = watr(s, 14)
    lg = legs(s, A, pv=3, minAtr=2.0)
    n = len(s)
    sig = catcher(s, A, V, need=need)
    st = {}
    for (b0, b1, d, sz) in lg:
        st.setdefault(b0, []).append(d)

    def rate(idx, want_dir):
        hit = 0
        for i in idx:
            for k in range(i, min(i + slack + 1, n)):
                ds = st.get(k)
                if ds and (not want_dir or sig[i] in ds):
                    hit += 1
                    break
        return hit / max(len(idx), 1), hit

    buckets = [("ALL hours", list(range(n)))]
    for k, v in KZ.items():
        buckets.append((k, [i for i in range(n) if hh[i] in v]))
    allkz = set()
    for v in KZ.values():
        allkz |= set(v)
    buckets.append(("outside killzones",
                    [i for i in range(n) if hh[i] not in allkz]))

    print(f"\n  ---- {label}: catcher value INSIDE each bucket "
          f"({len(lg)} legs, slack={slack}) ----")
    print(f"  {'bucket':<22}{'bars':>7}{'anyleg%':>9}{'fires':>7}"
          f"{'anyleg%':>9}{'dirmatch%':>11}{'legs':>6}{'catcher lift':>14}")
    print("  " + "-" * 78)
    for name, idx in buckets:
        base, _ = rate(idx, False)
        fi = [i for i in idx if sig[i] != 0]
        if len(fi) < 30:
            print(f"  {name:<22}{len(idx):>7}{100*base:>8.1f}%{len(fi):>7}"
                  f"   too few")
            continue
        ca, _ = rate(fi, False)
        cd, hd = rate(fi, True)
        lift = ca / base if base else 0.0
        flag = "" if hd >= 40 else "  (<40 legs)"
        print(f"  {name:<22}{len(idx):>7}{100*base:>8.1f}%{len(fi):>7}"
              f"{100*ca:>8.1f}%{100*cd:>10.1f}%{hd:>6}{lift:>14.2f}{flag}")


def main4():
    print("\n" + "=" * 84)
    print("  PART 4 — clock vs catcher, each holding the other fixed")
    print("=" * 84)
    within("1h 2024-2026", load_plain("GOLD_1h.json"))
    within("15m 2026", load_plain("GOLD_15m.json"))
    m1, V = load_m1_2018()
    within("M1 2018 (secondary)", m1, V=V)


if __name__ == "__main__":
    main()
    main2()
    main3()
    main4()

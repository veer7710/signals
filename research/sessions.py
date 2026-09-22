"""
sessions.py -- the session clock every ICT/SMC model needs and this repo did
not have. Without it not one killzone model is testable, so every "ICT test"
run before this file existed was testing the model with its time filter removed
-- which is not the model.

Timestamps in data/*.json are UTC. Gold's daily break shows up as a hole at
21:00-22:00 UTC (594 bars an hour everywhere else, 169 at hour 21), which is
17:00 New York -- the CME roll. That is the anchor: these are NY-session days.

NY time is UTC-5 (EST) / UTC-4 (EDT), and ICT's windows are stated in NEW YORK
local time, so DST has to be handled or every killzone is an hour wrong for
eight months of the year. US rule since 2007: DST from the 2nd Sunday in March
to the 1st Sunday in November.

NO LOOK-AHEAD ANYWHERE. Every session range, prior-day level and prior-week
level is complete and closed before the bar that is allowed to use it.
"""
import numpy as np
import datetime as _dt

# ------------------------------------------------------------------ clock

def _nth_sunday(year, month, n):
    d = _dt.date(year, month, 1)
    d += _dt.timedelta(days=(6 - d.weekday()) % 7)      # first Sunday
    return d + _dt.timedelta(weeks=n - 1)

def _us_dst(u):
    """True if this UTC datetime is inside US Eastern daylight time.
    Transitions happen at 02:00 LOCAL, which is 07:00 UTC for the spring
    forward (EST, UTC-5) and 06:00 UTC for the fall back (EDT, UTC-4)."""
    y = u.year
    start = _dt.datetime.combine(_nth_sunday(y, 3, 2), _dt.time(7, 0))
    end   = _dt.datetime.combine(_nth_sunday(y, 11, 1), _dt.time(6, 0))
    return start <= u < end

def ny(ts):
    """UTC epoch seconds -> naive New York datetime."""
    u = _dt.datetime.utcfromtimestamp(int(ts))
    return u - _dt.timedelta(hours=4 if _us_dst(u) else 5)

def ny_fields(d):
    """Vectorised NY calendar fields for a whole dataset, computed once.
    Returns hour, minute, weekday (Mon=0), and a DAY INDEX that rolls at
    17:00 NY -- the CME day, not the calendar day. Using the calendar day
    would split the Asian session in half and make 'previous day high'
    mean something different in Asia than in New York."""
    n = d["n"]
    hh = np.empty(n, np.int16); mm = np.empty(n, np.int16)
    wd = np.empty(n, np.int16); day = np.empty(n, np.int32)
    for i in range(n):
        t = ny(d["t"][i])
        hh[i] = t.hour; mm[i] = t.minute; wd[i] = t.weekday()
        roll = t + _dt.timedelta(hours=7)      # 17:00 -> next day 00:00
        day[i] = roll.toordinal()
    return dict(h=hh, m=mm, wd=wd, day=day)

# -------------------------------------------------------------- killzones
# All in NEW YORK local time, as ICT states them. Half-open [start, end).
KZ = {
    # the three Silver Bullet hours. These are the only windows ICT gives as
    # a single hard hour, which is why they are the only ones testable with
    # no interpretation at all.
    "sb_london":   (3, 0, 4, 0),
    "sb_am":      (10, 0, 11, 0),
    "sb_pm":      (14, 0, 15, 0),
    # the broader killzones
    "london_kz":   (2, 0,  5, 0),
    "ny_am_kz":    (7, 0, 10, 0),
    "ny_pm_kz":   (13, 30, 16, 0),
    "asia_kz":    (20, 0, 24, 0),
    # the Asian RANGE as ICT most often draws it for the London raid
    "asia_range": (19, 0,  0, 0),
}

def in_window(f, name):
    h0, m0, h1, m1 = KZ[name]
    t = f["h"] * 60 + f["m"]
    a, b = h0 * 60 + m0, h1 * 60 + m1
    return (t >= a) & (t < b) if b > a else ((t >= a) | (t < b))

# ------------------------------------------------- prior sessions & levels

def _range_by_day(d, f, mask):
    """High/low of `mask` bars within each CME day. Returns dicts keyed by
    day index, plus the index of the LAST bar of that day's window -- which
    is when the level becomes usable, not a second earlier."""
    hi, lo, end = {}, {}, {}
    for i in np.nonzero(mask)[0]:
        k = int(f["day"][i])
        if k not in hi or d["h"][i] > hi[k]: hi[k] = d["h"][i]
        if k not in lo or d["l"][i] < lo[k]: lo[k] = d["l"][i]
        end[k] = i
    return hi, lo, end

def session_levels(d, f, name):
    """Per-bar arrays of THIS CME day's session high/low, NaN until that
    session has closed. A bar inside the session sees NaN, because the range
    is not known yet -- that is the look-ahead this function exists to stop."""
    hi, lo, end = _range_by_day(d, f, in_window(f, name))
    H = np.full(d["n"], np.nan); L = np.full(d["n"], np.nan)
    for k, e in end.items():
        j = e + 1
        if j >= d["n"]: continue
        same = np.nonzero(f["day"][j:] == k)[0]
        if len(same) == 0: continue
        sl = slice(j, j + same[-1] + 1)
        H[sl] = hi[k]; L[sl] = lo[k]
    return H, L

def prior_day_levels(d, f):
    """Previous CME day's high/low, available from the first bar of the new
    day. Built from a running scan, so bar i can only ever see days < its own."""
    n = d["n"]
    PDH = np.full(n, np.nan); PDL = np.full(n, np.nan)
    cur = f["day"][0]; hi = -np.inf; lo = np.inf
    lastH = np.nan; lastL = np.nan
    for i in range(n):
        if f["day"][i] != cur:
            lastH, lastL = hi, lo
            cur = f["day"][i]; hi = -np.inf; lo = np.inf
        PDH[i] = lastH; PDL[i] = lastL
        hi = max(hi, d["h"][i]); lo = min(lo, d["l"][i])
    return PDH, PDL

def prior_week_levels(d, f):
    n = d["n"]
    PWH = np.full(n, np.nan); PWL = np.full(n, np.nan)
    wk = np.array([_dt.date.fromordinal(int(x)).isocalendar()[:2] for x in f["day"]])
    cur = tuple(wk[0]); hi = -np.inf; lo = np.inf; lastH = np.nan; lastL = np.nan
    for i in range(n):
        if tuple(wk[i]) != cur:
            lastH, lastL = hi, lo
            cur = tuple(wk[i]); hi = -np.inf; lo = np.inf
        PWH[i] = lastH; PWL[i] = lastL
        hi = max(hi, d["h"][i]); lo = min(lo, d["l"][i])
    return PWH, PWL

if __name__ == "__main__":
    import core
    for sym, tf in (("GOLD","1h"), ("GOLD","15m")):
        d = core.load(sym, tf); f = ny_fields(d)
        print(f"\n{sym} {tf}: {d['n']} bars, "
              f"{ny(d['t'][0])} -> {ny(d['t'][-1])} New York")
        for k in KZ:
            m = in_window(f, k)
            print(f"   {k:<12} {int(m.sum()):>6} bars  "
                  f"{100*m.mean():>5.1f}% of the set")
        PDH, PDL = prior_day_levels(d, f)
        AH, AL = session_levels(d, f, "asia_range")
        print(f"   prior-day level known on {int((~np.isnan(PDH)).sum())} bars, "
              f"asian range known on {int((~np.isnan(AH)).sum())}")
        # the sanity check that catches a timezone that is an hour out:
        # gold's dead hour must land at 17:00 New York.
        cnt = np.bincount(f["h"], minlength=24)
        print(f"   quietest NY hour = {int(cnt.argmin())}:00 "
              f"({int(cnt.min())} bars vs {int(np.median(cnt))} median) "
              f"-- must be 17 for the clock to be right")

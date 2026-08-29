"""
Liquidity sweep taxonomy and feature extraction.

This module turns "liquidity sweep" from a narrative into measurable events.
It is the core of the Phase 1 specification, written as runnable code so the
definitions cannot stay vague.

THE ONE RULE THIS FILE ENFORCES STRUCTURALLY
--------------------------------------------
Every sweep record separates:

    features  — measurable ONLY from bars closed at or before the decision bar.
                These may be used to decide whether to trade.
    outcome   — what happened afterwards (MFE, MAE, result).
                These may be used ONLY for analysis, never as an input.

They are separate dicts so a feature can never silently become an outcome or
vice versa. That single confusion is the most common way a liquidity backtest
produces a beautiful, false result.

CONFIRMATION LAG IS EXPLICIT
A pivot with N bars either side is not knowable until N bars later. A sweep is
not resolvable into "reversal" or "continuation" until the market has had time
to answer. Both lags are recorded on every event, so nothing is credited to a
bar that could not have known it.
"""
from __future__ import annotations
import os, sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Series, atr, ema


# --------------------------------------------------------------- liquidity
@dataclass
class Level:
    """A liquidity level: a price where resting orders are likely to sit."""
    price: float
    kind: str                 # swing_high | swing_low | equal_high | equal_low
    side: int                 # +1 = sell-side liquidity above, -1 = buy-side below
    formed_bar: int           # bar the extreme actually occurred on
    known_bar: int            # bar it could FIRST have been known (formed + lag)
    touches: int = 1
    swept_bar: int = -1
    strength: float = 0.0


def find_levels(s: Series, pivot_n=3, equal_tol_atr=0.15, max_age=500):
    """
    Detect swing highs/lows and cluster equal highs/lows into liquidity levels.

    `pivot_n` bars either side must be lower (for a high). That means the pivot
    at bar j is only KNOWN at bar j + pivot_n — recorded as known_bar, and every
    consumer must respect it.
    """
    a = atr(s, 14)
    levels: list[Level] = []
    for j in range(pivot_n, len(s) - pivot_n):
        win_h = s.h[j - pivot_n:j + pivot_n + 1]
        win_l = s.l[j - pivot_n:j + pivot_n + 1]
        known = j + pivot_n
        if s.h[j] == max(win_h) and win_h.count(s.h[j]) == 1:
            levels.append(Level(s.h[j], "swing_high", +1, j, known))
        if s.l[j] == min(win_l) and win_l.count(s.l[j]) == 1:
            levels.append(Level(s.l[j], "swing_low", -1, j, known))

    # cluster near-equal levels on the same side: equal highs/lows are stronger
    # liquidity because more stops accumulate at an obvious repeated price
    for i, lv in enumerate(levels):
        tol = equal_tol_atr * (a[lv.formed_bar] or 0)
        if tol <= 0:
            continue
        for other in levels[max(0, i - 30):i]:
            if other.side == lv.side and abs(other.price - lv.price) <= tol:
                lv.touches += 1
                lv.kind = "equal_high" if lv.side > 0 else "equal_low"
    for lv in levels:
        lv.strength = _strength(lv, s, a)
    return levels


def _strength(lv: Level, s: Series, a) -> float:
    """
    Liquidity strength score, 0..1. Deliberately simple and equal-weight:
    every weight is a free parameter, and free parameters are what produced a
    748-parameter EA. Inputs are things that plausibly increase resting orders.
    """
    score = 0.0
    score += min(lv.touches, 4) / 4.0 * 0.4        # repeated tests = more stops
    rnd = abs(lv.price - round(lv.price)) < 0.25   # gold round-dollar proximity
    score += 0.2 if rnd else 0.0
    rnd10 = abs(lv.price - round(lv.price / 10) * 10) < 1.0
    score += 0.2 if rnd10 else 0.0
    av = a[lv.formed_bar] or 0
    if av > 0:                                      # prominence vs local noise
        lookback = s.h[max(0, lv.formed_bar - 20):lv.formed_bar + 1]
        if lookback:
            rng = max(lookback) - min(s.l[max(0, lv.formed_bar - 20):lv.formed_bar + 1])
            score += 0.2 * min(1.0, (rng / av) / 6.0)
    return round(min(score, 1.0), 3)


# ------------------------------------------------------------ sweep events
SWEEP_TYPES = {
    "A": "wick sweep + rejection (closed back inside same bar)",
    "B": "close beyond level + rapid reclaim within window",
    "C": "deep sweep + rejection (depth > deep_atr)",
    "D": "sweep + displacement (expansion candle after reclaim)",
    "E": "sweep + structure shift (micro MSS after reclaim)",
    "F": "sweep + continuation (stayed beyond — reversal FAILED)",
    "G": "no resolution inside the window (expired)",
}


@dataclass
class Sweep:
    level: Level
    sweep_bar: int                 # bar the level was pierced
    decision_bar: int              # bar the classification became knowable
    stype: str                     # A..G
    side: int                      # +1 long setup, -1 short setup (0 if none)
    features: dict = field(default_factory=dict)   # decision-time ONLY
    outcome: dict = field(default_factory=dict)    # after the fact — analysis only


def detect_sweeps(s: Series, levels=None, pivot_n=3, window=6,
                  deep_atr=0.8, disp_atr=1.2, min_strength=0.0):
    """
    Walk forward bar by bar. For each bar, consider levels ALREADY KNOWN, check
    for a pierce, then resolve the outcome over the following `window` bars.

    The classification is stamped at `decision_bar` — the first bar at which the
    class was determinable. Nothing is credited earlier.
    """
    a = atr(s, 14)
    if levels is None:
        levels = find_levels(s, pivot_n=pivot_n)
    by_known: dict[int, list[Level]] = {}
    for lv in levels:
        by_known.setdefault(lv.known_bar, []).append(lv)

    active: list[Level] = []
    sweeps: list[Sweep] = []

    for i in range(20, len(s) - window - 1):
        active.extend(by_known.get(i, []))
        active = [lv for lv in active if lv.swept_bar < 0 and i - lv.formed_bar < 500]
        av = a[i] or 0
        if av <= 0:
            continue

        for lv in list(active):
            if lv.strength < min_strength:
                continue
            pierced = (s.h[i] > lv.price) if lv.side > 0 else (s.l[i] < lv.price)
            if not pierced:
                continue
            lv.swept_bar = i

            # ---- decision-time features, all from bars <= the decision bar
            depth = ((s.h[i] - lv.price) if lv.side > 0 else (lv.price - s.l[i]))
            rng = max(s.h[i] - s.l[i], 1e-9)
            wick = ((s.h[i] - max(s.o[i], s.c[i])) if lv.side > 0
                    else (min(s.o[i], s.c[i]) - s.l[i]))
            closed_back = (s.c[i] < lv.price) if lv.side > 0 else (s.c[i] > lv.price)
            setup_side = -lv.side          # fade the sweep: sweep high -> short

            stype, decision_bar = None, i
            reclaim_bars = -1

            if closed_back:
                # Type A: pierced and closed back inside on the SAME bar.
                # Knowable at bar i's close, so decision_bar = i.
                stype = "C" if depth > deep_atr * av else "A"
            else:
                # Closed beyond. We must WAIT — this is the state the naive
                # implementation collapses, and where most false signals live.
                for k in range(1, window + 1):
                    j = i + k
                    if j >= len(s):
                        break
                    back = (s.c[j] < lv.price) if lv.side > 0 else (s.c[j] > lv.price)
                    if back:
                        reclaim_bars = k
                        decision_bar = j
                        stype = "B"
                        break
                if stype is None:
                    # never reclaimed inside the window
                    far = ((s.c[i + window] - lv.price) if lv.side > 0
                           else (lv.price - s.c[i + window]))
                    stype = "F" if far > deep_atr * av else "G"
                    decision_bar = i + window
                    setup_side = 0 if stype == "G" else lv.side  # F = go WITH it

            # upgrade A/B/C to D or E if displacement or a micro structure
            # shift follows, still measured only up to decision_bar + a small lag
            if stype in ("A", "B", "C") and decision_bar + 2 < len(s):
                d1 = decision_bar + 1
                body = abs(s.c[d1] - s.o[d1])
                if body > disp_atr * av and (s.c[d1] > s.o[d1]) == (setup_side > 0):
                    stype = "D"
                    decision_bar = d1
                else:
                    prior = (max(s.h[max(0, i - 10):i]) if setup_side > 0
                             else min(s.l[max(0, i - 10):i]))
                    shifted = (s.c[d1] > prior) if setup_side > 0 else (s.c[d1] < prior)
                    if shifted:
                        stype = "E"
                        decision_bar = d1

            feats = {
                "depth_atr": round(depth / av, 3),
                "wick_ratio": round(wick / rng, 3),
                "close_loc": round((s.c[i] - s.l[i]) / rng, 3),
                "closed_back": closed_back,
                "reclaim_bars": reclaim_bars,
                "level_strength": lv.strength,
                "level_touches": lv.touches,
                "level_kind": lv.kind,
                "level_age": i - lv.formed_bar,
                "atr": round(av, 4),
                "bar_range_atr": round(rng / av, 3),
                "lag_bars": decision_bar - i,
            }
            sweeps.append(Sweep(lv, i, decision_bar, stype, setup_side, feats))
    return sweeps


def add_outcomes(s: Series, sweeps: list, horizon=40, stop_atr=1.0):
    """
    Measure what happened AFTER each decision bar. Analysis only.

    Entry is the decision bar's CLOSE — the earliest price actually obtainable
    once the classification was known.
    """
    a = atr(s, 14)
    for sw in sweeps:
        if sw.side == 0:
            continue
        e = sw.decision_bar
        if e + 2 >= len(s):
            continue
        entry = s.c[e]
        av = a[e] or 0
        if av <= 0:
            continue
        stop = entry - sw.side * stop_atr * av
        risk = abs(entry - stop)
        mfe = mae = 0.0
        hit_stop_at = -1
        # FIRST-TOUCH resolution. MFE and MAE measured independently are
        # misleading: a trade can be +1R at bar 30 having already stopped out at
        # bar 3. What matters is which came FIRST, so we resolve target-before-
        # stop bar by bar and treat a bar containing both as a LOSS (tick order
        # inside a bar is unknowable, and the pessimistic read is the honest one).
        first_touch = {"1R": None, "2R": None, "3R": None}
        for j in range(e + 1, min(e + 1 + horizon, len(s))):
            fav = (s.h[j] - entry) if sw.side > 0 else (entry - s.l[j])
            adv = (entry - s.l[j]) if sw.side > 0 else (s.h[j] - entry)
            mfe = max(mfe, fav)
            mae = max(mae, adv)
            stopped_here = adv >= risk
            for mult, key in ((1, "1R"), (2, "2R"), (3, "3R")):
                if first_touch[key] is None and fav >= mult * risk:
                    # ties lose: if the stop is also touched on this bar, the
                    # target does not count
                    first_touch[key] = (j - e) if not stopped_here else False
            if stopped_here:
                hit_stop_at = j
                for key in first_touch:
                    if first_touch[key] is None:
                        first_touch[key] = False
                break
        for key in first_touch:
            if first_touch[key] is None:
                first_touch[key] = False
        sw.outcome = {
            "mfe_R": round(mfe / risk, 3) if risk > 0 else 0,
            "mae_R": round(mae / risk, 3) if risk > 0 else 0,
            "hit_stop": hit_stop_at > 0,
            "bars_to_stop": (hit_stop_at - e) if hit_stop_at > 0 else -1,
            # these now mean "reached this target BEFORE being stopped out"
            "won_1R": first_touch["1R"] is not False,
            "won_2R": first_touch["2R"] is not False,
            "won_3R": first_touch["3R"] is not False,
            "bars_to_1R": first_touch["1R"] if first_touch["1R"] is not False else -1,
        }
    return sweeps

"""
Exit laboratory — answering "why does it never close at the peak?"

Veer's complaint, precisely: entries are often fine, but trades give back
profit. A move goes 50 points and the trade closes at a loss; five positions
sit at GBP10 profit and close near zero.

This module holds the ENTRIES constant and varies ONLY the exit rule, so any
difference in result is caused by the exit and nothing else. It also measures
MFE (maximum favourable excursion — the best the trade ever was) so we can
compute what fraction of the available profit each exit rule actually
captured.

The ORACLE exit is included deliberately: it closes at the exact high of the
trade, which requires knowing the future. It is not tradeable. It is the
ceiling, and the gap between it and the best real exit is the unavoidable
price of not knowing the future.
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Series, Costs, build_context, stats


def simulate(s: Series, signal_fn, exit_policy, costs: Costs,
             warmup=300, max_bars=200, allow_overlap=False):
    """Run one exit policy over the entries produced by signal_fn.

    exit_policy(state, bar) -> None to hold, or (exit_price, reason).
    `state` carries side, entry, stop, target, risk, bars_held, mfe, mae.
    """
    ctx = build_context(s)
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot
    trades = []
    pos = None
    # allow_overlap=True lets every signal become a trade regardless of what is
    # already open. That is essential for comparing exits fairly: otherwise a
    # fast exit frees the slot sooner and the policies end up trading a
    # DIFFERENT set of entries, so the comparison measures entry selection as
    # much as exit quality.
    open_list = []

    if allow_overlap:
        for i in range(warmup, len(s) - 1):
            still = []
            for p in open_list:
                side = p["side"]
                fav = (s.h[i] - p["entry"]) if side == 1 else (p["entry"] - s.l[i])
                adv = (p["entry"] - s.l[i]) if side == 1 else (s.h[i] - p["entry"])
                p["mfe"] = max(p["mfe"], fav)
                p["mae"] = max(p["mae"], adv)
                p["bars"] = i - p["i_in"]
                bar = {"i": i, "o": s.o[i], "h": s.h[i], "l": s.l[i],
                       "c": s.c[i], "atr": ctx["atr"][i]}
                res = exit_policy(p, bar)
                if res is None and p["bars"] >= max_bars:
                    res = (s.c[i], "time_cap")
                if res is None:
                    still.append(p); continue
                px, reason = res
                fill = px - side * (half + costs.slippage)
                r = ((fill - p["entry"]) * side - comm_px) / p["risk"]
                trades.append({"r": r, "reason": reason, "side": side,
                               "mfe_r": p["mfe"] / p["risk"],
                               "mae_r": p["mae"] / p["risk"],
                               "bars": p["bars"], "i_in": p["i_in"]})
            open_list = still
            sig = signal_fn(ctx, i)
            if not sig:
                continue
            side = sig["side"]
            entry = s.o[i + 1] + side * (half + costs.slippage)
            stop = sig["stop"]
            if (side == 1 and stop >= entry) or (side == -1 and stop <= entry):
                continue
            open_list.append({"side": side, "entry": entry, "stop": stop,
                              "init_stop": stop, "target": sig["target"],
                              "risk": abs(entry - stop), "i_in": i + 1,
                              "mfe": 0.0, "mae": 0.0, "bars": 0, "armed": False})
        return trades

    for i in range(warmup, len(s) - 1):
        if pos is not None:
            side = pos["side"]
            # update excursions using this bar's extremes
            fav = (s.h[i] - pos["entry"]) if side == 1 else (pos["entry"] - s.l[i])
            adv = (pos["entry"] - s.l[i]) if side == 1 else (s.h[i] - pos["entry"])
            pos["mfe"] = max(pos["mfe"], fav)
            pos["mae"] = max(pos["mae"], adv)
            pos["bars"] = i - pos["i_in"]
            bar = {"i": i, "o": s.o[i], "h": s.h[i], "l": s.l[i], "c": s.c[i],
                   "atr": ctx["atr"][i]}

            res = exit_policy(pos, bar)
            if res is None and pos["bars"] >= max_bars:
                res = (s.c[i], "time_cap")
            if res is not None:
                px, reason = res
                fill = px - side * (half + costs.slippage)
                r = ((fill - pos["entry"]) * side - comm_px) / pos["risk"]
                trades.append({
                    "r": r, "reason": reason, "side": side,
                    "mfe_r": pos["mfe"] / pos["risk"],
                    "mae_r": pos["mae"] / pos["risk"],
                    "bars": pos["bars"], "i_in": pos["i_in"],
                })
                pos = None
            else:
                continue

        if pos is not None:
            continue
        sig = signal_fn(ctx, i)
        if not sig:
            continue
        side = sig["side"]
        entry = s.o[i + 1] + side * (half + costs.slippage)
        stop = sig["stop"]
        if (side == 1 and stop >= entry) or (side == -1 and stop <= entry):
            continue
        pos = {"side": side, "entry": entry, "stop": stop,
               "init_stop": stop, "target": sig["target"],
               "risk": abs(entry - stop), "i_in": i + 1,
               "mfe": 0.0, "mae": 0.0, "bars": 0, "armed": False}
    return trades


# ------------------------------------------------------------ exit policies
def stop_and_target(rr):
    """Fixed target at rr x risk. Stop never moves. The classic."""
    def f(p, b):
        side = p["side"]
        tgt = p["entry"] + side * rr * p["risk"]
        hit_stop = b["l"] <= p["stop"] if side == 1 else b["h"] >= p["stop"]
        hit_tgt = b["h"] >= tgt if side == 1 else b["l"] <= tgt
        if hit_stop:                      # ties lose
            return (p["stop"], "stop")
        if hit_tgt:
            return (tgt, f"target_{rr}R")
        return None
    return f


def atr_trail(mult, arm_at_r=0.0):
    """Trail the stop `mult` x ATR behind the close. Optionally only start
    trailing once the trade is arm_at_r in profit."""
    def f(p, b):
        side = p["side"]
        a = b["atr"] or 0.0
        prof_r = ((b["c"] - p["entry"]) * side) / p["risk"]
        if a > 0 and prof_r >= arm_at_r:
            new = b["c"] - side * mult * a
            p["stop"] = max(p["stop"], new) if side == 1 else min(p["stop"], new)
        hit = b["l"] <= p["stop"] if side == 1 else b["h"] >= p["stop"]
        if hit:
            return (p["stop"], "trail")
        return None
    return f


def breakeven_then_trail(be_at_r, mult):
    """Move to break-even at be_at_r, then trail. This is the 'protect the
    profit' instinct — and the thing most likely to cause death by a thousand
    scratches if be_at_r is too small."""
    def f(p, b):
        side = p["side"]
        a = b["atr"] or 0.0
        prof_r = ((b["c"] - p["entry"]) * side) / p["risk"]
        if not p["armed"] and prof_r >= be_at_r:
            p["armed"] = True
            p["stop"] = p["entry"]
        if p["armed"] and a > 0:
            new = b["c"] - side * mult * a
            p["stop"] = max(p["stop"], new) if side == 1 else min(p["stop"], new)
        hit = b["l"] <= p["stop"] if side == 1 else b["h"] >= p["stop"]
        if hit:
            return (p["stop"], "be_trail" if p["armed"] else "stop")
        return None
    return f


def time_exit(bars, use_stop=True):
    """Hold a fixed number of bars, then leave at the close."""
    def f(p, b):
        side = p["side"]
        if use_stop:
            hit = b["l"] <= p["stop"] if side == 1 else b["h"] >= p["stop"]
            if hit:
                return (p["stop"], "stop")
        if p["bars"] >= bars:
            return (b["c"], f"time_{bars}")
        return None
    return f


def oracle_peak(max_hold=200):
    """NOT TRADEABLE. Exits at the single best price the trade ever reached.

    Requires knowing the future, so it cannot be run forward. It exists only
    to measure the ceiling: the most any exit rule could possibly have
    captured. Implemented by holding to the cap and then crediting the MFE.
    """
    def f(p, b):
        side = p["side"]
        hit = b["l"] <= p["stop"] if side == 1 else b["h"] >= p["stop"]
        if hit:
            # even the oracle banks the best price seen before the stop
            best = p["entry"] + side * p["mfe"]
            return (best, "oracle")
        if p["bars"] >= max_hold:
            best = p["entry"] + side * p["mfe"]
            return (best, "oracle")
        return None
    return f


POLICIES = {
    "fixed 1R":              stop_and_target(1.0),
    "fixed 2R":              stop_and_target(2.0),
    "fixed 3R":              stop_and_target(3.0),
    "trail 2xATR":           atr_trail(2.0),
    "trail 3xATR":           atr_trail(3.0),
    "trail 3xATR arm@1R":    atr_trail(3.0, arm_at_r=1.0),
    "BE@0.5R + trail 3ATR":  breakeven_then_trail(0.5, 3.0),
    "BE@1R + trail 3ATR":    breakeven_then_trail(1.0, 3.0),
    "time 20 bars":          time_exit(20),
    "time 50 bars":          time_exit(50),
    "ORACLE (not tradeable)": oracle_peak(),
}


# ---------------------------------------------------------------------------
# PEAK GIVE-BACK  (E-051)
#
# Veer's live complaint, stated mechanically: a trade reaches GBP10+ floating
# and closes for far less; a basket reaches GBP12 and closes at breakeven.
# Every exit rule above is anchored to PRICE (a stop level, an ATR distance,
# a fixed multiple of risk). None of them is anchored to HOW GOOD THE TRADE
# ALREADY WAS. This one is: it remembers the best the trade ever got, and
# leaves when a fixed fraction of that best has been handed back.
#
# NO LOOK-AHEAD. The trigger price for bar i is computed from the peak as it
# stood at the END of bar i-1. Using this bar's own high to place a trigger
# inside this bar would assume the high printed before the retrace, which is
# unknowable from OHLC. That assumption is worth roughly a third of the
# measured edge, so it is not made.
#
# The fill is still optimistic in the same way every stop in this lab is
# (L-012, intrabar discretisation): a real fill is at or past the trigger,
# never better. Read every number below as a ceiling.
def peak_giveback(arm_r, gb, use_stop=True):
    """Exit when the trade hands back `gb` of its best-ever profit, once that
    best has reached arm_r. Below arm_r the original stop is the only exit."""
    def f(p, b):
        side = p["side"]
        if use_stop:
            hit = b["l"] <= p["stop"] if side == 1 else b["h"] >= p["stop"]
            if hit:
                return (p["stop"], "stop")
        prev_peak = p.get("gb_peak", 0.0)          # peak as of the LAST bar
        if prev_peak >= arm_r * p["risk"]:
            trig = p["entry"] + side * prev_peak * (1.0 - gb)
            through = b["l"] <= trig if side == 1 else b["h"] >= trig
            if through:
                return (trig, f"gaveback_{int(gb*100)}pct")
        fav = (b["h"] - p["entry"]) if side == 1 else (p["entry"] - b["l"])
        p["gb_peak"] = max(prev_peak, fav)          # update AFTER the test
        return None
    return f


def peak_giveback_ratchet(arm_r, tiers, use_stop=True):
    """Same idea, but the allowed give-back TIGHTENS as the trade gets better.
    `tiers` is [(peak_in_R, allowed_giveback), ...] in ascending order — the
    last tier whose peak has been exceeded wins.

    The reason for tiering: handing back 35% of a 1R peak costs 0.35R and is
    the price of letting a trade breathe. Handing back 35% of a 6R peak costs
    2.1R, which is the failure Veer is describing. A flat percentage treats
    those as the same event; this does not."""
    def f(p, b):
        side = p["side"]
        if use_stop:
            hit = b["l"] <= p["stop"] if side == 1 else b["h"] >= p["stop"]
            if hit:
                return (p["stop"], "stop")
        prev_peak = p.get("gb_peak", 0.0)
        peak_r = prev_peak / p["risk"] if p["risk"] > 0 else 0.0
        if peak_r >= arm_r:
            gb = tiers[0][1]
            for lvl, allowed in tiers:
                if peak_r >= lvl:
                    gb = allowed
            trig = p["entry"] + side * prev_peak * (1.0 - gb)
            through = b["l"] <= trig if side == 1 else b["h"] >= trig
            if through:
                return (trig, "ratchet")
        fav = (b["h"] - p["entry"]) if side == 1 else (p["entry"] - b["l"])
        p["gb_peak"] = max(prev_peak, fav)
        return None
    return f


def trail_plus_giveback(mult, arm_r, gb):
    """The wide ATR trail (measured best so far) AND the give-back rule
    together — whichever fires first. This is the honest candidate: it does
    not remove the rule that already won, it adds a ceiling on how much of a
    good trade can evaporate."""
    tr = atr_trail(mult)
    pg = peak_giveback(arm_r, gb, use_stop=False)
    def f(p, b):
        r1 = pg(p, b)          # tested first: it uses last bar's peak
        r2 = tr(p, b)          # moves and tests the trailing stop
        if r2 is not None:
            return r2
        return r1
    return f


POLICIES.update({
    "giveback 30% arm@0.5R":  peak_giveback(0.5, 0.30),
    "giveback 30% arm@1R":    peak_giveback(1.0, 0.30),
    "giveback 40% arm@1R":    peak_giveback(1.0, 0.40),
    "giveback 50% arm@1R":    peak_giveback(1.0, 0.50),
    "giveback 25% arm@1.5R":  peak_giveback(1.5, 0.25),
    "ratchet 45/30/22":       peak_giveback_ratchet(
                                  0.8, [(0.8, 0.45), (2.0, 0.30), (4.0, 0.22)]),
    "ratchet 50/35/25":       peak_giveback_ratchet(
                                  0.5, [(0.5, 0.50), (2.0, 0.35), (4.0, 0.25)]),
    "trail3ATR + gb40 arm@1R": trail_plus_giveback(3.0, 1.0, 0.40),
    "trail3ATR + gb30 arm@1R": trail_plus_giveback(3.0, 1.0, 0.30),
})

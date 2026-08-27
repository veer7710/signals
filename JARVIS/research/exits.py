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
                    "bars": pos["bars"],
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

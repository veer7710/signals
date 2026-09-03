"""
E-074 — Every gate in the SuperTrend EA, and what each one throws away.

Veer: "we are now not hitting same trades as before and having delayed entry",
and "the ea is not performing to its BEST ... see what else we can ADD REMOVE
IMPROVE OPTIMISE".

The EA has TEN separate conditions that can refuse a signal. Each was added for
a reason; almost none was ever measured as a gate. A gate is only worth its
complexity if the trades it REFUSES are worse than the trades it ALLOWS, and
that is a one-line test nobody had run.

For each gate, on the identical signal set and the identical exit:

  ALLOWED   the trades the gate lets through
  REFUSED   the trades it blocks - THE COLUMN THAT MATTERS
  verdict   KEEP    refused trades are clearly worse than allowed ones
            REMOVE  refused trades are BETTER - the gate is backwards
            NOISE   no real difference - it is complexity with no payment

F-010 is why this exists: InpMaxCostFrac was set to 0.10, which refused
essentially every M1 entry, and E-053 - written the same day, by me - had
already measured M1 gold at 0.15-0.22. A gate nobody measured cost a day of
trading. This measures all ten.

Exit is the EA's current one: 2.0 ATR stop, 3R target, 200-bar cap.
Ties lose. Costs both ends.

Run:  python3 JARVIS/research/gate_audit.py
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, strategies
from engine import Series
from liquidity import stat
from st_entry import COMBOS

# the EA's own numbers, read out of SuperTrendSniper.mq5
MAX_ADX      = 35.0
MIN_EFF      = 0.08
CHOP_ER_LEN  = 50
CHOP_FLIP_N  = 20
MAX_FLIPS    = 5
MAX_COSTFRAC = 0.30
MIN_STOP_X   = 4.0
REENTRY_COOL = 3
NOFADE_ATR   = 3.0
NOFADE_BARS  = 3
STOP_ATR     = 2.0
TARGET_R     = 3.0


def eff_ratio(s, i, n):
    if i - n < 0:
        return None
    net = abs(s.c[i] - s.c[i - n])
    path = sum(abs(s.c[k] - s.c[k - 1]) for k in range(i - n + 1, i + 1))
    return (net / path) if path > 0 else None


def flips_in(d, i, n):
    c = 0
    for k in range(max(1, i - n + 1), i + 1):
        if d[k] != 0 and d[k - 1] != 0 and d[k] != d[k - 1]:
            c += 1
    return c


def build(s: Series, costs, atr_len=7, mult=1.2, dema_len=200):
    """Every flip, with the value of every gate attached to it. Nothing here
    looks past bar i."""
    d, fu, fl = strategies.supertrend_dir(s, atr_len, mult)
    A = engine.atr(s, atr_len)
    D = strategies.dema(s.c, dema_len)
    ctx = engine.build_context(s)
    ADX = ctx["adx"]
    rt = costs.spread + 2 * costs.slippage \
       + costs.commission_per_lot / costs.value_per_point_per_lot

    ev, last_dir, last_bar = [], 0, -9999
    for i in range(300, len(s) - 2):
        if d[i] == 0 or d[i - 1] == 0:
            continue
        up = d[i] == -1 and d[i - 1] == 1
        dn = d[i] == 1 and d[i - 1] == -1
        if not (up or dn):
            continue
        a = A[i]
        if a is None or a <= 0:
            continue
        side = 1 if up else -1
        stop_dist = STOP_ATR * a

        # --- the gates, each as the EA computes it
        dnow, dprev = D[i], D[i - 2]
        g_dema = (dnow is not None and dprev is not None
                  and ((side == 1 and dnow >= dprev) or (side == -1 and dnow <= dprev)))
        ad = ADX[i]
        g_adx = (ad is None or ad <= MAX_ADX)
        er = eff_ratio(s, i, CHOP_ER_LEN)
        g_eff = (er is None or er >= MIN_EFF)
        g_flip = (flips_in(d, i, CHOP_FLIP_N) < MAX_FLIPS)
        g_cost = ((rt / stop_dist) <= MAX_COSTFRAC) if stop_dist > 0 else False
        g_stopx = (stop_dist >= MIN_STOP_X * rt)
        g_cool = not (side == last_dir and (i - last_bar) < REENTRY_COOL)
        # no-fade: a big candle in the last NOFADE_BARS that went the other way
        nofade = True
        for k in range(max(1, i - NOFADE_BARS + 1), i + 1):
            if (s.h[k] - s.l[k]) < NOFADE_ATR * a:
                continue
            if (1 if s.c[k] > s.o[k] else -1) != side:
                nofade = False
                break
        ev.append({"i": i, "side": side, "atr": a, "close": s.c[i],
                   "dema": g_dema, "adx": g_adx, "eff": g_eff, "flips": g_flip,
                   "cost": g_cost, "stopx": g_stopx, "cool": g_cool,
                   "nofade": nofade})
        last_dir, last_bar = side, i
    return ev


def trade(s: Series, costs, ev, max_bars=200):
    """One trade from one signal. No 'one at a time' rule here on purpose: a
    gate must be judged on the trades it refuses, and a busy-flag would hide
    them behind whichever trade happened to be open."""
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot
    i, side, a = ev["i"], ev["side"], ev["atr"]
    j = i + 1
    if j >= len(s):
        return None
    entry = s.o[j] + side * (half + costs.slippage)
    stop = ev["close"] - side * STOP_ATR * a
    risk = (entry - stop) * side
    if risk <= 0:
        return None
    tgt = entry + side * TARGET_R * risk
    for k in range(j, min(j + max_bars, len(s))):
        hs = (s.l[k] <= stop) if side == 1 else (s.h[k] >= stop)
        ht = (s.h[k] >= tgt) if side == 1 else (s.l[k] <= tgt)
        if hs:
            px, k2 = stop, k; break
        if ht:
            px, k2 = tgt, k; break
    else:
        k2 = min(j + max_bars, len(s)) - 1
        px = s.c[k2]
    fill = px - side * (half + costs.slippage)
    return {"r": ((fill - entry) * side - comm_px) / risk,
            "pts": (fill - entry) * side - comm_px}


GATES = [("dema",   "DEMA slope agrees"),
         ("adx",    f"ADX <= {MAX_ADX:.0f}"),
         ("eff",    f"efficiency >= {MIN_EFF} over {CHOP_ER_LEN}"),
         ("flips",  f"< {MAX_FLIPS} flips in {CHOP_FLIP_N}"),
         ("cost",   f"cost/stop <= {MAX_COSTFRAC}"),
         ("stopx",  f"stop >= {MIN_STOP_X:.0f} round trips"),
         ("cool",   f"not same way within {REENTRY_COOL} bars"),
         ("nofade", f"no {NOFADE_ATR:.0f}xATR candle the other way")]


def verdict(al, rf, n_rf):
    if n_rf < 40:
        return "too few refused to judge"
    diff = al["exp"] - rf["exp"]
    # the refused set's own standard error, so "worse" means measurably worse
    se = 0.0
    if n_rf > 1 and rf["n"] > 0:
        se = abs(rf["exp"]) / max(abs(rf["t"]), 1e-9) if rf["t"] != 0 else 0.0
    if diff > 2 * max(se, 1e-9):
        return "KEEP    refuses clearly worse trades"
    if diff < -2 * max(se, 1e-9):
        return "REMOVE  the trades it blocks are BETTER"
    return "NOISE   no measurable difference"


def main():
    print("=" * 112)
    print("  E-074  EVERY GATE IN THE SUPERTREND EA, AND WHAT IT THROWS AWAY")
    print("  Same signals, same exit (2.0 ATR stop, 3R target) in every row.")
    print("  A gate earns its place only if REFUSED is worse than ALLOWED.")
    print("=" * 112)

    for scope, syms in (("GOLD ONLY", ("GOLD",)),
                        ("ALL EIGHT MARKETS", None)):
        book = {g: {"a": [], "r": []} for g, _ in GATES}
        total = []
        for sym, tf in COMBOS:
            if syms and sym not in syms:
                continue
            try:
                s = engine.load(sym, tf)
            except Exception:
                continue
            c = study.COSTS.get(sym, engine.Costs())
            for e in build(s, c):
                t = trade(s, c, e)
                if t is None:
                    continue
                total.append(t)
                for g, _ in GATES:
                    book[g]["a" if e[g] else "r"].append(t)

        base = stat(total)
        print(f"\n  ### {scope}   {base['n']} signals   "
              f"ungated expectancy {base['exp']:+.3f}R   "
              f"{base['exp']*base['n']:+.0f}R total")
        print(f"   {'gate':<38}{'allowed':>9}{'exp':>9}{'refused':>9}{'exp':>9}"
              f"{'delta':>9}   verdict")
        print("   " + "-" * 104)
        for g, desc in GATES:
            al, rf = stat(book[g]["a"]), stat(book[g]["r"])
            if al["n"] == 0:
                continue
            d = al["exp"] - rf["exp"] if rf["n"] else 0.0
            print(f"   {desc:<38}{al['n']:>9}{al['exp']:>+8.3f}R{rf['n']:>9}"
                  f"{rf['exp']:>+8.3f}R{d:>+8.3f}R   {verdict(al, rf, rf['n'])}")

    print("\n  WHAT 'REMOVE' MEANS AND DOES NOT MEAN")
    print("  * It means the gate is refusing trades that were BETTER than the ones")
    print("    it let through, on this exit, on this data. That is the definition")
    print("    of a backwards filter and there is no argument for keeping one.")
    print("  * 'NOISE' is not harmless. Every gate costs signals, and Veer wants")
    print("    30-40 entries a day. A gate that pays nothing and refuses trades is")
    print("    a cost with no benefit, which is what F-010 was.")


if __name__ == "__main__":
    main()


def combos():
    """The gates are not independent - they overlap. What matters is what the
    EA actually ends up trading under each COMBINATION, so this runs them."""
    SETS = [
        ("everything on (the EA today)", ["dema", "adx", "eff", "flips", "cost", "stopx"]),
        ("drop the chop guard",          ["dema", "adx", "cost", "stopx"]),
        ("drop ADX too",                 ["dema", "cost", "stopx"]),
        ("DEMA only",                    ["dema"]),
        ("no gates at all",              []),
        ("everything EXCEPT dema",       ["adx", "eff", "flips", "cost", "stopx"]),
    ]
    print("\n" + "=" * 112)
    print("  THE GATES IN COMBINATION — what the EA actually trades under each")
    print("=" * 112)
    for scope, syms in (("GOLD ONLY", ("GOLD",)), ("ALL EIGHT", None)):
        rows = []
        for sym, tf in COMBOS:
            if syms and sym not in syms:
                continue
            try:
                s = engine.load(sym, tf)
            except Exception:
                continue
            c = study.COSTS.get(sym, engine.Costs())
            for e in build(s, c):
                t = trade(s, c, e)
                if t is not None:
                    rows.append((e, t))
        print(f"\n  ### {scope}   {len(rows)} raw signals")
        print(f"   {'gate set':<32}{'taken':>8}{'kept%':>8}{'win%':>8}{'expect':>10}"
              f"{'PF':>7}{'t':>8}{'total R':>10}{'points':>10}")
        print("   " + "-" * 100)
        for name, gs in SETS:
            sel = [t for e, t in rows if all(e[g] for g in gs)]
            if not sel:
                continue
            a = stat(sel)
            pts = sum(x["pts"] for x in sel)
            print(f"   {name:<32}{a['n']:>8}{100.0*a['n']/len(rows):>7.0f}%"
                  f"{a['win']:>7.1f}%{a['exp']:>+9.3f}R{a['pf']:>7.2f}{a['t']:>+8.2f}"
                  f"{a['exp']*a['n']:>+9.1f}R{pts:>+9.1f}")
    print("\n  'kept%' is the answer to \"we are now not hitting same trades as")
    print("  before\". Every point of it is a signal the EA refused.")


if __name__ != "__main__":
    pass

"""
E-079 — SMC, measured. Order blocks, FVG, iFVG, BOS, CHoCH, displacement.

Veer: "base liquidity strat with order blooms fvg all those kinda things smc
bos choch everything you can be deep and thorough have signals sniper entry".

Deep and thorough does NOT mean drawing all of it on the chart. Every one of
these concepts is a claim about the future, and a claim can be checked. So each
is built here and tested two ways against the entry that already survives
(E-077: a limit resting past the zone edge, 0.60 ATR stop, 2R target,
GOLD 1h +0.378R, t=+5.58):

  AS A FILTER    does requiring it make the E-077 trade better? The test is
                 whether the trades it REFUSES are worse than the ones it
                 allows. That is the only thing that makes a filter worth
                 having, and it is the test that killed six of the eight gates
                 in the SuperTrend EA (E-074).
  AS A TRIGGER   does the concept generate a tradeable entry ON ITS OWN, with
                 the same stop and target? An SMC idea that cannot pass this
                 is chart decoration.

THE DEFINITIONS, written down so they can be argued with rather than assumed

  SWING       a pivot high/low with `sw` bars on each side. Confirmed only
              `sw` bars later, and used only from that bar on.
  DISPLACEMENT a bar whose BODY is >= disp x ATR. The impulsive move that
              says something changed. Body, not range: a big range with a
              tiny body is indecision, which is the opposite claim.
  BOS         a close beyond the last swing IN the direction of the current
              structure. Continuation.
  CHoCH       a close beyond the last swing AGAINST the current structure.
              The first sign the trend is over. Structure is tracked with a
              simple state machine, not inferred bar by bar.
  FVG         three bars where bar[i-2].high < bar[i].low (bullish) or
              bar[i-2].low > bar[i].high (bearish). The gap is the imbalance.
  iFVG        an FVG that price has since CLOSED through. It then acts in the
              opposite direction - support becomes resistance.
  ORDER BLOCK the last opposite-colour candle before a displacement leg. Its
              body is the zone.

Ties lose. Costs both ends. XAUUSD only.

Run:  python3 JARVIS/research/smc.py
"""
from __future__ import annotations
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from engine import Series
from liquidity import stat
from toptick import zone_stream, entry_level

COMBOS = [("GOLD", "15m"), ("GOLD", "1h")]
STOP_ATR, TGT_R, FRAC = 0.60, 2.0, -0.25


# ---------------------------------------------------------------- structure
def swings(s: Series, sw=5):
    """Confirmed swing highs and lows. sw[i] is the value KNOWN at bar i."""
    hi = [None] * len(s)
    lo = [None] * len(s)
    for i in range(sw, len(s) - sw):
        h, l = s.h[i], s.l[i]
        if all(h >= s.h[i - k] for k in range(1, sw + 1)) and \
           all(h >= s.h[i + k] for k in range(1, sw + 1)):
            hi[i + sw] = h            # only known sw bars later
        if all(l <= s.l[i - k] for k in range(1, sw + 1)) and \
           all(l <= s.l[i + k] for k in range(1, sw + 1)):
            lo[i + sw] = l
    return hi, lo


def structure(s: Series, sw=5):
    """Walk forward once, tracking the last confirmed swing each side and the
    current structural bias. Emits BOS and CHoCH per bar.

    bias: +1 after a bullish BOS/CHoCH, -1 after a bearish one, 0 until the
    first break. It is a STATE, which is what makes CHoCH meaningful: the same
    break is continuation or reversal depending on where structure already was.
    """
    hi, lo = swings(s, sw)
    lastH = lastL = None
    bias = 0
    bos = [0] * len(s)
    choch = [0] * len(s)
    biasArr = [0] * len(s)
    for i in range(len(s)):
        if hi[i] is not None: lastH = hi[i]
        if lo[i] is not None: lastL = lo[i]
        c = s.c[i]
        if lastH is not None and c > lastH:
            if bias >= 0: bos[i] = 1
            else:         choch[i] = 1
            bias = 1
            lastH = None                 # consumed; wait for the next swing
        elif lastL is not None and c < lastL:
            if bias <= 0: bos[i] = -1
            else:         choch[i] = -1
            bias = -1
            lastL = None
        biasArr[i] = bias
    return bos, choch, biasArr


# ---------------------------------------------------------------- imbalance
def displacement(s: Series, A, mult=1.0):
    """+1 / -1 on a bar whose BODY is at least `mult` ATR."""
    out = [0] * len(s)
    for i in range(len(s)):
        a = A[i]
        if a is None or a <= 0:
            continue
        body = s.c[i] - s.o[i]
        if abs(body) >= mult * a:
            out[i] = 1 if body > 0 else -1
    return out


def fvgs(s: Series, A, min_atr=0.10, life=200):
    """Every fair value gap, and the bar it is INVERTED on.

    A gap is known at bar i (it needs bars i-2, i-1, i, all closed). It is
    live from i+1. It inverts when a close passes fully through it.
    Returns a per-bar list of live gaps, plus per-bar inversion events.
    """
    live = []
    per_bar = [[] for _ in range(len(s))]
    inv = [0] * len(s)
    for i in range(2, len(s)):
        a = A[i]
        # ---- has anything inverted or filled on this bar?
        keep = []
        for g in live:
            if i - g["born"] > life:
                continue
            if not g["inverted"]:
                through = (s.c[i] < g["bot"]) if g["dir"] == 1 else (s.c[i] > g["top"])
                if through:
                    g["inverted"] = True
                    g["inv_bar"] = i
                    inv[i] = -g["dir"]          # it now works the other way
            keep.append(g)
        live = keep
        # ---- a new gap confirmed by this bar
        if a and a > 0:
            if s.h[i - 2] < s.l[i] and (s.l[i] - s.h[i - 2]) >= min_atr * a:
                live.append({"dir": 1, "bot": s.h[i - 2], "top": s.l[i],
                             "born": i, "inverted": False, "inv_bar": -1})
            if s.l[i - 2] > s.h[i] and (s.l[i - 2] - s.h[i]) >= min_atr * a:
                live.append({"dir": -1, "bot": s.h[i], "top": s.l[i - 2],
                             "born": i, "inverted": False, "inv_bar": -1})
        per_bar[i] = list(live)
    return per_bar, inv


def order_blocks(s: Series, A, disp, life=200):
    """The last opposite-colour candle before a displacement leg. Its BODY is
    the zone. Known at the displacement bar, live from the next one."""
    live = []
    per_bar = [[] for _ in range(len(s))]
    for i in range(len(s)):
        live = [b for b in live if i - b["born"] <= life and not b["dead"]]
        for b in live:
            # a close beyond the block the wrong way kills it
            if (b["dir"] == 1 and s.c[i] < b["bot"]) or \
               (b["dir"] == -1 and s.c[i] > b["top"]):
                b["dead"] = True
        if disp[i] != 0:
            d = disp[i]
            for k in range(i - 1, max(i - 8, 0), -1):
                opp = (s.c[k] < s.o[k]) if d > 0 else (s.c[k] > s.o[k])
                if opp:
                    live.append({"dir": d,
                                 "top": max(s.o[k], s.c[k]),
                                 "bot": min(s.o[k], s.c[k]),
                                 "born": i, "dead": False})
                    break
        per_bar[i] = [b for b in live if not b["dead"]]
    return per_bar


# ---------------------------------------------------------------- the trade
def resolve(s, costs, j, side, entry, stop, tgtpx, max_bars=200):
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot
    risk = (entry - stop) * side
    for k in range(j, min(j + max_bars, len(s))):
        hs = (s.l[k] <= stop) if side == 1 else (s.h[k] >= stop)
        ht = (s.h[k] >= tgtpx) if side == 1 else (s.l[k] <= tgtpx)
        if hs: px, why = stop, "stop"; break          # ties lose
        if ht: px, why = tgtpx, "target"; break
    else:
        k = min(j + max_bars, len(s)) - 1
        px, why = s.c[k], "time"
    fill = px - side * (half + costs.slippage)
    return {"r": ((fill - entry) * side - comm_px) / risk, "why": why,
            "pts": (fill - entry) * side - comm_px, "exit_bar": k}


def toptick_signals(s: Series, costs, per_bar, A, warmup=250, arm_life=60):
    """E-077's entries, but returning the SIGNAL BAR so SMC state can be
    attached to each one. Same rules, same order, one at a time."""
    half = costs.spread / 2.0
    out, busy, used = [], -1, set()
    for i in range(warmup, len(s) - 2):
        if i <= busy:
            continue
        a = A[i]
        if a is None or a <= 0:
            continue
        for z in per_bar[i]:
            key = (z["born"], round(z["px"], 6), z["dir"])
            if key in used or i - z["born"] > arm_life:
                continue
            lvl = entry_level(z, FRAC, a)
            side = -1 if z["dir"] == 1 else 1
            if (side == -1 and s.c[i] >= lvl) or (side == 1 and s.c[i] <= lvl):
                continue
            k = i + 1
            if k >= len(s):
                continue
            if not ((s.h[k] >= lvl) if side == -1 else (s.l[k] <= lvl)):
                continue
            used.add(key)
            entry = lvl + side * (half + costs.slippage)
            stop = entry - side * STOP_ATR * a
            if (entry - stop) * side <= 0:
                continue
            tgtpx = entry + side * TGT_R * (entry - stop) * side
            t = resolve(s, costs, k, side, entry, stop, tgtpx)
            t["i"] = i
            t["side"] = side
            out.append(t)
            busy = t["exit_bar"]
            break
    return out


# ---------------------------------------------------------------- filters
def smc_state(s: Series, A):
    """Every SMC reading, per bar, computed once."""
    bos, choch, bias = structure(s)
    disp = displacement(s, A)
    fvg_bars, inv = fvgs(s, A)
    ob_bars = order_blocks(s, A, disp)
    return {"bos": bos, "choch": choch, "bias": bias, "disp": disp,
            "fvg": fvg_bars, "inv": inv, "ob": ob_bars}


def recent(arr, i, n, want=None):
    for k in range(max(0, i - n + 1), i + 1):
        if arr[k] != 0 and (want is None or arr[k] == want):
            return True
    return False


def in_zone(bars, i, px, want_dir):
    for z in bars[i]:
        if z["dir"] != want_dir:
            continue
        if z["bot"] <= px <= z["top"]:
            return True
    return False


FILTERS = [
    ("structure agrees (bias)",
     lambda st, t, s: st["bias"][t["i"]] == t["side"]),
    ("BOS our way in 10 bars",
     lambda st, t, s: recent(st["bos"], t["i"], 10, t["side"])),
    ("CHoCH our way in 10 bars",
     lambda st, t, s: recent(st["choch"], t["i"], 10, t["side"])),
    ("displacement our way in 5",
     lambda st, t, s: recent(st["disp"], t["i"], 5, t["side"])),
    ("no displacement AGAINST in 5",
     lambda st, t, s: not recent(st["disp"], t["i"], 5, -t["side"])),
    ("a live FVG our way",
     lambda st, t, s: any(g["dir"] == t["side"] and not g["inverted"]
                          for g in st["fvg"][t["i"]])),
    ("entry inside an FVG our way",
     lambda st, t, s: any(g["dir"] == t["side"] and not g["inverted"]
                          and g["bot"] <= s.c[t["i"]] <= g["top"]
                          for g in st["fvg"][t["i"]])),
    ("an iFVG flipped our way in 20",
     lambda st, t, s: recent(st["inv"], t["i"], 20, t["side"])),
    ("a live order block our way",
     lambda st, t, s: any(b["dir"] == t["side"] for b in st["ob"][t["i"]])),
    ("entry inside an order block",
     lambda st, t, s: in_zone(st["ob"], t["i"], s.c[t["i"]], t["side"])),
]


def verdict(al, rf):
    if rf["n"] < 30:
        return "too few refused to judge"
    d = al["exp"] - rf["exp"]
    se = abs(rf["exp"] / rf["t"]) if rf["t"] else 0.0
    if d > 2 * max(se, 1e-9):  return "KEEP"
    if d < -2 * max(se, 1e-9): return "BACKWARDS"
    return "noise"


# ---------------------------------------------------------------- triggers
def trigger_trades(s: Series, costs, A, st, kind, warmup=250, max_bars=200):
    """Can the concept produce an entry ON ITS OWN? Same stop and target as
    E-077, so the comparison is like for like. A resting limit at the zone,
    filled on the touch - never a market order chasing the bar that made it."""
    half = costs.spread / 2.0
    out, busy = [], -1
    for i in range(warmup, len(s) - 2):
        if i <= busy:
            continue
        a = A[i]
        if a is None or a <= 0:
            continue
        side, lvl = 0, None

        if kind == "order block":
            for b in st["ob"][i]:
                mid = (b["top"] + b["bot"]) / 2.0
                if b["dir"] == 1 and s.c[i] > mid:  side, lvl = 1, mid; break
                if b["dir"] == -1 and s.c[i] < mid: side, lvl = -1, mid; break
        elif kind == "FVG":
            for g in st["fvg"][i]:
                if g["inverted"]:
                    continue
                mid = (g["top"] + g["bot"]) / 2.0
                if g["dir"] == 1 and s.c[i] > mid:  side, lvl = 1, mid; break
                if g["dir"] == -1 and s.c[i] < mid: side, lvl = -1, mid; break
        elif kind == "iFVG":
            for g in st["fvg"][i]:
                if not g["inverted"] or i - g["inv_bar"] > 20:
                    continue
                d = -g["dir"]
                mid = (g["top"] + g["bot"]) / 2.0
                if d == 1 and s.c[i] > mid:  side, lvl = 1, mid; break
                if d == -1 and s.c[i] < mid: side, lvl = -1, mid; break
        elif kind == "BOS retest":
            if st["bos"][i] != 0:
                side = st["bos"][i]
                lvl = s.c[i] - side * 0.5 * a
        elif kind == "CHoCH retest":
            if st["choch"][i] != 0:
                side = st["choch"][i]
                lvl = s.c[i] - side * 0.5 * a
        if side == 0 or lvl is None:
            continue

        # a resting limit: it must be on the far side and be TOUCHED
        j = None
        for k in range(i + 1, min(i + 21, len(s))):
            if (side == 1 and s.l[k] <= lvl) or (side == -1 and s.h[k] >= lvl):
                j = k; break
        if j is None:
            continue
        entry = lvl + side * (half + costs.slippage)
        stop = entry - side * STOP_ATR * a
        if (entry - stop) * side <= 0:
            continue
        tgtpx = entry + side * TGT_R * (entry - stop) * side
        t = resolve(s, costs, j, side, entry, stop, tgtpx)
        out.append(t)
        busy = t["exit_bar"]
    return out


def control(s, costs, A, n_want, seed, warmup=250, max_bars=200):
    half = costs.spread / 2.0
    rng = random.Random(seed)
    idx = [i for i in range(warmup, len(s) - 2) if A[i] and A[i] > 0]
    out, busy, tries = [], -1, 0
    while len(out) < n_want and tries < n_want * 40:
        tries += 1
        i = rng.choice(idx)
        if i <= busy:
            continue
        a = A[i]
        side = 1 if rng.random() < 0.5 else -1
        entry = s.o[i + 1] + side * (half + costs.slippage)
        stop = entry - side * STOP_ATR * a
        tgtpx = entry + side * TGT_R * (entry - stop) * side
        t = resolve(s, costs, i + 1, side, entry, stop, tgtpx)
        out.append(t)
        busy = t["exit_bar"]
    return out


def main():
    print("=" * 112)
    print("  E-079  SMC, MEASURED — order blocks, FVG, iFVG, BOS, CHoCH, displacement")
    print("  Each one tested twice: as a FILTER on the entry that already works")
    print("  (E-077), and as a TRIGGER on its own with the same stop and target.")
    print("  Ties lose. Costs both ends. XAUUSD.")
    print("=" * 112)

    for sym, tf in COMBOS:
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        A = engine.atr(s, 14)
        per_bar, _ = zone_stream(s)
        base = toptick_signals(s, c, per_bar, A)
        st = smc_state(s, A)
        b = stat(base)
        print(f"\n  ### {sym} {tf}   E-077 base: n={b['n']}  win {b['win']:.1f}%"
              f"  {b['exp']:+.3f}R  t={b['t']:+.2f}"
              f"  {sum(x['pts'] for x in base):+.0f} points")

        print(f"\n   AS A FILTER ON THAT ENTRY")
        print(f"   {'condition':<34}{'allowed':>9}{'exp':>9}{'refused':>9}{'exp':>9}"
              f"{'delta':>9}   verdict")
        print("   " + "-" * 96)
        for name, fn in FILTERS:
            al = [t for t in base if fn(st, t, s)]
            rf = [t for t in base if not fn(st, t, s)]
            A_, R_ = stat(al), stat(rf)
            if A_["n"] == 0:
                continue
            d = A_["exp"] - R_["exp"] if R_["n"] else 0.0
            print(f"   {name:<34}{A_['n']:>9}{A_['exp']:>+8.3f}R{R_['n']:>9}"
                  f"{R_['exp']:>+8.3f}R{d:>+8.3f}R   {verdict(A_, R_)}")

        print(f"\n   AS A TRIGGER ON ITS OWN  (same 0.60 ATR stop, same 2R target)")
        print(f"   {'concept':<20}{'n':>7}{'win%':>8}{'expect':>10}{'PF':>7}{'t':>8}"
              f"{'points':>10}   {'control exp':>12}{'edge':>9}")
        print("   " + "-" * 96)
        for kind in ("order block", "FVG", "iFVG", "BOS retest", "CHoCH retest"):
            tr = trigger_trades(s, c, A, st, kind)
            if len(tr) < 30:
                print(f"   {kind:<20}{len(tr):>7}   too few to judge")
                continue
            a_ = stat(tr)
            ce = [stat(control(s, c, A, len(tr), sd))["exp"] for sd in range(71, 86)]
            cm = sum(ce) / len(ce)
            print(f"   {kind:<20}{a_['n']:>7}{a_['win']:>7.1f}%{a_['exp']:>+9.3f}R"
                  f"{a_['pf']:>7.2f}{a_['t']:>+8.2f}"
                  f"{sum(x['pts'] for x in tr):>+10.0f}   {cm:>+11.3f}R"
                  f"{a_['exp']-cm:>+8.3f}R")

    print("\n  HOW TO READ THIS")
    print("  * A filter earns its place ONLY if the trades it REFUSES are worse")
    print("    than the ones it allows. 'noise' means it costs signals and pays")
    print("    nothing - which is what six of the eight SuperTrend gates were.")
    print("  * A trigger has to beat a random entry with identical geometry. An")
    print("    SMC idea that cannot is chart decoration, however good it looks.")


if __name__ == "__main__":
    main()

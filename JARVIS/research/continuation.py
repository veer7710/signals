"""
E-052 — Does the trend continue? And can you tell BEFORE you enter?

Veer, verbatim: "the ea doesn't understand a trend doesn't always continue so
when its constantly doing a buy or a sell it needs to actually use analysis
and see if it will continue as we don't wanna enter on the end of a trend get
caught in the reversal or new trend".

That is a hypothesis with a number attached, so it gets measured rather than
implemented. The claim decomposes into two separate questions, and they have
different answers:

  Q1  Does the chance of continuation FALL as a one-way run gets longer?
  Q2  Is the fall big enough, and stable enough across markets, to gate on?

Q1 can be true while Q2 is false, and that distinction is the whole point:
a real but tiny gradient that reverses sign on the next symbol is how a filter
gets fitted to noise (E-041: a filter improves a zero-edge entry toward zero,
never past it).

THE OUTCOME MEASURED IS DELIBERATELY NOT "R"
"How much did it make" depends on the exit rule, so conditioning R on entry
features measures the exit as much as the entry. Instead the outcome is
  P(+1R before -1R)  -- did price travel one unit of risk in the trade's
                        favour before it travelled one unit against?
which is a property of the ENTRY alone. A coin flip on a driftless series is
slightly under 50% once costs are paid. That is the number every bucket below
has to beat, and the base rate for the whole sample is printed first so no
bucket can be read without it.

FEATURES, all computed from information available AT THE BAR OF ENTRY:
  streak   consecutive same-direction signals with no opposite signal between
  stretch  |close - DEMA(200)| / ATR   (how far price has run from its mean)
  runbars  bars since the last opposite-direction signal
  runmove  price travelled since that signal, in ATR
  pos      where the entry sits in the last 100 bars' range (0 = low, 1 = high)
  adx      trend strength, already known to matter

Run:  python3 JARVIS/research/continuation.py [SYMBOL] [TF]
      python3 JARVIS/research/continuation.py ALL
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies, study
from engine import Series


def collect(s: Series, costs, warmup=300, horizon=200):
    """Every signal, its entry-time features, and whether it reached +1R
    before -1R. Nothing here reads a bar earlier than i+1 for the entry or
    later than the resolution bar for the outcome."""
    ctx = engine.build_context(s)
    sig = strategies.supertrend_sniper_ea(s)
    D = strategies.dema(s.c, 200)
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot

    rows = []
    streak = 0
    last_side = 0
    run_start = 0

    for i in range(warmup, len(s) - 2):
        sg = sig(ctx, i)
        if not sg:
            continue
        side = sg["side"]
        if side == last_side:
            streak += 1
        else:
            streak = 1
            run_start = i
        last_side = side

        a = ctx["atr"][i]
        d = D[i]
        if a is None or a <= 0 or d is None:
            continue

        entry = s.o[i + 1] + side * (half + costs.slippage)
        stop = sg["stop"]
        risk = abs(entry - stop)
        if risk <= 0:
            continue

        # ---- outcome: +1R before -1R, decided bar by bar from i+1 onward.
        # A bar that spans both levels is scored as a LOSS. That is the
        # pessimistic reading and it is the correct one: OHLC cannot say which
        # side was touched first, and assuming the good one is free money
        # (L-012).
        up = entry + side * risk
        dn = entry - side * risk
        won = None
        for j in range(i + 1, min(i + 1 + horizon, len(s))):
            hi, lo = s.h[j], s.l[j]
            hit_bad = (lo <= dn) if side == 1 else (hi >= dn)
            hit_good = (hi >= up) if side == 1 else (lo <= up)
            if hit_bad:
                won = False; break
            if hit_good:
                won = True; break
        if won is None:
            continue                        # unresolved inside the horizon

        # ---- features, all as of bar i
        lo100 = min(s.l[max(0, i - 99):i + 1])
        hi100 = max(s.h[max(0, i - 99):i + 1])
        pos = (s.c[i] - lo100) / (hi100 - lo100) if hi100 > lo100 else 0.5
        if side == -1:
            pos = 1.0 - pos                 # "how extended in MY direction"

        rows.append({
            "i": i, "side": side, "won": won,
            "streak":  streak,
            "stretch": abs(s.c[i] - d) / a,
            "runbars": i - run_start,
            "runmove": abs(s.c[i] - s.c[run_start]) / a if run_start < i else 0.0,
            "pos":     pos,
            "adx":     ctx["adx"][i] or 0.0,
        })
    return rows


def wilson(k, n, z=1.96):
    """95% interval for a proportion. Printed on every bucket because a 62%
    win rate on 11 trades and on 300 trades are not the same statement, and
    the whole failure mode here is reading the first as if it were the second."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def bucket(rows, key, edges, base):
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = [r for r in rows if lo <= r[key] < hi]
        if len(sel) < 25:
            out.append((lo, hi, len(sel), None, None, None))
            continue
        k = sum(1 for r in sel if r["won"])
        p = k / len(sel)
        l, u = wilson(k, len(sel))
        out.append((lo, hi, len(sel), p, l, u))
    return out


def show(name, rows, key, edges, base, unit=""):
    print(f"\n  by {name}")
    print(f"    {'bucket':<16}{'n':>6}{'P(+1R first)':>14}{'95% interval':>20}"
          f"{'vs base':>10}")
    prev = None
    mono = True
    for lo, hi, n, p, l, u in bucket(rows, key, edges, base):
        lab = f"{lo:g}-{hi:g}{unit}" if hi < 1e9 else f"{lo:g}{unit}+"
        if p is None:
            print(f"    {lab:<16}{n:>6}{'too few':>14}")
            continue
        sig = " *" if (l > base or u < base) else ""
        print(f"    {lab:<16}{n:>6}{100*p:>13.1f}%"
              f"{f'{100*l:.1f} - {100*u:.1f}%':>20}{100*(p-base):>+9.1f}{sig}")
        if prev is not None and p > prev + 0.005:
            mono = False
        prev = p
    print(f"    monotone decline across buckets: {'YES' if mono else 'no'}")
    return mono


def run(symbol="GOLD", tf="1h", quiet=False):
    s = engine.load(symbol, tf)
    costs = study.COSTS.get(symbol, engine.Costs())
    rows = collect(s, costs)
    if not rows:
        print(f"{symbol} {tf}: no resolved signals")
        return None
    k = sum(1 for r in rows if r["won"])
    base = k / len(rows)
    lo, hi = wilson(k, len(rows))

    print("=" * 78)
    print(f"  E-052  DOES THE TREND CONTINUE? — {symbol} {tf}")
    print("=" * 78)
    print(f"\n  BASE RATE: {k} of {len(rows)} signals reached +1R before -1R "
          f"= {100*base:.1f}%  (95% {100*lo:.1f}-{100*hi:.1f}%)")
    print(f"  Every bucket below must be read against that number, not against 50%.")
    print(f"  '*' marks a bucket whose interval excludes the base rate.")

    if quiet:
        return rows, base

    show("consecutive same-direction signals", rows, "streak",
         [1, 2, 3, 4, 6, 1e9], base)
    show("stretch from DEMA200", rows, "stretch",
         [0, 0.5, 1.0, 1.5, 2.5, 1e9], base, " ATR")
    show("bars since the opposite signal", rows, "runbars",
         [0, 5, 15, 40, 100, 1e9], base)
    show("distance travelled in this run", rows, "runmove",
         [0, 1, 2, 4, 8, 1e9], base, " ATR")
    show("position in the last 100 bars", rows, "pos",
         [0, 0.25, 0.5, 0.75, 0.9, 1e9], base)
    show("ADX at entry", rows, "adx",
         [0, 20, 25, 35, 50, 1e9], base)
    return rows, base


def run_all():
    """The only test that matters: does the SAME gradient appear on markets
    the rule was not designed on? A gradient that shows up on one symbol is a
    story; one that shows up on five is a finding."""
    combos = [("GOLD", "1h"), ("GOLD", "15m"), ("EURUSD", "1h"),
              ("GBPUSD", "1h"), ("US500", "1h"), ("US500", "15m"),
              ("EURUSD", "15m"), ("GBPUSD", "15m")]
    feats = [("streak", [1, 2, 3, 4, 6, 1e9]),
             ("stretch", [0, 0.5, 1.0, 1.5, 2.5, 1e9]),
             ("runbars", [0, 5, 15, 40, 100, 1e9]),
             ("runmove", [0, 1, 2, 4, 8, 1e9]),
             ("pos", [0, 0.25, 0.5, 0.75, 0.9, 1e9]),
             ("adx", [0, 20, 25, 35, 50, 1e9])]
    print("=" * 78)
    print("  E-052  CROSS-MARKET: does the same gradient appear everywhere?")
    print("  Cell = P(+1R first) minus that market's own base rate, in points.")
    print("  A real effect is the SAME SIGN across a row. Mixed signs are noise.")
    print("=" * 78)

    store = {}
    for sym, tf in combos:
        try:
            s = engine.load(sym, tf)
        except Exception:
            continue
        costs = study.COSTS.get(sym, engine.Costs())
        rows = collect(s, costs)
        if len(rows) < 100:
            continue
        base = sum(1 for r in rows if r["won"]) / len(rows)
        store[f"{sym} {tf}"] = (rows, base)
        print(f"  {sym} {tf}: {len(rows)} resolved signals, base {100*base:.1f}%")

    for key, edges in feats:
        print(f"\n  --- {key} " + "-" * (60 - len(key)))
        labs = [f"{lo:g}-{hi:g}" if hi < 1e9 else f"{lo:g}+"
                for lo, hi in zip(edges[:-1], edges[1:])]
        print(f"    {'market':<14}" + "".join(f"{l:>11}" for l in labs))
        agree = [0] * len(labs)
        seen = [0] * len(labs)
        for name, (rows, base) in store.items():
            cells = []
            for bi, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
                sel = [r for r in rows if lo <= r[key] < hi]
                if len(sel) < 25:
                    cells.append(f"{'-':>11}")
                    continue
                p = sum(1 for r in sel if r["won"]) / len(sel)
                d = 100 * (p - base)
                cells.append(f"{d:>+11.1f}")
                seen[bi] += 1
                if d < 0:
                    agree[bi] += 1
            print(f"    {name:<14}" + "".join(cells))
        print(f"    {'BELOW base':<14}"
              + "".join(f"{f'{agree[b]}/{seen[b]}':>11}" for b in range(len(labs))))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].upper() == "ALL":
        run_all()
    else:
        run(sys.argv[1] if len(sys.argv) > 1 else "GOLD",
            sys.argv[2] if len(sys.argv) > 2 else "1h")

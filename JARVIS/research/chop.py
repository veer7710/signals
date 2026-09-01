"""
E-053 — Sideways price action: how much does it cost, and can it be seen coming?

Veer sent an M1 gold screenshot: roughly 16 SuperTrend signals in 24 minutes,
inside a range of about $4.50, oscillating around two level lines 22 cents
apart. Then: "u can [see] how we perform shit in sideways price action make
sure we can limit loss on those".

That is two separate claims and they are tested separately:

  Q1  Do signals taken in sideways conditions actually lose more than signals
      taken elsewhere? (It is possible they merely FEEL worse because there
      are so many of them.)
  Q2  Is the sideways state visible BEFORE the entry, from bars already
      closed, well enough to refuse the trade?

Q2 is the one that matters. A regime that can only be recognised afterwards
is a description, not a filter.

FOUR DEFINITIONS OF "SIDEWAYS", tested against each other:
  flips20/flips50   SuperTrend direction changes in the last 20 / 50 bars.
                    This is the one in Veer's screenshot - a run of flips is
                    one range being sliced, not a run of setups. It is also
                    the cheapest to implement in the EA, which already
                    computes the direction.
  er20/er50         Kaufman efficiency ratio: |net move| / |total path|.
                    1.0 = a straight line, 0.0 = pure noise.
  comp20/comp50     Range compression: (highest high - lowest low) / ATR.
                    A small number means price is coiled.
  adx               Included for comparison only; E-052 already measured it
                    as the weakest of the readings tested there.

THE THREE OUTCOMES, because "loses more" can mean three different things:
  P(+1R first)  did price travel 1R the right way before 1R the wrong way
  expectancy    R per trade under the EA's own exit (1.5 ATR stop, 3R target,
                50-bar cap), so the answer is in money and not just in
                direction
  loss share    what FRACTION of every losing R in the whole sample happened
                in this bucket. This is the "limit loss" question exactly as
                Veer asked it: if half the damage is in one identifiable
                bucket, that bucket is worth refusing.

Run:  python3 JARVIS/research/chop.py [SYMBOL] [TF]
      python3 JARVIS/research/chop.py ALL
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies, study
from engine import Series

COMBOS = [("GOLD", "1h"), ("GOLD", "15m"), ("EURUSD", "1h"), ("EURUSD", "15m"),
          ("GBPUSD", "1h"), ("GBPUSD", "15m"), ("US500", "1h"), ("US500", "15m")]

FEATURES = [
    ("flips20", [0, 1, 2, 3, 5, 1e9],           "SuperTrend flips in the last 20 bars"),
    ("flips50", [0, 2, 4, 6, 9, 1e9],           "SuperTrend flips in the last 50 bars"),
    ("er20",    [0, .10, .20, .35, .55, 1e9],   "efficiency ratio over 20 bars (low = choppy)"),
    ("er50",    [0, .08, .15, .25, .40, 1e9],   "efficiency ratio over 50 bars (low = choppy)"),
    ("comp20",  [0, 2.5, 4, 6, 9, 1e9],         "20-bar range in ATRs (low = coiled)"),
    ("comp50",  [0, 4, 6.5, 10, 15, 1e9],       "50-bar range in ATRs (low = coiled)"),
    ("adx",     [0, 15, 20, 25, 35, 1e9],       "ADX at entry"),
    ("costfrac",[0, .04, .07, .11, .18, 1e9],    "round-trip cost as a fraction of the stop distance"),
]


def efficiency(c, i, n):
    """Kaufman efficiency ratio. Net distance divided by path length. Uses
    only closes at or before bar i."""
    if i < n:
        return None
    net = abs(c[i] - c[i - n])
    path = sum(abs(c[j] - c[j - 1]) for j in range(i - n + 1, i + 1))
    return (net / path) if path > 0 else 0.0


def collect(s: Series, costs, warmup=300, horizon=200, max_bars=50,
            stop_atr=1.5, rr=3.0):
    ctx = engine.build_context(s)
    sig = strategies.supertrend_sniper_ea(s)
    d, _fu, _fl = strategies.supertrend_dir(s, 7, 1.2)
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot

    # flip[i] = 1 if the SuperTrend direction changed ON bar i. Counting these
    # over a trailing window uses only closed bars, so it is available at the
    # moment of the decision.
    flip = [0] * len(s)
    for i in range(1, len(s)):
        if d[i] != 0 and d[i - 1] != 0 and d[i] != d[i - 1]:
            flip[i] = 1
    cum = [0] * (len(s) + 1)
    for i in range(len(s)):
        cum[i + 1] = cum[i] + flip[i]

    rows = []
    for i in range(warmup, len(s) - 2):
        sg = sig(ctx, i)
        if not sg:
            continue
        side = sg["side"]
        a = ctx["atr"][i]
        if a is None or a <= 0:
            continue

        entry = s.o[i + 1] + side * (half + costs.slippage)
        stop = entry - side * stop_atr * a
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        target = entry + side * rr * risk

        # ---- outcome A: +1R before -1R.  A bar spanning both scores as a
        # LOSS - OHLC cannot say which came first (L-012).
        up, dn = entry + side * risk, entry - side * risk
        won = None
        for j in range(i + 1, min(i + 1 + horizon, len(s))):
            bad = (s.l[j] <= dn) if side == 1 else (s.h[j] >= dn)
            good = (s.h[j] >= up) if side == 1 else (s.l[j] <= up)
            if bad:
                won = False; break
            if good:
                won = True; break
        if won is None:
            continue

        # ---- outcome B: R under the EA's own exit, same tie rule
        r = None
        for j in range(i + 1, min(i + 1 + max_bars, len(s))):
            hit_s = (s.l[j] <= stop) if side == 1 else (s.h[j] >= stop)
            hit_t = (s.h[j] >= target) if side == 1 else (s.l[j] <= target)
            if hit_s:
                r = ((stop - entry) * side - comm_px) / risk; break
            if hit_t:
                r = ((target - entry) * side - comm_px) / risk; break
        if r is None:
            j = min(i + max_bars, len(s) - 1)
            fill = s.c[j] - side * (half + costs.slippage)
            r = ((fill - entry) * side - comm_px) / risk

        # ---- features, all from bars at or before i
        e20, e50 = efficiency(s.c, i, 20), efficiency(s.c, i, 50)
        if e20 is None or e50 is None:
            continue
        rows.append({
            "won": won, "r": r, "side": side,
            "flips20": cum[i + 1] - cum[max(0, i - 19)],
            "flips50": cum[i + 1] - cum[max(0, i - 49)],
            "er20": e20, "er50": e50,
            "comp20": (max(s.h[i - 19:i + 1]) - min(s.l[i - 19:i + 1])) / a,
            "comp50": (max(s.h[i - 49:i + 1]) - min(s.l[i - 49:i + 1])) / a,
            "adx": ctx["adx"][i] or 0.0,
            # THE M1 HYPOTHESIS. Within one symbol the spread is fixed, so this
            # varies only with ATR: it is "how much of my risk am I paying to
            # the broker before the trade starts". On GOLD 15m the stop is
            # perhaps 40x the spread; on GOLD M1 it can be 2x. That difference
            # is not a regime, it is arithmetic, and it is the reason a range
            # that is survivable on 15m is fatal on M1.
            "costfrac": (costs.spread + 2 * costs.slippage + comm_px) / risk,
        })
    return rows


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / den, (c + r) / den)


def label(lo, hi):
    return f"{lo:g}-{hi:g}" if hi < 1e9 else f"{lo:g}+"


def run(symbol="GOLD", tf="1h"):
    s = engine.load(symbol, tf)
    costs = study.COSTS.get(symbol, engine.Costs())
    rows = collect(s, costs)
    if not rows:
        print(f"{symbol} {tf}: nothing resolved")
        return
    n = len(rows)
    base_p = sum(1 for r in rows if r["won"]) / n
    base_r = sum(r["r"] for r in rows) / n
    tot_loss = sum(r["r"] for r in rows if r["r"] < 0)

    print("=" * 84)
    print(f"  E-053  SIDEWAYS PRICE ACTION — {symbol} {tf}")
    print("=" * 84)
    print(f"\n  {n} signals.  base P(+1R first) {100*base_p:.1f}%   "
          f"base expectancy {base_r:+.3f}R   total losing R {tot_loss:+.1f}")
    print(f"  'loss share' = what fraction of ALL losing R happened in that bucket.")
    print(f"  A bucket holding 10% of trades and 25% of the damage is the target.")

    for key, edges, desc in FEATURES:
        print(f"\n  {desc}")
        print(f"    {'bucket':<12}{'n':>6}{'% of trades':>13}{'P(+1R)':>9}"
              f"{'expectancy':>12}{'loss share':>12}{'concentration':>15}")
        for lo, hi in zip(edges[:-1], edges[1:]):
            sel = [r for r in rows if lo <= r[key] < hi]
            if len(sel) < 25:
                print(f"    {label(lo,hi):<12}{len(sel):>6}{'  too few':>13}")
                continue
            p = sum(1 for r in sel if r["won"]) / len(sel)
            e = sum(r["r"] for r in sel) / len(sel)
            ls = sum(r["r"] for r in sel if r["r"] < 0)
            share = ls / tot_loss if tot_loss < 0 else 0.0
            frac = len(sel) / n
            conc = share / frac if frac > 0 else 0.0
            print(f"    {label(lo,hi):<12}{len(sel):>6}{100*frac:>12.1f}%"
                  f"{100*p:>8.1f}%{e:>+11.3f}R{100*share:>11.1f}%{conc:>14.2f}x")


def run_all():
    """The filter is only worth building if the SAME bucket is bad on markets
    it was not chosen on."""
    print("=" * 84)
    print("  E-053  CROSS-MARKET — expectancy in R by bucket, and what a filter costs")
    print("=" * 84)
    store = {}
    for sym, tf in COMBOS:
        try:
            s = engine.load(sym, tf)
        except Exception:
            continue
        rows = collect(s, study.COSTS.get(sym, engine.Costs()))
        if len(rows) < 100:
            continue
        store[f"{sym} {tf}"] = rows
        print(f"  {sym} {tf}: {len(rows)} signals, "
              f"expectancy {sum(r['r'] for r in rows)/len(rows):+.3f}R")

    for key, edges, desc in FEATURES:
        print(f"\n  --- {key}: {desc}")
        labs = [label(lo, hi) for lo, hi in zip(edges[:-1], edges[1:])]
        print(f"    {'market':<14}" + "".join(f"{l:>11}" for l in labs))
        worst_first = [0] * len(labs)
        seen = [0] * len(labs)
        for name, rows in store.items():
            base = sum(r["r"] for r in rows) / len(rows)
            cells = []
            for bi, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
                sel = [r for r in rows if lo <= r[key] < hi]
                if len(sel) < 25:
                    cells.append(f"{'-':>11}"); continue
                e = sum(r["r"] for r in sel) / len(sel)
                cells.append(f"{e:>+11.3f}")
                seen[bi] += 1
                if e < base:
                    worst_first[bi] += 1
            print(f"    {name:<14}" + "".join(cells))
        print(f"    {'BELOW own base':<14}"
              + "".join(f"{f'{worst_first[b]}/{seen[b]}':>11}" for b in range(len(labs))))

    # ---- WHAT DOES THE FILTER ACTUALLY BUY?
    # Refusing a bucket is only worth it if the trades removed were worse than
    # the ones kept BY ENOUGH to matter after you have also removed their
    # winners. This prints the honest before/after.
    print("\n" + "=" * 84)
    print("  WHAT A FILTER WOULD ACTUALLY BUY  (total R, all trades vs filtered)")
    print("=" * 84)
    rules = [
        ("skip flips20 >= 3", lambda r: r["flips20"] >= 3),
        ("skip flips20 >= 5", lambda r: r["flips20"] >= 5),
        ("skip flips50 >= 6", lambda r: r["flips50"] >= 6),
        ("skip flips50 >= 9", lambda r: r["flips50"] >= 9),
        ("skip er20 < 0.10",  lambda r: r["er20"] < 0.10),
        ("skip er20 < 0.20",  lambda r: r["er20"] < 0.20),
        ("skip er50 < 0.15",  lambda r: r["er50"] < 0.15),
        ("skip comp20 < 2.5", lambda r: r["comp20"] < 2.5),
        ("skip costfrac>0.07", lambda r: r["costfrac"] > 0.07),
        ("skip costfrac>0.11", lambda r: r["costfrac"] > 0.11),
        ("skip costfrac>0.18", lambda r: r["costfrac"] > 0.18),
        ("skip er50 < 0.08",  lambda r: r["er50"] < 0.08),
        ("skip er50<.08 OR f20>=5", lambda r: r["er50"] < 0.08 or r["flips20"] >= 5),
    ]
    print(f"\n    {'rule':<20}{'market':<14}{'kept':>7}{'cut':>6}"
          f"{'totR before':>13}{'totR after':>12}{'change':>10}")
    for name, pred in rules:
        agree = 0
        tested = 0
        for mkt, rows in store.items():
            before = sum(r["r"] for r in rows)
            kept = [r for r in rows if not pred(r)]
            after = sum(r["r"] for r in kept)
            tested += 1
            if after > before:
                agree += 1
            print(f"    {name:<20}{mkt:<14}{len(kept):>7}{len(rows)-len(kept):>6}"
                  f"{before:>+12.1f}{after:>+12.1f}{after-before:>+10.1f}")
        print(f"    {'':<20}{'IMPROVED IN':<14}{f'{agree}/{tested}':>7} markets\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].upper() == "ALL":
        run_all()
    else:
        run(sys.argv[1] if len(sys.argv) > 1 else "GOLD",
            sys.argv[2] if len(sys.argv) > 2 else "15m")

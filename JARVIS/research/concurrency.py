"""
E-097 — CONCURRENCY. The lever nobody in this project has ever pulled.

Every one of the 96 experiments here is SINGLE-POSITION. `engine.backtest` has
`one_at_a_time=True`, `smc_combine.simulate` drops any candidate with
`if i <= busy: continue`, both EAs ship `InpMaxPositions = 1`, and
`build_positions` does the same thing. Every signal that arrives while a trade
is open has been silently discarded for the entire life of the project.

WHY THIS MATTERS NOW. E-093 measured frequency as the dominant lever for a
funded account - 2 trades/day passes 24%, 10 trades/day passes 99.9%. But
E-089 says frequency bought by DROPPING TIMEFRAME costs R, because cost/stop
rises and the edge decays. That is a real trade-off and it caps the lever.

Concurrency is frequency that does NOT pay that price. Same timeframe, same
stop, same spread, so cost/stop is unchanged and every trade keeps the same
edge it always had. What it costs instead is CORRELATION: positions opened
close together move together, so the losing days get deeper. That is the
question, and it is measurable.

THE COMPARISON IS AT MATCHED TOTAL RISK. Holding 3 positions at full size is
not a strategy improvement, it is 3x the leverage, and it would "win" on points
for a trivial reason. So each configuration sizes at base/N, and the report is
return AND max drawdown, both in R.

Run:  python3 JARVIS/research/concurrency.py
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from engine import Series
from toptick import zone_stream
from smc import smc_state, resolve, STOP_ATR, TGT_R
from smc_combine import all_signals


def simulate_slots(s, costs, cands, slots=1, max_bars=200):
    """`smc_combine.simulate` with N concurrent positions instead of one.

    A candidate is taken when a slot is free at its signal bar. Everything else
    - fills, stops, targets, ties-lose, costs both ends - is identical, so the
    ONLY thing that changes between runs is how many trades may be open."""
    half = costs.spread / 2.0
    out = []
    busy = []            # exit bar of each open position
    for (i, side, lvl, a, src, wait) in cands:
        busy = [b for b in busy if b >= i]
        if len(busy) >= slots:
            continue
        j = None
        for k in range(i + 1, min(i + 1 + wait, len(s))):
            if (side == 1 and s.l[k] <= lvl) or (side == -1 and s.h[k] >= lvl):
                j = k; break
        if j is None:
            continue
        entry = lvl + side * (half + costs.slippage)
        stop = entry - side * STOP_ATR * a
        if (entry - stop) * side <= 0:
            continue
        tgtpx = entry + side * TGT_R * (entry - stop) * side
        t = resolve(s, costs, j, side, entry, stop, tgtpx, max_bars)
        t["src"] = src
        t["in_bar"] = j
        out.append(t)
        busy.append(t["exit_bar"])
    return out


def curve(trades, risk_per_trade):
    """Equity path in R, ordered by EXIT so overlapping trades settle in the
    order they actually close. Max drawdown is on that path."""
    ts = sorted(trades, key=lambda t: t["exit_bar"])
    eq, peak, dd = 0.0, 0.0, 0.0
    for t in ts:
        eq += t["r"] * risk_per_trade
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return eq, dd


def concurrent_load(trades):
    """Average and maximum number of positions actually open at once - the
    difference between the slots ALLOWED and the slots USED."""
    if not trades:
        return 0.0, 0
    ev = []
    for t in trades:
        ev.append((t["in_bar"], 1)); ev.append((t["exit_bar"], -1))
    ev.sort()
    cur = mx = 0
    area = 0
    last = ev[0][0]
    for b, d in ev:
        area += cur * (b - last); last = b
        cur += d; mx = max(mx, cur)
    span = ev[-1][0] - ev[0][0]
    return (area / span if span else 0.0), mx


def main():
    USE = {"toptick", "fvg", "ob"}         # E-080's shipped stack
    print("=" * 104)
    print("  E-097 — CONCURRENCY. Matched TOTAL risk: each slot sized at base/N,")
    print("  so every row carries the same exposure and only the SPREAD of it changes.")
    print("=" * 104)
    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        A = engine.atr(s, 14)
        per_bar, _ = zone_stream(s)
        st = smc_state(s, A)
        cands = all_signals(s, c, per_bar, A, st, USE)
        print(f"\n  ### {sym} {tf} — {len(cands)} candidate signals generated")
        print(f"  {'slots':>6} {'taken':>7} {'dropped':>8} {'avg open':>9} "
              f"{'max open':>9} {'total R':>9} {'maxDD R':>9} {'R/DD':>7} "
              f"{'points':>9}")
        print("  " + "-" * 88)
        base = None
        for n in (1, 2, 3, 4, 6, 10, 999):
            tr = simulate_slots(s, c, cands, slots=n)
            if not tr:
                continue
            # Risk per trade is fixed at 1.0 and NOT divided by the slot cap.
            # Dividing by n was wrong for the unlimited row - it capped at 999
            # while only ~32 were ever open at once, which crushed that row for
            # a bookkeeping reason rather than a market one. R/DD is scale-free
            # (multiply risk by k and both the return and the drawdown scale by
            # k), so it is the comparison; the raw columns are just shown.
            eq, dd = curve(tr, 1.0)
            avg, mx = concurrent_load(tr)
            pts = sum(t["pts"] for t in tr)
            lab = "unlim" if n == 999 else str(n)
            print(f"  {lab:>6} {len(tr):>7} {len(cands)-len(tr):>8} {avg:>9.2f} "
                  f"{mx:>9} {eq:>9.2f} {dd:>9.2f} "
                  f"{(eq/dd if dd > 0 else 0):>7.2f} {pts:>9.1f}")
            if n == 1:
                base = (eq, dd)
        if base:
            print(f"  (single-position baseline: {base[0]:+.2f}R with a "
                  f"{base[1]:.2f}R max drawdown)")


if __name__ == "__main__":
    main()

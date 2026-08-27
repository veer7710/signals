"""
JARVIS study runner — the anti-overfitting harness.

Running a strategy once over all history and reporting the profit is how
people fool themselves. This runner instead reports, for every strategy:

  IN-SAMPLE          the headline number (the seductive one)
  WALK-FORWARD       the same rules across 6 non-overlapping periods
  MONTE CARLO        what drawdown to expect if the trade order reshuffles
  COST SENSITIVITY   what happens as spread widens
  LONG vs SHORT      whether the "edge" is just a bull-market bias

A strategy is only PROMISING if it survives all five. Anything else is
REJECTED or UNPROVEN, and is recorded as such.

Usage:  python3 JARVIS/research/study.py [SYMBOL] [TIMEFRAME]
"""
from __future__ import annotations
import json, os, sys, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies

REPORTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports")

# Realistic retail costs, in PRICE units of the instrument.
COSTS = {
    "GOLD":   engine.Costs(spread=0.30, slippage=0.05, commission_per_lot=7.0,
                           value_per_point_per_lot=100.0),
    "US500":  engine.Costs(spread=0.50, slippage=0.10, commission_per_lot=5.0,
                           value_per_point_per_lot=50.0),
    "EURUSD": engine.Costs(spread=0.00012, slippage=0.00003, commission_per_lot=7.0,
                           value_per_point_per_lot=100000.0),
    "GBPUSD": engine.Costs(spread=0.00016, slippage=0.00004, commission_per_lot=7.0,
                           value_per_point_per_lot=100000.0),
}


def build(name, s):
    """Instantiate a strategy with its default parameters."""
    f = strategies.REGISTRY[name]
    return f(s)


def verdict(st, wf_positive, wf_total, mc):
    """Classify honestly. These words mean what the directive says they mean."""
    if st["n"] < 30:
        return "UNPROVEN (too few trades)"
    if st["expectancy_R"] <= 0:
        return "REJECTED (negative expectancy after costs)"
    if st["t_stat"] < 2.0:
        return "UNPROVEN (edge not distinguishable from noise)"
    if wf_positive < wf_total * 0.6:
        return "REJECTED (fails walk-forward — regime dependent)"
    if mc and mc["p_dd_over_30pct"] > 0.5:
        return "UNPROVEN (drawdown risk too high)"
    return "PROMISING (survived; still not proof of future profit)"


def run(symbol="GOLD", tf="1h"):
    s = engine.load(symbol, tf)
    costs = COSTS.get(symbol, engine.Costs())
    d0 = datetime.datetime.fromtimestamp(s.ts[0], datetime.timezone.utc).date()
    d1 = datetime.datetime.fromtimestamp(s.ts[-1], datetime.timezone.utc).date()

    print("=" * 74)
    print(f"  JARVIS STRATEGY STUDY — {symbol} {tf}")
    print(f"  {len(s)} bars   {d0} -> {d1}")
    print(f"  costs: spread {costs.spread} + slippage {costs.slippage}/fill "
          f"+ {costs.commission_per_lot}/lot commission")
    print(f"  entries fill at NEXT bar open · ties resolve as LOSSES")
    print("=" * 74)

    results = {}
    for name in strategies.REGISTRY:
        sig = build(name, s)
        trades = engine.backtest(s, sig, costs, warmup=300)
        st = engine.stats(trades)
        print(f"\n### {name}")
        if st["n"] == 0:
            print("  no trades"); continue
        print("IN-SAMPLE (the seductive number)")
        print(engine.fmt(st))

        # ---- walk-forward
        wf = engine.walk_forward(s, lambda sub, n=name: build(n, sub), costs,
                                 folds=6, warmup=300)
        pos = sum(1 for _, _, w, _ in wf if w.get("n", 0) and w["expectancy_R"] > 0)
        print(f"WALK-FORWARD  ({pos}/{len(wf)} folds positive)")
        for a, b, w, _ in wf:
            da = datetime.datetime.fromtimestamp(a, datetime.timezone.utc).date()
            db = datetime.datetime.fromtimestamp(b, datetime.timezone.utc).date()
            if w.get("n", 0) == 0:
                print(f"  {da} -> {db}   no trades"); continue
            flag = "+" if w["expectancy_R"] > 0 else "-"
            print(f"  {flag} {da} -> {db}  n={w['n']:<4} win {100*w['win_rate']:>4.0f}%  "
                  f"exp {w['expectancy_R']:+.3f}R  totalR {w['total_R']:+.1f}")

        # ---- monte carlo
        mc = engine.monte_carlo(trades)
        print("MONTE CARLO (20k reshuffles, 0.5% risk/trade)")
        print(f"  median maxDD {100*mc['median_dd']:.1f}%   95th-pct maxDD {100*mc['dd_95']:.1f}%")
        print(f"  P(drawdown > 30%) {100*mc['p_dd_over_30pct']:.1f}%   "
              f"P(losing overall) {100*mc['p_losing_overall']:.1f}%")

        # ---- long vs short (regime-bias check)
        lo = [t for t in trades if t.side == 1]
        sh = [t for t in trades if t.side == -1]
        ls, ss = engine.stats(lo), engine.stats(sh)
        print("DIRECTION (is this just a bull-market bias?)")
        print(f"  long  n={ls.get('n',0):<4} exp {ls.get('expectancy_R',0):+.3f}R   "
              f"short n={ss.get('n',0):<4} exp {ss.get('expectancy_R',0):+.3f}R")

        # ---- cost sensitivity
        print("COST SENSITIVITY (does the edge survive a worse broker?)")
        for mult in (1.0, 2.0, 3.0):
            c2 = engine.Costs(spread=costs.spread * mult, slippage=costs.slippage * mult,
                              commission_per_lot=costs.commission_per_lot,
                              value_per_point_per_lot=costs.value_per_point_per_lot)
            t2 = engine.stats(engine.backtest(s, build(name, s), c2, warmup=300))
            print(f"  {mult:.0f}x spread -> exp {t2.get('expectancy_R',0):+.3f}R  "
                  f"totalR {t2.get('total_R',0):+.1f}")

        v = verdict(st, pos, len(wf), mc)
        print(f"VERDICT: {v}")
        results[name] = {"stats": st, "verdict": v,
                         "wf_positive": pos, "wf_total": len(wf), "mc": mc}

    os.makedirs(REPORTS, exist_ok=True)
    out = os.path.normpath(os.path.join(REPORTS, f"study_{symbol}_{tf}.json"))
    with open(out, "w") as f:
        json.dump({k: {"verdict": v["verdict"], "stats": v["stats"],
                       "wf": f"{v['wf_positive']}/{v['wf_total']}"}
                   for k, v in results.items()}, f, indent=1, default=str)
    print("\n" + "=" * 74)
    print("SUMMARY")
    for k, v in results.items():
        print(f"  {k:<22} {v['verdict']}")
    print(f"\nsaved -> {out}")
    return results


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "GOLD",
        sys.argv[2] if len(sys.argv) > 2 else "1h")

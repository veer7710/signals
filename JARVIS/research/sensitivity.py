"""
Parameter sensitivity and multiple-testing correction.

TWO WAYS A BACKTEST LIES, AND THE DEFENCE AGAINST EACH.

1. LUCKY PARAMETERS. A real edge degrades smoothly as you nudge its settings;
   a curve-fit one falls off a cliff because it was tuned to specific noise.
   `sweep()` walks a parameter across a range and shows the whole surface, so a
   lone spike is visible instead of being reported as "the optimum".

2. MULTIPLE TESTING. Test enough variants and one will look great by luck
   alone. If you try N independent strategies with NO real edge, the best of
   them has an expected t-statistic of roughly sqrt(2 * ln N) — this is the
   standard expected-maximum-of-N-normals result, and it is the single most
   under-used check in retail backtesting.

     N=1   -> 0.00      N=10  -> 2.15      N=50  -> 2.80
     N=5   -> 1.79      N=32  -> 2.63      N=100 -> 3.03

   So after testing 32 combinations, a t-stat of 2.6 is what pure luck
   produces. Beating 2.0 means nothing at that point.

References: Bailey & Lopez de Prado on the deflated Sharpe ratio and the
probability of backtest overfitting.
"""
from __future__ import annotations
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies, study


def luck_threshold(n_trials: int) -> float:
    """Expected t-statistic of the BEST of n no-edge strategies."""
    if n_trials <= 1:
        return 0.0
    return math.sqrt(2.0 * math.log(n_trials))


def deflate(t_stat: float, n_trials: int) -> dict:
    """Compare an observed t-stat against what luck alone would produce."""
    thr = luck_threshold(n_trials)
    return {
        "t_stat": t_stat,
        "trials": n_trials,
        "luck_threshold": thr,
        "excess": t_stat - thr,
        "verdict": ("survives multiple testing" if t_stat > thr
                    else "INDISTINGUISHABLE FROM LUCK"),
    }


def sweep(symbol, tf, strat_name, param, values, warmup=300):
    """Run one strategy across a range of one parameter."""
    s = engine.load(symbol, tf)
    costs = study.COSTS.get(symbol, engine.Costs())
    out = []
    for v in values:
        try:
            sig = strategies.REGISTRY[strat_name](s, **{param: v})
        except TypeError:
            return None
        st = engine.stats(engine.backtest(s, sig, costs, warmup=warmup))
        out.append((v, st.get("n", 0), st.get("expectancy_R", 0.0),
                    st.get("t_stat", 0.0)))
    return out


def report_sweep(symbol, tf, strat, param, values):
    rows = sweep(symbol, tf, strat, param, values)
    if rows is None:
        print(f"  {strat}: no parameter '{param}'"); return None
    print(f"\n{strat} on {symbol} {tf} — sweeping '{param}'")
    print(f"  {'value':>8}{'trades':>8}{'expectancy':>13}{'t':>7}   shape")
    best = max(r[2] for r in rows)
    for v, n, e, t in rows:
        bar = "#" * max(0, int(round(20 * (e - min(r[2] for r in rows)) /
                                    (best - min(r[2] for r in rows) + 1e-9))))
        flag = "  <- best" if e == best else ""
        print(f"  {v:>8}{n:>8}{e:>+12.3f}R{t:>+7.2f}   {bar}{flag}")
    pos = sum(1 for r in rows if r[2] > 0)
    print(f"  {pos}/{len(rows)} settings positive.", end=" ")
    print("Plateau — robust." if pos >= 0.7 * len(rows)
          else "Narrow peak — likely curve-fit." if pos <= 0.3 * len(rows)
          else "Mixed.")
    return rows


if __name__ == "__main__":
    print("=" * 78)
    print("  MULTIPLE-TESTING CORRECTION")
    print("=" * 78)
    print("\nHow many strategy/market combinations has this project tested?")
    print("  8 strategies x 4 markets = 32 combinations, plus parameter tweaks.\n")
    for n in (1, 5, 10, 32, 50, 100, 500):
        print(f"  after {n:>4} trials, pure luck produces a best "
              f"t-stat of {luck_threshold(n):.2f}")
    print("\nBEST RESULTS ACTUALLY OBSERVED IN THIS PROJECT:")
    for name, t in [("donchian_trend on GOLD", 1.63), ("ma_cross on GOLD", 1.22)]:
        d = deflate(t, 32)
        print(f"  {name:<26} t={t:+.2f}  vs luck {d['luck_threshold']:.2f}"
              f"  ->  {d['verdict']}")
    print("\nBoth sit BELOW the level luck alone produces after 32 trials.")
    print("That is the cleanest statement of where this project stands:")
    print("no tested strategy has yet beaten chance.\n")

    print("=" * 78)
    print("  PARAMETER SENSITIVITY — plateau or lucky spike?")
    print("=" * 78)
    report_sweep("GOLD", "1h", "donchian_trend", "rr", [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0])
    report_sweep("GOLD", "1h", "donchian_trend", "stop_atr", [1.0, 1.5, 2.0, 2.5, 3.0, 3.5])
    report_sweep("GOLD", "1h", "ma_cross", "rr", [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0])

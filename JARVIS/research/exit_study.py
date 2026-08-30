"""
Exit study — how much of the available move can an exit rule actually keep?

Same entries every time. Only the exit changes.
Run:  python3 JARVIS/research/exit_study.py [SYMBOL] [TF]
"""
from __future__ import annotations
import os, sys, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies, exits


def run(symbol="GOLD", tf="1h"):
    s = engine.load(symbol, tf)
    import study
    costs = study.COSTS.get(symbol, engine.Costs())
    entry = lambda: strategies.donchian_trend(s)

    print("=" * 78)
    print(f"  EXIT STUDY — {symbol} {tf}   (IDENTICAL entries, only the exit changes)")
    print("=" * 78)

    # ---- first: what was actually AVAILABLE?
    base = exits.simulate(s, entry(), exits.POLICIES["ORACLE (not tradeable)"],
                          costs, warmup=300, allow_overlap=True)
    mfes = sorted(t["mfe_r"] for t in base)
    maes = sorted(t["mae_r"] for t in base)
    q = lambda a, p: a[int(p * (len(a) - 1))]
    print(f"\nHOW GOOD DID TRADES EVER GET?  ({len(base)} trades)")
    print(f"  best-ever profit (MFE), median {q(mfes,.5):.2f}R   "
          f"75th {q(mfes,.75):.2f}R   90th {q(mfes,.90):.2f}R   max {mfes[-1]:.2f}R")
    print(f"  worst drawdown before that (MAE), median {q(maes,.5):.2f}R   "
          f"90th {q(maes,.90):.2f}R")
    never = sum(1 for t in base if t["mfe_r"] < 0.3)
    print(f"  trades that NEVER got 0.3R green: {never}/{len(base)} "
          f"({100*never/len(base):.0f}%)  <- entry quality, not exit")

    # ---- then: what did each exit rule keep?
    print(f"\n{'exit rule':<26}{'trades':>7}{'win%':>6}{'expectancy':>12}"
          f"{'totalR':>9}{'kept of peak':>14}")
    print("-" * 78)
    results = {}
    for name, pol in exits.POLICIES.items():
        tr = exits.simulate(s, entry(), pol, costs, warmup=300, allow_overlap=True)
        if not tr:
            continue
        rs = [t["r"] for t in tr]
        n = len(rs)
        wins = sum(1 for r in rs if r > 0)
        expc = sum(rs) / n
        # of the profit that was available (MFE), how much did we keep?
        avail = sum(max(t["mfe_r"], 0) for t in tr)
        kept = sum(rs)
        pct = 100 * kept / avail if avail > 0 else 0
        mark = "  <- ceiling" if "ORACLE" in name else ""
        print(f"{name:<26}{n:>7}{100*wins/n:>5.0f}%{expc:>+11.3f}R"
              f"{sum(rs):>+8.1f}{pct:>13.0f}%{mark}")
        results[name] = (expc, sum(rs), pct)

    real = {k: v for k, v in results.items() if "ORACLE" not in k}
    best = max(real.items(), key=lambda kv: kv[1][0])
    oracle = results.get("ORACLE (not tradeable)")
    print("-" * 78)
    print(f"\nBest tradeable exit : {best[0]}  ({best[1][0]:+.3f}R per trade)")
    if oracle:
        print(f"Perfect-peak exit   : {oracle[0]:+.3f}R per trade  "
              f"— requires knowing the future")
        gap = oracle[0] - best[1][0]
        print(f"The gap             : {gap:+.3f}R per trade is the unavoidable")
        print(f"                      cost of not knowing where the top is.")
    return results


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "GOLD",
        sys.argv[2] if len(sys.argv) > 2 else "1h")

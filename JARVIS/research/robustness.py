"""
Cross-market robustness scan.

The central anti-overfitting question: does an edge appear in ONE market
(likely an artifact of that market's history) or in MANY (more likely a
structural behaviour)?

A strategy that works on gold 2024-2026 and nowhere else is almost certainly
describing gold's bull run, not a repeatable edge. This scan makes that
visible in one table instead of hiding it behind a single headline number.

Run:  python3 JARVIS/research/robustness.py
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies, study

SYMBOLS = ["GOLD", "US500", "EURUSD", "GBPUSD"]


def scan(tf="1h", warmup=300):
    print("=" * 86)
    print(f"  CROSS-MARKET ROBUSTNESS SCAN — {tf}")
    print("  expectancy in R per trade, after spread + slippage + commission")
    print("=" * 86)
    hdr = f"{'strategy':<20}" + "".join(f"{s:>13}" for s in SYMBOLS) + f"{'  markets +ve':>14}"
    print(hdr); print("-" * 86)

    table = {}
    for name in strategies.REGISTRY:
        if name == "capped_target_trap":
            continue                      # deliberately broken control
        row, pos, tot = [], 0, 0
        for sym in SYMBOLS:
            try:
                s = engine.load(sym, tf)
            except Exception:
                row.append("     n/a"); continue
            c = study.COSTS.get(sym, engine.Costs())
            st = engine.stats(engine.backtest(s, strategies.REGISTRY[name](s),
                                              c, warmup=warmup))
            if st.get("n", 0) < 30:
                row.append(f"{'few':>13}"); continue
            e = st["expectancy_R"]
            tot += 1
            if e > 0:
                pos += 1
            row.append(f"{e:>+11.3f}R")
        table[name] = (pos, tot)
        print(f"{name:<20}" + "".join(row) + f"{pos:>8}/{tot}")

    print("-" * 86)
    print("\nREADING THIS TABLE")
    print("  4/4 or 3/4 positive : worth serious investigation")
    print("  2/4                 : coin flip; no evidence of a structural edge")
    print("  1/4                 : almost certainly an artifact of that market")
    print("  0/4                 : rejected\n")
    best = sorted(table.items(), key=lambda kv: -kv[1][0])
    print("RANKED BY CONSISTENCY")
    for n, (p, t) in best:
        verdict = ("investigate" if p >= 3 else
                   "no evidence" if p == 2 else
                   "likely artifact" if p == 1 else "rejected")
        print(f"  {n:<20} {p}/{t}  {verdict}")
    return table


if __name__ == "__main__":
    scan(sys.argv[1] if len(sys.argv) > 1 else "1h")

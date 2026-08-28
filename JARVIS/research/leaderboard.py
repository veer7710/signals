"""
Strategy leaderboard.

One command that runs every strategy in the registry through the full
pipeline — backtest, walk-forward, multiple-testing correction, prop-firm
Monte Carlo — and ranks them. This is the "research machine" entry point:
Claude decides what strategy to ADD to strategies.py; this script does the
thousands of deterministic runs for free.

Ranking is multi-objective, not "highest profit": a strategy must clear the
multiple-testing luck bar AND survive walk-forward AND pass prop rules at a
non-trivial rate before profit even matters, exactly as the directive
specifies (survival and significance are gates, not tiebreakers).

Run:  python3 JARVIS/research/leaderboard.py [markets...] [--tf 1h]
"""
from __future__ import annotations
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies, study, sensitivity, prop_sim

DEFAULT_MARKETS = ["GOLD", "US500", "EURUSD", "GBPUSD"]
EXCLUDE = {"capped_target_trap"}   # deliberately-broken control, not a candidate


def run(markets=None, tf="1h", prop_rules="generic_2step_phase1", warmup=300):
    markets = markets or DEFAULT_MARKETS
    names = [n for n in strategies.REGISTRY if n not in EXCLUDE]
    n_trials = len(names) * len(markets)          # the honest trial count
    luck_bar = sensitivity.luck_threshold(n_trials)

    print("=" * 92)
    print(f"  STRATEGY LEADERBOARD — {tf}, {len(markets)} markets, "
          f"{len(names)} strategies = {n_trials} trials")
    print(f"  luck threshold at N={n_trials}: t must exceed {luck_bar:.2f} to mean anything")
    print("=" * 92)

    rows = []
    for name in names:
        best_t, agg_R, agg_n, agg_wins = -99, 0.0, 0, 0
        per_market, all_trades_by_mkt = {}, {}
        for sym in markets:
            s = engine.load(sym, tf)
            c = study.COSTS.get(sym, engine.Costs())
            trades = engine.backtest(s, strategies.REGISTRY[name](s), c, warmup=warmup)
            st = engine.stats(trades)
            per_market[sym] = st
            all_trades_by_mkt[sym] = trades
            if st.get("n", 0) >= 20:
                best_t = max(best_t, st["t_stat"])
                agg_R += st["total_R"]; agg_n += st["n"]
                agg_wins += st["win_rate"] * st["n"]

        pos_markets = sum(1 for st in per_market.values()
                          if st.get("n", 0) >= 20 and st["expectancy_R"] > 0)
        tested_markets = sum(1 for st in per_market.values() if st.get("n", 0) >= 20)

        # walk-forward on the market with the most trades (cheap proxy, not
        # a full per-market walk-forward, to keep this runnable in seconds)
        best_mkt = max(per_market, key=lambda k: per_market[k].get("n", 0))
        s = engine.load(best_mkt, tf)
        wf = engine.walk_forward(s, lambda x, nm=name: strategies.REGISTRY[nm](x),
                                 study.COSTS.get(best_mkt, engine.Costs()),
                                 folds=6, warmup=warmup)
        wf_pos = sum(1 for _, _, w, _ in wf if w.get("n", 0) and w["expectancy_R"] > 0)
        wf_tot = len(wf)

        # prop-firm Monte Carlo on the best market's trades
        rules = prop_sim.PRESETS[prop_rules]
        mc = prop_sim.monte_carlo_prop(all_trades_by_mkt[best_mkt], rules, trials=1000)

        beats_luck = best_t > luck_bar
        wf_ok = wf_tot > 0 and wf_pos >= 0.6 * wf_tot
        prop_ok = mc.get("pass_rate", 0) >= 0.30

        gates_passed = sum([beats_luck, wf_ok, prop_ok, pos_markets >= 3])
        rows.append({
            "name": name, "best_t": best_t, "luck_bar": luck_bar,
            "beats_luck": beats_luck, "pos_markets": pos_markets,
            "tested_markets": tested_markets, "wf_pos": wf_pos, "wf_tot": wf_tot,
            "wf_ok": wf_ok, "prop_pass_rate": mc.get("pass_rate", 0),
            "prop_ok": prop_ok, "agg_R": agg_R, "agg_n": agg_n,
            "win_rate": (agg_wins / agg_n) if agg_n else 0,
            "gates_passed": gates_passed, "best_market": best_mkt,
        })

    rows.sort(key=lambda r: (-r["gates_passed"], -r["best_t"]))

    print(f"\n{'strategy':<18}{'gates':>7}{'best t':>9}{'mkts+ve':>9}"
          f"{'walk-fwd':>10}{'prop pass':>11}{'totalR':>9}")
    print("-" * 92)
    for r in rows:
        gate_str = f"{r['gates_passed']}/4"
        wf_str = f"{r['wf_pos']}/{r['wf_tot']}" if r['wf_tot'] else "n/a"
        print(f"{r['name']:<18}{gate_str:>7}{r['best_t']:>+9.2f}"
              f"{r['pos_markets']:>5}/{r['tested_markets']:<3}"
              f"{wf_str:>10}{100*r['prop_pass_rate']:>10.0f}%{r['agg_R']:>+9.1f}")
    print("-" * 92)
    print("\nGATES (a strategy needs ALL FOUR before profit numbers matter):")
    print("  1. best t-stat beats the multiple-testing luck threshold")
    print("  2. positive on 3+ of the tested markets")
    print("  3. walk-forward: 60%+ of folds positive")
    print("  4. prop-firm Monte Carlo: 30%+ simulated pass rate")

    passers = [r for r in rows if r["gates_passed"] == 4]
    print(f"\nStrategies clearing all 4 gates: {len(passers)}")
    if not passers:
        print("NONE. Per the directive's own rule (do not fake it, statistical")
        print("integrity first): no strategy in the current library is ready")
        print("for a prop-firm deployment. The leaderboard exists to make that")
        print("checkable in one command as new strategies are added.")

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "leaderboard.json"), "w") as f:
        json.dump(rows, f, indent=1, default=str)
    return rows


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run(args or None)

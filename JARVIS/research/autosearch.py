"""
Automated strategy search — thousands of backtests, zero AI cost.

This is the piece that lets research continue without spending usage. It runs
entirely as local Python: the model chooses the SEARCH SPACE once, this script
grinds through it, and only a short honest summary needs to be read back.

THE ANTI-FOOLING DESIGN
Searching a large space and reporting the winner is how people produce
beautiful, worthless backtests. Three defences are built in and cannot be
switched off:

  1. CHRONOLOGICAL SPLIT. Every configuration is scored on the FIRST 70% of
     history. The last 30% is never touched during the search.
  2. OUT-OF-SAMPLE CONFIRMATION. Only the top handful from the search are then
     run once on the held-out 30%. That number is the one that counts.
  3. MULTIPLE-TESTING CORRECTION. Trying N configurations means the best of
     them has an expected t-statistic of sqrt(2 ln N) even with no edge at all.
     The report states that bar and whether anything actually cleared it.

A configuration that looks wonderful in-sample and fails out-of-sample is the
NORMAL outcome, not a bug. Reporting that honestly is the point.

Run:  python3 JARVIS/research/autosearch.py [--fast] [--tf 1h]
"""
from __future__ import annotations
import itertools, json, math, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies as S, study, sensitivity

REPORTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports")
MARKETS = ["GOLD", "US500", "EURUSD", "GBPUSD"]
IS_FRAC = 0.70


def split(s: engine.Series):
    """Chronological in-sample / out-of-sample split."""
    k = int(len(s) * IS_FRAC)
    a = engine.Series(s.ts[:k], s.o[:k], s.h[:k], s.l[:k], s.c[:k])
    b = engine.Series(s.ts[k:], s.o[k:], s.h[k:], s.l[k:], s.c[k:])
    return a, b


def build(cfg, series):
    """Instantiate a strategy from a config dict, optionally gated."""
    kw = {k: v for k, v in cfg.items()
          if k not in ("name", "market", "gate", "adx", "sqz")}
    base = S.REGISTRY[cfg["name"]]
    try:
        inner = base(series, **kw)
    except TypeError:
        return None
    if not cfg.get("gate"):
        return inner
    adx_max, sqz_max = cfg["adx"], cfg["sqz"]

    def sig(ctx, i):
        a, m, ad = ctx["atr"][i], ctx["atr_med"][i], ctx["adx"][i]
        if a is None or m is None or m <= 0:
            return None
        if (a / m) > sqz_max or ad > adx_max:
            return None
        return inner(ctx, i)
    return sig


def score(series, cfg, costs, warmup=300):
    fn = build(cfg, series)
    if fn is None:
        return None
    st = engine.stats(engine.backtest(series, fn, costs, warmup=warmup))
    return st if st.get("n", 0) >= 30 else None


def space(fast=False):
    """The search space. Kept deliberately small per strategy: a bigger space
    does not find more edge, it only raises the bar that any winner must clear."""
    names = ["sweep_continuation", "donchian_trend", "ma_cross",
             "tsmom", "minimal_trend", "liquidity_sweep", "ema_pullback"]
    rrs = [1.5, 2.0, 3.0] if fast else [1.0, 1.5, 2.0, 3.0, 4.0]
    stops = [1.5, 2.5] if fast else [1.0, 1.5, 2.0, 2.5]
    gates = [(False, 99, 9.9), (True, 20, 1.00), (True, 25, 1.15), (True, 45, 1.60)]
    out = []
    for nm, rr, sa, (g, adx, sqz) in itertools.product(names, rrs, stops, gates):
        out.append({"name": nm, "rr": rr, "stop_atr": sa,
                    "gate": g, "adx": adx, "sqz": sqz})
    return out


def run(tf="1h", fast=False, top_n=8, budget_s=900):
    t0 = time.time()
    cfgs = space(fast)
    print("=" * 88)
    print(f"  AUTOMATED SEARCH — {tf}, {len(cfgs)} configs x {len(MARKETS)} markets "
          f"= {len(cfgs)*len(MARKETS)} tests")
    print(f"  Searching on the first {int(100*IS_FRAC)}% of history. "
          f"The last {int(100*(1-IS_FRAC))}% is held out and never touched.")
    print("=" * 88)

    data = {}
    for m in MARKETS:
        try:
            s = engine.load(m, tf)
        except Exception:
            continue
        if len(s) < 2000:
            continue
        data[m] = (split(s), study.COSTS.get(m, engine.Costs()))

    results, tested = [], 0
    for cfg in cfgs:
        if time.time() - t0 > budget_s:
            print(f"\n  [time budget reached after {tested} tests]")
            break
        per_market, ok = {}, 0
        for m, ((is_s, _oos), costs) in data.items():
            st = score(is_s, cfg, costs)
            tested += 1
            if st:
                per_market[m] = st
                if st["expectancy_R"] > 0:
                    ok += 1
        if len(per_market) >= 3:
            avg = sum(v["expectancy_R"] for v in per_market.values()) / len(per_market)
            avg_t = sum(v["t_stat"] for v in per_market.values()) / len(per_market)
            results.append({"cfg": cfg, "is_avg_exp": avg, "is_avg_t": avg_t,
                            "markets_pos": ok, "markets_tested": len(per_market)})

    if not results:
        print("\n  no configuration produced enough trades to evaluate.")
        return

    # rank by consistency first, then by expectancy — never by expectancy alone
    results.sort(key=lambda r: (-r["markets_pos"], -r["is_avg_exp"]))
    print(f"\n  {tested} in-sample tests completed in {time.time()-t0:.0f}s")
    print(f"\n  TOP {top_n} IN-SAMPLE (the seductive numbers)")
    print(f"  {'strategy':<20}{'rr':>5}{'stop':>6}{'gate':>12}{'mkts+':>7}{'avg exp':>10}{'avg t':>8}")
    print("  " + "-" * 84)
    for r in results[:top_n]:
        c = r["cfg"]
        g = f"adx{c['adx']}/{c['sqz']}" if c["gate"] else "none"
        print(f"  {c['name']:<20}{c['rr']:>5}{c['stop_atr']:>6}{g:>12}"
              f"{r['markets_pos']:>4}/{r['markets_tested']:<2}"
              f"{r['is_avg_exp']:>+10.3f}{r['is_avg_t']:>+8.2f}")

    # ---- OUT OF SAMPLE: the only numbers that mean anything
    print(f"\n  OUT-OF-SAMPLE — the held-out {int(100*(1-IS_FRAC))}%, "
          f"run ONCE on the top {top_n}")
    print(f"  {'strategy':<20}{'gate':>12}{'mkts+':>7}{'avg exp':>10}{'avg t':>8}{'  verdict'}")
    print("  " + "-" * 84)
    oos_rows = []
    for r in results[:top_n]:
        cfg = r["cfg"]
        per, ok = {}, 0
        for m, ((_is, oos), costs) in data.items():
            st = score(oos, cfg, costs, warmup=250)
            if st:
                per[m] = st
                if st["expectancy_R"] > 0:
                    ok += 1
        if not per:
            continue
        avg = sum(v["expectancy_R"] for v in per.values()) / len(per)
        avg_t = sum(v["t_stat"] for v in per.values()) / len(per)
        best_t = max(v["t_stat"] for v in per.values())
        c = cfg
        g = f"adx{c['adx']}/{c['sqz']}" if c["gate"] else "none"
        held = "HELD UP" if (avg > 0 and ok >= len(per) * 0.6) else "failed"
        print(f"  {c['name']:<20}{g:>12}{ok:>4}/{len(per):<2}"
              f"{avg:>+10.3f}{avg_t:>+8.2f}   {held}")
        oos_rows.append({"cfg": cfg, "oos_avg_exp": avg, "oos_avg_t": avg_t,
                         "oos_best_t": best_t, "oos_markets_pos": ok,
                         "oos_markets": len(per), "held": held == "HELD UP"})

    # ---- the honest verdict
    N = tested
    bar = sensitivity.luck_threshold(N)
    print("\n" + "=" * 88)
    print(f"  MULTIPLE-TESTING CORRECTION")
    print(f"  {N} configurations were tried. With no edge at all, the best of")
    print(f"  {N} would still show a t-statistic of about {bar:.2f} by luck alone.")
    survivors = [r for r in oos_rows if r["held"] and r["oos_best_t"] > bar]
    if survivors:
        print(f"\n  {len(survivors)} configuration(s) held up out-of-sample AND beat the luck bar:")
        for r in survivors:
            print(f"    {r['cfg']['name']}  oos t={r['oos_best_t']:+.2f}  "
                  f"exp={r['oos_avg_exp']:+.3f}R")
    else:
        held = [r for r in oos_rows if r["held"]]
        print(f"\n  NOTHING cleared the bar.")
        print(f"  {len(held)} of {len(oos_rows)} held up out-of-sample at all, and the best")
        best = max(oos_rows, key=lambda r: r["oos_best_t"]) if oos_rows else None
        if best:
            print(f"  t-statistic anywhere was {best['oos_best_t']:+.2f} "
                  f"({best['cfg']['name']}) against a bar of {bar:.2f}.")
        print("\n  This is the normal outcome of an honest search. It is reported")
        print("  rather than hidden because the alternative is trading a number")
        print("  that only ever existed in a backtest.")
    print("=" * 88)

    os.makedirs(REPORTS, exist_ok=True)
    out = os.path.normpath(os.path.join(REPORTS, f"autosearch_{tf}.json"))
    with open(out, "w") as f:
        json.dump({"tf": tf, "tests": N, "luck_bar": bar,
                   "in_sample_top": results[:top_n], "out_of_sample": oos_rows},
                  f, indent=1, default=str)
    print(f"\n  saved -> {out}")


if __name__ == "__main__":
    run(tf=("15m" if "--15m" in sys.argv else "1h"), fast="--fast" in sys.argv)

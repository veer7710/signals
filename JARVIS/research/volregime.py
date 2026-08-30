"""
Does trend-following work better in LOW volatility? (the LeBaron effect)

The highest-value idea from the strategy hunt: Kurth, Eisler, Rej & Bouchaud
(2026) partition futures trend PnL by volatility and find low-volatility
periods keep accruing PnL even after the post-2008 break that killed
short-term trend elsewhere. The proposed mechanism is that low volatility means
underreaction to news, and trend monetises underreaction.

WHY THIS IS NOT A REPEAT OF E-021
E-021 gated entries on ADX AND ATR/median together and the gate failed
out-of-sample. This asks a narrower and more honest question: taking EVERY
trade, does the RESULT differ by the volatility regime the trade opened in?
That is a partition of outcomes, not a fitted filter — so it cannot overfit in
the same way, and it is measured in-sample and out-of-sample separately.

If low-vol trades are systematically better in BOTH halves, the flat Donchian
result may be a diluted signal rather than no signal.

Run:  python3 JARVIS/research/volregime.py
"""
from __future__ import annotations
import os, statistics as stat, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies as S, study

MARKETS = ["GOLD", "US500", "EURUSD", "GBPUSD"]
IS_FRAC = 0.70


def regime_of(ctx, i, lo, hi):
    """Which volatility tercile did this bar sit in? Thresholds are passed in,
    computed from the IN-SAMPLE half only, so the out-of-sample test never sees
    a boundary derived from its own data."""
    a, m = ctx["atr"][i], ctx["atr_med"][i]
    if a is None or m is None or m <= 0:
        return None
    r = a / m
    return "low" if r <= lo else ("high" if r >= hi else "mid")


def collect(series, name, costs, lo, hi, warmup=300):
    """Run the strategy, then label each trade by the regime it OPENED in."""
    ctx = engine.build_context(series)
    fn = S.REGISTRY[name](series)
    trades = engine.backtest(series, fn, costs, warmup=warmup)
    ts_to_i = {t: i for i, t in enumerate(series.ts)}
    out = {"low": [], "mid": [], "high": []}
    for t in trades:
        i = ts_to_i.get(t.ts_in)
        if i is None:
            continue
        g = regime_of(ctx, i, lo, hi)
        if g:
            out[g].append(t.r)
    return out


def run(name="donchian_trend", tf="1h"):
    print("=" * 84)
    print(f"  VOLATILITY REGIME PARTITION — {name}, {tf}")
    print("  Every trade is taken. Trades are then SPLIT by the volatility")
    print("  regime they opened in. Thresholds come from the in-sample half only.")
    print("=" * 84)

    agg = {"IS": {"low": [], "mid": [], "high": []},
           "OOS": {"low": [], "mid": [], "high": []}}

    for m in MARKETS:
        try:
            s = engine.load(m, tf)
        except Exception:
            continue
        k = int(len(s) * IS_FRAC)
        is_s = engine.Series(s.ts[:k], s.o[:k], s.h[:k], s.l[:k], s.c[:k])
        oos = engine.Series(s.ts[k:], s.o[k:], s.h[k:], s.l[k:], s.c[k:])
        costs = study.COSTS.get(m, engine.Costs())

        # terciles of ATR/median, measured on the IN-SAMPLE half only
        ctx = engine.build_context(is_s)
        ratios = sorted(a / mm for a, mm in zip(ctx["atr"], ctx["atr_med"])
                        if a and mm and mm > 0)
        if len(ratios) < 100:
            continue
        lo = ratios[int(0.33 * len(ratios))]
        hi = ratios[int(0.67 * len(ratios))]

        for label, ser, wu in (("IS", is_s, 300), ("OOS", oos, 250)):
            got = collect(ser, name, costs, lo, hi, warmup=wu)
            for g in got:
                agg[label][g].extend(got[g])

    def line(label, g):
        v = agg[label][g]
        if len(v) < 30:
            return f"{'n<30':>26}"
        e = sum(v) / len(v)
        sd = stat.stdev(v) if len(v) > 1 else 0
        t = e / (sd / (len(v) ** 0.5)) if sd > 0 else 0
        w = sum(1 for x in v if x > 0) / len(v)
        return f"{len(v):>6}{100*w:>6.0f}%{e:>+9.3f}R{t:>+6.2f}"

    print(f"\n  {'regime':<8}{'':<2}" + f"{'IN-SAMPLE':^26}" + "  " + f"{'OUT-OF-SAMPLE':^26}")
    print(f"  {'':<10}" + f"{'n':>6}{'win':>6}{'exp':>10}{'t':>6}" + "  "
          + f"{'n':>6}{'win':>6}{'exp':>10}{'t':>6}")
    print("  " + "-" * 76)
    for g in ("low", "mid", "high"):
        print(f"  {g:<10}" + line("IS", g) + "  " + line("OOS", g))
    print("  " + "-" * 76)

    def expc(label, g):
        v = agg[label][g]
        return (sum(v) / len(v)) if len(v) >= 30 else None

    il, ih = expc("IS", "low"), expc("IS", "high")
    ol, oh = expc("OOS", "low"), expc("OOS", "high")
    print("\n  VERDICT")
    if None in (il, ih, ol, oh):
        print("  not enough trades in some regimes to judge.")
    elif il > ih and ol > oh:
        print(f"  LOW-VOL trades beat HIGH-VOL trades in BOTH halves")
        print(f"    in-sample     {il:+.3f}R  vs {ih:+.3f}R  (gap {il-ih:+.3f})")
        print(f"    out-of-sample {ol:+.3f}R  vs {oh:+.3f}R  (gap {ol-oh:+.3f})")
        print("  The LeBaron effect REPLICATES here. The flat headline result is")
        print("  a diluted signal: the low-vol subset carries it and the high-vol")
        print("  subset drags it down.")
    elif il > ih:
        print(f"  Low-vol beat high-vol in-sample ({il:+.3f} vs {ih:+.3f}) but NOT")
        print(f"  out-of-sample ({ol:+.3f} vs {oh:+.3f}). That is in-sample fitting,")
        print("  and it matches what E-021 already found about the gate.")
    else:
        print(f"  No low-vol advantage. in-sample {il:+.3f} vs {ih:+.3f}, "
              f"out-of-sample {ol:+.3f} vs {oh:+.3f}.")
        print("  The LeBaron effect does NOT appear in this data. Close the idea.")
    return agg


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "donchian_trend",
        sys.argv[2] if len(sys.argv) > 2 else "1h")

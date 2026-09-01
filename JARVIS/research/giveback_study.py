"""
E-051 — Does protecting profit actually PAY, or does it only FEEL better?

Veer's complaint is about a lived experience: a basket reaches GBP12 and
closes at breakeven, a trade reaches GBP10 and closes for far less. The exit
study measured that a give-back rule does stop that happening. This script
asks the two questions the expectancy column alone cannot answer:

  1. What does the give-back rule cost in expectancy, and where does the cost
     come from? (Answer expected: the enormous runners.)
  2. What does it BUY in drawdown and survival? A small live account does not
     experience expectancy, it experiences the equity curve.

It also tests the obvious compromise, which no single all-or-nothing exit rule
can express: bank HALF at the give-back trigger and let the other half run on
the wide trail. Because the partial does not change how the remainder is
managed, that blend is exactly the average of the two policies' per-trade
results, trade by trade — so it can be computed from paired runs rather than
guessed at.

Run:  python3 JARVIS/research/giveback_study.py [SYMBOL] [TF]
"""
from __future__ import annotations
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies, exits, study


ENTRY = "donchian_trend"     # overridden from the command line


def _entry(s):
    """The entry set the exits are compared ON. This used to be hardcoded to
    donchian_trend, which meant E-051's headline - 'the give-back rule beat
    the 3xATR trail on 5 of 5 markets' - was measured on entries the EA does
    not take. The comparison between exits was still fair, but it was never a
    statement about SuperTrendSniper. Caught by the EA audit, 2026-09-01."""
    return getattr(strategies, ENTRY)(s)


def paired(s, costs, names):
    """Run each policy over identical entries and index the results by the
    bar the trade opened on, so trade i of one policy can be compared with
    trade i of another rather than with an average."""
    out = {}
    for n in names:
        tr = exits.simulate(s, _entry(s), exits.POLICIES[n],
                            costs, warmup=300, allow_overlap=True)
        d = {}
        for t in tr:
            d.setdefault(t["i_in"], t)
        out[n] = d
    return out


def curve_stats(rs, risk_pct, trials=5000, seed=7):
    """Sequential drawdown on the real order, plus a bootstrap of the order."""
    eq, peak, mdd = 1.0, 1.0, 0.0
    for r in rs:
        eq += eq * risk_pct * r
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak)
    rng = random.Random(seed)
    dds, ends = [], []
    for _ in range(trials):
        e, p, m = 1.0, 1.0, 0.0
        for _ in range(len(rs)):
            e += e * risk_pct * rs[rng.randrange(len(rs))]
            p = max(p, e)
            m = max(m, (p - e) / p)
        dds.append(m); ends.append(e)
    dds.sort(); ends.sort()
    q = lambda a, f: a[int(f * (len(a) - 1))]
    return {"end": eq, "mdd": mdd, "dd50": q(dds, .5), "dd95": q(dds, .95),
            "p_dd30": sum(1 for d in dds if d >= .30) / trials,
            "p_loss": sum(1 for e in ends if e < 1.0) / trials}


def run(symbol="GOLD", tf="1h", risk_pct=0.02):
    s = engine.load(symbol, tf)
    costs = study.COSTS.get(symbol, engine.Costs())
    A = "fixed 3R"                  # best price-anchored rule on GOLD 1h
    B = "giveback 30% arm@1R"       # best profit-anchored rule
    C = "trail 3xATR"               # the rule currently shipped in the EA
    D = "time 20 bars"
    P = paired(s, costs, [A, B, C, D])

    keys = sorted(set(P[A]) & set(P[B]) & set(P[C]) & set(P[D]))
    print("=" * 78)
    print(f"  E-051  PROFIT PROTECTION — {symbol} {tf}   {len(keys)} paired trades")
    print(f"  risk per trade {100*risk_pct:.1f}% of equity (a small live account)")
    print("=" * 78)

    rows = {n: [P[n][k]["r"] for k in keys] for n in (A, B, C, D)}
    # the 50/50 blend: half banked by the give-back rule, half left on the trail
    rows["HALF gb + HALF trail"] = [0.5 * P[B][k]["r"] + 0.5 * P[C][k]["r"]
                                    for k in keys]
    rows["HALF gb + HALF 3R"]    = [0.5 * P[B][k]["r"] + 0.5 * P[A][k]["r"]
                                    for k in keys]

    print(f"\n{'rule':<24}{'exp':>9}{'win%':>6}{'worst':>8}{'best':>8}"
          f"{'real DD':>9}{'DD95':>7}{'P(DD>30%)':>11}{'P(lose)':>9}")
    print("-" * 78)
    for n, rs in rows.items():
        cs = curve_stats(rs, risk_pct)
        w = 100 * sum(1 for r in rs if r > 0) / len(rs)
        print(f"{n:<24}{sum(rs)/len(rs):>+8.3f}R{w:>5.0f}%{min(rs):>+8.2f}"
              f"{max(rs):>+8.2f}{100*cs['mdd']:>8.0f}%{100*cs['dd95']:>6.0f}%"
              f"{100*cs['p_dd30']:>10.0f}%{100*cs['p_loss']:>8.0f}%")

    # ---- WHERE does the give-back rule lose its money?
    print("\nWHERE THE GIVE-BACK RULE LOSES ITS MONEY")
    print("  Trades split by how good they ever got (MFE), and what each rule")
    print("  made on that bucket. If the cost is concentrated in the big-MFE")
    print("  bucket, the rule is not broken - it is selling the runners.")
    buckets = [(0, 1), (1, 3), (3, 6), (6, 1e9)]
    print(f"\n  {'MFE bucket':<14}{'n':>5}{A:>12}{B:>22}{'difference':>13}")
    for lo, hi in buckets:
        ks = [k for k in keys if lo <= P[A][k]["mfe_r"] < hi]
        if not ks:
            continue
        a = sum(P[A][k]["r"] for k in ks) / len(ks)
        b = sum(P[B][k]["r"] for k in ks) / len(ks)
        lab = f"{lo}-{hi}R" if hi < 1e9 else f"{lo}R+"
        print(f"  {lab:<14}{len(ks):>5}{a:>+11.3f}R{b:>+21.3f}R{b-a:>+12.3f}R")

    # ---- how often does each rule deliver Veer's actual complaint?
    print("\nHOW OFTEN DOES THE COMPLAINT HAPPEN?")
    print("  'went at least 1R into profit and still closed at or below zero'")
    for n in (A, B, C, D):
        bad = [k for k in keys if P[n][k]["mfe_r"] >= 1.0 and P[n][k]["r"] <= 0]
        got = [k for k in keys if P[n][k]["mfe_r"] >= 1.0]
        print(f"  {n:<24}{len(bad):>4} of {len(got):<4} "
              f"({100*len(bad)/max(len(got),1):>3.0f}% of trades that got 1R green)")
    return rows


if __name__ == "__main__":
    if len(sys.argv) > 4:
        ENTRY = sys.argv[4]
    run(sys.argv[1] if len(sys.argv) > 1 else "GOLD",
        sys.argv[2] if len(sys.argv) > 2 else "1h",
        float(sys.argv[3]) if len(sys.argv) > 3 else 0.02)

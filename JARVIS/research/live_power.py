"""
HOW MANY LIVE TRADES SETTLE IT — statistical power for the setup scoreboard.

THE QUESTION
  The liquidity Pine files every completed trade under its setup type and shows
  a scoreboard of 8 types (BREAK, BOUNCE, RETEST, PULLBACK, BREAKOUT, GAP FILL,
  INVERSE GAP, ORDER BLOCK). MISSION.md calls "which setup types Veer personally
  converts" the only live question with a real chance of a positive answer.
  Nobody has computed what it takes to answer it. This file does:

    (1) how many LIVE trades PER SETUP TYPE are needed to distinguish a real
        per-setup expectancy from zero, at three evidential thresholds;
    (2) how many are needed to RANK two setup types against each other;
    (3) how many are needed only to DETECT A CATASTROPHIC type (much fewer);
    (4) what that is in CALENDAR WEEKS at the signal rate now in force
        (liquidity Pine: hard cap 12 signals/day, 8-bar entry cooldown,
        max 2 concurrent setups);
    (5) a sequential abandon-early rule whose error rates are SIMULATED here,
        not quoted from a textbook.

  This is a design/statistics task. It authorises nothing. D-006 stands: no
  live action without Veer confirming that specific action in that session.

THE NUISANCE PARAMETER — sd of per-trade R — AND WHERE IT COMES FROM
  Required sample size scales with sd_R SQUARED, so this is the number that
  decides everything. Two independent estimates are computed and both reported:

  A. BACKTEST (this repo, correct per-symbol costs from study.COSTS, next-bar
     fills, first touch, ties lose): the six setup builders in smc_setups.py on
     GOLD 15m and GOLD 1h — E-040 says GOLD is the only instrument with real
     room — plus supertrend_sniper, the live product's own entry.
  B. LIVE (LIVE_EVIDENCE.md, XAUUSD 3m, 12 SuperTrend trades). Only summary
     statistics exist, so the trade-by-trade R list is RECONSTRUCTED from them:
     12 trades, 33% win => 4 winners / 8 losers, 8 stop-outs at -1R, total
     -6.9R => the 4 winners share +1.1R. Splitting that equally is the
     MINIMUM-VARIANCE reconstruction, so the live sd it yields is a LOWER
     BOUND on the true live sd, and every n computed from it is a LOWER BOUND
     on the true required n. Its 95% bootstrap interval is computed, not
     assumed, because 12 observations estimate a standard deviation badly.

Run:  python3 JARVIS/research/live_power.py
      (run python3 JARVIS/research/test_engine.py first — if it fails, stop)
"""
from __future__ import annotations
import os, sys, math, random, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
import study
import strategies
import smc_setups

SEED = 11
TRIALS = 20000
Z_POWER80 = None            # computed below from the normal quantile function
N_SETUP_TYPES = 8           # the scoreboard scores 8 types in parallel


# ------------------------------------------------------------------ normal
def ncdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def nquant(p):
    """Inverse normal CDF by bisection — computed, not table-quoted."""
    lo, hi = -12.0, 12.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if ncdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


Z_POWER80 = nquant(0.80)            # 0.8416
T_UNCORRECTED = 2.00                # two-sided ~0.046
T_BONFERRONI = nquant(1.0 - 0.05 / (2.0 * N_SETUP_TYPES))   # 8 parallel tests
T_PROJECT = 3.65                    # E-012: ~780 configurations tested here


def mean(xs):
    return sum(xs) / len(xs)


def sd(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def tstat(xs):
    s = sd(xs)
    return (mean(xs) / (s / math.sqrt(len(xs)))) if s > 0 else 0.0


# --------------------------------------------------------- populations
def live_r_list():
    """Reconstructed from LIVE_EVIDENCE.md summary stats. See docstring."""
    losers = [-1.0] * 8
    winners = [1.1 / 4.0] * 4
    return losers + winners


def backtest_populations():
    """Per-setup R populations, measured with the repo's standard rules.
    Chronological 70/30 split reported separately as a stability check on the
    nuisance parameter; the pooled list is what the power work uses, because
    sd_R is a nuisance parameter and not an edge claim."""
    out = {}
    for sym, tf in (("GOLD", "15m"), ("GOLD", "1h")):
        s = engine.load(sym, tf)
        c = smc_setups.costs_for(sym)
        ins, oos = smc_setups.split(s)
        Ai, Ao, Af = engine.atr(ins, 14), engine.atr(oos, 14), engine.atr(s, 14)
        for name, build in smc_setups.BUILDERS.items():
            ti = engine.backtest(ins, build(ins, Ai), c, warmup=250, max_bars=50)
            to = engine.backtest(oos, build(oos, Ao), c, warmup=250, max_bars=50)
            tf_all = engine.backtest(s, build(s, Af), c, warmup=250, max_bars=50)
            out[f"{name} [{sym} {tf}]"] = {
                "r": [t.r for t in tf_all],
                "is_sd": sd([t.r for t in ti]) if len(ti) > 1 else 0.0,
                "oos_sd": sd([t.r for t in to]) if len(to) > 1 else 0.0,
                "is_n": len(ti), "oos_n": len(to),
                "sym": sym, "tf": tf, "setup": name,
            }
        st = engine.backtest(s, strategies.supertrend_sniper(s), c,
                             warmup=300, max_bars=200)
        sti = engine.backtest(ins, strategies.supertrend_sniper(ins), c,
                              warmup=300, max_bars=200)
        sto = engine.backtest(oos, strategies.supertrend_sniper(oos), c,
                              warmup=300, max_bars=200)
        out[f"SUPERTREND SNIPER [{sym} {tf}]"] = {
            "r": [t.r for t in st],
            "is_sd": sd([t.r for t in sti]), "oos_sd": sd([t.r for t in sto]),
            "is_n": len(sti), "oos_n": len(sto),
            "sym": sym, "tf": tf, "setup": "SUPERTREND SNIPER",
        }
    return out


def signal_rates():
    """Raw signals per session day per setup, GOLD 15m and 1h, no occupancy
    constraint (the Pine's cap acts on SIGNALS, not on filled trades)."""
    rows = []
    for sym, tf in (("GOLD", "15m"), ("GOLD", "1h")):
        s = engine.load(sym, tf)
        A = engine.atr(s, 14)
        days = len({datetime.datetime.fromtimestamp(t, datetime.timezone.utc).date()
                    for t in s.ts})
        ctx = engine.build_context(s)
        for name, build in smc_setups.BUILDERS.items():
            fn = build(s, A)
            n_raw = sum(1 for i in range(250, len(s) - 1) if fn(ctx, i))
            rows.append((sym, tf, name, days, n_raw, n_raw / days))
    return rows


# ------------------------------------------------------------- power maths
def n_analytic(sigma, delta, tcrit, power=0.80):
    zb = nquant(power)
    return math.ceil(((tcrit + zb) * sigma / abs(delta)) ** 2)


def n_analytic_two_sample(sigma, delta, tcrit, power=0.80):
    return math.ceil(2.0 * ((tcrit + nquant(power)) * sigma / abs(delta)) ** 2)


def shifted(pop, delta):
    m = mean(pop)
    return [x - m + delta for x in pop]


def _auto_trials(n, cap=TRIALS):
    """Simulation is O(n x trials) in pure Python. Hold the work per power
    estimate roughly constant; 600 trials still gives a standard error of about
    0.016 on a power near 0.80, which is finer than the grid being searched."""
    return max(600, min(cap, 1_500_000 // max(n, 1)))


def _t_of_sample(smp, n):
    s1 = 0.0
    s2 = 0.0
    for x in smp:
        s1 += x
        s2 += x * x
    var = (s2 - s1 * s1 / n) / (n - 1)
    if var <= 0:
        return 0.0
    return (s1 / n) / math.sqrt(var / n)


def sim_power(pop, n, tcrit, trials=None, seed=SEED, side=+1):
    """Empirical rejection rate: bootstrap n trades from pop, one-sided test."""
    trials = trials or _auto_trials(n)
    rng = random.Random(seed)
    pick = rng.choices
    hits = 0
    for _ in range(trials):
        t = _t_of_sample(pick(pop, k=n), n)
        if (t >= tcrit) if side > 0 else (t <= -tcrit):
            hits += 1
    return hits / trials


def sim_power_two_sample(pop_a, pop_b, n, tcrit, trials=None, seed=SEED):
    trials = trials or _auto_trials(n)
    rng = random.Random(seed)
    pick = rng.choices
    hits = 0
    for _ in range(trials):
        a = pick(pop_a, k=n)
        b = pick(pop_b, k=n)
        sa1 = sa2 = sb1 = sb2 = 0.0
        for x in a:
            sa1 += x
            sa2 += x * x
        for x in b:
            sb1 += x
            sb2 += x * x
        va = (sa2 - sa1 * sa1 / n) / (n - 1) / n
        vb = (sb2 - sb1 * sb1 / n) / (n - 1) / n
        if va + vb <= 0:
            continue
        if (sa1 / n - sb1 / n) / math.sqrt(va + vb) >= tcrit:
            hits += 1
    return hits / trials


def n_simulated(pop, delta, tcrit, power=0.80, seed=SEED,
                two_sample=False, side=+1, n_ref=None):
    """Smallest n on a multiplicative grid around the analytic n whose
    EMPIRICAL power (bootstrapped from the measured, skewed R distribution)
    reaches the target. Returns (n, power_at_that_n)."""
    p = shifted(pop, delta)
    q = shifted(pop, 0.0)

    def pw(n):
        if two_sample:
            return sim_power_two_sample(p, q, n, tcrit, seed=seed)
        return sim_power(p, n, tcrit, seed=seed, side=side)

    grid = sorted({max(5, int(round(n_ref * m)))
                   for m in (0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.25, 1.5, 1.8)})
    best = None
    for n in grid:
        pwr = pw(n)
        if pwr >= power:
            best = (n, pwr)
            break
    if best is None:
        best = (None, pw(grid[-1]))
    return best


# ---------------------------------------------------------- sequential rule
def sprt_path(rs, sigma, mu0=0.0, mu1=-0.5, alpha=0.05, beta=0.20,
              n_min=15, n_max=400):
    """One-sided Wald SPRT on per-trade R: H0 'this setup is not bad'(mu=mu0)
    vs H1 'this setup is catastrophic'(mu=mu1). Returns (decision, n_used):
    decision 'ABANDON' | 'CLEAR' | 'CONTINUE'. n_min blocks the 12-trade error."""
    A = math.log((1.0 - beta) / alpha)          # upper: evidence for H1
    B = math.log(beta / (1.0 - alpha))          # lower: evidence for H0
    llr = 0.0
    for i, x in enumerate(rs, start=1):
        llr += (mu1 - mu0) * (x - 0.5 * (mu1 + mu0)) / (sigma ** 2)
        if i < n_min:
            continue
        if llr >= A:
            return "ABANDON", i
        if llr <= B:
            return "CLEAR", i
        if i >= n_max:
            return "CONTINUE", i
    return "CONTINUE", len(rs)


def sim_sprt(pop, true_mu, sigma, trials=TRIALS, seed=SEED, n_max=400, **kw):
    rng = random.Random(seed)
    p = shifted(pop, true_mu)
    k = len(p)
    counts = {"ABANDON": 0, "CLEAR": 0, "CONTINUE": 0}
    ns = []
    for _ in range(trials):
        rs = [p[rng.randrange(k)] for _ in range(n_max)]
        d, n = sprt_path(rs, sigma, n_max=n_max, **kw)
        counts[d] += 1
        ns.append(n)
    ns.sort()
    return counts, ns[len(ns) // 2]


def sim_naive_peeking(pop, true_mu, tcrit, n_max=400, n_min=15,
                      trials=TRIALS, seed=SEED):
    """What happens with NO boundary: look after every trade, stop when the
    running t crosses +/-tcrit. This is what a scoreboard invites."""
    rng = random.Random(seed)
    p = shifted(pop, true_mu)
    pick = rng.choices
    hit_pos = hit_neg = 0
    for _ in range(trials):
        s1 = s2 = 0.0
        pos = neg = False
        for i, x in enumerate(pick(p, k=n_max), start=1):
            s1 += x
            s2 += x * x
            if i < n_min:
                continue
            var = (s2 - s1 * s1 / i) / (i - 1)
            if var <= 0:
                continue
            t = (s1 / i) / math.sqrt(var / i)
            if t >= tcrit:
                pos = True
                break
            if t <= -tcrit:
                neg = True
                break
        hit_pos += pos
        hit_neg += neg
    return hit_pos / trials, hit_neg / trials


# ----------------------------------------------------------------- self test
def self_test(sigma):
    print("=" * 78)
    print("  SELF-TEST — the power machinery must be right before any n is")
    print("  reported. Exits non-zero on failure.")
    print("=" * 78)
    ok = True
    rng = random.Random(SEED)
    gauss = [rng.gauss(0.0, sigma) for _ in range(4000)]

    # (a) POSITIVE CONTROL
    for tcrit, label in ((T_UNCORRECTED, "t=2.00"), (T_PROJECT, "t=3.65")):
        n = n_analytic(sigma, 0.25, tcrit)
        pw = sim_power(shifted(gauss, 0.25), n, tcrit, trials=4000)
        good = 0.75 <= pw <= 0.86
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  positive control {label}: "
              f"true +0.25R, sd {sigma:.3f}, analytic n {n} -> "
              f"empirical power {pw:.3f} (target 0.80)")

    # (b) NEGATIVE CONTROL + family-wise error
    n = n_analytic(sigma, 0.25, T_UNCORRECTED)
    null = shifted(gauss, 0.0)
    a_unc = sim_power(null, n, T_UNCORRECTED, trials=10000)
    a_bon = sim_power(null, n, T_BONFERRONI, trials=10000)
    nominal_unc = 1.0 - ncdf(T_UNCORRECTED)
    good = abs(a_unc - nominal_unc) < 0.006
    ok &= good
    print(f"  {'PASS' if good else 'FAIL'}  negative control: true 0.00R, "
          f"per-test alpha at t=2.00 {a_unc:.4f} vs nominal {nominal_unc:.4f}")
    fwer_unc = 1.0 - (1.0 - a_unc) ** N_SETUP_TYPES
    fwer_bon = 1.0 - (1.0 - a_bon) ** N_SETUP_TYPES
    good = fwer_bon <= 0.055
    ok &= good
    print(f"  {'PASS' if good else 'FAIL'}  family-wise over {N_SETUP_TYPES} "
          f"setup types: uncorrected FWER {fwer_unc:.3f}, "
          f"Bonferroni (t={T_BONFERRONI:.2f}) FWER {fwer_bon:.3f}")

    # (c) SEQUENTIAL CONTROL
    counts, med = sim_sprt(gauss, 0.0, sigma, trials=4000)
    fp = counts["ABANDON"] / 4000.0
    good = fp <= 0.06
    ok &= good
    print(f"  {'PASS' if good else 'FAIL'}  sequential control: SPRT designed "
          f"for alpha 0.05, realised false-ABANDON rate under a true 0.00R "
          f"{fp:.4f}")

    if not ok:
        print("\n  SELF-TEST FAILED — every number below would be wrong.")
        sys.exit(1)
    print("  ALL SELF-TESTS PASSED\n")


# --------------------------------------------------------------------- main
def main():
    print(__doc__)

    # ---------------- 1. the nuisance parameter
    print("=" * 78)
    print("  1. sd OF PER-TRADE R — measured, not assumed")
    print("=" * 78)
    pops = backtest_populations()
    print(f"  {'population':<34}{'n':>6}{'exp R':>9}{'sd R':>8}"
          f"{'IS sd':>8}{'OOS sd':>8}")
    for k, v in pops.items():
        rs = v["r"]
        print(f"  {k:<34}{len(rs):>6}{mean(rs):>+9.3f}{sd(rs):>8.3f}"
              f"{v['is_sd']:>8.3f}{v['oos_sd']:>8.3f}")
    bt_sds = [sd(v["r"]) for v in pops.values() if len(v["r"]) > 30]
    bt_sds.sort()
    sd_bt = bt_sds[len(bt_sds) // 2]

    live = live_r_list()
    sd_live = sd(live)
    rng = random.Random(SEED)
    boots = sorted(sd([live[rng.randrange(12)] for _ in range(12)])
                   for _ in range(TRIALS))
    lo95, hi95 = boots[int(0.025 * TRIALS)], boots[int(0.975 * TRIALS)]
    print(f"\n  LIVE (reconstructed, XAUUSD 3m, n=12): exp {mean(live):+.3f}R, "
          f"sd {sd_live:.3f}")
    print(f"  95% bootstrap interval on that sd from 12 observations: "
          f"[{lo95:.3f}, {hi95:.3f}]  <-- this is how little 12 trades say")
    print(f"  MEDIAN BACKTEST sd_R across {len(bt_sds)} populations: {sd_bt:.3f}")
    print("\n  The two disagree by ~2.7x, and the ratio SQUARES in the sample")
    print("  size. Both are carried forward: the live sd is the OPTIMISTIC")
    print("  bound (minimum-variance reconstruction, and a 1R-ish payoff), the")
    print("  backtest sd is the shape the liquidity Pine's own R:R produces.")

    self_test(sd_bt)

    # ---------------- 2. power grid, one setup type vs zero
    print("=" * 78)
    print("  2. TRADES PER SETUP TYPE to detect expectancy > 0 at 80% power")
    print("     (one-sided; analytic n, then the SIMULATED n from bootstrapping")
    print("      the measured, skewed R distribution)")
    print("=" * 78)
    pooled = []
    for v in pops.values():
        pooled.extend(v["r"])
    grid = []
    for label, sigma, pop in (("live sd %.2f" % sd_live, sd_live, live),
                              ("backtest sd %.2f" % sd_bt, sd_bt, pooled)):
        print(f"\n  --- {label} ---")
        print(f"  {'true edge':<12}{'t=2.00':>18}{'t=%.2f (Bonf 8)' % T_BONFERRONI:>20}"
              f"{'t=3.65 (project)':>20}")
        for delta in (0.10, 0.25, 0.50):
            cells = []
            for tcrit in (T_UNCORRECTED, T_BONFERRONI, T_PROJECT):
                na = n_analytic(sigma, delta, tcrit)
                ns, pwr = n_simulated(pop, delta, tcrit, n_ref=na)
                cells.append((na, ns))
                grid.append((label, delta, tcrit, na, ns))
            print(f"  +{delta:.2f}R{'':<6}" +
                  "".join(f"{('%d / %s' % (a, b if b else 'n/a')):>18}"
                          if i == 0 else
                          f"{('%d / %s' % (a, b if b else 'n/a')):>20}"
                          for i, (a, b) in enumerate(cells)))
        print("   (each cell: analytic n / simulated n — where they differ the")
        print("    SIMULATED one is the answer)")

    # verify one grid cell at full trial count
    n_chk = n_analytic(sd_bt, 0.25, T_PROJECT)
    pw_chk = sim_power(shifted(pooled, 0.25), n_chk, T_PROJECT, trials=4000)
    print(f"\n  full-precision check: backtest sd, +0.25R, t=3.65, n={n_chk} "
          f"-> empirical power {pw_chk:.3f} over 4000 bootstraps")

    # ---------------- 3. ranking two setup types
    print("\n" + "=" * 78)
    print("  3. TRADES PER SETUP TYPE to RANK two types (difference in")
    print("     expectancy, two-sample, 80% power)")
    print("=" * 78)
    print(f"  {'gap between types':<20}{'t=2.00':>16}{'t=3.65':>16}")
    for delta in (0.10, 0.25, 0.50):
        row = []
        for tcrit in (T_UNCORRECTED, T_PROJECT):
            na = n_analytic_two_sample(sd_bt, delta, tcrit)
            ns, _ = n_simulated(pooled, delta, tcrit, two_sample=True,
                                n_ref=na)
            row.append(f"{na} / {ns if ns else 'n/a'}")
        print(f"  {delta:+.2f}R{'':<14}{row[0]:>16}{row[1]:>16}")
    print("   (analytic / simulated, PER TYPE — a ranking needs this many in")
    print("    EACH of the two types being compared)")

    # ---------------- 4. catastrophe detection
    print("\n" + "=" * 78)
    print("  4. TRADES to DETECT A CATASTROPHIC setup type (one-sided, the")
    print("     cheap question: is this thing losing badly?)")
    print("=" * 78)
    print(f"  {'true edge':<12}{'t=2.00':>16}{'t=1.645 (a=.05)':>18}"
          f"{'t=2.50 (Bonf 8)':>18}")
    t165 = nquant(0.95)
    t_bon_1s = nquant(1.0 - 0.05 / N_SETUP_TYPES)
    for delta in (-0.25, -0.58, -1.00):
        row = []
        for tcrit in (T_UNCORRECTED, t165, t_bon_1s):
            na = n_analytic(sd_bt, delta, tcrit)
            # detection of a NEGATIVE mean: one-sided test on the lower tail
            ns, _ = n_simulated(pooled, delta, tcrit, side=-1, n_ref=na)
            row.append(f"{na} / {ns if ns else 'n/a'}")
        print(f"  {delta:+.2f}R{'':<6}{row[0]:>16}{row[1]:>18}{row[2]:>18}")
    print("   (analytic / simulated, using the backtest sd)")
    for delta in (-0.58, -1.00):
        na = n_analytic(sd_live, delta, t165)
        print(f"   same at the LIVE sd {sd_live:.2f}: {delta:+.2f}R needs "
              f"n = {na} at t=1.645")

    # ---------------- 5. calendar time
    print("\n" + "=" * 78)
    print("  5. CALENDAR TIME at the signal rate now in force")
    print("=" * 78)
    rates = signal_rates()
    print(f"  measured RAW signals per session day (GOLD, repo data):")
    print(f"  {'setup':<20}{'tf':>5}{'days':>7}{'signals':>9}{'per day':>9}")
    tot15 = tot1h = 0.0
    for sym, tf, name, days, n_raw, per in rates:
        print(f"  {name:<20}{tf:>5}{days:>7}{n_raw:>9}{per:>9.2f}")
        if tf == "15m":
            tot15 += per
        else:
            tot1h += per
    print(f"  {'ALL SIX COMBINED':<20}{'15m':>5}{'':>7}{'':>9}{tot15:>9.2f}")
    print(f"  {'ALL SIX COMBINED':<20}{'1h':>5}{'':>7}{'':>9}{tot1h:>9.2f}")
    print("\n  The live product runs on 3m with a HARD CAP of 12 signals/day,")
    print("  an 8-bar cooldown and max 2 concurrent setups, across 8 types.")
    print("  Trades TAKEN is what the scoreboard records, and that is <= signals.")

    scenarios = [
        ("cap saturated, EA takes all 12/day, split evenly over 8 types", 12.0 / 8),
        ("8 signals/day taken, evenly over 8 types", 8.0 / 8),
        ("4 trades/day taken (Veer manual, realistic)", 4.0 / 8),
        ("2 trades/day taken", 2.0 / 8),
        ("1 trade/day taken", 1.0 / 8),
    ]
    key_ns = [
        ("A", "catastrophe -0.58R, t=1.645, backtest sd",
         n_analytic(sd_bt, -0.58, t165)),
        ("B", "edge +0.25R, t=2.00, LIVE sd (optimistic bound)",
         n_analytic(sd_live, 0.25, T_UNCORRECTED)),
        ("C", "edge +0.25R, t=2.00, backtest sd",
         n_analytic(sd_bt, 0.25, T_UNCORRECTED)),
        ("D", "edge +0.25R, t=3.65 project bar, backtest sd",
         n_analytic(sd_bt, 0.25, T_PROJECT)),
        ("E", "RANK two types 0.25R apart, t=2.00, backtest sd",
         n_analytic_two_sample(sd_bt, 0.25, T_UNCORRECTED)),
    ]
    print(f"\n  {'weeks to reach n, per setup type':<58}" +
          "".join(f"{k:>10}" for k, _, _ in key_ns))
    for lbl, per_type_day in scenarios:
        cells = []
        for _, _, n in key_ns:
            weeks = n / (per_type_day * 5.0)
            cells.append(f"{weeks:.0f}w" if weeks < 1000 else ">1000w")
        print(f"  {lbl:<58}" + "".join(f"{c:>10}" for c in cells))
    print("\n  columns:")
    for k, lbl, n in key_ns:
        print(f"    {k}  {lbl}: n = {n} per type")
    print("  weeks = n / (trades per type per day x 5 trading days)")

    today = datetime.date(2026, 8, 31)
    print("\n  THE DATE, at the realistic 4 trades/day taken across 8 types")
    print("  (0.5 per type per day), counting from 2026-08-31:")
    for k, lbl, n in key_ns:
        wk = n / (0.5 * 5.0)
        d = today + datetime.timedelta(weeks=wk)
        print(f"    {k}  n={n:<6} {wk:>6.0f} weeks -> {d.isoformat()}   {lbl}")

    # ---------------- 6. sequential rule
    print("\n" + "=" * 78)
    print("  6. SEQUENTIAL ABANDON RULE — error rates SIMULATED, not quoted")
    print("=" * 78)
    print("  Rule: one-sided Wald SPRT on per-trade R, H0 mu=0 vs H1 mu=-0.5R,")
    print("  designed alpha 0.05 / beta 0.20, no decision before 15 trades,")
    print(f"  sd fixed at the backtest estimate {sd_bt:.3f}.")
    print(f"  {'true expectancy':<20}{'ABANDON':>10}{'CLEAR':>10}"
          f"{'CONTINUE':>10}{'median n':>10}")
    for mu in (0.00, -0.25, -0.50, -0.75, +0.25):
        counts, med = sim_sprt(pooled, mu, sd_bt, trials=4000)
        print(f"  {mu:+.2f}R{'':<14}{counts['ABANDON']/4000:>10.3f}"
              f"{counts['CLEAR']/4000:>10.3f}{counts['CONTINUE']/4000:>10.3f}"
              f"{med:>10}")
    print("\n  What happens with NO boundary — looking at the running t after")
    print("  every trade and stopping when |t| crosses 2.0, under a TRUE")
    print("  expectancy of exactly zero (400 trades max, 8 setup types):")
    pp, pn = sim_naive_peeking(pooled, 0.0, 2.0, trials=4000)
    print(f"    P(ever declares POSITIVE) {pp:.3f}   "
          f"P(ever declares NEGATIVE) {pn:.3f}")
    print(f"    per-type false-claim rate {pp+pn:.3f} against a nominal 0.046;")
    fw = 1.0 - (1.0 - (pp + pn)) ** N_SETUP_TYPES
    print(f"    across {N_SETUP_TYPES} scoreboard rows: {fw:.3f} chance of at")
    print("    least one false verdict when NO setup type has any edge at all.")

    print("\n" + "=" * 78)
    print("  DONE. Verdict and logging schema are written up in EXPERIMENTS.md.")
    print("  NOTHING HERE AUTHORISES A LIVE TRADE (D-006).")
    print("=" * 78)


if __name__ == "__main__":
    main()

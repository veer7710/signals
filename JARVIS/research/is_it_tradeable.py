"""
IS THERE ANYTHING TO TRADE HERE AT ALL?

Every strategy tested in this repo has failed to clear the significance bar.
That has been read as "the strategies are wrong". There is a second
explanation nobody has tested: at these timeframes these markets may be close
enough to a random walk that no entry pattern can help, and if that is true
then hunting for pattern number 782 is the wrong activity entirely.

This does not test a strategy. It asks what the data IS.

  1. VARIANCE RATIO. If prices are a random walk, the variance of a q-period
     return is exactly q times the variance of a 1-period return, so VR(q) = 1.
     VR > 1 means moves persist (trend-following has something to work with).
     VR < 1 means moves reverse (mean reversion does). The further from 1, the
     more there is to exploit. Lo-MacKinlay heteroscedasticity-robust z is
     reported, because financial data is not homoscedastic and the naive
     statistic over-rejects.

  2. AUTOCORRELATION of returns at lags 1-10. Same question, different lens.

  3. HOW BIG IS ANY OF IT. A statistically real but tiny deviation is not
     tradeable once spread is paid. Effect size is reported next to
     significance, because the two are different questions and only one of
     them pays.

Run:  python3 JARVIS/research/is_it_tradeable.py
"""
from __future__ import annotations
import os, sys, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study


def logret(c):
    return [math.log(c[i] / c[i - 1]) for i in range(1, len(c)) if c[i - 1] > 0]


def variance_ratio(r, q):
    """Lo-MacKinlay VR(q) with the heteroscedasticity-robust z statistic."""
    n = len(r)
    if n < q * 10:
        return None, None
    mu = sum(r) / n
    var1 = sum((x - mu) ** 2 for x in r) / (n - 1)
    if var1 <= 0:
        return None, None
    # overlapping q-period returns
    m = n - q + 1
    sums = []
    run = sum(r[:q])
    sums.append(run)
    for i in range(1, m):
        run += r[i + q - 1] - r[i - 1]
        sums.append(run)
    varq = sum((s - q * mu) ** 2 for s in sums) / (m * q)
    vr = varq / var1

    # robust variance of VR under the null
    theta = 0.0
    for j in range(1, q):
        num = den = 0.0
        for t in range(j, n):
            num += ((r[t] - mu) ** 2) * ((r[t - j] - mu) ** 2)
        # Lo-MacKinlay delta_j denominator is the SQUARE of the sum of squared
        # deviations - NOT divided by n. The stray /n inflated theta by a factor
        # of n, which drove every z to about -0.01 and would have had me
        # reporting "random walk everywhere" from an arithmetic slip.
        den = (sum((x - mu) ** 2 for x in r)) ** 2
        dj = num / den if den else 0.0
        theta += ((2.0 * (q - j) / q) ** 2) * dj
    z = (vr - 1.0) / math.sqrt(theta) if theta > 0 else 0.0
    return vr, z


def autocorr(r, lag):
    n = len(r)
    mu = sum(r) / n
    den = sum((x - mu) ** 2 for x in r)
    if den <= 0:
        return 0.0
    num = sum((r[t] - mu) * (r[t - lag] - mu) for t in range(lag, n))
    return num / den


def cost_in_sigma(sym, s, r):
    """Round-trip cost expressed in units of one bar's standard deviation.
    If a single bar's move is smaller than the cost, nothing at that horizon
    is tradeable no matter how predictable it is."""
    c = study.COSTS.get(sym, engine.Costs())
    rt = c.spread + 2 * c.slippage
    mu = sum(r) / len(r)
    sd = math.sqrt(sum((x - mu) ** 2 for x in r) / (len(r) - 1))
    px = sum(s.c) / len(s.c)
    bar_move = sd * px                     # typical bar move in price units
    return rt, bar_move, (rt / bar_move if bar_move else float("inf"))


def run(sym, tf):
    s = engine.load(sym, tf)
    r = logret(s.c)
    print(f"\n{'='*74}\n  {sym} {tf}   {len(r)} returns\n{'='*74}")

    rt, bar_move, ratio = cost_in_sigma(sym, s, r)
    print(f"  COST vs MOVEMENT")
    print(f"     round-trip cost      : {rt:.5f}")
    print(f"     typical 1-bar move   : {bar_move:.5f}")
    print(f"     cost / bar move      : {ratio:.2f}   "
          f"({'a single bar cannot pay for the trade' if ratio >= 1 else 'ok'})")
    print(f"     bars needed just to break even: {max(1, math.ceil(ratio)):d}")

    print(f"\n  VARIANCE RATIO   (1.00 = random walk, >1 trends, <1 reverts)")
    print(f"     {'q':>4}{'VR':>9}{'robust z':>11}   reading")
    for q in (2, 4, 8, 16, 32):
        vr, z = variance_ratio(r, q)
        if vr is None:
            continue
        if abs(z) < 1.96:
            read = "indistinguishable from a random walk"
        elif vr > 1:
            read = "TRENDS - momentum has something to work with"
        else:
            read = "REVERTS - mean reversion has something to work with"
        print(f"     {q:>4}{vr:>9.3f}{z:>11.2f}   {read}")

    ac = [autocorr(r, k) for k in range(1, 11)]
    big = max(range(10), key=lambda i: abs(ac[i]))
    se = 1.0 / math.sqrt(len(r))
    print(f"\n  AUTOCORRELATION of returns, lags 1-10")
    print(f"     largest |ac| is lag {big+1}: {ac[big]:+.4f}   "
          f"(2 standard errors = {2*se:.4f})")
    print(f"     " + "  ".join(f"{a:+.3f}" for a in ac))


def selftest():
    """The statistic must be validated before its output is believed. An
    earlier version of this file had a stray /n in the Lo-MacKinlay variance
    that drove every z to about -0.01, which would have produced the same
    headline conclusion - random walk everywhere - from an arithmetic slip
    rather than from the data. Series with KNOWN behaviour catch that."""
    import random
    random.seed(7)
    n = 5000
    rw = [random.gauss(0, 1) for _ in range(n)]
    tr = [0.0] * n
    mr = [0.0] * n
    for i in range(1, n):
        tr[i] = 0.2 * tr[i - 1] + random.gauss(0, 1)
        mr[i] = -0.2 * mr[i - 1] + random.gauss(0, 1)
    ok = True
    for name, ser, want in (("random walk", rw, "flat"),
                            ("trending", tr, "up"),
                            ("reverting", mr, "down")):
        vr, z = variance_ratio(ser, 8)
        got = "flat" if abs(z) < 2 else ("up" if z > 0 else "down")
        mark = "ok" if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"     {name:<14} VR(8) {vr:.3f}  z {z:+.2f}  expected {want:<5} {mark}")
    print("     " + ("statistic validated\n" if ok
                     else "STATISTIC IS BROKEN - output below is meaningless\n"))
    return ok


if __name__ == "__main__":
    print(__doc__)
    print("  SELF TEST (the statistic, against series with known behaviour)")
    if not selftest():
        sys.exit(1)
    for sym in ("GOLD", "US500", "EURUSD", "GBPUSD"):
        for tf in ("15m", "1h"):
            try:
                run(sym, tf)
            except FileNotFoundError:
                pass
    print("\n" + "=" * 74)
    print("  If VR is indistinguishable from 1 at every horizon, the market is")
    print("  a random walk at that timeframe and NO entry pattern fixes that.")
    print("  That would be the most useful negative result in this repo.")
    print("=" * 74)

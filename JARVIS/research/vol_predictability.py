"""
RETURNS ARE UNPREDICTABLE. IS VOLATILITY?

E-037 established that these series have no directional persistence - 40
variance-ratio tests, none significant. Every strategy in this repo bets on
direction, which is why every one of them failed.

But "I cannot predict WHERE price goes" and "I cannot predict HOW FAR it goes"
are different claims, and only the first has been tested. Volatility clustering
is among the most robust empirical facts in finance: large moves follow large
moves, quiet follows quiet, in almost every market ever studied. If that holds
here it is the first genuinely predictable thing found in this project.

It would not by itself be a strategy. It would be a foundation for one:
  - size positions by predicted volatility rather than trailing ATR
  - trade only when a large move is likely, whatever its direction
  - set targets from predicted range instead of a fixed multiple
  - stay flat when the expected move cannot clear the spread

WHAT IS MEASURED
  1. Autocorrelation of ABSOLUTE returns (the standard clustering test) against
     autocorrelation of SIGNED returns, side by side. Signed is the E-037 result
     and should be ~0; if absolute is materially higher, volatility carries
     information that direction does not.
  2. Does today's range predict tomorrow's? Regression R^2 and the correlation.
  3. CONDITIONAL EXPANSION: given a quiet window, how much bigger is the next
     window than average - and is that difference larger than the spread?

Self-tested first against synthetic series with known behaviour, because a bug
here would produce a headline finding out of arithmetic.

Run:  python3 JARVIS/research/vol_predictability.py
"""
from __future__ import annotations
import os, sys, math, statistics as st, random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study


def logret(c):
    return [math.log(c[i] / c[i - 1]) for i in range(1, len(c)) if c[i - 1] > 0]


def ac(x, lag):
    n = len(x)
    if n <= lag + 2: return 0.0
    m = sum(x) / n
    den = sum((v - m) ** 2 for v in x)
    if den <= 0: return 0.0
    return sum((x[t] - m) * (x[t - lag] - m) for t in range(lag, n)) / den


def selftest():
    """A GARCH-like series has clustered volatility and unpredictable direction -
    exactly the shape being looked for. A plain random walk has neither."""
    random.seed(11)
    n = 6000
    rw = [random.gauss(0, 1) for _ in range(n)]
    g, sig = [], 1.0
    for _ in range(n):
        z = random.gauss(0, 1)
        r = sig * z
        g.append(r)
        sig = math.sqrt(0.02 + 0.90 * sig * sig * 0.0 + 0.90 * r * r + 0.05)
    ok = True
    for name, s_, want_abs in (("random walk", rw, False), ("clustered vol", g, True)):
        a_abs = ac([abs(v) for v in s_], 1)
        a_sgn = ac(s_, 1)
        got = a_abs > 0.15
        mark = "ok" if got == want_abs else "FAIL"
        if got != want_abs: ok = False
        print(f"     {name:<15} |r| ac1 {a_abs:+.3f}   r ac1 {a_sgn:+.3f}   {mark}")
    print("     " + ("statistic validated\n" if ok else "STATISTIC BROKEN\n"))
    return ok


def run(sym, tf):
    s = engine.load(sym, tf)
    r = logret(s.c)
    absr = [abs(v) for v in r]
    n = len(r)
    se = 1.0 / math.sqrt(n)

    print(f"\n{'='*76}\n  {sym} {tf}   {n} returns   (2 standard errors = {2*se:.4f})\n{'='*76}")
    print(f"  {'lag':>4}{'signed r':>12}{'|r| (vol)':>12}   verdict")
    for lag in (1, 2, 3, 5, 10, 20):
        a_s, a_a = ac(r, lag), ac(absr, lag)
        v = "VOLATILITY CLUSTERS" if a_a > 2 * se and a_a > 3 * abs(a_s) else \
            ("vol > direction" if a_a > 2 * se else "neither")
        print(f"  {lag:>4}{a_s:>+12.4f}{a_a:>+12.4f}   {v}")

    # does one window's range predict the next?
    W = 20
    rng = []
    for i in range(0, len(s) - W, W):
        hi = max(s.h[i:i + W]); lo = min(s.l[i:i + W])
        rng.append(hi - lo)
    if len(rng) > 30:
        x, y = rng[:-1], rng[1:]
        mx, my = sum(x) / len(x), sum(y) / len(y)
        sx = math.sqrt(sum((v - mx) ** 2 for v in x))
        sy = math.sqrt(sum((v - my) ** 2 for v in y))
        cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
        cor = cov / (sx * sy) if sx and sy else 0.0
        print(f"\n  {W}-bar range predicting the NEXT {W}-bar range:")
        print(f"     correlation {cor:+.3f}   R^2 {cor*cor:.3f}   on {len(x)} windows")

        # conditional expansion, and whether it clears the cost
        c = study.COSTS.get(sym, engine.Costs())
        cost = c.spread + 2 * c.slippage
        srt = sorted(range(len(x)), key=lambda i: x[i])
        q = max(5, len(x) // 4)
        quiet = [y[i] for i in srt[:q]]
        loud = [y[i] for i in srt[-q:]]
        print(f"     after the quietest 25%: next range averages {sum(quiet)/len(quiet):.2f}")
        print(f"     after the loudest  25%: next range averages {sum(loud)/len(loud):.2f}")
        print(f"     all windows          : {my:.2f}   round-trip cost {cost:.2f}")
        ratio = (sum(quiet)/len(quiet)) / my if my else 0
        print(f"     -> a quiet window is followed by {ratio:.2f}x the average range")


if __name__ == "__main__":
    print(__doc__)
    print("  SELF TEST")
    if not selftest():
        sys.exit(1)
    for sym in ("GOLD", "US500", "EURUSD", "GBPUSD"):
        for tf in ("15m", "1h"):
            try: run(sym, tf)
            except FileNotFoundError: pass

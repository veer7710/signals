"""
E-043 / A4 — NON-DIRECTIONAL PAYOFF: can predictable volatility be monetised
on a single SPOT instrument, with no options?

THE QUESTION
------------
E-038 is this project's only CONFIRMED finding: volatility is predictable in
8 of 8 series (|r| autocorrelation 7-19x two standard errors) while signed
returns sit at zero.  E-041 established that a filter can move a zero-edge
directional entry toward zero but never past it, which closes the filtering
class.  So the remaining question is whether a different PAYOFF SHAPE - one
that does not bet on direction - can convert predictable range into
expectancy on the instruments actually available.

THE INSTRUMENT CONSTRAINT, stated up front because it is the crux
----------------------------------------------------------------
A retail spot MT5 account can express exactly these orders: market, buy stop,
sell stop, buy limit, sell limit, stop loss, take profit.  THERE ARE NO
OPTIONS.  A pair of stop orders straddling the price is NOT a straddle: it has
no premium, so there is nothing to be mispriced, and its payoff in the
underlying is piecewise LINEAR with fixed knots.  It is a breakout system with
two entries that pays the round trip on every leg that fills.  If any number
in this file ever implies otherwise, the number is wrong.

PRE-REGISTRATION - written and committed BEFORE any market data was read
-----------------------------------------------------------------------
Structure under test ("stop-order straddle"), decided at the CLOSE of bar i:
  anchor  P = c[i]                     (known at bar i, no lookahead)
  width   d = k * ATR(14)[i]
  a buy stop at P+d and a sell stop at P-d, both live for bars i+1 .. i+H.
  Neither order is cancelled when the other fills - that is what makes the
  structure non-directional, and it is also what makes it pay twice.

GRID (fixed in advance):
  H (window, bars) : 2, 4, 8, 16, 32, 64
  k (half-width in ATR units) : 0.25, 0.50, 1.00, 1.50, 2.00
  markets : GOLD, US500, EURUSD, GBPUSD x 15m and 1h.  Per E-040, GOLD and
  US500 are the real test; FX is the KNOWN-DEAD CONTROL and a structure that
  looks good on EURUSD 15m indicts the cost model, not the market.

WINDOWS: strictly NON-OVERLAPPING.  Anchor at i, traded bars i+1..i+H, next
anchor at i+H.  n is reported for every cell.

COST, matched to engine.backtest exactly:
  per leg round trip c = spread + 2*slippage + commission_per_lot /
  value_per_point_per_lot.  Charged on EVERY leg that fills.  Costs come from
  study.COSTS[sym]; a missing key must raise.

THE THREE PAYOFF ACCOUNTINGS (all computed on the same windows):
  A  ORACLE CEILING (the brief's formula, and the gate).  Perfect foresight
     of the EXIT only: the larger of the two excursions from the anchor is
     captured in full, minus the half-width, minus the cost of every leg that
     filled.  The losing leg is charitably assumed to cost only its round
     trip.  payoff_A = max(exc_up, exc_dn) - d - c * n_legs, and 0 when
     neither leg fills.
  A+ MAXIMAL ORACLE: both filled legs exited at their own perfect extreme.
     Reachable only with perfect foresight of both turning points; reported
     as the absolute upper bound so no reader thinks A was pessimistic.
  B  NO-FORESIGHT: every filled leg is closed at the window's closing price
     c[i+H].  This is what the structure earns with no direction skill and no
     exit skill.  When BOTH legs fill, B is exactly -2d - 2c by construction,
     whatever price does - that is the whipsaw, and it is the economics of
     the structure.

PRE-REGISTERED DECISION RULE (fixed before seeing any market number):
  1. GATE.  If mean payoff_A - after honest double cost - is not clearly
     positive in the GOLD and US500 cells, the branch is dead and the
     experiment stops there.  No real rule beats the oracle.
  2. If the gate passes, the structure is only USABLE if mean payoff_B > 0
     with t > 3.65 (the project's multiple-testing threshold) on GOLD or
     US500.  A ceiling that is entirely composed of exit foresight is not an
     edge, because E-037 says exit foresight is exactly what this data does
     not supply.
  3. P(both legs fill) - the whipsaw frequency - is reported for every cell.
     It is the whole economics of the structure and is measured, not assumed.
  4. Only if B clears is the E-038 conditioning worth running.

TIE RULE, and it is the single assumption the result rests on:
  There is no tick data (KNOWN_LIMITATIONS), so when ONE bar's range contains
  both P+d and P-d the intrabar sequence is unknown.  Resolved as the WORSE
  outcome: BOTH legs are treated as filled.  The same-bar double-fill count
  is reported separately so a reader can see how much rests on it.

FILLS: stop orders trigger on the RAW level (h >= P+d, l <= P-d) and are
filled adversely; the adverse move and the commission are both inside c.

WHAT THIS DOES NOT REPEAT
  E-031 breakout as a setup: held in 0 of 8 markets.  The distinguishing
    sentence: E-031 cancelled the opposite side and asked whether the break
    direction persists; this keeps BOTH sides live and asks whether RANGE
    alone pays, so the whipsaw is the subject rather than a nuisance.
  E-032 a compression threshold that could never fire.  No compression
    threshold is used here; the width is ATR-scaled and every cell reports
    its fill rate.
  E-021 gating on realised compression (failed OOS).  E-020 adaptive
    targeting (worse than fixed).  E-039 the ATR-scaled reachability ratio
    that was constant by construction - noted because an ATR-scaled d makes
    predicted-range / d near-constant too, and the conditional step measures
    that ratio's dispersion FIRST, as E-041 did.

SELF-TESTS (run before any market data; the script exits non-zero on failure)
  (a) a known zigzag with a hand-computable payoff
  (b) a tight oscillation where BOTH legs fill: the doubled cost and the
      -2d whipsaw must appear
  (c) a flat zero-volatility series at d=0: payoff must be exactly -2c
  (d) MARTINGALE CONTROL: on a driftless random walk, payoff_B's GROSS must
      be indistinguishable from zero, and DOUBLING the volatility must not
      improve it.  This is the mechanism the whole experiment turns on.

RUN:  python3 JARVIS/research/nondirectional.py
"""
from __future__ import annotations
import os, sys, math, random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study

H_GRID = [2, 4, 8, 16, 32, 64]
K_GRID = [0.25, 0.50, 1.00, 1.50, 2.00]
SERIES = [(s, tf) for s in ("GOLD", "US500", "EURUSD", "GBPUSD")
          for tf in ("15m", "1h")]
T_THRESH = 3.65


def split(s, frac=0.70):
    k = int(len(s) * frac)
    return (engine.Series(s.ts[:k], s.o[:k], s.h[:k], s.l[:k], s.c[:k]),
            engine.Series(s.ts[k:], s.o[k:], s.h[k:], s.l[k:], s.c[k:]))


def round_trip(costs):
    """Per-leg round-trip cost in PRICE units, matched to engine.backtest."""
    return (costs.spread + 2.0 * costs.slippage
            + costs.commission_per_lot / costs.value_per_point_per_lot)


def straddle_window(s, i, d, H, c):
    """One non-overlapping window.  Returns a dict of the three accountings.

    Decision at close of bar i; orders live over bars i+1..i+H only.
    """
    P = s.c[i]
    up_lvl, dn_lvl = P + d, P - d
    hi = max(s.h[i + 1:i + 1 + H])
    lo = min(s.l[i + 1:i + 1 + H])
    close = s.c[i + H]
    exc_up = hi - P
    exc_dn = P - lo
    up_fill = hi >= up_lvl
    dn_fill = lo <= dn_lvl
    # same-bar double fill: the tie case with no tick data.  TIES LOSE, so
    # both legs are treated as filled (already true above); counted here.
    same_bar = False
    if up_fill and dn_fill:
        for j in range(i + 1, i + 1 + H):
            if s.h[j] >= up_lvl and s.l[j] <= dn_lvl:
                same_bar = True
                break
    n_legs = (1 if up_fill else 0) + (1 if dn_fill else 0)

    if n_legs == 0:
        return dict(A=0.0, Aplus=0.0, B=0.0, gross_B=0.0, n_legs=0,
                    both=False, same_bar=False, fill=False)

    # A: the larger excursion, captured perfectly, minus the width
    A = max(exc_up, exc_dn) - d - c * n_legs
    # A+: every filled leg exited at its own perfect extreme
    Aplus = 0.0
    if up_fill:
        Aplus += exc_up - d
    if dn_fill:
        Aplus += exc_dn - d
    Aplus -= c * n_legs
    # B: every filled leg closed at the window close, no foresight at all
    gross_B = 0.0
    if up_fill:
        gross_B += close - up_lvl
    if dn_fill:
        gross_B += dn_lvl - close
    B = gross_B - c * n_legs
    return dict(A=A, Aplus=Aplus, B=B, gross_B=gross_B, n_legs=n_legs,
                both=(n_legs == 2), same_bar=same_bar, fill=True)


def mean_sd_t(xs):
    n = len(xs)
    if n < 2:
        return (0.0, 0.0, 0.0, n)
    m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / (n - 1)
    sd = math.sqrt(v)
    t = m / (sd / math.sqrt(n)) if sd > 0 else 0.0
    return (m, sd, t, n)


def sweep(s, a, c, H, k, warmup=250):
    """Non-overlapping straddle windows across a series.  a = ATR(14) list."""
    rows = []
    i = warmup
    while i + H < len(s):
        if a[i] is None or a[i] <= 0:
            i += H
            continue
        rows.append(straddle_window(s, i, k * a[i], H, c))
        i += H
    return rows


# --------------------------------------------------------------- self-test
def _mkseries(prices):
    """Build a Series from a list of closes; each bar h=l=o=c (a tick path)."""
    n = len(prices)
    return engine.Series(list(range(n)), list(prices), list(prices),
                         list(prices), list(prices))


def _fail(msg):
    print(f"  FAIL  {msg}")
    sys.exit(1)


def _close(a, b, tol):
    return abs(a - b) <= tol


def selftest():
    print("=" * 74)
    print("  SELF-TEST — synthetic series with answers known in advance")
    print("=" * 74)
    c = 0.5

    # (a) known zigzag: 100 -> 110 -> 100, never below 100.  d = 1.
    px = [100.0, 102.0, 105.0, 110.0, 106.0, 100.0]
    s = _mkseries(px)
    r = straddle_window(s, 0, 1.0, 5, c)
    # exc_up = 10, exc_dn = 0; only the up leg fills
    if r["n_legs"] != 1:
        _fail(f"(a) expected 1 leg filled, got {r['n_legs']}")
    if not _close(r["A"], 10.0 - 1.0 - 0.5, 1e-9):
        _fail(f"(a) A expected 8.5, got {r['A']}")
    if not _close(r["B"], (100.0 - 101.0) - 0.5, 1e-9):
        _fail(f"(a) B expected -1.5, got {r['B']}")
    print(f"  PASS  (a) zigzag: A = {r['A']:+.3f} (hand: +8.500), "
          f"B = {r['B']:+.3f} (hand: -1.500), legs = {r['n_legs']}")

    # (b) tight oscillation, BOTH legs fill.  d = 1.
    px = [100.0, 102.0, 100.0, 98.0, 100.0]
    s = _mkseries(px)
    r = straddle_window(s, 0, 1.0, 4, c)
    if r["n_legs"] != 2 or not r["both"]:
        _fail(f"(b) expected both legs filled, got {r['n_legs']}")
    if not _close(r["A"], 2.0 - 1.0 - 2 * 0.5, 1e-9):
        _fail(f"(b) A expected 0.0, got {r['A']}")
    if not _close(r["Aplus"], (2 - 1) + (2 - 1) - 2 * 0.5, 1e-9):
        _fail(f"(b) A+ expected +1.0, got {r['Aplus']}")
    if not _close(r["B"], -2.0 * 1.0 - 2 * 0.5, 1e-9):
        _fail(f"(b) B expected -3.0 (= -2d - 2c), got {r['B']}")
    print(f"  PASS  (b) whipsaw: both legs filled, B = {r['B']:+.3f} "
          f"(hand: -3.000 = -2d - 2c), doubled cost charged")

    # (b2) the same-bar tie must be detected and resolved as BOTH filled
    s = engine.Series([0, 1, 2], [100.0, 100.0, 100.0], [100.0, 103.0, 100.0],
                      [100.0, 97.0, 100.0], [100.0, 100.0, 100.0])
    r = straddle_window(s, 0, 1.0, 2, c)
    if not (r["both"] and r["same_bar"]):
        _fail(f"(b2) same-bar tie not resolved as both-filled: {r}")
    print(f"  PASS  (b2) same-bar tie resolved as BOTH filled (ties lose)")

    # (c) flat, zero volatility, d = 0: both legs fill at the anchor
    s = _mkseries([100.0] * 10)
    r = straddle_window(s, 0, 0.0, 9, c)
    if not (_close(r["A"], -2 * c, 1e-9) and _close(r["B"], -2 * c, 1e-9)):
        _fail(f"(c) flat series expected -2c = -1.0, got A={r['A']} B={r['B']}")
    print(f"  PASS  (c) flat/zero-vol at d=0: A = B = {r['A']:+.3f} "
          f"(exactly -2c, negative)")

    # (d) MARTINGALE CONTROL — the mechanism the experiment turns on
    def walk(n, sigma, seed):
        random.seed(seed)
        px = [1000.0]
        for _ in range(n):
            px.append(px[-1] + random.gauss(0.0, sigma))
        # give each bar a real high/low so stop orders can trigger intrabar
        ts, o, h, l, cl = [], [], [], [], []
        for j in range(1, len(px)):
            o.append(px[j - 1]); cl.append(px[j])
            h.append(max(px[j - 1], px[j]) + abs(random.gauss(0, sigma / 3)))
            l.append(min(px[j - 1], px[j]) - abs(random.gauss(0, sigma / 3)))
            ts.append(j)
        return engine.Series(ts, o, h, l, cl)

    print("\n  (d) MARTINGALE CONTROL — driftless random walk, GOLD costs")
    print("      gross B must be indistinguishable from zero, and DOUBLING")
    print("      the volatility must not improve it.")
    gc = round_trip(study.COSTS["GOLD"])
    for sigma in (0.5, 1.0, 2.0):
        s = walk(120000, sigma, 20260831)
        a = engine.atr(s, 14)
        rows = sweep(s, a, gc, H=16, k=1.0, warmup=250)
        gb = [r["gross_B"] for r in rows if r["fill"]]
        nb = [r["B"] for r in rows if r["fill"]]
        m, sd, t, n = mean_sd_t(gb)
        mn, _, tn, _ = mean_sd_t(nb)
        flag = "OK" if abs(t) < 3.0 else "SUSPECT"
        print(f"      sigma {sigma:4.1f}:  gross B mean {m:+9.4f}  "
              f"t {t:+6.2f}  [{flag}]   net B mean {mn:+9.4f} t {tn:+7.2f}  "
              f"n {n}")
        if abs(t) >= 3.0:
            _fail("(d) gross B is not a martingale on a random walk — "
                  "the simulator has a directional bug")
        if mn >= 0:
            _fail("(d) net B is not negative on a driftless walk — "
                  "cost is not being charged")
    print("  PASS  (d) gross payoff is zero on a martingale at EVERY "
          "volatility;\n            only the cost survives, and it scales "
          "with the number of legs.")

    # (e) POSITIVE CONTROL: a series with genuine drift must show a POSITIVE
    #     gross B, or the simulator is blind to an effect that exists.
    random.seed(7)
    px = [1000.0]
    for _ in range(60000):
        px.append(px[-1] + random.gauss(0.30, 1.0))
    ts, o, h, l, cl = [], [], [], [], []
    for j in range(1, len(px)):
        o.append(px[j - 1]); cl.append(px[j])
        h.append(max(px[j - 1], px[j]) + 0.2); l.append(min(px[j - 1], px[j]) - 0.2)
        ts.append(j)
    s = engine.Series(ts, o, h, l, cl)
    a = engine.atr(s, 14)
    rows = sweep(s, a, gc, H=16, k=1.0, warmup=250)
    gb = [r["gross_B"] for r in rows if r["fill"]]
    m, sd, t, n = mean_sd_t(gb)
    if t <= 3.0:
        _fail(f"(e) simulator did not detect strong injected drift: t={t:.2f}")
    print(f"  PASS  (e) injected drift +0.30/bar IS detected: gross B "
          f"{m:+.3f}, t {t:+.2f}, n {n}\n            (the pipeline is not "
          f"blind — it finds an effect when one is there)")
    print("\n  ALL SELF-TESTS PASSED\n")


# --------------------------------------------------------------- the ceiling
def ceiling_table():
    print("=" * 74)
    print("  STEP 1 — THE ORACLE CEILING (the gate).  Full sample.")
    print("  A  = larger excursion captured perfectly, - d, - cost per leg")
    print("  A+ = both filled legs exited at their own perfect extreme")
    print("  B  = every filled leg closed at the window close (NO foresight)")
    print("  All figures are MEAN PER WINDOW, in multiples of the per-leg")
    print("  round-trip cost c.  n = non-overlapping windows.")
    print("=" * 74)
    out = {}
    for sym, tf in SERIES:
        s = engine.load(sym, tf)
        costs = study.COSTS[sym]
        c = round_trip(costs)
        a = engine.atr(s, 14)
        print(f"\n### {sym} {tf}   ({len(s)} bars, c = {c:g} price units)")
        print(f"{'H':>4} {'k':>5} {'n':>5} {'fill%':>6} {'both%':>6} "
              f"{'tie%':>5} {'A/c':>8} {'A+/c':>8} {'B/c':>8} {'t(B)':>7}")
        for H in H_GRID:
            for k in K_GRID:
                rows = sweep(s, a, c, H, k)
                if not rows:
                    continue
                n = len(rows)
                filled = [r for r in rows if r["fill"]]
                nf = len(filled)
                if nf == 0:
                    continue
                both = sum(1 for r in filled if r["both"])
                tie = sum(1 for r in filled if r["same_bar"])
                mA, _, _, _ = mean_sd_t([r["A"] for r in rows])
                mAp, _, _, _ = mean_sd_t([r["Aplus"] for r in rows])
                mB, _, tB, _ = mean_sd_t([r["B"] for r in rows])
                out[(sym, tf, H, k)] = dict(n=n, nf=nf, both=both, tie=tie,
                                            A=mA, Ap=mAp, B=mB, tB=tB, c=c)
                print(f"{H:>4} {k:>5.2f} {n:>5} {100.0*nf/n:>6.1f} "
                      f"{100.0*both/nf:>6.1f} {100.0*tie/nf:>5.1f} "
                      f"{mA/c:>8.2f} {mAp/c:>8.2f} {mB/c:>8.2f} {tB:>7.2f}")
    return out


def main():
    selftest()
    tab = ceiling_table()

    print("\n" + "=" * 74)
    print("  SUMMARY — best cell per series, judged by the PRE-REGISTERED rule")
    print("=" * 74)
    print(f"{'series':>12} {'best A/c cell':>22} {'A/c':>8} | "
          f"{'best B/c cell':>22} {'B/c':>8} {'t(B)':>7} {'n':>6}")
    any_b = False
    for sym, tf in SERIES:
        cells = [(kk, v) for kk, v in tab.items() if kk[0] == sym and kk[1] == tf]
        if not cells:
            continue
        ba = max(cells, key=lambda x: x[1]["A"])
        bb = max(cells, key=lambda x: x[1]["B"])
        if bb[1]["B"] > 0 and bb[1]["tB"] > T_THRESH:
            any_b = True
        print(f"{sym+' '+tf:>12} {'H='+str(ba[0][2])+' k='+str(ba[0][3]):>22} "
              f"{ba[1]['A']/ba[1]['c']:>8.2f} | "
              f"{'H='+str(bb[0][2])+' k='+str(bb[0][3]):>22} "
              f"{bb[1]['B']/bb[1]['c']:>8.2f} {bb[1]['tB']:>7.2f} "
              f"{bb[1]['n']:>6}")

    print("\n  Fraction of ALL cells with mean B > 0: "
          f"{sum(1 for v in tab.values() if v['B'] > 0)}/{len(tab)}")
    print("  Fraction of ALL cells with mean B > 0 AND t > 3.65: "
          f"{sum(1 for v in tab.values() if v['B'] > 0 and v['tB'] > T_THRESH)}"
          f"/{len(tab)}")
    print("  Fraction of ALL cells with mean A > 0 (the ORACLE): "
          f"{sum(1 for v in tab.values() if v['A'] > 0)}/{len(tab)}")
    print("\n  PRE-REGISTERED RULE 2: usable requires mean B > 0 with "
          f"t > {T_THRESH} on GOLD or US500.")
    print(f"  RESULT: {'a cell qualifies' if any_b else 'NO cell qualifies'}.")


if __name__ == "__main__":
    main()

"""
E-098 — CROSS-SYMBOL CONCURRENCY. Frequency without the correlation tax.

E-097 found that holding more than one position AT ONCE ON THE SAME SYMBOL does
not pay risk-adjusted: on GOLD 1h the return-to-drawdown ratio falls from 25.4
at one slot to 11.2 at ten. And it found WHY, which is the useful half - the
trades concurrency adds are not bad trades, they are BETTER than average
(+0.68R against the base's +0.36R at ten slots). They arrive during strong moves,
which is exactly when signals cluster. What kills the ratio is that they are the
SAME TRADE TWICE: opened together, they lose together, so the drawdowns deepen
faster than the returns grow.

That diagnosis has an obvious consequence nobody here has tested. If the cost of
concurrency is correlation, then concurrency across DIFFERENT SYMBOLS should not
pay it. Four symbols sit in data/ and every experiment in this project bar a
handful is gold-only.

This matters more than it looks, because of E-093: frequency is the dominant
lever for a funded account (2 trades/day passes 24%, 10/day passes 99.9%), and
E-089 says frequency bought by dropping timeframe costs R. Cross-symbol
frequency costs neither R nor - if the correlation is low - drawdown.

THE HONEST BAR. E-069 recorded all four FX rows as REJECTED on the liquidity
rules. That was the E-069 geometry, not E-080's toptick+FVG+OB stack, so it is
re-measured here rather than assumed either way. And a weak symbol can still
EARN ITS PLACE in a portfolio if it is uncorrelated - that is the whole point of
a portfolio - so each symbol is judged twice: alone, and by what it does to the
combination.

Run:  python3 JARVIS/research/portfolio.py
"""
from __future__ import annotations
import os, sys, datetime, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from toptick import zone_stream
from smc import smc_state
from smc_combine import all_signals
from concurrency import simulate_slots, curve

USE = {"toptick", "fvg", "ob"}
SYMS = ("GOLD", "US500", "EURUSD", "GBPUSD")


def run_symbol(sym, tf, slots=1):
    s = engine.load(sym, tf)
    c = study.COSTS[sym]
    A = engine.atr(s, 14)
    per_bar, _ = zone_stream(s)
    st = smc_state(s, A)
    cands = all_signals(s, c, per_bar, A, st, USE)
    tr = simulate_slots(s, c, cands, slots=slots)
    for t in tr:
        t["ts"] = s.ts[t["exit_bar"]]
        t["sym"] = sym
    return tr


def stats(trades):
    if not trades:
        return 0, 0.0, 0.0, 0.0, 0.0
    n = len(trades)
    m = sum(t["r"] for t in trades) / n
    sd = (sum((t["r"] - m) ** 2 for t in trades) / max(n - 1, 1)) ** 0.5
    tstat = m / (sd / n ** 0.5) if sd > 0 else 0.0
    eq, dd = curve(trades, 1.0)
    return n, m, tstat, eq, dd


def daily(trades):
    """R per calendar day, for the correlation matrix."""
    d = {}
    for t in trades:
        k = datetime.datetime.fromtimestamp(t["ts"], datetime.timezone.utc).date()
        d[k] = d.get(k, 0.0) + t["r"]
    return d


def corr(a, b):
    ks = sorted(set(a) & set(b))
    if len(ks) < 20:
        return None
    xa = [a[k] for k in ks]; xb = [b[k] for k in ks]
    ma = sum(xa) / len(xa); mb = sum(xb) / len(xb)
    va = sum((x - ma) ** 2 for x in xa); vb = sum((x - mb) ** 2 for x in xb)
    if va <= 0 or vb <= 0:
        return None
    cv = sum((xa[i] - ma) * (xb[i] - mb) for i in range(len(ks)))
    return cv / (va * vb) ** 0.5


def main():
    for tf in ("1h", "15m"):
        print("\n" + "=" * 96)
        print(f"  E-098 — EVERY SYMBOL ON THE E-080 STACK, {tf}. One slot per symbol.")
        print("=" * 96)
        book = {}
        print(f"  {'symbol':<9} {'n':>6} {'mean R':>9} {'t':>7} {'total R':>9} "
              f"{'maxDD R':>9} {'R/DD':>7} {'verdict':>12}")
        print("  " + "-" * 74)
        for sym in SYMS:
            tr = run_symbol(sym, tf)
            book[sym] = tr
            n, m, t, eq, dd = stats(tr)
            v = ("worth it" if t > 3.0 and eq > 0 else
                 "marginal" if t > 1.5 and eq > 0 else "no")
            print(f"  {sym:<9} {n:>6} {m:>+9.3f} {t:>7.2f} {eq:>+9.2f} "
                  f"{dd:>9.2f} {(eq/dd if dd>0 else 0):>7.2f} {v:>12}")

        # ---- how correlated are the daily returns?
        print(f"\n  DAILY-RETURN CORRELATION (shared trading days only)")
        ds = {s_: daily(book[s_]) for s_ in SYMS}
        print(f"  {'':<9}" + "".join(f"{x:>9}" for x in SYMS))
        for a in SYMS:
            row = ""
            for b in SYMS:
                if a == b:
                    row += f"{'1.00':>9}"
                else:
                    c = corr(ds[a], ds[b])
                    row += f"{'n/a' if c is None else format(c, '+.2f'):>9}"
            print(f"  {a:<9}{row}")

        # ---- the portfolio, at matched total risk
        print(f"\n  THE PORTFOLIO. Each symbol gets one slot; risk split equally,")
        print(f"  so every row below carries the SAME total exposure.")
        print(f"  {'book':<28} {'n':>6} {'total R':>9} {'maxDD R':>9} {'R/DD':>7}")
        print("  " + "-" * 62)
        combos = [("GOLD alone", ["GOLD"]),
                  ("GOLD + US500", ["GOLD", "US500"]),
                  ("GOLD + EURUSD", ["GOLD", "EURUSD"]),
                  ("GOLD + US500 + EURUSD", ["GOLD", "US500", "EURUSD"]),
                  ("all four", list(SYMS))]
        for name, members in combos:
            allt = []
            for s_ in members:
                for t in book[s_]:
                    t2 = dict(t); t2["r"] = t["r"] / len(members)
                    allt.append(t2)
            allt.sort(key=lambda t: t["ts"])
            eq, dd = curve(allt, 1.0)
            print(f"  {name:<28} {len(allt):>6} {eq:>+9.2f} {dd:>9.2f} "
                  f"{(eq/dd if dd>0 else 0):>7.2f}")


if __name__ == "__main__":
    main()

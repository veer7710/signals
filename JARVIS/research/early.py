"""
E-060 — Fast early entry: a resting stop at the SuperTrend band.

Veer: "u need to prfect executin asnd fats early entry ... assume ur wrong
fact check ur own words everything".

THE IDEA
The EA waits for the flip bar to CLOSE, then buys the next open. But the
SuperTrend band from the previous bar is a PUBLISHED PRICE - it exists before
the current bar opens. A stop order resting there fills the moment price
trades through it, which on M1 is up to sixty seconds and a whole bar's range
earlier than the close-and-next-open entry.

THE BUG IN MY FIRST ATTEMPT, AND WHY THE FIRST RESULT WAS FICTION
Version one took the list of bars that DID flip and asked "could I have filled
at the band during those bars". That is look-ahead in the selection: it only
ever entered on bars that turned out to flip, and quietly skipped every bar
where price touched the band and closed back inside. Those false touches are
exactly the losing trades a real resting order eats. It produced +0.214R
pooled and it was not real.

This version rests the order honestly. When flat and the SuperTrend is bearish,
a BUY stop sits at the previous bar's upper band and fills on ANY touch,
flip or not. Every false break is taken, because a real order takes them.

Both entry styles are otherwise identical: same filters (read at i-1, since at
fill time the current bar has not closed), same stop, same target, same time
cap, one position at a time, ties resolved as losses.

COSTS: Veer's measured 0.46 gold spread, no commission (PU Prime Standard).

Run:  python3 JARVIS/research/early.py
"""
from __future__ import annotations
import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies, study
from engine import Series

COMBOS = [("GOLD", "15m"), ("GOLD", "1h"), ("US500", "15m"), ("US500", "1h"),
          ("EURUSD", "15m"), ("EURUSD", "1h"), ("GBPUSD", "15m"), ("GBPUSD", "1h")]


def simulate(s: Series, costs, mode, stop_atr=1.5, rr=2.0, max_bars=50,
             warmup=300, use_dema=True, max_adx=35.0, seed=7):
    """mode: 'close'  the EA today - flip bar closes, fill the next open
             'band'   a stop resting at the PREVIOUS bar's band, any touch
             'random' matched control: same trade count, random bar and side
    """
    ctx = engine.build_context(s)
    d, fu, fl = strategies.supertrend_dir(s, 7, 1.2)
    A = engine.atr(s, 7)
    D = strategies.dema(s.c, 200)
    half = costs.spread / 2.0
    comm_px = costs.commission_per_lot / costs.value_per_point_per_lot

    def filters_ok(k, side):
        """Read at bar k, which must be CLOSED at decision time."""
        a = A[k]
        if a is None or a <= 0:
            return False
        if use_dema:
            dn, dp = D[k], D[k - 2]
            if dn is None or dp is None:
                return False
            if side == 1 and dn < dp:
                return False
            if side == -1 and dn > dp:
                return False
        ad = ctx["adx"][k]
        if ad is None or ad > max_adx:
            return False
        return True

    def resolve(entry, side, risk, start):
        stop = entry - side * risk
        target = entry + side * rr * risk
        for j in range(start + 1, min(start + 1 + max_bars, len(s))):
            hit_s = (s.l[j] <= stop) if side == 1 else (s.h[j] >= stop)
            hit_t = (s.h[j] >= target) if side == 1 else (s.l[j] <= target)
            if hit_s:
                return ((stop - entry) * side - comm_px) / risk, j
            if hit_t:
                return ((target - entry) * side - comm_px) / risk, j
        j = min(start + max_bars, len(s) - 1)
        fill = s.c[j] - side * (half + costs.slippage)
        return ((fill - entry) * side - comm_px) / risk, j

    out = []
    i = warmup
    while i < len(s) - 2:
        if mode == "close":
            if d[i] == 0 or d[i - 1] == 0:
                i += 1; continue
            up = d[i] == -1 and d[i - 1] == 1
            dn = d[i] == 1 and d[i - 1] == -1
            if not (up or dn):
                i += 1; continue
            side = 1 if up else -1
            if not filters_ok(i, side):
                i += 1; continue
            a = A[i]
            risk = stop_atr * a
            entry = s.o[i + 1] + side * (half + costs.slippage)
            r, jout = resolve(entry, side, risk, i + 1)
            out.append(r)
            i = jout + 1
            continue

        if mode == "band":
            # the order rests at the level the PREVIOUS bar published
            if d[i - 1] == 0 or fu[i - 1] is None or fl[i - 1] is None:
                i += 1; continue
            side = 1 if d[i - 1] == 1 else -1     # bearish -> a BUY stop above
            lvl = fu[i - 1] if side == 1 else fl[i - 1]
            touched = (s.h[i] >= lvl) if side == 1 else (s.l[i] <= lvl)
            if not touched:
                i += 1; continue
            # filters read at i-1: bar i has not closed when the order fills
            if not filters_ok(i - 1, side):
                i += 1; continue
            a = A[i - 1]
            risk = stop_atr * a
            # a stop order fills AT the level or worse, never better
            entry = lvl + side * (half + costs.slippage)
            r, jout = resolve(entry, side, risk, i)
            out.append(r)
            i = jout + 1
            continue

        i += 1

    if mode == "random":
        rng = random.Random(seed)
        base = simulate(s, costs, "close", stop_atr, rr, max_bars, warmup,
                        use_dema, max_adx)
        pool = list(range(warmup, len(s) - max_bars - 2))
        for _ in range(len(base)):
            k = pool[rng.randrange(len(pool))]
            a = A[k]
            if a is None or a <= 0:
                continue
            side = 1 if rng.random() < 0.5 else -1
            risk = stop_atr * a
            entry = s.o[k + 1] + side * (half + costs.slippage)
            r, _j = resolve(entry, side, risk, k + 1)
            out.append(r)
    return out


def stat(rs):
    if not rs:
        return (0, 0.0, 0.0, 0.0)
    n = len(rs)
    e = sum(rs) / n
    w = 100 * sum(1 for r in rs if r > 0) / n
    sd = (sum((r - e) ** 2 for r in rs) / n) ** 0.5
    t = e / (sd / math.sqrt(n)) if sd > 0 else 0.0
    return (n, e, w, t)


def main():
    print("=" * 96)
    print("  E-060  EARLY ENTRY — a stop resting at the band, fills on ANY touch")
    print("  Every false break is taken, because a real resting order takes them.")
    print("  Costs: 0.46 gold spread measured off Veer's terminal, no commission.")
    print("=" * 96)
    print(f"\n  {'market':<13}{'n close':>9}{'CLOSE':>10}{'n band':>9}{'BAND':>10}"
          f"{'RANDOM':>10}{'band-close':>12}{'band-random':>13}")
    print("  " + "-" * 92)

    tot = {"close": [], "band": [], "random": []}
    bc = br = seen = 0
    for sym, tf in COMBOS:
        try:
            s = engine.load(sym, tf)
        except Exception:
            continue
        costs = study.COSTS.get(sym, engine.Costs())
        rc = simulate(s, costs, "close")
        rb = simulate(s, costs, "band")
        rr_ = simulate(s, costs, "random")
        if len(rc) < 40:
            continue
        nc, ec, wc, tc = stat(rc)
        nb, eb, wb, tb = stat(rb)
        nr, er, wr, tr = stat(rr_)
        tot["close"] += rc; tot["band"] += rb; tot["random"] += rr_
        seen += 1
        bc += 1 if eb > ec else 0
        br += 1 if eb > er else 0
        print(f"  {sym+' '+tf:<13}{nc:>9}{ec:>+9.3f}R{nb:>9}{eb:>+9.3f}R"
              f"{er:>+9.3f}R{eb-ec:>+12.3f}{eb-er:>+13.3f}")

    print("  " + "-" * 92)
    print(f"  BAND beats CLOSE in {bc}/{seen} markets, and RANDOM in {br}/{seen}")
    for k in ("close", "band", "random"):
        n, e, w, t = stat(tot[k])
        print(f"  POOLED {k:<7} n={n:<6} {e:+.3f}R   win {w:.1f}%   t={t:+.2f}")


if __name__ == "__main__":
    main()

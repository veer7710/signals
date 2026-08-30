"""
Does a setup at a HIGHER-TIMEFRAME level outperform one at a local level?

Veer's ask: "on M15, a buy opportunity aligned with levels from last week."

That is multi-timeframe confluence, and it is the single most promising
selection idea left — because E-025 showed bounce setups run at break-even
overall. If HTF-aligned setups are materially better, the break-even average is
hiding a good subset and a bad one, and the filter is worth having. If they are
not, confluence is decoration and should not be built.

METHOD
Levels are derived at three scales from the SAME 1h series by resampling:
  local   — pivots on 1h bars          (this week's noise)
  daily   — pivots on resampled 24h    (this month's structure)
  weekly  — pivots on resampled 120h   (last quarter's structure)
A level is "confluent" when levels from two or more scales sit within a
tolerance of each other. Every level carries its confirmation lag, so a weekly
pivot is not usable until the weekly bar that formed it has closed.

Outcome: first-touch, ties lose, costs applied by the caller's stop/target.
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, sweeps as sw, study


def htf_levels(base: engine.Series, factor: int, pivot_n=3):
    """Pivots found on a resampled series, mapped back to base-bar indices.

    A pivot on the resampled series at aggregated bar k is confirmed pivot_n
    aggregated bars later, which is (k + pivot_n) * factor base bars — so the
    level is not usable on the base chart until then. Returning that index is
    what keeps this honest.
    """
    htf = engine.resample(base, factor)
    lv = sw.find_levels(htf, pivot_n=pivot_n)
    out = []
    for l in lv:
        known_base = min(len(base) - 1, l.known_bar * factor)
        out.append((l.price, l.side, known_base))
    return out


def test(symbol="GOLD", tf="1h", tol_atr=0.35, rr=2.0, stop_atr=1.0, horizon=40):
    s = engine.load(symbol, tf)
    A = engine.atr(s, 14)

    local = [(l.price, l.side, l.known_bar) for l in sw.find_levels(s, pivot_n=3)]
    daily = htf_levels(s, 24)          # ~daily
    weekly = htf_levels(s, 120)        # ~weekly

    def near(px, pool, i, tol):
        return any(abs(px - p) <= tol and kb <= i for p, sd, kb in pool)

    buckets = {"local only": [], "+ daily": [], "+ weekly": [], "+ both": []}

    for i in range(400, len(s) - horizon - 1):
        a = A[i] or 0
        if a <= 0:
            continue
        tol = tol_atr * a
        rng = max(s.h[i] - s.l[i], 1e-9)
        dnW = min(s.o[i], s.c[i]) - s.l[i]
        upW = s.h[i] - max(s.o[i], s.c[i])

        side, lvl = 0, None
        for p, sd, kb in local:
            if kb > i or i - kb < 3:
                continue
            if sd < 0 and p - tol * 3 <= s.l[i] <= p + tol and s.c[i] > p and dnW / rng >= 0.30:
                side, lvl = 1, p; break
            if sd > 0 and p - tol <= s.h[i] <= p + tol * 3 and s.c[i] < p and upW / rng >= 0.30:
                side, lvl = -1, p; break
        if side == 0:
            continue

        d = near(lvl, daily, i, tol)
        w = near(lvl, weekly, i, tol)
        key = ("+ both" if (d and w) else "+ weekly" if w else "+ daily" if d else "local only")

        entry, risk = s.c[i], stop_atr * a
        tgt, won = rr * risk, False
        for j in range(i + 1, min(i + 1 + horizon, len(s))):
            fav = (s.h[j] - entry) if side > 0 else (entry - s.l[j])
            adv = (entry - s.l[j]) if side > 0 else (s.h[j] - entry)
            if adv >= risk:
                break
            if fav >= tgt:
                won = True; break
        buckets[key].append(won)
    return buckets


def run():
    print("=" * 78)
    print("  HIGHER-TIMEFRAME CONFLUENCE — is a level from last week worth more?")
    print("=" * 78)
    print("  Bounce setups only. Stop 1 ATR, target 2R, first-touch, ties lose.")
    print("  Break-even at 2R is 33.3%.\n")
    allb = {}
    for sym, tf in [("GOLD", "1h"), ("US500", "1h"), ("EURUSD", "1h"), ("GBPUSD", "1h")]:
        b = test(sym, tf)
        print(f"  {sym} {tf}")
        print(f"    {'confluence':<14}{'n':>7}{'win':>9}{'vs BE':>9}")
        for k in ("local only", "+ daily", "+ weekly", "+ both"):
            v = b[k]
            allb.setdefault(k, []).extend(v)
            if len(v) < 30:
                print(f"    {k:<14}{len(v):>7}   (too few)")
                continue
            w = sum(v) / len(v)
            print(f"    {k:<14}{len(v):>7}{100*w:>8.1f}%{100*(w-1/3):>+8.1f}")
        print()

    print("  " + "=" * 74)
    print("  POOLED ACROSS ALL FOUR MARKETS")
    print(f"    {'confluence':<14}{'n':>8}{'win':>9}{'vs BE':>9}")
    rows = []
    for k in ("local only", "+ daily", "+ weekly", "+ both"):
        v = allb.get(k, [])
        if len(v) < 50:
            print(f"    {k:<14}{len(v):>8}   (too few)")
            continue
        w = sum(v) / len(v)
        rows.append((k, len(v), w))
        print(f"    {k:<14}{len(v):>8}{100*w:>8.1f}%{100*(w-1/3):>+8.1f}")

    print("\n  VERDICT")
    if len(rows) >= 2:
        base = dict((k, w) for k, n, w in rows).get("local only")
        best = max(rows, key=lambda r: r[2])
        if base is not None and best[0] != "local only" and best[2] - base > 0.03:
            print(f"  CONFLUENCE HELPS. '{best[0]}' wins {100*best[2]:.1f}% against")
            print(f"  {100*base:.1f}% for a local-only level — a {100*(best[2]-base):+.1f} point gap.")
            print("  That is a real selection rule: take the aligned ones, skip the rest.")
        else:
            print("  No material advantage from higher-timeframe alignment.")
            print("  A level from last week performs about the same as a local one,")
            print("  so confluence is decoration here and should NOT be built as a filter.")
    return allb


if __name__ == "__main__":
    run()

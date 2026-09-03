"""
E-096 — THE 40 POUND SQUEEZE. Resolve it or state it plainly.

The handover calls this "unresolved and the central problem of goal 1":

    the spread wants a WIDE stop (E-089: the edge needs cost/stop <= ~0.11)
    a 40 pound account wants a SMALL one (E-081: 0.01 lots is 0.787/point and
    cannot be smaller, so the TIMEFRAME sets the risk, not the account)

At a 0.20 spread on M1 the EA needs about 2.7 points of stop to hold cost/stop
at 0.14, and 2.7 points x 0.787 = 2.12, which is 5.3% of 40 pounds PER TRADE.

This file does not argue about that. It computes the thing that actually decides
whether goal 1 is possible: RISK OF RUIN, on the measured R distribution, at
every combination of account size and per-trade risk. A strategy that "works"
at 5.3% risk per trade and has a 36% win rate is not a strategy, it is a
countdown - and the number of trades on the clock is computable.

Run:  python3 JARVIS/research/small_account.py
"""
from __future__ import annotations
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
from engine import atr as watr
from pine_ea_parity import ea_supertrend_at, ea_dema_at

ATRL, MULT, DEMAL, WARM = 7, 1.2, 200, 400
GBP_PER_POINT_001 = 0.787      # E-081. 0.01 lots. Cannot go smaller.


def r_dist(sym="GOLD", tf="15m", spread=0.46, stop_atr=2.0, trail=3.0,
           maxbars=50, arm=1.0):
    """The EA's own per-trade R multiples, full shipped exit stack."""
    s = engine.load(sym, tf)
    A = watr(s, ATRL)
    n = len(s)
    start = max(WARM + 10, DEMAL * 4 + 20)
    R, busy = [], -1
    for i in range(start, n - 1):
        if i <= busy:
            continue
        d, dp = ea_supertrend_at(s, i, ATRL, MULT, WARM)
        up, dn = d == -1 and dp == 1, d == 1 and dp == -1
        if not (up or dn):
            continue
        side = 1 if up else -1
        en, ep = ea_dema_at(s, i, DEMAL, 1), ea_dema_at(s, i, DEMAL, 3)
        if en is None or ep is None:
            continue
        if (side > 0 and en < ep) or (side < 0 and en > ep):
            continue
        a = A[i]
        if not a or a <= 0:
            continue
        entry = s.o[i + 1] + side * spread / 2.0
        risk = stop_atr * a
        stop = entry - side * risk
        peak, i_out, px, mfe = entry, None, None, 0.0
        for j in range(i + 1, min(i + 1 + maxbars, n)):
            if (side > 0 and s.l[j] <= stop) or (side < 0 and s.h[j] >= stop):
                i_out, px = j, stop - side * spread / 2.0
                break
            peak = max(peak, s.h[j]) if side > 0 else min(peak, s.l[j])
            mfe = max(mfe, side * (peak - entry) / risk)
            t = peak - side * trail * a
            stop = max(stop, t) if side > 0 else min(stop, t)
            if mfe >= arm:
                allow = 0.20
                if mfe >= 1.5: allow = 0.16
                if mfe >= 3.0: allow = 0.12
                gb = entry + side * side * (peak - entry) * (1.0 - allow)
                stop = max(stop, gb) if side > 0 else min(stop, gb)
        if i_out is None:
            i_out = min(i + maxbars, n - 1)
            px = s.c[i_out] - side * spread / 2.0
        R.append(side * (px - entry) / risk)
        busy = i_out
    return R


def ruin(R, risk_frac, n_trades=300, trials=4000, ruin_at=0.50, seed=5):
    """Fraction of runs that lose `ruin_at` of the account inside n_trades,
    and the median multiple of the starting balance at the end. Block-resampled
    in runs of 5 so losing streaks survive."""
    rng = random.Random(seed)
    ruined, ends = 0, []
    for _ in range(trials):
        eq = 1.0
        low = 1.0
        for t in range(n_trades):
            if t % 5 == 0:
                st = rng.randrange(len(R))
            r = R[(st + (t % 5)) % len(R)]
            eq *= (1.0 + risk_frac * r)
            low = min(low, eq)
            if eq <= 1.0 - ruin_at:
                break
        if low <= 1.0 - ruin_at:
            ruined += 1
        ends.append(eq)
    ends.sort()
    return ruined / trials, ends[len(ends) // 2]


def main():
    R = r_dist("GOLD", "15m")
    wins = sum(1 for r in R if r > 0)
    print("=" * 92)
    print("  E-096 — THE 40 POUND SQUEEZE")
    print("=" * 92)
    print(f"\n  The measured R distribution (GOLD 15m, the EA's own exit stack):")
    print(f"    {len(R)} trades, mean {sum(R)/len(R):+.3f}R, "
          f"win rate {100.0*wins/len(R):.1f}%, worst {min(R):+.2f}R, best {max(R):+.2f}R")

    print(f"\n  WHAT ONE TRADE COSTS, at 0.01 lots ({GBP_PER_POINT_001}/point, E-081)")
    print(f"  {'stop (points)':>14} {'risk in GBP':>12}   " +
          "".join(f"{'£'+str(a):>10}" for a in (40, 60, 100, 200, 500)))
    print("  " + "-" * 76)
    for pts in (2.7, 4.0, 6.0, 9.0, 12.0, 20.0):
        risk = pts * GBP_PER_POINT_001
        cells = "".join(f"{100.0*risk/a:>9.1f}%" for a in (40, 60, 100, 200, 500))
        print(f"  {pts:>14.1f} {risk:>12.2f}   {cells}")

    print(f"\n  RISK OF RUIN — chance of losing HALF the account inside 300 trades")
    print(f"  (block-resampled from the distribution above, 4000 runs each)")
    print(f"  {'risk/trade':>11} {'= stop of':>11} {'£40 needs':>11}   "
          f"{'P(lose half)':>13} {'median end':>12}")
    print("  " + "-" * 68)
    for rf in (0.053, 0.04, 0.03, 0.02, 0.015, 0.01, 0.005):
        p, med = ruin(R, rf)
        stop_pts = rf * 40.0 / GBP_PER_POINT_001
        print(f"  {rf*100:>10.1f}% {stop_pts:>10.1f}p {'':>11}   "
              f"{p*100:>12.1f}% {med:>11.2f}x")

    # ---------------------------------------------------------------------
    # THE TABLE ABOVE IS WORTHLESS AND IS KEPT ONLY TO SHOW WHY.
    #
    # It says a 40 pound account risking 5.3% a trade has a 0.7% chance of
    # losing half and a MEDIAN OUTCOME OF ELEVEN TIMES ITS MONEY. That is
    # nonsense, and the reason is structural: it resamples the strategy's OWN
    # BACKTEST, which has a mean of +0.181R. Feed a Monte Carlo a +0.181R edge
    # and it will report that the edge works. It cannot do anything else. This
    # is E-050 and E-064's mistake with a different face - the model has no
    # control, so it only ever confirms its own input.
    #
    # The measured edge is not a fact about the future:
    #   * n = 112 trades, so its own standard error is large (printed below);
    #   * E-092 has just shown the DEMA gate that SELECTED these trades is not
    #     established out of sample;
    #   * E-089 measured the edge falling from +0.249R to +0.041R once M1's
    #     cost burden is applied, and M1 is the timeframe this EA is for.
    #
    # So the question is turned round. Instead of assuming an edge and asking
    # whether 40 pounds survives, assume nothing and ask: WHAT EDGE DOES 40
    # POUNDS NEED? That is answerable without knowing the truth, and it is the
    # number that decides whether goal 1 is possible.
    sd = (sum((r - sum(R)/len(R))**2 for r in R) / (len(R)-1))**0.5
    se = sd / len(R)**0.5
    m = sum(R)/len(R)
    print(f"\n  {'='*88}")
    print(f"  THE TABLE ABOVE IS WORTHLESS. It resamples the strategy's own backtest,")
    print(f"  so a +{m:.3f}R input guarantees a positive answer. The measured edge is")
    print(f"  {m:+.3f}R +/- {se:.3f} (1 se, n={len(R)}), so the 95% interval is "
          f"[{m-1.96*se:+.3f}, {m+1.96*se:+.3f}]R")
    print(f"  - it does not exclude zero. E-089 puts the M1 figure at +0.041R.")
    print(f"  {'='*88}")
    print(f"\n  SO: WHAT EDGE DOES A GIVEN ACCOUNT NEED? Same R SHAPE, mean shifted.")
    print(f"  P(lose half of the account inside 300 trades), 4000 runs per cell.")
    print(f"  A 2.7 point stop = £2.12 at 0.01 lots, so the risk %% is set by the account.\n")
    ACCTS = (40, 60, 100, 200, 500)
    risk_gbp = 2.7 * GBP_PER_POINT_001
    print(f"  {'true mean R':>12} " + "".join(
        f"{'£'+str(a)+' ('+format(100*risk_gbp/a,'.1f')+'%)':>16}" for a in ACCTS))
    print("  " + "-" * 92)
    for target in (0.181, 0.120, 0.082, 0.041, 0.020, 0.000, -0.020):
        shift = target - m
        Rs = [r + shift for r in R]
        cells = []
        for a in ACCTS:
            pr, med = ruin(Rs, risk_gbp / a)
            cells.append(f"{pr*100:>7.1f}%  {med:>5.2f}x")
        tag = {0.181: " (as measured)", 0.041: " (E-089's M1)",
               0.000: " (no edge)"}.get(target, "")
        print(f"  {target:>+12.3f} " + "".join(f"{c:>16}" for c in cells) + tag)
    print(f"\n  Each cell is P(lose half) and the median ending multiple.")


if __name__ == "__main__":
    main()

"""
E-177 — PERFECTING THE SUPERTREND ENTRY AND EXIT, ON THE REGIME THAT MATTERS.

Veer: "perfect the execution on suoertrend for the ea same w liquidity strat",
and before that: "i want top tick entrie to reduce drawdown", "sl closer to be
as it grows then trail sl not too aggressively for liquidity sweeps".

E-176 established the only cell this project can honestly call SUPPORTED:
SuperTrend + DEMA slope on 2024-2026 gold at 1h, +0.374 ATR/trade, t +2.91.
So the execution questions get asked THERE, not on the 2018 range where every
previous answer in this repo was computed.

Three questions, in the order they change the money:

  1. ENTRY. Market at the next open, or a limit resting N x ATR back? A limit
     that fills is a better price; a limit that does not fill misses the trade
     entirely, and on a trend system the trades you miss are the big ones. The
     table reports the MISS RATE next to the result, because an entry style
     that improves the average by throwing away the winners is not an
     improvement.

  2. DRAWDOWN. Veer's actual constraint is funded-account drawdown, not mean
     return. So every row reports mean MAE - how far the average trade goes
     against you before it works - in ATR. That is the number a prop firm
     charges you for.

  3. EXIT. Hold to the opposite flip, or trail? His live panel said the exit
     stack banked LESS than holding. Tested here on the right regime.

FILL RULES, both of which cost money and both of which are enforced:
  * a limit that gaps through fills at the LIMIT (it fills better, and booking
    the level is the conservative reading)
  * a stop or trail that the bar has already passed cannot be filled at the
    level: engine.trail_apply returns None and the trade exits at the close
    (E-151). Nothing here hand-rolls a trail.
"""
from __future__ import annotations
import os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, ema, trail_level
from supertrend_rescue import st_state
from st_churn import flips
from regime import load_plain, resample, dema_of

COST_ATR = 0.02      # today's 1h gold spread as a fraction of 1h ATR (~0.15/12)


def signals(s, dLen=200):
    """Every DEMA-agreeing flip: (bar, dir). The E-176 SUPPORTED signal."""
    d, _, _ = st_state(s, 7, 1.2)
    D = dema_of(s.c, dLen)
    out = []
    for (i, t) in flips(s, d):
        if i < 2 or i + 1 >= len(s) or D[i] is None or D[i - 2] is None:
            continue
        slope = D[i] - D[i - 2]
        if (slope >= 0) if t > 0 else (slope <= 0):
            out.append((i, t))
    return out


def run(s, sig, pull=0.0, life=3, stopAtr=2.0, trail=None, hold=400):
    """pull = limit distance back, in ATR. 0 = market at the next open.
    trail = give-back fraction of the run-up, or None to hold to the flip."""
    A = watr(s, 14)
    res, missed, maes = [], 0, []
    nxt = {i: j for (i, _), (j, _) in zip(sig, sig[1:] + [(len(s) - 1, 0)])}
    for (i, t) in sig:
        a = A[i]
        if not a or a <= 0 or i + 1 >= len(s):
            continue
        ref = s.o[i + 1]
        if pull <= 0.0:
            j, entry = i + 1, ref
        else:
            want = ref - t * pull * a
            j = None
            for k in range(i + 1, min(i + 1 + life, len(s))):
                # a limit is filled by the bar's ADVERSE extreme reaching it
                if (s.l[k] <= want) if t > 0 else (s.h[k] >= want):
                    j, entry = k, want
                    break
            if j is None:
                missed += 1
                continue
        sl = entry - t * stopAtr * a
        end = min(nxt.get(i, len(s) - 1), i + hold)
        peak, mae, px_out, kk = entry, 0.0, None, None
        for k in range(j, min(end + 1, len(s))):
            adv = t * (entry - (s.l[k] if t > 0 else s.h[k]))
            mae = max(mae, adv)
            if (s.l[k] <= sl) if t > 0 else (s.h[k] >= sl):
                px_out, kk = sl, k
                break
            peak = max(peak, s.h[k]) if t > 0 else min(peak, s.l[k])
            if trail is not None and k > j:
                lv = trail_level(entry, sl, peak, s.c[k], t, trail)
                if lv is None:            # E-151: unplaceable -> exit at close
                    px_out, kk = s.c[k], k
                    break
                sl = lv
        if px_out is None:
            kk = min(end, len(s) - 1)
            px_out = s.o[min(kk + 1, len(s) - 1)]
        res.append(t * (px_out - entry) / a - COST_ATR)
        maes.append(mae / a)
    return res, missed, maes


def line(label, r, missed, maes, offered):
    if len(r) < 20:
        print(f"  {label:<34}  too few trades ({len(r)})")
        return
    m = statistics.fmean(r)
    t = m / (statistics.pstdev(r) / len(r) ** 0.5)
    w = 100.0 * sum(1 for x in r if x > 0) / len(r)
    print(f"  {label:<34}{len(r):>6}{100.0*missed/max(offered,1):>8.0f}%"
          f"{w:>7.1f}%{m:>+10.3f}{t:>+7.2f}{statistics.fmean(maes):>9.3f}"
          f"{sum(r):>9.1f}")


def main():
    h1 = load_plain("GOLD_1h.json")
    sig = signals(h1)
    print("=" * 104)
    print(f"  E-177 — SuperTrend execution on 2024-2026 gold, 1h."
          f" {len(sig)} DEMA-agreeing flips. Cost {COST_ATR} ATR/trade.")
    print("=" * 104)
    print(f"  {'':<34}{'n':>6}{'missed':>8}{'win%':>7}{'ATR/trd':>10}{'t':>7}"
          f"{'mean MAE':>9}{'total':>9}")
    print("  " + "-" * 98)

    print("\n  1. ENTRY — is a pullback limit worth the trades it misses?")
    for pull, life in ((0.0, 0), (0.25, 3), (0.25, 6), (0.50, 3), (0.50, 6),
                       (0.75, 6), (1.00, 6)):
        r, ms, mae = run(h1, sig, pull=pull, life=life)
        lbl = "market at the next open" if pull <= 0 else \
              f"limit {pull:.2f} ATR back, {life} bars"
        line(lbl, r, ms, mae, len(sig))

    print("\n  2. EXIT — hold to the opposite flip, or trail?")
    for trail, lbl in ((None, "hold to the opposite flip"),
                       (0.50, "trail, give back 50% of the run"),
                       (0.35, "trail, give back 35%"),
                       (0.25, "trail, give back 25%"),
                       (0.15, "trail, give back 15% (tight)")):
        r, ms, mae = run(h1, sig, trail=trail)
        line(lbl, r, ms, mae, len(sig))

    print("\n  3. THE STOP — what does a wider one buy?")
    for st_ in (1.0, 1.5, 2.0, 3.0, 4.0):
        r, ms, mae = run(h1, sig, stopAtr=st_)
        line(f"stop {st_:.1f} ATR, hold to flip", r, ms, mae, len(sig))




def grid():
    """The combination, judged the way a funded account judges it.

    Veer's binding constraint is not mean return, it is DRAWDOWN: a prop firm
    pays for the mean and charges for the excursion. So the column that decides
    this is ATR/trade divided by mean MAE - return per unit of the thing that
    fails the challenge. A setup with half the return and a third of the
    drawdown wins, because you can carry twice the size inside the same limit.

    "size x" is exactly that: how much bigger you could trade this row for the
    same drawdown as the shipped 2.0-ATR hold-to-flip row, and "at that size"
    is what the per-trade number becomes once you do.
    """
    h1 = load_plain("GOLD_1h.json")
    sig = signals(h1)
    print("\n" + "=" * 112)
    print("  4. THE COMBINATION — stop x trail, judged on DRAWDOWN, which is"
          " what a funded account actually charges for")
    print("=" * 112)
    print(f"  {'stop':>6}{'trail':>18}{'n':>6}{'win%':>7}{'ATR/trd':>10}{'t':>7}"
          f"{'MAE':>8}{'ret/MAE':>9}{'size x':>8}{'at that size':>14}")
    print("  " + "-" * 106)
    base = None
    rows = []
    for st_ in (1.0, 1.5, 2.0, 3.0):
        for trail, tl in ((None, "hold to flip"), (0.60, "give back 60%"),
                          (0.50, "give back 50%"), (0.35, "give back 35%")):
            r, ms, mae = run(h1, sig, stopAtr=st_, trail=trail)
            if len(r) < 20:
                continue
            m = statistics.fmean(r)
            t = m / (statistics.pstdev(r) / len(r) ** 0.5)
            w = 100.0 * sum(1 for x in r if x > 0) / len(r)
            mm = statistics.fmean(mae)
            if st_ == 2.0 and trail is None:
                base = mm
            rows.append((st_, tl, len(r), w, m, t, mm))
    for (st_, tl, n, w, m, t, mm) in rows:
        sx = base / mm if mm > 0 else 0.0
        print(f"  {st_:>6.1f}{tl:>18}{n:>6}{w:>6.1f}%{m:>+10.3f}{t:>+7.2f}"
              f"{mm:>8.3f}{(m/mm if mm else 0):>9.3f}{sx:>8.2f}"
              f"{m*sx:>+14.3f}")




def oos():
    """E-150's rule, which this project learned the hard way: a winner chosen on
    the full sample and then "validated" on part of that same sample has been
    validated on nothing. So the grid above is re-run on the FIRST half only,
    the best row is picked there, and that single row is then measured on the
    SECOND half, which the choice never saw. Anything that does not survive
    this is a curve fit and does not get to be a default.
    """
    h1 = load_plain("GOLD_1h.json")
    half = len(h1.c) // 2
    from engine import Series
    a = Series(h1.ts[:half], h1.o[:half], h1.h[:half], h1.l[:half], h1.c[:half])
    b = Series(h1.ts[half:], h1.o[half:], h1.h[half:], h1.l[half:], h1.c[half:])
    print("\n" + "=" * 104)
    print("  5. OUT OF SAMPLE — chosen on the first half, judged on the second")
    print("=" * 104)

    cands = [(st_, tr) for st_ in (1.0, 1.5, 2.0, 3.0)
             for tr in (None, 0.60, 0.50, 0.35)]
    sa, sb = signals(a), signals(b)

    def score(s, sig, st_, tr):
        r, _, mae = run(s, sig, stopAtr=st_, trail=tr)
        if len(r) < 20:
            return None
        m = statistics.fmean(r)
        mm = statistics.fmean(mae)
        return (len(r), m, m / (statistics.pstdev(r) / len(r) ** 0.5), mm,
                m / mm if mm else 0.0,
                100.0 * sum(1 for x in r if x > 0) / len(r))

    best, bestv = None, -9e9
    print(f"  first half ({len(a.c)} bars, {len(sa)} signals):")
    for (st_, tr) in cands:
        v = score(a, sa, st_, tr)
        if v and v[4] > bestv:
            best, bestv = (st_, tr), v[4]
    v = score(a, sa, *best)
    tl = "hold to flip" if best[1] is None else f"give back {best[1]:.0%}"
    print(f"    picked on return/MAE: stop {best[0]:.1f} ATR, {tl}"
          f"   n {v[0]}  {v[5]:.1f}% win  {v[1]:+.3f} ATR/trd  t {v[2]:+.2f}"
          f"  MAE {v[3]:.3f}  ret/MAE {v[4]:.3f}")

    print(f"\n  second half ({len(b.c)} bars, {len(sb)} signals) — UNSEEN:")
    w = score(b, sb, *best)
    if not w:
        print("    too few trades to judge")
        return
    print(f"    the SAME setting:                    "
          f"   n {w[0]}  {w[5]:.1f}% win  {w[1]:+.3f} ATR/trd  t {w[2]:+.2f}"
          f"  MAE {w[3]:.3f}  ret/MAE {w[4]:.3f}")
    sh = score(b, sb, 2.0, None)
    print(f"    the SHIPPED setting (2.0 ATR, hold):"
          f"    n {sh[0]}  {sh[5]:.1f}% win  {sh[1]:+.3f} ATR/trd  t {sh[2]:+.2f}"
          f"  MAE {sh[3]:.3f}  ret/MAE {sh[4]:.3f}")
    # The honest reading is NOT "the picked setting survives". Read the two
    # halves against each other first: if the first half is ~zero and the
    # second is strongly positive for EVERY setting, then what changed between
    # them is the market, not the parameter, and a parameter recommendation
    # drawn from that is a story about one trend.
    va = score(a, sa, 2.0, None)
    print()
    print(f"    picked setting  first half {v[1]:+.3f}  ->  second half {w[1]:+.3f}")
    print(f"    shipped setting first half {va[1]:+.3f}  ->  second half {sh[1]:+.3f}")
    gap = abs(w[4] - sh[4])
    if v[1] < 0.10 and sh[1] > 0.30 and va[1] < 0.10:
        print("\n    READ THIS AS A REGIME RESULT, NOT A PARAMETER RESULT.")
        print("    Both settings are ~zero in the first half and strongly positive")
        print("    in the second. What changed is the market, not the setting, and")
        print(f"    the two settings differ by {gap:.3f} on return/MAE out of sample,")
        print("    which is noise. Do NOT change a default on this evidence.")
    elif w[1] > 0 and w[4] > sh[4]:
        print("\n    The picked setting is positive on unseen data and better")
        print("    risk-adjusted than shipped.")
    else:
        print("\n    DOES NOT SURVIVE — do not ship this as a default.")


if __name__ == "__main__":
    main()
    grid()
    oos()

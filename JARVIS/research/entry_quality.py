"""
ENTRY QUALITY — heat, fakeouts, and whether waiting for a better price pays.

Veer: "where could our pine go wrong eg strategy entry exit fakes top tick
entry everything".

Three questions that decide whether an entry is good, each answerable with
numbers rather than opinion:

  1. HEAT. How far does a signal go AGAINST you before it works? If a winning
     trade routinely draws down 0.8R first, a stop at 1R is not protection, it
     is a coin flip on noise - and it explains "it stopped me out then went".

  2. FAKEOUTS. How often does price close back through the signal within a few
     bars? That is the signal failing, not the exit failing, and the two need
     completely different fixes.

  3. TOP TICK. The pullback entry was BUILT last session. Nobody measured
     whether it helps. It buys a better price at the cost of missing the setups
     that never look back. Which side of that trade wins is a measurement, and
     it is made here: market entry vs limit entries at several depths, on the
     same signals, with the same exits and the same costs.

METHOD is the house standard: signals from closed bars, fills at the next bar
or later, first touch, ties lose, per-symbol costs, and a chronological 70/30
split so the answer is not chosen on the data it is judged by.

Run:  python3 JARVIS/research/entry_quality.py
"""
from __future__ import annotations
import os, sys, math, statistics as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study, strategies as S
from engine import Series


def costs_for(sym):
    return study.COSTS.get(sym, engine.Costs())


def signals(s, atr_len=7, mult=1.2, dema_len=200):
    """Every SuperTrend flip that passes the DEMA filter, as (i, side)."""
    d, _, _ = S.supertrend_dir(s, atr_len, mult)
    D = S.dema(s.c, dema_len)
    out = []
    for i in range(300, len(s) - 2):
        if d[i] == 0 or d[i - 1] == 0:
            continue
        up = d[i] == -1 and d[i - 1] == 1
        dn = d[i] == 1 and d[i - 1] == -1
        if not (up or dn):
            continue
        if D[i] is None or D[i - 2] is None:
            continue
        if up and D[i] < D[i - 2]:
            continue
        if dn and D[i] > D[i - 2]:
            continue
        out.append((i, 1 if up else -1))
    return out


def pct(xs, p):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    return xs[max(0, min(len(xs) - 1, int(round(p / 100.0 * (len(xs) - 1)))))]


# ------------------------------------------------------------------ 1. heat
def heat(s, sigs, A, stop_atr=1.5, horizon=50):
    """For signals that eventually reach +1R, how far did they go against you
    first? Measured from the realistic fill: the next bar's open."""
    heats, fake, n_win = [], 0, 0
    for i, side in sigs:
        a = A[i]
        if a is None or a <= 0:
            continue
        en = s.o[i + 1]
        risk = stop_atr * a
        stop = en - side * risk
        tgt = en + side * risk
        mae = 0.0
        for j in range(i + 1, min(i + 1 + horizon, len(s))):
            adv = (en - (s.l[j] if side == 1 else s.h[j])) * side
            mae = max(mae, adv)
            hit_stop = (s.l[j] <= stop) if side == 1 else (s.h[j] >= stop)
            hit_tgt = (s.h[j] >= tgt) if side == 1 else (s.l[j] <= tgt)
            if hit_stop:
                break
            if hit_tgt:
                n_win += 1
                heats.append(mae / risk)
                break
        # a fakeout: closes back through the signal price within 3 bars
        k = min(i + 4, len(s) - 1)
        if any(((s.c[j] - s.c[i]) * side) < 0 for j in range(i + 1, k + 1)):
            fake += 1
    return heats, fake, n_win, len(sigs)


# ------------------------------------------------- 2. does waiting pay off?
def limit_test(s, sigs, A, depth, stop_atr=1.5, rr=3.0, wait=3, horizon=50,
               cost=0.0):
    """A resting limit `depth` x ATR better than the signal close. It fills only
    if price TRADES there within `wait` bars. Anything that does not fill is a
    missed trade and is counted, because that is the real cost of waiting."""
    rs, filled, missed = [], 0, 0
    for i, side in sigs:
        a = A[i]
        if a is None or a <= 0:
            continue
        want = s.c[i] - side * depth * a if depth > 0 else None
        en = None
        start = i + 1
        if want is None:
            en = s.o[i + 1]
        else:
            for j in range(i + 1, min(i + 1 + wait, len(s))):
                if (s.l[j] <= want) if side == 1 else (s.h[j] >= want):
                    en, start = want, j + 1
                    break
        if en is None:
            missed += 1
            continue
        filled += 1
        risk = stop_atr * a
        stop = en - side * risk
        tgt = en + side * rr * risk
        r = 0.0
        for j in range(start, min(start + horizon, len(s))):
            hit_stop = (s.l[j] <= stop) if side == 1 else (s.h[j] >= stop)
            hit_tgt = (s.h[j] >= tgt) if side == 1 else (s.l[j] <= tgt)
            if hit_stop:                       # ties lose
                r = -1.0 - cost / risk
                break
            if hit_tgt:
                r = rr - cost / risk
                break
        else:
            r = ((s.c[min(start + horizon, len(s)) - 1] - en) * side) / risk
        rs.append(r)
    n = len(rs)
    m = sum(rs) / n if n else 0.0
    sd = math.sqrt(sum((x - m) ** 2 for x in rs) / n) if n > 1 else 0.0
    t = m / (sd / math.sqrt(n)) if n > 1 and sd else 0.0
    return n, filled, missed, m, t


def split(s, frac=0.70):
    k = int(len(s) * frac)
    return (Series(s.ts[:k], s.o[:k], s.h[:k], s.l[:k], s.c[:k]),
            Series(s.ts[k:], s.o[k:], s.h[k:], s.l[k:], s.c[k:]))


def run(sym, tf):
    s = engine.load(sym, tf)
    A = engine.atr(s, 14)
    sigs = signals(s)
    if len(sigs) < 40:
        print(f"\n  {sym} {tf}: only {len(sigs)} signals, skipping")
        return
    c = costs_for(sym)
    cost = c.spread + 2 * c.slippage

    print(f"\n{'='*78}\n  {sym} {tf}   {len(sigs)} SuperTrend+DEMA signals\n{'='*78}")

    hs, fake, nwin, ntot = heat(s, sigs, A)
    if hs:
        print(f"  HEAT before a winner reaches +1R (in R):")
        print(f"     median {st.median(hs):.2f}   p75 {pct(hs,75):.2f}   "
              f"p90 {pct(hs,90):.2f}   worst {max(hs):.2f}")
        # NOT reported: "how many went more than 1R against you". MAE is
        # measured until the stop is hit and the stop sits at 1R, so that
        # number is 0% by construction - a tautology, not a finding.
        print(f"     -> a stop at {pct(hs,90):.2f}R would have cut 10% of the "
              f"eventual winners; at {pct(hs,75):.2f}R it would cut 25%")
    print(f"  FAKEOUTS: closed back through the signal within 3 bars: "
          f"{100.0*fake/ntot:.1f}% of signals")

    # does waiting pay? chosen on the first 70%, judged once on the last 30%
    ins, oos = split(s)
    Ai, Ao = engine.atr(ins, 14), engine.atr(oos, 14)
    si, so = signals(ins), signals(oos)
    print(f"\n  WAITING FOR A BETTER PRICE  (in-sample -> out-of-sample)")
    print(f"     {'entry':<22}{'fills':>7}{'missed':>8}{'IS exp':>9}"
          f"{'| OOS exp':>11}{'OOS t':>8}")
    for depth, label in ((0.0, "market, next open"), (0.15, "wait 0.15 ATR"),
                         (0.30, "wait 0.30 ATR"), (0.50, "wait 0.50 ATR"),
                         (0.75, "wait 0.75 ATR")):
        ni, fi, mi, m_i, _ = limit_test(ins, si, Ai, depth, cost=cost)
        no, fo, mo, m_o, t_o = limit_test(oos, so, Ao, depth, cost=cost)
        if ni < 20 or no < 12:
            print(f"     {label:<22}{fo:>7}{mo:>8}   too few to judge")
            continue
        share = 100.0 * mo / max(fo + mo, 1)
        print(f"     {label:<22}{fo:>7}{mo:>8}{m_i:>+9.3f}{m_o:>+11.3f}"
              f"{t_o:>+8.2f}   ({share:.0f}% never filled)")


if __name__ == "__main__":
    print(__doc__)
    for sym in ("GOLD", "US500", "EURUSD", "GBPUSD"):
        for tf in ("15m", "1h"):
            try:
                run(sym, tf)
            except FileNotFoundError:
                pass
    print("\n" + "=" * 78)
    print("  Read every t against the ~3.65 luck threshold for this repo's")
    print("  ~780 tested configurations. None of this is 15m advice for an M1")
    print("  chart - it ranks the IDEA, it does not certify the timeframe.")
    print("=" * 78)

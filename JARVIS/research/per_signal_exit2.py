"""
E-153 — EACH SIGNAL ITS OWN EXIT, ASKED AGAIN UNDER HONEST FILLS.

Veer: "yes each signal its own", and earlier and more specifically:
"we want tp based of levels and analysis we cant just set based of rr doesnt
work we need real analysis levels and where to place for top tick bottom tick".

E-150 asked this and the answer was contaminated by the E-151 trail leak. It is
asked again here with `engine.trail_level`, which refuses to fill at a level no
order could have been resting at.

Two questions, not one:

  1. Can a DIFFERENT exit rescue break+retest or the order block? Under E-151
     they lose money with a give-back trail. They are different trades - one
     rides a break, one enters at the birth of a move - so it is entirely
     possible the give-back is simply the wrong tool and they are being
     strangled. If a wider exit rescues them, they come back on.
  2. Does the SWEEP want something better than the 25% give-back? Including,
     for the first time, a target set by the NEXT OPPOSING LEVEL rather than by
     a multiple of risk - which is what Veer has asked for repeatedly and what
     nothing in this repo has ever measured.

THE EXIT MENU
  give g        trail that hands back g of the best excursion
  atr n         trail n ATR behind the extreme
  fixed r       take r x risk and leave
  level         exit at the nearest opposing swing level that was ALREADY KNOWN
                when the trade opened - resting liquidity is where a move stops
  level+trail   the level is the target, a 40% give-back protects the way there
  level_cap r   the level, but refuse the trade if the level is nearer than r x
                risk (a target too close to pay for the stop)

PROTOCOL, and this is the part E-150 got wrong: the winner is CHOSEN on the
first half of the data and JUDGED on the second half, which the choice has
never seen. A rule only changes what ships if it wins the half it never saw,
by more than nothing, on at least 100 trades. The 100 matters: the first run
of this file "adopted" a level target for break+retest on 25 unseen trades,
which is not a result, it is a coin landing the same way five times.
"""
from __future__ import annotations
import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import atr as watr, trail_level
from liq_m1 import load
from sweep_winrate import pivots
import combined as C

MENU = ([("give", g) for g in (0.15, 0.25, 0.40, 0.60, 0.80)]
        + [("atr", a) for a in (1.0, 2.0, 3.0, 5.0)]
        + [("fixed", r) for r in (1.0, 1.5, 2.0, 3.0)]
        + [("level", 0.0), ("level+trail", 0.40)]
        + [("level_cap", r) for r in (1.0, 1.5)])


def known_levels(s, pk=5):
    """(bar_known, price, side) sorted by the bar it became known on."""
    return sorted(pivots(s, pk), key=lambda x: x[0])


def opposing_level(piv, j, entry, d):
    """Nearest level in the trade's favour that was already known at bar j.

    A long is heading UP into sell-side liquidity, so the target is the lowest
    swing HIGH above entry. Only pivots confirmed strictly before j count."""
    best = None
    for (kb, px, side) in piv:
        if kb >= j:
            break
        if side != d:          # a long (+1) wants swing highs (side +1)
            continue
        if d * (px - entry) <= 0:
            continue
        if best is None or d * (px - best) < 0:
            best = px
    return best


def one_trade(s, A, piv, j, d, entry, sl, mode, param, hold=240):
    """Returns (exit price, exit bar) or None if the rule refuses the trade."""
    tgt = None
    if mode.startswith("level"):
        tgt = opposing_level(piv, j, entry, d)
        if tgt is None:
            return None
        if mode == "level_cap":
            if abs(tgt - entry) < param * abs(entry - sl):
                return None    # the target is nearer than the stop is far
    a = A[j] if A[j] else 1.0
    peak = entry
    for k in range(j, min(j + hold, len(s))):
        if (s.l[k] <= sl) if d > 0 else (s.h[k] >= sl):
            return sl, k
        if tgt is not None and ((s.h[k] >= tgt) if d > 0 else (s.l[k] <= tgt)):
            # E-110: the entry bar may not book its own favourable extreme
            if k > j:
                return tgt, k
        if k == j:
            continue
        peak = max(peak, s.h[k]) if d > 0 else min(peak, s.l[k])
        if mode == "give":
            nsl = trail_level(entry, sl, peak, s.c[k], d, param)
        elif mode == "level+trail":
            nsl = trail_level(entry, sl, peak, s.c[k], d, param)
        elif mode == "atr":
            from engine import trail_apply
            nsl = trail_apply(sl, peak - d * param * a, s.c[k], d)
        elif mode == "fixed":
            t = entry + d * param * abs(entry - sl)
            if (s.h[k] >= t) if d > 0 else (s.l[k] <= t):
                return t, k
            nsl = sl
        else:
            nsl = sl
        if nsl is None:
            return s.c[k], k
        sl = nsl
    kk = min(j + hold, len(s) - 1)
    return s.c[kk], kk


def book(tf, src, mode, param, subset=None, cooldown=5, _cache={}):
    key = (tf,)
    if key not in _cache:
        s, SP = load(tf)
        A = watr(s, 14)
        va = sorted(x for x in A[100:] if x)
        cs = 0.11 / (statistics.median(SP) / va[len(va) // 2])
        _cache[key] = (s, SP, A, cs, known_levels(s))
    s, SP, A, cs, piv = _cache[key]
    ck = (tf, src)
    if ck not in _cache:
        _cache[ck] = [c for c in C.candidates(s, A, cs, SP, {src}) if c[1] == src]
    out, busy = [], -1
    for (j, _, d, entry, sl0) in _cache[ck]:
        if j <= busy:
            continue
        if subset and not (subset[0] <= j < subset[1]):
            continue
        r = one_trade(s, A, piv, j, d, entry, sl0, mode, param)
        if r is None:
            continue
        px_out, kk = r
        out.append(d * ((px_out - d * SP[kk] * cs / 2.0) - entry))
        busy = kk + cooldown
    return out


def main():
    for tf in ("M1", "M5"):
        s, _ = load(tf)
        n = len(s)
        half = n // 2
        print("=" * 100)
        print(f"  E-153 — {tf}: each signal's own exit, honest fills, "
              f"chosen on the 1st half and judged on the 2nd")
        print("=" * 100)
        for src in (C.SWEEP, C.BR, C.OBD, C.OBR):
            rows = []
            for mode, param in MENU:
                r = book(tf, src, mode, param, subset=(0, half))
                if len(r) >= 30:
                    rows.append((sum(r) / len(r), sum(r), mode, param, len(r)))
            if not rows:
                continue
            rows.sort(reverse=True)
            print(f"\n  {C.NAME[src]}  — 1st half, best five by per-trade")
            print(f"    {'exit':<16}{'n':>7}{'points':>10}{'per trade':>12}")
            for (pt, tot, mode, param, N) in rows[:5]:
                lbl = f"{mode} {param:g}" if param else mode
                print(f"    {lbl:<16}{N:>7}{tot:>10.1f}{pt:>+12.4f}")
            pick = rows[0]
            ship = book(tf, src, "give", 0.25, subset=(half, n))
            best = book(tf, src, pick[2], pick[3], subset=(half, n))
            if not best or not ship:
                continue
            pb, ps = sum(best) / len(best), sum(ship) / len(ship)
            wb = 100.0 * sum(1 for x in best if x > 0) / len(best)
            lbl = f"{pick[2]} {pick[3]:g}" if pick[3] else pick[2]
            print(f"    2nd HALF, UNSEEN   pick '{lbl}': n={len(best)} "
                  f"{sum(best):+.1f} pts {pb:+.4f}/tr {wb:.1f}% win")
            print(f"                       shipped 'give 0.25': n={len(ship)} "
                  f"{sum(ship):+.1f} pts {ps:+.4f}/tr")
            if len(best) < 100:
                print(f"    -> REJECT: only {len(best)} trades unseen. A rule that "
                      f"wins on a sample this small has not won anything.")
            elif pb <= ps:
                print("    -> REJECT: the pick does not beat the shipped exit unseen")
            elif pb <= 0:
                print("    -> REJECT: it beats the shipped exit and still LOSES money")
            else:
                print(f"    -> ADOPT '{lbl}'")
        print()


if __name__ == "__main__":
    main()

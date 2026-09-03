"""
E-075 — The protection engine, re-measured on the EA as it now stands.

E-051b compared exit policies on a 1.5 ATR stop with the ADX gate on. Both of
those have since changed: E-071 widened the stop to 2.0 ATR and E-074 turned
the ADX ceiling off. R is now a third larger, so every rule expressed in R -
which is all of them - means something different. A conclusion measured on the
old geometry is not a conclusion about this EA.

The question Veer keeps asking, in his own words: "i've already seen us in the
past 5 min go up in peaks of 8 pound close not near was up 2.50 on two 0.01s
total and closed at 47 p each see how horrible that is". The give-back engine
exists to answer that. This measures whether it pays for itself, or whether it
only feels better - and it reports POINTS as well as R, because a rule that
improves expectancy while banking fewer pounds has not helped him.

allow_overlap=True throughout. Without it a fast exit frees the slot sooner and
the policies end up trading DIFFERENT entries, so the comparison would measure
entry selection as much as exit quality.

Run:  python3 JARVIS/research/exit_rerun.py
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies, exits, study

STOP_ATR = 2.0     # E-071
# Policies that do not exist in exits.py yet. Give-back armed at 1R fires on
# ordinary trades and caps them; armed high, it only ever engages on a trade
# that has genuinely become big, which is the version worth testing before
# the whole idea is condemned.
exits.POLICIES.update({
    "giveback 25% arm@3R":     exits.peak_giveback(3.0, 0.25),
    "giveback 30% arm@2R":     exits.peak_giveback(2.0, 0.30),
    "trail3ATR + gb25 arm@3R": exits.trail_plus_giveback(3.0, 3.0, 0.25),
    "trail3ATR + gb30 arm@2R": exits.trail_plus_giveback(3.0, 2.0, 0.30),
})

PICK = ["fixed 2R", "fixed 3R", "trail 2xATR", "trail 3xATR",
        "trail 3xATR arm@1R", "BE@1R + trail 3ATR",
        "giveback 30% arm@1R", "giveback 40% arm@1R", "giveback 25% arm@1.5R",
        "giveback 30% arm@2R", "giveback 25% arm@3R",
       "ratchet 45/30/22", "trail3ATR + gb30 arm@1R", "trail3ATR + gb40 arm@1R",
       "trail3ATR + gb30 arm@2R", "trail3ATR + gb25 arm@3R",
        "time 50 bars", "ORACLE (not tradeable)"]


def main():
    print("=" * 104)
    print("  E-075  THE EXIT STACK, ON THE EA AS IT NOW STANDS")
    print(f"  SuperTrend(7, 1.2) + DEMA, ADX gate OFF, stop {STOP_ATR} ATR.")
    print("  Every policy sees the SAME entries (overlap allowed), so this")
    print("  measures exits and nothing else. Ties lose. Costs both ends.")
    print("  ORACLE closes at the exact peak. It is not tradeable and it is here")
    print("  only to show how much of the move any real rule is leaving behind.")
    print("=" * 104)

    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        try:
            s = engine.load(sym, tf)
        except Exception:
            continue
        c = study.COSTS.get(sym, engine.Costs())
        sig = strategies.supertrend_sniper(s, stop_atr=STOP_ATR, rr=3.0)
        A = engine.atr(s, 7)
        print(f"\n  ### {sym} {tf}")
        print(f"   {'exit policy':<26}{'n':>6}{'win%':>8}{'expect':>10}{'PF':>7}"
              f"{'t':>7}{'total R':>10}{'points':>10}{'avg bars':>10}")
        print("   " + "-" * 92)
        rows = []
        for name in PICK:
            pol = exits.POLICIES.get(name)
            if pol is None:
                continue
            tr = exits.simulate(s, sig, pol, c, allow_overlap=True)
            if len(tr) < 30:
                continue
            rs = [t["r"] for t in tr]
            n = len(rs)
            e = sum(rs) / n
            w = 100.0 * sum(1 for r in rs if r > 0) / n
            sd = (sum((r - e) ** 2 for r in rs) / n) ** 0.5
            t_ = e / (sd / math.sqrt(n)) if sd > 0 else 0.0
            gp = sum(r for r in rs if r > 0); gl = -sum(r for r in rs if r < 0)
            pf = gp / gl if gl > 0 else 0.0
            # exits.simulate returns R only. POINTS is what Veer is paid in, and
            # R hides it: a rule can win its R on small bars and lose it on big
            # ones. Risk at entry is STOP_ATR x ATR(entry bar), so points = R x that.
            pts = 0.0
            for t in tr:
                a = A[t["i_in"]]
                if a:
                    pts += t["r"] * STOP_ATR * a
            bars = sum(t.get("bars", 0) for t in tr) / n
            rows.append((name, n, w, e, pf, t_, pts, bars))
        for name, n, w, e, pf, t_, pts, bars in rows:
            print(f"   {name:<26}{n:>6}{w:>7.1f}%{e:>+9.3f}R{pf:>7.2f}{t_:>+7.2f}"
                  f"{e*n:>+9.1f}R{pts:>+9.1f}{bars:>10.1f}")

    print("\n  READ THE POINTS COLUMN, NOT ONLY THE R COLUMN.")
    print("  R is scaled by the ATR at entry, so a rule that wins its R on small")
    print("  bars and loses it on big ones can look good in R and bank less money.")
    print("  Veer is paid in points.")


if __name__ == "__main__":
    main()

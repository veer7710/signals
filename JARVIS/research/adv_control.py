"""Controls that keep the FILL CONVENTION and the GEOMETRY and destroy only
one thing at a time. The E-137/E-151 control destroys the level AND the entry
order type (it enters at market on a random bar). That confounds two things."""
import os, sys, random, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adv_harness as H
from sweep_winrate import pivots


def cand_variant(s, A, SPC, mode, seed=0, pk=5, sweep_atr=0.10, wick=0.6460,
                 buf=0.30, cap=1.2, life=120, jit=0.5):
    """mode: real | jitter | flipdir | fakepivot"""
    rng = random.Random(90000 + seed)
    out = []
    piv = pivots(s, pk)
    if mode == "fakepivot":
        # SAME NUMBER of levels, same time distribution, but the level price is
        # an unrelated bar's close from the same neighbourhood, not a swing.
        piv = [(kb, s.c[max(0, kb - rng.randrange(1, 400))], side) for (kb, _, side) in piv]
    for (kb, px, side) in piv:
        a = A[kb]
        if not a or a <= 0:
            continue
        if mode == "jitter":
            u = rng.uniform(-jit, jit)
            if abs(u) < 0.15:
                u = 0.15 if u >= 0 else -0.15
            px = px + u * a
        t = -side
        if mode == "flipdir":
            t = side
        need = px + side * sweep_atr * a
        sw, ext = None, None
        for k in range(kb + 1, min(kb + life, len(s))):
            if (s.h[k] >= need) if side > 0 else (s.l[k] <= need):
                sw, ext = k, (s.h[k] if side > 0 else s.l[k]); break
        if sw is None:
            continue
        rng2 = s.h[sw] - s.l[sw]
        if (abs(s.c[sw] - s.o[sw]) / rng2 if rng2 > 0 else 1.0) > wick:
            continue
        j = None
        for k in range(sw + 1, min(sw + life, len(s))):
            if (s.h[k] >= px) if -side > 0 else (s.l[k] <= px):
                j = k; break
            ext = max(ext, s.h[k]) if side > 0 else min(ext, s.l[k])
        if j is None:
            continue
        if mode == "flipdir":
            # trade WITH the sweep: stop on the other side, same risk distance
            risk = abs(px - (ext - (-side) * buf * a))
            sl = px - t * risk
        else:
            sl = ext - t * buf * a
        if not (0 < abs(px - sl) <= cap * a):
            continue
        out.append((j, t, px + t * SPC[j] / 2.0, sl, kb, sw))
    out.sort(key=lambda x: x[0])
    return out


def main():
    for tf in ("M1", "M5"):
        s, SP, A, cs = H.ctx(tf)
        SPC = [x * cs for x in SP]
        print()
        H.hdr(f"{tf} — controls that keep the fill convention", 40)
        r = H.simulate(s, SPC, cand_variant(s, A, SPC, "real"))
        H.line("REAL sweep", r, 40)
        H.line("DIRECTION FLIPPED (trade with sweep)",
               H.simulate(s, SPC, cand_variant(s, A, SPC, "flipdir")), 40)
        for name, mode in (("LEVEL JITTERED +-0.5 ATR", "jitter"),
                           ("FAKE LEVEL (old close, same times)", "fakepivot")):
            ms = []
            for sd in range(6):
                rr = H.simulate(s, SPC, cand_variant(s, A, SPC, mode, seed=sd))
                z = H.summ(rr)
                ms.append(z["per"])
                if sd == 0:
                    H.line(f"{name} seed0", rr, 40)
            m = sum(ms) / len(ms)
            se = (sum((x - m) ** 2 for x in ms) / (len(ms) - 1)) ** 0.5 / len(ms) ** 0.5
            real = H.summ(r)["per"]
            print(f"    -> {name}: mean/trade over 6 seeds {m:+.4f} (se {se:.4f}); "
                  f"REAL {real:+.4f}; gap {real-m:+.4f} = {(real-m)/se:.1f} control se")


if __name__ == "__main__":
    main()

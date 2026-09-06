"""Parameter surface: every sweep parameter perturbed, and the NULL floor
(+0.0346 on a driftless walk) drawn in so the reader can see how much of each
cell is artefact."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adv_harness as H

s, SP, A, cs = H.ctx("M1")
SPC = [x * cs for x in SP]
base = dict(pk=5, sweep_atr=0.10, wick=0.6460, buf=0.30, cap=1.2)
GRID = {
    "pk (pivot lookback)": ("pk", [2, 3, 4, 5, 6, 7, 10, 15]),
    "sweep_atr (extension)": ("sweep_atr", [0.0, 0.05, 0.07, 0.10, 0.13, 0.15, 0.25, 0.50]),
    "wick (body/range max)": ("wick", [0.30, 0.45, 0.55, 0.646, 0.75, 0.90, 1.00]),
    "buf (stop buffer ATR)": ("buf", [0.0, 0.15, 0.21, 0.30, 0.39, 0.50, 1.00]),
    "cap (max risk ATR)": ("cap", [0.6, 0.84, 1.0, 1.2, 1.56, 2.0, 5.0]),
}
print(f"  M1 sweep parameter surface. null floor on a driftless walk = +0.0346/trade")
for title, (key, vals) in GRID.items():
    print(f"\n  {title}")
    print(f"    {'value':>8}{'n':>7}{'win%':>8}{'points':>10}{'per trade':>12}{'t':>8}{'excess over null':>18}")
    for v in vals:
        kw = dict(base); kw[key] = v
        r = H.simulate(s, SPC, H.sweep_candidates(s, A, SPC, **kw))
        z = H.summ(r)
        if not z: print(f"    {v:>8}   none"); continue
        star = " <- shipped" if abs(v - base[key]) < 1e-9 else ""
        print(f"    {v:>8}{z['n']:>7}{z['win']:>7.1f}%{z['pts']:>10.1f}"
              f"{z['per']:>+12.4f}{z['t']:>8.2f}{z['per']-0.0346:>+18.4f}{star}")
# give-back
print(f"\n  give-back (exit)")
print(f"    {'value':>8}{'n':>7}{'win%':>8}{'points':>10}{'per trade':>12}{'t':>8}")
c = H.sweep_candidates(s, A, SPC)
for g in (0.05, 0.10, 0.15, 0.25, 0.35, 0.50, 0.75, 0.95):
    z = H.summ(H.simulate(s, SPC, c, give=g))
    print(f"    {g:>8}{z['n']:>7}{z['win']:>7.1f}%{z['pts']:>10.1f}{z['per']:>+12.4f}{z['t']:>8.2f}")
print(f"\n  hold / cooldown")
for hold in (60, 120, 240, 480):
    z = H.summ(H.simulate(s, SPC, c, hold=hold))
    print(f"    hold {hold:>4}  n {z['n']:>5}  {z['per']:+.4f}")
for cd in (0, 5, 30, 120):
    z = H.summ(H.simulate(s, SPC, c, cooldown=cd))
    print(f"    cooldown {cd:>4}  n {z['n']:>5}  {z['per']:+.4f}")

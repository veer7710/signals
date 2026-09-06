import os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adv_harness as H
from adv_fix import sim

s, SP, A, cs = H.ctx("M1")
SPC = [x * cs for x in SP]
print("  M1: does the 'pre-registered ICT wick filter' (E-135d) survive an achievable entry?")
print(f"    {'wick cut':>10}{'n':>7}{'SHIPPED/tr':>13}{'t':>7}{'ACHIEVABLE/tr':>16}{'t':>7}")
for w in (0.30, 0.45, 0.55, 0.646, 0.80, 1.00):
    c = H.sweep_candidates(s, A, SPC, wick=w)
    a = H.summ(sim(s, SPC, c, False, False)); b = H.summ(sim(s, SPC, c, True, True))
    print(f"    {w:>10}{a['n']:>7}{a['per']:>+13.4f}{a['t']:>7.2f}{b['per']:>+16.4f}{b['t']:>7.2f}")
print("\n  M1: the sweep-extension parameter, same question")
print(f"    {'sweep_atr':>10}{'n':>7}{'SHIPPED/tr':>13}{'t':>7}{'ACHIEVABLE/tr':>16}{'t':>7}")
for v in (0.0, 0.05, 0.10, 0.25, 0.50):
    c = H.sweep_candidates(s, A, SPC, sweep_atr=v)
    a = H.summ(sim(s, SPC, c, False, False)); b = H.summ(sim(s, SPC, c, True, True))
    print(f"    {v:>10}{a['n']:>7}{a['per']:>+13.4f}{a['t']:>7.2f}{b['per']:>+16.4f}{b['t']:>7.2f}")
print("\n  M1: pivot lookback")
print(f"    {'pk':>10}{'n':>7}{'SHIPPED/tr':>13}{'t':>7}{'ACHIEVABLE/tr':>16}{'t':>7}")
for v in (3, 5, 10, 15):
    c = H.sweep_candidates(s, A, SPC, pk=v)
    a = H.summ(sim(s, SPC, c, False, False)); b = H.summ(sim(s, SPC, c, True, True))
    print(f"    {v:>10}{a['n']:>7}{a['per']:>+13.4f}{a['t']:>7.2f}{b['per']:>+16.4f}{b['t']:>7.2f}")
print("\n  M1: give-back exit")
c = H.sweep_candidates(s, A, SPC)
print(f"    {'give':>10}{'n':>7}{'SHIPPED/tr':>13}{'t':>7}{'ACHIEVABLE/tr':>16}{'t':>7}")
for g in (0.10, 0.25, 0.50, 0.75):
    a = H.summ(sim(s, SPC, c, False, False, give=g)); b = H.summ(sim(s, SPC, c, True, True, give=g))
    print(f"    {g:>10}{a['n']:>7}{a['per']:>+13.4f}{a['t']:>7.2f}{b['per']:>+16.4f}{b['t']:>7.2f}")

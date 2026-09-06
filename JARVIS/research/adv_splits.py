import os, sys, datetime, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adv_harness as H

def run(tf="M1", **kw):
    s, SP, A, cs = H.ctx(tf)
    SPC = [x * cs for x in SP]
    c = H.sweep_candidates(s, A, SPC, **kw)
    return s, A, H.simulate(s, SPC, c)

for tf in ("M1", "M5"):
    s, A, r = run(tf)
    print()
    H.hdr(f"{tf} SWEEP — splits (shipped cost model)", 30)
    H.line("ALL", r, 30)
    # month
    for m in range(1, 7):
        H.line(f"month 2018-{m:02d}", [x for x in r if datetime.datetime.utcfromtimestamp(x['ts']).month == m], 30)
    # half
    n = len(s)
    H.line("first half of bars (IS)", [x for x in r if x['j'] < n // 2], 30)
    H.line("second half of bars (OOS)", [x for x in r if x['j'] >= n // 2], 30)
    # direction
    H.line("LONG only", [x for x in r if x['d'] > 0], 30)
    H.line("SHORT only", [x for x in r if x['d'] < 0], 30)
    # session (UTC): Asia 23-07, London 07-13, NY 13-21
    def sess(ts):
        h = datetime.datetime.utcfromtimestamp(ts).hour
        if 7 <= h < 13: return "London 07-13"
        if 13 <= h < 21: return "NY 13-21"
        return "Asia/other 21-07"
    for lbl in ("Asia/other 21-07", "London 07-13", "NY 13-21"):
        H.line(lbl, [x for x in r if sess(x['ts']) == lbl], 30)
    # hour buckets
    # volatility regime by ATR at entry, terciles
    av = sorted(A[x['j']] for x in r if A[x['j']])
    q1, q2 = av[len(av)//3], av[2*len(av)//3]
    H.line(f"low vol  (ATR<{q1:.3f})", [x for x in r if A[x['j']] and A[x['j']] < q1], 30)
    H.line(f"mid vol", [x for x in r if A[x['j']] and q1 <= A[x['j']] < q2], 30)
    H.line(f"high vol (ATR>={q2:.3f})", [x for x in r if A[x['j']] and A[x['j']] >= q2], 30)
    # day of week
    for d in range(5):
        nm = ["Mon","Tue","Wed","Thu","Fri"][d]
        H.line(nm, [x for x in r if datetime.datetime.utcfromtimestamp(x['ts']).weekday() == d], 30)

"""
E-116 — THE M1 MICROSTRUCTURE EDGE HUNT.

157,051 real M1 XAUUSD bars built from 18.8M bid/ask ticks (2018-01-01 ..
2018-06-19), each bar carrying its OWN measured spread and its OWN tick count.

THE QUESTION: does ANY mechanism that needs M1 microstructure - tick-count
expansion, spread as a signal, intrabar runs/wicks, minute-resolution session
effects, volatility compression, mean reversion - have a real directional or
non-directional edge on real M1 gold?

METHOD, declared before any number was computed:
  * Signals read bars at or before i. Entry fills at open[i+1].
  * Costs are charged BOTH ENDS from the bar's OWN measured spread_mean.
  * One vote per trade: overlapping occurrences are dropped (busy tracking),
    so n is the number of independent decisions, not the number of bars.
  * Trades that would span a data gap (daily break / weekend) are refused.
  * PHASE A explores on the FIRST HALF only and produces NO verdicts.
  * PHASE B confirms only the Phase A candidates on the HELD-OUT SECOND HALF,
    with two matched random controls, both matched on FILL CONVENTION.
  * Reported: points, pounds per 0.01 lot (0.787 GBP/point), and BOTH the
    repo-mandated "control se" figure AND the honest paired-difference t.

Run: python3 JARVIS/research/m1_edge_hunt.py
"""
from __future__ import annotations
import os, sys, json, math, random, statistics, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
from engine import atr as watr

GBP_PER_POINT = 0.787          # 0.01 lots, per CLAUDE.md E-081
MED_SPREAD_2018 = 0.229        # measured, DATA_QUALITY.md
VOL_RATIO_TODAY = 7.38         # measured M15 ATR growth 2018 -> 2025/26


# --------------------------------------------------------------- data
def load():
    rows = json.load(open("/home/user/signals/data/GOLD_M1_2018.json"))
    rows.sort(key=lambda r: r[0])
    s = engine.Series([r[0] for r in rows], [r[1] for r in rows],
                      [r[2] for r in rows], [r[3] for r in rows],
                      [r[4] for r in rows])
    SP = [r[5] for r in rows]
    TK = [r[7] for r in rows]
    return s, SP, TK


def features(s, SP, TK):
    """All rolling stats. Everything at index i uses bars <= i only."""
    n = len(s)
    A = watr(s, 14)
    rng = [s.h[i] - s.l[i] for i in range(n)]
    body = [s.c[i] - s.o[i] for i in range(n)]
    up_w = [s.h[i] - max(s.o[i], s.c[i]) for i in range(n)]
    dn_w = [min(s.o[i], s.c[i]) - s.l[i] for i in range(n)]
    hour = [datetime.datetime.utcfromtimestamp(t).hour for t in s.ts]

    W = 60
    med_tk = [None]*n; med_sp = [None]*n; med_rg = [None]*n
    for i in range(W, n):
        med_tk[i] = sorted(TK[i-W:i])[W//2]
        med_sp[i] = sorted(SP[i-W:i])[W//2]
        med_rg[i] = sorted(rng[i-W:i])[W//2]

    # z-score of close vs trailing 20 (running sums)
    Z = [None]*n
    M = 20
    ssum = 0.0; ssq = 0.0
    for i in range(n):
        ssum += s.c[i]; ssq += s.c[i]*s.c[i]
        if i >= M:
            ssum -= s.c[i-M]; ssq -= s.c[i-M]*s.c[i-M]
        if i >= M:
            mu = ssum/M
            var = max(ssq/M - mu*mu, 0.0)
            sd = var**0.5
            if sd > 1e-9:
                Z[i] = (s.c[i]-mu)/sd
    # ATR vs its own trailing 500-bar mean (running sum, O(1))
    AR = [None]*n
    L = 500
    acc = 0.0; cnt = 0
    for i in range(n):
        a = A[i]
        if a is None: continue
        acc += a; cnt += 1
        if i-L >= 0 and A[i-L] is not None:
            acc -= A[i-L]; cnt -= 1
        if cnt >= L//2 and acc > 0:
            AR[i] = a/(acc/cnt)
    return dict(A=A, rng=rng, body=body, up_w=up_w, dn_w=dn_w, hour=hour,
                med_tk=med_tk, med_sp=med_sp, med_rg=med_rg, Z=Z, AR=AR)


# ------------------------------------------------------------ execution
def trade_fixed_horizon(s, SP, sigs, H, cost_mult=1.0, lo=0, hi=None):
    """Market entry at open[i+1], flat at close[i+H]. Half-spread both ends,
    from the bar's own measured spread. Non-overlapping. Refuses trades that
    span a data gap."""
    hi = len(s) if hi is None else hi
    out = []
    busy = -1
    for (i, side) in sigs:
        if i <= busy: continue
        j, k = i+1, i+H
        if j < lo or k >= hi: continue
        if s.ts[k] - s.ts[j] != (H-1)*60: continue          # gap / break
        entry = s.o[j] + side*SP[j]*cost_mult/2.0
        exitp = s.c[k] - side*SP[k]*cost_mult/2.0
        out.append(side*(exitp-entry))
        busy = k
    return out


def raw_forward(s, sigs, H, lo=0, hi=None):
    """Zero-cost forward move, non-overlapping. For PHASE A exploration only."""
    return trade_fixed_horizon(s, [0.0]*len(s), sigs, H, 0.0, lo, hi)


def st(pts):
    n = len(pts)
    if n < 2: return None
    m = sum(pts)/n
    sd = (sum((x-m)**2 for x in pts)/(n-1))**0.5
    se = sd/n**0.5
    w = 100.0*sum(1 for x in pts if x > 0)/n
    return dict(n=n, mean=m, sd=sd, se=se, t=(m/se if se > 0 else 0.0),
                win=w, total=sum(pts))


# ------------------------------------------------------------- signals
def build_signals(s, F, TK, SP):
    """Returns {name: (list_of(i,side), description)}. Side is the FOLLOW
    direction; the fade is exactly its negation, so each name is ONE two-sided
    test, not two."""
    n = len(s)
    A, rng, body = F["A"], F["rng"], F["body"]
    up_w, dn_w = F["up_w"], F["dn_w"]
    med_tk, med_sp, med_rg = F["med_tk"], F["med_sp"], F["med_rg"]
    Z, AR, hour = F["Z"], F["AR"], F["hour"]
    sg = {}
    def sgn(x): return 1 if x > 0 else (-1 if x < 0 else 0)

    def add(name, desc, pred, side_fn):
        out = []
        for i in range(520, n-1):
            if A[i] is None or A[i] <= 0: continue
            try:
                if pred(i):
                    sd = side_fn(i)
                    if sd: out.append((i, sd))
            except TypeError:
                continue
        sg[name] = (out, desc)

    # --- 1. TICK COUNT AS A SIGNAL --------------------------------------
    add("tick_burst_3x", "ticks >= 3x trailing-60 median; follow the bar",
        lambda i: med_tk[i] and TK[i] >= 3.0*med_tk[i],
        lambda i: sgn(body[i]))
    add("tick_burst_narrow", "ticks >= 3x median AND range < median range",
        lambda i: med_tk[i] and med_rg[i] and TK[i] >= 3.0*med_tk[i] and rng[i] < med_rg[i],
        lambda i: sgn(body[i]))
    add("tick_drought", "ticks <= 0.4x trailing-60 median; follow the bar",
        lambda i: med_tk[i] and TK[i] <= 0.4*med_tk[i],
        lambda i: sgn(body[i]))
    add("tick_eff_high", "ticks >= 2x median AND range >= 2x median (efficient push)",
        lambda i: med_tk[i] and med_rg[i] and TK[i] >= 2.0*med_tk[i] and rng[i] >= 2.0*med_rg[i],
        lambda i: sgn(body[i]))

    # --- 2. SPREAD AS A SIGNAL ------------------------------------------
    add("spread_spike_2x", "spread >= 2x trailing-60 median; follow the bar",
        lambda i: med_sp[i] and SP[i] >= 2.0*med_sp[i],
        lambda i: sgn(body[i]))
    add("spread_spike_15", "spread >= 1.5x trailing-60 median; follow the bar",
        lambda i: med_sp[i] and SP[i] >= 1.5*med_sp[i],
        lambda i: sgn(body[i]))
    add("spread_tight", "spread <= 0.85x trailing-60 median; follow the bar",
        lambda i: med_sp[i] and SP[i] <= 0.85*med_sp[i],
        lambda i: sgn(body[i]))

    # --- 3. INTRABAR MICROSTRUCTURE -------------------------------------
    add("run3", "3 consecutive higher/lower closes; follow",
        lambda i: (s.c[i] > s.c[i-1] and s.c[i-1] > s.c[i-2] and s.c[i-2] > s.c[i-3])
               or (s.c[i] < s.c[i-1] and s.c[i-1] < s.c[i-2] and s.c[i-2] < s.c[i-3]),
        lambda i: sgn(s.c[i]-s.c[i-3]))
    add("run5", "5 consecutive higher/lower closes; follow",
        lambda i: all(s.c[i-k] > s.c[i-k-1] for k in range(5))
               or all(s.c[i-k] < s.c[i-k-1] for k in range(5)),
        lambda i: sgn(s.c[i]-s.c[i-5]))
    add("wick_reject", "wick >= 2x body AND >= 2x opposite wick; follow rejection",
        lambda i: rng[i] > 0 and (
            (dn_w[i] >= 2*abs(body[i]) and dn_w[i] >= 2*up_w[i]) or
            (up_w[i] >= 2*abs(body[i]) and up_w[i] >= 2*dn_w[i])),
        lambda i: 1 if dn_w[i] > up_w[i] else -1)
    add("range_expand", "range >= 2x prev range and prev >= prev-prev; follow",
        lambda i: rng[i-1] > 0 and rng[i] >= 2.0*rng[i-1] and rng[i-1] >= rng[i-2],
        lambda i: sgn(body[i]))
    add("minute_gap", "|open - prev close| >= 1.0 ATR; follow the gap",
        lambda i: abs(s.o[i]-s.c[i-1]) >= 1.0*A[i-1] if A[i-1] else False,
        lambda i: sgn(s.o[i]-s.c[i-1]))
    add("big_body", "|close-open| >= 2 ATR; follow",
        lambda i: abs(body[i]) >= 2.0*A[i],
        lambda i: sgn(body[i]))

    # --- 6. MEAN REVERSION AT M1 ----------------------------------------
    add("z2_revert", "|z(close, 20)| >= 2; FADE (side = -sign z)",
        lambda i: Z[i] is not None and abs(Z[i]) >= 2.0,
        lambda i: -sgn(Z[i]))
    add("z3_revert", "|z(close, 20)| >= 3; FADE (side = -sign z)",
        lambda i: Z[i] is not None and abs(Z[i]) >= 3.0,
        lambda i: -sgn(Z[i]))

    # --- 5. VOLATILITY COMPRESSION (directional framing) -----------------
    add("compress_follow", "ATR <= 0.7x its 500-bar mean; follow the bar",
        lambda i: AR[i] is not None and AR[i] <= 0.7,
        lambda i: sgn(body[i]))
    return sg


# ------------------------------------------------------------- controls
def control_side(s, SP, sigs, H, cost_mult, lo, hi, seeds=12):
    """SAME entry bars, RANDOM side. Isolates directional information.
    Matched on fill convention (market entry at open[i+1])."""
    ms = []
    for sd_ in range(seeds):
        rng_ = random.Random(9000+sd_)
        r = [(i, rng_.choice((1, -1))) for (i, _) in sigs]
        p = trade_fixed_horizon(s, SP, r, H, cost_mult, lo, hi)
        if len(p) >= 30: ms.append(sum(p)/len(p))
    return ms


def control_time(s, SP, ntrades, H, cost_mult, lo, hi, seeds=12):
    """RANDOM entry bars, RANDOM side, same trade count. Isolates whether the
    TIMING is worth anything. Same fill convention."""
    ms = []
    span = hi-H-2 - (lo+520)
    for sd_ in range(seeds):
        rng_ = random.Random(4000+sd_)
        picks = sorted(rng_.sample(range(lo+520, hi-H-2), min(ntrades*3, span)))
        r = [(i, rng_.choice((1, -1))) for i in picks]
        p = trade_fixed_horizon(s, SP, r, H, cost_mult, lo, hi)
        if len(p) >= 30: ms.append(sum(p)/len(p))
    return ms


def cse(ms):
    if len(ms) < 2: return 0.0, 0.0
    m = sum(ms)/len(ms)
    sd = (sum((x-m)**2 for x in ms)/(len(ms)-1))**0.5
    return m, sd/len(ms)**0.5


# ================================================================ PHASE A
def phase_a(s, SP, TK, F, sg, HALF, HORIZONS):
    """EXPLORATION on the first half only. NO cost, NO verdicts. This stage
    exists to nominate candidates, and it is not evidence of anything."""
    print("="*100)
    print("  PHASE A — EXPLORATION, FIRST HALF ONLY (bars 520..%d), ZERO COST" % HALF)
    print("  Nominates candidates. Produces NO verdicts. Overlaps dropped: n = independent decisions.")
    print("="*100)
    print(f"  {'signal':<22} {'H':>4} {'n':>6} {'mean pts':>10} {'t':>7} {'win%':>7}   description")
    print("  " + "-"*96)
    rows = []
    for name, (sigs, desc) in sg.items():
        for H in HORIZONS:
            pts = raw_forward(s, sigs, H, 520, HALF)
            r = st(pts)
            if not r or r["n"] < 30:
                print(f"  {name:<22} {H:>4} {'<30':>6}   (too few independent decisions)")
                continue
            rows.append((abs(r["t"]), name, H, r))
            print(f"  {name:<22} {H:>4} {r['n']:>6} {r['mean']:>+10.4f} {r['t']:>+7.2f} "
                  f"{r['win']:>6.1f}%   {desc if H==HORIZONS[0] else ''}")
    rows.sort(reverse=True)
    return rows


# =============================================== HYPOTHESIS 4: TIME OF DAY
def hour_blocks(s, SP, cost_mult=1.0, lo=0, hi=None, side=1):
    """One trade per (day, hour): enter at the open of the hour's first bar,
    flat at the close of its last bar. n = independent hour-blocks.
    NOTE the sign trap: the SHORT leg pays the spread too, so a short is
    -(zero-cost move) - spread, NOT the negation of the long's net result."""
    hi = len(s) if hi is None else hi
    blocks = {}
    for i in range(lo, hi):
        t = datetime.datetime.utcfromtimestamp(s.ts[i])
        k = (t.date(), t.hour)
        b = blocks.get(k)
        if b is None: blocks[k] = [i, i]
        else: b[1] = i
    out = {}
    for (d, h), (a, b) in blocks.items():
        if b - a < 50: continue                       # need a near-full hour
        if a+1 > b: continue
        entry = s.o[a] + side*SP[a]*cost_mult/2.0
        exitp = s.c[b] - side*SP[b]*cost_mult/2.0
        out.setdefault(h, []).append(side*(exitp-entry))
    return out


def hour_abs(s, lo=0, hi=None):
    """Realised movement per hour block: mean absolute open->close and mean
    high-low range. The volatility profile, for the non-directional framing."""
    hi = len(s) if hi is None else hi
    blocks = {}
    for i in range(lo, hi):
        t = datetime.datetime.utcfromtimestamp(s.ts[i])
        k = (t.date(), t.hour)
        b = blocks.get(k)
        if b is None: blocks[k] = [i, i]
        else: b[1] = i
    ab, rg = {}, {}
    for (d, h), (a, b) in blocks.items():
        if b - a < 50: continue
        ab.setdefault(h, []).append(abs(s.c[b]-s.o[a]))
        rg.setdefault(h, []).append(max(s.h[a:b+1])-min(s.l[a:b+1]))
    return ab, rg


# ================================= HYPOTHESIS 5: TWO-SIDED BREAKOUT (STRADDLE)
def straddle(s, SP, anchors, BOX, WIN, HOLD, cost_mult=1.0, lo=0, hi=None):
    """Stop-entry two-sided breakout. At anchor i: buy stop at the high of the
    last BOX bars, sell stop at the low. Live for WIN bars.

    FILL CONVENTION (E-110): a stop order is evidenced by the bar's extreme
    reaching it, so the fill bar's own remaining extremes are REFUSED unless
    the bar OPENED beyond the level. Management starts at the next bar.
    TIES LOSE: if both levels are touched inside one bar, we cannot know the
    order, so the trade is recorded as a full box-width loss.
    """
    hi = len(s) if hi is None else hi
    out, busy = [], -1
    for i in anchors:
        if i <= busy or i < lo or i+WIN+HOLD+2 >= hi: continue
        hi_b = max(s.h[i-BOX+1:i+1]); lo_b = min(s.l[i-BOX+1:i+1])
        w = hi_b - lo_b
        if w <= 0: continue
        side = 0; k = None
        for k in range(i+1, i+1+WIN):
            up = s.h[k] >= hi_b; dn = s.l[k] <= lo_b
            if up and dn:
                out.append(-w - SP[k]*cost_mult); busy = k; side = None; break
            if up: side = 1; break
            if dn: side = -1; break
        if side is None: continue
        if not side: continue
        lvl = hi_b if side > 0 else lo_b
        gapped = (side > 0 and s.o[k] >= lvl) or (side < 0 and s.o[k] <= lvl)
        entry = (s.o[k] if gapped else lvl) + side*SP[k]*cost_mult/2.0
        stop = lo_b if side > 0 else hi_b
        start = k if gapped else k+1
        px = None; kk = None
        for kk in range(start, min(start+HOLD, hi)):
            if (side > 0 and s.l[kk] <= stop) or (side < 0 and s.h[kk] >= stop):
                px = stop; break
        if px is None:
            kk = min(start+HOLD-1, hi-1); px = s.c[kk]
        fill = px - side*SP[kk]*cost_mult/2.0
        out.append(side*(fill-entry)); busy = kk
    return out


def cost_mult_for(broker_spread_today):
    """Map a broker spread QUOTED TODAY onto this 2018 sample. Today's M1 ATR is
    ~7.38x 2018's (measured M15 ratio, DATA_QUALITY.md), so a spread of X today
    is worth X/7.38 in 2018 price units. Same convention as E-113."""
    return broker_spread_today / (VOL_RATIO_TODAY * MED_SPREAD_2018)


REGIMES = [("2018 as measured", 1.0),
           ("today @0.46 std ", cost_mult_for(0.46)),
           ("today @0.30     ", cost_mult_for(0.30)),
           ("today @0.20 ECN ", cost_mult_for(0.20)),
           ("ZERO cost       ", 0.0)]


def compare(s, SP, sigs, H, cm, lo, hi, seeds=12):
    """Strategy vs BOTH matched controls, with BOTH the repo-mandated
    control-se figure and the honest difference t."""
    pts = trade_fixed_horizon(s, SP, sigs, H, cm, lo, hi)
    r = st(pts)
    if not r or r["n"] < 30: return None
    ms = control_side(s, SP, sigs, H, cm, lo, hi, seeds)
    mt = control_time(s, SP, r["n"], H, cm, lo, hi, seeds)
    a, ase = cse(ms); b, bse = cse(mt)
    return dict(r=r, side_m=a, side_se=ase, time_m=b, time_se=bse,
                edge_side=r["mean"]-a, edge_time=r["mean"]-b,
                cse_side=(r["mean"]-a)/ase if ase > 0 else 0.0,
                cse_time=(r["mean"]-b)/bse if bse > 0 else 0.0,
                # honest: the strategy estimate's own se dominates the difference
                t_side=(r["mean"]-a)/math.sqrt(r["se"]**2+ase**2),
                t_time=(r["mean"]-b)/math.sqrt(r["se"]**2+bse**2))

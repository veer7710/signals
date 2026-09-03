"""
P92 / E-092 — PINE vs EA SIGNAL PARITY. Never checked in 180 commits.

The claim the whole project rests on is that `XAUUSD_CLEAN_3_7.pine` and
`SuperTrendSniper.mq5` are the same strategy: Veer reads the chart, the EA
trades it, and the backtest measures it. Nothing has ever verified that. This
file does, by re-implementing BOTH sources literally and diffing them bar by
bar on the same candles.

Three separate parity questions, because they fail in different ways:

  Q1 INDICATOR   Does the EA's SuperTrend equal the Pine's?
                 The EA does NOT carry state. `UpdateSuperTrend()` recomputes
                 the whole recursion from a 400-bar warm-up on every closed
                 bar, seeding direction at the oldest bar in that window with
                 `dir = (c > basicUpper) ? -1 : 1`. Pine's ta.supertrend seeds
                 once, at the start of the chart, with `direction := 1`. Two
                 different seeds and two different histories. They agree only
                 if SuperTrend forgets its seed inside 400 bars. That is an
                 assumption, and it is measurable.

  Q2 DEMA        Does the EA's DEMA slope gate equal a Pine DEMA slope?
                 Pine's ta.ema seeds from an SMA of the first n bars. The EA's
                 DEMA() seeds e1 from a SINGLE close, len*3+shift+5 bars back.
                 For len=200 that is 600 bars of warm-up against a decay of
                 k=2/201, so about 1.8% of the seeding error is still in the
                 number. The gate reads a SLOPE over two bars, so the question
                 is not whether the levels match but whether the SIGN does.

  Q3 SIGNAL SET  Does the Pine print the trades the EA takes?
                 This is the one that matters to Veer, because he trades the
                 chart by hand. Reading the two sources side by side:

                   PINE   buy = stDir == -1 and stDir[1] == 1
                          ...and that is the entire condition. There is NO
                          DEMA gate on the Pine signal. `dema` is plotted and
                          used for the SNAP target, and nothing else.
                   EA     flip AND DEMA slope agrees (InpUseDemaFilter=true)
                          AND no opposing >=3.0 ATR candle in the last 3 bars
                          (InpNoFadeAtr=3.0) AND the risk gates pass.

                 If that reading is right the Pine prints a strict SUPERSET of
                 the EA's entries, and every extra one is a BUY or SELL label
                 on Veer's chart that the EA will never take. That is the
                 "the EA does not do what the chart shows" defect the EA's own
                 header warns about, on the EA's own chart.

Run:  python3 JARVIS/research/pine_ea_parity.py
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
from engine import Series, atr as watr


# ---------------------------------------------------------------- PINE side
def pine_ema(vals, n):
    """ta.ema: seeded with the SMA of the first n values, then EMA."""
    out = [None] * len(vals)
    if len(vals) < n:
        return out
    k = 2.0 / (n + 1.0)
    acc = sum(vals[:n]) / n
    out[n - 1] = acc
    for i in range(n, len(vals)):
        acc = vals[i] * k + acc * (1 - k)
        out[i] = acc
    return out


def pine_dema(vals, n):
    """f_dema(src,len) => 2*ta.ema(src,len) - ta.ema(ta.ema(src,len),len)."""
    e1 = pine_ema(vals, n)
    first = next((i for i, v in enumerate(e1) if v is not None), len(e1))
    inner = [v for v in e1[first:]]
    e2p = pine_ema(inner, n)
    e2 = [None] * first + e2p
    return [None if (a is None or b is None) else 2 * a - b
            for a, b in zip(e1, e2)]


def pine_supertrend(s: Series, atr_len=7, mult=1.2):
    """
    ta.supertrend(factor, atrPeriod), transcribed from the published source.
    Seeds `direction := 1` on the first bar with no previous ATR, and carries
    the bands forward for the whole chart. -1 bullish, +1 bearish.
    """
    A = watr(s, atr_len)
    n = len(s)
    d = [0] * n
    ub = [None] * n
    lb = [None] * n
    st = [None] * n
    for i in range(n):
        a = A[i]
        if a is None or a <= 0:
            continue
        mid = (s.h[i] + s.l[i]) / 2.0
        u, l = mid + mult * a, mid - mult * a
        if i == 0 or ub[i - 1] is None:
            ub[i], lb[i] = u, l
            d[i] = 1                      # Pine: na(atr[1]) -> direction := 1
            st[i] = ub[i]
            continue
        pu, pl, pc = ub[i - 1], lb[i - 1], s.c[i - 1]
        lb[i] = l if (l > pl or pc < pl) else pl
        ub[i] = u if (u < pu or pc > pu) else pu
        if st[i - 1] == pu:               # we were riding the UPPER band
            d[i] = -1 if s.c[i] > ub[i] else 1
        else:                             # we were riding the LOWER band
            d[i] = 1 if s.c[i] < lb[i] else -1
        st[i] = lb[i] if d[i] == -1 else ub[i]
    return d


# ------------------------------------------------------------------ EA side
def ea_supertrend_at(s: Series, i: int, atr_len=7, mult=1.2, warm=400):
    """
    UpdateSuperTrend() as written, for ONE closed bar i. Rebuilds the whole
    recursion from `warm` bars of history and seeds at the oldest bar with
    `dir = (c > basicUpper) ? -1 : 1`. Returns (dir, dirPrev) at bar i.

    The EA reads shift 1 as "the last closed bar", so this is called with i
    being that bar. Every value here is a pure function of price history,
    exactly as the MQL5 intends.
    """
    A = watr(s, atr_len)
    start = max(0, i - warm + 1)
    fu = fl = 0.0
    d = dprev = 0
    seeded = False
    for j in range(start, i + 1):
        a = A[j]
        if a is None or a <= 0:
            continue                      # the EA's `continue`, kept verbatim
        mid = (s.h[j] + s.l[j]) / 2.0
        bu, bl = mid + mult * a, mid - mult * a
        if not seeded:
            fu, fl = bu, bl
            d = -1 if s.c[j] > bu else 1
            dprev = d
            seeded = True
            continue
        pu, pl, pc = fu, fl, s.c[j - 1]
        fu = bu if (bu < pu or pc > pu) else pu
        fl = bl if (bl > pl or pc < pl) else pl
        dprev = d
        if d == 1 and s.c[j] > fu:
            d = -1
        elif d == -1 and s.c[j] < fl:
            d = 1
    return (d, dprev) if seeded else (0, 0)


def ea_dema_at(s: Series, i: int, length: int, shift: int):
    """
    DEMA(len, shift) as written: warm-up of len*3+shift+5 bars, e1 and e2 both
    seeded from a SINGLE close at the oldest bar, walked forward to `shift`.
    `shift` counts back from the forming bar, so bar i here is shift 1.
    """
    need = length * 3 + shift + 5
    oldest = i + 1 - need                 # bar index of iClose(need-1) when i is shift 1
    if oldest < 0:
        return None
    k = 2.0 / (length + 1.0)
    e1 = s.c[oldest]
    e2 = e1
    # iClose(shift) counts back from the forming bar; i is shift 1, so shift s
    # is bar index i + 1 - s.
    for sh in range(need - 2, shift - 1, -1):
        c = s.c[i + 1 - sh]
        e1 = c * k + e1 * (1 - k)
        e2 = e1 * k + e2 * (1 - k)
    return 2.0 * e1 - e2


# ------------------------------------------------------------------- report
def hdr(t):
    print("\n" + "=" * 74)
    print("  " + t)
    print("=" * 74)


def run(symbol="GOLD", tf="15m", atr_len=7, mult=1.2, dema_len=200,
        nofade_atr=3.0, nofade_bars=3, warm=400):
    s = engine.load(symbol, tf)
    n = len(s)
    A = watr(s, atr_len)
    print(f"\n{symbol} {tf}: {n} bars")

    # ---- Q1: indicator parity
    pd = pine_supertrend(s, atr_len, mult)
    start = max(warm + 10, dema_len * 3 + 10)
    dis = 0
    checked = 0
    ea_d = [0] * n
    ea_dp = [0] * n
    for i in range(start, n):
        d, dp = ea_supertrend_at(s, i, atr_len, mult, warm)
        ea_d[i], ea_dp[i] = d, dp
        checked += 1
        if d != pd[i]:
            dis += 1
    print(f"  Q1 SuperTrend direction: {dis} of {checked} bars disagree "
          f"({100.0*dis/max(checked,1):.3f}%)")

    # ---- Q2: DEMA slope-sign parity
    pdm = pine_dema(s.c, dema_len)
    slope_dis = 0
    slope_checked = 0
    for i in range(start, n):
        pn, pp = pdm[i], pdm[i - 2]
        if pn is None or pp is None:
            continue
        en = ea_dema_at(s, i, dema_len, 1)
        ep = ea_dema_at(s, i, dema_len, 3)
        if en is None or ep is None:
            continue
        slope_checked += 1
        if (pn > pp) != (en > ep):
            slope_dis += 1
    print(f"  Q2 DEMA slope sign:      {slope_dis} of {slope_checked} bars "
          f"disagree ({100.0*slope_dis/max(slope_checked,1):.3f}%)")

    # ---- Q3: signal-set parity
    pine_sigs = []      # bars where the Pine prints BUY or SELL
    ea_sigs = []        # bars where the EA would enter
    for i in range(start, n):
        pu = pd[i] == -1 and pd[i - 1] == 1
        pdn = pd[i] == 1 and pd[i - 1] == -1
        if pu or pdn:
            pine_sigs.append((i, 1 if pu else -1))

        eu = ea_d[i] == -1 and ea_dp[i] == 1
        edn = ea_d[i] == 1 and ea_dp[i] == -1
        if not (eu or edn):
            continue
        side = 1 if eu else -1
        # DEMA slope gate
        en = ea_dema_at(s, i, dema_len, 1)
        ep = ea_dema_at(s, i, dema_len, 3)
        if en is None or ep is None:
            continue
        if side > 0 and en < ep:
            continue
        if side < 0 and en > ep:
            continue
        # NoFade: refuse a signal against a fresh big candle
        a = A[i]
        blocked = False
        if nofade_atr > 0 and a and a > 0:
            for k in range(1, nofade_bars + 1):
                j = i + 1 - k        # the EA's shift k, with i as shift 1
                if j < 1:
                    break
                rng = s.h[j] - s.l[j]
                if rng < nofade_atr * a:
                    continue
                impdir = 1 if s.c[j] > s.o[j] else -1
                if impdir != side:
                    blocked = True
                    break
        if blocked:
            continue
        ea_sigs.append((i, side))

    pset = {b: sd for b, sd in pine_sigs}
    eset = {b: sd for b, sd in ea_sigs}
    both = [b for b in eset if b in pset and pset[b] == eset[b]]
    ea_only = [b for b in eset if b not in pset or pset[b] != eset[b]]
    pine_only = [b for b in pset if b not in eset]

    print(f"  Q3 signal sets:")
    print(f"       Pine prints          {len(pset):5d} BUY/SELL labels")
    print(f"       EA would enter       {len(eset):5d} times")
    print(f"       on the same bar+side {len(both):5d}")
    print(f"       PINE ONLY (chart says trade, EA does not)  {len(pine_only):5d}"
          f"  = {100.0*len(pine_only)/max(len(pset),1):.1f}% of the chart's labels")
    print(f"       EA ONLY   (EA trades, chart is silent)     {len(ea_only):5d}")
    return s, A, pset, eset, pine_only, both


if __name__ == "__main__":
    hdr("P92 / E-092 — Pine 3.7 vs SuperTrendSniper 2.21, literal transcription")
    for sym, tf in [("GOLD", "15m"), ("GOLD", "1h")]:
        run(sym, tf)

"""
JARVIS backtest engine — dependency-free, deterministic, offline.

Design rules (these are the whole point of the file):
  * NO LOOK-AHEAD. A signal is computed only from bars that have CLOSED.
    Entry always fills at the OPEN of the NEXT bar.
  * COSTS ARE REAL. Every fill is moved against us by half-spread +
    slippage. Commission is charged per round turn.
  * TIES LOSE. If a bar's range contains both the stop and the target we
    cannot know which came first, so we record a LOSS.
  * NOTHING IS FITTED IN HERE. Parameters come from the caller so that
    walk-forward can hold them out.

Everything is pure Python: no pandas, no numpy, no network. The same input
files always produce the same numbers, on any machine, forever.
"""
from __future__ import annotations
import json, math, os, random
from dataclasses import dataclass, field

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")


# ----------------------------------------------------------------- data
@dataclass
class Series:
    ts: list; o: list; h: list; l: list; c: list
    def __len__(self): return len(self.c)


def load(symbol: str, tf: str) -> Series:
    """Load committed candle JSON: [[ts,o,h,l,c], ...]."""
    path = os.path.normpath(os.path.join(DATA_DIR, f"{symbol}_{tf}.json"))
    with open(path) as f:
        rows = json.load(f)
    rows.sort(key=lambda r: r[0])
    # drop exact duplicate timestamps (data vendors repeat bars occasionally)
    out = []
    seen = set()
    for r in rows:
        if r[0] in seen:
            continue
        seen.add(r[0])
        out.append(r)
    return Series([r[0] for r in out], [r[1] for r in out], [r[2] for r in out],
                  [r[3] for r in out], [r[4] for r in out])


def resample(s: Series, factor: int) -> Series:
    """Aggregate `factor` bars into one (e.g. 1h -> 4h with factor=4)."""
    ts, o, h, l, c = [], [], [], [], []
    for i in range(0, len(s) - factor + 1, factor):
        ts.append(s.ts[i]); o.append(s.o[i])
        h.append(max(s.h[i:i + factor])); l.append(min(s.l[i:i + factor]))
        c.append(s.c[i + factor - 1])
    return Series(ts, o, h, l, c)


# ----------------------------------------------------------- indicators
def ema(vals, n):
    k = 2.0 / (n + 1.0)
    out = [None] * len(vals)
    if not vals: return out
    acc = vals[0]; out[0] = acc
    for i in range(1, len(vals)):
        acc = vals[i] * k + acc * (1 - k)
        out[i] = acc
    return out


def _wilder(vals, n):
    """Wilder smoothing == ewm(alpha=1/n)."""
    a = 1.0 / n
    out = [None] * len(vals)
    if not vals: return out
    acc = vals[0]; out[0] = acc
    for i in range(1, len(vals)):
        acc = acc + a * (vals[i] - acc)
        out[i] = acc
    return out


def true_range(s: Series):
    tr = [s.h[0] - s.l[0]]
    for i in range(1, len(s)):
        pc = s.c[i - 1]
        tr.append(max(s.h[i] - s.l[i], abs(s.h[i] - pc), abs(s.l[i] - pc)))
    return tr


def atr(s: Series, n=14):
    return _wilder(true_range(s), n)


def rsi(vals, n=14):
    up, dn = [0.0], [0.0]
    for i in range(1, len(vals)):
        d = vals[i] - vals[i - 1]
        up.append(max(d, 0.0)); dn.append(max(-d, 0.0))
    su, sd = _wilder(up, n), _wilder(dn, n)
    out = []
    for u, d in zip(su, sd):
        out.append(100.0 if d == 0 else 100 - 100 / (1 + u / d))
    return out


def adx_di(s: Series, n=14):
    pdm, mdm = [0.0], [0.0]
    for i in range(1, len(s)):
        up = s.h[i] - s.h[i - 1]
        dn = s.l[i - 1] - s.l[i]
        pdm.append(up if (up > dn and up > 0) else 0.0)
        mdm.append(dn if (dn > up and dn > 0) else 0.0)
    str_ = _wilder(true_range(s), n)
    sp, sm = _wilder(pdm, n), _wilder(mdm, n)
    pdi, mdi, dx = [], [], []
    for i in range(len(s)):
        t = str_[i] or 1e-12
        p = 100 * sp[i] / t; m = 100 * sm[i] / t
        pdi.append(p); mdi.append(m)
        tot = p + m
        dx.append(0.0 if tot == 0 else 100 * abs(p - m) / tot)
    return _wilder(dx, n), pdi, mdi


def rolling_max(vals, n):
    out = [None] * len(vals)
    for i in range(n - 1, len(vals)):
        out[i] = max(vals[i - n + 1:i + 1])
    return out


def rolling_min(vals, n):
    out = [None] * len(vals)
    for i in range(n - 1, len(vals)):
        out[i] = min(vals[i - n + 1:i + 1])
    return out


def rolling_median(vals, n):
    out = [None] * len(vals)
    for i in range(n - 1, len(vals)):
        w = sorted(v for v in vals[i - n + 1:i + 1] if v is not None)
        if w: out[i] = w[len(w) // 2]
    return out


# ------------------------------------------------------------- costs
@dataclass
class Costs:
    """All in PRICE units of the instrument, except commission (account ccy)."""
    spread: float = 0.30          # gold: ~30 cents typical retail
    slippage: float = 0.05        # per fill, adverse
    commission_per_lot: float = 7.0   # round turn, per 1.00 lot
    value_per_point_per_lot: float = 100.0  # gold: 1.00 price move x 1 lot = $100


# ------------------------------------------------------------- trade
@dataclass
class Trade:
    ts_in: int; ts_out: int; side: int
    entry: float; exit: float; stop: float; target: float
    r: float; reason: str; meta: dict = field(default_factory=dict)


# --------------------------------------------------------- backtester
def backtest(s: Series, signal_fn, costs: Costs, warmup: int = 250,
             max_bars: int = 200, allow_shorts: bool = True,
             one_at_a_time: bool = True) -> list:
    """
    signal_fn(ctx, i) -> None, or dict(side=+-1, stop=<price>, target=<price>)
    evaluated using data up to and including bar i. Fill is bar i+1's open.
    """
    ctx = build_context(s)
    trades = []
    pos = None
    half = costs.spread / 2.0

    for i in range(warmup, len(s) - 1):
        if pos is not None:
            # ---- manage the open position on bar i
            hit_stop = s.l[i] <= pos["stop"] if pos["side"] == 1 else s.h[i] >= pos["stop"]
            hit_tgt = s.h[i] >= pos["target"] if pos["side"] == 1 else s.l[i] <= pos["target"]
            aged = (i - pos["i_in"]) >= max_bars
            exit_px = reason = None
            if hit_stop:                      # TIES LOSE: stop checked first
                exit_px, reason = pos["stop"], "stop"
            elif hit_tgt:
                exit_px, reason = pos["target"], "target"
            elif aged:
                exit_px, reason = s.c[i], "time"
            if exit_px is not None:
                # exit fill moved against us
                fill = exit_px - pos["side"] * (half + costs.slippage)
                risk = abs(pos["entry"] - pos["stop"])
                gross = (fill - pos["entry"]) * pos["side"]
                # commission expressed in price units for a 1-lot-equivalent
                comm_px = costs.commission_per_lot / costs.value_per_point_per_lot
                r = (gross - comm_px) / risk if risk > 0 else 0.0
                trades.append(Trade(s.ts[pos["i_in"]], s.ts[i], pos["side"],
                                    pos["entry"], fill, pos["stop"], pos["target"],
                                    r, reason, pos.get("meta", {})))
                pos = None
            if pos is not None or one_at_a_time:
                if pos is not None:
                    continue

        sig = signal_fn(ctx, i)
        if not sig:
            continue
        if sig["side"] == -1 and not allow_shorts:
            continue
        side = sig["side"]
        raw = s.o[i + 1]
        entry = raw + side * (half + costs.slippage)   # entry fill against us
        stop, target = sig["stop"], sig["target"]
        # a signal whose stop is already violated by the fill is unusable
        if (side == 1 and stop >= entry) or (side == -1 and stop <= entry):
            continue
        pos = {"side": side, "entry": entry, "stop": stop, "target": target,
               "i_in": i + 1, "meta": sig.get("meta", {})}
    return trades


def build_context(s: Series) -> dict:
    """Precompute every indicator once; strategies read from here."""
    a = atr(s, 14)
    adx, pdi, mdi = adx_di(s, 14)
    return {
        "s": s, "atr": a, "atr_med": rolling_median(a, 50),
        "adx": adx, "pdi": pdi, "mdi": mdi, "rsi": rsi(s.c, 14),
        "ema9": ema(s.c, 9), "ema21": ema(s.c, 21), "ema50": ema(s.c, 50),
        "ema20": ema(s.c, 20), "ema100": ema(s.c, 100), "ema200": ema(s.c, 200),
        "don_hi": rolling_max(s.h, 55), "don_lo": rolling_min(s.l, 55),
    }


# ------------------------------------------------------------- stats
def equity_curve(trades, start=10000.0, risk_pct=0.005):
    """Compound: each trade risks risk_pct of CURRENT equity."""
    eq = start; curve = [start]
    for t in sorted(trades, key=lambda x: x.ts_out):
        eq += eq * risk_pct * t.r
        curve.append(eq)
    return curve


def max_drawdown(curve):
    peak = curve[0]; mdd = 0.0
    for e in curve:
        peak = max(peak, e)
        mdd = max(mdd, (peak - e) / peak if peak > 0 else 0)
    return mdd


def stats(trades, start=10000.0, risk_pct=0.005) -> dict:
    n = len(trades)
    if n == 0:
        return {"n": 0}
    rs = [t.r for t in trades]
    wins = [r for r in rs if r > 0]; losses = [r for r in rs if r <= 0]
    gp = sum(wins); gl = abs(sum(losses))
    curve = equity_curve(trades, start, risk_pct)
    mean = sum(rs) / n
    var = sum((r - mean) ** 2 for r in rs) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(var)
    streak = worst = 0
    for r in rs:
        streak = streak + 1 if r <= 0 else 0
        worst = max(worst, streak)
    return {
        "n": n,
        "win_rate": len(wins) / n,
        "profit_factor": (gp / gl) if gl > 0 else float("inf"),
        "expectancy_R": mean,
        "sd_R": sd,
        # t-statistic of expectancy vs zero: is the mean R distinguishable from 0?
        "t_stat": (mean / (sd / math.sqrt(n))) if sd > 0 else 0.0,
        "avg_win_R": (sum(wins) / len(wins)) if wins else 0.0,
        "avg_loss_R": (sum(losses) / len(losses)) if losses else 0.0,
        "max_dd": max_drawdown(curve),
        "end_equity": curve[-1],
        "return_pct": curve[-1] / start - 1.0,
        "worst_losing_streak": worst,
        "total_R": sum(rs),
    }


def fmt(st: dict) -> str:
    if st.get("n", 0) == 0:
        return "  no trades"
    return (f"  trades {st['n']:<5} win {100*st['win_rate']:>5.1f}%   "
            f"PF {st['profit_factor']:>5.2f}   exp {st['expectancy_R']:+.3f}R   "
            f"t {st['t_stat']:+.2f}\n"
            f"  totalR {st['total_R']:+.1f}   maxDD {100*st['max_dd']:>5.1f}%   "
            f"ret {100*st['return_pct']:+.1f}%   worst streak {st['worst_losing_streak']}")


# ------------------------------------------------------- walk-forward
def walk_forward(s: Series, make_fn, costs, folds=6, **kw):
    """Split chronologically and report each fold separately.

    `make_fn` is a FACTORY: make_fn(sub_series) -> signal_fn. It must be a
    factory, not a prebuilt signal function, because strategies precompute
    per-series state (higher-timeframe gates, swing pivots) indexed by bar
    position. Handing a strategy built on the full series a SLICE to trade
    makes bar index i mean two different bars, which silently produces
    garbage (see FAILURE_LOG entry F-001). test_engine.py guards this.

    This does not tune anything — it shows whether the SAME rules hold up
    across different, non-overlapping periods. A strategy that only works
    in one fold is a strategy that only works in one market regime.
    """
    out = []
    step = len(s) // folds
    for f in range(folds):
        lo, hi = f * step, (f + 1) * step if f < folds - 1 else len(s)
        sub = Series(s.ts[lo:hi], s.o[lo:hi], s.h[lo:hi], s.l[lo:hi], s.c[lo:hi])
        if len(sub) < 400:
            continue
        tr = backtest(sub, make_fn(sub), costs, **kw)
        out.append((sub.ts[0], sub.ts[-1], stats(tr), tr))
    return out


# -------------------------------------------------------- monte carlo
def monte_carlo(trades, trials=20000, risk_pct=0.005, seed=11):
    """Bootstrap the trade ORDER to get a drawdown distribution and a
    probability of losing a given fraction of the account."""
    if not trades:
        return {}
    rng = random.Random(seed)
    rs = [t.r for t in trades]
    dds, ends, ruin30, ruin50 = [], [], 0, 0
    for _ in range(trials):
        seq = [rs[rng.randrange(len(rs))] for _ in range(len(rs))]
        eq = 1.0; peak = 1.0; mdd = 0.0
        for r in seq:
            eq += eq * risk_pct * r
            peak = max(peak, eq)
            mdd = max(mdd, (peak - eq) / peak)
        dds.append(mdd); ends.append(eq)
        if mdd >= 0.30: ruin30 += 1
        if mdd >= 0.50: ruin50 += 1
    dds.sort(); ends.sort()
    q = lambda a, p: a[int(p * (len(a) - 1))]
    return {
        "median_dd": q(dds, .5), "dd_95": q(dds, .95),
        "median_end": q(ends, .5), "end_05": q(ends, .05), "end_95": q(ends, .95),
        "p_dd_over_30pct": ruin30 / trials,
        "p_dd_over_50pct": ruin50 / trials,
        "p_losing_overall": sum(1 for e in ends if e < 1.0) / trials,
    }


# ---------------------------------------------------------------------------
# E-151. THE GIVE-BACK TRAIL, WITH THE FILL THAT IS ACTUALLY AVAILABLE.
#
# Every give-back trail in this repo used to be written inline, three lines at
# a time, in twelve different files - and all twelve had the same defect. The
# trail level is derived from the CURRENT bar's extreme, so it cannot exist
# until that bar has closed. If price has already gone past it by then, no
# order could have been resting there, and filling at it books the bar's own
# favourable extreme. The tell was that the "best" give-back ran to the
# tightest value in every range tested, on every signal, on every clock: a
# parameter monotone to the edge of what you tried is a leak, not an optimum.
#
# This is the only give-back trail. Import it. Do not write another one.
# ---------------------------------------------------------------------------
def trail_level(entry, sl, peak, close_k, d, give):
    """New stop after bar k closes, or None meaning EXIT AT close_k NOW.

    entry/sl/peak in price, d = +1 long / -1 short, give = fraction of the
    best excursion handed back.
    """
    up = d * (peak - entry)
    if up <= 0:
        return sl
    return trail_apply(sl, entry + d * up * (1.0 - give), close_k, d)


def trail_apply(sl, c, close_k, d):
    """Ratchet sl to the candidate level c, or None if c is unplaceable.

    Any trail - give-back, ATR, chandelier - has to pass through here. The one
    rule: a stop on the far side of the close cannot be sent to a broker and
    must never be filled in a backtest.
    """
    if d * (c - close_k) >= 0:      # the level is behind price: unplaceable
        return None                 # -> the honest exit is this bar's close
    return max(sl, c) if d > 0 else min(sl, c)


# ---------------------------------------------------------------------------
# E-165. THE ENTRY FILL, WITH THE PRICE ACTUALLY AVAILABLE.
#
# The exit-side version of this bug (E-151) cost three signals their status.
# The entry-side version cost the fourth - the sweep, the one thing left
# standing - and it was in the repo the whole time, one step earlier in the
# same trade.
#
# A stop order resting at `level` only fills AT `level` if the market is still
# on the far side when the bar opens. The sweep bar is REQUIRED to be a wick:
# it pokes through the level and closes back. So on 75-79% of setups the next
# bar opens past the level, no order can be resting there any more, and the
# fill is the open - which is worse, every time.
#
# Booking the level anyway extracts +0.0226 a trade from a DRIFTLESS RANDOM
# WALK at t = 5. Nothing real does that.
# ---------------------------------------------------------------------------
def entry_fill(level, open_k, d):
    """Where a stop order at `level` actually fills on bar k, or None if the
    trade is gone.

    d = +1 for a long (triggered by price rising to `level`), -1 for a short.
    Returns the open when the bar has already opened past the trigger - the
    price you would really get. Never returns something better than `level`.
    """
    if d * (open_k - level) > 0:      # already past: the stop fires at the open
        return open_k
    return level


# ---------------------------------------------------------------------------
# E-194-RT. THE EXIT-SIDE TWIN OF entry_fill(), WHICH WAS MISSING FOR NINE
# EXPERIMENTS.
#
# entry_fill() above has been in this file since E-165 and every study imports
# it. Its mirror image never got written, so every backtest here has booked
# STOP exits at the stop price even when the bar opened past it - a gap, a
# news spike, a session open. That is the same defect as E-151 and E-165, one
# layer further down the same trade, and it flatters every loser.
#
# A protective stop resting at `level` fills AT `level` only if the market is
# still on the near side when the bar opens. If the bar opens beyond it, the
# fill is the open and it is worse, always.
# ---------------------------------------------------------------------------
def stop_fill(level, open_k, d):
    """Where a protective stop at `level` actually fills on bar k.

    d = +1 for a long (the stop is BELOW, triggered by price falling to it),
    -1 for a short. Returns the open when the bar has already gapped past the
    stop. Never returns something better than `level`.
    """
    if d * (open_k - level) < 0:      # already past: the stop fires at the open
        return open_k
    return level


# ---------------------------------------------------------------------------
# E-173. THE COST SCALE, WHICH WAS WRONG ON EVERY CLOCK BUT M1.
#
# Cost was computed as  cs = 0.11 / (median_spread / median_ATR)  and then
# re-derived FOR EACH TIMEFRAME. That forces spread/ATR to 0.11 everywhere -
# which is exactly backwards, because the spread is a fixed PRICE and a slower
# clock's larger ATR is precisely what makes it cheaper. Forcing the ratio
# charged M5 2.5x and M15 4.6x what they actually pay:
#
#     tf   med spread   med ATR   sp/ATR      cs   CHARGED
#     M1       0.2294    0.2463    0.932   0.118    0.0271   <- correct
#     M5       0.2283    0.6126    0.373   0.295    0.0674   <- 2.5x too much
#    M15       0.2278    1.1448    0.199   0.553    0.1259   <- 4.6x too much
#
# The right model: pick the spread you actually pay TODAY, express it in the
# file's price units, and charge that same PRICE on every clock. Calibrated on
# M1 once, applied everywhere.
# ---------------------------------------------------------------------------
COST_M1_SPREAD_ATR = 0.11      # today's M1 spread as a fraction of M1 ATR (E-132)

# Measured on data/GOLD_M1_2018.json: median spread 0.2294 / median ATR(14)
# 0.2463 -> 0.931644. test_engine.py re-measures it on every run, so if the
# data file is ever replaced the constant cannot drift silently.
M1_SPREAD_ATR = 0.931644


def cost_scale(spread_series, atr_series, m1_ratio=M1_SPREAD_ATR):
    """Scale factor so that `spread * scale` is the cost ACTUALLY paid.

    `m1_ratio` defaults to the measured M1 spread/ATR, which is what makes the
    charge a fixed PRICE on every clock. Pass None to re-derive it from the
    series given - which is the E-173 bug and is only correct for M1 itself.
    """
    va = sorted(x for x in atr_series[100:] if x)
    med_atr = va[len(va) // 2]
    med_sp = sorted(spread_series)[len(spread_series) // 2]
    ratio = m1_ratio if m1_ratio is not None else (med_sp / med_atr)
    return COST_M1_SPREAD_ATR / ratio

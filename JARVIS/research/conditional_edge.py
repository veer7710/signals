"""
IS THERE A *CONDITIONAL* EDGE INSIDE AN UNCONDITIONALLY RANDOM WALK?

E-037 ran 40 Lo-MacKinlay variance-ratio tests across 4 markets x 2 timeframes
x 5 horizons and not one was significant. But a variance ratio measures
UNCONDITIONAL behaviour: it averages over every bar. An edge that only exists
in a specific state - a specific hour, the bars after a shock, the bars after a
gap - would be diluted to nothing by that average and would look exactly like
what E-037 saw.

FALSIFIABLE HYPOTHESIS
  H: There exists an observable state S, computable from closed bars only, such
     that the mean forward return over the next N bars conditional on S differs
     from the mean forward return outside S by more than multiple-testing noise.
  Mechanism claimed for each state is stated in STATES below.

WHAT IS TESTED (five state families, as directed)
  1. hour of day (UTC) and day of week
  2. the N bars after a bar whose range exceeds k x ATR (shock)
  3. the N bars after a gap between one bar's close and the next bar's open
  4. after a run of same-direction closes, and after a run of inside bars
  5. the TRANSITION from low to high volatility, contrasted with the LEVEL

METHOD
  * Every state is computed from bars at or before i. The forward window starts
    at the OPEN of bar i+1 - the same fill the engine uses - and ends at the
    CLOSE of bar i+N. Nothing reads a bar it could not have seen.
  * Primary statistic: OLS of forward return on a state dummy with a
    Newey-West HAC standard error. Overlapping forward windows make plain iid
    standard errors far too small; the self-test below prints exactly how much
    too small.
  * Time-of-day families use a circular-rotation permutation test on the
    max |t| across all 24 hours / all weekdays. That controls the family-wise
    error rate for those families exactly, rather than by Bonferroni.
  * Chronological 70/30 split. Everything is measured on both halves in one
    pass; the out-of-sample half is never used to choose anything.
  * Effect sizes are reported against the per-symbol round-trip cost from
    study.COSTS. NEVER engine.Costs() - that default is gold-shaped and
    charging it to FX has corrupted results here before (E-033).

Run:  python3 JARVIS/research/conditional_edge.py            (self-test + full)
      python3 JARVIS/research/conditional_edge.py --selftest (statistics only)
"""
from __future__ import annotations
import os, sys, math, datetime as dt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study

RNG = np.random.default_rng(20260831)
VR_BAR5 = 2.77   # set by the self-test: empirical 95th pct of |z| under a
VR_BAR1 = 4.97   # true random walk with fully overlapping forward windows

SERIES = [(sym, tf) for sym in ("GOLD", "US500", "EURUSD", "GBPUSD")
          for tf in ("15m", "1h")]
HORIZONS = (1, 5, 20)
REPO_T = 3.65          # multiple-testing bar used throughout this repo (E-012)


def bandwidth(N):
    """Newey-West lag for a forward horizon of N bars.

    N-1 lags come from the overlap of the forward windows, but that alone is
    NOT enough: real states (high volatility, a session, a run of closes) are
    CLUSTERED in time, and a clustered regressor leaves residual dependence far
    beyond the overlap. At lag = N the self-test measures 10% rejection under a
    true null. N + 20 brings it to 5-8% across state persistence from 1 to 120
    bars, with power essentially unchanged. Calibrated, not guessed.
    """
    return N + 20


# ===================================================================== stats
def hac_beta_t(y, d, lag):
    """OLS  y = a + b*d  with a Newey-West HAC standard error on b.

    y and d must be in TIME ORDER over a contiguous series - that is why every
    test below keeps the full series and puts 0 in d for out-of-state bars,
    rather than subsetting (subsetting destroys the lag structure HAC needs).
    Returns (b, t, n).
    """
    y = np.asarray(y, float); d = np.asarray(d, float)
    n = y.size
    X = np.column_stack([np.ones(n), d])
    XtX = X.T @ X
    if np.linalg.matrix_rank(XtX) < 2:
        return 0.0, 0.0, n
    XtXi = np.linalg.inv(XtX)
    beta = XtXi @ (X.T @ y)
    e = y - X @ beta
    u = X * e[:, None]
    S = u.T @ u
    for L in range(1, int(lag) + 1):
        w = 1.0 - L / (lag + 1.0)
        G = u[L:].T @ u[:-L]
        S += w * (G + G.T)
    V = XtXi @ S @ XtXi
    v = V[1, 1]
    if not np.isfinite(v) or v <= 0:
        return float(beta[1]), 0.0, n
    return float(beta[1]), float(beta[1] / math.sqrt(v)), n


def iid_beta_t(y, d):
    """Same regression with the NAIVE iid standard error. Only used in the
    self-test, to show how badly overlapping windows inflate it."""
    y = np.asarray(y, float); d = np.asarray(d, float)
    n = y.size
    X = np.column_stack([np.ones(n), d])
    XtXi = np.linalg.inv(X.T @ X)
    beta = XtXi @ (X.T @ y)
    e = y - X @ beta
    s2 = (e @ e) / (n - 2)
    se = math.sqrt(s2 * XtXi[1, 1])
    return float(beta[1]), float(beta[1] / se)


def cond_vr(paths, block=None):
    """Conditional variance ratio of the post-state path.

    `paths` is an (m, N) array of the N one-bar log returns that FOLLOW each of
    m occurrences of a state. VR = Var(row sums) / (N * Var(all elements)).
    Under a random walk VR = 1; >1 means the post-state path trends, <1 means it
    reverses.

    Standard error by MOVING-BLOCK bootstrap over occurrences. A plain
    row-wise bootstrap is wrong here: a state like "high volatility" fires on
    hundreds of ADJACENT bars, so its N-bar forward windows overlap almost
    completely and are nowhere near independent. Resampling single rows would
    treat 900 overlapping windows as 900 independent observations and inflate
    every z. The self-test below measures this directly. Returns (vr, z, m).
    """
    paths = np.asarray(paths, float)
    m, N = paths.shape
    if m < 30 or N < 2:
        return None, None, m
    if block is None:
        block = max(2, 4 * int(N))
    block = min(block, m)

    def _vr(P):
        v1 = P.reshape(-1).var(ddof=1)
        if v1 <= 0:
            return np.nan
        return P.sum(axis=1).var(ddof=1) / (N * v1)

    vr = _vr(paths)
    nblk = int(math.ceil(m / block))
    boots = np.empty(400)
    for b in range(400):
        starts = RNG.integers(0, m - block + 1, nblk)
        idx = (starts[:, None] + np.arange(block)[None, :]).reshape(-1)[:m]
        boots[b] = _vr(paths[idx])
    sd = np.nanstd(boots, ddof=1)
    z = (vr - 1.0) / sd if sd > 0 else 0.0
    return float(vr), float(z), m


def rotation_pvalue(y, labels, lag, n_perm=400):
    """Family-wise test for a categorical state (hour, weekday).

    Statistic: max over categories of |HAC t| for that category vs the rest.
    Null: circularly rotate y by a random offset. Rotation preserves the entire
    autocorrelation structure of y and destroys only its alignment with the
    labels, so it is the right null for "does this label carry information".
    Returns (observed max|t|, best category, p-value, per-category t dict).
    """
    y = np.asarray(y, float)
    cats = np.unique(labels)
    ts = {}
    for c in cats:
        d = (labels == c).astype(float)
        if d.sum() < 30 or d.sum() > y.size - 30:
            continue
        _, t, _ = hac_beta_t(y, d, lag)
        ts[int(c)] = t
    if not ts:
        return 0.0, None, 1.0, {}
    obs = max(abs(v) for v in ts.values())
    best = max(ts, key=lambda k: abs(ts[k]))
    n = y.size
    worse = 0
    for _ in range(n_perm):
        k = int(RNG.integers(1, n))
        yr = np.roll(y, k)
        mx = 0.0
        for c in cats:
            d = (labels == c).astype(float)
            if d.sum() < 30 or d.sum() > n - 30:
                continue
            _, t, _ = hac_beta_t(yr, d, lag)
            mx = max(mx, abs(t))
        if mx >= obs:
            worse += 1
    return obs, best, (worse + 1) / (n_perm + 1), ts


# ================================================================ self-test
def selftest():
    print("=" * 74)
    print("  SELF-TEST — every statistic against synthetic data of KNOWN")
    print("  behaviour, before one byte of market data is read.")
    print("=" * 74)
    ok = True
    rng = np.random.default_rng(7)

    # ---- 1. HAC size on a random walk with NO conditional effect.
    #         Real states are CLUSTERED in time (a volatility regime, a
    #         session, a run of closes). A clustered regressor is where a naive
    #         iid standard error breaks, so size is measured against state
    #         persistence from 1 bar to 120 bars.
    N = 5
    reps = 200
    print(f"\n1. SIZE on a random walk with NO conditional effect ({reps} reps,"
          f" horizon {N}, HAC lag {bandwidth(N)}):")
    sizes = []
    for blk in (1, 10, 30, 60, 120):
        rej_hac = rej_iid = 0
        for _ in range(reps):
            r = rng.normal(0, 1e-3, 3000)
            c = np.exp(np.cumsum(r))
            y = np.log(c[N:] / c[:-N])          # overlapping forward returns
            if blk == 1:
                d = (rng.random(y.size) < 0.2).astype(float)
            else:
                z = np.convolve(rng.normal(0, 1, y.size + 2 * blk),
                                np.ones(blk) / blk, mode="same")[:y.size]
                d = (z > np.quantile(z, 0.8)).astype(float)
            _, t, _ = hac_beta_t(y, d, bandwidth(N))
            _, ti = iid_beta_t(y, d)
            rej_hac += abs(t) > 1.96
            rej_iid += abs(ti) > 1.96
        sizes.append(rej_hac / reps)
        print(f"   state persistence {blk:>4} bars: HAC rejects {rej_hac/reps:6.1%}"
              f"   naive iid rejects {rej_iid/reps:6.1%}   (nominal 5%)")
    good = all(0.01 <= x <= 0.10 for x in sizes)
    ok &= good
    print(f"   -> {'PASS' if good else 'FAIL'}. Worst residual size {max(sizes):.1%}"
          f" > 5% nominal, so reported |t| are if anything slightly TOO"
          f" generous — which can only help a positive finding, never a negative one.")

    # ---- 2. HAC power: plant a real conditional drift, it must be found.
    r = rng.normal(0, 1e-3, 20000)
    state = rng.random(r.size) < 0.15
    for i in np.flatnonzero(state):
        r[i + 1:i + 1 + N] += 3e-4                    # drift only after state
    c = np.exp(np.cumsum(r))
    y = np.log(c[N:] / c[:-N])
    d = state[:y.size].astype(float)
    b, t, _ = hac_beta_t(y, d, bandwidth(N))
    print(f"\n2. POWER, planted +3e-4 per bar for {N} bars after the state:")
    print(f"   recovered beta {b:+.6f} (true {N*3e-4:+.6f})   t {t:+.2f}")
    good = t > 5 and abs(b - N * 3e-4) < N * 3e-4 * 0.5
    ok &= good
    print(f"   -> {'PASS' if good else 'FAIL'}")

    # ---- 3. HAC sign: planted NEGATIVE drift must come back negative.
    r = rng.normal(0, 1e-3, 20000)
    state = rng.random(r.size) < 0.15
    for i in np.flatnonzero(state):
        r[i + 1:i + 1 + N] -= 3e-4
    c = np.exp(np.cumsum(r))
    y = np.log(c[N:] / c[:-N])
    b, t, _ = hac_beta_t(y, state[:y.size].astype(float), bandwidth(N))
    print(f"\n3. SIGN, planted -3e-4: beta {b:+.6f}  t {t:+.2f}")
    good = t < -5 and b < 0
    ok &= good
    print(f"   -> {'PASS' if good else 'FAIL'}")

    # ---- 4. Conditional variance ratio on paths of known behaviour.
    m, NN = 800, 8
    rw = rng.normal(0, 1e-3, (m, NN))
    vr_rw, z_rw, _ = cond_vr(rw)
    # trending: an AR(1)-style persistent component added to each path
    e = rng.normal(0, 1e-3, (m, NN))
    trend = e + rng.normal(0, 1e-3, (m, 1))       # common per-path drift
    vr_tr, z_tr, _ = cond_vr(trend)
    # reverting: MA(1) with a negative coefficient - each move partly undone
    e2 = rng.normal(0, 1e-3, (m, NN + 1))
    rev = e2[:, 1:] - 0.8 * e2[:, :-1]
    vr_rv, z_rv, _ = cond_vr(rev)
    print(f"\n4. CONDITIONAL VARIANCE RATIO on synthetic paths:")
    print(f"   random walk paths : VR {vr_rw:.3f}  z {z_rw:+.2f}   (want ~1.00)")
    print(f"   trending  paths   : VR {vr_tr:.3f}  z {z_tr:+.2f}   (want > 1)")
    print(f"   reverting paths   : VR {vr_rv:.3f}  z {z_rv:+.2f}   (want < 1)")
    good = abs(vr_rw - 1) < 0.15 and vr_tr > 1.2 and vr_rv < 0.8
    ok &= good
    print(f"   -> {'PASS' if good else 'FAIL'}")

    # ---- 4b. cond_vr SIZE on MAXIMALLY OVERLAPPING windows from a random
    #          walk. This is the case that matters: states like "high
    #          volatility" fire on adjacent bars, so their forward windows
    #          overlap almost completely. A correct z rejects ~5% of the time.
    NN2 = 20
    rej_blk = rej_row = 0
    reps2 = 100
    for _ in range(reps2):
        r = rng.normal(0, 1e-3, 1200)
        P = np.lib.stride_tricks.sliding_window_view(r, NN2)[:1000]
        _, zb, _ = cond_vr(P)                       # block bootstrap
        _, zr, _ = cond_vr(P, block=1)              # row-wise (the wrong one)
        rej_blk += abs(zb) > 1.96
        rej_row += abs(zr) > 1.96
    print(f"\n4b. CONDITIONAL VR SIZE on {reps2} random walks, fully overlapping"
          f" windows (block = 4N):")
    print(f"   moving-block bootstrap z rejects {rej_blk/reps2:6.1%}   (nominal 5%)")
    print(f"   row-wise    bootstrap z rejects {rej_row/reps2:6.1%}   "
          f"(WRONG - overlap treated as independent)")
    zs = []
    for _ in range(300):
        r = rng.normal(0, 1e-3, 1200)
        P = np.lib.stride_tricks.sliding_window_view(r, NN2)[:1000]
        _, z, _ = cond_vr(P)
        zs.append(abs(z))
    zs = np.array(zs)
    global VR_BAR5, VR_BAR1
    VR_BAR5 = float(np.quantile(zs, 0.95)); VR_BAR1 = float(np.quantile(zs, 0.99))
    print(f"   even with blocks the z over-rejects, so the bar is CALIBRATED"
          f" empirically, not assumed:")
    print(f"   null |z| under a true random walk: 95th pct {VR_BAR5:.2f},"
          f" 99th pct {VR_BAR1:.2f}  -- NOT 1.96")
    good = rej_row / reps2 > rej_blk / reps2 and VR_BAR5 > 1.96
    ok &= good
    print(f"   -> {'PASS' if good else 'FAIL'}")

    # ---- 5. Rotation permutation test: size, then power.
    #         y[j] = r[j+1], so the hour label that belongs to y[j] is the hour
    #         of bar j+1. Getting this alignment wrong made the first run of
    #         this self-test report hour 8 for a drift planted at hour 9 — the
    #         statistic was right and the test data was wrong. Aligned here.
    n = 6000
    r = rng.normal(0, 1e-3, n)
    hr = np.arange(n) % 24
    c = np.exp(np.cumsum(r))
    y = np.log(c[1:] / c[:-1])
    hours = hr[1:]
    obs, best, p, _ = rotation_pvalue(y, hours, bandwidth(1), n_perm=200)
    print(f"\n5a. ROTATION TEST, no hour effect: max|t| {obs:.2f} at hour {best},"
          f" p = {p:.3f}  (want p > 0.05)")
    good_a = p > 0.05
    r2 = r.copy()
    r2[hr == 9] += 1.2e-3                              # hour 9 really drifts up
    c2 = np.exp(np.cumsum(r2))
    y2 = np.log(c2[1:] / c2[:-1])
    obs2, best2, p2, _ = rotation_pvalue(y2, hours, bandwidth(1), n_perm=200)
    print(f"5b. ROTATION TEST, planted hour-9 drift: max|t| {obs2:.2f} at hour "
          f"{best2}, p = {p2:.3f}  (want hour 9, p < 0.01)")
    good_b = (best2 == 9) and p2 < 0.01
    ok &= good_a and good_b
    print(f"   -> {'PASS' if good_a and good_b else 'FAIL'}")

    print("\n" + ("  SELF-TEST PASSED" if ok else "  SELF-TEST FAILED"))
    print("=" * 74)
    return ok


# =================================================================== states
def build_states(s: engine.Series):
    """Every state as (name, family, d_vector, kind, note).

    kind 'drift'  : d in {0,1}; beta = mean forward return in state minus out.
    kind 'signed' : d in {-1,0,+1}; beta = drift per unit of the state's own
                    direction. Positive beta = the state's direction CONTINUES,
                    negative = it REVERSES.
    Every element of d at index i uses bars <= i only.
    """
    n = len(s)
    o = np.array(s.o); h = np.array(s.h); l = np.array(s.l); c = np.array(s.c)
    a = np.array([x if x is not None else np.nan for x in engine.atr(s, 14)])
    tr = np.array(engine.true_range(s))
    rng_ = h - l
    out = []

    # --- family 2: shock. Mechanism: a large-range bar is a liquidity event;
    #     if it leaves a directional footprint the next bars drift with or
    #     against it. ATR is taken at i-1 so the shock bar cannot inflate it.
    a_prev = np.concatenate([[np.nan], a[:-1]])
    body = np.sign(c - o)
    for k in (2.0, 3.0):
        m = (rng_ > k * a_prev) & np.isfinite(a_prev)
        out.append((f"shock>{k:.0f}xATR", "shock", m.astype(float), "drift",
                    "does a large-range bar drift, either way"))
        out.append((f"shock>{k:.0f}xATR signed", "shock", (m * body).astype(float),
                    "signed", "does the shock's own direction continue"))

    # --- family 3: gap. Observed at bar i's OPEN vs bar i-1's CLOSE, so it is
    #     known at the close of bar i and acted on at the open of bar i+1. It
    #     is NOT the gap into the fill bar - that would be look-ahead (F-001).
    gap = np.concatenate([[np.nan], o[1:] - c[:-1]])
    gm = (np.abs(gap) > 0.25 * a_prev) & np.isfinite(a_prev)
    out.append(("gap>0.25xATR", "gap", gm.astype(float), "drift",
                "does any gap change forward drift"))
    out.append(("gap>0.25xATR signed", "gap", (gm * np.sign(gap)).astype(float),
                "signed", "does the gap continue (or fill)"))

    # --- family 4a: momentum run of same-direction closes.
    up = np.concatenate([[False], c[1:] > c[:-1]])
    dn = np.concatenate([[False], c[1:] < c[:-1]])
    for run in (3, 4):
        ru = np.ones(n, bool); rd = np.ones(n, bool)
        for k in range(run):
            ru &= np.concatenate([np.zeros(k, bool), up[:n - k]]) if k else up
            rd &= np.concatenate([np.zeros(k, bool), dn[:n - k]]) if k else dn
        d = ru.astype(float) - rd.astype(float)
        out.append((f"run of {run} signed", "run", d, "signed",
                    "does a run of same-direction closes continue"))

    # --- family 4b: compression, a run of inside bars. Non-directional.
    ins = np.concatenate([[False], (h[1:] <= h[:-1]) & (l[1:] >= l[:-1])])
    for run in (2, 3):
        m = np.ones(n, bool)
        for k in range(run):
            m &= np.concatenate([np.zeros(k, bool), ins[:n - k]]) if k else ins
        out.append((f"{run} inside bars", "compress", m.astype(float), "drift",
                    "does compression bias direction (E-038 says it biases SIZE)"))

    # --- family 5: volatility LEVEL vs the low->high TRANSITION.
    fast = np.convolve(tr, np.ones(5) / 5, mode="full")[:n]
    fast[:5] = np.nan
    slow = np.convolve(tr, np.ones(100) / 100, mode="full")[:n]
    slow[:100] = np.nan
    with np.errstate(invalid="ignore", divide="ignore"):
        q = fast / slow
    q_lag = np.concatenate([[np.nan] * 5, q[:-5]])
    lvl = (q >= 1.3) & np.isfinite(q)
    trans = lvl & (q_lag <= 0.7) & np.isfinite(q_lag)
    out.append(("vol LEVEL high", "vol", lvl.astype(float), "drift",
                "E-038 confirmed the LEVEL is predictable - is it directional"))
    out.append(("vol TRANSITION low->high", "vol", trans.astype(float), "drift",
                "does the transition itself carry direction"))
    return out


def hour_labels(s):
    return np.array([dt.datetime.fromtimestamp(t, dt.timezone.utc).hour for t in s.ts])


def dow_labels(s):
    return np.array([dt.datetime.fromtimestamp(t, dt.timezone.utc).weekday() for t in s.ts])


def forward_returns(s, N):
    """y[i] = log(close[i+N] / open[i+1]) — enters at the engine's fill, the
    open of the bar AFTER the state bar. Defined for i in [0, n-1-N]."""
    o = np.array(s.o); c = np.array(s.c)
    n = len(s)
    y = np.full(n, np.nan)
    end = n - N
    y[:end] = np.log(c[N:n] / o[1:end + 1])
    return y


def forward_paths(s, idx, N):
    """The N one-bar log returns following each occurrence, starting from the
    open of bar i+1 (so the first element is log(c[i+1]/o[i+1]))."""
    o = np.array(s.o); c = np.array(s.c)
    n = len(s)
    idx = idx[(idx + N) < n]
    if idx.size == 0:
        return np.zeros((0, N))
    P = np.empty((idx.size, N))
    P[:, 0] = np.log(c[idx + 1] / o[idx + 1])
    for k in range(1, N):
        P[:, k] = np.log(c[idx + 1 + k] / c[idx + k])
    return P


# ==================================================================== runner
def run():
    print("=" * 74)
    print("  E-040 — IS THERE A CONDITIONAL EDGE INSIDE A RANDOM WALK?")
    print("  5 state families x 8 series x 3 horizons. Every t reported.")
    print("=" * 74)

    n_tests = 0
    rows = []          # (series, horizon, state, kind, is_beta, is_t, oos_beta, oos_t, n_state)
    timerows = []      # categorical family results
    vrrows = []
    costnote = []

    for sym, tf in SERIES:
        s = engine.load(sym, tf)
        n = len(s)
        cut = int(n * 0.70)
        costs = study.COSTS[sym]                       # NEVER engine.Costs()
        rt_cost = costs.spread + 2 * costs.slippage + \
            costs.commission_per_lot / costs.value_per_point_per_lot
        px = float(np.mean(s.c))
        cost_ret = rt_cost / px                        # round trip in return units
        costnote.append((sym, tf, rt_cost, cost_ret))
        states = build_states(s)
        hrs = hour_labels(s); dws = dow_labels(s)

        print(f"\n{'='*74}\n  {sym} {tf}   {n} bars   split at bar {cut} "
              f"(70/30)   round-trip cost {cost_ret*1e4:.2f} bp\n{'='*74}")

        for N in HORIZONS:
            y = forward_returns(s, N)
            valid = np.isfinite(y)
            print(f"\n  --- forward horizon N = {N} bars ---")
            print(f"  {'state':<26} {'n_state':>7} {'IS beta bp':>11} {'IS t':>7} "
                  f"{'OOS beta bp':>12} {'OOS t':>7} {'|beta|/cost':>11}")

            for name, fam, d, kind, note in states:
                dd = np.nan_to_num(np.asarray(d, float))
                ok = valid & np.isfinite(dd)
                idx_is = np.flatnonzero(ok & (np.arange(n) < cut))
                idx_oos = np.flatnonzero(ok & (np.arange(n) >= cut))
                ns_is = int(np.sum(dd[idx_is] != 0))
                ns_oos = int(np.sum(dd[idx_oos] != 0))
                if ns_is < 40 or ns_oos < 20:
                    print(f"  {name:<26} {ns_is:>7} {'(too few occurrences)':>50}")
                    continue
                b_is, t_is, _ = hac_beta_t(y[idx_is], dd[idx_is], bandwidth(N))
                b_oo, t_oo, _ = hac_beta_t(y[idx_oos], dd[idx_oos], bandwidth(N))
                n_tests += 1
                ratio = abs(b_is) / cost_ret
                print(f"  {name:<26} {ns_is:>7} {b_is*1e4:>11.2f} {t_is:>+7.2f} "
                      f"{b_oo*1e4:>12.2f} {t_oo:>+7.2f} {ratio:>11.2f}")
                rows.append((sym, tf, N, name, fam, kind, b_is, t_is,
                             b_oo, t_oo, ns_is, ratio))

            # --- categorical families. Family-wise multiplicity across the
            #     24 hours / 7 weekdays is controlled by the rotation test, and
            #     that test is run on the IN-SAMPLE half ONLY. The category it
            #     picks is then confirmed once on the out-of-sample half.
            arange_n = np.arange(n)
            v_is = valid & (arange_n < cut)
            v_oo = valid & (arange_n >= cut)
            for label_name, labels in (("hour-of-day", hrs), ("day-of-week", dws)):
                y_is, l_is = y[v_is], labels[v_is]
                y_oo, l_oo = y[v_oo], labels[v_oo]
                obs, best, p, ts = rotation_pvalue(y_is, l_is, bandwidth(N),
                                                   n_perm=300)
                n_tests += 1
                if best is None:
                    continue
                d_is = (l_is == best).astype(float)
                d_oo = (l_oo == best).astype(float)
                b_is, t_is, _ = hac_beta_t(y_is, d_is, bandwidth(N))
                if d_oo.sum() >= 20:
                    b_oo, t_oo, _ = hac_beta_t(y_oo, d_oo, bandwidth(N))
                else:
                    b_oo, t_oo = float("nan"), float("nan")
                # diagnostic: a category whose returns are much QUIETER than the
                # rest gets a small standard error and can look significant
                # against a rotation null that reshuffles loud returns into it.
                sdr = (y_is[d_is > 0].std() / y_is.std()) if d_is.sum() > 2 else float("nan")
                print(f"  {label_name:<26} IS max|t| {obs:>5.2f} at {best:>2}"
                      f"  rot p {p:.3f}  n {int(d_is.sum()):>5}"
                      f"  IS t {t_is:>+6.2f}  OOS t {t_oo:>+6.2f}"
                      f"  IS bp {b_is*1e4:>7.2f}  |b|/cost {abs(b_is)/cost_ret:>5.2f}"
                      f"  sd vs rest {sdr:.2f}x")
                timerows.append((sym, tf, N, label_name, obs, best, p,
                                 t_is, t_oo, b_is, abs(b_is) / cost_ret, sdr,
                                 int(d_is.sum()), int(d_oo.sum())))
                if label_name == "day-of-week" and N == 5:
                    per = "  ".join(f"{k}:{v:+.2f}" for k, v in sorted(ts.items()))
                    print(f"    per-weekday IS t (0=Mon..6=Sun): {per}")

        # --- conditional variance ratio on the post-state paths, N = 20
        print(f"\n  --- conditional variance ratio of the 20 bars after each "
              f"state (1.00 = random walk) ---")
        for name, fam, d, kind, note in states:
            dd = np.nan_to_num(np.asarray(d, float))
            idx = np.flatnonzero(dd != 0)
            P = forward_paths(s, idx, 20)
            vr, z, m = cond_vr(P)
            if vr is None:
                print(f"  {name:<26} occurrences {m:>5}  (too few)")
                continue
            # volatility footprint: mean |1-bar return| after the state vs all
            allP = forward_paths(s, np.arange(len(s) - 21), 20)
            fp = np.mean(np.abs(P)) / np.mean(np.abs(allP))
            print(f"  {name:<26} occ {m:>5}   VR {vr:>5.3f}   z {z:>+6.2f}"
                  f"   fwd |ret| vs baseline {fp:>5.2f}x")
            vrrows.append((sym, tf, name, vr, z, m, fp))

    # ================================================================ summary
    print("\n" + "=" * 74)
    print("  SUMMARY")
    print("=" * 74)
    total = n_tests
    bonf = abs(_norm_ppf(0.025 / max(total, 1)))
    print(f"\n  Directional tests run: {total}")
    print(f"  Repo multiple-testing bar (E-012):  |t| >= {REPO_T:.2f}")
    print(f"  Exact Bonferroni bar for {total} tests at 5%: |t| >= {bonf:.2f}")

    rows.sort(key=lambda r: -abs(r[7]))
    print(f"\n  TEN LARGEST IN-SAMPLE |t| (of {len(rows)} dummy-regression tests):")
    print(f"  {'series':<14}{'N':>3} {'state':<26}{'IS t':>8}{'OOS t':>8}"
          f"{'IS bp':>8}{'OOS bp':>8}{'|b|/cost':>9}")
    for r in rows[:10]:
        print(f"  {r[0]+' '+r[1]:<14}{r[2]:>3} {r[3]:<26}{r[7]:>+8.2f}"
              f"{r[9]:>+8.2f}{r[6]*1e4:>8.2f}{r[8]*1e4:>8.2f}{r[11]:>9.2f}")

    over_repo = [r for r in rows if abs(r[7]) >= REPO_T]
    over_bonf = [r for r in rows if abs(r[7]) >= bonf]
    print(f"\n  In-sample tests clearing |t| >= {REPO_T:.2f} : {len(over_repo)}")
    print(f"  In-sample tests clearing |t| >= {bonf:.2f} (Bonferroni) : {len(over_bonf)}")
    held = [r for r in over_repo if r[7] * r[9] > 0 and abs(r[9]) >= 2.0]
    print(f"  ...of which HELD out-of-sample (same sign, |OOS t| >= 2): {len(held)}")
    for r in held:
        print(f"      {r[0]} {r[1]} N={r[2]} {r[3]}: IS t {r[7]:+.2f} "
              f"OOS t {r[9]:+.2f}")

    exp_false = 0.05 * total
    print(f"\n  Expected count above |t| = 1.96 by chance alone: {exp_false:.1f}")
    print(f"  Observed count above |t| = 1.96                 : "
          f"{sum(1 for r in rows if abs(r[7]) >= 1.96)}")

    print(f"\n  TIME-OF-DAY / DAY-OF-WEEK ({len(timerows)} family-wise tests,"
          f" rotation null, discovery on the IN-SAMPLE half only):")
    sig_t = [t for t in timerows if t[6] <= 0.05]
    print(f"  significant IN-SAMPLE at family-wise p <= 0.05: {len(sig_t)} of "
          f"{len(timerows)}  (chance alone gives {0.05*len(timerows):.1f})")
    held_t = [t for t in sig_t if np.isfinite(t[8]) and t[7] * t[8] > 0
              and abs(t[8]) >= 2.0]
    print(f"  ...of which the SAME category held out-of-sample "
          f"(same sign, |OOS t| >= 2): {len(held_t)}")
    print(f"  {'series':<13}{'N':>3} {'family':<12}{'cat':>4}{'rot p':>7}"
          f"{'IS t':>7}{'OOS t':>7}{'IS bp':>8}{'|b|/cost':>9}{'sd vs rest':>11}"
          f"{'n IS':>6}")
    for t in sorted(timerows, key=lambda x: x[6])[:12]:
        print(f"  {t[0]+' '+t[1]:<13}{t[2]:>3} {t[3]:<12}{t[5]:>4}{t[6]:>7.3f}"
              f"{t[7]:>+7.2f}{t[8]:>+7.2f}{t[9]*1e4:>8.2f}{t[10]:>9.2f}"
              f"{t[11]:>11.2f}{t[12]:>6}")
    for t in held_t:
        print(f"      HELD OOS: {t[0]} {t[1]} N={t[2]} {t[3]} category {t[5]}"
              f"  IS t {t[7]:+.2f}  OOS t {t[8]:+.2f}  |beta|/cost {t[10]:.2f}")

    print(f"\n  CONDITIONAL VARIANCE RATIO of the 20 bars after each state.")
    print(f"  CALIBRATED bar (self-test 4b): |z| >= {VR_BAR5:.2f} is 5%,"
          f" |z| >= {VR_BAR1:.2f} is 1% under a TRUE random walk. 1.96 is wrong here.")
    n_vr_sig = sum(1 for v in vrrows if abs(v[4]) >= VR_BAR5)
    print(f"  of {len(vrrows)} VR tests, {n_vr_sig} exceed the calibrated 5% bar"
          f" (chance alone gives {0.05*len(vrrows):.1f})")
    print(f"  |z| ranking (top 8 of {len(vrrows)}):")
    for v in sorted(vrrows, key=lambda x: -abs(x[4]))[:8]:
        print(f"      {v[0]} {v[1]:<4} {v[2]:<26} VR {v[3]:.3f}  z {v[4]:+6.2f}"
              f"  occ {v[5]}  fwd|ret| {v[6]:.2f}x")

    print(f"\n  VOLATILITY FOOTPRINT of shocks (forward |return| vs baseline):")
    for v in vrrows:
        if v[2].startswith("shock>2xATR") and "signed" not in v[2]:
            print(f"      {v[0]} {v[1]:<4} {v[6]:.2f}x")

    print("\n" + "=" * 74)
    return rows, timerows, vrrows, total, bonf


def _norm_ppf(p):
    """Inverse standard normal CDF (Acklam). Used only to print the exact
    Bonferroni threshold; self-checked against known quantiles below."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5; r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


if __name__ == "__main__":
    assert abs(_norm_ppf(0.025) + 1.959964) < 1e-4, "norm_ppf broken"
    assert abs(_norm_ppf(0.005) + 2.575829) < 1e-4, "norm_ppf broken"
    if not selftest():
        print("\nSELF-TEST FAILED — market results would be meaningless. Stop.")
        sys.exit(1)
    if "--selftest" in sys.argv:
        sys.exit(0)
    run()

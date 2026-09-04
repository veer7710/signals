"""
Regression tests for the JARVIS backtest engine.

These exist because a backtester that is subtly wrong is far more dangerous
than one that is obviously broken: it produces confident, beautiful, false
numbers and you bet real money on them. Every test here encodes a mistake
that was actually made, or a property that must never break.

Run:  python3 JARVIS/research/test_engine.py
"""
from __future__ import annotations
import math, os, random, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, strategies

FAIL = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(name)


def synth(n=3000, seed=3):
    """Deterministic random-walk candles. A correct engine must find NO edge."""
    rng = random.Random(seed)
    px = 2000.0
    ts, o, h, l, c = [], [], [], [], []
    t = 1700000000
    for i in range(n):
        op = px
        px = px * (1 + rng.gauss(0, 0.0012))
        hi = max(op, px) + abs(rng.gauss(0, 0.6))
        lo = min(op, px) - abs(rng.gauss(0, 0.6))
        ts.append(t + i * 3600); o.append(op); h.append(hi); l.append(lo); c.append(px)
    return engine.Series(ts, o, h, l, c)


print("=" * 66)
print("  JARVIS ENGINE REGRESSION TESTS")
print("=" * 66)

s = synth()

# ---- F-001: the walk-forward index-mismatch bug -----------------------
print("\nF-001  walk-forward must rebuild strategies per fold")
sub = engine.Series(s.ts[500:2500], s.o[500:2500], s.h[500:2500],
                    s.l[500:2500], s.c[500:2500])
wrong = engine.stats(engine.backtest(sub, strategies.ema_pullback(s),
                                     engine.Costs(), warmup=300))
right = engine.stats(engine.backtest(sub, strategies.ema_pullback(sub),
                                     engine.Costs(), warmup=300))
# A strategy fed mismatched indices produces pathological win rates.
check("mismatched-index run is detectably pathological",
      wrong.get("n", 0) == 0 or wrong.get("win_rate", 1) < 0.05 or
      right.get("n", 0) != wrong.get("n", 0),
      "the two runs were indistinguishable — the guard is not testing anything")
wf = engine.walk_forward(s, lambda x: strategies.ema_pullback(x),
                         engine.Costs(), folds=4, warmup=300)
allw = [w for _, _, w, _ in wf if w.get("n", 0) >= 5]
check("walk_forward folds have sane win rates (not 0%)",
      all(w["win_rate"] > 0.02 for w in allw) if allw else True,
      f"win rates {[round(w['win_rate'],3) for w in allw]}")

# ---- no look-ahead ----------------------------------------------------
print("\nLOOK-AHEAD  future bars must not change past trades")
s2 = engine.Series(s.ts[:], s.o[:], s.h[:], s.l[:], s.c[:])
rng = random.Random(9)
for i in range(2200, len(s2)):          # scramble only the tail
    s2.c[i] *= (1 + rng.gauss(0, 0.05))
    s2.h[i] = max(s2.h[i], s2.c[i]); s2.l[i] = min(s2.l[i], s2.c[i])
for nm in ("donchian_trend", "liquidity_sweep", "ema_pullback"):
    a = engine.backtest(s, strategies.REGISTRY[nm](s), engine.Costs(), warmup=300)
    b = engine.backtest(s2, strategies.REGISTRY[nm](s2), engine.Costs(), warmup=300)
    a = [t for t in a if t.ts_out < s.ts[2100]]
    b = [t for t in b if t.ts_out < s.ts[2100]]
    same = len(a) == len(b) and all(
        x.ts_in == y.ts_in and abs(x.r - y.r) < 1e-9 for x, y in zip(a, b))
    check(f"{nm}: trades closing before the scramble are unchanged", same,
          f"{len(a)} vs {len(b)} trades")

# ---- ties lose --------------------------------------------------------
print("\nTIES  a bar containing both stop and target must record a LOSS")
ts = [1700000000 + i * 3600 for i in range(400)]
o = [100.0] * 400; h = [100.5] * 400; l = [99.5] * 400; c = [100.0] * 400
h[350] = 120.0; l[350] = 80.0                     # bar engulfs both levels
tie = engine.Series(ts, o, h, l, c)
def tie_sig(ctx, i):
    if i != 348:
        return None
    return {"side": 1, "stop": 95.0, "target": 105.0}
tt = engine.backtest(tie, tie_sig, engine.Costs(spread=0, slippage=0,
                                                commission_per_lot=0), warmup=300)
check("engulfing bar resolves as a stop-out", len(tt) == 1 and tt[0].reason == "stop",
      f"got {[t.reason for t in tt]}")
check("that trade's R is negative", len(tt) == 1 and tt[0].r < 0)

# ---- costs must hurt --------------------------------------------------
print("\nCOSTS  wider spreads must reduce expectancy, never improve it")
base = engine.stats(engine.backtest(s, strategies.donchian_trend(s),
                                    engine.Costs(spread=0.1), warmup=300))
wide = engine.stats(engine.backtest(s, strategies.donchian_trend(s),
                                    engine.Costs(spread=3.0), warmup=300))
check("higher spread lowers expectancy",
      wide.get("expectancy_R", 0) < base.get("expectancy_R", 0),
      f"{base.get('expectancy_R')} -> {wide.get('expectancy_R')}")

# ---- no edge on random data ------------------------------------------
print("\nNULL  no strategy may show a significant edge on a random walk")
for nm in strategies.REGISTRY:
    st = engine.stats(engine.backtest(s, strategies.REGISTRY[nm](s),
                                      engine.Costs(), warmup=300))
    t = abs(st.get("t_stat", 0))
    check(f"{nm}: t-stat < 3 on random data", t < 3.0, f"t={t:.2f}")

# ---- indicator sanity -------------------------------------------------
print("\nINDICATORS")
ctx = engine.build_context(s)
check("RSI bounded 0..100", all(0 <= v <= 100 for v in ctx["rsi"]))
check("ATR positive", all(v is None or v > 0 for v in ctx["atr"][20:]))
check("ADX bounded 0..100", all(0 <= v <= 100 for v in ctx["adx"]))
check("EMA9 tracks price more closely than EMA200",
      abs(ctx["ema9"][-1] - s.c[-1]) < abs(ctx["ema200"][-1] - s.c[-1]))



# ------------------------------------------------ prop simulator sanity ----
print("\nPROP SIM  sanity checks")
import prop_sim

_winning = [type("T", (), {"r": 2.0, "ts_out": 1700000000 + i * 86400})()
            for i in range(200)]
_res = prop_sim.simulate_prop_account(_winning, prop_sim.PRESETS["generic_2step_phase1"])
check("a strategy that only wins passes the eval", _res.passed,
      f"reason={_res.fail_reason}")

_losing = [type("T", (), {"r": -1.0, "ts_out": 1700000000 + i * 86400})()
           for i in range(200)]
_res2 = prop_sim.simulate_prop_account(_losing, prop_sim.PRESETS["generic_2step_phase1"])
check("a strategy that only loses fails the eval", not _res2.passed and _res2.failed)

_mc = prop_sim.monte_carlo_prop(_winning, prop_sim.PRESETS["generic_2step_phase1"], trials=200)
check("monte carlo pass rate is high for an always-winning strategy",
      _mc["pass_rate"] > 0.9, f"pass_rate={_mc['pass_rate']}")


# ---------------------------------------------------------------- E-110
def test_entry_bar_not_post_fill():
    """No trade may realise favourable excursion on its own entry bar unless
    that bar OPENED beyond the entry level.

    THE BUG THIS EXISTS TO CATCH cost this project its headline result. A limit
    filled because bar j's LOW reached it was then credited with bar j's HIGH as
    profit - two unknown intrabar orderings both resolved in our favour. On GOLD
    1h, 497 of 534 trades (93.1%) opened AND closed on their entry bar and
    produced 99.0% of all reported profit. It read +0.991R and 104:1; corrected
    it is +0.205R and 4.86:1.

    Nothing in this file could see it, because every test here drives
    engine.backtest, which fills at the next bar's OPEN and is therefore immune.
    The liquidity research uses limit fills and bypasses it entirely.
    """
    import liq_exit, study
    from engine import Series
    c = study.COSTS["GOLD"]
    # one bar that dips to the limit and then rallies hard, then a flat bar.
    # A long filled at 100 must NOT be able to book the 130 high of its own bar.
    # bar 1 OPENS at 105 (above the limit), dips to 100 to fill the long, then
    # rallies to 130. The 130 is not ours: the fill is evidenced only by the dip.
    s = Series(ts=[0, 3600, 7200], o=[110.0, 105.0, 100.0],
               h=[110.0, 130.0, 100.0], l=[110.0, 100.0, 100.0],
               c=[110.0, 100.0, 100.0])
    t = liq_exit.resolve(s, c, 1, 1, 100.0, 95.0, "fixed2R", 5.0, tgt_r=2.0)
    ok_target = (t["why"] != "target")
    t2 = liq_exit.resolve(s, c, 1, 1, 100.0, 95.0, "trail_gb", 5.0)
    ok_gb = (t2["why"] != "giveback")
    check("entry bar cannot hit its own target", ok_target)
    check("entry bar cannot arm its own give-back", ok_gb)

    # ...but a bar that OPENED beyond the limit IS legitimately post-fill
    s2 = Series(ts=[0, 3600, 7200], o=[110.0, 99.0, 100.0],
                h=[110.0, 130.0, 100.0], l=[110.0, 99.0, 100.0],
                c=[110.0, 100.0, 100.0])
    t3 = liq_exit.resolve(s2, c, 1, 1, 100.0, 95.0, "fixed2R", 5.0, tgt_r=2.0)
    check("a gapped-through entry bar IS post-fill", t3["why"] == "target")


def test_no_future_in_fvg_snapshot():
    """smc.fvgs stored `list(live)`, a SHALLOW copy, so every bar's snapshot
    shared the same dicts and a gap flagged inverted at bar 353 was inverted in
    the snapshot stored at bar 300. 47,794 stored entries carried inv_bar > i.
    """
    import engine as _e, smc
    s = _e.load("GOLD", "1h")
    A = _e.atr(s, 14)
    per_bar, _ = smc.fvgs(s, A)
    items = (per_bar.items() if isinstance(per_bar, dict)
             else enumerate(per_bar))
    bad = sum(1 for i, gs in items if gs
              for g in gs if g.get("inv_bar", -1) > i)
    check("fvg snapshot carries no future", bad == 0,
          f"{bad} entries flagged by a future bar")


test_entry_bar_not_post_fill()
test_no_future_in_fvg_snapshot()

print("\n" + "=" * 66)
print(f"  {'ALL TESTS PASSED' if not FAIL else 'FAILURES: ' + ', '.join(FAIL)}")
print("=" * 66)
sys.exit(1 if FAIL else 0)
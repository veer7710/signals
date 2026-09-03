"""
P91 / E-082 — Does LiquiditySniper.mq5 actually trade what E-080 measured?

Nothing in this project has ever checked this, and it is the gap through which
a good backtest becomes a losing account. E-080 measured a SIGNAL SET: every
candidate from every source, in time order, first one touched wins. The EA does
something subtly different, because an EA cannot rest fifty orders:

  THE BACKTEST   emits every candidate and lets the market pick.
  THE EA         picks the NEAREST level on each side, rests ONE limit there,
                 and re-points it on every bar close as levels are born and die.

Those are not obviously the same strategy. The EA can be sitting on a zone
limit at the moment an FVG forms closer to price, and it will move; the
backtest would have had both orders live. Re-pointing also CANCELS a resting
order that was about to fill.

This file implements the EA'S logic - nearest-per-side, re-armed each bar - in
Python, runs it on the same bars, and puts the two side by side. If they
disagree materially, the EA is not the thing that was measured and the numbers
quoted for it are not its numbers.

Run:  python3 JARVIS/research/ea_parity.py
"""
from __future__ import annotations
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, study
from engine import Series
from liquidity import stat, pivots
from toptick import zone_stream, entry_level
from smc import smc_state, resolve, STOP_ATR, TGT_R, FRAC
from smc_combine import all_signals, simulate

MIN_GAP_ATR = 0.10
DISP_ATR = 1.0
SMC_LIFE = 200
ARM_LIFE = 60


# Source priority. "nearest" is what build 3.00/3.01 do; "zone_first" prefers a
# liquidity zone over an FVG over an order block, and only falls back when the
# better source has nothing live. The backtest implicitly did the latter - its
# candidate list is ordered zone, fvg, ob within each bar and the first touched
# wins - which is why it took 415 zone trades where the EA took 320 and 411
# order blocks. That is a SELECTION RULE difference, not a data difference.
PRIORITY = {"zone": 0, "fvg": 1, "ob": 2}


def ea_best_level(dirn, px, zones_side, gaps, obs, a, mode="nearest"):
    """BestLevel() from the EA. dirn +1 wants a level BELOW price to buy at."""
    best, src = None, ""
    # the nearest live zone on that side
    cand = []
    for z in zones_side:
        lvl = entry_level(z, FRAC, a)
        cand.append((lvl, "zone"))
    for g in gaps:
        if g["dir"] != dirn:
            continue
        cand.append(((g["top"] + g["bot"]) / 2.0, "fvg"))
    for b in obs:
        if b["dir"] != dirn:
            continue
        cand.append(((b["top"] + b["bot"]) / 2.0, "ob"))
    ok = [(lvl, s_) for (lvl, s_) in cand
          if not ((dirn > 0 and lvl >= px) or (dirn < 0 and lvl <= px))]
    if not ok:
        return None, ""
    if mode == "zone_first":
        ok.sort(key=lambda t: (PRIORITY[t[1]], abs(t[0] - px)))
    else:
        ok.sort(key=lambda t: abs(t[0] - px))
    return ok[0][0], ok[0][1]


def run_ea(s: Series, costs, per_bar, A, st, warmup=250, max_bars=200,
           arm_once=True, arm_wait=20, mode="nearest", blacklist="armed"):
    """The EA's own loop. One position; up to two resting limits, one per side.

    arm_once/arm_wait are build 3.01's fix: a level is armed ONCE, the order
    sits for arm_wait bars, and the level is never armed again. Passing
    arm_once=False reproduces build 3.00, which re-pointed every bar - kept so
    the difference stays measurable rather than asserted.
    """
    half = costs.spread / 2.0
    trades = []
    busy = -1
    arm = {1: None, -1: None}          # dir -> (level, src, atr_at_arm, bar)
    used = set()
    # blacklist="armed"  : a level is dead once an order has been placed at it,
    #                      even if that order expired untouched.
    # blacklist="filled" : a level is dead only once it has actually TRADED.
    #   The second is the honest one. An order that rested and was never
    #   touched has not "used up" anything - the level is exactly as valid as
    #   before - and the backtest treats it that way.

    for i in range(warmup, len(s) - 2):
        a = A[i]
        if a is None or a <= 0:
            continue

        # ---- FILLS FIRST. A resting order is live inside the bar, and the EA's
        # orders are at the broker, so they fill without the EA looking.
        if i > busy:
            for dirn in (1, -1):
                if arm[dirn] is None:
                    continue
                lvl, src, aa, _b = arm[dirn]
                touched = (s.l[i] <= lvl) if dirn > 0 else (s.h[i] >= lvl)
                if not touched:
                    continue
                entry = lvl + dirn * (half + costs.slippage)
                stop = entry - dirn * STOP_ATR * aa
                if (entry - stop) * dirn <= 0:
                    arm[dirn] = None
                    continue
                tgt = entry + dirn * TGT_R * (entry - stop) * dirn
                t = resolve(s, costs, i, dirn, entry, stop, tgt, max_bars)
                t["src"] = src
                trades.append(t)
                busy = t["exit_bar"]
                used.add(round(lvl, 4))
                arm = {1: None, -1: None}      # the other side is cancelled
                break

        # ---- then re-point, on the bar close, exactly as ManageOrders does
        if i <= busy:
            arm = {1: None, -1: None}
            continue
        zb = [z for z in per_bar[i] if z["dir"] == 1 and i - z["born"] <= ARM_LIFE]
        zs = [z for z in per_bar[i] if z["dir"] == -1 and i - z["born"] <= ARM_LIFE]
        gaps = [g for g in st["fvg"][i] if not g["inverted"]]
        obs = st["ob"][i]
        for dirn in (1, -1):
            # an order already resting and not yet expired is LEFT ALONE
            if arm_once and arm[dirn] is not None:
                if i - arm[dirn][3] <= arm_wait:
                    continue
                arm[dirn] = None
            zside = zs if dirn > 0 else zb
            lvl, src = ea_best_level(dirn, s.c[i], zside, gaps, obs, a, mode)
            if lvl is None:
                arm[dirn] = None
                continue
            key = round(lvl, 4)
            if arm_once and key in used:
                arm[dirn] = None
                continue
            if arm_once and blacklist == "armed":
                used.add(key)
            arm[dirn] = (lvl, src, a, i)
    return trades


def main():
    print("=" * 100)
    print("  P91 / E-082  EA PARITY — does the EA trade what the backtest measured?")
    print("  BACKTEST: every candidate emitted, first one touched wins.")
    print("  EA:       nearest level per side, ONE limit each, re-pointed every bar.")
    print("  Same bars, same stop, same target. Any gap is the EA's real behaviour.")
    print("=" * 100)

    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        A = engine.atr(s, 14)
        per_bar, _ = zone_stream(s)
        st = smc_state(s, A)

        cands = all_signals(s, c, per_bar, A, st, {"toptick", "fvg", "ob"})
        bt = simulate(s, c, cands, st)
        ea30 = run_ea(s, c, per_bar, A, st, arm_once=False)
        ea = run_ea(s, c, per_bar, A, st, arm_once=True)
        eaz = run_ea(s, c, per_bar, A, st, arm_once=True, mode="zone_first")

        print(f"\n  ### {sym} {tf}")
        print(f"   {'model':<12}{'n':>7}{'win%':>8}{'expect':>10}{'PF':>7}{'t':>8}"
              f"{'total R':>10}{'points':>10}")
        print("   " + "-" * 72)
        for name, tr in (("backtest", bt), ("EA 3.00", ea30), ("EA 3.01", ea),
                         ("EA zone-first", eaz)):
            if not tr:
                print(f"   {name:<12}  no trades")
                continue
            a_ = stat(tr)
            print(f"   {name:<12}{a_['n']:>7}{a_['win']:>7.1f}%{a_['exp']:>+9.3f}R"
                  f"{a_['pf']:>7.2f}{a_['t']:>+8.2f}{a_['exp']*a_['n']:>+9.1f}R"
                  f"{sum(x['pts'] for x in tr):>+10.0f}")
        if bt and ea:
            b_, e_ = stat(bt), stat(ea)
            dn = 100.0 * (e_["n"] - b_["n"]) / b_["n"]
            de = e_["exp"] - b_["exp"]
            dp = sum(x["pts"] for x in ea) - sum(x["pts"] for x in bt)
            print(f"\n   DIFFERENCE  trades {dn:+.0f}%   expectancy {de:+.3f}R"
                  f"   points {dp:+.0f}")
            for tr, nm in ((bt, "backtest"), (ea30, "EA 3.00"), (ea, "EA 3.01"),
                           (eaz, "EA zone-first")):
                mix = {}
                for x in tr:
                    mix[x["src"]] = mix.get(x["src"], 0) + 1
                print(f"   {nm:<10} sources: " +
                      "  ".join(f"{k} {v}" for k, v in sorted(mix.items())))

    # ---- the gap is large, so both versions get validated properly
    print("\n" + "=" * 100)
    print("  BOTH VERSIONS, ATTACKED. The EA row is the one that will trade.")
    print("=" * 100)
    from liq_validate import mc_drawdown
    from smc import control
    for sym, tf in (("GOLD", "1h"), ("GOLD", "15m")):
        s = engine.load(sym, tf)
        c = study.COSTS["GOLD"]
        A = engine.atr(s, 14)
        per_bar, _ = zone_stream(s)
        st = smc_state(s, A)
        cands = all_signals(s, c, per_bar, A, st, {"toptick", "fvg", "ob"})
        for nm, tr in (("backtest", simulate(s, c, cands, st)),
                       ("EA 3.00", run_ea(s, c, per_bar, A, st, arm_once=False)),
                       ("EA 3.01", run_ea(s, c, per_bar, A, st, arm_once=True)),
                       ("EA zone-first", run_ea(s, c, per_bar, A, st,
                                                arm_once=True, mode="zone_first"))):
            if len(tr) < 40:
                continue
            a_ = stat(tr)
            rs = [x["r"] for x in tr]
            h = len(tr) // 2
            A1, B1 = stat(tr[:h]), stat(tr[h:])
            nb = 6
            bl = [tr[i * len(tr) // nb:(i + 1) * len(tr) // nb] for i in range(nb)]
            bs = [stat(b) for b in bl if len(b) >= 10]
            wf = sum(1 for x in bs if x["exp"] > 0)
            ce = [stat(control(s, c, A, min(len(tr), 800), sd))["exp"]
                  for sd in range(51, 71)]
            cm = sum(ce) / len(ce)
            csd = (sum((x - cm) ** 2 for x in ce) / len(ce)) ** 0.5
            se_o = abs(a_["exp"] / a_["t"]) if a_["t"] else 0.0
            se_c = csd / math.sqrt(len(ce))
            z = (a_["exp"] - cm) / math.sqrt(se_o ** 2 + se_c ** 2)
            dds = mc_drawdown(rs)
            # drawdown in POUNDS at 0.01 lots, which is what a 40-pound
            # account actually experiences
            risk_pts = STOP_ATR * (sorted(x for x in A if x)[len(
                [x for x in A if x]) // 2])
            gbp = risk_pts * (1.0 / 1.27)
            print(f"\n  {sym} {tf} — {nm}")
            print(f"    n {a_['n']}  win {a_['win']:.1f}%  {a_['exp']:+.3f}R"
                  f"  PF {a_['pf']:.2f}  t {a_['t']:+.2f}"
                  f"  {sum(x['pts'] for x in tr):+.0f} points")
            print(f"    OOS {A1['exp']:+.3f} / {B1['exp']:+.3f}"
                  f"   walk-fwd {wf}/{len(bs)}   control {cm:+.3f}R -> {z:+.1f} sd")
            print(f"    drawdown {dds[len(dds)//2]:.1f}R median, "
                  f"{dds[int(len(dds)*0.95)]:.1f}R at the 95th"
                  f"   = GBP{dds[int(len(dds)*0.95)]*gbp:.0f} on 0.01 lots")

    print("\n  WHAT A GAP MEANS")
    print("  * The EA taking FEWER trades is expected: it can only rest two orders.")
    print("  * The EA taking trades with a WORSE expectancy is not expected, and")
    print("    would mean nearest-level-per-side is a worse selector than letting")
    print("    the market choose - a real finding about the EA, not about the edge.")
    print("  * Any figure quoted for this EA must come from the EA row, not the")
    print("    backtest row. That is the whole point of this file.")


if __name__ == "__main__":
    main()

"""
Prop-firm rule simulator.

Runs a strategy's trade-by-trade equity path through a prop firm's actual
rules — daily loss limit, max drawdown (static OR trailing), profit target,
minimum trading days — instead of scoring it as an unrestricted personal
account. A strategy that makes great historical profit but blows the daily
loss limit every third week is USELESS for a funded account; this catches
that, which a plain backtest cannot.

All deterministic, no AI cost per run. Run thousands of trials cheaply;
the model is only needed to decide what to test next.
"""
from __future__ import annotations
import math, os, random, sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine


@dataclass
class PropRules:
    """Configurable so real firms' rules can be plugged in once known."""
    name: str = "GENERIC"
    starting_balance: float = 100_000.0
    profit_target_pct: float = 0.10          # e.g. FTMO 2-step phase 1 ~10%
    daily_loss_limit_pct: float = 0.05        # against day's starting equity
    max_drawdown_pct: float = 0.10
    trailing_drawdown: bool = False           # False = static from initial balance
    min_trading_days: int = 4
    risk_pct_per_trade: float = 0.005         # 0.5% risk per R, position sizing
    max_eval_days: int = 30                   # None = unlimited


@dataclass
class PropResult:
    passed: bool
    failed: bool
    fail_reason: str
    trading_days: int
    end_balance: float
    max_dd_hit_pct: float
    daily_violations: int
    total_violations: int
    days_to_outcome: int
    trade_log: list = field(default_factory=list)


def simulate_prop_account(trades: list, rules: PropRules, seed=0) -> PropResult:
    """
    `trades` = engine.Trade objects, chronological, each with .r (R multiple)
    and .ts_out (bar close timestamp) used to group into trading days.

    Position size is risk_pct_per_trade of CURRENT balance per unit R, matching
    how a real funded account is sized (not fixed lots).
    """
    if not trades:
        return PropResult(False, True, "no trades", 0, rules.starting_balance,
                          0.0, 0, 0, 0)

    bal = rules.starting_balance
    peak = bal
    trailing_floor = bal * (1 - rules.max_drawdown_pct)
    static_floor = bal * (1 - rules.max_drawdown_pct)
    max_dd_seen = 0.0
    daily_start = bal
    cur_day = None
    days_traded = set()
    daily_violations = 0
    log = []

    import datetime
    for t in sorted(trades, key=lambda x: x.ts_out):
        day = datetime.datetime.fromtimestamp(t.ts_out, datetime.timezone.utc).date()
        if cur_day is None:
            cur_day = day
            daily_start = bal
        elif day != cur_day:
            # a new trading day starts: check the PREVIOUS day's loss limit
            day_loss = (daily_start - bal) / daily_start if daily_start > 0 else 0
            if day_loss >= rules.daily_loss_limit_pct:
                daily_violations += 1
                return PropResult(False, True,
                                  f"daily loss limit breached on {cur_day}",
                                  len(days_traded), bal, max_dd_seen,
                                  daily_violations, daily_violations,
                                  len(days_traded), log)
            cur_day = day
            daily_start = bal
        days_traded.add(day)

        pnl = bal * rules.risk_pct_per_trade * t.r
        bal += pnl
        log.append({"day": str(day), "r": t.r, "bal": round(bal, 2)})

        peak = max(peak, bal)
        if rules.trailing_drawdown:
            trailing_floor = max(trailing_floor, peak * (1 - rules.max_drawdown_pct))
            floor = trailing_floor
        else:
            floor = static_floor
        dd = (peak - bal) / peak if peak > 0 else 0
        max_dd_seen = max(max_dd_seen, dd)

        if bal <= floor:
            return PropResult(False, True, "max drawdown breached",
                              len(days_traded), bal, max_dd_seen,
                              daily_violations, daily_violations + 1,
                              len(days_traded), log)
        if rules.max_eval_days and len(days_traded) > rules.max_eval_days:
            return PropResult(False, True, "evaluation window expired",
                              len(days_traded), bal, max_dd_seen,
                              daily_violations, daily_violations,
                              len(days_traded), log)
        if (bal >= rules.starting_balance * (1 + rules.profit_target_pct)
                and len(days_traded) >= rules.min_trading_days):
            return PropResult(True, False, "target reached",
                              len(days_traded), bal, max_dd_seen,
                              daily_violations, daily_violations,
                              len(days_traded), log)

    # ran out of trades without hitting target or breaching
    return PropResult(False, False, "incomplete: no more trades",
                      len(days_traded), bal, max_dd_seen,
                      daily_violations, daily_violations, len(days_traded), log)


def monte_carlo_prop(trades: list, rules: PropRules, trials=2000, seed=7):
    """
    Bootstrap the trade R-sequence to estimate PASS RATE — the number a real
    account cares about, not just "did this exact historical order pass".
    """
    if not trades:
        return {"n": 0}
    rng = random.Random(seed)
    rs = [t.r for t in trades]
    ts = [t.ts_out for t in trades]
    n = len(rs)
    passes = fails_dd = fails_daily = fails_time = 0
    end_bals = []

    for _ in range(trials):
        idx = [rng.randrange(n) for _ in range(n)]
        seq_r = [rs[i] for i in idx]
        seq_t = sorted(ts)              # keep real day spacing, shuffle only R
        fake_trades = [_FakeTrade(r, t) for r, t in zip(seq_r, seq_t)]
        res = simulate_prop_account(fake_trades, rules)
        end_bals.append(res.end_balance)
        if res.passed:
            passes += 1
        elif "daily" in res.fail_reason:
            fails_daily += 1
        elif "drawdown" in res.fail_reason:
            fails_dd += 1
        elif "window" in res.fail_reason:
            fails_time += 1
    end_bals.sort()
    q = lambda p: end_bals[int(p * (len(end_bals) - 1))]
    return {
        "n": trials,
        "pass_rate": passes / trials,
        "fail_daily_loss": fails_daily / trials,
        "fail_max_dd": fails_dd / trials,
        "fail_timeout": fails_time / trials,
        "median_end_balance": q(0.5),
        "p10_end_balance": q(0.10),
        "p90_end_balance": q(0.90),
    }


class _FakeTrade:
    __slots__ = ("r", "ts_out")
    def __init__(self, r, ts_out):
        self.r = r; self.ts_out = ts_out


# A few illustrative rule sets. REPLACE WITH REAL FIRM RULES once Veer names
# his firm — these are structurally typical but NOT any specific firm's terms.
PRESETS = {
    "generic_2step_phase1": PropRules(
        name="Generic 2-step, phase 1", profit_target_pct=0.10,
        daily_loss_limit_pct=0.05, max_drawdown_pct=0.10,
        trailing_drawdown=False, min_trading_days=4, max_eval_days=30),
    "generic_2step_phase2": PropRules(
        name="Generic 2-step, phase 2", profit_target_pct=0.05,
        daily_loss_limit_pct=0.05, max_drawdown_pct=0.10,
        trailing_drawdown=False, min_trading_days=4, max_eval_days=60),
    "generic_1step_trailing": PropRules(
        name="Generic 1-step, trailing DD", profit_target_pct=0.10,
        daily_loss_limit_pct=0.04, max_drawdown_pct=0.06,
        trailing_drawdown=True, min_trading_days=0, max_eval_days=None),
}

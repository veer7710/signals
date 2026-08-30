# EA ARCHITECTURE SPECIFICATION — LiquiditySniper MT5 rebuild

**Document status:** Phase-1 design. **No MQL5 has been written or compiled.**
There is no MetaTrader and no MetaEditor in this container. Nothing in this
document has been compiled, tick-tested, or run in the strategy tester.
Everything marked "measured" comes from this repository's own Python tests and
is cited to the file that produced it.

**Written:** 2026-08-30
**Supersedes:** nothing. Replaces `JARVIS/ea/inbox/XAUUSD_QUAD_v19_18.mq5`
(20,695 lines, 748 inputs, REJECTED — `JARVIS/ea/AUDIT_v19_18.md`, E-006).
**Mirrors:** `JARVIS/pine/LiquiditySniper_v1.pine`
**Skeletons written:** `JARVIS/ea/src/*.mqh` (15 files) +
`JARVIS/ea/LiquiditySniper.mq5` — **declarations and doc comments only, no
bodies.** MQL5 requires a body for every declared method, so that tree does
not compile and is not meant to yet; the interfaces are being reviewed
before anything is built.

---

## 0. THE GATE — READ BEFORE WRITING ANY CODE

Standing rule: *never write an EA for a strategy that has not passed
`study.py` and the adversarial reviewer.*

**The sweep-continuation strategy has NOT passed.** Its current status in
`JARVIS/state/EXPERIMENTS.md` is **PROMISING**, not CONFIRMED. From
`findings/08_sweep_direction.md`:

| Test | Status |
|---|---|
| Direction (FOLLOW > FADE) on 5/5 markets | done, n ≈ 10,000 sweeps |
| Beats plain 20-bar breakout on 5/5 markets | done, +3.1 points average |
| t-statistic against the multiple-testing bar (~2.8–3.0 after ~100 variants) | **NOT COMPUTED** |
| Walk-forward across six periods | **NOT RUN** |
| Cost sensitivity at 2× and 3× spread | **NOT RUN for the sweep-follow variant** |
| Out-of-sample on unseen data | **NOT RUN** |

Measured net expectancy is **+0.04R to +0.05R** per trade after gold's ~0.35
round trip. E-003 — the sibling variant — went `+0.001R → −0.031R at 2×
spread → −0.061R at 3×`. A +0.04R edge is inside the same failure band.

**Therefore:** this specification and the header skeletons are Phase 1.
**Phase 2 (writing the implementations) is BLOCKED until all four missing
tests pass.** If they fail, this spec is filed and no MQL5 is written. That is
the point of writing the spec first — the architecture work is not wasted, but
it is not permission to trade.

Second gate: `InpDemoOnly = true` ships as the default and is only removed by
Veer, in a session, explicitly.

---

## 1. MODULE ARCHITECTURE

### 1.1 Design rules that produced this split

1. **One file per concern.** A module that needs to know two things is two
   modules.
2. **The dependency graph is a DAG with no cycles.** Signal modules never see
   money; money modules never see signals.
3. **Exactly one module may call `OrderSend`.** In v19.18 there were 35
   `CloseTagged()` call sites competing on every tick and the realised exit
   was the minimum of ten independent guards
   (`findings/05_ea_deep_audit.md`, "the guards fight each other"). Here there
   is one door.
4. **Every module is constructible with no side effects and testable in
   isolation** — `Init()` never sends an order, never reads the account.

### 1.2 Dependency graph

```
                       Types.mqh   Config.mqh        (leaf, no deps)
                            |          |
        +-------------------+----------+-------------------+
        |                   |                              |
   Logger.mqh          RiskEngine.mqh              RegimeEngine.mqh
        |                   |                              |
        |            ExecutionEngine.mqh          LiquidityEngine.mqh
        |                   |                              |
        |            PropFirmEngine.mqh             SweepEngine.mqh
        |                   |                              |
        |            TradeManagement.mqh   <---- EntryEngine.mqh
        |                   |                              |
        +--- StatisticsEngine.mqh                   TargetEngine.mqh
                            |                              |
                            |                    LiquiditySniperSignal.mqh
                            |                     implements ISignalProvider
                            |                              |
                            +---------- LiquiditySniper.mq5 (orchestrator only)
```

`ISignalProvider.mqh` is a leaf alongside `Types.mqh`: it includes nothing
but `Types.mqh` and forward-declares `CLogger`. The money modules
(`RiskEngine`, `PropFirmEngine`, `ExecutionEngine`, `TradeManagement`) do
not include it, and the signal side does not include them. **The
restriction is enforced by the include graph, not by discipline** — a
signal module cannot reach `ACCOUNT_EQUITY` through any type it can see.

Arrows point from dependency to dependent. There is no arrow from any money
module back into any signal module. `LiquiditySniper.mq5` contains **no
trading logic** — it is `OnInit`/`OnTick`/`OnTimer`/`OnDeinit` wiring, roughly
250 lines, and it is the only file that knows the order of operations.

### 1.3 Shared types (`Types.mqh`)

```cpp
enum ENUM_TARGET_MODE   { TARGET_NEXT_LIQUIDITY, TARGET_FIXED_R };
enum ENUM_RESET_CLOCK   { CLOCK_WORST_OF_ALL, CLOCK_UTC, CLOCK_CET, CLOCK_GMT2, CLOCK_GMT3 };
enum ENUM_LOG_LEVEL     { LOG_SILENT, LOG_ERROR, LOG_TRADE, LOG_SIGNAL, LOG_VERBOSE };
enum ENUM_LEVEL_SOURCE  { SRC_PIVOT, SRC_PREV_DAY, SRC_SESSION, SRC_ROUND };
enum ENUM_LOCK          { LOCK_NONE, LOCK_DAILY_SOFT, LOCK_DAILY_HARD,
                          LOCK_DD_SOFT, LOCK_DD_HARD, LOCK_STREAK, LOCK_SPREAD,
                          LOCK_NEWS, LOCK_FRIDAY, LOCK_ROLLOVER, LOCK_MARGIN,
                          LOCK_CONNECT, LOCK_SPECS, LOCK_DEMO };
enum ENUM_REJECT_STAGE  { RJ_NONE, RJ_NO_SWEEP, RJ_REGIME_ATR, RJ_REGIME_ADX,
                          RJ_SESSION, RJ_DISPLACEMENT, RJ_LEVEL_AGE,
                          RJ_STOP_TOO_WIDE, RJ_STOP_TOO_TIGHT, RJ_RR_TOO_LOW,
                          RJ_SPREAD, RJ_LOTS_BELOW_MIN, RJ_MAX_POSITIONS,
                          RJ_OPPOSING, RJ_PROPFIRM_LOCK, RJ_SEND_FAILED };

struct LiquidityLevel  { double price; datetime formed_time; int formed_bar;
                         int touch_count; bool swept; datetime swept_time;
                         bool is_high; ENUM_LEVEL_SOURCE source; };

struct SweepEvent      { bool valid; int direction; double level_price;
                         int level_touches; datetime level_formed;
                         double break_open, break_high, break_low, break_close;
                         double displacement_atr; int levels_killed;
                         datetime bar_time; };

struct RegimeState     { double atr, atr_median, atr_ratio, adx;
                         bool in_session, expansion_ok; ENUM_REJECT_STAGE reject; };

struct TradePlan       { bool valid; int direction; double entry, stop, target;
                         double risk_price, reward_risk, lots, atr_at_signal;
                         ENUM_REJECT_STAGE reject; datetime signal_bar;
                         string source_name; };

struct PositionState   { ulong ticket; int direction; double entry, stop_initial,
                         target, r_distance; bool r_approx; datetime open_time;
                         int bars_held; double peak_r, trough_r;
                         bool stop_verified; };

struct SymbolSpecs     { bool valid; string why_invalid; double point; int digits;
                         double tick_size, tick_value, contract_size;
                         double volume_min, volume_max, volume_step;
                         int stops_level_pts, freeze_level_pts;
                         bool spread_float; long filling_modes, trade_mode;
                         double money_per_lot_per_price; };
```

`SymbolSpecs` collects every runtime-read value from §4.2 into one struct
owned by one module. No literal from it (`100`, `0.01`, `10`) may appear
anywhere else in the codebase.

`RJ_NONE` is the zero value so that a zeroed `TradePlan` cannot masquerade
as a specific rejection. `RJ_OPPOSING` is set by the orchestrator (the
no-hedging rule) and `RJ_STOP_TOO_TIGHT` by `RiskEngine`
(`SYMBOL_TRADE_STOPS_LEVEL`); every other value is set by a signal module.
`TradePlan.source_name` carries `ISignalProvider::Name()` so no CSV row can
be ambiguous about which strategy produced it.

`direction` is `+1` long / `-1` short throughout. **`0` is never a valid
direction** — it is the "no signal" sentinel and any function returning it
must also set a `reject` code.

---

### 1.4 `LiquidityEngine`

**Responsibility.** Maintain the registry of live liquidity levels, from four
sources, with merge-on-equal, FIFO eviction and age expiry. This is the MQL5
mirror of Pine lines 197–262.

**State owned.**
`LiquidityLevel m_hi[]`, `LiquidityLevel m_lo[]` (insertion-ordered),
`datetime m_last_bar`, `double m_last_pdh`, `m_last_pdl`, `m_last_round`,
`int m_last_sess_id`, `double m_sess_hi`, `m_sess_lo`.

**Public interface.**
```cpp
bool   Init(const string symbol, const ENUM_TIMEFRAMES tf,
            const int pivot_len, const double eq_tol_atr,
            const int max_age_bars, const int max_levels,
            const bool use_prev_day, const bool use_session,
            const bool use_round, const double round_step);

// Called ONCE per closed bar. atr is the closed-bar ATR(14) at shift 1.
// Registers new pivots, prev-day H/L, session H/L and round levels,
// expires levels older than max_age_bars, evicts FIFO past max_levels.
bool   OnNewBar(const datetime bar_time, const double atr);

int    Count(const bool is_high)             const;   // total slots incl. swept
int    CountLive(const bool is_high)         const;   // unswept only
bool   Get(const bool is_high, const int idx, LiquidityLevel &out) const;
bool   MarkSwept(const bool is_high, const int idx, const datetime when);

// Nearest UNSWEPT level strictly above / below a price. Returns 0.0 if none.
double NearestLiveAbove(const double price)  const;
double NearestLiveBelow(const double price)  const;

int    Snapshot(LiquidityLevel &dst[])       const;   // parity dump / logging
void   Reset();
```

**Must NOT know about:** open positions, lots, equity, spread, orders,
prop-firm state, the trade direction convention, or `_Point`. It is a pure
price-structure container. It does not decide whether a break is tradable —
only `SweepEngine` does.

**Parity-critical implementation notes.**
- Pivot candidate offset is `pivot_len + 2` bars back from the just-closed
  bar. See §5.3 — using `pivot_len + 1` is one bar of look-ahead relative to
  Pine and is the single most likely parity break.
- On merge, `formed_bar`/`formed_time` keep the **original** value and
  `price` becomes `max` (highs) / `min` (lows). Pine does the same
  (line 206) and does not refresh the bar.
- Prev-day, session and round levels are registered with `formed_bar =
  current bar`, not the bar the extreme actually occurred on. This is
  deliberate parity with Pine lines 243/251/259 and it means `minLvlAge`
  counts from *registration* for those three sources.
- Eviction is `array.shift` semantics: remove index 0, the oldest by
  insertion order, not the oldest by price age.

---

### 1.5 `SweepEngine`

**Responsibility.** On a closed bar, determine which live levels were taken
out, mark them swept, and emit at most one `SweepEvent` per side describing
the *most extreme* level broken.

**State owned.** A pointer to `CLiquidityEngine` (borrowed, not owned) and
`datetime m_last_bar` for idempotence.

**Public interface.**
```cpp
bool Init(CLiquidityEngine *levels, const int min_level_age_bars,
          const double displacement_atr, const bool require_close);

// Evaluates the just-closed bar. Marks EVERY broken level swept (not just the
// extreme one) before returning, because TargetEngine's "next liquidity" read
// must not see a level this bar already took out.
// Returns true if at least one side produced a valid event.
bool DetectOnClosedBar(const datetime bar_time, const MqlRates &bar,
                       const double atr, const int bar_index_now,
                       SweepEvent &hi_event, SweepEvent &lo_event);

bool DisplacementOk(const MqlRates &bar, const double atr) const;  // |close-open| >= k*atr
```

**Must NOT know about:** whether to trade continuation or reversal, risk,
lots, the account, or orders. It reports *what happened to the levels*, not
what to do about it.

**Ordering contract (load-bearing).** `DetectOnClosedBar` must run to
completion, marking all broken levels swept, *before* `TargetEngine` queries
`NearestLiveAbove/Below`. This mirrors Pine's script order (sweep loops at
lines 308–327, `nextLiq` defined and used afterwards at 337). Getting this
backwards produces targets sitting on levels the entry bar just destroyed.

---

### 1.6 `RegimeEngine` — the expansion gate

**Responsibility.** Answer one question on closed bars only: *is volatility
compressed enough that a large move is likely to follow?*

Evidence this exists at all — E-019/E-020, `JARVIS/state/EXPERIMENTS.md`,
replicated on GOLD 15m and 1h independently:

| Condition | P(3+ ATR move in 40 bars), 15m | 1h |
|---|---|---|
| ADX 0–15 | 91% | 90% |
| ADX ≥ 40 | 68% | 66% |
| ATR ≥ 2× its median | — | **25%** |
| ATR 0.8–1.0× median | 93% | 83% |

Evidence for how to *use* it — E-020, four markets, full costs, identical
Donchian entries:

| Use | Average expectancy |
|---|---|
| fixed 1R target | −0.029R |
| fixed 3R target | +0.029R |
| **gate only (trade only when expansion likely)** | **+0.108R** |
| adaptive target (big when expansion likely) | +0.001R |

**Adaptive targeting measured worse than a plain fixed 3R.** The gate is a
boolean veto. It never touches the target. `TargetEngine` has no reference to
`RegimeEngine` and cannot acquire one.

#### E-021 corrects E-020, and this module must ship accordingly

**The gate failed out-of-sample.** E-020's table above was **not** split
in-sample/out-of-sample. `autosearch.py` then ran 672 tests (168 configs ×
4 markets) with a chronological 70/30 split and the out-of-sample run
executed **once**, on the top handful:

| config | in-sample | out-of-sample |
|---|---|---|
| sweep_continuation **+ gate** adx25/1.15, rr3 | 4/4 markets, **+0.166R** | 1/4 markets, **−0.109R** |
| sweep_continuation **+ gate** adx20/1.0, rr3 | 3/4, +0.185R | 1/2, −0.158R |
| ma_cross, **gate = none**, rr3 | 3/4, +0.094R | 3/3, **+0.208R** |

**The gated configs are the ones that collapsed, and the two best
out-of-sample configs both had `gate = none`.** The gate's apparent
+0.108R in E-020 was substantially in-sample fitting. The luck bar at
N=672 is t=3.61; the best out-of-sample t anywhere was +2.24.

What survives and what does not:
- **E-019 still stands.** That compressed volatility *precedes* larger
  moves was a direct measurement of the price series, replicated on two
  timeframes over different periods. It was never a fitted strategy and it
  cannot overfit in the way E-021 caught.
- **"Gating on it improves a traded system" does not stand.**

**Consequences for this module, and they are binding:**

1. **Do not hard-gate.** The gate must be cheap to turn off, and off must
   be a supported configuration, not a code path nobody has exercised.
   `InpMaxAtrRatio >= 3.00` together with `InpMaxAdx = 60` disables it in
   practice with no code change.
2. `InpMaxAtrRatio = 1.15` and `InpMaxAdx = 25` are the **Pine defaults**,
   carried across for parity — they are *not* a validated setting, and
   §5.5's parity run is a comparison of two implementations, not evidence
   about either one's edge.
3. Phase 2 must run the gated and ungated configurations through
   walk-forward **as two separate hypotheses**, and ship whichever wins
   out-of-sample. If neither wins, ship ungated: it is the simpler system
   and it has one fewer thing to be wrong about.
4. The `StatisticsEngine` reject histogram counts `RJ_REGIME_ATR` and
   `RJ_REGIME_ADX` separately from every other refusal precisely so the
   live cost of this gate is measurable rather than assumed.

**State owned.** Indicator handles (`m_h_atr`, plus hand-rolled DMI buffers),
a rolling 50-value ATR ring buffer for the median, cached closed-bar values,
`datetime m_last_bar`.

**Public interface.**
```cpp
bool   Init(const string symbol, const ENUM_TIMEFRAMES tf,
            const int atr_period,        // 14
            const int atr_median_len,    // 50
            const int adx_period);       // 14

bool   Update(const datetime bar_time);  // reads shift 1 ONLY; idempotent per bar

double Atr()       const;    // ATR(14) at shift 1
double AtrMedian() const;    // median of the last 50 closed-bar ATR values
double AtrRatio()  const;    // Atr()/AtrMedian(), 1.0 if median <= 0
double Adx()       const;    // Wilder ADX(14) at shift 1, hand-rolled (see 5.4)

bool   InSession(const datetime t, const int from_hour_utc,
                 const int to_hour_utc) const;   // wraps midnight correctly

bool   ExpansionOk(const double max_atr_ratio, const double max_adx,
                   const int from_hour_utc, const int to_hour_utc,
                   RegimeState &out) const;
```

**Must NOT know about:** levels, sweeps, positions, money, targets. It reads
price series and returns a boolean plus its inputs for logging.

**Hard constraint.** Every read is `shift >= 1`. There is **no** `shift 0`
read anywhere in this module. The `iATR`/DMI handles are queried with
`CopyBuffer(handle, 0, 1, n, buf)`.

---

### 1.7 `EntryEngine`

**Responsibility.** Turn `(SweepEvent, RegimeState, closed bar)` into a
directional `TradePlan` with entry and stop filled in. Nothing else.

**State owned.** Only the configured constants. **Deliberately stateless
across bars** — it holds no armed/pending state, because the retest path is
not being built (see §6).

**Public interface.**
```cpp
bool Init(const double stop_buffer_atr, const double max_stop_atr);

// Continuation mapping, per findings/08_sweep_direction.md:
//   a broken level ABOVE (sell-side liquidity taken)  -> LONG   (+1)
//   a broken level BELOW (buy-side liquidity taken)   -> SHORT  (-1)
// If both sides broke on the same bar the plan is INVALID (reject
// RJ_NO_SWEEP with reason "both sides"): the bar is an outside bar and the
// direction is unknowable at its close.
bool Evaluate(const SweepEvent &hi_event, const SweepEvent &lo_event,
              const RegimeState &regime, const MqlRates &signal_bar,
              const double atr, TradePlan &plan);
```

**Stop formula (exact, and matching Pine line 411):**
```
long :  stop = signal_bar.low  - stop_buffer_atr * atr
short:  stop = signal_bar.high + stop_buffer_atr * atr
risk_price = |entry - stop|,  entry = signal_bar.close
reject RJ_STOP_TOO_WIDE if risk_price > max_stop_atr * atr
reject if risk_price <= 0
```
Pine writes `math.min(low, ext)` where `ext = max(high, sweptHi)`. For a long,
`ext >= high >= low`, so the `min` always returns `low` and the swept level
never influences the stop. That term is a no-op in the non-retest path. The
MQL5 must reproduce the *behaviour* (`low - buf*atr`), and §5.6 records this
as a known Pine dead branch to be either deleted or fixed on both sides
together — never on one side only.

**Must NOT know about:** equity, lots, tick value, spread, `_Point`, the
broker, or prop-firm state. It works purely in price. The word `lots` appears
in `TradePlan` but `EntryEngine` never writes it.

---

### 1.8 `TargetEngine`

**Responsibility.** Fill `plan.target` and `plan.reward_risk`, and reject on
`reward_risk < min_rr`.

**State owned.** Borrowed pointer to `CLiquidityEngine`, plus the three
configured constants.

**Public interface.**
```cpp
bool Init(CLiquidityEngine *levels, const ENUM_TARGET_MODE mode,
          const double fixed_r, const double min_rr);

// Requires SweepEngine to have already marked this bar's broken levels swept.
// TARGET_NEXT_LIQUIDITY: nearest LIVE level beyond entry in the trade's
//   direction; if none exists, falls back to fixed_r (Pine line 415 does the
//   same via `na(lvlTp)`).
// TARGET_FIXED_R: entry + direction * fixed_r * plan.risk_price.
// Sets plan.reject = RJ_RR_TOO_LOW and plan.valid = false if RR < min_rr.
bool Resolve(TradePlan &plan);
```

**Must NOT know about:** the regime (E-020: adaptive targets measured worse
than fixed), the account, open positions, or how long a trade has been held.
The target is set once, at entry, and is never recomputed. There is no
"target extension", no "runner", no "partial".

---

### 1.9 `TradeManagement`

**Responsibility.** Everything that happens to a position *after* it is
filled: bar counting, time exit, the optional (default-off) trail, restart
adoption, and the stop-integrity check.

**State owned.** `PositionState m_pos[]`, rebuilt from the broker on
`Adopt()`. It is a cache, never the source of truth; the broker is.

**Public interface.**
```cpp
bool Init(const ulong magic, const string symbol, const ENUM_TIMEFRAMES tf,
          const int max_hold_bars, const double trail_arm_r,
          const double trail_atr_mult,
          CExecutionEngine *exec, CLogger *log, CStatisticsEngine *stats);

// Rebuild m_pos from PositionsTotal() filtered by magic AND symbol.
// Three-tier r_distance recovery, see 4.4. Returns count adopted.
int  Adopt();

// The ONLY place management logic acts. Never called from a mid-bar tick.
void OnNewBar(const datetime bar_time, const double atr);

// Per-tick, and the ONLY per-tick work this module does:
// verifies every position still carries a broker-side stop. See 4.1.
void VerifyStopsOnTick();

int    CountOpen()            const;
int    CountOpen(const int direction) const;   // the no-hedging rule
double TotalOpenRiskCash()    const;   // sum |entry-stop| * money_per_price * lots
bool   GetState(const ulong ticket, PositionState &out) const;
void   FlattenAll(const string reason);   // called by the orchestrator only
```

**The three exit rules, and there are only three.**
1. **Broker-side take profit** at `plan.target`, attached at `OrderSend`.
2. **Broker-side stop loss** at `plan.stop`, attached at `OrderSend`.
3. **Time exit** at `max_hold_bars` closed bars held (default 40; the
   `06_exit_experiment.md` winner on gold was `time 20` at +0.201R, and
   `movesize.py` measures forward travel over a 40-bar horizon — 40 is the
   horizon the gate was measured on).

Plus one optional, **off by default**: a Chandelier trail that arms only at
`trail_arm_r` R **and is disabled entirely when `trail_arm_r == 0.0`, which
is the shipped default.**

**Must NOT, ever:**
- Move a stop toward entry. `ModifyStop` is monotone: for a long,
  `new_sl > current_sl` or the call is refused inside this module.
- Move the stop to break-even. There is no break-even code path, no
  `T_MicroLock`, no `T_EarlyBE`, no `T_BeArmPts`. Measured cost of that
  pattern: **−0.161R gold, −0.188R US500, −0.308R EURUSD, −0.293R GBPUSD** —
  worst rule on 4/4 markets (`findings/06_exit_experiment.md`). v19.18 armed
  it at 0.24R.
- Close a position at market for any reason except the time exit and an
  explicit `FlattenAll` from `PropFirmEngine`. There is no peak-giveback, no
  basket lock, no trade lock, no exhaustion, no chop-stall, no momentum fade.
  v19.18 had 32 such tags; 21 of them fired zero times in 279 trades.
- Know about levels, sweeps, regime, or the next signal.

---

### 1.10 `RiskEngine`

**Responsibility.** Convert money into lots and back, using symbol specs read
at runtime. It is the *only* module that touches `SymbolInfo*` sizing fields.

**State owned.** A cached `SymbolSpecs` struct, refreshed on `OnInit`, on
every new bar, and after any `TRADE_RETCODE_INVALID_VOLUME`.

**Public interface.**
```cpp
bool   Init(const string symbol);
bool   RefreshSpecs();          // point, digits, volume min/max/step,
                                // tick value, tick size, contract size,
                                // stops level, freeze level, margin mode
bool   SpecsValid(string &why) const;   // false => LOCK_SPECS, EA refuses to trade

double MoneyPerLotPerPrice() const;     // tick_value / tick_size
double RiskCashForPct(const double pct) const;   // pct/100 * ACCOUNT_EQUITY

// Returns 0.0 and sets reason if the resulting size is below VOLUME_MIN.
// NEVER rounds up: rounding up increases risk beyond the configured budget.
double LotsForRisk(const double stop_distance_price, const double risk_cash,
                   ENUM_REJECT_STAGE &reject) const;

double NormalizeLots(const double lots) const;   // floor to VOLUME_STEP, clamp
double MinStopDistancePrice() const;   // SYMBOL_TRADE_STOPS_LEVEL * SYMBOL_POINT
double FreezeDistancePrice()  const;
double NormalizePrice(const double p) const;     // to SYMBOL_DIGITS
bool   MarginOkFor(const int direction, const double lots, const double price) const;
bool   GetSpecs(SymbolSpecs &out) const;
string SpecDump() const;   // printed at OnInit, LOG_ERROR — see 4.2
```

**The sizing formula, in full:**
```
money_per_lot_per_price = SYMBOL_TRADE_TICK_VALUE / SYMBOL_TRADE_TICK_SIZE
risk_cash               = InpRiskPctPerTrade / 100.0 * ACCOUNT_EQUITY
raw_lots                = risk_cash / (stop_distance_price * money_per_lot_per_price)
lots                    = floor(raw_lots / VOLUME_STEP) * VOLUME_STEP
if (lots > VOLUME_MAX) lots = VOLUME_MAX
if (lots < VOLUME_MIN) -> return 0.0, reject = RJ_LOTS_BELOW_MIN   // SKIP THE TRADE
```
The last line is not a formality. If the smallest tradable lot exceeds the
risk budget, the correct action is **not to trade**, not to trade the minimum.
v19.18 shipped `T_FixedLots = 0.03` and returned at line 7432 before reaching
any aggregate ceiling, so `AutoMaxExposurePct`, `InpMaxTotalLots` and
`T_MaxRiskStackMult` were all dead code — position size had no relationship to
stop distance, volatility, or equity.

**Must NOT know about:** signals, levels, regime, prop-firm locks, or the
`CTrade` object. It computes; it does not act.

---

### 1.11 `PropFirmEngine`

Specified in full in §3. Interface summary:

```cpp
bool   Init(const double daily_loss_pct, const double max_dd_pct,
            const int max_consecutive_losses, const ENUM_RESET_CLOCK clock,
            const int news_blackout_min, const ulong magic, CLogger *log);

void   OnTick();     // equity poll + anchor roll + all lock evaluation
void   OnTimer();    // identical work on a 250 ms timer, for tickless periods

bool   CanOpenNewPosition(ENUM_LOCK &lock, string &reason) const;
bool   MustFlatten(ENUM_LOCK &lock, string &reason) const;

void   RegisterClosedTrade(const double profit_cash, const datetime close_time);

double Equity()             const;
double Balance()            const;
double EffectiveAnchor()    const;
double DailyFloorEquity()   const;
double DailyLossCash()      const;
double DailyHeadroomPct()   const;
double HighWaterMark()      const;
double DrawdownFloorEquity()const;
int    ConsecutiveLosses()  const;
bool   DdHardLatched()      const;

bool   Persist();    // GlobalVariables, prefixed LS_<magic>_
bool   Restore();
string StatusLine()  const;
```

**Must NOT know about:** levels, sweeps, regime, entries, or targets. It knows
equity, balance, the clock, and how to say no.

---

### 1.12 `ExecutionEngine`

**Responsibility.** The only module permitted to call `CTrade` /
`OrderSend` / `OrderSendAsync`. Owns filling-mode negotiation, deviation,
spread measurement, and the retry state machine.

**State owned.** `CTrade m_trade`, negotiated `ENUM_ORDER_TYPE_FILLING`, and a
`PendingSend` struct (`attempts`, `next_attempt_ms`, the original `TradePlan`,
a unique `comment_token`).

**Public interface.**
```cpp
bool  Init(const string symbol, const ulong magic, const int deviation_points,
           const int retry_count, const int retry_delay_ms,
           CRiskEngine *risk, CLogger *log);
bool  RefreshFillingMode();          // from SYMBOL_FILLING_MODE
ENUM_ORDER_TYPE_FILLING FillingMode() const;

double SpreadPrice() const;          // (ask - bid), in price, live
bool   SpreadAcceptable(const double stop_distance_price,
                        const double max_pct_of_stop, double &spread_pct) const;

// Sends WITH sl and tp attached. Verifies POSITION_SL != 0 after the fill.
bool  OpenPosition(const TradePlan &plan, ulong &ticket, string &err);

// unlimited_retries = true when the caller is a HARD LOCK: failing to close
// under LOCK_DAILY_HARD is the one situation where giving up is not an option.
bool  ClosePosition(const ulong ticket, const string reason,
                    const bool unlimited_retries = false);
bool  ModifyStop(const ulong ticket, const double new_sl, const double new_tp);

// Retry state machine. Called from OnTick. Contains NO Sleep().
void  ProcessPending();
bool  HasPending() const;
void  CancelPending(const string reason);
```

**Must NOT know about:** why a trade is being taken, prop-firm limits (it is
called only after `PropFirmEngine` has said yes), or level structure.

**Hard constraint — no `Sleep()` in the tick path.** v19.18 called `Sleep()`
inside `ModifySLTP` (line 6988) and `Open` (line 11456), blocking `OnTick`
for `T_OrderRetryMs × T_OrderRetryN` and delaying every other position's
management. Retries here are scheduled against `GetTickCount()` and executed
on subsequent ticks.

---

### 1.13 `Logger`

**Responsibility.** Structured output to the Experts log and to a CSV that the
parity harness and `study.py` can both read.

**State owned.** File handle, log level, a small line buffer.

```cpp
bool Init(const ENUM_LOG_LEVEL level, const string csv_path, const string build_id);
void Event (const ENUM_LOG_LEVEL lvl, const string tag, const string msg);
void Signal(const SweepEvent &s, const RegimeState &r, const TradePlan &p,
            const string outcome);
void Reject(const ENUM_REJECT_STAGE stage, const string detail);
void Fill  (const ulong ticket, const TradePlan &p, const double fill_price,
            const double slippage_price);
void Exit  (const ulong ticket, const string tag, const double profit_cash,
            const double r_realized, const double r_peak);
void Lock  (const ENUM_LOCK lock, const string reason, const double equity,
            const double floor_eq);
void BarState(const datetime bar_time, const RegimeState &r,
              const int live_hi, const int live_lo,
              const string provider_row);              // parity CSV row, §5.1
void Flush();
ENUM_LOG_LEVEL Level() const;
```

`Init` prints `build_id` (a `#define EA_BUILD` string) at `OnInit`. This is
the one habit worth keeping verbatim from v19.18 — it is the fix for not
knowing which build is actually running.

**Must NOT:** make decisions, or be absent from any rejection path. Every
`return false` in the signal chain writes a `Reject()`.

---

### 1.14 `StatisticsEngine`

**Responsibility.** Port of v19.18's `QSP_TrackLive` / `QSP_TagRecord` /
`QSP_Recompute` — the one genuinely valuable artefact in the old file. It
measures MFE/MAE per ticket in R, keeps a per-exit-tag ledger of *points taken
versus peak offered*, and — the key part — records **suppressed** attempts so
the cost of every veto is visible.

```cpp
bool Init(CLogger *log, const ulong magic);
void TrackOpenPositions();        // per tick: update peak_r / trough_r per ticket
void RecordReject(const ENUM_REJECT_STAGE stage);
void RecordFill(const ulong ticket, const double r_distance);
void RecordExit(const ulong ticket, const string tag,
                const double r_realized, const double r_peak);
void RecordSuppressed(const ulong ticket, const string tag,
                      const double r_now, const double r_peak);
void RecordLock(const ENUM_LOCK lock);
string Report() const;            // printed on OnDeinit and on demand
bool   Persist();  bool Restore();
```

**Slot management (fixes v19.18 S2).** The old `TrackProgress` used
`if(g_pCount >= 200) g_pCount = 0;` — a blind wrap that overwrote slot 0 while
its position was still open, so a live position could inherit another ticket's
progress record. Here: a fixed array of 64 slots, each with an `in_use` flag;
a slot is only reclaimed when its ticket no longer appears in
`PositionsTotal()`; if all 64 are in use the engine logs `STATS_FULL` and
stops recording rather than corrupting a slot.

**Must NOT:** influence any decision. It is read-only with respect to trading.
If `StatisticsEngine` were deleted the EA's behaviour would be identical.

---

### 1.15 `ISignalProvider` — the swappable signal layer

This is the response to measured finding 5, and it is the most important
structural decision in the tree.

**The finding.** Nothing in this repository has cleared the multiple-testing
bar. E-012: with N configurations tried and no real edge, the best has an
expected t-statistic of about `sqrt(2 ln N)`. This project has now run
~100 variants, so the bar is **~3.0**. The best out-of-sample t observed
anywhere is **+2.24** (E-021). Sweep-continuation is `PROMISING` and
nothing stronger.

**E-021 is the concrete reason for an abstraction rather than a
preference.** Under a proper chronological 70/30 split, **7 of 8 in-sample
winners failed out-of-sample**, and the single best in-sample configuration
inverted completely:

| config | in-sample | out-of-sample |
|---|---|---|
| sweep_continuation + gate adx25/1.15, rr3 | 4/4 markets, **+0.166R** | 1/4 markets, **−0.109R** |
| ma_cross, no gate, rr3 | 3/4, +0.094R | 3/3, +0.208R |

The strategy this EA implements is therefore a **replaceable part**, and
the probability it is replaced is high. The durable asset is the money
layer — `RiskEngine`, `PropFirmEngine`, `ExecutionEngine`,
`TradeManagement` — and it must survive the strategy being deleted.
Welding a strategy into an execution layer means cutting it out later, and
that surgery is where 20,695-line EAs come from.

**The contract.**

```cpp
class ISignalProvider
  {
public:
   virtual          ~ISignalProvider(void) {}
   virtual string    Name(void) const = 0;
   virtual string    Version(void) const = 0;
   virtual bool      Init(const string symbol, const ENUM_TIMEFRAMES tf,
                          CLogger *log, string &why) = 0;
   virtual int       WarmupBars(void) const = 0;
   virtual bool      Evaluate(const datetime bar_time, TradePlan &plan) = 0;
   virtual bool      OnNewBarObserve(const datetime bar_time) = 0;
   virtual string    ParityRow(const datetime bar_time) const = 0;
   virtual string    Diagnostics(void) const = 0;
   virtual void      Reset(void) = 0;
  };
```

Six rules, all enforceable by review:

1. Called **once per closed bar**, never per tick.
2. Reads **shift ≥ 1 only**. No shift-0 read may influence a plan.
3. Returns a `TradePlan` **in price**. It never sees equity, lots, tick
   value, spread, the account or a prop-firm lock — and it has no way to
   acquire them, because none of those types are reachable through
   `ISignalProvider.mqh`, which includes only `Types.mqh`.
4. Never sends, modifies or closes an order.
5. **Idempotent per bar.** Calling it twice for the same `bar_time`
   produces the same plan and does not mutate registry state twice.
6. Every refusal sets a specific `ENUM_REJECT_STAGE`. Returning `false`
   with `RJ_NONE` is a bug.

`OnNewBarObserve()` exists separately from `Evaluate()` because the
registry must stay continuous even on bars the EA cannot trade (locked, at
the position limit, spread too wide). Implementations that keep rolling
state do that work in `OnNewBarObserve`, and the orchestrator calls it on
**every** closed bar before deciding whether to call `Evaluate`. Without
this split, a day spent under `LOCK_DAILY_SOFT` would leave a hole in the
level registry and the parity CSV.

**`CLiquiditySniperSignal`** is the one concrete implementation. It owns
the five sub-engines by value and owns the call order, and it contains no
strategy arithmetic of its own:

```
1. RegimeEngine::Update(bar_time)              shift-1 reads only
2. LiquidityEngine::OnNewBar(bar_time, atr)    register new levels
3. SweepEngine::DetectOnClosedBar(...)         MARK ALL BROKEN LEVELS SWEPT
4. RegimeEngine::ExpansionOk(...)              the boolean veto
5. SweepEngine::DisplacementOk(...)
6. EntryEngine::Evaluate(...)                  direction, entry, stop
7. TargetEngine::Resolve(plan)                 target, R:R    <- AFTER step 3
```

Steps 3 and 7 must not be reordered — that is `SweepEngine`'s ordering
contract (§1.5) and parity test P-10. Steps 4 and 5 run before 6 because
they are cheap and because the reject code recorded should be the *first*
reason, which is what the `StatisticsEngine` ledger counts.

**Swapping the strategy is:** write one new class implementing
`ISignalProvider`, change one `new` in `LiquiditySniper.mq5`. No other file
changes. Two strategies never run in one EA instance — that was v19.18's
three-engine design, of which two engines were dead in the shipped
defaults and the file said so itself at line 19169. A second strategy gets
a second EA instance, a second magic number, and its own measurements.

**Cost of the abstraction, stated honestly.** One virtual call per closed
bar, which is free, plus one indirection that a reader has to follow to
find the logic. That is the entire price, and it buys the ability to
delete a `PROMISING` strategy without touching the code that keeps the
account alive.

---

## 2. THE PARAMETER BUDGET

**Hard cap: 25 inputs. Actual: 25.**
Of these, **16 are optimizable degrees of freedom** and 9 are
compliance/operational switches that will never be swept. The distinction
matters: overfitting risk scales with the optimizable count, and 16 against a
target of "tens of trades per parameter" needs roughly 300–500 trades to fit
honestly — which is achievable. 748 needed tens of thousands and the old EA
had 279.

### 2.1 Every input, with default and range

#### STRUCTURE — 4 optimizable
| # | Input | Type | Default | Range | Note |
|---|---|---|---|---|---|
| 1 | `InpPivotLen` | int | 8 | 2 … 50 | Pine `pivLen`. Bars each side. Level is only *known* `len` bars later and the code respects it. |
| 2 | `InpEqualTolAtr` | double | 0.20 | 0.02 … 1.00 | Pine `eqTol`. Merge distance for equal highs/lows, × ATR. |
| 3 | `InpMinLevelAgeBars` | int | 5 | 0 … 100 | Pine `minLvlAge`. A level formed moments ago has no resting orders behind it. |
| 4 | `InpDisplacementAtr` | double | 1.00 | 0.00 … 3.00 | Pine `dispAtr`. `0.0` disables the displacement requirement (replaces Pine's separate `needDisp` bool). |

#### REGIME GATE — 3 optimizable
| # | Input | Type | Default | Range | Note |
|---|---|---|---|---|---|
| 5 | `InpMaxAtrRatio` | double | 1.15 | 0.50 … 3.00 | Pine `maxSqueeze`. `>= 3.00` effectively disables. Measured: ATR ≤ 1.0× median → 90% P(3+ATR move); 2× median → 25%. |
| 6 | `InpMaxAdx` | double | 25.0 | 10 … 60 | Pine `maxAdx`. Measured: ADX 0–15 → 90%; ADX ≥ 40 → 66%. |
| 7 | `InpSessionUtc` | string | `""` | `""` or `"HH-HH"` | `""` = all hours. `"04-12"` = 04:00–11:59 UTC. Wraps midnight. Measured on GOLD 15m only (04–12 UTC: 89–93%; 14–16 UTC: 62%) — off by default because it is one instrument. |

#### RISK AND SIZING — 4 optimizable
| # | Input | Type | Default | Range | Note |
|---|---|---|---|---|---|
| 8 | `InpRiskPctPerTrade` | double | 0.35 | 0.05 … 1.00 | `PROP_FIRMS.md` §7. 0.35 × 2 concurrent = 0.70% max open risk. |
| 9 | `InpStopBufferAtr` | double | 0.30 | 0.00 … 1.50 | Pine `slBuf`. Stop beyond the break-bar extreme. |
| 10 | `InpMaxStopAtr` | double | 2.50 | 0.50 … 6.00 | Pine `maxRiskAtr`. Reject the setup if the stop is wider. |
| 11 | `InpMaxConcurrentPositions` | int | 2 | 1 … 5 | Pine `maxTrades` is 3; **2 here** so that `InpRiskPctPerTrade × N ≤ 0.70%` matches `PROP_FIRMS.md` §7 `max_total_open_risk_pct`. Divergence from Pine is deliberate and is a *position-count* difference, not a signal difference — parity tests compare signals, not fills. |

#### TARGET AND EXIT — 5 optimizable
| # | Input | Type | Default | Range | Note |
|---|---|---|---|---|---|
| 12 | `InpMinRewardRisk` | double | 1.20 | 0.50 … 5.00 | Pine `minR`. |
| 13 | `InpTargetMode` | enum | `TARGET_NEXT_LIQUIDITY` | 2 values | Pine `tpMode`. |
| 14 | `InpFixedTargetR` | double | 3.00 | 0.50 … 10.0 | Pine `tpR` is 2.0; **3.0 here**. `06_exit_experiment.md`: fixed 3R beat fixed 1R by 0.058R on average and 30% wins at 3R beats 53% wins at 1R (+0.181R vs +0.054R). Also the fallback when no live level exists beyond entry. |
| 15 | `InpMaxHoldBars` | int | 40 | 0 … 500 | `0` = off. Time exit. `06_exit_experiment.md` best gold exit was `time 20` (+0.201R); `movesize.py` measures the 40-bar forward horizon the gate was validated on. **Both 20 and 40 must be walk-forwarded before either is trusted.** |
| 16 | `InpTrailArmR` | double | **0.00** | 0.00 … 5.00 | **`0.00` = trail entirely disabled, the shipped default.** If enabled it must be ≥ 1.0. Standoff is fixed at `TRAIL_ATR_MULT 2.0` in source, not an input — a disabled feature does not get a tuning knob. |

#### PROP-FIRM COMPLIANCE — 5, not optimizable
| # | Input | Type | Default | Range | Note |
|---|---|---|---|---|---|
| 17 | `InpDailyLossLimitPct` | double | 3.00 | 0.50 … 10.0 | Strictest found: FundingPips Zero / 2 Step Pro. Engine acts at 1/3 and 1/2 of it (§3.4). |
| 18 | `InpMaxDrawdownPct` | double | 6.00 | 1.00 … 20.0 | Strictest overall floor found. Assumed **trailing** always. |
| 19 | `InpMaxConsecutiveLosses` | int | 4 | 0 … 20 | `0` = off. Blocks new entries until the next daily anchor roll. |
| 20 | `InpResetClock` | enum | `CLOCK_WORST_OF_ALL` | 5 values | §3.2. |
| 21 | `InpNewsBlackoutMin` | int | 0 | 0 … 360 | `0` = off, **and off is the honest default** because there is no verified calendar feed in this build (§3.7). |

#### EXECUTION AND OPERATIONS — 4, not optimizable
| # | Input | Type | Default | Range | Note |
|---|---|---|---|---|---|
| 22 | `InpMaxSpreadPctOfStop` | double | 5.00 | 1.00 … 25.0 | Spread as a fraction of the *planned stop distance*, never an absolute number. `AUDIT_v19_18.md`: M1 gold at 1.4×ATR was 21.4% cost/risk and unsurvivable; the target is <10%, ideally <5%. |
| 23 | `InpMagicNumber` | long | 20260901 | any | Position ownership. |
| 24 | `InpDemoOnly` | bool | **true** | — | `OnInit` returns `INIT_FAILED` on a non-demo account. Removed only by Veer, explicitly, in a session. |
| 25 | `InpLogLevel` | enum | `LOG_SIGNAL` | 5 values | `LOG_VERBOSE` writes the parity CSV row every bar. |

### 2.2 Deliberately NOT inputs (compile-time constants)

These live as `#define` / `const` in `Config.mqh`. They are configurable in
source and reviewable in git, but they are not knobs a backtest can fit.

| Constant | Value | Why it is not an input |
|---|---|---|
| `ATR_PERIOD` | 14 | Pine `ta.atr(14)`. Changing it breaks parity by definition. |
| `ATR_MEDIAN_LEN` | 50 | Pine `ta.median(atr,50)`. Same. |
| `ADX_PERIOD` | 14 | Pine `ta.dmi(14,14)`. Same. |
| `MAX_LEVELS_PER_SIDE` | 20 | Pine `maxLevels`. A display/memory cap, not an edge parameter. |
| `MAX_LEVEL_AGE_BARS` | 500 | Pine `lvlMaxAge`. Housekeeping. |
| `TRAIL_ATR_MULT` | 2.0 | The trail is off by default. |
| `DEVIATION_POINTS` | 20 | Slippage tolerance; a broker fact, not a strategy choice. |
| `ORDER_RETRY_N` | 3 | §4.5. |
| `ORDER_RETRY_DELAY_MS` | 200 | §4.5. |
| `RETRY_ABORT_DRIFT_FRAC` | 0.25 | Abort a retry if price drifted >25% of the stop distance from plan. |
| `EQUITY_POLL_MS` | 250 | `PROP_FIRMS.md` §7 `poll_interval_ms`. |
| `DAILY_SOFT_FRACTION` | 0.333 | Soft lock at 1/3 of the daily limit. |
| `DAILY_HARD_FRACTION` | 0.50 | Hard flatten at 1/2. |
| `DD_SOFT_FRACTION` | 0.50 | Soft lock at 1/2 of max DD. |
| `DD_HARD_FRACTION` | 0.667 | Hard flatten at 2/3. |
| `FRIDAY_FLATTEN_UTC` | 20:00 | `PROP_FIRMS.md` §7. |
| `MIN_TRADE_DURATION_SEC` | 120 | Defeats HFT/tick-scalping classification everywhere. Enforced as: no time-exit or trail action inside 120 s. Stops and targets still apply. |
| `STATS_SLOTS` | 64 | §1.14. |
| `EA_BUILD` | string | Printed at `OnInit`. |

### 2.3 What is being DELETED from the 748, and why

| Deleted concept | v19.18 evidence | Reason |
|---|---|---|
| **Three engines (TREND / SCALP / APEX)** | `InpUseScalp=false`, `InpUseApex=false`; the file itself says "THIS WHOLE BRANCH IS UNREACHABLE" (line 19169) | Two of three were dead in the shipped defaults. One strategy, one engine. |
| **The 32 exit tags / 35 `CloseTagged` sites** | 21 tags produced **zero** exits across 279 trades | Three exits: stop, target, time. |
| **Eight peak-anchored guards** (TRADE-LOCK, BASKET-LOCK, GIVEBACK, peak trail, ratchet floor, hard giveback cap, PEAK-BANK, SPIKE-PEAK) | Realised exit = the *minimum* of ten competing guards; measured 33% of peak retained (£110 peak → £73.43 handed back on 43 trades) | Structurally guarantees giving back 40–60% of every winner. Arithmetic, not tuning. |
| **All three break-even mechanisms** (`T_MicroLock` @0.24R, `T_EarlyBE` @1.0R, `T_BeArmPts`) | `06_exit_experiment.md`: −0.161R / −0.188R / −0.308R / −0.293R, **worst on 4/4 markets** | The mechanism that destroyed the account. Not reduced — removed. |
| **Adaptive / volatility-scaled targets** | E-020: adaptive +0.001R vs gate-only +0.108R vs fixed 3R +0.029R | Measured worse than a plain fixed target. |
| **`NoiseFloorPts` as a threshold floor** | Every arm and every giveback floored at `spread + 0.60×ATR` ≈ 1.18 pts | Kept as a *diagnostic* only: reject a market/timeframe where the target move is under ~4 bands. Never as an exit threshold. |
| **`PtsScale()` / the "fixed ruler" family** | Scales threshold and band together, so the ratio that decides bankability is unchanged | Solved a problem that scaling cannot solve. |
| **The hold-vote quorum, `holdGrace`, `holdVotesEff`, `strongVote`** | Appears at exactly 5 of ~35 decision sites; the header's claim that it suppressed 30 exits is **false** | A voting system over exits that should not exist. |
| **The exit arbiter, winner floor, `T_MinWinnerExitPts`, `T_BanksOff`, `T_HtfNeverCloses`** | The real chokepoint; `IsHtfCloseTag` does substring matching so any future tag containing "H1" is silently vetoed (S3) | Machinery whose only job is to undo the damage of other machinery. |
| **`T_FixedLots` and the ~30 orphaned sizing inputs behind it** | `LotFor()` returns at 7432, never reaching the ceilings at 7739/7752 (S1) | Size is `f(risk %, stop distance, tick value)`. One input. |
| **Per-hour parameter learning (`T_HourLearning`, `SessionQuality`, `CoordBoost`, `T_WinLadder`, `LiveRisk`)** | Dead behind `T_FixedLots` anyway | 24 hour-buckets × parameters is the textbook overfit. The one session finding (E-019) is a single boolean gate, measured on one instrument, and ships **off**. |
| **Six entry paths** (CONFIRMED, EARLY-FLIP, MICRO-BREAKOUT, REVERSAL, PULLBACK, RECLAIM) | Three blocked by `T_PineParity`; `EARLY-FLIP` is an **intrabar** signal | One entry path, computed on closed bars only. |
| **`EARLY-FLIP` intrabar entry** | Fires when bid/ask crosses the Supertrend before the bar closes | Repainting by construction: it takes flips that un-form by bar close. |
| **The Supertrend signal itself** | `T_StMultiplier = 1.2`, re-seeded over 1000 bars every bar (S4), non-deterministic direction | Replaced entirely by sweep-continuation, which is the only entry in this repo that beat its own baseline on 5/5 markets. |
| **`DemaTopUp`** | Adds a lot with **SL = 0 and TP = 0**, no profit check — averaging down unprotected (dormant, `InpDemaTopUp=false`) | Deleted, not defaulted off. |
| **Basket / net-book P&L logic** | Sums `POSITION_PROFIT` across both directions; hedged books net to zero so the lock never arms, then closes everything at once (S3) | Positions are managed individually. Hedging is prohibited (§6). |
| **The panel / `ObjectCreate` drawing code (≈450 lines)** | Skimmed, not audited | Charts are for the Pine script. The EA writes a CSV. |
| **`InpMaxDailyLossPct = 40.0` and the halt that does not flatten** | A 40% daily stop is not a stop; `g_halt` only blocks entries and cancels pendings; **no max-drawdown guard exists anywhere in the file** | Replaced by `PropFirmEngine` (§3). |
| **`g_dayStart` re-seeded on every `OnInit`** | A restart mid-day resets the daily baseline | Anchors are persisted to `GlobalVariable` and reconstructed from deal history (§3.3). |
| **19 structurally orphaned inputs** | Declared, never referenced | Nothing to say. |

**Net:** 748 → 25, of which 16 are optimizable.

---

## 3. THE PROP-FIRM RISK ENGINE

This is the part that saves the account. Everything above it is an opinion
about price; this is arithmetic about survival.

**The universal mechanic, from `PROP_FIRMS.md` §4:** *every* firm measures the
daily limit against **equity**, not balance. Floating loss on an open position
counts immediately. **You can fail an account without closing a single trade
and without any stop-loss being hit.** An EA that holds through a spike is the
single most common cause of funded-account death.

### 3.1 Equity-based daily loss tracking, including floating P/L

```cpp
equity_now  = AccountInfoDouble(ACCOUNT_EQUITY);    // includes floating P/L
balance_now = AccountInfoDouble(ACCOUNT_BALANCE);
```
`ACCOUNT_EQUITY` is the *only* acceptable source. `PROP_FIRMS.md` §7 states it
plainly: *"the floating-loss monitor is the whole product. Balance-based checks
are useless — every worked example in §4 breaches on unrealised P/L. If the
engine only evaluates on trade close, it will watch accounts die."*

Polled in two places, because neither alone is sufficient:
- **`OnTick()`** — catches every price move while quotes flow.
- **`OnTimer()` at `EventSetMillisecondTimer(250)`** — catches the case where
  ticks stop arriving (thin book, weekend gap, feed stall) but equity is still
  moving on the broker's side, and guarantees `EQUITY_POLL_MS = 250` staleness
  regardless of tick rate.

### 3.2 The reset clock, and why "worst of all" is the safe default

Four different reset clocks appear across the firms researched:

| Firm | Daily reset | UTC equivalent |
|---|---|---|
| Maven | 00:00 UTC | **00:00** |
| FTMO | 00:00 CE(S)T | **23:00** (CET, winter) / **22:00** (CEST, summer) |
| FundedNext, Alpha Capital | 00:00 server = GMT+2 / GMT+3 | **22:00** / **21:00** |
| E8, FundingPips | 00:00 server, offset unconfirmed | assume within the same set |

`InpResetClock = CLOCK_WORST_OF_ALL` maintains **four independent anchors**
simultaneously, at 21:00, 22:00, 23:00 and 00:00 UTC, and uses the most
restrictive resulting floor:

```
for each anchor time i in {21:00, 22:00, 23:00, 00:00} UTC:
    anchor[i]     = max(balance, equity) sampled at the instant clock crosses i
    limit_cash[i] = InpDailyLossLimitPct/100 * min(initial_balance, anchor[i])
    floor[i]      = anchor[i] - limit_cash[i]

effective_floor  = MAX over i of floor[i]           // highest floor = most restrictive
effective_anchor = anchor of the argmax
daily_loss_cash  = effective_anchor - equity_now
headroom_pct     = (equity_now - effective_floor) / effective_anchor * 100
```

Three deliberate harshness choices, each taking the worse of two readings:
1. **`max(balance, equity)` as the anchor.** This automatically implements
   Alpha Capital's carry-over rule: if a position is held across the boundary
   with a floating loss, `equity < balance`, the anchor is `balance`, and the
   day starts with a reduced budget it never asked for. The rule falls out of
   the formula rather than needing its own branch.
2. **`min(initial_balance, anchor)` as the limit base.** Some firms compute
   the limit on the initial balance (FundedNext: "fixed $ = 5% of *initial*
   balance"), some on the day-start value. Whichever gives the smaller
   allowance wins.
3. **`MAX` over the four floors.** Higher floor = less room = safer.

**Why not just pick the right clock?** Because the offset moves. From
`PROP_FIRMS.md` §4.2: *"the server rolls GMT+3 ↔ GMT+2 seasonally. An engine
hard-coded to one offset will compute the wrong daily anchor twice a year, on
the exact days volatility is unusual."* And §7: *"the four different reset
clocks in this document are the most likely source of a silent bug that fails
an account at 23:30 UTC on a Sunday in October."*

Worked failure of the single-clock approach:
> **Sunday 25 October 2026, 21:00–22:00 UTC.** Europe leaves DST. A
> FundedNext server rolls GMT+3 → GMT+2, so the firm's day now resets at
> 22:00 UTC, not 21:00. A single-clock engine pinned to 21:00 UTC believes the
> budget reset at 21:00. If the account is −2.4% for the firm's day at that
> point, the engine sees −0.0% and permits new trades. One 0.7% loss inside
> that hour puts the firm's count at −3.1% and the account is dead — with the
> engine's own daily-loss reading at −0.7% and every internal check green.
>
> With four anchors, the 22:00 anchor has not rolled yet, its floor is the
> higher one, `effective_floor` still reflects the −2.4%, and the engine is
> already in `LOCK_DAILY_SOFT`. It sits out the hour. Cost: the engine is more
> restrictive than any single firm requires, for up to three hours a day.
> Benefit: it cannot be wrong about which day it is.

The four single-clock enum values exist for the case where a firm's rule is
later *page-verified* by a human (`PROP_FIRMS.md` §0 hard instruction) and the
engine can safely be loosened. They are not the default and must not be set
from a search-summary reading of a firm's FAQ.

### 3.3 Anchor persistence and restart reconstruction

v19.18's bug: `g_dayStart = ACCOUNT_BALANCE` re-seeded on every `OnInit`
(line 9199), so a mid-day restart reset the daily baseline and the guard
started from scratch after the loss it was supposed to be counting.

Here:
1. Every anchor roll writes `GlobalVariableSet("LS_<magic>_ANCHOR_<hh>",
   value)` and `..._ANCHOR_<hh>_T` (the timestamp) — MT5 global variables
   survive terminal restart and are flushed to disk on shutdown.
2. On `OnInit`, `Restore()` reads them. An anchor is accepted only if its
   timestamp is within the current anchor period.
3. **If an anchor is missing or stale**, reconstruct:
   ```
   balance_at_anchor = balance_now
                     - SUM(profit + swap + commission) over HistoryDeals
                       with DEAL_ENTRY_OUT and DEAL_TIME >= anchor_time
   anchor = MAX(balance_at_anchor, equity_now, balance_now)
   ```
   Balance at the anchor is exactly reconstructible from deal history. Equity
   at the anchor is not — so the reconstruction takes the maximum of three
   candidates, which can only be too restrictive, never too permissive.
4. **And then halves the remaining budget for that anchor period**
   (`limit_cash[i] *= 0.5`) and logs `ANCHOR_RECONSTRUCTED`. A reconstructed
   anchor is an estimate; the engine pays for the uncertainty out of its own
   allowance, not out of the account.

### 3.4 Static vs trailing max drawdown

**Assume trailing, always.** `PROP_FIRMS.md` §7: `max_drawdown_model:
TRAILING` — *"never assume static"*. §8 records that FTMO's 2-step
static-vs-ratcheting wording could not be separated from an official page and
instructs encoding the harsher reading.

```
hwm       = MAX(hwm, balance_now, equity_now)     // updated every tick, persisted
dd_floor  = hwm * (1 - InpMaxDrawdownPct/100)
dd_cash   = hwm - equity_now
```

Three harshness choices, matching §7:
- `trailing_basis: MAX(highest_closed_balance, highest_equity)` — harsher than
  either alone. An intraday equity spike that was never closed still raises
  the high-water mark.
- `trailing_updates: CONTINUOUS` — harsher than end-of-day-only, and safe
  under an EOD firm.
- `trailing_locks_at_initial_balance: false` — the engine does not rely on the
  lock existing, even at firms that have one.

The E8 One trap (§4.4) is the reason: *"a strategy that grinds up 3% then
gives back 4% survives a static 8% drawdown and dies instantly on a 4% dynamic
one."* If the real firm's model is static, this engine is merely
conservative. If it is dynamic and the engine assumed static, the account is
gone.

The high-water mark is persisted (`LS_<magic>_HWM`) and, on a missing value,
reconstructed as `MAX(balance_now, equity_now, highest balance implied by deal
history)` — again the maximum, again only ever too restrictive.

### 3.5 The exact hard locks

`CanOpenNewPosition()` returns false if **any** lock is active.
`MustFlatten()` returns true only for the four flatten locks.

| Lock | Trigger (exact) | New entries | Open positions | Clears when |
|---|---|---|---|---|
| `LOCK_DEMO` | `InpDemoOnly && ACCOUNT_TRADE_MODE != ACCOUNT_TRADE_MODE_DEMO` | `OnInit` returns `INIT_FAILED` | never opened | input changed by Veer |
| `LOCK_SPECS` | `RiskEngine::SpecsValid()` false (tick_size ≤ 0, tick_value ≤ 0, volume_step ≤ 0) | BLOCK | keep, stops already attached | specs read successfully |
| `LOCK_CONNECT` | `!TerminalInfoInteger(TERMINAL_CONNECTED)` or `!AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)` or `!MQLInfoInteger(MQL_TRADE_ALLOWED)` | BLOCK | keep (cannot act anyway) | reconnect |
| `LOCK_DAILY_SOFT` | `daily_loss_cash >= 0.333 * limit_cash` → **1.0%** of anchor at the 3.0% default | BLOCK | keep, managed normally | next anchor roll |
| `LOCK_DAILY_HARD` | `daily_loss_cash >= 0.50 * limit_cash` → **1.5%** at default | BLOCK | **FLATTEN ALL** | next anchor roll |
| `LOCK_DD_SOFT` | `equity_now <= hwm * (1 - 0.50*InpMaxDrawdownPct/100)` → **−3.0%** at default | BLOCK | keep | `equity_now >= hwm*(1-0.025)` — 0.5% hysteresis, so it cannot chatter |
| `LOCK_DD_HARD` | `equity_now <= hwm * (1 - 0.667*InpMaxDrawdownPct/100)` → **−4.0%** at default | BLOCK | **FLATTEN ALL** | **NEVER automatically.** Writes `LS_<magic>_DD_HARD=1`; `OnInit` re-reads it and stays locked. Only a human deleting that global variable restarts trading. |
| `LOCK_STREAK` | `consecutive_losses >= InpMaxConsecutiveLosses` (default 4) | BLOCK | keep | next anchor roll |
| `LOCK_SPREAD` | `spread_price > InpMaxSpreadPctOfStop/100 * plan.risk_price` | BLOCK **this signal only** | keep | evaluated per signal |
| `LOCK_MARGIN` | `OrderCalcMargin` for the next order leaves free margin below 30% of equity | BLOCK | keep | next tick |
| `LOCK_FRIDAY` | Friday, `TimeGMT() >= 20:00` | BLOCK | **FLATTEN ALL** | Sunday session open |
| `LOCK_NEWS` | `InpNewsBlackoutMin > 0` and inside the window | BLOCK | **FLATTEN ALL** (§7: `flatten_before_news: true`) | window ends |

**Why soft and hard are separate.** A soft lock stops the bleeding from new
decisions while letting existing positions reach their broker-side stops —
which are already inside the budget. A hard flatten is an admission that the
model of the account is no longer trustworthy, and it is set at **half** the
firm's actual limit precisely so that the flatten itself, including slippage
on the exit fills, still lands inside the firm's number. Flattening *at* the
limit is flattening *past* it.

**Flatten is idempotent and retried.** `FlattenAll()` loops
`PositionsTotal()` filtered by magic+symbol, calls `ExecutionEngine::
ClosePosition` on each, and re-runs on the next tick until the count is zero.
A rejected close is retried. v19.18's `CloseTagged` logged *"REJECTED,
retrying"* and had no retry loop (S2) — a rejected close was silently dropped.

### 3.6 Consecutive-loss counting

Counted from `HistoryDealGetInteger(DEAL_ENTRY) == DEAL_ENTRY_OUT` with our
magic, ordered by `DEAL_TIME`, using `DEAL_PROFIT + DEAL_SWAP + DEAL_COMMISSION
< 0`. Persisted. Reset to zero on any winning close and at each anchor roll.

Note this is a *circuit breaker*, not a strategy input: `06_exit_experiment.md`
establishes that a low win rate is correct for this style (30% wins at 3R
beats 53% at 1R), so a 4-loss streak is completely normal and the lock exists
to catch a *regime* failure or a broken data feed, not a run of bad luck. It
clears at the next anchor roll, not on a win.

### 3.7 News — stated honestly

`InpNewsBlackoutMin` defaults to **0 (off)**. MT5's built-in economic calendar
(`CalendarValueHistory`) is not available in the strategy tester and is not
present on every broker's terminal build. Shipping a news filter that silently
does nothing is worse than shipping none, because it produces the *belief* in
protection.

Phase 2 decision required, and it is Veer's, not mine:
- **(a)** Use `CalendarValueHistory` with `CALENDAR_IMPORTANCE_HIGH` filtered
  to USD/XAU, accept that it is live-only, and hard-fail `OnInit` if the
  calendar returns zero events in the next 30 days.
- **(b)** Read a CSV of event timestamps from `MQL5/Files/`, maintained
  manually. Testable, auditable, and it works in the tester.
- **(c)** Leave it off and rely on the equity guard.

`PROP_FIRMS.md` §7 asks for `news_blackout_before_min: 300` (FundingPips flags
trades *opened* within 5 hours of restricted news if they are closed in the
window) and `flatten_before_news: true`. A 5-hour pre-news blackout on USD
events removes a large fraction of the trading week, which is a strategy
decision with a measurable cost that has not been measured. **Do not encode it
until it has been backtested.**

### 3.8 Worked numeric example — $100k breaching on floating loss

Account: **$100,000** initial. Firm: FundingPips 2 Step Pro — **3% daily loss,
measured on the higher of day-start balance or equity, floating included.**
This is the tightest daily limit in `PROP_FIRMS.md` §3.
Gold convention: 1.00 lot = 100 oz, so **$1.00/oz move = $100 per lot**.

**Day 12, 00:00 server. Balance $101,200, flat, so equity $101,200.**

```
anchor        = max(101,200, 101,200)          = $101,200
limit_cash    = 3.0% * min(100,000, 101,200)   = $3,000
firm floor    = 101,200 - 3,000                = $98,200
```

#### (a) The naive EA — the one that dies

Opens **2.00 lots** long gold at 3,900.00, stop 3,880.00.
Intended risk: `20.00 × 100 × 2.00 = $4,000` — **already $1,000 larger than
the entire daily limit**, before anything goes wrong.

CPI prints. Gold trades to 3,885.00 without touching the stop.

```
floating P/L  = (3,885.00 - 3,900.00) * 100 * 2.00   = -$3,000
equity        = 101,200 - 3,000                       = $98,200
$98,200 <= $98,200  ->  ACCOUNT FAILED
```

No stop was hit. No trade was closed. The position may well recover to
profit five minutes later — it does not matter, the breach is recorded on the
equity print. This is `PROP_FIRMS.md` §4.3 exactly: *"A $15 gold move on 2 lots
kills a $100k account. That is roughly a 0.4% move — a single CPI candle."*

#### (b) The same account, this engine

Symbol specs read at runtime: `tick_value = 1.00`, `tick_size = 0.01`, so
`money_per_lot_per_price = 100.00`. `volume_step = 0.01`, `volume_min = 0.01`.
GOLD H1 `ATR(14) = 14.00`.

Signal: a sweep-continuation long. Break bar closes at 3,901.00, low 3,896.00.

```
stop            = 3,896.00 - 0.30 * 14.00              = 3,891.80
risk_price      = |3,901.00 - 3,891.80|                = 9.20
stop / ATR      = 9.20 / 14.00 = 0.657                 <= 2.50   OK
risk_cash       = 0.35% * 101,200                      = $354.20
raw_lots        = 354.20 / (9.20 * 100.00)             = 0.38500
lots            = floor(0.38500/0.01)*0.01             = 0.38
actual risk     = 9.20 * 100.00 * 0.38                 = $349.60   (0.345% of equity)
spread check    = 0.35 / 9.20 = 3.80%                  <= 5.00%   OK
```

Engine locks at the 3.0% setting:
```
limit_cash        = $3,000
LOCK_DAILY_SOFT   at 0.333 * 3,000 = $999    (0.99% of anchor)   -> block new entries
LOCK_DAILY_HARD   at 0.500 * 3,000 = $1,500  (1.48% of anchor)   -> flatten all
firm floor        at                 $3,000                       -> account dead
```

Same CPI candle, gold 3,901.00 → 3,885.00, a **−16.00** move:

| | naive EA | this engine |
|---|---|---|
| position | 2.00 lots | 0.38 lots (+ at most one more, capped at 2 concurrent) |
| stop distance | 20.00 | 9.20 |
| stop reached at | 3,880.00 — not reached | **3,891.80 — reached** |
| realised loss | $0 (still open) | **−$349.60** |
| floating at 3,885 | **−$3,000** | $0, position already closed |
| equity | **$98,200 — BREACHED** | $100,850.40 |
| daily loss vs $3,000 limit | 100.0% | **11.7%** |

For this engine's `LOCK_DAILY_HARD` to fire at $1,500 on a single 0.38-lot
position, gold would have to travel `1,500 / (100 × 0.38) = $39.47/oz` against
it — **4.3× further than the stop**. It cannot happen through normal price
movement. Both positions at maximum size stopping out simultaneously costs
`2 × $349.60 = $699.20 = 0.69%`, which does not even reach the **soft** lock at
$999.

**That relationship is the design target, stated as a rule:**
> `InpRiskPctPerTrade × InpMaxConcurrentPositions` (0.70%) must sit strictly
> below `DAILY_SOFT_FRACTION × InpDailyLossLimitPct` (1.00%), which must sit
> strictly below `DAILY_HARD_FRACTION × InpDailyLossLimitPct` (1.50%), which
> must sit strictly below the firm's actual limit (3.00%).
> `OnInit` asserts this chain and returns `INIT_FAILED` if it is violated.

The prop locks exist for what the sizing model cannot see: a weekend gap
through the stop, a broker rejecting a close, a feed stall, a stop stripped by
the server, or a fat-finger manual position on the same magic. They are not
the primary defence. **The primary defence is that the position is small
enough that the limit is unreachable.**

---

## 4. EXECUTION CORRECTNESS CHECKLIST

The things that silently lose money. Each item states the rule, the v19.18
precedent where one exists, and how the rebuild enforces it.

### 4.1 The stop is attached at `OrderSend` and verified after the fill

```cpp
m_trade.SetTypeFillingBySymbol(m_symbol);
m_trade.SetDeviationInPoints(DEVIATION_POINTS);
bool sent = (dir > 0)
   ? m_trade.Buy (lots, m_symbol, 0.0, sl, tp, comment_token)
   : m_trade.Sell(lots, m_symbol, 0.0, sl, tp, comment_token);
```
`sl` and `tp` are non-zero at send. There is no path that opens a position and
then attaches a stop on a later tick.

**And then it is verified**, because "sent with a stop" and "has a stop" are
different claims:
```
after a successful fill:
   read POSITION_SL for the new ticket
   if (POSITION_SL == 0.0):
        attempt ModifyStop up to 3 times, 200 ms apart, via the retry state machine
        if still 0.0 after 3 attempts:  CLOSE THE POSITION IMMEDIATELY, log SL_MISSING
```
A position without a broker-side stop is not allowed to exist. v19.18's S1 bug
was the mirror image of this: `ManagePosition` began with
`if(atr <= 0 || sl == 0) return;` — the *first* guard — so a position whose SL
was 0 received **zero** management and was completely unbounded.

`VerifyStopsOnTick()` re-checks every open position every tick, because a
broker or a bridge can strip a stop at any time, not only at fill.

### 4.2 Symbol specs read at runtime, nothing hardcoded

Read in `RiskEngine::RefreshSpecs()` on `OnInit`, on every new bar, and after
any `TRADE_RETCODE_INVALID_VOLUME`:

| Field | Used for |
|---|---|
| `SYMBOL_POINT` | converting `SYMBOL_TRADE_STOPS_LEVEL` (points) to price. **The only use.** |
| `SYMBOL_DIGITS` | `NormalizeDouble` on every price sent |
| `SYMBOL_TRADE_TICK_VALUE` | `money_per_lot_per_price = tick_value / tick_size` |
| `SYMBOL_TRADE_TICK_SIZE` | same; **must guard `> 0` before dividing** |
| `SYMBOL_TRADE_CONTRACT_SIZE` | sanity cross-check of the tick-value maths, logged at `OnInit` |
| `SYMBOL_VOLUME_MIN` | below this → **skip the trade**, do not trade the minimum |
| `SYMBOL_VOLUME_MAX` | clamp |
| `SYMBOL_VOLUME_STEP` | `floor` to step, never `round`, never `ceil` |
| `SYMBOL_TRADE_STOPS_LEVEL` | minimum stop distance; a plan violating it is **rejected**, not silently widened (widening changes R and therefore lot size) |
| `SYMBOL_TRADE_FREEZE_LEVEL` | refuse `ModifyStop` inside the freeze band |
| `SYMBOL_FILLING_MODE` | negotiate `FOK` / `IOC` / `RETURN` |
| `SYMBOL_TRADE_MODE` | must be `SYMBOL_TRADE_MODE_FULL` |
| `SYMBOL_SPREAD_FLOAT` | logged; changes the interpretation of the spread filter |

`OnInit` prints the whole spec block at `LOG_ERROR` level so it appears in
every journal. `05_ea_deep_audit.md` §"what I could not verify" flags that a
broker screenshot of the gold contract spec is still a missing input — this
print is the substitute, and it must be read on the first demo run before any
number in §3.8 is trusted.

**Nowhere in the codebase does the literal `100`, `0.01`, or `10` appear as a
gold contract constant.** The §3.8 worked example uses `tick_value = 1.00` and
`tick_size = 0.01` as an *illustration*; the code derives them.

### 4.3 New-bar detection, and what is allowed per tick

```cpp
datetime t[1];
if(CopyTime(m_symbol, m_tf, 0, 1, t) != 1) return;   // feed problem: do nothing
if(t[0] == m_last_bar_time) { /* mid-bar */ } else { m_last_bar_time = t[0]; /* new bar */ }
```

| Work | New bar | Every tick |
|---|---|---|
| `RegimeEngine::Update` (shift 1 reads) | yes | never |
| `LiquidityEngine::OnNewBar` | yes | never |
| `SweepEngine::DetectOnClosedBar` | yes | never |
| `EntryEngine` / `TargetEngine` | yes | never |
| `RiskEngine::LotsForRisk` + `OpenPosition` | yes | never |
| `TradeManagement::OnNewBar` (time exit, trail) | yes | never |
| `PropFirmEngine::OnTick` (equity, locks) | yes | **yes** |
| `TradeManagement::VerifyStopsOnTick` | yes | **yes** |
| `ExecutionEngine::ProcessPending` (retries) | yes | **yes** |
| `StatisticsEngine::TrackOpenPositions` | yes | **yes** |
| `FlattenAll` when a hard lock is active | yes | **yes** |

Four things run per tick, all of them safety or measurement, none of them
signal. v19.18's `OnTick` comment said *"Entries only on a new bar"* at line
20644 and then called `Engine_Trend()` on every tick at 20692. The comment was
false. Here the split is enforced by the call graph: the signal modules are
only reachable from the new-bar branch.

**No repainting.** Every indicator and price read in the signal path uses
`shift >= 1`. There is no `shift 0` read anywhere except `SymbolInfoTick` for
spread measurement and margin checks, neither of which feeds a signal.

### 4.4 State surviving terminal restart

Positions are identified by **`POSITION_MAGIC == InpMagicNumber` AND
`POSITION_SYMBOL == _Symbol`**. Both. A position failing either test is
invisible to this EA — never modified, never closed, never counted.

`TradeManagement::Adopt()` runs in `OnInit` and rebuilds `PositionState` for
every owned position. The one value that cannot be read directly from the
position is `r_distance` (needed for R-multiple logging and the trail arm), so
it has **three tiers of recovery**:

1. **`GlobalVariable`** — `LS_<magic>_R_<ticket>` written at fill, deleted on
   close. Survives restart, flushed to disk by the terminal.
2. **`POSITION_COMMENT`** — the token written at `OrderSend`, format
   `LS<dir><r_x100>` (e.g. `LS+920` for a long with `r_distance = 9.20`),
   kept under 31 characters. Brokers can and do rewrite comments, so this is
   the fallback, not the primary.
3. **`|POSITION_PRICE_OPEN - POSITION_SL|`** — exact whenever the stop has not
   moved, which with `InpTrailArmR = 0.0` (the default) is **always**. If the
   trail is ever enabled this tier becomes an underestimate of R and the
   engine logs `R_RECOVERED_APPROX`.

Also persisted: the four daily anchors and their timestamps, the high-water
mark, the consecutive-loss count, the `DD_HARD` latch, and the
`StatisticsEngine` tag ledger. Everything is prefixed `LS_<magic>_` so two
instances on different magics on the same terminal cannot collide.

v19.18 persisted only the hour-of-day learning. On restart `QSP_TrackLive`
re-seeded each position's peak to the *current* P/L, so a trade that had
peaked at +5R and was sitting at +1R was recorded as having peaked at +1R.

`OnDeinit` writes a final `Persist()` and flushes the CSV, on every deinit
reason including `REASON_RECOMPILE`.

### 4.5 `OrderSend` failure handling

Retcodes are classified into three buckets. This is a direct port of the one
piece of v19.18 that `05_ea_deep_audit.md` called *"better than most
production EAs — keep verbatim"* (lines 11404–11455).

**Bucket A — retry, price moved but nothing executed.**
`TRADE_RETCODE_REQUOTE (10004)`, `PRICE_CHANGED (10020)`,
`PRICE_OFF (10021)`, `TOO_MANY_REQUESTS (10024)`.
Refresh the tick, re-verify the spread filter, retry. Maximum
`ORDER_RETRY_N = 3` attempts, `ORDER_RETRY_DELAY_MS = 200` apart, scheduled
against `GetTickCount()` and executed on later ticks. **No `Sleep()`.**

**Bucket B — abort, do not retry.** The request is structurally wrong or the
account cannot take it.
`INVALID_VOLUME (10014)`, `INVALID_PRICE (10015)`, `INVALID_STOPS (10016)`,
`TRADE_DISABLED (10017)`, `MARKET_CLOSED (10018)`, `NO_MONEY (10019)`,
`LIMIT_VOLUME (10034)`, `LIMIT_POSITIONS (10040)`, `INVALID_ORDER (10013)`.
Log at `LOG_ERROR`, `StatisticsEngine::RecordReject(RJ_SEND_FAILED)`, discard
the signal. On `INVALID_VOLUME` also force `RiskEngine::RefreshSpecs()`; on
`INVALID_STOPS` also log the computed stop against `SYMBOL_TRADE_STOPS_LEVEL`,
because that pair of numbers is the whole diagnosis.

**Bucket C — ambiguous, it may have executed.**
`TIMEOUT (10012)`, `CONNECTION (10031)`, `DONE_PARTIAL (10009 with partial
volume)`, and any transport-level failure of `OrderSend` itself.
**Never blind-retry.** Sequence:
1. Wait 500 ms (scheduled, not slept).
2. Re-scan `PositionsTotal()` and `OrdersTotal()` for our magic + the unique
   `comment_token` of this attempt.
3. If found → adopt it, verify its stop (§4.1), stop retrying.
4. If not found → treat as Bucket A and retry, up to the same 3-attempt cap.
5. On partial fill → accept the partial, verify the stop, do **not** top up.

**The abort-on-drift rule, in every bucket.** Before any retry:
```
if( |current_price - plan.entry| > RETRY_ABORT_DRIFT_FRAC * plan.risk_price )
      abort, log RETRY_ABORT_DRIFT
```
With `RETRY_ABORT_DRIFT_FRAC = 0.25`, a fill more than a quarter of the stop
distance away from the planned entry is refused. Chasing a moved market turns
a 1.2:1 setup into a 0.9:1 setup silently — the R:R filter was applied to the
plan, not to the fill.

`ClosePosition` uses the same classifier, and — unlike v19.18 — actually
retries. A close that fails is re-attempted on every subsequent tick until it
succeeds or the position is gone, with no attempt cap when the caller is a
hard lock. Failing to close under `LOCK_DAILY_HARD` is the one situation where
giving up is not an option.

### 4.6 3/5-digit broker handling

**The word "pip" does not appear in the codebase.** All internal arithmetic is
in **price**, which is dimensionless with respect to digit count. A 3-digit
and a 5-digit quote of the same instrument produce the same price arithmetic;
only the point size differs.

`SYMBOL_POINT` is used in exactly two places:
1. `MinStopDistancePrice() = SYMBOL_TRADE_STOPS_LEVEL * SYMBOL_POINT` —
   converting the broker's points-denominated field into price.
2. `SetDeviationInPoints(DEVIATION_POINTS)` — a `CTrade` API that demands
   points.

Everywhere else — ATR multiples, stop distances, targets, spread as a fraction
of stop, R multiples — is a ratio of prices and is unit-free by construction.
`money_per_lot_per_price = tick_value / tick_size` carries the conversion into
account currency and is read from the broker.

This is the fix for v19.18's S2 bug. That file defined its own "point" as one
unit of price, explicitly not `_Point`, and then hardcoded thresholds in it:
`T_SlFloorPtsAbs = 1.20`. On EURUSD that is `max(2.00 × 0.0006, 1.20) = 1.20`
— a **12,000-pip** stop floor — while `T_MaxLossPts = 3.0` and
`T_TargetPts = 8.0` could never fire. The header claimed *"MULTI-SYMBOL, FOR
FREE"*; the EA was gold-only whatever the switches said.

**Verification for Phase 2:** run the identical build on GOLD, EURUSD and
US500 in the tester and confirm the *distribution of stop distances in ATR
units* is the same shape on all three. If it is not, a hardcoded price
constant has survived.

### 4.7 Weekend, rollover and swap

- `LOCK_FRIDAY` flattens at 20:00 UTC Friday. FundingPips prohibits weekend
  holds and auto-closes; several others restrict them on funded accounts.
  Flat by default everywhere.
- No new entries within `MAX_HOLD_BARS` bars of the Friday flatten time — the
  time exit would fire into a closed market otherwise.
- `rollover_blackout_utc: ["21:55", "22:10"]` from `PROP_FIRMS.md` §7 —
  The5ers bans rollover scalping and spreads widen hard there. Enforced as a
  no-new-entry window; the spread filter would usually catch it anyway, and
  both is better.
- Swap on held positions is *reported* by `StatisticsEngine` per closed trade
  (`DEAL_SWAP`) but is not modelled at entry. On XAUUSD with a ≤40-bar hold on
  H1 the exposure is at most two rollovers. **Unverified without a real
  account's swap table.**
- Monday gap: `Adopt()` re-verifies every stop before the first new bar is
  processed. A position that gapped through its stop is already closed by the
  broker; a position whose stop was stripped over the weekend is closed
  immediately by §4.1.

### 4.8 What I could not verify without MT5

Stated plainly, because the checklist above is a *design*, not a test result:

1. **It has not been compiled.** No MetaEditor here. Syntax, declaration
   order, and `#include` cycles are unverified.
2. **`ORDER_FILLING` negotiation is untested.** Whether the broker actually
   grants `FOK` on XAUUSD, and what it does with `IOC` on a partial, is a
   live-account fact.
3. **Real slippage and requote rates are unknown.** `DEVIATION_POINTS = 20`
   and `RETRY_ABORT_DRIFT_FRAC = 0.25` are guesses until measured.
4. **`SYMBOL_TRADE_TICK_VALUE` on the target broker's gold symbol is
   unconfirmed.** §3.8 assumes 1.00 at tick size 0.01. Every cash figure in
   that example scales linearly with it.
5. **Whether `GlobalVariable` survives every crash mode** (as opposed to a
   clean shutdown) is untested. The three-tier R recovery exists because of
   this.
6. **CPU cost is unmeasured.** It should be far below v19.18 (three Supertrend
   chains × 1000 iterations rebuilt per bar, plus six `PositionsTotal()` loops
   per tick), but "should be" is not a measurement.
7. **MT5's economic calendar availability** on the target terminal and in the
   tester — see §3.7.

---

## 5. PINE ↔ MQL5 PARITY PLAN

Two implementations of one idea will diverge. The only question is whether the
divergence is found in a test harness or in a live account.

### 5.0 Blocker: the Pine does not currently compile

`JARVIS/pine/LiquiditySniper_v1.pine` references **`needRetest` and
`retestBars` at lines 377, 385, 392, 401, 409, 410 and 518, and neither is
declared anywhere in the file.** There is no `input.bool(... "needRetest")`
and no `input.int(... "retestBars")`. As written the script cannot compile.

Resolve **before** any parity work, one of two ways:
- **(a)** Add the two inputs (`needRetest = input.bool(false, ...)`,
  `retestBars = input.int(5, ...)`) and then decide whether the MQL5 mirrors
  the retest path. Recommendation: add them defaulted **off**, and do **not**
  build the retest path in MQL5 — it is a separate, untested hypothesis
  (§6).
- **(b)** Delete the armed/retest block entirely. Simpler, and it matches what
  the EA will do.

Either way, **the same choice is made on both sides in the same commit.**

### 5.1 The harness

```
JARVIS/specification/parity/
    fixture_A_pivots.csv        synthetic, 320 bars, hand-computable
    fixture_B_gold_h1.csv       real GOLD H1, 3,000 bars from data/
    expected_A.csv              hand-derived expected outputs for fixture A
    compare.py                  the referee
    README_PARITY.md            how to run both sides
```

**Common state vector.** Both implementations emit one CSV row per closed bar
with exactly these columns, in this order:

```
bar_index, time_utc, open, high, low, close,
atr, atr_median, atr_ratio, adx, in_session, expansion_ok,
n_live_hi, n_live_lo,
new_level_hi_px, new_level_hi_bar, new_level_hi_hits,
new_level_lo_px, new_level_lo_bar, new_level_lo_hits,
swept_hi_px, swept_hi_hits, swept_lo_px, swept_lo_hits,
displacement_ok, can_fire, dir, entry, sl, tp, risk, rr, rejected_by
```

- **Pine side:** the indicator gains a `PARITY DUMP` input (default off). When
  on, it calls `log.info(str.format(...))` once per confirmed bar with the row.
  TradingView's Pine Logs pane exports to text. Alternative for long runs:
  `plot()` each numeric column with `display=display.data_window` and use
  "Export chart data".
- **MQL5 side:** `Logger::BarState()` writes the identical row to
  `MQL5/Files/parity_<symbol>_<tf>.csv` when `InpLogLevel == LOG_VERBOSE`.
- **Fixture import:** fixture A is imported into MT5 as a custom symbol via
  `CustomSymbolCreate` + `CustomRatesUpdate` from the CSV, and into TradingView
  by pasting the same OHLC as a seed series. Both must read *identical* bars —
  this is itself the first thing `compare.py` checks (columns 3–6).

**Tolerances.** `compare.py` fails on:
- any mismatch in `can_fire`, `dir`, `displacement_ok`, `expansion_ok`,
  `in_session`, `n_live_hi`, `n_live_lo`, `*_bar`, `*_hits`, `rejected_by`
  — these are exact;
- any price column differing by more than `1e-8` absolute for fixture A
  (synthetic, exact arithmetic);
- any of `atr`, `atr_median`, `adx` differing by more than `1e-6` **relative**
  for fixture B, and only after bar 200 (warm-up, §5.4).

The first 200 bars of every fixture are warm-up and are excluded from
comparison. Anything before that is smoothing-seed noise, not a logic
difference.

### 5.2 Test scenarios — fixture A, hand-computable

Fixture A runs with `pivLen = 3` (not the default 8) so the sequences are
short enough to verify by hand, `eqTol = 0.20`, `minLvlAge = 5`,
`dispAtr = 1.0`, `maxLevels = 3`, expansion filters **off**, `slBuf = 0.30`,
`tpMode = Next liquidity`, `minR = 1.2`, `maxRiskAtr = 2.5`,
`useDaily = useSessH = useRound = false`. Every scenario is a segment of one
320-bar file so they also test interaction.

| # | Scenario | Construction | Expected — both sides identical |
|---|---|---|---|
| **P-01** | **A pivot is known `len` bars late, and one bar later again** | Bar 8 high = 100.00, bars 5–7 and 9–11 highs all ≤ 99.50 | `n_live_hi` goes 0→1 at **bar_index 12**, not 11. `new_level_hi_px = 100.00`, `new_level_hi_bar = 8`. If MQL5 registers at bar 11 it has one bar of look-ahead. See §5.3. |
| **P-02** | **Equal-high merge strengthens, does not duplicate** | Bar 8 high 100.00; bar 20 high 100.10; ATR ≈ 1.00 so `eqTol*atr = 0.20` and `|100.10−100.00| = 0.10 ≤ 0.20` | After bar 24: `n_live_hi = 1`, stored `px = 100.10` (the max), `hits = 2`, and `new_level_hi_bar` **stays 8**. Not two levels, not `bar = 20`. |
| **P-03** | **Merge tolerance is exclusive at the boundary** | Same as P-02 but bar 20 high = 100.21, `eqTol*atr = 0.20` | Two separate levels. `n_live_hi = 2`. Tests `<=` vs `<` on the same line in both languages. |
| **P-04** | **FIFO eviction by insertion order, not by price age** | `maxLevels = 3`. Add levels L1(bar 8), L2(bar 20), L3(bar 32), then merge into L1 at bar 40 (making it "newest by touch"), then add L4 at bar 52 | **L1 is evicted**, not L2. Pine's `array.shift` removes index 0. A "least-recently-touched" implementation in MQL5 evicts L2 and diverges. |
| **P-05** | **A wick through is not a break** | Level at 100.00. Bar 60: high 100.40, **close 99.80** | `swept_hi_px` is empty, level stays live, `n_live_hi` unchanged. With `needClose` on, `close > p` is the test, not `high > p`. |
| **P-06** | **A close through is a break, and it dies the same bar** | Bar 61: open 99.80, close 100.60, ATR 1.00 → body 0.80 | `swept_hi_px = 100.00`, `swept_hi_hits` = that level's hit count, and `n_live_hi` **drops by one on this same bar**. |
| **P-07** | **Displacement gate uses BODY, not RANGE** | Bar 70: low 98.00, high 101.20 (range 3.20), open 100.55, close 100.60 (body 0.05), ATR 1.00, `dispAtr = 1.0` | `displacement_ok = false`, `can_fire = false`, `rejected_by = RJ_DISPLACEMENT` — even though the bar broke the level and had a huge range. |
| **P-08** | **`minLvlAge` counts from the pivot's own bar** | Level formed at bar 8 (known at bar 12), `minLvlAge = 5`. Break attempt at bar 12 (`age = 4`) then at bar 13 (`age = 5`) | Bar 12: no sweep, `rejected_by = RJ_LEVEL_AGE`. Bar 13: sweep fires. Note it is sweepable **one bar after it becomes visible**, which is a property of `pivLen=3, minLvlAge=5` and is worth seeing explicitly. |
| **P-09** | **Multiple levels broken on one bar: highest wins, ALL die** | Levels at 100.00, 100.30, 100.60 all live and old enough. Bar 90 closes at 101.00 | `swept_hi_px = 100.60` (the highest, per `p > sweptHi`), and `n_live_hi` drops by **3**, not 1. If MQL5 only kills the extreme one, P-10 then fails. |
| **P-10** | **Target reads the registry AFTER the sweep marked levels dead** | Continuing P-09: a live level exists at 100.45 (below the 100.60 that just died) and another at 102.00 | `tp = 102.00`. If `nextLiq` runs before the sweep loop, the answer is 100.45 — a target *behind* the entry. This is the ordering contract in §1.5. |
| **P-11** | **No live level beyond entry falls back to fixed R** | All highs above `close` are dead. `tpR = 2.0`, risk = 1.00, entry = 101.00 | `tp = 103.00`, `rr = 2.0`. Pine line 415 does this via `na(lvlTp)`; MQL5 must not emit "no trade". |
| **P-12** | **R:R rejection** | `nextLiq` returns 101.90, entry 101.00, sl 100.10 → risk 0.90, reward 0.90, `rr = 1.00 < minR 1.20` | `can_fire = true` but no trade recorded; `rejected_by = RJ_RR_TOO_LOW`. Both sides must reject on the *same* bar. |
| **P-13** | **Stop-too-wide rejection** | Break bar low 96.00, close 101.00, ATR 1.00, `slBuf 0.30` → sl 95.70, risk 5.30, `maxRiskAtr*atr = 2.50` | `rejected_by = RJ_STOP_TOO_WIDE`. No trade. |
| **P-14** | **The stop formula, exactly** | Long. Break bar low 99.40, close 101.00, ATR 1.00, `slBuf 0.30`, swept level 100.00 | `sl = 99.40 − 0.30 = 99.10`. **The swept level does not appear in the answer** — see §5.6. Any MQL5 that produces `99.70` (from `sweptHi − slBuf*atr`) is "more sensible" and is a parity failure. |
| **P-15** | **Both sides swept on one bar** | Outside bar: closes above a live high AND below a live low | Pine: `goLong` and `goShort` are both true; `dir = goLong ? 1 : -1` → **long wins by the ternary**. MQL5 rejects the bar as `RJ_NO_SWEEP` ("both sides"). **This is a deliberate, documented divergence** — Pine's behaviour here is an artefact of operator order, not a decision. `compare.py` whitelists rows where `swept_hi_px` and `swept_lo_px` are both non-empty, and counts them: if fixture B produces more than 2% such bars, the divergence matters and Pine must be changed to match. |
| **P-16** | **Session-hour wrap** | `useSess = true`, `sessFrom = 22`, `sessTo = 4` | `in_session` true for hours 22, 23, 0, 1, 2, 3; false for 4. Tests the `from > to` branch on both sides. |
| **P-17** | **Expansion gate boundary** | `atr/atrMed` exactly 1.15 with `maxSqueeze = 1.15`; `adx` exactly 25.0 with `maxAdx = 25` | Both **pass** (`<=`, not `<`). A `<` in one implementation is a silent, rare, and extremely annoying divergence. |
| **P-18** | **Extra sources register at the CURRENT bar, not the extreme's bar** | `useDaily = true`. Previous day's high formed 30 bars ago; the level registers at the first bar of the new day, bar 200 | `new_level_hi_bar = 200`, not 170. So `minLvlAge` for prev-day levels counts from registration. Deliberate parity with Pine lines 243/251/259. |

### 5.3 The pivot-offset trap, in full

This is the most likely single point of divergence, so it gets its own
derivation.

**Pine.** At bar index `B`, `ta.pivothigh(high, len, len)` returns the pivot at
bar `B − len` once confirmed, i.e. it is first non-`na` at `B = pivot_bar +
len`. The script then reads `[1]`, taking the value the function had at
`B − 1`. So the level becomes visible at:
```
B_visible = pivot_bar + len + 1
pivotBar  = bar_index - 1 - pivLen        (line 145, and it is consistent)
```
With `len = 3` and a pivot at bar 8: first non-`na` at bar 11, `[1]` makes it
visible at **bar 12**, and `12 − 1 − 3 = 8`. Correct.

**MQL5, the obvious (wrong) implementation.** On a new bar, `shift 1` is the
just-closed bar `B`. To confirm a pivot you need `len` bars on each side, so
the candidate is at `shift len + 1`, confirmed the moment `shift 1` exists:
```
candidate = shift (len + 1) = bar B - len   ->  confirmed at B = 11
```
That is **one bar earlier than Pine** — a one-bar look-ahead relative to the
reference implementation, and on a fast market one bar is the whole edge.

**MQL5, the correct implementation.**
```
PIVOT_CANDIDATE_SHIFT = pivot_len + 2      // from the just-closed bar
```
Candidate at `shift 5` when `len = 3`, i.e. bar `B − 4 = 8` when `B = 12`. ✓

`compare.py` treats a systematic one-bar offset in the `n_live_hi` /
`n_live_lo` transition columns as a **hard failure with a named diagnostic**
(`PIVOT_OFFSET_SUSPECT`), because it will otherwise look like a small
timing wobble rather than the specific bug it is.

### 5.4 Indicator parity — the three real risks

| Indicator | Pine | MQL5 | Risk | Resolution |
|---|---|---|---|---|
| **ATR** | `ta.atr(14)` = `ta.rma(ta.tr(true), 14)`, Wilder | `iATR(sym, tf, 14)` | **Low.** Both Wilder. Seeding differs for the first ~14 bars — Pine seeds from the first TR, MT5 uses an SMA seed. | 200-bar warm-up excluded; `1e-6` relative tolerance thereafter. |
| **ATR median** | `ta.median(atr, 50)` | **no built-in** | **Medium.** 50 is even, so Pine's `array.median` returns the **average of the two middle values** after sorting. An MQL5 implementation returning "the 25th element" is off by half a gap and will drift the gate boundary. | Hand-implement: copy 50 closed-bar ATR values, `ArraySort`, return `(v[24] + v[25]) / 2.0`. P-17 is the boundary test. |
| **ADX** | `ta.dmi(14, 14)` — `ta.rma` on TR, +DM and −DM, then `ta.rma(dx, 14)` | `iADX(sym, tf, 14)` | **HIGH.** MT5's built-in ADX has historically differed from Wilder's original in how it handles bars where `+DM` and `−DM` are equal or both non-positive, and in whether DI is smoothed before or after normalisation. This is the most likely numeric divergence in the whole system, and it moves the gate. | **Do not use `iADX`.** Hand-roll Wilder ADX in `RegimeEngine` following Pine's `ta.dmi` step for step: `up = high−high[1]`, `dn = low[1]−low`, `+DM = (up > dn and up > 0) ? up : 0`, `−DM = (dn > up and dn > 0) ? dn : 0`, RMA each over 14, `+DI = 100*rma(+DM)/rma(TR)`, `−DI` likewise, `DX = 100*abs(+DI − −DI)/(+DI + −DI)`, `ADX = rma(DX, 14)`. Then validate against fixture B with `1e-6` relative tolerance, and **also** log `iADX` alongside it for one run so the size of the built-in's error is on record. |

Two further notes:
- Pine's `ta.rma(x, n)` is `alpha = 1/n` exponential smoothing seeded with an
  SMA of the first `n` values. Match that seed exactly.
- Pine's `ta.tr(true)` handles the first bar as `high − low`. Match it.

### 5.5 Fixture B — the real-data regression

Fixture A proves the logic. Fixture B proves it at scale.

3,000 bars of GOLD H1 from `data/`, default parameters, all filters on. Run
both sides, compare, and require:
- **100% agreement on `can_fire` and `dir`.** Not 99%. A single disagreed bar
  is a bug that will recur.
- **100% agreement on `n_live_hi` / `n_live_lo`** after bar 200.
- **`entry`, `sl`, `tp` within `1e-6` relative** on every agreed signal bar.
- A printed histogram of `rejected_by` from both sides that matches
  bucket-for-bucket. This catches the case where both sides reject the same
  bar for *different reasons* — which is a real bug that a boolean comparison
  of `can_fire` would hide entirely.

`compare.py` exits non-zero on any failure and prints the first 20 diverging
rows with all 30 columns side by side.

### 5.6 Known and accepted divergences

Recorded here so they are not rediscovered as bugs. Each needs an explicit
decision in Phase 2, and the decision applies to **both** implementations.

1. **The dead `ext` term in the stop.** Pine line 411:
   `sl = dir > 0 ? math.min(low, ext) - slBuf*atr : ...` with
   `ext = math.max(high, nz(sweptHi, high))`. For a long, `ext >= high >=
   low`, so `min(low, ext) == low` always and the swept level never affects
   the stop. **Decision: MQL5 reproduces the behaviour (`low − slBuf*atr`),
   and the dead term is deleted from the Pine in the same commit.** Making the
   MQL5 "correct" instead of "identical" is how parity is lost on day one.
2. **`maxTrades` 3 (Pine) vs `InpMaxConcurrentPositions` 2 (MQL5).** A
   position-count difference, not a signal difference. Parity compares
   `can_fire`, which is evaluated *before* the concurrency check in the MQL5.
   The Pine's `canFire` includes `array.size(trDir) < maxTrades`, so for
   parity runs the Pine must be set to a value ≥ any count the fixture
   reaches, or the concurrency term must be excluded from the dumped
   `can_fire`. **Decision: dump `can_fire_raw` (pre-concurrency) as the
   compared column, and `can_fire` as an informational one.**
3. **`tpR` 2.0 (Pine) vs `InpFixedTargetR` 3.0 (MQL5).** Deliberate; the
   MQL5 default follows `06_exit_experiment.md`. Parity runs set both to 2.0.
4. **Both-sides-swept bars (P-15).** Divergence by design; measured and
   bounded rather than eliminated.
5. **Pine has no execution layer.** Spread, slippage, `VOLUME_MIN`, stops
   level and prop-firm locks exist only in the MQL5 and can turn a `can_fire`
   into no trade. Parity is defined on the **signal**, never on the fill.

### 5.7 The third implementation, and why it matters most

Both Pine and MQL5 are unverifiable in this container — no TradingView, no
MetaEditor. So the **Python port in `JARVIS/research/strategies.py` is the
referee**, and it is the only one of the three that can be run here, against
`study.py`, with walk-forward and cost sensitivity.

Order of work:
1. Port the sweep-continuation logic into `strategies.py` as
   `liquidity_sniper_follow`, matching this specification exactly.
2. Run the §0 gauntlet on it. **If it fails, stop — no MQL5 is written.**
3. Make the Python emit the same 30-column parity CSV on fixture A and
   fixture B.
4. `compare.py` then referees **three** implementations, pairwise. Two
   agreeing against one localises the bug immediately; without the third,
   a Pine/MQL5 disagreement is just an argument.

---

## 6. WHAT NOT TO BUILD

Each of these is tempting, several were in v19.18, and every one is refused on
a measurement from this repository rather than on taste.

| Feature | Why not |
|---|---|
| **Martingale / size-up after a loss** | Prohibited or "all-or-nothing"-rejected at the firms researched; assume banned everywhere (`PROP_FIRMS.md` §8). Mathematically it converts a small negative expectancy into a rare catastrophic one. To v19.18's credit it had none — `T_WinLadder` sized up after *wins*, which is the correct direction. Not building either. |
| **Grid / averaging down** | Explicitly prohibited at Maven across all accounts. v19.18's `DemaTopUp` added a lot with **SL = 0 and TP = 0** on a DEMA agreement with no profit check — averaging down into a loser, unprotected. Dormant, but present. Deleted, not defaulted off. |
| **Early break-even** | The headline finding. `06_exit_experiment.md`: −0.161R gold, −0.188R US500, −0.308R EURUSD, −0.293R GBPUSD. **Worst rule on 4/4 markets.** Win rate collapses to 15–20% because ordinary noise scratches the trade before the tail that pays for everything can develop. v19.18 armed it at 0.24R — earlier than the 0.5R that was tested. This is the single mechanism most responsible for the give-back. |
| **Any trailing stop that arms below 1R** | Same mechanism, same evidence. The shipped `InpTrailArmR = 0.0` disables trailing entirely; if it is ever enabled the input's own validation refuses values in `(0.0, 1.0)`. |
| **Adaptive / regime-scaled targets** | E-020, four markets, full costs: gate-only **+0.108R**, adaptive **+0.001R**, worse than a plain fixed 3R (+0.029R). The hypothesis was explicitly tested and explicitly lost. Use the regime as a gate; never as a target multiplier. |
| **A hard-wired expansion gate** | E-021, 672 tests with a chronological 70/30 split: the gated sweep-continuation configs went from **4/4 markets +0.166R in-sample to 1/4 markets −0.109R out-of-sample**, and both of the best out-of-sample configs had **gate = none**. E-019's underlying measurement (compressed volatility precedes larger moves, replicated on two timeframes) stands; *gating a traded system on it* does not. Build the gate so it can be switched off without a code change, ship the ungated variant if walk-forward does not separate them, and count `RJ_REGIME_*` rejections separately so its live cost is measured. |
| **Volatility-scaled thresholds (`PtsScale`)** | `05_ea_deep_audit.md`: scaling the threshold and the noise band together leaves the ratio — which is what decides whether a peak is bankable — unchanged. It solves nothing and adds a parameter. |
| **Confidence scores / setup grading / A-B-C quality tiers** | v19.18 had six entry paths, a confluence multiplier, `SessionQuality`, `CoordBoost` and `LiveRisk`. **Not one of them was ever shown to correlate with outcome.** A score that has not been validated against realised R is a number that makes a discretionary decision feel systematic. If a grading is ever proposed, the entry bar is: bucket historical trades by the score and show monotonically increasing expectancy across buckets, out of sample. Until then, every valid setup is the same size. |
| **Per-hour / per-session parameter tables** | 24 buckets × parameters is the textbook overfit, and v19.18's `T_HourLearning` was dead code behind `T_FixedLots` anyway. The one measured session effect (E-019: GOLD 15m, 04–12 UTC 89–93% vs 14–16 UTC 62%) is a **single boolean gate on one instrument** and ships **off** (`InpSessionUtc = ""`). |
| **Basket / net-book P&L management** | v19.18's `LedgerBasket` summed `POSITION_PROFIT` across both directions, so a hedged book netted toward zero and never armed — and a peak recorded while hedged could be "given back" purely by the hedge unwinding, at which point BASKET-LOCK closed **everything** (S3). Positions are independent. |
| **Hedging / opposing positions** | `InpNoOpposing = false` in v19.18 meant `DirectionAllowed()` returned `true` unconditionally, permitting 0.30 lots long and 0.30 lots short simultaneously. Hard-banned at some firms, group-hedging banned at others. The EA holds one direction at a time; a signal opposing an open position is **rejected**, not netted. |
| **Multiple engines / strategy switching** | Two of v19.18's three engines were dead in the shipped defaults, and the file itself said so. One strategy per EA instance. Want a second strategy? Second EA, second magic number, second set of measurements. |
| **Intrabar / tick-level entry (`EARLY-FLIP`)** | Repainting by construction: it fires when bid/ask crosses a line before the bar closes, and it takes flips that un-form by the close. Also `MIN_TRADE_DURATION_SEC = 120` exists specifically to stay outside every firm's HFT/tick-scalping prohibition. |
| **Anything on M1** | `AUDIT_v19_18.md`: M1 gold at a 1.40×ATR stop is **21.4% cost/risk**; the EA's own live log recorded *"spread bill was GBP76.53 = 48% of the loss."* And the 26 Aug session ran at efficiency ratio **0.038** — 26 units of price travelled per unit of progress. Target is <10% cost/risk, ideally <5%, which means H1 (3.1%) or 15m (6.1%), not M1. |
| **A chart panel / object drawing** | ~450 lines of v19.18 that were skimmed and never audited. Visualisation is the Pine script's job. The EA writes a CSV that `study.py` and `compare.py` can read. |
| **A 32-tag exit taxonomy** | 21 of 32 produced **zero** exits across 279 trades. Three exits: stop, target, time. If a fourth is ever proposed it must first be shown, on the `StatisticsEngine` ledger, to improve expectancy against the three that exist. |
| **Retry-forever order logic, or `Sleep()` in `OnTick`** | v19.18 called `Sleep()` inside `ModifySLTP` and `Open`, blocking every other position's management for `T_OrderRetryMs × T_OrderRetryN` (S3). Scheduled retries only. |
| **Randomised entry timing across accounts** | `PROP_FIRMS.md` §7: `stagger_entries_ms: 0` — *"do NOT randomise to disguise copying — that is evasion."* The multi-account answer is fewer accounts across more firms (R-002), not obfuscation. |
| **Optimising 16 parameters at once** | The rule that produced 748 inputs was "add a knob, re-tune, ship". Each parameter must earn its place by improving **walk-forward**, not in-sample, results — one at a time, with the others frozen. |

---

## 7. FILE LAYOUT AND BUILD ORDER

```
JARVIS/ea/
    LiquiditySniper.mq5              orchestrator ONLY, ~250 lines, no logic
    src/
        Types.mqh                    enums + structs, zero dependencies
        Config.mqh                   the 25 inputs + the compile-time constants
        ISignalProvider.mqh          the swappable signal contract  (§1.15)
        Logger.mqh
        StatisticsEngine.mqh
        RiskEngine.mqh
        ExecutionEngine.mqh
        PropFirmEngine.mqh
        RegimeEngine.mqh
        LiquidityEngine.mqh
        SweepEngine.mqh
        EntryEngine.mqh
        TargetEngine.mqh
        LiquiditySniperSignal.mqh    the ONE ISignalProvider implementation
        TradeManagement.mqh
JARVIS/specification/
    EA_ARCHITECTURE.md               this file
    parity/                          §5.1
```

**Phase-1 status of these files.** All fifteen `.mqh` headers and the
`.mq5` orchestrator now exist as **skeletons: declarations and doc comments
only, no bodies**. MQL5 requires a body for every declared method, so the
tree does **not** compile as it stands and is not expected to — the point
is that the interfaces are reviewable before anything is built. Every file
carries the same banner. There is no MetaEditor in the container they were
authored in, so nothing here has been compiled or syntax-checked.

**Implementation order for Phase 2** — deliberately money-first, so that if
the work is interrupted the account is protected rather than the signal being
clever:

1. `Types.mqh`, `Config.mqh`, `ISignalProvider.mqh`, `Logger.mqh` — no
   logic, all plumbing. The interface is written first, before any
   strategy exists, so the strategy cannot quietly acquire a dependency on
   the money layer.
2. `RiskEngine.mqh` — and a `OnInit` spec dump. Run it on demo, read the real
   gold contract spec, and check §3.8's numbers against reality **before
   writing anything else**.
3. `PropFirmEngine.mqh` — with a test harness that drives it from a synthetic
   equity series across DST boundaries.
4. `ExecutionEngine.mqh` + `TradeManagement.mqh` — verified with a manual
   fixed-lot signal, not the real one.
5. `RegimeEngine.mqh` — validated against fixture B for ATR/median/ADX before
   any entry logic exists.
6. `LiquidityEngine.mqh` → `SweepEngine.mqh` → `EntryEngine.mqh` →
   `TargetEngine.mqh` → `LiquiditySniperSignal.mqh` — validated at each
   step against fixture A.
7. `StatisticsEngine.mqh`.
8. `LiquiditySniper.mq5` — wiring.

At every step: the module compiles and its fixture passes before the next one
is started. v19.18 became 20,695 lines because each version explained the
previous version's losses; the antidote is that nothing gets added without a
test that fails before and passes after.

**And nothing in this section begins until §0's four missing tests pass.**

---

## 8. WHAT THIS DOCUMENT DOES NOT ESTABLISH

- **That the strategy is profitable.** It is `PROMISING` (§0). Measured net
  expectancy +0.04R to +0.05R on gold, with no t-statistic, no walk-forward,
  no cost sensitivity and no out-of-sample.
- **That the EA will compile.** No MetaEditor here.
- **That the parity fixtures pass.** They do not exist yet; §5.2 specifies
  them, it does not run them.
- **That the prop-firm rules encoded are correct.** `PROP_FIRMS.md` §0 is
  explicit: every rule came from search-engine summaries, not from pages that
  were opened and read. **A human must verify daily-loss %, daily-loss basis,
  daily-loss reset time and whether max drawdown trails, on each firm's own
  help centre, before any real money is committed.** §8 of that document lists
  the specific unverified items. The engine is built to the harshest reading
  of each precisely because the readings are unverified.
- **That any number in §3.8 matches a real broker.** It uses
  `tick_value = 1.00` at `tick_size = 0.01` as an illustration. Every cash
  figure scales linearly with the real value, which §4.2's `OnInit` spec dump
  exists to obtain.

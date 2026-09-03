//+------------------------------------------------------------------+
//|  Config.mqh — the 25 inputs and the compile-time constants        |
//|  LiquiditySniper MT5 rebuild · PHASE 1 SKELETON                   |
//+------------------------------------------------------------------+
//  SPEC: JARVIS/specification/EA_ARCHITECTURE.md §2
//
//  HARD CAP: 25 inputs. Actual: 25. Of these 16 are optimizable degrees
//  of freedom; 9 are compliance/operational switches that will never be
//  swept. v19.18 had 748 inputs against 279 trades — see E-006 and
//  JARVIS/ea/AUDIT_v19_18.md. Adding a 26th input requires deleting one.
//
//  RULE FOR EVERY FUTURE CHANGE: a parameter earns its place by improving
//  WALK-FORWARD results, one at a time, others frozen. Never in-sample.
//  E-013 records the trap: running 20 parameter sweeps raised the
//  multiple-testing luck bar from t=2.63 to t=2.80, and the best swept
//  variant reached 2.52 — still under the bar it had just raised.
//
//  NOT COMPILED. No MetaEditor in the authoring container.
//+------------------------------------------------------------------+
#ifndef LS_CONFIG_MQH
#define LS_CONFIG_MQH

#include "Types.mqh"

//--- Printed at OnInit at LOG_ERROR level. The one habit worth keeping
//--- verbatim from v19.18: it is the fix for not knowing which build ran.
#define EA_BUILD "LiquiditySniper 0.1.0-skeleton (PHASE 1, NOT IMPLEMENTED)"

//====================================================================//
//  INPUTS — STRUCTURE (4, optimizable)                               //
//====================================================================//
input group "=== STRUCTURE ===";
// Pine `pivLen`. A pivot is only KNOWN pivot_len bars after it forms and
// the code respects that. See §5.3: the MQL5 candidate shift is
// pivot_len + 2 from the just-closed bar, NOT pivot_len + 1.
input int    InpPivotLen              = 8;      // Swing size, bars each side [2..50]
// Pine `eqTol`. Merge distance for equal highs/lows, in ATR. Boundary is
// INCLUSIVE (<=) on both sides — parity test P-03.
input double InpEqualTolAtr           = 0.20;   // Equal high/low merge tolerance x ATR [0.02..1.00]
// Pine `minLvlAge`. A level formed moments ago has no resting orders behind it.
input int    InpMinLevelAgeBars       = 5;      // Level must be this many bars old [0..100]
// Pine `dispAtr`. Measured on the BODY |close-open|, not the range — P-07.
// 0.0 disables the requirement (replaces Pine's separate `needDisp` bool).
input double InpDisplacementAtr       = 1.00;   // Break bar body >= x ATR, 0=off [0.00..3.00]

//====================================================================//
//  INPUTS — REGIME GATE (3, optimizable)                             //
//====================================================================//
input group "=== REGIME GATE ===";
// E-019, replicated GOLD 15m and 1h: ATR <= 1.0x median -> 90% P(3+ATR move
// in 40 bars); ATR >= 2x median -> 25%. >= 3.00 effectively disables.
// E-021 WARNING: gating on this FAILED out-of-sample as a traded rule
// (4/4 markets in-sample -> 1/4 out-of-sample). The measurement stands;
// its value as a filter does not. Do NOT hard-gate without re-testing.
input double InpMaxAtrRatio           = 1.15;   // Max ATR / median ATR [0.50..3.00]
// E-019: ADX 0-15 -> 90%; ADX >= 40 -> 66%. Same E-021 caveat.
input double InpMaxAdx                = 25.0;   // Max ADX [10..60]
// "" = all hours. "04-12" = 04:00-11:59 UTC. Wraps midnight (P-16).
// Measured on GOLD 15m ONLY (04-12 UTC 89-93%, 14-16 UTC 62%) — one
// instrument, so it ships OFF.
input string InpSessionUtc            = "";     // Trading hours UTC "HH-HH", ""=all

//====================================================================//
//  INPUTS — RISK AND SIZING (4, optimizable)                         //
//====================================================================//
input group "=== RISK AND SIZING ===";
// PROP_FIRMS.md §7. 0.35 x 2 concurrent = 0.70% max open risk, which must
// stay strictly below DAILY_SOFT_FRACTION * InpDailyLossLimitPct (1.00%).
// OnInit asserts that chain and returns INIT_FAILED if it is violated.
input double InpRiskPctPerTrade       = 0.35;   // Risk per trade, % of EQUITY [0.05..1.00]
// Pine `slBuf`. Stop beyond the break-bar extreme.
input double InpStopBufferAtr         = 0.30;   // Stop buffer x ATR [0.00..1.50]
// Pine `maxRiskAtr`. Reject the setup outright if the stop is wider.
input double InpMaxStopAtr            = 2.50;   // Reject if stop wider than x ATR [0.50..6.00]
// Pine `maxTrades` is 3; 2 here so risk x N <= 0.70%. Deliberate divergence,
// and it is a position-COUNT difference, not a signal difference — §5.6(2).
input int    InpMaxConcurrentPositions= 2;      // Max concurrent positions [1..5]

//====================================================================//
//  INPUTS — TARGET AND EXIT (5, optimizable)                         //
//====================================================================//
input group "=== TARGET AND EXIT ===";
input double InpMinRewardRisk         = 1.20;   // Reject setup if R:R below [0.50..5.00]
input ENUM_TARGET_MODE InpTargetMode  = TARGET_NEXT_LIQUIDITY; // Target mode
// Pine `tpR` is 2.0; 3.0 here per 06_exit_experiment.md — fixed 3R beat
// fixed 1R by 0.058R on average (30% wins at 3R = +0.181R beats 53% at 1R
// = +0.054R). Also the fallback when no live level exists beyond entry.
input double InpFixedTargetR          = 3.00;   // Fixed R target / fallback [0.50..10.0]
// 0 = off. Time exit in CLOSED bars. 06_exit_experiment.md's best gold exit
// was time-20 (+0.201R); movesize.py measured the 40-bar forward horizon the
// regime gate was validated on. BOTH must be walk-forwarded before either
// is trusted — this default is a choice, not a result.
input int    InpMaxHoldBars           = 40;     // Time exit, closed bars, 0=off [0..500]
// 0.00 = trailing ENTIRELY DISABLED, and that is the shipped default.
// E-008: "break-even at 0.5R then trail" was the WORST exit on 4/4 markets
// (GOLD -0.161R, US500 -0.188R, EURUSD -0.308R, GBPUSD -0.293R). v19.18
// armed its equivalent at 0.24R. If ever enabled, validation refuses
// values in (0.0, 1.0). Standoff is TRAIL_ATR_MULT below, not an input —
// a disabled feature does not get a tuning knob.
input double InpTrailArmR             = 0.00;   // Trail arms at R, 0=OFF [0.00 or 1.00..5.00]

//====================================================================//
//  INPUTS — PROP-FIRM COMPLIANCE (5, NOT optimizable)                //
//====================================================================//
input group "=== PROP-FIRM COMPLIANCE ===";
// Strictest daily limit found: FundingPips Zero / 2 Step Pro, 3%.
// The engine acts at 1/3 (soft) and 1/2 (hard flatten) of this. §3.5.
input double InpDailyLossLimitPct     = 3.00;   // Firm daily loss limit, % [0.50..10.0]
// Strictest overall floor found. ASSUMED TRAILING ALWAYS (§3.4) —
// PROP_FIRMS.md §7: "never assume static"; §8: encode the harsher reading.
input double InpMaxDrawdownPct        = 6.00;   // Max drawdown from HWM, % [1.00..20.0]
// 0 = off. A circuit breaker for a regime/feed failure, NOT a strategy
// input: a low win rate is CORRECT for this style, so a 4-loss streak is
// normal. Clears at the next anchor roll, not on a win.
input int    InpMaxConsecutiveLosses  = 4;      // Consecutive losses then block, 0=off [0..20]
// CLOCK_WORST_OF_ALL keeps four anchors and uses the most restrictive
// floor. Single-clock values only after a HUMAN page-verifies the firm's
// rule (PROP_FIRMS.md §0). §3.2.
input ENUM_RESET_CLOCK InpResetClock  = CLOCK_WORST_OF_ALL; // Daily reset clock
// 0 = off, and OFF IS THE HONEST DEFAULT: there is no verified calendar
// feed in this build. Shipping a filter that silently does nothing is
// worse than shipping none. §3.7.
input int    InpNewsBlackoutMin       = 0;      // News blackout minutes, 0=off [0..360]

//====================================================================//
//  INPUTS — EXECUTION AND OPERATIONS (4, NOT optimizable)            //
//====================================================================//
input group "=== EXECUTION AND OPERATIONS ===";
// Spread as a fraction of the PLANNED STOP DISTANCE, never an absolute
// number. AUDIT_v19_18.md: M1 gold at 1.40xATR was 21.4% cost/risk and
// unsurvivable; its own live log shows the spread bill was 48% of the loss.
// Target <10%, ideally <5%.
input double InpMaxSpreadPctOfStop    = 5.00;   // Max spread as % of stop distance [1.00..25.0]
input long   InpMagicNumber           = 20260901; // Position ownership
// DEMO GUARD. OnInit returns INIT_FAILED on a non-demo account.
// Removed ONLY by Veer, explicitly, in a session. v19.18 had no such check.
input bool   InpDemoOnly              = true;   // Refuse to attach to a live account
input ENUM_LOG_LEVEL InpLogLevel      = LOG_SIGNAL; // LOG_VERBOSE writes the parity CSV

//====================================================================//
//  COMPILE-TIME CONSTANTS — configurable in source, reviewable in    //
//  git, but NOT knobs a backtest can fit. §2.2.                      //
//====================================================================//
#define ATR_PERIOD                14      // Pine ta.atr(14). Changing it breaks parity.
#define ATR_MEDIAN_LEN            50      // Pine ta.median(atr,50). EVEN n -> average the
                                          // two middle values, not the 25th element (§5.4).
#define ADX_PERIOD                14      // Pine ta.dmi(14,14). Hand-rolled, NOT iADX.
#define MAX_LEVELS_PER_SIDE       20      // Pine maxLevels. Memory cap, not an edge parameter.
#define MAX_LEVEL_AGE_BARS       500      // Pine lvlMaxAge. Housekeeping.
#define PIVOT_CANDIDATE_SHIFT_ADD  2      // candidate shift = InpPivotLen + 2 from the
                                          // just-closed bar. +1 is a ONE-BAR LOOK-AHEAD
                                          // versus Pine and is the single most likely
                                          // parity break in the system. §5.3.
#define TRAIL_ATR_MULT           2.0      // only used if InpTrailArmR > 0, which is not default
#define DEVIATION_POINTS          20      // slippage tolerance; a broker fact. UNMEASURED.
#define ORDER_RETRY_N              3      // §4.5
#define ORDER_RETRY_DELAY_MS     200      // scheduled against GetTickCount(). NEVER Sleep().
#define RETRY_ABORT_DRIFT_FRAC  0.25      // abort a retry if price drifted >25% of the stop
                                          // distance from plan: chasing turns a 1.2:1 setup
                                          // into a 0.9:1 setup silently.
#define AMBIGUOUS_RECHECK_MS     500      // bucket C: wait, then re-scan for our comment token
#define EQUITY_POLL_MS           250      // PROP_FIRMS.md §7 poll_interval_ms
#define DAILY_SOFT_FRACTION    0.333      // soft lock at 1/3 of the firm's daily limit
#define DAILY_HARD_FRACTION     0.50      // hard flatten at 1/2 — so the flatten itself,
                                          // INCLUDING exit slippage, lands inside the number
#define DD_SOFT_FRACTION        0.50      // soft lock at 1/2 of max DD
#define DD_HARD_FRACTION       0.667      // hard flatten at 2/3, then LATCHED
#define DD_SOFT_CLEAR_HYST     0.005      // 0.5% equity hysteresis so the soft lock cannot chatter
#define ANCHOR_RECONSTRUCT_HAIRCUT 0.50   // a reconstructed anchor halves that period's budget
#define FRIDAY_FLATTEN_HOUR_UTC   20      // PROP_FIRMS.md §7
#define ROLLOVER_BLOCK_FROM   "21:55"     // The5ers bans rollover scalping; spreads widen hard
#define ROLLOVER_BLOCK_TO     "22:10"
#define MIN_TRADE_DURATION_SEC   120      // defeats HFT/tick-scalping classification everywhere.
                                          // Enforced as: no TIME-EXIT and no TRAIL action inside
                                          // 120s. Broker-side stop and target still apply.
#define MIN_FREE_MARGIN_PCT     30.0      // LOCK_MARGIN threshold after the next order
#define STATS_SLOTS               64      // fixed slots with in_use flags; NO blind wrap (§1.14)
#define GV_PREFIX             "LS_"       // GlobalVariable namespace: LS_<magic>_<key>

#endif // LS_CONFIG_MQH
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//|  ExecutionEngine.mqh — the ONE door to the broker                 |
//|  LiquiditySniper MT5 rebuild · PHASE 1 SKELETON                   |
//+------------------------------------------------------------------+
//  SPEC: JARVIS/specification/EA_ARCHITECTURE.md §1.12, §4.1, §4.5
//
//  RESPONSIBILITY. The ONLY module permitted to call CTrade / OrderSend /
//  OrderSendAsync. Owns filling-mode negotiation, deviation, spread
//  measurement, and the retry state machine.
//
//  WHY "ONE DOOR" IS A RULE. v19.18 had 35 CloseTagged() call sites and 32
//  distinct exit tags competing on every tick with no arbitration, so the
//  realised exit was the MINIMUM of ten independent peak-anchored guards.
//  21 of the 32 tags fired ZERO times across 279 trades. Here there is one
//  door, and every caller has already been told yes by PropFirmEngine.
//
//  HARD CONSTRAINT — NO Sleep() IN THE TICK PATH. v19.18 called Sleep()
//  inside ModifySLTP (line 6988) and Open (line 11456), blocking OnTick for
//  T_OrderRetryMs x T_OrderRetryN and delaying EVERY OTHER position's
//  management (bug S3). Retries here are scheduled against GetTickCount()
//  and executed on subsequent ticks.
//
//  MUST NOT KNOW ABOUT: why a trade is being taken, prop-firm limits, or
//  level structure.
//
//  NOT COMPILED. Declarations only, and the retcode handling below is a
//  DESIGN — real fill behaviour, requote rates and whether the broker
//  actually grants FOK on XAUUSD are live-account facts that cannot be
//  established in this container.
//+------------------------------------------------------------------+
#ifndef LS_EXECUTIONENGINE_MQH
#define LS_EXECUTIONENGINE_MQH

#include <Trade/Trade.mqh>
#include "Types.mqh"
#include "RiskEngine.mqh"

class CLogger;

//--- How a retcode is treated. §4.5.
enum ENUM_SEND_BUCKET
  {
   SEND_OK        = 0,
   SEND_RETRY     = 1,  // A: price moved, NOTHING executed. Safe to retry.
   SEND_ABORT     = 2,  // B: structurally wrong or the account cannot take it.
   SEND_AMBIGUOUS = 3   // C: it MAY have executed. Never blind-retry.
  };

//+------------------------------------------------------------------+
//| PendingSend — one in-flight order attempt.                        |
//| comment_token is UNIQUE per attempt and is how a bucket-C recovery |
//| identifies a fill that happened while the reply was lost.          |
//+------------------------------------------------------------------+
struct PendingSend
  {
   bool              active;
   TradePlan         plan;
   int               attempts;
   ulong             next_attempt_ms;   // GetTickCount() based; NEVER a Sleep()
   string            comment_token;     // "LS<dir><r_x100>" + serial, <= 31 chars
   ENUM_SEND_BUCKET  last_bucket;
   uint              last_retcode;
  };

//+------------------------------------------------------------------+
//| CExecutionEngine                                                  |
//| STATE OWNED: CTrade, the negotiated filling mode, one PendingSend. |
//+------------------------------------------------------------------+
class CExecutionEngine
  {
private:
   CTrade            m_trade;           // the ONE CTrade instance in the program
   string            m_symbol;
   ulong             m_magic;
   int               m_deviation_points;
   int               m_retry_count;
   int               m_retry_delay_ms;
   CRiskEngine      *m_risk;            // borrowed
   CLogger          *m_log;             // borrowed
   ENUM_ORDER_TYPE_FILLING m_filling;
   PendingSend       m_pending;
   ulong             m_send_serial;

   //--- BUCKET A (retry, nothing executed): REQUOTE 10004, PRICE_CHANGED
   //---   10020, PRICE_OFF 10021, TOO_MANY_REQUESTS 10024.
   //--- BUCKET B (abort, do not retry): INVALID_VOLUME 10014, INVALID_PRICE
   //---   10015, INVALID_STOPS 10016, TRADE_DISABLED 10017, MARKET_CLOSED
   //---   10018, NO_MONEY 10019, LIMIT_VOLUME 10034, LIMIT_POSITIONS 10040,
   //---   INVALID_ORDER 10013.
   //---   On INVALID_VOLUME also force RiskEngine::RefreshSpecs().
   //---   On INVALID_STOPS also log the computed stop AGAINST
   //---   SYMBOL_TRADE_STOPS_LEVEL — that pair of numbers is the whole
   //---   diagnosis and without it the error is unreadable.
   //--- BUCKET C (ambiguous, it may have executed): TIMEOUT 10012,
   //---   CONNECTION 10031, DONE_PARTIAL 10009, and any transport-level
   //---   failure of OrderSend itself.
   ENUM_SEND_BUCKET  Classify(const uint retcode) const;

   //--- Bucket C recovery, in order:
   //---   1. wait AMBIGUOUS_RECHECK_MS (SCHEDULED, not slept)
   //---   2. re-scan PositionsTotal() and OrdersTotal() for our magic AND
   //---      this attempt's unique comment_token
   //---   3. found      -> adopt it, verify its stop, stop retrying
   //---   4. not found  -> treat as bucket A, same 3-attempt cap
   //---   5. partial    -> accept the partial, verify the stop, DO NOT top up
   bool              RecoverAmbiguous(const string comment_token, ulong &ticket);

   //--- Before ANY retry, in every bucket:
   //---   if |current_price - plan.entry| > RETRY_ABORT_DRIFT_FRAC * plan.risk_price
   //---        abort, log RETRY_ABORT_DRIFT
   //--- Chasing a moved market turns a 1.2:1 setup into a 0.9:1 setup
   //--- silently: the R:R filter was applied to the PLAN, not to the FILL.
   bool              DriftAcceptable(const TradePlan &plan) const;

public:
                     CExecutionEngine(void);
                    ~CExecutionEngine(void);

   bool              Init(const string symbol, const ulong magic,
                          const int deviation_points, const int retry_count,
                          const int retry_delay_ms,
                          CRiskEngine *risk, CLogger *log);

   //--- Negotiated from SYMBOL_FILLING_MODE, not assumed. UNVERIFIED
   //--- WITHOUT MT5: whether the broker really grants FOK on XAUUSD, and
   //--- what it does with IOC on a partial, are live-account facts.
   bool              RefreshFillingMode(void);
   ENUM_ORDER_TYPE_FILLING FillingMode(void) const;

   //--- (ask - bid) in PRICE, live. This and MarginOkFor are the only
   //--- shift-0 reads in the entire EA, and neither feeds a signal.
   double            SpreadPrice(void) const;

   //--- Spread as a FRACTION OF THE PLANNED STOP DISTANCE, never an
   //--- absolute number. AUDIT_v19_18.md: M1 gold at a 1.40xATR stop is
   //--- 21.4% cost/risk and unsurvivable, and the EA's own live log records
   //--- "spread bill was GBP76.53 = 48% of the loss". Target <10%, ideally
   //--- <5%. The reject is RJ_SPREAD and it blocks THIS SIGNAL ONLY.
   bool              SpreadAcceptable(const double stop_distance_price,
                                      const double max_pct_of_stop,
                                      double &spread_pct) const;

   //--- SENDS WITH sl AND tp ATTACHED. There is no path in this codebase
   //--- that opens a position and attaches a stop on a later tick.
   //---
   //--- AND THEN VERIFIES, because "sent with a stop" and "has a stop" are
   //--- different claims:
   //---   read POSITION_SL for the new ticket
   //---   if POSITION_SL == 0.0:
   //---       ModifyStop up to 3 times, 200 ms apart, via the retry machine
   //---       if still 0.0: CLOSE THE POSITION IMMEDIATELY, log SL_MISSING
   //--- A position without a broker-side stop is not allowed to exist.
   //--- v19.18's S1 bug was the mirror image: ManagePosition began with
   //--- `if(atr <= 0 || sl == 0) return;` as its FIRST guard, so a position
   //--- whose SL was 0 received ZERO management and was completely unbounded.
   bool              OpenPosition(const TradePlan &plan, ulong &ticket, string &err);

   //--- Uses the same classifier and — unlike v19.18 — ACTUALLY RETRIES.
   //--- v19.18's CloseTagged logged "REJECTED, retrying" and had no retry
   //--- loop (bug S2): a rejected close was silently dropped until some
   //--- later tick happened to re-evaluate the same branch, which for a
   //--- peak-anchored exit it may never do because the peak has moved.
   //--- When the caller is a HARD LOCK there is no attempt cap: failing to
   //--- close under LOCK_DAILY_HARD is the one situation where giving up
   //--- is not an option.
   bool              ClosePosition(const ulong ticket, const string reason,
                                   const bool unlimited_retries = false);

   //--- Refused inside SYMBOL_TRADE_FREEZE_LEVEL. Monotonicity (never
   //--- toward entry) is enforced by the CALLER, TradeManagement — this
   //--- module does not know which way is "better".
   bool              ModifyStop(const ulong ticket, const double new_sl,
                                const double new_tp);

   //--- Drives the retry state machine. Called from OnTick.
   //--- Contains NO Sleep().
   void              ProcessPending(void);
   bool              HasPending(void) const;
   void              CancelPending(const string reason);
  };

#endif // LS_EXECUTIONENGINE_MQH
//+------------------------------------------------------------------+

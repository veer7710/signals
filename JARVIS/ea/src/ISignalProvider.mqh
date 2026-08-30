//+------------------------------------------------------------------+
//|  ISignalProvider.mqh — the swappable signal layer                 |
//|  LiquiditySniper MT5 rebuild · PHASE 1 SKELETON                   |
//+------------------------------------------------------------------+
//  SPEC: JARVIS/specification/EA_ARCHITECTURE.md §1.15
//
//  WHY THIS INTERFACE EXISTS — and it is the most important design
//  decision in the tree.
//
//  NOTHING IN THIS REPOSITORY HAS CLEARED THE MULTIPLE-TESTING BAR.
//  E-012: with ~100 configurations tried, the luck threshold is
//  t ~= sqrt(2 ln N) ~= 3.0. The best out-of-sample t observed anywhere
//  is +2.24 (E-021). Sweep-continuation is PROMISING (E-018: beats plain
//  20-bar breakout on 5/5 markets, ~+0.04R net after gold's 0.35 round
//  trip) and nothing stronger.
//
//  E-021 is the reason for the abstraction, stated concretely: 7 of 8
//  in-sample winners failed out-of-sample, and the single best in-sample
//  configuration INVERTED (4/4 markets +0.166R -> 1/4 markets -0.109R).
//  Any strategy welded into an execution layer will have to be cut out of
//  it later, and that surgery is where 20,695-line EAs come from.
//
//  Therefore: the strategy is a REPLACEABLE PART. The money layer
//  (RiskEngine / PropFirmEngine / ExecutionEngine / TradeManagement) is
//  the durable asset and must survive the strategy being deleted.
//
//  THE CONTRACT
//   1. A provider is called ONCE PER CLOSED BAR and never per tick.
//   2. It reads only shift >= 1. No shift-0 read may influence a plan.
//   3. It returns a TradePlan in PRICE. It never sees equity, lots, tick
//      value, spread, the account, or a prop-firm lock, and it has no way
//      to acquire them — none of those types are reachable from here.
//   4. It never sends, modifies or closes an order.
//   5. It is idempotent per bar: calling it twice for the same bar_time
//      must produce the same plan and must not mutate registry state twice.
//   6. Every refusal sets plan.reject to a specific ENUM_REJECT_STAGE.
//      "Returned false with RJ_NONE" is a bug.
//
//  Swapping the strategy = writing one new class that implements this
//  interface and changing one `new` in LiquiditySniper.mq5. No other file
//  changes. That is the whole point.
//
//  NOT COMPILED. Declarations only; MQL5 requires bodies, Phase 2 supplies
//  them. There is no MetaEditor in the authoring container.
//+------------------------------------------------------------------+
#ifndef LS_ISIGNALPROVIDER_MQH
#define LS_ISIGNALPROVIDER_MQH

#include "Types.mqh"

class CLogger;

//+------------------------------------------------------------------+
//| ISignalProvider                                                   |
//|                                                                   |
//| State it owns:  whatever its own strategy needs, and nothing else.|
//| Must NOT know about: equity, balance, lots, tick value, margin,   |
//|   spread, ENUM_LOCK, CTrade, PositionState, open tickets, the     |
//|   daily anchor, or how many positions are already open.           |
//+------------------------------------------------------------------+
class ISignalProvider
  {
public:
   virtual          ~ISignalProvider(void) {}

   //--- Identity, written into TradePlan.source_name and every log row so a
   //--- CSV can never be ambiguous about which strategy produced it.
   virtual string    Name(void) const = 0;
   virtual string    Version(void) const = 0;

   //--- Construct indicator handles, size buffers, validate parameters.
   //--- MUST NOT send an order or read the account. Returns false on any
   //--- invalid parameter, with `why` set — OnInit turns that into INIT_FAILED.
   virtual bool      Init(const string symbol, const ENUM_TIMEFRAMES tf,
                          CLogger *log, string &why) = 0;

   //--- How many closed bars of history must exist before Evaluate() may be
   //--- trusted. The orchestrator refuses to trade until Bars() exceeds it.
   //--- For LiquiditySniper: max(ATR_MEDIAN_LEN + ATR_PERIOD, MAX_LEVEL_AGE_BARS)
   //--- plus the 200-bar parity warm-up.
   virtual int       WarmupBars(void) const = 0;

   //--- THE ONE ENTRY POINT. Called once per closed bar, from the new-bar
   //--- branch only. `bar_time` is the open time of the bar that just closed.
   //--- Returns true only when plan.valid is true.
   //--- Fills: direction, entry, stop, target, risk_price, reward_risk,
   //---        atr_at_signal, signal_bar, source_name, reject.
   //--- NEVER fills: lots.
   virtual bool      Evaluate(const datetime bar_time, TradePlan &plan) = 0;

   //--- Called on every closed bar EVEN WHEN the orchestrator will not trade
   //--- (locked, at position limit, spread too wide), so registry state stays
   //--- continuous and the parity CSV has no holes. Evaluate() may then be
   //--- skipped. Implementations that keep rolling state MUST do that work
   //--- here, not in Evaluate().
   virtual bool      OnNewBarObserve(const datetime bar_time) = 0;

   //--- One CSV row for the parity harness, §5.1. Column set and ORDER are
   //--- fixed by the harness; the provider fills its own columns and leaves
   //--- the rest empty. Returns "" if the provider has no parity dump.
   virtual string    ParityRow(const datetime bar_time) const = 0;

   //--- Human-readable one-liner for the journal: gate values, live level
   //--- counts, last rejection. Never used in a decision.
   virtual string    Diagnostics(void) const = 0;

   //--- Drop all rolling state. Called on OnInit after Adopt() and whenever
   //--- the feed is judged discontinuous (symbol change, history refill).
   virtual void      Reset(void) = 0;
  };

#endif // LS_ISIGNALPROVIDER_MQH
//+------------------------------------------------------------------+

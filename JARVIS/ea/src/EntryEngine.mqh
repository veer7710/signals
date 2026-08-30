//+------------------------------------------------------------------+
//|  EntryEngine.mqh — sweep + regime -> a directional plan           |
//|  LiquiditySniper MT5 rebuild · PHASE 1 SKELETON                   |
//+------------------------------------------------------------------+
//  SPEC: JARVIS/specification/EA_ARCHITECTURE.md §1.7
//
//  RESPONSIBILITY. Turn (SweepEvent, RegimeState, closed bar) into a
//  TradePlan with direction, entry and stop filled in. Nothing else.
//
//  DELIBERATELY STATELESS ACROSS BARS. It holds no armed/pending state
//  because the retest path is NOT being built — that is a separate,
//  untested hypothesis (spec §6, and the Pine's own retest block does not
//  currently compile, §5.0).
//
//  THE DIRECTION MAPPING — the single most consequential line in the EA:
//      a level ABOVE was broken (sell-side liquidity taken)  ->  LONG
//      a level BELOW was broken (buy-side liquidity taken)   ->  SHORT
//  This is CONTINUATION. It is the opposite of the retail assumption.
//  E-017, ~10,000 sweep events, first-touch resolution, ties counted as
//  losses: FADE 44.5% at 1R on GOLD 15m against a 49.2% coin flip at the
//  same bars; FOLLOW 54.1%, and FOLLOW beat FADE on 5/5 markets.
//  E-018: FOLLOW also beat a plain "buy any 20-bar high" on 5/5 markets by
//  an average +3.1 points, so the liquidity layer carries information a
//  plain breakout does not. Status is PROMISING, NOT confirmed.
//
//  MUST NOT KNOW ABOUT: equity, lots, tick value, spread, _Point, the
//  broker, or prop-firm state. It works purely in price. The word `lots`
//  appears in TradePlan; this class never writes it.
//
//  NOT COMPILED. Declarations only.
//+------------------------------------------------------------------+
#ifndef LS_ENTRYENGINE_MQH
#define LS_ENTRYENGINE_MQH

#include "Types.mqh"

//+------------------------------------------------------------------+
//| CEntryEngine                                                      |
//| STATE OWNED: two configured constants. Nothing rolls between bars.|
//+------------------------------------------------------------------+
class CEntryEngine
  {
private:
   double            m_stop_buffer_atr;   // Pine slBuf
   double            m_max_stop_atr;      // Pine maxRiskAtr

public:
                     CEntryEngine(void);
                    ~CEntryEngine(void);

   bool              Init(const double stop_buffer_atr, const double max_stop_atr);

   //--- THE STOP FORMULA, EXACTLY (Pine line 411 behaviour):
   //---     entry      = signal_bar.close
   //---     long  stop = signal_bar.low  - stop_buffer_atr * atr
   //---     short stop = signal_bar.high + stop_buffer_atr * atr
   //---     risk_price = |entry - stop|
   //---     reject RJ_STOP_TOO_WIDE if risk_price > max_stop_atr * atr
   //---     reject if risk_price <= 0
   //---
   //--- Pine writes `math.min(low, ext)` where `ext = max(high, sweptHi)`.
   //--- For a long, ext >= high >= low, so the min ALWAYS returns low and
   //--- the swept level never influences the stop. That term is a dead
   //--- branch. The MQL5 reproduces the BEHAVIOUR (low - buf*atr).
   //--- Parity test P-14 exists to catch the "more sensible" implementation
   //--- that uses sweptHi: being correct instead of identical is how parity
   //--- is lost on day one. The dead term is deleted from the Pine in the
   //--- SAME COMMIT as any change here, never on one side only.
   //---
   //--- BOTH SIDES SWEPT ON ONE BAR: the plan is INVALID with reject
   //--- RJ_NO_SWEEP. The bar is an outside bar and the direction is
   //--- genuinely unknowable at its close. Pine resolves it to LONG by an
   //--- accident of ternary order; that is an artefact, not a decision.
   //--- Documented divergence, spec §5.6(4), parity test P-15, and
   //--- compare.py counts these bars — if fixture B produces >2% of them
   //--- the divergence matters and the Pine must be changed to match.
   bool              Evaluate(const SweepEvent &hi_event, const SweepEvent &lo_event,
                              const RegimeState &regime, const MqlRates &signal_bar,
                              const double atr, TradePlan &plan);
  };

#endif // LS_ENTRYENGINE_MQH
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//|  RiskEngine.mqh — money <-> lots, from RUNTIME symbol specs       |
//|  LiquiditySniper MT5 rebuild · PHASE 1 SKELETON                   |
//+------------------------------------------------------------------+
//  SPEC: JARVIS/specification/EA_ARCHITECTURE.md §1.10, §4.2, §4.6
//
//  RESPONSIBILITY. Convert money into lots and back, using symbol
//  specifications READ AT RUNTIME. This is the ONLY module that touches
//  the SymbolInfo* sizing fields.
//
//  THE SIZING FORMULA, IN FULL:
//     money_per_lot_per_price = SYMBOL_TRADE_TICK_VALUE / SYMBOL_TRADE_TICK_SIZE
//     risk_cash  = InpRiskPctPerTrade / 100.0 * ACCOUNT_EQUITY
//     raw_lots   = risk_cash / (stop_distance_price * money_per_lot_per_price)
//     lots       = floor(raw_lots / VOLUME_STEP) * VOLUME_STEP
//     if (lots > VOLUME_MAX) lots = VOLUME_MAX
//     if (lots < VOLUME_MIN) return 0.0, reject = RJ_LOTS_BELOW_MIN  // SKIP
//
//  THAT LAST LINE IS NOT A FORMALITY. If the smallest tradable lot exceeds
//  the risk budget, the correct action is NOT TO TRADE — not to trade the
//  minimum. Rounding up increases risk beyond the configured budget, and
//  the budget is what keeps the prop-firm limit unreachable (§3.8).
//
//  WHAT THIS REPLACES. v19.18 shipped T_FixedLots = 0.03 and LotFor()
//  returned at line 7432, before reaching ANY aggregate ceiling: the code
//  at 7739 (InpMaxTotalLots) and 7752 (AutoMaxExposurePct) was unreachable,
//  as were AutoMaxLots(), RiskCeilingLots() and T_MaxRiskStackMult. Net:
//  position size had no relationship to stop distance, volatility or
//  equity. Roughly 30 sizing inputs existed and none of them ran.
//
//  3/5-DIGIT BROKERS. The word "pip" does not appear in this codebase.
//  All internal arithmetic is in PRICE, which is dimensionless with
//  respect to digit count. SYMBOL_POINT is used in EXACTLY TWO places:
//  MinStopDistancePrice() and CTrade::SetDeviationInPoints(). Everything
//  else — ATR multiples, stop distances, targets, spread as a fraction of
//  stop, R multiples — is a ratio of prices and is unit-free by
//  construction. This is the fix for v19.18's S2 bug, where a "point" was
//  defined as one unit of price and T_SlFloorPtsAbs = 1.20 became a
//  12,000-pip stop floor on EURUSD while T_MaxLossPts = 3.0 and
//  T_TargetPts = 8.0 could never fire. The header claimed "MULTI-SYMBOL,
//  FOR FREE"; the EA was gold-only whatever the switches said.
//
//  MUST NOT KNOW ABOUT: signals, levels, regime, prop-firm locks, or the
//  CTrade object. It computes; it does not act.
//
//  NOT COMPILED. Declarations only.
//+------------------------------------------------------------------+
#ifndef LS_RISKENGINE_MQH
#define LS_RISKENGINE_MQH

#include "Types.mqh"

//+------------------------------------------------------------------+
//| CRiskEngine                                                       |
//| STATE OWNED: one cached SymbolSpecs struct and its refresh time.  |
//+------------------------------------------------------------------+
class CRiskEngine
  {
private:
   string            m_symbol;
   SymbolSpecs       m_spec;
   datetime          m_spec_read_time;

public:
                     CRiskEngine(void);
                    ~CRiskEngine(void);

   bool              Init(const string symbol);

   //--- Re-read every field of SymbolSpecs from the terminal. Called on
   //--- OnInit, on EVERY NEW BAR, and after any TRADE_RETCODE_INVALID_VOLUME.
   //--- Guards tick_size > 0 BEFORE dividing — a zero there is a silent
   //--- division by zero that produces an infinite lot size.
   bool              RefreshSpecs(void);

   //--- False when the specs cannot support sizing (tick_size <= 0,
   //--- tick_value <= 0, volume_step <= 0, trade_mode != FULL). The caller
   //--- raises LOCK_SPECS and the EA refuses to open anything. Existing
   //--- positions are kept — their stops are already attached broker-side.
   bool              SpecsValid(string &why) const;

   //--- The whole currency conversion, in one number: tick_value/tick_size.
   double            MoneyPerLotPerPrice(void) const;

   //--- pct/100 * ACCOUNT_EQUITY. Equity, never balance — for the same
   //--- reason the prop engine uses equity: floating P/L is real money.
   double            RiskCashForPct(const double pct) const;

   //--- The formula above. Returns 0.0 and sets `reject` when the result is
   //--- below VOLUME_MIN. NEVER ROUNDS UP.
   double            LotsForRisk(const double stop_distance_price,
                                 const double risk_cash,
                                 ENUM_REJECT_STAGE &reject) const;

   //--- floor to VOLUME_STEP, clamp to [VOLUME_MIN, VOLUME_MAX].
   //--- Uses floor, never MathRound, never MathCeil.
   double            NormalizeLots(const double lots) const;

   //--- SYMBOL_TRADE_STOPS_LEVEL * SYMBOL_POINT. A plan violating this is
   //--- REJECTED (RJ_STOP_TOO_TIGHT), never silently widened: widening
   //--- changes R, which changes lot size, which breaks the risk budget
   //--- the plan was validated against.
   double            MinStopDistancePrice(void) const;

   //--- SYMBOL_TRADE_FREEZE_LEVEL * SYMBOL_POINT. ModifyStop is refused
   //--- inside this band.
   double            FreezeDistancePrice(void) const;

   //--- NormalizeDouble to SYMBOL_DIGITS. Every price sent to the broker
   //--- passes through here.
   double            NormalizePrice(const double p) const;

   //--- OrderCalcMargin for the prospective order; false if it would leave
   //--- free margin below MIN_FREE_MARGIN_PCT of equity.
   bool              MarginOkFor(const int direction, const double lots,
                                 const double price) const;

   bool              GetSpecs(SymbolSpecs &out) const;

   //--- Printed at OnInit at LOG_ERROR level so it appears in EVERY journal.
   //--- 05_ea_deep_audit.md flags that a broker screenshot of the gold
   //--- contract spec is still a missing input; this print is the
   //--- substitute, and it must be read on the first demo run before any
   //--- cash figure in spec §3.8 is trusted. §3.8 illustrates with
   //--- tick_value = 1.00 at tick_size = 0.01; every cash number there
   //--- scales linearly with the real value.
   string            SpecDump(void) const;
  };

#endif // LS_RISKENGINE_MQH
//+------------------------------------------------------------------+

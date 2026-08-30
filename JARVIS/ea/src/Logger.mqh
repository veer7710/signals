//+------------------------------------------------------------------+
//|  Logger.mqh — structured output, and the parity CSV               |
//|  LiquiditySniper MT5 rebuild · PHASE 1 SKELETON                   |
//+------------------------------------------------------------------+
//  SPEC: JARVIS/specification/EA_ARCHITECTURE.md §1.13, §5.1
//
//  RESPONSIBILITY. Structured output to the Experts log and to a CSV that
//  the parity harness and study.py can both read.
//
//  MUST NOT: make decisions, or be absent from any rejection path. Every
//  `return false` in the signal chain writes a Reject(). The value of the
//  old EA's instrumentation was that it recorded SUPPRESSED attempts as
//  well as taken ones, so the cost of every veto was visible; that is the
//  habit being ported, not the 32-tag taxonomy around it.
//
//  NOT COMPILED. Declarations only.
//+------------------------------------------------------------------+
#ifndef LS_LOGGER_MQH
#define LS_LOGGER_MQH

#include "Types.mqh"

//+------------------------------------------------------------------+
//| CLogger                                                           |
//| STATE OWNED: one file handle, the level, a small line buffer.     |
//+------------------------------------------------------------------+
class CLogger
  {
private:
   ENUM_LOG_LEVEL    m_level;
   int               m_handle;
   string            m_csv_path;
   string            m_build_id;
   bool              m_header_written;

public:
                     CLogger(void);
                    ~CLogger(void);

   //--- Prints build_id at OnInit at LOG_ERROR level so it appears in every
   //--- journal. This is the one habit worth keeping verbatim from v19.18
   //--- (#define EA_BUILD): it is the fix for not knowing which build was
   //--- actually running when a result was produced.
   bool              Init(const ENUM_LOG_LEVEL level, const string csv_path,
                          const string build_id);

   void              Event (const ENUM_LOG_LEVEL lvl, const string tag, const string msg);

   //--- Every evaluated bar that produced a direction, whether or not it
   //--- became a trade. `outcome` is "FILLED", "REJECTED" or "LOCKED".
   void              Signal(const SweepEvent &s, const RegimeState &r,
                            const TradePlan &p, const string outcome);

   //--- Called on EVERY refusal, with the specific stage. The histogram of
   //--- these is what compare.py matches bucket-for-bucket between the two
   //--- implementations: two engines can agree on can_fire and still be
   //--- rejecting the same bar for DIFFERENT reasons, which a boolean
   //--- comparison hides entirely (spec §5.5).
   void              Reject(const ENUM_REJECT_STAGE stage, const string detail);

   //--- slippage_price is fill_price - plan.entry, signed by direction.
   //--- Logged on every fill because DEVIATION_POINTS = 20 and
   //--- RETRY_ABORT_DRIFT_FRAC = 0.25 are GUESSES until this column has a
   //--- few hundred rows in it.
   void              Fill  (const ulong ticket, const TradePlan &p,
                            const double fill_price, const double slippage_price);

   //--- tag is one of exactly three: "STOP", "TARGET", "TIME" — plus
   //--- "FLATTEN:<lock>" when a prop lock closed it. If a fourth ever
   //--- appears here without a spec change, that is the 32-tag failure mode
   //--- starting again.
   void              Exit  (const ulong ticket, const string tag,
                            const double profit_cash, const double r_realized,
                            const double r_peak);

   void              Lock  (const ENUM_LOCK lock, const string reason,
                            const double equity, const double floor_eq);

   //--- The 30-column parity row, written once per closed bar when
   //--- InpLogLevel == LOG_VERBOSE. Column set and ORDER are fixed by
   //--- JARVIS/specification/parity/compare.py and must not be reordered
   //--- without changing the harness in the same commit:
   //---   bar_index, time_utc, open, high, low, close,
   //---   atr, atr_median, atr_ratio, adx, in_session, expansion_ok,
   //---   n_live_hi, n_live_lo,
   //---   new_level_hi_px, new_level_hi_bar, new_level_hi_hits,
   //---   new_level_lo_px, new_level_lo_bar, new_level_lo_hits,
   //---   swept_hi_px, swept_hi_hits, swept_lo_px, swept_lo_hits,
   //---   displacement_ok, can_fire_raw, dir, entry, sl, tp, risk, rr,
   //---   rejected_by
   //--- can_fire_raw is PRE-CONCURRENCY (spec §5.6(2)): the Pine's canFire
   //--- includes its own maxTrades term, so the compared column must
   //--- exclude the position-count check on both sides.
   void              BarState(const datetime bar_time, const RegimeState &r,
                              const int live_hi, const int live_lo,
                              const string provider_row);

   void              Flush(void);
   ENUM_LOG_LEVEL    Level(void) const;
  };

#endif // LS_LOGGER_MQH
//+------------------------------------------------------------------+

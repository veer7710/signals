//+------------------------------------------------------------------+
//|  TargetEngine.mqh — where the trade is trying to go               |
//|  LiquiditySniper MT5 rebuild · PHASE 1 SKELETON                   |
//+------------------------------------------------------------------+
//  SPEC: JARVIS/specification/EA_ARCHITECTURE.md §1.8
//
//  RESPONSIBILITY. Fill plan.target and plan.reward_risk, and reject the
//  plan when reward_risk < min_rr. That is the entire job.
//
//  THE TARGET IS SET ONCE, AT ENTRY, AND IS NEVER RECOMPUTED.
//  There is no target extension, no runner, no partial, no scale-out and
//  no regime-scaled target. E-020, four markets, full costs, identical
//  entries: gate-only +0.108R, ADAPTIVE TARGET +0.001R, plain fixed 3R
//  +0.029R, fixed 1R -0.029R. Adaptive targeting sounded better and
//  measured worse than a plain fixed target. The hypothesis was tested
//  and it lost.
//
//  MUST NOT KNOW ABOUT: the regime (it holds no CRegimeEngine pointer and
//  cannot acquire one), the account, open positions, or how long a trade
//  has been held.
//
//  NOT COMPILED. Declarations only.
//+------------------------------------------------------------------+
#ifndef LS_TARGETENGINE_MQH
#define LS_TARGETENGINE_MQH

#include "Types.mqh"
#include "LiquidityEngine.mqh"

//+------------------------------------------------------------------+
//| CTargetEngine                                                     |
//| STATE OWNED: a BORROWED registry pointer and three constants.     |
//+------------------------------------------------------------------+
class CTargetEngine
  {
private:
   CLiquidityEngine *m_levels;       // borrowed; never deleted here
   ENUM_TARGET_MODE  m_mode;
   double            m_fixed_r;      // InpFixedTargetR, also the fallback
   double            m_min_rr;       // InpMinRewardRisk

public:
                     CTargetEngine(void);
                    ~CTargetEngine(void);

   bool              Init(CLiquidityEngine *levels, const ENUM_TARGET_MODE mode,
                          const double fixed_r, const double min_rr);

   //--- PRECONDITION: SweepEngine::DetectOnClosedBar has ALREADY marked this
   //--- bar's broken levels swept. Violating that ordering produces a target
   //--- sitting on a level this bar destroyed. Parity test P-10.
   //---
   //--- TARGET_NEXT_LIQUIDITY: nearest LIVE level beyond entry in the
   //---   trade's direction. If none exists, fall back to fixed_r —
   //---   Pine line 415 does exactly this via na(lvlTp), and the fallback
   //---   must NOT emit "no trade". Parity test P-11.
   //--- TARGET_FIXED_R: entry + direction * fixed_r * plan.risk_price.
   //---
   //--- Sets plan.reject = RJ_RR_TOO_LOW and plan.valid = false when
   //--- reward_risk < min_rr. Parity test P-12: both implementations must
   //--- reject on the SAME bar.
   bool              Resolve(TradePlan &plan);
  };

#endif // LS_TARGETENGINE_MQH
//+------------------------------------------------------------------+

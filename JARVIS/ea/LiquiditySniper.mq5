//+------------------------------------------------------------------+
//|  LiquiditySniper.mq5 — ORCHESTRATOR ONLY                          |
//|  PHASE 1 SKELETON · NO TRADING LOGIC LIVES IN THIS FILE           |
//+------------------------------------------------------------------+
//  SPEC: JARVIS/specification/EA_ARCHITECTURE.md §4.3, §7
//
//  This file is OnInit / OnTick / OnTimer / OnDeinit wiring and the order
//  of operations. Target size ~250 lines. If a price comparison, an ATR
//  multiple or a lot calculation ever appears here, it belongs in a module.
//
//  NOT COMPILED, NOT TICK-TESTED. There is no MetaTrader and no
//  MetaEditor in the container this was authored in. Declarations only:
//  MQL5 requires a body for every declared function, so this tree will not
//  build until Phase 2 supplies them. Phase 2 is BLOCKED until
//  sweep-continuation clears the four missing tests in spec §0.
//+------------------------------------------------------------------+
#property copyright "JARVIS"
#property version   "0.10"
#property strict

#include "src/Types.mqh"
#include "src/Config.mqh"
#include "src/Logger.mqh"
#include "src/StatisticsEngine.mqh"
#include "src/RiskEngine.mqh"
#include "src/ExecutionEngine.mqh"
#include "src/PropFirmEngine.mqh"
#include "src/TradeManagement.mqh"
#include "src/ISignalProvider.mqh"
#include "src/LiquiditySniperSignal.mqh"

//--- Module instances. The ONLY `new` in the program is the signal
//--- provider, and swapping the strategy means changing that one line.
CLogger            g_log;
CStatisticsEngine  g_stats;
CRiskEngine        g_risk;
CExecutionEngine   g_exec;
CPropFirmEngine    g_prop;
CTradeManagement   g_mgmt;
ISignalProvider   *g_signal = NULL;

datetime           g_last_bar = 0;

//+------------------------------------------------------------------+
//| OnInit — order matters, and it is money-first.                    |
//|                                                                   |
//|   1. g_log.Init(...) and print EA_BUILD                            |
//|   2. DEMO GUARD: if(InpDemoOnly && ACCOUNT_TRADE_MODE !=           |
//|      ACCOUNT_TRADE_MODE_DEMO) -> INIT_FAILED. v19.18 had no such   |
//|      check anywhere in 20,695 lines. Removed only by Veer,         |
//|      explicitly, in a session.                                     |
//|   3. ValidateInputs() — including the risk-chain assertion:        |
//|        risk*positions < soft < hard < firm limit                   |
//|      INIT_FAILED if violated.                                      |
//|   4. g_risk.Init + RefreshSpecs + SpecsValid; print SpecDump() at  |
//|      LOG_ERROR so the real contract spec is in every journal.      |
//|   5. g_prop.Init then g_prop.Restore() — anchors, HWM, streak, and |
//|      the LATCHED DD_HARD flag are read back BEFORE anything else   |
//|      can trade.                                                    |
//|   6. g_exec.Init + RefreshFillingMode                              |
//|   7. g_stats.Init + Restore                                        |
//|   8. g_mgmt.Init then Adopt() — rebuild PositionState from the     |
//|      broker, three-tier r_distance recovery, verify every stop.    |
//|   9. g_signal = new CLiquiditySniperSignal(); g_signal.Init(...)   |
//|  10. EventSetMillisecondTimer(EQUITY_POLL_MS)                      |
//+------------------------------------------------------------------+
int  OnInit(void);

//+------------------------------------------------------------------+
//| OnTick — EXACTLY this order. Safety first, signal last.           |
//|                                                                   |
//|   1. g_prop.OnTick()                    equity poll, anchors, locks|
//|   2. if(g_prop.MustFlatten(...))                                   |
//|          g_mgmt.FlattenAll(reason); return;   <- nothing else runs |
//|   3. g_mgmt.VerifyStopsOnTick()         a stop can be stripped     |
//|                                          at any time, not just at  |
//|                                          fill                      |
//|   4. g_exec.ProcessPending()            scheduled retries, NO Sleep|
//|   5. g_stats.TrackOpenPositions()       MFE/MAE, read-only         |
//|   6. if(!IsNewBar()) return;            <- EVERYTHING BELOW IS     |
//|                                            NEW-BAR ONLY            |
//|   7. g_risk.RefreshSpecs()                                         |
//|   8. g_mgmt.OnNewBar(bar_time, atr)     time exit, optional trail  |
//|   9. g_signal.OnNewBarObserve(bar_time) registry stays continuous  |
//|      even when we cannot trade                                     |
//|  10. if(!g_prop.CanOpenNewPosition(...)) { log; return; }          |
//|  11. if(g_mgmt.CountOpen() >= InpMaxConcurrentPositions) return;   |
//|  12. g_signal.Evaluate(bar_time, plan)  -> plan in PRICE           |
//|  13. reject if plan.direction opposes an open position (no hedging)|
//|  14. g_exec.SpreadAcceptable(plan.risk_price, InpMaxSpreadPctOfStop)|
//|  15. plan.lots = g_risk.LotsForRisk(...)  0.0 -> SKIP, never the   |
//|      minimum lot                                                   |
//|  16. g_risk.MarginOkFor(...)                                       |
//|  17. g_exec.OpenPosition(plan, ticket)  SL AND TP ATTACHED AT SEND |
//|                                                                    |
//| v19.18's OnTick carried the comment "Entries only on a new bar" at |
//| line 20644 and then called Engine_Trend() on every tick at 20692.  |
//| Here the split is enforced by the call graph: the signal modules   |
//| are unreachable except from the new-bar branch.                    |
//+------------------------------------------------------------------+
void OnTick(void);

//+------------------------------------------------------------------+
//| OnTimer — EQUITY_POLL_MS = 250. Catches the case where ticks stop |
//| arriving but equity is still moving on the broker's side.         |
//|   1. g_prop.OnTimer()                                              |
//|   2. if(g_prop.MustFlatten(...)) g_mgmt.FlattenAll(reason)         |
//|   3. g_exec.ProcessPending()                                       |
//| It does NOT evaluate signals. Ever.                                |
//+------------------------------------------------------------------+
void OnTimer(void);

//+------------------------------------------------------------------+
//| OnDeinit — runs for EVERY reason including REASON_RECOMPILE.      |
//|   g_prop.Persist(); g_stats.Persist(); print g_stats.Report();    |
//|   g_log.Flush(); delete g_signal; EventKillTimer();               |
//+------------------------------------------------------------------+
void OnDeinit(const int reason);

//--- New-bar detection. CopyTime failure means a feed problem and the
//--- answer is to do NOTHING, not to reuse the last bar time.
bool IsNewBar(datetime &bar_time);

//--- All input-range and cross-input validation, including the risk chain.
bool ValidateInputs(string &why);

//+------------------------------------------------------------------+

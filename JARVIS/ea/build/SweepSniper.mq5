//+------------------------------------------------------------------+
//|  SweepSniper.mq5  —  the liquidity sweep Veer trades, automated   |
//|                                                                  |
//|  "i literally run liquidity sweep strat myself and i have 80%     |
//|   winrate. i wanted u using ict smc perfect and automate so i     |
//|   dont have to do analysis"                                       |
//|                                                                  |
//|  THE RULES. Every one was measured before it was allowed in, on   |
//|  157,051 real M1 bars built from 18,816,940 bid/ask ticks with    |
//|  each bar charged its OWN measured spread.                        |
//|                                                                  |
//|   1 LEVEL       a confirmed swing pivot, 5 bars either side.      |
//|                 Resting liquidity - the stops above a high or     |
//|                 below a low.                                       |
//|   2 SWEEP       price runs THROUGH it by 0.10 ATR. The stop run.  |
//|   3 THE WICK    the sweep bar's body must be at most 64.6% of its |
//|                 range. THIS IS THE FAKEOUT FILTER. A sweep that   |
//|                 CLOSES with a big body is a real breakout and     |
//|                 fading it is how you lose; a sweep that is mostly |
//|                 WICK is a rejection. The DIRECTION of this rule   |
//|                 comes from ICT, not from the data - the data only |
//|                 supplied the cut, from the first half of the      |
//|                 sample, tested once on the second (E-135d).       |
//|   4 DISPLACEMENT  MEASURED, AND THEN SWITCHED OFF. It was the     |
//|                 second half of the tested filter and it is worth   |
//|                 real money - but it is evaluated at the FILL bar,  |
//|                 and an EA holding a resting limit cannot know      |
//|                 which bar will fill it. E-139 tested all four ways |
//|                 of getting round that and every one was worse than |
//|                 simply dropping it:                                 |
//|                   A wick+disp, limit at level  349.7 NOT EA-ABLE   |
//|                   B wick only, limit at level  310.7 <- SHIPPED    |
//|                   C wick+disp, market next bar  81.4 (dead at      |
//|                                                 0.05 slippage)     |
//|                   D limit, then bail out       228.4               |
//|                 A rule an EA can execute beats a better rule it    |
//|                 cannot. This is the P92 lesson - a 52% signal gap  |
//|                 between a Pine and an EA sat unnoticed for 180     |
//|                 commits because nobody checked.                     |
//|   5 ENTRY       a limit resting AT the level. NOT the sweep's     |
//|                 close - E-130 measured that and it cost 97 of     |
//|                 97.1 points on System A.                           |
//|   6 STOP        beyond the SWEEP EXTREME + 0.30 ATR. Where the    |
//|                 setup is genuinely wrong, not a fixed distance.    |
//|   7 RISK CAP    REFUSE the setup if that stop is wider than 2.0   |
//|                 ATR. Read the audit below before touching this.    |
//|   8 EXIT        give back 25%: the stop ratchets to entry + 75%   |
//|                 of the best excursion. No fixed target - every    |
//|                 fixed target banked less (E-137).                  |
//|                                                                  |
//|  MEASURED — these are VARIANT B's numbers, the one that ships,     |
//|  not variant A's. Quoting A's validation for B would be quoting    |
//|  numbers for a system that is not the one running (E-139b).        |
//|    2579 trades, 23.6/day, 65.1% win, +309.5 points, GBP1797 @0.01  |
//|    control  real +0.1119/trade vs -0.0142  =  107.3 control se     |
//|    in-sample +0.1241  ->  OUT OF SAMPLE +0.0991                    |
//|    walk-forward +0.1056/+0.1477/+0.1155/+0.0927/+0.0968   5 of 5   |
//|    cost   310.7 at a 0.20 spread -> 241.8 at a 0.40 spread         |
//|    slippage 309.5 -> 257.9 at 0.02 -> 180.5 at 0.05 -> 51.6 at     |
//|             0.10, charged on EVERY trade                            |
//|    max drawdown GBP12.68, worst single trade -GBP4.63              |
//|                                                                    |
//|  THE AUDIT THAT CHANGED THE DESIGN (E-138)                        |
//|    WITHOUT the risk cap the worst single trade was -GBP34.27 and  |
//|    the max drawdown GBP37.99 - 57% and 63% of a GBP60 account.    |
//|    The edge was never the problem. The ACCOUNT would have died    |
//|    before the edge paid. The stop sits beyond the SWEEP EXTREME   |
//|    and nothing bounds how far a sweep runs; 0.01 lots is the      |
//|    floor (E-081) so a stop too wide to afford cannot be sized     |
//|    down - only REFUSED.                                            |
//|         risk cap    points   max DD    worst trade                 |
//|         none         316.6   GBP37.99   -GBP34.27                  |
//|         2.0 ATR      310.7   GBP14.93   -GBP5.90                   |
//|         1.2 ATR      309.5   GBP12.68   -GBP4.63   <- SHIPPED      |
//|    It costs almost nothing and removes two thirds of the          |
//|    drawdown. It is not an optimisation.                            |
//|                                                                    |
//|  ON THE GIVE-BACK: tighter measured better all the way down -      |
//|  5% gives 374.1 points against 25%'s 309.5, and it survives cost   |
//|  and slippage. It is NOT the default, because an optimum sitting   |
//|  at the edge of the tested range is the classic shape of a fitted  |
//|  result, and 25% is the value the full harness was run on. Move    |
//|  it if a demo run supports it, not because the backtest liked it.  |
//|                                                                    |
//|  NOT PROVEN. One instrument, 2018 H1, NEVER FORWARD TESTED, and   |
//|  the money figure depends on scaling 2018 volatility to today.    |
//|  SUPPORTED, in the vocabulary of EXPERIMENTS.md. DEMO FIRST.      |
//+------------------------------------------------------------------+
#property copyright "JARVIS"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

#include "ProfitBox.mqh"
#include "TimeframeGuard.mqh"

#define SS_BUILD "1.00"

input group "=== SAFETY ==="
input bool   InpDemoOnly     = true;    // refuse to start on a live account
input long   InpMagic        = 990077;  // magic number
input ENUM_TIMEFRAMES InpMaxTF = PERIOD_M30;  // highest chart this will start on

input group "=== THE SETUP ==="
input int    InpPivotBars    = 5;       // swing needs this many bars either side
input double InpSweepAtr     = 0.10;    // sweep must clear the level by this x ATR
input double InpWickCut      = 0.646;   // sweep body/range must be under this
input bool   InpUseDisp      = false;   // OFF. E-139: an EA cannot execute this - see below
input double InpDispCutNote  = 0.0;     // (unused; kept so the group reads in order)
input double InpDispCut      = -1.4909; // only used if InpUseDisp is switched on
input int    InpSetupLife    = 120;     // give up on a setup after N bars

input group "=== RISK — read E-138 before changing anything here ==="
input double InpStopBufAtr   = 0.30;    // stop this far beyond the sweep extreme
input double InpMaxRiskAtr   = 1.2;     // REFUSE the setup if the stop is wider
input double InpGiveBack     = 0.25;    // give back this much of the best excursion
input int    InpMaxBars      = 240;     // time exit, M1 bars
input bool   InpUseFixedLots = true;
input double InpFixedLots    = 0.01;    // E-081: 0.01 is GBP0.787/point and is the floor
input double InpRiskPct      = 0.50;    // used only when InpUseFixedLots = false
input double InpMaxSpreadPts = 0.60;    // refuse to arm when the spread is wider

input group "=== GUARDS ==="
input double InpMaxDayLossPct = 3.0;
input double InpMaxDDPct      = 6.0;
input int    InpMaxTradesDay  = 60;     // it runs ~19/day; this is a circuit breaker
input bool   InpVerbose       = true;

input group "=== THE PROFIT BOX ==="
input bool   InpShowProfitBox = true;
input int    InpBoxCorner     = 3;      // 0 TL, 1 TR, 2 BL, 3 BR
input int    InpBoxX          = 12;
input int    InpBoxY          = 12;
input long   InpTrackMagic2   = 880041; // ZoneSniper, if you run it too
input string InpTrackLabel2   = "ZONE  st+liq";
input long   InpTrackMagic3   = 770001; // SuperTrendSniper
input string InpTrackLabel3   = "SUPERTREND";

//==================== STATE ========================================
// One live setup per side. A swing HIGH is sell-side liquidity: the sweep runs
// UP through it and the trade is SHORT back through the level.
struct Setup
{
   bool     live;
   double   lvl;        // the level price
   double   atr;        // ATR at the level's confirmation - frozen, not live
   int      born;       // bar the level was confirmed
   int      swept;      // bar the sweep happened, -1 until then
   double   ext;        // the sweep's running extreme
   double   disp;       // the sweep bar's body / range
};
Setup g_sell, g_buy;

int      g_atr = INVALID_HANDLE;
datetime g_lastBar = 0;
ulong    g_pend = 0;        // the resting limit
int      g_pendBar = 0;
int      g_pendDir = 0;
double   g_pendStop = 0.0;

double   g_peakPrice = 0.0; // best excursion of the open position
int      g_posBar = 0;
double   g_posEntry = 0.0;
int      g_posDir = 0;

double   g_dayStartEq = 0.0, g_peakEq = 0.0, g_floor = 0.0;
int      g_dayStamp = 0, g_tradesToday = 0, g_refusedToday = 0;
bool     g_lockDay = false, g_lockPerm = false;

void Log(string s) { if(InpVerbose) Print("[SS] ", s); }

double ATR()
{
   double b[];
   if(CopyBuffer(g_atr, 0, 1, 1, b) != 1) return 0.0;
   return b[0];
}

int BarNo() { return Bars(_Symbol, PERIOD_M1); }

//==================== PIVOTS =======================================
// A pivot is only KNOWN InpPivotBars bars after it forms. This checks the bar
// at that offset, so the level is real at the moment it is acted on. Reading it
// any earlier is look-ahead and it is the single easiest way to fake this
// strategy into working.
bool ConfirmedPivot(int k, bool wantHigh, double &px)
{
   int c = k + 1;                      // the candidate, k bars back from bar 1
   double v = wantHigh ? iHigh(_Symbol, PERIOD_M1, c) : iLow(_Symbol, PERIOD_M1, c);
   for(int i = 1; i <= k; i++)
   {
      if(wantHigh)
      {
         if(iHigh(_Symbol, PERIOD_M1, c - i) > v) return false;
         if(iHigh(_Symbol, PERIOD_M1, c + i) > v) return false;
      }
      else
      {
         if(iLow(_Symbol, PERIOD_M1, c - i) < v) return false;
         if(iLow(_Symbol, PERIOD_M1, c + i) < v) return false;
      }
   }
   px = v;
   return true;
}

void ResetSetup(Setup &s)
{
   s.live = false; s.lvl = 0.0; s.atr = 0.0; s.born = 0;
   s.swept = -1; s.ext = 0.0; s.disp = 1.0;
}

//==================== POSITION / ORDER HELPERS =====================
int PosCount()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == InpMagic
         && PositionGetString(POSITION_SYMBOL) == _Symbol) n++;
   }
   return n;
}

bool OrderAlive(ulong tk)
{
   if(tk == 0) return false;
   return OrderSelect(tk);
}

void KillPending(string why)
{
   if(!OrderAlive(g_pend)) { g_pend = 0; return; }
   if(trade.OrderDelete(g_pend))
      Log("cancelled resting limit: " + why);
   g_pend = 0;
   g_pendDir = 0;
}

double MinStopDist()
{
   long lv = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   return (double)lv * _Point;
}

double LotFor(double stopPts)
{
   if(InpUseFixedLots) return InpFixedLots;
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tv <= 0.0 || ts <= 0.0 || stopPts <= 0.0) return InpFixedLots;
   double risk = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0;
   double perLot = stopPts / ts * tv;
   if(perLot <= 0.0) return InpFixedLots;
   double lots = risk / perLot;
   double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double mx = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(st > 0.0) lots = MathFloor(lots / st) * st;
   if(lots < mn) lots = mn;
   if(lots > mx) lots = mx;
   return lots;
}

//==================== THE SETUP MACHINE ============================
void UpdateSetups()
{
   double a = ATR();
   if(a <= 0.0) return;
   int bar = BarNo();

   // ---- a new confirmed pivot replaces any unfilled setup on that side ----
   double px;
   if(ConfirmedPivot(InpPivotBars, true, px))
   {
      if(!g_sell.live || MathAbs(px - g_sell.lvl) > _Point)
      {
         ResetSetup(g_sell);
         g_sell.live = true; g_sell.lvl = px; g_sell.atr = a; g_sell.born = bar;
      }
   }
   if(ConfirmedPivot(InpPivotBars, false, px))
   {
      if(!g_buy.live || MathAbs(px - g_buy.lvl) > _Point)
      {
         ResetSetup(g_buy);
         g_buy.live = true; g_buy.lvl = px; g_buy.atr = a; g_buy.born = bar;
      }
   }

   double h1 = iHigh(_Symbol, PERIOD_M1, 1);
   double l1 = iLow(_Symbol, PERIOD_M1, 1);
   double o1 = iOpen(_Symbol, PERIOD_M1, 1);
   double c1 = iClose(_Symbol, PERIOD_M1, 1);
   double r1 = h1 - l1;

   // ---- the sweep ---------------------------------------------------------
   if(g_sell.live && g_sell.swept < 0 && h1 >= g_sell.lvl + InpSweepAtr * g_sell.atr)
   {
      g_sell.swept = bar;
      g_sell.ext = h1;
      g_sell.disp = (r1 > 0.0) ? MathAbs(c1 - o1) / r1 : 1.0;
   }
   if(g_buy.live && g_buy.swept < 0 && l1 <= g_buy.lvl - InpSweepAtr * g_buy.atr)
   {
      g_buy.swept = bar;
      g_buy.ext = l1;
      g_buy.disp = (r1 > 0.0) ? MathAbs(c1 - o1) / r1 : 1.0;
   }

   // ---- after a sweep the run can keep extending, and the stop goes with it
   if(g_sell.live && g_sell.swept >= 0 && bar > g_sell.swept)
      g_sell.ext = MathMax(g_sell.ext, h1);
   if(g_buy.live && g_buy.swept >= 0 && bar > g_buy.swept)
      g_buy.ext = MathMin(g_buy.ext, l1);

   // ---- a setup that never came back is not a signal ----------------------
   if(g_sell.live && bar - g_sell.born > InpSetupLife) ResetSetup(g_sell);
   if(g_buy.live  && bar - g_buy.born  > InpSetupLife) ResetSetup(g_buy);
}

// the return leg's displacement, bar 1 against bar 3 - the same pair the
// measurement used (j against j-2)
bool DispOk(int dir, double a)
{
   if(!InpUseDisp) return true;
   double gap = (dir > 0)
      ? iLow(_Symbol, PERIOD_M1, 1) - iHigh(_Symbol, PERIOD_M1, 3)
      : iLow(_Symbol, PERIOD_M1, 3) - iHigh(_Symbol, PERIOD_M1, 1);
   return (gap / a) >= InpDispCut;
}

void TryArm()
{
   if(g_lockDay || g_lockPerm) return;
   if(PosCount() > 0 || OrderAlive(g_pend)) return;
   if(g_tradesToday >= InpMaxTradesDay) return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(ask - bid > InpMaxSpreadPts) return;

   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   int bar = BarNo();

   for(int pass = 0; pass < 2; pass++)
   {
      bool sellSide = (pass == 0);
      Setup s = sellSide ? g_sell : g_buy;
      if(!s.live || s.swept < 0 || bar <= s.swept) continue;
      if(s.disp > InpWickCut) continue;              // THE FAKEOUT FILTER

      int dir = sellSide ? -1 : 1;
      if(!DispOk(dir, s.atr)) continue;

      double lvl  = NormalizeDouble(s.lvl, dg);
      double stop = NormalizeDouble(s.ext - dir * InpStopBufAtr * s.atr, dg);
      double risk = MathAbs(lvl - stop);

      // ---- THE RISK CAP, and it is a REFUSAL, not a resize -------------
      // 0.01 lots is the floor (E-081), so a stop too wide to afford cannot
      // be sized down. E-138: uncapped, one trade took 57% of a GBP60
      // account. This is the line between an edge that compounds and an
      // account that does not survive to see it.
      if(risk > InpMaxRiskAtr * s.atr)
      {
         g_refusedToday++;
         Log(StringFormat("REFUSED %s: stop %.*f is %.2f ATR, cap is %.2f",
                          sellSide ? "SELL" : "BUY", dg, risk,
                          risk / s.atr, InpMaxRiskAtr));
         if(sellSide) ResetSetup(g_sell); else ResetSetup(g_buy);
         continue;
      }

      double md = MinStopDist();
      if(md > 0.0 && risk < md) continue;

      double lots = LotFor(risk);
      if(lots <= 0.0) continue;

      // NO TAKE PROFIT. E-137 measured every fixed target and all of them
      // banked less than the give-back trail.
      bool ok = sellSide
         ? trade.SellLimit(lots, lvl, _Symbol, stop, 0.0, ORDER_TIME_GTC, 0, "SS sweep")
         : trade.BuyLimit(lots, lvl, _Symbol, stop, 0.0, ORDER_TIME_GTC, 0, "SS sweep");
      if(ok)
      {
         g_pend = trade.ResultOrder();
         g_pendBar = bar;
         g_pendDir = dir;
         g_pendStop = stop;
         PB_NoteOrder(g_pend, (bid + ask) / 2.0);
         Log(StringFormat("armed %s limit at %.*f, stop %.*f (%.2f ATR), %.2f lots",
                          sellSide ? "SELL" : "BUY", dg, lvl, dg, stop,
                          risk / s.atr, lots));
         if(sellSide) ResetSetup(g_sell); else ResetSetup(g_buy);
         return;
      }
      Log(StringFormat("arm failed: %d %s", trade.ResultRetcode(),
                       trade.ResultRetcodeDescription()));
   }
}

void AgePending()
{
   if(!OrderAlive(g_pend)) { g_pend = 0; return; }
   if(BarNo() - g_pendBar > InpSetupLife) KillPending("unfilled and stale");
}

//==================== THE GIVE-BACK TRAIL ==========================
// The stop ratchets to entry + (1 - giveBack) x the best excursion. It only
// ever moves toward profit - a stop that can move backwards is not a stop.
void TrailStop()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

      int    dir   = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl    = PositionGetDouble(POSITION_SL);
      double px    = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                               : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      if(g_posDir == 0 || MathAbs(entry - g_posEntry) > _Point)
      {
         g_posDir = dir; g_posEntry = entry; g_peakPrice = entry;
         g_posBar = BarNo();
      }
      g_peakPrice = (dir > 0) ? MathMax(g_peakPrice, px) : MathMin(g_peakPrice, px);

      double runUp = dir * (g_peakPrice - entry);
      if(runUp > 0.0)
      {
         int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
         double cand = NormalizeDouble(entry + dir * runUp * (1.0 - InpGiveBack), dg);
         bool better = (dir > 0) ? (cand > sl) : (cand < sl);
         double md = MinStopDist();
         bool room = (md <= 0.0) || (MathAbs(px - cand) >= md);
         if(better && room)
            trade.PositionModify(tk, cand, 0.0);
      }

      if(BarNo() - g_posBar >= InpMaxBars)
      {
         trade.PositionClose(tk);
         Log("time exit");
      }
   }
}

//==================== GUARDS =======================================
int DayStamp()
{
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   return t.year * 10000 + t.mon * 100 + t.day;
}

void CheckGuards()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_peakEq) g_peakEq = eq;
   if(!g_lockDay && g_dayStartEq > 0.0
      && eq <= g_dayStartEq * (1.0 - InpMaxDayLossPct / 100.0))
   {
      g_lockDay = true;
      KillPending("daily loss limit");
      Log("DAILY LOSS LIMIT - no new trades today");
   }
   if(!g_lockPerm && g_floor > 0.0 && eq <= g_floor)
   {
      g_lockPerm = true;
      KillPending("max drawdown");
      Log("MAX DRAWDOWN - stopped");
   }
}

//==================== LIFECYCLE ====================================
int OnInit()
{
   if(!TfGuard("SS", InpMaxTF)) return INIT_FAILED;
   if(InpDemoOnly && AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      Print("[SS] REFUSING TO START: InpDemoOnly is true and this is not a demo "
            "account. This has NEVER been forward tested. Set InpDemoOnly=false "
            "deliberately, and only after a demo run that measured your real "
            "stop-fill slippage.");
      return INIT_FAILED;
   }
   g_atr = iATR(_Symbol, PERIOD_M1, 14);
   if(g_atr == INVALID_HANDLE) { Print("[SS] ATR handle failed"); return INIT_FAILED; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(20);

   ResetSetup(g_sell);
   ResetSetup(g_buy);

   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dayStartEq = eq; g_peakEq = eq;
   g_floor = eq * (1.0 - InpMaxDDPct / 100.0);
   g_dayStamp = DayStamp();

   int corner = InpBoxCorner == 0 ? CORNER_LEFT_UPPER  :
                InpBoxCorner == 1 ? CORNER_RIGHT_UPPER :
                InpBoxCorner == 2 ? CORNER_LEFT_LOWER  : CORNER_RIGHT_LOWER;
   PB_Init("SS.", "SWEEP SNIPER " + SS_BUILD, InpMagic, InpShowProfitBox,
           corner, InpBoxX, InpBoxY, "SWEEP  liq");
   if(InpTrackMagic2 != 0) PB_AddStrategy(InpTrackMagic2, InpTrackLabel2);
   if(InpTrackMagic3 != 0) PB_AddStrategy(InpTrackMagic3, InpTrackLabel3);

   PrintFormat("[SS] === SWEEP SNIPER %s === pivot %d, sweep %.2f ATR, wick <= %.3f, "
               "stop %.2f ATR past the extreme, RISK CAP %.2f ATR, give back %.0f%%",
               SS_BUILD, InpPivotBars, InpSweepAtr, InpWickCut, InpStopBufAtr,
               InpMaxRiskAtr, InpGiveBack * 100.0);
   Print("[SS] Measured (variant B, the one that runs): 2579 trades, 23.6/day, "
         "65.1% win, +309.5 points, 107.3 control se, OOS +0.0991 vs IS +0.1241, "
         "walk-forward 5 of 5, max drawdown GBP12.68, worst trade -GBP4.63.");
   Print("[SS] THE RISK CAP IS NOT AN OPTIMISATION. Uncapped, the worst single "
         "trade was 57% of a GBP60 account and the max drawdown 63%. Read E-138 "
         "before raising InpMaxRiskAtr.");
   if(InpUseDisp)
      Print("[SS] WARNING: InpUseDisp is ON. That filter is evaluated at the FILL "
            "bar and this EA rests a LIMIT, so it will be applied at the ARM bar "
            "instead - a different signal from the one measured. E-139.");
   Print("[SS] 2018 H1 only. NEVER FORWARD TESTED. Demo first, and watch the "
         "'fill vs signal' row - it is how you see your limits filling late.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_atr != INVALID_HANDLE) IndicatorRelease(g_atr);
   PB_Destroy();
}

void OnTick()
{
   int ds = DayStamp();
   if(ds != g_dayStamp)
   {
      g_dayStamp = ds;
      g_dayStartEq = AccountInfoDouble(ACCOUNT_EQUITY);
      g_tradesToday = 0;
      g_refusedToday = 0;
      g_lockDay = false;
      Log("new trading day");
   }

   CheckGuards();

   datetime b = iTime(_Symbol, PERIOD_M1, 0);
   if(b != g_lastBar)
   {
      g_lastBar = b;
      UpdateSetups();
      AgePending();
      if(PosCount() == 0) TryArm();
   }

   TrailStop();
   PB_Draw();
}

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &req, const MqlTradeResult &res)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagic) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;

   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entry == DEAL_ENTRY_IN)
   {
      g_tradesToday++;
      g_pend = 0;
      g_posDir = 0;                       // TrailStop re-seeds from the position
      PB_PromoteOrder((ulong)HistoryDealGetInteger(trans.deal, DEAL_ORDER),
                      (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID),
                      HistoryDealGetDouble(trans.deal, DEAL_PRICE));
      Log("FILLED");
      return;
   }
   if(entry == DEAL_ENTRY_OUT)
   {
      g_posDir = 0;
      g_peakPrice = 0.0;
      g_pbDirty = true;
      Log(StringFormat("closed, profit %.2f",
                       HistoryDealGetDouble(trans.deal, DEAL_PROFIT)));
   }
}

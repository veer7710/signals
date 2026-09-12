//+------------------------------------------------------------------+
//|                                            LiquidityEngine.mq5   |
//|  Liquidity / SMC engine for XAUUSD (and any other symbol).       |
//|                                                                  |
//|  TWO RULES DECIDE WHETHER A "SWEEP" MEANS ANYTHING AT ALL:       |
//|                                                                  |
//|   1. CONSUME THE POOL WHEN IT IS RUN. Without this, "a level was |
//|      run" stays true on every later bar that wicks near it, and  |
//|      most fires land mid-move. One event per level, never one    |
//|      per bar that touches it.                                    |
//|   2. ONLY THE NEAREST FEW POOLS ARE ELIGIBLE. Scan forty levels  |
//|      and "a level was run" is true on most bars, which is the    |
//|      same as having no signal.                                   |
//|                                                                  |
//|  A RUN = price pierces the pool by InpPierceATR and CLOSES BACK  |
//|  INSIDE. A close BEYOND is a BREAK -- a different event, not     |
//|  this one, and it is not traded here.                            |
//|                                                                  |
//|  DIRECTION -- READ THIS BEFORE CHANGING IT:                      |
//|  Textbook ICT says a swept low is a LONG (reversal). Measured on |
//|  GOLD 15m and 1h with the stop placed correctly beyond the wick, |
//|  that reading LOST on both timeframes (lift 0.87-1.02, negative  |
//|  $/trade). The CONTINUATION reading -- swept low, go SHORT --    |
//|  was the mildly positive one (lift 1.04-1.11) on both. Neither   |
//|  clears a best-of-N null, so treat the edge as unproven either   |
//|  way; the default is simply the side that measured better.       |
//|                                                                  |
//|  NOT CLAIMED: profitability. The exit, not the entry, is the     |
//|  part with a statistically significant result behind it.         |
//+------------------------------------------------------------------+
#property copyright "Signals research build"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade Trade;

input group             "=== POOLS ==="
input int    InpPivotLeft   = 3;      // bars left of a swing
input int    InpPivotRight  = 3;      // bars right (a pivot confirms this late)
input int    InpMaxPools    = 3;      // nearest-N eligible. Raising this kills the signal.
input double InpEqTolATR    = 0.10;   // equal highs/lows merged within this
input double InpPierceATR   = 0.05;   // how far past the pool counts as a run

input group             "=== DIRECTION ==="
enum SweepMode { SWEEP_CONTINUATION, SWEEP_REVERSAL };
input SweepMode InpMode     = SWEEP_CONTINUATION; // measured better of the two
input bool   InpUseHtfBias  = false;  // only take trades agreeing with HTF EMA slope
input ENUM_TIMEFRAMES InpHtf = PERIOD_H1;
input int    InpHtfEma      = 50;

input group             "=== STOP ==="
input double InpStopBufATR  = 0.25;   // beyond the swept wick
input double InpMaxStopATR  = 4.0;    // skip if wider (risk cap)

input group             "=== EXIT ==="
input double InpTrailAtr    = 3.0;    // measured best on both timeframes
input double InpArmAtR      = 1.0;    // arm the trail only at this R
input double InpHardTpR     = 0.0;    // 0 = none; let the trail run
input int    InpMaxBars     = 150;

input group             "=== RISK ==="
input bool   InpUseRiskPct  = true;
input double InpRiskPct     = 0.50;
input double InpFixedLot    = 0.01;
input int    InpMaxOpen     = 1;

input group             "=== FUNDED GUARDS ==="
input bool   InpUseGuards   = true;
input double InpDailyLossPct= 3.0;
input double InpMaxDDPct    = 6.0;
input bool   InpCloseOnGuard= true;

input group             "=== GENERAL ==="
input long   InpMagic       = 770022;
input int    InpSlippage    = 20;
input bool   InpShowPanel   = true;
input bool   InpJournal     = true;

//--- pools ---------------------------------------------------------
struct Pool { double level; datetime born; int hits; bool used; };
Pool poolHi[]; Pool poolLo[];

int      hAtr = INVALID_HANDLE, hHtf = INVALID_HANDLE;
datetime lastBar = 0;
double   gEntry=0, gStopDist=0, gPeakFav=0, gArmed=0;
int      gDir=0;
double   gDayStart=0, gPeakEquity=0;
datetime gDayStamp=0;
bool     gHalted=false; string gHaltWhy="";
int      nTrades=0, nWins=0, nSkipWide=0, nSkipSize=0, nSweeps=0, nCapture=0;
double   sumR=0, sumPts=0, sumCapture=0;

string GuardFile() { return "LQE_" + _Symbol + "_" + (string)InpMagic + ".guard"; }

int OnInit()
{
   hAtr = iATR(_Symbol, _Period, 14);
   if(hAtr == INVALID_HANDLE) return INIT_FAILED;
   if(InpUseHtfBias)
   {
      hHtf = iMA(_Symbol, InpHtf, InpHtfEma, 0, MODE_EMA, PRICE_CLOSE);
      if(hHtf == INVALID_HANDLE) return INIT_FAILED;
   }
   Trade.SetExpertMagicNumber(InpMagic);
   Trade.SetDeviationInPoints(InpSlippage);
   Trade.SetTypeFillingBySymbol(_Symbol);
   ArrayResize(poolHi, 0); ArrayResize(poolLo, 0);
   LoadGuards();
   EventSetTimer(5);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int r)
{
   EventKillTimer(); SaveGuards();
   ObjectsDeleteAll(0, "LQE_");
   if(hAtr != INVALID_HANDLE) IndicatorRelease(hAtr);
   if(hHtf != INVALID_HANDLE) IndicatorRelease(hHtf);
}
void OnTimer(){ SaveGuards(); if(InpShowPanel) DrawPanel(); }

//--- guards (identical contract to the other two EAs) ---------------
datetime Today(){ MqlDateTime t; TimeToStruct(TimeCurrent(),t); t.hour=0;t.min=0;t.sec=0; return StructToTime(t); }
void LoadGuards()
{
   gPeakEquity = AccountInfoDouble(ACCOUNT_EQUITY); gDayStart = gPeakEquity; gDayStamp = Today();
   int h = FileOpen(GuardFile(), FILE_READ|FILE_TXT|FILE_COMMON);
   if(h != INVALID_HANDLE)
   {
      gDayStamp   = (datetime)StringToInteger(FileReadString(h));
      gDayStart   = StringToDouble(FileReadString(h));
      gPeakEquity = StringToDouble(FileReadString(h));
      gHalted     = (StringToInteger(FileReadString(h)) == 1);
      gHaltWhy    = FileReadString(h);
      FileClose(h);
   }
   if(gDayStamp != Today()) NewDay();
   if(gPeakEquity <= 0) gPeakEquity = AccountInfoDouble(ACCOUNT_EQUITY);
}
void SaveGuards()
{
   int h = FileOpen(GuardFile(), FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(h == INVALID_HANDLE) return;
   FileWrite(h,(string)(long)gDayStamp); FileWrite(h,DoubleToString(gDayStart,2));
   FileWrite(h,DoubleToString(gPeakEquity,2)); FileWrite(h,gHalted?"1":"0");
   FileWrite(h,gHaltWhy); FileClose(h);
}
void NewDay()
{
   gDayStamp = Today(); gDayStart = AccountInfoDouble(ACCOUNT_EQUITY);
   if(gHaltWhy == "daily") { gHalted=false; gHaltWhy=""; }
   SaveGuards();
}
bool GuardsBlock()
{
   if(!InpUseGuards) return false;
   if(gDayStamp != Today()) NewDay();
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > gPeakEquity) gPeakEquity = eq;
   if(gDayStart>0 && (gDayStart-eq)/gDayStart*100.0 >= InpDailyLossPct){ gHalted=true; gHaltWhy="daily"; }
   if(gPeakEquity>0 && (gPeakEquity-eq)/gPeakEquity*100.0 >= InpMaxDDPct){ gHalted=true; gHaltWhy="maxdd"; }
   if(gHalted && InpCloseOnGuard) CloseAll("guard:"+gHaltWhy);
   return gHalted;
}

double AtrNow(){ double a[]; ArraySetAsSeries(a,true); if(CopyBuffer(hAtr,0,1,2,a)<2) return 0; return a[0]; }

//+------------------------------------------------------------------+
//| Pool bookkeeping                                                  |
//+------------------------------------------------------------------+
void AddPool(bool isHigh, double level, datetime when, double tol)
{
   if(isHigh)
   {
      for(int i = 0; i < ArraySize(poolHi); i++)
         if(!poolHi[i].used && MathAbs(poolHi[i].level - level) <= tol)
         { poolHi[i].level = MathMax(poolHi[i].level, level); poolHi[i].hits++; return; }
      int n = ArraySize(poolHi); ArrayResize(poolHi, n+1);
      poolHi[n].level = level; poolHi[n].born = when; poolHi[n].hits = 1; poolHi[n].used = false;
   }
   else
   {
      for(int i = 0; i < ArraySize(poolLo); i++)
         if(!poolLo[i].used && MathAbs(poolLo[i].level - level) <= tol)
         { poolLo[i].level = MathMin(poolLo[i].level, level); poolLo[i].hits++; return; }
      int n = ArraySize(poolLo); ArrayResize(poolLo, n+1);
      poolLo[n].level = level; poolLo[n].born = when; poolLo[n].hits = 1; poolLo[n].used = false;
   }
}

//--- was bar `sh` a confirmed fractal pivot?
bool IsPivotHigh(int sh)
{
   double v = iHigh(_Symbol,_Period,sh);
   for(int k = 1; k <= InpPivotLeft;  k++) if(iHigh(_Symbol,_Period,sh+k) >= v) return false;
   for(int k = 1; k <= InpPivotRight; k++) if(iHigh(_Symbol,_Period,sh-k) >= v) return false;
   return true;
}
bool IsPivotLow(int sh)
{
   double v = iLow(_Symbol,_Period,sh);
   for(int k = 1; k <= InpPivotLeft;  k++) if(iLow(_Symbol,_Period,sh+k) <= v) return false;
   for(int k = 1; k <= InpPivotRight; k++) if(iLow(_Symbol,_Period,sh-k) <= v) return false;
   return true;
}

//--- RULE 2: eligibility, not deletion.
//    A pool outside the nearest-N is IGNORED this bar, not destroyed --
//    price moves and it can become eligible again. Deleting it would make
//    the EA and the Pine fire on different bars.
//    Only the retention buffer is capped, oldest dropped first.
#define POOL_BUF 24

void CapBuffer()
{
   int n = ArraySize(poolHi);
   if(n > POOL_BUF)
   {
      int drop = n - POOL_BUF;
      for(int i = 0; i + drop < n; i++) poolHi[i] = poolHi[i+drop];
      ArrayResize(poolHi, POOL_BUF);
   }
   n = ArraySize(poolLo);
   if(n > POOL_BUF)
   {
      int drop = n - POOL_BUF;
      for(int i = 0; i + drop < n; i++) poolLo[i] = poolLo[i+drop];
      ArrayResize(poolLo, POOL_BUF);
   }
}

//--- distance of the InpMaxPools-th nearest live pool. Anything further
//--- than this is not eligible on this bar. Returns 0 if none.
double LowCut(double px)
{
   double d[]; ArrayResize(d, 0);
   for(int i = 0; i < ArraySize(poolLo); i++)
   {
      if(poolLo[i].used) continue;
      double dd = px - poolLo[i].level;
      if(dd <= 0) continue;
      int n = ArraySize(d); ArrayResize(d, n+1); d[n] = dd;
   }
   if(ArraySize(d) == 0) return 0.0;
   ArraySort(d);
   int idx = MathMin(InpMaxPools - 1, ArraySize(d) - 1);
   return d[idx];
}

double HighCut(double px)
{
   double d[]; ArrayResize(d, 0);
   for(int i = 0; i < ArraySize(poolHi); i++)
   {
      if(poolHi[i].used) continue;
      double dd = poolHi[i].level - px;
      if(dd <= 0) continue;
      int n = ArraySize(d); ArrayResize(d, n+1); d[n] = dd;
   }
   if(ArraySize(d) == 0) return 0.0;
   ArraySort(d);
   int idx = MathMin(InpMaxPools - 1, ArraySize(d) - 1);
   return d[idx];
}

int LiveCount(bool high)
{
   int n = 0;
   if(high) { for(int i=0;i<ArraySize(poolHi);i++) if(!poolHi[i].used) n++; }
   else     { for(int i=0;i<ArraySize(poolLo);i++) if(!poolLo[i].used) n++; }
   return n;
}

int HtfBias()
{
   if(!InpUseHtfBias) return 0;
   double m[]; ArraySetAsSeries(m,true);
   if(CopyBuffer(hHtf,0,1,3,m) < 3) return 0;
   return (m[0] > m[2]) ? 1 : ((m[0] < m[2]) ? -1 : 0);
}

//+------------------------------------------------------------------+
void OnTick()
{
   ManageOpen();
   datetime bt = iTime(_Symbol,_Period,0);
   if(bt == lastBar) return;
   lastBar = bt;

   double a = AtrNow();
   if(a <= 0) return;
   double tol = InpEqTolATR * a;

   // a pivot at shift InpPivotRight+1 has just become confirmed
   int sh = InpPivotRight + 1;
   if(Bars(_Symbol,_Period) > sh + InpPivotLeft + 2)
   {
      if(IsPivotHigh(sh)) AddPool(true,  iHigh(_Symbol,_Period,sh), iTime(_Symbol,_Period,sh), tol);
      if(IsPivotLow(sh))  AddPool(false, iLow(_Symbol,_Period,sh),  iTime(_Symbol,_Period,sh), tol);
   }
   CapBuffer();

   if(GuardsBlock()) return;
   if(CountOpen() >= InpMaxOpen) return;

   double hi1 = iHigh(_Symbol,_Period,1), lo1 = iLow(_Symbol,_Period,1), c1 = iClose(_Symbol,_Period,1);
   double pierce = InpPierceATR * a;
   int    swept = 0; double wick = 0;

   double loCut = LowCut(c1), hiCut = HighCut(c1);
   for(int i = 0; i < ArraySize(poolLo) && loCut > 0; i++)
   {
      if(poolLo[i].used) continue;
      double dd = c1 - poolLo[i].level;
      if(dd <= 0 || dd > loCut) continue;                  // RULE 2: eligibility
      if(lo1 <= poolLo[i].level - pierce && c1 > poolLo[i].level)
      { poolLo[i].used = true; swept = 1; wick = lo1; nSweeps++; break; }   // RULE 1: consume
   }
   if(swept == 0)
      for(int i = 0; i < ArraySize(poolHi) && hiCut > 0; i++)
      {
         if(poolHi[i].used) continue;
         double dd = poolHi[i].level - c1;
         if(dd <= 0 || dd > hiCut) continue;
         if(hi1 >= poolHi[i].level + pierce && c1 < poolHi[i].level)
         { poolHi[i].used = true; swept = -1; wick = hi1; nSweeps++; break; }
      }
   if(swept == 0) return;

   // swept==+1 means a LOW was run. Reversal reads that long; continuation short.
   int dir = (InpMode == SWEEP_REVERSAL) ? swept : -swept;
   int bias = HtfBias();
   if(InpUseHtfBias && bias != 0 && dir != bias) return;

   TryEnter(dir, wick, a);
}

double MoneyPerPricePerLot()
{
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   return (ts > 0) ? tv/ts : 0.0;
}
double SizeFor(double stopDist)
{
   double minL=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxL=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double stp =SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(!InpUseRiskPct) return MathMax(minL, MathMin(maxL, InpFixedLot));
   double mpp = MoneyPerPricePerLot();
   if(mpp <= 0 || stopDist <= 0) return 0.0;
   double lots = (AccountInfoDouble(ACCOUNT_BALANCE)*InpRiskPct/100.0)/(stopDist*mpp);
   lots = MathFloor(lots/stp)*stp;
   if(lots < minL) return 0.0;              // never round UP
   return MathMin(lots, maxL);
}

void TryEnter(int dir, double wick, double a)
{
   double px = (dir>0)?SymbolInfoDouble(_Symbol,SYMBOL_ASK):SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double sd;
   if(dir > 0) sd = MathAbs(px - MathMin(wick, px)) + InpStopBufATR*a;
   else        sd = MathAbs(MathMax(wick, px) - px) + InpStopBufATR*a;
   if(sd <= 0) sd = InpStopBufATR*a;
   if(sd > InpMaxStopATR*a) { nSkipWide++; return; }

   double lots = SizeFor(sd);
   if(lots <= 0) { nSkipSize++; return; }

   int dg = (int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double sl = NormalizeDouble((dir>0)?px-sd:px+sd, dg);
   double tp = 0.0;
   if(InpHardTpR > 0) tp = NormalizeDouble((dir>0)?px+InpHardTpR*sd:px-InpHardTpR*sd, dg);

   bool ok = (dir>0) ? Trade.Buy(lots,_Symbol,0.0,sl,tp,"LQE")
                     : Trade.Sell(lots,_Symbol,0.0,sl,tp,"LQE");
   if(!ok){ Print("order failed ",Trade.ResultRetcode()," ",Trade.ResultRetcodeDescription()); return; }
   gDir=dir; gEntry=(Trade.ResultPrice()>0?Trade.ResultPrice():px);
   gStopDist=sd; gPeakFav=0; gArmed=0; nTrades++;
   if(InpJournal) PrintFormat("SWEEP %s entry=%.2f stopDist=%.2f (%.2fATR) mode=%s",
      dir>0?"BUY":"SELL", gEntry, sd, sd/a,
      InpMode==SWEEP_REVERSAL?"reversal":"continuation");
}

void ManageOpen()
{
   if(!PositionSelect(_Symbol)) { if(gDir != 0) FinishTrade(); return; }
   if(PositionGetInteger(POSITION_MAGIC) != InpMagic) return;
   int dir = (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY)?1:-1;
   double ent = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl  = PositionGetDouble(POSITION_SL);
   double cur = (dir>0)?SymbolInfoDouble(_Symbol,SYMBOL_BID):SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   if(gStopDist <= 0) gStopDist = MathAbs(ent - sl);
   if(gStopDist <= 0) return;
   gDir=dir; gEntry=ent;
   double fav = (cur-ent)*dir;
   if(fav > gPeakFav) gPeakFav = fav;
   if(gPeakFav < InpArmAtR*gStopDist) return;          // the arming rule
   gArmed = 1.0;
   double a = AtrNow();
   double cand = (dir>0)?cur-InpTrailAtr*a:cur+InpTrailAtr*a;
   int dg=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   cand = NormalizeDouble(cand,dg);
   bool better = (dir>0)?(cand>sl):(cand<sl);
   double lvl = (double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   bool legal = (dir>0)?(cur-cand>lvl):(cand-cur>lvl);
   if(better && legal) Trade.PositionModify(_Symbol,cand,PositionGetDouble(POSITION_TP));
}

void FinishTrade()
{
   if(!HistorySelect(TimeCurrent()-86400,TimeCurrent()+60)) { gDir=0; return; }
   double pts=0; bool found=false;
   for(int i=HistoryDealsTotal()-1;i>=0&&!found;i--)
   {
      ulong t=HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(t,DEAL_MAGIC)!=InpMagic) continue;
      if(HistoryDealGetInteger(t,DEAL_ENTRY)!=DEAL_ENTRY_OUT) continue;
      pts=(HistoryDealGetDouble(t,DEAL_PRICE)-gEntry)*gDir; found=true;
   }
   if(found && gStopDist>0)
   {
      double eR=pts/gStopDist, pR=gPeakFav/gStopDist;
      sumR+=eR; sumPts+=pts; if(pts>0) nWins++;
      if(pR>=0.5){ sumCapture+=eR/pR; nCapture++; }
      if(InpJournal) PrintFormat("EXIT peakR=%.2f exitR=%.2f capture=%.2f",pR,eR,pR>0?eR/pR:0);
   }
   gDir=0; gPeakFav=0; gStopDist=0; gArmed=0;
}

int CountOpen()
{
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong t=PositionGetTicket(i); if(t==0) continue;
      if(PositionGetInteger(POSITION_MAGIC)==InpMagic && PositionGetString(POSITION_SYMBOL)==_Symbol) n++;
   }
   return n;
}
void CloseAll(string why)
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong t=PositionGetTicket(i); if(t==0) continue;
      if(PositionGetInteger(POSITION_MAGIC)==InpMagic && PositionGetString(POSITION_SYMBOL)==_Symbol)
         Trade.PositionClose(t);
   }
}
string SessionNow()
{
   MqlDateTime t; TimeToStruct(TimeGMT(),t); int h=t.hour;
   if(h>=23||h<7) return "Asia";
   if(h<12) return "London";
   if(h<16) return "London/NY overlap";
   if(h<21) return "New York";
   return "Off-session";
}
void DrawPanel()
{
   string n="LQE_panel";
   double cap=(nCapture>0)?sumCapture/nCapture:0.0;
   string s=StringFormat(
      "Liquidity Engine   %s %s   mode=%s\n"
      "session: %s (GMT %s)\n"
      "pools live: %d high / %d low   sweeps seen %d\n"
      "trades %d   win %.0f%%   sumR %+.2f   pts %+.1f\n"
      "CAPTURE RATIO %.2f (n=%d)\n"
      "skipped: wide %d | size %d\n"
      "guards: %s   day %+.2f%%   dd %+.2f%%",
      _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
      InpMode==SWEEP_REVERSAL?"reversal":"continuation",
      SessionNow(), TimeToString(TimeGMT(),TIME_MINUTES),
      LiveCount(true), LiveCount(false), nSweeps,
      nTrades, nTrades>0?100.0*nWins/nTrades:0.0, sumR, sumPts, cap, nCapture,
      nSkipWide, nSkipSize,
      gHalted?("HALTED "+gHaltWhy):"ok",
      gDayStart>0?(AccountInfoDouble(ACCOUNT_EQUITY)-gDayStart)/gDayStart*100.0:0.0,
      gPeakEquity>0?(AccountInfoDouble(ACCOUNT_EQUITY)-gPeakEquity)/gPeakEquity*100.0:0.0);
   if(ObjectFind(0,n)<0)
   {
      ObjectCreate(0,n,OBJ_LABEL,0,0,0);
      ObjectSetInteger(0,n,OBJPROP_CORNER,CORNER_LEFT_UPPER);
      ObjectSetInteger(0,n,OBJPROP_XDISTANCE,12);
      ObjectSetInteger(0,n,OBJPROP_YDISTANCE,20);
      ObjectSetInteger(0,n,OBJPROP_FONTSIZE,9);
      ObjectSetString(0,n,OBJPROP_FONT,"Consolas");
      ObjectSetInteger(0,n,OBJPROP_SELECTABLE,false);
   }
   ObjectSetInteger(0,n,OBJPROP_COLOR, gHalted?clrTomato:clrGainsboro);
   ObjectSetString(0,n,OBJPROP_TEXT,s);
   ChartRedraw(0);
}
//+------------------------------------------------------------------+

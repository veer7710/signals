//+------------------------------------------------------------------+
//|                                        SessionRangeEngine.mq5    |
//|  Session opening-range break. XAUUSD / NAS100 / anything.        |
//|                                                                  |
//|  WHY THIS ONE EXISTS                                             |
//|  Of everything measured in this repo, exactly one effect         |
//|  replicated on independent data: hour-of-day volatility.         |
//|  On GOLD 15m the 13:00 UTC hour runs 1.82x the median hourly     |
//|  range and 14:00 runs 1.68x, while 20:00 runs 0.58x. That was    |
//|  also the finding (E-190) in the earlier research, measured on   |
//|  different data years apart. It predicts SIZE, never DIRECTION.  |
//|                                                                  |
//|  That matters here and NOT in the other two EAs, and the reason  |
//|  is worth understanding: an ATR-scaled stop already absorbs a    |
//|  volatility change, so gating those by hour adds nothing         |
//|  (measured: +2.68 all hours vs +2.50 high-vol only). A breakout  |
//|  of a FIXED range does not absorb it -- spread is fixed in       |
//|  dollars, so a 1.8x bigger move is worth roughly 1.8x more per   |
//|  dollar of spread paid. That is the whole thesis of this EA.     |
//|                                                                  |
//|  Of the entry families tested this had the highest raw $/trade   |
//|  (+$2.91 on GOLD 1h de-trended) -- but t=0.97, so it is NOT a    |
//|  significant result. Treat it as the best of several unproven    |
//|  options, not as an edge.                                        |
//|                                                                  |
//|  Symbol-agnostic: every size is in ATR or account %, nothing is  |
//|  in gold dollars, so it can be put on an index without edits.    |
//+------------------------------------------------------------------+
#property copyright "Signals research build"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade Trade;

input group             "=== SESSION ==="
input int    InpSessionHour = 13;    // GMT hour the range breaks from (13 = measured 1.82x)
input int    InpRangeBars   = 16;    // bars BEFORE that hour that build the range
input int    InpWindowBars  = 12;    // bars after it in which a break is accepted
input bool   InpAlsoSecond  = false; // also allow a second session
input int    InpSecondHour  = 7;     // London open

input group             "=== RANGE QUALITY ==="
input double InpMinRangeATR = 0.8;   // too tight = the break is noise
input double InpMaxRangeATR = 6.0;   // too wide  = the stop is unaffordable
input bool   InpCloseBeyond = true;  // require a CLOSE outside, not just a wick

input group             "=== STOP / EXIT ==="
enum StopKind { STOP_OPPOSITE_SIDE, STOP_ATR };
input StopKind InpStopKind  = STOP_OPPOSITE_SIDE;
input double InpStopAtrMult = 1.5;   // used when StopKind = STOP_ATR
input double InpMaxStopATR  = 4.0;
input double InpTrailAtr    = 3.0;   // validated best on both timeframes
input double InpArmAtR      = 1.0;   // arm the trail only at this R
input double InpHardTpR     = 0.0;
input int    InpMaxBars     = 150;

input group             "=== RISK ==="
input bool   InpUseRiskPct  = true;
input double InpRiskPct     = 0.25;    // Monte-Carlo optimum for a funded challenge; see FINDINGS 10
input double InpFixedLot    = 0.01;
input int    InpTradesPerDay= 1;

input group             "=== FUNDED GUARDS ==="
input bool   InpUseGuards   = true;
input double InpDailyLossPct= 3.0;
input double InpMaxDDPct    = 6.0;
input bool   InpCloseOnGuard= true;

input group             "=== GENERAL ==="
input long   InpMagic       = 770023;
input int    InpSlippage    = 20;
input bool   InpShowPanel   = true;
input bool   InpDrawRange   = true;
input bool   InpJournal     = true;

int      hAtr = INVALID_HANDLE;
datetime lastBar = 0;
double   rHi = 0, rLo = 0;
bool     rReady = false;
int      rBarsLeft = 0;
datetime rDay = 0;
int      nTakenToday = 0;
double   gEntry=0, gStopDist=0, gPeakFav=0, gArmed=0;
int      gDir=0;
double   gDayStart=0, gPeakEquity=0;
datetime gDayStamp=0;
bool     gHalted=false; string gHaltWhy="";
int      nTrades=0, nWins=0, nSkipWide=0, nSkipSize=0, nSkipRange=0, nCapture=0;
double   sumR=0, sumPts=0, sumCapture=0;

string GuardFile(){ return "SRE_"+_Symbol+"_"+(string)InpMagic+".guard"; }

int OnInit()
{
   hAtr = iATR(_Symbol,_Period,14);
   if(hAtr == INVALID_HANDLE) return INIT_FAILED;
   Trade.SetExpertMagicNumber(InpMagic);
   Trade.SetDeviationInPoints(InpSlippage);
   Trade.SetTypeFillingBySymbol(_Symbol);
   LoadGuards(); EventSetTimer(5);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int r)
{
   EventKillTimer(); SaveGuards();
   ObjectsDeleteAll(0,"SRE_");
   if(hAtr != INVALID_HANDLE) IndicatorRelease(hAtr);
}
void OnTimer(){ SaveGuards(); if(InpShowPanel) DrawPanel(); }

datetime Today(){ MqlDateTime t; TimeToStruct(TimeCurrent(),t); t.hour=0;t.min=0;t.sec=0; return StructToTime(t); }
void LoadGuards()
{
   gPeakEquity=AccountInfoDouble(ACCOUNT_EQUITY); gDayStart=gPeakEquity; gDayStamp=Today();
   int h=FileOpen(GuardFile(),FILE_READ|FILE_TXT|FILE_COMMON);
   if(h!=INVALID_HANDLE)
   {
      gDayStamp=(datetime)StringToInteger(FileReadString(h));
      gDayStart=StringToDouble(FileReadString(h));
      gPeakEquity=StringToDouble(FileReadString(h));
      gHalted=(StringToInteger(FileReadString(h))==1);
      gHaltWhy=FileReadString(h);
      FileClose(h);
   }
   if(gDayStamp!=Today()) NewDay();
   if(gPeakEquity<=0) gPeakEquity=AccountInfoDouble(ACCOUNT_EQUITY);
}
void SaveGuards()
{
   int h=FileOpen(GuardFile(),FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(h==INVALID_HANDLE) return;
   FileWrite(h,(string)(long)gDayStamp); FileWrite(h,DoubleToString(gDayStart,2));
   FileWrite(h,DoubleToString(gPeakEquity,2)); FileWrite(h,gHalted?"1":"0");
   FileWrite(h,gHaltWhy); FileClose(h);
}
void NewDay()
{
   gDayStamp=Today(); gDayStart=AccountInfoDouble(ACCOUNT_EQUITY); nTakenToday=0;
   if(gHaltWhy=="daily"){ gHalted=false; gHaltWhy=""; }
   SaveGuards();
}
bool GuardsBlock()
{
   if(!InpUseGuards) return false;
   if(gDayStamp!=Today()) NewDay();
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq>gPeakEquity) gPeakEquity=eq;
   if(gDayStart>0 && (gDayStart-eq)/gDayStart*100.0>=InpDailyLossPct){ gHalted=true; gHaltWhy="daily"; }
   if(gPeakEquity>0 && (gPeakEquity-eq)/gPeakEquity*100.0>=InpMaxDDPct){ gHalted=true; gHaltWhy="maxdd"; }
   if(gHalted && InpCloseOnGuard) CloseAll();
   return gHalted;
}
double AtrNow(){ double a[]; ArraySetAsSeries(a,true); if(CopyBuffer(hAtr,0,1,2,a)<2) return 0; return a[0]; }

bool IsSessionBar(int hourGmt)
{
   MqlDateTime t; TimeToStruct(iTime(_Symbol,_Period,1),t);
   // treat the bar as the session bar only when GMT hour matches and it is
   // the FIRST bar of that hour, so intraday timeframes fire once
   MqlDateTime p; TimeToStruct(iTime(_Symbol,_Period,2),p);
   return (t.hour==hourGmt && p.hour!=hourGmt);
}

void OnTick()
{
   ManageOpen();
   datetime bt=iTime(_Symbol,_Period,0);
   if(bt==lastBar) return;
   lastBar=bt;

   if(Today()!=rDay){ rDay=Today(); nTakenToday=0; rReady=false; }

   double a=AtrNow();
   if(a<=0) return;

   // ---- build the pre-session range on the session bar
   bool sess = IsSessionBar(InpSessionHour) ||
               (InpAlsoSecond && IsSessionBar(InpSecondHour));
   if(sess)
   {
      rHi=-DBL_MAX; rLo=DBL_MAX;
      for(int k=2; k<=InpRangeBars+1; k++)
      {
         rHi=MathMax(rHi,iHigh(_Symbol,_Period,k));
         rLo=MathMin(rLo,iLow(_Symbol,_Period,k));
      }
      double w=rHi-rLo;
      rReady = (w >= InpMinRangeATR*a && w <= InpMaxRangeATR*a);
      if(!rReady) nSkipRange++;
      rBarsLeft = InpWindowBars;
      if(InpDrawRange && rReady) DrawRange();
   }

   if(!rReady) return;
   if(rBarsLeft-- <= 0){ rReady=false; return; }
   if(GuardsBlock()) return;
   if(nTakenToday >= InpTradesPerDay) return;
   if(CountOpen() > 0) return;

   double c1=iClose(_Symbol,_Period,1), h1=iHigh(_Symbol,_Period,1), l1=iLow(_Symbol,_Period,1);
   int dir=0;
   if(InpCloseBeyond) { if(c1>rHi) dir=1; else if(c1<rLo) dir=-1; }
   else               { if(h1>rHi) dir=1; else if(l1<rLo) dir=-1; }
   if(dir==0) return;

   double px=(dir>0)?SymbolInfoDouble(_Symbol,SYMBOL_ASK):SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double sd;
   if(InpStopKind==STOP_ATR) sd=InpStopAtrMult*a;
   else                      sd=(dir>0)?MathAbs(px-rLo):MathAbs(rHi-px);
   if(sd<=0) return;
   if(sd>InpMaxStopATR*a){ nSkipWide++; rReady=false; return; }

   double lots=SizeFor(sd);
   if(lots<=0){ nSkipSize++; rReady=false; return; }

   int dg=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double sl=NormalizeDouble((dir>0)?px-sd:px+sd,dg);
   double tp=0.0;
   if(InpHardTpR>0) tp=NormalizeDouble((dir>0)?px+InpHardTpR*sd:px-InpHardTpR*sd,dg);

   bool ok=(dir>0)?Trade.Buy(lots,_Symbol,0.0,sl,tp,"SRE")
                  :Trade.Sell(lots,_Symbol,0.0,sl,tp,"SRE");
   if(!ok){ Print("order failed ",Trade.ResultRetcode()); return; }
   gDir=dir; gEntry=(Trade.ResultPrice()>0?Trade.ResultPrice():px);
   gStopDist=sd; gPeakFav=0; gArmed=0; nTrades++; nTakenToday++; rReady=false;
   if(InpJournal) PrintFormat("ORB %s range=%.2f-%.2f (%.2fATR) entry=%.2f stop=%.2f",
      dir>0?"BUY":"SELL", rLo, rHi, (rHi-rLo)/a, gEntry, sd);
}

double MoneyPerPricePerLot()
{
   double tv=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   return (ts>0)?tv/ts:0.0;
}
double SizeFor(double stopDist)
{
   double minL=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxL=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double stp =SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(!InpUseRiskPct) return MathMax(minL,MathMin(maxL,InpFixedLot));
   double mpp=MoneyPerPricePerLot();
   if(mpp<=0||stopDist<=0) return 0.0;
   double lots=(AccountInfoDouble(ACCOUNT_BALANCE)*InpRiskPct/100.0)/(stopDist*mpp);
   lots=MathFloor(lots/stp)*stp;
   if(lots<minL) return 0.0;
   return MathMin(lots,maxL);
}

void ManageOpen()
{
   if(!PositionSelect(_Symbol)){ if(gDir!=0) FinishTrade(); return; }
   if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) return;
   int dir=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY)?1:-1;
   double ent=PositionGetDouble(POSITION_PRICE_OPEN);
   double sl =PositionGetDouble(POSITION_SL);
   double cur=(dir>0)?SymbolInfoDouble(_Symbol,SYMBOL_BID):SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   if(gStopDist<=0) gStopDist=MathAbs(ent-sl);
   if(gStopDist<=0) return;
   gDir=dir; gEntry=ent;
   double fav=(cur-ent)*dir;
   if(fav>gPeakFav) gPeakFav=fav;
   if(gPeakFav < InpArmAtR*gStopDist) return;
   gArmed=1.0;
   double a=AtrNow();
   double cand=(dir>0)?cur-InpTrailAtr*a:cur+InpTrailAtr*a;
   int dg=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   cand=NormalizeDouble(cand,dg);
   bool better=(dir>0)?(cand>sl):(cand<sl);
   double lvl=(double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   bool legal=(dir>0)?(cur-cand>lvl):(cand-cur>lvl);
   if(better&&legal) Trade.PositionModify(_Symbol,cand,PositionGetDouble(POSITION_TP));
}

void FinishTrade()
{
   if(!HistorySelect(TimeCurrent()-86400,TimeCurrent()+60)){ gDir=0; return; }
   double pts=0; bool found=false;
   for(int i=HistoryDealsTotal()-1;i>=0&&!found;i--)
   {
      ulong t=HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(t,DEAL_MAGIC)!=InpMagic) continue;
      if(HistoryDealGetInteger(t,DEAL_ENTRY)!=DEAL_ENTRY_OUT) continue;
      pts=(HistoryDealGetDouble(t,DEAL_PRICE)-gEntry)*gDir; found=true;
   }
   if(found&&gStopDist>0)
   {
      double eR=pts/gStopDist,pR=gPeakFav/gStopDist;
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
void CloseAll()
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong t=PositionGetTicket(i); if(t==0) continue;
      if(PositionGetInteger(POSITION_MAGIC)==InpMagic && PositionGetString(POSITION_SYMBOL)==_Symbol)
         Trade.PositionClose(t);
   }
}
void DrawRange()
{
   string n="SRE_range_"+(string)(long)rDay;
   if(ObjectFind(0,n)<0)
      ObjectCreate(0,n,OBJ_RECTANGLE,0,iTime(_Symbol,_Period,InpRangeBars+1),rHi,
                                       iTime(_Symbol,_Period,1),rLo);
   ObjectSetInteger(0,n,OBJPROP_COLOR,clrSlateGray);
   ObjectSetInteger(0,n,OBJPROP_FILL,true);
   ObjectSetInteger(0,n,OBJPROP_BACK,true);
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
   string n="SRE_panel";
   double cap=(nCapture>0)?sumCapture/nCapture:0.0;
   string s=StringFormat(
      "Session Range Engine   %s %s\n"
      "session: %s (GMT %s)   break hour %02d:00\n"
      "range %s  %.2f - %.2f   window left %d\n"
      "trades %d   win %.0f%%   sumR %+.2f   pts %+.1f\n"
      "CAPTURE RATIO %.2f (n=%d)\n"
      "skipped: range %d | wide %d | size %d\n"
      "guards: %s   day %+.2f%%   dd %+.2f%%",
      _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
      SessionNow(), TimeToString(TimeGMT(),TIME_MINUTES), InpSessionHour,
      rReady?"ARMED":"-", rLo, rHi, MathMax(rBarsLeft,0),
      nTrades, nTrades>0?100.0*nWins/nTrades:0.0, sumR, sumPts, cap, nCapture,
      nSkipRange, nSkipWide, nSkipSize,
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
   ObjectSetInteger(0,n,OBJPROP_COLOR,gHalted?clrTomato:clrGainsboro);
   ObjectSetString(0,n,OBJPROP_TEXT,s);
   ChartRedraw(0);
}
//+------------------------------------------------------------------+

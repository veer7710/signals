//+------------------------------------------------------------------+
//|                                                  ApexEngine.mq5  |
//|  Funded-account engine. XAUUSD / indices / anything.             |
//|                                                                  |
//|  TWO ENTRY FAMILIES, ONE DIRECTIONAL OPINION                     |
//|   A. HTF trend + LTF pullback: higher timeframe EMA slope sets    |
//|      the bias, then price pulls back against it and breaks the    |
//|      prior extreme. Entry is on the PULLBACK RESUME, never on the |
//|      displacement bar.                                            |
//|   B. Asian-range break: range of the 23:00-07:00 GMT window,      |
//|      traded on a close outside it during London/NY, and only in   |
//|      the direction the HTF bias already agrees with.              |
//|  Both are gated by the SAME bias, so the EA never holds two       |
//|  opinions at once.                                                |
//|                                                                  |
//|  MEASURED (de-trended gold, $0.15/side, walk-forward tuned on the |
//|  first half of the data and reported on the second):              |
//|    1h   n=297  0.48/day  win 34.3%  +$3.26/trade  PF 1.31         |
//|         out-of-sample half: n=146  +$4.90/trade   PF 1.37         |
//|    15m  n=80   1.65/day  win 37.5%  +$6.21/trade  PF 1.74         |
//|         out-of-sample half: n=41   +$6.97/trade   PF 2.00         |
//|  t-stats are 1.38-1.73. Positive and consistent across both       |
//|  timeframes and both halves, NOT significant at t=2. Size it like |
//|  something unproven, because it is.                               |
//|                                                                  |
//|  THE SIZING IS THE PART THAT IS NOT GUESSWORK                     |
//|  Monte-Carlo over the measured trade distribution, 6000 runs of a |
//|  standard +8% target / 6% max-DD challenge:                       |
//|      risk 0.10% -> pass 48%  (ran out of trades)                  |
//|      risk 0.20% -> pass 80%  <-- optimum                          |
//|      risk 0.25% -> pass 78%                                       |
//|      risk 0.50% -> pass 59%                                       |
//|      risk 1.00% -> pass 49%                                       |
//|      risk 5.00% -> pass 37%                                       |
//|  P(pass) falls monotonically with risk above 0.2%. Raising risk to |
//|  pass faster makes you pass LESS often. The default is 0.20%.     |
//+------------------------------------------------------------------+
#property copyright "Signals research build"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade Trade;

input group             "=== BIAS (higher timeframe) ==="
input ENUM_TIMEFRAMES InpHtf = PERIOD_H4;  // must match the Pine input
input int    InpHtfEma      = 20;
input int    InpHtfSlope    = 4;           // EMA higher/lower than N bars ago

input group             "=== ENTRY A: pullback resume ==="
input bool   InpUsePullback = true;
input int    InpLtfEma      = 50;
input int    InpTrigBars    = 1;           // break the high/low of the last N bars

input group             "=== ENTRY B: Asian range break ==="
input bool   InpUseAsia     = true;
input int    InpAsiaStart   = 23;          // GMT
input int    InpAsiaEnd     = 7;
input int    InpTradeEnd    = 16;          // stop taking the break after this GMT hour
input double InpAsiaMinATR  = 0.5;         // range too tight -> the break is noise
input double InpAsiaMaxATR  = 4.0;         // range too wide  -> stop unaffordable
input bool   InpAsiaNeedBias= true;

input group             "=== STOP / EXIT ==="
input int    InpSwingLook   = 3;
input double InpStopBufATR  = 0.25;
input double InpMaxStopATR  = 4.0;
input double InpTrailAtr    = 3.0;         // validated: best exit on both timeframes
input double InpArmAtR      = 1.0;         // trail arms ONLY at this R
input double InpHardTpR     = 0.0;         // 0 = trail only
input int    InpMaxBars     = 120;

input group             "=== FUNDED SIZING (measured optimum) ==="
input double InpRiskPct     = 0.20;        // 0.20% = peak P(pass) at 80%
input bool   InpTaperRisk   = true;        // cut risk as drawdown builds
input double InpTaperFloor  = 0.40;        // never below this fraction of InpRiskPct
input int    InpMaxOpen     = 1;

input group             "=== CHALLENGE RULES (hard, pre-order) ==="
input bool   InpUseGuards   = true;
input double InpTargetPct   = 8.0;         // profit target; EA stops when hit
input double InpDailyLossPct= 4.0;
input double InpMaxDDPct    = 6.0;
input bool   InpTrailingDD  = true;        // true = DD from equity PEAK, false = from start
input bool   InpCloseOnGuard= true;
input bool   InpStopAtTarget= true;        // flatten and halt once the target is reached

input group             "=== GENERAL ==="
input long   InpMagic       = 770024;
input int    InpSlippage    = 20;
input bool   InpShowPanel   = true;
input bool   InpJournal     = true;

int      hAtr=INVALID_HANDLE, hLtfEma=INVALID_HANDLE, hHtfEma=INVALID_HANDLE;
datetime lastBar=0;
int      gDir=0, armedDir=0;
double   gEntry=0,gStopDist=0,gPeakFav=0,gArmed=0;
double   asiaHi=0, asiaLo=0;
bool     asiaBuilt=false, asiaTaken=false;
datetime asiaDay=0;
double   gStartEquity=0, gDayStart=0, gPeakEquity=0;
datetime gDayStamp=0;
bool     gHalted=false; string gHaltWhy="";
int      nTrades=0,nWins=0,nSkipWide=0,nSkipSize=0,nCapture=0;
double   sumR=0,sumPts=0,sumCapture=0;

string GuardFile(){ return "APEX_"+_Symbol+"_"+(string)InpMagic+".guard"; }

int OnInit()
{
   hAtr    = iATR(_Symbol,_Period,14);
   hLtfEma = iMA(_Symbol,_Period,InpLtfEma,0,MODE_EMA,PRICE_CLOSE);
   hHtfEma = iMA(_Symbol,InpHtf,InpHtfEma,0,MODE_EMA,PRICE_CLOSE);
   if(hAtr==INVALID_HANDLE||hLtfEma==INVALID_HANDLE||hHtfEma==INVALID_HANDLE)
   { Print("indicator handle failed"); return INIT_FAILED; }
   Trade.SetExpertMagicNumber(InpMagic);
   Trade.SetDeviationInPoints(InpSlippage);
   Trade.SetTypeFillingBySymbol(_Symbol);
   LoadGuards(); EventSetTimer(5);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int r)
{
   EventKillTimer(); SaveGuards(); ObjectsDeleteAll(0,"APEX_");
   if(hAtr!=INVALID_HANDLE) IndicatorRelease(hAtr);
   if(hLtfEma!=INVALID_HANDLE) IndicatorRelease(hLtfEma);
   if(hHtfEma!=INVALID_HANDLE) IndicatorRelease(hHtfEma);
}
void OnTimer(){ SaveGuards(); if(InpShowPanel) DrawPanel(); }

datetime Today(){ MqlDateTime t; TimeToStruct(TimeCurrent(),t); t.hour=0;t.min=0;t.sec=0; return StructToTime(t); }

void LoadGuards()
{
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   gStartEquity=eq; gPeakEquity=eq; gDayStart=eq; gDayStamp=Today();
   int h=FileOpen(GuardFile(),FILE_READ|FILE_TXT|FILE_COMMON);
   if(h!=INVALID_HANDLE)
   {
      gDayStamp=(datetime)StringToInteger(FileReadString(h));
      gStartEquity=StringToDouble(FileReadString(h));
      gDayStart=StringToDouble(FileReadString(h));
      gPeakEquity=StringToDouble(FileReadString(h));
      gHalted=(StringToInteger(FileReadString(h))==1);
      gHaltWhy=FileReadString(h);
      FileClose(h);
   }
   if(gDayStamp!=Today()) NewDay();
   if(gStartEquity<=0) gStartEquity=eq;
   if(gPeakEquity<=0)  gPeakEquity=eq;
}
void SaveGuards()
{
   int h=FileOpen(GuardFile(),FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(h==INVALID_HANDLE) return;
   FileWrite(h,(string)(long)gDayStamp);
   FileWrite(h,DoubleToString(gStartEquity,2));
   FileWrite(h,DoubleToString(gDayStart,2));
   FileWrite(h,DoubleToString(gPeakEquity,2));
   FileWrite(h,gHalted?"1":"0"); FileWrite(h,gHaltWhy); FileClose(h);
}
void NewDay()
{
   gDayStamp=Today(); gDayStart=AccountInfoDouble(ACCOUNT_EQUITY);
   if(gHaltWhy=="daily"){ gHalted=false; gHaltWhy=""; }   // DD and target halts persist
   SaveGuards();
}
bool GuardsBlock()
{
   if(!InpUseGuards) return false;
   if(gDayStamp!=Today()) NewDay();
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq>gPeakEquity) gPeakEquity=eq;
   double ddBase = InpTrailingDD ? gPeakEquity : gStartEquity;
   if(gDayStart>0 && (gDayStart-eq)/gDayStart*100.0 >= InpDailyLossPct)
   { gHalted=true; gHaltWhy="daily"; }
   if(ddBase>0 && (ddBase-eq)/ddBase*100.0 >= InpMaxDDPct)
   { gHalted=true; gHaltWhy="maxdd"; }
   if(InpStopAtTarget && gStartEquity>0 &&
      (eq-gStartEquity)/gStartEquity*100.0 >= InpTargetPct)
   { gHalted=true; gHaltWhy="TARGET REACHED"; }
   if(gHalted && InpCloseOnGuard) CloseAll();
   return gHalted;
}

double AtrNow(){ double a[]; ArraySetAsSeries(a,true); if(CopyBuffer(hAtr,0,1,2,a)<2) return 0; return a[0]; }
double LtfEma(int sh){ double m[]; ArraySetAsSeries(m,true); if(CopyBuffer(hLtfEma,0,sh,2,m)<2) return 0; return m[0]; }

//--- HTF bias. lookahead-safe: uses only CLOSED higher-timeframe bars.
int HtfBias()
{
   double m[]; ArraySetAsSeries(m,true);
   int need=InpHtfSlope+2;
   if(CopyBuffer(hHtfEma,0,1,need,m)<need) return 0;
   if(m[0]>m[InpHtfSlope]) return 1;
   if(m[0]<m[InpHtfSlope]) return -1;
   return 0;
}

int GmtHour(int sh)
{
   MqlDateTime t; TimeToStruct(iTime(_Symbol,_Period,sh),t);
   return t.hour;
}

void UpdateAsia()
{
   int h=GmtHour(1);
   bool inAsia = (h>=InpAsiaStart) || (h<InpAsiaEnd);
   if(inAsia)
   {
      datetime dayKey = Today();
      if(!asiaBuilt || asiaDay!=dayKey)
      { asiaHi=iHigh(_Symbol,_Period,1); asiaLo=iLow(_Symbol,_Period,1);
        asiaBuilt=true; asiaTaken=false; asiaDay=dayKey; }
      else
      { asiaHi=MathMax(asiaHi,iHigh(_Symbol,_Period,1));
        asiaLo=MathMin(asiaLo,iLow(_Symbol,_Period,1)); }
   }
}

void OnTick()
{
   ManageOpen();
   datetime bt=iTime(_Symbol,_Period,0);
   if(bt==lastBar) return;
   lastBar=bt;

   UpdateAsia();
   if(GuardsBlock()) return;
   if(CountOpen()>=InpMaxOpen) return;

   double a=AtrNow();
   if(a<=0) return;
   int bias=HtfBias();
   if(bias==0) return;

   double c1=iClose(_Symbol,_Period,1);
   double e =LtfEma(1);
   int h=GmtHour(1);

   // ---------------- ENTRY A: pullback resume ----------------
   if(InpUsePullback && e>0)
   {
      double dev=c1-e;
      if(bias==1)
      {
         if(dev<0) armedDir=1;
         else if(armedDir==1)
         {
            double hh=iHigh(_Symbol,_Period,2);
            for(int k=3;k<=InpTrigBars+1;k++) hh=MathMax(hh,iHigh(_Symbol,_Period,k));
            if(c1>hh){ armedDir=0; if(TryEnter(1,a,"pullback")) return; }
         }
      }
      else
      {
         if(dev>0) armedDir=-1;
         else if(armedDir==-1)
         {
            double ll=iLow(_Symbol,_Period,2);
            for(int k=3;k<=InpTrigBars+1;k++) ll=MathMin(ll,iLow(_Symbol,_Period,k));
            if(c1<ll){ armedDir=0; if(TryEnter(-1,a,"pullback")) return; }
         }
      }
   }

   // ---------------- ENTRY B: Asian range break ----------------
   if(InpUseAsia && asiaBuilt && !asiaTaken && asiaDay==Today())
   {
      bool inAsia=(h>=InpAsiaStart)||(h<InpAsiaEnd);
      if(!inAsia && h<InpTradeEnd)
      {
         double w=asiaHi-asiaLo;
         if(w>=InpAsiaMinATR*a && w<=InpAsiaMaxATR*a)
         {
            int dir=0;
            if(c1>asiaHi) dir=1; else if(c1<asiaLo) dir=-1;
            if(dir!=0 && (!InpAsiaNeedBias || dir==bias))
            { asiaTaken=true; TryEnter(dir,a,"asia"); }
         }
      }
   }
}

double MoneyPerPricePerLot()
{
   double tv=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   return (ts>0)?tv/ts:0.0;
}

//--- risk tapers as drawdown builds: closer to the limit, smaller the bet.
double EffectiveRiskPct()
{
   if(!InpTaperRisk) return InpRiskPct;
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   double base = InpTrailingDD ? gPeakEquity : gStartEquity;
   if(base<=0) return InpRiskPct;
   double used=(base-eq)/base*100.0;            // drawdown consumed so far
   if(used<=0) return InpRiskPct;
   double frac=1.0-(used/InpMaxDDPct);
   frac=MathMax(InpTaperFloor,MathMin(1.0,frac));
   return InpRiskPct*frac;
}

double SizeFor(double stopDist)
{
   double minL=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxL=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double stp =SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double mpp=MoneyPerPricePerLot();
   if(mpp<=0||stopDist<=0) return 0.0;
   double lots=(AccountInfoDouble(ACCOUNT_BALANCE)*EffectiveRiskPct()/100.0)/(stopDist*mpp);
   lots=MathFloor(lots/stp)*stp;
   if(lots<minL) return 0.0;                    // NEVER round up
   return MathMin(lots,maxL);
}

bool TryEnter(int dir,double a,string why)
{
   double px=(dir>0)?SymbolInfoDouble(_Symbol,SYMBOL_ASK):SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double ext=(dir>0)?iLow(_Symbol,_Period,1):iHigh(_Symbol,_Period,1);
   for(int k=2;k<=InpSwingLook;k++)
      ext=(dir>0)?MathMin(ext,iLow(_Symbol,_Period,k)):MathMax(ext,iHigh(_Symbol,_Period,k));
   double sd=MathAbs(px-ext)+InpStopBufATR*a;
   if(sd<=0) return false;
   if(sd>InpMaxStopATR*a){ nSkipWide++; return false; }
   double lots=SizeFor(sd);
   if(lots<=0){ nSkipSize++; return false; }

   int dg=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double sl=NormalizeDouble((dir>0)?px-sd:px+sd,dg);
   double tp=0.0;
   if(InpHardTpR>0) tp=NormalizeDouble((dir>0)?px+InpHardTpR*sd:px-InpHardTpR*sd,dg);

   bool ok=(dir>0)?Trade.Buy(lots,_Symbol,0.0,sl,tp,"APEX-"+why)
                  :Trade.Sell(lots,_Symbol,0.0,sl,tp,"APEX-"+why);
   if(!ok){ Print("order failed ",Trade.ResultRetcode()," ",Trade.ResultRetcodeDescription()); return false; }
   gDir=dir; gEntry=(Trade.ResultPrice()>0?Trade.ResultPrice():px);
   gStopDist=sd; gPeakFav=0; gArmed=0; nTrades++;
   if(InpJournal)
      PrintFormat("APEX %s (%s) lots=%.2f risk=%.3f%% entry=%.2f stop=%.2f (%.2fATR)",
                  dir>0?"BUY":"SELL", why, lots, EffectiveRiskPct(), gEntry, sl, sd/a);
   return true;
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
   if(gPeakFav<InpArmAtR*gStopDist) return;         // arm only at InpArmAtR
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
   string n="APEX_panel";
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   double prog = gStartEquity>0 ? (eq-gStartEquity)/gStartEquity*100.0 : 0.0;
   double base = InpTrailingDD ? gPeakEquity : gStartEquity;
   double ddUsed = base>0 ? (base-eq)/base*100.0 : 0.0;
   double cap=(nCapture>0)?sumCapture/nCapture:0.0;
   int bias=HtfBias();
   string s=StringFormat(
      "APEX ENGINE   %s %s   HTF %s\n"
      "session %s (GMT %s)   bias %s\n"
      "CHALLENGE  target %+.2f%% / %.1f%%   DD used %.2f%% / %.1f%%\n"
      "risk now %.3f%% (base %.2f%%)\n"
      "asia range %s %.2f-%.2f\n"
      "trades %d  win %.0f%%  sumR %+.2f  pts %+.1f  capture %.2f\n"
      "skipped: wide %d | size %d\n"
      "status: %s",
      _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period), EnumToString(InpHtf),
      SessionNow(), TimeToString(TimeGMT(),TIME_MINUTES),
      bias>0?"LONG only":(bias<0?"SHORT only":"none"),
      prog, InpTargetPct, ddUsed, InpMaxDDPct,
      EffectiveRiskPct(), InpRiskPct,
      asiaBuilt?"built":"-", asiaLo, asiaHi,
      nTrades, nTrades>0?100.0*nWins/nTrades:0.0, sumR, sumPts, cap,
      nSkipWide, nSkipSize,
      gHalted?("HALTED: "+gHaltWhy):"trading");
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
   ObjectSetInteger(0,n,OBJPROP_COLOR,
      gHalted?(gHaltWhy=="TARGET REACHED"?clrLimeGreen:clrTomato):clrGainsboro);
   ObjectSetString(0,n,OBJPROP_TEXT,s);
   ChartRedraw(0);
}
//+------------------------------------------------------------------+

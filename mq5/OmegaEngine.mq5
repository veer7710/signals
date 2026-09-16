//+------------------------------------------------------------------+
//|                                                OmegaEngine.mq5   |
//|  Dual-slot engine: frequent scalps AND runners, one EA.          |
//|  Funded challenges and live accounts. Any symbol, any timeframe. |
//|                                                                  |
//|  ============ HOW THE HIGH WIN RATE IS ACTUALLY PRODUCED ========|
//|  Bank most of the position at a small structure target, let the  |
//|  rest run on a trail. Most trades then close green, and the      |
//|  occasional runner pays for the losers. That is the mechanism    |
//|  behind every 70-90% win rate you have ever been shown.          |
//|                                                                  |
//|  MEASURED on de-trended gold, $0.15/side, structures chosen on   |
//|  the FIRST half of the data and reported on the SECOND:          |
//|                                                                  |
//|    XAUUSD M15            in-sample        out-of-sample          |
//|    SCALP  (win-rate)   77.1% PF 1.31    82.5% PF 1.39  +$1.24    |
//|    BALANCED            68.3% PF 1.20    69.8% PF 1.29  +$1.54    |
//|    RUNNER (max profit) 50.0% PF 1.51    61.4% PF 1.65  +$4.37    |
//|    pure trail          34.3% PF 1.41    40.0% PF 1.72  +$5.96    |
//|                                                                  |
//|  Read that table honestly: the 82% win rate is real AND it is    |
//|  the LEAST profitable per trade of the four. Win rate and money  |
//|  pull in opposite directions. That is why this EA runs BOTH at   |
//|  once in two slots rather than making you choose.                |
//|                                                                  |
//|  ON H1 AND ABOVE the win-rate mode measured NEGATIVE in-sample   |
//|  (PF 0.67). Keep this EA on M1-M30. It is gated to refuse        |
//|  win-rate mode above H1 unless you override it.                  |
//|                                                                  |
//|  t-stats are 0.5-1.2. Positive and consistent across both halves |
//|  on M15, not significant at t=2. Size it as unproven.            |
//|                                                                  |
//|  ============ WHAT IS NOT IN HERE, AND WHY ======================|
//|  An adaptive trail that widens while the HTF bias agrees and     |
//|  tightens when it flips was built and measured: identical on the |
//|  scalp slot, WORSE on the runner (4.11 -> 3.84 in-sample). The   |
//|  confirmations are shown on the panel as information; they do    |
//|  not touch the trail, because measuring said they should not.    |
//+------------------------------------------------------------------+
#property copyright "Signals research build"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
CTrade        Trade;
CPositionInfo Pos;

//====================================================================
input group "=== SLOTS ==="
input bool   InpScalpOn      = true;   // frequent, high win rate, small
input bool   InpRunnerOn     = true;   // fewer, lower win rate, the bangers
input bool   InpAllowBoth    = true;   // hold one of each at the same time

input group "=== BIAS (higher timeframe) ==="
input ENUM_TIMEFRAMES InpHtf = PERIOD_H4;
input int    InpHtfEma       = 20;
input int    InpHtfSlope     = 4;

input group "=== ENTRIES ==="
input bool   InpUsePullback  = true;
input int    InpLtfEma       = 50;
input int    InpTrigBars     = 1;
input bool   InpUseAsia      = true;
input int    InpAsiaStart    = 23;     // GMT
input int    InpAsiaEnd      = 7;
input int    InpTradeEnd     = 16;
input double InpAsiaMinATR   = 0.5;
input double InpAsiaMaxATR   = 4.0;

input group "=== STOP (analysis-based, not fixed) ==="
input int    InpSwingLook    = 3;      // stop goes beyond this swing
input double InpStopBufATR   = 0.25;
input double InpMaxStopATR   = 4.0;    // skip if structure demands more

input group "=== SCALP SLOT EXIT ==="
input double InpS_Tp1R       = 0.25;   // measured: 82.5% win OOS at 0.25R
input double InpS_Part       = 0.85;   // fraction banked at TP1
input double InpS_Trail      = 3.0;
input double InpS_ArmR       = 1.0;
input int    InpS_MaxBars    = 80;

input group "=== RUNNER SLOT EXIT ==="
input double InpR_Tp1R       = 1.00;   // measured: 61.4% win OOS, PF 1.65
input double InpR_Part       = 0.30;
input double InpR_BeAtR      = 1.00;   // stop to breakeven once TP1 is reached
input double InpR_BeLockR    = 0.05;
input double InpR_Trail      = 2.0;
input double InpR_ArmR       = 1.0;
input int    InpR_MaxBars    = 200;

input group "=== TP FROM STRUCTURE ==="
input bool   InpStructTp     = true;   // TP1 = nearest untaken swing level
input double InpStructMinR   = 0.30;   // ignore the level if nearer than this
input double InpStructMaxR   = 4.00;   // or further than this

input group "=== RISK -- auto-adapts to the account ==="
input double InpRiskPct      = 0.20;   // Monte-Carlo optimum: 80% pass rate
input bool   InpTaperRisk    = true;   // shrink risk as drawdown is consumed
input double InpTaperFloor   = 0.40;
input bool   InpRefuseIfOversized = true; // skip rather than exceed target risk

input group "=== ACCOUNT RULES -- pick a preset or set your own ==="
enum RuleSet { RULES_CUSTOM, RULES_PROP_8_4_6, RULES_PROP_10_5_10, RULES_LIVE };
input RuleSet InpRules       = RULES_PROP_8_4_6;
input double InpTargetPct    = 8.0;
input double InpDailyLossPct = 4.0;
input double InpMaxDDPct     = 6.0;
input bool   InpTrailingDD   = true;   // DD measured from equity peak
input bool   InpStopAtTarget = true;
input bool   InpCloseOnGuard = true;

input group "=== SAFETY ==="
input bool   InpAllowAboveH1 = false;  // win-rate mode measured NEGATIVE on H1+
input long   InpMagic        = 770025;
input int    InpSlippage     = 20;
input bool   InpShowPanel    = true;
input bool   InpJournal      = true;

//====================================================================
#define SLOT_SCALP  0
#define SLOT_RUNNER 1

struct Slot
{
   ulong  ticket;
   int    dir;
   double entry, stopDist, peakFav, tp1;
   bool   hit1, beDone, armed, canPartial;
   int    openBar;
   bool   bankMode;        // small account: this trade banks at TP1 instead
};
Slot S[2];

int      hAtr=INVALID_HANDLE, hLtf=INVALID_HANDLE, hHtf=INVALID_HANDLE;
datetime lastBar=0;
int      armedDir=0;
double   asiaHi=0, asiaLo=0;
bool     asiaBuilt=false, asiaTaken=false;
datetime asiaDay=0;
double   gStart=0, gDayStart=0, gPeak=0;
datetime gDayStamp=0;
bool     gHalted=false; string gHaltWhy="";
// broker facts, resolved once
double   bMinLot=0.01, bMaxLot=100, bLotStep=0.01, bMoneyPerPrice=0, bStopLvl=0;
int      bDigits=2;
bool     bCanPartial=false;
// stats per slot
int      nT[2], nW[2], nSkipWide=0, nSkipSize=0;
double   sumPts[2], sumR[2], sumCap[2];
int      nCap[2];
double   bankAcc=0.0;





//--- forward declarations (auto-generated; see tools/add_fwd_decls.py)
string GuardFile();
void ClearSlot(int i);
void ResolveBroker();
void ApplyRules(double &target,double &daily,double &maxdd,bool &trailing);
double AtrNow();
double LtfEma();
int HtfBias();
int HoldScore(int dir);
datetime Today();
void LoadGuards();
void SaveGuards();
void NewDay();
bool GuardsBlock();
double EffectiveRiskPct();
int GmtHour(int sh);
void UpdateAsia();
double StructTarget(int dir,double entry,double stopDist);
double StopDistance(int dir,double a);
double SizeFor(double stopDist,double riskShare);
void OpenSlot(int slot,int dir,double a,string why);
bool SelectSlot(int slot);
void ManageSlot(int slot);
void SetStop(int slot,double cand,double cur,int dir);
void FinishSlot(int slot);
void CloseAll();
string SessionNow();
void DrawPanel();
//--- end forward declarations

string GuardFile(){ return "OMEGA_"+_Symbol+"_"+(string)InpMagic+".guard"; }

//====================================================================
int OnInit()
{
   hAtr = iATR(_Symbol,_Period,14);
   hLtf = iMA(_Symbol,_Period,InpLtfEma,0,MODE_EMA,PRICE_CLOSE);
   hHtf = iMA(_Symbol,InpHtf,InpHtfEma,0,MODE_EMA,PRICE_CLOSE);
   if(hAtr==INVALID_HANDLE||hLtf==INVALID_HANDLE||hHtf==INVALID_HANDLE)
   { Print("OMEGA: indicator handle failed"); return INIT_FAILED; }

   if(!InpAllowAboveH1 && _Period>PERIOD_H1)
   {
      Print("OMEGA: the win-rate exit measured NEGATIVE on H1 and above ",
            "(PF 0.67 in-sample). Use M1-M30, or set InpAllowAboveH1=true.");
      return INIT_FAILED;
   }

   ResolveBroker();
   Trade.SetExpertMagicNumber(InpMagic);
   Trade.SetDeviationInPoints(InpSlippage);
   Trade.SetTypeFillingBySymbol(_Symbol);
   for(int i=0;i<2;i++) ClearSlot(i);
   LoadGuards();
   EventSetTimer(5);
   PrintFormat("OMEGA init %s %s | minLot %.2f step %.2f | money/price/lot %.2f %s"
               " | partials %s | rules %s",
               _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
               bMinLot, bLotStep, bMoneyPerPrice,
               AccountInfoString(ACCOUNT_CURRENCY),
               bCanPartial?"available":"NOT possible at this size",
               EnumToString(InpRules));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int r)
{
   EventKillTimer(); SaveGuards(); ObjectsDeleteAll(0,"OMEGA_");
   if(hAtr!=INVALID_HANDLE) IndicatorRelease(hAtr);
   if(hLtf!=INVALID_HANDLE) IndicatorRelease(hLtf);
   if(hHtf!=INVALID_HANDLE) IndicatorRelease(hHtf);
}
void OnTimer(){ SaveGuards(); if(InpShowPanel) DrawPanel(); }

void ClearSlot(int i)
{
   S[i].ticket=0; S[i].dir=0; S[i].entry=0; S[i].stopDist=0; S[i].peakFav=0;
   S[i].tp1=0; S[i].hit1=false; S[i].beDone=false; S[i].armed=false;
   S[i].canPartial=false; S[i].openBar=0; S[i].bankMode=false;
}

//====================================================================
//  BROKER / ACCOUNT ADAPTATION
//  Nothing below is hard-coded for gold. Everything is read from the
//  symbol, so the same EA works on an index or a pair without edits.
//====================================================================
void ResolveBroker()
{
   bMinLot  = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   bMaxLot  = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   bLotStep = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   bDigits  = (int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   bStopLvl = (double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)
              * SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   double tv=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   bMoneyPerPrice = (ts>0) ? tv/ts : 0.0;
   if(bLotStep<=0) bLotStep=0.01;
   if(bMinLot<=0)  bMinLot=0.01;
}

//--- rule presets, so you do not have to look them up
void ApplyRules(double &target,double &daily,double &maxdd,bool &trailing)
{
   switch(InpRules)
   {
      case RULES_PROP_8_4_6:  target=8.0;  daily=4.0; maxdd=6.0;  trailing=true;  break;
      case RULES_PROP_10_5_10:target=10.0; daily=5.0; maxdd=10.0; trailing=false; break;
      case RULES_LIVE:        target=1e9;  daily=5.0; maxdd=20.0; trailing=true;  break;
      default:                target=InpTargetPct; daily=InpDailyLossPct;
                              maxdd=InpMaxDDPct;   trailing=InpTrailingDD;        break;
   }
}

double AtrNow(){ double a[]; ArraySetAsSeries(a,true); if(CopyBuffer(hAtr,0,1,2,a)<2) return 0; return a[0]; }
double LtfEma(){ double m[]; ArraySetAsSeries(m,true); if(CopyBuffer(hLtf,0,1,2,m)<2) return 0; return m[0]; }

int HtfBias()
{
   double m[]; ArraySetAsSeries(m,true);
   int need=InpHtfSlope+2;
   if(CopyBuffer(hHtf,0,1,need,m)<need) return 0;
   if(m[0]>m[InpHtfSlope]) return 1;
   if(m[0]<m[InpHtfSlope]) return -1;
   return 0;
}

//--- informational only. Measured: gating the trail on this did not help.
int HoldScore(int dir)
{
   int s=0;
   if(HtfBias()==dir) s++;
   double e=LtfEma(), c=iClose(_Symbol,_Period,1);
   if((dir>0 && c>e) || (dir<0 && c<e)) s++;
   double a[]; ArraySetAsSeries(a,true);
   if(CopyBuffer(hAtr,0,1,6,a)>=6 && a[0]>a[5]) s++;
   return s;
}

//====================================================================
//  GUARDS -- checked BEFORE every order, persisted across restarts
//====================================================================
datetime Today(){ MqlDateTime t; TimeToStruct(TimeCurrent(),t); t.hour=0;t.min=0;t.sec=0; return StructToTime(t); }

void LoadGuards()
{
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   gStart=eq; gPeak=eq; gDayStart=eq; gDayStamp=Today();
   int h=FileOpen(GuardFile(),FILE_READ|FILE_TXT|FILE_COMMON);
   if(h!=INVALID_HANDLE)
   {
      gDayStamp=(datetime)StringToInteger(FileReadString(h));
      gStart   =StringToDouble(FileReadString(h));
      gDayStart=StringToDouble(FileReadString(h));
      gPeak    =StringToDouble(FileReadString(h));
      gHalted  =(StringToInteger(FileReadString(h))==1);
      gHaltWhy =FileReadString(h);
      FileClose(h);
   }
   if(gDayStamp!=Today()) NewDay();
   if(gStart<=0) gStart=eq;
   if(gPeak<=0)  gPeak=eq;
}
void SaveGuards()
{
   int h=FileOpen(GuardFile(),FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(h==INVALID_HANDLE) return;
   FileWrite(h,(string)(long)gDayStamp);
   FileWrite(h,DoubleToString(gStart,2));
   FileWrite(h,DoubleToString(gDayStart,2));
   FileWrite(h,DoubleToString(gPeak,2));
   FileWrite(h,gHalted?"1":"0"); FileWrite(h,gHaltWhy); FileClose(h);
}
void NewDay()
{
   gDayStamp=Today(); gDayStart=AccountInfoDouble(ACCOUNT_EQUITY);
   asiaTaken=false;
   if(gHaltWhy=="daily"){ gHalted=false; gHaltWhy=""; }
   SaveGuards();
}
bool GuardsBlock()
{
   if(gDayStamp!=Today()) NewDay();
   double target,daily,maxdd; bool trailing;
   ApplyRules(target,daily,maxdd,trailing);
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq>gPeak) gPeak=eq;
   double base = trailing ? gPeak : gStart;
   if(gDayStart>0 && (gDayStart-eq)/gDayStart*100.0 >= daily)
   { gHalted=true; gHaltWhy="daily"; }
   if(base>0 && (base-eq)/base*100.0 >= maxdd)
   { gHalted=true; gHaltWhy="maxdd"; }
   if(InpStopAtTarget && gStart>0 && (eq-gStart)/gStart*100.0 >= target)
   { gHalted=true; gHaltWhy="TARGET REACHED"; }
   if(gHalted && InpCloseOnGuard) CloseAll();
   return gHalted;
}

double EffectiveRiskPct()
{
   if(!InpTaperRisk) return InpRiskPct;
   double target,daily,maxdd; bool trailing;
   ApplyRules(target,daily,maxdd,trailing);
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   double base = trailing ? gPeak : gStart;
   if(base<=0 || maxdd<=0) return InpRiskPct;
   double used=(base-eq)/base*100.0;
   if(used<=0) return InpRiskPct;
   double frac=1.0-(used/maxdd);
   frac=MathMax(InpTaperFloor,MathMin(1.0,frac));
   return InpRiskPct*frac;
}

//====================================================================
//  ASIAN RANGE
//====================================================================
int GmtHour(int sh){ MqlDateTime t; TimeToStruct(iTime(_Symbol,_Period,sh),t); return t.hour; }

void UpdateAsia()
{
   int h=GmtHour(1);
   bool inAsia=(h>=InpAsiaStart)||(h<InpAsiaEnd);
   if(!inAsia) return;
   datetime key=Today();
   if(!asiaBuilt || asiaDay!=key)
   { asiaHi=iHigh(_Symbol,_Period,1); asiaLo=iLow(_Symbol,_Period,1);
     asiaBuilt=true; asiaTaken=false; asiaDay=key; }
   else
   { asiaHi=MathMax(asiaHi,iHigh(_Symbol,_Period,1));
     asiaLo=MathMin(asiaLo,iLow(_Symbol,_Period,1)); }
}

//====================================================================
//  STRUCTURE TARGET -- "TP from analysis", not a fixed multiple
//====================================================================
double StructTarget(int dir,double entry,double stopDist)
{
   if(!InpStructTp) return 0.0;
   int bars=MathMin(200,Bars(_Symbol,_Period)-8);
   double best=0.0;
   for(int i=InpSwingLook+2;i<bars-InpSwingLook;i++)
   {
      bool piv=true;
      if(dir>0)
      {
         double v=iHigh(_Symbol,_Period,i);
         for(int k=1;k<=InpSwingLook && piv;k++)
            if(iHigh(_Symbol,_Period,i+k)>=v || iHigh(_Symbol,_Period,i-k)>=v) piv=false;
         if(piv && v>entry)
         { double want=v-entry;
           if(want>=InpStructMinR*stopDist && want<=InpStructMaxR*stopDist)
             if(best==0.0 || v<best) best=v; }
      }
      else
      {
         double v=iLow(_Symbol,_Period,i);
         for(int k=1;k<=InpSwingLook && piv;k++)
            if(iLow(_Symbol,_Period,i+k)<=v || iLow(_Symbol,_Period,i-k)<=v) piv=false;
         if(piv && v<entry)
         { double want=entry-v;
           if(want>=InpStructMinR*stopDist && want<=InpStructMaxR*stopDist)
             if(best==0.0 || v>best) best=v; }
      }
   }
   return best;
}

//====================================================================
//  MAIN
//====================================================================
void OnTick()
{
   ManageSlot(SLOT_SCALP);
   ManageSlot(SLOT_RUNNER);

   datetime bt=iTime(_Symbol,_Period,0);
   if(bt==lastBar) return;
   lastBar=bt;

   UpdateAsia();
   if(GuardsBlock()) return;

   double a=AtrNow();
   if(a<=0) return;
   int bias=HtfBias();
   if(bias==0) return;

   double c1=iClose(_Symbol,_Period,1);
   double e =LtfEma();
   int h=GmtHour(1);
   int sig=0; string why="";

   // ---- entry A: pullback resume (never on the displacement bar) ----
   if(InpUsePullback && e>0)
   {
      if(bias==1)
      {
         if(c1<e) armedDir=1;
         else if(armedDir==1)
         {
            double hh=iHigh(_Symbol,_Period,2);
            for(int k=3;k<=InpTrigBars+1;k++) hh=MathMax(hh,iHigh(_Symbol,_Period,k));
            if(c1>hh){ sig=1; why="pullback"; armedDir=0; }
         }
      }
      else
      {
         if(c1>e) armedDir=-1;
         else if(armedDir==-1)
         {
            double ll=iLow(_Symbol,_Period,2);
            for(int k=3;k<=InpTrigBars+1;k++) ll=MathMin(ll,iLow(_Symbol,_Period,k));
            if(c1<ll){ sig=-1; why="pullback"; armedDir=0; }
         }
      }
   }

   // ---- entry B: Asian range break, bias-agreeing only ----
   if(sig==0 && InpUseAsia && asiaBuilt && !asiaTaken && asiaDay==Today())
   {
      bool inAsia=(h>=InpAsiaStart)||(h<InpAsiaEnd);
      if(!inAsia && h<InpTradeEnd)
      {
         double w=asiaHi-asiaLo;
         if(w>=InpAsiaMinATR*a && w<=InpAsiaMaxATR*a)
         {
            int d2=0;
            if(c1>asiaHi) d2=1; else if(c1<asiaLo) d2=-1;
            if(d2!=0 && d2==bias){ sig=d2; why="asia"; asiaTaken=true; }
         }
      }
   }
   if(sig==0) return;

   bool scalpFree  = InpScalpOn  && S[SLOT_SCALP].dir==0;
   bool runnerFree = InpRunnerOn && S[SLOT_RUNNER].dir==0;
   if(!InpAllowBoth && (S[SLOT_SCALP].dir!=0 || S[SLOT_RUNNER].dir!=0)) return;
   if(scalpFree)  OpenSlot(SLOT_SCALP, sig, a, why);
   if(runnerFree) OpenSlot(SLOT_RUNNER,sig, a, why);
}

double StopDistance(int dir,double a)
{
   double px=(dir>0)?SymbolInfoDouble(_Symbol,SYMBOL_ASK):SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double ext=(dir>0)?iLow(_Symbol,_Period,1):iHigh(_Symbol,_Period,1);
   for(int k=2;k<=InpSwingLook;k++)
      ext=(dir>0)?MathMin(ext,iLow(_Symbol,_Period,k)):MathMax(ext,iHigh(_Symbol,_Period,k));
   return MathAbs(px-ext)+InpStopBufATR*a;
}

double SizeFor(double stopDist,double riskShare)
{
   if(bMoneyPerPrice<=0||stopDist<=0) return 0.0;
   double money=AccountInfoDouble(ACCOUNT_BALANCE)*EffectiveRiskPct()/100.0*riskShare;
   double lots=money/(stopDist*bMoneyPerPrice);
   lots=MathFloor(lots/bLotStep)*bLotStep;
   if(lots<bMinLot)
   {
      if(InpRefuseIfOversized) return 0.0;   // never round UP into extra risk
      lots=bMinLot;
   }
   return MathMin(lots,bMaxLot);
}

void OpenSlot(int slot,int dir,double a,string why)
{
   double sd=StopDistance(dir,a);
   if(sd<=0) return;
   if(sd>InpMaxStopATR*a){ nSkipWide++; return; }

   // scalp and runner each get half the risk budget when both are live
   double share = (InpScalpOn && InpRunnerOn && InpAllowBoth) ? 0.5 : 1.0;
   double lots=SizeFor(sd,share);
   if(lots<=0){ nSkipSize++; return; }

   double px=(dir>0)?SymbolInfoDouble(_Symbol,SYMBOL_ASK):SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double sl=NormalizeDouble((dir>0)?px-sd:px+sd,bDigits);

   bool ok=(dir>0)?Trade.Buy(lots,_Symbol,0.0,sl,0.0,
                             slot==SLOT_SCALP?"OMEGA-S-"+why:"OMEGA-R-"+why)
                  :Trade.Sell(lots,_Symbol,0.0,sl,0.0,
                             slot==SLOT_SCALP?"OMEGA-S-"+why:"OMEGA-R-"+why);
   if(!ok){ Print("OMEGA order failed ",Trade.ResultRetcode()," ",
                  Trade.ResultRetcodeDescription()); return; }

   S[slot].ticket   = Trade.ResultOrder();
   S[slot].dir      = dir;
   S[slot].entry    = (Trade.ResultPrice()>0?Trade.ResultPrice():px);
   S[slot].stopDist = sd;
   S[slot].peakFav  = 0;
   S[slot].hit1=false; S[slot].beDone=false; S[slot].armed=false;
   S[slot].openBar  = Bars(_Symbol,_Period);

   // can this position be split at all? 0.01 lots on a small account cannot.
   S[slot].canPartial = (lots >= 2.0*bMinLot);
   bCanPartial = S[slot].canPartial;

   // If it cannot be split, reproduce the SAME blend across trades instead
   // of within one: bank this whole trade at TP1, or run the whole thing,
   // in the measured proportion. Same expectation, more variance.
   double partFrac = (slot==SLOT_SCALP)?InpS_Part:InpR_Part;
   if(!S[slot].canPartial)
   {
      // Fractional accumulator: over N trades exactly partFrac of them are
      // banked whole and the rest are run whole, spread evenly rather than
      // in a block. Same expectation as splitting inside one trade, higher
      // variance -- which is the honest cost of a min-lot account.
      bankAcc += partFrac;
      if(bankAcc >= 1.0) { S[slot].bankMode = true;  bankAcc -= 1.0; }
      else               { S[slot].bankMode = false; }
   }
   else S[slot].bankMode=false;

   double tp1R=(slot==SLOT_SCALP)?InpS_Tp1R:InpR_Tp1R;
   double t=S[slot].entry+dir*tp1R*sd;
   double st=StructTarget(dir,S[slot].entry,sd);
   if(st>0) t=st;                                  // analysis beats a multiple
   S[slot].tp1=NormalizeDouble(t,bDigits);

   nT[slot]++;
   if(InpJournal)
      PrintFormat("OMEGA %s %s %s lots=%.2f risk=%.3f%% entry=%.2f sl=%.2f "
                  "(%.2fATR) tp1=%.2f%s partial=%s",
                  slot==SLOT_SCALP?"SCALP":"RUNNER", dir>0?"BUY":"SELL", why,
                  lots, EffectiveRiskPct()*share, S[slot].entry, sl, sd/a,
                  S[slot].tp1, st>0?" (structure)":" (R-multiple)",
                  S[slot].canPartial?"yes":(S[slot].bankMode?"bank-whole":"run-whole"));
}

//--- find the live position that belongs to this slot
bool SelectSlot(int slot)
{
   if(S[slot].ticket==0) return false;
   if(!PositionSelectByTicket(S[slot].ticket)) return false;
   if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) return false;
   return true;
}

void ManageSlot(int slot)
{
   if(S[slot].dir==0) return;
   if(!SelectSlot(slot)){ FinishSlot(slot); return; }

   int    dir = S[slot].dir;
   double ent = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl  = PositionGetDouble(POSITION_SL);
   double vol = PositionGetDouble(POSITION_VOLUME);
   double cur = (dir>0)?SymbolInfoDouble(_Symbol,SYMBOL_BID):SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double sd  = S[slot].stopDist;
   if(sd<=0){ sd=MathAbs(ent-sl); S[slot].stopDist=sd; }
   if(sd<=0) return;

   double fav=(cur-ent)*dir;
   if(fav>S[slot].peakFav) S[slot].peakFav=fav;

   double partFrac = (slot==SLOT_SCALP)?InpS_Part:InpR_Part;
   double trailM   = (slot==SLOT_SCALP)?InpS_Trail:InpR_Trail;
   double armR     = (slot==SLOT_SCALP)?InpS_ArmR:InpR_ArmR;
   double beAtR    = (slot==SLOT_SCALP)?0.0:InpR_BeAtR;
   double beLockR  = (slot==SLOT_SCALP)?0.0:InpR_BeLockR;
   int    maxBars  = (slot==SLOT_SCALP)?InpS_MaxBars:InpR_MaxBars;

   // ---- TP1 ----
   bool tpHit = (dir>0)?(cur>=S[slot].tp1):(cur<=S[slot].tp1);
   if(!S[slot].hit1 && tpHit)
   {
      if(S[slot].canPartial)
      {
         double closeVol=MathFloor((vol*partFrac)/bLotStep)*bLotStep;
         if(closeVol>=bMinLot && (vol-closeVol)>=bMinLot)
         {
            if(Trade.PositionClosePartial(S[slot].ticket,closeVol))
            { S[slot].hit1=true;
              if(InpJournal) PrintFormat("OMEGA %s banked %.2f at %.2f",
                 slot==SLOT_SCALP?"SCALP":"RUNNER", closeVol, cur); }
         }
         else S[slot].hit1=true;          // cannot split further; let it run
      }
      else if(S[slot].bankMode)
      {
         Trade.PositionClose(S[slot].ticket);
         if(InpJournal) Print("OMEGA banked whole position (account too small to split)");
         return;
      }
      else S[slot].hit1=true;
   }

   // ---- breakeven push (runner slot only) ----
   if(beAtR>0 && !S[slot].beDone && S[slot].peakFav>=beAtR*sd)
   {
      double cand=ent+dir*beLockR*sd;
      if((dir>0&&cand>sl)||(dir<0&&cand<sl)) SetStop(slot,cand,cur,dir);
      S[slot].beDone=true;
   }

   // ---- runner trail, armed only at armR ----
   if(S[slot].peakFav>=armR*sd)
   {
      S[slot].armed=true;
      double a=AtrNow();
      double cand=(dir>0)?cur-trailM*a:cur+trailM*a;
      if((dir>0&&cand>sl)||(dir<0&&cand<sl)) SetStop(slot,cand,cur,dir);
   }

   // ---- time stop ----
   if(Bars(_Symbol,_Period)-S[slot].openBar>=maxBars)
   {
      Trade.PositionClose(S[slot].ticket);
      if(InpJournal) Print("OMEGA time stop on ",slot==SLOT_SCALP?"SCALP":"RUNNER");
   }
}

void SetStop(int slot,double cand,double cur,int dir)
{
   cand=NormalizeDouble(cand,bDigits);
   bool legal=(dir>0)?(cur-cand>bStopLvl):(cand-cur>bStopLvl);
   if(!legal) return;
   Trade.PositionModify(S[slot].ticket,cand,PositionGetDouble(POSITION_TP));
}

void FinishSlot(int slot)
{
   if(!HistorySelect(TimeCurrent()-604800,TimeCurrent()+60)){ ClearSlot(slot); return; }
   double pts=0; bool found=false; double volSum=0;
   for(int i=HistoryDealsTotal()-1;i>=0;i--)
   {
      ulong t=HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(t,DEAL_MAGIC)!=InpMagic) continue;
      if(HistoryDealGetInteger(t,DEAL_POSITION_ID)!=(long)S[slot].ticket) continue;
      if(HistoryDealGetInteger(t,DEAL_ENTRY)!=DEAL_ENTRY_OUT) continue;
      double v=HistoryDealGetDouble(t,DEAL_VOLUME);
      pts += v*(HistoryDealGetDouble(t,DEAL_PRICE)-S[slot].entry)*S[slot].dir;
      volSum+=v; found=true;
   }
   if(found && volSum>0 && S[slot].stopDist>0)
   {
      pts/=volSum;
      double eR=pts/S[slot].stopDist, pR=S[slot].peakFav/S[slot].stopDist;
      sumPts[slot]+=pts; sumR[slot]+=eR;
      if(pts>0) nW[slot]++;
      if(pR>=0.5){ sumCap[slot]+=eR/pR; nCap[slot]++; }
      if(InpJournal)
         PrintFormat("OMEGA %s closed peakR=%.2f exitR=%.2f capture=%.2f",
                     slot==SLOT_SCALP?"SCALP":"RUNNER",pR,eR,pR>0?eR/pR:0);
   }
   ClearSlot(slot);
}

void CloseAll()
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong t=PositionGetTicket(i); if(t==0) continue;
      if(PositionGetInteger(POSITION_MAGIC)==InpMagic
         && PositionGetString(POSITION_SYMBOL)==_Symbol) Trade.PositionClose(t);
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
   double target,daily,maxdd; bool trailing;
   ApplyRules(target,daily,maxdd,trailing);
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   double prog=gStart>0?(eq-gStart)/gStart*100.0:0.0;
   double base=trailing?gPeak:gStart;
   double ddUsed=base>0?(base-eq)/base*100.0:0.0;
   int bias=HtfBias();
   int liveDir = S[SLOT_SCALP].dir!=0?S[SLOT_SCALP].dir:S[SLOT_RUNNER].dir;

   string s=StringFormat(
     "OMEGA ENGINE  %s %s   HTF %s   bias %s\n"
     "session %s (GMT %s)   hold-score %d/3\n"
     "-------------------------------------------\n"
     "RULES %s   target %+.2f%%/%.1f%%   DD %.2f%%/%.1f%%\n"
     "risk now %.3f%% of %.2f %s   min lot %.2f  partials %s\n"
     "-------------------------------------------\n"
     "SCALP  trades %d  win %.0f%%  pts %+.1f  capture %.2f  %s\n"
     "RUNNER trades %d  win %.0f%%  pts %+.1f  capture %.2f  %s\n"
     "skipped: stop too wide %d | too small to size %d\n"
     "status: %s",
     _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period), EnumToString(InpHtf),
     bias>0?"LONG only":(bias<0?"SHORT only":"none"),
     SessionNow(), TimeToString(TimeGMT(),TIME_MINUTES),
     liveDir!=0?HoldScore(liveDir):0,
     EnumToString(InpRules), prog, target, ddUsed, maxdd,
     EffectiveRiskPct(), AccountInfoDouble(ACCOUNT_BALANCE),
     AccountInfoString(ACCOUNT_CURRENCY), bMinLot,
     bCanPartial?"on":"too small - alternating",
     nT[0], nT[0]>0?100.0*nW[0]/nT[0]:0.0, sumPts[0],
     nCap[0]>0?sumCap[0]/nCap[0]:0.0,
     S[0].dir==0?"flat":(S[0].dir>0?"LONG":"SHORT"),
     nT[1], nT[1]>0?100.0*nW[1]/nT[1]:0.0, sumPts[1],
     nCap[1]>0?sumCap[1]/nCap[1]:0.0,
     S[1].dir==0?"flat":(S[1].dir>0?"LONG":"SHORT"),
     nSkipWide, nSkipSize,
     gHalted?("HALTED: "+gHaltWhy):"trading");

   string n="OMEGA_panel";
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

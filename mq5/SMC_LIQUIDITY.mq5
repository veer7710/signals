//+------------------------------------------------------------------+
//|                                              SMC_LIQUIDITY.mq5   |
//|  Leg-to-leg in trend, ping-pong in range. Any symbol, any TF.    |
//|                                                                  |
//|  ================ WHAT THIS TRADES, IN ONE PARAGRAPH ============ |
//|  Price does not move to "resistance and stop". It moves TO the   |
//|  orders. A swing high is buy-stops plus resting sells; a swing   |
//|  low is sell-stops plus resting buys. Price is ATTRACTED to      |
//|  them, trades through to fill them, and only then turns. So      |
//|  this EA never fades a level on approach. It waits for the level |
//|  to be RUN, checks whether the run was absorbed or expanded, and |
//|  trades the absorption -- with the stop beyond the wick that     |
//|  did the running and the target at the next pool, because that   |
//|  is where price is going next.                                   |
//|                                                                  |
//|  ================ TP AND SL COME FROM THE CHART ================ |
//|  Neither is an R-multiple. That is the point.                    |
//|    SL  = beyond the sweep wick + ONE NOISE BAND. A stop inside   |
//|          the noise is not a stop, it is a donation -- and the    |
//|          "stopped then reversed" diagnosis in SNIPER exists      |
//|          because that kept happening.                            |
//|    TP  = the next opposing pool. If that pool sits behind two or |
//|          more live levels (HIGH RESISTANCE) the trade is refused: |
//|          a target you have to grind through is a bad target.      |
//|                                                                  |
//|  ================ TWO REGIMES, ONE ENGINE ====================== |
//|    TREND  leg-to-leg. Bias from the last BOS. Wait for the       |
//|           counter-side pool to be swept (that is the inducement  |
//|           being taken), enter the reclaim, target the next pool. |
//|    RANGE  ping-pong. Both boundaries touched twice or more, and  |
//|           wide enough to pay the spread twice over. Buy the low  |
//|           boundary on a sweep-and-reclaim, target the high.      |
//|  Regime is measured (efficiency ratio), not assumed. The         |
//|  reference day ran at 0.038 and was traded as a trend.           |
//|                                                                  |
//|  ================ HONEST STATUS ================================ |
//|  The absorption-vs-expansion split -- which everything here      |
//|  rests on -- was tested on de-trended gold and did NOT separate  |
//|  beyond a best-of-N null: +6.6 points on 15m (t=1.53) and -2.5   |
//|  on 1h (t=-1.04). The sign flips. That test was on 15m/1h        |
//|  futures; this runs on M1 spot, where a pierce-and-reclaim       |
//|  resolves in minutes rather than hours, so it is untested where  |
//|  it matters rather than disproven. Run it small, read the CSV,   |
//|  and let your own tape settle it.                                |
//+------------------------------------------------------------------+
#property copyright "SNIPER project"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
CTrade Trade;
#define SMC_BUILD "SMC LIQUIDITY v1.00"

input group "=== STRUCTURE ==="
input int    InpSwingN       = 3;      // pivot strength each side
input int    InpLookback     = 300;    // bars scanned for levels
input double InpEqTolATR     = 0.15;   // levels this close are ONE pool
input int    InpReactTouch    = 3;     // touches before a level counts as a reaction level

input group "=== THE RUN ==="
input double InpPierceATR    = 0.05;   // how far past the pool counts as run
input double InpExpandATR    = 0.35;   // close beyond by this = EXPANSION, level dead
input int    InpResolveBars  = 3;      // bars allowed to resolve absorption vs expansion
input bool   InpNeedReclaim  = true;   // require close back inside before entry

input group "=== CONFLUENCE (each is optional, each is counted) ==="
input bool   InpUseOTE       = true;   // entry inside the 0.62-0.79 retracement
input double InpOTELo        = 0.62;
input double InpOTEHi        = 0.79;
input bool   InpUseDiscount  = true;   // longs only below the 50% of the dealing range
input bool   InpUseOB        = true;   // entry must tap an order block
input bool   InpUseFVG       = true;   // ...or an unfilled fair value gap
input int    InpMinConfluence= 1;      // how many of the above must agree

input group "=== TARGET QUALITY ==="
input double InpMinRoomATR   = 1.20;   // clear air needed to the target pool
input int    InpMaxBetween   = 1;      // live levels allowed between here and target
input double InpMinRR        = 1.00;   // refuse if structural TP/SL is worse than this

input group "=== REGIME ==="
input int    InpRegimeBars   = 30;
input double InpRangeER      = 0.15;   // below = RANGE (ping-pong)
input double InpTrendER      = 0.30;   // above = TREND (leg-to-leg)
input bool   InpTradeRange   = true;
input bool   InpTradeTrend   = true;
input double InpMinRangeATR  = 3.0;    // a range under this wide cannot pay the spread

input group "=== STOP / EXIT ==="
input double InpNoiseATR     = 0.60;   // band = spread + this x ATR
input double InpStopBands    = 1.00;   // stop sits this many bands beyond the wick
input double InpMaxStopATR   = 4.00;
input bool   InpLockPeak     = true;
input double InpKeepMin      = 0.65;   // keep this fraction of a small peak
input double InpKeepMax      = 0.90;   // ...rising to this on a large one
input double InpKeepScaleATR = 2.00;
input double InpBEAtR        = 1.00;   // past this R the stop never goes below entry
input int    InpMaxHoldMin   = 120;

input group "=== RISK ==="
input double InpRiskPct      = 0.35;
input int    InpMaxOpen      = 1;
input bool   InpSpreadGate   = true;
input double InpMaxSpreadMult= 1.60;

input group "=== ACCOUNT RULES ==="
enum SmcRules { SMC_LIVE, SMC_PROP_8_4_6, SMC_PROP_10_5_10 };
input SmcRules InpRules      = SMC_LIVE;
input double InpDailyLossPct = 4.0;
input double InpMaxDDPct     = 6.0;

input group "=== DISPLAY ==="
input bool   InpDrawLevels   = true;
input bool   InpDrawBox      = true;   // the live position box, entry / SL / TP / P-L
input bool   InpShowPanel    = true;
input bool   InpWriteCSV     = true;
input string InpCSVName      = "SMC_LIQUIDITY.csv";
input bool   InpJournal      = true;

input group "=== GENERAL ==="
input long   InpMagic        = 3100001;
input int    InpSlippage     = 30;

//====================================================================
//  state
//====================================================================
#define MAXLV 64
double   hiLv[MAXLV], loLv[MAXLV];
int      hiTouch[MAXLV], loTouch[MAXLV];
bool     hiDead[MAXLV], loDead[MAXLV];
int      hiN = 0, loN = 0;

int      hAtr = INVALID_HANDLE;
datetime lastBar = 0;
double   gAtr = 0.0, gBand = 0.0;
int      gBias = 0;                    // +1 after a bullish BOS, -1 after bearish
double   gLegLo = 0.0, gLegHi = 0.0;   // current dealing range

ulong    pTicket = 0;
int      pDir = 0;
double   pEntry = 0, pStop = 0, pTarget = 0, pStopDist = 0, pPeak = 0;
datetime pOpened = 0;
bool     pLocked = false;
string   pWhy = "";

double   gStart = 0, gDayStart = 0, gPeakEq = 0;
datetime gDayStamp = 0;
bool     gHalt = false;
string   gHaltWhy = "";
int      nT = 0, nWin = 0, nRefRoom = 0, nRefConf = 0, nRefRR = 0, nRefSpread = 0;
double   sumPts = 0, sumPeak = 0;
int      csvH = INVALID_HANDLE;
double   spHist[200];
int      spN = 0;


//--- forward declarations (auto-generated; see tools/add_fwd_decls.py)
datetime DayStamp();
double Atr();
double SpreadNow();
double Band();
bool IsPivotHigh(int i);
bool IsPivotLow(int i);
void BuildLevels();
void UpdateBias();
double EfficiencyRatio();
string Regime();
double NearestPool(int dir, int &idx);
int LevelsBetween(double target, int dir);
bool InOTE(int dir);
bool InDiscount(int dir);
bool TapsOB(int dir);
bool TapsFVG(int dir);
int Confluence(int dir);
bool SpreadOK();
double SizeFor(double sd);
void Manage();
void Push(double want, double cur);
void Settle();
int CountOpen();
bool GuardsBlock();
void OpenCSV();
void WriteCSV(double pts);
void DrawBox();
void Rect(string n,datetime t1,double p1,datetime t2,double p2,color c);
void HLine(string n,double p,color c,int st,int w);
void Txt(string n,datetime t,double p,string s,color c);
void DrawLevels();
void DrawPanel();
//--- end forward declarations

//====================================================================
int OnInit()
{
   hAtr = iATR(_Symbol, _Period, 14);
   if(hAtr == INVALID_HANDLE) { Print(SMC_BUILD, ": ATR failed"); return INIT_FAILED; }
   Trade.SetExpertMagicNumber(InpMagic);
   Trade.SetDeviationInPoints(InpSlippage);
   Trade.SetTypeFillingBySymbol(_Symbol);
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   gStart = eq; gPeakEq = eq; gDayStart = eq; gDayStamp = DayStamp();
   OpenCSV();
   EventSetTimer(1);
   Print(SMC_BUILD, " on ", _Symbol, " ", EnumToString((ENUM_TIMEFRAMES)_Period));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int r)
{
   EventKillTimer();
   if(csvH != INVALID_HANDLE) { FileClose(csvH); csvH = INVALID_HANDLE; }
   ObjectsDeleteAll(0, "SMC_");
   if(hAtr != INVALID_HANDLE) IndicatorRelease(hAtr);
}

void OnTimer()
{
   Manage();
   if(InpDrawBox)   DrawBox();
   DrawLevels();
   if(InpShowPanel) DrawPanel();
}

datetime DayStamp()
{
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   t.hour = 0; t.min = 0; t.sec = 0;
   return StructToTime(t);
}

double Atr()
{
   double a[]; ArraySetAsSeries(a, true);
   if(CopyBuffer(hAtr, 0, 1, 2, a) < 2) return 0.0;
   return a[0];
}

double SpreadNow()
{
   return SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
}

//--- the noise band. Nothing may be locked or stopped closer than this.
double Band() { return SpreadNow() + InpNoiseATR * gAtr; }

//====================================================================
//  STRUCTURE
//====================================================================
bool IsPivotHigh(int i)
{
   double v = iHigh(_Symbol,_Period,i);
   for(int k = 1; k <= InpSwingN; k++)
      if(iHigh(_Symbol,_Period,i+k) >= v || iHigh(_Symbol,_Period,i-k) >= v) return false;
   return true;
}
bool IsPivotLow(int i)
{
   double v = iLow(_Symbol,_Period,i);
   for(int k = 1; k <= InpSwingN; k++)
      if(iLow(_Symbol,_Period,i+k) <= v || iLow(_Symbol,_Period,i-k) <= v) return false;
   return true;
}

//--- rebuild pools. Equal levels MERGE and count as touches: an equal high is
//--- not two levels, it is one shelf that has been defended twice.
void BuildLevels()
{
   hiN = 0; loN = 0;
   double tol = InpEqTolATR * gAtr;
   int look = MathMin(InpLookback, Bars(_Symbol,_Period) - InpSwingN - 2);
   for(int i = InpSwingN + 1; i < look; i++)
   {
      if(IsPivotHigh(i))
      {
         double v = iHigh(_Symbol,_Period,i);
         int at = -1;
         for(int j = 0; j < hiN; j++) if(MathAbs(hiLv[j]-v) <= tol) { at = j; break; }
         if(at >= 0) hiTouch[at]++;
         else if(hiN < MAXLV) { hiLv[hiN]=v; hiTouch[hiN]=1; hiDead[hiN]=false; hiN++; }
      }
      if(IsPivotLow(i))
      {
         double v = iLow(_Symbol,_Period,i);
         int at = -1;
         for(int j = 0; j < loN; j++) if(MathAbs(loLv[j]-v) <= tol) { at = j; break; }
         if(at >= 0) loTouch[at]++;
         else if(loN < MAXLV) { loLv[loN]=v; loTouch[loN]=1; loDead[loN]=false; loN++; }
      }
   }
   // the dealing range: the most recent confirmed swing low and high
   gLegHi = 0; gLegLo = 0;
   for(int i = InpSwingN + 1; i < look && (gLegHi == 0 || gLegLo == 0); i++)
   {
      if(gLegHi == 0 && IsPivotHigh(i)) gLegHi = iHigh(_Symbol,_Period,i);
      if(gLegLo == 0 && IsPivotLow(i))  gLegLo = iLow(_Symbol,_Period,i);
   }
}

//--- BOS / CHoCH. A close beyond the last opposing swing flips the bias.
void UpdateBias()
{
   double c = iClose(_Symbol,_Period,1);
   if(gLegHi > 0 && c > gLegHi) gBias = 1;
   if(gLegLo > 0 && c < gLegLo) gBias = -1;
}

double EfficiencyRatio()
{
   int n = MathMin(InpRegimeBars, Bars(_Symbol,_Period)-2);
   if(n < 5) return 0.0;
   double net = MathAbs(iClose(_Symbol,_Period,1) - iClose(_Symbol,_Period,n));
   double path = 0.0;
   for(int i = 1; i < n; i++)
      path += MathAbs(iClose(_Symbol,_Period,i) - iClose(_Symbol,_Period,i+1));
   return (path > 0.0) ? net/path : 0.0;
}

string Regime()
{
   double er = EfficiencyRatio();
   if(er < InpRangeER) return "RANGE";
   if(er > InpTrendER) return "TREND";
   return "MIXED";
}

//--- nearest live pool in a direction, with its index
double NearestPool(int dir, int &idx)
{
   idx = -1;
   double px = iClose(_Symbol,_Period,1), best = 0.0;
   if(dir > 0)
   {
      for(int i = 0; i < hiN; i++)
      {
         if(hiDead[i] || hiLv[i] <= px) continue;
         if(idx < 0 || hiLv[i] < best) { best = hiLv[i]; idx = i; }
      }
   }
   else
   {
      for(int i = 0; i < loN; i++)
      {
         if(loDead[i] || loLv[i] >= px) continue;
         if(idx < 0 || loLv[i] > best) { best = loLv[i]; idx = i; }
      }
   }
   return best;
}

//--- LOW vs HIGH RESISTANCE LIQUIDITY: how many live levels sit between price
//--- and the target. A target behind a stack of them is a target you grind to.
int LevelsBetween(double target, int dir)
{
   double px = iClose(_Symbol,_Period,1);
   int n = 0;
   if(dir > 0) { for(int i=0;i<hiN;i++) if(!hiDead[i] && hiLv[i]>px && hiLv[i]<target) n++; }
   else        { for(int i=0;i<loN;i++) if(!loDead[i] && loLv[i]<px && loLv[i]>target) n++; }
   return n;
}

//====================================================================
//  CONFLUENCE
//====================================================================
//--- OTE: is price inside the 0.62-0.79 retracement of the dealing range?
bool InOTE(int dir)
{
   if(!InpUseOTE) return true;
   if(gLegHi <= gLegLo) return false;
   double c = iClose(_Symbol,_Period,1);
   double r = gLegHi - gLegLo;
   double f = (dir > 0) ? (gLegHi - c)/r : (c - gLegLo)/r;
   return (f >= InpOTELo && f <= InpOTEHi);
}

//--- premium / discount: longs belong below the 50%, shorts above it
bool InDiscount(int dir)
{
   if(!InpUseDiscount) return true;
   if(gLegHi <= gLegLo) return false;
   double mid = (gLegHi + gLegLo) / 2.0;
   double c = iClose(_Symbol,_Period,1);
   return (dir > 0) ? (c <= mid) : (c >= mid);
}

//--- order block: the last opposing candle before the displacement that broke
//--- structure. Tapping it is the confluence; it is never the trigger.
bool TapsOB(int dir)
{
   if(!InpUseOB) return true;
   int look = MathMin(60, Bars(_Symbol,_Period)-4);
   double c = iClose(_Symbol,_Period,1);
   for(int i = 2; i < look; i++)
   {
      bool disp = (iHigh(_Symbol,_Period,i) - iLow(_Symbol,_Period,i)) > 1.5 * gAtr;
      if(!disp) continue;
      if(dir > 0 && iClose(_Symbol,_Period,i) > iOpen(_Symbol,_Period,i))
      {
         if(iClose(_Symbol,_Period,i+1) < iOpen(_Symbol,_Period,i+1))
            if(c >= iLow(_Symbol,_Period,i+1) && c <= iHigh(_Symbol,_Period,i+1)) return true;
      }
      if(dir < 0 && iClose(_Symbol,_Period,i) < iOpen(_Symbol,_Period,i))
      {
         if(iClose(_Symbol,_Period,i+1) > iOpen(_Symbol,_Period,i+1))
            if(c >= iLow(_Symbol,_Period,i+1) && c <= iHigh(_Symbol,_Period,i+1)) return true;
      }
   }
   return false;
}

//--- unfilled fair value gap in the trade's direction
bool TapsFVG(int dir)
{
   if(!InpUseFVG) return true;
   int look = MathMin(60, Bars(_Symbol,_Period)-4);
   double c = iClose(_Symbol,_Period,1);
   for(int i = 2; i < look; i++)
   {
      if(dir > 0)
      {
         double lo = iHigh(_Symbol,_Period,i+1), hi = iLow(_Symbol,_Period,i-1);
         if(hi - lo > 0.25*gAtr && c >= lo && c <= hi) return true;
      }
      else
      {
         double hi = iLow(_Symbol,_Period,i+1), lo = iHigh(_Symbol,_Period,i-1);
         if(hi - lo > 0.25*gAtr && c >= lo && c <= hi) return true;
      }
   }
   return false;
}

int Confluence(int dir)
{
   int n = 0;
   if(InpUseOTE      && InOTE(dir))      n++;
   if(InpUseDiscount && InDiscount(dir)) n++;
   if(InpUseOB       && TapsOB(dir))     n++;
   if(InpUseFVG      && TapsFVG(dir))    n++;
   return n;
}

//====================================================================
//  ENTRY
//====================================================================
bool SpreadOK()
{
   if(!InpSpreadGate) return true;
   double sp = SpreadNow();
   if(sp <= 0) return true;
   spHist[spN % 200] = sp; spN++;
   int have = MathMin(spN, 200);
   if(have < 20) return true;
   double t[]; ArrayResize(t, have);
   for(int i = 0; i < have; i++) t[i] = spHist[i];
   ArraySort(t);
   double med = t[have/2];
   if(med <= 0 || sp <= InpMaxSpreadMult*med) return true;
   nRefSpread++;
   return false;
}

void OnTick()
{
   Manage();
   datetime bt = iTime(_Symbol,_Period,0);
   if(bt == lastBar) return;
   lastBar = bt;

   gAtr = Atr();
   if(gAtr <= 0) return;
   gBand = Band();
   if(GuardsBlock()) return;
   if(pDir != 0 || CountOpen() >= InpMaxOpen) return;
   if(!SpreadOK()) return;

   BuildLevels();
   UpdateBias();

   string reg = Regime();
   int dir = 0; string why = "";
   double wick = 0.0;

   // ---- THE RUN. A pool is pierced; what happened next decides everything. ----
   double c1 = iClose(_Symbol,_Period,1);
   double h1 = iHigh(_Symbol,_Period,1), l1 = iLow(_Symbol,_Period,1);
   double pe = InpPierceATR * gAtr, ex = InpExpandATR * gAtr;

   for(int i = 0; i < loN && dir == 0; i++)
   {
      if(loDead[i] || loLv[i] >= c1 + gAtr*4) continue;
      if(l1 > loLv[i] - pe) continue;                    // not run
      // EXPANSION is judged over InpResolveBars, not one bar: a level that is
      // broken decisively two bars later was still broken, and fading it is
      // the single most expensive mistake available here.
      bool expanded = false;
      for(int q = 1; q <= InpResolveBars && !expanded; q++)
         if(iClose(_Symbol,_Period,q) < loLv[i] - ex) expanded = true;
      if(expanded) { loDead[i] = true; continue; }
      if(InpNeedReclaim && c1 <= loLv[i]) continue;      // run, not reclaimed
      loDead[i] = true;                                  // one event per level
      dir = 1; wick = l1;
      why = (loTouch[i] >= InpReactTouch) ? "SSL-sweep-react" : "SSL-sweep";
   }
   for(int i = 0; i < hiN && dir == 0; i++)
   {
      if(hiDead[i] || hiLv[i] <= c1 - gAtr*4) continue;
      if(h1 < hiLv[i] + pe) continue;
      bool expandedH = false;
      for(int q = 1; q <= InpResolveBars && !expandedH; q++)
         if(iClose(_Symbol,_Period,q) > hiLv[i] + ex) expandedH = true;
      if(expandedH) { hiDead[i] = true; continue; }
      if(InpNeedReclaim && c1 >= hiLv[i]) continue;
      hiDead[i] = true;
      dir = -1; wick = h1;
      why = (hiTouch[i] >= InpReactTouch) ? "BSL-sweep-react" : "BSL-sweep";
   }
   if(dir == 0) return;

   // ---- regime decides whether this sweep is a leg start or a rotation ----
   if(reg == "TREND")
   {
      if(!InpTradeTrend) return;
      if(gBias != 0 && dir != gBias) return;    // leg-to-leg only with the bias
      why += "|leg";
   }
   else if(reg == "RANGE")
   {
      if(!InpTradeRange) return;
      if(gLegHi - gLegLo < InpMinRangeATR * gAtr) return;   // too tight to pay
      why += "|pingpong";
   }
   else return;                                  // MIXED: stand down

   if(Confluence(dir) < InpMinConfluence) { nRefConf++; return; }

   // ---- TP AND SL FROM THE CHART ----
   int ti = -1;
   double tgt = NearestPool(dir, ti);
   if(ti < 0) { nRefRoom++; return; }
   double px = (dir>0)?SymbolInfoDouble(_Symbol,SYMBOL_ASK):SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double room = MathAbs(tgt - px);
   if(room < InpMinRoomATR*gAtr)            { nRefRoom++; return; }
   if(LevelsBetween(tgt, dir) > InpMaxBetween) { nRefRoom++; return; }   // HIGH RESISTANCE

   // the stop goes beyond the wick that did the running, plus a full band --
   // a stop inside the noise is not a stop
   double sd = MathAbs(px - wick) + InpStopBands * gBand;
   if(sd <= 0 || sd > InpMaxStopATR*gAtr) { nRefRoom++; return; }
   if(room / sd < InpMinRR)               { nRefRR++;  return; }

   double lots = SizeFor(sd);
   if(lots <= 0) return;
   int dg = (int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double sl = NormalizeDouble((dir>0)?px-sd:px+sd, dg);
   double tp = NormalizeDouble(tgt, dg);

   bool ok = (dir>0) ? Trade.Buy(lots,_Symbol,0.0,sl,tp,"SMC-"+why)
                     : Trade.Sell(lots,_Symbol,0.0,sl,tp,"SMC-"+why);
   if(!ok) { Print(SMC_BUILD," order failed ",Trade.ResultRetcode()); return; }

   pTicket = Trade.ResultOrder(); pDir = dir;
   pEntry = (Trade.ResultPrice()>0?Trade.ResultPrice():px);
   pStop = sl; pTarget = tp; pStopDist = sd; pPeak = 0; pLocked = false;
   pOpened = TimeCurrent(); pWhy = why; nT++;
   if(InpJournal)
      PrintFormat("%s %s %s  entry %.2f  SL %.2f (%.2f ATR, %.1f bands past the wick)"
                  "  TP %.2f (%.2f ATR away, %d levels between)  RR %.2f  conf %d  %s",
                  SMC_BUILD, (dir>0?"BUY":"SELL"), why, pEntry, sl, sd/gAtr,
                  InpStopBands, tp, room/gAtr, LevelsBetween(tgt,dir),
                  room/sd, Confluence(dir), reg);
}

double SizeFor(double sd)
{
   double minL=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxL=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double stp =SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double tv  =SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double ts  =SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(ts<=0||sd<=0) return 0.0;
   double mpp = tv/ts;
   if(stp<=0) stp=0.01;
   if(minL<=0) minL=0.01;
   double lots=(AccountInfoDouble(ACCOUNT_BALANCE)*InpRiskPct/100.0)/(sd*mpp);
   lots=MathFloor(lots/stp)*stp;
   if(lots<minL) return 0.0;              // skip, never round up
   return MathMin(lots,maxL);
}

//====================================================================
//  MANAGE
//====================================================================
void Manage()
{
   if(pDir == 0) return;
   if(!PositionSelectByTicket(pTicket)) { Settle(); return; }
   double a = Atr(); if(a<=0) a = gAtr; if(a<=0) return;
   double band = SpreadNow() + InpNoiseATR*a;
   double cur = (pDir>0)?SymbolInfoDouble(_Symbol,SYMBOL_BID):SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double fav = (cur-pEntry)*pDir;
   if(fav > pPeak) pPeak = fav;

   // past InpBEAtR the stop never goes below entry again
   if(InpBEAtR > 0 && pPeak >= InpBEAtR*pStopDist)
      Push(pEntry + pDir*0.05*pStopDist, cur);

   if(InpLockPeak && pPeak >= 2.0*band)
   {
      double t = MathMax(0.0, MathMin(1.0, (pPeak/a - 2.0*band/a) /
                 MathMax(0.0001, InpKeepScaleATR - 2.0*band/a)));
      double keep = InpKeepMin + t*(InpKeepMax - InpKeepMin);
      // never lock closer than one band -- no trail holds inside the noise
      double want = pEntry + pDir*MathMin(pPeak*keep, pPeak - band);
      if(!pLocked) pLocked = true;
      Push(want, cur);
   }
   if((int)(TimeCurrent()-pOpened) >= InpMaxHoldMin*60)
   { Trade.PositionClose(pTicket); if(InpJournal) Print(SMC_BUILD," time stop"); }
}

void Push(double want, double cur)
{
   int dg=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   want=NormalizeDouble(want,dg);
   double sl=PositionGetDouble(POSITION_SL);
   double lvl=(double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   bool better=(pDir>0)?(want>sl):(want<sl);
   bool legal =(pDir>0)?(cur-want>lvl):(want-cur>lvl);
   if(better&&legal) { Trade.PositionModify(pTicket,want,PositionGetDouble(POSITION_TP)); pStop=want; }
}

void Settle()
{
   double pts=0, vol=0;
   if(HistorySelect(pOpened-60, TimeCurrent()+60))
      for(int k=HistoryDealsTotal()-1;k>=0;k--)
      {
         ulong t=HistoryDealGetTicket(k);
         if(HistoryDealGetInteger(t,DEAL_MAGIC)!=InpMagic) continue;
         if(HistoryDealGetInteger(t,DEAL_POSITION_ID)!=(long)pTicket) continue;
         if(HistoryDealGetInteger(t,DEAL_ENTRY)!=DEAL_ENTRY_OUT) continue;
         double v=HistoryDealGetDouble(t,DEAL_VOLUME);
         pts += v*(HistoryDealGetDouble(t,DEAL_PRICE)-pEntry)*pDir; vol+=v;
      }
   if(vol>0) pts/=vol;
   sumPts += pts; sumPeak += pPeak;
   if(pts>0) nWin++;
   WriteCSV(pts);
   if(InpJournal)
      PrintFormat("%s closed %s  peak %.2f  exit %.2f  kept %.0f%%  held %dm",
                  SMC_BUILD, pWhy, pPeak, pts, (pPeak>0?100.0*pts/pPeak:0.0),
                  (int)((TimeCurrent()-pOpened)/60));
   pDir=0; pTicket=0; pPeak=0; pLocked=false;
}

int CountOpen()
{
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong t=PositionGetTicket(i); if(t==0) continue;
      if(PositionGetInteger(POSITION_MAGIC)==InpMagic
         && PositionGetString(POSITION_SYMBOL)==_Symbol) n++;
   }
   return n;
}

bool GuardsBlock()
{
   if(DayStamp()!=gDayStamp)
   { gDayStamp=DayStamp(); gDayStart=AccountInfoDouble(ACCOUNT_EQUITY);
     if(gHaltWhy=="daily"){gHalt=false;gHaltWhy="";} }
   double daily=InpDailyLossPct, maxdd=InpMaxDDPct;
   if(InpRules==SMC_PROP_8_4_6){daily=4.0;maxdd=6.0;}
   if(InpRules==SMC_PROP_10_5_10){daily=5.0;maxdd=10.0;}
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq>gPeakEq) gPeakEq=eq;
   if(gDayStart>0 && (gDayStart-eq)/gDayStart*100.0>=daily){gHalt=true;gHaltWhy="daily";}
   if(gPeakEq>0 && (gPeakEq-eq)/gPeakEq*100.0>=maxdd){gHalt=true;gHaltWhy="maxdd";}
   if(gHalt)
      for(int i=PositionsTotal()-1;i>=0;i--)
      {
         ulong t=PositionGetTicket(i); if(t==0) continue;
         if(PositionGetInteger(POSITION_MAGIC)==InpMagic
            && PositionGetString(POSITION_SYMBOL)==_Symbol) Trade.PositionClose(t);
      }
   return gHalt;
}

//====================================================================
//  CSV + DISPLAY
//====================================================================
void OpenCSV()
{
   if(!InpWriteCSV) return;
   bool fresh=!FileIsExist(InpCSVName,FILE_COMMON);
   csvH=FileOpen(InpCSVName,FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON,',');
   if(csvH==INVALID_HANDLE) return;
   FileSeek(csvH,0,SEEK_END);
   if(fresh) FileWrite(csvH,"open","close","dir","why","regime","entry","exit_pts",
                       "peak_pts","kept","stop_atr","target","rr","confluence","held_s");
}

void WriteCSV(double pts)
{
   if(!InpWriteCSV||csvH==INVALID_HANDLE) return;
   double a=(gAtr>0?gAtr:1.0);
   FileWrite(csvH,
      TimeToString(pOpened,TIME_DATE|TIME_SECONDS),
      TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS),
      (pDir>0?"BUY":"SELL"), pWhy, Regime(),
      DoubleToString(pEntry,2), DoubleToString(pts,2), DoubleToString(pPeak,2),
      DoubleToString((pPeak>0?pts/pPeak:0.0),3),
      DoubleToString(pStopDist/a,2), DoubleToString(pTarget,2),
      DoubleToString((pStopDist>0?MathAbs(pTarget-pEntry)/pStopDist:0.0),2),
      "", (string)(int)(TimeCurrent()-pOpened));
   FileFlush(csvH);
}

//--- the position box: entry, stop, target, live P/L, and how much of the peak
//--- is currently being held. Four numbers, nothing else.
void DrawBox()
{
   ObjectsDeleteAll(0,"SMC_pos");
   if(pDir==0) return;
   datetime t1=pOpened, t2=TimeCurrent()+PeriodSeconds()*10;
   Rect("SMC_pos_risk", t1,pEntry,t2,pStop, (pDir>0?clrFireBrick:clrFireBrick));
   Rect("SMC_pos_rew",  t1,pEntry,t2,pTarget,(pDir>0?clrSeaGreen:clrSeaGreen));
   HLine("SMC_pos_e", pEntry, clrGold, STYLE_SOLID, 2);
   double prof = PositionSelectByTicket(pTicket) ? PositionGetDouble(POSITION_PROFIT) : 0.0;
   string txt=StringFormat("%s %.2f   SL %.2f   TP %.2f   %+.2f %s   peak kept %.0f%%",
              (pDir>0?"LONG":"SHORT"), pEntry, pStop, pTarget, prof,
              AccountInfoString(ACCOUNT_CURRENCY),
              (pPeak>0? 100.0*((PositionSelectByTicket(pTicket)?
                (SymbolInfoDouble(_Symbol,pDir>0?SYMBOL_BID:SYMBOL_ASK)-pEntry)*pDir:0.0)/pPeak):0.0));
   Txt("SMC_pos_t", t2, pEntry, txt, pDir>0?clrAquamarine:clrLightPink);
}

void Rect(string n,datetime t1,double p1,datetime t2,double p2,color c)
{
   if(ObjectFind(0,n)<0) ObjectCreate(0,n,OBJ_RECTANGLE,0,t1,p1,t2,p2);
   else { ObjectMove(0,n,0,t1,p1); ObjectMove(0,n,1,t2,p2); }
   ObjectSetInteger(0,n,OBJPROP_COLOR,c);
   ObjectSetInteger(0,n,OBJPROP_FILL,true);
   ObjectSetInteger(0,n,OBJPROP_BACK,true);
}
void HLine(string n,double p,color c,int st,int w)
{
   if(ObjectFind(0,n)<0) ObjectCreate(0,n,OBJ_HLINE,0,0,p);
   else ObjectMove(0,n,0,0,p);
   ObjectSetInteger(0,n,OBJPROP_COLOR,c);
   ObjectSetInteger(0,n,OBJPROP_STYLE,st);
   ObjectSetInteger(0,n,OBJPROP_WIDTH,w);
}
void Txt(string n,datetime t,double p,string s,color c)
{
   if(ObjectFind(0,n)<0) ObjectCreate(0,n,OBJ_TEXT,0,t,p);
   else ObjectMove(0,n,0,t,p);
   ObjectSetString(0,n,OBJPROP_TEXT,s);
   ObjectSetInteger(0,n,OBJPROP_COLOR,c);
   ObjectSetInteger(0,n,OBJPROP_FONTSIZE,8);
}

//--- nearest two live pools each side. Two, not forty: a chart with every
//--- level on it carries the same information as a chart with none.
void DrawLevels()
{
   ObjectsDeleteAll(0, "SMC_lv");
   if(!InpDrawLevels) return;
   double px = iClose(_Symbol,_Period,1);
   for(int side = -1; side <= 1; side += 2)
   {
      double prev = (side > 0) ? px : px;
      for(int pass = 0; pass < 2; pass++)
      {
         int bi = -1; double b = 0.0;
         int cnt = (side > 0) ? hiN : loN;
         for(int i = 0; i < cnt; i++)
         {
            bool dead = (side > 0) ? hiDead[i] : loDead[i];
            double v  = (side > 0) ? hiLv[i]   : loLv[i];
            if(dead) continue;
            bool ahead = (side > 0) ? (v > prev) : (v < prev);
            if(!ahead) continue;
            if(bi < 0 || ((side > 0) ? (v < b) : (v > b))) { b = v; bi = i; }
         }
         if(bi < 0) break;
         int touch = (side > 0) ? hiTouch[bi] : loTouch[bi];
         bool react = (touch >= InpReactTouch);
         int between = LevelsBetween(b, side);
         string nm = StringFormat("SMC_lv_%d_%d", side, pass);
         if(ObjectFind(0, nm) < 0) ObjectCreate(0, nm, OBJ_HLINE, 0, 0, b);
         else ObjectMove(0, nm, 0, 0, b);
         ObjectSetInteger(0, nm, OBJPROP_COLOR, side > 0 ? clrIndianRed : clrMediumSeaGreen);
         ObjectSetInteger(0, nm, OBJPROP_STYLE, react ? STYLE_SOLID : STYLE_DOT);
         ObjectSetInteger(0, nm, OBJPROP_WIDTH, react ? 2 : 1);
         ObjectSetString(0, nm, OBJPROP_TEXT,
            StringFormat("%s %.2f  %s%s", (side > 0 ? "BSL" : "SSL"), b,
                         (between > InpMaxBetween ? "HRL" : "LRL"),
                         (react ? "  ***" : "")));
         prev = b;
      }
   }
}

void DrawPanel()
{
   int ti=-1;
   double up=NearestPool(1,ti); int upN=(ti>=0)?LevelsBetween(up,1):0; bool haveUp=(ti>=0);
   double dn=NearestPool(-1,ti); int dnN=(ti>=0)?LevelsBetween(dn,-1):0; bool haveDn=(ti>=0);
   double kept=(sumPeak>0)?100.0*sumPts/sumPeak:0.0;
   string s=StringFormat(
     "%s   %s %s\n"
     "regime %s (ER %.3f)   bias %s\n"
     "BSL %.2f  %s   SSL %.2f  %s\n"
     "trades %d  win %.0f%%  net %.1f pts\n"
     "peak pool %.1f  KEPT %.0f%%\n"
     "session %+.2f%%   day %+.2f%%\n"
     "refused: room %d  confluence %d  RR %d  spread %d\n"
     "%s",
     SMC_BUILD,_Symbol,EnumToString((ENUM_TIMEFRAMES)_Period),
     Regime(),EfficiencyRatio(),
     (gBias>0?"bullish":(gBias<0?"bearish":"none")),
     haveUp?up:0.0,(upN>InpMaxBetween?"HRL":"LRL"),
     haveDn?dn:0.0,(dnN>InpMaxBetween?"HRL":"LRL"),
     nT,(nT>0?100.0*nWin/nT:0.0),sumPts,sumPeak,kept,
     (gStart>0?(AccountInfoDouble(ACCOUNT_EQUITY)-gStart)/gStart*100.0:0.0),
     (gDayStart>0?(AccountInfoDouble(ACCOUNT_EQUITY)-gDayStart)/gDayStart*100.0:0.0),
     nRefRoom,nRefConf,nRefRR,nRefSpread,
     gHalt?("HALTED "+gHaltWhy):"trading");
   string n="SMC_panel";
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
   ObjectSetInteger(0,n,OBJPROP_COLOR,gHalt?clrTomato:clrGainsboro);
   ObjectSetString(0,n,OBJPROP_TEXT,s);
   ChartRedraw(0);
}
//+------------------------------------------------------------------+

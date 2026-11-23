//+------------------------------------------------------------------+
//|  XAUUSD_LEAN.mq5   v1.00                                         |
//|                                                                  |
//|  A deliberately small, auditable replacement for XAUUSD_QUAD      |
//|  (19,662 lines, 715 inputs, 23 racing exits, >=49 inputs that     |
//|  only ever executed in dead code).                                |
//|                                                                  |
//|  DESIGN RULES — each one answers a specific measured failure:     |
//|   1. ONE entry door. SendEntry() is the only function in this     |
//|      file that opens a position. QUAD had six Open() sites and    |
//|      three more order senders that bypassed its own guards.       |
//|   2. ONE exit manager. DecideExit() returns AT MOST ONE action    |
//|      from an ordered list. QUAD evaluated 23 exits per tick, so   |
//|      the trade died on whichever fired first and fixing one just  |
//|      promoted the next.                                           |
//|   3. The protective stop lives at the BROKER, attached at entry.  |
//|      It is never re-evaluated in the tick loop, so it cannot      |
//|      race anything.                                               |
//|   4. Per-ticket state in ONE array with an explicit lifecycle.    |
//|      No ring buffer that wraps and silently loses a live trade.   |
//|   5. EVERY input below is read by the code. Verified by script.   |
//|   6. Every threshold is in NAMED UNITS and carries the            |
//|      measurement that justifies it, or is OFF and says so.        |
//|   7. Anything not justified by a measurement ships DISABLED.      |
//|                                                                  |
//|  MEASUREMENT THIS WAS BUILT FROM (3.83M real broker M1 bars,      |
//|  2016-2026, real per-bar spread; see research/FINDINGS.md):       |
//|   * ON M1 THE SUPERTREND FLIP IS MEASURABLY WORSE THAN A COIN     |
//|     FLIP. Gross, before any cost, over 283,251 trades (2019+):    |
//|     -0.030 pt/trade, t = -5.44. It is not merely uninformative,   |
//|     it is anti-predictive: the band crossing systematically buys  |
//|     the top of the move and sells the bottom.                     |
//|   * Forward return after a flip, 10 horizons from 1m to 240m:     |
//|     every |t| < 0.95. No information at any horizon.              |
//|   * 93% of the realised loss is spread.                           |
//|   * 38 exit variants tested; NONE passed a pre-registered         |
//|     acceptance test. Every early cut removed a LARGER share of    |
//|     winning points than of losing points.                         |
//|                                                                  |
//|  CORRECTED IN v1.30 — the owner spotted a real gap: that sweep    |
//|  only had profit LOCKS and TARGETS, never a true BREAK-EVEN. It   |
//|  turns out to matter more than anything else tested. At his real  |
//|  broker spread, per trade, 93,391 trades:                         |
//|     nothing                        -0.362                         |
//|     break-even 0.10 ATR            -0.179                         |
//|     + trail 0.25 ATR from +0.5     -0.075                         |
//|  So break-even + trail removes 79% of the loss. Both are now ON.  |
//|                                                                  |
//|  BUT TWO THINGS KEEP IT FROM BEING AN EDGE:                       |
//|   a) A COIN FLIP GETS ALMOST ALL OF IT. Same entry bars, same     |
//|      exits, direction randomised: -0.099 vs the signal's -0.075.  |
//|      The Supertrend's direction is worth +0.024 pt/trade, about   |
//|      7% of one spread. The exit rule is doing the work, not the   |
//|      indicator.                                                  |
//|   b) WITH A TRAIL, ~100% OF TRADES EXIT ON A STOP, so slippage    |
//|      becomes a straight per-trade tax. 0.29 pt of average stop    |
//|      slippage erases the entire +0.287 gain. That number is NOT   |
//|      in any dataset I have, so v1.30 MEASURES it: see the panel   |
//|      line "avg slippage" and the journal's slip_pts column.      |
//|   * Net points rise monotonically with ATR and cross zero at      |
//|     ATR ~1.63 at a 0.320 spread (slope t = 38.4, sign agrees in   |
//|     both walk-forward halves). A volatility CONDITION is the one  |
//|     untested idea with a real basis -- but it is a signal filter, |
//|     so it is NOT in this build. Owner decides that one.           |
//|   * The edge improves monotonically with timeframe and is only    |
//|     non-negative at H1/H4 (gross t = +1.88 / +1.17 — suggestive,  |
//|     still not significant).                                       |
//|   => break-even and the trail are ON; targets and locks stay OFF. |
//|      On the Supertrend signal this EA is still expected to        |
//|      LOSE MONEY, just far more slowly than v1.10 did. It is a     |
//|      trustworthy chassis, not a profitable strategy. Do not run   |
//|      it live expecting profit until a signal with measured edge   |
//|      is fitted in Signal_Compute().                               |
//+------------------------------------------------------------------+
#property copyright "personal"
#property version   "1.30"
#define EA_BUILD "LEAN v1.30"

#include <Trade/Trade.mqh>
CTrade  trade;

//==================== INPUTS =======================================
input group "=== SIGNAL (Pine parity: XAUUSD CLEAN rebuilt) ==="
input ENUM_TIMEFRAMES InpTF         = PERIOD_M1;  // signal timeframe
input double InpStMult              = 1.2;        // Supertrend multiplier (Pine stMult)
input int    InpStAtrLen            = 7;          // Supertrend ATR length (Pine stLen)
input int    InpWarmupBars          = 1000;       // bars used to converge the Supertrend chain.
                                                  // RMA converges by (n-1)/n per bar, so 1000 bars
                                                  // is exact to double precision for ATR 7.
input bool   InpDemaFilter          = false;      // require price on the DEMA side of the trade.
                                                  // MEASURED: no help (t=-1.96, wrong sign). OFF.
input int    InpDemaLen             = 60;         // Pine uses 60 on M1, 100 on M3, else 200

input group "=== RISK — hard limits, nothing can bypass these ==="
input double InpLots                = 0.01;       // fixed size. 0.01 on a 50 GBP account.
input int    InpMaxOpenPositions    = 1;          // signals alternate, so 1 is the natural cap
input double InpMaxSpreadUSD        = 1.00;       // refuse a NEW entry above this. Median real
                                                  // spread is 0.16-0.28, so 0.60 only blocks a
                                                  // genuinely blown spread. Set 999 to disable.
input double InpMaxDailyLoss        = 10.0;       // halt new entries for the day past this. 0=off
input bool   InpCloseAllOnHalt      = false;      // false = let open trades finish on their stop
input double InpMarginFloorPct      = 40.0;       // keep this % of equity as free margin. 0=off
input double InpStopAtrMult         = 1.5;        // stop distance = this x ATR(InpStAtrLen)
input double InpStopMinUSD          = 1.00;       // floor, in dollars of gold
input double InpStopMaxUSD          = 8.00;       // ceiling, in dollars of gold
input double InpMoneyPerPtPerLot    = 0.0;        // account currency per 1.00 gold move per 1.00
                                                  // lot. 0 = READ IT FROM THE SYMBOL (correct on
                                                  // any broker/account currency). Only override
                                                  // if the panel's money column looks wrong.

input group "=== EXITS — break-even + trail ON: measured, see header ==="
input bool   InpExitOnFlip          = true;       // exit when the opposite signal confirms.
                                                  // This IS the strategy's own exit. Keep ON.
input double InpBreakEvenAtr        = 0.10;       // once PEAK profit reaches this x ATR, move the
                                                  // stop to the FILL PRICE. True break-even: caps
                                                  // the loss, leaves the upside wide open. That is
                                                  // why it beats a target, which also amputates
                                                  // the 6.7% of trades that carry everything.
                                                  // MEASURED 0.10 best of 0.05-1.00. 0 = off.
input double InpBreakEvenCushUSD    = 0.0;        // extra dollars ABOVE break-even to park the stop.
                                                  // 0 = the fill price itself, which is exactly
                                                  // flat. v1.20 wrongly added a spread here: a long
                                                  // fills at ASK and exits on BID, so P/L = exit -
                                                  // fill and a stop AT the fill is already flat.
                                                  // That error booked +0.32pt that never filled.
input double InpTrailAtrMult        = 0.25;       // chandelier trail in ATR, from the peak.
                                                  // MEASURED: with break-even, this is what takes
                                                  // -0.362 to -0.075 pt/trade. 0 = off.
input double InpTrailArmUSD         = 0.0;        // ...arms past this gain in dollars (0 = ignore)
input double InpTrailArmAtr         = 0.50;       // ...or past this x ATR. The LARGER of the two
                                                  // applies, so both inputs bite.
input double InpLockArmUSD          = 0.0;        // profit lock (arm X, give back Y): OFF. Strictly
input double InpLockGiveUSD         = 0.0;        // worse than break-even in every test.
input double InpTargetUSD           = 0.0;        // fixed target. 0=off (measured strictly worse:
                                                  // tighter target = higher win rate = smaller
                                                  // average win, and the product gets WORSE)
input int    InpMaxHoldBars         = 0;          // time stop in signal-TF bars. 0=off

input group "=== DIAGNOSTICS ==="
input bool   InpJournal             = true;       // append every closed trade to CSV
input bool   InpPanel               = true;       // on-chart panel
input int    InpPanelFont           = 9;          // panel font size
input bool   InpVerbose             = true;       // log every decision
input bool   InpParityExport        = false;      // ONE-SHOT: dump per-bar signal state to CSV
input int    InpParityBars          = 20000;      // how many bars to dump
input long   InpMagic               = 990001;

//==================== STATE ========================================
// Rule 4: ONE state array, explicit lifecycle, never silently overwritten.
#define MAXPOS 8
struct PosState
{
   ulong    ticket;
   bool     live;
   int      dir;          // +1 long, -1 short
   double   entry;        // actual fill
   double   stop;         // current protective level (broker-side)
   double   atr;          // ATR at entry
   double   spreadIn;     // spread at entry
   datetime opened;
   int      barsHeld;
   double   mfe;          // best favourable excursion, USD
   double   mae;          // worst adverse excursion, USD
   double   peak;         // == mfe, kept separate for lock arithmetic
   bool     beArmed;      // break-even stop has been placed
   bool     trArmed;      // trail has been placed
};
PosState  g_pos[MAXPOS];

double    g_tickVal = 0, g_tickSz = 0, g_lotStep = 0, g_lotMin = 0, g_lotMax = 0;
double    g_minStopDist = 0;
int       g_digits = 2;

// signal state for the last CLOSED bar
int       g_dir = 0, g_prevDir = 0;
double    g_stLevel = 0, g_atr = 0, g_dema = 0;
bool      g_sigBuy = false, g_sigSell = false;
datetime  g_lastSigBar = 0;

// daily accounting
int       g_day = -1;
double    g_dayStartEquity = 0, g_dayPts = 0;
int       g_dayTrades = 0;
bool      g_halted = false;

// --- THE DIAGNOSTIC BOOK: how much gold moved vs how much we took of it ---
// dayOffered = sum of each closed trade's PEAK favourable excursion (what our trades
//              actually put on the table). dayPts = what we realised.
// capture% = realised / offered. That single number separates "the signal offered
// nothing" from "we captured it badly", which is the question this panel exists for.
double    g_dayOffered = 0;          // pt
double    g_dayRangeHi = 0, g_dayRangeLo = 0;   // how far gold travelled, high-low
double    g_dayPath = 0;             // total absolute bar-to-bar travel today, pt
datetime  g_dayPathBar = 0;
double    g_dayPrevClose = 0;

int       g_totTrades = 0;
double    g_totPts = 0, g_totOffered = 0;

// refusal visibility: a silent refusal is how QUAD looked "not trading" for weeks
int       g_refused = 0;
string    g_lastRefusal = "";
int       g_signalsSeen = 0;

// peak of a position, stashed when its slot is freed so OnTradeTransaction can pair the
// realised points (exact, from history) with the peak (only known while it was open).
#define PENDN 64
ulong     g_pendId[PENDN];
double    g_pendPeak[PENDN];
double    g_pendStop[PENDN];    // last protective level, to measure fill slippage
bool      g_pendBe[PENDN];
bool      g_pendTr[PENDN];
int       g_pendW = 0;

void StashPeak(ulong id, double peak, double stop, bool be, bool tr)
{
   int k = g_pendW % PENDN;
   g_pendId[k] = id; g_pendPeak[k] = peak; g_pendStop[k] = stop;
   g_pendBe[k] = be; g_pendTr[k] = tr;
   g_pendW++;
}
double TakePeak(ulong id, bool &found, double &stop, bool &be, bool &tr)
{
   for(int i = 0; i < PENDN; i++)
      if(g_pendId[i] == id)
      {
         found = true; g_pendId[i] = 0;
         stop = g_pendStop[i]; be = g_pendBe[i]; tr = g_pendTr[i];
         return g_pendPeak[i];
      }
   found = false; stop = 0.0; be = false; tr = false;
   return 0.0;
}

//---- SLIPPAGE: the number that decides whether the trail is worth having.
// With a trail, essentially EVERY trade exits on a stop, so every point of slippage
// is a point per trade. Research says the whole break-even+trail gain (+0.287 pt) is
// erased by 0.29 pt of average slippage. So we measure it instead of assuming it.
double g_slipSum = 0.0; int g_slipN = 0; double g_slipWorst = 0.0;

string    g_jrnl = "";
bool      g_parityDone = false;
bool      g_firstEval = true;

//==================== HELPERS ======================================
double NP(double p) { return NormalizeDouble(p, g_digits); }
double AskPx()      { return SymbolInfoDouble(_Symbol, SYMBOL_ASK); }
double BidPx()      { return SymbolInfoDouble(_Symbol, SYMBOL_BID); }
double SpreadUSD()  { double a=AskPx(), b=BidPx(); return (a>0 && b>0 && a>b) ? a-b : 0.0; }
// Money per 1.00 of gold price movement, at InpLots, in the ACCOUNT's own currency.
// Derived from the symbol so it is right on any broker without being told.
double MoneyPerPt()
{
   if(InpMoneyPerPtPerLot > 0.0) return InpMoneyPerPtPerLot * InpLots;
   if(g_tickSz > 0.0 && g_tickVal > 0.0) return (g_tickVal / g_tickSz) * InpLots;
   return 0.0;
}
string Ccy() { return AccountInfoString(ACCOUNT_CURRENCY); }

void Log(string s) { if(InpVerbose) Print("[", EA_BUILD, "] ", s); }

int FreeSlot()
{
   for(int i=0; i<MAXPOS; i++) if(!g_pos[i].live) return i;
   return -1;
}
int SlotOf(ulong tk)
{
   for(int i=0; i<MAXPOS; i++) if(g_pos[i].live && g_pos[i].ticket==tk) return i;
   return -1;
}
int LiveCount()
{
   int n=0;
   for(int i=0; i<MAXPOS; i++) if(g_pos[i].live) n++;
   return n;
}
void ReleaseSlot(int i)
{
   if(i < 0 || i >= MAXPOS) return;
   if(g_pos[i].live && g_pos[i].ticket != 0)
      StashPeak(g_pos[i].ticket, g_pos[i].mfe, g_pos[i].stop,
                g_pos[i].beArmed, g_pos[i].trArmed);   // peak+stop, for slippage measurement
   g_pos[i].live = false;
   g_pos[i].ticket = 0;
}

//==================== SIGNAL =======================================
// Rule: ONE small function. Swap this to change strategy; nothing else moves.
//
// Faithful transcription of TradingView's published ta.supertrend, which is what
// XAUUSD_CLEAN uses. Verified bar-for-bar against a Python transcription of the
// same reference on 3.8M bars.
//
//   src = hl2 ; atr = ta.atr(len)          [ = RMA of true range ]
//   upperBand = src + f*atr ; lowerBand = src - f*atr
//   lowerBand := lowerBand > prevLower or close[1] < prevLower ? lowerBand : prevLower
//   upperBand := upperBand < prevUpper or close[1] > prevUpper ? upperBand : prevUpper
//   if na(atr[1])                     direction := 1
//   else if prevSuperTrend==prevUpper direction := close > upperBand ? -1 : 1
//   else                              direction := close < lowerBand ?  1 : -1
//   superTrend := direction==-1 ? lowerBand : upperBand
//
// DIRECTION CONVENTION: -1 == UPTREND (line below price). Pine's own signal is
//   buy  = dir==-1 && dir[1]== 1
//   sell = dir== 1 && dir[1]==-1
// Computed on CLOSED bars only (shift 1 is the newest bar used), so no repaint.
bool Signal_Compute(int &dirOut, int &prevDirOut, double &stOut,
                    double &atrOut, double &demaOut)
{
   int need = MathMax(60, InpWarmupBars);
   MqlRates r[];
   ArraySetAsSeries(r, false);                 // r[0] = OLDEST
   int got = CopyRates(_Symbol, InpTF, 1, need, r);
   if(got < MathMax(InpStAtrLen + 10, 60))
   {
      Log(StringFormat("signal: only %d bars available, need %d. Waiting for history.",
                        got, MathMax(InpStAtrLen+10, 60)));
      return false;
   }

   int n = got;
   int L = InpStAtrLen;

   // --- true range, Pine ta.tr(true): first bar falls back to high-low
   double tr[];  ArrayResize(tr, n);
   tr[0] = r[0].high - r[0].low;
   for(int i=1; i<n; i++)
   {
      double pc = r[i-1].close;
      double a = r[i].high - r[i].low;
      double b = MathAbs(r[i].high - pc);
      double c = MathAbs(r[i].low  - pc);
      tr[i] = MathMax(a, MathMax(b, c));
   }

   // --- ta.rma: na until L-1, SMA seed at L-1, Wilder thereafter
   double atr[]; ArrayResize(atr, n);
   bool   atrOk[]; ArrayResize(atrOk, n);
   for(int i=0; i<n; i++) { atr[i]=0.0; atrOk[i]=false; }
   if(n <= L) return false;
   double s = 0.0;
   for(int i=0; i<L; i++) s += tr[i];
   atr[L-1] = s / L; atrOk[L-1] = true;
   for(int i=L; i<n; i++)
   {
      atr[i] = atr[i-1] + (tr[i] - atr[i-1]) / L;   // == (prev*(L-1)+tr)/L
      atrOk[i] = true;
   }

   // --- the Supertrend chain
   double prevLb = 0.0, prevUb = 0.0;   // Pine nz() on the first bar
   double prevSt = 0.0, prevUbFinal = 0.0;
   bool   havePrevSt = false;
   int    d = 1, dPrev = 1;
   double stLevel = 0.0;

   for(int i=0; i<n; i++)
   {
      double mid = (r[i].high + r[i].low) / 2.0;
      bool   aOk = atrOk[i];
      double lb = aOk ? mid - InpStMult*atr[i] : 0.0;
      double ub = aOk ? mid + InpStMult*atr[i] : 0.0;
      bool   pcOk = (i > 0);
      double pc = pcOk ? r[i-1].close : 0.0;

      // lowerBand := lb > prevLb or close[1] < prevLb ? lb : prevLb
      bool condL = (aOk && lb > prevLb) || (pcOk && pc < prevLb);
      double newLb = condL ? lb : prevLb;
      // upperBand := ub < prevUb or close[1] > prevUb ? ub : prevUb
      bool condU = (aOk && ub < prevUb) || (pcOk && pc > prevUb);
      double newUb = condU ? ub : prevUb;

      dPrev = d;
      bool atrPrevNa = (i == 0) || (!atrOk[i-1]);
      if(atrPrevNa)                                   d = 1;
      else if(havePrevSt && prevSt == prevUbFinal)     d = (r[i].close > newUb) ? -1 : 1;
      else                                             d = (r[i].close < newLb) ?  1 : -1;

      stLevel = (d == -1) ? newLb : newUb;

      prevLb = newLb; prevUb = newUb;
      prevUbFinal = newUb; prevSt = stLevel; havePrevSt = true;
   }

   // --- DEMA (plotted in Pine; only used if InpDemaFilter is on)
   double dema = 0.0;
   int DL = InpDemaLen;
   if(n > DL*2 + 2)
   {
      double e1[]; ArrayResize(e1, n);
      double a = 2.0/(DL+1.0);
      double acc = 0.0;
      for(int i=0; i<DL; i++) acc += r[i].close;
      acc /= DL;
      for(int i=0; i<DL-1; i++) e1[i] = 0.0;
      e1[DL-1] = acc;
      for(int i=DL; i<n; i++) { acc = a*r[i].close + (1.0-a)*acc; e1[i] = acc; }
      double acc2 = 0.0;
      for(int i=DL-1; i<DL-1+DL; i++) acc2 += e1[i];
      acc2 /= DL;
      for(int i=DL-1+DL; i<n; i++) acc2 = a*e1[i] + (1.0-a)*acc2;
      dema = 2.0*e1[n-1] - acc2;
   }

   dirOut = d; prevDirOut = dPrev; stOut = stLevel;
   atrOut = atrOk[n-1] ? atr[n-1] : 0.0; demaOut = dema;
   return true;
}

//==================== PARITY EXPORT ================================
// Writes per-bar signal state so it can be diffed against the Python engine.
// This is how Pine/EA parity gets PROVEN instead of assumed — the single thing
// that was never done for QUAD.
void ParityExport()
{
   if(!InpParityExport || g_parityDone) return;
   int need = InpParityBars + InpWarmupBars;
   MqlRates r[]; ArraySetAsSeries(r, false);
   int got = CopyRates(_Symbol, InpTF, 1, need, r);
   if(got < InpWarmupBars + 100) { Log("parity: not enough history"); return; }

   string fn = StringFormat("parity_%s_%s.csv", _Symbol, EnumToString(InpTF));
   int fh = FileOpen(fn, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
   if(fh == INVALID_HANDLE) { Log("parity: cannot open file"); return; }
   FileWrite(fh, "time", "open", "high", "low", "close", "dir", "st");

   int L = InpStAtrLen;
   double prevLb=0, prevUb=0, prevSt=0, prevUbF=0; bool havePrevSt=false;
   int d=1;
   double tr, atr=0; bool atrOk=false; int cnt=0; double seed=0;
   for(int i=0; i<got; i++)
   {
      if(i==0) tr = r[0].high - r[0].low;
      else
      {
         double pc=r[i-1].close;
         tr = MathMax(r[i].high-r[i].low, MathMax(MathAbs(r[i].high-pc), MathAbs(r[i].low-pc)));
      }
      bool atrPrevNa = !atrOk;
      if(!atrOk) { seed += tr; cnt++; if(cnt==L) { atr=seed/L; atrOk=true; } }
      else atr = atr + (tr-atr)/L;

      double mid=(r[i].high+r[i].low)/2.0;
      double lb = atrOk ? mid-InpStMult*atr : 0.0;
      double ub = atrOk ? mid+InpStMult*atr : 0.0;
      bool pcOk=(i>0); double pc = pcOk ? r[i-1].close : 0.0;
      bool condL=(atrOk && lb>prevLb)||(pcOk && pc<prevLb);
      double newLb= condL?lb:prevLb;
      bool condU=(atrOk && ub<prevUb)||(pcOk && pc>prevUb);
      double newUb= condU?ub:prevUb;
      if(atrPrevNa)                               d=1;
      else if(havePrevSt && prevSt==prevUbF)      d=(r[i].close>newUb)?-1:1;
      else                                        d=(r[i].close<newLb)? 1:-1;
      double st=(d==-1)?newLb:newUb;
      prevLb=newLb; prevUb=newUb; prevUbF=newUb; prevSt=st; havePrevSt=true;

      if(i >= InpWarmupBars)
         FileWrite(fh, (string)r[i].time, DoubleToString(r[i].open,3),
                   DoubleToString(r[i].high,3), DoubleToString(r[i].low,3),
                   DoubleToString(r[i].close,3), (string)d, DoubleToString(st,5));
   }
   FileClose(fh);
   g_parityDone = true;
   PrintFormat("[%s] PARITY EXPORT written: MQL5/Files/%s  (%d bars)", EA_BUILD, fn,
               got-InpWarmupBars);
}

//==================== RISK GATES ===================================
bool MarginOkFor(double lots, int dir)
{
   if(InpMarginFloorPct <= 0.0) return true;
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double free = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   if(eq <= 0) return true;
   double need = 0;
   ENUM_ORDER_TYPE ot = (dir>0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double px = (dir>0) ? AskPx() : BidPx();
   if(!OrderCalcMargin(ot, _Symbol, lots, px, need)) return true;
   double floorCash = eq * InpMarginFloorPct / 100.0;
   if((free - need) < floorCash)
   {
      Log(StringFormat("REFUSED: margin. %.2f lots needs %.2f, free %.2f, floor %.2f",
                        lots, need, free, floorCash));
      return false;
   }
   return true;
}

double StopDistance()
{
   double d = InpStopAtrMult * g_atr;
   if(d < InpStopMinUSD) d = InpStopMinUSD;
   if(d > InpStopMaxUSD) d = InpStopMaxUSD;
   double sp = SpreadUSD();
   if(d < 3.0*sp) d = 3.0*sp;      // a stop inside 3x the spread is taken by the spread itself
   if(d < g_minStopDist) d = g_minStopDist;
   return d;
}

//==================== THE ONE ENTRY DOOR ===========================
// Rule 1: this is the ONLY function in this file that opens a position.
void Refuse(string reason)
{
   g_refused++;
   g_lastRefusal = reason;
   Log("REFUSED: " + reason);
}

bool SendEntry(int dir, string why)
{
   if(dir == 0) return false;

   if(g_halted)                       { Refuse("daily loss halt"); return false; }
   if(LiveCount() >= InpMaxOpenPositions)
                                      { Refuse("position cap"); return false; }
   int slot = FreeSlot();
   if(slot < 0)                       { Refuse("no state slot"); return false; }

   double sp = SpreadUSD();
   if(sp > InpMaxSpreadUSD)
   { Refuse(StringFormat("spread %.3f > cap %.3f", sp, InpMaxSpreadUSD)); return false; }

   if(InpDemaFilter && g_dema > 0.0)
   {
      double px = (dir>0) ? AskPx() : BidPx();
      bool ok = (dir>0) ? (px > g_dema) : (px < g_dema);
      if(!ok) { Refuse("DEMA filter"); return false; }
   }

   if(g_atr <= 0.0)                   { Refuse("no ATR yet"); return false; }
   if(!MarginOkFor(InpLots, dir))     { Refuse("margin floor"); return false; }

   double lots = InpLots;
   if(g_lotStep > 0) lots = MathFloor(lots/g_lotStep)*g_lotStep;
   if(lots < g_lotMin) lots = g_lotMin;
   if(g_lotMax > 0 && lots > g_lotMax) lots = g_lotMax;

   double px   = (dir>0) ? AskPx() : BidPx();
   double dist = StopDistance();
   double sl   = (dir>0) ? px - dist : px + dist;

   trade.SetExpertMagicNumber(InpMagic);
   // slippage tolerance scaled to the live spread, not a fixed point count (a fixed 40
   // points is 0.40 on a 2-digit symbol but only 0.04 on a 3-digit one -> requotes)
   int dev = (int)MathMax(40.0, 3.0 * SpreadUSD() / _Point);
   trade.SetDeviationInPoints(dev);
   bool ok = (dir>0) ? trade.Buy (lots, _Symbol, 0.0, NP(sl), 0.0, "LEAN")
                     : trade.Sell(lots, _Symbol, 0.0, NP(sl), 0.0, "LEAN");
   if(!ok)
   {
      Refuse(StringFormat("broker rejected: %d %s", trade.ResultRetcode(),
                          trade.ResultRetcodeDescription()));
      return false;
   }

   // --- resolve the POSITION ticket, not the deal ticket.
   // ResultDeal() is a DEAL id. If the history lookup that converts it to a position id
   // fails (it can lag the fill), storing the deal id means PositionSelectByTicket()
   // later fails and ManageOpen() abandons a LIVE position believing it had closed.
   // So: try the deal -> position mapping, then fall back to scanning for our own
   // newest untracked position, and refuse to record anything we cannot verify.
   ulong tk = 0;
   ulong deal = trade.ResultDeal();
   if(deal > 0 && HistoryDealSelect(deal))
      tk = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
   if(tk == 0 || !PositionSelectByTicket(tk))
   {
      tk = 0;
      datetime newest = 0;
      for(int pi = PositionsTotal()-1; pi >= 0; pi--)
      {
         ulong t2 = PositionGetTicket(pi);
         if(t2 == 0 || !PositionSelectByTicket(t2)) continue;
         if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
         if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
         if(SlotOf(t2) >= 0) continue;                  // already tracked by another slot
         datetime ot = (datetime)PositionGetInteger(POSITION_TIME);
         if(ot >= newest) { newest = ot; tk = t2; }
      }
   }
   if(tk == 0)
   {
      Refuse("order filled but the position ticket could not be resolved - NOT tracked. "
             "Close it by hand if one opened.");
      return false;
   }
   // the broker's own fill price beats ResultPrice()
   double fill = px;
   if(PositionSelectByTicket(tk))
   {
      double po = PositionGetDouble(POSITION_PRICE_OPEN);
      if(po > 0) fill = po;
   }
   else
   {
      double rp = trade.ResultPrice();
      if(rp > 0) fill = rp;
   }

   g_pos[slot].ticket   = tk;
   g_pos[slot].live     = true;
   g_pos[slot].dir      = dir;
   g_pos[slot].entry    = fill;
   g_pos[slot].stop     = NP(sl);
   g_pos[slot].atr      = g_atr;
   g_pos[slot].spreadIn = sp;
   g_pos[slot].opened   = TimeCurrent();
   g_pos[slot].barsHeld = 0;
   g_pos[slot].mfe = 0; g_pos[slot].mae = 0; g_pos[slot].peak = 0;
   g_pos[slot].beArmed = false; g_pos[slot].trArmed = false;

   g_dayTrades++;
   PrintFormat("[%s] OPEN %s #%I64u %.2f lots @ %.3f  stop %.3f (%.2f USD = %.2f x ATR)  "
               "spread %.3f  risk %.2f %s  | %s",
               EA_BUILD, dir>0?"BUY":"SELL", tk, lots, fill, sl, dist, dist/g_atr,
               sp, dist*MoneyPerPt(), Ccy(), why);
   return true;
}

//==================== THE ONE EXIT MANAGER =========================
// Rule 2: returns AT MOST ONE action, from an explicitly ordered list.
// The protective stop is broker-side and is NOT in this list, so it can never
// race these. Optional exits all default to OFF because they measured worthless.
string DecideExit(int i)
{
   int d = g_pos[i].dir;
   double px = (d>0) ? BidPx() : AskPx();       // the price we could exit AT
   double gain = (px - g_pos[i].entry) * d;

   // 1. the strategy's own exit: the opposite signal confirmed on a closed bar
   if(InpExitOnFlip && g_dir != 0 && g_dir != ((d>0) ? -1 : 1))
      return "FLIP";

   // 2. fixed target (OFF by default: measured strictly worse the tighter it got)
   if(InpTargetUSD > 0.0 && gain >= InpTargetUSD)
      return "TARGET";

   // 3. time stop (OFF by default)
   if(InpMaxHoldBars > 0 && g_pos[i].barsHeld >= InpMaxHoldBars)
      return "TIME";

   // 4. daily halt, only if the user asked for open trades to be flattened too
   if(g_halted && InpCloseAllOnHalt)
      return "HALT";

   return "";
}

// Stop ratcheting. Separate from DecideExit because it moves a level, it does not
// close anything. Only ever tightens. Both mechanisms default to OFF.
void RatchetStop(int i)
{
   int d = g_pos[i].dir;
   double px = (d>0) ? BidPx() : AskPx();
   double gain = (px - g_pos[i].entry) * d;
   double want = g_pos[i].stop;

   double lim0 = (d>0) ? px - g_minStopDist : px + g_minStopDist;   // placeable boundary

   // TRUE BREAK-EVEN, at the FILL PRICE. A long fills at ASK and exits on BID, so
   // P/L = exit - fill and a stop sitting AT the fill is exactly flat. v1.20 added a
   // spread on top, which asked the broker for a level price had not reached.
   if(InpBreakEvenAtr > 0.0 && g_pos[i].atr > 0.0
      && g_pos[i].peak >= InpBreakEvenAtr * g_pos[i].atr)
   {
      double be = g_pos[i].entry + d*InpBreakEvenCushUSD;
      // Arm ONLY once the level is placeable. Clamping an unplaceable break-even to the
      // broker minimum would park the stop on top of price -- a market exit in disguise.
      if((d>0 && be <= lim0) || (d<0 && be >= lim0))
      {
         want = (d>0) ? MathMax(want, be) : MathMin(want, be);
         if(!g_pos[i].beArmed)
         {
            g_pos[i].beArmed = true;
            Log(StringFormat("#%I64u BREAK-EVEN armed at %.3f (peak %.2f = %.2f x ATR)",
                g_pos[i].ticket, be, g_pos[i].peak, g_pos[i].peak/g_pos[i].atr));
         }
      }
   }
   if(InpLockArmUSD > 0.0 && g_pos[i].peak >= InpLockArmUSD)
   {
      double lvl = g_pos[i].entry + d*(g_pos[i].peak - InpLockGiveUSD);
      want = (d>0) ? MathMax(want, lvl) : MathMin(want, lvl);
   }
   // CHANDELIER TRAIL. Arms off the PEAK, never the current price, so once armed it stays
   // armed even if price pulls back.
   if(InpTrailAtrMult > 0.0 && g_pos[i].atr > 0)
   {
      double arm = MathMax(InpTrailArmUSD, InpTrailArmAtr*g_pos[i].atr);
      if(g_pos[i].peak >= arm)
      {
         double ext = g_pos[i].entry + d*g_pos[i].peak;
         double lvl = ext - d*InpTrailAtrMult*g_pos[i].atr;
         if((d>0 && lvl <= lim0) || (d<0 && lvl >= lim0))
         {
            want = (d>0) ? MathMax(want, lvl) : MathMin(want, lvl);
            if(!g_pos[i].trArmed)
            {
               g_pos[i].trArmed = true;
               Log(StringFormat("#%I64u TRAIL armed at %.3f (peak %.2f, arm %.2f)",
                   g_pos[i].ticket, lvl, g_pos[i].peak, arm));
            }
         }
      }
   }
   // never place a stop the wrong side of price, or inside the broker minimum
   double lim = (d>0) ? px - g_minStopDist : px + g_minStopDist;
   if(d>0 && want > lim) want = lim;
   if(d<0 && want < lim) want = lim;

   if(MathAbs(want - g_pos[i].stop) > _Point)
   {
      if(!PositionSelectByTicket(g_pos[i].ticket)) return;
      if(trade.PositionModify(g_pos[i].ticket, NP(want), PositionGetDouble(POSITION_TP)))
      {
         Log(StringFormat("stop #%I64u %.3f -> %.3f (locking %.2f USD)",
                           g_pos[i].ticket, g_pos[i].stop, want, (want-g_pos[i].entry)*d));
         g_pos[i].stop = NP(want);
      }
   }
}

void ManageOpen(bool newBar)
{
   for(int i=0; i<MAXPOS; i++)
   {
      if(!g_pos[i].live) continue;

      if(!PositionSelectByTicket(g_pos[i].ticket))     // closed by broker stop, or by hand
      { ReleaseSlot(i); continue; }

      int d = g_pos[i].dir;
      double px = (d>0) ? BidPx() : AskPx();
      double gain = (px - g_pos[i].entry) * d;
      if(gain > g_pos[i].mfe)  { g_pos[i].mfe = gain; g_pos[i].peak = gain; }
      if(-gain > g_pos[i].mae) { g_pos[i].mae = -gain; }
      if(newBar) g_pos[i].barsHeld++;

      string why = DecideExit(i);
      if(why != "")
      {
         double ptsNow = gain;
         if(trade.PositionClose(g_pos[i].ticket))
         {
            PrintFormat("[%s] CLOSE %s #%I64u  %+.2f pt (%+.2f %s)  peak %+.2f pt  "
                        "kept %.0f%% of peak",
                        EA_BUILD, why, g_pos[i].ticket, ptsNow, ptsNow*MoneyPerPt(), Ccy(),
                        g_pos[i].mfe, g_pos[i].mfe>0 ? 100.0*ptsNow/g_pos[i].mfe : 0.0);
            ReleaseSlot(i);
         }
         continue;
      }
      RatchetStop(i);
   }
}

//==================== DAILY ACCOUNTING =============================
void SeedDayStats()
{
   // scan today's bars once so the market numbers are right even when attached mid-session
   g_dayRangeHi = 0; g_dayRangeLo = 0; g_dayPath = 0; g_dayPrevClose = 0;
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   t.hour = 0; t.min = 0; t.sec = 0;
   datetime midnight = StructToTime(t);
   int bars = Bars(_Symbol, InpTF);
   int look = (int)MathMin(bars - 1, 3000);
   double prev = 0;
   for(int i = look; i >= 1; i--)              // oldest -> newest, closed bars only
   {
      datetime bt = iTime(_Symbol, InpTF, i);
      if(bt <= 0 || bt < midnight) { prev = 0; continue; }
      double hi = iHigh(_Symbol, InpTF, i), lo = iLow(_Symbol, InpTF, i);
      double cl = iClose(_Symbol, InpTF, i);
      if(hi <= 0 || lo <= 0) continue;
      if(g_dayRangeHi == 0 || hi > g_dayRangeHi) g_dayRangeHi = hi;
      if(g_dayRangeLo == 0 || lo < g_dayRangeLo) g_dayRangeLo = lo;
      if(prev > 0) g_dayPath += MathAbs(cl - prev);
      prev = cl;
      g_dayPathBar = bt;
   }
   g_dayPrevClose = prev;
}

void UpdateDayStats()
{
   // called once per NEW bar: extend today's range and total travelled path
   datetime bt = iTime(_Symbol, InpTF, 1);
   if(bt <= 0 || bt == g_dayPathBar) return;
   g_dayPathBar = bt;
   double hi = iHigh(_Symbol, InpTF, 1), lo = iLow(_Symbol, InpTF, 1);
   double cl = iClose(_Symbol, InpTF, 1);
   if(hi <= 0 || lo <= 0) return;
   if(g_dayRangeHi == 0 || hi > g_dayRangeHi) g_dayRangeHi = hi;
   if(g_dayRangeLo == 0 || lo < g_dayRangeLo) g_dayRangeLo = lo;
   if(g_dayPrevClose > 0) g_dayPath += MathAbs(cl - g_dayPrevClose);
   g_dayPrevClose = cl;
}

void DailyRoll()
{
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   if(t.day == g_day) return;
   g_day = t.day;
   g_dayStartEquity = AccountInfoDouble(ACCOUNT_BALANCE);
   g_dayPts = 0; g_dayTrades = 0; g_dayOffered = 0; g_halted = false;
   SeedDayStats();
   PrintFormat("[%s] --- new day --- balance %.2f %s", EA_BUILD, g_dayStartEquity, Ccy());
}

void CheckHalt()
{
   if(InpMaxDailyLoss <= 0.0 || g_halted) return;
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double lossGbp = g_dayStartEquity - eq;
   if(lossGbp >= InpMaxDailyLoss)
   {
      g_halted = true;
      PrintFormat("[%s] DAILY LOSS HALT: down %.2f %s (limit %.2f). No new entries today.",
                  EA_BUILD, lossGbp, Ccy(), InpMaxDailyLoss);
      if(InpCloseAllOnHalt) Log("flattening open trades (InpCloseAllOnHalt=true)");
   }
}

//==================== JOURNAL ======================================
void BookClose(ulong posId)
{
   if(!HistorySelectByPosition(posId)) return;
   int n = HistoryDealsTotal();
   double volIn=0, pxIn=0, volOut=0, pxOut=0, cash=0;
   datetime tIn=0, tOut=0; int dir=0;
   for(int i=0; i<n; i++)
   {
      ulong dk = HistoryDealGetTicket(i);
      if(dk==0) continue;
      double v = HistoryDealGetDouble(dk, DEAL_VOLUME);
      double p = HistoryDealGetDouble(dk, DEAL_PRICE);
      long   e = HistoryDealGetInteger(dk, DEAL_ENTRY);
      cash += HistoryDealGetDouble(dk, DEAL_PROFIT)
            + HistoryDealGetDouble(dk, DEAL_SWAP)
            + HistoryDealGetDouble(dk, DEAL_COMMISSION);
      if(e == DEAL_ENTRY_IN)
      {
         volIn += v; pxIn += p*v;
         if(dir==0) dir = (HistoryDealGetInteger(dk, DEAL_TYPE)==DEAL_TYPE_BUY) ? 1 : -1;
         if(tIn==0) tIn = (datetime)HistoryDealGetInteger(dk, DEAL_TIME);
      }
      else if(e == DEAL_ENTRY_OUT)
      {
         volOut += v; pxOut += p*v;
         tOut = (datetime)HistoryDealGetInteger(dk, DEAL_TIME);
      }
   }
   if(volIn<=0 || volOut<=0) return;
   double ein = pxIn/volIn, eout = pxOut/volOut;
   double pts = (eout - ein) * dir;            // realised, spread already inside the fills

   bool havePeak = false, wasBe = false, wasTr = false;
   double lastStop = 0.0;
   double peak = TakePeak(posId, havePeak, lastStop, wasBe, wasTr);
   if(peak < pts) peak = pts;                  // peak can never be below what we realised

   // Did we fill at the stop level, or worse? Only meaningful if the exit actually was
   // the stop, which we infer from the fill landing at or beyond the level.
   double slip = 0.0; bool stopHit = false;
   if(havePeak && lastStop > 0.0)
   {
      bool beyond = (dir>0) ? (eout <= lastStop + 0.5) : (eout >= lastStop - 0.5);
      if(beyond)
      {
         stopHit = true;
         slip = (lastStop - eout) * dir;       // positive = filled WORSE than the level
         g_slipSum += slip; g_slipN++;
         if(slip > g_slipWorst) g_slipWorst = slip;
      }
   }

   g_dayPts += pts;   g_totPts += pts;   g_totTrades++;
   if(havePeak) { g_dayOffered += peak; g_totOffered += peak; }

   PrintFormat("[%s] BOOKED #%I64u %s  took %+.2f pt of a %+.2f pt peak (%.0f%%)  %+.2f %s"
               "  [%s%s%s slip %+.3f]",
               EA_BUILD, posId, dir>0?"BUY":"SELL", pts, peak,
               peak>0 ? 100.0*pts/peak : 0.0, cash, Ccy(),
               wasBe?"BE ":"", wasTr?"TRAIL ":"", stopHit?"stop":"flip", slip);

   if(!InpJournal) return;
   if(g_jrnl == "") g_jrnl = StringFormat("lean_journal_%s.csv", _Symbol);
   int fh = FileOpen(g_jrnl, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
   if(fh == INVALID_HANDLE) return;
   bool fresh = (FileSize(fh)==0);
   FileSeek(fh, 0, SEEK_END);
   if(fresh)
      FileWrite(fh, "build","pos_id","dir","t_in","t_out","entry","exit",
                    "points","peak_points","capture_pct","money","secs_held",
                    "spread_now","atr_now","lots",
                    "stop_level","stop_hit","slip_pts","be_armed","trail_armed");
   FileWrite(fh, EA_BUILD, (string)posId, dir>0?"BUY":"SELL",
             TimeToString(tIn, TIME_DATE|TIME_SECONDS),
             TimeToString(tOut, TIME_DATE|TIME_SECONDS),
             DoubleToString(ein,3), DoubleToString(eout,3),
             DoubleToString(pts,3), DoubleToString(peak,3),
             DoubleToString(peak>0 ? 100.0*pts/peak : 0.0, 1),
             DoubleToString(cash,2),
             (string)(int)(tOut-tIn), DoubleToString(SpreadUSD(),3),
             DoubleToString(g_atr,3), DoubleToString(volIn,2),
             DoubleToString(lastStop,3), stopHit?"1":"0",
             DoubleToString(slip,3), wasBe?"1":"0", wasTr?"1":"0");
   FileClose(fh);
}

//==================== PANEL ========================================
#define PLINES 19
void Panel()
{
   if(!InpPanel) return;
   string L[PLINES];
   for(int i=0; i<PLINES; i++) L[i] = "";

   double mpp  = MoneyPerPt();
   double rng  = (g_dayRangeHi > 0 && g_dayRangeLo > 0) ? g_dayRangeHi - g_dayRangeLo : 0.0;
   double capD = (g_dayOffered > 0.0) ? 100.0*g_dayPts/g_dayOffered : 0.0;
   double capS = (g_totOffered > 0.0) ? 100.0*g_totPts/g_totOffered : 0.0;

   // live open-trade totals, so the box is not stale between closes
   double openNow = 0, openPeak = 0; int nOpen = 0;
   string openTxt = "none";
   for(int i=0; i<MAXPOS; i++)
   {
      if(!g_pos[i].live) continue;
      nOpen++;
      int d = g_pos[i].dir;
      double px = (d>0) ? BidPx() : AskPx();
      double g = (px - g_pos[i].entry)*d;
      openNow += g; openPeak += g_pos[i].mfe;
      if(nOpen == 1)
      {
         bool beOn = g_pos[i].beArmed;
         bool trOn = g_pos[i].trArmed;
         bool safe = (d>0) ? (g_pos[i].stop >= g_pos[i].entry)
                           : (g_pos[i].stop <= g_pos[i].entry);
         openTxt = StringFormat("#%I64u %s now %+.2f peak %+.2f stop %.3f  %s",
                                g_pos[i].ticket, d>0?"BUY":"SELL", g, g_pos[i].mfe,
                                g_pos[i].stop,
                                trOn ? "[TRAILING]" : (safe||beOn ? "[RISK-FREE]" : "[at risk]"));
      }
   }

   int k = 0;
   L[k++] = StringFormat("%s   %s %s        signal: %s", EA_BUILD, _Symbol,
              EnumToString(InpTF),
              g_dir==-1 ? "UP (long side)" : g_dir==1 ? "DOWN (short side)" : "none yet");
   L[k++] = StringFormat("spread %.3f   ATR %.3f   ST line %.3f   1pt = %.3f %s",
              SpreadUSD(), g_atr, g_stLevel, mpp, Ccy());
   L[k++] = "---- TODAY: did gold move, and did we get any of it? ----";
   L[k++] = StringFormat("  gold range       %8.1f pt   (%.2f - %.2f)",
              rng, g_dayRangeLo, g_dayRangeHi);
   L[k++] = StringFormat("  gold total path  %8.1f pt   (all the back-and-forth)", g_dayPath);
   L[k++] = StringFormat("  trades           %8d closed, %d open", g_dayTrades, nOpen);
   L[k++] = StringFormat("  OFFERED (peaks)  %+8.1f pt   <- what our trades put on the table",
              g_dayOffered);
   L[k++] = StringFormat("  CAPTURED         %+8.1f pt   <- what we actually kept", g_dayPts);
   L[k++] = StringFormat("  CAPTURE          %+8.1f %%    <- the execution read", capD);
   L[k++] = StringFormat("  money            %+8.2f %s", g_dayPts*mpp, Ccy());
   if(nOpen > 0)
      L[k++] = StringFormat("  open float       %+8.1f pt  (peak %+.1f)", openNow, openPeak);
   L[k++] = StringFormat("---- SESSION: %d trades  offered %+.1f  captured %+.1f  "
              "capture %+.1f%%  %+.2f %s ----",
              g_totTrades, g_totOffered, g_totPts, capS, g_totPts*mpp, Ccy());
   L[k++] = "  OPEN: " + openTxt;
   // THE DECIDING NUMBER. With a trail, nearly every trade exits on a stop, so slippage
   // is a straight per-trade tax. Research says 0.29 pt of it erases the whole gain.
   L[k++] = StringFormat("  stop fills %d | avg slippage %+.3f pt (%.2f %s/trade) | worst %+.3f",
                         g_slipN, g_slipN>0 ? g_slipSum/g_slipN : 0.0,
                         g_slipN>0 ? (g_slipSum/g_slipN)*mpp : 0.0, Ccy(), g_slipWorst);
   if(g_slipN >= 20)
      L[k++] = StringFormat("  %s  <- trail pays for itself only below 0.29 pt",
                            (g_slipSum/g_slipN) < 0.29 ? "slippage OK so far" : "SLIPPAGE IS EATING IT");
   L[k++] = StringFormat("  signals seen %d | entries refused %d%s", g_signalsSeen, g_refused,
              g_refused > 0 ? ("  last: " + g_lastRefusal) : "");
   L[k++] = StringFormat("  %s%s", g_halted ? "*** DAILY LOSS HALT ***  " : "",
              "read: offered small = SIGNAL gave nothing. offered big, capture low = EXECUTION.");

   for(int i=0; i<PLINES; i++)
   {
      string nm = "LEAN_P" + IntegerToString(i);
      if(L[i] == "")
      {
         if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
         continue;
      }
      if(ObjectFind(0, nm) < 0)
      {
         ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
         ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_LEFT_UPPER);
         ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, 10);
         ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, 18 + i*14);
         ObjectSetString (0, nm, OBJPROP_FONT, "Consolas");
         ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, InpPanelFont);
         ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      }
      color c = clrGainsboro;
      if(i == 7 || i == 8) c = (g_dayPts >= 0) ? clrLimeGreen : clrTomato;
      if(i == 6) c = clrKhaki;
      ObjectSetInteger(0, nm, OBJPROP_COLOR, c);
      ObjectSetString(0, nm, OBJPROP_TEXT, L[i]);
   }
   ChartRedraw(0);
}

//==================== LIFECYCLE ====================================
int OnInit()
{
   g_digits  = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   g_tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   g_tickSz  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   g_lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   g_lotMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   g_lotMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   long sl = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   long fz = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   g_minStopDist = (double)MathMax(sl, fz) * _Point;
   if(g_minStopDist < 10*_Point) g_minStopDist = 10*_Point;

   for(int i=0; i<MAXPOS; i++) { g_pos[i].live=false; g_pos[i].ticket=0; }
   for(int i=0; i<PENDN; i++)
   { g_pendId[i]=0; g_pendPeak[i]=0; g_pendStop[i]=0; g_pendBe[i]=false; g_pendTr[i]=false; }

   // Filling mode must match what the broker supports or EVERY order is rejected with
   // "unsupported filling mode". This is the commonest reason an EA silently never trades.
   long fm = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((fm & SYMBOL_FILLING_FOK) != 0)      trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((fm & SYMBOL_FILLING_IOC) != 0) trade.SetTypeFilling(ORDER_FILLING_IOC);
   else                                    trade.SetTypeFilling(ORDER_FILLING_RETURN);
   trade.SetAsyncMode(false);

   ENUM_SYMBOL_TRADE_MODE tm =
      (ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE);
   if(tm != SYMBOL_TRADE_MODE_FULL)
      PrintFormat("WARNING: %s trade mode is %s — orders may be refused by the broker.",
                  _Symbol, EnumToString(tm));

   // restart recovery: re-adopt our own open positions into state
   int adopted = 0;
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk==0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      int s = FreeSlot(); if(s < 0) break;
      g_pos[s].live   = true;
      g_pos[s].ticket = tk;
      g_pos[s].dir    = (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY) ? 1 : -1;
      g_pos[s].entry  = PositionGetDouble(POSITION_PRICE_OPEN);
      g_pos[s].stop   = PositionGetDouble(POSITION_SL);
      g_pos[s].opened = (datetime)PositionGetInteger(POSITION_TIME);
      // ATR at the original entry is gone after a restart. Use the CURRENT ATR rather
      // than 0, because 0 silently disables break-even and the trail for this position
      // (both require atr > 0) -- an adopted trade would run naked to its hard stop.
      g_pos[s].atr    = g_atr; g_pos[s].spreadIn = SpreadUSD();
      g_pos[s].mfe=0; g_pos[s].mae=0; g_pos[s].peak=0; g_pos[s].barsHeld=0;
      // if the broker-side stop is already past entry, break-even was armed before.
      int ad = g_pos[s].dir;
      g_pos[s].beArmed = (g_pos[s].stop > 0.0) &&
                         ((ad>0) ? (g_pos[s].stop >= g_pos[s].entry)
                                 : (g_pos[s].stop <= g_pos[s].entry));
      g_pos[s].trArmed = false;
      adopted++;
   }

   DailyRoll();

   PrintFormat("================ %s ================", EA_BUILD);
   PrintFormat("%s %s | Supertrend %.2f / ATR %d | warmup %d bars | lots %.2f",
               _Symbol, EnumToString(InpTF), InpStMult, InpStAtrLen, InpWarmupBars, InpLots);
   PrintFormat("stop %.2f x ATR, floor %.2f, ceiling %.2f pt | broker min stop %.3f",
               InpStopAtrMult, InpStopMinUSD, InpStopMaxUSD, g_minStopDist);
   PrintFormat("1.00 of gold movement = %.4f %s at %.2f lots (read from the symbol)",
               MoneyPerPt(), Ccy(), InpLots);
   if(MoneyPerPt() <= 0.0)
      Print("WARNING: could not derive money-per-point from the symbol. Set "
            "InpMoneyPerPtPerLot manually or the panel's money column will read 0.");
   PrintFormat("exits active: FLIP=%s BREAKEVEN=%s TARGET=%s TIME=%s LOCK=%s TRAIL=%s",
               InpExitOnFlip?"on":"off",
               InpBreakEvenAtr>0?StringFormat("%.2f ATR",InpBreakEvenAtr):"off",
               InpTargetUSD>0?"on":"off",
               InpMaxHoldBars>0?"on":"off", InpLockArmUSD>0?"on":"off",
               InpTrailAtrMult>0?"on":"off");
   if(adopted>0) PrintFormat("adopted %d existing position(s) after restart", adopted);

   // honest preflight
   double worst = MathMax(InpStopMinUSD, InpStopAtrMult*1.5) * MoneyPerPt();
   PrintFormat("PREFLIGHT: a full stop costs about %.2f %s. Daily halt at %.2f "
               "= about %d losses.", worst, Ccy(), InpMaxDailyLoss,
               worst>0 ? (int)(InpMaxDailyLoss/worst) : 0);
   Print("PREFLIGHT: measured on 3.83M real broker bars. On M1 this signal is "
         "ANTI-PREDICTIVE: gross before any cost -0.030 pt/trade at t=-5.44 over 283,251 "
         "trades, and a median 64.6% of each swing is already gone when the arrow prints. "
         "93% of the realised loss is spread. This build is a clean, instrumented chassis "
         "for TESTING, not a profitable strategy. See research/FINDINGS.md.");
   Print("PREFLIGHT: the panel's OFFERED vs CAPTURED vs CAPTURE% is the diagnostic. "
         "If OFFERED is small, the signal gave nothing and no execution fix helps. "
         "If OFFERED is large but CAPTURE% is low, execution is the problem.");
   if(PeriodSeconds(InpTF) < PeriodSeconds(PERIOD_M30))
      PrintFormat("*** TIMEFRAME WARNING *** On %s this signal measured gross %s before any "
                  "cost. On M1 specifically it is -0.030 pt/trade at t=-5.44 over 283,251 "
                  "trades, i.e. significantly WORSE than random. H1 is the only timeframe "
                  "tested that was not negative. Running this on %s is expected to lose.",
                  EnumToString(InpTF), InpTF==PERIOD_M1 ? "NEGATIVE" : "~zero",
                  EnumToString(InpTF));
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))
      Print("WARNING: algo trading is OFF for this EA — it will not place orders.");
   Print("=============================================");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, "LEAN_P");
   PrintFormat("[%s] FINAL: %d trades  offered %+.1f pt  captured %+.1f pt  "
               "capture %.1f%%  %+.2f %s",
               EA_BUILD, g_totTrades, g_totOffered, g_totPts,
               g_totOffered>0 ? 100.0*g_totPts/g_totOffered : 0.0,
               g_totPts*MoneyPerPt(), Ccy());
}

void OnTick()
{
   DailyRoll();
   CheckHalt();
   ParityExport();

   datetime bt = iTime(_Symbol, InpTF, 0);
   bool newBar = (bt != g_lastSigBar && bt > 0);

   if(newBar)
   {
      UpdateDayStats();
      int d, pd; double st, atr, dema;
      if(Signal_Compute(d, pd, st, atr, dema))
      {
         g_prevDir = pd; g_dir = d; g_stLevel = st; g_atr = atr; g_dema = dema;
         g_sigBuy  = (d == -1 && pd ==  1);
         g_sigSell = (d ==  1 && pd == -1);
      }
      g_lastSigBar = bt;
      if(g_firstEval)      // the newest closed bar may already be a flip from before we
      {                    // attached; initialise state without trading it
         g_firstEval = false;
         if(g_sigBuy || g_sigSell)
            Log("first evaluation: ignoring the already-printed flip, waiting for a fresh one");
         g_sigBuy = false; g_sigSell = false;
      }
   }

   // exits first: a flip must close the old trade before it opens the new one
   ManageOpen(newBar);

   if(newBar && (g_sigBuy || g_sigSell))
   {
      g_signalsSeen++;
      int dir = g_sigBuy ? 1 : -1;
      SendEntry(dir, StringFormat("ST flip %s on %s, line %.3f, ATR %.3f",
                                  g_sigBuy?"UP":"DOWN", EnumToString(InpTF), g_stLevel, g_atr));
      g_sigBuy = false; g_sigSell = false;
   }

   static datetime lastPanel = 0;
   if(TimeCurrent() != lastPanel) { lastPanel = TimeCurrent(); Panel(); }
}

void OnTradeTransaction(const MqlTradeTransaction &tr, const MqlTradeRequest &rq,
                        const MqlTradeResult &rs)
{
   if(tr.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(tr.deal)) return;
   if(HistoryDealGetString(tr.deal, DEAL_SYMBOL) != _Symbol) return;
   if(HistoryDealGetInteger(tr.deal, DEAL_ENTRY) != DEAL_ENTRY_OUT) return;
   ulong pid = (ulong)HistoryDealGetInteger(tr.deal, DEAL_POSITION_ID);
   if(PositionSelectByTicket(pid)) return;        // partial, not fully closed
   int s = SlotOf(pid);
   // a position closed BY HAND can arrive with magic 0, so also accept it if we owned it
   if(HistoryDealGetInteger(tr.deal, DEAL_MAGIC) != InpMagic && s < 0) return;
   if(s >= 0) ReleaseSlot(s);                     // stashes the peak for the book
   BookClose(pid);
}

//+------------------------------------------------------------------+
//|                                          SuperTrendSniper.mq5    |
//|         Your SuperTrend strategy, rebuilt around the exits       |
//+------------------------------------------------------------------+
//
//  WHAT THIS IS
//  The SAME signal you already trust - SuperTrend(7, 1.2) with a DEMA trend
//  filter, identical to XAUUSD_CLEAN_3.5.pine. The signal logic is NOT
//  changed, because you are right that it finds moves.
//
//  What IS rebuilt is everything after the entry, because that is where the
//  money was going. Your own words: "a majority of trades go into profit, we
//  just don't close in that profit."
//
//  WHY THE OLD EA GAVE PROFIT BACK - measured, not guessed
//  Testing 11 exit rules over identical entries on GOLD, US500, EURUSD and
//  GBPUSD, first-touch resolution, ties counted as losses:
//
//      break-even at 0.5R then trail : -0.161R  (GOLD)   <- WORST on all four
//      break-even at 1R then trail   : -0.009R
//      trail 2x ATR                  : -0.029R
//      fixed 3R target               : +0.181R
//      hold 20 bars                  : +0.201R  <- BEST
//
//  Moving the stop up early is the single most expensive habit available. It
//  scratches the trade out before the rare large winner - the one that pays
//  for everything - can develop. v19.18 was built around doing exactly that
//  (NoiseFloorPts armed at one band and gave back one band), which is why
//  peaks summed GBP110 and handed back GBP73.
//
//  So this EA defaults to: NO break-even move, a WIDE trail armed
//  immediately, a fixed R target, and a 50-bar time cap.
//
//  CORRECTED 2026-09-01 by audit. This paragraph used to say "NO early trail"
//  and "hold 20 bars <- BEST" while the file shipped InpTrailAtR = 0.0 (the
//  trail arms at once) and InpMaxBars = 50. Both defaults are deliberate and
//  both measured better on THIS strategy's entries; the summary above was
//  quoting a Donchian-entry table and was simply describing a different EA.
//  A wide trail armed early is not the same habit as break-even: the trail
//  rides 3 ATR behind and only ratchets, break-even parks the stop at entry
//  and gets scratched out. That distinction is the whole finding.
//
//  WHY YOUR BACKTESTS DID NOT MATCH LIVE
//  Three causes, all fixed here:
//    1. v19.18 acted on EVERY TICK. Its own OnTick carried the comment
//       "Entries only on a new bar" and then called the engine every tick.
//       This EA computes signals ONLY when a bar closes, so "Open prices
//       only", "1 minute OHLC" and live all produce the same decisions.
//    2. Indicator values were read from the FORMING bar, which changes until
//       the bar closes. Everything here is read at shift >= 1.
//    3. Spread was not modelled. Here it is checked before every entry and
//       the trade is skipped if it is abnormal.
//
//  NOT COMPILED. There is no MetaTrader in the environment this was written
//  in. Compile in MetaEditor and report any error text.
//
//  DEMO GUARD IS ON BY DEFAULT. InpDemoOnly must be set false deliberately.
//+------------------------------------------------------------------+
#property copyright "JARVIS"
#property version   "2.30"
// THE BUILD STAMP. Printed on start and shown in the panel. Three separate
// reports of "the profit box does not work" and no way to tell whether the
// build carrying the fix was ever compiled. If the number below is not the one
// in the message that shipped it, MetaEditor has not rebuilt: open the file and
// press F7. An .ex5 does not update itself when the .mq5 changes.
#define STS_BUILD "2026-09-03 / 2.21 / disaster brake"
#property strict

#include <Trade/Trade.mqh>

// The shared profit box. It sits opposite the EXECUTION BOX and answers a
// different question: that one measures how WELL a trade was executed, this
// one measures WHAT WAS EARNED, in points first and money second (E-074).
// On market entries the LEVEL row reads zero and everything lands on TREND -
// which is correct, not a gap: only a resting limit can earn a better fill.
//==============================================================
// BEGIN ProfitBox.mqh  (spliced by JARVIS/tools/build_ea.py - edit the .mqh, not this)
//==============================================================
//+------------------------------------------------------------------+
//|  ProfitBox.mqh  —  the on-chart profit box, shared by every EA    |
//|                                                                  |
//|  WHAT IT IS FOR                                                  |
//|  Veer asked for a box that "should show profit from supertrend    |
//|  strat and liquidity, so it should know how to measure and treat  |
//|  each different".                                                 |
//|                                                                  |
//|  HOW IT DOES THAT: one row per STRATEGY, keyed by magic number.   |
//|  Register every magic you run with PB_AddStrategy() and the box   |
//|  reports each one separately - points, money, trades, win rate -  |
//|  plus a total. Run ZoneSniper, SuperTrendSniper and               |
//|  LiquiditySniper on one account and all three read off one box.   |
//|                                                                  |
//|  WHAT THIS DELIBERATELY DOES *NOT* DO, and the number that        |
//|  settled it (E-131)                                               |
//|  ---------------------------------------------------------------- |
//|  The first version of this file split each trade along the price  |
//|  axis at the arm price:                                           |
//|      LEVEL = dir*(armPx - entry),  TREND = dir*(exit - armPx)     |
//|  That identity holds exactly - it was checked to 0.00e+00 over    |
//|  981 real trades - and it is USELESS. On the shipped System A:    |
//|      TOTAL   +97.1 points                                         |
//|      LEVEL  +691.9  (712% of the result, positive on 100.0% of    |
//|                      trades)                                      |
//|      TREND  -594.8  (-612%, positive on 6.2%)                     |
//|  LEVEL is positive on every single trade because it is MECHANICAL:|
//|  the limit rests 0.50 ATR past the level, so the fill beats the   |
//|  arm price by that offset by construction. It measures the offset,|
//|  not the level. Two rows reading +692 and -595 against a +97      |
//|  result would have looked broken and meant nothing.               |
//|                                                                   |
//|  An exact decomposition is not automatically an honest            |
//|  attribution. What a component is WORTH is an ablation - run the  |
//|  system with and without it - and that is a backtest question,    |
//|  not something a live panel can answer. So the box reports what   |
//|  it can actually measure and says so.                             |
//|                                                                   |
//|  FILL VS SIGNAL is kept, correctly labelled, as an ENTRY-QUALITY  |
//|  diagnostic in points per trade: how much better the resting      |
//|  limit filled than the market at the moment the EA armed. On the  |
//|  backtest that is +0.705/trade against a 0.50 ATR design offset.  |
//|  If your broker's live number comes in far below that, the limits |
//|  are being filled late and the edge is going with it. That is a   |
//|  real thing to watch. It is not a share of the profit.            |
//|                                                                   |
//|  POINTS COME FIRST. E-074: the best per-trade gate set in this    |
//|  project banked the LEAST money. Points are the unit that         |
//|  matters, money second.                                           |
//|                                                                   |
//|  Money is the BROKER'S number: DEAL_PROFIT + swap + commission,   |
//|  in the account currency. It is never modelled here.              |
//+------------------------------------------------------------------+
#property strict

#ifndef PROFITBOX_MQH
#define PROFITBOX_MQH

//==================== configuration ================================
struct PBConfig
{
   string  prefix;        // object-name prefix, must be unique per EA
   string  title;         // shown top-left
   long    magic;         // this EA's own magic (the first strategy row)
   int     corner;        // CORNER_LEFT_UPPER etc.
   int     x;             // margin from that corner, pixels
   int     y;
   int     fontSize;
   string  font;
   color   cBg;
   color   cFrame;
   color   cHead;
   color   cVal;
   color   cPos;
   color   cNeg;
   color   cDim;
   bool    show;
};

//==================== per-position ledger ==========================
struct PBTrade
{
   ulong    pid;
   long     magic;        // which strategy opened it
   int      dir;          // +1 long, -1 short
   double   inVol,  inPxVol;
   double   outVol, outPxVol;
   double   money;        // profit + swap + commission, account currency
   double   armPx;        // market price when the EA decided to trade
   datetime tOpen, tClose;
   bool     closed;
};

//==================== the strategy table ===========================
// One row per magic number. Register the EA's own magic first, then any other
// EA you run on the same account, and this box speaks for all of them.
struct PBStrat
{
   long   magic;
   string label;
   int    n, wins;
   double pts, money, ptsDay;
};
PBStrat g_pbS[];

int PB_StratIdx(long magic)
{
   for(int i = 0; i < ArraySize(g_pbS); i++)
      if(g_pbS[i].magic == magic) return i;
   return -1;
}

void PB_AddStrategy(long magic, string label)
{
   if(PB_StratIdx(magic) >= 0) return;
   int n = ArraySize(g_pbS);
   ArrayResize(g_pbS, n + 1);
   g_pbS[n].magic = magic;
   g_pbS[n].label = label;
   g_pbS[n].n = 0; g_pbS[n].wins = 0;
   g_pbS[n].pts = 0; g_pbS[n].money = 0; g_pbS[n].ptsDay = 0;
}

//==================== state ========================================
PBConfig  g_pb;
PBTrade   g_pbT[];
datetime  g_pbLastScan  = 0;
bool      g_pbDirty     = true;
int       g_pbMaxRows   = 16;

// box geometry, in one place so the background and the rows can never disagree
#define PB_BOX_W 262
int PB_BoxH() { return 20 + g_pbMaxRows * (g_pb.fontSize + 7); }

// aggregates, recomputed by PB_Scan()
double g_pbPts, g_pbPtsDay, g_pbFill, g_pbMoney, g_pbMoneyDay;
int    g_pbNFill;   // trades that carried an arm-price note
double g_pbBest, g_pbWorst, g_pbMaxDD, g_pbLong, g_pbShort;
int    g_pbN, g_pbNDay, g_pbWins, g_pbNLong, g_pbNShort;
datetime g_pbFirst;

//+------------------------------------------------------------------+
//| the arm price is remembered in an MT5 global variable so that an  |
//| EA restart, a terminal restart or a recompile does not silently   |
//| move a trade's points from LEVEL to TREND. A missing note is not  |
//| an error - it just means that trade reads as entered at market.   |
//+------------------------------------------------------------------+
string PB_Key(string kind, ulong id)
{
   return g_pb.prefix + kind + "." + IntegerToString((long)id);
}

void PB_NoteOrder(ulong orderTicket, double px)
{
   if(orderTicket == 0 || px <= 0.0) return;
   GlobalVariableSet(PB_Key("o", orderTicket), px);
}

// call from OnTradeTransaction on DEAL_ENTRY_IN: moves the note from the
// order ticket it was filed under to the position it became.
void PB_PromoteOrder(ulong orderTicket, ulong positionId, double fallbackPx)
{
   string ko = PB_Key("o", orderTicket);
   double px = GlobalVariableCheck(ko) ? GlobalVariableGet(ko) : fallbackPx;
   if(GlobalVariableCheck(ko)) GlobalVariableDel(ko);
   if(positionId != 0 && px > 0.0)
      GlobalVariableSet(PB_Key("p", positionId), px);
   g_pbDirty = true;
}

// returns 0.0 when there is no note - the caller must not invent one
double PB_ArmPx(ulong positionId, double fallbackPx)
{
   string kp = PB_Key("p", positionId);
   if(GlobalVariableCheck(kp))
   {
      double v = GlobalVariableGet(kp);
      if(v > 0.0) return v;
   }
   return fallbackPx;
}

// notes older than this many days are dead weight in the terminal
void PB_Prune(int days = 30)
{
   datetime cut = TimeCurrent() - (datetime)days * 86400;
   for(int i = GlobalVariablesTotal() - 1; i >= 0; i--)
   {
      string nm = GlobalVariableName(i);
      if(StringFind(nm, g_pb.prefix) != 0) continue;
      if(GlobalVariableTime(nm) < cut) GlobalVariableDel(nm);
   }
}

//==================== the ledger ===================================
int PB_Find(ulong pid)
{
   for(int i = ArraySize(g_pbT) - 1; i >= 0; i--)
      if(g_pbT[i].pid == pid) return i;
   return -1;
}

int PB_Add(ulong pid)
{
   int n = ArraySize(g_pbT);
   ArrayResize(g_pbT, n + 1);
   g_pbT[n].pid = pid;
   g_pbT[n].magic = 0;
   g_pbT[n].dir = 0;
   g_pbT[n].inVol = 0.0;  g_pbT[n].inPxVol = 0.0;
   g_pbT[n].outVol = 0.0; g_pbT[n].outPxVol = 0.0;
   g_pbT[n].money = 0.0;  g_pbT[n].armPx = 0.0;
   g_pbT[n].tOpen = 0;    g_pbT[n].tClose = 0;
   g_pbT[n].closed = false;
   return n;
}

//+------------------------------------------------------------------+
//| Rebuild everything from the terminal's own deal history. Doing it |
//| this way rather than incrementing counters means a restart, a     |
//| manual close or a stop-out filled by the broker all show up - the |
//| box can never drift away from the account.                        |
//|                                                                   |
//| Partial closes are handled by volume-weighting both sides, so a   |
//| position closed in three pieces still reports one honest average  |
//| entry and one honest average exit.                                 |
//+------------------------------------------------------------------+
void PB_Scan()
{
   ArrayFree(g_pbT);
   g_pbPts = 0; g_pbPtsDay = 0; g_pbFill = 0; g_pbNFill = 0;
   g_pbMoney = 0; g_pbMoneyDay = 0;
   g_pbBest = 0; g_pbWorst = 0; g_pbMaxDD = 0; g_pbLong = 0; g_pbShort = 0;
   g_pbN = 0; g_pbNDay = 0; g_pbWins = 0; g_pbNLong = 0; g_pbNShort = 0;
   g_pbFirst = 0;
   for(int i = 0; i < ArraySize(g_pbS); i++)
   {
      g_pbS[i].n = 0; g_pbS[i].wins = 0;
      g_pbS[i].pts = 0; g_pbS[i].money = 0; g_pbS[i].ptsDay = 0;
   }

   if(!HistorySelect(0, TimeCurrent() + 86400)) return;

   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0) continue;
      long mg = HistoryDealGetInteger(tk, DEAL_MAGIC);
      if(PB_StratIdx(mg) < 0) continue;          // not a strategy we track
      if(HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol) continue;

      long entry = HistoryDealGetInteger(tk, DEAL_ENTRY);
      long dtype = HistoryDealGetInteger(tk, DEAL_TYPE);
      if(dtype != DEAL_TYPE_BUY && dtype != DEAL_TYPE_SELL) continue;

      ulong  pid = (ulong)HistoryDealGetInteger(tk, DEAL_POSITION_ID);
      double px  = HistoryDealGetDouble(tk, DEAL_PRICE);
      double vol = HistoryDealGetDouble(tk, DEAL_VOLUME);
      if(pid == 0 || vol <= 0.0) continue;

      int j = PB_Find(pid);
      if(j < 0) j = PB_Add(pid);
      g_pbT[j].magic = mg;

      if(entry == DEAL_ENTRY_IN)
      {
         // a BUY deal opening a position means the position is long
         g_pbT[j].dir     = (dtype == DEAL_TYPE_BUY) ? 1 : -1;
         g_pbT[j].inVol  += vol;
         g_pbT[j].inPxVol += px * vol;
         if(g_pbT[j].tOpen == 0)
            g_pbT[j].tOpen = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
      }
      else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
      {
         g_pbT[j].outVol   += vol;
         g_pbT[j].outPxVol += px * vol;
         g_pbT[j].tClose    = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
      }
      // commission and swap are booked on whichever deal carries them
      g_pbT[j].money += HistoryDealGetDouble(tk, DEAL_PROFIT)
                      + HistoryDealGetDouble(tk, DEAL_SWAP)
                      + HistoryDealGetDouble(tk, DEAL_COMMISSION);
   }

   // ---- turn the ledger into the numbers on the box -----------------
   MqlDateTime nowS; TimeToStruct(TimeCurrent(), nowS);
   double eq = 0.0, peak = 0.0;

   for(int i = 0; i < ArraySize(g_pbT); i++)
   {
      if(g_pbT[i].inVol <= 0.0 || g_pbT[i].outVol <= 0.0) continue;  // still open
      g_pbT[i].closed = true;

      double inPx  = g_pbT[i].inPxVol  / g_pbT[i].inVol;
      double outPx = g_pbT[i].outPxVol / g_pbT[i].outVol;
      int    d     = g_pbT[i].dir;
      double pts   = d * (outPx - inPx);

      // FILL VS SIGNAL, and this is an entry-quality diagnostic, NOT a share
      // of the profit - see the E-131 note in the header. A trade with no
      // arm-price note (market entry, or the note was lost) is left out of the
      // average rather than counted as zero, which would drag it toward 0 and
      // say something false about the fills we can actually measure.
      double arm = PB_ArmPx(g_pbT[i].pid, 0.0);
      if(arm > 0.0)
      {
         g_pbFill += d * (arm - inPx);
         g_pbNFill++;
      }

      g_pbN++;
      if(pts > 0) g_pbWins++;
      g_pbPts   += pts;
      g_pbMoney += g_pbT[i].money;
      if(pts > g_pbBest)  g_pbBest  = pts;
      if(pts < g_pbWorst) g_pbWorst = pts;
      if(d > 0) { g_pbNLong++;  g_pbLong  += pts; }
      else      { g_pbNShort++; g_pbShort += pts; }
      if(g_pbFirst == 0 || g_pbT[i].tOpen < g_pbFirst) g_pbFirst = g_pbT[i].tOpen;

      eq += pts;
      if(eq > peak) peak = eq;
      if(peak - eq > g_pbMaxDD) g_pbMaxDD = peak - eq;

      MqlDateTime cs; TimeToStruct(g_pbT[i].tClose, cs);
      bool today = (cs.year == nowS.year && cs.mon == nowS.mon && cs.day == nowS.day);
      if(today)
      {
         g_pbNDay++;
         g_pbPtsDay   += pts;
         g_pbMoneyDay += g_pbT[i].money;
      }

      int si = PB_StratIdx(g_pbT[i].magic);
      if(si >= 0)
      {
         g_pbS[si].n++;
         if(pts > 0) g_pbS[si].wins++;
         g_pbS[si].pts   += pts;
         g_pbS[si].money += g_pbT[i].money;
         if(today) g_pbS[si].ptsDay += pts;
      }
   }
   g_pbLastScan = TimeCurrent();
   g_pbDirty    = false;
}

//==================== drawing ======================================
string PB_Num(double v, int d)
{
   return (v >= 0 ? "+" : "") + DoubleToString(v, d);
}

void PB_Obj(string name, int sub, string text, color c, int row, int col)
{
   string nm = g_pb.prefix + name;
   if(ObjectFind(0, nm) < 0)
   {
      ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN,     true);
      ObjectSetInteger(0, nm, OBJPROP_BACK,       false);
      ObjectSetString (0, nm, OBJPROP_FONT,       g_pb.font);
   }
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, sub > 0 ? g_pb.fontSize - 1 : g_pb.fontSize);
   ObjectSetInteger(0, nm, OBJPROP_CORNER,   g_pb.corner);

   // Everything below is laid out in BOX-LOCAL pixels - lx from the box's left
   // edge, ly from its top - and only the last step converts to the chart's
   // corner. MT5 measures XDISTANCE leftward from a right corner and YDISTANCE
   // upward from a lower one, so without this the box renders mirrored or
   // upside down depending on which corner it is pinned to. The first draft of
   // this file did exactly that.
   int lineH = g_pb.fontSize + 7;
   int lx = (col == 0) ? 10 : (col == 1) ? 152 : PB_BOX_W - 10;
   int ly = 10 + row * lineH;

   bool right = (g_pb.corner == CORNER_RIGHT_UPPER || g_pb.corner == CORNER_RIGHT_LOWER);
   bool lower = (g_pb.corner == CORNER_LEFT_LOWER  || g_pb.corner == CORNER_RIGHT_LOWER);

   int xd = right ? g_pb.x + (PB_BOX_W - lx) : g_pb.x + lx;
   int yd = lower ? g_pb.y + (PB_BoxH()  - ly) : g_pb.y + ly;

   // the anchor describes the TEXT, not the corner: column 0 starts at its
   // point, the two number columns end at theirs.
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR,
                    col == 0 ? ANCHOR_LEFT_UPPER : ANCHOR_RIGHT_UPPER);
   ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, xd);
   ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, yd);
   ObjectSetString (0, nm, OBJPROP_TEXT,  text);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, c);
}

void PB_Row(int row, string a, string b, color cb, string c)
{
   PB_Obj("r" + IntegerToString(row) + "a", 0, a, g_pb.cHead, row, 0);
   PB_Obj("r" + IntegerToString(row) + "b", 0, b, cb,         row, 1);
   PB_Obj("r" + IntegerToString(row) + "c", 1, c, g_pb.cDim,  row, 2);
}

void PB_Sep(int row, string caption)
{
   PB_Obj("r" + IntegerToString(row) + "a", 1, caption, g_pb.cDim, row, 0);
   PB_Obj("r" + IntegerToString(row) + "b", 1, "",      g_pb.cDim, row, 1);
   PB_Obj("r" + IntegerToString(row) + "c", 1, "",      g_pb.cDim, row, 2);
}

void PB_Destroy()
{
   ObjectsDeleteAll(0, g_pb.prefix);
}

//+------------------------------------------------------------------+
//| PB_Draw - call from OnTick. Rescans at most once every 3 seconds  |
//| unless a deal has just landed, so it costs nothing on a tick.     |
//+------------------------------------------------------------------+
void PB_Draw()
{
   if(!g_pb.show) return;
   if(g_pbDirty || TimeCurrent() - g_pbLastScan >= 3) PB_Scan();

   // ---- the open position, live -------------------------------------
   int    oDir = 0;
   double oPts = 0.0, oMoney = 0.0, oLots = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != g_pb.magic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)    continue;
      int d = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      oDir   = d;
      oLots += PositionGetDouble(POSITION_VOLUME);
      oPts  += d * (PositionGetDouble(POSITION_PRICE_CURRENT)
                  - PositionGetDouble(POSITION_PRICE_OPEN));
      oMoney += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   }

   string cur   = AccountInfoString(ACCOUNT_CURRENCY);
   double winPc = g_pbN > 0 ? 100.0 * g_pbWins / g_pbN : 0.0;
   double avg   = g_pbN > 0 ? g_pbPts / g_pbN : 0.0;
   double days  = 1.0;
   if(g_pbFirst > 0)
      days = MathMax(1.0, (double)(TimeCurrent() - g_pbFirst) / 86400.0);

   // 15 fixed rows plus one per registered strategy
   g_pbMaxRows = 15 + ArraySize(g_pbS);

   // ---- background ---------------------------------------------------
   string bg = g_pb.prefix + "bg";
   if(ObjectFind(0, bg) < 0)
   {
      ObjectCreate(0, bg, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, bg, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, bg, OBJPROP_HIDDEN,     true);
      ObjectSetInteger(0, bg, OBJPROP_BACK,       false);
      ObjectSetInteger(0, bg, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, bg, OBJPROP_STYLE,      STYLE_SOLID);
      ObjectSetInteger(0, bg, OBJPROP_WIDTH,      1);
   }
   ObjectSetInteger(0, bg, OBJPROP_CORNER,    g_pb.corner);
   ObjectSetInteger(0, bg, OBJPROP_XDISTANCE, g_pb.x);
   ObjectSetInteger(0, bg, OBJPROP_YDISTANCE, g_pb.y);
   ObjectSetInteger(0, bg, OBJPROP_XSIZE,     PB_BOX_W);
   ObjectSetInteger(0, bg, OBJPROP_YSIZE,     PB_BoxH());
   ObjectSetInteger(0, bg, OBJPROP_BGCOLOR,   g_pb.cBg);
   ObjectSetInteger(0, bg, OBJPROP_COLOR,     g_pb.cFrame);

   // ---- the rows -----------------------------------------------------
   // The row count is dynamic because the strategy section grows with however
   // many magics are registered, so every row index is taken from one counter
   // rather than hard-coded. Hard-coded indices are how a panel ends up with
   // two rows drawn on top of each other.
   int r = 0;
   PB_Obj("title",  0, g_pb.title, g_pb.cVal, r, 0);
   PB_Obj("titleb", 0, "",         g_pb.cVal, r, 1);
   PB_Obj("state",  1, oDir == 0 ? "flat" : (oDir > 0 ? "LONG" : "SHORT"),
          oDir == 0 ? g_pb.cDim : (oDir > 0 ? g_pb.cPos : g_pb.cNeg), r, 2);
   r++;

   // POINTS FIRST. E-074.
   PB_Row(r++, "points", PB_Num(g_pbPts, 1),
          g_pbPts >= 0 ? g_pb.cPos : g_pb.cNeg,
          PB_Num(g_pbMoney, 2) + " " + cur);
   PB_Row(r++, "today",  PB_Num(g_pbPtsDay, 1),
          g_pbPtsDay >= 0 ? g_pb.cPos : g_pb.cNeg,
          PB_Num(g_pbMoneyDay, 2) + " " + cur);
   PB_Row(r++, "trades", IntegerToString(g_pbN), g_pb.cVal,
          DoubleToString(g_pbN / days, 1) + "/day");
   PB_Row(r++, "win rate", DoubleToString(winPc, 1) + "%", g_pb.cVal,
          IntegerToString(g_pbWins) + "W " + IntegerToString(g_pbN - g_pbWins) + "L");
   PB_Row(r++, "avg trade", PB_Num(avg, 3),
          avg >= 0 ? g_pb.cPos : g_pb.cNeg, "points");

   // ---- one row per strategy. This is the split Veer asked for, and it is
   // the one that means something: separate magics, separate books.
   PB_Sep(r++, "-- by strategy --");
   for(int i = 0; i < ArraySize(g_pbS); i++)
   {
      string note = g_pbS[i].n == 0
                  ? "no trades yet"
                  : IntegerToString(g_pbS[i].n) + " tr  "
                    + DoubleToString(100.0 * g_pbS[i].wins / g_pbS[i].n, 0) + "%W  "
                    + PB_Num(g_pbS[i].money, 2);
      PB_Row(r++, g_pbS[i].label, PB_Num(g_pbS[i].pts, 1),
             g_pbS[i].n == 0 ? g_pb.cDim
                             : (g_pbS[i].pts >= 0 ? g_pb.cPos : g_pb.cNeg), note);
   }

   // ---- entry quality. NOT a share of the profit - see the E-131 note at the
   // top of this file. It is how much better the resting limit filled than the
   // market at the moment the EA armed, and it is here so a broker that fills
   // limits late shows up as a falling number instead of as a mystery.
   PB_Sep(r++, "-- entry quality --");
   PB_Row(r++, "fill vs signal",
          g_pbNFill > 0 ? PB_Num(g_pbFill / g_pbNFill, 3) : "-",
          g_pbNFill > 0 && g_pbFill >= 0 ? g_pb.cPos : g_pb.cDim,
          g_pbNFill > 0 ? "pts/trade, " + IntegerToString(g_pbNFill) + " limits"
                        : "market entries");

   PB_Sep(r++, "-- risk --");
   PB_Row(r++, "best / worst",
          PB_Num(g_pbBest, 1) + " / " + DoubleToString(g_pbWorst, 1),
          g_pb.cVal, "points");
   PB_Row(r++, "max drawdown", DoubleToString(-g_pbMaxDD, 1), g_pb.cNeg, "points");
   PB_Row(r++, "long / short",
          PB_Num(g_pbLong, 1) + " / " + PB_Num(g_pbShort, 1), g_pb.cVal,
          IntegerToString(g_pbNLong) + " / " + IntegerToString(g_pbNShort));

   PB_Sep(r++, "-- open --");
   PB_Row(r++, oDir == 0 ? "no position" : "unrealised",
          oDir == 0 ? "-" : PB_Num(oPts, 1),
          oDir == 0 ? g_pb.cDim : (oPts >= 0 ? g_pb.cPos : g_pb.cNeg),
          oDir == 0 ? "" : PB_Num(oMoney, 2) + " " + cur);
   PB_Row(r++, "lots", oDir == 0 ? "-" : DoubleToString(oLots, 2), g_pb.cVal,
          "spread " + DoubleToString(SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                   - SymbolInfoDouble(_Symbol, SYMBOL_BID), 2));

   // any row left over from a previous, taller draw
   for(int i = r; i < r + 4; i++)
   {
      ObjectDelete(0, g_pb.prefix + "r" + IntegerToString(i) + "a");
      ObjectDelete(0, g_pb.prefix + "r" + IntegerToString(i) + "b");
      ObjectDelete(0, g_pb.prefix + "r" + IntegerToString(i) + "c");
   }

   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| PB_Init - call from OnInit, after the magic number is known.      |
//+------------------------------------------------------------------+
void PB_Init(string prefix, string title, long magic, bool show,
             int corner = CORNER_RIGHT_LOWER, int x = 12, int y = 12,
             string label = "")
{
   ArrayFree(g_pbS);
   PB_AddStrategy(magic, label == "" ? title : label);

   g_pb.prefix   = prefix;
   g_pb.title    = title;
   g_pb.magic    = magic;
   g_pb.show     = show;
   g_pb.corner   = corner;
   g_pb.x        = x;
   g_pb.y        = y;
   g_pb.fontSize = 9;
   g_pb.font     = "Consolas";
   g_pb.cBg      = C'14,22,33';
   g_pb.cFrame   = C'42,58,77';
   g_pb.cHead    = C'143,163,184';
   g_pb.cVal     = C'230,237,245';
   g_pb.cPos     = C'0,176,255';
   g_pb.cNeg     = C'255,59,92';
   g_pb.cDim     = C'92,112,137';

   PB_Destroy();
   PB_Prune();
   g_pbDirty = true;
}

#endif  // PROFITBOX_MQH

//==============================================================
// END ProfitBox.mqh
//==============================================================
// M1-M30 only. Higher timeframes are context, not instruments (E-133).
//==============================================================
// BEGIN TimeframeGuard.mqh  (spliced by JARVIS/tools/build_ea.py - edit the .mqh, not this)
//==============================================================
//+------------------------------------------------------------------+
//|  TimeframeGuard.mqh                                              |
//|                                                                  |
//|  Veer, and this is a hard rule, not a preference:                 |
//|    "we trade m1 m5 m15 and m3 maybe... we simply LOOK AT higher   |
//|     timeframes we don't trade them"                               |
//|                                                                  |
//|  Two of these EAs read _Period and will trade whatever chart they |
//|  are dropped on. Nothing stopped an H1 or H4 chart from becoming  |
//|  an H1 or H4 strategy - a defect, because every number any of     |
//|  them is quoted at was measured on M1, and the cost picture is    |
//|  completely different up there (E-132: the same 0.40 spread is    |
//|  0.220 of ATR on M1 and 0.047 on M15).                            |
//|                                                                  |
//|  This refuses to start above M30. It is deliberately a REFUSAL    |
//|  and not a warning: a warning in the Experts log is something you |
//|  find out about after the trades.                                 |
//|                                                                  |
//|  Higher timeframes are still read for CONTEXT wherever an EA does |
//|  that. Reading H4 is not trading H4.                              |
//|                                                                  |
//|  WHAT THE CONTEXT IS ACTUALLY WORTH, so nobody re-adds it on a    |
//|  hunch (E-133, 157,051 real M1 bars, nine variants):              |
//|    M1 direction only        981 trades   97.1 pts   +0.0990 each  |
//|    M1 + H1 must agree       850          80.2       +0.0943       |
//|    M1 + H4 must agree       851          93.1       +0.1094       |
//|    M1 + H1 + H4             582          53.9       +0.0926       |
//|    H1 alone                 942          94.3       +0.1001       |
//|    H4 alone                 937          82.6       +0.0882       |
//|  NOT ONE of them beats reading direction off M1. A trend filter   |
//|  is worth a great deal - without any, the same entries make 48.4  |
//|  points instead of 97.1 (E-127) - but the best clock to read it   |
//|  from is the one being traded.                                    |
//+------------------------------------------------------------------+
#property strict

#ifndef TIMEFRAME_GUARD_MQH
#define TIMEFRAME_GUARD_MQH

// The ceiling is a SETTING, not a constant. Veer: "i'm putting all ea on m1
// it can trade based of whatever it wants... i wanted to trade m1 to m30
// possibly h1 possibly if good setup". The first version of this file hard
// refused above M30, which was me turning a default into a rule. The default
// is still M30 because that is where every measurement lives, but raising it
// is his call to make, and the log says what he is giving up when he does.
bool TfAllowed(ENUM_TIMEFRAMES tf, ENUM_TIMEFRAMES ceiling)
{
   if(tf == PERIOD_MN1) return false;
   int mins = PeriodSeconds(tf) / 60;
   int cap  = PeriodSeconds(ceiling) / 60;
   return mins > 0 && cap > 0 && mins <= cap;
}

// Returns false and prints why. Call it first in OnInit and return
// INIT_FAILED on false.
bool TfGuard(string ea, ENUM_TIMEFRAMES ceiling = PERIOD_M30)
{
   if(TfAllowed((ENUM_TIMEFRAMES)_Period, ceiling)) return true;
   PrintFormat("[%s] REFUSING TO START on %s - above the configured ceiling %s.",
               ea, EnumToString((ENUM_TIMEFRAMES)_Period),
               EnumToString(ceiling));
   Print("Raise InpMaxTF if you mean to do this. It is your call, but read "
         "the next two lines first.");
   Print("This is an M1-M30 system. Every number it is quoted at was measured "
         "on M1 and none of it transfers upward: the spread is a far smaller "
         "fraction of the move up there, the stop and trail are sized in an "
         "ATR that means something different, and the trade count collapses.");
   Print("Higher timeframes are for CONTEXT. Reading H4 is not trading H4. "
         "E-133 measured H1 and H4 as direction sources against M1 across nine "
         "variants and not one of them beat M1.");
   Print("Attach this to M1, M3, M5, M15 or M30, or raise InpMaxTF deliberately.");
   return false;
}

#endif  // TIMEFRAME_GUARD_MQH

//==============================================================
// END TimeframeGuard.mqh
//==============================================================
CTrade trade;

//===================================================================
//  EVERY PRICE SCENARIO, AND WHAT THIS EA DOES ABOUT IT
//===================================================================
//  Written out because "think of every scenario" is only answerable if the
//  answers are listed somewhere they can be checked against the code.
//
//  ENTRY
//   signal fires, open air ahead ....... take it
//   signal fires, level in the way ..... REFUSED (InpSkipNoRoom), reason logged
//   signal fires, market chopping ...... refused ONLY if InpUseChopGuard is
//                                        on, and it is OFF by default. Until
//                                        2026-09-01 this line claimed a
//                                        refusal the EA did not implement at
//                                        all. The guard now exists; the
//                                        measurement (E-053) does not support
//                                        switching it on, so it is not on.
//   spread eats the trade .............. REFUSED (InpUseCostGate). The whole
//                                        round trip, not just the spread,
//                                        measured against the stop
//   want a better price ................ rest a limit InpPullAtr back
//                                        (InpUseLimitEntry). Measured +0.451R
//                                        vs +0.321R out-of-sample on GOLD 1h
//   limit never filled ................. cancelled after InpLimitLifeBars and
//                                        logged, so the miss rate is visible
//   second signal while one is live .... ignored; one position or one pending,
//                                        never both
//
//  HOLD
//   trade in profit .................... trail follows at InpTrailAtrMult,
//                                        ratcheting - it never gives ground back
//   approaching a level ................ bank half (InpPartialAtLevel), let the
//                                        rest ride through if it breaks
//   trade stalls ....................... closed after InpMaxBars
//   trend flips against it ............. closed
//
//  WHEN THE LEVEL IS NOT RESPECTED - and it often is not
//   This is why the position is SPLIT at a level rather than closed there.
//   Nobody knows in advance whether a level holds, so the trade stops guessing:
//   half is banked while the level is still in front of price (the "pennies"),
//   and the remainder trails through it if it breaks (the big move). A level
//   that fails costs the banked half's upside and nothing else; a level that
//   holds means the runner's trail takes it out near the high. There is no
//   configuration of a single all-or-nothing exit that wins both cases.
//
//  EXIT - IN THE ORDER THEY ACTUALLY FIRE
//   guard breach .... every tick. A daily-loss or max-drawdown breach closes
//                     everything (InpFlattenOnBreach) and locks the EA. It
//                     outranks every rule below it.
//   give-back ....... every tick. Once a trade has been at least 1R good,
//                     handing back the allowed fraction of that best BANKS
//                     HALF (InpGbClosePart) and leaves the rest on the trail.
//                     Fires once per position.
//   basket protect .. every tick. The same idea on the TOTAL of every open
//                     position plus what this basket has already realised.
//                     Four trades can each behave and still round-trip the
//                     total; nothing but a total-level rule sees that.
//   partial at level. bank half approaching a level, let the rest run
//   trail ........... 3 ATR behind, ratchets only, bar close
//   STALL ........... closed after InpMaxStall bars with NO NEW HIGH. This is
//                     the primary time exit. A trade that stopped climbing is
//                     measurably a different trade from one that has not, and
//                     the blind bar cap could not tell them apart (E-056).
//   time cap ........ closed after InpMaxBars. A backstop now.
//   target .......... capped just SHORT of the next level, so it fills rather
//                     than watching price turn a tick away from it
//   stop ............ attached at OrderSend, never held in EA memory only
//   gap through it .. the broker fills at the gap; the journal records the real
//                     price, not the intended one
//
//  WHAT IT DOES NOT DO, stated so it is not assumed
//   It does not re-enter automatically after a stop-out. It does not add to a
//   winner. It does not trade news events differently. And it cannot make a
//   drawdown-free entry exist - see the note on InpUseLimitEntry: the median
//   winning trade first goes 0.35R AGAINST the entry, and 10% go 0.85R against.
//   Minimising that is possible; eliminating it is not.
//===================================================================

//============================== INPUTS ==============================
// 21 inputs. The EA this replaces had 748.

input group "=== SIGNAL (identical to your Pine) ==="
input int    InpStAtrLen      = 7;      // SuperTrend ATR length
input double InpStMult        = 1.2;    // SuperTrend multiplier
input int    InpDemaLen       = 200;    // DEMA length used when per-clock is OFF
input bool   InpDemaPerClock  = true;   // E-092: 60 on M1, 100 on M3, else the above
input bool   InpUseDemaFilter = true;   // only trade with the DEMA slope

input group "=== EXIT (measured on THIS strategy, out-of-sample) ==="
// Every default below held on data the test never saw (GOLD 1h, 70/30 split):
//   fixed 3R      in-sample +0.183R   out-of-sample +0.394R
//   time 50 bars  in-sample +0.293R   out-of-sample +0.506R
//   trail 3xATR   in-sample +0.248R   out-of-sample +0.505R   <- default
// Re-measured 2026-09-01 on the full sample with supertrend_sniper_ea entries
// (E-051b): trail 3xATR = +0.488R on GOLD 1h, +0.051R on GOLD 15m. The 0.505
// figure above is an out-of-sample slice and is consistent with it. Do NOT
// confuse either with E-051's +0.077R for the same rule - that number is from
// DONCHIAN entries and does not describe this EA.
//   BE@1R + trail in-sample +0.110R   out-of-sample lower      <- still off
// A WIDE trail is not the same thing as moving to break-even. The trail rides
// 3 ATR behind price and only ever ratchets in your favour; break-even parks
// the stop at entry and gets scratched by noise. That distinction is the whole
// difference between +0.505R and the worst rule tested.
// NO HARD TAKE PROFIT. 0 = uncapped, and that is the shipped default.
//
// Veer: "we can't measure rr because some trades do 40rr some 0.5". He is right
// and it was a criticism of my method, not of the strategy. Every SuperTrend
// measurement in this project used a fixed 2R or 3R target, and if the edge
// lives in a tail then a fixed target is the one thing guaranteed to destroy
// it: it turns the 28R trade into a 3R trade and then reports the average as
// though nothing was lost.
//
// E-090 removed the ceiling. GOLD 1h, identical entries:
//     capped at 3R,  stop 2.0 ATR   mean +0.156R   +1035 points   best +3.0R
//     UNCAPPED,      stop 2.0 ATR   mean +0.178R   +1245 points   best +8.3R
//     UNCAPPED,      stop 0.6 ATR   mean +0.275R    +601 points   best +28.0R
//
// And the tail is real. On the tight-stop run the TOP 5% OF TRADES CARRY 68%
// OF ALL GROSS PROFIT; trades reaching 10R are 4% of the count and 53% of the
// money. 16% of trades win. That is the shape he has been describing all along.
//
// The 2.0 ATR stop is kept rather than the tight one, because E-090 also asked
// whether the tail protects against the spread and it does NOT - the tail
// winners are 4% of trades and the other 84% each pay the full spread. At M1's
// cost burden the 0.6 ATR version falls to +0.065R and 69 points while the
// 2.0 ATR version holds +0.114R and 880.
input double InpTargetR       = 0.0;    // hard take profit at N x risk. 0 = none
input int    InpMaxBars       = 50;     // absolute ceiling. See InpMaxStall first.

input group "=== STALL (E-056: the strongest result in this project) ==="
// Veer: "what if price reacts to our position but has slow price action how
// do we know how to move".
//
// STALL = bars since the position last made a NEW BEST. A trade that printed
// a new high on the last bar has stall 0; one that peaked thirty bars ago has
// stall 30. InpMaxBars cannot tell those apart. They are not the same trade.
//
// MEASURED on every bar of every trade that reached +0.5R, across 8
// market/timeframe combinations. P(gives it back to break-even before adding
// another 0.5R), minus each market's own base rate:
//
//   stall      0-1     1-3     3-6    6-12   12-25     25+
//   worse in   0/8     0/8     3/8     7/8     7/8     8/8   markets
//
// Monotone in every market. GOLD 15m in absolute terms: 24.0% give-back at
// stall 0-1 against 62.1% at stall 25+. GOLD 1h: 18.0% against 47.3%. That is
// a 30-to-38 point swing available from a number the EA already has.
//
// CAVEAT, because it is a real one: those are observations per BAR, so rows
// within one trade are correlated and the confidence intervals in the study
// are too narrow. What carries the finding is the 8-of-8 unanimity, which
// correlated sampling inside a trade cannot manufacture.
input bool   InpUseReversalExit = true; // close when structure breaks against the trade
input int    InpMaxStall      = 25;     // close a stalled trade after this many bars
input bool   InpStallScales   = true;   // and tighten the give-back as it stalls
input double InpImpulseAtr    = 2.0;    // a bar this many ATRs wide is an impulse
// VEER'S -GBP12 TRADE, and it is a rule not a story.
// "there was a volume candle shot up and we entered a sell the second it
// closes immediately shot up in 2 pound profit but unfortunately that candle
// started a trend and we made -12p".
//
// That is the EA selling INTO a fresh up-impulse. The SuperTrend flips on the
// pullback that always follows a big candle, so the signal fires in the exact
// direction the impulse is not going. The +GBP2 was the pullback; the -GBP12
// was the trend the candle had just started.
//
// E-057 measured the two sides of this and they disagree by size: a 2 x ATR
// impulse typically hands back MORE than its own range (median 1.07-1.36,
// beating a matched control in 8 of 8), but a 4 x ATR impulse hands back much
// less (median 0.55-0.79) and continues. So a small impulse is faded safely
// and a BIG one is not - which is exactly the candle that cost him GBP12.
// n was 38-57 at 4 x ATR, too few to size on, but the direction is clear and
// the cost of being wrong here is asymmetric.
input double InpNoFadeAtr     = 3.0;    // refuse a signal AGAINST a bar this big
input int    InpNoFadeBars    = 3;      // ...for this many bars afterwards
input double InpImpulseTighten= 0.70;   // tighten the give-back by this after one
input bool   InpUseTrail      = true;   // ON: measured best on SuperTrend entries
input double InpTrailAtR      = 0.0;    // arm immediately. A wide trail needs no delay
input double InpTrailAtrMult  = 3.0;    // 3 ATR. Wide on purpose - tight trails lost
input bool   InpUseBreakEven  = false;  // KEEP FALSE. Worst rule on all 4 markets
input double InpBreakEvenAtR  = 1.5;    // only used if you switch BE on to test it
input bool   InpPartialAt1R   = false;  // close half at 1R, let the rest run

input group "=== FILTERS (both held out-of-sample) ==="
// Measured by partitioning every trade by the condition it opened in, then
// re-checking on held-out data. GOLD 1h:
//   ADX > 35 (already-extended trend) : -0.132R   <- the losing bucket
//   ADX < 20 (quiet before expansion) : +0.304R
//   skip ADX>35 : in-sample +0.053R -> out-of-sample +0.426R  HELD
//   NY session  : in-sample +0.181R -> out-of-sample +0.704R  HELD
//   both        : in-sample +0.293R -> out-of-sample +0.672R  HELD
// THE TRADE-OFF, STATED: these filters roughly THIRD the number of trades
// (2.6/week -> 0.8/week on gold 1h). They raise expectancy per trade and cut
// how many you get. Turn them off for frequency, on for quality.
// OFF. E-074 audited all eight gates on the EA's own signals with its own exit.
// On GOLD the ADX ceiling refuses 323 of 1323 signals - a quarter of them - for
// a difference of +0.087R that is inside its own error. Gold, gates in
// combination, points banked per 0.01 lot:
//
//     DEMA + ADX + cost gates (the EA before this)   519 trades   +4445
//     DEMA + cost gates       (the EA now)           625 trades   +4639
//
// More trades AND more money. The DEMA filter is a different animal and stays
// on: it is worth +0.316R of separation on gold, and with it removed the whole
// edge collapses from +0.275R to +0.111R. It is the only gate in this EA that
// has ever paid for itself.
input bool   InpUseAdxFilter  = false;  // skip entries when the trend is already extended
input double InpMaxAdx        = 35.0;   // ADX ceiling
input bool   InpUseSession    = false;  // restrict to one session (see below)
input int    InpSessFromUTC   = 13;     // NY open
input int    InpSessToUTC     = 20;     // NY close

input group "=== ENTRY STYLE (this is the drawdown question) ==="
// MEASURED, GOLD 1h, out-of-sample, next-bar fills, ties losing:
//    market at next open ........ +0.321R    0% missed
//    limit 0.15 ATR back ........ +0.393R   11% missed
//    limit 0.30 ATR back ........ +0.451R   23% missed
//    limit 0.50 ATR back ........ +0.473R   37% missed
// The mechanism is not a guess either: 71.7% of signals close back THROUGH the
// signal price within three bars, so a resting limit gets filled most of the
// time at a better price - and a better entry is a smaller drawdown on the
// same trade.
// The honest wrinkle: IN sample the market entry looked better, so the two
// halves disagree, and t = +2.47 is under this repo's 3.65 luck threshold.
// It is the best-supported way to cut drawdown here, not a certainty.
input bool   InpUseLimitEntry = false;  // rest a limit instead of paying the market
input double InpPullAtr       = 0.30;   // how far back to wait (x ATR)
input int    InpLimitLifeBars = 3;      // cancel it if unfilled after this many bars

input group "=== LEVELS (the EA can now see them) ==="
input bool   InpUseLevels     = true;   // find levels and trade around them
input int    InpPivotBars     = 5;      // swing size for a level
input int    InpLevelLookback = 400;    // bars to scan for swings
input bool   InpUseDayLevels  = true;   // previous day high / low
input bool   InpUseWeekLevels = true;   // previous week high / low
input bool   InpUseRound      = true;   // round numbers (gold clusters stops there)
input double InpRoundStep     = 10.0;   // round number spacing
input double InpNearAtr       = 0.60;   // "close to a level" = within this x ATR
input double InpLevelBufAtr   = 0.25;   // park the target THIS far short of it
input bool   InpTpAtLevel     = true;   // cap the target at the next level
input bool   InpPartialAtLevel= true;   // bank half there, let the rest run
input bool   InpSkipNoRoom    = true;   // refuse entries with a level in the way
input double InpMinRoomR      = 1.0;    // need at least this much room, in R

input group "=== RISK ==="
input group "=== AFTER A CLOSE ==="
// Veer: "when we finish a buy or a sell we do not need to immedtily look to
// take a trade in the same direction can we understand that its causing us
// loss m1 trends are not often big unless caused by liquidity sweep".
//
// He is describing the same thing E-052 measured from the other end: the far
// end of a one-way run was worse in 7 of 8 markets. A SuperTrend flip back
// into the direction you just closed is usually the same run continuing, not
// a new one - and on M1 that run is usually already over.
//
// So a same-direction entry has to WAIT after a close. The opposite direction
// is free to fire immediately: that is a genuine change of mind by the market,
// not the tail of the trade that just ended.
// 15 bars was too blunt. Veer has said from the start that 100+ signals a day
// is FINE and the problem is what happens AFTER the entry, not the entry count
// - and E-053 measured that filters shrink a system toward zero rather than
// improving it. 3 bars stops the instant re-entry on the same candle he was
// complaining about without deleting the day.
input int    InpReentryCool   = 3;      // bars before re-entering the SAME way
input bool   InpReentryNeedsNewSignal = false; // ...and only after price makes a new extreme

input group "=== SIZE ==="
// OFF by default since E-063. The stop now widens itself when the spread is
// large relative to ATR, and a fixed lot against a wider stop simply risks
// more money - on M1 gold that is GBP 4.74 a trade instead of GBP 1.78, which
// is 4.2% of a GBP 112 account. Percent-risk sizing keeps the money constant
// and lets the geometry move, which is the point. Set it back to true only if
// you want a fixed 0.03 regardless of what the stop is doing.
input bool   InpUseFixedLots  = false;  // fixed size instead of % risk
input double InpFixedLots     = 0.03;   // total size for one entry
input double InpRiskPct       = 0.50;   // % of equity risked per trade (if not fixed)
// 2.0, not 1.5. E-071 measured every stop/target pair on the EA's own signals.
// GOLD, points made per 0.01 lot:  1.5 ATR stop / 3R = +715.  2.0 ATR / 3R =
// +1385.  Same entries, same target, one number changed. A 1.5 ATR stop on M1
// gold sits inside the noise the flip bar itself just made, so the trade is
// stopped by the move that signalled it. Nothing else in this file changes.
input double InpStopAtrMult   = 2.0;    // stop distance in ATR
// THE COST FLOOR ON THE STOP. E-063, and it is the most important line in
// this file.
//
// Veer's measured gold spread is 0.46. His M1 bars run 0.3-0.8, so ATR(7) is
// about 0.5 and a 1.5 x ATR stop is 0.75 POINTS. The round trip is 0.56.
// That means cost/stop is 0.75 and THE SPREAD ALONE IS 61% OF THE DISTANCE TO
// THE STOP - every trade is filled 0.46 in the red on a 0.75 stop and has to
// travel three quarters of its own risk to reach zero.
//
// E-053 measured that every market under 0.07 cost/stop was positive and both
// markets over 0.40 lost about a third of a unit of risk per trade. M1 gold at
// the shipped settings was 0.75, off the end of that table.
//
// So the stop is now the LARGER of the ATR distance and this many round trips.
// It is self-adjusting: on 15m and 1h the ATR term wins and nothing changes;
// on M1 the cost term takes over and the stop widens to where the trade is not
// mostly fee. No per-timeframe tuning, no guessing.
//
// IT MOVES THE RISK. A 4 x ATR M1 stop is 2.0 points = GBP 4.74 at 0.03 lots
// against GBP 1.78 before. Turn InpUseFixedLots OFF so InpRiskPct carries the
// sizing once the stop is honest, or the wider stop simply risks more money.
// 7.0, not 4.0. This one input solves the M1 cost problem WITHOUT hardcoding a
// timeframe, and the mechanism was already here - the EA WIDENS the stop to
// meet it rather than refusing the trade.
//
// E-089 measured where the edge dies as the spread grows relative to the stop:
//     cost/stop 0.07   +0.249R      cost/stop 0.22   +0.041R
//     cost/stop 0.12   +0.177R      cost/stop 0.29   -0.077R
// It needs to stay at or under about 0.14, which is 7 round trips of stop.
// At 4.0 it allowed 0.25, which is inside the range where the edge is gone.
//
// What it does in practice, at 0.01 lots on M1 gold:
//     spread 0.46 -> stop widens to 3.92 points = GBP3.09 a trade
//     spread 0.20 -> stop widens to 2.10 points = GBP1.65 a trade
// So a tighter spread buys a tighter stop automatically, on every timeframe,
// with no setting to change. Veer says his spread is not large; this is the
// input that turns that into money rather than into an argument.
input double InpMinStopCostX   = 7.0;   // stop must be at least this many round trips
input double InpMaxSpreadAtr  = 0.15;   // skip entry if spread > this x ATR

input group "=== COST GATE (E-053: this is the real M1 problem) ==="
// The old gate looked at the SPREAD only. That is not the cost of a trade -
// it ignores the commission and both slippages, which on gold add roughly 55%
// on top of the spread. This gate measures the whole round trip against the
// stop distance, which is the number that actually separated the winning
// markets from the losing ones:
//
//   market       cost/stop   stop is N x cost   expectancy
//   GOLD 1h        0.028         35.2x            +0.335R
//   GOLD 15m       0.039         25.9x            +0.227R
//   US500 15m      0.067         14.9x            -0.319R
//   GBPUSD 1h      0.150          6.7x            -0.076R
//   GBPUSD 15m     0.412          2.4x            -0.344R
//   EURUSD 15m     0.429          2.3x            -0.356R
//
// Extrapolated to M1 gold by the square root of bar duration, cost/stop is
// 0.15 to 0.22 - four to six times the 15m figure, and level with the FX
// markets that lose. That is the arithmetic behind "we perform shit in
// sideways price action": a 24-minute $4.50 range does not contain enough
// movement to pay for sixteen round trips that each cost a fifth of their
// own risk. It is not the range that is fatal, it is the toll.
//
// This gate is the one part of that the EA can settle WITHOUT a backtest,
// because it reads the live spread at the moment of the decision.
input bool   InpUseCostGate   = true;
// 0.10 WAS A BUG AND IT SILENCED THE EA. E-053 measured M1 gold at 0.15-0.22
// cost/stop, so a 0.10 ceiling refused essentially EVERY M1 entry - which is
// exactly what Veer saw: "we are now not hitting same trades as before and
// having delayed entry". A gate is supposed to catch a blown-out spread, not
// to be the normal state of the market. 0.30 catches news and a broken feed
// and nothing else. The cost problem is real (see E-053) but the answer to it
// is a wider stop or a different timeframe, NOT refusing to trade.
input double InpMaxCostFrac   = 0.30;   // refuse only when the spread is genuinely blown out
input double InpCommPerLot    = 7.0;    // commission per lot, ROUND TURN, in the ACCOUNT currency
input double InpSlipSpreads   = 0.25;   // expected slippage per side, as a FRACTION of the spread

input group "=== CHOP GUARD (present so it can be tested, not argued about) ==="
// DEFAULT OFF, and the reason is the measurement, not caution. Across 8
// market/timeframe combinations, skipping the lowest-efficiency bucket
// improved total R in 5 of 8 - a coin flip with one extra head. Worse, the
// PATTERN of who it helps is damning: it took EURUSD 15m from -95.1R to
// -71.4R and GBPUSD 15m from -90.2R to -54.5R, while taking GOLD 1h from
// +124.9R to +91.8R and US500 1h from +19.6R to -3.2R.
//
// It helps losing systems and hurts winning ones, because it does not select
// - it removes trades roughly proportionally and drags the result toward
// zero. A chop filter is not a way to limit loss. It is a way to trade less.
//
// It is here because Veer asked for it and because GOLD 15m, the nearest
// thing to his instrument, did improve (+13.2R). Turn it on to test it on
// the journal, not because this comment recommends it.
// E-066. WHERE THE STRATEGY ACTUALLY MAKES MONEY, and it is not where anyone
// would guess. 2,967 trades across 8 market/timeframe combinations, bucketed
// by the 50-bar efficiency ratio (net distance / path walked):
//
//                 chop(<0.10)   MIXED(0.10-0.25)   trend(>0.25)
//   slow            -0.027         +0.192            -0.267
//   normal          -0.053         -0.023            -0.072
//   fast            -0.181         +0.063            -0.097
//
// The money is in the MIDDLE. Dead chop loses at every speed and an already-
// established trend loses at every speed. That is mechanically obvious once
// seen: a SuperTrend catches TURNS - in chop the turns are noise, and in a
// running trend the turn already happened and this is late.
//
// GOLD 1h, the closest thing to Veer's instrument: base +0.339R, and the
// normal/mixed cell is +0.549R on 102 trades - the strongest cell anywhere
// with enough trades to mean something.
//
// THIS IS SIZING, NOT FILTERING, and the distinction is the whole point.
// Veer has said from his first message that signal count is not the problem
// and E-053 measured that filters only drag a system toward zero. Every
// signal is still taken. The bad regimes are taken SMALLER and the good one
// BIGGER, so the edge is weighted rather than the trades deleted.
// ── THE MIDDLE OF THE RANGE (E-084 / E-085) ──────────────────────────────────
// Nine backward-looking price-action descriptors were measured against every
// trade. Eight showed nothing coherent. One showed a clean U:
//
//   GOLD 1h, where the entry sits in the last 20-bar range, by quintile
//     bottom 36%   +0.221R      <- at the range low: a real reversal
//     0.36-0.50    -0.013R
//     0.50-0.63    -0.159R      <- these two carry 53% OF ALL LOSSES
//     0.63-0.78    +0.341R
//     top 22%      +0.372R      <- at the range high: a real break
//
// A SuperTrend flip AT an extreme is a genuine break or reversal. The same flip
// in the MIDDLE of a range is the market changing its mind inside noise - the
// "false move" Veer describes, and exactly where a trend signal should fail.
//
// It is not a fluke of one bucket: it is a U with a mechanism, it replicates on
// 15m, and it HOLDS OUT OF SAMPLE in all four splits tested - the separation is
// actually LARGER out of sample on 1h (+0.453R against +0.225R in-sample).
//
// Pooled 1h+15m, points banked per 0.01 lot:
//     leave it alone            447 trades   +1551
//     QUARTER SIZE in the band  447 trades   +1801   <- shipped
//     half size in the band     447 trades   +1718
//     skip the band entirely    219 trades   +1885
//
// Skipping books slightly more and costs HALF THE TRADES. Quarter size keeps
// every trade and 96% of the benefit, which is the right trade for someone who
// wants the signal count. Set InpMidRangeSize to 0.0 to skip instead.
input int    InpRangeLook     = 20;     // bars for the range position
input double InpMidRangeLo    = 0.35;   // the losing band starts here...
input double InpMidRangeHi    = 0.70;   // ...and ends here
input double InpMidRangeSize  = 0.25;   // size multiplier inside it (0 = skip)

input bool   InpUseRegimeSize = true;   // size by market shape (E-066)
input double InpRegimeChopX   = 0.70;   // multiplier in dead chop
input double InpRegimeMixX    = 1.25;   // ...in the middle, where the money is
input double InpRegimeTrendX  = 0.70;   // ...in an already-running trend

input bool   InpUseChopGuard  = false;
input int    InpChopErLen     = 50;     // BARS, never minutes - flip density is per bar
input double InpMinEffRatio   = 0.08;   // skip below this efficiency ratio
input int    InpChopFlipLen   = 20;     // bars to count SuperTrend flips over
input int    InpChopMaxFlips  = 5;      // skip at this many flips or more

input group "=== PROP FIRM GUARDS ==="
input double InpDailyLossPct  = 3.0;    // stop for the day at this % equity loss
input double InpMaxDDPct      = 6.0;    // stop permanently at this % from peak
input int    InpMaxTradesDay  = 20;     // hard cap on entries per day
input int    InpResetHourUTC  = 0;      // daily reset hour, UTC
input bool   InpFlattenOnBreach = true; // close open positions when a limit breaks

input group "=== SAFETY ==="
input bool   InpDemoOnly      = true;   // refuse to run on a live account
input long   InpMagic         = 770001; // magic number
input bool   InpVerboseLog    = true;   // log every decision
input bool   InpJournal       = true;   // write every signal and fill to a CSV

input group "=== PROFIT PROTECTION (E-051: measured, not guessed) ==="
// This is the answer to "we need to stop watching profit disappear", and it
// is NOT a fixed take profit. A fixed TP decides in advance how big the move
// will be, which nobody knows. This rule decides nothing in advance: it
// remembers the best the trade ever was and acts when a fixed fraction of
// that best has been handed back.
//
// MEASURED ON THIS EA'S OWN ENTRIES (E-051b). An earlier version of this
// comment cited E-051's "beat the trail on 5 of 5 markets". That number was
// real but it was computed on DONCHIAN entries, not on this strategy's, and
// citing it here was wrong. Re-run on supertrend_sniper_ea:
//
//   market       trail 3xATR   give-back 30%   expectancy winner
//   GOLD 1h        +0.488R        +0.158R        TRAIL, by three times
//   GOLD 15m       +0.051R        +0.015R        trail
//   GBPUSD 15m     -0.371R        -0.393R        trail
//   EURUSD 15m     -0.541R        -0.433R        give-back
//   US500 15m      -0.215R        -0.101R        give-back
//
// So on gold the trail EARNS MORE and closing on give-back is the wrong
// trade. What the give-back rule buys is a much kinder path:
//
//   GOLD 1h            expectancy   max DD   P(DD > 30%)
//   trail 3xATR          +0.488R      42%        57%
//   give-back only       +0.158R      40%        39%
//   HALF AND HALF        +0.323R      38%        29%   <- what this ships
//
// Banking HALF at the give-back trigger and leaving the rest on the trail
// keeps two thirds of the trail's expectancy for half its chance of a 30%
// drawdown. That is why InpGbClosePart defaults to 0.5 rather than 1.0: the
// rule below does not close the trade, it banks part of it, once.
//
// WHAT IT IS NOT: it did not beat a random entry on GOLD 1h (E-050), and
//   EURUSD/GBPUSD stay negative under every exit rule tried. It shapes the
//   equity path. It does not manufacture an edge.
// RETUNED 2026-09-02 FROM A LIVE TRADE VEER REPORTED.
// Two 0.01 positions peaked at GBP 2.50 together and closed at GBP 0.47 each -
// GBP 0.94 kept out of GBP 2.50, so 62% of the peak was handed back. He has
// also seen peaks of GBP 8 close for a fraction.
//
// WHY THE OLD SETTINGS LET THAT HAPPEN: the rule armed at 1.0 R and then
// allowed 24-30% of the peak back. On 0.01 lots one R is a large number in
// MONEY, so a trade could run up GBP 2.50, never reach the arming threshold in
// R terms on a wide stop, and give the lot back with the rule never firing.
//
// TWO CHANGES:
//  1. It now arms on MONEY OR R, whichever comes first. Veer thinks in pounds
//     and trades 0.01 lots; a rule that only speaks R is blind to exactly the
//     trades he is complaining about.
//  2. The allowances are roughly a third tighter. At GBP 2.50 peak and a 20%
//     allowance the trade closes at GBP 2.00 instead of GBP 0.94.
//
// THE COST, STATED: E-051b measured that a tighter give-back keeps LESS
// expectancy - it sells the runners that pay for the losers. Veer has chosen
// the certain smaller number over the larger uncertain one three times now, in
// writing: "we are not looking for massive profits ... we want small
// consistent profits hundreds of times". These settings do what he asked for.
input bool   InpUseGiveBack   = true;   // leave when profit is handed back
// ARMING IS THE WHOLE ARGUMENT, AND IT IS A DIAL, NOT A SWITCH.
// E-075 re-measured every exit policy on this EA as it now stands (2.0 ATR
// stop, ADX gate off), all on the same entries. GOLD 1h, 459 trades:
//
//     give-back 30% armed at 1.0R   +0.136R   +2251 points
//     give-back 25% armed at 1.5R   +0.227R   +3210 points
//     give-back 30% armed at 2.0R   +0.295R   +3763 points
//     give-back 25% armed at 3.0R   +0.368R   +4313 points   <- best expectancy
//     trail 3xATR armed at 1.0R     +0.347R   +4622 points   <- best points
//
// The give-back RULE was never the problem. Arming it early was. At 0.6R and
// GBP0.30 - where this EA has been - it fires on ordinary trades and caps
// them, and that is where the "3x worse than the trail" result came from. Armed
// at 3R it is the highest-expectancy rule tested and it still does the job
// Veer actually asked for: "was up 2.50 on two 0.01s total and closed at 47p".
// A GBP2.00 floor protects that peak. A GBP0.30 floor protects nothing and
// costs the runners that pay for the losers.
//
// Honest note: on POINTS the trail alone still wins (+4622 vs +4313). Keeping
// the give-back armed high is a deliberate concession to a preference Veer has
// stated three times in writing, and it now costs about 7% rather than 65%.
// ARMING IS IN R, AND THE MONEY IS A FLOOR - NOT AN ALTERNATIVE TRIGGER.
//
// This used to read "arm at 3R OR at GBP2.00, whichever comes first", and that
// OR was a bug that made the money term decide everything, on every timeframe:
//
//   GOLD 1h, one R is about 28 points, so GBP2.00 at 0.03 lots is 0.03R
//   M1,      one R is about 1.3 points, so GBP2.00 is about 0.65R
//
// Either way the money branch fires long before 3R, so the R setting never did
// anything and the give-back armed almost immediately - which E-075 measured
// as the worst end of the dial (+0.136R armed at 1R against +0.368R at 3R).
// P91b then found the same disease in the trail: sweeping its arming level
// from 0R to 2R changed NOTHING, because the trade was always already closed.
//
// A money threshold does not survive a change of timeframe OR of lot size, and
// this EA has to run on M1 at 0.01 lots after being measured on 1h at 0.03.
// So R decides, and the money is only a floor that stops the rule acting on
// noise. Scale-free, in the R grid, both timeframes agree:
//
//   GOLD 1h   lock 1.0R + give-back 3.0R   +0.152R  +1112 points
//   GOLD 15m  lock 1.0R + give-back 2.0R   +0.175R   +463 points
//             lock 1.0R + give-back 3.0R   +0.174R   +439 points
// THE PROFIT STOP. Arms EARLIER than the give-back on purpose: its job is not
// to decide when the trade is over, it is to stop a spike taking back money
// that was already made. A stop at 1R of peak costs nothing while the trade
// keeps running - it only ever moves up - and it is the only mechanism here
// that works when no tick reaches the EA.

// ── THE DISASTER BRAKE (E-091) ───────────────────────────────────────────────
// Veer: "stop loss initially is way too far, if news or reversals happens
// that's a massive massive loss unless we can close immediately thru ea."
//
// He is right, and it is a consequence of my own fix: E-089 forced the stop
// WIDER (7 round trips) so the spread could not own it, which makes a full
// stop-out a big loss. A wide stop with no faster brake is not risk management,
// it is a bigger bet.
//
// But "cut early" is the classic rule that feels safe and costs money, so it
// was measured rather than assumed. GOLD, points against leaving the trade
// alone:
//
//   cut when never green and 0.40 of the stop against us    1h  -779   15m  +35
//   cut when never green and 0.55 of the stop against us    1h  -682   15m   +6
//   cut on 0.8 ATR against us in 2 bars                     1h   +16   15m -185
//   cut on 1.2 ATR against us in 2 bars                     1h  +181   15m -251
//   cut on 1.8 ATR against us in 2 bars                     1h    -6   15m   -4
//
// EVERY TIGHT BRAKE COSTS MONEY. The trades they cut recover. Only the far-out
// one is free: it fires on about 6% of trades and its cost is inside the noise.
//
// So this brake is set to catch a DISASTER and nothing else. It is insurance,
// not a trading rule, and it is priced at zero. Tightening it below about 1.5
// ATR is measurably paying to feel safer.
input bool   InpUseBrake      = true;   // emergency close on a violent move against us
input double InpBrakeAtr      = 1.8;    // ...this many ATR against us...
input int    InpBrakeBars     = 2;      // ...within this many bars
input double InpMaxSpreadX    = 3.0;    // also close if the spread blows out this much

input bool   InpUseProfitStop = true;   // push the give-back level to the BROKER as a stop
// E-095 — THE PRICE OF THIS NUMBER, MEASURED. It is NOT changed from 1.0,
// because 1.0 is Veer's written instruction (quoted below) and a preference is
// not a defect. But the cost was never measured before and now it has been.
//
// Sweeping the arming threshold, same entries, same everything else:
//
//              GOLD 15m                 GOLD 1h
//   arm at   points   trades >=4R    points   trades >=4R
//   OFF      +406.1        1        +1542.8        9
//   0.6R     +242.2        0        +1172.7        0
//   1.0R     +432.1        0        +1096.3        0     <- ships
//   1.5R     +402.6        0        +1232.4        0
//   2.0R     +399.7        0        +1242.5        0
//   3.0R     +391.2        1        +1234.2        1
//   4.0R     +462.7        2        +1744.5       12
//   6.0R     +406.3        1        +1616.1        9
//
// TWO THINGS ARE IN THAT TABLE.
//
// 1. ARMING EARLY ELIMINATES THE TAIL, MECHANICALLY. At 0.6R, 1.0R, 1.5R and
//    2.0R, the number of trades that reach 4R is ZERO on both timeframes. At
//    4.0R it is 2 and 12. This is E-090 exactly - the finding that a fixed 2R/3R
//    target was destroying the tail, and that the top 5% of trades carry 68% of
//    gross profit. The give-back stop armed at 1.0R is a fixed target wearing a
//    different hat. On GOLD 1h it costs 446 points against leaving it OFF.
//
// 2. THERE IS NO BASIS TO PICK A DIFFERENT EARLY VALUE. Within the arm-early
//    family the two timeframes DISAGREE: 15m prefers 1.0R (432.1) over 1.5R
//    (402.6) and 2.0R (399.7); 1h ranks 1.0R LAST of those three. So 1.0 stays.
//    The only setting that beats OFF on both is 4.0R, and that is the opposite
//    of what Veer asked for.
//
// E-075 recorded 3R as the best arming threshold it tested and this file ships
// 1.0. That gap is deliberate and documented, not an oversight.
//
// VEER'S INSTRUCTION, 2026-09-01: "although we wanna claim big big trends we
// want to actually CLOSE IN PROFIT ... im happy if maximum potential profit on
// a trend is not taken as long as we actually took a solid ammount."
//
// So: set this to 4.0 if you ever want the runners back. It measured +13% on
// 1h and +14% on 15m against OFF, and it is the only value that beat OFF on
// both. It will also mean more trades that go +1.5R and come back to the trail.
input double InpProfitStopArmR= 1.0;    // arm the profit stop at this peak R

input double InpGbArmR        = 3.0;    // arm once the trade is this good in R
input double InpGbArmMoney    = 0.30;   // AND at least this much money (noise floor)
input double InpGbBase        = 0.20;   // give back this much of the peak
input double InpGbTier2R      = 1.5;    // once the peak passes this...
input double InpGbTier2       = 0.16;   // ...allow only this much give-back
input double InpGbTier3R      = 3.0;    // and past this...
input double InpGbTier3       = 0.12;   // ...this much. Big peaks are protected hardest
input double InpGbMinMoney    = 0.10;   // but never act below this profit - noise
// 1.0 SINCE 2026-09-01, ON VEER'S EXPLICIT INSTRUCTION:
// "although we wanna claim big big trends we want to actually CLOSE IN PROFIT
//  ... im happy if maximum potential profit on a trend is not taken as long as
//  we actually took a solid ammount".
//
// That is a preference between two measured options, not a mistake. E-051b:
// banking HALF keeps about two thirds of the wide trail's expectancy for half
// its chance of a 30% drawdown; closing it ALL keeps less expectancy again and
// less drawdown again. He has chosen the certain smaller number over the
// larger uncertain one, twice now, in writing. Set it back to 0.5 to let the
// runner run.
input double InpGbClosePart   = 1.0;    // fraction to bank (1.0 = close it all)

input group "=== BASKET (manage the TOTAL, not one trade) ==="
// Veer's actual failure was never one trade: "the basket reached ~GBP12 and
// closed at breakeven; four positions reached ~GBP4 and still closed in loss".
// Four positions each individually behaving reasonably can still hand back
// the whole basket, because nothing was watching the total. Now something is.
input bool   InpUseBasket     = true;   // protect total floating profit
// Same retune. Veer's basket peaked at GBP 2.50 and the old floor of GBP 2.00
// meant it barely armed before the money was gone.
input double InpBasketArmPct  = 0.40;   // arm once the basket is this % of equity green
input double InpBasketMinMoney= 1.00;   // ...or at least this much money, whichever is lower
input double InpBasketGiveBack= 0.20;   // close the basket after handing back this much
input bool   InpBasketCloseAll= true;   // false = only close the losers, keep the winner
// Veer: "what if everytime a trade goes above 1 pound 20 TOTAL we put sl there
// although often it can hit that sl and then just run off".
//
// The second half of that sentence is the measured half. E-051 tested exactly
// this family: moving the stop to break-even was the WORST exit rule on all
// four markets, -0.161R to -0.308R, because it scratches out the trades that
// were about to pay for the losers. He knows - he said it himself.
//
// So it is here, on, at HIS number, and it does the least damaging version of
// the idea: it locks break-even plus the round-trip cost, so a trade that has
// been worth GBP1.20 can no longer become a loser, and it does NOT try to bank
// the GBP1.20 itself. Set InpLockAtMoney to 0 to switch it off entirely.
// "what about trades which go up say 30p then close in loss"
//
// A trade that has been genuinely green should not be allowed to become a
// loser. This locks EACH POSITION at break-even plus its own round trip once
// it has been InpLockPosMoney in profit, so the worst case becomes zero rather
// than a loss. The basket rule below does the same thing for the total.
//
// THE COST, AND IT IS REAL: E-051 measured break-even stops as the WORST exit
// rule on all four markets tested, -0.161R to -0.308R, because they scratch
// out the trades that were about to pay for the losers. Veer knows - he wrote
// "often it can hit that sl and then just run off" himself. The threshold is
// therefore set ABOVE noise: a trade has to have made real money before its
// downside is removed, and a trade still finding its feet is left alone.
input double InpLockPosR      = 1.0;    // lock a POSITION out of loss once this good in R
input double InpLockPosMoney  = 0.30;   // AND at least this much money (noise floor)
input double InpLockAtMoney   = 1.20;   // once the BASKET is this green, stops go to break-even+
input bool   InpLockOnlyOnce  = true;   // and are never pulled back afterwards
// STACKING IS OFF AND SHOULD STAY OFF.
// Veer, from the live account: "scale adds are making us profit but also loss
// its better to just had hold out that first trade and trail sl or look for a
// real reentry postion also scale adds make 0.01".
//
// That is the same conclusion the numbers reached from the other side. An add
// is taken at the WORST price of the move so far, it enlarges the position at
// the moment give-back risk is highest, and E-053 measured that adding trades
// does not add edge because the cost is charged per trade while the edge is
// not. The first trade with a trail, or a genuine re-entry after a close, is
// the same exposure without the extra fee and the extra fill risk.
input int    InpMaxStack      = 1;      // positions allowed at once. 1 = no stacking
input int    InpStackCoolBars = 5;      // bars between adds
input double InpMaxNetLots    = 0.0;    // hard cap on one-way exposure (0 = auto)

input group "=== TREND PERSISTENCE (trends do not last forever) ==="
// Veer, verbatim: "sometimes the ea will continue in one direction have it
// understand that it can be risky trends don't always last forever".
// MEASURED, not assumed (E-052). Eight market/timeframe combinations, outcome
// = P(+1R before -1R), each bucket read against that market's OWN base rate:
//
//   run older than 100 bars ....... below base in 7 of 8 markets, -3.4 points
//   run travelled over 8 ATR ...... below base in 7 of 8 markets, -3.0 points
//   ADX at entry above 25 ......... below base in 6 of 8 markets, -1.3 points
//
// And, for the record, the two readings that FAILED and were removed from
// this EA rather than kept because they sounded right:
//
//   consecutive same-way signals .. 4/8, 4/8, 2/6, 2/8, 5/8. A coin flip.
//   stretch from the DEMA ......... no gradient, and the CLOSE-to-the-mean
//                                   bucket was the bad one, not the far one.
//   at the top of the range ....... backwards - better in 6 of 8 markets.
//
// THE SIZE OF THIS EFFECT IS 3 PERCENTAGE POINTS on a base rate near 50%.
// It is real and it is consistent, and it is small. It is a reason to size
// down and to stop ADDING to an exhausted run. It is not a reason to expect
// a different system, and no score here blocks a fresh signal in a NEW
// direction - the finding is about continuing an old run, not about trading.
input bool   InpUseTrendAge   = true;
input int    InpRunOldBars    = 100;    // bars since the OPPOSITE signal = exhausted
input double InpRunFarAtr     = 8.0;    // ATR travelled in this run = exhausted
input double InpRunAdx        = 25.0;   // ADX at entry (weakest of the three)

input group "=== EXECUTION BOX (what is actually happening) ==="
input bool   InpShowBox       = true;   // on-chart profit and execution panel
input bool   InpShowProfitBox = true;   // the shared points/money ledger box
input int    InpBoxCorner     = 3;      // 0 top-left, 1 top-right, 2 bottom-left, 3 bottom-right
input int    InpBoxX          = 12;     // pixels in from that corner
input int    InpBoxY          = 12;
// The highest chart this EA will start on. M30 by default because that is
// where every number it is quoted at was measured - raise it deliberately.
input ENUM_TIMEFRAMES InpMaxTF = PERIOD_M30;
input long   InpTrackMagic2  = 880041;  // ZoneSniper, if you run it too
input string InpTrackLabel2  = "ZONE  st+liq";
input long   InpTrackMagic3  = 770069;  // LiquiditySniper
input string InpTrackLabel3  = "LIQUIDITY";
input bool   InpBoxComment    = true;   // ALSO print it as a chart Comment (cannot be hidden)
input int    InpBoxCorner     = 0;      // 0 top-left 1 top-right 2 bottom-left 3 bottom-right
input int    InpBoxX          = 12;     // pixels in from that corner
input int    InpBoxY          = 18;
input int    InpBoxSize       = 9;      // font size
input int    InpBoxWidth      = 330;    // backdrop width in pixels
input color  InpBoxBg         = C'13,17,23';   // solid, so the panel is readable
input color  InpBoxBorder     = C'48,54,61';
input color  InpBoxHead       = clrGold;
input color  InpBoxText       = clrGainsboro;

//============================ STATE ================================
datetime g_lastBarTime = 0;
double   g_dayStartEq  = 0.0;
double   g_peakEq      = 0.0;
int      g_tradesToday = 0;
int      g_dayStamp    = -1;
bool     g_lockedDay   = false;
bool     g_lockedPerm  = false;
int      g_atrHandle   = INVALID_HANDLE;
int      g_adxHandle   = INVALID_HANDLE;

// SuperTrend state, carried bar to bar exactly as the Pine does
double   g_lotClampX   = 1.0;    // how many times the asked-for risk we send
bool     g_lotClampWarned = false;
bool     g_configFatal = false;  // set by CheckConfigSanity(); blocks all entries
string   g_configWhy   = "";
double   g_finalUpper  = 0.0;
double   g_finalLower  = 0.0;
int      g_stDir       = 0;      // -1 bullish, +1 bearish (Pine convention)
int      g_stDirPrev   = 0;
bool     g_stReady     = false;

//================ BASKET / PEAK / TREND STATE ======================
// Per-position tracking. MQL5 has no dictionary, so this is parallel arrays
// with a linear find. MAX_TRACK is 64; the EA cannot open anywhere near that
// many, and an overflow degrades to "not tracked" rather than to corruption.
#define MAX_TRACK 64
ulong    g_tkId[MAX_TRACK];        // position ticket
double   g_tkPeakPx[MAX_TRACK];    // best favourable excursion, in price
// The peak as it stood BEFORE this tick. E-051 deliberately computed its
// trigger from the previous bar's peak, because using the same bar's high to
// place a trigger inside that bar assumes the high printed before the
// retrace - an assumption worth roughly a third of the measured result. The
// EA was raising the exit floor with the current tick and then testing the
// same tick against it, which is that assumption wearing a different hat.
// (Audit finding 7.) Testing against the previous tick's peak restores it.
double   g_tkPeakPrev[MAX_TRACK];
datetime g_tkCloseTry[MAX_TRACK];  // last close REQUEST, to stop tick-rate retries
bool     g_tkGbDone[MAX_TRACK];    // the give-back partial has already fired
bool     g_tkPeakImp[MAX_TRACK];   // the peak was set by an IMPULSE bar (E-057)
double   g_tkWorstPx[MAX_TRACK];   // worst adverse excursion, in price
double   g_tkRisk[MAX_TRACK];      // original risk distance, in price
double   g_tkPeakMoney[MAX_TRACK]; // best floating profit, in account currency
datetime g_tkPeakTime[MAX_TRACK];  // when that best happened
datetime g_tkPeakBar[MAX_TRACK];   // the BAR it happened on - stall is measured in bars
int      g_tkCount = 0;

// Basket-level. A "basket" is every position this EA has open on this symbol,
// treated as one trade, because that is how the account experiences it.
// BLOCKER 2, found by audit 2026-09-01. g_bkPeak only reset when FLAT, so
// money BANKED by a partial close was recorded as money GIVEN BACK. At the
// shipped defaults the arithmetic closed the runner every time: the basket
// arms at max(equity x 0.60%, GBP2) which is 1.2R at 0.5% risk, the level
// partial halves the floating profit, and the protection floor is 65% of the
// peak - and a half is always below 65%. So the trade reached a level, banked
// half exactly as designed, and the next tick liquidated the rest. That
// destroyed the "bank half, let the rest ride" design the scenario map calls
// the central answer to wanting both the pennies and the big moves.
//
// The fix is to define basket profit as FLOATING PLUS REALISED-SINCE-THE-
// BASKET-OPENED. A partial then moves money from one column to the other and
// leaves the total untouched, which is what actually happened.
double   g_bkRealized  = 0.0;     // banked by partials while the basket is open
double   g_bkPeak      = 0.0;      // best TOTAL profit this basket saw
datetime g_bkPeakTime  = 0;
datetime g_bkStart     = 0;
bool     g_bkArmed     = false;
bool     g_bkLocked    = false;   // stops have been pushed to break-even+

// Trend persistence. A "run" is the stretch of signals since the last one in
// the OPPOSITE direction - which is what E-052 measured, and is not the same
// as the current SuperTrend leg (the leg is fresh at every flip, and on M1
// there are dozens of flips inside one directional run).
int      g_barsInTrend   = 0;   // bars in the current SuperTrend leg (display)
// Flip history, newest first. Written by UpdateSuperTrend, read by the chop
// guard. 256 entries is far more than any window the guard can ask for.
#define MAX_FLIPHIST 256
uchar    g_flipHist[MAX_FLIPHIST];
int      g_flipHistN     = 0;

// The panel's readings are all closed-bar-only and therefore CONSTANT within
// a bar, but DrawBox recomputed them on every tick: EfficiencyRatio(50) alone
// is 103 iClose calls, and on an active M1 that was roughly 3,000 per second
// for a display that feeds no decision. (Audit finding 13.) Cached per bar;
// the money figures below still update on every tick, which is the only part
// a person actually watches move.
// SPREAD TELEMETRY. I have twice built an argument on a spread number I read
// off a chart rather than off the account that trades. Veer's EA runs on a
// different broker from his TradingView feed, and he says the spread is not
// large. Guessing again would be the third time, so the EA now MEASURES it:
// every tick updates the running picture, every entry records the spread at
// the moment of the fill, and the box shows it. One session of this settles
// what no amount of analysis can.
double   g_spMin         = 1e9;
double   g_spMax         = 0.0;
double   g_spSum         = 0.0;
long     g_spN           = 0;
double   g_spEntrySum    = 0.0;   // spread at the moment of each entry
int      g_spEntryN      = 0;
double   g_spEntryMax    = 0.0;

datetime g_boxBar        = 0;
double   g_boxEff        = 0.0;
int      g_boxFlips      = 0;
int      g_boxRisk       = 0;
string   g_boxRiskWhy    = "";
double   g_boxCost       = 0.0;
double   g_boxStop       = 0.0;
int      g_lastSigDir    = 0;   // direction of the last signal that passed the filters
datetime g_runStartBar   = 0;   // bar of the first signal of this run
double   g_runStartPx    = 0.0; // close at that bar
int      g_lastEntryDir  = 0;
int      g_lastCloseDir  = 0;   // direction of the last position that CLOSED
datetime g_lastCloseBar  = 0;
double   g_lastCloseExt  = 0.0; // the extreme price at that close
datetime g_lastEntryBar  = 0;

// Lifetime execution statistics - the numbers the box exists to show.
// These are what makes "we keep giving profit back" a measurement instead of
// an argument. They survive a terminal restart via GlobalVariables.
int      g_stTrades      = 0;   // closed positions
int      g_stWins        = 0;
int      g_stGreenRed    = 0;   // got >= 0.5R green and STILL closed <= 0
double   g_stRealized    = 0.0; // money actually banked, all time
double   g_stPeakSum     = 0.0; // sum of each trade's best-ever floating profit
double   g_stGivenBack   = 0.0; // that sum minus what was kept
double   g_stDayRealized = 0.0;
int      g_stDayTrades   = 0;
double   g_stWorstGB     = 0.0; // biggest single give-back seen

struct Basket
{
   int      n;            // open positions
   int      nLong;
   int      nShort;
   double   lots;         // total volume
   double   netLots;      // long lots minus short lots
   double   money;        // total floating profit, account currency
   double   wAvgEntry;    // volume-weighted average entry price
   double   peakMoney;    // best floating profit this basket ever showed
   double   givenBack;    // peak minus current
   double   bestR;        // best R across the open positions, right now
   double   peakR;        // best peak-R across the open positions
   int      oldestBars;   // bars the oldest position has been open
   int      sincePeakSec; // seconds since the basket peaked
   int      stall;        // BARS since any open position made a new best (E-056)
   int      dir;          // +1 net long, -1 net short, 0 flat or hedged
};

// FORWARD DECLARATIONS.
// MQL5 does compile a call to a function defined further down the file, but
// this EA has already been shipped three times in a state that would not
// compile (F-006, F-007, F-008), and each time the cause was an ordering or
// scoping rule I had assumed rather than checked. Prototypes make the
// question moot: every function below is declared before anything calls it,
// under any rule the compiler happens to use.
double MoneyPerPricePerLot();
string Money(double v);
int    TrackFind(ulong tk);
int    TrackAdd(ulong tk, double risk);
void   TrackDrop(int i);
void   Snapshot(Basket &b);
int    TrendRisk(string &why);
double GiveBackAllowed(double peakR, int stall, bool afterImpulse);
int    StallBars(int ti);
int    ReversalAgainst(int dir);
void   UpdatePeaks();
void   ProtectPositions();
void   ProtectBasket();
void   LockBasket();
void   LockPositions();
void   TrailProfitStop();
void   DisasterBrake();
bool   StackAllows(int dir, string &why);
void   RegisterEntry(int dir);
void   RegisterSignal(int dir);
int    RunBars();
double EfficiencyRatio(int len);
int    FlipsIn(int len);
double RoundTripCost();
double RunMoveAtr();
void   BoxLine(int idx, string txt, color c);
void   BoxClear();
void   DrawBox();
void   Readout();
long   g_readN = 0;   // readout beats, so a frozen box is visibly frozen
// LIVE ANSWER TO A DISAGREEMENT. Veer, forward testing on M1: "back to back
// same direction signals can cause loss as m1 trends are not often big". On
// the 1h/15m data in this repo that is measurably FALSE - same-direction
// signals are 342 of 447 trades and carry 86% OF ALL THE PROFIT (+0.211R
// against +0.004R for alternating ones). But his mechanism is explicitly about
// M1, where a trend may be five bars, and there is no M1 data here to test it.
// So instead of guessing, the EA COUNTS IT LIVE. After a few sessions his own
// account settles the question, on his own timeframe, with his own fills.
int      g_sdN   = 0;                 // same-direction trades
int      g_sdWin = 0;
double   g_sdSum = 0.0;
int      g_altN   = 0;                // alternating ones
int      g_altWin = 0;
double   g_altSum = 0.0;
int      g_lastEntryDir = 0;
bool     g_sameAsLast = false;
int      g_thisDir = 0;               // direction of the position now open
void   SaveStats();
void   LoadGuards();
double MinStopDist();
double RangePos();
void   CheckGuardsTick();
void   LoadStats();


//==================== HELPERS ======================================
void Log(string msg)
{
   if(InpVerboseLog) Print(msg);
}

// Current UTC day number, for the daily reset
int DayStamp()
{
   datetime t = TimeCurrent() - InpResetHourUTC * 3600;
   MqlDateTime d;
   TimeToStruct(t, d);
   return d.year * 1000 + d.day_of_year;
}

//---------------------------------------------------------------------------
// PERSISTENT GUARD STATE
// OnInit used to re-seed g_peakEq to the CURRENT equity and clear both locks.
// MT5 calls OnInit on every terminal restart, reconnect-with-recompile,
// timeframe change and parameter change - so the max-drawdown lock could be
// cleared, and the drawdown baseline moved down to the already-drawn-down
// equity, simply by restarting the terminal. A guard a restart removes is not
// a guard. These values now live in terminal global variables, which survive
// a restart, keyed by account login + magic so a different account or a
// different EA never inherits them.
//
// Disabled in the tester so nothing can leak between optimisation passes.
bool GuardsPersist()
{
   return !(bool)MQLInfoInteger(MQL_TESTER);
}

string GKey(string field)
{
   return "STS_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))
        + "_" + IntegerToString(InpMagic) + "_" + field;
}

double GGet(string field, double def)
{
   if(!GuardsPersist()) return def;
   string k = GKey(field);
   if(!GlobalVariableCheck(k)) return def;
   return GlobalVariableGet(k);
}

void GSet(string field, double v)
{
   if(!GuardsPersist()) return;
   GlobalVariableSet(GKey(field), v);
}

// BLOCKER 1, found by audit 2026-09-01. PersistGuards() WROTE these values
// and nothing ever read them back. OnInit re-seeded g_peakEq to current
// equity and left both locks false, so a parameter change, a recompile on
// reconnect or a timeframe switch cleared the max-drawdown lock and moved the
// drawdown baseline down to the already-drawn-down equity - exactly the fault
// the comment above claimed had been fixed. The comment was written; the
// reader never was.
//
// The daily figures are only restored if the stored day is TODAY. Restoring
// yesterday's daily loss would lock a fresh day for no reason.
void LoadGuards()
{
   if(!GuardsPersist()) return;

   double eq = AccountInfoDouble(ACCOUNT_EQUITY);

   double pk = GGet("peakEq", 0.0);
   if(pk > 0.0) g_peakEq = MathMax(pk, eq);

   g_lockedPerm = (GGet("lockPerm", 0.0) > 0.5);

   int storedDay = (int)GGet("dayStamp", -1.0);
   if(storedDay == DayStamp())
   {
      double ds = GGet("dayStartEq", 0.0);
      if(ds > 0.0) g_dayStartEq = ds;
      g_tradesToday = (int)GGet("tradesDay", 0.0);
      g_lockedDay   = (GGet("lockDay", 0.0) > 0.5);
   }

   if(g_lockedPerm)
      Print("RESTORED STATE: the permanent max-drawdown lock is SET. This EA "
            "will not open new positions. Clear it deliberately by deleting "
            "the terminal global variable " + GKey("lockPerm") + ".");
   if(g_lockedDay)
      PrintFormat("RESTORED STATE: locked for today, %d trades already taken, "
                  "day started at %.2f, peak equity %.2f",
                  g_tradesToday, g_dayStartEq, g_peakEq);
}

void PersistGuards()
{
   GSet("peakEq",     g_peakEq);
   GSet("dayStartEq", g_dayStartEq);
   GSet("dayStamp",   (double)g_dayStamp);
   GSet("tradesDay",  (double)g_tradesToday);
   GSet("lockDay",    g_lockedDay  ? 1.0 : 0.0);
   GSet("lockPerm",   g_lockedPerm ? 1.0 : 0.0);
}

double ATR(int shift)
{
   double buf[];
   if(CopyBuffer(g_atrHandle, 0, shift, 1, buf) != 1) return 0.0;
   return buf[0];
}

// Buffer 0 of iADX is the main ADX line.
double ADXValue(int shift)
{
   if(g_adxHandle == INVALID_HANDLE) return 0.0;
   double buf[];
   if(CopyBuffer(g_adxHandle, 0, shift, 1, buf) != 1) return 0.0;
   return buf[0];
}

// THE DEMA LENGTH ACTUALLY USED. E-092, and this was a live-account defect.
//
// Pine 3.7 computes  demaEff = perClock ? (M1 ? 60 : M3 ? 100 : demaLen) : demaLen
// and `perClock` defaults TRUE. This EA had InpDemaLen = 200 flat, with the
// comment "(60 on M1, 100 on M3)" -- an instruction to the human that the code
// never enforced. So on M1, the ONLY timeframe this EA is for, the chart gated
// with DEMA(60) and the EA gated with DEMA(200) unless Veer edited the input by
// hand, and neither file said so.
//
// MEASURED (E-092d): on the same flip set, DEMA(60) and DEMA(200) select the
// same trade only 74% of the time on GOLD 15m (121 of 164) and 74% on GOLD 1h
// (349 of 472). A quarter of every signal differed. Which length is BETTER is
// not settled and is not the point -- 15m preferred 200 (+384.5 pts vs +176.6)
// and 1h preferred 60 (+3188.2 vs +2911.8), which is exactly the inconsistency
// that means neither is chosen on evidence. The point is that the two files
// must gate identically, and the Pine's rule is the documented intent.
int DemaEffLen()
{
   if(!InpDemaPerClock) return InpDemaLen;
   if(_Period == PERIOD_M1) return 60;
   if(_Period == PERIOD_M3) return 100;
   return InpDemaLen;
}

// DEMA = 2*EMA(n) - EMA(EMA(n)), computed from closes. Matches the Pine.
//
// SEEDING (E-092, Q2). This used to seed e1 from a SINGLE close len*3+shift+5
// bars back. Pine's ta.ema seeds from the SMA of the first n values, and the
// difference does not wash out: at len=200 the decay over the 600-bar warm-up
// leaves about 1.8% of the seeding error in the number, and the gate reads a
// two-bar SLOPE, so a small level error flips the SIGN near a turn. Measured
// against a literal Pine transcription: the single-close seed disagreed on the
// slope sign for 70 of 3544 bars on GOLD 15m (1.975%) and 264 of 12715 on GOLD
// 1h (2.076%). Seeding from the SMA, as Pine does, takes that to 5 of 3544
// (0.141%) and 12 of 12715 (0.094%). It costs one extra loop over `len` bars.
double DEMA(int len, int shift)
{
   int need = len * 3 + shift + 5;
   if(Bars(_Symbol, _Period) < need + len) return 0.0;
   double k = 2.0 / (len + 1.0);
   // SMA seed over the `len` bars ending at the oldest bar of the warm-up.
   double sum = 0.0;
   for(int j = 0; j < len; j++) sum += iClose(_Symbol, _Period, need - 1 + j);
   double e1 = sum / len;
   double e2 = e1;
   for(int i = need - 2; i >= shift; i--)
   {
      double c = iClose(_Symbol, _Period, i);
      e1 = c * k + e1 * (1.0 - k);
      e2 = e1 * k + e2 * (1.0 - k);
   }
   return 2.0 * e1 - e2;
}

//==================== SUPERTREND ===================================
// Recomputed FROM HISTORY on every closed bar. The recursion is unchanged and
// still matches ta.supertrend(mult, len); what changed is where the previous
// bar's state comes from.
//
// WHY IT NO LONGER CARRIES STATE IN MEMORY
// The old version advanced g_finalUpper/g_finalLower/g_stDir once per new-bar
// event and kept them between calls. That equals the chart's SuperTrend only
// if this EA has observed EVERY bar of the series. It has not:
//   * the first call seeded direction from a SINGLE bar (c > basicUpper),
//     which is a guess, and the guess can survive for hundreds of bars and
//     manufacture one flip that the indicator never had;
//   * any bar that arrives with no tick, any disconnect, any weekend, any
//     terminal restart, timeframe change or parameter change drops bars out
//     of the recursion;
//   * because the state is recursive, a single dropped bar desynchronises the
//     EA from the chart PERMANENTLY, silently, with no error anywhere.
// That is precisely the "the EA does not do what the chart shows" class of
// defect. Recomputing over a fixed warm-up makes the value a pure function of
// price history, so live, tester and chart agree and a restart changes
// nothing. Cost is one CopyBuffer, one CopyRates and a few hundred
// multiplications, once per closed bar.
//==================== CONFIG SANITY (E-102) ========================
// THE DEFECT THIS EXISTS TO CATCH, and it is the worst one found in this file.
//
// The guards are percentages of equity. The stop is a multiple of ATR. Nothing
// ever compared the two, so on a small account they cross over and the EA
// destroys itself while every individual rule looks reasonable:
//
//   GBP 60, InpDailyLossPct = 3.0   ->  GBP 1.80  =  2.29 points at 0.01 lots
//   M1 gold, ATR ~2.2, 2.0 ATR stop ->  4.40 points = GBP 3.46
//
// The DAILY LOSS LIMIT IS SMALLER THAN ONE STOP. The trade cannot reach its own
// stop without breaching the day first, so the EA flattens at 52% of the way to
// a stop it placed itself - which is precisely the tight brake E-091 measured
// at -682 to -779 points, shipped by accident through the back door.
// InpMaxDDPct = 6.0 is GBP 3.60, so ONE stop is 96% of the entire lifetime
// budget: two losers and the account is permanently locked.
//
// The rule below is the arithmetic, not a preference: a daily allowance must
// hold at least TWO full stops or the EA is not running the strategy that was
// measured. At a 4.40-point stop that needs 3% of GBP 231.
//
// It REFUSES TO TRADE rather than warning, because Veer's requirement is
// "i dont wanna have to monitor it i want to be able to trust it". An EA that
// cannot work must say so on the chart, not discover it with his money.
void CheckConfigSanity()
{
   g_configFatal = false;
   g_configWhy   = "";

   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double a  = ATR(1);
   if(eq <= 0.0 || a <= 0.0) return;          // too early; re-checked each bar

   double stopPts   = InpStopAtrMult * a;
   double tickVal   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double minL      = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if(tickVal <= 0.0 || tickSize <= 0.0 || minL <= 0.0) return;

   double stopMoney = (stopPts / tickSize) * tickVal * minL;   // one stop, minimum lot
   double dayMoney  = eq * InpDailyLossPct / 100.0;
   double ddMoney   = eq * InpMaxDDPct     / 100.0;

   string msg = "";
   if(dayMoney < 2.0 * stopMoney)
      msg = StringFormat("DAILY LOSS LIMIT (%.1f%% = %.2f) IS LESS THAN TWO "
                         "STOPS (%.2f). One losing trade breaches the day, so "
                         "the EA would flatten at %.0f%% of its own stop - the "
                         "brake E-091 measured at -779 points. Needs %.2f "
                         "equity, or InpDailyLossPct >= %.2f.",
                         InpDailyLossPct, dayMoney, 2.0 * stopMoney,
                         100.0 * dayMoney / stopMoney,
                         2.0 * stopMoney * 100.0 / InpDailyLossPct,
                         200.0 * stopMoney / eq);
   else if(ddMoney < 4.0 * stopMoney)
      msg = StringFormat("MAX DRAWDOWN (%.1f%% = %.2f) IS LESS THAN FOUR STOPS "
                         "(%.2f). Four ordinary losses lock the account "
                         "permanently. Needs %.2f equity.",
                         InpMaxDDPct, ddMoney, 4.0 * stopMoney,
                         4.0 * stopMoney * 100.0 / InpMaxDDPct);

   if(msg != "")
   {
      g_configFatal = true;
      g_configWhy   = msg;
      static string lastMsg = "";
      if(msg != lastMsg)
      {
         lastMsg = msg;
         Print("=== EA HALTED, CONFIGURATION CANNOT WORK ===");
         Print(msg);
         PrintFormat("stop %.2f points = %.2f at %.2f lots | equity %.2f",
                     stopPts, stopMoney, minL, eq);
         Print("No entries will be taken until this is fixed. Nothing is being "
               "risked; this is not a failure to find signals.");
      }
   }
}

#define ST_WARMUP_BARS 400

void UpdateSuperTrend()
{
   g_stReady = false;

   int avail = Bars(_Symbol, _Period);
   int warm  = MathMin(ST_WARMUP_BARS, avail - 2);
   if(warm < InpStAtrLen + 3) return;

   double atrBuf[];
   if(CopyBuffer(g_atrHandle, 0, 1, warm, atrBuf) != warm) return;
   MqlRates r[];
   if(CopyRates(_Symbol, _Period, 1, warm + 1, r) != warm + 1) return;

   // Set AFTER the copy: that guarantees index 0 is the newest element no
   // matter which direction the copy filled the array in.
   ArraySetAsSeries(atrBuf, true);
   ArraySetAsSeries(r, true);

   double fUpper = 0.0, fLower = 0.0;
   int    dir = 0, dirPrev = 0;
   int    run = 0;    // bars this direction has lasted
   bool   seeded = false;

   // s indexes atrBuf, so bar shift = s + 1. s = 0 is the last CLOSED bar;
   // the forming bar (shift 0) is never read anywhere in this loop.
   for(int s = warm - 1; s >= 0; s--)
   {
      double atr = atrBuf[s];
      if(!MathIsValidNumber(atr) || atr <= 0.0) continue;

      double h   = r[s].high;
      double l   = r[s].low;
      double c   = r[s].close;
      double cp  = r[s + 1].close;
      double mid = (h + l) / 2.0;

      double basicUpper = mid + InpStMult * atr;
      double basicLower = mid - InpStMult * atr;

      if(!seeded)
      {
         fUpper  = basicUpper;
         fLower  = basicLower;
         dir     = (c > basicUpper) ? -1 : 1;
         dirPrev = dir;
         seeded  = true;
         continue;
      }

      double prevUpper = fUpper;
      double prevLower = fLower;

      fUpper = (basicUpper < prevUpper || cp > prevUpper) ? basicUpper : prevUpper;
      fLower = (basicLower > prevLower || cp < prevLower) ? basicLower : prevLower;

      dirPrev = dir;
      if(dir == 1 && c > fUpper)       dir = -1;   // flip bullish
      else if(dir == -1 && c < fLower) dir = 1;    // flip bearish

      if(dir != dirPrev) run = 0; else run++;

      // s == 0 is the last CLOSED bar, so g_flipHist[0] is the most recent.
      if(s < MAX_FLIPHIST) g_flipHist[s] = (dir != dirPrev) ? (uchar)1 : (uchar)0;
   }

   if(!seeded) return;

   g_finalUpper = fUpper;
   g_finalLower = fLower;
   g_stDir       = dir;
   g_stDirPrev   = dirPrev;
   g_barsInTrend = run;
   g_flipHistN   = MathMin(warm, MAX_FLIPHIST);
   g_stReady     = true;
}

//==================== LEVELS =======================================
// Veer: "i need the ea to auto UNDERSTAND all these levels what they mean and
// that we may get close to them and react not always hit them exactly".
//
// Price does not turn ON a level, it turns NEAR one. So every question here is
// asked with a tolerance rather than an equality: is there a level within
// InpNearAtr of this price, how far is the nearest one, is there room to the
// next one. A target parked just short of a level fills; one sitting exactly on
// it watches price stop a tick away and reverse.
#define MAX_LEVELS 200
double g_lvl[MAX_LEVELS];
int    g_lvlCount = 0;

void AddLevel(double p)
{
   if(p <= 0 || g_lvlCount >= MAX_LEVELS) return;
   double atr = ATR(1);
   double tol = (atr > 0 ? atr * 0.25 : _Point * 10);
   for(int i = 0; i < g_lvlCount; i++)          // merge near-equal levels
      if(MathAbs(g_lvl[i] - p) <= tol) return;
   g_lvl[g_lvlCount++] = p;
}

// A swing high is a bar whose high is the highest of the InpPivotBars either
// side of it. It is only KNOWN InpPivotBars later, and the scan respects that
// by starting at that offset - reading it sooner would be reading the future.
void BuildLevels()
{
   g_lvlCount = 0;
   if(!InpUseLevels) return;

   int n = MathMin(InpLevelLookback, Bars(_Symbol, _Period) - InpPivotBars - 2);
   for(int i = InpPivotBars + 1; i < n; i++)
   {
      bool isHigh = true, isLow = true;
      double h = iHigh(_Symbol, _Period, i);
      double l = iLow(_Symbol, _Period, i);
      for(int j = 1; j <= InpPivotBars; j++)
      {
         if(iHigh(_Symbol, _Period, i - j) > h || iHigh(_Symbol, _Period, i + j) > h) isHigh = false;
         if(iLow(_Symbol, _Period, i - j)  < l || iLow(_Symbol, _Period, i + j)  < l) isLow  = false;
         if(!isHigh && !isLow) break;
      }
      if(isHigh) AddLevel(h);
      if(isLow)  AddLevel(l);
   }

   if(InpUseDayLevels)
   {
      AddLevel(iHigh(_Symbol, PERIOD_D1, 1));
      AddLevel(iLow(_Symbol, PERIOD_D1, 1));
   }
   if(InpUseWeekLevels)
   {
      AddLevel(iHigh(_Symbol, PERIOD_W1, 1));
      AddLevel(iLow(_Symbol, PERIOD_W1, 1));
   }
   if(InpUseRound && InpRoundStep > 0)
   {
      double px = iClose(_Symbol, _Period, 1);
      for(int k = -3; k <= 3; k++)
         AddLevel(MathRound(px / InpRoundStep + k) * InpRoundStep);
   }
}

// Nearest level strictly above / below a price. 0 when there is none.
double NearestLevel(double from, int dir)
{
   double best = 0.0;
   for(int i = 0; i < g_lvlCount; i++)
   {
      double p = g_lvl[i];
      if(dir > 0 && p > from && (best == 0.0 || p < best)) best = p;
      if(dir < 0 && p < from && (best == 0.0 || p > best)) best = p;
   }
   return best;
}

// Is price sitting AT a level right now - within tolerance, not exactly on it?
bool NearAnyLevel(double px, double &which)
{
   double atr = ATR(1);
   if(atr <= 0) return false;
   double tol = InpNearAtr * atr;
   for(int i = 0; i < g_lvlCount; i++)
      if(MathAbs(g_lvl[i] - px) <= tol) { which = g_lvl[i]; return true; }
   return false;
}

//==================== RISK GATES ===================================
// Every prop firm measures the daily limit on EQUITY including floating P/L,
// so this uses AccountInfoDouble(ACCOUNT_EQUITY), never balance.
bool RiskAllowsEntry(string &why)
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);

   // E-102. The guards and the stop are measured in different units and on a
   // small account they cross over; CheckConfigSanity() does that arithmetic
   // once per bar. If it fails, nothing is tradeable and saying so is the only
   // honest behaviour.
   if(g_configFatal) { why = g_configWhy; return false; }

   // And refuse when the lot floor has turned the configured risk into
   // something else entirely. 3x is the line: below it the account is merely
   // small, above it the EA is not running the strategy that was measured.
   if(g_lotClampX > 3.0)
   {
      why = StringFormat("the broker's minimum lot makes every trade %.1fx the "
                         "configured %.2f%% risk. E-081: 0.01 lots cannot be "
                         "smaller, so the account must be larger.",
                         g_lotClampX, InpRiskPct);
      return false;
   }

   if(g_lockedPerm) { why = "max drawdown lock"; return false; }
   if(g_lockedDay)  { why = "daily loss lock";   return false; }

   if(g_dayStartEq > 0)
   {
      double dayLoss = (g_dayStartEq - eq) / g_dayStartEq * 100.0;
      if(dayLoss >= InpDailyLossPct)
      {
         g_lockedDay = true;
         PersistGuards();
         why = StringFormat("daily loss %.2f%% >= %.2f%%", dayLoss, InpDailyLossPct);
         Log("LOCK: " + why);
         return false;
      }
   }
   if(g_peakEq > 0)
   {
      double dd = (g_peakEq - eq) / g_peakEq * 100.0;
      if(dd >= InpMaxDDPct)
      {
         g_lockedPerm = true;
         PersistGuards();
         why = StringFormat("max drawdown %.2f%% >= %.2f%%", dd, InpMaxDDPct);
         Log("LOCK: " + why);
         return false;
      }
   }
   if(g_tradesToday >= InpMaxTradesDay) { why = "daily trade cap"; return false; }

   double atr = ATR(1);
   double spread = (SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                  - SymbolInfoDouble(_Symbol, SYMBOL_BID));
   if(atr > 0 && spread > InpMaxSpreadAtr * atr)
   {
      why = StringFormat("spread %.5f > %.1f%% of ATR", spread, InpMaxSpreadAtr * 100);
      return false;
   }
   return true;
}

// Size from the stop distance and the symbol's REAL tick value. Nothing here
// is hardcoded for gold, so the same EA sizes correctly on any symbol.
double LotFor(double stopDistPrice)
{
   if(stopDistPrice <= 0) return 0.0;

   // FIXED SIZE. Veer: "total lot size entering should be 0.03 unless stacking
   // or sizing". Still clamped to the symbol's own min/max/step below, so an
   // impossible size cannot be sent.
   if(InpUseFixedLots)
   {
      double stepF = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      double minF  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      double maxF  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
      double lf    = InpFixedLots;
      if(stepF > 0) lf = MathFloor(lf / stepF) * stepF;
      lf = MathMax(lf, minF);
      lf = MathMin(lf, maxF);
      return NormalizeDouble(lf, 2);
   }
   double eq       = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskCash = eq * InpRiskPct / 100.0;
   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0 || tickSize <= 0) return 0.0;

   double lossPerLot = (stopDistPrice / tickSize) * tickVal;
   if(lossPerLot <= 0) return 0.0;

   double lots = riskCash / lossPerLot;
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step > 0) lots = MathFloor(lots / step) * step;

   // THE LOT FLOOR IS A SILENT RISK MULTIPLIER, AND IT WAS SILENT. E-102.
   // `MathMax(minL, ...)` rounds the size UP to the broker minimum whenever the
   // account is too small for the configured risk, and said nothing. On GBP 60
   // at InpRiskPct = 0.50 with a 4.40-point M1 stop, the honest size is 0.00087
   // lots; the broker minimum is 0.01; so the trade carried 11.5x the risk that
   // was asked for, on every trade, for ever.
   //
   // E-081 is the reason it cannot be fixed by shrinking: 0.01 lots is
   // GBP 0.787 per point and there is nothing below it. So this reports the
   // real number instead of hiding it, and RiskAllowsEntry() refuses to trade
   // when the multiple is absurd.
   double want = lots;
   if(minL > 0.0 && want < minL)
   {
      g_lotClampX = (want > 0.0) ? (minL / want) : 0.0;
      if(!g_lotClampWarned)
      {
         g_lotClampWarned = true;
         PrintFormat("RISK WARNING: %.2f%% of %.2f is %.2f, which is %.5f lots, "
                     "but the broker minimum is %.2f. Every trade will risk "
                     "%.2f (%.1f%% of equity), which is %.1fx what you asked "
                     "for. E-081: 0.01 lots cannot be made smaller - the "
                     "ACCOUNT has to be bigger.",
                     InpRiskPct, eq, riskCash, want, minL,
                     minL * lossPerLot, 100.0 * minL * lossPerLot / eq,
                     g_lotClampX);
      }
   }
   else g_lotClampX = 1.0;

   lots = MathMax(minL, MathMin(maxL, lots));
   return NormalizeDouble(lots, 2);
}

//==================== PENDING ORDERS ===============================
// A resting limit is the only way to get a better price than the market is
// offering. The cost is real and is not hidden here: an order that never gets
// filled is a trade you did not take, and roughly a quarter of them will not
// fill at 0.30 ATR. Every expiry is logged so the miss rate is visible rather
// than assumed.
bool HasPending()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0) continue;
      if(OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol)  continue;
      return true;
   }
   return false;
}

// Cancel a limit that has sat unfilled too long. The setup that justified it
// is stale by then, and a limit left resting is an order waiting to be filled
// by exactly the move that invalidates it.
void ExpireStalePendings()
{
   int lifeSec = InpLimitLifeBars * PeriodSeconds(_Period);
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0) continue;
      if(OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol)  continue;
      datetime setup = (datetime)OrderGetInteger(ORDER_TIME_SETUP);
      if(TimeCurrent() - setup >= lifeSec)
      {
         double px = OrderGetDouble(ORDER_PRICE_OPEN);
         if(trade.OrderDelete(tk))
         {
            Log(StringFormat("limit at %.*f expired unfilled after %d bars",
                             (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS),
                             px, InpLimitLifeBars));
            Journal("LIMIT EXPIRED", "-", px, 0, 0, 0, 0, "never filled");
         }
      }
   }
}

//==================== POSITION HELPERS =============================
bool HasPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == InpMagic
         && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
   }
   return false;
}

//==================== ENTRY ========================================
void TryEntry()
{
   // A resting limit already IS this signal. Without this the next flip stacks
   // a second order on the same idea and both can fill within a few points of
   // each other - the same triple-entry fault that had to be fixed in the Pine.
   if(HasPending()) return;

   // The flip test comes FIRST so that every line logged below corresponds to
   // a real signal. Testing the risk gates first logged a refusal on every
   // single bar of a locked day, which buried the signals in noise.
   bool flipUp   = (g_stDir == -1 && g_stDirPrev == 1);
   bool flipDown = (g_stDir == 1  && g_stDirPrev == -1);
   if(!flipUp && !flipDown) return;

   string sdir = flipUp ? "long" : "short";


   string why = "";
   if(!RiskAllowsEntry(why)) { SkipLog(sdir, why); return; }

   if(InpUseDemaFilter)
   {
      int    dLen  = DemaEffLen();
      double dNow  = DEMA(dLen, 1);
      double dPrev = DEMA(dLen, 3);
      if(dNow <= 0 || dPrev <= 0) return;
      if(flipUp   && dNow < dPrev) { SkipLog(sdir, "DEMA falling"); return; }
      if(flipDown && dNow > dPrev) { SkipLog(sdir, "DEMA rising");  return; }
   }

   // --- ADX ceiling. The losing bucket on this strategy is entries taken when
   // the trend is ALREADY extended: ADX>35 measured -0.132R while ADX<20
   // measured +0.304R. Skipping the extended ones held out-of-sample.
   if(InpUseAdxFilter)
   {
      double adx = ADXValue(1);
      if(adx > 0 && adx > InpMaxAdx)
      {
         SkipLog(sdir, StringFormat("ADX %.1f > %.1f, trend already extended",
                                    adx, InpMaxAdx));
         return;
      }
   }

   // ---- DO NOT TRADE AGAINST A FRESH BIG CANDLE
   if(InpNoFadeAtr > 0.0)
   {
      double aNow = ATR(1);
      for(int k = 1; k <= InpNoFadeBars && aNow > 0.0; k++)
      {
         double rngK = iHigh(_Symbol, _Period, k) - iLow(_Symbol, _Period, k);
         if(rngK < InpNoFadeAtr * aNow) continue;
         int impDir = (iClose(_Symbol, _Period, k) > iOpen(_Symbol, _Period, k))
                      ? 1 : -1;
         if(impDir != (flipUp ? 1 : -1))
         {
            SkipLog(sdir, StringFormat("a %.1f x ATR candle went the OTHER way "
                                       "%d bar(s) ago - this is the pullback, "
                                       "not the trade", rngK / aNow, k));
            return;
         }
      }
   }

   // The signal is real from here: it has passed the DEMA slope and the ADX
   // ceiling, which is exactly how E-052 defined a signal. Record it against
   // the run BEFORE anything reads the risk score.
   RegisterSignal(flipUp ? 1 : -1);

   // STACKING IS TESTED *AFTER* THE SIGNAL IS RECORDED. (Audit finding 12.)
   // It used to sit before RegisterSignal, and at InpMaxStack=1 it rejected
   // every signal while a position was open - so the opposite-direction
   // signals that should RESET the run were never seen, RunBars() climbed
   // without bound, and a long that outlived a turn had its give-back
   // allowance LOOSENED from 13.5% back to 30% at exactly the moment it
   // should have tightened. The risk score was being applied backwards.
   // ---- NOT STRAIGHT BACK IN THE SAME DIRECTION
   int wantDir = flipUp ? 1 : -1;
   if(InpReentryCool > 0 && g_lastCloseDir == wantDir && g_lastCloseBar > 0)
   {
      int sinceClose = iBarShift(_Symbol, _Period, g_lastCloseBar, false);
      if(sinceClose < InpReentryCool)
      {
         SkipLog(sdir, StringFormat("closed a %s %d bars ago and this is the "
                                    "same way again - waiting %d",
                                    sdir, sinceClose, InpReentryCool));
         return;
      }
      // and, optionally, only once price has actually gone somewhere new.
      // Re-entering long below where the last long closed is buying the same
      // ground twice.
      if(InpReentryNeedsNewSignal && g_lastCloseExt > 0.0)
      {
         double px2 = (wantDir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                    : SymbolInfoDouble(_Symbol, SYMBOL_BID);
         bool newGround = (wantDir > 0) ? (px2 > g_lastCloseExt)
                                        : (px2 < g_lastCloseExt);
         if(!newGround)
         {
            SkipLog(sdir, "same direction and price has not passed where the "
                          "last one closed - this is the same trade again");
            return;
         }
      }
   }

   string sw = "";
   if(!StackAllows(flipUp ? 1 : -1, sw)) { SkipLog(sdir, sw); return; }

   // CHOP GUARD. Off by default - see the input group for why the measurement
   // does not support turning it on. Left switchable so the journal can
   // settle it on Veer's own fills instead of on my 15m data.
   if(InpUseChopGuard)
   {
      double er = EfficiencyRatio(InpChopErLen);
      if(er < InpMinEffRatio)
      {
         SkipLog(sdir, StringFormat("efficiency %.3f over %d bars is below "
                                    "%.3f - the market is going nowhere",
                                    er, InpChopErLen, InpMinEffRatio));
         return;
      }
      int fl = FlipsIn(InpChopFlipLen);
      if(fl >= InpChopMaxFlips)
      {
         SkipLog(sdir, StringFormat("%d flips in %d bars - one range being "
                                    "sliced, not %d setups",
                                    fl, InpChopFlipLen, fl));
         return;
      }
   }

   // --- session filter
   if(InpUseSession)
   {
      MqlDateTime dt_;
      TimeToStruct(TimeCurrent(), dt_);
      int h = dt_.hour;
      bool inSess = (InpSessFromUTC <= InpSessToUTC)
                  ? (h >= InpSessFromUTC && h < InpSessToUTC)
                  : (h >= InpSessFromUTC || h < InpSessToUTC);
      if(!inSess) { SkipLog(sdir, "outside session"); return; }
   }

   double atr = ATR(1);
   if(atr <= 0) return;
   int dg0 = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   double stopDist = InpStopAtrMult * atr;

   // THE COST FLOOR (E-063). A stop the spread has already half-consumed is
   // not a stop. This is checked BEFORE the broker minimum, because the two
   // are different constraints and the wider of them has to win.
   if(InpMinStopCostX > 0.0)
   {
      double needed = InpMinStopCostX * RoundTripCost();
      if(stopDist < needed)
      {
         Log(StringFormat("stop %.*f is only %.1f round trips wide - the spread "
                          "alone would be %.0f%% of it. Widening to %.*f.",
                          dg0, stopDist, stopDist / MathMax(RoundTripCost(), 1e-9),
                          100.0 * (SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                 - SymbolInfoDouble(_Symbol, SYMBOL_BID)) / stopDist,
                          dg0, needed));
         stopDist = needed;
      }
   }

   // The broker's floor. Widen to it and let LotFor re-derive the size, so
   // the risk in money is unchanged and only the distance moves.
   double minStop = MinStopDist();
   if(minStop > 0.0 && stopDist < minStop * 1.2)
   {
      Log(StringFormat("stop %.*f is inside the broker minimum %.*f, widening "
                       "to %.*f and resizing so the risk is unchanged",
                       dg0, stopDist, dg0, minStop, dg0, minStop * 1.2));
      stopDist = minStop * 1.2;
   }

   // COST GATE. The one thing here that needs no backtest: the EA reads the
   // spread that exists right now. If the whole round trip eats more than
   // InpMaxCostFrac of the stop, the trade is mostly a fee and is refused.
   if(InpUseCostGate)
   {
      double cost = RoundTripCost();
      double frac = (stopDist > 0.0) ? cost / stopDist : 1.0;
      if(frac > InpMaxCostFrac)
      {
         SkipLog(sdir, StringFormat("cost %.5f is %.1f%% of the %.5f stop, "
                                    "over the %.1f%% ceiling",
                                    cost, 100.0 * frac, stopDist,
                                    100.0 * InpMaxCostFrac));
         return;
      }
   }

   // NO ROOM, NO TRADE. A signal pointing straight into a level a few points
   // away is not the same trade as one with open air ahead of it, and taking
   // both at the same size is how the small ones pay for nothing.
   if(InpUseLevels && InpSkipNoRoom)
   {
      double px   = iClose(_Symbol, _Period, 1);
      double wall = NearestLevel(px, flipUp ? +1 : -1);
      if(wall > 0)
      {
         double roomR = MathAbs(wall - px) / stopDist;
         if(roomR < InpMinRoomR)
         {
            SkipLog(sdir, StringFormat("only %.2fR of room, level at %.*f",
                                       roomR, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS), wall));
            return;
         }
      }
   }

   double lots = LotFor(stopDist);
   if(lots <= 0) { SkipLog(sdir, "lot size rounded to zero"); return; }

   // TRENDS DO NOT LAST FOREVER. A signal in the same direction as a run that
   // is already old, already stretched and already crowded is not the same
   // trade as the first signal of that run, and it should not be the same
   // size. At the top of the scale the EA simply declines: the measured
   // late-trend bucket was -0.132R, and the correct size for a negative
   // expectation is zero.
   string trWhy = "";
   int trRisk = TrendRisk(trWhy);
   // TREND RISK SIZES DOWN. IT DOES NOT REFUSE.
   // It used to refuse at 3/3, which was wrong twice over: the measured effect
   // is about THREE PERCENTAGE POINTS (E-052), and a three-point penalty is a
   // discount, not a veto. E-053 then measured what refusing actually buys -
   // filters improved total R in 5 of 8 markets, i.e. a coin flip, and they
   // hurt precisely the markets that were winning. Sizing down keeps the trade
   // and prices the risk; refusing just trades less.
   if(trRisk >= 3)
   {
      double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      double cut  = lots * (trRisk >= 3 ? 0.34 : 0.5);
      if(step > 0) cut = MathFloor(cut / step) * step;
      if(cut >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
      {
         Log(StringFormat("trend risk %d/3 (%s): sizing down %.2f -> %.2f",
                          trRisk, trWhy, lots, cut));
         lots = cut;
      }
   }

   // ---- SIZE BY MARKET SHAPE (E-066). Applied last, so it scales whatever
   // the risk model and the trend-risk discount have already decided.
   if(InpUseRegimeSize)
   {
      double erNow = EfficiencyRatio(50);
      double mult  = (erNow < 0.10) ? InpRegimeChopX
                   : ((erNow < 0.25) ? InpRegimeMixX : InpRegimeTrendX);
      string shape = (erNow < 0.10) ? "chop"
                   : ((erNow < 0.25) ? "MIXED - the paying regime" : "running trend");
      double step2 = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      double sized = lots * mult;
      if(step2 > 0) sized = MathFloor(sized / step2) * step2;
      double vmin2 = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      double vmax2 = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
      sized = MathMax(vmin2, MathMin(sized, vmax2));
      if(MathAbs(sized - lots) > 1e-9)
         Log(StringFormat("efficiency %.3f = %s: sizing %.2f -> %.2f",
                          erNow, shape, lots, sized));
      lots = sized;
   }

   // ── THE MIDDLE OF THE RANGE (E-085) ──────────────────────────────────────
   // Applied AFTER every other sizing rule, because it is the one with the
   // out-of-sample evidence behind it and it must not be diluted by them.
   double rp = RangePos();
   if(rp >= InpMidRangeLo && rp <= InpMidRangeHi)
   {
      if(InpMidRangeSize <= 0.0)
      {
         SkipLog(sdir, StringFormat("range position %.2f is mid-range - the "
                                    "flip is inside noise, not at an extreme", rp));
         return;
      }
      double step3 = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      double cut   = lots * InpMidRangeSize;
      if(step3 > 0) cut = MathFloor(cut / step3) * step3;
      double vmin3 = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      cut = MathMax(vmin3, cut);
      if(cut < lots - 1e-9)
      {
         Log(StringFormat("range position %.2f is mid-range (%.2f-%.2f): "
                          "sizing %.2f -> %.2f. A flip here is the market "
                          "changing its mind inside noise.",
                          rp, InpMidRangeLo, InpMidRangeHi, lots, cut));
         lots = cut;
      }
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   int    dg  = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   // The stop is attached AT OrderSend, never "managed later". A stop that
   // only exists in EA memory does not exist at all if the terminal drops.
   if(flipUp)
   {
      double sl = NormalizeDouble(ask - stopDist, dg);
      // InpTargetR = 0 means NO ceiling: the trail decides where it ends.
      double tp = (InpTargetR <= 0.0) ? 0.0 : NormalizeDouble(ask + InpTargetR * stopDist, dg);
      // A target sitting beyond the next level watches price stop just short of
      // it and turn. Park it INSIDE the level instead, by InpLevelBufAtr, so it
      // is reached rather than admired.
      if(InpUseLevels && InpTpAtLevel)
      {
         double capLvl = NearestLevel(ask, +1);
         if(capLvl > 0)
         {
            double capped = NormalizeDouble(capLvl - InpLevelBufAtr * atr, dg);
            if(tp > 0.0 && capped > ask && capped < tp)
            {
               Log(StringFormat("target pulled in from %.*f to %.*f, level at %.*f",
                                dg, tp, dg, capped, dg, capLvl));
               tp = capped;
            }
         }
      }
      // A LIMIT rests below and is filled by the pullback; the stop and target
      // are re-anchored to that better price, so the whole trade shifts down
      // rather than just the entry. That is what makes it a smaller drawdown
      // and not merely a nicer-looking fill.
      if(InpUseLimitEntry)
      {
         double lim = NormalizeDouble(ask - InpPullAtr * atr, dg);
         double lsl = NormalizeDouble(lim - stopDist, dg);
         double ltp = (tp <= 0.0) ? 0.0 : NormalizeDouble(lim + (tp - ask), dg);
         if(trade.BuyLimit(lots, lim, _Symbol, lsl, ltp, ORDER_TIME_GTC, 0,
                           RiskTag(stopDist, dg)))
         {
            PB_NoteOrder(trade.ResultOrder(), ask);
            g_tradesToday++; RegisterEntry(flipUp ? 1 : -1);
            Journal("LIMIT", "long", lim, lots, lsl, ltp, 0, "waiting for pullback");
            Log(StringFormat("BUY LIMIT %.2f at %.*f  sl %.*f  tp %.*f",
                             lots, dg, lim, dg, lsl, dg, ltp));
         }
         else Log("BuyLimit failed: " + IntegerToString(trade.ResultRetcode()));
         return;
      }

      double spAtEntry = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                       - SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(trade.Buy(lots, _Symbol, 0.0, sl, tp, RiskTag(stopDist, dg)))
      {
         g_spEntrySum += spAtEntry; g_spEntryN++;
         if(spAtEntry > g_spEntryMax) g_spEntryMax = spAtEntry;
         g_tradesToday++; RegisterEntry(flipUp ? 1 : -1);
         Journal("ENTRY", "long", ask, lots, sl, tp, 0,
                 StringFormat("spread %.*f stop %.*f cost/stop %.3f",
                              dg, spAtEntry, dg, stopDist,
                              stopDist > 0 ? RoundTripCost() / stopDist : 0.0));
         Log(StringFormat("LONG %.2f lots  sl %.*f  tp %.*f  atr %.*f",
                          lots, dg, sl, dg, tp, dg, atr));
      }
      else Log("Buy failed: " + IntegerToString(trade.ResultRetcode()));
   }
   else
   {
      double sl = NormalizeDouble(bid + stopDist, dg);
      // InpTargetR = 0 means NO ceiling: the trail decides where it ends.
      double tp = (InpTargetR <= 0.0) ? 0.0 : NormalizeDouble(bid - InpTargetR * stopDist, dg);
      if(InpUseLevels && InpTpAtLevel)
      {
         double capLvl = NearestLevel(bid, -1);
         if(capLvl > 0)
         {
            double capped = NormalizeDouble(capLvl + InpLevelBufAtr * atr, dg);
            if(tp > 0.0 && capped < bid && capped > tp)
            {
               Log(StringFormat("target pulled in from %.*f to %.*f, level at %.*f",
                                dg, tp, dg, capped, dg, capLvl));
               tp = capped;
            }
         }
      }
      if(InpUseLimitEntry)
      {
         double lim = NormalizeDouble(bid + InpPullAtr * atr, dg);
         double lsl = NormalizeDouble(lim + stopDist, dg);
         double ltp = (tp <= 0.0) ? 0.0 : NormalizeDouble(lim - (bid - tp), dg);
         if(trade.SellLimit(lots, lim, _Symbol, lsl, ltp, ORDER_TIME_GTC, 0,
                            RiskTag(stopDist, dg)))
         {
            PB_NoteOrder(trade.ResultOrder(), bid);
            g_tradesToday++; RegisterEntry(flipUp ? 1 : -1);
            Journal("LIMIT", "short", lim, lots, lsl, ltp, 0, "waiting for pullback");
            Log(StringFormat("SELL LIMIT %.2f at %.*f  sl %.*f  tp %.*f",
                             lots, dg, lim, dg, lsl, dg, ltp));
         }
         else Log("SellLimit failed: " + IntegerToString(trade.ResultRetcode()));
         return;
      }

      double spAtEntry = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                       - SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(trade.Sell(lots, _Symbol, 0.0, sl, tp, RiskTag(stopDist, dg)))
      {
         g_spEntrySum += spAtEntry; g_spEntryN++;
         if(spAtEntry > g_spEntryMax) g_spEntryMax = spAtEntry;
         g_tradesToday++; RegisterEntry(flipUp ? 1 : -1);
         Journal("ENTRY", "short", bid, lots, sl, tp, 0,
                 StringFormat("spread %.*f stop %.*f cost/stop %.3f",
                              dg, spAtEntry, dg, stopDist,
                              stopDist > 0 ? RoundTripCost() / stopDist : 0.0));
         Log(StringFormat("SHORT %.2f lots  sl %.*f  tp %.*f  atr %.*f",
                          lots, dg, sl, dg, tp, dg, atr));
      }
      else Log("Sell failed: " + IntegerToString(trade.ResultRetcode()));
   }
}

//==================== JOURNAL ======================================
// This EA runs on a LIVE account, and the honest reason nobody can say WHY it
// underperforms is that nobody has the data. The Experts tab is not data - it
// scrolls away and cannot be analysed.
//
// So every signal, every refusal and every fill is written to
//   MQL5/Files/STS_journal_<symbol>_<timeframe>.csv
// with the market conditions at that moment attached. Send that file back and
// the next fix is derived from your actual trades instead of from theory.
//
// The SKIP rows are the valuable ones: they are the signals the filters
// refused. If those keep winning, a filter is costing you money, and that is
// only knowable from this file.
string JournalName()
{
   return StringFormat("STS_journal_%s_%s.csv", _Symbol,
                       EnumToString((ENUM_TIMEFRAMES)_Period));
}

void Journal(string ev, string dir, double px, double lots,
             double sl, double tp, double money, string note)
{
   if(!InpJournal) return;

   int h = FileOpen(JournalName(),
                    FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ, ',');
   if(h == INVALID_HANDLE) return;

   if(FileSize(h) == 0)
      FileWrite(h, "utc_time", "event", "dir", "price", "lots", "sl", "tp",
                   "money", "atr", "adx", "spread", "equity", "note");
   FileSeek(h, 0, SEEK_END);

   double atr = ATR(1);
   double adx = ADXValue(1);
   double sp  = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
              - SymbolInfoDouble(_Symbol, SYMBOL_BID);

   FileWrite(h, TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
             ev, dir, DoubleToString(px, _Digits), DoubleToString(lots, 2),
             DoubleToString(sl, _Digits), DoubleToString(tp, _Digits),
             DoubleToString(money, 2), DoubleToString(atr, _Digits),
             DoubleToString(adx, 1), DoubleToString(sp, _Digits),
             DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2), note);
   FileClose(h);
}

// A signal the filters refused, recorded with the reason.
void SkipLog(string dir, string why)
{
   Log("skip " + dir + ": " + why);
   Journal("SKIP", dir, iClose(_Symbol, _Period, 1), 0, 0, 0, 0, why);
}

//==================== R MEASUREMENT ================================
// R must be measured against the risk the trade was OPENED with, never against
// the current stop. The moment a trail moves the stop, |open - sl| shrinks, so
// R computed from it inflates - and every R-based rule below (partial,
// break-even, trail arm) fires on a number that is not true. Worse, when a
// trail crosses the entry price |open - sl| passes through zero, the guard
// `if(risk <= 0) continue;` fires, and the position stops being managed at all.
//
// So the original stop distance rides on the position itself, in its comment,
// and therefore survives a terminal restart. If a broker mangles the comment
// the fallback is the old behaviour, which is wrong but not fatal.
string RiskTag(double stopDist, int dg)
{
   return "STS|" + DoubleToString(stopDist, dg);
}

// The risk this trade was SIZED on, in price. It is stamped into the position
// comment at entry because the stop moves afterwards - once the trail has run,
// the distance from entry to the current stop is not the risk any more.
//
// (Audit finding 10.) Many brokers replace or strip position comments. The
// fallback then reads the CURRENT stop, and that fails in three different
// ways, all of them previously silent:
//   - trail already moved  -> risk read too small, the give-back rule arms
//                             far too early
//   - trail crossed entry  -> risk read near zero, one tick of noise fires it
//   - no stop at all       -> risk zero, the position is unmanaged entirely
// So the fallback is now the ATR-derived stop distance, which is what the
// trade was actually sized on, and it says so out loud the first time.
double OriginalRisk(double openPx, double sl, string cmt)
{
   if(StringLen(cmt) > 4 && StringSubstr(cmt, 0, 4) == "STS|")
   {
      double d = StringToDouble(StringSubstr(cmt, 4));
      if(d > 0) return d;
   }

   static bool told = false;
   if(!told)
   {
      told = true;
      Print("NOTE: a position comment did not carry its original risk tag - "
            "this broker probably rewrites comments. Falling back to the "
            "ATR stop distance. Every R figure in the log and the box is an "
            "approximation from here on.");
   }

   double a = ATR(1);
   if(a > 0.0) return InpStopAtrMult * a;

   double d2 = MathAbs(openPx - sl);
   return (d2 > 0.0) ? d2 : 0.0;
}

// A partial close must happen ONCE. Without this the old code re-closed half
// the remaining volume on every single bar the trade spent above 1R, bleeding
// a winner down to the minimum lot while it was still working.
ulong g_partialed[];
// A SECOND, separate register. The 1R partial and the level partial are
// different events and can both happen on one trade; sharing one list would
// let whichever fired first silently cancel the other.
ulong g_lvlPartialed[];

bool AlreadyLvlPartialed(ulong tk)
{
   for(int i = 0; i < ArraySize(g_lvlPartialed); i++)
      if(g_lvlPartialed[i] == tk) return true;
   return false;
}

void MarkLvlPartialed(ulong tk)
{
   int n = ArraySize(g_lvlPartialed);
   ArrayResize(g_lvlPartialed, n + 1);
   g_lvlPartialed[n] = tk;
   if(n > 400) ArrayRemove(g_lvlPartialed, 0, 200);
}

bool AlreadyPartialed(ulong tk)
{
   for(int i = 0; i < ArraySize(g_partialed); i++)
      if(g_partialed[i] == tk) return true;
   return false;
}

void MarkPartialed(ulong tk)
{
   int n = ArraySize(g_partialed);
   ArrayResize(g_partialed, n + 1);
   g_partialed[n] = tk;
   if(n > 400) ArrayRemove(g_partialed, 0, 200);   // never grow without bound
}

//==================== MANAGEMENT ===================================
// Two rules are ON by default because they MEASURED better on these entries:
// a wide 3-ATR trail armed immediately, and a 50-bar stall exit. Break-even
// and the 1R partial are OFF: break-even was the worst exit rule on all four
// markets tested, and the partial has never been measured on this strategy.
void ManagePosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)  continue;

      long   type  = PositionGetInteger(POSITION_TYPE);
      double open  = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl    = PositionGetDouble(POSITION_SL);
      double tp    = PositionGetDouble(POSITION_TP);
      double vol   = PositionGetDouble(POSITION_VOLUME);
      datetime ot  = (datetime)PositionGetInteger(POSITION_TIME);
      string  cmt  = PositionGetString(POSITION_COMMENT);
      int    dg    = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
      double atr   = ATR(1);
      if(atr <= 0) continue;

      double price = (type == POSITION_TYPE_BUY)
                   ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                   : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      int dir      = (type == POSITION_TYPE_BUY) ? 1 : -1;
      double risk  = OriginalRisk(open, sl, cmt);
      if(risk <= 0) continue;
      double rNow  = (price - open) * dir / risk;

      // --- REVERSAL EXIT. Structure has broken against the trade.
      // This is the "close later than we can" complaint: the EA used to wait
      // for the SuperTrend to flip, which on M1 is late and noisy. A close
      // beyond the last swing point is earlier and is not a single candle.
      if(InpUseReversalExit)
      {
         int rev = ReversalAgainst(dir);
         if(rev != 0 && rev != dir)
         {
            if(trade.PositionClose(tk))
               Log(StringFormat("REVERSAL exit at %.2fR: price closed through "
                                "the last swing against this %s. Structure has "
                                "broken - not waiting for the SuperTrend.",
                                rNow, dir > 0 ? "long" : "short"));
            continue;
         }
      }

      // --- STALL EXIT, and it comes before the blind bar cap because it is
      // the better of the two. A trade still printing new highs at bar 49 is
      // not the trade InpMaxBars was written for; one that peaked thirty bars
      // ago and is drifting is, and InpMaxBars cannot tell them apart. E-056
      // measured the difference at 30 to 38 percentage points of give-back
      // probability, unanimous across 8 of 8 markets.
      int tix = TrackFind(tk);
      int stallNow = StallBars(tix);
      if(InpMaxStall > 0 && tix >= 0 && stallNow >= InpMaxStall)
      {
         if(trade.PositionClose(tk))
            Log(StringFormat("STALL exit: no new high for %d bars, sitting at "
                             "%.2fR. Measured give-back rate at this stall is "
                             "roughly 60%%.", stallNow, rNow));
         continue;
      }

      // --- absolute bar cap. A backstop now, not the main rule.
      int barsHeld = iBarShift(_Symbol, _Period, ot, false);
      if(InpMaxBars > 0 && barsHeld >= InpMaxBars)
      {
         if(trade.PositionClose(tk))
            Log(StringFormat("time exit after %d bars at %.2fR", barsHeld, rNow));
         continue;
      }

      // --- APPROACHING A LEVEL: bank half, let the rest run.
      // This is the answer to wanting both the pennies and the big moves out of
      // the same signal. Price arriving at a level does one of two things and
      // nobody knows which in advance, so the trade does both: half is taken
      // while the level is still in front of price, and the remainder rides the
      // trail through it if it breaks. Note NearAnyLevel uses a TOLERANCE -
      // price reacts near a level, not on it, and a partial that waits for an
      // exact touch is a partial that often never happens.
      if(InpUseLevels && InpPartialAtLevel && rNow > 0.3
         && !AlreadyLvlPartialed(tk)
         && vol > SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
      {
         double hitLvl = 0.0;
         if(NearAnyLevel(price, hitLvl))
         {
            // only a level the trade is running INTO, not one behind it
            bool ahead = (dir > 0) ? (hitLvl >= open) : (hitLvl <= open);
            if(ahead)
            {
               double half = NormalizeDouble(vol / 2.0, 2);
               double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
               if(step > 0) half = MathFloor(half / step) * step;
               if(half >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN)
                  && trade.PositionClosePartial(tk, half))
               {
                  MarkLvlPartialed(tk);
                  Log(StringFormat("banked %.2f of %.2f at level %.*f (%.2fR), "
                                   "rest rides the trail", half, vol,
                                   (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS),
                                   hitLvl, rNow));
                  Journal("PARTIAL", dir > 0 ? "long" : "short", price, half,
                          0, 0, 0, StringFormat("at level %.2f", hitLvl));
               }
            }
         }
      }

      // --- partial at 1R, optional
      if(InpPartialAt1R && rNow >= 1.0 && !AlreadyPartialed(tk)
         && vol > SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
      {
         double half = NormalizeDouble(vol / 2.0, 2);
         double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         if(step > 0) half = MathFloor(half / step) * step;
         if(half >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
         {
            if(trade.PositionClosePartial(tk, half))
            {
               MarkPartialed(tk);
               Log(StringFormat("partial close %.2f of %.2f at 1R", half, vol));
            }
         }
      }

      // --- break-even. OFF by default. Measured as the WORST exit rule on all
      // four markets tested (-0.161R to -0.308R). Present only so it can be
      // tested rather than argued about.
      if(InpUseBreakEven && rNow >= InpBreakEvenAtR)
      {
         double be = NormalizeDouble(open, dg);
         bool better = (dir > 0) ? (be > sl) : (be < sl);
         if(better) { trade.PositionModify(tk, be, tp); Log("moved to break-even"); }
      }

      // --- trail. ON by default and arms IMMEDIATELY (InpTrailAtR = 0), because
      // a wide trail measured best on these entries and a tight or late one did
      // not. It only ever moves the stop in the trade's favour.
      if(InpUseTrail && rNow >= InpTrailAtR)
      {
         double t = (dir > 0) ? price - InpTrailAtrMult * atr
                              : price + InpTrailAtrMult * atr;
         t = NormalizeDouble(t, dg);
         bool better = (dir > 0) ? (t > sl) : (t < sl);
         // A modify inside the broker's stop level is rejected, silently and
         // repeatedly. Leave the stop where it is rather than spam the server.
         double mn = MinStopDist();
         bool room = (mn <= 0.0) || (MathAbs(price - t) >= mn);
         if(better && room) { trade.PositionModify(tk, t, tp); }
      }
   }
}

//==================== CLOSE RECORDING ==============================
// Every fill is recorded here rather than where it was requested, because a
// stop or a target is hit by the BROKER, not by this EA - those closes never
// pass through any code above. DEAL_REASON is the broker's own statement of
// why the position ended, so the journal records what actually happened
// instead of what the EA intended.
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest    &request,
                        const MqlTradeResult     &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;

   ulong d = trans.deal;
   if(d == 0 || !HistoryDealSelect(d)) return;
   if(HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic)     return;
   if(HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol)      return;

   // the profit box needs BOTH halves of a trade, and the guard below throws
   // away everything that is not a close, so this comes first.
   long pbEntry = HistoryDealGetInteger(d, DEAL_ENTRY);
   if(pbEntry == DEAL_ENTRY_IN)
   {
      PB_PromoteOrder((ulong)HistoryDealGetInteger(d, DEAL_ORDER),
                      (ulong)HistoryDealGetInteger(d, DEAL_POSITION_ID),
                      HistoryDealGetDouble(d, DEAL_PRICE));
      return;
   }
   g_pbDirty = true;
   if(pbEntry != DEAL_ENTRY_OUT) return;

   double px    = HistoryDealGetDouble(d, DEAL_PRICE);
   double vol   = HistoryDealGetDouble(d, DEAL_VOLUME);
   double money = HistoryDealGetDouble(d, DEAL_PROFIT)
                + HistoryDealGetDouble(d, DEAL_SWAP)
                + HistoryDealGetDouble(d, DEAL_COMMISSION);
   long   rsn   = HistoryDealGetInteger(d, DEAL_REASON);
   long   type  = HistoryDealGetInteger(d, DEAL_TYPE);

   // the closing deal is the OPPOSITE side of the position it closed
   string dir = (type == DEAL_TYPE_SELL) ? "long" : "short";

   string why = "other";
   if(rsn == DEAL_REASON_SL)     why = "SL";
   else if(rsn == DEAL_REASON_TP) why = "TP";
   else if(rsn == DEAL_REASON_EXPERT) why = "EA (time cap or partial)";
   else if(rsn == DEAL_REASON_SO) why = "STOP OUT - margin";

   Journal("EXIT", dir, px, vol, 0, 0, money, why);
   Log(StringFormat("closed %s %.2f at %s for %.2f (%s)",
                    dir, vol, DoubleToString(px, _Digits), money, why));

   // ---- EXECUTION STATISTICS
   // Only a FULL close counts as a finished trade. A partial produces an
   // out-deal too, and counting those would inflate the trade count and make
   // every ratio in the box wrong.
   // Every out-deal, partial or full, is money this basket has realised.
   g_bkRealized += money;

   // SAME-DIRECTION vs ALTERNATING, counted live. See g_sdN above for why.
   if(!PositionSelectByTicket((ulong)HistoryDealGetInteger(d, DEAL_POSITION_ID)))
   {
      if(g_sameAsLast) { g_sdN++;  g_sdSum  += money; if(money > 0) g_sdWin++; }
      else             { g_altN++; g_altSum += money; if(money > 0) g_altWin++; }
   }

   ulong pid = (ulong)HistoryDealGetInteger(d, DEAL_POSITION_ID);
   if(PositionSelectByTicket(pid))
   {
      // A PARTIAL. The position lives on, so it is not a finished trade - but
      // the money is real and KEPT OF PEAK is the headline number in the box.
      // Counting the peak later while never counting this cash biased that
      // figure LOW every time a level partial fired, and the level partial is
      // on by default. (Audit finding 11.)
      g_stRealized    += money;
      g_stDayRealized += money;
      SaveStats();
      return;
   }

   int ti = TrackFind(pid);
   double peakMoney = (ti >= 0) ? g_tkPeakMoney[ti] : MathMax(money, 0.0);
   double peakR     = (ti >= 0 && g_tkRisk[ti] > 0.0)
                    ? g_tkPeakPx[ti] / g_tkRisk[ti] : 0.0;

   g_stTrades++;
   g_stDayTrades++;
   g_stRealized    += money;
   g_stDayRealized += money;
   g_stPeakSum     += MathMax(peakMoney, 0.0);
   g_stGivenBack   += MathMax(0.0, peakMoney - money);
   if(money > 0) g_stWins++;

   // The row that names Veer's complaint: it went into profit and did not
   // close profitably. 0.5R is the threshold for "was genuinely green" -
   // below that a trade never really got going and calling it a give-back
   // would be counting spread noise.
   // remember which way the trade that just finished was pointing
   g_lastCloseDir = (dir == "long") ? 1 : -1;
   g_lastCloseBar = iTime(_Symbol, _Period, 0);
   g_lastCloseExt = px;

   if(peakR >= 0.5 && money <= 0.0)
   {
      g_stGreenRed++;
      Log(StringFormat("GREEN->RED: peaked %.2fR (%s) and closed %s. "
                       "That is now %d of %d closed trades.",
                       peakR, Money(peakMoney), Money(money),
                       g_stGreenRed, g_stTrades));
   }
   if(ti >= 0) TrackDrop(ti);
   SaveStats();
}

//===================================================================
//  MODULE: MONEY
//===================================================================
// Everything below is quoted to Veer in pounds, because that is the unit he
// actually experiences. R is the unit the research is in. This converts.
double MoneyPerPricePerLot()
{
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0.0) return 0.0;
   return tv / ts;
}

string Money(double v)
{
   return StringFormat("%s%.2f", (v < 0 ? "-" : ""),
                       MathAbs(NormalizeDouble(v, 2)));
}

//===================================================================
//  MODULE: PER-POSITION PEAK REGISTRY
//===================================================================
// The single most important thing this EA did not know before: how good each
// trade ALREADY WAS. Without that number, "it gave the profit back" is an
// opinion. With it, it is a column.
int TrackFind(ulong tk)
{
   for(int i = 0; i < g_tkCount; i++)
      if(g_tkId[i] == tk) return i;
   return -1;
}

int TrackAdd(ulong tk, double risk)
{
   if(g_tkCount >= MAX_TRACK) return -1;
   int i = g_tkCount;
   g_tkId[i]        = tk;
   g_tkPeakPx[i]    = 0.0;
   g_tkPeakPrev[i]  = 0.0;
   g_tkCloseTry[i]  = 0;
   g_tkGbDone[i]    = false;
   g_tkPeakImp[i]   = false;
   g_tkWorstPx[i]   = 0.0;
   g_tkRisk[i]      = risk;
   g_tkPeakMoney[i] = 0.0;
   g_tkPeakTime[i]  = TimeCurrent();
   g_tkPeakBar[i]   = iTime(_Symbol, _Period, 0);
   g_tkCount++;
   return i;
}

void TrackDrop(int i)
{
   if(i < 0 || i >= g_tkCount) return;
   for(int j = i; j < g_tkCount - 1; j++)
   {
      g_tkId[j]        = g_tkId[j + 1];
      g_tkPeakPx[j]    = g_tkPeakPx[j + 1];
      g_tkPeakPrev[j]  = g_tkPeakPrev[j + 1];
      g_tkCloseTry[j]  = g_tkCloseTry[j + 1];
      g_tkGbDone[j]    = g_tkGbDone[j + 1];
      g_tkPeakImp[j]   = g_tkPeakImp[j + 1];
      g_tkWorstPx[j]   = g_tkWorstPx[j + 1];
      g_tkRisk[j]      = g_tkRisk[j + 1];
      g_tkPeakMoney[j] = g_tkPeakMoney[j + 1];
      g_tkPeakTime[j]  = g_tkPeakTime[j + 1];
      g_tkPeakBar[j]   = g_tkPeakBar[j + 1];
   }
   g_tkCount--;
}

//===================================================================
//  MODULE: BASKET SNAPSHOT
//===================================================================
// One pass over the open positions producing every number the rest of the EA
// and the box need. Called on EVERY TICK, so it does no trading and no
// logging - it only looks.

void Snapshot(Basket &b)
{
   b.n = 0; b.nLong = 0; b.nShort = 0;
   b.lots = 0.0; b.netLots = 0.0; b.money = 0.0; b.wAvgEntry = 0.0;
   b.bestR = 0.0; b.peakR = 0.0; b.oldestBars = 0; b.dir = 0; b.stall = 0;
   b.peakMoney = 0.0; b.givenBack = 0.0; b.sincePeakSec = 0;

   double num = 0.0;
   datetime oldest = 0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)  continue;

      long   type = PositionGetInteger(POSITION_TYPE);
      int    dir  = (type == POSITION_TYPE_BUY) ? 1 : -1;
      double vol  = PositionGetDouble(POSITION_VOLUME);
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double prof = PositionGetDouble(POSITION_PROFIT)
                  + PositionGetDouble(POSITION_SWAP);
      datetime ot = (datetime)PositionGetInteger(POSITION_TIME);

      b.n++;
      if(dir > 0) b.nLong++; else b.nShort++;
      b.lots    += vol;
      b.netLots += dir * vol;
      b.money   += prof;
      num       += open * vol;
      if(oldest == 0 || ot < oldest) oldest = ot;

      int ti = TrackFind(tk);
      if(ti >= 0 && g_tkRisk[ti] > 0.0)
      {
         double px = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                               : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double rNow = (px - open) * dir / g_tkRisk[ti];
         double rPk  = g_tkPeakPx[ti] / g_tkRisk[ti];
         if(rNow > b.bestR) b.bestR = rNow;
         if(rPk  > b.peakR) b.peakR = rPk;
         // the basket's stall is the SMALLEST of its positions': if anything
         // is still making new highs, the basket has not stopped working
         int st = StallBars(ti);
         if(b.stall == 0 || st < b.stall) b.stall = st;
      }
   }

   if(b.lots > 0.0) b.wAvgEntry = num / b.lots;
   if(b.netLots > 0.0) b.dir = 1; else if(b.netLots < 0.0) b.dir = -1;
   if(oldest > 0) b.oldestBars = iBarShift(_Symbol, _Period, oldest, false);
   // realised-so-far is part of what this basket has made. Without it, taking
   // profit looks identical to losing it.
   b.money    += g_bkRealized;
   b.peakMoney = g_bkPeak;
   b.givenBack = MathMax(0.0, g_bkPeak - b.money);
   if(g_bkPeakTime > 0) b.sincePeakSec = (int)(TimeCurrent() - g_bkPeakTime);
}

//===================================================================
//  MODULE: TREND PERSISTENCE RISK
//===================================================================
// "Sometimes the EA will continue in one direction - have it understand that
//  it can be risky, trends don't always last forever."
//
// Three independent readings, each worth one point:
//   RUN AGE  - bars since the last signal in the OPPOSITE direction
//   RUN FAR  - how far price has travelled since that signal, in ATRs
//   ADX      - trend strength at entry (the weakest of the three)
//
// CORRECTED 2026-09-01. This header used to name AGE / STRETCH / CROWDING.
// Stretch and crowding were DISPROVED in E-052 and deleted from the code
// weeks-of-work ago; the header describing them survived. Run age and run
// distance are two measurements of one thing - the far end of a one-way run -
// which is why they agree, and why they are trusted more than three
// independent-looking readings would be.
//
// The score is not a prediction that the trend will end. It is a statement
// that the PAYOFF for staying has got worse: late-trend entries measured
// -0.132R against +0.304R for early ones (the ADX result). So a high score
// buys less and protects sooner. It never reverses anything on its own.
// Bars since the first signal of the current run, and how far price has
// travelled since it. These are the two readings that replicated.
int RunBars()
{
   if(g_runStartBar == 0) return 0;
   int b = iBarShift(_Symbol, _Period, g_runStartBar, false);
   return (b < 0) ? 0 : b;
}

double RunMoveAtr()
{
   double a = ATR(1);
   if(a <= 0.0 || g_runStartPx <= 0.0) return 0.0;
   return MathAbs(iClose(_Symbol, _Period, 1) - g_runStartPx) / a;
}

// Called the moment a signal clears the filters, BEFORE the risk score is
// read - so the score describes the run this signal belongs to, exactly as
// the study computed it.
void RegisterSignal(int dir)
{
   if(dir != g_lastSigDir)
   {
      g_runStartBar = iTime(_Symbol, _Period, 1);
      g_runStartPx  = iClose(_Symbol, _Period, 1);
      g_lastSigDir  = dir;
   }
}

//===================================================================
//  MODULE: COST AND CHOP
//===================================================================
// The true round trip, in PRICE, not in spread alone. Commission arrives per
// lot in account currency and has to be converted before it can be compared
// with a stop distance; leaving it out was what made the old spread-only gate
// understate the real cost by about 55% on gold.
// BLOCKER 3. Nothing in this EA asked the broker what its minimum stop
// distance was. On M1 (D-010) a 1.5 x ATR(7) stop on gold can fall below it,
// and the symptom is a silent stream of 10016 rejections with no journal row
// to explain them - the EA simply looks like it stopped trading.
//
// The response is to WIDEN the stop to the broker's minimum and let LotFor
// re-derive the lot from the wider distance, so the money at risk is
// unchanged and only the geometry moves. Refusing the trade instead would
// silently delete whole sessions on exactly the timeframe Veer trades.
// Where the last closed bar sits in the recent range. 0 = at the low,
// 1 = at the high, 0.5 = dead centre, which is where the losses are.
double RangePos()
{
   int n = InpRangeLook;
   if(n < 3) return 0.5;
   double hi = -DBL_MAX, lo = DBL_MAX;
   for(int k = 1; k <= n; k++)
   {
      double h = iHigh(_Symbol, _Period, k);
      double l = iLow(_Symbol, _Period, k);
      if(h > hi) hi = h;
      if(l < lo) lo = l;
   }
   if(hi <= lo) return 0.5;
   return (iClose(_Symbol, _Period, 1) - lo) / (hi - lo);
}

double MinStopDist()
{
   long   lvl = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double pt  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(lvl <= 0 || pt <= 0.0) return 0.0;
   return (double)lvl * pt;
}

double RoundTripCost()
{
   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                 - SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // Slippage as a FRACTION OF THE SPREAD, not in points. (Audit finding 14.)
   // Points are a digits-dependent unit: 5 points meant $0.05 on a 2-digit
   // gold feed and $0.005 on a 3-digit one, so the same default was wrong by
   // ten times depending on the broker's quote precision. A fraction of the
   // live spread scales itself across every symbol and every digit count,
   // and needs no per-broker tuning.
   double slip = 2.0 * InpSlipSpreads * spread;

   // Commission is quoted per lot in the ACCOUNT currency and has to be
   // converted to price before it can be compared with a stop distance.
   // If the symbol reports no tick value, commission would silently vanish
   // from the cost gate - so refuse to pretend the trade is cheap.
   double mpp = MoneyPerPricePerLot();
   if(mpp <= 0.0)
   {
      static bool warned = false;
      if(!warned)
      {
         warned = true;
         Print("WARNING: this symbol reports no usable tick value, so "
               "commission cannot be converted to price. The cost gate is "
               "counting spread and slippage only and is UNDERSTATING cost.");
      }
      return spread + slip;
   }
   return spread + slip + InpCommPerLot / mpp;
}

// Kaufman efficiency ratio: net distance divided by the length of the path
// walked to get there. 1.0 is a straight line, 0.0 is pure noise. Reads only
// closed bars, so it is available at the moment of the decision.
double EfficiencyRatio(int len)
{
   if(len < 2) return 1.0;
   if(Bars(_Symbol, _Period) < len + 3) return 1.0;
   double net = MathAbs(iClose(_Symbol, _Period, 1)
                      - iClose(_Symbol, _Period, 1 + len));
   double path = 0.0;
   for(int k = 1; k <= len; k++)
      path += MathAbs(iClose(_Symbol, _Period, k) - iClose(_Symbol, _Period, k + 1));
   return (path > 0.0) ? net / path : 0.0;
}

// SuperTrend direction changes in the last `len` CLOSED bars.
int FlipsIn(int len)
{
   int n = MathMin(len, g_flipHistN);
   int c = 0;
   for(int k = 0; k < n; k++)
      if(g_flipHist[k] != 0) c++;
   return c;
}

// "this ea doesnt see reversals clearly ... therefore close later than we can"
//
// A SuperTrend flip is not a reversal - on M1 it flips constantly. A REVERSAL
// is structural: the trade stops making new extremes, and then price BREAKS
// the last swing point in the opposite direction. Two conditions, both from
// closed bars, and it cannot fire on a single opposite candle - which Veer has
// ruled out explicitly and repeatedly.
//
// Returns +1 if structure has broken UP (bad for a short), -1 if DOWN (bad for
// a long), 0 otherwise.
int ReversalAgainst(int dir)
{
   int look = 30;
   if(Bars(_Symbol, _Period) < look + 5) return 0;

   // the most recent confirmed swing in the direction the trade cares about
   double swHi = 0.0, swLo = 0.0;
   int    swHiBar = -1, swLoBar = -1;
   for(int i = 3; i <= look; i++)
   {
      double h = iHigh(_Symbol, _Period, i);
      double l = iLow(_Symbol, _Period, i);
      bool isHi = h > iHigh(_Symbol, _Period, i - 1)
               && h > iHigh(_Symbol, _Period, i - 2)
               && h > iHigh(_Symbol, _Period, i + 1)
               && h > iHigh(_Symbol, _Period, i + 2);
      bool isLo = l < iLow(_Symbol, _Period, i - 1)
               && l < iLow(_Symbol, _Period, i - 2)
               && l < iLow(_Symbol, _Period, i + 1)
               && l < iLow(_Symbol, _Period, i + 2);
      if(isHi && swHiBar < 0) { swHi = h; swHiBar = i; }
      if(isLo && swLoBar < 0) { swLo = l; swLoBar = i; }
      if(swHiBar >= 0 && swLoBar >= 0) break;
   }

   double c1 = iClose(_Symbol, _Period, 1);

   // a LONG is reversed when price CLOSES below the last swing low
   if(dir > 0 && swLoBar > 0 && c1 < swLo) return -1;
   // a SHORT is reversed when price CLOSES above the last swing high
   if(dir < 0 && swHiBar > 0 && c1 > swHi) return 1;
   return 0;
}

int TrendRisk(string &why)
{
   why = "";
   if(!InpUseTrendAge) return 0;
   int sc = 0;

   int rb = RunBars();
   if(rb >= InpRunOldBars)
   {
      sc++;
      why += StringFormat("run %d bars old ", rb);
   }

   double rm = RunMoveAtr();
   if(rm >= InpRunFarAtr)
   {
      sc++;
      why += StringFormat("run %.1f ATR far ", rm);
   }

   double adx = ADXValue(1);
   if(adx > 0.0 && adx >= InpRunAdx)
   {
      sc++;
      why += StringFormat("ADX %.0f ", adx);
   }

   if(sc == 0) why = StringFormat("run %d bars / %.1f ATR - not exhausted", rb, rm);
   return sc;
}

// How much of a peak the EA is willing to hand back, given how big that peak
// is and how far the trend has already run. Two forces, both tightening:
//   - a bigger peak is worth protecting harder (30% of 1R is 0.3R and is the
//     price of letting a trade breathe; 30% of 6R is 1.8R and is the failure
//     Veer is describing). This is the E-051 ratchet.
//   - an old, stretched, crowded trend deserves less rope than a fresh one.
// Bars since this position last made a new best. The whole of E-056.
int StallBars(int ti)
{
   if(ti < 0 || ti >= g_tkCount || g_tkPeakBar[ti] == 0) return 0;
   int b = iBarShift(_Symbol, _Period, g_tkPeakBar[ti], false);
   return (b < 0) ? 0 : b;
}

// How much of a peak the EA will hand back, given how big the peak is, how
// far the run has already gone, and - now - whether the trade is still
// working. A trade making new highs gets ROPE; one that stopped climbing
// twenty bars ago gets a leash. Measured: at stall 0-1 a trade gives it back
// 24% of the time on GOLD 15m, at stall 25+ it is 62%.
double GiveBackAllowed(double peakR, int stall, bool afterImpulse)
{
   double gb = InpGbBase;
   if(peakR >= InpGbTier2R) gb = InpGbTier2;
   if(peakR >= InpGbTier3R) gb = InpGbTier3;

   string w = "";
   int risk = TrendRisk(w);
   if(risk == 1)      gb *= 0.80;
   else if(risk == 2) gb *= 0.62;
   else if(risk >= 3) gb *= 0.45;

   // E-056, AS CORRECTED BY E-073. These tiers used to run 1.35 down to 0.55,
   // a 2.5x spread, on the strength of "8 of 8 markets, monotone". That result
   // took ONE OBSERVATION PER BAR. A trade that runs 61 bars contributed 61
   // rows sharing one entry, one peak and one outcome, and every count in
   // E-056 treated them as 61 independent facts.
   //
   // E-073 re-ran it with each trade voting once. Pooled over 1826 independent
   // trades across eight markets:
   //
   //     counting BARS        gap +0.289   95% [+0.264, +0.316]   clear
   //     ONE VOTE PER TRADE   gap +0.046   95% [-0.002, +0.105]   SPANS ZERO
   //
   // Six markets of eight still lean positive and the pooled point estimate is
   // positive, so the DIRECTION is kept - a trade still making new highs gets
   // more rope than one that stopped 25 bars ago. But the effect is 6x smaller
   // than the number these tiers were cut from, and at 95% it does not clear
   // zero. So the spread is cut by the same factor: 1.35/0.55 becomes
   // 1.07/0.93. That is what +0.046 buys. Set InpStallScales=false to remove
   // it entirely, which the evidence would also permit.
   if(InpStallScales)
   {
      if(stall <= 1)       gb *= 1.07;
      else if(stall <= 3)  gb *= 1.04;
      else if(stall <= 6)  gb *= 1.00;
      else if(stall <= 12) gb *= 0.98;
      else if(stall <= 25) gb *= 0.95;
      else                 gb *= 0.93;
   }

   // E-057: an impulse gives back more of itself than an ordinary bar does,
   // so a peak printed by one is worth less rope. This is the ONLY impulse
   // behaviour the control supported - "buy the bounce" and "wait for the
   // pullback then resume" both matched the control exactly and are not
   // implemented anywhere in this EA.
   if(afterImpulse) gb *= InpImpulseTighten;

   // NEVER SO TIGHT THAT THE EXIT COSTS MORE THAN IT SAVES. (Audit finding 8.)
   // At trend risk 3 the shipped tiers gave 18% x 0.45 = 8.1%, which on a
   // 1.5R peak is a 0.12R retrace - INSIDE E-053's 0.15-0.22R round-trip cost
   // for M1 gold. An exit that fires inside its own spread is a fee, not a
   // rule. The allowance is therefore floored so the give-back it permits is
   // always at least twice the round trip.
   double floorGb = 0.08;
   double a = ATR(1);
   if(a > 0.0 && peakR > 0.0)
   {
      double stopDist = InpStopAtrMult * a;
      if(stopDist > 0.0)
      {
         double costR = RoundTripCost() / stopDist;   // cost expressed in R
         floorGb = MathMax(floorGb, (2.0 * costR) / peakR);
      }
   }
   return MathMax(gb, MathMin(floorGb, 0.60));
}

//===================================================================
//  MODULE: PROFIT PROTECTION  (runs on EVERY TICK)
//===================================================================
// WHY EVERY TICK, when everything else in this EA runs on bar close:
// the whole complaint is about profit disappearing while nothing acts. On M1
// a bar-close-only exit watches up to 60 seconds of give-back before it is
// even allowed to look. Entries stay on bar close - that is what keeps the
// backtest honest (it is why v19.18 was rejected). Exits do not have that
// problem: acting sooner than the backtest assumed can only close nearer the
// trigger, never further from it.
// Test this in the Strategy Tester on "Every tick based on real ticks".
void UpdatePeaks()
{
   // register anything new, and refresh every peak
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)  continue;

      long   type = PositionGetInteger(POSITION_TYPE);
      int    dir  = (type == POSITION_TYPE_BUY) ? 1 : -1;
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      string cmt  = PositionGetString(POSITION_COMMENT);
      double prof = PositionGetDouble(POSITION_PROFIT)
                  + PositionGetDouble(POSITION_SWAP);
      double px   = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                              : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      int ti = TrackFind(tk);
      if(ti < 0)
      {
         // OriginalRisk reads the risk stamped into the comment at entry, so
         // it stays correct after the stop has been trailed away from it.
         ti = TrackAdd(tk, OriginalRisk(open, sl, cmt));
         if(ti < 0) continue;
      }

      // snapshot BEFORE the update: this is what ProtectPositions tests against
      g_tkPeakPrev[ti] = g_tkPeakPx[ti];

      double fav = (px - open) * dir;
      double adv = (open - px) * dir;
      if(fav > g_tkPeakPx[ti])
      {
         g_tkPeakPx[ti]   = fav;
         g_tkPeakTime[ti] = TimeCurrent();
         g_tkPeakBar[ti]  = iTime(_Symbol, _Period, 0);
         // E-057. Was this peak printed by an impulse bar? Measured across 8
         // of 8 markets, an impulse hands back MORE of its own range than a
         // matched non-impulse bar does - median 1.07-1.36 against 0.92-1.13.
         // Small, unanimous, and the only one of the three readings of an
         // impulse that survived its control.
         double aNow = ATR(1);
         double rNow2 = iHigh(_Symbol, _Period, 1) - iLow(_Symbol, _Period, 1);
         g_tkPeakImp[ti] = (aNow > 0.0 && rNow2 >= InpImpulseAtr * aNow);
      }
      if(adv > g_tkWorstPx[ti]) g_tkWorstPx[ti] = adv;
      if(prof > g_tkPeakMoney[ti]) g_tkPeakMoney[ti] = prof;
   }

   // forget positions that have closed
   for(int i = g_tkCount - 1; i >= 0; i--)
      if(!PositionSelectByTicket(g_tkId[i])) TrackDrop(i);

   // basket peak
   Basket b;
   Snapshot(b);
   if(b.n == 0)
   {
      // flat: the basket is over, so its peak resets. Nothing is carried into
      // the next one - a fresh basket has given nothing back yet.
      g_bkPeak = 0.0; g_bkPeakTime = 0; g_bkStart = 0; g_bkArmed = false;
      g_bkRealized = 0.0;
      g_bkLocked   = false;
      return;
   }
   if(g_bkStart == 0) g_bkStart = TimeCurrent();
   if(b.money > g_bkPeak)
   {
      g_bkPeak     = b.money;
      g_bkPeakTime = TimeCurrent();
   }
}


//===================================================================
//  MODULE: THE DISASTER BRAKE
//===================================================================
// Runs on EVERY TICK. It is the only thing in this EA that can close a losing
// trade before its stop, and it exists because the stop is deliberately wide.
//
// TWO TRIGGERS, both aimed at the same event - the market moving faster than a
// stop can be relied on:
//   VELOCITY  price has travelled InpBrakeAtr against us within InpBrakeBars.
//   SPREAD    the spread has blown out past InpMaxSpreadX times its own
//             running average, which is what news looks like from inside an
//             EA. A stop is not dependable while that is true, and neither is
//             the fill we would get - so the position goes now, at a spread we
//             can still see, rather than after a gap we cannot.
void DisasterBrake()
{
   if(!InpUseBrake) return;
   if(PositionsTotal() == 0) return;

   double a = ATR(1);
   if(a <= 0.0) return;

   double spNow = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double spAvg = (g_spN > 20) ? g_spSum / (double)g_spN : 0.0;
   bool   blown = (spAvg > 0.0 && InpMaxSpreadX > 0.0
                   && spNow > InpMaxSpreadX * spAvg);

   int look = MathMax(InpBrakeBars, 1);
   double was = iClose(_Symbol, _Period, look);
   double now = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)  continue;

      long   type = PositionGetInteger(POSITION_TYPE);
      int    dir  = (type == POSITION_TYPE_BUY) ? 1 : -1;
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double prof = PositionGetDouble(POSITION_PROFIT);

      // only ever cuts a trade that is ALREADY LOSING. A violent move in our
      // favour is not a disaster and the trail already owns it.
      if(prof >= 0.0) continue;

      double against = (was - now) * dir;      // positive = moved against us
      bool   fast    = (against >= InpBrakeAtr * a);

      if(!fast && !blown) continue;

      string why = fast ? StringFormat("%.1f ATR against us in %d bars",
                                       against / a, look)
                        : StringFormat("spread blew out to %.*f against an "
                                       "average of %.*f", _Digits, spNow,
                                       _Digits, spAvg);
      if(trade.PositionClose(tk))
         Log("DISASTER BRAKE: closed because " + why
             + ". The stop is wide on purpose; this is what makes that safe.");
      else
         Log(StringFormat("DISASTER BRAKE could not close: %d %s",
                          trade.ResultRetcode(), trade.ResultRetcodeDescription()));
   }
}

//===================================================================
//  MODULE: THE PROFIT STOP  —  the fix for "up 4-5 pound, closed in loss"
//===================================================================
// Veer, from forward testing: "we never look at total profit eg total profit
// im up 4-5 pound i somehow close in loss see what i mean this happens 20-40
// times a day easily".
//
// The give-back rules DID exist and they were not the problem. The problem is
// that they are TICK-REACTIVE: ProtectPositions and ProtectBasket wake on a
// tick, see that the profit has fallen below the allowance, and send a MARKET
// CLOSE. On M1 gold a single spike can carry price from +GBP5 to -GBP2 between
// two ticks the EA is handed. By the time the rule looks, the money it was
// protecting has already gone, and it closes at whatever is left.
//
// A market close cannot beat a fast move. The only thing that can hold a
// profit through one is A STOP ORDER SITTING AT THAT PRICE, at the broker,
// which fills without this EA being awake or the terminal being connected.
//
// So the same give-back allowance is now expressed as a STOP LEVEL and pushed
// to the broker every time the peak improves. The tick-reactive rules stay as
// a second line - if a tick does arrive in time they still act - but the stop
// is what actually holds the money.
//
// It is a RATCHET: the stop only ever moves in the profitable direction, so a
// retrace can never widen it.
void TrailProfitStop()
{
   if(!InpUseProfitStop) return;

   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double mn = MinStopDist();

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)  continue;

      int ti = TrackFind(tk);
      if(ti < 0 || g_tkRisk[ti] <= 0.0) continue;

      double peakPx = g_tkPeakPx[ti];          // best excursion, in PRICE
      if(peakPx <= 0.0) continue;
      double peakR    = peakPx / g_tkRisk[ti];
      double peakMoney= g_tkPeakMoney[ti];

      // Arm on the SAME terms as the give-back: R decides, money is a floor.
      if(peakR < InpProfitStopArmR) continue;
      if(InpGbMinMoney > 0.0 && peakMoney < InpGbMinMoney) continue;

      // keep this much of the peak
      double allow = GiveBackAllowed(peakR, StallBars(ti), false);
      double keep  = peakPx * (1.0 - allow);

      // never place it inside the round trip - that is a fee, not a rule
      double rt = RoundTripCost();
      if(keep < rt) continue;

      long   type = PositionGetInteger(POSITION_TYPE);
      int    dir  = (type == POSITION_TYPE_BUY) ? 1 : -1;
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      double px   = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                              : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      double want = NormalizeDouble(open + dir * keep, dg);

      // RATCHET: only ever in the profitable direction
      bool better = (sl == 0.0) || ((dir > 0) ? (want > sl) : (want < sl));
      bool safe   = (dir > 0) ? (want < px) : (want > px);
      bool room   = (mn <= 0.0) || (MathAbs(px - want) >= mn);
      if(!better || !safe || !room) continue;

      if(trade.PositionModify(tk, want, tp))
         Log(StringFormat("profit stop -> %.*f  (peak %s = %.2fR, keeping "
                          "%.0f%% = %s). The broker holds this now, so a spike "
                          "cannot take it back.",
                          dg, want, Money(peakMoney), peakR,
                          (1.0 - allow) * 100.0,
                          Money(peakMoney * (1.0 - allow))));
   }
}

// PER-POSITION give-back. This is the E-051 rule, in the EA.
void ProtectPositions()
{
   if(!InpUseGiveBack) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)  continue;

      int ti = TrackFind(tk);
      if(ti < 0 || g_tkRisk[ti] <= 0.0) continue;
      if(g_tkGbDone[ti]) continue;      // banks once, then the trail has it

      double peakR = g_tkPeakPrev[ti] / g_tkRisk[ti];   // NOT this tick's high

      // R DECIDES, MONEY IS A FLOOR. This was an OR, and the OR was a bug:
      // GBP2.00 at 0.03 lots is 0.03R on 1h and 0.65R on M1, so the money
      // branch always fired first and InpGbArmR never did anything at all.
      // P91b proved it by sweeping the TRAIL's arming level from 0R to 2R and
      // getting byte-identical results - the trade was always already shut.
      // R is scale-free; money is not, and this EA is measured on 1h at 0.03
      // lots and run on M1 at 0.01.
      if(peakR < InpGbArmR) continue;
      if(InpGbArmMoney > 0.0 && g_tkPeakMoney[ti] < InpGbArmMoney) continue;
      if(InpGbMinMoney > 0.0 && g_tkPeakMoney[ti] < InpGbMinMoney) continue;

      long   type = PositionGetInteger(POSITION_TYPE);
      int    dir  = (type == POSITION_TYPE_BUY) ? 1 : -1;
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double px   = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                              : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double rNow = (px - open) * dir / g_tkRisk[ti];

      int    stall = StallBars(ti);
      double gb    = GiveBackAllowed(peakR, stall, g_tkPeakImp[ti]);
      double keep  = peakR * (1.0 - gb);

      // If the trade armed on MONEY rather than on R, the R-space floor above
      // can sit below zero and never trigger. Protect the money peak directly
      // as well, and act on whichever floor is hit first.
      bool moneyBreach = false;
      if(armedMoney && g_tkPeakMoney[ti] > 0.0)
      {
         double mNow = PositionGetDouble(POSITION_PROFIT)
                     + PositionGetDouble(POSITION_SWAP);
         moneyBreach = (mNow <= g_tkPeakMoney[ti] * (1.0 - gb));
      }
      if(rNow > keep && !moneyBreach) continue;

      // One close REQUEST at a time. Without this a requote produced a fresh
      // close attempt, a Log line and a full FileOpen/Write/Close journal row
      // on every tick, because a failed close does not change the trigger.
      // (Audit findings 5 and 6.)
      if(TimeCurrent() - g_tkCloseTry[ti] < 3) continue;
      g_tkCloseTry[ti] = TimeCurrent();

      double money = PositionGetDouble(POSITION_PROFIT)
                   + PositionGetDouble(POSITION_SWAP);
      double vol   = PositionGetDouble(POSITION_VOLUME);

      // BANK PART, DO NOT CLOSE. E-051b: on gold the trail out-earns the
      // give-back rule roughly three to one, so closing here sells the runner
      // that pays for everything. Banking half keeps two thirds of the
      // trail's expectancy for half its chance of a 30% drawdown, and it is
      // also the "pennies AND the big move out of one signal" that this EA
      // was asked for. InpGbClosePart = 1.0 restores the close-it-all rule.
      double part = MathMin(MathMax(InpGbClosePart, 0.0), 1.0);
      double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      double cut  = vol * part;
      if(step > 0.0) cut = MathFloor(cut / step) * step;

      // If half is not a tradeable size, the choice is all or nothing. Take
      // it all: the rule fired, and leaving a position the rule wanted out of
      // because the lot arithmetic was awkward is the worst of both.
      bool wholeThing = (part >= 1.0) || (cut < vmin) || (vol - cut < vmin);
      bool ok = wholeThing ? trade.PositionClose(tk)
                           : trade.PositionClosePartial(tk, cut);
      if(!ok)
      {
         Log(StringFormat("give-back %s REJECTED, retcode %d - will retry",
                          wholeThing ? "close" : "partial",
                          trade.ResultRetcode()));
      }
      else
      {
         g_tkGbDone[ti] = true;
         double back = g_tkPeakMoney[ti] - money;
         if(back > g_stWorstGB) g_stWorstGB = back;
         Log(StringFormat("GIVE-BACK: peaked %.2fR (%s), now %.2fR (%s), "
                          "allowance %.0f%% - %s",
                          peakR, Money(g_tkPeakMoney[ti]), rNow, Money(money),
                          gb * 100.0,
                          wholeThing
                          ? "closed in full"
                          : StringFormat("banked %.2f of %.2f, rest rides the trail",
                                         cut, vol)));
         Journal("GIVEBACK", dir > 0 ? "long" : "short", px,
                 wholeThing ? vol : cut, 0, 0, money,
                 StringFormat("peak %.2fR kept %.2fR", peakR, rNow));
      }
   }
}

// LOCK EACH POSITION OUT OF LOSS once it has been worth InpLockPosMoney.
// This is the answer to a trade that goes 30p green and closes red: after this
// fires, the worst that trade can do is zero.
void LockPositions()
{
   if(InpLockPosR <= 0.0 && InpLockPosMoney <= 0.0) return;

   double cost = RoundTripCost();
   double mn   = MinStopDist();
   int    dg   = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)  continue;

      int ti = TrackFind(tk);
      if(ti < 0) continue;
      // R first, money only as a noise floor - same fix as the give-back.
      // GBP0.50 at 0.03 lots is 0.21 points, which is INSIDE the spread: the
      // lock was arming before the trade had covered its own cost. In the
      // scale-free grid a 1.0R lock with a 3R give-back is the best pair on
      // both timeframes tested.
      if(g_tkRisk[ti] <= 0.0) continue;
      double peakRl = g_tkPeakPx[ti] / g_tkRisk[ti];
      if(InpLockPosR > 0.0 && peakRl < InpLockPosR) continue;
      if(InpLockPosMoney > 0.0 && g_tkPeakMoney[ti] < InpLockPosMoney) continue;

      long   type = PositionGetInteger(POSITION_TYPE);
      int    dir  = (type == POSITION_TYPE_BUY) ? 1 : -1;
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      double px   = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                              : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      double lock = NormalizeDouble(open + dir * cost, dg);
      bool better = (dir > 0) ? (lock > sl) : (lock < sl);
      bool room   = (mn <= 0.0) || (MathAbs(px - lock) >= mn);
      bool safe   = (dir > 0) ? (lock < px) : (lock > px);
      if(better && room && safe && trade.PositionModify(tk, lock, tp))
         Log(StringFormat("locked out of loss: it has been %s green, so the "
                          "worst this trade can now do is zero",
                          Money(g_tkPeakMoney[ti])));
   }
}

// LOCK THE BASKET OUT OF LOSS once it has been worth InpLockAtMoney.
// Not a profit target - a floor. See the note on InpLockAtMoney for why this
// is the least damaging version of a rule that measured badly.
void LockBasket()
{
   if(InpLockAtMoney <= 0.0) return;
   if(g_bkLocked && InpLockOnlyOnce) return;

   Basket b;
   Snapshot(b);
   if(b.n == 0) return;
   if(b.money < InpLockAtMoney) return;

   double cost = RoundTripCost();
   double mn   = MinStopDist();
   int    dg   = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   int    moved = 0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)  continue;

      long   type = PositionGetInteger(POSITION_TYPE);
      int    dir  = (type == POSITION_TYPE_BUY) ? 1 : -1;
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      double px   = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                              : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      // break-even PLUS the round trip, so the exit is not itself a loss
      double lock = NormalizeDouble(open + dir * cost, dg);

      bool better = (dir > 0) ? (lock > sl) : (lock < sl);
      bool room   = (mn <= 0.0) || (MathAbs(px - lock) >= mn);
      bool safe   = (dir > 0) ? (lock < px) : (lock > px);
      if(better && room && safe && trade.PositionModify(tk, lock, tp))
         moved++;
   }

   if(moved > 0)
   {
      g_bkLocked = true;
      Log(StringFormat("basket reached %s - %d stop(s) moved to break-even "
                       "plus costs. This basket can no longer lose.",
                       Money(b.money), moved));
   }
}

// BASKET give-back. The rule that would have saved the GBP12 basket.
//
// A basket of four positions can be handed back without any single position
// breaking its own give-back rule: each one individually retraces less than
// its allowance, and the TOTAL still round-trips. Nothing but a total-level
// rule sees that, which is exactly why it kept happening.
void ProtectBasket()
{
   if(!InpUseBasket) return;

   Basket b;
   Snapshot(b);
   if(b.n == 0) return;

   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   // MathMin, not MathMax. The old line armed at the LARGER of the two, so on
   // a small account the GBP 2.00 floor dominated and a GBP 2.50 peak had
   // almost no protected range at all. The floor is meant to stop the rule
   // firing on noise, not to postpone it until the money is gone.
   double arm = MathMin(MathMax(eq * InpBasketArmPct / 100.0, 0.25),
                        InpBasketMinMoney);

   // an old, stretched, crowded run gets protected sooner, not later
   string w = "";
   int risk = TrendRisk(w);
   if(risk >= 2) arm *= 0.60;

   if(g_bkPeak < arm) return;         // never got big enough to be worth saving
   if(!g_bkArmed)
   {
      g_bkArmed = true;
      Log(StringFormat("basket protection ARMED at %s peak (%d positions, "
                       "%.2f lots, trend %s)",
                       Money(g_bkPeak), b.n, b.lots, w));
   }

   double allowed = InpBasketGiveBack;
   if(risk == 1)      allowed *= 0.80;
   else if(risk == 2) allowed *= 0.62;
   else if(risk >= 3) allowed *= 0.45;
   allowed = MathMax(allowed, 0.10);

   double floorMoney = g_bkPeak * (1.0 - allowed);
   if(b.money > floorMoney) return;

   double back = g_bkPeak - b.money;
   if(back > g_stWorstGB) g_stWorstGB = back;
   Log(StringFormat("BASKET PROTECT: peaked %s, now %s, handed back %s "
                    "(%.0f%% of peak, allowance %.0f%%). Closing %s.",
                    Money(g_bkPeak), Money(b.money), Money(back),
                    (g_bkPeak > 0 ? 100.0 * back / g_bkPeak : 0.0),
                    allowed * 100.0,
                    InpBasketCloseAll ? "the basket" : "the losing side"));

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)  continue;
      double prof = PositionGetDouble(POSITION_PROFIT)
                  + PositionGetDouble(POSITION_SWAP);
      // InpBasketCloseAll=false keeps the position that is still working and
      // cuts the ones dragging the total down. It banks less and it can be
      // right more often. Neither version has been measured against the other
      // on live fills, so the default is the simple one.
      if(InpBasketCloseAll || prof < 0.0)
         trade.PositionClose(tk);
   }
   Journal("BASKET", b.dir > 0 ? "long" : "short", b.wAvgEntry, b.lots,
           0, 0, b.money, StringFormat("peak %s given back %s",
                                       Money(g_bkPeak), Money(back)));
}

// BLOCKER 4. The daily-loss and max-drawdown locks lived inside
// RiskAllowsEntry, which has exactly one call site: TryEntry, reached only on
// a bar close, only after the flip test. So a limit could be breached and
// nothing would notice until the next signal - and nothing would ever close
// the positions doing the damage. A limit that only declines new trades is
// not a limit, it is a preference.
//
// This runs on every tick. It sets the locks the moment they are breached,
// persists them so a restart cannot clear them (see BLOCKER 1), and - if
// InpFlattenOnBreach is on - closes what is open, because on a prop account
// the breach IS the failure and holding through it does not undo it.
void CheckGuardsTick()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   bool   hit = false;
   string why = "";

   if(!g_lockedPerm && g_peakEq > 0.0)
   {
      double ddPct = 100.0 * (g_peakEq - eq) / g_peakEq;
      if(ddPct >= InpMaxDDPct)
      {
         g_lockedPerm = true; hit = true;
         why = StringFormat("MAX DRAWDOWN %.2f%% from peak %.2f - PERMANENT LOCK",
                            ddPct, g_peakEq);
      }
   }
   if(!g_lockedDay && g_dayStartEq > 0.0)
   {
      double dayPct = 100.0 * (g_dayStartEq - eq) / g_dayStartEq;
      if(dayPct >= InpDailyLossPct)
      {
         g_lockedDay = true; hit = true;
         why = StringFormat("DAILY LOSS %.2f%% from %.2f - locked for today",
                            dayPct, g_dayStartEq);
      }
   }

   if(!hit) return;

   Log(why);
   PersistGuards();

   if(!InpFlattenOnBreach) return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)  continue;
      if(trade.PositionClose(tk))
         Log("closed on guard breach: " + IntegerToString((int)tk));
   }
   Journal("GUARD", "-", 0, 0, 0, 0, eq, why);
}

//===================================================================
//  MODULE: STACKING
//===================================================================
// Default InpMaxStack = 1, so this EA does not stack at all until Veer turns
// it on deliberately. That is not timidity: stacking has never been measured
// on these entries, and the live baskets that prompted this whole rebuild
// were stacked ones. The gates below are what it has to pass if he does.
bool StackAllows(int dir, string &why)
{
   Basket b;
   Snapshot(b);
   if(b.n == 0) return true;

   if(b.n >= InpMaxStack)
   { why = StringFormat("already %d position(s), max %d", b.n, InpMaxStack); return false; }

   if(b.dir != 0 && b.dir != dir)
   { why = "would hedge the basket"; return false; }

   if(g_lastEntryBar > 0
      && iBarShift(_Symbol, _Period, g_lastEntryBar, false) < InpStackCoolBars)
   { why = StringFormat("only %d bars since the last entry, need %d",
                        iBarShift(_Symbol, _Period, g_lastEntryBar, false),
                        InpStackCoolBars); return false; }

   string w = "";
   int risk = TrendRisk(w);
   if(risk >= 2)
   { why = "trend already run: " + w; return false; }

   // DO NOT ADD AFTER PROFIT. An add on top of a basket that is already green
   // is the trade that turns a good day into a flat one: it is bought at the
   // worst price of the move so far, and it enlarges the position exactly
   // when the give-back risk is highest.
   double px = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                         : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   bool better = (dir > 0) ? (px < b.wAvgEntry) : (px > b.wAvgEntry);
   if(!better)
   { why = "add would be at a worse price than the basket average"; return false; }

   double cap = InpMaxNetLots;
   if(cap <= 0.0)
   {
      // auto cap: no more one-way exposure than InpMaxStack normal-sized
      // trades would be. Without this, a run of flips in one direction can
      // build a position nobody chose.
      double atr = ATR(1);
      if(atr > 0) cap = LotFor(InpStopAtrMult * atr) * InpMaxStack;
   }
   if(cap > 0.0 && MathAbs(b.netLots) >= cap)
   { why = StringFormat("net exposure %.2f lots already at the %.2f cap",
                        MathAbs(b.netLots), cap); return false; }

   return true;
}

void RegisterEntry(int dir)
{
   // is this the same way as the last trade we took?
   g_thisDir = dir;
   g_sameAsLast = (g_lastEntryDir != 0 && dir == g_lastEntryDir);
   g_lastEntryDir = dir;

   g_lastEntryDir = dir;
   g_lastEntryBar = iTime(_Symbol, _Period, 0);
}

//===================================================================
//  MODULE: EXECUTION BOX
//===================================================================
// Nothing here is a decision. It is the answer to "what is actually
// happening", written where it cannot scroll away.
//
// The row that matters most is KEPT OF PEAK. If the EA banks GBP60 out of
// GBP100 of floating profit it ever showed, that is 60% and it is the single
// number that says whether the execution problem is fixed. GREEN->RED is the
// second: trades that went into profit and did not close profitably. Those
// two rows are Veer's complaint, as a measurement.
// A panel over candles is unreadable without something behind it. This draws
// one rectangle sized to the rows and puts every label on top of it.
void BoxBackdrop(int rows)
{
   string nm = "STS_box_bg";
   if(ObjectFind(0, nm) < 0)
   {
      ObjectCreate(0, nm, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, nm, OBJPROP_CORNER, (ENUM_BASE_CORNER)InpBoxCorner);
      ObjectSetInteger(0, nm, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, nm, OBJPROP_BGCOLOR, InpBoxBg);
      ObjectSetInteger(0, nm, OBJPROP_COLOR, InpBoxBorder);
      ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, nm, OBJPROP_BACK, false);
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nm, OBJPROP_ZORDER, 0);
   }
   ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, InpBoxX - 10);
   ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, InpBoxY - 12);
   ObjectSetInteger(0, nm, OBJPROP_XSIZE, InpBoxWidth);
   ObjectSetInteger(0, nm, OBJPROP_YSIZE, rows * (InpBoxSize + 6) + 16);
}

void BoxLine(int idx, string txt, color c)
{
   string nm = StringFormat("STS_box_%02d", idx);
   if(ObjectFind(0, nm) < 0)
   {
      ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, nm, OBJPROP_CORNER, (ENUM_BASE_CORNER)InpBoxCorner);
      ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, InpBoxX);
      ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, InpBoxY + idx * (InpBoxSize + 6));
      ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, InpBoxSize);
      ObjectSetString(0, nm, OBJPROP_FONT, "Consolas");
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nm, OBJPROP_BACK, false);
      ObjectSetInteger(0, nm, OBJPROP_ZORDER, 1);   // above the backdrop
      // right-hand corners read right-to-left, or the text runs off the chart
      if(InpBoxCorner == 1 || InpBoxCorner == 3)
         ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_RIGHT_UPPER);
   }
   // SET THESE EVERY CALL, NOT ONLY AT CREATION.
   // They used to be inside the "if it does not exist yet" block. An object
   // left on the chart by an earlier build kept that build's corner and
   // position forever - so the panel was drawn, correctly, somewhere the
   // chart was not showing. Veer has reported the box not working three
   // times; this is the version of that bug I can actually find.
   ObjectSetInteger(0, nm, OBJPROP_CORNER, (ENUM_BASE_CORNER)InpBoxCorner);
   ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, InpBoxX);
   ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, InpBoxY + idx * (InpBoxSize + 6));
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, InpBoxSize);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR,
        (InpBoxCorner == 1 || InpBoxCorner == 3) ? ANCHOR_RIGHT_UPPER
                                                 : ANCHOR_LEFT_UPPER);
   ObjectSetString(0, nm, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, c);
}

void BoxClear()
{
   for(int i = 0; i < 40; i++)
      ObjectDelete(0, StringFormat("STS_box_%02d", i));
}

void DrawBox()
{
   if(!InpShowBox) return;

   Basket b;
   Snapshot(b);
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);

   // recompute the closed-bar readings once per bar, not once per tick
   datetime bnow = iTime(_Symbol, _Period, 0);
   if(bnow != g_boxBar)
   {
      g_boxBar     = bnow;
      g_boxEff     = EfficiencyRatio(InpChopErLen);
      g_boxFlips   = FlipsIn(InpChopFlipLen);
      g_boxRisk    = TrendRisk(g_boxRiskWhy);
      g_boxCost    = RoundTripCost();
      g_boxStop    = InpStopAtrMult * ATR(1);
   }
   string tw  = g_boxRiskWhy;
   int    risk = g_boxRisk;

   color ok   = clrLime, bad = clrTomato, warn = clrOrange;
   color pnlC = (b.money >= 0) ? ok : bad;

   BoxBackdrop(20);
   int r = 0;
   BoxLine(r++, "== SNIPERBOT EXECUTION ==", InpBoxHead);
   BoxLine(r++, StringFormat("open        %d pos  %.2f lots  net %+.2f",
                             b.n, b.lots, b.netLots), InpBoxText);
   BoxLine(r++, StringFormat("basket P/L  %s", Money(b.money)), pnlC);
   BoxLine(r++, StringFormat("basket peak %s   armed %s",
                             Money(b.peakMoney), g_bkArmed ? "YES" : "no"),
           g_bkArmed ? ok : InpBoxText);
   BoxLine(r++, StringFormat("given back  %s%s", Money(b.givenBack),
                             (b.peakMoney > 0
                              ? StringFormat("  (%.0f%% of peak)",
                                             100.0 * b.givenBack / b.peakMoney)
                              : "")),
           (b.givenBack > 0 ? warn : InpBoxText));
   if(b.n > 0)
      BoxLine(r++, StringFormat("best now %.2fR  peaked %.2fR  held %d bars",
                                b.bestR, b.peakR, b.oldestBars), InpBoxText);
   BoxLine(r++, "", InpBoxText);

   // ---- the two rows the whole rebuild exists to move
   double kept = (g_stPeakSum > 0.0) ? 100.0 * g_stRealized / g_stPeakSum : 0.0;
   BoxLine(r++, StringFormat("KEPT OF PEAK   %.0f%%   (%s of %s)",
                             kept, Money(g_stRealized), Money(g_stPeakSum)),
           (g_stPeakSum <= 0 ? InpBoxText : (kept >= 50 ? ok : (kept >= 30 ? warn : bad))));
   BoxLine(r++, StringFormat("GREEN -> RED   %d of %d closed (%.0f%%)",
                             g_stGreenRed, g_stTrades,
                             (g_stTrades > 0 ? 100.0 * g_stGreenRed / g_stTrades : 0.0)),
           (g_stTrades == 0 ? InpBoxText
                            : (g_stGreenRed * 100 <= g_stTrades * 10 ? ok : bad)));
   BoxLine(r++, StringFormat("given back all-time %s   worst one %s",
                             Money(g_stGivenBack), Money(g_stWorstGB)),
           InpBoxText);
   BoxLine(r++, "", InpBoxText);

   BoxLine(r++, StringFormat("closed %d   won %d (%.0f%%)   realized %s",
                             g_stTrades, g_stWins,
                             (g_stTrades > 0 ? 100.0 * g_stWins / g_stTrades : 0.0),
                             Money(g_stRealized)), InpBoxText);
   BoxLine(r++, StringFormat("today  %d trades   %s   equity %s",
                             g_stDayTrades, Money(g_stDayRealized), Money(eq)),
           (g_stDayRealized >= 0 ? ok : bad));
   BoxLine(r++, StringFormat("same-dir %d %.0f%% %s  |  alternating %d %.0f%% %s",
                             g_sdN, (g_sdN > 0 ? 100.0 * g_sdWin / g_sdN : 0.0),
                             Money(g_sdSum),
                             g_altN, (g_altN > 0 ? 100.0 * g_altWin / g_altN : 0.0),
                             Money(g_altSum)), InpBoxText);
   BoxLine(r++, "", InpBoxText);

   BoxLine(r++, StringFormat("run    %s  %d bars  %.1f ATR  risk %d/3",
                             (g_lastSigDir == 1 ? "LONG" : (g_lastSigDir == -1 ? "SHORT" : "-")),
                             RunBars(), RunMoveAtr(), risk),
           (risk >= 2 ? bad : (risk == 1 ? warn : ok)));
   BoxLine(r++, StringFormat("       %s", tw),
           (risk >= 2 ? bad : InpBoxText));
   BoxLine(r++, StringFormat("       supertrend leg %s, %d bars",
                             (g_stDir == -1 ? "UP" : (g_stDir == 1 ? "DOWN" : "-")),
                             g_barsInTrend), InpBoxText);
   // THE ROW THAT SETTLES THE ARGUMENT. If the average spread here is small,
   // the cost floor on the stop (InpMinStopCostX) never binds and the ATR term
   // decides the stop, exactly as before. If it is large, it binds - and the
   // number is measured rather than assumed.
   double spAvg = (g_spN > 0) ? g_spSum / (double)g_spN : 0.0;
   double spEnt = (g_spEntryN > 0) ? g_spEntrySum / (double)g_spEntryN : 0.0;
   BoxLine(r++, StringFormat("spread now %.*f  avg %.*f  entry-avg %.*f  worst %.*f",
                             _Digits, SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                    - SymbolInfoDouble(_Symbol, SYMBOL_BID),
                             _Digits, spAvg, _Digits, spEnt, _Digits, g_spMax),
           InpBoxText);
   BoxLine(r++, StringFormat("cost %.1f%% of stop   efficiency %.2f   flips %d/%d",
                             (g_boxStop > 0 ? 100.0 * g_boxCost / g_boxStop : 0.0),
                             g_boxEff, g_boxFlips, InpChopFlipLen),
           (g_boxStop > 0 && g_boxCost / g_boxStop > InpMaxCostFrac)
           ? bad : InpBoxText);
   BoxLine(r++, StringFormat("give-back allowance now %.0f%%   stall %d bars",
                             GiveBackAllowed(MathMax(b.peakR, 0.0), b.stall, false) * 100.0,
                             b.stall),
           (b.stall > 12 ? warn : InpBoxText));

   string lock = g_lockedPerm ? "LOCKED (max drawdown)"
               : (g_lockedDay ? "locked for today" : "trading");
   BoxLine(r++, StringFormat("state  %s   %d/%d trades today",
                             lock, g_tradesToday, InpMaxTradesDay),
           (g_lockedPerm || g_lockedDay) ? bad : ok);

   // clear anything left over from a longer previous draw
   for(int i = r; i < 40; i++)
      ObjectDelete(0, StringFormat("STS_box_%02d", i));

   // WITHOUT THIS THE BOX DOES NOT UPDATE.
   // Veer: "the profit box is see thru and not good can't see clearly also it
   // doesn't update at all". Object text changes are not shown until the chart
   // is told to repaint; on a quiet chart that can be many seconds, and in the
   // tester it never happens at all. Every value above was being computed
   // correctly and thrown away.
   ChartRedraw(0);
}

//===================================================================
//  MODULE: STATISTICS PERSISTENCE
//===================================================================
// The box is worthless if a terminal restart zeroes it, so the counters live
// in GlobalVariables, which survive restarts. GKey() keys them on ACCOUNT
// LOGIN + MAGIC NUMBER - not on symbol or timeframe. Two charts running this
// EA on the same magic therefore SHARE one set of counters, which is correct
// for the prop-firm guards (the daily loss limit is an account-level rule)
// and is a deliberate choice, not an oversight. Give each chart its own
// InpMagic if you want them counted separately. An earlier version of this
// comment claimed per-symbol keying and contradicted the comment on GKey
// itself twenty lines above.
void SaveStats()
{
   GSet("st_trades",  (double)g_stTrades);
   GSet("st_wins",    (double)g_stWins);
   GSet("st_greenred",(double)g_stGreenRed);
   GSet("st_real",    g_stRealized);
   GSet("st_peaksum", g_stPeakSum);
   GSet("st_back",    g_stGivenBack);
   GSet("st_worstgb", g_stWorstGB);
}

void LoadStats()
{
   g_stTrades    = (int)GGet("st_trades", 0);
   g_stWins      = (int)GGet("st_wins", 0);
   g_stGreenRed  = (int)GGet("st_greenred", 0);
   g_stRealized  = GGet("st_real", 0);
   g_stPeakSum   = GGet("st_peaksum", 0);
   g_stGivenBack = GGet("st_back", 0);
   g_stWorstGB   = GGet("st_worstgb", 0);
}

//==================== LIFECYCLE ====================================

//===================================================================
//  MODULE: THE READOUT
//===================================================================
// Veer, three separate times: "the profit box is not working", "it doesn't
// update at all", "the profit box is still not updating".
//
// The first two fixes were both real bugs and neither was THE bug. The panel
// was being drawn without ChartRedraw (fixed), and the readout lived inside
// DrawBox, which returns early when InpShowBox is off (fixed, moved into
// OnTick). Both shipped. It still did not update, because both fixes left the
// readout depending on the same single thing: A TICK ARRIVING.
//
// OnTick does not run when the market is quiet. It does not run at all when
// the market is shut. It does not run between the EA being attached and the
// first quote. On M1 gold in a dead hour that is minutes of a frozen box
// showing a P/L that has already moved - which is exactly the report, three
// times, and I kept fixing the drawing instead of the trigger.
//
// The readout now also runs off a 250ms TIMER, and once inside OnInit. The
// terminal calls OnTimer whether or not the market is doing anything, so the
// box is live from the instant the EA is attached and it keeps counting
// through silence.
void Readout()
{
   if(!InpBoxComment) return;

   double eq    = AccountInfoDouble(ACCOUNT_EQUITY);
   double spNow = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                - SymbolInfoDouble(_Symbol, SYMBOL_BID);

   Basket bq;
   Snapshot(bq);
   double spAvgQ = (g_spN > 0) ? g_spSum / (double)g_spN : 0.0;

   // A HEARTBEAT. If this clock is frozen the EA is not running, and no other
   // line on this box can be trusted. It is here so that "it is not updating"
   // becomes answerable from the chart instead of from a guess.
   g_readN++;
   string beat = TimeToString(TimeCurrent(), TIME_MINUTES | TIME_SECONDS);

   Comment(StringFormat(
      "SNIPERBOT  build %s\n"
      "%s %s   equity %s   live %s  (%d)\n"
      ">>> TOTAL NOW %s      PEAK %s      GIVEN BACK %s <<<\n"
      "OPEN  %d pos  %.2f lots\n"
      "KEPT OF PEAK %.0f%%   GREEN->RED %d of %d closed\n"
      "TODAY %d trades   %s\n"
      "SAME-DIR %d trades %.0f%% won %s   |   ALTERNATING %d %.0f%% won %s\n"
      "spread now %.*f   avg %.*f   worst %.*f\n"
      "%s",
      STS_BUILD,
      _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period), Money(eq), beat, (int)g_readN,
      Money(bq.money), Money(bq.peakMoney), Money(bq.givenBack),
      bq.n, bq.lots,
      (g_stPeakSum > 0.0 ? 100.0 * g_stRealized / g_stPeakSum : 0.0),
      g_stGreenRed, g_stTrades,
      g_stDayTrades, Money(g_stDayRealized),
      g_sdN,  (g_sdN  > 0 ? 100.0 * g_sdWin  / g_sdN  : 0.0), Money(g_sdSum),
      g_altN, (g_altN > 0 ? 100.0 * g_altWin / g_altN : 0.0), Money(g_altSum),
      _Digits, spNow, _Digits, spAvgQ, _Digits, g_spMax,
      g_lockedPerm ? "LOCKED - max drawdown"
                   : (g_lockedDay ? "locked for today" : "trading")));
}

// The timer exists ONLY to keep the readout and the panel alive when ticks are
// not arriving. It must never enter, size, or close a trade: those stay on the
// tick and the bar close so that the backtest and the live account remain the
// same system. Protection is not here for a reason that is not laziness - it
// reads prices, and prices only move on a tick.
void OnTimer()
{
   Readout();
   DrawBox();
   PB_Draw();
}

int OnInit()
{
   if(!TfGuard("STS", InpMaxTF)) return INIT_FAILED;
   if(InpDemoOnly && AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      Print("REFUSING TO START: InpDemoOnly is true and this is not a demo "
            "account. Set InpDemoOnly=false deliberately to trade live.");
      return INIT_FAILED;
   }

   g_atrHandle = iATR(_Symbol, _Period, InpStAtrLen);
   if(g_atrHandle == INVALID_HANDLE) { Print("ATR handle failed"); return INIT_FAILED; }
   g_adxHandle = iADX(_Symbol, _Period, 14);
   if(g_adxHandle == INVALID_HANDLE) { Print("ADX handle failed"); return INIT_FAILED; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(20);

   LoadStats();

   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dayStartEq = eq;
   g_peakEq     = eq;
   g_dayStamp   = DayStamp();

   // AFTER the defaults are set, never before: LoadGuards only overwrites
   // what it actually finds stored, and a restart must not be able to erase
   // a lock or move the drawdown baseline.
   LoadGuards();

   // 250ms: fast enough that the P/L line tracks the terminal's own, slow
   // enough to cost nothing. Started BEFORE the first Print so the box is on
   // the chart before anything below can fail.
   EventSetMillisecondTimer(250);
   Readout();
   DrawBox();
   PB_Draw();

   Print("=== SNIPERBOT BUILD " + STS_BUILD + " ===");
   Print("If that build stamp is not the one in the message that sent you this "
         "file, MetaEditor has not rebuilt it. Open the .mq5 and press F7.");
   PrintFormat("Broker spread right now: %.*f. The stop's cost floor "
               "(InpMinStopCostX = %.1f) only binds if the spread is large "
               "relative to ATR - watch the 'spread' row in the box.",
               _Digits, SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                      - SymbolInfoDouble(_Symbol, SYMBOL_BID), InpMinStopCostX);
   PrintFormat("SuperTrendSniper started. ST(%d, %.2f) DEMA(%d) risk %.2f%% "
               "target %.1fR  BE=%s trail=%s",
               InpStAtrLen, InpStMult, DemaEffLen(), InpRiskPct, InpTargetR,
               InpUseBreakEven ? "ON" : "off", InpUseTrail ? "ON" : "off");
   if(InpUseBreakEven)
      Print("WARNING: break-even is ON. It measured as the worst exit rule on "
            "all four markets tested. Only leave it on if you are testing it.");

   int pbCorner = InpBoxCorner == 0 ? CORNER_LEFT_UPPER  :
                  InpBoxCorner == 1 ? CORNER_RIGHT_UPPER :
                  InpBoxCorner == 2 ? CORNER_LEFT_LOWER  : CORNER_RIGHT_LOWER;
   PB_Init("STSPB.", "SUPERTREND SNIPER", InpMagic, InpShowProfitBox,
           pbCorner, InpBoxX, InpBoxY, "SUPERTREND");
   if(InpTrackMagic2 != 0) PB_AddStrategy(InpTrackMagic2, InpTrackLabel2);
   if(InpTrackMagic3 != 0) PB_AddStrategy(InpTrackMagic3, InpTrackLabel3);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   SaveStats();
   PB_Destroy();
   BoxClear();
   ObjectDelete(0, "STS_box_bg");
   Comment("");
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
   if(g_adxHandle != INVALID_HANDLE) IndicatorRelease(g_adxHandle);
}

void OnTick()
{
   // Equity peak tracks on every tick so the drawdown lock cannot be
   // out-run between bars.
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_peakEq) g_peakEq = eq;

   int ds = DayStamp();
   if(ds != g_dayStamp)
   {
      g_dayStamp    = ds;
      g_dayStartEq  = eq;
      g_tradesToday = 0;
      g_lockedDay   = false;
      g_stDayRealized = 0.0;
      g_stDayTrades   = 0;
      Log("new trading day, daily counters reset");
   }

   // ---- EVERY TICK: watch the profit and protect it.
   // This is the only part of the EA that does not wait for a bar to close,
   // and it is deliberate. The complaint being fixed is profit evaporating
   // while nothing acts; on M1 a bar-close-only exit is allowed to look once
   // a minute. Entries stay on bar close - that is what keeps the backtest
   // and the live account the same system.
   // measure the spread on every tick, before anything decides anything
   double spNow = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(spNow > 0.0)
   {
      if(spNow < g_spMin) g_spMin = spNow;
      if(spNow > g_spMax) g_spMax = spNow;
      g_spSum += spNow;
      g_spN++;
   }

   Readout();

   DisasterBrake();        // FIRST. Nothing outranks getting out of a disaster.
   CheckGuardsTick();      // then: a breach outranks a rule
   UpdatePeaks();
   ProtectPositions();
   LockPositions();       // each trade out of loss first
   TrailProfitStop();     // then hand the profit to the broker to hold
   LockBasket();          // then the basket, then the give-back rule
   ProtectBasket();
   DrawBox();
   PB_Draw();

   // EVERYTHING BELOW RUNS ONLY WHEN A BAR CLOSES.
   // This is what makes a backtest match live. v19.18 recomputed its engine on
   // every tick, so its backtest and its live behaviour were different systems.
   datetime bt = iTime(_Symbol, _Period, 0);
   if(bt == g_lastBarTime) return;
   g_lastBarTime = bt;

   if(Bars(_Symbol, _Period) < DemaEffLen() * 4 + 10) return;

   UpdateSuperTrend();
   CheckConfigSanity();   // E-102: does this account fit these guards at all?
   BuildLevels();          // before anything asks where the levels are
   ExpireStalePendings();  // a limit is only good while its setup is
   ManagePosition();
   TryEntry();
}
//+------------------------------------------------------------------+

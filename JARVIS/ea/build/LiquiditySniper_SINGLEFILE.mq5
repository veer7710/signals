//+------------------------------------------------------------------+
//|  LIQUIDITY SNIPER                                                |
//|  The liquidity sweep strategy, as MEASURED - not as imagined.    |
//+------------------------------------------------------------------+
//
//  WHAT THIS TRADES, AND WHY EVERY NUMBER IN IT IS THE NUMBER IT IS
//
//  Veer trades this by hand and reports an 80% win rate. The first research
//  build of these rules measured 31.6% and it was WRONG - it fired twelve
//  times in 4501 bars, so nothing it reported was a measurement of anything.
//  E-068 found three errors, each with a price tag, and this EA is what is
//  left after they are corrected:
//
//   1. A ZONE IS ONE CONFIRMED PIVOT, not three clustered.
//      Requiring three inside a +/-ATR/6.9 band fires 2.7 times per 1000 bars.
//      One pivot fires 39.3 times. Veer sent two LuxAlgo scripts - "Liquidity
//      Sweeps" (a single swing point IS liquidity) and "Buyside & Sellside
//      Liquidity" (clustered) - and the research build ANDed them, keeping the
//      strictest reading of each.
//
//   2. THE ORDER RESTS INSIDE THE ZONE AND THE SWEEP FILLS IT.
//      Veer: "we need to have top tick entrys meaning we do a small stop loss
//      which is reasonable and catch a massiveeee entry from the tick".
//
//      Both entries I had measured before this enter AFTER the sweep is over -
//      at the sweep bar's close, or back at the zone edge later. Neither is
//      that trade. A professional does not wait: the zone is WHERE THE STOPS
//      ARE, the sweep is the market reaching in to take them, so the limit
//      rests inside the zone BEFORE the sweep and is filled BY it. The stop
//      then sits just past the poke - small - and the whole reversal is the
//      target.
//
//      It also fills on every BREAK, not only every sweep, and that is the
//      honest cost. A break is a full-size loss. The measurement below is
//      whether a small stop and a 2R target pay for those.
//
//   3. SMALL STOP, BIG TARGET. Risk 1 to make 2.
//      0.60 ATR of risk, 2R of target. NOT the 1.5-ATR-stop / 0.5-ATR-target
//      shape this EA shipped with yesterday, which wins 87% of the time and
//      makes a third of the money.
//
//  E-077, the geometry attacked. XAUUSD:
//    GOLD 1h   n=491  47.5% win  +0.378R  PF 1.69  t=+5.58   +2172 points
//              OOS +0.470 / +0.286   walk-forward 6 of 6 blocks
//              +4.7 sd clear of 30 random-entry control seeds    PROMISING
//    GOLD 15m  n=158  48.1% win  +0.382R  PF 1.69  t=+3.20    +301 points
//              OOS +0.498 / +0.265   walk-forward 4 of 6       PROMISING
//
//  And it is a PLATEAU, not a cell. Every combination from a 0.45-0.90 ATR
//  stop and a 1.5R-2.5R target is positive on GOLD 1h. The best of them is
//  0.75 ATR / 1.5R at +3183 points; the shipped default sits in the interior
//  because an edge-of-grid optimum is usually a fit.
//
//  PROMISING is the strongest word the directive allows for something that has
//  survived. It does not mean profitable and this EA does not claim to be.
//
//  WHAT YOU MUST KNOW BEFORE RUNNING IT
//   * XAUUSD. FX is rejected outright on these rules.
//   * HALF THE TRADES LOSE. 47.5% win rate. The money is in 2R being twice
//     as big as 1R, not in being right often. A run of five losses is normal
//     and the Monte Carlo says the drawdown to expect is about 12R, with 18R
//     at the 95th percentile. If that would make you turn it off, turn it off
//     now instead.
//   * THIS SHAPE CARES ABOUT THE SPREAD, unlike the one it replaces. Measured
//     on GOLD 1h: +0.492R at zero spread, +0.378R at the 0.46 off Veer's
//     terminal, +0.279R at 1.00. A small stop cannot absorb a wide spread, so
//     news-time spreads are a real cost, not a rounding error.
//   * IT WAS MEASURED ON 15m AND 1h BARS. There is no M1 or M5 data in the
//     repository. Running it on M1 is an extrapolation, and the honest way to
//     end that is to run ExportHistory.mq5 and re-measure.
//
#property copyright "JARVIS"
#property version   "3.40"
#property strict

#define LQS_BUILD "3.40"

#include <Trade/Trade.mqh>

// The shared profit box: points first, money second (E-074), split between the
// two things a level trade is made of - the fill the resting limit bought, and
// what the trade did afterwards.
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

//==================== INPUTS =======================================
input group "=== SAFETY ==="
input bool   InpDemoOnly      = true;   // refuse to start on a live account
input long   InpMagic         = 770069; // magic number
input bool   InpShowProfitBox = true;   // the on-chart points/money ledger box
input int    InpBoxCorner     = 3;      // 0 top-left, 1 top-right, 2 bottom-left, 3 bottom-right
input int    InpBoxX          = 12;     // pixels in from that corner
input int    InpBoxY          = 12;
// The highest chart this EA will start on. M30 by default because that is
// where every number it is quoted at was measured - raise it deliberately.
input ENUM_TIMEFRAMES InpMaxTF = PERIOD_M30;
input long   InpTrackMagic2  = 880041;  // ZoneSniper, if you run it too
input string InpTrackLabel2  = "ZONE  st+liq";
input long   InpTrackMagic3  = 770001;  // SuperTrendSniper
input string InpTrackLabel3  = "SUPERTREND";

input group "=== ZONES  (LuxAlgo: Liquidity Sweeps) ==="
input int    InpPivLen        = 7;      // pivot length
input double InpMarDiv        = 6.9;    // zone half-width = ATR / this
input int    InpMinPivots     = 1;      // pivots needed to make a zone
input int    InpZoneLife      = 600;    // forget a zone after N bars
input int    InpMaxZones      = 40;     // zones tracked each side

input group "=== THE TRADE  (E-077 - do not tune without re-measuring) ==="
input double InpEntryPast     = 0.25;   // limit sits this many ATR PAST the zone's far edge
input double InpStopAtr       = 0.60;   // stop, ATR beyond the FILL. Small, on purpose.
// ...BUT NEVER SO SMALL THAT THE SPREAD OWNS IT. E-089: this strategy's edge
// holds at a cost/stop of 0.07 (+0.249R) and is gone by 0.22 (+0.041R). A 0.60
// ATR stop is 5 points on 15m gold and about 1.3 on M1 - the same setting, a
// four-fold difference in what the spread costs. So the stop is floored at a
// number of round trips, and the EA WIDENS it to meet that floor rather than
// refusing the trade. A tighter spread then buys a tighter stop automatically.
input double InpMinStopCostX  = 7.0;    // ...but at least this many round trips
input double InpTargetR       = 2.0;    // fallback target if no level is found
// E-106 / E-107 — THE FIXED TARGET IS THE CEILING ON EVERY TRADE THIS EA TAKES.
//
// Veer: "they miss clear clear moves that could've made us 40-200 pounds".
// The first half is true (this stack catches 16.3% of 40-point moves on GOLD
// 1h). The second half is arithmetic, and it is not about the entry at all:
//
//    0.60 ATR stop = 7.4 pts  |  2R target = 14.8 pts
//    at 0.01 lots (E-081, GBP 0.787/pt) A WIN IS GBP 11.64. That is the ceiling.
//    GBP 40 needs 51 points captured. GBP 200 needs 254.
//
// EVEN AT A 100% CATCH RATE THIS GEOMETRY CANNOT PAY HIM GBP 40.
//
// And the cause is our own unapplied finding. E-090 killed the fixed target on
// SuperTrendSniper (InpTargetR = 0) and it was never carried here. Same entries,
// exit swapped for an uncapped run with a give-back stop:
//
//                          n     mean R    points   avg win   wins>GBP40
//    fixed 2R (ships)    517     +0.414    2078.7   GBP13.48       7
//    uncapped+giveback   534     +0.991    4697.5   GBP14.20      19
//    GOLD 15m: +0.441R -> +1.212R  |  US500 1h: +0.334R -> +0.898R
//
// It survived walk-forward 6/6, OOS halves +1.004/+0.975, a long/short split
// (SHORTS score better than longs, so it is not the gold uptrend), independent
// confirmation on US500, and a random-ENTRY control - random entries with this
// exact exit score only +0.086R against the real entries' +0.991R, so the
// entries carry 91% of it and the exit is not manufacturing the number.
//
// IT IS OFF BY DEFAULT ANYWAY. A mean of +0.99R per trade is roughly double
// anything in this project's history, and a result that good is usually wrong.
// What has happened so far is that it has not been broken - which is not the
// same as it being right. A look-ahead audit of the entry generator is
// outstanding, and every test above would inherit such a bug. Turn this on for
// DEMO first, and only after that audit comes back clean.
//
// ===================== CORRECTED, E-110 =====================
// Everything above this line was measured with a broken fill convention and the
// numbers in it are WRONG. A resting limit filled because a bar's ADVERSE
// extreme reached it was then credited with that SAME bar's FAVOURABLE extreme
// as profit. On GOLD 1h, 497 of 534 trades (93.1%) opened AND closed on their
// entry bar and produced 99.0% of the reported profit, while only 7 (1.3%)
// actually gapped through the limit. A random limit entry with no logic in it
// scored +0.236R under that convention - the bug alone beat the real strategy.
//
// Corrected, and re-checked against a control matched on the FILL CONVENTION
// (every previous control entered at the OPEN, which is why six attacks passed):
//
//   GOLD 1h, 2R target, arm_life 60 - AS THIS EA SHIPPED   -0.093R   -331 pts
//   + uncapped exit and give-back                          +0.123R   +619 pts
//   + arm_life 600                                         +0.205R  +1172 pts
//   + US500 as a second book (1224 trades, R/DD 10.2)      +0.237R  +1316 pts
//
//   random limit, same convention, 12 seeds:               +0.047R
//   edge of the real entries:  GOLD +0.158R (13.1 se) | US500 +0.221R (13.2 se)
//
// SO THE DEFAULT IS NOW TRUE. The capped 2R configuration this EA shipped with
// is MEASURED NEGATIVE - it is not a conservative choice, it is a losing one.
// The uncapped exit is what makes the strategy positive at all. E-090 said this
// about the SuperTrend EA a month ago and it was never carried across.
//
// Still demo-gated by InpDemoOnly, and everything here is GOLD/US500 1h. There
// is no M1 data in this repository and none of it speaks to M1.
input bool   InpUncappedExit  = true;   // E-110: capped is measured NEGATIVE
input double InpGiveBackArmR  = 1.0;    // arm the give-back at this peak R
input double InpGiveBackFrac  = 0.20;   // hand back at most this share of peak
// ── TARGET THE NEXT LEVEL (E-087) ────────────────────────────────────────────
// Veer: "provide a real tp and sl based of levels ... you can see price
// reacting and also playing ping pong with levels we need to catch it alllll".
//
// Measured on the identical top-tick entries, GOLD:
//     target 2R          1h  43% win  +0.25R  +2714 points
//     target NEXT LEVEL  1h  31% win  +0.26R  +2382 points
//     target 2R          15m 46% win  +0.31R   +536 points
//     target NEXT LEVEL  15m 33% win  +0.30R   +563 points
//
// Statistically the same money, structurally the thing he asked for, and a
// completely different SHAPE: the level target wins less often and wins far
// bigger - median distance 1.89 ATR, average WIN +3.21R against +1.9R. That is
// the "banger" profile, and it is why this ships on by default.
//
// THE STOP STAYS AT 0.60 ATR AND THAT IS NOT AN OVERSIGHT. A stop "just beyond
// the level" was measured too and it is a disaster: -0.36R, a 9-28% win rate.
// Obvious once seen - the ENTRY is at the level, so a stop just past it lands
// on top of the entry, the risk is a rounding error and every wick takes it.
input bool   InpTargetLevel   = true;   // aim at the next opposing level
input double InpTgtMinAtr     = 0.50;   // ignore levels nearer than this
input double InpTgtMaxR       = 0.0;    // 0 = uncapped (capping measured worse)
// E-105. 60 was never measured - it was assumed. Of every 40-point move this
// stack MISSED on GOLD 1h, 24.7% had a zone that was still LIVE and had simply
// aged past this number. Raising it to the zone's own life (InpZoneLife = 600)
// removes the constraint rather than tuning it, and points improve monotonically
// in 14 of 15 FRAC x timeframe cells:
//    GOLD 1h  base n=517 +0.414R t=+6.28 +2079 pts  ->  n=600 +0.487R t=+7.95 +2743
//             the ADDED trades score +0.645R, better than the base, so E-074 is
//             satisfied: it is not buying trades by lowering their quality.
//             OOS +0.526/+0.448, walk-forward 6/6, 20-seed control +2.5 sd.
//    GOLD 15m n=199 +0.510R +565 pts; the added trades score +0.697R; 6/6; +3.4 sd.
input int    InpArmLife       = 600;    // a zone stops being armable this many bars after birth
input int    InpArmWait       = 60;     // an unfilled limit is cancelled after this many bars
input bool   InpArmOncePerLvl = true;   // never re-arm a level that has actually TRADED
input double InpEntryLots     = 0.02;   // size for one entry
input int    InpMaxPositions  = 1;      // one at a time, as measured

input group "=== THE DISASTER BRAKE  (E-091) ==="
// The stop here is small in ATR terms but floored at 7 round trips, so on M1
// it is not small in money. Same reasoning as the SuperTrend EA: a stop that
// cannot be tightened without the spread owning it needs something faster
// behind it for the case a stop cannot handle at all - a news gap.
// E-091 measured every tighter brake as a net LOSS: the trades they cut
// recover. This one fires on about 6% of trades and its cost is inside the
// noise. It is insurance priced at zero, not a trading rule.
input bool   InpUseBrake      = true;   // emergency close on a violent move against us
input double InpBrakeAtr      = 1.8;    // ...this many ATR against us...
input int    InpBrakeBars     = 2;      // ...within this many bars
input double InpMaxSpreadX    = 3.0;    // also close if the spread blows out this much

//==================== FUNDED ACCOUNTS (Block F, P79-P90) ===========
// ONE INPUT BLOCK RE-SIZES EVERYTHING. Pick the firm and set the account size;
// every limit below is derived. Nothing else needs touching to move this EA
// from a 10k challenge to a 200k funded account at a different firm.
//
// WHAT THE MEASUREMENT SAYS (E-093, JARVIS/research/funded.py, 2000 attempts
// per cell, bootstrapped from the EA's own trade distribution):
//
//   THE CONSISTENCY RULE IS THE LARGEST SINGLE OBSTACLE. Larger than the daily
//   loss limit and the max drawdown put together. Holding everything else
//   fixed and switching only that rule on:
//        FundingPips   92.1% -> 29.7%   (-62.4 points)
//        E8 performance 92.7% -> 23.1%   (-69.7 points)
//        Alpha One      78.7% -> 60.2%   (-18.4 points)
//        FTMO, FundedNext, E8 Classic, The5ers:  no such rule, no cost.
//
//   YOU CANNOT SIZE YOUR WAY OUT OF IT. best-day / total-profit is a RATIO, so
//   it is scale-free. Measured on one path at E8 performance: 0.25% risk gave a
//   52.0% ratio, 0.50% gave 78.4%, 1.00% gave 90.8%. Cutting risk made it
//   WORSE, because the smaller account takes longer and banks its profit in
//   fewer, larger relative days.
//
//   FREQUENCY IS WHAT DISSOLVES IT, and Veer has been right to demand it. With
//   the daily risk budget held constant and only the trade count changed:
//        2 trades/day   24.0% pass        10 trades/day   99.9%
//        5 trades/day   89.2%             20 trades/day  100.0%
//   But frequency is bought by dropping timeframe, and E-089 says that costs R.
//   At the cost/stop of 0.14 this EA holds (InpMinStopCostX = 7) the frontier
//   is 5/day 57.6%, 10/day 86.2%, 20/day 95.0%, 50/day 98.8% - and 100/day
//   COLLAPSES to 16.5%, because the size per trade gets too small to reach the
//   target before the window closes (662 of 800 attempts simply ran out of
//   days). The target is 10 to 50 trades a day, not as many as possible.
//
//   THE DERIVED DAILY CAP. To pass a best-day rule of X you need
//   best_day <= X * total_profit, and at the moment you pass, total_profit IS
//   the profit target. So the cap is X * target * account. That exact number
//   barely helps, because a lock can only refuse new ENTRIES and a trade
//   already open still runs. HALF of it is what measured well: at 2 trades/day
//   FundingPips went 23.5% -> 37.2% and E8 performance 20.8% -> 41.7%.
//   InpConsistencyLock defaults to 0.50 for that reason.
enum ENUM_FIRM
  {
   FIRM_CUSTOM,            // Custom - use the manual numbers below
   FIRM_FTMO_2STEP,        // FTMO 2-step phase 1 (no consistency rule)
   FIRM_FUNDEDNEXT,        // FundedNext Stellar 2-step (no consistency rule)
   FIRM_FUNDINGPIPS,       // FundingPips 2 Step Pro (35% best day)
   FIRM_E8_CLASSIC,        // E8 Classic challenge (no consistency rule)
   FIRM_E8_PERF,           // E8 performance / funded (40% best day)
   FIRM_ALPHA_ONE,         // Alpha Capital Alpha One (40% best day)
   FIRM_5ERS               // The5ers High Stakes (no consistency rule)
  };

//==================== RUNNING MORE THAN ONE CHART (E-098) ==========
// E-097 found that holding several positions AT ONCE ON ONE SYMBOL does not pay
// risk-adjusted - GOLD 1h fell from 25.4 return-per-drawdown at one slot to 11.2
// at ten - and found why: the extra trades are GOOD (+0.68R against the base's
// +0.36R), they are just the same trade twice, so they lose together.
//
// E-098 then removed the correlation and kept the frequency, by running the SAME
// strategy on legs that do not move together. Daily-return correlations measured
// on this stack:  GOLD 1h vs GOLD 15m  -0.01 |  GOLD 1h vs US500 1h  +0.03 |
// GOLD 15m vs US500 1h  -0.07.  Essentially independent.
//
//   book                              trades  total R  maxDD R   R/DD   /day
//   GOLD 1h alone                        517  +214.15     8.42  25.45   1.25
//   + GOLD 15m                           687  +144.58     5.07  28.53   1.59
//   + US500 1h                          1045  +192.50     5.38  35.79   1.89
//   GOLD 1h + US500 1h + GOLD 15m       1215  +153.33     3.98  38.54   2.17
//
// 51% better return per unit of drawdown, 74% more trades, and LESS THAN HALF
// the drawdown - with no new edge, no lower timeframe and no extra risk. It is
// the frequency lever E-093 identified, bought without paying E-089's cost.
//
// US500 stands on its own, it is not a passenger: n=528, +0.324R, t=4.96,
// walk-forward 6 of 6 positive and IMPROVING (+0.213 to +0.486 across blocks),
// and +0.709R over a 16-seed matched random control = 6.9 control standard
// errors. That is a stronger control result than GOLD's own 6.4.
// US500 15m is EXCLUDED - it fails standalone (t=0.86) and drags the book from
// 38.54 to 31.11. Legs are screened on their own merit, not on what they do to
// the portfolio.
//
// HOW TO RUN IT: attach one instance per leg, set InpBooks to the number of
// legs, and give every instance a DIFFERENT InpMagic. Size is divided by
// InpBooks so the total risk is unchanged, and the funded guards below share
// one account-wide state so three instances cannot each spend the full daily
// allowance.
//
// AGAINST THE MANDATE, AND SAID SO. D-010 settles XAUUSD only, M1/M5/M15, with
// H1 as context that is never traded. This result is mostly H1 and one leg is
// an index. It is brought as evidence, not slipped in: the defaults below are
// unchanged and single-leg. Overruling D-010 is Veer's call, not this file's.
input group "=== MULTI-BOOK (E-098) ==="
input int    InpBooks         = 1;      // how many charts this EA runs on
input bool   InpSharedGuards  = true;   // pool the funded guards across them

input group "=== FUNDED ACCOUNT (set these two, the rest derives) ==="
input ENUM_FIRM InpFirm       = FIRM_FTMO_2STEP; // firm rule set
input double InpAccountSize   = 0.0;    // 0 = read the balance from the account
input double InpSafetyBuffer  = 0.80;   // act at this fraction of every limit
input double InpConsistencyLock = 0.50; // day cap, as a fraction of the derived one
input bool   InpStopWhenPassed= true;   // stop trading once the target is met

input group "=== RISK (used when InpFirm = FIRM_CUSTOM) ==="
input double InpMaxDayLossPct = 3.0;    // stop for the day after this drawdown
input double InpMaxDDPct      = 10.0;   // stop permanently after this drawdown
input int    InpMaxTradesDay  = 60;     // hard cap on entries per day
input double InpProfitTgtPct  = 10.0;   // the challenge profit target
input double InpConsistPct    = 0.0;    // best-day cap. 0 = the firm has none
input int    InpResetHourUTC  = 0;      // the firm's daily reset clock, UTC
input bool   InpTrailingDD    = false;  // does the drawdown floor follow the peak

input group "=== READOUT ==="
input bool   InpComment       = true;   // the chart readout
input bool   InpVerboseLog    = true;   // log every decision

//==================== STATE ========================================
struct Zone
{
   double px;        // centre
   double top;
   double bot;
   int    born;      // bar index when it was confirmed
   int    dir;       // +1 buyside (above), -1 sellside (below)
   bool   broken;    // a CLOSE went through it - the zone is dead
};

Zone   g_zB[];       // buyside zones
Zone   g_zS[];       // sellside zones


int      g_atrHandle = INVALID_HANDLE;
datetime g_lastBar   = 0;
double   g_pivH[];         // recent confirmed pivot highs
double   g_pivL[];

// accounting
double   g_dayStartEq = 0.0;
double   g_peakEq     = 0.0;

// ---- funded-account state, all derived in ApplyFirmPreset()
double   g_fBalance   = 0.0;   // the account size every limit is a % of
double   g_fDayLoss   = 0.0;   // daily loss limit, fraction
double   g_fMaxDD     = 0.0;   // max drawdown, fraction
double   g_fTarget    = 0.0;   // profit target, fraction
double   g_fConsist   = 0.0;   // best-day cap, fraction. 0 = none
bool     g_fTrailing  = false;
int      g_fResetHour = 0;
int      g_fMinDays   = 0;
double   g_fFloor     = 0.0;   // the ACTUAL equity floor, in money
double   g_fDayCap    = 0.0;   // stop entering for the day above this profit
double   g_dayProfit  = 0.0;   // today'"'"'s REALISED profit, in money
bool     g_lockedProf = false; // locked because today has gone well enough
bool     g_passed     = false;
int      g_daysTraded = 0;
string   g_firmName   = "";
int      g_dayStamp   = 0;
int      g_tradesToday = 0;
bool     g_lockedDay  = false;
bool     g_lockedPerm = false;
int      g_nTrades    = 0;
int      g_nWins      = 0;
double   g_realized   = 0.0;
double   g_dayRealized = 0.0;
long     g_readN      = 0;
double   g_spSum     = 0.0;
int      g_spN       = 0;
double   g_spMax     = 0.0;

//==================== FORWARD ======================================
void   Log(string m);
string Money(double v);
double ATRv(int shift);
int    DayStamp();
int    FundedDayStamp();
string FundedKey();
double BookLots();
void   ApplyFirmPreset();
void   FundedSave();
void   FundedLoad();
void   Readout();
void   BuildZones();
double EntryLevel(const Zone &z, double a);
void   PushGap(Gap &G[], double top, double bot, int dir, int bar);
void   AgeGaps(Gap &G[], int bar, double c);
void   BuildSmc();
double BestLevel(int dir, double px, double a, string &src);
double NextLevel(int dir, double px, double a);
bool   LevelUsed(double lvl);
void   MarkUsed(double lvl);
int    NearestZone(const Zone &Z[], int bar, double px, bool above);
void   ArmSide(int dir);
void   KillSide(int dir, string why);
void   KillAll(string why);
void   ManageOrders();
bool   HavePosition();
void   AddZone(Zone &Z[], double &piv[], double at, int dir, double mar, int bar);
void   ExpireZones(Zone &Z[], int bar);
void   MarkBroken(Zone &Z[], double c);
void   DisasterBrake();
void   TrailGiveBack();
int    TrackFind(ulong tk);
void   TrackAdd(ulong tk, double risk);
void   TrackPrune();
double MinStopDist();
int    PosCount();

//==================== HELPERS ======================================
void Log(string m)
{
   if(InpVerboseLog) Print(m);
}

string Money(double v)
{
   return StringFormat("%s%.2f", (v < 0 ? "-" : ""),
                       MathAbs(NormalizeDouble(v, 2)));
}

double ATRv(int shift)
{
   double b[];
   if(CopyBuffer(g_atrHandle, 0, shift, 1, b) != 1) return 0.0;
   return b[0];
}

int DayStamp()
{
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   return t.year * 10000 + t.mon * 100 + t.day;
}

// The broker will not accept a stop closer than this to the market. Ignoring
// it is how an EA ends up sending orders that are silently rejected all day.
double MinStopDist()
{
   long   lvl = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double pt  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(lvl <= 0 || pt <= 0.0) return 0.0;
   return (double)lvl * pt;
}

int PosCount()
{
   int c = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      c++;
   }
   return c;
}

bool HavePosition() { return PosCount() > 0; }

//==================== ZONES ========================================
// A pivot at bar i is only KNOWN at bar i+InpPivLen. Every use below respects
// that; the whole strategy is worthless if it does not.
void BuildZones()
{
   int n = Bars(_Symbol, _Period);
   int p = InpPivLen;
   if(n < p * 2 + 8) return;

   // The candidate pivot sits at shift p+1, confirmed by the p bars closed on
   // either side of it. NOT shift p: that window reaches shift 0, which is the
   // bar still forming. Reading it would let a pivot be confirmed or denied by
   // a high that has not happened yet, and the whole strategy is worthless if
   // any part of it can see the current bar.
   int b = p + 1;
   double h = iHigh(_Symbol, _Period, b);
   double l = iLow(_Symbol, _Period, b);
   bool isH = true, isL = true;
   for(int k = 1; k <= p; k++)
   {
      if(iHigh(_Symbol, _Period, b - k) > h || iHigh(_Symbol, _Period, b + k) > h) isH = false;
      if(iLow(_Symbol, _Period, b - k)  < l || iLow(_Symbol, _Period, b + k)  < l) isL = false;
   }

   double a = ATRv(1);
   if(a <= 0.0) return;
   double mar = a / InpMarDiv;
   int bar = Bars(_Symbol, _Period) - 1;

   if(isH) AddZone(g_zB, g_pivH, h, 1, mar, bar);
   if(isL) AddZone(g_zS, g_pivL, l, -1, mar, bar);

   // A zone price has CLOSED beyond is DEAD - that is a break, not a sweep,
   // and there is no trade left at it. The old sweep scanner used to set this
   // flag; it was removed with the sweep logic, so for one build nothing did,
   // and orders would have gone on resting at levels the market had left
   // behind. Zones are now killed here, on every bar close, unconditionally.
   MarkBroken(g_zB, iClose(_Symbol, _Period, 1));
   MarkBroken(g_zS, iClose(_Symbol, _Period, 1));

   ExpireZones(g_zB, bar);
   ExpireZones(g_zS, bar);
}

void MarkBroken(Zone &Z[], double c)
{
   for(int i = 0; i < ArraySize(Z); i++)
   {
      if(Z[i].broken) continue;
      if((Z[i].dir == 1 && c > Z[i].top) || (Z[i].dir == -1 && c < Z[i].bot))
         Z[i].broken = true;
   }
}

void AddZone(Zone &Z[], double &piv[], double at, int dir, double mar, int bar)
{
   // remember the pivot, and count how many recent ones cluster with it
   int np = ArraySize(piv);
   ArrayResize(piv, np + 1);
   piv[np] = at;
   if(ArraySize(piv) > 50)
   {
      for(int i = 0; i < ArraySize(piv) - 1; i++) piv[i] = piv[i + 1];
      ArrayResize(piv, 50);
   }
   int cnt = 0;
   for(int i = 0; i < ArraySize(piv); i++)
      if(MathAbs(piv[i] - at) <= mar) cnt++;
   if(cnt < InpMinPivots) return;

   // merge into an existing live zone rather than stacking duplicates
   for(int i = 0; i < ArraySize(Z); i++)
      if(!Z[i].broken && MathAbs(Z[i].px - at) <= mar)
      {
         Z[i].top = MathMax(Z[i].top, at + mar);
         Z[i].bot = MathMin(Z[i].bot, at - mar);
         return;
      }

   int nz = ArraySize(Z);
   ArrayResize(Z, nz + 1);
   Z[nz].px = at;  Z[nz].top = at + mar;  Z[nz].bot = at - mar;
   Z[nz].born = bar;  Z[nz].dir = dir;  Z[nz].broken = false;

   if(ArraySize(Z) > InpMaxZones)
   {
      for(int i = 0; i < ArraySize(Z) - 1; i++) Z[i] = Z[i + 1];
      ArrayResize(Z, InpMaxZones);
   }
}

void ExpireZones(Zone &Z[], int bar)
{
   int w = 0;
   for(int i = 0; i < ArraySize(Z); i++)
   {
      if(bar - Z[i].born > InpZoneLife) continue;
      if(Z[i].broken) continue;
      if(w != i) Z[w] = Z[i];
      w++;
   }
   ArrayResize(Z, w);
}

//==================== SMC: FVG AND ORDER BLOCKS ====================
// E-079 built six SMC concepts and measured every one of them against the
// entry that already works. Three pay and three do not, and the three that do
// not are in this comment rather than in the code:
//
//   FAIR VALUE GAP     IN.  As a trigger on its own, GOLD 1h: 34 trades,
//                      67.6% win, +0.998R, +466 points. The strongest single
//                      signal in the project.
//   ORDER BLOCK        IN.  58 trades, 53.4% win, +0.559R, +338 points.
//   INVERSE FVG        OUT. 1136 trades and MINUS 39 points. It fires
//                      constantly and dilutes everything it is added to:
//                      the full stack drops from +0.487R to +0.119R with it.
//   BOS / CHoCH        OUT. As triggers, -0.028R to +0.030R - inside noise.
//   STRUCTURE BIAS     OUT, and this one is the interesting refusal. As a
//                      filter it RAISES expectancy from +0.487R to +0.638R -
//                      and cuts the trade count from 515 to 205 and the money
//                      from +2792 points to +1403. That is exactly the trap
//                      E-074 caught in the SuperTrend EA: the best per-trade
//                      number and the least money. Veer is paid in points.
//
// Together with the zone entry: n=515, 51.1% win, +0.487R, PF 1.95, t=+7.37,
// +2792 points, walk-forward 6 of 6, +5.0 sd clear of 30 control seeds, and a
// Monte Carlo drawdown of 9.8R median. Against the zone entry alone (480
// trades, +0.385R, +2110 points) it is MORE trades, higher expectancy and 32%
// more money - better on every axis, which is rare enough to be suspicious of,
// so it was checked out of sample (+0.598 / +0.377) and block by block.

struct Gap
{
   double top;
   double bot;
   int    born;
   int    dir;        // +1 bullish (support), -1 bearish (resistance)
   bool   dead;
};

Gap g_fvg[];
Gap g_ob[];

input group "=== SMC  (E-079: these two pay, iFVG/BOS/CHoCH do not) ==="
input bool   InpUseFvg        = true;   // rest orders at fair value gaps
input bool   InpUseOB         = true;   // rest orders at order blocks
input double InpDispAtr       = 1.0;    // a displacement bar's BODY, in ATR
input double InpMinGapAtr     = 0.10;   // ignore gaps smaller than this
input int    InpSmcLife       = 200;    // bars an FVG or block stays live

void PushGap(Gap &G[], double top, double bot, int dir, int bar)
{
   int n = ArraySize(G);
   ArrayResize(G, n + 1);
   G[n].top = top;  G[n].bot = bot;  G[n].dir = dir;
   G[n].born = bar; G[n].dead = false;
   if(ArraySize(G) > 60)
   {
      for(int i = 0; i < ArraySize(G) - 1; i++) G[i] = G[i + 1];
      ArrayResize(G, 60);
   }
}

void AgeGaps(Gap &G[], int bar, double c)
{
   int w = 0;
   for(int i = 0; i < ArraySize(G); i++)
   {
      if(bar - G[i].born > InpSmcLife) continue;
      // a close through it the wrong way kills it. For an FVG that is the
      // INVERSION, which E-079 measured as worth nothing - so it is killed
      // here rather than traded the other way.
      if((G[i].dir == 1 && c < G[i].bot) || (G[i].dir == -1 && c > G[i].top))
         continue;
      if(w != i) G[w] = G[i];
      w++;
   }
   ArrayResize(G, w);
}

// Runs on the CLOSED bar. An FVG needs bars 1, 2 and 3 back, all closed.
void BuildSmc()
{
   int bar = Bars(_Symbol, _Period) - 1;
   double a = ATRv(1);
   if(a <= 0.0) return;
   double c1 = iClose(_Symbol, _Period, 1);

   AgeGaps(g_fvg, bar, c1);
   AgeGaps(g_ob,  bar, c1);

   if(InpUseFvg)
   {
      double h3 = iHigh(_Symbol, _Period, 3), l3 = iLow(_Symbol, _Period, 3);
      double h1 = iHigh(_Symbol, _Period, 1), l1 = iLow(_Symbol, _Period, 1);
      if(h3 < l1 && (l1 - h3) >= InpMinGapAtr * a) PushGap(g_fvg, l1, h3,  1, bar);
      if(l3 > h1 && (l3 - h1) >= InpMinGapAtr * a) PushGap(g_fvg, l3, h1, -1, bar);
   }

   if(InpUseOB)
   {
      double o1 = iOpen(_Symbol, _Period, 1);
      double body = c1 - o1;
      if(MathAbs(body) >= InpDispAtr * a)
      {
         int d = (body > 0) ? 1 : -1;
         // the last OPPOSITE-colour candle before the displacement leg
         for(int k = 2; k < 9; k++)
         {
            double ok = iOpen(_Symbol, _Period, k), ck = iClose(_Symbol, _Period, k);
            bool opp = (d > 0) ? (ck < ok) : (ck > ok);
            if(opp)
            {
               PushGap(g_ob, MathMax(ok, ck), MathMin(ok, ck), d, bar);
               break;
            }
         }
      }
   }
}

// The nearest tradeable level on one side, from ANY source. dir +1 wants a
// level BELOW price to buy at, dir -1 a level above to sell at.
double BestLevel(int dir, double px, double a, string &src)
{
   double best = 0.0;
   bool   have = false;
   src = "";

   int bar = Bars(_Symbol, _Period) - 1;
   int idx = (dir > 0) ? NearestZone(g_zS, bar, px, false)
                       : NearestZone(g_zB, bar, px, true);
   if(idx >= 0)
   {
      Zone z = (dir > 0) ? g_zS[idx] : g_zB[idx];
      double lvl = EntryLevel(z, a);
      if((dir > 0 && lvl < px) || (dir < 0 && lvl > px))
      { best = lvl; have = true; src = "zone"; }
   }

   for(int pass = 0; pass < 2; pass++)
   {
      if(pass == 0 && !InpUseFvg) continue;
      if(pass == 1 && !InpUseOB)  continue;
      int cnt = (pass == 0) ? ArraySize(g_fvg) : ArraySize(g_ob);
      for(int i = 0; i < cnt; i++)
      {
         Gap g = (pass == 0) ? g_fvg[i] : g_ob[i];
         if(g.dir != dir) continue;
         double mid = (g.top + g.bot) / 2.0;
         if(dir > 0 && mid >= px) continue;
         if(dir < 0 && mid <= px) continue;
         if(!have || MathAbs(mid - px) < MathAbs(best - px))
         {
            best = mid; have = true;
            src = (pass == 0) ? "fvg" : "ob";
         }
      }
   }
   return have ? best : 0.0;
}

// The nearest level IN THE TRADE'S FAVOUR that is far enough away to be worth
// aiming at. This is the take-profit: where the ping-pong is going.
double NextLevel(int dir, double px, double a)
{
   double best = 0.0;
   bool   have = false;
   double minD = InpTgtMinAtr * a;

   for(int i = 0; i < ArraySize(g_zB); i++)
   {
      if(g_zB[i].broken) continue;
      double L = g_zB[i].px;
      if((L - px) * dir < minD) continue;
      if(!have || (L - px) * dir < (best - px) * dir) { best = L; have = true; }
   }
   for(int i = 0; i < ArraySize(g_zS); i++)
   {
      if(g_zS[i].broken) continue;
      double L = g_zS[i].px;
      if((L - px) * dir < minD) continue;
      if(!have || (L - px) * dir < (best - px) * dir) { best = L; have = true; }
   }
   for(int pass = 0; pass < 2; pass++)
   {
      int cnt = (pass == 0) ? ArraySize(g_fvg) : ArraySize(g_ob);
      for(int i = 0; i < cnt; i++)
      {
         Gap g = (pass == 0) ? g_fvg[i] : g_ob[i];
         double L = (g.top + g.bot) / 2.0;
         if((L - px) * dir < minD) continue;
         if(!have || (L - px) * dir < (best - px) * dir) { best = L; have = true; }
      }
   }
   return have ? best : 0.0;
}

//==================== THE RESTING ORDERS ===========================
// The whole strategy, in one idea: a limit sits INSIDE the nearest live zone
// on each side, and the sweep fills it. Nothing waits for confirmation, because
// E-076 measured what waiting costs - by the time the sweep bar has closed, the
// wick is far away and the risk is no longer small.
//
// Two orders can rest at once, one each side, which is what a desk actually
// does. The first to fill cancels the other: InpMaxPositions is 1 and the
// measurement counted one trade at a time.
//
// These are REAL broker-side pending orders. That matters more here than
// anywhere else: the fill IS the edge, and a limit simulated inside OnTick only
// fills if a tick happens to arrive while price is through the level. On a fast
// sweep wick - which is precisely the bar this strategy exists to catch - that
// tick may never come, so the EA would miss the fills the backtest counted and
// keep the slow ones it did not.

ulong    g_tkBuy  = 0;      // resting BUY limit  (at a sellside zone, below)
ulong    g_tkSell = 0;      // resting SELL limit (at a buyside zone, above)
double   g_lvlBuy = 0.0;
double   g_lvlSell = 0.0;
int      g_barBuy = -1;     // bar the buy limit was placed on
int      g_barSell = -1;
double   g_used[];          // levels already traded or expired - never re-armed

// Where the order sits: past the far edge of the zone, into the liquidity.
double EntryLevel(const Zone &z, double a)
{
   // buyside zone (above): we SELL, so the far edge is its top
   if(z.dir == 1) return z.top + InpEntryPast * a;
   return z.bot - InpEntryPast * a;
}

// The nearest live zone on one side that is still young enough to trade.
int NearestZone(const Zone &Z[], int bar, double px, bool above)
{
   int best = -1;
   double bd = 0.0;
   for(int i = 0; i < ArraySize(Z); i++)
   {
      if(Z[i].broken) continue;
      if(bar - Z[i].born > InpArmLife) continue;
      double lvl = (Z[i].dir == 1) ? Z[i].top : Z[i].bot;
      if(above && lvl <= px) continue;
      if(!above && lvl >= px) continue;
      double d = MathAbs(lvl - px);
      if(best < 0 || d < bd) { best = i; bd = d; }
   }
   return best;
}

// LEAVE A RESTING ORDER ALONE, AND ONLY SPEND A LEVEL THAT TRADED.
// This is what P91 forced, and the road to it is worth recording because two
// plausible fixes were wrong before the third was right.
//
// Build 3.00 re-pointed both limits to the nearest level on EVERY bar close.
// The parity harness put that beside what E-080 actually measured. GOLD 1h:
//
//                        trades   win%   expectancy   points   95th drawdown
//   E-080, as measured      515  51.1%     +0.487R    +2792    14.6R = GBP99
//   build 3.00 in fact     1519  41.5%     +0.201R    +2884    32.9R = GBP223
//
// Marginally more money for MORE THAN DOUBLE THE DRAWDOWN. On a 40-pound
// account that is not a preference, it is the account. Chasing the nearest
// level meant order blocks - which form close to price constantly - supplied
// 1025 of 1519 trades against 62 in the measurement.
//
// Two fixes were tried and measured before this one:
//   preferring the zone source over FVG and order blocks    +0.167R  WORSE
//   expiring the order faster (wait 1, 2, 3, 5 bars)        flat, no effect
// Both were reasonable guesses and both were wrong, which is the reason to
// measure rather than reason.
//
// What actually mattered: build 3.01 blacklisted a level as soon as an order
// was PLACED there, even if that order expired untouched. An untouched order
// has not spent anything - the level is exactly as valid as before. Marking it
// only on a real fill, with a 60-bar rest, gives +0.249R and +2714 points
// against +0.166R and +2202.
//
// HONEST LIMIT: this EA still does not reproduce +0.487R and cannot. That
// number belongs to a backtest that may hold many candidate orders at once;
// an EA rests two. THE EA'S NUMBER IS +0.249R, and that is the one to quote.
bool LevelUsed(double lvl)
{
   for(int i = 0; i < ArraySize(g_used); i++)
      if(MathAbs(g_used[i] - lvl) < _Point * 2) return true;
   return false;
}

void MarkUsed(double lvl)
{
   int n = ArraySize(g_used);
   ArrayResize(g_used, n + 1);
   g_used[n] = lvl;
   if(ArraySize(g_used) > 400)
   {
      for(int i = 0; i < ArraySize(g_used) - 1; i++) g_used[i] = g_used[i + 1];
      ArrayResize(g_used, 400);
   }
}

void ArmSide(int dir)
{
   if(g_lockedDay || g_lockedPerm || g_lockedProf || g_passed) return;
   if(PosCount() >= InpMaxPositions) return;
   if(g_tradesToday >= InpMaxTradesDay) return;

   // an order already resting and not yet expired is LEFT ALONE
   ulong tkNow = (dir > 0) ? g_tkBuy : g_tkSell;
   int   bAt   = (dir > 0) ? g_barBuy : g_barSell;
   int   barNo = Bars(_Symbol, _Period) - 1;
   if(tkNow != 0 && OrderSelect(tkNow))
   {
      if(barNo - bAt <= InpArmWait) return;
      KillSide(dir, StringFormat("unfilled after %d bars", InpArmWait));
   }

   ulong  tk   = (dir > 0) ? g_tkBuy : g_tkSell;
   double a    = ATRv(1);
   if(a <= 0.0) return;
   int    bar  = Bars(_Symbol, _Period) - 1;
   double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(bid <= 0.0 || ask <= 0.0) return;

   // The nearest level on this side from ANY source - liquidity zone, fair
   // value gap or order block. Nearest, because that is the one price reaches
   // first, and the backtest resolved overlapping signals the same way: first
   // touched wins, one position at a time.
   string src = "";
   double raw = BestLevel(dir, (dir > 0) ? bid : ask, a, src);
   if(raw == 0.0) { KillSide(dir, "no live level on this side"); return; }

   int dg   = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double lvl = NormalizeDouble(raw, dg);

   if(InpArmOncePerLvl && LevelUsed(lvl)) return;

   // already resting at this exact level for this exact zone: leave it alone.
   // Re-sending it every bar would churn the order book and reset its age.
   KillSide(dir, "");

   double stopDist = InpStopAtr * a;
   if(InpMinStopCostX > 0.0)
   {
      double rt = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                - SymbolInfoDouble(_Symbol, SYMBOL_BID) + 2 * _Point;
      double need = InpMinStopCostX * rt;
      if(stopDist < need)
      {
         Log(StringFormat("stop %.*f is only %.1f round trips - widening to %.*f "
                          "so the spread is not a third of the risk",
                          dg, stopDist, stopDist / MathMax(rt, 1e-9), dg, need));
         stopDist = need;
      }
   }
   double stop = NormalizeDouble(lvl - dir * stopDist, dg);
   double risk = (lvl - stop) * dir;
   if(risk <= 0.0) return;
   // E-106: with the uncapped exit there is no broker TP at all - the trade is
   // closed by the ratcheting give-back stop in ManageOpen(). A TP and an
   // uncapped run are contradictory instructions, so only one may be live.
   double tgt = 0.0;
   if(!InpUncappedExit)
      tgt = NormalizeDouble(lvl + dir * InpTargetR * risk, dg);
   if(InpTargetLevel && !InpUncappedExit)
   {
      double nxt = NextLevel(dir, lvl, a);
      if(nxt != 0.0)
      {
         if(InpTgtMaxR > 0.0)
         {
            double cap = lvl + dir * InpTgtMaxR * risk;
            nxt = (dir > 0) ? MathMin(nxt, cap) : MathMax(nxt, cap);
         }
         tgt = NormalizeDouble(nxt, dg);
      }
      // no level far enough away: the R target above stands
   }

   // the broker's floor. A limit inside the stops level is REJECTED, and a
   // rejected order is a trade silently not taken.
   double md = MinStopDist();
   if(md > 0.0)
   {
      if(MathAbs(lvl - stop) < md) stop = NormalizeDouble(lvl - dir * md, dg);
      if(MathAbs(tgt - lvl)  < md) tgt  = NormalizeDouble(lvl + dir * md, dg);
   }

   // A limit must rest on the far side of the market. If price is already
   // through the level the sweep has happened without us, and chasing it with
   // a market order is the entry E-076 measured at -0.003R.
   if((dir > 0 && ask <= lvl) || (dir < 0 && bid >= lvl))
   {
      Log("not arming: price is already through the level");
      return;
   }

   // E-098: the size is split across the books so that running three legs is a
   // DIVERSIFICATION of the same risk, not three times the risk. Three charts at
   // full size is not the measured result - it is 3x leverage, and it would blow
   // the daily limit the shared guards are there to protect.
   double lots = BookLots();
   bool ok = (dir > 0)
      ? trade.BuyLimit(lots, lvl, _Symbol, stop, tgt,
                       ORDER_TIME_GTC, 0, "LQS toptick")
      : trade.SellLimit(lots, lvl, _Symbol, stop, tgt,
                        ORDER_TIME_GTC, 0, "LQS toptick");
   if(ok)
   {
      if(dir > 0) { g_tkBuy = trade.ResultOrder();  g_lvlBuy = lvl;  g_barBuy = barNo; }
      else        { g_tkSell = trade.ResultOrder(); g_lvlSell = lvl; g_barSell = barNo; }
      // what the market cost at the moment we decided. Everything the resting
      // limit earns against this is the LEVEL's contribution.
      PB_NoteOrder(trade.ResultOrder(),
                   (SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                  + SymbolInfoDouble(_Symbol, SYMBOL_BID)) / 2.0);
      // NOT marked used here. A level is only spent once it has actually
      // TRADED - see OnTradeTransaction. Blacklisting a level because an order
      // rested there and expired untouched throws away a level that is exactly
      // as valid as it was before, and measured 0.166R against 0.249R.
      Log(StringFormat("ARMED %s LIMIT %.2f at %.*f   stop %.*f (%.*f risk)   "
                       "target %.*f   source %s",
                       dir > 0 ? "BUY" : "SELL", lots, dg, lvl,
                       dg, stop, dg, risk, dg, tgt, src));
   }
   else
      Log(StringFormat("ARM REJECTED (%s): %d %s", dir > 0 ? "buy" : "sell",
                       trade.ResultRetcode(), trade.ResultRetcodeDescription()));
}

void KillSide(int dir, string why)
{
   ulong tk = (dir > 0) ? g_tkBuy : g_tkSell;
   if(tk == 0) return;
   if(OrderSelect(tk))
   {
      trade.OrderDelete(tk);
      if(why != "") Log(StringFormat("cancelled the %s limit: %s",
                                     dir > 0 ? "buy" : "sell", why));
   }
   if(dir > 0) { g_tkBuy = 0;  g_lvlBuy = 0.0;  g_barBuy = -1; }
   else        { g_tkSell = 0; g_lvlSell = 0.0; g_barSell = -1; }
}

void KillAll(string why)
{
   KillSide(1, why);
   KillSide(-1, why);
}

// Called on every bar close: re-point the orders at the zones that are still
// alive, and clear any ticket the broker has already disposed of.
void ManageOrders()
{
   if(g_tkBuy  != 0 && !OrderSelect(g_tkBuy))  { g_tkBuy = 0;  g_lvlBuy = 0.0;  g_barBuy = -1; }
   if(g_tkSell != 0 && !OrderSelect(g_tkSell)) { g_tkSell = 0; g_lvlSell = 0.0; g_barSell = -1; }

   if(PosCount() >= InpMaxPositions || g_lockedDay || g_lockedPerm
      || g_lockedProf || g_passed)
   {
      KillAll("a position is open, or trading is locked");
      return;
   }
   ArmSide(1);
   ArmSide(-1);
}

//==================== THE DISASTER BRAKE ===========================
// Every tick. The only thing here that closes a losing trade before its stop.
void DisasterBrake()
{
   if(!InpUseBrake) return;
   if(PosCount() == 0) return;

   double a = ATRv(1);
   if(a <= 0.0) return;

   double spNow = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double spAvg = (g_spN > 20) ? g_spSum / (double)g_spN : 0.0;
   bool   blown = (spAvg > 0.0 && InpMaxSpreadX > 0.0
                   && spNow > InpMaxSpreadX * spAvg);

   int    look = MathMax(InpBrakeBars, 1);
   double was  = iClose(_Symbol, _Period, look);
   double now  = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)  continue;
      if(PositionGetDouble(POSITION_PROFIT) >= 0.0) continue;  // losing only

      int    dir = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      double against = (was - now) * dir;
      bool   fast = (against >= InpBrakeAtr * a);
      if(!fast && !blown) continue;

      string why = fast ? StringFormat("%.1f ATR against us in %d bars",
                                       against / a, look)
                        : StringFormat("spread blew out to %.*f against an "
                                       "average of %.*f", _Digits, spNow,
                                       _Digits, spAvg);
      if(trade.PositionClose(tk))
         Log("DISASTER BRAKE: closed because " + why);
      else
         Log(StringFormat("DISASTER BRAKE could not close: %d %s",
                          trade.ResultRetcode(), trade.ResultRetcodeDescription()));
      // a resting order on the other side is now unmanaged, so it goes too
      KillAll("the disaster brake fired");
   }
}

//==================== FUNDED ACCOUNT ===============================
// P89 - the preset table. Every number is from JARVIS/research/PROP_FIRMS.md
// and is tagged OFFICIAL-SUMMARY there, which means: taken from the firm's own
// help centre via a search summary, NOT from a page opened and read line by
// line. That document's standing instruction applies and is repeated here
// because it is the one that costs money if ignored:
//
//   BEFORE ANY REAL MONEY IS COMMITTED, OPEN THE FIRM'S OWN HELP CENTRE AND
//   CONFIRM FOUR NUMBERS: the daily-loss %, the daily-loss BASIS, the
//   daily-loss RESET TIME, and whether the max drawdown TRAILS.
//
// An unverified drawdown rule in a risk engine is worse than no rule, because
// it is trusted.
void ApplyFirmPreset()
{
   // defaults = the manual inputs; each preset overwrites what it knows
   g_firmName   = "Custom";
   g_fDayLoss   = InpMaxDayLossPct / 100.0;
   g_fMaxDD     = InpMaxDDPct      / 100.0;
   g_fTarget    = InpProfitTgtPct  / 100.0;
   g_fConsist   = InpConsistPct    / 100.0;
   g_fTrailing  = InpTrailingDD;
   g_fResetHour = InpResetHourUTC;
   g_fMinDays   = 0;

   switch(InpFirm)
     {
      case FIRM_FTMO_2STEP:
         g_firmName = "FTMO 2-step phase 1";
         g_fDayLoss = 0.05; g_fMaxDD = 0.10; g_fTarget = 0.10;
         g_fConsist = 0.00; g_fTrailing = false; g_fResetHour = 23;
         g_fMinDays = 4;  break;
      case FIRM_FUNDEDNEXT:
         g_firmName = "FundedNext Stellar 2-step";
         g_fDayLoss = 0.05; g_fMaxDD = 0.10; g_fTarget = 0.08;
         g_fConsist = 0.00; g_fTrailing = true;  g_fResetHour = 21;
         g_fMinDays = 5;  break;
      case FIRM_FUNDINGPIPS:
         g_firmName = "FundingPips 2 Step Pro";
         g_fDayLoss = 0.03; g_fMaxDD = 0.06; g_fTarget = 0.08;
         g_fConsist = 0.35; g_fTrailing = false; g_fResetHour = 0;
         g_fMinDays = 2;  break;
      case FIRM_E8_CLASSIC:
         g_firmName = "E8 Classic challenge";
         g_fDayLoss = 0.04; g_fMaxDD = 0.08; g_fTarget = 0.08;
         g_fConsist = 0.00; g_fTrailing = true;  g_fResetHour = 0;
         g_fMinDays = 0;  break;
      case FIRM_E8_PERF:
         g_firmName = "E8 performance (funded)";
         g_fDayLoss = 0.04; g_fMaxDD = 0.08; g_fTarget = 0.06;
         g_fConsist = 0.40; g_fTrailing = true;  g_fResetHour = 0;
         g_fMinDays = 0;  break;
      case FIRM_ALPHA_ONE:
         g_firmName = "Alpha Capital Alpha One";
         g_fDayLoss = 0.04; g_fMaxDD = 0.06; g_fTarget = 0.10;
         g_fConsist = 0.40; g_fTrailing = true;  g_fResetHour = 21;
         g_fMinDays = 0;  break;
      case FIRM_5ERS:
         g_firmName = "The5ers High Stakes";
         g_fDayLoss = 0.05; g_fMaxDD = 0.10; g_fTarget = 0.10;
         g_fConsist = 0.00; g_fTrailing = false; g_fResetHour = 0;
         g_fMinDays = 0;  break;
      default: break;
     }

   g_fBalance = (InpAccountSize > 0.0)
                ? InpAccountSize : AccountInfoDouble(ACCOUNT_BALANCE);

   // THE FLOOR IS THE FIRM'S FLOOR, NOT THE EQUITY PEAK. Build 3.05 measured
   // the drawdown from the running equity high, which is harsher than any rule
   // in the table: a trade that goes +4% and comes back to flat had used 4% of
   // its allowance under the old code and 0% under every real firm. That locked
   // the EA out of days it was entitled to trade.
   g_fFloor = g_fBalance * (1.0 - g_fMaxDD);

   // The derived daily profit cap, at InpConsistencyLock strength. E-093.
   g_fDayCap = (g_fConsist > 0.0)
               ? g_fBalance * g_fConsist * g_fTarget * InpConsistencyLock : 0.0;

   PrintFormat("FUNDED: %s | balance %.2f | daily %.1f%% | DD %.1f%% (%s, floor %.2f)"
               " | target %.1f%% | best-day cap %s | day cap %s | reset %02d:00 UTC",
               g_firmName, g_fBalance, g_fDayLoss * 100.0, g_fMaxDD * 100.0,
               g_fTrailing ? "trailing, locks at start" : "static", g_fFloor,
               g_fTarget * 100.0,
               g_fConsist > 0.0 ? DoubleToString(g_fConsist * 100.0, 0) + "%" : "none",
               g_fDayCap > 0.0 ? DoubleToString(g_fDayCap, 2) : "none",
               g_fResetHour);
   if(g_fConsist <= 0.0)
      Print("FUNDED: this firm has no consistency rule, which E-093 measured as "
            "worth 62 to 70 percentage points of pass rate. Good choice.");
   else
      PrintFormat("FUNDED: %s enforces a %.0f%% best-day rule. E-093 measured that "
                  "as the largest single obstacle here, and frequency is the only "
                  "thing that dissolves it - 2 trades/day passed 24%%, 10/day 99.9%%.",
                  g_firmName, g_fConsist * 100.0);
}

// E-098. One entry's size, divided across the books this EA is running on and
// clamped to what the broker will actually accept. At InpBooks = 1 this returns
// InpEntryLots unchanged, so the single-chart default is untouched.
//
// The floor matters here and is not cosmetic: E-081 measured 0.01 lots as
// GBP 0.787 per point and it CANNOT go smaller. So on a small account three
// books do NOT divide the risk into thirds - each leg is still 0.01 - and the
// account carries 3x the exposure the measurement assumed. That is why this
// warns rather than silently rounding up.
double BookLots()
{
   double want = InpEntryLots / MathMax(1, InpBooks);
   double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(st > 0.0) want = MathFloor(want / st + 0.5) * st;
   if(mn > 0.0 && want < mn)
   {
      static bool warned = false;
      if(!warned)
      {
         warned = true;
         PrintFormat("WARNING: %d books at %.2f lots wants %.4f, but the broker "
                     "minimum is %.2f. Each leg will trade %.2f, so the account "
                     "carries %.1fx the risk the E-098 measurement assumed. "
                     "Either reduce InpBooks or fund a larger account (E-096).",
                     InpBooks, InpEntryLots, InpEntryLots / MathMax(1, InpBooks),
                     mn, mn, mn * InpBooks / InpEntryLots);
      }
      want = mn;
   }
   return want;
}

// The day boundary at the FIRM'S clock, not the broker's midnight. FTMO rolls
// at 00:00 CE(S)T, FundedNext at GMT+3, Maven at 00:00 UTC. Using the wrong one
// puts the daily-loss baseline hours away from where the firm puts it, and the
// EA then polices a limit the firm is not measuring.
int FundedDayStamp()
{
   MqlDateTime t;
   TimeToStruct(TimeGMT() - (datetime)(g_fResetHour * 3600), t);
   return t.year * 10000 + t.mon * 100 + t.day;
}

// STATE THAT MUST SURVIVE A RESTART. g_dayStartEq and g_peakEq were re-seeded
// from the live equity in OnInit, so a terminal restart, a recompile or a
// parameter change silently reset the day's baseline and handed the EA a fresh
// allowance the firm had not given it. Terminal globals persist across all
// three. Same defect class as the SuperTrend recursion, same fix: never keep
// something in memory that the account depends on.
// THE STATE KEY. With InpSharedGuards the key carries the ACCOUNT, not the
// magic, so every instance on this account reads and writes the SAME day
// baseline, peak and floor. Without it three charts would each believe they had
// the full daily allowance and the account would breach at three times the limit
// the EA thought it was enforcing - the most expensive possible way to find out
// that a per-instance guard is not an account guard.
string FundedKey()
{
   if(InpSharedGuards)
      return "JVS_FUNDED_" + (string)AccountInfoInteger(ACCOUNT_LOGIN) + "_";
   return "LQS_" + (string)InpMagic + "_";
}

void FundedSave()
{
   string k = FundedKey();
   GlobalVariableSet(k + "dayStamp", (double)g_dayStamp);
   GlobalVariableSet(k + "dayStartEq", g_dayStartEq);
   GlobalVariableSet(k + "peakEq", g_peakEq);
   GlobalVariableSet(k + "dayProfit", g_dayProfit);
   GlobalVariableSet(k + "daysTraded", (double)g_daysTraded);
   GlobalVariableSet(k + "floor", g_fFloor);
}

void FundedLoad()
{
   string k = FundedKey();
   if(!GlobalVariableCheck(k + "dayStamp")) return;
   g_dayStamp    = (int)GlobalVariableGet(k + "dayStamp");
   g_dayStartEq  = GlobalVariableGet(k + "dayStartEq");
   g_peakEq      = GlobalVariableGet(k + "peakEq");
   g_dayProfit   = GlobalVariableGet(k + "dayProfit");
   g_daysTraded  = (int)GlobalVariableGet(k + "daysTraded");
   double fl     = GlobalVariableGet(k + "floor");
   if(fl > 0.0) g_fFloor = MathMax(g_fFloor, fl);   // a trailed floor only rises
   PrintFormat("FUNDED: restored state from disk - day %d, baseline %.2f, "
               "peak %.2f, floor %.2f, %d day(s) traded",
               g_dayStamp, g_dayStartEq, g_peakEq, g_fFloor, g_daysTraded);
}

//==================== RISK =========================================
// Every limit is enforced at InpSafetyBuffer of its true value. Acting AT the
// limit means acting after the breach has already happened: a 3% daily limit
// checked at 3% is a failed account, not a stopped one. At 0.80 the EA stops
// itself at 2.4% and the firm never sees a breach.
//==================== PER-TICKET TRACKING (E-106) ==================
// The give-back needs two things a position does not carry: the risk it STARTED
// with (once the stop ratchets past break-even the original distance is gone)
// and the best excursion it has ever shown. Both are per ticket.
//
// Kept in parallel arrays rather than a map because MQL5 has no dictionary, and
// pruned on every pass so a long run does not grow them without bound.
ulong  g_tkId[];
double g_tkRisk[];
double g_tkPeak[];

int TrackFind(ulong tk)
{
   for(int i = 0; i < ArraySize(g_tkId); i++)
      if(g_tkId[i] == tk) return i;
   return -1;
}

void TrackAdd(ulong tk, double risk)
{
   int n = ArraySize(g_tkId);
   ArrayResize(g_tkId, n + 1);
   ArrayResize(g_tkRisk, n + 1);
   ArrayResize(g_tkPeak, n + 1);
   g_tkId[n] = tk; g_tkRisk[n] = risk; g_tkPeak[n] = 0.0;
}

// Drop tickets that are no longer open. Without this the arrays grow for the
// life of the terminal and TrackFind gets slower every trade.
void TrackPrune()
{
   for(int i = ArraySize(g_tkId) - 1; i >= 0; i--)
   {
      if(PositionSelectByTicket(g_tkId[i])) continue;
      int last = ArraySize(g_tkId) - 1;
      g_tkId[i] = g_tkId[last]; g_tkRisk[i] = g_tkRisk[last];
      g_tkPeak[i] = g_tkPeak[last];
      ArrayResize(g_tkId, last);
      ArrayResize(g_tkRisk, last);
      ArrayResize(g_tkPeak, last);
   }
}

// E-106 — THE RATCHETING GIVE-BACK STOP. Only runs when InpUncappedExit is on,
// because with it on there is NO broker take-profit and this is the only thing
// that closes a winner.
//
// It lives at the BROKER as a stop, not as an EA decision. E-086: the give-back
// rules used to be TICK-REACTIVE and a spike beat them; a stop order does not
// need this EA to be awake, connected, or even running.
//
// The ratchet is one-way. A stop that can move backwards is not a stop.
void TrailGiveBack()
{
   if(!InpUncappedExit) return;
   TrackPrune();

   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double md = MinStopDist();

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic)  continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)   continue;

      int    dir  = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      if(sl == 0.0) continue;                  // no stop: leave it to the brake

      // R is measured from the position's OWN original risk, which is the
      // distance the stop started at. Once the stop has ratcheted past break-
      // even that distance is gone, so it is tracked per ticket.
      int ix = TrackFind(tk);
      if(ix < 0) { TrackAdd(tk, MathAbs(open - sl)); ix = TrackFind(tk); }
      if(ix < 0) continue;
      double risk = g_tkRisk[ix];
      if(risk <= 0.0) continue;

      double px   = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                              : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double peak = g_tkPeak[ix];
      double now  = (px - open) * dir;
      if(now > peak) { peak = now; g_tkPeak[ix] = peak; }

      double peakR = peak / risk;
      if(peakR < InpGiveBackArmR) continue;    // not yet worth protecting

      // Bigger peaks are protected harder - the same tiering the SuperTrend EA
      // uses, and for the same reason (E-090: the tail carries the profit, so
      // do not hand a large one back).
      double frac = InpGiveBackFrac;
      if(peakR >= 1.5) frac = InpGiveBackFrac * 0.80;
      if(peakR >= 3.0) frac = InpGiveBackFrac * 0.60;

      double keep = peak * (1.0 - frac);
      double want = NormalizeDouble(open + dir * keep, dg);

      // never inside the round trip: that is a fee, not a rule
      double rt = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                - SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(keep < rt) continue;
      // never closer to price than the broker allows, or the modify is rejected
      if(md > 0.0 && MathAbs(px - want) < md) continue;
      // RATCHET: profitable direction only
      if((dir > 0 && want <= sl) || (dir < 0 && want >= sl)) continue;

      if(!trade.PositionModify(tk, want, PositionGetDouble(POSITION_TP)))
         Log(StringFormat("give-back modify failed: %d %s",
                          trade.ResultRetcode(), trade.ResultRetcodeDescription()));
      else
         Log(StringFormat("give-back stop -> %.*f (peak %.2fR, keeping %.0f%%)",
                          dg, want, peakR, 100.0 * (1.0 - frac)));
   }
}

void CheckGuards()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_peakEq) g_peakEq = eq;

   // ---- the drawdown floor, per the firm's own mechanic
   if(g_fTrailing)
     {
      double nf = g_peakEq * (1.0 - g_fMaxDD);
      // E8 and Alpha Capital both LOCK the trail at the initial balance once
      // the account is up. Trailing forever is a rule no firm in the table has.
      if(nf > g_fBalance) nf = g_fBalance;
      if(nf > g_fFloor)   g_fFloor = nf;
     }

   double ddStop = g_fFloor + (g_fBalance - g_fFloor) * (1.0 - InpSafetyBuffer);
   if(!g_lockedPerm && eq <= ddStop)
     {
      g_lockedPerm = true;
      PrintFormat("PERMANENT LOCK: equity %.2f reached %.0f%% of the way to the "
                  "%s floor at %.2f. No further entries.",
                  eq, InpSafetyBuffer * 100.0, g_firmName, g_fFloor);
     }

   // ---- the daily loss limit, on EQUITY, so floating loss counts immediately.
   // PROP_FIRMS.md section 4 is a worked example of an account failing while UP
   // 1,500 on the day with nothing closed and no stop hit. That is the most
   // common way a funded account dies and it is invisible to any check that
   // reads the balance.
   if(!g_lockedDay && g_dayStartEq > 0.0)
     {
      double lost = (g_dayStartEq - eq) / g_dayStartEq;
      if(lost >= g_fDayLoss * InpSafetyBuffer)
        {
         g_lockedDay = true;
         PrintFormat("LOCKED FOR TODAY: down %.2f%% against a %.2f%% limit "
                     "(acting at %.0f%% of it). Floating loss counts.",
                     lost * 100.0, g_fDayLoss * 100.0, InpSafetyBuffer * 100.0);
         KillAll("daily loss guard");
        }
     }

   // ---- the consistency guard. Stop taking NEW trades once the day has made
   // enough. It cannot cap a trade already open, which is why the cap is set at
   // half the derived number - see the header block.
   if(!g_lockedProf && g_fDayCap > 0.0 && g_dayProfit >= g_fDayCap)
     {
      g_lockedProf = true;
      PrintFormat("LOCKED FOR TODAY ON PROFIT: %.2f made against a %.2f cap. "
                  "This protects the %.0f%% best-day rule, which E-093 measured "
                  "as worth 62-70 points of pass rate.",
                  g_dayProfit, g_fDayCap, g_fConsist * 100.0);
     }

   // ---- have we finished?
   if(InpStopWhenPassed && !g_passed && g_fTarget > 0.0
      && eq >= g_fBalance * (1.0 + g_fTarget) && g_daysTraded >= g_fMinDays)
     {
      g_passed = true;
      PrintFormat("TARGET REACHED: equity %.2f against a target of %.2f, over "
                  "%d trading day(s). No further entries.",
                  eq, g_fBalance * (1.0 + g_fTarget), g_daysTraded);
      KillAll("profit target reached");
     }

   FundedSave();
}

//==================== READOUT ======================================
// On a 250ms TIMER, not on the tick. OnTick does not run when the market is
// quiet, does not run when it is shut, and does not run between the EA being
// attached and the first quote - which is how the SuperTrend EA's box came to
// look frozen three separate times. The heartbeat clock is there so that "it
// is not updating" is answerable from the chart instead of from a guess.
void Readout()
{
   if(!InpComment) return;

   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sp  = ask - bid;
   if(sp > 0.0) { g_spSum += sp; g_spN++; if(sp > g_spMax) g_spMax = sp; }
   double spAvg = (g_spN > 0) ? g_spSum / (double)g_spN : 0.0;

   double pl = 0.0, lots = 0.0, ent = 0.0, slp = 0.0, tpp = 0.0;
   int    dir = 0, np = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      np++;
      lots += PositionGetDouble(POSITION_VOLUME);
      pl   += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      ent   = PositionGetDouble(POSITION_PRICE_OPEN);
      slp   = PositionGetDouble(POSITION_SL);
      tpp   = PositionGetDouble(POSITION_TP);
      dir   = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
   }

   g_readN++;
   string live = TimeToString(TimeCurrent(), TIME_MINUTES | TIME_SECONDS);

   // both sides, because both can be resting at once
   string armed = "";
   if(g_tkBuy != 0)
      armed += StringFormat("BUY limit %.*f", _Digits, g_lvlBuy);
   if(g_tkSell != 0)
      armed += StringFormat("%sSELL limit %.*f", armed == "" ? "" : "   ",
                            _Digits, g_lvlSell);
   if(armed == "") armed = "none resting";

   string pos = (np == 0)
      ? "flat"
      : StringFormat("%s %.2f lots from %.*f   stop %.*f   target %.*f",
                     dir > 0 ? "LONG" : "SHORT", lots, _Digits, ent,
                     _Digits, slp, _Digits, tpp);

   Comment(StringFormat(
      "LIQUIDITY SNIPER  build %s\n"
      "%s %s   equity %s   live %s  (%d)\n"
      "\n"
      "POSITION   %s\n"
      "P/L        %s        today %s over %d trades\n"
      "ARMED      %s\n"
      "\n"
      "LEVELS     %d buyside  %d sellside  %d FVG  %d order blocks\n"
      "WIN RATE   %s   (%d of %d closed)\n"
      "SPREAD     now %.*f   avg %.*f   worst %.*f\n"
      "STATE      %s\n"
      "\n"
      "P91 parity, THE EA's own numbers: GOLD 1h 43.0%% on 895, +0.249R,\n"
      "PF 1.42, t=+5.0. The +0.487R figure is the BACKTEST's and is not this EA's.\n"
      "HALF THESE TRADES LOSE. The money is in 2R, not in being right often.\n"
      "Measured on 15m/1h bars, NOT on M1. XAUUSD only.",
      LQS_BUILD,
      _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period), Money(eq), live, (int)g_readN,
      pos,
      Money(pl), Money(g_dayRealized), g_tradesToday,
      armed,
      ArraySize(g_zB), ArraySize(g_zS), ArraySize(g_fvg), ArraySize(g_ob),
      (g_nTrades > 0 ? StringFormat("%.1f%%", 100.0 * g_nWins / g_nTrades) : "-"),
      g_nWins, g_nTrades,
      _Digits, sp, _Digits, spAvg, _Digits, g_spMax,
      g_passed     ? "PASSED - target reached"
      : g_lockedPerm ? "LOCKED - max drawdown"
      : g_lockedDay  ? "locked for today - daily loss"
      : g_lockedProf ? "locked for today - best-day rule"
                     : "trading"));
}

//==================== EVENTS =======================================
int OnInit()
{
   if(!TfGuard("LQS", InpMaxTF)) return INIT_FAILED;
   if(InpDemoOnly && AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      Print("REFUSING TO START: InpDemoOnly is true and this is not a demo "
            "account. Set InpDemoOnly=false deliberately to trade live.");
      return INIT_FAILED;
   }

   g_atrHandle = iATR(_Symbol, _Period, 14);
   if(g_atrHandle == INVALID_HANDLE) { Print("ATR handle failed"); return INIT_FAILED; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(20);

   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dayStartEq = eq;
   g_peakEq     = eq;
   ApplyFirmPreset();        // derive every limit from the firm and the size
   g_dayStamp   = FundedDayStamp();
   FundedLoad();             // ...then let any persisted state override it

   ArrayResize(g_zB, 0);  ArrayResize(g_zS, 0);
   ArrayResize(g_pivH, 0); ArrayResize(g_pivL, 0);

   EventSetMillisecondTimer(250);
   int pbCorner = InpBoxCorner == 0 ? CORNER_LEFT_UPPER  :
                  InpBoxCorner == 1 ? CORNER_RIGHT_UPPER :
                  InpBoxCorner == 2 ? CORNER_LEFT_LOWER  : CORNER_RIGHT_LOWER;
   PB_Init("LQSPB.", "LIQUIDITY SNIPER " + LQS_BUILD, InpMagic, InpShowProfitBox,
           pbCorner, InpBoxX, InpBoxY, "LIQUIDITY");
   if(InpTrackMagic2 != 0) PB_AddStrategy(InpTrackMagic2, InpTrackLabel2);
   if(InpTrackMagic3 != 0) PB_AddStrategy(InpTrackMagic3, InpTrackLabel3);
   Readout();

   Print("=== LIQUIDITY SNIPER BUILD " + LQS_BUILD + " ===");
   Print("If that build stamp is not the one you were sent, MetaEditor has not "
         "rebuilt it. Open the .mq5 and press F7.");
   Print("Geometry is E-077 and is NOT a tuning surface: the limit rests 0.25 "
         "ATR PAST the zone's far edge, the stop is 0.60 ATR beyond the fill, "
         "the target is 2R. Changing any of the three invalidates every number "
         "quoted for it.");
   Print("EXPECT TO LOSE ABOUT HALF THESE TRADES. 47.5% win rate is the "
         "measured figure and it is not a fault. Monte Carlo on trade order "
         "puts the drawdown to expect near 12R, and 18R at the 95th "
         "percentile. Decide now whether you can sit through that.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   PB_Destroy();
   // Leave no order behind that nothing is managing.
   KillAll("the EA is shutting down");
   Comment("");
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
}

void OnTimer()
{
   Readout();
   PB_Draw();
}

void OnTick()
{
   // THE FIRM'S CLOCK, not the broker's midnight. FundedDayStamp() offsets by
   // the preset's reset hour, so the baseline lands where the firm puts it.
   int ds = FundedDayStamp();
   if(ds != g_dayStamp)
   {
      if(g_tradesToday > 0) g_daysTraded++;
      g_dayStamp     = ds;
      g_dayStartEq   = AccountInfoDouble(ACCOUNT_EQUITY);
      g_tradesToday  = 0;
      g_lockedDay    = false;
      g_lockedProf   = false;
      g_dayRealized  = 0.0;
      g_dayProfit    = 0.0;
      FundedSave();
      PrintFormat("new trading day (%s clock, reset %02d:00 UTC): baseline "
                  "equity %.2f, %d day(s) traded so far",
                  g_firmName, g_fResetHour, g_dayStartEq, g_daysTraded);
   }

   DisasterBrake();   // FIRST. Nothing outranks getting out of a disaster.
   TrailGiveBack();   // E-106: the only thing that closes a winner when uncapped
   CheckGuards();

   // There is nothing for OnTick to do about the entry: the limit order is at
   // the BROKER, so it fills on the touch whether or not a tick reaches this
   // EA. That is the point of using a real pending order.

   // EVERYTHING BELOW RUNS ONLY WHEN A BAR CLOSES, so that the backtest and
   // the live account remain the same system.
   datetime bt = iTime(_Symbol, _Period, 0);
   if(bt == g_lastBar) return;
   g_lastBar = bt;

   if(Bars(_Symbol, _Period) < InpPivLen * 4 + 30) return;

   BuildZones();
   BuildSmc();
   ManageOrders();
}

// The stop and the target are on the order, so the broker closes the trade.
// This only counts the result, which is what the readout reports.
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &req,
                        const MqlTradeResult &res)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagic) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;
   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);

   // THE FILL. g_tradesToday used to be incremented where the EA sent the
   // order; now the broker owns the order, so the only honest place to count a
   // trade is where one actually opened.
   if(entry == DEAL_ENTRY_IN)
   {
      PB_PromoteOrder((ulong)HistoryDealGetInteger(trans.deal, DEAL_ORDER),
                      (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID),
                      HistoryDealGetDouble(trans.deal, DEAL_PRICE));
      g_tradesToday++;
      // NOW the level is spent - it produced a trade.
      if(InpArmOncePerLvl)
         MarkUsed(HistoryDealGetDouble(trans.deal, DEAL_PRICE));
      // one side filled, so the other must go: the measurement counted one
      // position at a time and two open would be a different strategy.
      KillAll("the other side filled");
      Log(StringFormat("FILLED at %.*f   %d trades today",
                       _Digits, HistoryDealGetDouble(trans.deal, DEAL_PRICE),
                       g_tradesToday));
      return;
   }
   g_pbDirty = true;
   if(entry != DEAL_ENTRY_OUT) return;

   double p = HistoryDealGetDouble(trans.deal, DEAL_PROFIT)
            + HistoryDealGetDouble(trans.deal, DEAL_SWAP)
            + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
   g_nTrades++;
   if(p > 0.0) g_nWins++;
   g_realized    += p;
   g_dayRealized += p;
   if(p > 0.0) g_dayProfit += p;   // the consistency guard counts PROFIT only
   FundedSave();
   Log(StringFormat("CLOSED %s   running %s over %d trades, %.1f%% won",
                    Money(p), Money(g_realized), g_nTrades,
                    100.0 * g_nWins / MathMax(g_nTrades, 1)));
}

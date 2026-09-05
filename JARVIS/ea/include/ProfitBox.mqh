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

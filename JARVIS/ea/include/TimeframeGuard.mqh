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

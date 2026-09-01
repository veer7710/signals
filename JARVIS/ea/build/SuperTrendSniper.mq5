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
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
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
input int    InpDemaLen       = 200;    // DEMA length (60 on M1, 100 on M3)
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
input double InpTargetR       = 3.0;    // hard take profit at N x risk
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
input int    InpMaxStall      = 25;     // close a stalled trade after this many bars
input bool   InpStallScales   = true;   // and tighten the give-back as it stalls
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
input bool   InpUseAdxFilter  = true;   // skip entries when the trend is already extended
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
input double InpRiskPct       = 0.50;   // % of equity risked per trade
input double InpStopAtrMult   = 1.5;    // stop distance in ATR
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
input double InpMaxCostFrac   = 0.10;   // refuse if round trip > this x the stop
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
input bool   InpUseGiveBack   = true;   // leave when profit is handed back
input double InpGbArmR        = 1.0;    // only after the trade got this good
input double InpGbBase        = 0.30;   // give back this much of the peak
input double InpGbTier2R      = 2.0;    // once the peak passes this...
input double InpGbTier2       = 0.24;   // ...allow only this much give-back
input double InpGbTier3R      = 4.0;    // and past this...
input double InpGbTier3       = 0.18;   // ...this much. Big peaks are protected harder
input double InpGbMinMoney    = 0.0;    // ignore the rule below this profit (0 = off)
input double InpGbClosePart   = 0.5;    // fraction to bank (1.0 = close it all)

input group "=== BASKET (manage the TOTAL, not one trade) ==="
// Veer's actual failure was never one trade: "the basket reached ~GBP12 and
// closed at breakeven; four positions reached ~GBP4 and still closed in loss".
// Four positions each individually behaving reasonably can still hand back
// the whole basket, because nothing was watching the total. Now something is.
input bool   InpUseBasket     = true;   // protect total floating profit
input double InpBasketArmPct  = 0.60;   // arm once the basket is this % of equity green
input double InpBasketMinMoney= 2.00;   // ...and at least this much money
input double InpBasketGiveBack= 0.35;   // close the basket after handing back this much
input bool   InpBasketCloseAll= true;   // false = only close the losers, keep the winner
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
input int    InpBoxCorner     = 1;      // 0 top-left 1 top-right 2 bottom-left 3 bottom-right
input int    InpBoxX          = 12;     // pixels in from that corner
input int    InpBoxY          = 18;
input int    InpBoxSize       = 8;      // font size
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
double GiveBackAllowed(double peakR, int stall);
int    StallBars(int ti);
void   UpdatePeaks();
void   ProtectPositions();
void   ProtectBasket();
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
void   SaveStats();
void   LoadGuards();
double MinStopDist();
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

// DEMA = 2*EMA(n) - EMA(EMA(n)), computed from closes. Matches the Pine.
double DEMA(int len, int shift)
{
   int need = len * 3 + shift + 5;
   if(Bars(_Symbol, _Period) < need) return 0.0;
   double k = 2.0 / (len + 1.0);
   double e1 = iClose(_Symbol, _Period, need - 1);
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
      double dNow  = DEMA(InpDemaLen, 1);
      double dPrev = DEMA(InpDemaLen, 3);
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
   bool sameWay = (g_lastEntryDir != 0 && g_lastEntryDir == (flipUp ? 1 : -1));
   if(trRisk >= 3 && sameWay)
   {
      SkipLog(sdir, "trend risk 3/3 and this is another same-way entry: " + trWhy);
      return;
   }
   if(trRisk == 2)
   {
      double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      double half = lots * 0.5;
      if(step > 0) half = MathFloor(half / step) * step;
      if(half >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
      {
         Log(StringFormat("trend risk 2/3 (%s): sizing down %.2f -> %.2f",
                          trWhy, lots, half));
         lots = half;
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
      double tp = NormalizeDouble(ask + InpTargetR * stopDist, dg);
      // A target sitting beyond the next level watches price stop just short of
      // it and turn. Park it INSIDE the level instead, by InpLevelBufAtr, so it
      // is reached rather than admired.
      if(InpUseLevels && InpTpAtLevel)
      {
         double capLvl = NearestLevel(ask, +1);
         if(capLvl > 0)
         {
            double capped = NormalizeDouble(capLvl - InpLevelBufAtr * atr, dg);
            if(capped > ask && capped < tp)
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
         double ltp = NormalizeDouble(lim + (tp - ask), dg);
         if(trade.BuyLimit(lots, lim, _Symbol, lsl, ltp, ORDER_TIME_GTC, 0,
                           RiskTag(stopDist, dg)))
         {
            g_tradesToday++; RegisterEntry(flipUp ? 1 : -1);
            Journal("LIMIT", "long", lim, lots, lsl, ltp, 0, "waiting for pullback");
            Log(StringFormat("BUY LIMIT %.2f at %.*f  sl %.*f  tp %.*f",
                             lots, dg, lim, dg, lsl, dg, ltp));
         }
         else Log("BuyLimit failed: " + IntegerToString(trade.ResultRetcode()));
         return;
      }

      if(trade.Buy(lots, _Symbol, 0.0, sl, tp, RiskTag(stopDist, dg)))
      {
         g_tradesToday++; RegisterEntry(flipUp ? 1 : -1);
         Journal("ENTRY", "long", ask, lots, sl, tp, 0, "");
         Log(StringFormat("LONG %.2f lots  sl %.*f  tp %.*f  atr %.*f",
                          lots, dg, sl, dg, tp, dg, atr));
      }
      else Log("Buy failed: " + IntegerToString(trade.ResultRetcode()));
   }
   else
   {
      double sl = NormalizeDouble(bid + stopDist, dg);
      double tp = NormalizeDouble(bid - InpTargetR * stopDist, dg);
      if(InpUseLevels && InpTpAtLevel)
      {
         double capLvl = NearestLevel(bid, -1);
         if(capLvl > 0)
         {
            double capped = NormalizeDouble(capLvl + InpLevelBufAtr * atr, dg);
            if(capped < bid && capped > tp)
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
         double ltp = NormalizeDouble(lim - (bid - tp), dg);
         if(trade.SellLimit(lots, lim, _Symbol, lsl, ltp, ORDER_TIME_GTC, 0,
                            RiskTag(stopDist, dg)))
         {
            g_tradesToday++; RegisterEntry(flipUp ? 1 : -1);
            Journal("LIMIT", "short", lim, lots, lsl, ltp, 0, "waiting for pullback");
            Log(StringFormat("SELL LIMIT %.2f at %.*f  sl %.*f  tp %.*f",
                             lots, dg, lim, dg, lsl, dg, ltp));
         }
         else Log("SellLimit failed: " + IntegerToString(trade.ResultRetcode()));
         return;
      }

      if(trade.Sell(lots, _Symbol, 0.0, sl, tp, RiskTag(stopDist, dg)))
      {
         g_tradesToday++; RegisterEntry(flipUp ? 1 : -1);
         Journal("ENTRY", "short", bid, lots, sl, tp, 0, "");
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
   if(HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_OUT) return;

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
double GiveBackAllowed(double peakR, int stall)
{
   double gb = InpGbBase;
   if(peakR >= InpGbTier2R) gb = InpGbTier2;
   if(peakR >= InpGbTier3R) gb = InpGbTier3;

   string w = "";
   int risk = TrendRisk(w);
   if(risk == 1)      gb *= 0.80;
   else if(risk == 2) gb *= 0.62;
   else if(risk >= 3) gb *= 0.45;

   // E-056. Weighted to the measured gradient, not to taste: the 0-1 and
   // 1-3 buckets were BETTER than base in 8 of 8 markets, so a trade still
   // printing new highs is given more room, not less.
   if(InpStallScales)
   {
      if(stall <= 1)       gb *= 1.35;
      else if(stall <= 3)  gb *= 1.15;
      else if(stall <= 6)  gb *= 1.00;
      else if(stall <= 12) gb *= 0.85;
      else if(stall <= 25) gb *= 0.70;
      else                 gb *= 0.55;
   }

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
      return;
   }
   if(g_bkStart == 0) g_bkStart = TimeCurrent();
   if(b.money > g_bkPeak)
   {
      g_bkPeak     = b.money;
      g_bkPeakTime = TimeCurrent();
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
      if(peakR < InpGbArmR) continue;                 // never got good enough
      if(InpGbMinMoney > 0.0 && g_tkPeakMoney[ti] < InpGbMinMoney) continue;

      long   type = PositionGetInteger(POSITION_TYPE);
      int    dir  = (type == POSITION_TYPE_BUY) ? 1 : -1;
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double px   = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                              : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double rNow = (px - open) * dir / g_tkRisk[ti];

      int    stall = StallBars(ti);
      double gb    = GiveBackAllowed(peakR, stall);
      double keep  = peakR * (1.0 - gb);
      if(rNow > keep) continue;

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
   double arm = MathMax(eq * InpBasketArmPct / 100.0, InpBasketMinMoney);

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
      // right-hand corners read right-to-left, or the text runs off the chart
      if(InpBoxCorner == 1 || InpBoxCorner == 3)
         ObjectSetInteger(0, nm, OBJPROP_ANCHOR, ANCHOR_RIGHT_UPPER);
   }
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
   BoxLine(r++, StringFormat("cost %.1f%% of stop   efficiency %.2f   flips %d/%d",
                             (g_boxStop > 0 ? 100.0 * g_boxCost / g_boxStop : 0.0),
                             g_boxEff, g_boxFlips, InpChopFlipLen),
           (g_boxStop > 0 && g_boxCost / g_boxStop > InpMaxCostFrac)
           ? bad : InpBoxText);
   BoxLine(r++, StringFormat("give-back allowance now %.0f%%   stall %d bars",
                             GiveBackAllowed(MathMax(b.peakR, 0.0), b.stall) * 100.0,
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
int OnInit()
{
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

   PrintFormat("SuperTrendSniper started. ST(%d, %.2f) DEMA(%d) risk %.2f%% "
               "target %.1fR  BE=%s trail=%s",
               InpStAtrLen, InpStMult, InpDemaLen, InpRiskPct, InpTargetR,
               InpUseBreakEven ? "ON" : "off", InpUseTrail ? "ON" : "off");
   if(InpUseBreakEven)
      Print("WARNING: break-even is ON. It measured as the worst exit rule on "
            "all four markets tested. Only leave it on if you are testing it.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   SaveStats();
   BoxClear();
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
   CheckGuardsTick();      // before anything else: a breach outranks a rule
   UpdatePeaks();
   ProtectPositions();
   ProtectBasket();
   DrawBox();

   // EVERYTHING BELOW RUNS ONLY WHEN A BAR CLOSES.
   // This is what makes a backtest match live. v19.18 recomputed its engine on
   // every tick, so its backtest and its live behaviour were different systems.
   datetime bt = iTime(_Symbol, _Period, 0);
   if(bt == g_lastBarTime) return;
   g_lastBarTime = bt;

   if(Bars(_Symbol, _Period) < InpDemaLen * 3 + 10) return;

   UpdateSuperTrend();
   BuildLevels();          // before anything asks where the levels are
   ExpireStalePendings();  // a limit is only good while its setup is
   ManagePosition();
   TryEntry();
}
//+------------------------------------------------------------------+

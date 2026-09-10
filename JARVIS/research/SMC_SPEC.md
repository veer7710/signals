# SMC_SPEC.md — mechanical specification of ICT / Smart Money Concepts / liquidity concepts

Reference document. Produced 2026-09-10. **No code was written and no backtest was run to produce this.**
Nothing in this file is a claim that anything works. Every concept below is UNPROVEN in this
repository's vocabulary (`JARVIS/state/EXPERIMENTS.md`) until `JARVIS/research/study.py` says otherwise.

---

## 0. HOW THIS DOCUMENT WAS SOURCED, AND WHAT FAILED

This matters more than usual, because a spec written from recall would be coded as though it were sourced.

**What worked.** Outbound HTTPS in this session is filtered by an egress policy. `raw.githubusercontent.com`
and `gist.github.com` are reachable; GitHub code search is reachable through the MCP GitHub tool. That
turned out to be the good channel: the TradingView Pine source of most of the well-known public ICT/SMC
indicators is mirrored on GitHub, and **Pine source is the most precise spec that exists for these concepts** —
it has no judgement calls left in it. About 45 indicator sources plus one Python package were downloaded; roughly 30 of them were
read in detail (the rest were checked only for their settings blocks). Every definition marked **[CODE]** below was read directly out of a source file, and the
raw URL is given.

**What failed.** `WebFetch` returned `EGRESS_BLOCKED` for every non-GitHub domain tried:
luxalgo.com, tradingfinder.com, forexfactory.com, writofinance.com. `WebSearch` worked for the first
~6 queries and then returned "Web search error: unavailable" for every subsequent query and never
recovered (≈10 consecutive failures across spaced retries).

Consequences you must hold onto:

1. Definitions marked **[SEARCH]** come from a *search engine's summary of a page*, not from the page
   itself. They are second-hand. They are good enough to tell you what the community means by a term
   and where the disagreements are; they are **not** good enough to code from without checking the page.
2. **Section 8 (published numbers) is nearly empty, and that is a finding, not a gap in effort.** The
   queries that would have surfaced backtests ("silver bullet backtest win rate", "FVG fill rate study",
   "SMC backtest results sample size") are exactly the ones that failed. What little is below is flagged.
   Do not fill the hole from memory later. Re-run those searches from an unblocked session.
3. Anywhere sources contradict, both versions are given. Where only one implementation exists, it is
   named as *that author's* choice, not as "the" definition.

**Source key.**
- `LUX-<name>` = `https://raw.githubusercontent.com/deepentropy/lightweight-charts-indicators/main/docs/official/indicators_community/<name>.pine`
  (a GitHub mirror of the published TradingView community scripts; author credit is in the file header).
- `SMC-PY` = `https://raw.githubusercontent.com/joshyattridge/smart-money-concepts/master/smartmoneyconcepts/smc.py`
  (Python package, ~2.0k stars, the most-used programmatic SMC implementation).
- `LUX-SMC` = `https://raw.githubusercontent.com/TamTH-Dev/trading-view-scripts/master/collections/LuxAlgo/SmartMoneyConcepts.pine`
  (mirror of LuxAlgo's flagship "Smart Money Concepts [LuxAlgo]").
- `SOB` = `https://raw.githubusercontent.com/TradersDen/makuchaku/master/super_order_block.pine`
- `RB-UALGO` = `https://raw.githubusercontent.com/regalouisei/collect-tradingview/main/pinescript/trend_analysis/rejection-blocks-ualgo.pine`
- `SNIPER` = `https://raw.githubusercontent.com/RumeshChathuranga/Forex/main/indicator/advanced-rc-ict-sniper.pine`
  (one anonymous author's full-stack implementation; useful because it defines the rare arrays, but it
  is one person's opinion, not a community standard — treated as such throughout).

**Notation.** `high[1]` = previous bar's high, `high[2]` = two bars ago, Pine convention, index 0 = current.
"NY time" = America/New_York with DST. Gold trades XAUUSD; where a rule references a stock-index session
(09:30 equities open) it is noted, because it may not transfer.

---

## 1. LIQUIDITY

### 1.1 Buyside liquidity / Sellside liquidity (BSL / SSL)

**1. Aliases.** BSL / SSL; buy-side and sell-side liquidity pools; "buyside liquidity" = resting buy stops
above highs; "sellside" = resting sell stops below lows. Also "liquidity pool", "resting liquidity",
"draw on liquidity" (DOL) when used as a target.

**2. Mechanical definition.**

*Version A — clustered-pivot pool* **[CODE]**, `LUX-Buyside & Sellside Liquidity`:
```
atr    = ta.atr(10)
liqLen = 7                      // detection length, allowed 3..13
liqMar = 10 / 6.9  = 1.4493     // "margin" divisor
ph = ta.pivothigh(liqLen, 1)    // NOTE: asymmetric — 7 bars left, 1 bar right
pl = ta.pivotlow (liqLen, 1)
// on each new pivot high ph, walk back through stored zigzag highs:
//   stop when a stored high > ph + atr/liqMar
//   count a stored high if  ph - atr/liqMar < stored < ph + atr/liqMar
// if count > 2  (i.e. 3 or more highs inside the band) -> a BUYSIDE LIQUIDITY level exists
level  = avg(minP, maxP)                       // mean of the clustered highs
zone   = [level - atr/liqMar , level + atr/liqMar]
```
So a buyside pool = **3+ pivot highs whose prices all sit inside a band of ±ATR(10)/1.449 ≈ ±0.69·ATR(10)**,
and the level is the mean of those highs. Sellside is the mirror on `ta.pivotlow(7,1)`.

*Breach vs sweep zone, same file:* the level is `brL` (breached) the first bar `high > zone.top`. On that
bar a "sweep zone" is opened from the level up to `min(level + 2.3·ATR(10), high)`. The sweep zone stays
alive while `low > level - 2.3·ATR(10) and high < level + 2.3·ATR(10)`; the first bar that leaves that
band closes it. `marBuy = marSel = 2.3` by default (range 1.5–10).

*Version B — grouped swing pool* **[CODE]**, `SMC-PY` `smc.liquidity()`:
```
pip_range = (max(high) - min(low)) * range_percent      # range_percent default 0.01 -> 1% of the whole chart range
# for each swing high i (swing_length default 50):
#   band = [level - pip_range, level + pip_range]
#   swept = first bar after i whose high >= band.top   (0 if never)
#   group in every later swing high inside the band, stopping at swept
#   if the group has >1 member -> Liquidity = +1, Level = mean of group, End = last member, Swept = index
```
Note the tolerance here is **a fixed fraction of the entire dataset's range**, not ATR. On a long XAUUSD
history 1% of the full range is enormous. This is a real defect for our use; if you port this, replace
`pip_range` with an ATR-scaled band or the whole thing degenerates.

**Version A needs 3 highs, Version B needs 2.** That is a genuine disagreement, not a detail: it changes
how many pools exist by a large factor.

**3. Claimed to predict.** That price is *drawn toward* the pool (a target — "draw on liquidity"), and that
on reaching it price either continues (a genuine break) or reverses (a sweep). The pool itself is claimed
to be a magnet, not a signal. LuxAlgo's own framing (`LUX-Buyside & Sellside Liquidity` alerts) is
"liquidity level detected/updated" and "liquidity level breached" — an event marker, no direction claimed.

**4. Numbers.** None retrievable. See §8.

---

### 1.2 Equal highs / equal lows (EQH / EQL)

**1. Aliases.** EQH/EQL, double top/bottom, "liquidity level", "clean highs".

**2. Mechanical definition.** Three published thresholds, all different:

*(a)* **[CODE]** `LUX-SMC`:
```
eq_len = 3, eq_threshold = 0.1, atr = ta.atr(200)
eq_top = ta.pivothigh(eq_len, eq_len)        // symmetric 3-left / 3-right
on a new eq_top:
    max = math.max(eq_top, eq_prev_top); min = math.min(eq_top, eq_prev_top)
    if max < min + atr * eq_threshold  ->  EQH   (i.e. |h1 - h2| < 0.1 * ATR(200))
EQL: if min > max - atr * eq_threshold
```
Only the **two most recent** pivots are compared — this is a pairwise test, not a cluster test.

*(b)* **[CODE]** `LUX-ICT Institutional Order Flow (fadi)`, labelled "Relative Equal Highs and Lows":
```
median.unshift(ta.atr(14)); keep last 14; spacing = median.median() * EQ_Tolerance
EQ_Tolerance = input.int(2, options 1..10) / 10     -> default 0.2
```
so tolerance = **0.2 × median of the last 14 ATR(14) values**. Additionally fadi runs `testEQ()`, which
draws a straight line between the two pivots and **rejects the pair if any bar between them trades
through that line** (`high[j] > p` for highs). That "no bar pierced the connecting line" condition is
absent from every other implementation and is the single most useful discriminator in this section —
it is what separates a clean shelf from two coincidentally similar highs with chop between them.

*(c)* **[CODE]** `LUX-Swing Breakout Sequence`, `strictThresholdInput = 0.50 * ta.atr(200)` for
"Require Equal H/L at Point 5" — five times looser than (a).

**"Relatively equal" vs "equal"**: in practice nobody means exactly equal. (a)(b)(c) *are* the
relatively-equal definitions. The distinction people voice — "equal" = to the tick, "relatively equal" =
within a tolerance — does not exist in any code I read; every implementation uses a tolerance.

**3. Claimed to predict.** That stops rest just beyond the shelf, so price is likely to run it. Direction
claimed only after the run (see 1.6).

**4. Numbers.** None retrievable.

**Note for this repo.** Equal highs/lows are already scored here. What is *not* scored is fadi's
"connecting line unpierced" filter and the 3-vs-2 pivot count. Those are the parts worth testing next.

---

### 1.3 LOW-RESISTANCE vs HIGH-RESISTANCE LIQUIDITY RUN (LRLR / HRLR)

The user named this specifically. Here is the honest position: **no public implementation of this exists
in code that I could find, and the prose definitions are qualitative.** It is currently not codeable
without you making the quantitative decisions yourself. Below is the real prose definition and then the
minimum set of decisions you would have to invent.

**1. Aliases.** LRLR / HRLR; "low-resistance liquidity run" / "high-resistance liquidity run";
low-/high-resistance liquidity. Occasionally "clean run" vs "grindy run".

**2. Definition as published** **[SEARCH]** (these are search-engine summaries of pages I could not
fetch; sources: https://www.luxalgo.com/library/concept/low-resistance-vs-high-resistance-liquidity-runs/ ,
https://tradingfinder.com/education/forex/ict-hrlr-lrlr/ ,
https://www.forexfactory.com/thread/1342561-high-and-low-resistance-liquidity-run-in-ict ,
https://www.writofinance.com/liquidity-run-lrlr-hrlr-in-forex/ ,
https://innercircletrader.net/tutorials/ict-hrlr-lrlr/ ,
https://infinity-trading.io/articles/month-1-liquidity-runs/ ):

> **LRLR** — price runs through territory with *little opposing interest*: the intervening highs/lows have
> already been swept, imbalances point the same way, price travels fast and directly to its target pool.
> Momentum-driven, sharp, quick.
>
> **HRLR** — price must grind through *fresh, unswept* swing points and opposing levels. Slow,
> overlapping, prone to deep retracements. Arises when a liquidity level is defended by multiple
> short-term highs/lows in the way.

The distinguishing variable in every source is the same: **how many unswept opposing swing points sit
between current price and the target pool**, plus whether the space between is already balanced (no
unfilled imbalance) or unbalanced.

**Not to be confused with** ICT's older, different use of the phrase, where "high resistance liquidity"
means a level that has *already been run several times* and so has little left resting behind it. The
Forex Factory thread cited above exists precisely because traders disagree on which of these two readings
is right. **Treat this as two competing concepts sharing one name.**

**3. Claimed to predict.** LRLR predicts *reachability and speed* — that the target pool will be reached,
in fewer bars, with shallower pullbacks. HRLR predicts the opposite: the target may not be reached at all,
and any position held toward it will be given back. It is a claim about **path**, not about direction.
No published source claims a win rate for either.

**4. Numbers.** None. Every source I could reach is a course seller or an indicator vendor's education
page, none quotes a sample size.

**If you want to code it, these are the decisions you must make (none are given by any source):**
- *Which swings count as "resistance"?* Pick a swing definition and a term (short/intermediate/long, §2.1)
  and count only unswept pivots of that term strictly between current price and the target level.
- *Threshold.* e.g. `resistance_count == 0` → LRLR; `>= 2` → HRLR; `1` → ambiguous. Arbitrary.
- *Does an unfilled FVG pointing the wrong way count as resistance?* Sources imply yes.
- *Is it directional-aware?* A pool above with 3 unswept minor highs below it is not "defended"; only
  levels *between* price and the target count.
- The obvious testable form here, and the one this repo should actually run, is **not** the label but the
  underlying continuous variable: *count of unswept opposing pivots between price and the target*, and
  *sum of unfilled opposing imbalance in that span*. Score those as continuous features against
  "did price reach the target within N bars" and "MAE on the way". The LRLR/HRLR label is just a
  threshold on those numbers, so score the number and let the threshold fall out.

---

### 1.4 Liquidity sweep / stop run vs genuine break

**1. Aliases.** Sweep, raid, stop hunt, liquidity grab, purge, "run on liquidity"; the failed version is a
Swing Failure Pattern (SFP) or Turtle Soup.

**2. Mechanical definition.** The community-wide test is *wick through, body back*:

**[CODE]** `LUX-Liquidity Sweeps` (author LuxAlgo, `len = 5`, `ta.pivothigh(5,5)`):
```
// for a stored pivot high get.prc:
//   "wick sweep":      high > get.prc  and  close < get.prc      -> bearish sweep
//   "outbreak":        close > get.prc                            -> genuine break (get.brk := true)
//   after a genuine break, "retest":  low < get.prc and close > get.prc -> bullish continuation signal
// mirror for pivot lows.
```
That is the whole distinction, and it is clean: **`high > level and close < level` = sweep;
`close > level` = break.** Everything else is decoration.

**[CODE]** `LUX-Market Structure with Inducements & Sweeps` uses the same test against a *trailing* extreme
rather than a pivot, and adds an age filter:
```
if high > max and close < max and os == 1 and n - max_x1 > 1   -> sweep
```
`n - max_x1 > 1` means the extreme must be at least 2 bars old — it refuses to call a sweep on the bar
that just made the high.

**[CODE]** `LUX-Buyside & Sellside Liquidity` uses close-agnostic breach (`high > zone.top`) and then
classifies afterwards by whether price stays inside the ±2.3·ATR band. Different and looser.

**Competing versions summary:**
- (i) wick beyond + close back inside, same bar. (LuxAlgo Liquidity Sweeps, SFP, Turtle Soup.)
- (ii) wick beyond + close back inside **within N bars** (N=1..3) rather than the same bar. Used by the
  SFP script via its `opposL` confirmation search; more permissive.
- (iii) any trade beyond the level = a "raid", with genuineness decided later by displacement (§2.7).
  This is the ICT-lecture version and it is *not* mechanical on the bar it happens.

**3. Claimed to predict.** A sweep is claimed to precede reversal; a genuine break is claimed to precede
continuation. This is the load-bearing claim of the entire methodology.

**4. Numbers.** None retrievable. Sweep is already scored in this repo — the untested variants are
(ii) the N-bar window and the age filter `n - max_x1 > 1`.

---

### 1.5 Swing Failure Pattern (SFP)

**1. Aliases.** SFP; "swing failure"; close cousin of Turtle Soup (§6.4) and of the sweep above.

**2. Mechanical definition** **[CODE]** `LUX-Swing Failure Pattern (SFP)`:
```
len = 5;  ph = ta.pivothigh(len, 1);  pl = ta.pivotlow(len, 1)     // asymmetric 5-left, 1-right
bearish SFP: high > swingHigh  and  close < swingHigh
then a confirmation search backwards for an "opposite" level opposL such that low[i] < opposL
optional VOLUME VALIDATION (this is the distinctive part):
   res = '1'  (1-minute intrabar data via request.security_lower_tf)
   totalVolume   = sum of intrabar volume on the SFP bar
   outsideVolume = sum of intrabar volume of those 1-min bars whose close > swingHigh
   percent = 25 (default);  valid if  100/totalVolume * outsideVolume  <  percent
```
i.e. **the SFP is only valid if less than 25% of the bar's volume traded above the swept level.** That is
a genuinely mechanical, genuinely novel filter and it is directly testable on M1 XAUUSD — on M1 you would
use tick or M1-of-M1 substitute, or apply it on M5/M15 using M1 as the lower timeframe, which is exactly
the timeframe set this repo trades.

**3. Claimed to predict.** Reversal from the swept level. The volume filter is claimed to separate "the
level was speared and rejected" from "the level was genuinely traded through and then price came back".

**4. Numbers.** None published in the script. The script has no backtest dashboard.

---

### 1.6 Liquidity void

**1. Aliases.** Liquidity void, imbalance, "no-trade zone"; often conflated with FVG — the sources
themselves conflate them (the LuxAlgo script is literally named "Liquidity Voids (FVG)").

**2. Mechanical definition** — two different sizes of the *same* three-bar gap:

**[CODE]** `LUX-Liquidity Voids (FVG)`:
```
atr = ta.atr(144) * lqTH        // lqTH default 0.5  -> threshold = 0.5 * ATR(144)
bull = (low - high[2]) > atr and low > high[2] and close[1] > high[2]
bear = (low[2] - high) > atr and high < low[2] and close[1] < low[2]
```
**[CODE]** `LUX-Buyside & Sellside Liquidity` (same author, different threshold):
```
bull = b.l - b.h[2] > atr200 and b.l > b.h[2] and b.c[1] > b.h[2]     // atr200 = ta.atr(200), multiplier 1.0
```
So a liquidity void **is an FVG with a large-size filter**: `gap > 0.5·ATR(144)` in one script,
`gap > 1.0·ATR(200)` in the other. There is no structural difference from an FVG at all.
Anyone telling you a void is a different object than an FVG is describing a size threshold.

Fill/invalidation, `LUX-Buyside & Sellside Liquidity`: the void is drawn as 13 stacked sub-boxes and is
removed when price crosses its **midpoint** (`sign(close[1] - ba) != sign(close - ba)` or the same test
against the bar's high/low). Midpoint, not full fill.

**3. Claimed to predict.** That price returns to fill the void (a target/magnet claim), and that the void
offers no support on the way through (a *path* claim — price is claimed to travel through voids quickly).

**4. Numbers.** None published, but see §8 — the LuxAlgo Imbalance Detector *computes* fill rates live.

---

### 1.7 Trendline liquidity

**1. Aliases.** Trendline liquidity, diagonal liquidity, "trendline stops".

**2. Mechanical definition.** **No implementation found.** None of the sources read here detects it. The
prose idea — stops rest along a rising/falling line joining 2+ swing lows/highs, and price sweeps the line
rather than a horizontal level — has no published tolerance, no published minimum number of touches, and
no published rule for when the line dies. `LUX-Trend Lines` and `LUX-Trendlines with Breaks` detect
trendlines but make no liquidity claim about them.

To make it mechanical you would have to choose: number of touches (2 or 3), fit method (through pivots
exactly vs regression), tolerance band, and expiry. All four are yours to invent, which means any result
you get is a result about your choices. **Rank this low: it is the least specified concept in the list.**

**3. Claimed to predict.** Same claim as horizontal liquidity — a sweep of the line precedes reversal.

**4. Numbers.** None.

---

### 1.8 Previous day / week / month high and low

**1. Aliases.** PDH/PDL, PWH/PWL, PMH/PML; "previous session high/low"; part of "external range liquidity".

**2. Mechanical definition** **[CODE]** `LUX-Previous Highs & Lows`:
```
freq  = 'Hour' | 'Day' | 'Week' | 'Month' | 'Year'
[prev_h, prev_l, prev_t] = request.security(tickerid, tf, output(), calc_bars_count = showLast+1)
// prev_h.push(high[i]) for i = 1..showLast on the higher timeframe
```
i.e. simply the high and low of the completed prior HTF bar, no tolerance, no confirmation. Unambiguous.
`LUX-SMC` exposes the same as `show_pdhl` (daily) and weekly.

The only real decision is **which daily boundary**, and it is not innocent: TradingView's daily bar for
XAUUSD depends on the broker/exchange feed, while ICT's own convention is midnight New York (§4.5).
A "previous day high" cut at 00:00 NY and one cut at your broker's 00:00 server time are *different levels*.
Decide once, write it down, and never mix.

**3. Claimed to predict.** Magnet/target and reversal point. PDH/PDL are the most commonly named "draw on
liquidity" targets in the 2022 model (§6.1).

**4. Numbers.** None retrievable.

---

### 1.9 Session ranges: Asia range, CBDR, Flout, opening range

**1. Aliases.** Asian range, Asian box; CBDR = Central Bank Dealers Range; Flout = "flout range";
initial balance / opening range.

**2. Mechanical definition** **[CODE]** `LUX-ICT Everything` (the only script I found that implements all
three with ICT's own windows and SD increments):
```
CBDR   16:00 - 20:00 NY,  standard-deviation increments of 1
ASIA   20:00 - 00:00 NY,  standard-deviation increments of 1
FLOUT  16:00 - 00:00 NY,  standard-deviation increments of 0.5
```
The box is simply running `max(high)` / `min(low)` over the window. Projection maths (same file):
```
cbdr_diff = cbdr_hi - cbdr_lo
SD+i  =  cbdr_hi + cbdr_diff * i        // i = 1,2,3,4
SD-i  =  cbdr_lo - cbdr_diff * i
```
i.e. a "standard deviation" here is **not a statistical standard deviation** — it is one *range-multiple*
of the box, projected above the high and below the low. Do not implement `ta.stdev`. This is a naming
collision that will silently produce wrong levels if you assume the statistical meaning.

`SMC-PY` `smc.sessions()` **[CODE]** gives a different, UTC-based session table (see §4.1 for the clash).

**3. Claimed to predict.** The Asia/CBDR range high and low are claimed to be swept during London
(the "Judas swing" / manipulation leg of §4.4), and the SD projections are claimed to be the day's
objectives. ICT's often-quoted rider is that CBDR is only usable when the range is small (he quotes a
40-pip cap on FX majors); no such number exists for gold in anything I could reach.

**4. Numbers.** None retrievable.

---

### 1.10 Inducement (IDM)

**Prioritised: not previously scored in this repo.**

**1. Aliases.** IDM, inducement, "the trap before the entry", sometimes "the retail level". ICT-native
speakers say inducement; SMC/"how-to-trade-forex" speakers say IDM. Sources agree the mechanic is
identical **[SEARCH]**.

**2. Mechanical definition.** There is exactly one clean published implementation and it is very precise:

**[CODE]** `LUX-Market Structure with Inducements & Sweeps` (author LuxAlgo). Two swing detectors run
simultaneously at two lengths:
```
len      = 50   // 'CHoCH Detection Period'  -> major swings
shortLen = 3    // 'IDM Detection Period'    -> minor swings

swings(len):
    upper = ta.highest(len); lower = ta.lowest(len)
    os := high[len] > upper ? 0 : low[len] < lower ? 1 : os[1]
    top = (os==0 and os[1]!=0) ? high[len] : na       // confirmed len bars later
    btm = (os==1 and os[1]!=1) ? low[len]  : na

[top, topx, btm, btmx]    = swings(50)     // major
[stop,stopx,sbtm,sbtmx]   = swings(3)      // minor
stopy = fixnan(stop); sbtmy = fixnan(sbtm) // last minor high / minor low

// trend state os: 1 = bullish, 0 = bearish, flipped by CHoCH:
if close > topy and not top_crossed:  os := 1; top_crossed := true
if close < btmy and not btm_crossed:  os := 0; btm_crossed := true
// on a flip, reset:  max := high, min := low, max_x1 := n, min_x1 := n,
//                    stop_crossed := false, sbtm_crossed := false

// ===== BULLISH INDUCEMENT =====
if low < sbtmy and not sbtm_crossed and os == 1 and sbtmy != btmy:
        -> IDM at price sbtmy;  sbtm_crossed := true

// ===== BULLISH BOS, GATED ON THE INDUCEMENT =====
if close > max and sbtm_crossed and os == 1:
        -> BOS at max;  sbtm_crossed := false      // re-arm for the next leg

// bearish mirror: IDM when high > stopy and not stop_crossed and os == 0 and stopy != topy
//                 BOS  when close < min and stop_crossed and os == 0
```
Read that carefully, because it encodes the whole claim:

- **An inducement is the most recent minor (3-bar) swing low inside an up-leg, taken out.** Not any
  pullback — the *last* minor extreme before the push.
- `sbtmy != btmy` — the minor low must **not be the same price as the major swing low**. That is what
  separates "inducement" from "the structural low"; taking out the structural low would be a CHoCH,
  not an inducement.
- **`sbtm_crossed` gates BOS.** In this implementation a break of the high is only labelled BOS *if the
  inducement was taken first*. A break of the high without a prior inducement sweep is not printed at all.
  This is a strong, falsifiable claim and it is the one worth testing: **do BOS events preceded by an
  inducement sweep behave differently from BOS events that were not?** That is exactly the form of the
  repo's standing rule — a filter earns its place only if the trades it refuses are worse.

**[SEARCH]** prose confirms the same rule in words: "inducement is the first valid pullback inside the
leg that produced a BOS or CHoCH; mark the high or low of that pullback as the IDM level"
(sources: https://www.luxalgo.com/library/concept/inducement/ ,
https://tradingfinder.com/education/forex/inducement/ ,
https://www.equiti.com/sc-en/news/trading-ideas/inducement-in-smc-explained-how-smart-money-traps-work/ ,
https://liquidityscan.io/blog/what-is-inducement-idm-in-smart-money-concepts ,
https://forexmt4indicators.com/what-is-inducement/ ).

**Ambiguity flag: "first" vs "last".** The prose says *first* valid pullback in the leg; the code uses the
*most recent* minor swing (which, because `sbtm_crossed` is reset on each BOS, is effectively the first
pullback after the previous BOS). These coincide in a clean leg and diverge in a messy one. Code both,
they are cheap.

**3. Claimed to predict.** (a) That price will take the IDM level *before* it goes to the real target —
so entering before the IDM is taken is the mistake the concept exists to prevent. (b) That an order block
or FVG is only "valid" if the inducement below/above it has already been swept. (c) That a BOS without a
prior inducement is untrustworthy.

**4. Numbers.** None retrievable. Every source in the list is an education page or an indicator vendor.

---

### 1.11 Internal range liquidity vs external range liquidity (IRL / ERL)

**1. Aliases.** IRL/ERL; "internal liquidity" = the FVGs/OBs *inside* a dealing range; "external
liquidity" = the swing high/low that bound the range.

**2. Mechanical definition.** **Under-sourced.** No implementation found; the search that would have
resolved it failed. The operational content of the idea is only this: given a range defined by the last
major swing high and swing low, *external* liquidity is those two boundary prices, and *internal*
liquidity is every unmitigated PD array between them. The claimed sequence — "price alternates: it takes
external liquidity, then delivers to internal, then back to external" — has no published mechanical test.

Do not code this as a named concept. Code the two ingredients (boundary levels; unmitigated arrays inside)
which you get for free from §1.8 and §3, and the "alternation" claim becomes a testable transition matrix
rather than a label.

**3. Claimed to predict.** Sequencing of targets.

**4. Numbers.** None.

---

## 2. STRUCTURE

### 2.1 Swing point definitions — 3 bars vs 5 bars vs N-bar rolling extreme

This is the hidden variable under everything else in §2 and §3. There are **three genuinely different
mechanisms** in use, not one mechanism with a tunable length.

**(A) Fractal / pivot, symmetric, k bars each side.** `ta.pivothigh(k, k)`: bar `i` is a swing high if its
high is the highest of `[i-k, i+k]`. Confirmed `k` bars late.
- `k = 3` in `LUX-SMC` for equal highs (`eq_len = 3`).
- `k = 5` in `LUX-Market Structure CHoCH_BOS (Fractal)` (`length = 5, minval 3`) and `LUX-Liquidity Sweeps`
  and `LUX-SMT Divergences` (`length = 3, minval 2`).

**(B) Fractal, asymmetric.** `ta.pivothigh(k, 1)` — k bars left, **1 bar right**. Confirmed 1 bar late.
- `LUX-Buyside & Sellside Liquidity`: `ta.pivothigh(7, 1)`.
- `LUX-Swing Failure Pattern (SFP)`: `ta.pivothigh(5, 1)`.
- `LUX-ICT Concepts`: `ta.pivothigh(3, 1)`.
This is a materially different object: it detects far more swings, and it is much less laggy. Anyone
comparing "3-bar vs 5-bar swings" without noticing the left/right asymmetry is comparing the wrong things.

**(C) Rolling-extreme state machine (LuxAlgo's house style).** **[CODE]** `LUX-SMC`, `LUX-ICT Concepts`,
`LUX-Order Blocks & Breaker Blocks`, `LUX-Market Structure with Inducements & Sweeps`:
```
upper = ta.highest(len); lower = ta.lowest(len)
os := high[len] > upper ? 0 : low[len] < lower ? 1 : os[1]
top = (os == 0 and os[1] != 0) ? high[len] : na
btm = (os == 1 and os[1] != 1) ? low[len]  : na
```
This emits **one alternating high, low, high, low sequence** — it cannot emit two consecutive highs. A
pivot detector can and does. That single property is why LuxAlgo's BOS/CHoCH logic is so short and why
`SMC-PY` needs 40 lines of de-duplication to reproduce it.

**(D) Three-bar ICT fractal with the ≥ / ≤ tie rule.** **[CODE]** `LUX-Pure Price Action Structures`:
```
swing high: prevPrice < midPrice and midPrice >= lastPrice     // high[2] < high[1] >= high[0]
swing low : prevPrice > midPrice and midPrice <= lastPrice
```
Note `>=` / `<=`: a flat second bar still counts. Most implementations use strict `>`; this one does not.
On M1 gold, where equal highs to the tick are common, that choice changes the swing count noticeably.

**(E) Terms — short / intermediate / long.** **[CODE]** same file, and this is the actual ICT definition
of "internal vs external structure":
```
ST (short term)        = the 3-bar fractal above, on price
IT (intermediate term) = the 3-bar fractal applied to the sequence of ST swings
LT (long term)         = the 3-bar fractal applied to the sequence of IT swings
```
Fractals of fractals. `SNIPER` and `LUX-ICT Institutional Order Flow (fadi)` implement the same
three-tier scheme. Labels emitted: ST-HH / ST-HL / ST-LH / ST-LL, then IT-, then LT-.

**Default lengths actually shipped**, for reference when you pick yours:
`SMC-PY swing_length = 50` (and internally doubled to 100 for the rolling window);
`LUX-SMC` swing = 50, **internal = 5** (hardcoded `n - 5`);
`LUX-Order Blocks & Breaker Blocks` = 10; `LUX-Unicorn` = 10; `LUX-Turtle Soup MSS` = 10;
`LUX-Market Structure with Inducements` = 50 major / 3 minor.

---

### 2.2 Break of Structure (BOS)

**1. Aliases.** BOS, MSB (market structure break), "continuation break".

**2. Mechanical definition.**

*(a) Close through the last swing, trend-agreeing* **[CODE]** `LUX-SMC`:
```
if ta.crossover(close, top_y) and top_cross:
    choch = (trend < 0)          // if the prior trend was down -> CHoCH
    label = choch ? 'CHoCH' : 'BOS'
    top_cross := false; trend := 1
```
So BOS and CHoCH are **the same event with a different label**, decided purely by the prior `trend` state.

*(b) Four-swing pattern test* **[CODE]** `SMC-PY` `bos_choch()`. Over the last four alternating swings
`[-1,1,-1,1]` (low, high, low, high):
```
bullish BOS  if  level[-4] < level[-2] < level[-3] < level[-1]
bullish CHoCH if level[-1] > level[-3] > level[-4] > level[-2]
```
Both then require the level to actually be *broken later*: `close > level` (or `high > level` if
`close_break=False`), searched from `i+2` onward; unbroken candidates are deleted, and an older
still-unbroken structure that is straddled by a newer one is deleted too. This is a much stricter,
pattern-based definition and it will not agree with (a).

*(c) Inducement-gated BOS* — see §1.10. LuxAlgo's inducement script refuses to print BOS unless the
inducement was swept first.

**Wick vs close.** `SMC-PY` exposes `close_break=True/False`. LuxAlgo always uses close. This is a real
fork: on M1 XAUUSD wick-breaks are far more numerous.

**3. Claimed to predict.** Continuation of the existing trend.

**4. Numbers.** None retrievable. BOS is already scored in this repo; the untested variants are the
four-swing pattern form (b) and the inducement gate.

---

### 2.3 Change of Character (CHoCH) — and is MSS a different thing?

**1. Aliases.** CHoCH, CHOCH, change of character; MSS = market structure shift; MSB/MSS pairing.

**2. Mechanical definition.** Same event as BOS but against the prior trend, per (a) and (b) above.

**Is MSS different from CHoCH? The code says: no.** Three independent scripts equate them:

- **[CODE]** `LUX-Market Structure (Breakers)`: on `close > ph and not phcross`, the label printed is
  `os == -1 ? 'MSS' : 'MSB'`. So **MSS = the trend-flipping break, MSB = the continuation break** — which
  is exactly BOS/CHoCH with the names swapped in.
- **[CODE]** `LUX-Pure Price Action Structures`: label is `termText + '-MSS'` when
  `marketStructure.type == (isBullish ? -1 : 1)`, else `termText + '-BOS'`. Same test.
- **[CODE]** `LUX-ICT Silver Bullet` and `LUX-ICT Concepts` use only `MSS` and `BOS` and never the word
  CHoCH:
```
// MSS Bullish
close > aZZ.y.get(iH) and aZZ.d.get(iH) == 1 and MSS_dir < 1  ->  MSS_dir := 1
// BOS (continuation)
MSS.dir == 1 and close > aZZ.y.get(iH)                        ->  BOS
```

**Conclusion to carry into code: MSS and CHoCH are the same object under two vocabularies (ICT says MSS,
SMC-influencers say CHoCH). Do not implement two features.** The only defensible distinction anyone
makes is a *soft* one — that "MSS" additionally requires displacement (§2.7) through the level whereas
"CHoCH" does not. Nothing enforces that in code except by pairing the MSS with a displacement filter,
which is what the 2022 model does (§6.1). If you want to test "MSS ≠ CHoCH", the testable form is
**"break-against-trend WITH displacement" vs "break-against-trend WITHOUT displacement"**.

**3. Claimed to predict.** The first warning of a reversal — the earliest tradable evidence the trend has
turned. In every entry model in §6 the CHoCH/MSS is the *confirmation* step, never the entry itself.

**4. Numbers.** None retrievable. CHoCH already scored here.

---

### 2.4 Internal vs external (swing) structure

**1. Aliases.** Internal structure / minor structure / short-term structure vs swing structure / major /
external structure.

**2. Mechanical definition** **[CODE]** `LUX-SMC` — two parallel structure engines at two lengths:
```
swing structure   : swings(length)      length = 50 (input)
internal structure: swings(5)           hardcoded, itop_x = n - 5
```
and a "confluence filter" that only applies to internal breaks:
```
if ifilter_confluence:
    bull_concordant := high - math.max(close, open) > math.min(close, open - low)
```
i.e. **the breaking bar's upper wick must exceed its lower wick** for a bullish internal break to count.
(Read literally, `math.min(close, open - low)` is almost certainly a bracket bug in the published source —
it should read `math.min(close, open) - low`. It is in the shipped script. If you port it, port the
*intended* version and note the discrepancy.)

Additional guard: `top_y != itop_y` — an internal break is suppressed when the internal level coincides
with the swing level, so the same break isn't printed twice.

The `LUX-Pure Price Action Structures` ST/IT/LT scheme (§2.1E) is the same idea done as fractals-of-fractals.

**3. Claimed to predict.** Internal structure is claimed to give earlier entries inside a swing leg;
external structure is claimed to give the bias. The standard rule is "trade internal structure in the
direction of external structure".

**4. Numbers.** None retrievable.

---

### 2.5 Protected high / protected low ("strong" and "weak")

**1. Aliases.** Protected high/low; strong high / weak high; strong low / weak low; "the low that caused
the BOS"; "unmitigated swing".

**2. Mechanical definition** **[CODE]** `LUX-SMC` — this is the only implementation I found and it is
trivially simple:
```
label = trend > 0 ? 'Strong Low' : 'Weak Low'      // on the trailing minimum
label = trend < 0 ? 'Strong High' : 'Weak High'    // on the trailing maximum
trail_dn := math.min(low, trail_dn); trail_up := math.max(high, trail_up)
```
That is: **the current trailing extreme is "strong" if it is on the correct side of the current trend and
"weak" otherwise.** A low made during an uptrend is a strong low (= protected); the same low in a
downtrend is a weak low (= expected to be taken).

The richer folk definition — "a protected high is the high whose break caused the last BOS, and it must
not be violated for the bias to survive" — is not implemented anywhere I found, but it *is* mechanical
and easy: store `top_y` at the moment of a bullish BOS/CHoCH; the bias is invalidated by a close back
below the swing low that originated that break.

**3. Claimed to predict.** The strong/protected extreme is claimed to hold; the weak one is claimed to be
taken. This is the same content as inducement (§1.10) viewed from the other end.

**4. Numbers.** None retrievable.

---

### 2.6 Failure swing

**1. Aliases.** Failure swing (Wyckoff/Dow origin), failed break, "failure to make a new high".

**2. Mechanical definition.** No ICT-specific implementation found. The Dow-theory version is mechanical:
in an uptrend, a swing high that fails to exceed the prior swing high, followed by a break of the
intervening swing low. In LuxAlgo's ST/IT/LT labels this is exactly the transition
`ST-HH → ST-LH` followed by a bearish break, and in `SMC-PY` it is the CHoCH pattern
`level[-1] < level[-3] < level[-4] < level[-2]`. **Treat "failure swing" as an alias for CHoCH-with-a-lower-high,
not as a separate feature.**

**3. Claimed to predict.** Reversal.

**4. Numbers.** None.

---

### 2.7 Displacement

**1. Aliases.** Displacement, energetic move, expansion candle, "the drop/rip".

**2. Mechanical definition** — three competing, all published, all different:

*(a) Body vs a rolling stdev of bodies, plus a required FVG* **[CODE]**
`LUX-ICT Institutional Order Flow (fadi)`:
```
body = math.abs(open - close)
std  = ta.stdev(math.abs(open - close), displacement_length)      // length default 100
displacement_factor = 2         // options 1,2,3,4  ("Displacement Strength")
displacement_fvg    = true      // "Require FVG", ON by default
condition = displacement_fvg
    ? (candle_range[1] > std[1] * displacement_factor and fvg)
    : (candle_range > std)
```
So: **the bar's range exceeds 2 × stdev(|open−close|, 100) AND the three-bar FVG exists.**
Note the mixed units — range compared against a stdev of *bodies*. That is what the shipped code does.

*(b) Wick-suppression + above-average body* **[CODE]** `LUX-ICT Concepts`:
```
perc_Body = 0.36
L_body   = (high - max(open,close)) < body * perc_Body  and  (min(open,close) - low) < body * perc_Body
L_bodyUP = body > meanBody and L_body and close > open
L_bodyDN = body > meanBody and L_body and close < open
```
i.e. **both wicks smaller than 36% of the body, and the body bigger than the running mean body.**
A "clean" candle, not necessarily a big one.

*(c) Displacement as "an FVG happened"* — the loosest and the most common in prose: any three-bar gap
counts as displacement. This is what most 2022-model tutorials actually mean.

**These three will disagree constantly.** (b) rejects a large bar with a big wick; (a) accepts it.
Displacement is already scored in this repo — check which of the three the existing scorer implements,
because the phrase alone does not pin it down.

**3. Claimed to predict.** That the move is institutional rather than noise, and therefore that the
structure break it accompanies is real and the FVG it leaves will be respected.

**4. Numbers.** None retrievable.

---

### 2.8 CISD — Change In State of Delivery

**1. Aliases.** CISD; sometimes conflated with MSS.

**2. Mechanical definition** **[CODE]** `LUX-One Shot One Kill ICT [TradingFinder] Liquidity MMXM + CISD OTE`:
```
BarBackCheck = 5      // how many bars back to find the opposing run
CISDVal      = 25     // level validity, in bars
```
and, stated in prose inside `SNIPER` and in `Ultra_Alpha_Mentor` (RetailBeastFX):
> "CISD = body close past the **open of the first candle** in the opposite sequence; ignore wicks."

So: find the last run of consecutive down-close candles; the CISD level is the **open of the first candle
of that run**; the CISD fires when a candle **closes** above it. Mirror for bearish. It is a
close-through-an-open test, deliberately wick-blind, and it is *earlier* than an MSS because it does not
wait for a swing to be taken.

**3. Claimed to predict.** The earliest confirmation that delivery has flipped; used as the entry trigger
in place of MSS by traders who find MSS too late.

**4. Numbers.** None retrievable. **This one is cheap to code and genuinely distinct from everything
already scored here** — worth putting in the queue.

---

### 2.9 Swing Breakout Sequence (SBS)

**1. Aliases.** SBS; 1-2-3-4-5 sequence; close relative of a Wyckoff spring / QM pattern.

**2. Mechanical definition** **[CODE]** `LUX-Swing Breakout Sequence`:
```
pivotLengthInput    = 5        // swing length
internalLengthInput = 2        // internal length
point4Beyond2Input  = false    // whether point 4 must exceed point 2
detectPoint5Input   = true
strictModeInput     = true     // "Require Equal H/L at Point 5"
strictThresholdInput= 0.50 * ta.atr(200)
```
Five alternating swing points; point 5 must be within `0.5·ATR(200)` of point 3 (the "equal H/L" strict
mode). Entry is at point 5, target beyond point 4.

**3. Claimed to predict.** Continuation after the point-5 retest.

**4. Numbers.** None.

---

## 3. PD ARRAYS AND ZONES

### 3.1 Order block — four competing definitions

**1. Aliases.** OB, order block, bullish/bearish OB, supply/demand zone (loosely), "the last down candle".

**2. Mechanical definitions.** This is the most contested object in the whole methodology. Four
distinct, published, incompatible rules:

**(A) Last opposing candle before the move — pure candle pattern** **[CODE]** `SOB` (makuchaku & eFe):
```
isObUp(i)   = isDown(i+1) and isUp(i)   and close[i] > high[i+1]
isObDown(i) = isUp(i+1)   and isDown(i) and close[i] < low[i+1]
// bullish OB box = [ high[2] , min(low[2], low[1]) ]  drawn from bar_index-2
```
No structure required at all. Just: a down candle, then an up candle that closes above the down candle's
high. Enormous count. This is what most retail "order block indicators" do.

**(B) Extreme candle inside the structure interval, ATR-filtered** **[CODE]** `LUX-SMC` `ob_coord()`:
```
ob_threshold = (ob_filter == 'Atr') ? ta.atr(200) : ta.cum(high-low)/n     // 'Atr' or 'Cumulative Mean Range'
// on a bullish structure break at swing index loc, scan i = 1 .. (n-loc)-1:
//     if (high[i] - low[i]) < ob_threshold[i] * 2:
//         min := math.min(low[i], min);  max := (min == low[i]) ? high[i] : max;  idx := ...
// bullish OB = [max, min] at bar idx     (the LOWEST LOW in the leg, among bars narrower than 2*ATR)
```
Two things to notice: (i) the OB is **the lowest-low bar of the leg**, regardless of its colour; (ii) the
`< 2·ATR` filter **excludes the big displacement candle itself** — deliberately, so the block sits at the
origin of the move rather than in it.

**(C) Lowest-low bar in the leg, no ATR filter, structure-confirmed** **[CODE]**
`LUX-Order Blocks & Breaker Blocks`:
```
length = 10;  [top, btm] = swings(10)
max = useBody ? math.max(close,open) : high      // 'Use Candle Body' toggle
min = useBody ? math.min(close,open) : low
if close > top.y and not top.crossed:
    top.crossed := true
    minima = max[1]; maxima = min[1]; loc = time[1]
    for i = 1 to (n - top.x) - 1:
        minima := math.min(min[i], minima)
        maxima := (minima == min[i]) ? max[i] : maxima
        loc    := (minima == min[i]) ? time[i] : loc
    bullish_ob.unshift(ob.new(maxima, minima, loc))
```
Same "lowest low in the leg" idea as (B) without the width filter, plus a body/wick toggle.

**(D) Structure-break-triggered, with volume and strength** **[CODE]** `SMC-PY` `smc.ob()`:
```
# on close > high[last_swing_high] and that swing not yet crossed:
#   default OB bar = the previous bar
#   but if there is more than 1 bar since the swing high, take the bar with the LOWEST LOW
#   in (last_top_index, close_index), ties -> LAST occurrence
#   OBVolume  = volume[i] + volume[i+1] + volume[i+2]
#   Percentage = min(highVolume, lowVolume) / max(highVolume, lowVolume)
# mitigation: not close_mitigation -> low < bottom ; close_mitigation -> min(open,close) < bottom
#   on mitigation the OB becomes a BREAKER (see 3.2); the breaker is destroyed when high > top
```

**Where they disagree, concretely.** (A) fires on any two-candle engulf. (B),(C),(D) all require a
structure break and all pick "the extreme bar of the leg". (B) alone excludes wide bars. (C) alone offers
body-only boxes. (D) alone attaches volume. **The "last down-close candle before displacement" definition
that ICT actually teaches is implemented by NONE of them** — the closest is `LUX-ICT Unicorn Model`, which
does exactly that (see 3.13): it walks back up to 5 bars from the swing point to find the first candle
with `close < open`.

**Mitigation / invalidation** also differs: `LUX-SMC` deletes the box when the top/bottom is broken;
`LUX-Order Blocks & Breaker Blocks` flips it to a breaker instead; `SMC-PY` flips to breaker then deletes.

**3. Claimed to predict.** That price returning into the block reverses from it. Freshness ("untested"
blocks are better) is universally claimed and universally unquantified.

**4. Numbers.** None retrievable. OB is already scored here — which of A/B/C/D is scored matters a lot.

---

### 3.2 Breaker block

**Prioritised: not previously scored.**

**1. Aliases.** Breaker, breaker block, BRB, "flipped order block", polarity change.

**2. Mechanical definition** **[CODE]** `LUX-Order Blocks & Breaker Blocks` — a breaker is a *state* of an
order block, not a separate detection:
```
// bullish OB lifecycle:
if not element.breaker:
    if math.min(close, open) < element.btm:        // body closes below the block's bottom
        element.breaker := true; element.break_loc := time
else:
    if close > element.top:                        // reclaimed -> destroy it
        bullish_ob.remove(i)
    else if i < showBull and top.y < element.top and top.y > element.btm:
        bull_break_conf := 1                       // a new swing high forming INSIDE the old block
                                                   // = confirmed polarity change (prints ▼)
```
So: **a bullish OB whose body-bottom is closed through becomes a bearish breaker; it is confirmed when a
subsequent swing high forms inside its range; it dies when price closes back above its top.**

`SMC-PY` implements the same flip (`breaker[idx] = True` on `low < bottom`, destroyed on `high > top`).

**Breaker vs mitigation block — the distinguishing condition** **[SEARCH]**
(https://ghosttraders.co/breaker-blocks-vs-mitigation-blocks-key-differences/ ,
https://fxopen.com/blog/en/mitigation-blocks-how-may-traders-identify-and-trade-them/ ,
https://www.luxalgo.com/library/concept/breaker-block/ ,
https://fxnx.com/en/blog/ict-mitigation-vs-breaker-block-trader-s-guide ,
https://tradingstrategyguides.com/day-12-breaker-blocks-mitigation-blocks-explained-ict-smc-deep-dive/ ):

> "The critical detail that defines a breaker: price must have **swept liquidity** — made a new high or new
> low beyond the previous swing — before the reversal. In a mitigation block scenario, there is **no
> liquidity sweep first**: price forms a **lower high** — it never makes the new higher high."

That is a clean, codeable discriminator (§3.3).

**3. Claimed to predict.** That price retesting the broken block from the other side reverses — i.e. the
block has changed polarity. Breakers are the highest-ranked array in most published hierarchies.

**4. Numbers.** None retrievable.

---

### 3.3 Mitigation block

**Prioritised: not previously scored.**

**1. Aliases.** Mitigation block, MB; "unswept breaker".

**2. Mechanical definition.** **No dedicated implementation found in any script I read.** It exists only
in prose. But the prose is precise enough to code, and it is a strict sub-case of the breaker:

```
Bearish mitigation block (from the [SEARCH] sources in 3.2):
  1. an established up-leg with swing high H1 and swing low L1
  2. price rallies again but makes a LOWER HIGH H2 < H1        <-- no liquidity sweep. this is the whole difference
  3. price then closes below L1 (structure broken to the downside)
  4. the mitigation block = the zone between the broken low L1 and the lower high H2
  5. it is bearish on the retest
Bullish is the mirror: higher low that never sweeps L1, then close above H1.
```
Compare: a **breaker** requires step 2 to be `H2 > H1` (the sweep). Everything else is identical.
So in code they are one detector with a boolean: `swept = (H2 > H1)` → breaker, else → mitigation block.

**Ambiguity flag.** A minority of writers use "mitigation block" to mean simply "the order block price
returns to in order to mitigate positions", i.e. an ordinary order block. If a source uses it that way,
it is not describing the object above. Check which meaning a source is using before importing its claim.

**3. Claimed to predict.** Same as breaker (reversal on retest), but the sources are explicit that it is
considered the *weaker* of the two precisely because no liquidity was taken.
`https://fxnx.com/en/blog/ict-mitigation-vs-breaker-block-trader-s-guide` is titled "One Pays, One Traps",
i.e. a vendor asserting a difference in edge — with no data.

**4. Numbers.** None. And note the source asserting the difference is selling a product.

**Testable form for this repo:** detect the shared pattern once, split by `swept`, and check whether the
swept branch outperforms the unswept branch. That is a direct test of the community's central claim about
these two objects, and it is exactly the "does the filter refuse worse trades" test in CLAUDE.md.

---

### 3.4 Propulsion block

**Prioritised: not previously scored.**

**1. Aliases.** Propulsion block, PB.

**2. Mechanical definition.** One implementation found, and it is one author's:
**[CODE]** `SNIPER`, tooltip verbatim:
> "Propulsion Blocks — an order block that forms **inside a live block of the same direction**: the
> algorithm returning to its own level to continue delivery rather than to reverse."

So: `new_OB.dir == existing_OB.dir` and `new_OB` overlaps `existing_OB` and `existing_OB.active`.
That is codeable as written.

**3. Claimed to predict.** Continuation, not reversal. It is explicitly the *continuation* member of the
block family: price returns to its own prior block and pushes on from it.

**4. Numbers.** None. Single-author definition — treat as a hypothesis, not a standard.

---

### 3.5 Rejection block

**1. Aliases.** Rejection block, RJB, RB; "wick block"; overlaps heavily with "rejection wick", which this
repo already scores.

**2. Mechanical definition** — three published versions, and the difference is *where the box is*:

**(A) Wick-of-the-trapped-candle** **[CODE]** `SOB`:
```
isDownRjb1 = isObDown(1) and (high[1] < (close[2] + 0.2*(high[2]-close[2])))
             // box = [ high[2] , close[2] ]  -> the UPPER WICK of the trapped candle,
             //   and <50% (here 20%) of that wick was covered by the signal candle
isDownRjb2 = isObDown(1) and (high[1] > high[2])
             // box = [ high[1] , open[1] ]   -> the wick of the SIGNAL candle
bearRJB = isDownRjb1 or isDownRjb2
```
**(B) Shape-filtered pivot wick that swept a level** **[CODE]** `RB-UALGO`:
```
minWickToBody  = 2.0     // dominant wick >= 2.0 * body
minDomWickPct  = 0.55    // dominant wick >= 55% of the bar's range
maxOppWickPct  = 0.30    // opposite wick <= 30% of range
maxBodyPct     = 0.60    // body <= 60% of range
sweep test (dir = -1):  high > level + minSweepTicks*mintick  and  close < level
sweepType 'Wick sweep': additionally  open < level            // open AND close inside
zone models: 'Wick-to-Body' (default) | 'Open-to-Extreme' | 'Full Candle' | 'Body'
```
**(C)** **[CODE]** `SNIPER`: `rbWickRatio = 0.55` (wick/range), `rbMinWickATR = 0.35` (wick ≥ 0.35·ATR),
box = "the wick alone, body extreme to wick extreme". Numerically almost identical to (B)'s defaults.

A fourth, from `Ultra_Alpha_Mentor` (RetailBeastFX) quoting TTrades: *"wick > 50% of range → Rejection Block"* —
the loosest version, one condition.

**Consensus across (B) and (C): dominant wick ≥ 55% of the bar's range, and the bar swept a level.**
That is a reasonable canonical form.

**3. Claimed to predict.** Reversal; the wick is claimed to mark where orders were filled and rejected,
so price returning into the *wick* (not the body) reverses again.

**4. Numbers.** None. Rejection wick already scored here; the untested increments are (i) restricting to
wicks that swept a registered level, and (ii) using the wick body-to-extreme as a *zone* rather than the
bar as a signal.

---

### 3.6 Fair Value Gap (FVG)

**1. Aliases.** FVG, imbalance, three-candle gap, BISI (buyside imbalance sellside inefficiency) /
SIBI (sellside imbalance buyside inefficiency), liquidity void when large (§1.6).

**2. Mechanical definition.** The core is agreed; the *filters* are not.

**Core, everywhere:**
```
bullish FVG: low[0] > high[2]        // gap between bar -2's high and bar 0's low
bearish FVG: high[0] < low[2]
zone = [high[2], low[0]] (bull) or [high[0], low[2]] (bear)
```

**Variant differences:**

| source | extra conditions | threshold |
|---|---|---|
| `LUX-SMC` **[CODE]** | `close[1] > high[2]` (middle bar must close beyond) | `delta_per > threshold`, `delta_per = (close[1]-open[1])/open[1]*100`; auto threshold `= ta.cum(abs(delta_per))/n * 2` |
| `LUX-Fair Value Gap` **[CODE]** | `close[1] > high[2]` | `(low - high[2]) / high[2] > threshold`; auto `= ta.cum((high-low)/low)/bar_index` |
| `LUX-Inversion FVG` **[CODE]** | `close[1] > high[2]` | `abs(low - high[2]) > ta.atr(200) * 0.25` |
| `LUX-Liquidity Voids` **[CODE]** | `close[1] > high[2]` | `gap > 0.5 * ta.atr(144)` |
| `SMC-PY` **[CODE]** | **`close > open`** on the *current* bar, and it uses `shift(1)`/`shift(-1)` so the gap is around the middle bar | none |

Two real forks:
- **middle-bar close condition.** Every LuxAlgo script requires `close[1] > high[2]`; `SMC-PY` instead
  requires the middle candle to be bullish (`close > open`). These are different tests.
- **`SMC-PY` indexes differently**: it centres the FVG on the middle bar (`high.shift(1) < low.shift(-1)`),
  so its FVG is reported one bar earlier than the LuxAlgo convention and **is not causal** —
  `shift(-1)` looks forward. If you port `SMC-PY` verbatim into a backtest you introduce lookahead.
  **Flagging this loudly: `SMC-PY.fvg()` is not tradeable as written.**

**Mitigation.** `SMC-PY`: bullish FVG mitigated when `low[i+2:] <= top`, i.e. first touch of the far edge.
`LUX-Fair Value Gap` tracks `max_bull_fvg`/`min_bull_fvg` and counts mitigations for its dashboard.

**Consecutive-FVG merging** is offered by `SMC-PY` (`join_consecutive=True`, merge to `max(top), min(bottom)`)
and by `LUX-ICT Concepts` (extends the existing box when `imbalanceUP[1]` is also true). Whether you merge
changes the count materially in fast gold moves.

**3. Claimed to predict.** Price returns to fill it (magnet), and reverses from it on the retest (support/
resistance). Both claims, from the same object, which is worth remembering when a result is ambiguous.

**4. Numbers.** None retrievable. But see §8 — `LUX-Imbalance Detector` and `LUX-Fair Value Gap` both ship
a dashboard that *computes* fill percentage from your own data, which is the honest way to get this number.

---

### 3.7 Consequent encroachment (CE)

**1. Aliases.** CE, consequent encroachment, "the 50% of the gap", midline.

**2. Mechanical definition.** Unambiguous: `CE = (top + bottom) / 2` of any FVG / gap / range.
**[CODE]** `LUX-SMC` splits every FVG into two boxes at `math.avg(src_l, src_h2)`.
**[CODE]** `LUX-ICT Implied FVG` plots `math.avg(bull_top, bull_btm)` as the "average".
**[CODE]** `LUX-Inversion FVG` draws `mid` as a dashed line on every inversion.
**[CODE]** `SNIPER` tooltip: *"the 50% line of every live gap. This is where ICT entries are actually
taken, not the far edge — the entry engine arms on a tap that reaches it, and confirms on a close that
reclaims it."*

**3. Claimed to predict.** That the *half* of the gap is the real reaction point, so a 50% fill is a
complete fill for entry purposes. This is a directly testable and cheap claim: **for gold, does price
reverse more reliably from the CE than from the proximal edge or the distal edge?** Three candidate entry
prices from one detected object.

**4. Numbers.** None retrievable.

---

### 3.8 IFVG — and the fact that "IFVG" means TWO DIFFERENT THINGS

**Prioritised: not previously scored. And this is the single biggest naming trap in the whole document.**

**Meaning 1: INVERSION Fair Value Gap.** An FVG that was traded through and now acts in the opposite
direction.
**[CODE]** `LUX-Inversion Fair Value Gaps (IFVG)`:
```
atr = nz(ta.atr(200)*0.25, ta.cum(high-low)/(bar_index+1))
fvg_up   = (low > high[2]) and (close[1] > high[2])           ; requires abs(low-high[2]) > atr
fvg_down = (high < low[2]) and (close[1] < low[2])            ; requires abs(low[2]-high) > atr
// INVERSION occurs when the body closes through the gap:
//   bullish FVG (dir=1)  inverts when  min(open,close) < value.bot
//   bearish FVG (dir=-1) inverts when  max(open,close) > value.top
// on inversion the zone flips direction (state := 1, dir := -dir)
// SIGNAL, bearish (an inverted bullish gap now acting as resistance):
//   dir == -1 and state == 1 and close < bx_bot
//   and (wick ? high : close[1]) >= bx_bot and (wick ? high : close[1]) < bx_top
// SIGNAL, bullish: mirror
// the inverted zone is DESTROYED when max(open,close) > bx_top (bear) / min(open,close) < bx_bot (bull)
```
Note `signal_pref = 'Close' | 'Wick'` — whether the retest is judged on the wick or on the prior close.
Both ship.

**Meaning 2: IMPLIED Fair Value Gap.** A *different pattern entirely* — a single large candle whose two
neighbouring wicks imply an inefficiency, with **no actual gap present.**
**[CODE]** `LUX-ICT Implied Fair Value Gap (IFVG)`:
```
thr = 0.30                              // 'Shadow Threshold %'
r = high - low;  b = abs(close - open)
bull_top = avg(min(close,open), low)                  // midpoint of the CURRENT bar's lower wick
bull_btm = avg(max(close[2],open[2]), high[2])        // midpoint of bar -2's upper wick
bull_ifvg = b[1] > math.max(b, b[2])                  // middle bar has the biggest body of the three
    and low < high[2]                                 // NOTE: the bars OVERLAP. there is no gap.
    and (min(close,open) - low)  / r > thr            // current lower wick > 30% of range
    and (high[2] - max(close[2],open[2])) / r > thr   // bar -2 upper wick > 30% of range
    and bull_top > bull_btm
// zone = [bull_top, bull_btm], i.e. between the two wick MIDPOINTS
```
**These are not variants of one another.** Meaning 1 is a reversal-of-polarity concept; meaning 2 is a
pattern-recognition concept about wick midpoints. Both are published by the same vendor under the same
acronym. **If you implement "IFVG" you must say which.** In the wild, "IFVG" almost always means
Inversion; "Implied FVG" is the rarer one and is usually spelled out.

**3. Claimed to predict.** Inversion IFVG: reversal at the retest of the flipped gap — this is one of the
most commonly published ICT entry triggers and is the mechanism behind "the gap that failed becomes
resistance". Implied FVG: same as an FVG (a zone price should react to).

**4. Numbers.** None retrievable.

---

### 3.9 Balanced Price Range (BPR)

**Prioritised: not previously scored.**

**1. Aliases.** BPR, balanced price range; "double gap"; occasionally "overlapping FVG".

**2. Mechanical definition** **[CODE]** `LUX-ICT Concepts` — and it is short:
```
// bxUP = most recent BULLISH FVG box, bxDN = most recent BEARISH FVG box
if bxUPbtm < bxDNtop and bxDNbtm < bxUPbtm:
    // -> a BPR exists; its box spans
    //    left  = min(bxUP.left , bxDN.left)
    //    right = max(bxUP.right, bxDN.right)
    //    and vertically the OVERLAP of the two gaps
```
So: **a bullish FVG and a bearish FVG that overlap in price. The BPR is the overlap.** Nothing else.
`SNIPER` implements the same with a minimum-overlap filter `bprMinOverlapATR = 0.04` (overlap must exceed
0.04·ATR) and describes it as *"price delivered inefficiently in both directions through the same band"*.

**3. Claimed to predict.** A stronger reaction than either gap alone, because both sides are unfilled;
usually treated as a reversal zone.

**4. Numbers.** None retrievable.

---

### 3.10 Volume imbalance

**1. Aliases.** VI, volume imbalance; body gap; distinct from FVG (which is a *wick-to-wick* gap).

**2. Mechanical definition** **[CODE]** `LUX-Imbalance Detector` — exact and non-obvious:
```
bull_gap_top = math.min(close, open)          // current bar's body bottom
bull_gap_btm = math.max(close[1], open[1])    // previous bar's body top
bull_vi = open > close[1] and high[1] > low and close > close[1]
          and open > open[1] and high[1] < bull_gap_top
// bearish mirror:
bear_gap_top = math.min(close[1], open[1])
bear_gap_btm = math.max(close, open)
bear_vi = open < close[1] and low[1] < high and close < close[1]
          and open < open[1] and low[1] > bear_gap_btm
```
Key: `high[1] > low` means **the two bars' RANGES overlap** (so it is not an FVG) while their **bodies do
not** (that is the imbalance). `SNIPER` gives the same in prose and adds `viMinATR = 0.10`, and notes it
turns them off by default because *"they are numerous and price revisits them constantly"* — an honest
warning worth heeding.

**3. Claimed to predict.** A small magnet; a minor support/resistance. Nobody claims much for these alone.

**4. Numbers.** None retrievable, but `LUX-Imbalance Detector` computes bull/bear counts and filled-%
live for VI, opening gaps and FVG separately. That dashboard is the right template for the study to run.

---

### 3.11 Opening gaps: NDOG and NWOG

**1. Aliases.** NDOG = New Day Opening Gap; NWOG = New Week Opening Gap; "opening gap"; OG.

**2. Mechanical definition** **[CODE]** `LUX-ICT Concepts`:
```
// NWOG:
if dayofweek == dayofweek.friday:  friCp := close, friCi := n
if ta.change(dayofweek) and dayofweek == dayofweek.monday:
    monOp := open, monOi := n
    box = [ max(friCp, monOp) , min(friCp, monOp) ]      // Friday CLOSE to Monday OPEN
    midline = avg(friCp, monOp)
// NDOG:
if ta.change(dayofweek):
    cuDOp := open;  prDCp := close[1]
    box = [ max(prDCp, cuDOp) , min(prDCp, cuDOp) ]      // previous day's close to today's open
```
Also **[CODE]** `LUX-Imbalance Detector` has a simpler "opening gap" = `low > high[1]` (bull), which is a
plain bar gap and a different object — don't conflate.

`SNIPER` note: *"Reference levels: they are never retired for being traded through."* — i.e. NDOG/NWOG,
unlike FVGs, are conventionally **not** deleted on mitigation.

**3. Claimed to predict.** Magnet and support/resistance, especially the midline; NWOG is claimed to be a
week-scale reference. For XAUUSD the weekend gap is real and frequent, so NWOG is directly applicable;
NDOG on a 23/5 gold feed is often zero-width, which makes it near-useless intraday — check your feed
before implementing.

**4. Numbers.** None retrievable.

---

### 3.12 Immediate rebalance

**1. Aliases.** IR, immediate rebalance, "wick rebalance".

**2. Mechanical definition** **[CODE]** `LUX-ICT Immediate Rebalance Toolkit`:
```
bullish IR:  low < high[2]  and  low > close[2]  and  close > high[2]
             and close[1] > high[2]  and  close > close[1]
bearish IR:  high > low[2]  and  high < close[2] and  close < low[2]
             and close[1] < low[2]   and  close < close[1]
// levels drawn at 25% / 50% / 75% of the wick that did the rebalancing
// confirmation window irCFR = 2 bars: if within 2 bars low < level -> marked FAILED (❌)
```
i.e. price left a gap and **immediately closed it with a wick on the very next bar instead of leaving an
FVG**. The script explicitly says both the successful and the failed version are meaningful signatures.

**3. Claimed to predict.** A successful IR is claimed to show strength (the market rebalanced and kept
going); a failed IR the opposite. This is one of the few concepts that ships with an explicit
**failure** label, which makes it unusually testable.

**4. Numbers.** None published in the script.

---

### 3.13 Unicorn (breaker + FVG overlap)

**Prioritised: not previously scored.**

**1. Aliases.** Unicorn model, unicorn setup, breaker+FVG.

**2. Mechanical definition** **[CODE]** `LUX-ICT Unicorn Model` — full ordered sequence, bearish case:
```
len = 10 ('Swings');  a 4-point zigzag A,B,C,D is maintained (A oldest)
trigger on the bar where  n - lenL == Dx  (D just confirmed) and:
    dir < 1                                  // current leg is down
    close[lenL] < By                         // price closed below B  -> structure broken
    Cy > Ay                                  // C made a HIGHER HIGH than A  -> C swept liquidity
    Dx - Cx > 1  and  Cx - Bx > 1  and  Bx - Ax > 1     // legs at least 2 bars each
// BREAKER BLOCK = the first DOWN-CLOSE candle at or within 4 bars after B:
    switch: close[n-Bx+0] < open[n-Bx+0] -> x=Bx-0, y=high[..], z=low[..]
            close[n-Bx+1] < open[n-Bx+1] -> ...
            ... up to +4
    breaker zone = [y, z] = that candle's high and low
// FVG: scan i = 0 .. n-Cx for a bearish gap
    fvgT = low[i+2]; fvgB = high[i]
    require fvgB < fvgT                                        // a real gap
    and ((fvgT < y and fvgT > z) or (fvgB < y and fvgB > z))   // the gap OVERLAPS the breaker
    and (fvgT - fvgB) > atr * 0.05                             // gap large enough
// invalidation: not triggered and close > firstBr.fvg.top  -> remove
// targets: stop at Cy (the swept high); reward = risk * (reward/risk), default 1:1
```
Bullish is the mirror (`close[lenL] > By`, `Cy < Ay`, first UP-close candle after B).

**Note the `Cy > Ay` condition** — that is the liquidity sweep that makes it a breaker rather than a
mitigation block (§3.3), enforced in code. This is the cleanest published example of the whole family
being one detector with a sweep flag.

**3. Claimed to predict.** Reversal, with a defined stop (the swept extreme) and a defined target. Ranked
by its proponents as the highest-confidence array because it stacks two independent conditions.
`SNIPER` calls it *"the highest tier array in the engine"*.

**4. Numbers.** None retrievable. The LuxAlgo script draws risk/reward boxes with a default of 1:1 but
publishes no hit rate.

---

### 3.14 Premium / discount / equilibrium

**1. Aliases.** Premium/discount, PD zones, equilibrium, "50% of the dealing range".

**2. Mechanical definition** **[CODE]** `LUX-SMC`:
```
trail_up = running max of high since the last structure point
trail_dn = running min of low
premium    zone = [ trail_up , 0.95*trail_up + 0.05*trail_dn ]     // top 5% of the range
equilibrium zone= [ 0.525*trail_up + 0.475*trail_dn , 0.525*trail_dn + 0.475*trail_up ]  // middle 5%
discount   zone = [ 0.95*trail_dn + 0.05*trail_up , trail_dn ]     // bottom 5%
```
Note that LuxAlgo draws only the **outer 5% bands and the middle 5%**, not "everything above 50% is
premium". The looser folk definition — above the 50% of the range = premium, below = discount — is what
most traders mean and is what this repo already scores. **Both are defensible; they are different
features.** The narrow-band version is a much rarer, much more selective signal.

The other decision is **which range**: LuxAlgo uses the trailing extremes since the last structure point;
others use the last confirmed swing high to swing low; others use the day's range. Pin this down.

**3. Claimed to predict.** Longs only in discount, shorts only in premium. It is a *filter*, not a signal.

**4. Numbers.** None retrievable.

---

### 3.15 Optimal Trade Entry (OTE)

**1. Aliases.** OTE, optimal trade entry, "the golden zone", 62–79.

**2. Mechanical definition.** Consistent across every implementation I checked — retracement of the
current impulse leg to:
```
0.618  /  0.705  /  0.79       (some write 0.62 and 0.786)
long:  level = swingHigh - range * f      (retracement down into an up-leg)
short: level = swingLow  + range * f
```
**[CODE]** confirmed identically in: `https://raw.githubusercontent.com/jcortes254/btmm-pine-script-system/main/scripts/core/BTMM_Stop_Hunt_Detection.pine`
(`fib_705 ... // OTE Zone`, `fib_79 ... // OTE Zone`),
`https://raw.githubusercontent.com/TamTH-Dev/trading-view-scripts/master/collections/SmartMoneyConcepts.pine`
(`processFibLevel(..., 0.618)`, `0.705`, `0.79`),
`https://raw.githubusercontent.com/swiffc/Study_app/main/D.X.C._LEVELS_v2.0.pine`
(`OTE_62_LEVEL = 0.62`, `OTE_705_LEVEL = 0.705`, `OTE_79_LEVEL = 0.79`),
`SNIPER` (`showOTE ... "0.62 / 0.705 / 0.79"`, with `oteMinLegATR = 1.0` — legs smaller than 1 ATR
produce no OTE band).

The only real decision is **which leg**: `SNIPER` uses the current impulse leg with a ≥1·ATR size filter;
`LUX-ICT Killzones` instead draws 0/0.236/0.382/0.5/0.618/0.782/1 across the **killzone session's**
high–low, which is a different anchor entirely.

**3. Claimed to predict.** That entries in the 0.62–0.79 band get the best risk:reward. Note this is a
claim about **R**, not about win rate — and per this repo's E-074, R and money are not the same thing.

**4. Numbers.** None retrievable.

---

### 3.16 Standard deviation projections

**1. Aliases.** SD projections, standard deviations, "deviations", range projections.

**2. Mechanical definition** **[CODE]** `LUX-ICT Everything` — repeated from §1.9 because it is the most
misunderstood item here:
```
range = box_high - box_low                    // box = CBDR, Asia, or Flout
SD+i  = box_high + range * i
SD-i  = box_low  - range * i
CBDR and Asia: i = 1, 2, 3, 4
Flout:         i = 0.5, 1.0, 1.5, 2.0
```
**This is not `ta.stdev`.** It is range multiples. Same for `SNIPER`, which projects
*"0.5 / 1 / 2 standard deviations of the leg itself"* past a leg extreme and uses them as TP1/TP2.

**3. Claimed to predict.** Objectives — where a move terminates. Used as targets, not entries.

**4. Numbers.** None retrievable.

---

## 4. TIME

### 4.1 Killzones — and they contradict each other badly

**1. Aliases.** Killzone, KZ, session window; London open KZ, New York AM KZ, London close KZ, Asian KZ.

**2. Mechanical definition.** Every source agrees a killzone is just `time(timeframe.period, session, tz)`.
**No source agrees on the windows.** Here is every published window I read, verbatim:

| script | Asia | London open | NY (AM) | London close / NY PM | timezone |
|---|---|---|---|---|---|
| `LUX-ICT Killzones` **[CODE]** | 2000–0000 | 0200–0500 | 0700–0900 | 1000–1200 | `UTC-5` (fixed, **no DST**) |
| `LUX-ICT Concepts` **[CODE]** | — | 0700–1000 | 0700–0900 | 1500–1700 | London open/close in `Europe/London`, NY in `America/New_York` |
| `LUX-ICT Killzones Toolkit` **[CODE]** | 2000–0000 | 0200–0500 | **0830–1100** | **1330–1600** | NY |
| `ICT Killzones + Pivots [TFO]` **[CODE]** | 2000–0000 | 0200–0500 | **0930–1100** | 1330–1600 (+ NY Lunch 1200–1300) | `America/New_York` (default) |
| `SMC-PY` `sessions()` **[CODE]** | Asian KZ **0000–0400** | London open KZ **0600–0900** | NY KZ **1100–1400** | London close KZ **1400–1600** | **UTC** |
| `LUX-ICT Everything` **[CODE]** | 2000–2359 | 0200–0500 | 0700–1000 | 1000–1200, PM 1300–1600 | NY |

Read that table again before you code anything time-based. The "New York killzone" is variously
07:00–09:00, 07:00–10:00, 08:30–11:00 and 09:30–11:00 **NY time**, and 11:00–14:00 **UTC**. The
`LUX-ICT Killzones` script uses a **fixed `UTC-5`, which is wrong for half the year** — during US DST
NY is UTC-4, so that script's windows silently shift by an hour for ~8 months of the year.

**In UTC, for XAUUSD, the defensible canonical set** (converting the `America/New_York` versions, which
are the majority, and stating both DST states explicitly):

| killzone | NY local | UTC in EDT (Mar–Nov) | UTC in EST (Nov–Mar) |
|---|---|---|---|
| Asia | 20:00–00:00 | 00:00–04:00 | 01:00–05:00 |
| London open | 02:00–05:00 | 06:00–09:00 | 07:00–10:00 |
| NY AM (narrow) | 08:30–11:00 | 12:30–15:00 | 13:30–16:00 |
| NY AM (wide) | 07:00–10:00 | 11:00–14:00 | 12:00–15:00 |
| NY PM / London close | 13:30–16:00 | 17:30–20:00 | 18:30–21:00 |

**Do not hardcode UTC offsets.** Convert from `America/New_York` and `Europe/London` with a real tz
library, or your session boundaries move twice a year — and the two zones do not switch on the same dates
(London: last Sunday March / last Sunday October at 01:00 UTC; New York: second Sunday March / first
Sunday November at 02:00 local — both stated in the `LUX-ICT Macros` tooltip **[CODE]**).

**3. Claimed to predict.** That the day's high or low forms inside a killzone, and that setups outside
them should be skipped. It is a filter, and it is the single easiest thing in this document to test on
XAUUSD M1/M5/M15: bucket every existing signal by killzone and compare.

**4. Numbers.** None retrievable.

---

### 4.2 Silver Bullet

**1. Aliases.** Silver bullet, SB; "the 10–11 window"; ICT Silver Bullet.

**2. Mechanical definition** **[CODE]** `LUX-ICT Silver Bullet` — three windows, all one hour, all
`America/New_York` (so DST-correct):
```
SB_LN = "0300-0400"    // London Open Silver Bullet
SB_AM = "1000-1100"    // AM Session Silver Bullet
SB_PM = "1400-1500"    // PM Session Silver Bullet
```
The setup logic in the same file:
```
left = 5                                        // swing lookback
// MSS via a 4-point zigzag:
//   bullish: close > aZZ.y.get(iH) and aZZ.d.get(iH) ==  1 and MSS_dir <  1
//   bearish: close < aZZ.y.get(iL) and aZZ.d.get(iL) == -1 and MSS_dir > -1
// FVG filter, 4 modes:
//   'All FVG' | 'Only FVG in the same direction of trend' | 'Strict' | 'Super-Strict' (default)
// targets: swing highs/lows from the PREVIOUS session, two modes:
//   'previous session (any)' | 'previous session (similar)'   (default: similar)
```
So the shipped model is: **inside a one-hour SB window, take an FVG in the direction of the MSS, target a
prior-session swing level.** The 'Super-Strict' default means only FVGs that survive the trend and the
structure filter are shown.

**3. Claimed to predict.** That a tradeable move originates in that specific hour, most days. ICT's own
framing is that it is a time-based setup: the window comes first, the pattern second.

**4. Numbers.** None retrievable — and this is the concept for which the "high win rate" claims are
loudest online, which makes the absence of retrievable data the most important sentence in this section.
**Every "silver bullet 80/90% win rate" figure you will meet online is from a course seller or a YouTube
thumbnail. None was verifiable here.**

---

### 4.3 Macros

**1. Aliases.** ICT macros, macro windows, "the 20-minute macros", algorithmic macros.

**2. Mechanical definition** **[CODE]** `LUX-ICT Macros` — exact list, exact timezones, exact DST rules:
```
London (Europe/London, DST: last Sun Mar 01:00 UTC -> last Sun Oct 01:00 UTC):
    02:33 - 03:00
    04:03 - 04:30
New York (America/New_York, DST: 2nd Sun Mar 02:00 -> 1st Sun Nov 02:00):
    08:50 - 09:10
    09:50 - 10:10
    10:50 - 11:10
    11:50 - 12:10        ("Launch Macro")
    13:10 - 13:40
    15:15 - 15:45
// the script REFUSES to run above 5-minute charts:
//   "ICT Macros are supported on: 1 min, 3 mins and 5 mins charts"
```
Per macro the script records open, high, low, mid, and the close-of-window OHLC.

Note the shape: most are **:50 to :10 around the hour**, i.e. straddling the hour boundary. The two
London ones and the 13:10/15:15 ones break that pattern.

**Directly relevant to this repo:** these are 1/3/5-minute-only objects. That is precisely the timeframe
band E-081 forces a £40 account onto. If any time-of-day effect in gold is real at M1, this is the
highest-resolution published hypothesis about where it is.

**3. Claimed to predict.** That algorithmic activity concentrates in these windows, so expansion and
liquidity runs cluster there.

**4. Numbers.** None retrievable.

---

### 4.4 Power of Three / AMD

**Prioritised: not previously scored.**

**1. Aliases.** PO3, Power of 3, AMD (Accumulation–Manipulation–Distribution), "the daily candle model",
Judas swing (the manipulation leg specifically).

**2. Mechanical definition.** Two families:

*(a) Time-boxed sessions* **[CODE]**
`LUX-Power Of 3 ICT 01 [TradingFinder] AMD ICT & SMC Accumulations`:
```
Accumulation  session '1900-0100'   America/New_York
Manipulation  session '0100-0700'   America/New_York
Distribution  session '0700-1300'   America/New_York
// each phase draws a box tracking running max(high)/min(low) over its window
// script only draws when timeframe <= 60 min
```
Fully mechanical, zero pattern recognition, and note these are **not** the same as the killzone windows.

*(b) Pattern-detected phases* **[CODE]** `LUX-ICT Power Of Three | Flux Charts`:
```
algorithmMode = 'Small Manipulation' | 'Short Accumulation' | 'Big Manipulation'
accumulationLength    = 40 (High) or 11 (Low)      // min bars of accumulation
accumulationATRMult   = 5  (High) or 2  (Low)      // MAX size of the accumulation range, in ATR
manipulationATRMult   = 0.6 (Low)  or 1  (High)    // MIN size of the manipulation leg, in ATR
breakoutMethod = 'Wick' | 'Close'
```
i.e. **accumulation = ≥40 bars whose whole range is ≤5·ATR; manipulation = a break of that range by
≥0.6·ATR; distribution = the move the other way.** That is codeable exactly as stated and is the only
quantified PO3 definition I found.

**[SEARCH]** prose (https://ictflow.com/blog/power-of-three-amd-model ,
https://ttrades.com/ict-power-of-three-amd-accumulation-manipulation-distribution-explained/ ,
https://innercircletrader.net/tutorials/ict-power-of-3/ ,
https://www.dhanith.com/blog/accumulation-manipulation-distribution ) confirms the standard mapping:
Asian range accumulates, London open manipulates (the **Judas swing**), New York distributes; reference
open is the **True Daily Open = midnight New York**; and the claim that the pattern is fractal (applies to
the weekly, daily, and to any session).

**3. Claimed to predict.** That the day's *extreme opposite to the daily direction* forms during the
manipulation window — i.e. if today closes up, today's low is set in the London manipulation leg. That is
a sharply falsifiable statement and it is the version worth testing, because it is a claim about **where
in the day the extreme sits**, which you can measure directly with no entry model at all.

**4. Numbers.** None retrievable.

---

### 4.5 True day open / midnight open

**1. Aliases.** True day open, midnight open, TDO, 00:00 NY open.

**2. Mechanical definition** **[CODE]** `LUX-ICT Everything` opening-price lines, all `America/New_York`:
```
MIDNIGHT   00:00      (default ON)   <- the "True Day Open"
NEW YORK   08:30      (default off)
EQUITIES   09:30      (default off)
AFTERNOON  13:30      (default off)
+ weekly open, monthly open
```
`ICT Killzones + Pivots [TFO]` **[CODE]** ships the same idea as configurable "open" lines defaulting to
`0000-0001`, `0600-0601`, `1000-1001`, `1400-1401`.

The level is simply **the open price of the first bar at or after 00:00 New York**. Unambiguous once the
timezone is fixed. Everything above/below it is "premium/discount relative to the day open".

**Contradiction flag.** Some sources call 09:30 NY the "true day open" (equities open). The ICT-native
usage, and every implementation above, uses **midnight NY**. Use midnight; note that a broker feed whose
day starts at 00:00 server time will give you a different number.

**3. Claimed to predict.** Daily bias — price above the midnight open = bullish day, below = bearish; and
that price returns to it.

**4. Numbers.** None retrievable.

---

### 4.6 Day-of-week tendencies

**1. Aliases.** Day of week, DOW; "Tuesday/Wednesday sets the weekly high or low"; Monday range
expectations; "Seek & Destroy day".

**2. Mechanical definition.** **Not properly sourced.** `LUX-ICT Everything` has a "Day Of Week & Labels"
settings group **[CODE]** — it labels days but implements no tendency. `ICT Seek & Destroy Profile [TFO]`
exists in the mirror and its title implies a consolidation-day classifier, but I did not read it.

The commonly stated claims are: the weekly high or low forms Tuesday or Wednesday London; Monday is
typically the smallest range; Friday afternoon is untradeable. **None of these has a published mechanical
definition or a published number, and the search that would have found any failed.**

This is trivially testable here from data alone and does not need a source: group XAUUSD days by weekday
and measure where in the week the weekly extreme falls. **Do that rather than importing anyone's claim.**

**3. Claimed to predict.** Which day contains the weekly extreme, and therefore which direction the rest
of the week runs.

**4. Numbers.** None.

---

## 5. CROSS-MARKET: SMT DIVERGENCE

**Prioritised: not previously scored.**

**1. Aliases.** SMT, SMT divergence, Smart Money Technique/Tool divergence; "correlated-pair divergence";
"one made a higher high, the other didn't".

**2. Mechanical definition** **[CODE]** `LUX-SMT Divergences` — this is a complete, unambiguous spec:
```
length = 3 (minval 2)                   // 'Pivot Lookback'
ph = fixnan(ta.pivothigh(length, length))              // on the CHART symbol
pl = fixnan(ta.pivotlow (length, length))
[h1,l1,c1] = request.security(sym1, timeframe.period, [high, low, close])
[h2,l2,c2] = request.security(sym2, timeframe.period, [high, low, close])
sym_ph1 = fixnan(ta.pivothigh(h1, length, length))     // SAME pivot length on the comparison symbol
sym_pl1 = fixnan(ta.pivotlow (l1, length, length))

get_divergence(ph_flag, y2, sym_y2, css):
    // y1, sym_y1, x1 = the PREVIOUS pivot pair
    if y2 != y2[1] and sym_y2 != sym_y2[1]:                 // BOTH symbols printed a new pivot
        if (y2 - y1) * (sym_y2 - sym_y1) < 0:               // <<<< THE TEST
            -> SMT divergence; draw line; smt += 1
        sym_y1 := sym_y2; y1 := y2; x1 := n[length]
    else if (ph_flag and y2 > y2[1]) or (not ph_flag and y2 < y2[1]):
        sym_y1 := na; y1 := y2; x1 := n[length]             // reset when only one side moved
```
**The test is the sign of the product of the two changes.** `(Δchart) × (Δcomparison) < 0` — one made a
higher high while the other made a lower high (or one a lower low while the other made a higher low).
That is it. It requires **both symbols to print a pivot at the same pivot index**, which is the reason
naive implementations produce garbage: if the two instruments' pivots don't line up, there is no test.

The script also maintains a dashboard showing, per comparison symbol, the **SMT count and SMT count as a
percentage of all pivots** on swing highs and swing lows separately — i.e. it will tell you your own
divergence base rate. **That is the most useful published measurement tool in this whole document, and it
costs nothing to point at gold.**

**Which pairs.** The script's own defaults are index futures: `CME_MINI_DL:ES1!` and `CBOT_MINI_DL:YM1!`.
For XAUUSD the candidates named in the community are XAGUSD (silver), DXY, and the USD legs
(EURUSD/GBPUSD as dollar proxies). **I could not verify which pairing anyone recommends for gold — the
search failed.** Do not guess; test all four against the base rate the dashboard gives you.

**Caveat that matters more for gold than for indices:** SMT assumes the two instruments are genuinely
correlated over the window. Gold/silver correlation is unstable, and DXY is inverse (so the sign test
must be flipped, or you must use `-DXY`). Getting the sign wrong turns the feature into its own negation
and will look like a *negative* edge.

**3. Claimed to predict.** Reversal. The instrument that failed to make the new extreme is claimed to be
the honest one; the divergence marks the sweep as false.

**4. Numbers.** None published, but the script computes the base rate for you.

---

## 6. ENTRY MODELS AS ORDERED CONDITION SEQUENCES

### 6.1 The 2022 Mentorship Model

**[SEARCH]** (https://tradingfinder.com/education/forex/ict-mentorship-2022-model/ ,
https://icttraders.net/ict-2022-model-complete-trading-strategy-explained-step-by-step/ ,
https://www.r2ftrading.com/learn/ict-2022-model-explained ,
https://innercircletrader.net/tutorials/complete-ict-trading-strategy-2022/ ,
https://www.quantum-algo.com/blog/guides/ict-2022-model-complete-guide/ ). Ordered sequence as published:

```
1. Establish daily bias (direction).
2. Mark the midnight (00:00 NY) opening range / true day open, and mark the liquidity:
   PDH/PDL, prior session highs/lows, equal highs/lows.
3. WAIT for a liquidity sweep — price raids liquidity on the side OPPOSITE the intended direction.
4. Require DISPLACEMENT away from the raid (§2.7).
5. Require MSS — a break of a recent swing high/low, with that displacement (§2.3).
6. The displacement leg leaves an FVG (or an order block). That is the PD array.
7. ENTER on the retrace into the FVG/OB.
8. STOP just beyond the sweep wick.
9. TARGET the opposite liquidity pool. Minimum 1:3 R:R is the commonly stated filter.
```
Every step except 1 and 9 is mechanical given the definitions above. Step 1 (bias) is the judgement call
and is where every implementation differs. Step 9's "minimum 1:3" is a *selection* rule, and note E-074
in this repo: the best per-trade R gate banked the least money. Report points.

**Numbers:** none retrievable.

---

### 6.2 Silver Bullet model

Per `LUX-ICT Silver Bullet` **[CODE]**, as an ordered sequence:
```
1. Wait for one of the three one-hour windows (03:00-04:00 / 10:00-11:00 / 14:00-15:00 NY).
2. Inside the window, detect MSS via the 4-point zigzag (swing length 5).
3. Find an FVG in the MSS direction; apply the FVG filter mode
   ('Super-Strict' by default = trend-aligned AND structure-confirmed).
4. Enter on the FVG.
5. Target a swing high/low taken from the PREVIOUS session ('similar' session by default).
```
No stop rule is published in the script. **Numbers:** none retrievable.

---

### 6.3 Unicorn model

Per `LUX-ICT Unicorn Model` **[CODE]**, ordered (bearish; mirror for bullish):
```
1. Maintain a 4-point zigzag A-B-C-D at swing length 10; each leg at least 2 bars.
2. Require Cy > Ay      -> point C swept the prior high (LIQUIDITY TAKEN).
3. Require close[lenL] < By  -> structure broken downward (MSS/CHoCH).
4. BREAKER = the first down-close candle at or within 4 bars after B; zone = that candle's high..low.
5. FVG = any bearish gap (low[i+2] > high[i]) that OVERLAPS the breaker zone and is > 0.05 * ATR.
6. The unicorn zone is the breaker; entry on the retest.
7. STOP at Cy (the swept high).  TARGET at risk * (reward/risk), default 1:1.
8. INVALIDATION: untriggered and close > FVG top -> discard.
```
**Numbers:** none retrievable.

---

### 6.4 Turtle Soup

Two published versions, and they are genuinely different setups sharing a name.

*(a) Classic (Street Smarts / Linda Raschke lineage, adopted by ICT)* **[SEARCH]**
(https://fxopen.com/blog/en/what-is-ict-turtle-soup-and-how-can-you-use-it-in-trading/ ,
https://www.theinnercircletraders.com/ict-turtle-soup/ ,
https://www.stockmarketmethod.com/lessons/turtle-soup-the-failed-breakout-reversal-pros-love-ict-concepts/ ,
https://www.luxalgo.com/library/indicator/n7MU1chB-ict-turtle-soup-liquidity-reversal/ ):
```
1. The prior high (or low) must be at least 20 PERIODS old.
2. That 20-period high/low must have occurred at least FOUR sessions earlier.
3. Price makes a new 20-period high/low.
4. Price reverses and closes back inside (below the prior high / above the prior low).
5. Entry on that failure; stop just beyond the false-break extreme.
```
The "20 periods" and "at least four sessions earlier" are the distinguishing quantities and they are
absent from every modern SMC retelling.

*(b) Modern intraday, HTF-range version* **[CODE]** `LUX-ICT Turtle Soup | Flux Charts`:
```
higherTimeframe = "60"          // default
mssOffset       = 10            // MSS swing length
breakoutMethod  = 'Wick' | 'Close'    (default Wick)
barLength = HTF_minutes / chart_minutes
high12 = ta.highest(barLength); low12 = ta.lowest(barLength)     // last HTF bar's high/low
highMSS = ta.highest(mssOffset); lowMSS = ta.lowest(mssOffset)

state machine:
  "Waiting For Liquidity Break":
      if (Close?close:low)  < lastHourLow   -> sellside grab -> entryType = Long   (Classic mode)
      if (Close?close:high) > lastHourHigh  -> buyside  grab -> entryType = Short  (Classic mode)
      -> state = "Waiting For Execution"
  "Waiting For Execution" (only on bars after the sweep bar):
      Short: (Close?close:low)  < lowMSS[1]   -> entry at close or lowMSS[1]
      Long : (Close?close:high) > highMSS[1]  -> entry at close or highMSS[1]
  TP/SL: 'Dynamic' (ATR * risk setting) or 'Fixed' (tpPercent 0.3%, slPercent 0.4%); RR debug default 0.9
  only ONE trade open at a time
```
Note `entryMethod = 'Adaptive'` flips the direction based on which side has broken more often
(`highBreaks` vs `lowBreaks`) — i.e. the same sweep can be traded either way depending on a counter.
That is a red flag for overfitting and worth knowing before you borrow this logic.

**Numbers:** the Flux Charts script ships a "Backtesting Dashboard" that computes win rate on your chart.
No numbers are published in the source.

---

### 6.5 One Shot One Kill / MMXM

**[CODE]** `LUX-One Shot One Kill ICT [TradingFinder] Liquidity MMXM + CISD OTE`:
```
BarBackCheck = 5        // CISD lookback
CISDVal      = 25       // CISD level validity in bars
SwingPeriod  = 50       // liquidity swing period
MaxSwingBack = 100      // 'All' or custom
fib levels computed:  0.236, 0.382, 0.500, 0.618, 0.786   (X0 + (X1-X0)*f)
MSH / MSL tracking for market structure
```
Sequence: liquidity level from a 50-period swing → CISD (§2.8) → retrace into the OTE fibs → entry.
MMXM ("market maker buy/sell model") is the surrounding narrative; the script's mechanical content is
liquidity + CISD + fib.

**Numbers:** none.

---

## 7. WHAT IS ACTUALLY TESTABLE

Ranked by how little you have to invent. **Tier 1** can be coded today with zero further decisions.
**Tier 2** needs one clearly-labelled choice. **Tier 3** is not ready.

### Tier 1 — fully mechanical, code it as written

| concept | § | the one line that defines it |
|---|---|---|
| Liquidity sweep vs genuine break | 1.4 | `high > level and close < level` vs `close > level` |
| SFP with volume validation | 1.5 | `< 25%` of the bar's 1-min volume traded above the swept level |
| Equal highs/lows (LuxAlgo form) | 1.2 | `abs(h1 - h2) < 0.1 * ATR(200)` on `pivothigh(3,3)` |
| Relatively-equal + unpierced-line filter (fadi) | 1.2 | tolerance `0.2 * median(ATR(14),14)` AND no bar between pierces the connecting line |
| **Inducement / IDM** | 1.10 | last `swings(3)` extreme, `!= ` the major extreme, taken out while `os` is with-trend; and it **gates BOS** |
| BOS / CHoCH (LuxAlgo form) | 2.2–2.3 | `ta.crossover(close, top_y)`; CHoCH iff prior trend opposite |
| BOS / CHoCH (4-swing pattern form) | 2.2 | the `level[-4]<level[-2]<level[-3]<level[-1]` ordering test |
| Internal vs external structure | 2.4 | two engines at `swings(50)` and `swings(5)` |
| Strong/weak (protected) highs and lows | 2.5 | trailing extreme + current trend sign |
| Displacement, all three forms | 2.7 | `range > 2*stdev(body,100) and fvg` / both wicks `< 0.36*body` and `body > meanBody` / "an FVG exists" |
| **CISD** | 2.8 | close through the open of the first candle of the opposing run |
| Order block, all four forms | 3.1 | see the four code blocks; they are all one-screen |
| **Breaker block** | 3.2 | OB whose body-bottom is closed through; confirmed by a swing forming inside it |
| **Mitigation block** | 3.3 | same detector as breaker with `swept = (H2 > H1)` set FALSE |
| **Propulsion block** | 3.4 | OB forming inside a live same-direction OB |
| Rejection block | 3.5 | dominant wick ≥55% of range, opposite wick ≤30%, body ≤60%, and it swept a level |
| FVG (all variants) | 3.6 | `low > high[2] and close[1] > high[2]` + a size threshold |
| Consequent encroachment | 3.7 | `(top+bottom)/2` |
| **IFVG (inversion)** | 3.8 | gap body-closed through, then retested from the other side |
| **IFVG (implied)** | 3.8 | biggest middle body + two wicks each >30% of range + wick-midpoints ordered |
| **BPR** | 3.9 | overlap of the latest bullish and latest bearish FVG |
| Volume imbalance | 3.10 | bodies gap, ranges overlap |
| NDOG / NWOG | 3.11 | prev close → next open box; Friday close → Monday open box |
| Immediate rebalance | 3.12 | the 5-condition test, plus its explicit 2-bar failure label |
| **Unicorn** | 3.13 | breaker ∩ FVG, with `Cy > Ay` enforcing the sweep |
| Premium/discount (both the 5% band and the 50% forms) | 3.14 | explicit formulas |
| OTE 0.618/0.705/0.79 | 3.15 | explicit, with a ≥1·ATR leg filter |
| SD projections | 3.16 | **range multiples, not `ta.stdev`** |
| Killzones | 4.1 | pick a row from the table; convert from tz, don't hardcode UTC |
| Silver bullet windows | 4.2 | 03:00–04:00, 10:00–11:00, 14:00–15:00 NY |
| Macros | 4.3 | the 8 listed windows; M1/M3/M5 only |
| Power of 3, time-boxed | 4.4 | 19:00–01:00 / 01:00–07:00 / 07:00–13:00 NY |
| Power of 3, pattern-detected | 4.4 | ≥40 bars with range ≤5·ATR, then a break ≥0.6·ATR |
| True day open | 4.5 | open of the first bar at/after 00:00 NY |
| **SMT divergence** | 5 | `(Δchart) × (Δcomparison) < 0` on `pivot(3,3)` pairs that print together |
| Turtle soup (both versions) | 6.4 | both fully specified above |
| 2022 model, unicorn model, silver bullet model | 6.1–6.3 | ordered sequences, all steps mechanical except "daily bias" |

### Tier 2 — one labelled decision each

- **Order block**: which of the four definitions. Not a tuning parameter — four different objects.
- **FVG**: whether to merge consecutive gaps; which size threshold; **and never port `SMC-PY.fvg()`,
  it uses `shift(-1)` and looks ahead.**
- **Premium/discount**: which range (trailing extremes / last swing pair / the day).
- **SMT**: which comparison instrument for gold, and the sign convention for inverse instruments.
- **Session/previous-day levels**: which day boundary (00:00 NY vs broker server day).
- **Swing definition**: symmetric pivot / asymmetric pivot / rolling-extreme state machine (§2.1).
  This choice propagates into every other feature. Fix it once, globally, and record it.
- **Day-of-week**: no source; measure it from data instead of importing a claim.

### Tier 3 — NOT ready to code; you would be testing your own inventions

- **HRLR / LRLR (§1.3)** — no implementation exists, and the term has two incompatible meanings.
  *But* the underlying continuous variables are Tier 1: **count of unswept opposing pivots between price
  and the target**, and **unfilled opposing imbalance in that span**. Score those. Skip the label.
- **Trendline liquidity (§1.7)** — four free parameters, no source. Lowest priority in the document.
- **Internal vs external range liquidity (§1.11)** — no mechanical alternation rule published.
- **Failure swing (§2.6)** — reduces to CHoCH-with-a-lower-high; do not build a separate feature.
- **"MSS vs CHoCH" as two features (§2.3)** — the code says they are one object. Build one, and if you
  want to test the distinction, test *with-displacement* vs *without-displacement*.

### Highest-value things here that this repo has not yet scored

1. **Inducement as a gate on BOS** (§1.10) — a direct instance of "does the filter refuse worse trades".
2. **CISD** (§2.8) — cheap, distinct, earlier than MSS.
3. **Breaker vs mitigation split on the sweep flag** (§3.2/3.3) — one detector, one boolean, tests the
   community's central claim about the block family.
4. **IFVG-inversion** (§3.8) — a reversal trigger with a clean invalidation rule.
5. **Consequent encroachment vs proximal vs distal** (§3.7) — three entry prices from one detected object;
   pure execution study, no new detection needed.
6. **SMT base rate on gold** (§5) — measure the base rate before believing any signal built on it.
7. **Killzone / macro bucketing of signals already scored** (§4.1/4.3) — costs nothing, uses existing
   signals, and is directly on the M1/M5/M15 band E-081 forces.

---

## 8. PUBLISHED NUMBERS AND HOW MUCH TO TRUST THEM

**The honest headline: I retrieved essentially no trustworthy numbers, and the retrieval failure was
partly structural and partly a network block.**

### 8.1 What the network did

`WebFetch` was refused (`EGRESS_BLOCKED`) for every non-GitHub domain attempted. `WebSearch` worked for
about six queries and then failed permanently. **The queries that failed were disproportionately the
numeric ones** — "silver bullet backtest win rate", "SMC backtest results win rate sample size",
"FVG fill rate statistics study", "OTE fibonacci levels", "SMT divergence pairs", "turtle soup rules",
"trendline liquidity", "killzone times UTC". Some of those I recovered from code instead; the numeric ones
I did not. **Do not fill this section from memory in a later session. Re-run those searches from an
unblocked environment and cite what comes back.**

### 8.2 Numbers that appear in the sources I did read

| number | where | what it actually is | trust |
|---|---|---|---|
| `tpPercent 0.3% / slPercent 0.4%`, `RR 0.9` | `LUX-ICT Turtle Soup \| Flux Charts` **[CODE]** | the script's *default TP/SL settings*, not a result | **Not a performance number at all.** A default. |
| `RR 1:1` default | `LUX-ICT Unicorn Model` **[CODE]** | drawn target box default | Not a result. |
| "minimum 1:3 R:R" | 2022-model pages **[SEARCH]** | a *selection rule* taught to students | No sample size, no market, no dates. Course material. |
| "20 periods old, at least four sessions earlier" | Turtle Soup **[SEARCH]** | a *condition*, not a result | Inherited from Street Smarts; no forex/gold validation cited. |
| `25%` outside-volume threshold | `LUX-SFP` **[CODE]** | a *filter parameter* | A default someone chose. Not validated in the source. |
| every ATR multiple in this document (0.05, 0.1, 0.25, 0.36, 0.5, 2.0, 2.3, 5.0…) | all **[CODE]** | indicator defaults | Chosen for chart legibility, not for edge. Treat every one as a starting point to sweep, never as a finding. |

**That is the complete list.** No win rate, no sample size, no date range, no cost assumption was found in
any source I could reach.

### 8.3 What I did NOT find, and why that itself is informative

Not one of the ~45 published indicators I read ships a validated performance claim. Two ship *calculators*:
- `LUX-Imbalance Detector` **[CODE]** — dashboard of FVG / volume-imbalance / opening-gap counts and
  **filled percentage**, computed live on whatever you point it at.
- `LUX-SMT Divergences` **[CODE]** — dashboard of SMT count and **SMT as a percentage of all pivots**,
  per comparison symbol, split by swing highs and swing lows.
- `LUX-Breakaway Fair Value Gaps` **[CODE]** — counts and mean/median duration.
- `LUX-ICT Turtle Soup | Flux Charts` **[CODE]** — an on-chart win-rate dashboard.

The vendors who know these concepts best ship tools that *compute* the base rate rather than publishing
one. Read that as the strongest available signal about how well these concepts survive measurement.

### 8.4 Standing rules for anything that arrives later

Any number that turns up for these concepts must be checked against all of:

1. **Who is selling something?** Every ICT/SMC education domain in the source lists above
   (innercircletrader.net, tradingfinder.com, icttraders.net, r2ftrading.com, quantum-algo.com,
   fxnx.com, ghosttraders.co, stockmarketmethod.com, theinnercircletraders.com, writofinance.com,
   dhanith.com, ictflow.com, ttrades.com, arongroups.co, liquidityscan.io, equiti.com, fxopen.com,
   litefinance.org, algokings.net, forexmt4indicators.com, tradingstrategyguides.com, crypoptionhub.com,
   orbex.com) **is a broker, a course seller, or an indicator vendor.** Not one is a disinterested party.
   No academic or independent study surfaced at all.
2. **Sample size, or it does not exist.** Per this repo's E-073: bar counts are not decision counts. A
   "500-trade backtest" of an intraday SMC model on one instrument is a handful of independent regimes.
3. **Costs.** Nothing above includes spread, commission or slippage. On XAUUSD M1 at 0.01 lots
   (£0.787/point, E-081), cost is the dominant term — a model quoting a 60% win rate on a 1:1 with a
   3-point round-trip cost is a losing model.
4. **Long/short split, walk-forward, Monte Carlo** — `JARVIS/research/study.py`, no exceptions.
5. **Points, not R** — E-074.

### 8.5 The one number-generating job worth doing first

Before testing any of these as *signals*, use them as *measurements*, on your own XAUUSD data, at M1/M5/M15:
FVG fill rate by size bucket; sweep-then-reverse rate by level type (EQH vs PDH vs session high vs pool);
SMT base rate against silver and DXY; where in the NY day the daily extreme actually forms. Those are
base rates. Without them, any win rate that shows up later is uninterpretable — you will not know whether
the concept did anything or whether the market does that anyway.

---

*End of SMC_SPEC.md. Every `[CODE]` definition was read from the file at the URL given; every `[SEARCH]`
definition is a search-engine summary of a page that could not be fetched from this session and is
second-hand. Nothing here has been tested. Nothing here is a claim that anything is profitable.*

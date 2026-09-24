# SMC / Liquidity-Sweep Strategies — Mechanical Rules, Claimed Win Rates, and the Geometry Test

Research date: 2026-09-22. Target instrument: XAUUSD.

**Tooling caveat, stated up front:** direct page fetching (WebFetch, curl) was blocked by the
network egress proxy for every external domain tried (tradingview.com, quantifiedstrategies.com,
mpmmarkets.com, tradingstats.net, fxnx.com, grandalgo.com, arxiv.org, wikipedia.org). All content
below comes from **search-engine result summaries**, not from reading the primary pages. Numbers
attributed to a source are therefore *second-hand*. Every figure marked **[UNVERIFIED-FETCH]**
needs the primary page opened before it is trusted. This matters most for the StatOasis and MPM
studies, which are the only methodologically serious sources found.

---

## 0. How to read this document: the geometry test

For a driftless price series with a symmetric barrier problem, the probability of touching a target
`T` points away before touching a stop `S` points away is:

```
P(win) = S / (S + T)        equivalently, with R = T/S:   P(win) = 1 / (1 + R)
```

This is **zero-edge geometry**. It is not a strategy result. Reference values:

| R (reward:risk) | 1:1  | 1:1.5 | 1:2   | 1:2.5 | 1:3   | 1:4   | 1:8   |
|-----------------|------|-------|-------|-------|-------|-------|-------|
| Geometric win % | 50.0 | 40.0  | 33.3  | 28.6  | 25.0  | 20.0  | 11.1  |

**RESIDUAL = claimed win rate − geometric win rate.** Only the residual can be edge.

One independent source states this identity in the same terms, which is a useful sanity check that
the framing is not idiosyncratic: *"If market fluctuations follow approximately random walk
behavior, the probability of a 60-point target being reached before a 20-point stop is hit will be
approximately 25 percent"* — which is exactly `20/(20+60) = 25%`.
(Search summary of tradingview.com/chart/SPX/HUmb4N1D, EdgeTools)

### Three traps in applying the test

**Trap 1 — an implausibly LARGE residual is evidence of fabrication, not of edge.**
The residual test cuts both ways. A 70% win rate at 1:3 implies expectancy
`0.70x3 − 0.30x1 = +1.80R per trade`. Nothing in liquid markets pays 1.8R per trade. So a claim of
"70% win rate at 1:3 R:R" is not a strong edge claim — it is an *incoherent* claim, and the correct
inference is that the number was never measured. Genuine edges show up as residuals of a few
percentage points (see MPM's +5pp, section 10.2). **Treat residual > ~15pp with no published trade
log as a fabrication marker, not a discovery.**

**Trap 2 — planned R is not realised R.** Almost every source quotes an *intended* risk:reward
("minimum 1:3", "we target 1:2"). Partial exits, trailing stops, break-even moves, time-based
exits and unfilled targets all pull realised average-win down. The geometry test must use realised
average win / average loss, which essentially nobody publishes. Where only planned R exists, the
computed geometric baseline is a *lower bound on the true baseline*, so the true residual is
smaller than the one I report.

**Trap 3 — "touch" statistics are not win rates.** Many of the most impressive SMC numbers
(96% reversion, 84% chance of hitting PDH or PDL, 70%+ London sweep rate) measure *whether price
ever reached a level*, with **no opposing barrier and no time limit**. With no stop, `S → ∞` and
`P → 100%` trivially. These are not tradeable win rates and must never be compared against a
strategy win rate. This is the single most common error in the SMC literature. Flagged throughout
as **[TOUCH-STAT]**.

---

## 1. Liquidity sweep / stop-hunt reversal (the base pattern)

### 1.1 The mechanical core (this part *is* codeable)

Synthesised from multiple sources that agree on the skeleton (LuxAlgo library, backtrex,
dailypriceaction, quantum-algo, Pro-Scalper, the "Gold 15m Trend+S/R+Liquidity Sweep" TradingView
script):

- **Level set:** confirmed pivot highs/lows stored as watched levels; or equal highs/lows; or
  PDH/PDL; or session high/low.
- **SWEEP TRIGGER:** a bar whose `high > level` (or `low < level`) but whose `close` is back on the
  original side of the level. This is a strictly codeable two-condition test.
- **ENTRY:** on the close of the sweep bar, or on the close of a confirming reclaim bar within
  1–3 bars, or on a retest of the swept level.
- **STOP:** beyond the sweep wick plus a buffer. Buffers seen: `+0.5 x ATR`; `2–5 pips`;
  `5–15 pips`; "ATR-based buffer".
- **TARGET:** "the next liquidity level in the reversal direction"; or a fixed R multiple
  (1:2 standard); or 50% of the last impulsive leg (T1) then next significant swing (T2).
- **TIME FILTER:** London and New York sessions; killzones = first 60–90 min of London and NY.
- **TIMEFRAME:** 1H/4H for level selection, 15M for the sweep, 1M–5M for entry refinement.

### 1.2 Claimed win rates and the geometry verdict

| Claim | Source | Stated S | Stated T | R | Geometric | RESIDUAL | Verdict |
|---|---|---|---|---|---|---|---|
| **65–75% WR** | quantum-algo / backtrex "expected metrics" | "sweep wick + 0.5 ATR" (**non-numeric**) | R:R 2.5:1 to 4:1 | 2.5–4 | 28.6% – 20.0% | **+36 to +55 pp** | Incoherent. Implies +1.4R to +2.0R/trade. Fabrication marker. |
| **60%+ WR, ~1:2** | same cluster, "historical backtests" | not stated | 1:2 | 2 | 33.3% | **+27 pp** | Implies +0.8R/trade. No sample size, no date range, no costs. |
| **"win rate +10–15%" from tighter stop buffer** | Sweep & Strike / XAUUSD sources | 2–5 pip buffer | structural | — | — | — | **Backwards.** Tightening S *lowers* `S/(S+T)`, so a tighter stop must *reduce* win rate, not raise it. The claim contradicts the geometry it is describing. |

**No source in this cluster states a numeric stop and a numeric target together.** Stops are given
as "beyond the wick + buffer" (a data-dependent quantity) and targets as "the next liquidity level"
(also data-dependent). That combination makes every claimed win rate in section 1
**unfalsifiable as published** — you cannot reconstruct the trade from the rule text.

### 1.3 Ambiguities requiring human judgement

1. **Which levels count as "obvious"?** Sources say "obvious equal highs" / "a respected low" /
   "a key level". No source defines respected or obvious. This is the largest single degree of
   freedom in the whole family.
2. **Pivot length** for swing detection is unstated in most write-ups; it changes the level set
   completely. (Explicitly acknowledged: *"Backtest results are sensitive to pivot length, stop
   distance, and which filters are enabled."*)
3. **"Aggressive wick"** — no threshold given (some scripts use an ATR multiple, default 2.0,
   ATR period 14).
4. **"Within 1–3 candles"** — a 3x degree of freedom left to the trader.
5. **"Next liquidity level"** as target — which one? The nearest, the most touched, the one on the
   trading timeframe or the HTF? Undefined.
6. **Sweep-failure exit:** one source gives a genuinely mechanical abort rule —
   *"price not closing back above the swept level within two to three candles → exit at market"* —
   but "two to three" is again unfixed.

---

## 2. Asian-range sweep and reversal (London raid on the Asia range)

The best-evidenced family in this document, and the one with real published statistics.

### 2.1 Mechanical rules

- **RANGE DEFINITION:** high and low of the Asian session. **Session times disagree between
  sources** — this is a material ambiguity, not a detail:
  - `00:00–08:00 UTC` (Pro-Scalper, for XAUUSD: "the Asian session, midnight to 08:00 UTC")
  - Tokyo session proper (roughly `00:00–09:00 JST`)
  - ICT convention commonly `20:00–00:00 ET` (the "Asian range" as the pre-London accumulation)
  A different window gives a different range gives a different trade. **Must be pinned before coding.**
- **TRIGGER:** during London (approx. `03:00–05:00 ET`, i.e. first two hours of London open, or
  "first 30–90 min of London open, `02:00–03:30 ET`" for the Judas-swing variant), price trades
  beyond the Asian high or low and then closes back inside.
- **CONFIRMATION:** a market-structure shift (MSS/CHoCH) on a lower timeframe in the opposite
  direction to the sweep.
- **ENTRY:** on the MSS, or on retrace into the FVG left by the displacement leg.
- **STOP:** beyond the sweep extreme (the wick of the sweep).
- **TARGET:** the opposite side of the Asian range; then the session extreme / PDH or PDL.
- **TIMEFRAME:** M30 for the range and sweep (Pro-Scalper's XAUUSD recommendation); M5/M3/M1 for MSS
  and FVG entry.

### 2.2 The published statistics — and which are real

From the **tradingstats.net 12-year study on NQ/ES/YM/RTY** (May 2026) **[UNVERIFIED-FETCH]**:

| Statistic | Value | Is it a win rate? |
|---|---|---|
| Asia range is broken before 08:30 ET | **93–95% of sessions** | **[TOUCH-STAT]** — no stop, no barrier. Near-certain by construction: a range must be exited eventually. |
| Price returns inside the range after breaking | **96–97% of broken sessions** | **[TOUCH-STAT]** — this is the headline number and it is *pure geometry*. The sweep is typically 10–30 points beyond the edge; "returning inside" requires only that small move back, with **no opposing stop and no deadline**. `S → ∞ ⇒ P → 100%`. A 96% reversion rate is worth approximately nothing as a win rate. |
| Reversion rate stability across 3/6/12-month windows | ±2pp | Genuinely useful: the statistic is *stable*, so the geometry is stable. Still not an edge. |
| 10% extension break rate | 88–92%, ±2pp across windows | [TOUCH-STAT] |
| 50% extension | drifts ~7pp lower in recent quarters | Regime drift warning. |
| 100% extension | up to ~9pp lower recently | Regime drift warning — the *tradeable* (far) targets are the ones decaying. |
| Cross-instrument spread (NQ/ES/YM/RTY) | 1.1–2.2pp | Good robustness signal. |

**Interpretation.** The 96–97% figure is the most-quoted and least-meaningful number in the Asian
range literature. The study's *real* contribution is the third row: the extension probabilities are
stable over time, and the far extensions are decaying. Note the study is on index futures, **not
gold** — transfer to XAUUSD is unestablished.

From **breakoutalerts.io** (tracked results) **[UNVERIFIED-FETCH]** — the single most honest
number found in this family because it is quoted as **expectancy, not win rate**:

| Range size | Average result |
|---|---|
| 40+ pip Asian range | **+0.64R per trade** |
| 15–25 pip Asian range | **−0.33R per trade** |

**This is the most actionable finding in the entire document.** It says the edge is not in the
sweep — it is in a **volatility-regime filter on the range width**. Narrow Asian ranges produce
negative expectancy; wide ones positive. Expectancy is immune to the geometry artefact (it already
prices in both R and win rate), so no residual correction is needed. For XAUUSD the equivalent
threshold must be re-derived: gold's Asian range is typically **$20–$35** (Pro-Scalper), daily
range **$60–$100**, 4H ATR **$4–$12**, so a fixed pip threshold from FX/indices will not transfer —
use a **percentile of trailing Asian-range width**, or **range width / daily ATR**, instead.

Other claims in this family:

| Claim | Source | Assessment |
|---|---|---|
| "London sweeps the Asian high or low **70%+ of the time**" | GrandAlgo | **[TOUCH-STAT]**. No stop. Also near-tautological given the 93–95% break rate above. |
| "The pre-London stop hunt is the most reliably recurring micro-structure event in XAUUSD... occurs almost every trading day" | Pro-Scalper | No number, no sample, no stop/target. **Unfalsifiable.** |
| "Sweep typically extends **10–30 pips** beyond the boundary; retail stops sit **5–15 pips** beyond" | Pro-Scalper | Useful *sizing* input — it tells you the minimum viable stop buffer. Not a win-rate claim. |
| "Success rate = price reversing **at least 20 pips** after the sweep confirmation candle **within 4 hours**", based on "12 months of H1 data" | Pro-Scalper | **This is the best-specified claim in the family** — it has a target (20 pips), a deadline (4h) and a sample (12 months H1). **But the actual percentage was not retrievable**, and there is **no stop**, so it remains a [TOUCH-STAT] with a time limit. Worth fetching the primary page. |
| EUR/USD London breakout "mixed results, entering long on a breakout above the Asian high often resulting in losses" | QuantifiedStrategies | **Negative result.** The naive breakout (as opposed to the fade) loses. Consistent with the reversal framing. |

### 2.3 Ambiguities

1. **Session window** (above) — unresolved across sources, materially changes everything.
2. **Which side is swept first when both are swept** in the same London window? No source handles
   the double-sweep case.
3. **"Market structure shift"** — see section 6; the definition is itself contested.
4. **What if no sweep occurs by 03:30 ET?** One source: "the setup is weaker" — not a rule.
5. **Holiday / low-liquidity Asian sessions** and the days the range is abnormally wide (post-news)
   are not excluded by any published rule.

---

## 3. PDH / PDL raid strategies

### 3.1 Mechanical rules

- **LEVELS:** previous day's high and low. Codeable, but **the daily boundary must be fixed** —
  broker 00:00 server time, 00:00 UTC, 17:00 ET (CME close), or midnight NY? Gold trades nearly
  24h, so the choice moves PDH/PDL materially. No source specifies.
- **RAID (reversal) variant:** displacement beyond PDH/PDL → price returns and taps an OB/FVG near
  that level → enter on LTF confirmation. Stop beyond the level and beyond the liquidity wick.
  Targets: "Golden Pocket" first (0.618–0.65 retrace), then the opposite previous-day level.
- **CONTINUATION variant:** PDH/PDL break as a directional bias signal for the rest of the session.
- **TIME FILTER:** killzones — first 60–90 minutes of London and NY.
- One indicator formalises: entry at signal-candle close, stop at current-day extreme + buffer,
  **minimum R:R filter default 1.5R**, structure-based trailing that activates at **+1R** and trails
  using higher lows (longs) / lower highs (shorts).

### 3.2 Published statistics (edgeful, 12 months, NY session, ES/NQ/CL/GC) [UNVERIFIED-FETCH]

| Statistic | Value | Assessment |
|---|---|---|
| After PDH or PDL breaks, session **closes in the break direction** | **76–88%** across all four markets | **Continuation, not reversal.** This directly contradicts the SMC "raid = reversal" premise. Not a win rate (no stop), but a genuine directional conditional. |
| **GC (gold)** and CL **extend beyond** the broken level | **67–72%** | Gold-specific and the most relevant number here. Still no stop/target pair, so no residual computable. |
| Inside day → price breaks yesterday's range | **81–88%** | [TOUCH-STAT] |
| MNQ/QQQ opens inside PD range → hits PDH **or** PDL | **84%** | **[TOUCH-STAT], and the clearest artefact in the document:** two targets, no stop, whole session. Near-100% is the null expectation. A "84% hit rate" here is *evidence of nothing*. |

**The important finding:** edgeful's data says PDH/PDL breaks **continue** 76–88% of the time and
gold **extends** 67–72% of the time. The SMC PDH/PDL "raid" model assumes the opposite — that the
break is a false move to be faded. **These two bodies of claims are in direct conflict, and the one
with published multi-market data favours continuation.** For XAUUSD specifically, gold is called out
as one of only two markets that extend at meaningful rates. If anything here is worth building, it
is the **continuation** model, not the raid.

### 3.3 Ambiguities

1. Daily boundary definition (above).
2. "Displacement" beyond the level — no magnitude threshold published.
3. "Golden Pocket" — 0.618, 0.65, or the 0.618–0.786 band? Sources differ.
4. Which OB/FVG "near that level" — the nearest, the largest, the unmitigated one? Undefined.
5. Whether a PDH touched-but-not-closed-beyond counts as a break. Unspecified everywhere.

---

## 4. "Ping pong" / range rotation between two liquidity levels

**This is the least mechanisable family found. No source produced a codeable range definition.**

### 4.1 What the sources actually say

- Range boundaries: *"More touches make the boundaries better defined and more widely watched, but
  **consistent rejection at both extremes matters more than the number itself**."* — the criterion is
  explicitly *not* countable.
- Range break: *"Treat the direction as unknown until price actually **accepts** outside an edge."*
  — "acceptance" is never defined (no bar count, no close count, no volume threshold, no time).
- *"Fakeout detection identifies the specific price action signals that distinguish a true range
  expansion from a temporary liquidity sweep."* — asserts the distinction exists, supplies no test.
- Trading rule: buy near the lower boundary, sell near the upper, stops just outside the boundary.
- ICT framing: **internal range liquidity** (inside the range: FVGs, OBs, minor highs/lows) vs
  **external range liquidity** (the range extremes themselves).

### 4.2 The geometry problem is severe here

Range rotation is the **structurally worst** family for the geometry artefact. The canonical trade
is: enter at the edge, stop just outside the edge (small `S`), target the opposite edge (large `T`).
That is a *low* `S/(S+T)`, so geometry predicts a **low** win rate — yet the strategy is marketed on
the intuition that ranges hold. Conversely, the *statistics* usually quoted in support
(96% reversion, section 2.2) come from the no-stop touch framing, which predicts ~100%.
**The marketing statistic and the trade geometry are measuring opposite things.** Any backtest must
therefore use the trade's own S and T, never the reversion statistic.

**No source in this family published a win rate at all**, which — per the brief — is itself the
finding: the claims are unfalsifiable because there is no rule and no number.

### 4.3 The only codeable versions (my construction, not published)

If this must be built, the range has to be anchored by something mechanical. Candidates:
- **Session range:** Asian high/low (section 2). Fully mechanical, already has statistics.
- **Fixed-pivot range:** the most recent confirmed pivot high and pivot low at a fixed lookback `N`.
- **Volatility-compression range:** N bars whose true range is below a percentile of trailing ATR;
  boundaries = high/low of that window.
- **Break definition:** `k` consecutive closes beyond the boundary (k=1,2,3) **or** a close beyond
  boundary + `m x ATR`. Both are sweepable parameters; neither is "correct".

Every one of these is a *substitute* for a definition the literature does not supply.

---

## 5. "Leg to leg" / swing-to-swing trend continuation

### 5.1 Mechanical rules

- **BIAS:** higher timeframe (Daily), pullback structure mapped on 4H, trigger on 1H — or
  Daily/4H/15M for intraday.
- **CONTEXT:** price must be in **discount** for longs (lower half of the dealing range) / premium
  for shorts. See section 7.
- **TRIGGER:** price retraces into an **unmitigated** order block that is aligned with a **fresh**
  FVG, in the direction of the HTF trend, after a BOS in that direction.
- **ENTRY:** at the OB/FVG (midpoint of the gap is the common choice; OB body vs wick is contested,
  section 6.4).
- **STOP:** below the OB low (or the pullback swing low) with an **ATR-scaled buffer**.
- **TARGET:** *"next relevant external liquidity (PDH, daily high, BSL)"*; minimum 1:2 R:R.
- **ABORT:** invalidation on *"a decisive close back inside the old range"*.
- One variant requires **no entry without a pullback to an FVG after CISD** (change in state of
  delivery).

### 5.2 Claimed performance

**No source published a win rate for the continuation model specifically.** The nearest figures:
- "Order blocks with confluence: **62% win rate, 1.8 profit factor** on forex majors", from a
  2,600-trade Medium backtest (section 10.3) — a confluence model, not purely continuation.
- "The best SMC setups have at least **4 aligned confluences**" — an unfalsifiable quality gate.

### 5.3 Ambiguities (this family is the most judgement-laden of the tradeable ones)

1. **"Unmitigated"** — mitigated by a wick touch, a close inside, or a 50% penetration? Three
   conventions in use, no default.
2. **"Fresh" FVG** — fresh means unfilled, but *partially* filled? Threshold unpublished.
3. **"Aligned with"** — how close must the OB and FVG be to count as aligned? No distance rule.
4. **"Relevant" external liquidity** as target — pure judgement.
5. **"Decisive close"** for invalidation — undefined.
6. **"At least 4 confluences"** — the confluence list is open-ended, so this can always be satisfied
   or denied after the fact. This is the mechanism by which the model becomes unfalsifiable.
7. **Timeframe triplet** (D/4H/1H vs D/4H/15M vs 4H/15M/1M) is chosen by the trader.

---

## 6. BOS / CHoCH — the competing definitions, and exactly where they disagree

This is the load-bearing definition for almost every strategy above. There are **at least four
independent axes of disagreement**, and they multiply.

### 6.1 Axis 1 — what is a swing point?

| Convention | Source | Parameter |
|---|---|---|
| Fractal / pivot: bar with `N` bars on each side that do not exceed it | universal | `N` |
| `swing_highs_lows(swing_length=...)` | `smartmoneyconcepts` Python package (joshyattridge) | default commonly 50 |
| **Two-tier**: "internal" (fast, dashed) and "swing" (macro, solid) structure tracked *simultaneously* | LuxAlgo SMC indicator | internal ~5, swing lookback default **50** |
| **"Protected" swings only** — the swing that produced the last BOS | "protected swing" school | qualitative |

**Disagreement:** `N` is arbitrary and unpublished in nearly every strategy write-up. It also
introduces **confirmation lag of `N` bars** — a pivot is not known until `N` bars later, so any
backtest that uses pivots without that lag is look-ahead biased. The "protected swing" school
argues most retail BOS calls are breaks of *unprotected* swings and therefore invalid — i.e. two
practitioners using the same chart will disagree on whether a BOS even occurred.

### 6.2 Axis 2 — what confirms the break? (the most consequential disagreement)

The `smartmoneyconcepts` package exposes this as a single boolean, which is the clearest statement
of the split anywhere in the literature:

> `bos_choch(swing_highs_lows, close_break: bool)` — *"if True then the break of structure will be
> mitigated based on the **close** of the candle, otherwise it will be the **high/low**."*

- `close_break = True` → a break requires a **close** beyond the swing level.
- `close_break = False` → a **wick** beyond the level is sufficient.

**Why this is fatal if left unset:** with `close_break = False`, *every liquidity sweep is also a
BOS*. The sweep-versus-break distinction — which is the entire premise of sections 1, 2 and 3 —
**collapses**. A strategy that says "wait for a sweep, then a BOS in the other direction" is
literally uncomputable until this flag is fixed. Most educational sources side with close-based
(*"validated only when price closes beyond the structure, not just by wick"*; *"a wick beyond
structure that snaps back quickly is not a real break"*), but the most-used code library ships the
option and many indicators default the other way.

### 6.3 Axis 3 — BOS versus CHoCH labelling

| Convention | Rule |
|---|---|
| **Standard** | BOS = break in the direction of the prevailing trend (continuation). CHoCH = first break *against* it (potential reversal). |
| **Confirmation school** | *"A ChoCH is only an early signal... The confirmation comes when price follows the ChoCH with a BOS in the new direction."* — i.e. CHoCH alone is not a signal. |
| **Two-tier (LuxAlgo)** | Internal and swing structure each carry their own BOS/CHoCH labels. **The same bar can be an internal CHoCH and a swing BOS at once.** |
| **Library output** | Returns `BOS` and `CHOCH` as separate ±1 series plus `Level` and `BrokenIndex`. |

**Disagreement:** whether CHoCH is tradeable on its own; and, under the two-tier scheme, *which
tier* the strategy means. A strategy saying "enter on CHoCH" is ambiguous across all three.

### 6.4 Axis 4 — order block zone definition (needed for every OB entry)

> *"Conventions vary, and **none is official**. The most common is the candle's full high-to-low
> range; others use only the body, or the open of the candle to its extreme. Both conventions are
> in active use."*

- **Wick-to-wick:** captures every traded price, suits invalidation, wider zone → more fills, worse
  average entry, larger stop.
- **Body-only:** tighter zone, better entry, more misses.
- **Hybrid (common):** body for entry, wick extreme for the stop.

Plus the base definition — *"the last down-closing candle, or **consecutive group of them**, before
an impulsive move up"* — leaves "consecutive group" unbounded, and lifecycle rules
(*"downgrade a block after its first mitigation, retire it once price closes through the far
side"*) are conventions, not standards.

### 6.5 Axis 5 — inducement (IDM), where the model becomes explicitly non-mechanical

IDM = the first pullback swing after a BOS/CHoCH, which must be swept before the "real" POI is
valid. The literature is unusually candid that this cannot be automated:

> *"The IDM for a 4H Order Block is a 4H-visible swing, not a 5-minute wiggle. **Marking
> micro-swings as inducement for macro zones is how the concept degenerates into hindsight art.**"*

There is no published rule for which timeframe's swings qualify as inducement for a given zone.
**This is a hindsight-only construct as published.**

### 6.6 Practical consequence

Counting only the *published* free parameters: pivot length `N` (say 5 values) x `close_break`
(2) x CHoCH tradeable alone (2) x OB zone convention (3) x mitigation rule (3) x tier (2)
= **360 distinct, all equally "correct" implementations of the same written strategy.** This is
precisely why StatOasis swept 54 variants per concept rather than picking one (section 10.1), and
why any single backtest result from an SMC educator carries almost no information.

---

## 7. Premium / discount and the dealing range

### 7.1 The rule

- **Dealing range** = the price span between a meaningful swing low and swing high.
- **Equilibrium (EQ)** = the **50%** midpoint. Above = premium, below = discount.
- **Rule:** only long in discount, only short in premium. Never initiate at EQ
  (*"no-man's-land"*).
- Implementation: draw a Fibonacci retracement across the swing, keep only the 0.50 line.
- Often combined with **OTE** (Optimal Trade Entry) = the **0.618–0.786** retracement band.

The 50% split, once the range is anchored, is fully mechanical. **The anchoring is not.**

### 7.2 The anchoring problem — the single worst-defined step in SMC

The published rule is:

> *"Define the dealing range: the swing low and high of **the most recent leg that did something
> meaningful**, such as sweeping a prior low or breaking structure."*

"The most recent leg that did something meaningful" is not a definition. It is the step where the
entire premium/discount framework becomes discretionary, and because premium/discount **gates every
other setup** in sections 1–5, this ambiguity propagates into all of them.

Note also the circularity: the range is anchored by a leg that "swept a prior low or broke
structure" — but *which* structure break is itself contested (section 6). The framework is defined
in terms of another contested definition.

**Codeable substitutes (mine, not published), in order of defensibility:**
1. **Sweep-to-CHoCH range:** low = the swept extreme; high = the extreme reached by the
   displacement leg that caused the CHoCH. Fully determined by the sweep event, no free choice.
2. **Fixed-pivot range:** most recent confirmed pivot high and pivot low at lookback `N`.
3. **Session range:** prior session high/low (ties into sections 2–3, already has statistics).
4. **Fixed-lookback range:** highest high / lowest low of the last `M` bars.

(1) is the only one that preserves the intended semantics; the others are proxies. All four should
be swept as variants, not chosen.

### 7.3 Geometry note on OTE

The OTE band (0.618–0.786) mechanically produces a **small stop** (just beyond the 0.786 or the
swing origin) and a **large target** (the prior extreme or beyond), i.e. a high `R`, i.e. a **low**
geometric win rate (1:3 → 25%; 1:4 → 20%). Practitioners quoting OTE win rates above ~40% are
therefore claiming very large residuals. Relevantly, **StatOasis found OTE to be the worst of the
four ICT entries tested — 0.0% of its variants beat the random baseline on SPY** (section 10.1).

---

## 8. XAUUSD-specific strategies with published rules

### 8.1 Gold volatility reference (needed to size any of the above)

| Metric | Value | Source |
|---|---|---|
| Average daily range | **$60–$100** (200–500+ "pips" at $0.01/pip) | Pro-Scalper / FXNX |
| Daily range, high-impact news | **$150–$300** | Pro-Scalper |
| Asian session range (00:00–08:00 UTC) | **$20–$35** | Pro-Scalper |
| 4H ATR | **$4–$12** | Pro-Scalper |
| London/NY volatility vs Asia | **2–3x** | Pro-Scalper |
| Typical sweep extension beyond Asian boundary | **10–30 pips** ($0.10–$0.30) | Pro-Scalper |
| Retail stop clustering beyond Asian high/low | **5–15 pips** | Pro-Scalper |

### 8.2 Published XAUUSD strategies and their claims

| Strategy | Rules (as published) | Claimed WR | S | T | Geometric | RESIDUAL | Verdict |
|---|---|---|---|---|---|---|---|
| **5-min order-block scalp** (FXNX) | Mark last opposing candle before impulsive move; wait for return to zone on M5; enter on rejection; stop just beyond block | none stated | "5–15 pips beyond recent swing" | "minimum 2:1" | 33.3% | — | No WR claimed. At least S and T are both numeric-ish: S=5–15 pips, T=2S ⇒ **geometric 33.3%**. Any claim above ~40% needs evidence. |
| **M1 tight-stop scalp** (FXNX) | Must wait for sweep of major liquidity **and** CHoCH on M1 before using a tight stop | none stated | **10–15 pips** | not stated | — | — | Target never stated ⇒ **unfalsifiable**. |
| **Asian-session gold / pre-London stop hunt** (Pro-Scalper) | M30 Asian range; London sweeps one side; enter reversal | "occurs almost every trading day" | not stated | "reverse ≥20 pips within 4h" | — | — | Success *criterion* given (20 pips / 4h) but **no stop** ⇒ [TOUCH-STAT], and the percentage itself was not retrievable. |
| **Sweep & Strike** (XAUUSD scalp) | Liquidity sweep + reversal candle on LTF | none retrievable | sweep high/low **+2–5 pip buffer** | "next opposing liquidity pool", **min 1:2 filter** | 33.3% | — | Best-specified stop in the gold set. No WR published. |
| **Gold 15m: Trend + S/R + Liquidity Sweep (RR 1:2)** (TradingView, open source) | Long only above 200 EMA / short below; pivot S/R; bullish sweep = break below last pivot low then close back above; stop beyond pivot with ATR buffer; **TP = 2x risk** | **none published** | ATR-buffered pivot | **exactly 2R** | **33.3%** | — | **The most fully mechanical gold strategy found** — every element codeable, zero judgement. But **no strategy-tester numbers published.** |
| **"Goldmine" strategy** (Medium, promoted) | Grid system | **80–90%** | *grid = no stop* | "small consistent wins" | → **~100%** | **≈ 0 or negative** | **Textbook geometry artefact.** A grid has tiny `T` and unbounded `S`, so `S/(S+T) → 1`. An 80–90% win rate is *below* what pure geometry delivers. The residual is zero or negative; the hidden cost is ruin risk. |
| **Gumroad gold course** | not published | **86% over 100 trades** | not stated | not stated | — | — | **Unfalsifiable**, and n=100 is below the 200+ the community itself calls significant. |

### 8.3 Gold-specific caution found in sources

> *"Because XAUUSD is highly volatile, using standard SMC rules **without filtering for
> time-of-day** often leads to lower win rates."*

and

> *"XAUUSD moves an average of $60 to $100 per day in normal conditions, and **$150 to $300 during
> high-impact news**."*

A 10–15 pip ($0.10–$0.15) stop against a $4–$12 4H ATR is roughly **1–4% of ATR**. At that ratio the
stop is inside the noise; realised win rate will fall far below the geometric baseline because
spread and slippage consume a large fraction of `S`. **For gold, any strategy with a sub-$1 stop
should be assumed non-viable until proven otherwise on tick data with real spreads.** Gold spreads
are commonly $0.15–$0.35 — i.e. **comparable to the entire 10–15 pip stop**.

---

## 9. TradingView published SMC strategies with tester reports

**Result: I could not obtain a single verified strategy-tester report.** tradingview.com is
egress-blocked, and no search summary surfaced a complete tester panel (net profit / PF / win rate /
trade count / drawdown) for an SMC strategy. What was recoverable:

| Script | Type | Settings recovered | Tester numbers |
|---|---|---|---|
| **Gold 15m: Trend + S/R + Liquidity Sweep (RR 1:2)** (open source) | strategy | 200 EMA trend filter, pivot S/R, ATR stop buffer, **fixed 2R TP**; adjustable EMA length, pivot settings, ATR multiplier, RR; toggles for trend filter and S/R display | **none published** |
| **SMC BOS Strategy for XAUUSD** (FrankFx14) | strategy | swing sensitivity, stop loss setting, R:R ratio; "strategy tester support" | **none recovered** |
| **Sweep & Reverse — Liquidity Sweep Reversal Strategy** (blitz_locked) | strategy | pivot-detected swing levels; sweep = wick past level + close back inside; stop beyond wick + ATR buffer; TP from chosen R:R | **none recovered** |
| **SMC Pro BTC — ICT Order Blocks & FVG [DOE]** | strategy | — | **none recovered** |
| **Smart Money Concepts (SMC) [LuxAlgo]** | indicator (not a strategy) | internal vs swing structure, swing lookback default **50**, optional "liquidity sweep required before structural break", OB grading A/B/C | n/a — indicator, no tester |
| **Equal Highs/Lows finders** | indicator | **EQH/EQL tolerance default 0.05%**; FX 1–5 pips; crypto 1–50 pts; stocks 0.01–1.00 | n/a |
| **Displacement filter (various)** | indicator | **ATR multiplier default 2.0, ATR period 14** | n/a |

Third-party aggregation of TradingView OB indicators (lunefi) reports **"54% win rate over six
months"** for one order-block indicator alongside **"a year-long Reddit test across markets yielded
negative outcomes"** — with no stop/target stated, so **no residual is computable**, and the two
results conflict. Same source: *"backtest results from community scripts vary widely once live
slippage and spread costs are included"*, and recommends testing ≥1,000 bars.

**Conclusion for this section: the TradingView SMC strategy population does not publish verifiable
tester reports. Treat any win rate sourced from it as unevidenced.** The default settings above are
nonetheless useful as *priors for parameter sweeps*.

---

## 10. Honest backtests, academic work and NEGATIVE RESULTS

This is the most valuable section. Four sources attempt real methodology; **all four are
substantially negative**, and two of them independently use the correct geometry control.

### 10.1 StatOasis — *"I Backtested ICT / Smart Money Concepts — What Survives"* [UNVERIFIED-FETCH]

The most rigorous work located. Methodology (as reported in search summaries):

- Codified **four** ICT entries — order blocks, FVGs, liquidity sweeps, OTE — into mechanical rules
  using ICT's own explicit definitions (e.g. *"a fair value gap is when the high of the first
  candle doesn't overlap the low of the third"*).
- **Swept the ambiguous parameters instead of cherry-picking them**: 54 OB variants, 54 FVG
  variants, 3 liquidity-sweep variants, 6 OTE variants. (This is the correct response to the
  360-implementation problem in section 6.6.)
- **Standardised the exits** so only *entry quality* was measured — this removes the geometry
  artefact by construction, since every variant shares the same S and T.
- Compared against **a frequency-matched coin flip** (a random entry taking the same number of
  trades) **and** three textbook entries **and** buy-and-hold.
- Markets: **SPY, QQQ, DIA, IWM**, daily bars.

Liquidity sweep, as coded: *"price breaking below the N-bar low intrabar (the stop hunt) but
closing back above it to enter long"* — i.e. exactly the section 1.1 definition.
OTE, as coded: *"entering after an upward structure shift on the retrace into the 61.8%–78.6%
Fibonacci band of the last swing leg."*

**Results:**

| Finding | Value |
|---|---|
| Best OB variant, SPY | **$110,039.85** net profit, **0.241** return per unit of drawdown, **296 trades**, 100% of variants profitable |
| **% of OB variants beating the frequency-matched coin flip** | **SPY 81.5% · DIA 66.7% · QQQ 59.3% · IWM 55.6%** |
| OB vs best simple entry | Best OB variant beat the best simple entry (inside-bar breakout) |
| **OTE** | **0.0% of variants beat the random baseline on SPY** — worst of the four |
| **ICT variants beating buy-and-hold** | **0 out of 648** |

**Author's verdict:** *"on daily bars, mechanical ICT is a story you can trade without losing, not
an edge that earns its complexity"*, and *"the concepts, reduced to their published mechanical
definitions, carry no special edge on the timeframe where anyone can verify them."*

**Interpretation for our purposes — this is the properly-computed residual.**
"% of variants beating a frequency-matched coin flip" **is** the residual-over-geometry test done
correctly, because the coin flip shares the exits and therefore the geometry. A result of 50% would
mean zero edge. So:
- Order blocks: **+31.5pp above chance on SPY, +16.7 on DIA, +9.3 on QQQ, +5.6 on IWM.** Real,
  decaying across markets, and on IWM within touching distance of noise.
- OTE: **−50pp.** Actively worse than random.
- And the decisive framing: **0/648 beat buy-and-hold.** An edge that loses to doing nothing is not
  an edge.

Also from StatOasis, on the state of the evidence base:

> *"Every existing 'ICT backtest' you can find is one of three things: a concept explainer with
> hand-picked chart markups, a code library that detects the patterns but never publishes results,
> or an anecdote claiming a win rate with no methodology, no data file, and no baseline."*

> *"If ICT's value exists, it lives in the discretion — which is exactly the part you cannot
> backtest, audit, or learn from a win-rate screenshot."*

### 10.2 MPM Research — *"Does the Fair Value Gap Strategy Work?"* [UNVERIFIED-FETCH]

The cleanest single finding in the document, and the only one that reports a **small, honest
residual**:

> *"The Fair Value Gap reaction is real but faint — **price reacts at FVG levels about five
> percentage points more than at a random level** — yet it does not survive conversion into a
> profitable strategy across **five independent trade constructions, four markets, and three
> timeframes**."*

- **Baseline: a random price level.** This is the right control — it holds geometry constant.
- **RESIDUAL: +5pp.** Real, measurable, and *far* below every educator claim in sections 1–8.
- **Robustness: 5 constructions x 4 markets x 3 timeframes = 60 tests, all failing to be
  profitable.** A +5pp reaction is simply too small to clear spread and slippage.

**This is what a genuine SMC effect actually looks like: ~5pp, and not tradeable.** Every claim of
a 25–55pp residual elsewhere in this document should be read against this number.

### 10.3 The 54-variation cost study [UNVERIFIED-FETCH — attribution uncertain]

Reported in a search summary without clear attribution (plausibly StatOasis or a related write-up):

> *"Across **54 rule variations**, the best win rate reached was **56.3%**, and **0 of 54 were
> profitable after a 0.5-pip cost**, indicating the underlying patterns are real, but a precise
> mechanical rule built on them did not produce an edge."*

and separately: *"**No ICT signal produced a significant forward edge on any of four markets.**"*

**Note the cost sensitivity: a 0.5-pip cost was sufficient to kill all 54 variants.** Gold's spread
is an order of magnitude larger in relative terms than the 0.5 pip used here. This is the most
directly transferable warning in the document for a XAUUSD system.

### 10.4 Community / semi-rigorous results

| Source | Result | Geometry check |
|---|---|---|
| Medium, **2,600 trades**, OB + confluence, forex majors | **62% WR, PF 1.8** | PF and WR jointly imply realised `W/L = 1.8 x 0.38/0.62 = **1.10**` ⇒ geometric `1/(1+1.10) = **47.6%**` ⇒ **RESIDUAL +14.4pp**. **Internally self-consistent** (rare), and the implied R of 1.10 is far below the advertised "1:2.5+" — good evidence for Trap 2. No costs, methodology or data file published. |
| Community SMC with strict confluence (OB + FVG + sweep + killzone) | **50–65% WR, R:R > 1:2.5** | Geometric 28.6% ⇒ **RESIDUAL +21 to +36pp**. Implies +0.75R to +1.3R per trade. **Not credible** per Trap 1. |
| **Unfiltered, rules-based SMC** | **38–48% WR**, "double-digit losing streaks that systematically destroy prop firm challenge accounts" | The honest end of the community range. |
| **Naked order blocks, micro-stops** | **sub-45% WR**, "theoretical 1:8+ payoffs suffer severe degradation from spread, slippage and execution friction" | At 1:8 geometry gives 11.1%, so 45% is a **+34pp residual** — yet this is reported as **loss-making**. The contradiction is Trap 2 in its purest form: the 1:8 was never realised. |
| 1-year Reddit OB test across markets | **negative outcomes** | Negative result. |
| 1-year Reddit OB+FVG test | 55–65% wins | No S/T ⇒ uncomputable. Conflicts with the line above. |
| One OB indicator, 6 months | 54% WR | No S/T ⇒ uncomputable. |

**Sample-size standard the community itself states:** *"Most retail SMC traders review 50 to 100
setups manually, but **statistical significance starts at 200+ trades** on the same exact rule
set."* Most educator claims above are built on fewer than 100.

### 10.5 Academic / microstructure position

From **IndicatorEdge**, which grounds its claims in peer-reviewed work (Chordia, Roll &
Subrahmanyam 2002; Plastun et al. 2020):

- **Supported:** stop orders *do* cluster at predictable levels such as round numbers; **signed
  order imbalance genuinely moves price**; a gap-related anomaly does exist.
- **Not supported:** *"The visual '3-candle fair value gap' is a charting heuristic with **no
  peer-reviewed test**, and it should not be conflated with the order-flow 'imbalance' literature."*
- **Contradicted:** *"gaps more often **CONTINUE** in their direction, and one study explicitly
  calls universal gap-fill a **'myth'**. Gap-fill is conditional on size, horizon and market, not
  universal."*

And the blunt summary from the SMC-debunk cluster: *"there is **no rigorous public evidence that
the full SMC framework carries an edge by itself**."*

**Conclusion: there is no academic validation of SMC constructs.** The genuine microstructure
findings (stop clustering, order-imbalance impact) are real but are *not* what SMC indicators
measure.

### 10.6 The FVG fill-rate literature contradicts itself — and the contradiction is geometric

| Claim | Value |
|---|---|
| Community consensus | FVGs fill **70–75%** of the time |
| Competing research | FVGs stay **unfilled over 60%** of the time |
| 2026 analysis, **32,202 FVG events, 4 asset classes** [UNVERIFIED] | **30–45% of mechanically-detected FVGs fail to produce predictable reactions**; "slow-formation" FVGs gave 3.2x stronger reactions and **>75% win rate** (no S/T stated ⇒ unfalsifiable) |
| High-confluence setups | fill probability **40–60%** |

**These cannot all be true.** But the size-conditioned data explains why they disagree, and it is
pure geometry:

| Gap size | Fill rate by close |
|---|---|
| < 0.3x ATR | **78%** |
| small | **42%** |
| medium | **25%** |
| > 1.2x ATR | **8%** |

**This is `S/(S+T)` restated.** A smaller gap is a shorter distance `T` to travel, so it is touched
more often. The "fill rate" of an FVG is **primarily a function of how far away it is**, not of any
property of the gap. Consequently: *the 70–75% headline fill rate is an artefact of small gaps
dominating the sample*, and **"FVG fill rate" is not evidence of an FVG effect at all.**
This is consistent with MPM's finding that the genuine FVG residual is ~5pp.

---

## 11. Cross-cutting ambiguity catalogue

Every item below requires human judgement as published, and must be fixed (or swept as a parameter)
before any of these strategies can be executed by a computer.

**Structure and levels**
1. Pivot/swing lookback `N` — unstated in nearly all strategy write-ups.
2. Pivot confirmation lag (`N` bars) — a look-ahead bias trap in backtests.
3. `close_break` — wick vs close for structure breaks. **Highest-impact single flag.**
4. Internal vs swing structure tier (LuxAlgo two-tier).
5. "Protected" vs unprotected swings.
6. Whether CHoCH is tradeable alone or requires a following BOS.
7. Equal-high/low tolerance — default 0.05%, but FX sources say 1–5 pips; no gold-specific value.
8. "Obvious" / "respected" / "key" / "meaningful" levels — used constantly, never defined.

**Zones**
9. Order block: wick-to-wick vs body-only vs open-to-extreme.
10. "Consecutive group" of opposing candles — unbounded.
11. Mitigation: wick touch vs close inside vs 50% penetration.
12. "Fresh" / "unmitigated" FVG — partial-fill threshold undefined.
13. "Aligned" OB+FVG — no distance criterion.
14. Displacement magnitude — ATR x2 (period 14) is a common default, not a standard.
15. Inducement timeframe matching — **explicitly hindsight-only** per the sources themselves.

**Ranges**
16. Asian session window: 00:00–08:00 UTC vs Tokyo vs 20:00–00:00 ET. Unresolved.
17. Daily boundary for PDH/PDL on a 24h instrument. Unresolved.
18. Dealing-range anchor: *"the most recent leg that did something meaningful."* Not a definition.
19. Range "acceptance" outside an edge — undefined (no bar count, close count, or volume rule).
20. Double-sweep (both sides swept in one window) — unhandled everywhere.

**Execution**
21. "Within 1–3 candles" reclaim windows — 3x degree of freedom.
22. "Next relevant liquidity" as target — which pool?
23. "Decisive close" for invalidation — undefined.
24. "At least 4 confluences" — open-ended list ⇒ unfalsifiable by construction.
25. Partial exits / break-even / trailing rules — unpublished, yet they determine realised R and
    therefore the entire geometry comparison.
26. News exclusion — no published rule, despite gold's $150–$300 news-day ranges.

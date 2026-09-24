# ICT MODELS — mechanical specification and evidence audit

Target: a XAUUSD algorithmic system. Every model below is reduced to the smallest set of
conditions a computer can evaluate, with every point of human judgement listed separately.

---

## 0. Sourcing rules (binding — read before using any number here)

**WebFetch/curl are blocked by the egress proxy for almost every domain.** Confirmed blocked
this session: `luxalgo.com`, `innercircletrader.net`, `theinnercircletraders.com`,
`tradingview.com`, `statoasis.com`, `arxiv.org`, `michaeljhuddleston.org`, `en.wikipedia.org`.

**`github.com` IS fetchable.** This is new relative to `SMC_SPEC.md` / `WINRATE_RESEARCH.md`,
which were written when nothing could be opened. Every number in §12 tagged `[repo, read]` was
read from the actual page, not a search summary. That makes §12 the only section of this
document with primary-source numbers in it.

Tags used throughout:

| tag | meaning |
|---|---|
| `[repo, read]` | page opened and read. Primary source. Still an unaudited self-report by its author. |
| `[search summary]` | read off a WebSearch result summary. Page **never opened**. Not verified. Establishes only *what people say*, never that it is true. |
| `[own knowledge]` | my own knowledge, no source consulted. |
| `[VAGUE]` | the source does not specify this. A threshold here would be invented, so none is given. |

**No ICT model in this document has a primary, auditable, published rule set from ICT himself.**
ICT's material is ~thousands of hours of YouTube video with no written specification. Every
"rule" below is a third-party transcription, and third parties disagree with each other on
material points. Where they disagree, the disagreement is recorded rather than resolved.

### 0.1 The single most important finding

Across every model: **the time filter and the liquidity-sweep definition are mechanically
specifiable. The entry trigger is not.** Every model bottoms out in one of four undefined
predicates:

| undefined predicate | appears in | why it cannot be coded as stated |
|---|---|---|
| "displacement" / "strong move" | SB, Judas, 2022, Unicorn, PO3, OB, MSS | Explicitly defined as *not* a size threshold — "it's not about size, it's about effortlessness… body dominance, context" `[search summary]`. There is no number anywhere. |
| "a valid / clean sweep" | all sweep models | No minimum penetration distance, no maximum, no required close-back-inside bar count in ICT's version. |
| "significant swing" / "the relevant swing" | OTE, MSS, Turtle Soup | No fractal order (R), no lookback, no alternation rule. |
| "higher-timeframe bias" | 2022 model, PO3, all "with-bias only" filters | Circular: bias is usually defined by the same premium/discount and sweep logic the entry uses. |

Any implementation must **choose** values for these four. Those choices are free parameters,
not ICT's rules, and every one of them is a degree of freedom for overfitting. Count them
explicitly in any backtest's effective parameter count.

### 0.2 Timezone convention for gold

All ICT times are **America/New_York local, DST-aware** `[search summary, consistent across
all sources]`. They are *not* fixed UTC offsets. NY is UTC−5 (EST) / UTC−4 (EDT); London is
UTC+0/+1. The transition dates differ between the US and EU by ~2–3 weeks each spring and
autumn, so a fixed-UTC implementation is wrong for roughly 5 weeks per year and its London
killzone drifts by one hour during those windows. Convert from the bar's UTC timestamp through
a tz database every bar. Do not hardcode offsets.

Gold-specific anchors that are *not* ICT but are real, scheduled, and matter more than most of
the ICT windows `[search summary]`:

| event | time | note |
|---|---|---|
| LBMA Gold Price AM auction | 10:30 London | fixed London clock, moves in NY terms with DST |
| LBMA Gold Price PM auction | 15:00 London | the PM fix; institutional settlement benchmark |
| COMEX GC/MGC Globex session | Sun 18:00 ET → Fri 17:00 ET, daily halt 17:00–18:00 ET | the daily halt defines the true futures day boundary |
| Legacy COMEX "floor" hours | 08:20–13:30 ET | pit is long gone; 08:20 ET is still a real liquidity step for GC |
| US macro releases | 08:30 ET | the dominant single driver of gold's NY range |

The 08:20 ET COMEX open and 08:30 ET data are gold's structural time edges. ICT's 10:00–11:00
window has no gold-specific institutional event behind it at all.

---

## 1. KILLZONES — session time filters

### Canonical times (NY local)

Sources disagree. All four variants below were returned by searches this session:

| killzone | most-cited | competing variants seen | notes |
|---|---|---|---|
| Asian | 20:00–00:00 `[search summary]` | 19:00–22:00; "7pm–10pm"; one source gave "8pm–midnight NY" and "20:00–00:00 GMT" **in the same sentence**, which is self-contradictory (4h apart) | Consolidation. Its high/low is the input to Judas Swing. |
| London | **02:00–05:00** `[search summary, near-unanimous]` | 03:00–06:00 in a minority | The most consistently quoted of the four. |
| New York AM | **07:00–10:00** `[search summary]` | 08:00–11:00; 08:30–11:00 | ICT's "official" is usually quoted 07:00–10:00; the 2022-model literature usually says 08:30–11:00. Material disagreement. |
| London Close | 10:00–12:00 `[search summary]` | 10:00–11:00 | Poorly specified; least used. |

**Silver Bullet windows** (a separate, narrower overlay, see §2): 03:00–04:00, 10:00–11:00,
14:00–15:00 NY `[search summary, unanimous]`.

**Macro windows** (20-minute sub-windows) `[search summary]`: London 02:33–03:00 and
04:03–04:30; NY AM 08:50–09:10, 09:50–10:10, 10:50–11:10; lunch 11:50–12:10; PM 13:10–13:40,
14:50–15:10, 15:15–15:45. The 02:33 and 13:10 start times are odd-looking and are quoted
without justification anywhere — treat as folklore.

- **TRIGGER / ENTRY / STOP / TARGET:** none. A killzone is a filter, never a signal. One source
  states this explicitly and correctly: *"A killzone is a time filter under a price model, never
  a signal by itself"* `[search summary]`.
- **TIME FILTER:** is the whole content of the concept.
- **TIMEFRAME:** timeframe-independent.
- **CLAIMED WIN RATE:** none for killzones alone. Claim that filtering by session lifts SMC win
  rates from 38–48% to 55–62% `[search summary, fxnx.com — a broker content site, no
  methodology, no sample size, no data window stated; treat as marketing]`.
- **AMBIGUITIES:**
  1. Which variant of each window (above). The NY AM disagreement is a full 1.5 hours.
  2. DST handling — never specified by any source; most retail indicators get it wrong.
  3. Whether a setup that *starts* inside the window but *triggers* outside it is valid. Never
     stated. Must be decided by the implementer.
  4. Whether killzone times are meant to apply to gold at all, or only to index futures and FX
     majors. ICT's material is index/FX-centric; no source gives a gold-specific justification.

### Gold mapping — recommendation

For XAUUSD the defensible time filter is **07:00–11:00 NY** (covers the COMEX open, the 08:30
data, and the 10:00–11:00 SB window) and **02:00–05:00 NY** (London, covers the 10:30 London AM
fix). 14:00–15:00 NY covers the 15:00 London PM fix only during periods when the two clocks
align — check per-day, do not assume.

---

## 2. SILVER BULLET

The most mechanically specified of all the models, and the only one where the time filter is
genuinely unambiguous.

- **TRIGGER:**
  1. Clock is inside one of exactly three one-hour windows, NY local: **03:00–04:00**,
     **10:00–11:00**, **14:00–15:00** `[search summary, unanimous]`.
  2. A directional bias exists for the window. `[VAGUE — see ambiguities]`
  3. A **Fair Value Gap forms inside the window**, in the bias direction. FVG is the one fully
     mechanical object in the whole ICT toolkit:
     - bullish FVG at bar `i`: `L[i] > H[i-2]`; gap = `(H[i-2], L[i])`
     - bearish FVG at bar `i`: `H[i] < L[i-2]`; gap = `(H[i], L[i-2])`
     `[search summary, unanimous and consistent across every source]`
  4. **The FVG must form after the window opens.** Pre-window FVGs do not qualify
     `[search summary]`. This is a real, codeable constraint and it is stated explicitly.
  5. Most (not all) versions additionally require, in strict sequence: liquidity sweep → MSS →
     FVG, all three inside the window `[search summary]`. Other versions require only the FVG.
     **This is a fork in the rules and the sources do not agree.**
  6. Stricter versions: it must be the **first** FVG after the MSS — "if you wait for the second
     or third, the move might already be exhausted" `[search summary]`.
- **ENTRY:** limit order at the near edge of the FVG (proximal edge: for a long, the FVG low =
  `H[i-2]`). Alternative widely taught: enter at **consequent encroachment**, the FVG midpoint
  `(gap_high + gap_low)/2` `[search summary]`. A third variant: drop to M1 and enter a micro-FVG
  nested inside the M5 FVG `[search summary]`. Three incompatible entry prices, all attributed
  to the same model.
  Fill must occur **before the window closes** in the mechanical reading; not all sources say
  this.
- **STOP:** below the low of the candle that created the FVG (long) / above its high (short)
  `[search summary]`. Competing version: beyond the wick of the sweep that preceded the FVG
  `[search summary]`. These can be very far apart on gold.
- **TARGET:** the opposing liquidity pool — the nearest prior swing high/low from the Asian and
  London sessions `[search summary]`. Fallback taught: fixed 1:2 R. A staged version exists:
  50% at first internal-range liquidity, 25% at second, 25% at external-range liquidity
  `[search summary]`. Stated objectives: "5–15 handles on indices, 15 pips on FX"
  `[search summary]`; "10–40 pips in 60 minutes" `[search summary, from a title only — page
  blocked]`. No gold-denominated objective exists anywhere.
- **TIME FILTER:** the three windows above, NY local, DST-aware. Outside them, no SB trade
  exists regardless of setup quality `[search summary, unanimous]`.
- **TIMEFRAME:** defined on M5; entered on M5 or M1 `[search summary]`. The sweep/liquidity
  levels are marked from M15/H1.
- **CLAIMED WIN RATE:** "around 70–80% if used properly" `[search summary, unattributed]`. A
  single social-media post: 62.5% over **10 days** on EURUSD `[search summary]` — 10 days is not
  a sample. One source is honest: *"No audited public statistics exist and claimed win rates
  circulating online should be treated as marketing until shown otherwise"* `[search summary]`.
  **Measured, mechanical results are far worse — see §12.1 and §12.2.**
- **AMBIGUITIES:**
  1. **Bias.** "In the direction of the prevailing institutional bias" is never defined. This is
     the single largest hole: a discretionary trader supplies bias from hindsight, and it is
     exactly what makes chart-replay backtests of SB unreliable.
  2. Sweep+MSS required, or FVG alone? Sources split.
  3. Entry at proximal edge, at CE, or at a nested M1 FVG? Three answers.
  4. Stop at FVG candle extreme or at sweep extreme? Two answers, materially different risk.
  5. "First FVG" — first after the window opens, or first after the MSS? Both are taught.
  6. What if two FVGs form? What if the FVG is 0.05 wide? No minimum gap size is ever given.
     (The one mechanical implementation found used **≥ 0.5 index points** — see §12.1 — which is
     that author's invention, not ICT's.)
  7. What if price never returns to the FVG inside the window? Unstated.
  8. Which liquidity pool is "the" target when several exist.

---

## 3. JUDAS SWING

- **TRIGGER:**
  1. Define the **Asian range**: high and low of the Asian session. Session bounds
     `[VAGUE]` — quoted variously as 20:00–00:00 NY, 19:00–22:00, or "the Asian killzone".
  2. Price **sweeps** one extreme of that range — trades beyond the Asian high or Asian low
     `[search summary]`. No minimum penetration given. `[VAGUE]`
  3. Price rejects and a candle **closes back inside** the range / back through the swept level
     (this is the CHoCH in the 5-step retelling) `[search summary]`.
  4. Displacement back the other way leaves an FVG or a breaker `[search summary]`.
  The five-step sequence most commonly quoted: Asian range → sweep → rejection → CHoCH →
  displacement/FVG `[search summary]`.
- **ENTRY:** on retracement into the FVG or breaker left by the reversal displacement
  `[search summary]`. Typically the M5 FVG. Some versions enter on the close of the CHoCH
  candle instead.
- **STOP:** below the low of the manipulation wick (the sweep extreme) for a long; above the
  high for a short `[search summary]`. This one is consistent across sources — the logic given
  is "price should not return to the manipulation extreme if the narrative is correct."
- **TARGET:** the opposite side of the Asian range, then the prior day's high/low, then the next
  liquidity pool `[search summary]`. `[VAGUE]` — no rule says which.
- **TIME FILTER:** the sweep must occur between the **NY midnight open (00:00 NY)** and
  **05:00 NY**; "setups that print after 05:00 NY are not Judas Swings" `[search summary]`.
  Narrower common variant: sweep between **03:00–05:30 NY** `[search summary]`. The core
  London-killzone reading is 02:00–05:00 NY.
- **TIMEFRAME:** Asian range marked on M15/H1; sweep and CHoCH read on M5; entry M5 or M1.
- **CLAIMED WIN RATE:** **none found with any number attached.** Searching specifically for
  Judas Swing win rates and for the base rate of "how often does London sweep the Asian range"
  returned no statistic from any source. This is notable: the base rate is trivially computable
  from data and nobody has published it. One vendor claim: "the London open Judas Swing appears
  in a recognisable form 3–4 times per week on gold" `[search summary, fxnx.com, no method]`.
- **AMBIGUITIES:**
  1. Asian session bounds — three competing definitions, and the range they produce differs
     materially.
  2. How far past the Asian extreme counts as a sweep. Nothing.
  3. Which side gets swept is supposed to be predicted from daily bias — circular, since bias is
     frequently *inferred from* the Judas sweep itself. This is the model's worst circularity.
  4. "Recognisable form" (the vendor's own words) is not a rule.
  5. Multiple sweeps in the window — first, last, or largest? Unstated.
  6. On gold, the Asian range is often wide and the London sweep frequently continues rather than
     reverses. No source gives a rule for distinguishing a manipulation sweep from a genuine
     breakout **at the time it happens**. This is the model's core unfalsifiable step.

---

## 4. TURTLE SOUP / "2022 MODEL"

These are two different things that get conflated. Separate them.

### 4a. Turtle Soup — the original (Connors & Raschke, *Street Smarts*, 1995)

Fully mechanical. No judgement anywhere. This is the only model in this document with a
published, unambiguous, pre-ICT rule set. `[search summary, but the rules are well-known and
consistent — `[own knowledge]` agrees]`

- **TRIGGER (buy):** today prints a new **20-day low**, AND the previous 20-day low is **at
  least 4 trading sessions old**.
- **ENTRY:** resting **buy stop 5–10 ticks above the previous 20-day low**. Only fills if the
  breakout is already failing. If not filled, no trade.
- **STOP:** GTC sell stop **one tick below today's low**, placed immediately on fill.
- **TARGET:** not mechanically specified in the original; Raschke trails/discretionary-exits. The
  common mechanical proxy is the prior swing high or a fixed R.
- **TIME FILTER:** none. Daily bars.
- **TIMEFRAME:** daily, defined and entered on the same bar.
- **VARIANT:** "Turtle Soup Plus One" allows the reclaim to occur on the *following* session.
- **SELL side:** mirror at fresh 20-day highs.
- **CLAIMED WIN RATE:** Raschke reported high hit rates in the 1990s on futures. No modern
  audited figure. Do not carry a 1995 futures result onto 2026 XAUUSD M15.
- **AMBIGUITIES:** essentially none. "At least 4 sessions old" and "5–10 ticks" are the only free
  parameters and both are bounded.

### 4b. ICT Turtle Soup

ICT's version drops the mechanical skeleton and replaces it with discretion.

- **TRIGGER:** price sweeps **any** swing high/low "with visible stop concentration" — equal
  highs/lows, session extremes, PDH/PDL — then closes back inside `[search summary]`. The 20-bar
  lookback survives only in indicator implementations as a default, not as ICT's rule.
- **ENTRY:** on the **close of the confirmation candle** that closes back inside the range — not
  on the sweep candle `[search summary]`. Stricter implementations additionally require an MSS
  before entry `[search summary]`, which delays entry and changes the model materially.
- **STOP:** just beyond the sweep wick `[search summary]`.
- **TARGET:** opposite side of the range / next liquidity pool. `[VAGUE]`
- **TIME FILTER:** none intrinsic; usually overlaid with a killzone filter.
- **TIMEFRAME:** any. Retail implementations use M5/M15.
- **CLAIMED WIN RATE:** none credible. **Measured results are bad — see §12.3 and §12.2.**
- **AMBIGUITIES:**
  1. "Visible stop concentration" is not a rule. It is the whole trigger, and it is a vibe.
  2. Minimum sweep penetration: one indicator-derived description mentions "pierce by a minimum
     number of pips" and "close recovering a defined ratio of the bar's range" `[search summary]`
     — but no *value* for either is published. `[VAGUE]`
  3. Lookback N: 20 is an indicator default, not a rule.
  4. Whether MSS confirmation is required.
  5. **Stop distance vs. cost.** Turtle Soup's stop is by construction just beyond the sweep
     wick, i.e. very tight. On XAUUSD this is the model's fatal flaw — see §12.3, where a
     frictionless +1,371R became −2,788R on a 1.5-pip spread.

### 4c. The "ICT 2022 Mentorship Model" (a different model)

- **TRIGGER, in strict order:**
  1. **Liquidity sweep** of a marked level (PDH/PDL, session high/low, equal highs/lows), marked
     on M15–H1 `[search summary]`.
  2. **Market Structure Shift** on M5/M3/M1: a body close through the most recent opposing swing,
     *with displacement* `[search summary]`.
  3. The displacement leaves an **FVG** (or order block).
- **ENTRY:** limit into that FVG/OB on retracement `[search summary]`.
- **STOP:** beyond the **sweep extreme** (the original sweep wick), not the FVG
  `[search summary]`. This is consistent across sources and is a meaningful distinction from
  Silver Bullet.
- **TARGET:** the opposing liquidity pool — the draw on liquidity that motivated the sweep.
  Minimum **1:3 R** filter is widely quoted as part of the model `[search summary]`; setups not
  offering 3R are skipped. This is a real, codeable filter.
- **TIME FILTER:** London KZ 02:00–05:00 NY as primary; if London does not sweep, NY AM
  08:30–11:00 NY `[search summary]`.
- **TIMEFRAME:** Daily for bias; M15 for liquidity mapping; M5/M3/M1 for MSS and entry.
- **CLAIMED WIN RATE:** none with a number and a method. **Measured: see §12.2 (negative).**
- **AMBIGUITIES:**
  1. "Displacement" — undefined (§0.1).
  2. "Daily bias" — undefined and circular.
  3. Which swing the MSS must break (most recent minor? the one that formed the sweep?).
  4. Whether the FVG must be the first one after MSS.
  5. Entry at proximal edge vs CE.
  6. The 1:3 filter interacts with stop placement: stop-at-sweep-extreme makes R large on gold,
     so the 3R target is often beyond any real liquidity pool. No source addresses this.

---

## 5. UNICORN MODEL (breaker + FVG overlap)

- **TRIGGER:**
  1. Price runs a swing level (creating the trapped orders that make a breaker)
     `[search summary]`.
  2. **Displacement** back through structure in the opposite direction.
  3. That displacement leaves an **FVG** that **overlaps the breaker block's price range**.
  4. The overlapping slice = the "unicorn zone".
- **ENTRY:** on retracement into the overlap zone only — never chase the impulse
  `[search summary]`. Price level: proximal edge of the overlap, or the breaker candle's
  **mean threshold** (50% of the OB candle's open–close body) `[search summary]`. Two answers.
- **STOP:** below the breaker block's outer edge (long) `[search summary]`. Invalidation is a
  **body close** through the far edge, not a wick `[search summary]` — codeable.
- **TARGET:** commonly quoted as fixed **1:2 R** `[search summary]`; otherwise the opposing
  liquidity pool.
- **TIME FILTER:** none intrinsic. Usually overlaid with a killzone.
- **TIMEFRAME:** any; retail usage M5–M15, with HTF (H1/H4) breakers.
- **CLAIMED WIN RATE:** YouTube titles claim **80%** (creator "Bionic NQ") `[search summary,
  title only — no methodology, no sample, page not opened]`. A more measured source: "many
  traders report 50–70% with strict filters… these figures are anecdotal" `[search summary]`.
  One source correctly notes "the pattern alone does not establish a high win rate"
  `[search summary]`. **No backtest of the Unicorn with a stated sample size was found anywhere.**
  Treat the 80% as advertising.
- **AMBIGUITIES:**
  1. **Breaker definition itself is contested** — see §7. If the breaker is ambiguous, so is the
     overlap.
  2. "Overlap" — any overlap of 1 tick, or a minimum fraction? Never specified. `[VAGUE]`
  3. Breaker zone boundaries: candle high–low, or body open–close? Both are taught.
  4. Displacement — undefined (§0.1).
  5. Rarity is advertised as a virtue ("that is why it is called a unicorn"), which means the
     model is *structurally* low-sample. A model that fires rarely cannot be validated quickly;
     this is a practical reason its claimed win rate has never been measured.

---

## 6. POWER OF THREE (AMD)

PO3 is a **narrative framework, not a trade model.** It describes the shape of a candle after
the fact. Treat with maximum suspicion.

- **TRIGGER (as usually operationalised):**
  1. Mark the period's opening price (daily open 00:00 NY / 18:00 NY, or the session open).
  2. Wait for a **manipulation leg**: price moves *against* the anticipated daily direction and
     sweeps a swing high/low beyond the opening range `[search summary]`.
  3. Confirm the sweep failed: price fails at the swept extreme and reverses `[search summary]`.
     `[VAGUE — "fails and reverses" has no bar-level definition]`
  4. Entry confirmation on M5/M15 at a PD array (FVG, OB, breaker).
- **ENTRY:** on the PD-array tap after the manipulation `[search summary]`. i.e. PO3 does not
  supply its own entry — it delegates to §2/§4c/§9.
- **STOP:** beyond the manipulation extreme `[search summary]`. Consistent.
- **TARGET:** the opposite end of the period's expected range, or the next liquidity pool
  `[search summary]`.
- **TIME FILTER:** accumulation ≈ Asian session; manipulation ≈ London; distribution ≈ New York
  `[search summary]`. On the weekly: accumulation Monday, manipulation Tuesday, distribution
  Wed–Fri. The model is explicitly claimed to work on every timeframe simultaneously.
- **TIMEFRAME:** Daily/H4 for the AMD read; M5/M15 for entry.
- **CLAIMED WIN RATE:** none published with a number. `[search summary — nothing found]`
- **AMBIGUITIES:** this model is close to pure hindsight.
  1. The three phases are only identifiable **after** the period closes. A bullish daily candle
     with a lower wick is *defined* as accumulation-manipulation-distribution; a bullish daily
     candle with no lower wick simply isn't called PO3. **The pattern is fitted to the outcome.**
  2. "Anticipated daily direction" — undefined and required before step 2. Without it there is no
     way to tell manipulation from distribution *in real time*, which is the only time it matters.
  3. Phase boundaries have no clock times and no price definitions.
  4. Claiming it applies on weekly, daily, H4, H1, M15 and M5 simultaneously means any move can
     be labelled as some phase of some cycle. That is the definition of unfalsifiable.
  5. The one genuinely testable sub-claim — *does the daily open sit near one end of the daily
     range more often than chance?* — is easy to measure and nobody publishes it.

**Verdict:** the only mechanically usable residue of PO3 is "the daily open is a reference
level, and the day often sweeps one side of it before running the other way." That is a
testable statistic (§12.5 has the nearest thing to a measurement) and should be tested directly
on XAUUSD rather than implemented as "PO3".

---

## 7. ORDER BLOCK / BREAKER BLOCK / MITIGATION BLOCK

### Order Block (OB)

- **Definition:** bullish OB = the **last down-close candle before an up-move**; bearish OB = the
  last up-close candle before a down-move `[search summary, unanimous]`.
- **Validity conditions** commonly added `[search summary]`:
  1. The move away must be *immediate and violent* and must leave an **FVG**;
  2. the move must **break an opposing swing high/low** (i.e. cause a BOS/MSS);
  3. the OB is **invalidated by a body close** beyond its far extreme;
  4. the OB is **mitigated** (dead) once price has returned into it and traded through.
- **Zone boundaries:** candle high–low, or open–close body, or wick-to-body. **All three are
  taught.** `[VAGUE]` The "mean threshold" = 50% of the **body** (open+close)/2
  `[search summary]`.
- **AMBIGUITY:** "last down-close candle" is mechanical. Everything qualifying it is not. Also:
  if there are three consecutive down-closes before the move, is the OB the last one or the whole
  run? Sources differ.

### Breaker Block

- **Definition:** an order block that **failed** — price closed *past* the OB's extreme, swept
  liquidity beyond it, and structure shifted in the **opposite** direction. The OB then flips
  polarity: a failed bullish OB becomes bearish resistance `[search summary]`.
- **Distinguishing test vs mitigation block:** *did a candle body close through the OB extreme?*
  Yes → breaker (direction flips). No → mitigation block (direction continues)
  `[search summary]`.
- **Entry:** retest of the breaker; at its edge or its mean threshold. **Stop:** beyond the
  breaker's outer edge. **Invalidation:** body close through the far edge.

### Mitigation Block

**This definition is genuinely contested in the sources.** Two incompatible versions both
returned this session:

| version | definition | implication |
|---|---|---|
| A `[search summary]` | an OB from a **failed expansion** — orders partially filled, the move failed | reversal-flavoured |
| B `[search summary]` | an **old OB re-tested after the original move played out**, price did **not** close past it; acts as **continuation** in the same direction | continuation-flavoured |

These are not the same object. Version B is the one that pairs with the breaker via the
"body close through the extreme?" test and is the more internally consistent. **Do not
implement "mitigation block" without picking one and documenting the choice.**

### Which one to use

For an algorithm, the **breaker** is the only one of the three with a crisp, codeable
distinguishing test (body close through the OB extreme + subsequent structure shift). The
plain OB is the vaguest. `SMC_SPEC.md`/`FINDINGS.md` already record that OB scored ≤ random as
a leg-start marker on gold in this repo's own testing — that prior stands.

---

## 8. BALANCED PRICE RANGE (BPR) AND INVERSION FVG (IFVG)

### BPR

- **TRIGGER:** a bullish FVG and a bearish FVG **overlap in price**. The overlapping slice is
  the BPR `[search summary]`. Fully mechanical given the FVG definition (§2).
  ```
  bull_gap = (H[a-2], L[a])        # formed at bar a
  bear_gap = (H[b], L[b-2])        # formed at bar b, b > a
  bpr = (max(lows), min(highs)) if they intersect
  ```
- **ENTRY:** on return into the BPR; proximal edge or midpoint. `[VAGUE — both taught]`
- **STOP:** beyond the far edge of the BPR.
- **TARGET:** `[VAGUE]` — next liquidity pool.
- **TIME FILTER:** none intrinsic.
- **TIMEFRAME:** any.
- **CLAIMED WIN RATE:** none found with a number.
- **AMBIGUITIES:** (1) maximum bar separation between the two FVGs — never specified, and without
  a cap a BPR can be assembled from gaps hours apart; (2) minimum overlap size — never specified;
  (3) direction of the resulting trade when a BPR forms mid-range.

### IFVG (Inversion FVG)

- **TRIGGER:**
  1. An FVG exists.
  2. A candle **closes fully beyond** the gap's far boundary — "a wick through does not count,
     only a close" `[search summary, consistent]`. The gap is now inverted: a broken bullish FVG
     becomes bearish resistance, and vice versa.
  3. Price **retests** the inverted zone.
- **ENTRY:** on the retest — at the zone boundary, or at **consequent encroachment** (the 50%
  midpoint) `[search summary]`. Two answers again.
- **STOP:** beyond the IFVG extreme — below the IFVG low for a bullish IFVG `[search summary]`.
  Consistent across sources.
- **TARGET:** `[VAGUE]` — next liquidity pool.
- **TIME FILTER:** none intrinsic.
- **TIMEFRAME:** any; defined on the timeframe the close occurred on.
- **CLAIMED WIN RATE:** none found with a number.
- **AMBIGUITIES:**
  1. "Closes fully beyond the gap boundaries" vs "invalidated by a wick or close" — one source
     said both in different places. The close-only reading is the majority and is the codeable
     one.
  2. Does the inverting close have to be on the same timeframe the FVG was defined on? Unstated.
  3. How long does an IFVG remain valid? Unstated.
  4. How many retests before it is spent? Unstated.

**Assessment:** BPR and IFVG are, after the raw FVG, the **most mechanically specified objects
in the ICT toolkit** — both reduce to arithmetic on OHLC with a single ambiguity each (entry at
edge vs midpoint). They also have **zero published performance evidence of any kind**. High
specifiability, zero evidence.

---

## 9. THE CORE "SMC ENTRY": SWEEP → MSS → FVG

This is the union of §2/§3/§4c and deserves its own precise statement because it is what most
implementations actually code.

- **TRIGGER, in strict bar order:**
  1. **Sweep.** At bar `s`, price trades beyond a reference level `Lvl` (prior swing high/low,
     session high/low, PDH/PDL, equal highs/lows) and the bar **closes back inside**.
     Codeable form: `H[s] > Lvl and C[s] < Lvl` (buy-side sweep).
     `[VAGUE: minimum penetration, maximum penetration, how many bars are allowed for the
     close-back-inside, and which levels qualify as "liquidity". The mechanical implementation
     in §12.1 chose "prior 2-hour extreme" and "close back inside on the same bar" — the
     author's choices, not ICT's.]`
  2. **MSS / CHoCH.** At some bar `m > s`, a candle **body closes** through the most recent
     opposing swing point, in the direction opposite the sweep.
     - MSS and CHoCH denote the *same event*; CHoCH is the SMC term, MSS the ICT one
       `[search summary]`.
     - **MSS additionally requires displacement**; "every MSS is a CHoCH, but not every CHoCH
       qualifies as an MSS" `[search summary]`. Since displacement is undefined, **MSS is CHoCH
       plus an undefined filter.** In practice, code CHoCH and add your own displacement test.
     - **BOS** is the same break but *with* the trend (continuation), not against it.
     - Wick-through does not count. Body close only. `[search summary, consistent]` — codeable.
  3. **FVG.** The displacement leg from `s` to `m` leaves an FVG (§2 definition).
- **ENTRY:** limit at the FVG proximal edge, or at CE. Bar: whichever bar first trades into that
  price after `m`.
- **STOP:** two competing rules — (a) beyond the sweep extreme at bar `s`; (b) beyond the FVG's
  far edge. (a) is the ICT-2022 reading, (b) is the Silver Bullet reading. On gold these can
  differ by several dollars.
- **TARGET:** the liquidity on the opposite side that the sweep was "reaching for". `[VAGUE]`
- **TIME FILTER:** whatever killzone is overlaid.
- **TIMEFRAME:** levels M15/H1; sweep and MSS M5; entry M5/M1.
- **AMBIGUITIES:** all of §0.1, plus:
  1. **Swing definition.** MSS requires "the most recent opposing swing". No fractal order, no
     lookback, no alternation rule is given anywhere in ICT's material. This repo's
     `SMC_SPEC.md` §1 already supplies a concrete algorithm (R=3 minor / R=15 major, strict-left
     / non-strict-right, alternation filter) — **that algorithm is this repo's invention and
     should be treated as a parameter, not a rule.**
  2. Maximum bars allowed between sweep and MSS. Unstated.
  3. Maximum bars allowed between MSS and FVG fill. Unstated.
  4. What happens if price fills the FVG *before* the MSS confirms.

### CISD — a genuinely better-specified alternative to MSS

Worth noting because it is the one structural trigger with a crisp definition
`[search summary, consistent across sources]`:

> Mark the **opening price of the first candle in the last unbroken run of down-closing
> candles** into the low. A **body close above that opening price** is a bullish CISD.
> Wicks never count.

This is fully mechanical: no swing definition, no displacement threshold, no lookback
parameter. If a structural trigger is needed for a XAUUSD algorithm, **CISD is more
specifiable than MSS/CHoCH** and is the version used in the best-performing gold repo found
(§12.4).

---

## 10. OPTIMAL TRADE ENTRY (OTE)

- **TRIGGER:** an impulse leg exists, defined by a swing low and a swing high. Price retraces
  into the **0.62–0.79** retracement band of that leg `[search summary, unanimous]`, with
  **0.705** the preferred single level.
- **How the fib is anchored:** for a long, anchor **1.0 at the swing low, 0.0 at the swing high**
  of the impulse (i.e. drawn in the direction of the move being measured); mirror for shorts
  `[search summary, unanimous]`. Note the 0.705 level is not a standard Fibonacci number — it is
  the midpoint of 0.62 and 0.79.
- **ENTRY:** limit at 0.705 (or anywhere in 0.62–0.79). Most teachings additionally require an
  OB or FVG inside the band, and/or a CHoCH/BOS confirmation `[search summary]` — which makes it
  a confluence filter rather than a standalone entry.
- **STOP:** just beyond the **1.0 level** — the original swing low (long) / swing high (short)
  `[search summary, consistent]`. This is codeable and unambiguous once the swing is defined.
- **TARGET:** standard-deviation projections of the same leg, quoted as **−0.27**, **−0.62**,
  **−1.0**, **−2.0** `[search summary]`. −0.27 = first target; −0.62 = "close the majority";
  −1.0 = symmetrical projection (1× the leg); −2.0 = full expansion. Alternatively: the old
  high/low the leg was reaching for.
- **TIME FILTER:** none intrinsic.
- **TIMEFRAME:** any. The leg is usually marked on M15/H1, entered on M5/M1.
- **CLAIMED WIN RATE:** none found with a number and a method. **Measured: §12.2 shows −0.168R
  expectancy on synthetic data — see the caveat there.**
- **AMBIGUITIES:**
  1. **"Significant swing" is the entire model and it is undefined.** Which leg? Started where,
     ended where? Change the anchor by two bars and the 0.705 moves. This is the single biggest
     free parameter in OTE, and it is precisely the parameter a discretionary trader sets with
     hindsight.
  2. Band-vs-level: 0.62, 0.705, 0.79 or "anywhere between" — three entry prices.
  3. Whether an OB/FVG inside the band is required or optional.
  4. Whether the leg must have made a BOS first.
  5. Stop "just beyond 1.0" — how far beyond? Unstated. On gold this matters: a 1-tick buffer and
     a $1 buffer are different strategies.
  6. Risk geometry: entry at 0.705 with stop at 1.0 gives risk = 0.295 × leg and a −0.27 target
     gives reward = 1.0 − 0.705 + 0.27 = 0.565 × leg ⇒ **≈1.9R**. Entry at 0.62 gives ≈2.4R,
     at 0.79 gives ≈1.4R. The choice of level inside the band changes R by 70%. No source
     mentions this.

---

## 11. Quick mechanical-specifiability ranking

| object / model | % mechanically specified | remaining free parameters |
|---|---|---|
| FVG (3-bar) | ~100% | none (optionally: min gap size) |
| Consequent encroachment | 100% | none |
| Killzone / SB windows | ~95% | which variant; DST |
| Turtle Soup (Raschke 1995) | ~95% | tick buffer; exit rule |
| CISD | ~90% | none material |
| BPR | ~85% | max bar separation; min overlap |
| IFVG | ~85% | entry at edge vs CE; validity horizon |
| OTE | ~60% | **the swing anchor**; level in band; stop buffer |
| Breaker block | ~55% | zone bounds (body vs wick); displacement |
| Silver Bullet | ~55% | **bias**; sweep+MSS required?; entry price; stop reference |
| Sweep→MSS→FVG | ~45% | swing algo; displacement; sweep tolerance; bar windows |
| ICT 2022 model | ~40% | all of the above + daily bias |
| Judas Swing | ~40% | Asian bounds; sweep tolerance; **bias (circular)** |
| ICT Turtle Soup | ~35% | "visible stop concentration" |
| Unicorn | ~35% | breaker bounds; overlap minimum; displacement |
| Order block | ~30% | zone bounds; validity conditions; run-of-candles |
| Power of Three | ~10% | it is a post-hoc label, not a model |

---

## 12. ACTUAL BACKTESTS WITH REAL NUMBERS

Everything in this section was **read from the source page** (`github.com` is reachable). All
are self-reported by their authors and none is independently audited. Read the caveats.

### 12.1 Silver Bullet, fully mechanical, NQ futures — `[repo, read]`

`github.com/cjosh4toyotas-stack/silver-bullet-backtest`

| field | value |
|---|---|
| Instrument | NQ (E-mini Nasdaq 100) front-month continuous |
| Timeframe | M5 |
| Period | 2026-06-08 → 2026-09-22 (20,244 bars) |
| Trades | **29** (6 targets, 20 stops, 3 time exits) |
| Win rate | **31.0%** |
| Profit factor | **0.64** |
| Net P&L | −$4,405 (1 contract, $10 round-trip costs) |
| Avg/trade | −$152 |
| Max DD | $6,835 |

Rules as coded (note how much the author had to invent):
- Windows 03:00–04:00, 10:00–11:00, 14:00–15:00 NY.
- Sweep = bar takes out the **prior 2-hour extreme** and closes back inside; scanned from 30 min
  before the window.
- First FVG **≥ 0.5 pt** with a displacement candle closing in the bias direction, forming inside
  the window after the sweep.
- Limit at the **near gap edge**, must fill before window close.
- Stop **1 tick beyond the sweep extreme**; skipped if risk > 60 points.
- **2R** target; 2-hour time exit; max one trade per window.

**Methodology: stated, clear, and reproducible.** Cross-validated on ES and CL with identical
mechanics. **Sample is far too small (29 trades, 3.5 months) to conclude anything**, and the
author says so. But it is the only fully-specified mechanical SB test found, and it did not
reproduce anything close to the claimed 70–80%.

### 12.2 Seven ICT models, walk-forward — `[repo, read]` — **READ THE CAVEAT**

`github.com/skoolboykenny/skoolboykenny` PR #12. 200 days, 7 folds.

| Model | Trades | Win% | PF | Exp R | Total R | Max DD |
|---|---|---|---|---|---|---|
| Power of Three | 4 | 75.0% | 6.53 | +1.472 | +5.89 | 0.5% |
| Judas Swing | 10 | 50.0% | 2.51 | +0.889 | +8.89 | 1.7% |
| Silver Bullet | 57 | 17.5% | 1.14 | +0.180 | +10.27 | 12.6% |
| Optimal Trade Entry | 40 | 15.0% | 0.84 | −0.168 | −6.71 | 7.9% |
| Sweep to Sweep | 40 | 15.0% | 0.63 | −0.383 | −15.30 | 10.7% |
| Mentorship 2022 | 15 | 13.3% | 0.37 | −0.650 | −9.75 | 4.9% |
| Turtle Soup | 101 | 5.0% | 0.40 | −0.934 | −94.32 | 50.6% |

**CAVEAT — this is the most important line in this document.** The test data was a **Gaussian
random walk** with no trend, no session structure and no fat tails. The author's own conclusion:
*"every concept these models look for is defined against behaviour the data does not contain."*

So these are **not** market results. They are a **null-hypothesis / false-discovery
demonstration**, and as that they are extremely valuable:

- Turtle Soup came **top at +14.49R on 120 days and bottom at −94.32R on 200 days**, with
  **nothing about the model changed**.
- Power of Three "won" on 4 trades. Judas Swing "won" on 10.

**Use this as the calibration for reading every other ICT backtest you will ever see.** On pure
noise, a 7-model horse race produced a 75%-win-rate, PF 6.53 "winner". Any ICT result reported
on fewer than ~100 trades, or without an out-of-sample split, is indistinguishable from this.

### 12.3 Turtle Soup on XAUUSD — `[repo, read]`

`github.com/balaji4621/xauusd-turtle-soup-backtest`

| field | value |
|---|---|
| Instrument | XAUUSD |
| Timeframe | M15 |
| Rules | enter immediately on liquidity sweep; tight stop relative to sweep point |
| Net return, **zero costs** | **+1,371R** |
| Net return, **1.5-pip spread** | **−2,788R** |
| Period | **not stated** — a real methodology gap |

The author names the mechanism: the **"Spread Trap"** — the stop is by construction tight
relative to the sweep, so the spread is a large fraction of R on every trade. The team then
abandoned the reversal model and rebuilt on trend-following FVG mechanics on H4/D1, reporting
**+251R at 38.2% win rate** on daily.

**This is the single most directly relevant result in the document for a XAUUSD system.** A
4,159R swing from a 1.5-pip spread. It aligns with this repo's own `FINDINGS.md` §7 ("any zone
thinner than 0.35 is noise"). **On gold, tight-stop sweep reversals are a cost-structure problem
before they are a signal problem.**

### 12.4 Gold ICT order-flow + ML filter — `[repo, read]` — best reported, treat carefully

`github.com/Jupiterix/algo-trading`

| field | value |
|---|---|
| Instrument | XAUUSD, M5 |
| In-sample | 2016 onward |
| Out-of-sample | 2020–2026, five independent walk-forward windows |
| OOS trades | **622** |
| Win rate | **39.4%** |
| Expected value | **+2.13R** |
| Profit factor | **4.74** |
| Max DD | **−5.37%** |

Signals: CISD, supply/demand zones, BOS/CHoCH, FVG, killzones (London 07:00–10:00 UTC, NY
12:00–15:00 UTC), liquidity sweeps. **Plus a Random Forest filter requiring P(win) ≥ 0.60
before execution.**

Methodology is stated: *"Parameters are re-optimised on in-sample data only. OOS results are
never touched during optimisation."* Author's own caveats: hypothetical backtest, MT4
file-bridge dependency, no third-party audit.

**Be sceptical anyway.** PF 4.74 with +2.13R expectancy at a 39.4% win rate implies average
winners around 8R. That is an extraordinary claim. Five walk-forward windows is five
opportunities to pick a configuration, and the ML filter has its own large parameter surface
that walk-forward on the same data does not fully protect against. 622 trades across 6 years is
~100/year, which is thin for a M5 system and suggests heavy filtering — the ML gate doing most
of the work. **The ICT concepts here are feature inputs to a classifier, not the strategy.**
If anything in this document motivates a build, this is the architecture worth copying: ICT
objects as *features*, a learned filter as the *decision*.

### 12.5 XAUUSD sweep-and-reclaim, pre-registered — `[repo, read]` — the cleanest negative

`github.com/tebibusolomonka-ops/gold-quant-desk`

| field | value |
|---|---|
| Instrument | XAUUSD, M15 |
| Period | 2021-01-03 → 2026-07-24 (131,469 bars) |
| Trades | **1,953** |
| Win rate | **46.2%** |
| Expectancy | **−0.159R** |
| Profit factor | **0.73** |
| t-statistic | **−6.27** |

Rules: sweep a prior high/low, close back inside within K bars (K tested 1–5) on volume
> 1.5 × SMA(20), enter on the reclaim, stop = sweep extreme ± 0.25 × ATR(14). Level modes tested:
PIVOT, SESSION, PDH/PDL.

Methodology is the **best of any source in this document**: modelled costs, anti-look-ahead
pivots, train/validate/vault splits, a **pre-registered prediction** (that edge would decay as
K widened), and a multiple-testing-corrected significance bar of |t| ≥ 3.3.

Results: **the pre-registered prediction failed entirely** — no decay pattern. Average R was
~3.3 price points, and *"realistic spreads consumed roughly 9% of every R before the trade has
an opinion about anything."* The author's automated rulebook **suspended the strategy on the
evidence**, against prior conviction.

**This is the strongest single piece of evidence in the document and it is negative.** 1,953
trades, 5.5 years, XAUUSD, pre-registered, cost-aware, t = −6.27. The core SMC primitive —
sweep and reclaim — is **significantly negative on gold** at M15 over 5.5 years.

### 12.6 FVG + OB EA on XAUUSD — `[repo, read]`

`github.com/foeed/FvgGold-EA`

| field | value |
|---|---|
| Instrument | XAUUSD.m, M15 |
| Jan–Jul 2026 (6 mo) | 64 trades, **45.3%** WR, +48.7% return |
| Apr–Jul 2026 (3 mo) | 35 trades, **40.0%** WR, +5.2% return |
| PF / max DD | **not disclosed** |

Rules: 3-bar FVG, quality score 0–100 across five weighted factors, min score 50; +20 bonus for
OB overlap; impulse body ≥ ATR × 1.5 (**this is the only numeric displacement threshold found
anywhere in the entire research** — and it is this author's invention); lookback 50 bars; buy
limit just above FVG bottom edge; stop beyond opposite FVG edge + 3.0 price-unit buffer;
**fixed 1.5 R:R**; London 07:00–10:00 and overlap 12:00–16:00 GMT session filter.

**Sample of 64 trades over 6 months is too small.** No PF, no drawdown, no out-of-sample split.
The two windows overlap, so the 3-month result is a subset, not a validation. Treat as an
existence proof of a codeable rule set, not as evidence of edge.

### 12.7 Claims found with NO usable evidence

| claim | source | why it fails |
|---|---|---|
| SMC: 61% WR, PF 2.17, +2.27R over **2,600 trades**, 10 assets, Jan 2024–Mar 2026 | Medium `@QuantumAlgo` `[search summary — page not opened]` | No rule specification, no code, no data, no cost model, no out-of-sample split. +2.27R average at 61% WR implies ~5.4R average winners — commercially implausible. Treat as content marketing. |
| Discretionary SMC traders report 70–80%; algorithmic tests of the *same rules* give **~41%**; raw setups 38–48%; with killzone + HTF filters 55–62% at 1:2–1:2.5 | fxnx.com `[search summary]` | No sample size, no period, no instrument, no method. The *direction* (discretionary claims collapse when mechanised) matches §12.1/§12.5 and is credible as a qualitative point only. |
| Silver Bullet 70–80% | unattributed, everywhere | Never once accompanied by a sample size. |
| Unicorn 80% | YouTube title `[search summary]` | Title only. |
| ICT midnight-open retracement: price returns to the 00:00 NY open during the NY session **66%** of the time; but only **47%** on a recent 6-month window; YM 63–67% | edgeful `[search summary]` | edgeful is a legitimate stats vendor and this is the closest thing to a real base-rate statistic found. Instruments are index futures, **not gold**. The 66% → 47% spread across windows is itself the warning. |
| "74% win rate" headline exposed as a **7-month cherry-pick** after an honest 3-year backtest | `[search summary, github]` | Cited here as a cautionary example. |
| SMC "liquidity sweep + reclaim on volume": PF **1.70** over 3-month windows, PF **0.73** over the full 5.5 years | same repo as §12.5 | The clearest illustration in the whole corpus of why short-window ICT backtests are worthless. |

### 12.8 Evidence summary

**There is no ICT model with a credible, cost-aware, adequately-sized, out-of-sample positive
backtest in the public domain.** The only two studies in this document with proper
methodology and adequate samples are §12.5 (1,953 trades, pre-registered, **negative**,
t = −6.27) and §12.4 (622 OOS trades, positive but ML-gated and self-reported). Every positive
claim with a big number attached (70%, 80%) has zero methodology behind it.

---

## 13. Recommendations for this repo's XAUUSD system

1. **Do not implement "ICT models". Implement objects and test them as features.** FVG, CE,
   BPR, IFVG, CISD, killzone flags, sweep-distance, midnight-open displacement are all
   computable. The "models" are assemblies of those objects glued together with undefined
   predicates. §12.4 is the only positive result found and it treats ICT purely as a feature set
   behind a learned filter.
2. **The cost structure is the binding constraint on gold, not the signal.** §12.3 (+1,371R →
   −2,788R on a 1.5-pip spread) and §12.5 ("spreads consume ~9% of every R") both say the same
   thing, independently. Any model whose stop is "just beyond the sweep wick" is a cost problem
   before it is a signal. This matches `FINDINGS.md` §7. **Reject tight-stop sweep reversals on
   XAUUSD a priori** unless a cost model proves otherwise.
3. **Treat the sweep-and-reclaim primitive as refuted until shown otherwise on our own data.**
   §12.5 is 1,953 trades at t = −6.27 on exactly our instrument and a reasonable timeframe.
4. **Use CISD instead of MSS/CHoCH** wherever a structural trigger is needed. It is the only
   structure definition that does not require inventing a swing-detection algorithm (§9).
5. **Prefer the objects at the top of §11.** FVG/CE/BPR/IFVG/CISD cost nothing in free
   parameters. OB, Unicorn, PO3 and ICT-Turtle-Soup each require inventing 2–4 thresholds — every
   one is an overfitting channel.
6. **Set a minimum sample bar before believing anything.** §12.2 produced a 75% / PF 6.53
   "winner" on a random walk. Adopt that repo's implicit standard: ≥ 100 trades, out-of-sample,
   costs modelled, and a pre-registered prediction. Anything less is §12.2.
7. **Test the one cheap base rate nobody publishes:** how often does the London session
   (02:00–05:00 NY) sweep the Asian range extreme and then close the NY session on the other
   side? That single number decides whether Judas Swing exists on gold, it is one query against
   data we already have, and no source in this research had it.
8. **Fix the timezone layer first.** DST-aware NY-local conversion from UTC bar timestamps, plus
   the LBMA 10:30/15:00 London fixes and the 08:20/08:30 ET COMEX-and-data block as gold-native
   time features. The gold-specific clock events are better motivated than ICT's killzones and
   nobody in the ICT corpus mentions them.

---

## 14. Source list

Opened and read (primary): `github.com/cjosh4toyotas-stack/silver-bullet-backtest`,
`github.com/skoolboykenny/skoolboykenny/pull/12`, `github.com/balaji4621/xauusd-turtle-soup-backtest`,
`github.com/Jupiterix/algo-trading`, `github.com/tebibusolomonka-ops/gold-quant-desk`,
`github.com/foeed/FvgGold-EA`, `github.com/Koestas/micro-futures-analyzer`.

Search-summary only, never opened (each is a commercial content site with an incentive to
present ICT favourably; none published a methodology): innercircletrader.net,
theinnercircletraders.com, ictkillzone.com, luxalgo.com, fxnx.com, fxopen.com, tradingfinder.com,
backtrex.com, arongroups.co, tradingstrategyguides.com, quantum-algo.com, grandalgo.com,
fluxcharts.com, howtotrade.com, litefinance.org, edgeful.com, tradingview.com, medium.com,
statoasis.com, zarixschool.com, phidiaspropfirm.com.

**No primary ICT source (Michael J. Huddleston's own videos or written material) was accessible
in this environment.** Every rule in §1–§11 is a third-party transcription. Where transcriptions
conflict, the conflict is recorded above and must be resolved by the implementer as a
documented parameter choice.

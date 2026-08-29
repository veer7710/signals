# DEFINITIONS — liquidity / SMC / market-structure concepts as objective, no-lookahead rules

Purpose: the definitional backbone for an intraday XAUUSD system (M15 bias →
M5 setup → M1 trigger). Every rule below must be computable at the close of a
bar from bars that have already closed. Where a concept cannot be defined that
way, that is recorded as a finding, not patched with an invented rule.

Written: 2026-08-29. Status of this document: **specification, not evidence.**
Nothing here is a claim that any of it is profitable. E-003 already showed that
the *naive* sweep rule has no edge on gold 1h and dies as costs rise
(`JARVIS/state/EXPERIMENTS.md`). These definitions exist so that the
sophisticated version can be tested fairly instead of hand-waved.

## METHOD NOTE — read before trusting any citation here

Outbound network access in this session was restricted by the egress proxy.
`www.tradingview.com`, `www.luxalgo.com`, `gist.githubusercontent.com`,
ScienceDirect, SSRN and NBER were all **blocked**. `raw.githubusercontent.com`
and the search index were reachable.

Consequently there are two tiers of citation in this document:

- **[VERIFIED]** — I fetched and read the source code or text myself. This
  applies to exactly one artefact: `smartmoneyconcepts/smc.py` from
  `joshyattridge/smart-money-concepts` (987 lines, read in full). Every claim
  about that library's behaviour below is from the code, and line numbers are
  given.
- **[2nd-hand]** — from search-engine synthesis of snippets and abstracts. I
  did **not** open the underlying page or PDF. Treat as a pointer to check,
  never as an established number.

I am flagging this rather than implying I read everything, because a
definitions document whose citations are secretly unverified is worse than no
document.

---

# BOTTOM LINE

## Tier 1 — objectively codeable, zero residual judgement

Given a fixed parameter vector these produce a deterministic, replayable,
bit-identical answer in Pine v6 and MQL5:

swing high/low (pivot-K) · HH/HL/LH/LL · BOS · CHoCH · equal highs/lows
(with a stated tolerance) · previous day/week high-low (with a stated
rollover) · session high/low (with a stated timezone rule) · fair value gap ·
displacement · consolidation detectors · regime metrics (ER, ADX, ATR
percentile, CHOP) · all seven sweep classes · structural invalidation.

## Tier 2 — codeable only after you impose an arbitrary convention

These have no single correct definition. Multiple incompatible definitions are
in active use and each is internally consistent. You must *choose* one and
declare it; the choice is a modelling decision, not a discovery, and it must be
included in sensitivity testing:

**MSS** · **protected high / protected low** · **internal vs external
structure** · **order block** · **breaker block** · **liquidity strength
score** · the boundary between **Type C and Type A/B sweeps**.

The specific danger: a strategy that only works under one convention and dies
under an equally defensible one has not found an edge, it has found a
convention.

## Tier 3 — irreducibly subjective or unfalsifiable as commonly stated

- **Inducement.** Every definition found reduces to "the liquidity that gets
  taken *before the real move*". The real move is only identifiable after it
  happens. As stated this is unfalsifiable ex ante. A codeable *proxy* is given
  in §L6, but it is a convention wearing the word's clothes.
- **"Valid" / "major" / "high-probability" POI, order block, or level.** In
  every source found, validity is conferred by what price does afterwards.
  Circular.
- **"Smart money intent", "the algorithm is seeking liquidity".** Not
  observable on any retail XAUUSD feed. There is no resting-order data. Every
  liquidity construct in this document is a *proxy inferred from price*, and
  should be named as such in code and in reports.
- **Continuation vs reversal consolidation, decided before the break.** No
  source found offers a pre-break rule that is not just "look at the trend".
  See §CN3 — it is stated as an open, testable hypothesis with a test spec,
  not as a definition.

## The finding that matters most

**The community's own reference implementations contain lookahead.** The most
widely used open-source Python SMC library — the one a researcher would
naturally reach for to "test SMC properly" — has at least four distinct
lookahead defects, all verified in source (§RT1–§RT4). A backtest built on it
will report an edge that cannot be traded. Any comparison against "published
SMC results" must first ask whether the implementation was causal. Most were
not.

Second finding: **the seven sweep classes are not seven values of one variable.**
They conflate three orthogonal axes — morphology (A/B/C), confirmation
(D/E), and outcome (F/G) — into a single list. Types F and G are *outcome
labels knowable only in hindsight*; they cannot be entry signals. A reversal
trader at the moment of entry cannot distinguish D/E from F. That is not a
flaw in the definitions, it is the actual structure of the problem, and it is
why the naive test in E-003 was a fair test of what it tested. §SW.

---

# NOTATION AND GROUND RULES

- Bars are indexed by integer `i`, increasing with time. `i` always denotes the
  **most recently closed** bar. Bar `i+1` is forming and is invisible.
- `O[i] H[i] L[i] C[i] V[i]` are that bar's open/high/low/close/volume.
  On XAUUSD, `V` is **tick volume**, not traded volume. Any rule using volume
  must say so and must be re-checked across brokers, because tick volume is
  broker-specific and not comparable between feeds.
- `ATR[i]` = Wilder ATR over `ATR_LEN` bars, using bars `≤ i`.
- **Threshold convention:** when a bar is tested against a volatility
  threshold, the threshold uses `ATR[i-1]`, not `ATR[i]`. Otherwise the bar
  inflates the ATR it is being judged against, which mutes exactly the large
  bars you are trying to detect. This one choice measurably changes
  displacement counts.
- "Known at bar `k`" means: the boolean is computable from `O,H,L,C,V` for all
  bars `≤ k`, and never changes afterwards. **Monotonic and final.** Any value
  that can change after it is first emitted is repainting, full stop.
- All comparisons use `>` / `<` strictly, except where a tie rule is stated.
  Ties are not rare on XAUUSD M1 — the tick size is 0.01 and quiet Asian bars
  produce genuinely equal highs. Every tie must be resolved explicitly or Pine
  and MQL5 will silently disagree.
- **Timeframe subscript.** Where a rule is applied on more than one timeframe,
  parameters are subscripted (`K_M15`, `K_M5`, `K_M1`). Sharing one value
  across timeframes is a legitimate constraint that saves parameters; it is the
  default recommendation here.

---

# PART 1 — STRUCTURE

## S1. Swing high / swing low

### (a) Competing definitions in the wild

1. **Williams fractal (pivot-2).** A bar whose high exceeds the highs of the
   two bars either side; five-bar pattern. Confirmed two bars late. Bill
   Williams, *Trading Chaos*; TradingView's implementation description
   [2nd-hand]. Search snippet: "there will always be considerable fractal lag
   (two or more candlesticks)" — the lag is acknowledged in the indicator's own
   documentation.
2. **Pivot-N / `ta.pivothigh(N,N)`.** Generalised fractal: highest high across
   `N` left + pivot + `N` right. "Pivot highs and lows are simply the highest
   high for x bars back and x bars forwards" [2nd-hand]. `N=3` (7-bar window)
   is the common TradingView default.
3. **Pivot-50 as used by the reference SMC library.** `smc.py`
   `swing_highs_lows(swing_length=50)` — and note it does `swing_length *= 2`
   then takes a 100-bar rolling max shifted by 50, so the default is ≈50 bars
   **each side**, i.e. a **50-bar confirmation lag**, not 50 total. [VERIFIED,
   smc.py L137–160]. Almost certainly not what most users of that default
   believe they are getting.
4. **ZigZag / reversal-threshold swings.** A new pivot is fixed only once
   price retraces by a fixed % or ATR multiple from the extreme. Lag is
   *variable and unbounded* — a strong trend can leave the last pivot
   unconfirmed for hundreds of bars. "The most recent swing point is not final
   until price moves far enough in the opposite direction… the last leg extends
   or relocates as new bars arrive" [2nd-hand].
5. **ATR-adjusted / significance-filtered swings.** Pivot-N plus a requirement
   that the swing be at least `M × ATR` from the preceding opposite pivot,
   to suppress noise pivots without lengthening `N`.

### (b) Where they disagree, and why it matters

- **Lag.** Fractal = 2 bars. Pivot-3 = 3 bars. The library default = 50 bars.
  On M5, 50 bars is over four hours. Every downstream concept (BOS, protected
  low, liquidity level) inherits this lag exactly. A strategy that "enters on
  the sweep of the swing low" with a 50-bar swing definition is entering on a
  level that only became knowable four hours after it formed. That is not
  wrong — but it is a completely different strategy from the pivot-2 version,
  and the two will not have the same trade set, the same count, or the same
  edge.
- **Bounded vs unbounded lag.** Pivot-N has a *fixed, known* lag. ZigZag does
  not. This is decisive: a fixed lag can be honestly simulated; an unbounded
  one means the number of confirmed pivots at any moment depends on the future.
  **ZigZag is rejected as a primitive here** for exactly that reason. It may be
  used for visualisation only, never as a signal input.
- **Tie handling.** Definitions 1–3 all break down on equal highs. Pine and
  MQL5 default tie behaviour is not guaranteed identical. Two equal highs
  separated by one bar: is that one pivot or none? Unstated in every source
  found.
- **Alternation.** Raw pivot-N can emit two consecutive highs with no low
  between them. `smc.py` post-processes to force alternation by deleting the
  weaker of each consecutive pair [VERIFIED, L165–192] — but does so in a
  *global while-loop over the entire array*, which is a batch operation that
  cannot be reproduced causally (§RT2).

### (c) Canonical definition

```
PARAMS: K            # pivot half-width, bars each side
        M_SWING_ATR  # optional significance filter, 0 disables

# --- raw pivot, evaluated at the close of bar i ---
# candidate pivot bar is p = i - K
is_pivot_high(p) evaluated at bar i where i = p + K:
    left_ok  = for all k in 1..K:  H[p] >= H[p-k]     # ties -> earlier bar wins
    right_ok = for all k in 1..K:  H[p] >  H[p+k]     # strict; forces uniqueness
    return left_ok AND right_ok

is_pivot_low(p) evaluated at bar i = p + K:
    left_ok  = for all k in 1..K:  L[p] <= L[p-k]
    right_ok = for all k in 1..K:  L[p] <  L[p+k]
    return left_ok AND right_ok

# --- alternation, causal version ---
# maintain: last_confirmed_pivot = (type, bar_index, level)
on confirming pivot_high at p with level H[p]:
    if last_confirmed_pivot.type == HIGH:
        if H[p] > last_confirmed_pivot.level:
            REPLACE last_confirmed_pivot with this one   # emit "pivot revised"
        else:
            DISCARD this pivot                            # emit nothing
    else:
        if M_SWING_ATR > 0 and
           abs(H[p] - last_confirmed_pivot.level) < M_SWING_ATR * ATR[p]:
            DISCARD                                       # not significant
        else:
            APPEND this pivot; last_confirmed_pivot = it
# symmetric for pivot_low
```

Note the honest consequence of causal alternation: **the most recent pivot of a
given type can still be replaced by a higher one later.** This is unavoidable
— it is the same information problem ZigZag has — but here it is *bounded and
explicit*: only the newest pivot of each type is mutable, all older ones are
frozen. Downstream rules must therefore only ever reference **the newest
pivot that has already been superseded by an opposite-type pivot**, which is
immutable. Call this the *sealed* pivot. Use sealed pivots for levels;
never use the tip.

### (d) Confirmation lag

A pivot at bar `p` is first knowable at bar **`p + K`**. Not earlier, ever.
Its *sealing* (immutability) happens at the confirmation bar of the next
opposite-type pivot, which is variable — but sealing only ever removes
candidates, never adds them, so a rule that requires a sealed pivot is causal.

### (e) Repaint trap

Plotting the pivot at bar `p` (where the chart naturally draws it) and then
reading it at bar `p` in a backtest. The chart is drawing `K` bars in the past
what was learned at `p+K`. In Pine, `ta.pivothigh(K,K)` **returns the value on
the bar where it is confirmed** but the common `plot(..., offset=-K)` idiom
moves the mark back — and people then reference the plotted series. In MQL5,
the equivalent error is indexing an indicator buffer at `shift = K` without
checking that `Bars` has advanced past confirmation.

### (f) Parameters

| name | range | default | note |
|---|---|---|---|
| `K` | 1–8 | 2 (M1/M5), 3 (M15) | direct lag in bars |
| `M_SWING_ATR` | 0 or 0.25–1.5 | 0 | 0 = disabled; prefer disabled |

### (g) Objectively measurable?

**Yes, fully.** Tier 1. The only content is the parameter choice.

---

## S2. HH / HL / LH / LL

### (a) Competing definitions

1. Compare each confirmed pivot to the previous pivot of the *same type*
   (high vs high, low vs low). Universal in textbook Dow-theory presentations.
2. Compare to the previous *two* same-type pivots (requires a sequence).
3. Compare using a tolerance band so that near-equal pivots are labelled
   "equal high" rather than forced into HH or LH — the SMC "EQH/EQL" case.
4. `smc.py` sidesteps labels entirely and encodes the pattern directly into its
   BOS/CHoCH tests as ordering constraints on the last four pivot levels
   [VERIFIED, L253–330].

### (b) Disagreement

Whether a "flat" comparison exists at all. Definition 1 has no ties by
construction (with real-valued prices ties are measure-zero — but on a
0.01-tick instrument they are *not*), so it will label a 2-cent difference as a
genuine HH. Definition 3 introduces a third state. This matters because EQH/EQL
is the single most important liquidity construct downstream: if you have no
tolerance, you have no equal highs, and half the liquidity model vanishes.

### (c) Canonical definition

```
PARAMS: EQ_TOL_ATR    # tolerance for "equal", in ATR units

label(pivot_n, pivot_{n-1}) for same-type consecutive pivots:
    d = level(pivot_n) - level(pivot_{n-1})
    tol = EQ_TOL_ATR * ATR[confirm_bar(pivot_n)]
    if abs(d) <= tol:  return EQUAL
    if type == HIGH:   return (d > 0) ? HH : LH
    if type == LOW:    return (d > 0) ? HL : LL
```

`ATR` is evaluated at the **confirmation bar of the later pivot** — a causal
timestamp. Never at "now", or the label of an old pivot pair changes as ATR
drifts, which is repainting a label.

### (d) Lag

Known at `confirm_bar(pivot_n)` = `p_n + K`. No extra lag beyond S1.

### (e) Repaint trap

Recomputing the label with today's ATR. The label of a 2023 pivot pair must
never change in 2026.

### (f) Parameters

| name | range | default |
|---|---|---|
| `EQ_TOL_ATR` | 0.02–0.30 | 0.10 |

Shared with EQH/EQL (§L2) — **do not introduce a second tolerance**.

### (g) Measurable? Yes, Tier 1, conditional on declaring the tolerance.

---

## S3. BOS vs CHoCH vs MSS — resolving the three-way confusion

### (a) Competing definitions

1. **BOS = continuation, CHoCH = reversal.** "BOS occurs when price breaks a
   swing high in an uptrend or swing low in a downtrend, confirming trend
   continuation… CHoCH occurs when price breaks structure in the opposite
   direction… the earliest warning that the trend may be reversing"
   [2nd-hand, fxopen / quantum-algo]. This is the dominant retail usage.
2. **MSS = CHoCH + displacement.** "An MSS embodies the principles of a CHoCH
   but with additional confirmation… it then proceeds to break a strong swing
   point with a 'displacement'" [2nd-hand, quantum-algo]. Under this reading
   MSS ⊂ CHoCH.
3. **MSS = synonym for CHoCH.** Used interchangeably across large parts of the
   ICT-derived material; no distinguishing rule offered.
4. **MSS = the ICT-native term, CHoCH = the SMC-native term for the same
   event**, with BOS reserved for continuation. Common in "abbreviation
   glossary" content [2nd-hand, tradingfinder].
5. **`smc.py`'s operational definition** [VERIFIED, L253–330]: given the last
   four alternating pivot levels `[l4,l3,l2,l1]` (oldest→newest) with types
   `[-1,1,-1,1]` (low,high,low,high):
   - bullish **BOS** iff `l4 < l2 < l3 < l1`
   - bullish **CHoCH** iff `l1 > l3 > l4 > l2`
   and the mirror for bearish. Note these are pure *orderings of four pivot
   levels* — displacement plays no part, and the library has no MSS at all.

### (b) Where they disagree, and why it matters

- **MSS is the problem term.** Definitions 2, 3 and 4 are mutually
  incompatible: under (2) MSS is strictly rarer than CHoCH, under (3) it is
  identically as common, under (4) it depends which dialect the author speaks.
  There is no way to write "detect MSS" that satisfies all three.
  **Resolution adopted here: the word MSS is banned from the specification.**
  Use `CHOCH` and `CHOCH_D` (CHoCH whose breaking leg contains a displacement
  bar). Every published usage of "MSS" maps onto one of those two. This costs
  nothing and removes an entire class of ambiguity.
- **Break by close or by wick?** Sources are almost universally silent. This is
  the single highest-impact unstated choice in the whole framework — a
  wick-break BOS on M1 gold fires several times more often than a close-break
  BOS. `smc.py` exposes it as `close_break: bool = True` [VERIFIED, L224], so
  its own author recognised the ambiguity. Adopt **close-break** as canonical:
  it is the more conservative, it is what the trend state should hinge on, and
  wick-breaks are separately captured as sweeps (§SW) — which is precisely the
  distinction the whole liquidity thesis rests on. If a wick break of a level
  and a close break of a level are treated identically, "sweep" is not a
  concept you can express.
- **Which high do you break?** The last pivot high, the highest recent pivot
  high, or the *sealed* pivot high. Using the tip (§S1) makes the break level
  mutable.
- **Does a BOS require prior structure?** In (5) it needs four pivots. In (1)
  it needs a declared trend, which needs… structure. Definitions 1 and 5 differ
  in the first few bars of any dataset and after every regime break.

### (c) Canonical definition

```
STATE (carried across bars, updated only at bar close):
    trend        in {UP, DOWN, NONE}     # init NONE
    ref_high     = level of the newest SEALED pivot high      (or NONE)
    ref_low      = level of the newest SEALED pivot low       (or NONE)

at close of bar i:
    broke_up   = (ref_high != NONE) and (C[i] > ref_high)
    broke_down = (ref_low  != NONE) and (C[i] < ref_low)

    if broke_up and broke_down:            # engulfing bar breaks both
        resolve by |C[i]-ref_high| vs |C[i]-ref_low|:
            the FARTHER breach wins; if exactly equal, emit NEITHER.
        # this case must be logged; on M1 gold it is not rare during news

    if broke_up:
        event = (trend == UP)   ? BOS_BULL :
                (trend == DOWN) ? CHOCH_BULL : BOS_BULL   # NONE -> treat as BOS
        trend = UP
        broken_level = ref_high
        ref_high = NONE          # consumed; next sealed pivot high replaces it
    elif broke_down:
        event = (trend == DOWN) ? BOS_BEAR :
                (trend == UP)   ? CHOCH_BEAR : BOS_BEAR
        trend = DOWN
        broken_level = ref_low
        ref_low = NONE
    else:
        event = NONE

# displacement-qualified variant, same bar:
    CHOCH_D = (event in {CHOCH_BULL, CHOCH_BEAR}) and displacement_leg(i)
    # displacement_leg(i) = at least one displacement bar (§D1) in the same
    # direction within the last DISP_LOOKBACK bars ending at i, inclusive.
```

**A level is consumed on first close through it.** It never produces a second
BOS. Without this, a level in a chop zone emits a BOS on every re-cross.

### (d) Confirmation lag

Let the reference pivot be at bar `p`, confirmed at `p+K`.
The break **cannot** occur on bar `p+K`: the pivot's own right-side condition
requires `H[p+K] < H[p]`, hence `C[p+K] < H[p]`. So:

> **Earliest possible BOS/CHoCH bar = `p + K + 1`.**

Total lag from the structural event to the tradable signal is therefore
`K + 1` bars *minimum*, plus however long price takes to reach the level.
`CHOCH_D` adds nothing if the displacement bar is the breaking bar itself; it
adds up to `DISP_LOOKBACK` bars of context but no extra lag.

### (e) Repaint trap

Three, in increasing subtlety:

1. Using the unsealed pivot tip as `ref_high`. The level moves.
2. **The `smc.py` trap** [VERIFIED, L253–330 and L358–370]: the library stamps
   the BOS/CHoCH flag at array position `last_positions[-2]` — the
   *second-most-recent pivot*, which is **before** the bar that broke anything
   — and then, at L358–370, **deletes every BOS/CHoCH that was never
   subsequently broken**. So the value sitting at bar `i` was decided by bars
   after `i`, twice over. A backtest that reads `bos[i]` at bar `i` is reading
   the future. This is the most consequential defect found in this review,
   because this library is a natural first choice for anyone trying to test SMC
   "properly", and its output is not causal.
3. Recomputing the trend state from scratch over the whole history on every
   bar. State machines must be advanced forward, never re-derived, or an
   ambiguity resolved one way early in the series can flip later.

### (f) Parameters

| name | range | default | note |
|---|---|---|---|
| break mode | {close, wick} | close | structural choice, test both |
| `DISP_LOOKBACK` | 1–5 | 3 | only for `CHOCH_D` |

No other new parameters — inherits `K`.

### (g) Measurable?

**BOS and CHoCH: Tier 1**, once break-mode and sealed-pivot rules are declared.
**MSS: Tier 2 and best deleted** — it is a word, not a rule.

---

## S4. Protected high / protected low

### (a) Competing definitions

1. The swing low that *originated* the leg which produced the most recent
   bullish BOS — "the low that must hold for the uptrend to remain valid".
2. The lowest low between the previously-broken high and the breaking bar.
3. The last confirmed swing low prior to the BOS bar (may sit anywhere in the
   leg).
4. In inducement-based dialects: the low *after* the inducement was taken —
   which makes it depend on Tier-3 machinery.

### (b) Disagreement and why it matters

(1) and (3) coincide when the leg contains exactly one pivot low and diverge
when it contains several — which on M1 is most of the time. (2) requires no
pivot machinery at all and is therefore both cheaper and more robust, but can
land on a low that no pivot rule would recognise. Since the protected low is
what a structure-based **stop** hangs on, the three choices produce materially
different R-multiples on the same trade. That means backtested expectancy is
sensitive to a definition nobody in the source material bothers to pin down.

### (c) Canonical definition

```
On a BOS_BULL or CHOCH_BULL at bar i with broken_level from pivot bar p_h:
    protected_low  = min( L[j] for j in [p_h .. i] )
    protected_low_bar = argmin of the above; ties -> LATEST bar
On a BOS_BEAR or CHOCH_BEAR at bar i with broken_level from pivot bar p_l:
    protected_high = max( H[j] for j in [p_l .. i] )
    protected_high_bar = argmax; ties -> LATEST bar
```

Definition (2) is chosen because it is fully determined by the bars in the leg,
needs no second pivot pass, cannot be affected by `K`, and is identical in Pine
and MQL5. It is a convention — say so in the report.

The protected level is **replaced** on the next same-direction BOS and
**discarded** on a CHoCH against it.

### (d) Lag

Known at the same bar `i` as the BOS/CHoCH that created it. Zero extra lag.

### (e) Repaint trap

Extending the min/max window past `i` as new bars arrive ("the protected low
keeps getting lower"). The window is closed at `i` and frozen.

### (f) Parameters

None. This is the argument for definition (2).

### (g) Measurable? Tier 2 — objective once the convention is declared.

---

## S5. Internal vs external structure

### (a) Competing definitions

1. **Two pivot lengths on one timeframe.** External/"swing" structure from a
   long pivot length, internal from a short one. This is LuxAlgo's approach:
   "internal and swing structure are distinguished with dashed internal labels
   tracking the fast rhythm inside the larger moves marked by solid swing
   lines" [2nd-hand].
2. **Two timeframes.** External = M15 structure, internal = M5/M1 structure.
3. **Containment.** Internal structure = all pivots strictly between two
   consecutive external pivots, regardless of how each was detected.
4. **Fractal recursion** — internal structure of internal structure, ad
   infinitum. Attractive, unbounded, and a parameter factory.

### (b) Disagreement

(1) and (2) are *not* equivalent, and the difference is not cosmetic: a
pivot-15 on M1 is not the same object as a pivot-3 on M15, because the M15 bar
boundaries impose a grid that the M1 rolling window does not. They agree on
strong swings and disagree constantly on marginal ones. (2) also introduces
timeframe-alignment hazards absent from (1) — see §RT5.

For a M15→M5→M1 system, (2) is what the system is *already* doing, so adding
(1) on top means two nested definitions of the same idea. That is exactly how a
parameter count reaches 748.

### (c) Canonical definition

```
Adopt (2) + (3):
    EXTERNAL structure = the BOS/CHoCH state machine (§S3) run on M15.
    INTERNAL structure = the same state machine run on M5 (and M1),
                         with parameters K_M5 / K_M1.
    An internal event is labelled CONTAINED if it occurs strictly between the
    bar of the last external pivot and the current bar, and its broken_level
    lies strictly inside [external_ref_low, external_ref_high].
    An internal event that breaks an external level is NOT internal — it is
    reported as external and the internal label is suppressed.
```

Rule: **an event is counted at exactly one level of the hierarchy.** Without
this, a single M15 BOS is also an M5 BOS and an M1 BOS, and any "confluence
count" is triple-counting the same event — a very common way to manufacture a
score that looks discriminating and is not.

### (d) Lag

Internal event: `K_TF + 1` bars of its own timeframe.
An M15 external event is not knowable until the M15 bar **closes**: worst case
14 M1 bars of additional latency on top of `K_M15 + 1` M15 bars. State this
explicitly in the execution model; it is the difference between a plausible and
an impossible fill.

### (e) Repaint trap

The big one, §RT5: reading a higher-timeframe value on a lower timeframe before
the HTF bar has closed. In Pine, `request.security(..., lookahead=barmerge.
lookahead_on)` does exactly this and is the single most common source of
fantasy backtests. In MQL5 the equivalent is calling `CopyRates(sym, PERIOD_M15,
0, ...)` — index 0 is the *forming* M15 bar. Both must use the closed bar:
Pine `lookahead_off` (and read `[1]`), MQL5 `shift = 1`
[2nd-hand, MQL5 docs: "passing shift = 1 ensures rates[i] evaluates closed
bars… which helps avoid lookahead bias"].

### (f) Parameters

`K_M15`, `K_M5`, `K_M1` — already counted under §S1 as a per-timeframe `K`.
Recommendation: **tie them to one shared `K`** unless a test shows otherwise.
Saves 2 parameters.

### (g) Measurable? Tier 2 — objective, but the hierarchy is a convention.

---

## S6. Structural invalidation

### (a) Competing definitions

1. Trend invalidated when the protected level is closed through.
2. Invalidated when the protected level is touched (wick).
3. Invalidated on CHoCH.
4. Never explicitly invalidated — the structure "just updates". (Most common,
   and unimplementable.)

### (b) Disagreement

(1)/(3) are near-equivalent by construction if the protected level is a pivot,
but not identical, because the protected low under §S4 need not be a pivot. (2)
is far more trigger-happy and interacts with the sweep concept perversely: a
sweep of the protected low would invalidate the very structure the sweep is
supposed to be setting up a trade within. Any system that both (i) trades
sweeps and (ii) invalidates structure on wick touches is internally
contradictory. Several published SMC rule-sets are.

### (c) Canonical definition

```
Three distinct invalidation events, kept separate:

1. STATE_FLIP:  close through the protected level (§S4) in the counter
                direction  ->  trend := opposite; all pending setups killed.
2. LEVEL_CONSUMED: a liquidity level (§L1) is closed through -> that level is
                retired permanently. It does not come back.
3. SETUP_EXPIRY: a pending setup that has not triggered within MAX_SETUP_BARS
                bars of its creation is discarded.
```

`SETUP_EXPIRY` exists because without it, "the level is still valid" is an
unfalsifiable statement and a backtester will happily hold a 2024 level into
2026 and count the eventual touch as a win.

### (d) Lag

Same bar as the invalidating close. Zero extra.

### (e) Repaint trap

Reviving a consumed level because price came back to it. If a level can be
revived, its history is a function of the future.

### (f) Parameters

| name | range | default |
|---|---|---|
| `MAX_SETUP_BARS` | 5–60 | 20 |

### (g) Measurable? Tier 1, once the three events are separated.

---

# PART 2 — LIQUIDITY

**Framing statement that must appear in every report using these terms:**
no retail XAUUSD feed exposes resting orders. "Liquidity", "resting orders" and
"stop clusters" as used below are **price-derived proxies**, not observations.
The only direct evidence that orders cluster at obvious levels is Osler's
dealer-book work on 1999–2000 FX (see `findings/01_liquidity_evidence.md`),
which is second-hand here and has not been replicated on a modern venue. Do not
write code comments that assert stops exist at a level. Write that the level is
a *candidate* stop cluster under the clustering hypothesis.

## L1. Buy-side / sell-side liquidity

### (a) Competing definitions

1. Buy-side liquidity = the pool of buy-stop orders resting **above** a high;
   sell-side = sell-stops **below** a low. Standard ICT usage.
2. Buy-side liquidity = anywhere buyers will be forced in, including above
   equal highs, above prior day high, above session highs — a *set of levels*
   rather than a single one.
3. Some material inverts the naming (calling the pool above a high "sell-side"
   because that is where you sell into it). This inversion is present in enough
   sources to be a genuine hazard when transcribing rules from a text.

### (b) Disagreement

Naming inversion (3) is the practical one: it silently reverses a strategy. It
is worth defining the term *out* of the codebase entirely.

### (c) Canonical definition

```
Replace the term with a signed structure:

    Level = { price, side, kind, origin_bar, timeframe, touches, consumed }
      side ∈ {ABOVE, BELOW}      # which side of current price it sat on when created
      kind ∈ {PIVOT_HIGH, PIVOT_LOW, EQH, EQL, PDH, PDL, PWH, PWL,
              SESSION_HIGH, SESSION_LOW}

An ABOVE level is a candidate buy-stop cluster (ICT "buy-side liquidity").
A BELOW level is a candidate sell-stop cluster (ICT "sell-side liquidity").
The words "buy-side"/"sell-side" appear only in this comment, never in code.
```

### (d) Lag

Inherited from the level's `kind`: see the confirmation lag table.

### (e) Repaint trap

Recomputing `side` relative to current price. `side` is fixed at creation.

### (f) Parameters — none of its own.

### (g) Measurable? The **level** is Tier 1. The **liquidity** is unobservable;
it is a hypothesis attached to the level.

---

## L2. Equal highs / equal lows — the tolerance question

### (a) Competing definitions

1. **Absolute tolerance** — "within N pips". Simple, breaks across regimes:
   $1.00 on gold at $1,800 in a quiet 2019 tape is a different event from
   $1.00 at $3,400 in a volatile 2026 tape.
2. **Percent-of-price** — `|Ha-Hb| <= q * price`. Handles the price level but
   not the volatility regime; gold's ATR/price ratio varies by more than 3×.
3. **ATR-relative** — `|Ha-Hb| <= q * ATR`. Handles both.
4. **`smc.py`'s implementation** [VERIFIED, L595]:
   `pip_range = (ohlc["high"].max() - ohlc["low"].min()) * range_percent`
   with `range_percent=0.01`. The tolerance is 1% of the **entire dataset's**
   high-to-low range. On a 2-year gold series that is roughly $15 — an absurdly
   wide band on M5 — **and it is computed from the whole series including the
   future.** Both a calibration failure and a lookahead failure in one line.
5. **Visual / "looks equal"** — the actual method in most educational material.
   Unfalsifiable.

### (b) Disagreement and why it matters

Tolerance choice directly controls how many EQH/EQL exist, and EQH/EQL is the
highest-conviction liquidity construct in the framework. Too tight: the pattern
essentially never occurs on gold and the strategy has no trades. Too loose:
every pair of nearby highs is "equal" and the concept carries no information.
There is no principled value in any source — every one found either states a
default without justification or says "adjust to taste". **Therefore the
tolerance must be swept in sensitivity testing and the strategy must survive
the sweep, or it is fitted to the tolerance.**

### (c) Canonical definition

```
PARAMS: EQ_TOL_ATR      # shared with §S2
        EQ_MAX_SPAN     # max bars between the first and last member
        EQ_MIN_COUNT    # minimum pivots in the cluster (>= 2)

Maintain a list of sealed pivot highs.
At the confirmation bar c of a new sealed pivot high P_n:
    tol = EQ_TOL_ATR * ATR[c]
    members = [P_n]
    for P_m in sealed pivot highs, newest first, while (bar(P_n)-bar(P_m)) <= EQ_MAX_SPAN:
        if abs(level(P_m) - level(P_n)) <= tol and P_m not already consumed:
            members.append(P_m)
    if len(members) >= EQ_MIN_COUNT:
        emit EQH level with
            price   = max(level(m) for m in members)   # the extreme, NOT the mean
            touches = len(members)
            origin_bar = bar of the OLDEST member
            known_at   = c
# EQL is the mirror, price = min(...)
```

Two deliberate departures from `smc.py`:

- **`ATR[c]`, not a global range.** Causal, and regime-adaptive.
- **`price = max(members)`, not `mean(members)`.** The stops sit above the
  *highest* of the equal highs; a mean level would be swept without the pool
  being reached, systematically mis-timing every sweep measurement by a
  fraction of `tol`. `smc.py` uses the mean [VERIFIED, L648].

### (d) Lag

Known at `c` = confirmation bar of the newest member = `p_n + K`.

### (e) Repaint trap

Adding a later pivot to an *existing* cluster and retroactively changing its
`price` or `touches`. A cluster is emitted once, with the members known at `c`.
A later equal high creates a **new** cluster object with a new `known_at`. The
old one is not edited.

### (f) Parameters

| name | range | default |
|---|---|---|
| `EQ_TOL_ATR` | 0.02–0.30 | 0.10 | (shared with §S2) |
| `EQ_MAX_SPAN` | 10–200 bars | 60 |
| `EQ_MIN_COUNT` | 2–4 | 2 |

### (g) Measurable? Tier 1 given a declared tolerance; the tolerance itself is
a free choice with no principled value in the literature.

---

## L3. Liquidity pool / resting orders / stop clusters

### (a) Competing definitions

1. Osler's microstructure result: stop-loss orders cluster *just beyond* round
   numbers, take-profit orders cluster *at* them [2nd-hand; see
   `findings/01_liquidity_evidence.md`].
2. Retail SMC: "liquidity rests above highs and below lows."
3. "Liquidity pool" = any region of clustered highs/lows, trendline touches,
   or round numbers, unweighted.

### (b) Disagreement

(1) is an empirical claim about a specific 1999–2000 dealer book; (2) and (3)
are geometric restatements of "there is a high there". Critically, (1)'s
stop-loss half predicts **acceleration through** a level (positive feedback),
not rejection at it — which points the opposite way from the fade-the-sweep
trade. This is documented at length in `findings/01_liquidity_evidence.md` and
is not re-argued here.

### (c) Canonical definition

**There is no observable to define.** Refuse to define it. What can be defined
is the *level* (§L1) and a *score* (§L7) that ranks levels by properties that
are plausibly correlated with order density. Any code identifier named
`liquidity_pool` should be renamed `level_cluster`.

### (d)–(f) N/A.

### (g) Measurable? **No.** Tier 3. Unobservable on retail data.

---

## L4. Previous day / week high-low — the rollover matters more than the concept

### (a) Competing definitions of the day boundary

1. **Broker server midnight.** What MT5 gives you for free. Typically GMT+2 in
   winter / GMT+3 in summer for European brokers, but **not standardised** —
   this is a per-broker property.
2. **17:00 America/New_York** — the CME / interbank FX rollover. The
   "true" trading day for gold.
3. **00:00 UTC.**
4. **`smc.py`**: `ohlc.resample("1D")` [VERIFIED, L720] — pandas resamples on
   the index's own timezone, i.e. whatever the input data was in, undocumented.
   Then it takes `indices[-2]`, the second-to-last completed period, which is
   correct and causal for the *previous* period.
5. Exchange-session-based, e.g. Pine's `request.security(tickerid, "D", ...)`
   which uses the symbol's exchange session — which for a broker CFD gold
   symbol is broker-defined again.

### (b) Disagreement and why it matters — this is not pedantry

Gold's largest intraday moves cluster around the NY session. A day boundary at
00:00 UTC cuts the NY afternoon *away* from its own morning; a boundary at
17:00 NY keeps the whole session in one day. PDH/PDL differ materially between
the two — different levels, different sweep events, different trades. And
because Pine will use the exchange session and MQL5 will use broker server
time, **the same "strategy" will produce different PDH values in TradingView
and MetaTrader unless the boundary is forced identically in both.** A
Pine→MQL5 port that does not force this will not reconcile, and the developer
will spend days looking for a bug that is a definition.

### (c) Canonical definition

```
PARAMS: DAY_ROLL_TZ  = "America/New_York"
        DAY_ROLL_HH  = 17          # 17:00 local, DST-aware
        WEEK_ROLL    = the DAY_ROLL boundary on Sunday

trading_day(t) = the date d such that
    roll(d)  <= t <  roll(d+1)
    where roll(d) = the instant 17:00 on (d-1) in America/New_York, in UTC
    (i.e. 21:00 UTC in EDT, 22:00 UTC in EST)

PDH(i) = max H over all bars with trading_day == trading_day(i) - 1
PDL(i) = min L over the same set
Both are FROZEN at the moment the previous day closes; they never update
intraday.

PWH/PWL: same with trading_week = weeks starting at the Sunday roll.
```

Implementation requirement, both platforms: convert every bar's timestamp to
`America/New_York` **with DST rules**, not with a fixed offset. Pine:
`timestamp("America/New_York", ...)` / `hour(time, "America/New_York")`.
MQL5: no native IANA tz — must implement the US DST rule (second Sunday in
March, first Sunday in November) explicitly, or the levels will be wrong for
about 8 months of every year relative to Pine.

### (d) Lag

Known at the **first bar of the new trading day** — i.e. immediately, and with
zero lag for the whole day. This makes PDH/PDL the *lowest-latency* levels in
the entire framework and the natural first thing to test. It is also the only
level type with **no `K` dependence**, hence no pivot parameters.

### (e) Repaint trap

Using the *current, still-forming* day's running high as "today's high" and
then treating a break of it as a sweep of a level. The running high is not a
level; it is a statistic of the future when read historically. Only the
completed day is a level.

### (f) Parameters

| name | range | default |
|---|---|---|
| `DAY_ROLL_TZ` | fixed | America/New_York |
| `DAY_ROLL_HH` | {0 UTC, 17 NY, broker} | 17 NY |

Treat as a **structural switch to test**, not a parameter to optimise.

### (g) Measurable? Tier 1, and the cleanest object in the document.

---

## L5. Session highs / lows and exact boundaries

### (a) Competing definitions (all UTC unless stated)

| source | Asia | London | New York |
|---|---|---|---|
| ICT killzones [2nd-hand, ictkillzonetimes / tradingrage] | 00:00–05:00 | 07:00–10:00 | 12:00–15:00 |
| ICT killzones, NY-local phrasing [2nd-hand, fxopen] | 19:00–22:00 NY | 02:00–05:00 NY | 07:00–10:00 NY |
| `smc.py` full sessions [VERIFIED, L820–856] | Tokyo 00:00–09:00 | 07:00–16:00 | 13:00–22:00 |
| `smc.py` killzones [VERIFIED, L820–856] | 00:00–04:00 | 06:00–09:00 | 11:00–14:00 |
| Exchange hours | Tokyo 09:00–17:00 JST | LSE 08:00–16:30 London | NYSE 09:30–16:00 NY |

### (b) Disagreement and why it matters

Three separate problems:

1. **The windows themselves disagree** — the London killzone is 07:00–10:00 in
   one source and 06:00–09:00 in `smc.py`. A one-hour shift on M5 is 12 bars
   and changes which bar is the session high.
2. **The two ICT rows above are inconsistent with each other.** 02:00–05:00
   New York is 06:00–09:00 or 07:00–10:00 UTC depending on the month, because
   US and UK DST transitions are three weeks apart in spring and one week apart
   in autumn. Any source quoting a *fixed* UTC killzone is wrong for roughly
   4 weeks a year. `smc.py` uses fixed wall-clock with no DST handling at all
   [VERIFIED, L858–866 — it localises to a fixed `Etc/GMT` offset].
3. **Asia is the only clean one.** JST has no DST, so Tokyo 09:00–17:00 JST is
   permanently 00:00–08:00 UTC. This is a real argument for making the Asian
   range the primary session construct in an XAUUSD system: it is the only one
   with no timezone ambiguity.

### (c) Canonical definition

```
PARAMS: sessions defined in LOCAL time with an IANA zone, converted per-bar.

  ASIA   : 00:00 - 08:00  UTC          (fixed; = Tokyo 09:00-17:00 JST)
  LONDON : 08:00 - 16:30  Europe/London  (DST-aware)
  NY     : 08:00 - 17:00  America/New_York (DST-aware; CME gold pit-equivalent)
  Overlap: LONDON ∩ NY

For each session S and each trading_day d (per §L4):
    SESSION_HIGH(S,d) = max H over closed bars whose timestamp ∈ S on day d
    SESSION_LOW (S,d) = min L over the same
    Both are EMITTED AS A LEVEL only at the first bar AFTER S closes on day d.
    Before that instant they do not exist.
```

The Asian range is then `[SESSION_HIGH(ASIA,d), SESSION_LOW(ASIA,d)]`, emitted
at 08:00 UTC, available for the whole London and NY sessions. Zero lag from
that point, no pivot parameters. Together with PDH/PDL these are the two
cheapest, least-parameterised level families available — and therefore the two
that should be tested **first and alone**, before any pivot-based level is
added.

### (d) Lag

Zero, from the session close bar onward. The session high **during** the
session is not a level.

### (e) Repaint trap

The `smc.py` `sessions()` function returns a per-bar running `High`/`Low` of
the in-progress session [VERIFIED, L876–890]. Used naively as "the session
high", this is a forward-looking statistic on every bar except the last one of
the session. It is safe only if you read it at the final bar of the session.
Its reset also depends on there being an inactive bar between sessions
(`high[i-1]` seeds from the previous bar, which is 0 only if that bar was
inactive) — so with back-to-back session definitions it will not reset.

### (f) Parameters

| name | range | default |
|---|---|---|
| session set | {ASIA, LONDON, NY, OVERLAP} | all four |
| boundary mode | {fixed-UTC, DST-aware} | DST-aware |

Session windows themselves are **not** to be optimised. Opening them up as
tunable start/end times adds 8 continuous parameters and is a straight path to
the 748-parameter failure.

### (g) Measurable? Tier 1. The disagreement is in the constants, not the
concept.

---

## L6. Inducement

### (a) Competing definitions

1. "The extreme point of the last pullback in a market structure that prompts
   traders to buy and sell" [2nd-hand, tradingfinder].
2. "A valid inducement level is the swing high or low of the first valid
   pullback within the leg that created the most recent significant BOS or
   CHoCH" [2nd-hand, writofinance]. Note **three** undefined qualifiers in one
   sentence: *valid* pullback, *significant* BOS, *the* leg.
3. "The liquidity that must be taken before price can reach the real point of
   interest." Defined by outcome.
4. "Inducement typically appears as the first pullback after a BOS or CHOCH,
   and is followed by a liquidity sweep" [2nd-hand, equiti].

### (b) Disagreement

(1), (2) and (4) are compatible and *nearly* codeable. (3) is the one most
often used in practice and is circular: an inducement is the liquidity that got
taken before the move; if no move followed, it "wasn't the inducement". This
makes the concept **unfalsifiable** — every failed setup is retro-explained as
having mis-identified the inducement. This is the clearest example in the whole
framework of a term that cannot be wrong.

Additional problem: definitions (1)/(2)/(4) make inducement a *deterministic
function of structure* — it is just "the first counter-pivot in the leg". If
that is all it is, it introduces no information beyond §S1 and §S4, and any
claimed benefit from "waiting for inducement to be taken" is a claim about
pullback depth, which is testable directly and much more cheaply.

### (c) Canonical definition — offered as a convention, clearly labelled

```
PARAMS: none (derived)

After a BOS_BULL / CHOCH_BULL at bar i created by breaking a high from pivot
bar p_h:
    candidate pivots = sealed pivot LOWS with bar index in (p_h, i)
    if none exist:                   inducement := NONE
    else:                            inducement := the EARLIEST such pivot low
    # "first pullback within the leg"
INDUCEMENT_TAKEN at bar j > i  iff  L[j] < inducement.level   (wick basis)
```

**Report this as `first_leg_pullback`, not `inducement`.** The rename is not
cosmetic: it stops the code from asserting an intent it cannot observe, and it
makes the resulting test a test of a geometric fact rather than of a story.

### (d) Lag

Known at bar `i` (the BOS bar), since it only references pivots already sealed
before `i`. `INDUCEMENT_TAKEN` at the bar it happens.

### (e) Repaint trap

Selecting the inducement *after* seeing which pullback got swept. That is the
trap that makes the concept look predictive in visual backtests: the analyst
picks, on the chart, the pullback that was in fact taken, and the rule appears
to have 90% accuracy. The rule above forces the choice before the outcome.

### (f) Parameters — none.

### (g) Measurable?

**As commonly stated: Tier 3, unfalsifiable.** As the convention above:
Tier 2, objective, and probably redundant with structure. This is a finding:
inducement adds a word, not a variable.

---

## L7. Liquidity strength score

There is no published score. This section is therefore **construction, not
review** — and its most important content is a warning about how to build it.

### (a) Inputs found in the wild that are actually measurable

| input | measurable? | how |
|---|---|---|
| touch count | yes | `touches` from §L2, or count of bars whose H came within `tol` and did not close through |
| age | yes | `i - origin_bar`, in bars of the level's own timeframe |
| timeframe rank | yes | ordinal: M1 < M5 < M15 < H1 < D1 |
| round-number proximity | yes | distance to nearest $10 / $5 / $1 multiple, in ATR |
| volume at level | **partly** | XAUUSD has tick volume only; broker-dependent, not comparable across feeds |
| "untested" | yes | `touches == 0` since creation |
| session of origin | yes | which session the level formed in |
| distance from price | yes | `abs(price - level)/ATR` |
| "institutional interest" | **no** | unobservable |
| "how obvious it looks" | **no** | subjective |

### (b) Where scores go wrong

Every one of these components introduces at minimum a weight and often a
normalisation constant. Eight components with a weight and a scale each is
**16 new parameters**, none of which has a prior, all fitted on the same data
that produced the strategy. That is the mechanism by which the previous EA
reached 748 parameters. A weighted score of eight weakly-informative inputs is
not more information than the best single input — it is the same information
plus seven degrees of freedom.

### (c) Canonical definition — deliberately minimal

```
STAGE 1 (mandatory, before any score exists):
    Test each candidate input UNIVARIATELY. For input x and outcome y
    (e.g. did the sweep of this level reverse by >= 1R before -1R):
        - bucket levels into quintiles of x
        - report outcome rate per quintile with Wilson CIs
        - report the monotonicity and the spread between Q1 and Q5
    Discard every input whose Q1-Q5 spread CI includes zero.

STAGE 2 (only if >= 2 inputs survive Stage 1):
    LIQ_SCORE = sum over surviving inputs of  w_k * z_k
    where z_k is the CAUSAL percentile rank of input k, computed over a
    TRAILING window of the last PCT_WIN completed level-events only,
    and w_k ∈ {1} unless a test justifies otherwise.
    Equal weights are the default. Fitted weights must beat equal weights
    out-of-sample or they are noise.

STAGE 3: use LIQ_SCORE only as a GATE (top tercile vs rest), never as a
    continuous position-size multiplier. A gate costs 1 parameter; a
    multiplier costs a functional form.
```

### (d) Lag

Score is knowable at the same bar as the level, except `touches`/`age` which
update forward-only and must be read as of the evaluation bar.

### (e) Repaint trap

Percentile ranks computed over the **whole sample**. `z_k` must use a trailing
window. This is the same class of error as `smc.py` L595 and it is extremely
easy to commit in pandas (`df['x'].rank(pct=True)` is full-sample).

### (f) Parameters

| name | range | default |
|---|---|---|
| `PCT_WIN` | 100–2000 events | 500 |
| `SCORE_GATE` | top 1/3, 1/2, or off | top 1/3 |
| weights `w_k` | fixed at 1 | 1 |

**2 parameters if the discipline holds. 16+ if it does not.**

### (g) Measurable? Tier 2 — objective, but every design choice in it is
arbitrary, so it must earn its existence component by component.

---

# PART 3 — SWEEP CLASSES A–G

## SW0. The structural finding: these are three axes, not seven categories

The seven types as circulated cannot be a partition, because they answer
different questions:

| type | question it answers | knowable when? |
|---|---|---|
| A wick sweep + rejection | **morphology** — what did the bar look like? | at the sweep bar |
| B close beyond + rapid reclaim | morphology | at the reclaim bar |
| C deep sweep + rejection | morphology (depth-dominant) | at the reclaim bar |
| D sweep + displacement | **confirmation** — what followed? | reclaim + ≤ `R_D` bars |
| E sweep + structure shift | confirmation | reclaim + ≤ `W` bars |
| F sweep + continuation | **outcome** — did it work? | only at the end of `W` |
| G failed sweep / genuine breakout | outcome | only at the end of `W` |

A and D are not alternatives: a single event is routinely a wick sweep *and*
followed by displacement. F and G are not detectable at entry — **they are
labels for what happened to the trade.** Any claim of the form "trade types
A–E, avoid F and G" is not implementable, because at the decision bar F is
indistinguishable from D and E. This is the crux: the value of D and E is
precisely that they are *conditioning variables available before* the outcome,
and the whole empirical question is whether conditioning on them lowers the
rate of F.

**Canonical representation: a 3-tuple per sweep event.**

```
SweepEvent = {
    level_ref,
    morphology   ∈ {A, B, C, NONE_G},    # exactly one, decided by priority
    confirm      ⊆ {D, E},               # a SET, possibly empty
    outcome      ∈ {REVERSAL, F, G}      # terminal label, research only
}
```

A forced single label (for compatibility with the seven-type vocabulary) is
given in §SW3, but the 3-tuple is what the code should carry.

## SW1. Common measurement frame

All definitions below are written for a sweep of an **ABOVE** level `P`
(a high; expected reversal is short). The BELOW/long case is the exact mirror
with `H↔L`, `>↔<`, `max↔min`.

```
PARAMS: W          # decision window, bars after penetration
        DEEP_ATR   # depth threshold separating C from A/B
        FAST_N     # max bars for a "rapid" reclaim (B)
        WICK_MIN   # min beyond-level wick fraction (A)
        CLR_MAX    # max close-location-in-range (A)
        R_D        # max bars after reclaim for a displacement to count (D)
        NB_BREAK   # closes beyond P required to call it a breakout (G)

Penetration bar:
    i0 = first bar with H[i0] > P, for a level that is not yet consumed.
         (wick basis. If the level was already closed through, it is consumed
          per §S6 and no sweep can occur.)

Measured features, all computed from closed bars only:
    atr0        = ATR[i0 - 1]                       # NOT ATR[i0]
    depth(k)    = (H[k] - P) / atr0                 # in ATR units
    depth_max   = max over k in [i0, min(i0+W, i)] of depth(k)
    penetration_bars = count of k in [i0..] with H[k] > P, consecutive from i0
    closes_beyond    = count of k in [i0..min(i0+W,i)] with C[k] > P
    beyond_wick(k)   = (H[k] - max(O[k], C[k])) / (H[k] - L[k])   # 0 if range 0
    body_ratio(k)    = abs(C[k] - O[k]) / (H[k] - L[k])
    clr(k)           = (C[k] - L[k]) / (H[k] - L[k])   # 0 = close at low
    reclaim_bar r    = first k in [i0 .. i0+W] with C[k] < P
    reclaim_speed    = r - i0                        # 0 = same bar
    disp_bar         = first k in [r .. r+R_D] that is a bearish displacement
                       bar per §D1
    shift_bar        = first k in [i0 .. i0+W] with a CHOCH_BEAR (§S3)
                       whose broken_level is a swing low sealed before i0
```

**Zero-range guard:** on M1 gold, `H==L` bars occur (illiquid rollover
minutes). Every ratio above must return 0 and the bar must be excluded from
morphology tests, or both platforms will produce NaN/inf and diverge.

## SW2. The seven classes

### Type A — wick sweep + rejection

```
A(i0) := (H[i0] > P)
     AND (C[i0] < P)                       # closed back below on the SAME bar
     AND (depth(i0) <= DEEP_ATR)
     AND (beyond_wick(i0) >= WICK_MIN)
     AND (clr(i0) <= CLR_MAX)
```
- **Knowable at bar `i0`.** Zero lag beyond the level's own lag. This is the
  only sweep morphology with same-bar confirmation, and therefore the only one
  that can be traded at the close of the sweeping bar.
- **vs B:** A requires `closes_beyond == 0` at `i0`; B requires ≥ 1.
- **vs C:** A requires `depth <= DEEP_ATR`; C exceeds it.
- **vs G:** A has already reclaimed; G never does.
- Sensitivity note: `WICK_MIN` and `CLR_MAX` are largely redundant — both
  measure "closed far from the extreme". Prefer keeping `CLR_MAX` and setting
  `WICK_MIN = 0` unless a test shows the wick fraction adds information.
  That saves a parameter.

### Type B — close beyond + rapid reclaim

```
B := (closes_beyond >= 1)
 AND (reclaim_bar exists) AND (reclaim_speed <= FAST_N)
 AND (depth_max <= DEEP_ATR)
```
- **Knowable at `reclaim_bar`**, i.e. `i0 + 1 .. i0 + FAST_N`.
- **vs A:** price *closed* above the level, so under the §S3 close-break rule
  this event also produced a bullish BOS. B is therefore a **failed BOS**, not
  merely a wick. That is a materially different market event and mixing A and B
  into one "sweep" bucket is a modelling error many implementations make.
- **vs F:** B reclaimed within `FAST_N`; F reclaimed and then re-broke.
- Because B implies a consumed level under §S6, the level bookkeeping must
  decide whether a reclaimed level is revived. **Canonical: it is not revived.**
  The B event itself becomes the tradable object; the old level is gone.

### Type C — deep sweep + rejection

```
C := (depth_max > DEEP_ATR)
 AND (reclaim_bar exists within W)
```
- **Knowable at `reclaim_bar`**, ≤ `i0 + W`.
- **vs A/B:** depth only. C is evaluated **first** in the priority order, so a
  deep event never counts as A or B.
- The depth threshold is the load-bearing parameter of the whole taxonomy and
  has no principled value anywhere in the source material. Sweep it.

### Type D — sweep + displacement

```
D := (reclaim_bar exists within W) AND (disp_bar exists)
```
- **Knowable at `disp_bar`**, ≤ `reclaim_bar + R_D`.
- D is a **flag**, orthogonal to A/B/C. Any of A, B, C can carry it.
- Cost of D: entering after a displacement bar means entering after the move
  has already gone `>= DISP_ATR × ATR`. The confirmation is bought with
  adverse entry. Any test of D must charge that entry price honestly — it is
  the mechanism by which "higher win rate" becomes "worse expectancy", which
  is exactly what killed the capped-target design in E-002.

### Type E — sweep + structure shift

```
E := (reclaim_bar exists within W) AND (shift_bar exists within W)
```
- **Knowable at `shift_bar`**, ≤ `i0 + W`. In practice E is the slowest
  confirmation: it needs the swept-side structure to break, which needs a
  sealed opposite pivot, which costs `K` bars.
- **vs D:** D is about the *bar*; E is about the *level structure*. They
  overlap heavily but not completely; carry both flags, do not merge.

### Type F — sweep + continuation (the reversal trader's failure case)

```
F := (reclaim_bar exists within W)                # it looked like a sweep
 AND (exists k in (reclaim_bar .. i0+W] with C[k] > P)   # then re-broke
```
- **Knowable only at the re-break bar, and NOT knowable at entry.**
- F is the complement that makes the taxonomy honest. A/B/C/D/E all describe
  events that *can* become F afterwards. The research question is:
  `P(F | morphology, confirm)` — and if that probability does not vary with
  the conditioning variables, the entire taxonomy is decoration.
- **This is the single most important statistic to compute from these
  definitions.** It is cheap, it needs no trading rule, no stop, no target, and
  no cost model. Compute it first. If `P(F | A) ≈ P(F | C+D+E)`, stop.

### Type G — failed sweep / genuine breakout

```
G := (no reclaim_bar within W) AND (closes_beyond >= NB_BREAK)
```
- **Knowable at `i0 + W`** at the earliest — a pure hindsight label.
- G is not a sweep at all. Its rate matters because `P(G)` is the base rate of
  "levels just break", and any sweep-fading strategy is short that event.
- Note the asymmetry with Osler's stop-loss result (positive feedback through
  levels) — if that mechanism dominates on gold, `P(G)` will be high, and it
  is directly measurable here without any strategy.

## SW3. Forced single label (priority order) — for reporting only

```
if no penetration:                       -> no event
elif G condition:                        -> "G"
elif F condition:                        -> "F"
elif depth_max > DEEP_ATR:               -> "C"   (+D/+E flags)
elif closes_beyond >= 1:                 -> "B"   (+D/+E flags)
elif A condition at i0:                  -> "A"   (+D/+E flags)
else:                                    -> "unclassified"   # must be logged
```

The `unclassified` bucket is mandatory. Any taxonomy that classifies 100% of
events has a catch-all masquerading as a category. Report its size; if it is
large, the thresholds are wrong.

## SW4. Parameters introduced by the sweep taxonomy

| name | range | default | note |
|---|---|---|---|
| `W` | 3–30 | 10 | decision window |
| `DEEP_ATR` | 0.3–2.0 | 0.75 | A/B vs C boundary |
| `FAST_N` | 1–5 | 2 | B |
| `CLR_MAX` | 0.15–0.50 | 0.33 | A |
| `WICK_MIN` | 0 or 0.3–0.7 | 0 (off) | A, redundant with CLR |
| `R_D` | 1–5 | 3 | D |
| `NB_BREAK` | 1–3 | 2 | G |

**7 parameters, 6 if `WICK_MIN` stays off.**

## SW5. Repaint traps specific to sweeps

1. **Choosing `i0` in hindsight.** The penetration bar must be the *first*
   breach of a level that was already known. Scanning for "the bar that made
   the low of the day and then reversed" is the classic visual-backtest lie.
2. **Using a level created after `i0`.** The level's `known_at` must be
   strictly `< i0`. With pivot levels this is easy to violate: the pivot at
   bar `p` is confirmed at `p+K`, and if `i0 < p+K` the sweep is of a level
   that did not exist yet.
3. **Same-bar `i0` and reclaim on intrabar data.** On M1, `C[i0] < P` with
   `H[i0] > P` is knowable at the M1 close. On M15, the same statement is
   knowable only at the M15 close — 15 minutes of price action later. A
   backtest that evaluates M15 sweeps at M1 resolution and enters at the M15
   sweep bar's close is fine; one that enters at the M15 sweep bar's *open* is
   not.
4. **Letting `W` extend past the current bar.** `depth_max` and
   `closes_beyond` must be computed over `[i0, min(i0+W, i)]`, never
   `[i0, i0+W]` when `i < i0+W`. In a vectorised pandas implementation this is
   the default failure mode.
5. **Re-arming a consumed level.** See §S6.

## SW6. Objectively measurable?

**A, B, C, F, G: Tier 1.** Fully determined by the parameter vector.
**D, E: Tier 1**, conditional on §D1 and §S3.
**The boundary between C and A/B: Tier 2** — `DEEP_ATR` is arbitrary.
**The claim that any of them is a signal: untested.** Nothing here is
evidence.

---

# PART 4 — DISPLACEMENT

## D1. What distinguishes displacement from a big candle?

### (a) Competing definitions

1. **ATR multiple on the body.** "Candle body must exceed ATR(14) ×
   multiplier (default 1.5)" [2nd-hand, TradingView displacement scripts].
2. **Body/range ratio.** "Candle body must be at least a configurable
   percentage (default 65%) of the total candle range"; elsewhere "60 to 80
   percent or more" [2nd-hand].
3. **Imbalance creation.** Displacement is a move that leaves an FVG behind —
   i.e. defined by its 3-bar footprint rather than by one candle.
4. **Sequence-based.** "a rapid sequence of 2–3 candles that moves price
   aggressively away from a prior range" [2nd-hand].
5. **Narrative only.** "an unusually large body relative to recent volatility,
   often leaving minimal wicks in the move direction" — no threshold.

### (b) Disagreement and why it matters

- (1) and (2) measure different things: (1) is magnitude, (2) is purity. A
  large bar with a big wick passes (1) and fails (2). On gold news bars this is
  the majority case, so the two definitions select nearly disjoint samples in
  the highest-volatility periods.
- (3) costs an extra bar of lag (the FVG needs bar `i+1`) and cannot be
  same-bar. (4) costs 2–3 bars. (1)+(2) are same-bar. This is the whole
  practical difference between displacement as a *trigger* and displacement as
  a *filter*.
- **The ATR reference bar is unstated in every source.** Using `ATR[i]` means a
  big bar raises its own threshold by roughly `1/ATR_LEN` of its own range —
  a systematic bias that shrinks detection counts and, worse, makes detection
  depend on `ATR_LEN` in a non-obvious way. Use `ATR[i-1]`.
- **Percentile vs multiple.** An ATR multiple is a fixed ratio; a percentile
  threshold ("top 10% of the last 500 bar ranges") adapts to the *shape* of the
  range distribution, which for gold is strongly non-normal and regime
  dependent. A 1.5×ATR bar is a 1-in-30 event in one regime and 1-in-300 in
  another. The percentile version holds the event *rate* constant, which is far
  more useful for research because it decouples "how often does this fire" from
  "how strong is the signal".

### (c) Canonical definition

```
PARAMS: DISP_ATR      # magnitude, in ATR[i-1] units
        DISP_BODY     # body/range purity
        DISP_PCT      # optional percentile guard, 0 disables
        DISP_PCT_WIN  # trailing window for the percentile

range_i     = H[i] - L[i]
body_i      = abs(C[i] - O[i])
if range_i == 0: return NONE

bull_disp(i) := (C[i] > O[i])
            AND (range_i >= DISP_ATR * ATR[i-1])
            AND (body_i / range_i >= DISP_BODY)
            AND (DISP_PCT == 0 OR
                 range_i >= percentile(range over bars [i-DISP_PCT_WIN .. i-1],
                                       DISP_PCT))
bear_disp(i) := mirror with C[i] < O[i]
```

Notes: the percentile window **excludes bar `i`**. The FVG condition is
deliberately *not* part of the definition — it is carried as a separate
attribute `disp_left_fvg(i)` knowable at `i+1`, so that the same displacement
object can be used both as a same-bar trigger and, one bar later, as a
gap-qualified filter, without two definitions.

### (d) Confirmation lag

**Zero** — knowable at the close of bar `i`. This is the fastest primitive in
the document and the reason displacement is attractive as a confirmation for
sweeps (§SW Type D). The FVG-qualified variant is `+1`.

### (e) Repaint trap

- `ATR[i]` instead of `ATR[i-1]` (above).
- Full-sample percentile instead of trailing (`.rank(pct=True)` / `np.
  percentile` over the whole array).
- Defining displacement by "it broke structure and kept going" — outcome
  leakage. Displacement must be a property of the bar, not of what followed.

### (f) Parameters

| name | range | default |
|---|---|---|
| `DISP_ATR` | 1.0–3.0 | 1.5 |
| `DISP_BODY` | 0.45–0.85 | 0.60 |
| `DISP_PCT` | 0 or 0.85–0.99 | 0 (off) |
| `DISP_PCT_WIN` | 200–2000 | 500 |

Recommendation: run the taxonomy **once with `DISP_ATR` fixed and `DISP_PCT`
off**, and once with the reverse (percentile only, `DISP_ATR = 0`). If the
conclusions differ, the result is a threshold artefact.

## D2. Is there published evidence that displacement predicts continuation?

**No evidence was found that tests displacement as SMC defines it.** Every
source located is a TradingView script description or a course page. None
reports a hit rate, a sample size, an out-of-sample split, or a cost model.

The nearest genuine literature is the **large one-day price change** family in
equities, and it points the *wrong way* for the displacement-continuation
story [all 2nd-hand]:

- Atkins & Dyl (1990) and Bremer & Sweeney (1991): evidence of **reversal**
  after large one-day declines.
- Cox & Peterson (1994): **no** overreaction/reversal after large one-day
  declines; they report a **momentum effect over the following 4–20 days**
  instead — i.e. continuation, but on a multi-week horizon, not an intraday
  one.
- Across the family, the reported effect **"disappears after accounting for the
  bid-ask bounce"**. That is the same failure mode as E-003: a real but tiny
  effect that does not survive the spread.
- The whole area is subject to the Sullivan, Timmermann & White (1999)
  data-snooping critique — their best rule over 100 years of DJIA data
  survived the Reality Check bootstrap in-sample but **did not deliver superior
  performance in the subsequent 10-year post-sample period**.
- Lo, Mamaysky & Wang (2000) is the closest methodological ancestor of what
  this document is doing: they built automatic, non-subjective pattern
  definitions via kernel regression precisely because "the presence of
  geometric shapes in historical price charts is often in the eyes of the
  beholder", and found several patterns carry **incremental information** —
  a statement about conditional return *distributions*, explicitly not a
  statement about tradable profit.

**Status: UNPROVEN, no test found.** The honest position is that displacement
is a well-defined, zero-lag, cheap-to-compute feature with no published
evidence either way, and it should be tested as a conditioning variable
(does `P(F)` fall given D?) before being built into a strategy.

---

# PART 5 — FVG / ORDER BLOCKS / BREAKERS

## F1. Fair value gap

### (a) Competing definitions

1. **Pure 3-bar gap.** Bullish FVG at bar `i` iff `L[i] > H[i-2]`. No condition
   on the middle bar. The minimal definition.
2. **Gap + middle-bar direction.** `smc.py` [VERIFIED, L72–83]:
   `(high.shift(1) < low.shift(-1)) & (close > open)` — i.e. it centres on the
   middle bar and additionally requires that **middle** bar to be bullish. So
   an up-gap created by a bearish middle candle is not an FVG in this library
   but is under (1).
3. **Gap + displacement.** The middle bar must additionally satisfy §D1.
   Common in ICT-derived material ("displacement leaves an imbalance").
4. **Gap size filter.** Gap must exceed some minimum in ATR/points to matter.
5. **Volume imbalance / opening gap** variants — different objects, often
   conflated in the same article.

### (b) Disagreement

(1) vs (2) differ on a non-trivial share of gaps and (2) is the version most
Python backtests use without knowing it. (3) is strictly rarer and correlates
with §D1, so using both "displacement" and "displacement-FVG" as separate
confluence factors is double-counting. (4) is unavoidable on M1 gold: without a
minimum size, tick-level gaps of $0.02 qualify and the concept becomes noise.

### (c) Canonical definition

```
PARAMS: FVG_MIN_ATR    # minimum gap height in ATR units

# Evaluated at the close of bar i, referencing i-1 and i-2 only.
bull_fvg(i) := L[i] > H[i-2]  AND  (L[i] - H[i-2]) >= FVG_MIN_ATR * ATR[i-1]
    zone = [ H[i-2] , L[i] ]         # bottom, top
bear_fvg(i) := H[i] < L[i-2]  AND  (L[i-2] - H[i]) >= FVG_MIN_ATR * ATR[i-1]
    zone = [ H[i] , L[i-2] ]
midpoint (consequent encroachment) CE = (zone.bottom + zone.top) / 2

# Middle-bar direction is recorded as an ATTRIBUTE, not a filter:
    fvg.middle_bullish = (C[i-1] > O[i-1])
    fvg.middle_disp    = bull_disp(i-1) / bear_disp(i-1) per §D1
# so that variants (1),(2),(3) can all be tested from one detection pass
# without three separate definitions in the code.

# Mitigation state machine, forward-only:
    state = OPEN
    at each later bar k:
        bull FVG:
            if L[k] <= zone.top    : state = TOUCHED   (first entry)
            if L[k] <= CE          : state = HALF
            if C[k] <  zone.bottom : state = INVERTED  (terminal)
            if L[k] <= zone.bottom : state = FILLED    (if not INVERTED)
        # bear FVG mirrors
    Once INVERTED the zone becomes an INVERSION_FVG with side flipped and a
    new object id. The original is retired and never re-opens.
```

Three mitigation levels (`TOUCHED`, `HALF`, `FILLED`) are carried rather than
one, because sources disagree about which counts and it costs nothing to
record all three and pick in the test.

### (d) Lag

**Knowable at bar `i`** — the third bar. Zero extra lag. Note the FVG is
conventionally *drawn* spanning bars `i-2..i` and is often *stamped* at `i-1`;
see below.

### (e) Repaint trap

**`smc.py` L72–100 stamps the FVG at the middle bar** (it uses
`shift(-1)`, so the row that carries `FVG=1` is bar `i-1`, one bar before the
gap can be known). Reading `fvg[t]` at bar `t` therefore looks one bar into the
future. It further computes `MitigatedIndex` by scanning `ohlc[i+2:]` — the
mitigation index for every FVG is a future value, correct as an offline label
but fatal if joined onto the bar and read as a feature.

### (f) Parameters

| name | range | default |
|---|---|---|
| `FVG_MIN_ATR` | 0.05–0.60 | 0.15 |
| mitigation level used | {TOUCHED, HALF, FILLED} | HALF |

### (g) Measurable? **Tier 1.** FVG is the most cleanly defined object in the
entire SMC vocabulary — a pure 3-bar arithmetic test with zero lag.

## F2. Order blocks

### (a) Competing definitions

1. **"Last opposing candle before an impulsive move."** "A bullish order block
   is the last down candle before a sharp rally" [2nd-hand, multiple]. Needs
   "impulsive" defined — usually left undefined, or defined as displacement.
2. **Last opposing candle before a move that BREAKS STRUCTURE.** Adds the §S3
   requirement. "Without a strong impulsive move and structure break, it's not
   a valid OB" [2nd-hand, dailypriceaction].
3. **`smc.py`'s implementation** [VERIFIED, L423–470] — and this is **not**
   definition (1). When `C[i] > H[last_swing_high]` and that swing high has not
   already been crossed, the library searches the bars between the swing high
   and `i` for the bar with the **lowest low** (ties → last occurrence), and
   uses that bar's `[low, high]` as the bullish OB. The lowest-low bar is
   frequently *not* the last down candle. So the most-used implementation and
   the most-quoted definition disagree on which candle the zone is.
4. **The whole consolidation range** before the move (Wyckoff-flavoured
   readings).
5. **Zone bounds** disagree independently of candle selection: full high-low
   (`smc.py`), body only, open-to-wick, or the "mean threshold" (50%).

### (b) Disagreement and why it matters

Four candle-selection rules × four zone-bound rules = sixteen defensible
"order blocks", producing different zones on the same chart. Because the OB is
an *entry zone*, this directly sets entry price, and therefore R-multiple, on
every trade. An expectancy computed under one convention says nothing about
another. This is the clearest Tier-2 concept in the document: there is no fact
of the matter about where the order block is.

### (c) Canonical definition — one convention, declared

```
PARAMS: OB_ZONE      ∈ {FULL, BODY}      # structural switch
        OB_MAX_ATR   # reject zones wider than this (news bars)
        OB_MIT       ∈ {TOUCH, HALF, CLOSE_THROUGH}

On a BOS_BULL or CHOCH_BULL at bar i breaking a high from pivot bar p_h:
    candidates = bars j in [p_h .. i-1] with C[j] < O[j]      # down candles
    if candidates is empty: no OB
    ob_bar = max(candidates)                # the LAST down candle  (def. 1)
    zone   = OB_ZONE == FULL ? [L[ob_bar], H[ob_bar]]
                             : [min(O,C)[ob_bar], max(O,C)[ob_bar]]
    reject if (zone.top - zone.bottom) > OB_MAX_ATR * ATR[i]
    CE = midpoint(zone)

Mitigation (forward-only, mirrors §F1):
    TOUCH          : L[k] <= zone.top
    HALF           : L[k] <= CE
    CLOSE_THROUGH  : C[k] <  zone.bottom   -> INVALIDATED, becomes a BREAKER
```

Definition (1) is adopted over `smc.py`'s lowest-low rule because it is what
the literature says, is cheaper, and does not require a scan. **Both should be
run in sensitivity testing** — if the edge exists under one and not the other,
there is no edge.

### (d) Lag

Knowable at the BOS bar `i`, which is `≥ p_h + K + 1` (§S3). The OB *candle*
sits in the past; the OB *object* does not exist until the structure break
confirms it. Drawing it back on the chart at `ob_bar` is correct for display
and wrong for backtesting.

### (e) Repaint trap

The dominant one in this whole family: **plotting the OB at `ob_bar` and
reading it at `ob_bar`.** The zone is only knowable `i - ob_bar` bars later,
which on M5 gold is routinely 5–30 bars. A backtest that enters "at the order
block" on the first touch after `ob_bar` may be entering before the object
existed.

### (f) Parameters

| name | range | default |
|---|---|---|
| `OB_ZONE` | {FULL, BODY} | FULL |
| `OB_MAX_ATR` | 0.5–4.0 | 2.0 |
| `OB_MIT` | {TOUCH, HALF, CLOSE_THROUGH} | TOUCH |
| candle rule | {LAST_OPPOSING, LOWEST_LOW} | LAST_OPPOSING |

### (g) Measurable? **Tier 2.** Objective per convention, but the convention is
a free choice and there are ≥16 of them.

## F3. Breaker blocks

### (a) Competing definitions

1. An OB whose zone is closed through; role flips (bullish OB → bearish
   breaker). [2nd-hand, multiple]
2. "Forms when an order block is partially mitigated (tested once) but doesn't
   fully fill" [2nd-hand, quantum-algo] — a **completely different and
   incompatible** definition: (1) requires full violation, (2) requires
   partial mitigation and no violation.
3. `smc.py` [VERIFIED, L424–440] implements (1): sets `breaker[idx] = True`
   when price violates the OB's far edge, then *deletes* the OB entirely if
   price later exceeds the OB's top.

### (b) Disagreement

(1) and (2) are not variants — they select disjoint sets. An analyst reading
two articles will implement contradictory logic. This is the sharpest example
of vocabulary drift in the source material.

### (c) Canonical definition

```
Adopt (1), and name it explicitly:
    A bullish OB whose zone is CLOSE_THROUGH-invalidated at bar k becomes a
    BEARISH_BREAKER with the same zone bounds, origin_bar = k, and a fresh
    object id. The parent OB is retired.
    A breaker is retired in turn when price closes through it in the
    opposite direction.
Definition (2) is renamed PARTIALLY_MITIGATED_OB and kept as an attribute of
the OB, not as a separate object.
```

### (d) Lag: knowable at bar `k`, the invalidating close. Zero extra.

### (e) Repaint trap: reviving a retired breaker.

### (f) Parameters: none new — inherits `OB_MIT`.

### (g) Measurable? Tier 2, inherits every convention from §F2.

## F4. Evidence for FVG / OB / breakers — honest statement

**No systematic test with reported statistics was found for any of the three.**

Everything located is vendor or educational content. The one page that
advertises numbers ("60%+ win rates using real market data") gives no sample
size, no instrument list, no cost assumption, no out-of-sample split, and no
definition of the win — it is marketing, and is cited here only to be
dismissed.

What can be said:

- These are the **cheapest concepts to test in the entire framework**: FVG has
  zero lag, two parameters, and an unambiguous definition. An FVG study needs
  no strategy at all — measure the conditional distribution of the next `N`
  bars' returns given an FVG formed, versus the unconditional distribution,
  in the Lo-Mamaysky-Wang style.
- The prior from `findings/01_liquidity_evidence.md` is not encouraging: the
  measured microstructure effects in this family are smaller than a retail
  gold spread.
- The specific risk with OBs is that their **Tier-2 status makes false positives
  cheap**: with 16 defensible conventions, someone testing all of them will find
  one that works at the 5% level by construction. Any OB result must be
  reported with the number of conventions tried, and must survive the
  Sullivan-Timmermann-White style adjustment for that count.

Status for all three: **UNPROVEN. No test found, ours or anyone's.**

---

# PART 6 — CONSOLIDATION

## CN1. Mathematical detection

### (a) Competing definitions

1. **Range/ATR.** `(maxH(N) - minL(N)) / ATR <= threshold`. Simplest.
2. **Choppiness Index.** `CHOP = 100*log10( sum(TR,N) / (maxH(N)-minL(N)) ) /
   log10(N)`, N=14, thresholds 61.8 (chop) / 38.2 (trend) [2nd-hand,
   TradingView/LuxAlgo]. This is exactly a **path-to-range ratio** in log
   form — the reciprocal of the "range-to-path" idea.
3. **Volatility contraction.** `ATR(N) / ATR(4N) <= threshold`; the NR7 /
   inside-bar family is a discrete cousin.
4. **Bar overlap ratio.** Mean pairwise overlap of consecutive bars'
   `[L,H]` intervals as a fraction of their union.
5. **Swing compression.** Successive pivot amplitudes shrinking (a triangle).
6. **Bollinger squeeze / band width percentile.**

### (b) Disagreement and why it matters

(1) and (2) are near-duplicates: CHOP's numerator is summed true range (path)
and its denominator is the N-bar range, so CHOP and `range/ATR` are monotone
transforms of nearly the same quantity. **Including both is collinear
parameter bloat with no added information.** Likewise the Kaufman efficiency
ratio (§R1) is `|net move| / path` — the same family again. Three names, one
measurement. Recognising this removes several parameters for free.

(3) and (4) genuinely measure something different (contraction over time,
and bar-to-bar containment) and are worth carrying separately. (5) requires
pivots and inherits `K` and its lag.

### (c) Canonical definition

```
PARAMS: CN_N          # window length
        CN_RANGE_ATR  # range/ATR ceiling
        CN_MIN_BARS   # minimum duration to call it a consolidation

At close of bar i (all windows END at i, never extend past it):
    hi   = max(H[i-CN_N+1 .. i])
    lo   = min(L[i-CN_N+1 .. i])
    width_atr = (hi - lo) / ATR[i]
    in_box(i) := width_atr <= CN_RANGE_ATR

    consolidation is ACTIVE at i iff in_box has been true for the last
    CN_MIN_BARS consecutive bars.
    box = [lo, hi] frozen at the bar where ACTIVE first became true;
          it is NOT extended as new bars arrive.

Carried as continuous diagnostics, not as extra gates:
    chop(i)    = 100*log10( sum(TR, CN_N) / (hi - lo) ) / log10(CN_N)
    contract(i)= ATR(CN_N)[i] / ATR(4*CN_N)[i]
    overlap(i) = mean over k in window of
                 max(0, min(H[k],H[k-1]) - max(L[k],L[k-1])) /
                 (max(H[k],H[k-1]) - min(L[k],L[k-1]))
```

Freezing the box is essential: a box that grows to contain new bars can never
be broken, so "breakout from consolidation" becomes undefined.

### (d) Lag

`in_box` is knowable at `i`. `ACTIVE` requires `CN_MIN_BARS` of persistence, so
a consolidation is first declared `CN_MIN_BARS - 1` bars after it actually
began. The **box boundaries** are known at that moment, which is what matters
for a breakout rule.

### (e) Repaint trap

- Extending the box forward (above).
- Declaring the consolidation at its *start* bar in the plot, then reading it
  there. Same class as the pivot trap.
- Using `ATR[i]` computed over a window that overlaps the box — mild, but note
  that a consolidation deflates ATR, so `width/ATR` is partly self-referential.
  Using `ATR[i - CN_N]` (pre-box volatility) is the cleaner choice and should
  be tested as a variant.

### (f) Parameters

| name | range | default |
|---|---|---|
| `CN_N` | 8–60 | 20 |
| `CN_RANGE_ATR` | 1.0–4.0 | 2.0 |
| `CN_MIN_BARS` | 3–20 | 5 |

## CN2. Objectively measurable?

**Tier 1.** Consolidation detection is arithmetic.

## CN3. Continuation vs reversal consolidation, decided BEFORE the break

**No source found offers a pre-break rule that is not a restatement of the
prior trend.** "A continuation pattern is one that resolves in the direction of
the prior trend" is a definition by outcome — Tier 3, unfalsifiable.

The candidate pre-break features that *are* measurable:

| feature | measurable at | rationale offered in the wild |
|---|---|---|
| prior trend direction (§R1 ER sign) | box confirmation | trend persistence |
| where the box sits vs the prior leg (retracement %) | box confirmation | shallow = continuation |
| box slope (regression on closes) | box confirmation | drift inside the box |
| volume/tick-volume trend inside box | box confirmation | "absorption" |
| which side of the box has more touches | continuously | "pressure" |
| position of the box relative to PDH/PDL/session levels | box confirmation | liquidity context |
| whether the box formed after a displacement | box confirmation | flag vs reversal |

**Status: OPEN QUESTION with a cheap test.** Fit no model. Instead:
for every confirmed box, record the features above and the realised break
direction, then report `P(break in prior-trend direction | feature quintile)`
with Wilson intervals. If no feature's Q1–Q5 spread excludes zero, the answer
is "no, they cannot be distinguished before the break" — which is a publishable
finding for this project and would kill a large amount of downstream
complexity. This test costs one script and no strategy.

---

# PART 7 — REGIME

## R1. Trend / range / compression / expansion, measurably

### (a) Candidate measures compared

| measure | formula | range | what it actually measures | causal? |
|---|---|---|---|---|
| **Kaufman Efficiency Ratio** | `abs(C[i]-C[i-N]) / sum(abs(C[k]-C[k-1]), N)` | 0–1 | net displacement ÷ path length | yes |
| **ADX** | Wilder DI smoothing | 0–100 | persistence of directional movement, smoothed | yes, but heavily lagged (2 nested Wilder smoothings ≈ 2N effective) |
| **CHOP** | `100*log10(sum(TR,N)/(maxH-minL))/log10(N)` | 0–100 | path ÷ range, log-scaled | yes |
| **ATR percentile** | rank of `ATR[i]` in trailing window | 0–1 | volatility level vs own history | yes if trailing |
| **Realized vol** | stdev of log returns × sqrt(bars/yr) | ≥0 | dispersion, direction-blind | yes |
| **Range-to-path** | `(maxH-minL) / sum(TR)` | 0–1 | reciprocal-ish of CHOP | yes |

### (b) Disagreement and redundancy — the important part

- **ER, CHOP and range-to-path are the same family.** All three are
  net-or-range over path. Using two of them as "confluence" is
  self-confirmation. **Pick one. ER is preferred**: it is bounded 0–1, uses
  closes (so it is directionally meaningful), needs one parameter, and has no
  smoothing lag.
- **ADX answers a different question but slowly.** "ADX rises with persistent
  directional movement while choppiness rises with congestion… they answer
  near-opposite questions" [2nd-hand]. ADX's double Wilder smoothing means a
  regime change is reflected roughly `2N` bars late, which for intraday
  regime-switching is often longer than the regime.
- **Fixed thresholds do not transfer.** "Efficiency baselines differ by market
  and timeframe, so a fixed cutoff like 0.3 that works on one chart is
  meaningless on another. The defensible approaches are relative: percentile
  thresholds computed from the instrument's own history" [2nd-hand, LuxAlgo].
  Likewise "ADX… its fixed scale means a reading of 25 carries different weight
  on different instruments." **Adopt percentile thresholds, not levels.** This
  also removes the need to re-tune per timeframe, which saves parameters.
- **Trend/range and compression/expansion are orthogonal.** ER answers the
  first; ATR percentile answers the second. A market can be trending and quiet,
  or ranging and violent. Collapsing them into one "regime" number destroys the
  distinction that matters most to a sweep strategy (a sweep in a quiet range is
  a different animal from a sweep in a volatile trend).

### (c) Canonical definition — a 2×2 grid, two parameters

```
PARAMS: ER_N, ATRP_N, REG_WIN, REG_LO_Q, REG_HI_Q

er(i)   = abs(C[i] - C[i-ER_N]) / sum(abs(C[k]-C[k-1]) for k in (i-ER_N, i])
          # 0 if denominator == 0
atrp(i) = fraction of the last REG_WIN values of ATR (bars i-REG_WIN .. i-1)
          that are <= ATR[i]                      # TRAILING percentile

er_q(i) = trailing percentile of er(i) over the last REG_WIN values of er
          (excluding i)

trend_axis = er_q(i) >= REG_HI_Q  ? TRENDING
           : er_q(i) <= REG_LO_Q  ? RANGING
           :                        MIXED
vol_axis   = atrp(i) >= REG_HI_Q  ? EXPANSION
           : atrp(i) <= REG_LO_Q  ? COMPRESSION
           :                        NORMAL

regime(i)  = (trend_axis, vol_axis)     # 9 cells; report all, gate on few
```

Both axes are percentile-based, so both are unit-free, both transfer across
timeframes and instruments, and both hold the *event rate* fixed — which means
a regime filter cannot silently change the number of trades when you change
instrument, which is a common source of illusory improvement.

### (d) Lag

`er` and `atrp` are knowable at bar `i`. The **percentile** needs `REG_WIN`
bars of warm-up. ADX, if used at all, is effectively `2 × ADX_N` bars late.

### (e) Repaint trap

- **Full-sample percentiles.** Fatal and easy: computing `ATR` percentile over
  the entire backtest means the 2024 regime label depends on 2026 volatility.
  A strategy gated on that will look like it avoided the bad periods.
- Z-scoring with full-sample mean/std — same error in a different costume.
- Using `ATR[i]` where `ATR[i-1]` belongs (consistency with §D1).

### (f) Parameters

| name | range | default |
|---|---|---|
| `ER_N` | 10–50 | 20 |
| `REG_WIN` | 200–2000 | 500 |
| `REG_LO_Q` | 0.20–0.40 | 0.33 |
| `REG_HI_Q` | 0.60–0.80 | 0.67 |
| `ATRP_N` | fixed = `ATR_LEN` | 14 |

`REG_LO_Q` and `REG_HI_Q` should be tied (`REG_HI_Q = 1 - REG_LO_Q`), saving
one parameter. **4 parameters, or 3 if tied.** Compare with carrying ER + ADX +
CHOP + BB-width, which is 8+ parameters measuring 2 things.

### (g) Measurable? **Tier 1.** Regime is the best-defined part of the whole
framework and the only part with a genuine quantitative literature behind the
individual measures.

---

# CONFIRMATION LAG TABLE

Lag is in **bars of the concept's own timeframe**, counted from the bar where
the underlying event *occurred* to the bar at which it is first knowable and
final. `K` is the pivot half-width (§S1).

| concept | first knowable at | lag | why |
|---|---|---|---|
| Displacement bar (§D1) | bar `i` | **0** | pure single-bar arithmetic on closed OHLC |
| Displacement + FVG qualified | bar `i+1` | **1** | needs the third bar of the gap |
| FVG (§F1) | bar `i` (3rd bar) | **0** | `L[i] > H[i-2]` needs no future bar |
| PDH / PDL, PWH / PWL (§L4) | first bar of the new period | **0** | previous period is complete by construction |
| Session high/low (§L5) | first bar after the session closes | **0** | ditto; the in-session running max is NOT a level |
| Regime: ER, ATR percentile (§R1) | bar `i` | **0** (+`REG_WIN` warm-up) | trailing windows only |
| ADX (if used) | bar `i` | **≈2·N effective** | two nested Wilder smoothings |
| Consolidation box (§CN1) | `CN_MIN_BARS - 1` bars after it began | `CN_MIN_BARS-1` | persistence requirement |
| Swing pivot, raw (§S1) | `p + K` | **`K`** | needs `K` bars to the right |
| Swing pivot, *sealed* | confirmation of the next opposite pivot | `K` + variable | only sealed pivots are immutable |
| HH/HL/LH/LL (§S2) | `p_n + K` | **`K`** | inherits the pivot |
| EQH / EQL (§L2) | `p_n + K` (newest member) | **`K`** | inherits the pivot |
| BOS / CHoCH (§S3) | the breaking bar, `≥ p + K + 1` | **`K+1` minimum** | the pivot's own right-side rule forbids a break on bar `p+K` |
| CHOCH_D | same bar as the CHoCH | **`K+1` min** | displacement is same-bar |
| Protected high/low (§S4) | the BOS/CHoCH bar | **`K+1` min** | derived from the leg |
| Order block (§F2) | the BOS/CHoCH bar `i` | **`i - ob_bar`**, unbounded | the zone does not exist until structure breaks |
| Breaker (§F3) | the invalidating close | 0 past the OB | |
| First-leg pullback / "inducement" (§L6) | the BOS bar | **`K+1` min** | uses pivots sealed before the break |
| Sweep **A** (§SW) | the sweep bar `i0` | **0** past the level | same-bar reclaim |
| Sweep **B** | `reclaim_bar` | **1 … `FAST_N`** | |
| Sweep **C** | `reclaim_bar` | **1 … `W`** | |
| Sweep **D** | `disp_bar` | reclaim **+ 0 … `R_D`** | |
| Sweep **E** | `shift_bar` | reclaim + (`K+1` … `W`) | needs a CHoCH on the other side |
| Sweep **F** | the re-break bar | **up to `W`** | **outcome label — not tradable** |
| Sweep **G** | `i0 + W` | **`W`** | **outcome label — not tradable** |
| M15 signal read on M1 | close of the M15 bar | **up to 14 M1 bars** | HTF bars close on a grid |

**Worst realistic chain**, an M15 Type-E sweep with `K=3`, `W=10`:
the M15 pivot forms → +3 M15 bars to confirm → +1 M15 bar minimum to break →
sweep → +1..10 M15 bars to reclaim and shift → and each M15 bar is 15 minutes.
The entry can legitimately be **over two hours** after the swing low that the
narrative says caused it. Any backtest that enters closer than that to the
swing is lying.

---

# REPAINT TRAP LIST

Ordered by how much damage each does to a backtest.

**RT1 — Full-sample statistics used as a per-bar threshold.**
`smc.py` L595: `pip_range = (high.max() - low.min()) * range_percent`. The
equal-high tolerance for every bar in the series is derived from the entire
series' range, future included. Same class: `df.rank(pct=True)`,
`np.percentile(whole_array)`, z-scores on full-sample mean/std, "top decile of
ATR" computed once. **Fix:** every normalisation uses a trailing window ending
at `i-1`.

**RT2 — Signals stamped at a bar earlier than the bar that decided them.**
`smc.py` L253–330 writes the BOS/CHoCH flag at `last_positions[-2]`; L354–370
then deletes any BOS/CHoCH that was never subsequently broken. `smc.py`
L72–100 stamps the FVG at the middle bar via `shift(-1)`. `smc.py` L165–192
runs the pivot-alternation cleanup as a global while-loop, and L196–205 force
the first and last elements of the series to be pivots regardless of price.
**Fix:** every emitted signal carries a `known_at` field and the backtester
reads signals by `known_at`, never by array position.

**RT3 — Reading the pivot at the pivot bar.** The chart draws it at `p`; it was
learned at `p+K`. Applies identically to order blocks (drawn at `ob_bar`,
learned at the BOS bar) and to consolidation boxes.
**Fix:** shift every plotted object's *usable* timestamp forward to its
`known_at`, and assert `known_at <= current_bar` at read time.

**RT4 — Future-scanning "mitigation" columns joined onto the bar.**
`smc.py` computes `MitigatedIndex` / `BrokenIndex` / `Swept` by scanning
`ohlc[i+2:]`. These are correct *labels* for offline analysis and are pure
lookahead if used as features. **Fix:** keep labels and features in separate
frames, and never let the feature frame contain a column derived from `i+1`
onward.

**RT5 — Higher-timeframe leakage.** Pine
`request.security(..., lookahead=barmerge.lookahead_on)`, or reading
`request.security` output without `[1]`. MQL5 `CopyRates(sym, PERIOD_M15, 0,
...)` — index 0 is the *forming* bar. **Fix:** Pine `lookahead_off` plus `[1]`;
MQL5 `shift = 1`, and gate on `iTime(sym, tf, 0)` changing before acting.

**RT6 — The forming bar.** Acting on `C[0]` / `close` of the in-progress bar.
In Pine, guard with `barstate.isconfirmed`; in MQL5, detect a new bar by
comparing `iTime(_Symbol, _Period, 0)` to a stored value.

**RT7 — Windows that extend past the current bar.** `depth_max` over
`[i0, i0+W]` when only `i < i0+W` bars exist. In vectorised code this is the
default behaviour and produces silently perfect entries.

**RT8 — Reviving consumed objects.** A level that was closed through, an OB
that was invalidated, a breaker that was broken. If an object's state can move
backwards, its history depends on the future.

**RT9 — Choosing the level/inducement/POI in hindsight.** The visual-backtest
lie: picking, on the chart, the swing that was in fact swept. Every level must
have been emitted, with an id, before `i0`.

**RT10 — Recomputing an old label with today's ATR.** The HH/LH label of a
2023 pivot pair, or the ATR-relative equal-highs tolerance of an old cluster,
must be frozen at its `known_at` bar.

**RT11 — Broker/exchange time drift between platforms.** Pine uses the
symbol's exchange session; MQL5 uses broker server time; neither is UTC and
neither is `America/New_York` unless you force it. A PDH that differs between
the two is not a bug in the code, it is a missing definition. **Fix:** force
`DAY_ROLL_TZ` explicitly on both sides and reconcile PDH values bar-for-bar
before comparing any strategy result.

**RT12 — Tie-break divergence.** Equal highs are common on 0.01-tick XAUUSD.
If Pine's pivot tie handling and your MQL5 port's differ, the two produce
different pivot sets and neither is wrong. **Fix:** implement the pivot rule by
hand in both, with the tie rules of §S1 written out, rather than using
`ta.pivothigh` on one side and a hand-rolled loop on the other.

**RT13 — Survivorship in the level set.** Deleting levels that were never
touched, or only keeping "the levels that mattered". `findings/` already
records this class of error; it applies directly to level bookkeeping.

---

# PARAMETER INVENTORY

The previous EA reached **748 parameters** and that killed it. Total count is
therefore treated here as a first-class design constraint, not an afterthought.

Column key: **T** = tunable (must be swept, counts fully against the budget);
**S** = structural switch (a definition choice — test both, never optimise);
**O** = off by default (costs nothing until enabled);
**D** = derived/tied (costs nothing).

| # | parameter | § | class | range | default |
|---|---|---|---|---|---|
| 1 | `ATR_LEN` | global | T | 10–30 | 14 |
| 2 | `K` (pivot half-width, shared across TFs) | S1 | T | 1–8 | 2 |
| 3 | `K_M5`, `K_M1` untied | S5 | D | — | tied to `K` |
| 4 | `M_SWING_ATR` | S1 | O | 0.25–1.5 | 0 (off) |
| 5 | break mode (close / wick) | S3 | S | — | close |
| 6 | `DISP_LOOKBACK` | S3 | T | 1–5 | 3 |
| 7 | `MAX_SETUP_BARS` | S6 | T | 5–60 | 20 |
| 8 | `EQ_TOL_ATR` (shared S2+L2) | L2 | T | 0.02–0.30 | 0.10 |
| 9 | `EQ_MAX_SPAN` | L2 | T | 10–200 | 60 |
| 10 | `EQ_MIN_COUNT` | L2 | T | 2–4 | 2 |
| 11 | `DAY_ROLL_TZ` / `DAY_ROLL_HH` | L4 | S | — | 17:00 America/New_York |
| 12 | session set | L5 | S | — | ASIA, LONDON, NY, OVERLAP |
| 13 | session boundary mode | L5 | S | fixed-UTC / DST-aware | DST-aware |
| 14 | `PCT_WIN` (score normalisation) | L7 | T | 100–2000 | 500 |
| 15 | `SCORE_GATE` | L7 | S | off / top½ / top⅓ | top⅓ |
| 16 | score weights `w_k` | L7 | D | — | all 1 |
| 17 | `W` (sweep decision window) | SW | T | 3–30 | 10 |
| 18 | `DEEP_ATR` | SW | T | 0.3–2.0 | 0.75 |
| 19 | `FAST_N` | SW | T | 1–5 | 2 |
| 20 | `CLR_MAX` | SW | T | 0.15–0.50 | 0.33 |
| 21 | `WICK_MIN` | SW | O | 0.3–0.7 | 0 (off, redundant with `CLR_MAX`) |
| 22 | `R_D` | SW | T | 1–5 | 3 |
| 23 | `NB_BREAK` | SW | T | 1–3 | 2 |
| 24 | `DISP_ATR` | D1 | T | 1.0–3.0 | 1.5 |
| 25 | `DISP_BODY` | D1 | T | 0.45–0.85 | 0.60 |
| 26 | `DISP_PCT` | D1 | O | 0.85–0.99 | 0 (off) |
| 27 | `DISP_PCT_WIN` | D1 | O | 200–2000 | 500 (only if 26 on) |
| 28 | `FVG_MIN_ATR` | F1 | T | 0.05–0.60 | 0.15 |
| 29 | FVG mitigation level | F1 | S | TOUCH/HALF/FILLED | HALF |
| 30 | `OB_ZONE` | F2 | S | FULL/BODY | FULL |
| 31 | `OB_MAX_ATR` | F2 | T | 0.5–4.0 | 2.0 |
| 32 | `OB_MIT` | F2 | S | TOUCH/HALF/CLOSE_THROUGH | TOUCH |
| 33 | OB candle rule | F2 | S | LAST_OPPOSING / LOWEST_LOW | LAST_OPPOSING |
| 34 | `CN_N` | CN1 | T | 8–60 | 20 |
| 35 | `CN_RANGE_ATR` | CN1 | T | 1.0–4.0 | 2.0 |
| 36 | `CN_MIN_BARS` | CN1 | T | 3–20 | 5 |
| 37 | `ER_N` | R1 | T | 10–50 | 20 |
| 38 | `REG_WIN` | R1 | T | 200–2000 | 500 |
| 39 | `REG_LO_Q` | R1 | T | 0.20–0.40 | 0.33 |
| 40 | `REG_HI_Q` | R1 | D | — | `1 - REG_LO_Q` |
| 41 | `ATRP_N` | R1 | D | — | `= ATR_LEN` |

## Counts

| class | count |
|---|---|
| **T — tunable, counts against the budget** | **26** |
| S — structural switches (test both, do not optimise) | 9 |
| O — off by default | 4 |
| D — derived / tied | 4 |
| **Total named** | **43** |

**26 tunable parameters is still too many for a single fit.** Two disciplines
keep it honest:

1. **Staged enabling.** The document is deliberately built so that the cheapest
   concepts stand alone. A first study needs only:
   `ATR_LEN`, `DAY_ROLL`, session set, `W`, `DEEP_ATR`, `FAST_N`, `CLR_MAX`,
   `NB_BREAK` — **6 tunable + 2 switches**. That is enough to measure
   `P(F | morphology)` on PDH/PDL and session levels, with no pivots, no order
   blocks, no score, and no strategy. If that shows nothing, none of the
   remaining 20 parameters can save it, and they should never be written.
2. **Every added parameter must buy its place.** Before a parameter is
   introduced, state the univariate test it must pass (§L7 Stage 1). The 748
   came from adding knobs to fix symptoms; the fix for a symptom is usually
   deletion, not a knob.

Explicit savings already taken in this document, and what they cost elsewhere:
banning MSS (−1 concept), tying `K` across timeframes (−2), tying `REG_HI_Q`
(−1), using `CLR_MAX` instead of `CLR_MAX`+`WICK_MIN` (−1), picking ER over
ER+CHOP+range-to-path (−2 to −4), refusing an 8-input weighted liquidity score
in favour of an equal-weight gate (−14), refusing tunable session boundaries
(−8). **Roughly 30 parameters not created.**

---

# SOURCES

**[VERIFIED] — read in full by me this session**

- `joshyattridge/smart-money-concepts`, `smartmoneyconcepts/smc.py`, 987 lines,
  master branch, fetched 2026-08-29.
  https://raw.githubusercontent.com/joshyattridge/smart-money-concepts/master/smartmoneyconcepts/smc.py
  Repo: https://github.com/joshyattridge/smart-money-concepts
  Line references used above: L72–100 (fvg), L137–205 (swing_highs_lows,
  incl. `swing_length *= 2` at L151 and the forced first/last pivots at
  L196–205), L222–370 (bos_choch, incl. the `last_positions[-2]` stamping and
  the L354 "remove the ones that aren't broken" pass), L376–470 (ob, incl. the
  lowest-low candle selection), L573–698 (liquidity, incl. the global
  `pip_range` at L595 and the mean level at L648), L701–790 (previous_high_low),
  L793–898 (sessions).

**[2nd-hand] — search-snippet synthesis only, NOT opened**

Structure / SMC vocabulary
- TradingView, *Williams Fractal* support article —
  https://www.tradingview.com/support/solutions/43000591663-williams-fractal/
- TradingView, *Pivot Points High Low* support article —
  https://www.tradingview.com/support/solutions/43000589195-pivot-points-high-low/
- TradingView, Pine Script docs, *FAQ / Techniques* (repainting) —
  https://www.tradingview.com/pine-script-docs/faq/techniques/
- FXOpen, *What is a Break of Structure* —
  https://fxopen.com/blog/en/what-is-a-break-of-structure-and-how-can-you-trade-it/
- Quantum-Algo, *BOS & CHoCH: Complete 2026 Guide to Market Structure Shifts*
  (the MSS = CHoCH + displacement reading) —
  https://www.quantum-algo.com/blog/guides/bos-choch-complete-trading-guide/
- TradingFinder, *All Smart Money Concepts (SMC) Abbreviations* —
  https://tradingfinder.com/education/forex/smc-abbreviation/
- LuxAlgo, *Smart Money Concepts (SMC)* indicator library (internal vs swing
  structure, EQH/EQL threshold, ATR-based OB size filter) —
  https://www.luxalgo.com/library/indicator/smart-money-concepts-smc/
- LuxAlgo, *Zigzag Structure* concept —
  https://www.luxalgo.com/library/concept/zigzag-structure/
- PatternSmart, *Why Do Some Trading Indicators Repaint?* —
  https://patternsmart.com/wp/why-do-some-trading-indicators-repaint/

Liquidity / sessions / inducement
- ICT Killzone Times —  https://ictkillzonetimes.com/
- TradingRage, *ICT Killzones (2026)* —
  https://tradingrage.com/learn/ict-killzone-explained
- FXOpen, *Kill Zone Trading in Forex* —
  https://fxopen.com/blog/en/kill-zone-trading-in-forex/
- TradingFinder, *What is Inducement* —
  https://tradingfinder.com/education/forex/inducement/
- WritOfFinance, *What is Inducement (IDM) in Trading* —
  https://www.writofinance.com/inducement-in-forex-trading/
- Equiti, *Inducement in SMC Explained* —
  https://www.equiti.com/sc-en/news/trading-ideas/inducement-in-smc-explained-how-smart-money-traps-work/

Displacement / FVG / order blocks
- ICTKillzone, *ICT Displacement: The Complete Guide* —
  https://www.ictkillzone.com/ict-displacement
- Backtrex, *ICT Displacement Candle* —
  https://backtrex.com/en/blog/ict-displacement-candle-market-concept
- LuxAlgo, *Fair Value Gap* concept —
  https://www.luxalgo.com/library/concept/fair-value-gap/
- DailyPriceAction, *Fair Value Gaps* —
  https://dailypriceaction.com/blog/fair-value-gap/
- DailyPriceAction, *Order Blocks Will Fail You Without These 3 Simple Rules* —
  https://dailypriceaction.com/blog/order-blocks/
- Quantum-Algo, *Order Blocks Deep Dive: 7 Types* (the incompatible
  "partially mitigated" breaker definition) —
  https://www.quantum-algo.com/academy/order-blocks-deep-dive/
- Edgeful, *FVG best practices* (the "60%+ win rates" marketing claim, cited
  only to be dismissed) —
  https://www.edgeful.com/blog/posts/fair-value-gap-best-practices-guide

Regime
- LuxAlgo, *Kaufman Efficiency Ratio* concept —
  https://www.luxalgo.com/library/concept/kaufman-efficiency-ratio/
- LuxAlgo, *Choppiness Index* concept —
  https://www.luxalgo.com/library/concept/choppiness-index/
- TradingView, *Choppiness Index (CHOP)* —
  https://www.tradingview.com/support/solutions/43000501980-choppiness-index-chop/
- TrendSpider, *Kaufman Efficiency Ratio* —
  https://trendspider.com/learning-center/kaufman-efficiency-ratio/

Platform mechanics
- MQL5 docs, *CopyRates* — https://www.mql5.com/en/docs/series/copyrates
- MQL5 Articles, *Building a Modular Fair Value Gap (FVG) Detection Engine in
  MQL5* (the `shift = 1` closed-bar convention) —
  https://www.mql5.com/en/articles/23539

Academic (all second-hand; none of these PDFs was reachable this session)
- Lo, Mamaysky & Wang (2000), *Foundations of Technical Analysis*,
  J. Finance 55(4) — https://www.nber.org/papers/w7613
- Sullivan, Timmermann & White (1999), *Data-Snooping, Technical Trading Rule
  Performance, and the Bootstrap*, J. Finance 54(5) —
  https://onlinelibrary.wiley.com/doi/10.1111/0022-1082.00163
- Atkins & Dyl (1990); Bremer & Sweeney (1991); Cox & Peterson (1994) — large
  one-day price change reversal/continuation; reached only via search snippets.
  See also https://www.sciencedirect.com/science/article/abs/pii/S014829631830420X
- Osler (2000, 2003, 2005) and Osler & Savaser (2011) — order clustering; not
  re-reviewed here, see `JARVIS/research/findings/01_liquidity_evidence.md`.

---

# WHAT TO DO WITH THIS DOCUMENT

1. Implement §S1, §L4, §L5, §D1, §F1 first. They are the zero-lag, low-parameter
   primitives and they need no pivots except §S1.
2. Run the **`P(F | morphology, confirm)` study** (§SW Type F). It requires no
   entries, no stops, no targets and no cost model, so it cannot be killed by
   cost assumptions and cannot be fitted. It is the cheapest possible fair test
   of whether the sophisticated sweep taxonomy contains information that the
   naive rule in E-003 did not.
3. Only if step 2 shows separation, build a strategy — and register it in
   `EXPERIMENTS.md` as UNPROVEN until `study.py` says otherwise.
4. Do not implement order blocks, breakers, or the liquidity score until every
   component has passed §L7 Stage 1. They are Tier 2, they are expensive in
   parameters, and there is no evidence for them.


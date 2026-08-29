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


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


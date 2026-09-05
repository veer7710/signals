# ICT / SMC — EXTERNAL RESEARCH
**What practitioners and open-source implementations ACTUALLY do, at the level of
a rule a program can evaluate on closed bars — and what evidence exists that any
of it pays.**

Written 2026-09-05. External research only: **no experiment was run for this
document.** Nothing here is a claim that anything is profitable.

---

## 0. HOW TO READ THIS, AND WHAT IT DOES NOT REPEAT

`JARVIS/research/DEFINITIONS.md` (2311 lines, 2026-08-29) already derives the
no-lookahead canonical definitions, the confirmation-lag table, the repaint-trap
list and the parameter inventory. **This document does not redo that work.** It
adds the four things that session could not get:

1. **Source code it could not reach.** That session had exactly ONE verified
   artefact (`smc.py`). This one has five, including LuxAlgo's actual Pine.
2. **Measured detection densities at M1** from an independent dataset.
3. **A real published backtest of ICT concepts** with a stated methodology —
   `DEFINITIONS.md` §D2 and §F4 both record "no test found, ours or anyone's."
   One now exists, and it is negative.
4. **Hypotheses aimed at the CURRENT system** (E-127/128/129: M1 pivot 5 +
   SuperTrend direction + limit inside the zone + ST band trail, 79.2 control se).

### Sourcing tiers used throughout

| tag | meaning |
|---|---|
| **[CODE]** | I fetched the source file and read it. Line numbers given. This is the only tier I will defend as fact. |
| **[DOC]** | I fetched a text/markdown file in full from a public repo and read it. Its own citations are unverified. |
| **[SNIPPET]** | Search-engine synthesis of a page I could **not** open. A pointer, never a number to rely on. |

### The egress constraint, stated plainly
`raw.githubusercontent.com`, anonymous `git clone`, and the GitHub code-search
API are reachable. **Everything else practitioner-facing is blocked at the
proxy**: tradingview.com, luxalgo.com, gist.githubusercontent.com, arxiv.org,
newyorkfed.org, statoasis.com, backtrex.com, quantum-algo.com, mql5.com,
technicalanalysis.org.uk. So every practitioner claim below is [SNIPPET] unless
it came out of a GitHub file. I did not paper over this by paraphrasing snippets
as if I had read the source.

---

## 1. PRECISE ALGORITHMIC DEFINITIONS

Only rules a program can evaluate on **closed bars**. Where implementations
disagree, the disagreement is the finding.

### 1.1 The definitions table

| concept | the rule, evaluated at close of bar `i` | tolerance / threshold actually used | who disagrees, and how |
|---|---|---|---|
| **swing pivot (symmetric fractal)** | `p = i-K` is a pivot high iff `high[p] > max(high[p-K..p-1])` and `high[p] > max(high[p+1..p+K])`. Known only at `i`, K bars late. | K=3,5 (LTF), 10–20 (structural M1) | `smc-py` uses K=`swing_length` but **doubles the input** (`swing_length *= 2`, smc.py:151) so `swing_length=50` means ±50 bars **[CODE]**. Strict `>` silently drops equal highs — the research pack calls this the single most likely cause of "some swings detect, some don't" **[DOC]** |
| **swing pivot (LuxAlgo `leg()`)** | **Not symmetric.** `newLegHigh = high[size] > ta.highest(size)` — compares the bar `size` back only against the `size` bars AFTER it, no left-side test. A state machine (`leg` flips 0↔1) then emits one alternating pivot per flip. lux_smc.pine:337-347 **[CODE]** | `swingsLengthInput = 50`, internal `= 5` (lux_smc.pine:95, 783) **[CODE]** | This is a materially different level set from a symmetric fractal at the **same** confirmation lag. Nobody documents the difference. |
| **alternation / zigzag normalisation** | After fractal detection, collapse consecutive same-type pivots, keeping the more extreme; iterate to fixpoint. smc.py:165-190 **[CODE]** | none | LuxAlgo gets alternation free from the state machine; smc-py bolts it on afterwards; most Pine scripts don't do it at all. |
| **equal highs / lows (EQH/EQL)** | Two consecutive same-type pivots with `abs(prev_pivot_level - high[size]) < thr` | **`thr = 0.10 × ATR(200)`**, pivot confirmation **3 bars**. lux_smc.pine:110-111, 419, 441; `atrMeasure = ta.atr(200)` at :315 **[CODE]** | `smc-py` uses `pip_range = (df.high.max() - df.low.min()) * 0.01` — **a constant derived from the whole dataset's range, future included** (smc.py:595) **[CODE]**. `ICT_Validated_SMC_v1.6` uses a **percent-of-price** tolerance, default 0.15% (:80) **[CODE]** — on gold at 4100 that is 6.15 points, ~50× LuxAlgo's. |
| **BSL / SSL pool** | The price level of an EQH cluster (BSL, above) or EQL cluster (SSL, below). ≥2 members. | `min_n = 2` | `smc-py` returns the **mean** of the grouped levels and marks the event at the FIRST pivot's index, with `swept` computed from the future (smc.py:641-651) **[CODE]**. Most Pine scripts use the most recent level, not the mean. |
| **liquidity sweep** | `high[i] > level` **and** `close[i] < level` (bearish sweep of a BSL); mirror for SSL. `ICT_Validated_SMC_v1.6.pine`:1394-1410, scanning the last 10 confirmed pivots **[CODE]** | close-back-inside **same bar** is the strict form; the loose form allows return within **1–5 bars** **[DOC]** | **This is the one rule the whole field agrees on** and the variance is only in the return window. Contrast `DAX_SmartMoneyConcepts.mq5`:510-524, which fires "Liquidity Sweep" on `high[i] > level && high[i-1] <= level` with **no close condition at all** **[CODE]** — that is a first-touch breakout detector wearing the word "sweep". |
| **sweep vs run vs grab vs raid** | Same event, three outcomes. **Sweep** = probe + close back inside. **Run/breakout** = probe + close stays outside. **Grab** = single-bar sweep that reverses (long wick). Raid/purge/stop-hunt are synonyms for the sweep. **[SNIPPET]** | — | "The classification only resolves after the close that follows the sweep prints" **[SNIPPET]**. That is the honest statement: sweep and run are **not separable at the probe**. |
| **inducement (IDM)** | **The first pullback inside the leg that produced a BOS/CHoCH** — i.e. an INTERNAL pivot (small K) that forms while the SWING structure (large K) points the other way. In a bullish swing trend, internal **lows** are inducement. **[SNIPPET]** | `ICT_Validated_SMC_v1.6.pine`:751-778 **[CODE]**: `internalLen = 5`, `swingLen = 10`; IDM created from `internalLowVal` only while `swingBullish`; rejected if within **0.1% of price** of the swing low itself; **expires the moment the swing trend flips**. Triggered by `low < idm.price and close > idm.price`. | The rule "never take the first pullback after a BOS — that is the inducement, wait for the sweep" is repeated everywhere **[SNIPPET]** but almost nobody codes it. This is the most under-implemented ICT concept and the most mechanically precise. |
| **displacement** | Two independent dimensions, ANDed: `abs(close-open) > ATR(n) × m` **and** `abs(close-open)/(high-low) >= r` | **`m = 1.5`, `r = 0.65`** is the modal community default (FibAlgo). Zeiierman: `m = 1.2` plus volume `>= 1.5×` 20-bar mean and close in top/bottom 25% of the bar. `ICT_Validated_SMC_v1.6.pine`:65,858 uses `m = 1.0` on `ATR[1]` and **no** body-ratio test. LuxAlgo folds displacement into the FVG as "middle-candle body % move > 2 × running mean absolute body % move" (lux_smc.pine:637-643) **[CODE]** | Six mutually incompatible quantifications catalogued **[DOC]**. There is **no canonical threshold.** Anyone quoting one is quoting a default, not a standard. |
| **BOS** | `close > last confirmed swing high` while trend is already bullish (mirror for bearish). Continuation. | **close beyond, not wick** — near-universal **[DOC][SNIPPET]** | Three incompatible codings: (a) LuxAlgo `ta.crossover(close, pivot.currentLevel)` with a `crossed` flag so each pivot fires once (lux_smc.pine:566-575) **[CODE]**; (b) `smc-py` a 4-swing pattern `[-1,1,-1,1]` with `L1<L2<H1<H2`, **stamped at `last_positions[-2]`**, i.e. two swings in the PAST (smc.py:258-292) **[CODE]**; (c) `profittown` a **Donchian break**: `close > max(high[-21:-1])` (structure.py `detect_bos`) **[CODE]**. These are not the same object. |
| **CHoCH** | Same break, but the trend state was the OTHER way. LuxAlgo: `tag = trend.bias == BEARISH ? CHOCH : BOS` — one line, one state variable (lux_smc.pine:557) **[CODE]** | — | `smc-py` bullish CHoCH requires `H2 > H1 > L1 > L2` — a lower low then a higher high (smc.py:293-305) **[CODE]**. Not the same as LuxAlgo's state-machine version. |
| **MSS** | A counter-trend structural break **with displacement required**. Most sources treat MSS ≈ CHoCH, distinguished only by (i) internal vs external swing and (ii) displacement being **mandatory** for MSS and merely preferred for BOS **[DOC]** | displacement thresholds as above | This is the real content of "MSS vs CHoCH": there is no agreed difference except the displacement requirement. `DEFINITIONS.md` §S3 reaches the same conclusion independently. |
| **fair value gap** | Bullish: `low[i] > high[i-2]`. Bearish: `high[i] < low[i-2]`. Evaluated at close of bar `i`. **Zero lag.** | LuxAlgo adds `close[i-1] > high[i-2]` (the middle candle must also close beyond) **and** a displacement threshold (lux_smc.pine:641) **[CODE]**. `ICT_Validated_SMC_v1.6` adds `midbody >= ATR[1] × 1.0` (:858) **[CODE]** | `smc-py` computes the FVG at the **middle** bar's index using `shift(-1)` (smc.py:74-82) **[CODE]** — one bar of look-ahead if used naively. Universal agreement on the raw 3-bar condition; total disagreement on whether displacement is part of it. |
| **FVG mitigated** | First bar after formation whose `low <= fvg_top` (bullish) — i.e. price re-enters the gap at all. smc.py:115-122 **[CODE]** | — | LuxAlgo instead **deletes** the FVG when price closes fully through the far side (`low < fvg.bottom` for a bullish gap, lux_smc.pine:628-632) **[CODE]**. So one library's "mitigated" is the other's "still live". A study that says "unmitigated FVG" without saying which is uninterpretable. |
| **inverted FVG (iFVG)** | A bullish FVG becomes bearish when **`close < fvg_bottom`** — a full close beyond the **far** boundary. Mirror for bearish. | Majority/canonical camp: close-based. Minority (FluxCharts, FXOpen): wick allowed **[DOC]** | This matters for this repo: **E-079's iFVG produced n=1333 on 1h gold**, which is far too many for a close-through-the-far-boundary trigger on hourly bars. Whatever was tested, it was almost certainly the loose form. |
| **order block** | The last opposing candle before a displacement move that breaks structure. | **Zone = the BODY (open→close)** is the community consensus; the 50% of the body is the "mean threshold" refinement **[DOC]** | Every implementation reviewed uses the **full high–low range instead**: `ICT_Validated_SMC_v1.6.pine`:1057-1058 **[CODE]**, `profittown` ob_filters.py **[CODE]**, `smc-py` (which stores `parsedHighs/parsedLows`) **[CODE]**. The consensus definition and the shipped code disagree on the single most basic property. |
| **OB "valid"** | LuxAlgo's only filter: a bar with `(high-low) >= 2 × ATR(200)` has its `high` and `low` **swapped** before OB search (lux_smc.pine:319-323) **[CODE]** — a deliberately weird way to exclude news spikes from being the OB. Then bullish OB = the bar with the **lowest** `parsedLow` between the broken pivot and the breaking bar (:507-520) **[CODE]** | `2 × ATR(200)` | `ICT_Validated_SMC_v1.6` scores instead: sweep +2, displacement +2, killzone +1, correct premium/discount zone +1, HTF aligned +2, keep if `>= minScore` (:1094-1108) **[CODE]**. Phidias' published version is 8 points, keep at 7+ **[DOC]**. |
| **OB mitigated / invalidated** | LuxAlgo removes a bullish OB when `low < ob.barLow` (or `close`, per input) (:481-501) **[CODE]** | HIGHLOW default, CLOSE optional | Folklore says an OB is **stale after 5–10 bars without a retest** **[DOC]**. **This repo's own E-104 measured the opposite**: points improved monotonically with `arm_life` in 14 of 15 cells and the best value was 600 = no constraint at all. Trust the measurement, not the folklore. |
| **breaker block** | Four-point swing sequence (low → high → **lower low** → higher high for a bullish breaker), where the failing swing **first traded beyond a prior extreme** (a liquidity raid), then structure broke the other way. The old OB is retested from the opposite side. **Body close** to violate, not wick. **[SNIPPET]** | — | The raid is what separates a **breaker** from a **mitigation block**: same role-flip, but a mitigation block's failing swing stops short of the prior extreme **[SNIPPET]**. |
| **dealing range** | The leg between the last confirmed significant swing low and swing high. | — | Nobody defines "significant" **[SNIPPET]**. |
| **premium / discount** | **Above the 50% of the dealing range = premium; below = discount.** Equilibrium is exactly 0.50. This is unanimous in the practitioner literature **[SNIPPET]** and is what `ICT_Validated_SMC_v1.6.pine`:1422-1443 codes **[CODE]** | 0.50 | **LuxAlgo does something else entirely**: premium = the top **5%** of the range `[0.95·top+0.05·bottom, top]`, discount = the bottom 5%, equilibrium = ±2.5% around the midpoint (lux_smc.pine:756-761) **[CODE]**. The #1 SMC indicator on TradingView and the entire written literature use incompatible definitions of the same phrase. |
| **OTE** | Fibonacci **62% / 70.5% / 79%** retracement of the impulse leg that caused a BOS. | ICT-native: 0.62 / 0.705 / 0.79. Standard-fib camp: 0.618 / — / 0.786. **[DOC]** | 0.705 does not exist in Fibonacci theory; it is ICT-specific **[DOC]**. `profittown`'s implementation anchors the fib on `df['high'].max()` over **all history to date** rather than the impulse leg (fibonacci.py) **[CODE]** — a definitional error, not a bug. |
| **Judas swing** | A sweep occurring **00:00–05:00 New York**, of the Asian range or the midnight open, that closes back through the midnight open **[DOC]** | 00:00–05:00 NY | Deterministic given a timezone. **Untestable on this repo's feed** — the tick-derived M1 bars are missing the 00:00 UTC hour every day (DATA_QUALITY.md), which is 19:00–20:00 NY, but the daily-boundary contamination sits right where the Judas window's reference levels are built. |
| **turtle soup** | The original, from Connors & Raschke *Street Smarts* (1995): a new 20-day low where the **previous** 20-day low is **at least 4 sessions old**; enter on a buy stop back above that prior low; stop below the new extreme **[SNIPPET]** | 20 bars, 4-session age gate | **This is what SYSTEM A already is.** ICT relabelled it as the stop-run reversal. The one component the original has and this repo does not is the **age gate on the level being swept**. |

### 1.2 The three things the field genuinely agrees on

1. **A break is a sweep only if price closes back inside.** Every source, every implementation, no exceptions. It is also the only rule with a mechanism behind it (Osler, §4).
2. **Structure breaks on the close, not the wick.**
3. **FVG is `low[i] > high[i-2]`.** Zero lag, zero ambiguity, universal.

Everything else in the vocabulary is a convention with a default, not a standard.

---

## 2. HOW PRACTITIONERS COMBINE A DIRECTION FILTER WITH A LIQUIDITY ENTRY

This is the section the owner's thesis needs. His claim: *"M1 SuperTrend catches
every trend but LATE; SMC/ICT top-ticks the entry via liquidity."*

### 2.1 The standard sequence — there is essentially only one

Called the "ICT 2022 model", and every variant reduces to the same chain
**[SNIPPET, corroborated across ~8 independent pages]**:

```
1. HTF BIAS          Daily / 4H / 1H. Direction only. Without it the rest has no anchor.
2. LIQUIDITY SWEEP   Price runs a prior high/low AGAINST the intended direction.
                     (For a long: it sweeps a LOW first. "Judas swing".)
3. DISPLACEMENT      An impulsive move back the other way, leaving an imbalance.
4. MSS               That displacement CLOSES beyond the most recent LTF swing
                     in the bias direction. This is the confirmation.
5. FVG / OB ENTRY    Limit in the imbalance the displacement left behind.
                     Stop below the sweep extreme. Target = the opposing liquidity.
```

The timeframe convention is **HTF bias (1H–D) → sweep on 15m → MSS on 5m/3m/1m →
FVG entry on 1m** **[SNIPPET]**.

### 2.2 What this repo's E-127 architecture is, in that vocabulary

| ICT step | E-127 does | notes |
|---|---|---|
| 1. HTF bias | **M1 SuperTrend(7,1.2) direction** | Not a higher timeframe at all. Same-TF trend state. |
| 2. sweep | limit at `pivot − side·0.50·ATR(14,M1)`, filled by the probe | **Fills on the sweep AND on the run.** No close-back-inside test anywhere. |
| 3. displacement | — | **absent** |
| 4. MSS | — | **absent** |
| 5. entry | the limit itself, at the extreme | This is the *aggressive* variant. |

So the current system implements steps 1, 2 and 5, with step 2 in its
undiscriminated form. **Steps 3 and 4 are the entire content of what the
literature says separates a sweep from a run** — and E-122 measured exactly the
symptom that predicts: MFE/|MAE| = **0.96** over 240 bars after the fill. The
trade goes as far against as for. That is the arithmetic signature of a
population containing both sweeps and runs, undiscriminated.

Two independent facts point the same way, and this is the strongest single
finding in this document.

### 2.3 The entry-timing question, as practitioners argue it

Three positions, all documented **[SNIPPET]**:

| position | rule | claimed cost |
|---|---|---|
| **aggressive** | limit resting in the OB/FVG, filled by the sweep. Best price. | takes every failed sweep at full size |
| **conservative** | wait for the LTF MSS, then enter on the retrace into the FVG the displacement left | misses the moves that never retrace |
| **middle** | enter at the FVG's near edge rather than deep inside | "if price only taps the FVG edge and runs, aggressive far-edge entries miss" |

The stated community consensus favours confirmation **[SNIPPET]**, with the
explicit rationale that *"the sweep alone is not the entry — the lower-timeframe
MSS is the trigger that filters out failed sweeps."*

**This is a direct, testable contradiction with this repo's E-076/E-077**, which
measured the sweep CLOSE at −0.003R and found the resting limit filled by the
sweep to be 3.5× the expectancy of the retest entry. Both cannot be right in the
same conditions. The most likely resolution — and it is a hypothesis, not a
finding — is that the two are measuring different things: E-077 compared the
limit against a **retest of the same level**, whereas practitioners compare it
against **waiting for a structure break and entering the NEW imbalance**, which
is a different level entirely. **That cell has never been run here.**

### 2.4 Documented failure modes of the sequence

| # | failure mode | source | already seen here? |
|---|---|---|---|
| 1 | **Trend day: the level runs and does not reverse.** The sweep "fails" and price keeps going. | **[SNIPPET]** | Yes — E-122's symmetric MFE/MAE is this population. |
| 2 | **Range day: all four conditions print, neither side follows through.** | **[SNIPPET]** | Yes — E-125's chop split (choppy days 2.0 pts vs 11.0 for all). |
| 3 | **MSS without a prior sweep is a weak signal** — "should be smaller size or passed entirely". | **[SNIPPET]** | Untested here. |
| 4 | **Deeper sweep**: the setup invalidates if price returns through the sweep level; either liquidity was not exhausted or a larger sweep is in progress. | **[SNIPPET]** | Untested. This is a stop-placement rule, and E-127 uses a fixed 4.0·ATR stop instead. |
| 5 | **Entering the OB before the sweep** — the most-cited beginner error. | **[SNIPPET]** | N/A — E-077 already established the limit must be INSIDE, past the level. |
| 6 | **Real-time swing points repaint.** "Any real-time implementation must account for this lookahead bias." | **[DOC]** | Handled — E-119's zones are known only k bars late by construction. |

---

## 3. GITHUB IMPLEMENTATIONS REVIEWED

Five artefacts read as source. **The GitHub SMC ecosystem is far thinner than
its popularity suggests**: a repository search for `smart money concepts trading
ICT` with `stars:>15` returns **exactly two repositories**. One of them is a
shell.

### 3.1 `joshyattridge/smart-money-concepts` — the de-facto Python standard
- 1,976★, 847 forks, **MIT**, `smartmoneyconcepts/smc.py`, 987 lines, read in full **[CODE]**
- Computes: `fvg`, `swing_highs_lows`, `bos_choch`, `ob`, `liquidity`, `previous_high_low`, `sessions`, `retracements`

**Defects found, in severity order:**

1. **`bos_choch` stamps the signal two swings in the past.** `bos[last_positions[-2]] = 1` (smc.py:258). The 4-swing pattern is only recognised when the 4th swing confirms, and the flag is then written to the index of the 2nd-to-last swing. A naive `df[df.BOS==1]` at bar `i` is reading a decision that could not be made until many bars after `i`.
2. **`bos_choch` deletes signals using the future.** Lines 340-353: any BOS/CHoCH that is never subsequently broken is set to zero, and any earlier one whose break came after a later one's is also erased. **A signal's existence depends on what happens after it.** This is the single most dangerous defect in the file.
3. **`liquidity` uses a global constant computed from the whole dataset.** `pip_range = (ohlc["high"].max() - ohlc["low"].min()) * range_percent` (smc.py:595). On 2018 H1 gold (1275–1366) that is 0.91 points at the default — about 3.7× the measured M1 ATR of 0.246.
4. **`liquidity` marks the pool at the FIRST pivot's index** and fills `Swept` from a forward scan (smc.py:641-651). Knowable only in retrospect.
5. **`swing_highs_lows` force-writes the first and last elements of the array** based on the last pivot in the dataset (smc.py:194-201). The end of the series depends on where the series ends.
6. **`fvg` is stamped at the middle bar** via `shift(-1)` (smc.py:74-82) — one bar of look-ahead if the series is used positionally.
7. `swing_length` is silently doubled (smc.py:151).

**Independent corroboration:** issue **#101, "Look-ahead bias in swing_highs_lows() — backtest results are inflated"**, opened 2026-04-01, still **open**; and #34 "Lockaheaad methods", open since 2024-05-12. (Issue bodies were not readable from this session — GitHub issue access is scoped to `veer7710/signals` — but the titles and open state came back from search.)

**Verdict:** the definitions are worth reading; **the outputs must never be indexed positionally in a backtest.** Every function that returns an event at a bar index returns it at an index earlier than the bar where it became knowable. If any experiment in this repo ever used this package, its result is void.

### 3.2 LuxAlgo — `Smart Money Concepts (SMC) [LuxAlgo]`, Pine v5
- 847 lines. Obtained from the mirror `deepentropy/lightweight-charts-indicators`, `docs/official/indicators_community/` **[CODE]**
- **Licence: CC BY-NC-SA 4.0.** *Non-commercial, share-alike.* The ideas are free; **the code is not usable in a commercial trading product**, and any derivative must carry the same licence. Reimplement from the spec, do not copy.
- The most-installed SMC indicator on TradingView; its defaults are the field's de-facto standards.

**Defaults extracted (these are the numbers everyone else copies):**
```
swingsLengthInput            50      internal structure length      5
equalHighsLowsLengthInput     3      (bars confirmation)
equalHighsLowsThresholdInput  0.1    × ATR(200)
orderBlock high-vol filter    (high-low) >= 2 × ATR(200)  -> swap high/low
internal/swing OB count       5 each, cap 100 stored
FVG threshold (auto)          middle-candle body % move > 2 × cumulative mean |body % move|
premium zone                  top 5% of [last swing low, last swing high]
equilibrium                   midpoint ± 2.5%
discount zone                 bottom 5%
```

**Defects found:**
1. **Genuine look-ahead in the FVG when a higher timeframe is selected.** `request.security(..., [close[1], open[1], time[1], high[0], low[0], time[0], high[2], low[2]], lookahead = barmerge.lookahead_on)` (lux_smc.pine:635). The `[1]` and `[2]` offsets are the safe idiom; **`high[0]`/`low[0]` with `lookahead_on` are not** — on an HTF they return the completed HTF bar's extremes before that bar has completed. Harmless on the chart timeframe (the default), a real future leak the moment `fairValueGapsTimeframeInput` is set. This is exactly the trap most users walk into, because "FVG on a higher timeframe" is the headline use.
2. `barDeltaPercent = (lastClose - lastOpen) / (lastOpen * 100)` (:637, threshold at :639) — divides by `open × 100` instead of multiplying the ratio by 100. Self-consistent with the threshold (both sides are scaled the same way) so it does not change behaviour, but the displayed/derived quantity is 1/10000 of a percent, not a percent.
3. Premium/discount at 5% bands (:756-761) contradicts the universal 50% definition. Not a bug — an undocumented redefinition of a standard term inside the most popular implementation of it.
4. Structure and OB detection are **causal and correct**: `ta.crossover(close, pivot.currentLevel)` with a one-shot `crossed` flag, and `storeOrdeBlock` slices only `[pivot.barIndex, bar_index)`. No look-ahead. Credit where due.

### 3.3 `Simon-Dev-Ops/ICT_Validated_SMC-Project` — `ICT_Validated_SMC_v1.6.pine`
- 2,014 lines, **Mozilla Public License 2.0** (declared in the header; there is no LICENSE file in the repo — a 404). MPL-2.0 is file-level copyleft and **is** commercially usable, unlike LuxAlgo's.
- The most complete single-file implementation I found: swings, internal structure, HTF structure, OB with a scoring gate, breakers, FVG with a displacement filter, IFVG, BPR, EQH/EQL, sweeps, **inducement**, premium/discount, PDH/PDL/PWH/PWL, killzones.

**What it computes that nothing else does:**
- **Inducement, coded** (:751-830). Internal pivots (`internalLen=5`) become IDM levels only while the swing structure (`swingLen=10`) points the other way; they expire the instant the swing trend flips; triggered by `low < idm.price and close > idm.price`.
- **OB quality as an additive score** (:1094-1108): sweep +2, displacement +2, killzone +1, correct P/D zone +1, HTF aligned +2, gate at `minScore`.
- **Sweep with the strict close-back-inside rule** (:1394-1410), optionally requiring the previous bar to have had a rejection wick `> max(prevBody, ATR × 0.1)`.

**Defects found:** I looked hard and found **none of the look-ahead class.**
- `request.security` at :294-295 uses `lookahead_on` with `high[1]`/`low[1]` — that is the *correct* non-repainting idiom for previous-day/week levels, not a defect.
- HTF structure at :366 uses `lookahead_off`.
- OBs are only created when `latest.idx == bar_index - swingLen`, i.e. at the correct confirmation lag.
- The FVG uses `atrVal[1]` and bar `i-1` as the middle candle. Causal.
- Its own header documents that v1.5 fixed negative-array-index crashes and v1.4 fixed an **inverted displacement direction check in OB validation** — i.e. it shipped for some time with the bullish/bearish displacement test backwards. Read the version notes before trusting any single version.
- The OB zone is the **full high–low**, not the body, contradicting the consensus it claims to implement.

### 3.4 `manuelinfosec/profittown-sniper-smc` — a cautionary data point
- 74★, 25 forks, **no licence file**. Python.
- `internal/core/trade_engine.py`, `internal/core/market_scanner.py`, `internal/engines/day_trader.py`, `internal/engines/swing_trader.py` are all **0 bytes**. The bot does not exist. **[CODE]**
- What does exist (`shared/rules/*.py`) is a crude but honest reference for the sequence:
  - `detect_bos`: `close > max(high[-21:-1])` — a Donchian break, not a swing break.
  - `check_liquidity_sweep`: the candle immediately before the OB wicked below `min(low)` of the previous 10 bars. **No close-back-inside test.**
  - `find_order_block`: last opposing candle in `[-20:-1]`. No displacement requirement.
  - `check_fibonacci_zone`: OTE computed from `df['high'].max()` / `df['low'].min()` over **all history to date** instead of the impulse leg.
- **Relevance:** 74 stars and 25 forks for an empty repository with a README promising "$1k → $3k per day". That is the field's signal-to-noise ratio, and it is why star counts are not evidence.

### 3.5 `Kjaehr/MT5_EA_HOUSE` — `DAX_SmartMoneyConcepts.mq5`
- 562 lines, no licence declared **[CODE]**. Representative of the MQL5 tier (71 files match `"liquidity sweep" extension:mq5`; almost all are single-file EAs with no tests).
- **`DetectLiquiditySweeps` (:502-526) has no close condition.** It fires on `high[i] > level && high[i-1] <= level` — the first bar to touch the level. It is a breakout alert labelled "Liquidity Sweep — Potential reversal". Anyone building on the MQL5 corpus should assume this class of error until they read the code.

### 3.6 `SlimWojak/research_accelerator` — an independent research corpus
- ~9,800 lines of ICT primitive research across 16 markdown files, MIT-ish/unlicensed, read in full for `research_tier2_primitives.md` (1,086 lines), `sanity_band_results.md` (367), `RG1_IFVG_DEEP_RESEARCH.md`, `RG2_BPR_DEEP_RESEARCH.md`, `RG5_DISPLACEMENT_RESEARCH.md` **[DOC]**
- It is another AI-assisted research pack (dated 2026-03), so its *citations* are unverified — but its **empirical counts are measured** on 7,177 bars of EURUSD 1m and are the most useful thing in it. §5 below uses them.
- Its own headline conclusions, for the record: all six Tier-2 primitives are "PARTIALLY deterministic"; MMXM cannot be classified in real time and should be used only for retrospective labelling; and Volume Imbalance must be removed as a primitive because it floods at 765 detections/day.

---

## 4. EVIDENCE, IN THREE TIERS

The owner's belief is that these strategies "work and are widely used". Widely
used is true and not in dispute. **Works** has three very different kinds of
support, and they must not be blended.

### TIER C — reproducible or peer-reviewed. The strongest evidence, and it is NOT about ICT.

**C1. Osler (2003), "Currency Orders and Exchange Rate Dynamics", *Journal of Finance* 58(5):1791-1819. [SNIPPET]**
The complete order book of the Royal Bank of Scotland, 1 Aug 1999 – 11 Apr 2000:
**9,655 orders, >$55bn face value**, USD/JPY, GBP/USD, EUR/USD. Findings:
- **Take-profit orders cluster at round numbers** → prices reverse at support and resistance.
- **Stop-loss orders cluster JUST BEYOND round numbers** → trends accelerate once such a level is crossed.
- ~**10%** of all stop and take-profit orders sit at rates ending in `00`.

**C2. Osler (2005), "Stop-loss orders and price cascades in currency markets", *JIMF* 24(2):219-241. [SNIPPET]** Same data. Stop-loss sell orders cluster **just below** round numbers, buy stops **just above**; the price response to a stop cluster is **larger and longer-lasting** than the response to a take-profit cluster.

**C3. Kavajecz & Odders-White (2004), "Technical Analysis and Liquidity Provision", *Review of Financial Studies* 17(4):1043-1071. [SNIPPET]** Support and resistance levels **coincide with peaks in depth on the limit order book**; moving-average signals reveal information about where that depth sits. Their framing is the important part: technical analysis has value **because it locates liquidity already resting on the book**, which is consistent with market efficiency.

**What C1–C3 do and do not support.** They are the *mechanism* behind the
liquidity thesis, from real order books, peer-reviewed, in FX. They establish
that stops cluster in predictable places and that price behaves differently when
those places are reached. **They say nothing about whether a retail trader can
extract money from it after spread.** Osler's own framing is that the clustering
*explains* the folk observations, not that it is tradeable.

**Note the direction, carefully.** Osler's stop-cluster result predicts
**acceleration through** the level, not reversal at it. The ICT reading — sweep
then reverse — is the *opposite* of the documented cascade. Both can be true at
different horizons, but nobody should cite Osler as support for the reversal
trade without acknowledging that the paper's headline finding is continuation.

**C4. StatOasis, "I Backtested ICT / Smart Money Concepts — What Survives". [SNIPPET, page blocked; methodology and numbers from search index]**
This is the first systematic public test of ICT rules with a stated methodology,
and `DEFINITIONS.md` §D2/§F4's "no test found, ours or anyone's" is now out of date.
- **Method:** daily OHLCV, SPY (1993+), QQQ (1999+), DIA (1998+), IWM (2000+). Layer 1: forward-return edge (event mean − all-bar baseline) at 1/2/3/5/10/20 days, two-sample t at 5 and 10 days. Layer 2: 7 entry families (4 ICT + 3 textbook) × parameter grids (54/54/9/18/9/9/9) × time exits {5,10,20} × 4 markets = **648 backtests**, flat-only, next-open fills, vs a coin flip and buy-and-hold.
- **Results:** *no* ICT concept reached significance. Best was **order blocks on SPY, t = +1.22**. **Liquidity sweep: +0.119% 5-day edge on SPY, 547 events, t = +0.94**; DIA +0.143%, t = +1.09. **OTE was the worst: −0.028%, t = −0.17, beating the random baseline in 0.0% of variants.** **0 of 648 backtests beat buying and holding the index.**
- **Scope limits that matter here, and they are large:** daily bars, US equity index ETFs, 5-day forward horizons, long-biased instruments in a secular uptrend. That is about as far from *intraday M1 gold with a 4·ATR stop and a volatility trail* as a test can be while still being about the same words. **It is evidence that the concepts carry no edge as daily equity-index signals. It is not evidence about M1 XAUUSD.** But it is the only real test that exists, it is negative, and it converges with this repo's own E-100 (26 declared cells, not one reaching t=2.0).

**C5. This repository.** E-100's 26 declared cells; E-104's random-bar control column showing prior swing pivots sit within 1 ATR of **67% of random bars**; E-121's time-shifted control at 20–22 se; E-128's 79.2 se. These are the most rigorously controlled tests of these concepts I found anywhere, including the published ones. That is not a compliment to this repo so much as an indictment of the field.

### TIER B — a shown result with no reproducible methodology

- "Backtests of rule-based SMC entries (e.g. on DXY) report **50–65% win rates with profit factor above 1.5**" **[SNIPPET]** — no instrument list, no sample size, no cost model, no out-of-sample split.
- "I Backtested 2,600 Trades Using Smart Money Concepts" (Medium) **[SNIPPET]** — a count, and a claim that SMC "consistently outperformed"; no methodology.
- "1-minute breaks fail **68–72%** of the time, daily breaks 40–45%, close-back-inside definition, five-bar re-entry window; **XAUUSD fakes out ~62% intraday** vs NQ ~54%, EURUSD ~58%, CME BTC ~65%" **[SNIPPET]** — precise-sounding, entirely unsourced, no dataset named. **If it were true it would be the single most useful number in this document**, which is exactly why it should not be believed without reproduction. It is cheap to measure directly on the 157,051 M1 bars already built (see H-1).
- The `research_accelerator` corpus **[DOC]** — its measured densities are usable; its sourced claims are second-hand.
- Prop-firm statistics: "**7% of traders who buy a challenge ever receive a payout**" (FPFX Technologies, 300,000+ accounts) **[SNIPPET]**; "fewer than 15% of prop traders are consistently profitable over a full year" **[SNIPPET]**. FTMO publishes payout totals (>$450m) but **has never published a pass rate** **[SNIPPET]**. Relevant as a base rate, not as evidence about any strategy.

### TIER A — social-media claims

The bulk of the corpus. Educational sites, YouTube transcripts, prop-firm blogs,
indicator marketing. None reports a sample size, a cost assumption or an
out-of-sample split. Multiple pages state the honest version themselves: *"the
ICT rules have no peer-reviewed validation, the win rates are unsourced, and the
institutional narrative is an interpretation rather than a documented
mechanism"* **[SNIPPET]**.

### The honest summary of the evidence

| claim | grade |
|---|---|
| Stops cluster at and just beyond obvious levels, in real order books | **Tier C. Established.** |
| Technical levels locate depth already resting on the book | **Tier C. Established.** |
| Price reacts differently when a stop cluster is reached | **Tier C. Established.** The documented direction is *acceleration through*, not reversal. |
| ICT/SMC rules produce a tradeable edge | **Tier C evidence exists and is NEGATIVE** (648 backtests, daily equity ETFs). No positive Tier-C evidence found anywhere. |
| Specific win rates quoted for SMC | **Tier A/B. Unsourced. Do not repeat them.** |

**The mechanism is real and the strategy is unproven.** That is the same
conclusion this repository reached from its own data (E-121: levels carry
enormous structural information; E-122: converting it is the unsolved problem),
arrived at independently. The external literature does not rescue the
conversion problem — it has not solved it either.

---

## 5. WHAT WE ARE MISSING — RANKED TESTABLE HYPOTHESES

Each is stated as a rule with thresholds, on top of **SYSTEM A as it now stands**
(E-127: M1 pivot k=5 zones, SuperTrend(7,1.2) direction filter, limit at
`pivot − side·0.50·ATR(14,M1)`, stop 4.0·ATR, ST band trail, 981 trades).

Ranking is by *(strength of external support) × (cheapness to test) ÷ (number of
new parameters)*. The mandate's §14 test applies to every one of them: **a filter
earns its place only if the trades it REFUSES are worse than the ones it allows**,
and the answer is in POINTS, not R.

---

### H-1 — **THE CLOSE-BACK-INSIDE TEST. Separate the sweep from the run.**
**Rank 1. This is the one.**

Every source in the field agrees a break is a sweep only if price closes back
inside. **SYSTEM A does not test this anywhere.** Its limit fills identically on
a sweep and on a breakout, and E-122 measured the exact consequence:
MFE/|MAE| = 0.96.

```
Let  L   = the zone pivot price
     s   = +1 for a buy at a swing low, -1 for a sell at a swing high
     t   = the M1 bar on which the limit filled

RULE:  the fill is a SWEEP iff, within N bars of t,
           some bar j in [t, t+N] has  s · (close[j] - L) > 0
       i.e. price closed back on the correct side of the level.
       Otherwise it is a RUN.

GRID:  N ∈ {0, 1, 2, 3, 5}      (N=0 = the strict same-bar rule)
```
Three separate measurements, in this order, and the first is not a strategy:
1. **Conditional split, no trading.** Points/trade and MFE/|MAE| for SWEEP vs RUN. If the field's central claim is true here, RUN's MFE/|MAE| is materially below 1 and SWEEP's materially above.
2. **As a refusal filter**: cut RUN trades. §14 test — are the refused trades worse?
3. **As a flip**: on a RUN, reverse. (This is the honest steelman: if the level is a genuine breakout, the ICT reading of your own position is that you are on the wrong side.)

**Why rank 1:** zero new indicators, one integer parameter, it is the single
most-agreed rule in the entire literature, and this repo's own E-122 number is
the predicted symptom of not having it. It also directly measures the
unsourced Tier-B claim "1-minute breaks fail 68-72% of the time; XAUUSD ~62%" on
data we already have — turning a Tier-B rumour into a Tier-C fact for one run.

**Cost of being wrong:** low. If SWEEP and RUN are indistinguishable, that is a
publishable negative and it kills the "sweep" framing of the whole system.

---

### H-2 — **INDUCEMENT: a two-scale pivot hierarchy as level SELECTION.**
**Rank 2.**

E-104 diagnosed the largest miss category as **level SELECTION**, not level
existence, and E-104 also showed a prior swing pivot sits within 1 ATR of **67%
of random bars** — pivots as such carry no information about turns. Inducement
is the literature's answer to exactly that question, it is precisely codeable,
and it is not in `DEFINITIONS.md` as an implemented rule.

```
Two pivot scales on M1:
    INTERNAL  k_i = 5      (what SYSTEM A already uses)
    SWING     k_s = 15     (structural; grid k_s ∈ {10, 15, 20})

STRUCTURE STATE (causal, from confirmed k_s pivots only):
    swingBullish = the last confirmed k_s pivot sequence made a higher high
                   and a higher low   (equivalently: last BOS was bullish)

RULE (the IDM filter):
    Arm a BUY limit at an internal swing LOW  only while swingBullish.
    Arm a SELL limit at an internal swing HIGH only while not swingBullish.
    Do not arm a zone whose price is within 0.10 · ATR(14,M1) of the
    governing k_s swing extreme itself  (that is the swing, not the inducement).
    EXPIRE the armed zone the moment the k_s structure state flips.
```
This is a **direct competitor to the SuperTrend direction filter**, testing the
same idea with structure instead of an indicator. E-127 showed the ST filter
doubles the result at M1 (48.4 → 97.1) and does nothing at M5/M15. The question
this answers is whether that gain is about *trend* or about *structural
alignment* — and whether the two are additive.

**Report all four cells**: neither filter / ST only / IDM only / both. The
plateau structure matters more than the peak.

**External support:** `ICT_Validated_SMC_v1.6.pine`:751-830 is a working
reference implementation **[CODE]**. The "never take the first pullback after a
BOS, wait for it to be swept" rule is one of the most repeated in ICT
**[SNIPPET]**.

---

### H-3 — **POST-FILL DISPLACEMENT as the confirmation E-123 never tested.**
**Rank 3.**

E-123/124 tested **eight discriminators computable AT THE FILL** and only the
rejection wick weakly survived; E-126 then dropped even that once the trail was
in. Every discriminator tried was simultaneous with the fill. **Displacement is a
discriminator computable one to three bars AFTER the fill**, and it is the single
most consistently quantified threshold in the practitioner literature.

```
At M1, for bars j = t+1 .. t+3 after the fill:
    body   = |close[j] - open[j]|
    range  = high[j] - low[j]
    DISPLACEMENT(j)  iff   body >= 1.5 · ATR(14,M1)
                     and   body / range >= 0.65
                     and   sign(close[j]-open[j]) == s

RULE A (confirmation):  if no DISPLACEMENT bar in [t+1, t+3], exit at market
                        at the close of t+3. Otherwise hold, ST trail as now.
RULE B (sizing):        hold everything; report the split.

GRID: ATR multiple m ∈ {1.0, 1.2, 1.5, 2.0};  body ratio r ∈ {0.55, 0.65, 0.75}
      window W ∈ {1, 2, 3}
```
**Watch for the E-074 trap.** A confirmation filter that raises expectancy while
banking fewer points is a *worse* system. Report points first. And **12 grid
cells plus H-1's 5 = an honest t bar near 3.0, not 2.0** — declare the count.

**External support:** `m=1.5, r=0.65` is the modal community default; Zeiierman
uses `m=1.2` **[DOC]**. Note the volume leg of Zeiierman's criteria
(`vol >= 1.5 ×` 20-bar mean) is **untestable on this feed** — DATA_QUALITY.md
records that both volume columns are identically zero. Say so in the writeup
rather than silently dropping it.

---

### H-4 — **AGE AND VIRGINITY OF THE SWEPT LEVEL — the turtle-soup gate.**
**Rank 4.**

The original Connors–Raschke rule that ICT dropped when it renamed the pattern:
*the previous 20-day low must be **at least four sessions old*** **[SNIPPET]**.
The intuition is that stops need time to accumulate. This repo has tested
`arm_life` (how long a zone stays armed) but has **never tested the age of the
level at the moment it is swept**, nor how many times it has been touched.

```
For each armed zone at price L, created at M1 bar c, filled at bar t:
    AGE     = t - c                     (bars the level has rested)
    TOUCHES = #{ j in (c, t) : |low[j] - L| <= 0.10·ATR  }  (for a buy zone)
    VIRGIN  = (TOUCHES == 0)

RULES to test independently:
    (a) AGE >= A            A ∈ {30, 60, 120, 240} M1 bars
    (b) VIRGIN only         (untested level)
    (c) TOUCHES >= 2        (the opposite hypothesis: repeatedly defended)
```
**(b) and (c) are opposite predictions and both are folklore.** That is the
point: run them together and let one of them die. `arm_life` already answered
the related question in the *unexpected* direction (E-104: unconstrained is
best), so the prior here should be weak.

Cost: two integers, no new indicator, computable from data already in memory.

---

### H-5 — **PREMIUM / DISCOUNT, tested with the CANONICAL definition.**
**Rank 5.**

Premium/discount has already failed in this repo — but **the field contains two
incompatible definitions of it**, and the most popular implementation uses the
non-canonical one. Before writing it off, run the canonical form once.

```
DEALING RANGE: [ lastSwingLow, lastSwingHigh ] from confirmed k=15 M1 pivots
               (or the M5/M15 pivots — declare which, do not test both silently)
EQ = 0.5 · (lastSwingHigh + lastSwingLow)

CANONICAL RULE:  arm BUY  zones only where  L <  EQ   (discount)
                 arm SELL zones only where  L >  EQ   (premium)

LUXALGO RULE (the other one, for contrast):
                 arm BUY  only where L <= 0.95·low + 0.05·high  (bottom 5%)
                 arm SELL only where L >= 0.95·high + 0.05·low  (top 5%)
```
Two cells, no new parameters beyond the pivot scale. Its value is mostly
**epistemic**: it closes a definitional loophole that would otherwise let anyone
re-open the question later. If both fail, premium/discount is dead here and can
be recorded as such with the definition named.

---

### H-6 — **INVERTED FVG with the canonical close-through trigger.**
**Rank 6.**

E-079 rejected inverse FVG at **n=1333 on 1h gold** — a rate that is not
consistent with the canonical trigger. The canonical rule is a **full close
beyond the FAR boundary**:

```
A bullish FVG  [bot = high[i-2], top = low[i]]  becomes a BEARISH iFVG
    at the first bar j > i with  close[j] < bot.        (NOT a wick)
Mirror for bearish.
The flipped zone is the ENTIRE original box, unchanged. Its CE is the 50%.
The iFVG dies when a close returns fully inside the original zone.
```
Retest as a **level source for the existing sweep entry** (an iFVG boundary is a
zone), not as a standalone trigger — standalone triggers have failed here
repeatedly and the field's own test (StatOasis) found nothing either. Expect
n to fall by an order of magnitude. **If n does not fall by roughly 10×, the
trigger is still wrong** — that is the sanity check on the run itself.

**External support:** seven independent sources in the close-based camp vs two
in the wick-based camp **[DOC]**.

---

### H-7 — **THE LUXALGO PIVOT: a one-sided leg detector instead of a symmetric fractal.**
**Rank 7. Cheap, and nobody has noticed it.**

LuxAlgo's `leg()` is **not** a symmetric fractal, and every SMC user who thinks
they are using "the standard swing" and is using LuxAlgo is using this instead:

```
Maintain state  leg ∈ {BULLISH, BEARISH}, and per bar i:
    newLegHigh = high[i-K] > max(high[i-K+1 .. i])
    newLegLow  = low[i-K]  < min(low[i-K+1  .. i])
    if newLegHigh: leg := BEARISH
    elif newLegLow: leg := BULLISH
    A pivot is emitted ONLY on a change of leg, at price high[i-K] / low[i-K].
```
Same K-bar confirmation lag as the current detector, **no left-side condition**,
and alternation is free. On M1 that should produce materially fewer and more
structural levels than a symmetric k=5 fractal. Drop-in replacement for the zone
generator; change nothing else; compare points and trades/day.

Related and equally cheap: **zigzag normalisation** (smc.py:165-190) — collapse
consecutive same-type fractal pivots keeping the extreme one, iterate to fixpoint.
Reduces M1 flooding without lengthening the lag.

**Calibration target from independent data [DOC]:** on 7,177 bars of EURUSD 1m,
a symmetric fractal produces **242 swings/day at K=3, 148 at K=5, 77 at K=10,
39 at K=20**. The research pack's conclusion is that *"N=10 is near the minimum
meaningful setting; N=15–20 is preferred for true structural swing
identification"* on 1-minute data. **SYSTEM A uses K=5.** That is not proof it is
wrong — E-128's plateau is real evidence and this is one week of a different
instrument — but it is a specific, cheap, externally-motivated direction to
extend the existing K grid: **run K ∈ {5, 10, 15, 20} on M1 and report the
plateau, not the peak.**

---

### H-8 — **EQUAL HIGHS / LOWS as a zone-QUALITY filter rather than a trigger.**
**Rank 8. Low prior — include it to close the question.**

E-100 tested BSL/SSL pools as **triggers** and they failed (best cell t=+0.34).
E-104 measured them as **locators** and found 30% at missed turns vs 28% at
random bars — **zero information**. Its `tol_atr = 0.10` with ATR(14) and pivot 5
is close enough to LuxAlgo's `0.10 × ATR(200)` with pivot 3 that I do not think
the tolerance was the problem.

The one untested framing: **as a filter on the zones SYSTEM A already trades.**
```
A zone at L is a POOL zone iff at least one other confirmed same-type pivot
    within the preceding 200 M1 bars satisfies  |p - L| <= 0.10 · ATR(200,M1)
Split the existing 981 trades into POOL and SINGLETON. Report points for both.
```
Zero new trades, zero new parameters, one pass over existing results. **Its value
is that it is nearly free and it retires a question the owner will otherwise keep
raising.** My honest expectation, given E-104's random-bar column, is that it
shows nothing.

---

### H-9 — **THE FULL 2022 MODEL (sweep → MSS → FVG retrace) as a separate system.**
**Rank 9. Expensive, and the external evidence is against it.**

The conservative-entry branch of §2.3 — enter the FVG left by the displacement
that broke structure, not the sweep extreme. This is the cell §2.3 identifies as
never having been run here, and it is the field's consensus model.

```
1. SWEEP at bar t of a confirmed M1 pivot (H-1's rule, N<=2)
2. MSS: within 20 M1 bars of t, close beyond the most recent opposite
   internal pivot (k=5), in the direction away from the sweep
3. DISPLACEMENT on the MSS bar (H-3's thresholds)
4. FVG: the 3-bar imbalance left by that displacement
5. ENTRY: limit at the FVG's near edge (grid: near edge / CE 50% / far edge)
6. STOP: beyond the sweep extreme, not a fixed ATR multiple
7. TRAIL: unchanged, M1 SuperTrend band
```
**Rank 9 not because it is wrong but because of what it costs.** It introduces at
least five new parameters, it is the sequence StatOasis found no edge in (t=+0.94
for sweeps, t=+1.22 for order blocks, 0 of 648 beating buy-and-hold), and it will
cut n hard — a four-condition chain at M1 on 109 days may not leave enough trades
to say anything. **Do H-1 and H-3 first**: they are the same idea decomposed into
two independently measurable pieces, on the existing trade population, at a
fraction of the cost. If both pay, H-9 is the assembly. If H-1 shows sweep and
run are indistinguishable, H-9 cannot work and should not be built.

---

### Explicitly NOT recommended

| idea | why not |
|---|---|
| **Any use of `smartmoneyconcepts` (pip package)** | §3.1. Its event indices precede the bars where the events become knowable, and `bos_choch` deletes signals based on the future. Read it, never call it. |
| **Copying LuxAlgo's Pine** | CC BY-NC-SA 4.0 — non-commercial, share-alike. Reimplement from the spec. |
| **Killzones / session gating** | The feed has zero bars at 00:00 UTC daily and 199 gaps of exactly 61 minutes (DATA_QUALITY.md). Session studies on this feed are contaminated at the daily boundary. E-094's six sideways detectors and 15m session tests already failed. Not until the feed is fixed. |
| **Anything volume-based** (Zeiierman's `vol >= 1.5×`, LuxAlgo's OB volume scoring, "volume spike confirms the sweep") | Both volume columns in the tick feed are identically zero. **Untestable here.** State it; do not approximate volume with tick count without saying so. |
| **MMXM / Power of 3 / market-maker models** | The independent research corpus concludes real-time phase classification is "near NO" — it is a retrospective label composed of every other primitive **[DOC]**. Unfalsifiable as usually stated. |
| **Optimal Trade Entry (62–79% fib)** | The single worst performer in the only systematic public test: −0.028% edge, t = −0.17, beat the random baseline in **0.0%** of variants **[SNIPPET]**. Converges with this repo's own rejection of fixed-R geometry (E-122). |
| **Chasing published SMC win rates** | Every number in Tier B is unsourced. Do not put any of them in a document that also contains measured numbers. |

---

## 6. THE ONE-PARAGRAPH ANSWER TO "WHAT ARE WE MISSING?"

**A test of whether the sweep was a sweep.** SYSTEM A rests a limit where stops
sit and gets filled by whatever comes through — a reversal or a breakout,
identically. The entire external literature, in every source and every
implementation, distinguishes these two by one rule: *did price close back
inside?* This repo has never applied it, and E-122's MFE/|MAE| = 0.96 is exactly
what a mixed, undiscriminated population looks like. Everything else in the
ranked list — inducement, displacement, level age, the 2022 model — is a
refinement of the same missing idea: **the zone tells you WHERE, and nothing in
the current system tells you WHETHER.** The academic record (Osler, Kavajecz &
Odders-White) supports the WHERE strongly and from real order books, and offers
no support at all for the WHETHER — in fact Osler's documented direction at a
stop cluster is *acceleration through it*. The only systematic public test of the
WHETHER (StatOasis, 648 backtests) is negative. Test H-1 first, expect it to
fail, and be pleased either way: a clean negative retires the sweep framing, and
a clean positive is the first thing in this project that the outside world has
independently predicted in advance.

---

## APPENDIX — ARTEFACTS READ, WITH LICENCES

| artefact | tier | licence | commercially usable? |
|---|---|---|---|
| `joshyattridge/smart-money-concepts` `smc.py`, 987 lines | [CODE] | **MIT** | yes — but see §3.1, do not use |
| LuxAlgo `Smart Money Concepts (SMC)`, Pine v5, 847 lines (via `deepentropy/lightweight-charts-indicators`) | [CODE] | **CC BY-NC-SA 4.0** | **NO — non-commercial + share-alike** |
| `Simon-Dev-Ops/ICT_Validated_SMC-Project` `ICT_Validated_SMC_v1.6.pine`, 2014 lines | [CODE] | **MPL-2.0** (header; no LICENSE file in repo) | yes, file-level copyleft |
| `manuelinfosec/profittown-sniper-smc` (`shared/rules/*.py`; core files 0 bytes) | [CODE] | **none declared** | no — all rights reserved by default |
| `Kjaehr/MT5_EA_HOUSE` `DAX_SmartMoneyConcepts.mq5`, 562 lines | [CODE] | none declared | no |
| `SlimWojak/research_accelerator` `research/*.md`, ~9,800 lines | [DOC] | none declared | text, not code |

**Primary literature referenced (all [SNIPPET] — the PDFs are blocked at the proxy):**
- Osler, C.L. (2003). *Currency Orders and Exchange Rate Dynamics: An Explanation for the Predictive Success of Technical Analysis.* Journal of Finance 58(5), 1791-1819. https://onlinelibrary.wiley.com/doi/abs/10.1111/1540-6261.00588
- Osler, C.L. (2005). *Stop-loss orders and price cascades in currency markets.* Journal of International Money and Finance 24(2), 219-241. https://www.sciencedirect.com/science/article/abs/pii/S0261560604001147 · working paper: https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.pdf
- Kavajecz, K.A. & Odders-White, E.R. (2004). *Technical Analysis and Liquidity Provision.* Review of Financial Studies 17(4), 1043-1071. https://academic.oup.com/rfs/article-abstract/17/4/1043/1570736
- Connors, L. & Raschke, L.B. (1995). *Street Smarts.* — origin of Turtle Soup.
- StatOasis, *I Backtested ICT / Smart Money Concepts — What Survives.* https://statoasis.com/overfit/research/ict-backtest-what-survives
- LuxAlgo, *Smart Money Concepts (SMC).* https://www.tradingview.com/script/CnB3fSph-Smart-Money-Concepts-SMC-LuxAlgo/
- Zeiierman, *Liquidity Sweeps in Trading.* https://www.zeiierman.com/blog/liquidity-sweeps-in-trading/
- LuxAlgo Library concept pages (inducement, breaker block, premium & discount, liquidity sweep, turtle soup): https://www.luxalgo.com/library/
- innercircletrader.net tutorials (BOS, MSS, sweep vs run, IFVG, Judas swing, OTE).

**Also referenced, blocked, and therefore NOT read:** the GitHub issue bodies for
`smart-money-concepts` #101 and #34 (issue access in this session is scoped to
`veer7710/signals`); every tradingview.com script page; every luxalgo.com page;
the Osler and Kavajecz PDFs; statoasis.com; mql5.com articles. Titles, states and
summaries came from the search index. **Anything above marked [SNIPPET] should be
re-verified from a session with wider egress before it is relied on for a
decision.**

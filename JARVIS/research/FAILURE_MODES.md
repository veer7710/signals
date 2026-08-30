# FAILURE MODES DATABASE — intraday liquidity-sweep / market-structure on XAUUSD

Scope: M15 → M5 → M1 execution stack, XAUUSD, retail prop-firm funded accounts.
Research date: 2026-08-29. Author: JARVIS research session.

**Purpose.** This file is the answer to "why does it lose?", not "why does it win?".
Every design decision downstream should be traceable to a row in this table.

---

## HOW TO READ THIS FILE

**Confidence vocabulary (strict):**

| Tag | Meaning |
|---|---|
| **MEASURED** | A number exists. Either computed in this repo (marked `[ours]`) or published by an identified source with a stated sample. |
| **REPORTED** | Traders/practitioners consistently describe it; no number, or only vendor numbers. |
| **PLAUSIBLE** | Mechanism is coherent and mechanical, but nobody has tested it. |
| **FOLKLORE** | Widely repeated, no traceable evidence, and often an incentive behind the repetition. |

**Method note, stated up front.** The egress proxy in this container blocks arxiv,
SSRN, ScienceDirect, NY Fed, mql5 and most academic PDF hosts. I could not open
the primary papers. Numbers attributed to papers are second-hand from search
synthesis and are marked `[2nd-hand]`. Numbers marked `[ours]` I computed here
from committed data and can be reproduced by running the named script.

**New code written for this file** (both deterministic, offline, no fitting):
- `JARVIS/research/sweep_anatomy.py` — conditional sweep outcome frequencies
- `JARVIS/research/microstructure_facts.py` — baselines, cost/range, give-back, gaps
- `JARVIS/research/failure_probes.py` — sweeps vs baseline, M1 extrapolation, loss clustering

**Incentive warning.** Roughly 90% of search results on this topic are published by
brokers, prop firms, VPS vendors, indicator sellers or course sellers. Every one of
them profits from you trading more, on lower timeframes, with a funded account.
Where I use such a source I say so. No vendor win-rate claim is treated as evidence.

---

## THE SINGLE MOST IMPORTANT MEASUREMENT IN THIS FILE

I measured what actually happens after a liquidity sweep on gold, using a
**symmetric ±1×ATR14 barrier from the sweep bar's close, 24 bars forward**, and
compared it to **the instrument's own unconditional baseline** rather than to 0.500.
That baseline step matters: gold does not resolve a symmetric barrier 50/50.

```
BASELINE  P(price falls 1 ATR before rising 1 ATR) from a random bar close
  GOLD   1h   0.544   (n=13,286)   <- gold falls faster than it rises
  GOLD   15m  0.523   (n= 4,159)
  EURUSD 1h   0.500   (n=16,717)
  US500  1h   0.490   (n=13,138)
```

Against that baseline, the classic long setup — *swing low pierced, bar closes back
above it* — is a **continuation-down signal on gold, not a reversal signal**:

```
GOLD 1h   LOW swept + closed back above   n=1694  P(down first)=0.633  delta +8.9pp  z=+6.95
GOLD 15m  LOW swept + closed back above   n= 495  P(down first)=0.604  delta +8.1pp  z=+3.41
GOLD 1h   HIGH swept + closed back below  n=1346  P(down first)=0.555  delta +1.1pp  z=+0.75
GOLD 15m  HIGH swept + closed back below  n= 423  P(down first)=0.506  delta -1.7pp  z=-0.68
EURUSD 1h LOW swept + closed back above   n=1665  delta -1.5pp  z=-1.20   (nothing)
US500 1h  LOW swept + closed back above   n=1359  delta +1.1pp  z=+0.80   (nothing)
```

Read that carefully. **The long sweep setup on gold is significantly worse than
doing nothing, in the direction the retail literature says it should be better.**
The effect replicates across two timeframes on gold and is absent on EURUSD and
US500. It is exactly the sign Osler's stop-loss cascade result predicts, and it is
the opposite sign the retail "stop hunt reversal" narrative predicts.

It also explains E-003's split without needing to blame the implementation: shorts
+0.054R, longs −0.018R. The long side was fighting a measurable −8.9pp headwind.

**It also survives the regime split**, which is the test GX-04 says everything must
pass. Splitting the 1h sample into three date blocks and recomputing each block's own
baseline `[ours]`:

```
block                   own baseline   LOW-sweep-reclaim            HIGH-sweep-reclaim
A 2024-04 .. 2025-03      0.563        n=759  0.660  +9.7pp z=+5.04    +4.9pp z=+2.31
B 2025-04 .. 2025-12      0.544        n=535  0.613  +7.0pp z=+3.05    -4.4pp z=-1.64
C 2026-01 .. 2026-08      0.517        n=400  0.610  +9.3pp z=+3.54    -0.0pp z=-0.01
```

The long-side continuation effect is **+7 to +10pp in all three blocks, |z| > 3 in all
three** — through a grind, a parabola and a 29.7% crash. The short side replicates in
**zero of three** and changes sign. That asymmetry is itself the finding: the sweep
family has one direction with a persistent, wrong-signed effect and one direction with
nothing at all.

**And the "sophisticated" filters do not rescue it.** Every filter that improved the
number on 1h reversed sign on 15m (`failure_probes.py`, section A; full grid run
2026-08-29):

| Filter (short setup, reclaim) | GOLD 1h edge | GOLD 15m edge | replicates? |
|---|---|---|---|
| displacement bar > 1.5 ATR | **+6.6pp** (z=+2.46) | **−13.2pp** (z=−2.74) | NO — sign flip |
| with-trend (EMA50 vs EMA200) | +4.8pp (z=+2.61) | −8.3pp (z=−2.15) | NO — sign flip |
| 12:00–17:00 UTC | +5.7pp (z=+2.54) | −10.3pp (z=−2.10) | NO — sign flip |
| shallow pierce < 0.15 ATR | +5.0pp (z=+2.25) | +1.5pp (z=+0.35) | weak/no |
| 1st sweep vs nested (2nd+) | +0.3 vs +1.5pp | −2.0 vs −1.6pp | no difference either way |

Not one of the five "quality" filters holds its sign across timeframes. Four of them
cross zero with |z|>2 on **both** sides — which is the statistical signature of
re-slicing noise, not of finding structure. This is the direct answer to the
question "what separates the naive version from the sophisticated version": on the
data we hold, **nothing measurable does**. The sophistication is where the multiple
testing lives.

---

## SECTION 1 — WHY LIQUIDITY SWEEPS FAIL

| ID | Failure mode | Mechanism (why it happens) | Observable signature (measurable BEFORE it hurts) | Proposed rule/filter | How to test it | Confidence |
|---|---|---|---|---|---|---|
| LS-01 | **Stop cascade → continuation, not reversal** | Stop-loss orders cluster *just beyond* obvious levels. When hit they become market orders in the same direction, which is positive feedback. Osler 2005 finds the stop-loss response is *larger and longer-lasting* than the take-profit response. The reversal half of her result comes from take-profit clustering, a different order type at a different price. | On gold, P(down 1 ATR first) after a reclaimed low sweep is 0.633 vs baseline 0.544 `[ours]`. Live signature: sweep bar closes back inside but the NEXT bar makes a new extreme within 1–3 bars. | Do not take long sweep setups on gold at all until an out-of-sample dataset overturns this. Treat a reclaimed low sweep as a *short* continuation candidate instead. | Rerun `failure_probes.py` on 2+ years of M15 gold when available; require the −8.9pp to hold in ≥4 of 6 walk-forward folds and on a second symbol family. | **MEASURED** `[ours]` — and the strongest result in this file: 3/3 date blocks, +7.0 to +9.7pp, all |z|>3. Mechanism `[2nd-hand]` Osler 2005 |
| LS-02 | **Citing the wrong half of the evidence** | The retail narrative cites stop-hunting as authority for a fade trade, but the stop-hunt mechanism predicts continuation. The reversal evidence (take-profit clustering, ~3.4pp extra bounce frequency at round numbers) is a *different mechanism at a different price* and is far too small to pay costs. | A strategy document that names "stop hunt" as its mechanism but trades reversal. | Force every rule to name which order type creates the edge (TP cluster = fade; SL cluster = follow), then check the rule's direction matches. | Split the sweep population by whether the level is a round number (TP-cluster proxy) vs a swing extreme (SL-cluster proxy) and measure the two separately. | **MEASURED** (3.4pp figure `[2nd-hand]` Osler 2003) |
| LS-03 | **Drift/baseline confound — measuring against 0.500** | A symmetric barrier does not resolve 50/50 on a trending or skewed instrument. Gold's own baseline is 0.544 down-first. A rule scoring 0.52 "reversals" looks like edge and is actually −2.4pp. | Compare any conditional frequency with the unconditional one on the same bars. | Every conditional statistic in this project must be reported as a delta vs the instrument's own baseline, never vs 0.5. | Already implemented in `microstructure_facts.baseline()`. Make it a required output of any sweep study. | **MEASURED** `[ours]` |
| LS-04 | **The level was real information (genuine breakout)** | Some pierces are not liquidity events; the level failed because new information arrived. Ex-ante these look identical to a sweep on OHLC data alone. | Post-pierce: no reclaim, expanding range, continuation on the next bar. Ex-ante: nothing on OHLC. Requires order-flow or news to separate. | Do not attempt to separate these from OHLC. Accept the mixture and price it into expectancy; or add an external news gate. | Tag every sweep with proximity to a scheduled release once a calendar feed exists; compare reversal rates inside vs outside ±30 min. | **PLAUSIBLE** (mechanism), needs data we do not have |
| LS-05 | **Entering on the reclaim close (too early)** | The reclaim bar's close is the point of maximum ambiguity: the sweep has happened but nothing has yet demonstrated who is in control. It is also the point at which the retail rule fires, which is why it is crowded. | Reclaim close with no follow-through: next bar's range fails to exceed the reclaim bar's close in the trade direction. | Require the *next* bar to close beyond the reclaim bar's close before entering, at the cost of worse price. | A/B the same signal population with entry at reclaim close vs entry at next-bar-confirm. Compare expectancy net of the wider stop. | **REPORTED** (traders), effect size untested |
| LS-06 | **Entering after displacement (too late) — R:R collapse** | The stop must sit behind the sweep extreme. As the move develops, entry moves away from the stop, so risk grows while the remaining distance to the target shrinks. Reward:risk degrades continuously with delay. | Distance from current price to the sweep extreme, divided by ATR, at the moment the entry fires. | Hard cap: reject any entry where (entry − sweep extreme) > 1.0 ATR. Reject rather than widen the stop. | Backtest the same signals with an entry-lateness cap at 0.5 / 1.0 / 1.5 ATR and measure expectancy and trade count. | **MEASURED** (this is exactly E-001's failure: 70% wins, R:R 0.53) |
| LS-07 | **Nested sweeps do not carry extra information** | The folklore says the second sweep of a level is "the real one". On gold the second-and-later sweep behaves the same as the first. | Count of prior pierces of the same level. | Do not add a "nth sweep" filter. It costs trades and buys nothing. | Already measured; retest on longer M15 history. | **MEASURED** `[ours]` — 1h: 1st +0.3pp vs nested +1.5pp (short); 15m: −2.0 vs −1.6pp |
| LS-08 | **Displacement filter does not replicate** | "Require a strong reclaim candle" is the most-taught quality filter. Its sign flips between timeframes on the same instrument, which means it is fitting local volatility regime, not structure. | The filter's own sign stability across timeframes and folds. | Ban any filter that has not held its sign on ≥2 independent samples. | Pre-register the filter, then run it on M15 gold history that does not overlap the fitting window. | **MEASURED** `[ours]` — 1h +6.6pp vs 15m −13.2pp, both |z|>2 |
| LS-09 | **Trend-vs-range regime filter does not replicate** | Same as LS-08. On 1h the with-trend short is +4.8pp; on 15m it is −8.3pp. Regime classification is itself a free parameter (which MAs, which separation threshold). | Sign stability of the regime split. | Do not gate on regime until it survives out-of-sample. If used, the regime definition must be fixed before seeing results. | Walk-forward the regime definition, holding the MA lengths out of the fitting fold. | **MEASURED** `[ours]` |
| LS-10 | **The reversal statistic is unmeasurable as usually quoted** | Vendor sources quote 60–75% reversal rates for "confirmed" sweeps. None publish a sample size, an instrument, a definition of "confirmed", a cost model, or a barrier. The one repeatedly quoted figure ("XAUUSD ~62% intraday fakeouts") could not be traced to any dataset in either this session or the earlier evidence review. | Any quoted win rate with no denominator. | Treat all published sweep reversal rates as unusable. Use only numbers computed in this repo. | n/a — this is a source-quality rule, not a strategy rule. | **FOLKLORE** (vendor incentive: all sell courses, indicators or brokerage) |
| LS-11 | **Level definition sensitivity** | A "swing low" is a free parameter (fractal width, ATR-significance, session anchoring). Changing k=3 to k=5 changes the entire trade population, so "the strategy" is really a family of thousands of strategies. | Number of qualifying levels per 1,000 bars, as a function of k. | Fix k once, before testing, and record it in DECISIONS.md. Never tune it after seeing results. | Sensitivity sweep across k and report the full distribution of expectancies, not the best one. | **MEASURED** in principle (repo already has `sensitivity.py`); **PLAUSIBLE** for the specific magnitude |
| LS-12 | **Level staleness — undeclared lookback parameter** | How long a swing level "counts" as liquidity is never specified in the retail rules but silently determines trade count and hit rate. Our own measurement used a 60-bar validity window; that choice was arbitrary. | Bars elapsed between level formation and the pierce. | Declare the validity window explicitly; test 20/60/200 bars as a pre-registered sweep. | Add `age_bars` to each event in `sweep_anatomy.py` and bucket the outcome by age. | **PLAUSIBLE** |
| LS-13 | **Equal-highs / inducement subjectivity** | "Equal highs", "valid inducement", "major POI" are not geometric conditions. They cannot be coded without inventing a tolerance, and the tolerance becomes the strategy. | Whether two independent implementations produce the same trade list. | Only trade constructs that are exactly codeable. Reject anything requiring a judgement call at signal time. | Code two independent implementations of the same verbal rule and measure trade-list overlap. If <90%, the rule is not a rule. | **REPORTED** (this is the standard quant criticism of SMC) |
| LS-14 | **Hindsight selection in every teaching example** | Educational content shows charts chosen because they reversed. The base rate is invisible. This is why the perceived hit rate is 70% and the measured one is at baseline. | Ratio of examples-shown to sweeps-occurred in the same period. | Never calibrate expectations from charts. Only from the full enumerated event population. | Enumerate every sweep in a window and count how many look like the textbook example. | **REPORTED**, mechanism **MEASURED** `[ours]` (7,686 pierce events on gold 1h in 2.4 years — nobody shows 7,686 charts) |
| LS-15 | **Volatility clustering → sweeps arrive in correlated bursts** | Sweeps are triggered by volatility, and volatility clusters. Trades are therefore not independent draws; several losers land in the same hour. | Sweeps per rolling 24h vs ATR percentile. | Cap trades per day and per volatility regime. This is a risk rule, not an edge rule. | Measured partly: naive sweep averages 1.68 trades/day but reaches 6 `[ours]`. Extend to a per-day correlation estimate. | **MEASURED** `[ours]` |
| LS-16 | **Both-side sweep (whipsaw) within one setup** | Price sweeps the low, reclaims, then sweeps the high — the "liquidity grab" happens in both directions inside the same range. Both a long and a short signal fire and both lose. | Range compression before the event; two pierces of opposite levels within N bars. | Suppress signals for N bars after an opposite-side sweep of the same range. | Count opposite-side pierces within 6 bars and measure the expectancy of trades taken inside that window. | **PLAUSIBLE** |
| LS-17 | **Broker-specific wick depth** | The sweep is defined by a wick. Wick extremes differ between feeds because the low tick differs. A setup that exists on one broker does not exist on another. | Compare the same bar's low across two feeds. | Require the pierce to exceed the level by a buffer (≥0.15 ATR) so it survives feed differences. **Note this cuts against LS-08's "shallow pierce" filter — choose feed robustness over the unreplicated filter.** | When MT5 data arrives from Veer's broker, diff its GOLD 15m lows against `data/GOLD_15m.json` and count sign-changing sweeps. | **REPORTED** (broker data quality: some MT5 feeds cannot exceed 60% history quality where Dukascopy reaches 99.9%) |
| LS-18 | **Round-number edge is smaller than the spread** | The best-documented level effect in the literature is ~3.4pp of extra bounce frequency at round numbers. The cost tax on a $2 gold stop at $0.30 round trip is 5.0pp of required win rate. The documented edge does not cover the documented cost. | Break-even win rate = (1 + cost/risk) / (RR + 1), computable before trading. | Any level-based rule must clear a 5pp+ hurdle before it is interesting. Reject on arithmetic, not on backtest. | Compute the hurdle for the actual stop distance the strategy uses; require measured edge > 2× hurdle. | **MEASURED** (3.4pp `[2nd-hand]`; 5.0pp computed in `findings/01_liquidity_evidence.md`) |
| LS-19 | **Your own stop is the liquidity** | A stop placed just beyond the sweep wick sits precisely where the next sweep's stops cluster. The strategy manufactures the liquidity that kills it. | Distance from stop to the nearest obvious level, in ATR. | Place the stop *beyond* the obvious cluster (≥0.3 ATR past the wick) and size down, rather than tight-and-large. | Test stop buffer 0.15 / 0.30 / 0.50 ATR with position size held constant in R terms. | **PLAUSIBLE**, mechanism **MEASURED** `[2nd-hand]` (SL clustering just beyond levels) |
| LS-20 | **Crowding — the rule is on every YouTube channel** | Any rule taught to millions has its liquidity consumed by faster participants, and the resting orders it depends on are increasingly placed by algorithms that do not behave like 1999 human dealers. | Decay of the effect over calendar time. | Test the effect on the oldest and newest halves of the data separately; require both to be positive. | Split-sample by date in `failure_probes.py`. | **PLAUSIBLE** (the only order-book evidence is from a 9-month window in 1999–2000; never replicated on modern venues) |

---

## SECTION 2 — WHY SETUPS GO INTO PROFIT THEN REVERSE

| ID | Failure mode | Mechanism | Observable signature | Proposed rule/filter | How to test it | Confidence |
|---|---|---|---|---|---|---|
| PR-01 | **Give-back is the normal case, not the exception** | With a 1R stop and a 3R target, a large fraction of paths touch +1R and then still reach the stop. This is a property of the price process, not of the entry. | Unconditional give-back rate, measurable from any bar. | Stop treating give-back as a fixable defect. Budget for it in expectancy. | Already computed; extend to other RR geometries. | **MEASURED** `[ours]` — GOLD 1h: 46.1% of probes reach +1R, **42.6% of those still stop out**. GOLD 15m: 47.7% reach +1R, **50.0% still stop out** |
| PR-02 | **Moving to break-even early** | Scratching at BE removes the trade from the tail-paying population while keeping all the small losers. It converts a positive-expectancy geometry into a negative one. | Win rate collapsing toward 15–20% with a large "scratch" bucket. | **Never move to break-even before the target.** Already a settled decision in this repo. | Already done: `exit_study.py`, 4 markets. | **MEASURED** (repo E-008: −0.161R GOLD, −0.188R US500, −0.308R EURUSD, −0.293R GBPUSD — worst rule on all four) |
| PR-03 | **Winners require adverse excursion first** | A trade that eventually wins usually goes against you before it works. A stop tight enough to avoid give-back is tight enough to remove the winners. | MAE distribution of eventual winners. | Stop must be ≥ p75 of winners' MAE. Anything tighter is a winner-removal device. | Compute MAE percentiles per strategy before choosing the stop; re-check after any entry change. | **MEASURED** `[ours]` — naive sweep GOLD 1h winners: median MAE 0.44R, p75 0.65R, p90 0.82R; **40.2% of winners first went 0.5R against** |
| PR-04 | **Consolidation after entry read as failure** | Post-entry coiling looks like the thesis dying. Time stops and discretionary exits fire during it. The repo already shows a time-20 exit was the *best* simple exit on gold — meaning the coil often resolves in favour. | Range contraction with no violation of the entry structure. | Define invalidation as *price* (structure violated), never as *time*, unless a time stop has been tested as such. | Compare time-stop-N vs structure-stop on the same entry population. | **MEASURED** partly (repo E-008: time-20 exit +0.201R, best simple exit on gold) |
| PR-05 | **"Structure still valid" vs "thesis broken" is undefined** | Without a written invalidation condition set at entry, the exit becomes a discretionary judgement made under loss aversion — the worst possible conditions. | Whether the trade record contains a pre-declared invalidation price. | Every entry must write down, at entry time, the exact price at which the thesis is dead. That price is the stop. There is no second exit rule. | Trivially auditable: reject any trade log row without a pre-declared invalidation price. | **REPORTED**, mechanism **PLAUSIBLE** |
| PR-06 | **Your target sits at someone else's level** | A fixed 3R target that lands just beyond an obvious swing high is where take-profit orders cluster — price often stalls just short of it. | Distance from target to the nearest prior swing extreme. | Either place the target *inside* the nearest opposing level, or accept the fixed-R target and do not chase. Do not do both. | Measure the fill rate of targets that sit within 0.25 ATR beyond an opposing swing extreme vs those in clear space. | **PLAUSIBLE**, cluster mechanism **MEASURED** `[2nd-hand]` (TP clustering at round numbers ~9.8%) |
| PR-07 | **Trailing stops cut the tail that pays for everything** | The MFE distribution is extremely skewed: total profit comes from a small number of very large trades. Any trailing rule that protects the median removes the tail. | MFE distribution skew, measurable on any strategy. | Fixed target or time exit. Trail only after a multiple far beyond the median MFE. | Already done for one entry type; repeat for the sweep entry. | **MEASURED** (repo: GOLD median MFE 1.12R, p75 3.89R, p90 7.51R, max 102.68R) |
| PR-08 | **Partial profits feel good, cost expectancy** | Taking half off at 1R converts a 3R winner into ~2R while leaving the full loser intact. Same mechanism as PR-02, smaller magnitude. | Realised average win vs target R. | No partials until a partial-scaling policy has been tested against the flat policy on the same entries. | Add "50% at 1R, rest at 3R" to `exit_study.py`'s policy list. | **PLAUSIBLE** (direct corollary of PR-02, which is MEASURED) |
| PR-09 | **Entry failures cannot be fixed by exits** | A fraction of trades never go meaningfully green. No exit rule can help those; they are an entry problem misdiagnosed as an exit problem. | % of losers whose MFE < 0.3R. | Fix entries first. Judge entries by the fraction of dead trades, not by win rate. | Report `%losers with MFE<0.3R` as a standard metric on every strategy. | **MEASURED** `[ours]` — naive sweep: **38.8% of losers never reached +0.3R**. Repo baseline 23%; Veer's EA **81%** (153/188) |
| PR-10 | **Retrace-then-continue vs retrace-then-fail has no found separator** | Both look identical while happening. The honest position is that no OHLC-observable feature separating them has been demonstrated. | None known. | Do not build a rule that requires telling these apart. Design the stop so the answer does not need to be known. | Attempt the split: bucket post-entry retraces by whether they violate the sweep extreme, and measure forward outcome. If the split is <5pp, declare it unseparable and move on. | **PLAUSIBLE** — flagged as an open question, not a solved one |

---

## SECTION 3 — WHY M1 IS DANGEROUS

| ID | Failure mode | Mechanism | Observable signature | Proposed rule/filter | How to test it | Confidence |
|---|---|---|---|---|---|---|
| M1-01 | **Cost is a quarter of the entire bar** | Bar range scales as t^H. Fitting gold's own median true range across M15→H4 gives **H = 0.554**. Extrapolating down: median M1 true range ≈ **$1.64**, against a $0.47 round trip ($0.30 spread + 2×$0.05 slip + ~$0.07 commission) = **28.7% of one whole bar's range**. | The ratio itself, computable before writing any strategy. | **M1 is banned as a signal timeframe on gold.** It may be used only to time an execution inside an already-decided M15/M5 level. | `failure_probes.py` section B. Re-fit once real M1 data exists rather than relying on extrapolation. | **MEASURED** `[ours]` (extrapolated; the M15–H4 ladder is directly measured: M15 6.4%, M5 11.8%, M3 15.6%, M1 28.7%) |
| M1-02 | **Cost as a fraction of risk, not of range** | The binding constraint is cost/risk, not cost/range. A 1.40×ATR M1 stop on gold ≈ $1.40 of risk against a $0.30 round trip = **21.4% of risk lost before any edge**, which raises the RR2 break-even win rate by ~7pp. | (round-trip cost) / (stop distance), known at entry. | Hard gate: reject any signal whose stop distance is < 10× the round-trip cost. On gold that means a stop ≥ $4.70, which M1 structure cannot supply. | Compute the ratio at signal time and log it. Reject and count rejections. | **MEASURED** (repo E-006, from the EA's own live record) |
| M1-03 | **The illusion of opportunity** | M1 produces ~15× more bars than M15 and therefore ~15× more signals with the same (or worse) per-signal edge. Cost scales linearly with trade count; edge does not. | Trades per day vs expectancy per trade. | Judge every timeframe by *expectancy × trades* net of cost, and always report the cost bill separately. | The repo already has the template: the EA's spread bill was **48% of its total loss**. Reproduce that decomposition for any candidate. | **MEASURED** (repo E-006: spread bill = 48% of loss; efficiency ratio 0.038 = 26:1 churn) |
| M1-04 | **M1 "structure" is 3 minutes of information** | A k=3 fractal pivot on M1 is defined by seven minutes of price. Calling that a "swing low" imports the connotations of a daily swing low with none of the substance. | Number of qualifying pivots per hour. | Structure levels come from M15 and above only. M5/M1 are execution layers with no level-defining authority. | Count pivots/hour at each timeframe and compare to the number a human would mark. | **PLAUSIBLE**, strongly implied by M1-01 |
| M1-05 | **Serial dependence inflates significance** | Overlapping M1 observations are highly autocorrelated. A t-statistic computed as if 100,000 bars were 100,000 independent draws is badly overstated. | Effective sample size vs raw bar count. | Use block bootstrap / walk-forward on non-overlapping windows. Never quote a naive t on M1. | The repo already uses stationary-resampling ideas in `study.py`; extend to explicit block bootstrap before any M1 claim. | **MEASURED** (standard result; also the method Darmanin 2026 uses — stationary bootstrap + Benjamini-Yekutieli) |
| M1-06 | **Latency is material at M1** | Signal-to-fill delay of 100–250ms is negligible on an M15 stop of $10 and material on an M1 stop of $1.50. Reported: moving from home connection (50–300ms) to co-located VPS (1–10ms) changed monthly performance by >18% for one scalping setup. | Measured round-trip latency; distribution of (intended fill − actual fill). | If the strategy's edge depends on latency, it is not a strategy JARVIS can run. | Log intended vs actual fill on demo for 200 trades and compute the mean adverse difference in R. | **REPORTED** (vendor sources: VPS providers — direct incentive to overstate; treat the 18% figure as unverified) |
| M1-07 | **Broker M1 history is often synthetic** | Many MT5 feeds cannot exceed ~60% history quality on M1; gaps are interpolated. A backtest on interpolated M1 tests the interpolation. | MT5's own "history quality" figure; count of zero-range bars; count of missing minutes per session. | Refuse to backtest M1 on broker-supplied history. Require tick data with a stated quality figure. | Count missing minutes and zero-range bars in any M1 file before use; reject above a pre-set threshold. | **REPORTED** (MQL5 community; Dukascopy 99.9% vs broker <60%) |
| M1-08 | **When M1 IS legitimate** | The one defensible use: the *decision* is made on M15 (level, direction, invalidation), and M1 is used only to reduce the distance from entry to invalidation, improving R:R without changing the thesis. | Whether the M1 event can change the trade's direction. If yes, M1 is generating signal and the rule is violated. | M1 may tighten a stop or refine a fill. It may never create, cancel or reverse a trade. | Log both the M15-only version and the M15+M1-execution version of the same trades; the trade *list* must be identical, only the fills differ. | **PLAUSIBLE** — this is the design rule this file recommends, not a measured fact |

---

## SECTION 4 — WHY BACKTESTS BEAT LIVE

| ID | Failure mode | Mechanism | Observable signature | Proposed rule/filter | How to test it | Confidence |
|---|---|---|---|---|---|---|
| BT-01 | **Intrabar sequencing is unknowable** | When a bar's range contains both the stop and the target, OHLC cannot say which came first. The engine must guess, and the guess is often wrong. | Fraction of trades where both levels lie inside one bar. | Already correct in this repo: **ties lose**. Keep it. Also report the ambiguity rate so its influence is visible. | Measured. | **MEASURED** `[ours]` — for a 1R stop / 3R target on gold, both-in-one-bar occurs on **0.22% of 1h probes and 0.14% of 15m probes**. Small for this geometry — but it grows sharply as stop and target converge, which is exactly the M1 scalping geometry |
| BT-02 | **Constant spread assumption** | Backtests charge one spread; live spread is a distribution with a fat right tail concentrated exactly when signals fire. | Spread distribution vs time of day and vs news. | Every candidate must be reported at 1×, 2× and 3× spread, and must survive 3×. | Already implemented in `sensitivity.py`. | **MEASURED** (repo E-003: sweep goes +0.001R → −0.031R at 2× → **−0.061R at 3×**) |
| BT-03 | **Weekend and session gaps jump the stop** | The stop is a trigger, not a guarantee. On a gap the fill is the next available price. | Gap size distribution in ATR. | Size positions assuming the stop can fill 1 ATR worse. Do not hold through the weekly close unless the strategy has been tested with gap fills. | Measured; extend by re-running the backtest with gap fills at the gap open rather than at the stop price. | **MEASURED** `[ours]` — GOLD session/weekend gaps: median 0.40 ATR, p90 **1.93 ATR**, max **5.00 ATR**, **28.4% exceed 1 ATR** (EURUSD 36.6%, US500 31.4%) |
| BT-04 | **Broker data differs from test data** | Different feeds have different highs/lows/spreads. A wick-defined strategy is maximally exposed to this because its trigger *is* the extreme tick. | Diff of the same bar across two feeds. | Require the pierce buffer (LS-17) to exceed typical inter-feed wick disagreement. | Diff Veer's MT5 export against `data/GOLD_15m.json` bar-by-bar; report % of bars whose low differs by >0.15 ATR. | **REPORTED** |
| BT-05 | **Latency and requotes create adverse fill selection** | The fills you miss during fast markets are disproportionately the good ones (price ran away = your winner); the fills you get are the ones where price came to you. Backtests fill everything. | Rejection/requote rate; slippage sign conditional on subsequent trade outcome. | Model a fill-probability haircut on signals that fire during expanding ranges. | Compare demo fill logs against the backtest's assumed fills over 200 trades. | **PLAUSIBLE**, adverse-selection mechanism well established in microstructure |
| BT-06 | **Multiple testing / selection bias** | Trying many strategies on one dataset guarantees a good-looking best one. The reported statistic must be deflated by the number of trials. | Count of variants tried on this dataset. | Maintain a running trial counter; apply a Bailey/López de Prado-style deflation before believing any Sharpe or t. | The repo already has multiple-testing correction (commit a1f4b4c). Extend it to count every sweep-filter variant tried in this file. | **MEASURED** (Bailey & López de Prado 2014, deflated Sharpe ratio) |
| BT-07 | **Regime survivorship in the sample window** | Gold's 2024–2026 data is a strong bull market. Any long-biased rule flatters. Conversely, our long-sweep result may be partly a bull-market-mean-reversion artifact. | Direction split of expectancy; performance by calendar half. | Report longs and shorts separately, always. Require both halves of the sample to agree in sign. | Split-sample by date; require sign agreement. | **MEASURED** (repo: E-001 had 29 of 30 trades long during a +17% bull run) |
| BT-08 | **Look-ahead through pivot confirmation** | A k=3 fractal pivot is only *known* k bars after it forms. Code that uses the pivot at its own index is looking ahead by 3 bars. | Whether the level's index of first use is ≥ pivot index + k + 1. | Enforced by construction. `sweep_anatomy.py` uses `first_valid = j + k + 1`. | Unit test: shift the data forward and confirm the trade list does not change. | **PLAUSIBLE** as a bug class; the guard is **MEASURED** as present in our code |
| BT-09 | **Overlapping / concurrent position accounting** | Allowing overlapping positions inflates trade counts and hides the fact that the account could not have taken them all at that size. | Max concurrent open positions. | Test both `one_at_a_time=True` (realistic) and overlapping (for exit isolation) and never mix the two in one claim. | Already handled explicitly in `engine.backtest`. | **MEASURED** (repo design) |
| BT-10 | **Costs omitted entirely: swap, commission, financing** | Gold carries a meaningful overnight financing cost. A strategy holding through sessions pays it and most backtests do not. | Swap per lot per night from the broker spec. | Add swap to `Costs` and charge it per night held before any multi-session strategy is believed. | Extend `engine.Costs` with a `swap_per_night` field. | **PLAUSIBLE** (magnitude broker-specific and not yet known) |
| BT-11 | **Contract-spec and pip-definition errors** | XAUUSD "pips" are quoted inconsistently (0.01 vs 0.1 vs 1.0 depending on broker). Sizing code that assumes the wrong one is wrong by 10×. | Value per point per lot, read from the broker spec, not assumed. | Read contract specs programmatically. Never hard-code. | Assert value-per-point against a known trade's realised P&L before going live. | **REPORTED** (recurring cause of blown accounts; also visible in the wildly inconsistent "pip" usage across every source consulted for this file) |
| BT-12 | **The strategy that is tested is not the strategy that is traded** | Live discretion — skipping a signal because it "looks bad" — changes the population and usually removes the tail winners. | Backtest trade count vs live trade count over the same period. | Full automation or a written no-skip rule. Reconcile live and backtest trade lists weekly. | Weekly reconciliation report; count and classify divergences. | **REPORTED** |

---

## SECTION 5 — WHY PROFITABLE TRADERS STILL FAIL FUNDED ACCOUNTS

The core asymmetry: **a strategy is judged on expectancy; a funded account is judged
on a path constraint.** A positive-expectancy strategy with the wrong loss
distribution fails a prop account with near-certainty. This is a geometry problem,
not a discipline problem.

Measured on our own naive sweep rule, GOLD 1h, 603 trades over 358 trading days `[ours]`:

```
daily R:  min -6.07   p5 -3.05   median -0.44   p95 +2.80   max +7.43
days worse than -2R:  80  (22.3% of trading days)
days worse than -3R:  28  ( 7.8% of trading days)
days worse than -4R:   7  ( 2.0% of trading days)
longest losing streak: 16 trades
```

Set against a 5% daily loss limit: at 1.0% risk/trade the limit is **5R** — breached
on ~1% of days; at 0.5% it is 10R; at 0.25% it is 20R. **The risk-per-trade choice,
not the strategy, decides whether this account survives.**

| ID | Failure mode | Mechanism | Observable signature | Proposed rule/filter | How to test it | Confidence |
|---|---|---|---|---|---|---|
| PF-01 | **Daily loss limit vs the strategy's daily loss distribution** | The limit is a hard barrier on a random walk. The relevant statistic is the left tail of *daily* R, which is not the same as per-trade R because losses cluster (LS-15). | p1/p5 of daily R, in R units, from the backtest. | Set risk/trade so that the p1 daily loss is ≤ 60% of the daily limit. Derive risk from the measured tail, never from a rule of thumb. | `prop_sim.py` already exists. Feed it each candidate's actual trade sequence and count breaches. | **MEASURED** `[ours]` + industry `[vendor]`: daily drawdown breaches are reported as ~71% of phase-1 failures |
| PF-02 | **Trailing drawdown ratchets on *unrealised* highs** | On intraday-trailing firms the floor moves the instant an open position prints a new equity high. A trade that reaches +$1,500 and is closed at +$400 still lifts the floor by $1,500. | The firm's rule text: intraday vs EOD trailing. This is knowable before funding. | Prefer static or EOD-trailing firms. If intraday-trailing, treat unrealised peak equity as if it were realised for risk purposes. | Simulate both floor models over the same trade path in `prop_sim.py` and compare survival. | **MEASURED** (mechanic is deterministic and documented); failure share ~20–30% `[vendor]` |
| PF-03 | **Taking profit early is *worse* under trailing DD** | The instinct that protects the P&L (PR-02) also raises the floor without banking the profit — a double penalty unique to trailing accounts. | Ratio of realised P&L to peak unrealised P&L per trade. | Same conclusion as PR-02 from a completely different direction: do not scratch trades early. | Compare "BE at 0.5R" vs "fixed 3R" *inside* `prop_sim.py` with trailing DD enabled. | **MEASURED** (repo E-008) + deterministic mechanic |
| PF-04 | **Consistency rule caps the best day** | Typical rule: best single day ≤ 30–45% of total profit. A strategy whose profit comes from a skewed tail (PR-07) violates this **by design**, because one tail trade is most of the profit. | best-day / total-profit, computable from the backtest equity curve. | Either cap daily profit deliberately, or choose a firm without a consistency rule. Do not discover this at payout time. | Add a consistency check to `prop_sim.py` and report the ratio for every candidate. | **MEASURED** (rule text is explicit); ~10–15% of failures `[vendor]` |
| PF-05 | **Long losing streaks are structural for low-win-rate systems** | A 30–35% win-rate system with 3R targets — which E-008 shows is the *correct* design — produces long streaks. 16 consecutive losers is not bad luck; it is the expected worst streak for this trade count. | Longest streak in backtest and its Monte Carlo distribution. | Size so that the 99th-percentile Monte Carlo streak stays inside the max drawdown. | Monte Carlo the streak distribution; `study.py` already does drawdown MC. | **MEASURED** `[ours]` — 16-trade streak, and 59.8R peak-to-trough drawdown on a strategy with +0.81R total |
| PF-06 | **The correct strategy design conflicts with the account design** | Prop rules reward smooth, frequent, small gains. The measured evidence says profit comes from rare large winners. **These are opposed.** Most funded-account failure is this conflict, not incompetence. | The conflict is visible the moment you plot expectancy vs max-daily-loss constraint. | Accept lower expectancy in exchange for path smoothness, *knowingly and in writing*, or do not use funded accounts. Do not pretend both are achievable. | Run the same strategy through `prop_sim.py` at several risk levels and plot pass-probability vs expected profit. The frontier is the honest answer. | **PLAUSIBLE** (mechanism), components **MEASURED** |
| PF-07 | **High win rate invites over-sizing** | A 70% win rate feels safe and encourages larger size, precisely in a system whose losses are large relative to wins. This repo has already lived this exact failure. | Win rate reported without R:R. | Ban win rate as a headline metric. Report expectancy and break-even win rate side by side, always. | Already a standing rule; enforce in `leaderboard.py` output. | **MEASURED** (repo E-002: **69.5% win rate, −0.066R expectancy**, PF 0.79, 0/6 folds positive) |
| PF-08 | **Time limits force trades** | An evaluation with a max-days window converts "wait for the setup" into "take what's there". The forced trades are the marginal ones — the ones with the least edge. | Trades taken per day, late in the evaluation window, vs early. | Prefer unlimited-time evaluations. If timed, pre-compute the required trades/week and check the strategy actually produces them. | Count signals per week in backtest; if the median week yields fewer than the required number, the evaluation is unpassable by design. | **REPORTED** |
| PF-09 | **News-window breach via a stop or target fill** | Firms such as FTMO forbid opening *or closing* within ±2 min of listed high-impact USD news on affected instruments — and **XAUUSD is explicitly on the USD-affected list**. A stop-loss that triggers inside the window is a breach, even though the trader did nothing. | The economic calendar, known in advance. | Flatten before the window, or move stops outside it, or do not hold gold through listed USD releases on a standard funded account. | Requires a calendar feed. Until then: hard block on holding gold positions through known release times. | **MEASURED** (rule text is explicit and public) |
| PF-10 | **Pass ≠ paid** | Passing the challenge is not the terminal event; the funded account then has to survive to a payout. Reported: ~5–14% pass, but only ~7% of all entrants ever receive a payout. | The two rates quoted separately by the firm. | Model the whole path (challenge → funded → first payout), not just the challenge. | Extend `prop_sim.py` to run challenge and funded phases end to end with the payout rule. | **REPORTED** `[vendor]` — figures come from prop-firm-affiliate sites with an incentive to appear candid while still selling challenges. Treat as indicative only |
| PF-11 | **Multi-account correlation** | Running the same strategy on several accounts to diversify does nothing: the trades are identical, so the failure is perfectly correlated. | Cross-account trade correlation — which is 1.0 by construction. | Multiple accounts must run *uncorrelated* strategies or they are one account with more fees. | Already measured in this repo (commit 64119cd, correlation structure / concentration risk). | **MEASURED** (repo `findings/07_correlation.md`) |
| PF-12 | **Slippage at the boundary closes the account, not the trade** | Near the daily limit, a single slipped stop crosses the line. The account dies from execution, not from the strategy. | Distance from current equity to the limit, in units of "one slipped stop". | Hard stop-trading rule at 60% of the daily limit. No exceptions, no recovery trades. | Add a soft-limit rule to `prop_sim.py` and measure how much expectancy it costs vs how much breach probability it removes. | **PLAUSIBLE**, mechanically certain |

---

## SECTION 6 — NEWS AND SESSION FAILURES

**Measured session profile, GOLD 1h median bar range by UTC hour `[ours]`:**

```
04:00  $ 6.70   <- quietest
07:00  $11.50
12:00  $15.60
13:00  $20.95   <- peak (US data / NY open)
14:00  $20.25
15:00  $16.10
01:00  $15.50   <- SECOND PEAK, in the "quiet Asian session"
20:00  $ 7.10
```

The 13:00 UTC hour has **3.1× the median range of the 04:00 hour**. But note the
01:00 UTC peak of $15.50 — larger than 08:00–11:00 London. The folklore that "Asia
is quiet, London and New York are where gold moves" is **half wrong**: gold has a
genuine Asian-hours volatility peak.

| ID | Failure mode | Mechanism | Observable signature | Proposed rule/filter | How to test it | Confidence |
|---|---|---|---|---|---|---|
| NS-01 | **Spread blowout at release** | Liquidity providers withdraw quotes at the release instant; the book thins and the quoted spread widens by an order of magnitude. Reported figures for XAUUSD range from 5–15× normal up to 100–200 "pips" — the sources disagree wildly and all are broker-affiliated. | Spread time series, recordable on demo now, before any live risk. | Never open a position within ±5 min of a listed high-impact USD release. This is a cost rule, independent of the prop rule (PF-09). | **Record the actual spread every second on Veer's MT5 for two weeks including one NFP.** This is the highest-value cheap measurement available and it is currently missing. | **REPORTED** — magnitudes are `[vendor]` and mutually inconsistent; the *direction* is certain |
| NS-02 | **A stop is a trigger, not a guarantee** | On a news gap the stop becomes a market order into a thin book. Realised loss exceeds planned risk, invalidating the R accounting the whole system rests on. | Gap distribution (BT-03): p90 = 1.93 ATR, max 5.00 ATR `[ours]`. | Assume worst-case realised risk = 2× planned when a position is open across a release. Size accordingly or be flat. | Log realised-vs-planned risk for every stop-out; the ratio is the number that matters. | **MEASURED** `[ours]` for gaps; news-specific magnitude unmeasured |
| NS-03 | **News destroys the level, not just the trade** | A release re-prices the instrument. The swing low the setup was built on becomes irrelevant information from a different regime. Continuing to trade pre-news levels after the release is trading a stale map. | Post-release bar range > 3× ATR. | Invalidate all structure levels after any bar exceeding 3× ATR; re-derive from scratch. | Tag levels with the max bar range since formation; bucket outcomes by whether a >3× ATR bar intervened. | **PLAUSIBLE** — cheap to test with data we already have |
| NS-04 | **The sweep *is* the news** | Sweeps cluster where volatility clusters, which is where news lands. A large share of "liquidity sweeps" are simply the first 15 minutes of a data release. The strategy is therefore an unlabelled news-trading strategy. | Overlap between sweep timestamps and the economic calendar. | Once a calendar exists: measure the sweep expectancy inside vs outside news windows. If the edge lives inside, it is a news strategy and should be designed as one. | Needs a calendar feed. Until then, use the hour-of-day proxy: the naive sweep's worst hour is **14:00 UTC (−0.647R, n=52)** — the US-data hour. | **MEASURED** (hour proxy `[ours]`); news attribution **PLAUSIBLE** |
| NS-05 | **Hour-of-day expectancy is an overfitting trap** | With ~20–50 trades per hour bucket, hourly expectancy is almost pure noise, and the spread between "best" and "worst" hour is enormous. Selecting the good hours is one of the easiest ways to manufacture a fake edge. | The naive sweep's hourly expectancy ranges from **+0.652R (17:00, n=23)** to **−0.647R (14:00, n=52)** `[ours]` — a 1.3R spread on samples of a few dozen. | **Do not filter by hour** unless the split is pre-registered, mechanistically motivated, and holds out of sample. Session filters must be justified by the *volatility* profile, not the expectancy profile. | Randomly permute trade timestamps and re-derive the best hour. If the fake best-hour spread is comparable, the real one is noise. | **MEASURED** `[ours]` |
| NS-06 | **"Asia is quiet" is half folklore** | Gold's 01:00 UTC hour has a median range of $15.50 — the second-highest of the day and well above London morning hours. Rules that widen stops in London and tighten them in Asia have it backwards for one hour of the Asian session. | The hourly range profile itself. | Scale stops by *measured* hourly median range, not by session name. | Already measured. Recompute on M15 when longer history arrives. | **MEASURED** `[ours]` |
| NS-07 | **Rollover / broker session break** | The 21:00 UTC hour has only 169 bars in our 2.4-year gold sample versus ~595 for every other hour `[ours]` — the broker's daily maintenance break. Spreads widen sharply around it and the bar series is not continuous. | Bar count per hour; any hour with an anomalous count is a structural break. | No entries 20:30–22:30 UTC. Treat the break as a session boundary, not as continuous time. | Already measured; verify against Veer's own broker's session spec, which may differ. | **MEASURED** `[ours]` |
| NS-08 | **Weekly-open gap through a held position** | Gold gaps at the Sunday open. 28.4% of session gaps exceed 1 ATR `[ours]`. A position held over the weekend has an uncapped tail. | Whether the strategy ever holds through Friday close. | Flat by Friday close unless the weekend gap has been explicitly backtested with gap fills. | Re-run any multi-day candidate with a forced Friday-close exit and compare. | **MEASURED** `[ours]` |
| NS-09 | **"Wait 15 minutes after news" is untested folklore** | Universally repeated, always with a different number (5, 10, 15, 30 minutes). No source consulted provided a measurement. | The recommended wait time varies by source, which is the tell. | If a post-news blackout is used, choose the duration by measuring spread normalisation time, not by copying a number. | Record spread on demo through several releases; define the blackout as "spread back within 1.5× median". | **FOLKLORE** |

---

## SECTION 7 — GOLD-SPECIFIC FAILURE MODES

| ID | Failure mode | Mechanism | Observable signature | Proposed rule/filter | How to test it | Confidence |
|---|---|---|---|---|---|---|
| GX-01 | **Gold falls faster than it rises, even in a bull market** | Baseline P(down 1 ATR before up 1 ATR) = **0.544 on gold 1h**, versus 0.500 on EURUSD and 0.490 on US500 `[ours]`, measured *during a period in which gold rose strongly*. Short-horizon downside moves are faster; the drift is upward but the path is down-skewed. | The baseline itself. | Long and short setups on gold are not symmetric and must never share a threshold. Report every statistic separately by side. | Recompute the baseline on each new data window; it is a regime property and may change. | **MEASURED** `[ours]` |
| GX-02 | **ATR in dollars is non-stationary** | Median 1h true range is $11.20 over the full 2024–2026 sample but $15.50 over the 2026 sub-window when gold traded near $4,300 `[ours]`. Any fixed-dollar stop, target, buffer or filter threshold silently changes meaning as price doubles. | Median true range as a rolling series; ATR as a % of price. | Every threshold in the system must be expressed in ATR or in % of price. **Zero hard-coded dollar values.** | Grep the codebase for numeric price constants; each one is a bug. | **MEASURED** `[ours]` |
| GX-03 | **Spread as a fraction of price changed by ~2× over the sample** | A $0.30 spread is 1.3 bp at $2,300 and 0.7 bp at $4,400. Cost models calibrated on one price level mis-state the other. Conversely, brokers often widen the absolute spread as price rises, so the improvement may not be real. | Spread quoted in absolute dollars vs in bp, tracked over time. | Model cost in bp of price, and verify against the broker's actual current quote before any live decision. | Record live spread for two weeks and fit spread-vs-price. | **MEASURED** `[ours]` for the price change; broker behaviour **PLAUSIBLE** |
| GX-04 | **The sample is not a bull run — it is a bubble and a crash** | Gold went $2,277 → a peak of **$5,626.80 (2026-01-28 23:00 UTC)**, then fell **−29.7% to $3,955**, ending at $4,702. Single 1h bars reached **$399 of range**. This is not a benign uptrend that merely flatters longs; it is a regime sequence (grind up → parabola → crash → range) in which *every* strategy family gets a period where it looks brilliant. Fitting on the whole window averages four incompatible regimes into one number. | Rolling 60-day return and rolling ATR/price. The parabola and the crash are visible in both. | Report every result split into at least three date blocks (pre-parabola, parabola+crash, post-crash) and require sign agreement. A strategy positive only in one block is a regime bet, not an edge. | Add a date-block split to `study.py` alongside walk-forward, and print the per-block expectancy for every candidate. | **MEASURED** `[ours]` |
| GX-05 | **Spot gold has no central exchange** | XAUUSD is an OTC broker-constructed price. There is no consolidated tape, no true "the" high or low, and the broker is often the counterparty. Wick-triggered strategies are maximally exposed to this. | Inter-broker price and wick disagreement. | Prefer strategies whose trigger is a *close* (agreed across feeds) over strategies whose trigger is an *extreme tick* (feed-specific). **Note: this directly disadvantages the entire sweep family.** | Diff two feeds' 15m bars; count how many sweep signals appear on one and not the other. | **PLAUSIBLE**, mechanism structurally certain |
| GX-06 | **Volatility clustering vs ATR lag** | ATR is a lagging average. In a volatility expansion, an ATR-scaled stop is sized for the *previous* regime and is too tight; in a contraction it is too wide and over-risks. | Ratio of current bar range to ATR14. | Reject entries where the signal bar's range exceeds ~2.5× ATR (regime has already changed and the stop is mis-sized). | Bucket outcomes by (bar range / ATR) and check whether realised risk exceeds planned risk in the top bucket. | **PLAUSIBLE**, cheap to test on data we hold |
| GX-07 | **Correlation anchors (DXY, real yields) break exactly when it matters** | Gold's inverse-DXY relationship is a tendency, not a law, and it inverts during flight-to-safety when both rise together. A confirmation filter built on DXY will confirm loudest just as it becomes wrong. | Rolling correlation of gold and DXY; its instability is the signature. | Do not use cross-asset confirmation as a hard gate. We also have no DXY data, so this is currently unbuildable. | Would require DXY data we do not have. Record as blocked. | **REPORTED**, blocked by data availability |
| GX-08 | **Unscheduled geopolitical risk** | Gold is the primary safe-haven instrument, so it reprices on events that have no calendar entry. No filter can anticipate these. | None ex-ante. | This is unhedgeable event risk. Its only management is position size and not holding oversized positions overnight. | n/a — accept and size for it. | **REPORTED** |
| GX-09 | **Overnight financing on gold is material** | Gold swap rates are typically larger than major FX pairs. A strategy that holds positions across sessions pays a cost absent from every backtest in this repo. | The broker's swap table, readable today. | Add swap to the cost model before any multi-session strategy is believed. | Add `swap_per_night` to `engine.Costs`; re-run all multi-day candidates. | **PLAUSIBLE** (magnitude unknown; the omission is certain) |
| GX-10 | **Prop firms treat gold as a USD instrument for news rules** | XAUUSD is on the USD-affected list at FTMO and similar firms, so US data releases restrict gold trading even though the trader may think of gold as a commodity. | The firm's affected-instrument list. | Treat gold as a USD pair for all rule purposes. | Read the specific firm's rule text before funding. | **MEASURED** (rule text explicit) |

---

## TOP 10 FAILURE MODES BY EXPECTED COST

Ranked by (probability it applies to this system) × (R cost when it does). Where I
have a measured magnitude I use it; where I do not, I say so.

**1. LS-01 — the long sweep setup on gold is a continuation signal (−8.9pp vs baseline).**
The largest single measured effect in this file, and it points the *opposite way to
the strategy's core thesis*. It is worth roughly 9 percentage points of win rate on
the long side, against a cost tax of 5pp. z = +6.95 on 1h, +8.1pp on 15m, and **+7.0 to +9.7pp with
|z|>3 in each of three disjoint date blocks** spanning a grind, a parabola and a
29.7% crash. If this holds, half the intended system is not merely edgeless, it is
anti-correlated with its own premise. Cost: catastrophic — it invalidates a
direction, not a parameter.

**2. PF-06 — the correct strategy design and the prop account design are opposed.**
E-008 proves profit comes from a skewed tail (median MFE 1.12R, p90 7.51R). Prop
rules — daily limit, trailing drawdown, consistency cap — all penalise skew. This is
not a rule to add; it is a contradiction to resolve consciously. Left unresolved it
guarantees eventual failure regardless of edge. Cost: total account, repeatedly.

**3. PR-02 / PF-03 — early break-even, now doubly penalised.**
Measured at −0.161R to −0.308R across four markets, the worst exit rule tested on
every one. Under trailing drawdown it is worse still, because it raises the floor
without banking the profit. It is also the exact instinct Veer's EA was built
around. Cost: 0.2–0.4R per trade, plus account-level.

**4. M1-01 / M1-02 — M1 cost geometry on gold.**
A round trip is ~28.7% of a median M1 bar's entire range (fitted H = 0.554), and
21.4% of risk on a 1.4×ATR M1 stop. This is arithmetic, not opinion, and it already
destroyed one 748-parameter EA where the spread bill was 48% of the loss. Cost:
guaranteed negative expectancy; no entry quality can overcome it.

**5. LS-08 / LS-09 — the quality filters do not replicate.**
Every one of displacement, trend regime and session flipped sign between 1h and 15m
gold, four of them with |z| > 2 on both sides. This is the mechanism by which
"sophisticated" versions look better than naive ones: more filters, more trials,
more chances to find noise. Cost: the entire research programme, if not controlled —
this is how you spend six months building E-006 again.

**6. PF-01 / PF-05 — loss clustering vs the daily limit.**
22.3% of trading days lose more than 2R, 7.8% lose more than 3R, worst day −6.07R,
longest streak 16 trades, peak drawdown 59.8R on a strategy with +0.81R total. At 1%
risk/trade the 5% daily limit is 5R and gets breached. Risk-per-trade, not strategy
selection, is the dominant variable. Cost: account termination on a positive-
expectancy system.

**7. BT-02 — spread sensitivity.**
E-003 goes +0.001R → −0.061R at 3× spread. The strategy's entire result sits inside
the cost error bar, and gold's spread reliably triples exactly when sweeps happen.
Cost: converts a null into a loser, which is the difference between wasting time and
losing money.

**8. PR-01 / PR-03 — give-back is normal and winners need room.**
42.6% of gold 1h paths that reach +1R still stop out; 40.2% of winners first go 0.5R
against. Any rule designed to prevent give-back necessarily removes winners. This is
the mathematical core of why "protect profits" destroys accounts. Cost: 0.2–0.4R per
trade if mishandled — and it is the most emotionally compelling mistake available.

**9. BT-07 / GX-04 — the sample contains a parabola and a crash, and contaminates everything.**
The sample runs $2,277 -> $5,627 (+147%) -> $3,955 (-29.7% from peak) -> $4,702, with
single 1h bars of up to $399 range. Every long-biased result is suspect, including,
in the other direction, the LS-01 finding above. Cost: unknown but systematic; it is
the reason E-004 was downgraded and it will claim more findings.

**10. NS-01 / NS-02 / PF-09 — news.**
Spread blowout, gapped stops (p90 gap 1.93 ATR, max 5.00 ATR), and a hard prop
breach if a stop merely *fills* inside FTMO's ±2 minute window on gold. The first
two cost money; the third costs the account outright for doing nothing wrong. Cost:
occasional but severe, and one of the few that can end an account in one event.

*Just outside the top 10:* NS-05 (hour-of-day expectancy as an overfitting trap,
+0.652R to −0.647R across hours on n≈20–50) and LS-14 (hindsight selection —
7,686 sweep events occurred on gold 1h in 2.4 years; every course shows the same
dozen charts).

---

## WHICH OF THESE THE NAIVE IMPLEMENTATION PROBABLY HIT

E-003: `liquidity_sweep`, GOLD 1h, 603 trades, +0.001R, PF 1.00, 3/6 folds.

**Almost certainly hit — and these explain the result without any need to blame the code:**

| ID | Why | Evidence |
|---|---|---|
| **LS-01** | It took long setups into a −8.9pp headwind. Its measured long expectancy was −0.018R against short +0.054R — the sign and the ordering both match. | `[ours]` |
| **LS-03** | It compared itself to break-even rather than to gold's own drift baseline. Its +0.001R "null" is actually a null *relative to zero*, which is a different and weaker claim than a null relative to the instrument. | `[ours]` |
| **LS-18** | It needed ~5pp of edge to pay the spread. The largest documented level effect in the literature is 3.4pp. It was arithmetically short before it started. | computed |
| **BT-02** | −0.061R at 3× spread. Sweeps happen in volatility; volatility is when spread triples. Its realised live cost would exceed its tested cost. | repo E-003 |
| **LS-15 / PF-01** | 22.3% of its trading days lost >2R and it produced a 16-trade losing streak and a 59.8R drawdown — on a strategy that netted +0.81R. It was never a viable funded-account candidate at any risk level. | `[ours]` |
| **PR-09** | 38.8% of its losers never reached +0.3R. Those are entry failures; no exit rule can rescue them. | `[ours]` |
| **GX-04** | Tested across a +147% parabola AND a −29.7% crash, averaged into one expectancy. Its 3/6 walk-forward folds are consistent with a strategy whose sign depends on regime. | `[ours]` |
| **NS-05** | Its hourly expectancy ranged +0.652R to −0.647R on samples of 16–52. Any session filter fitted to that would have been noise. | `[ours]` |

**Probably did NOT hit (to its credit — these are things it got right):**

- **BT-01** — the engine's ties-lose rule handles intrabar ambiguity conservatively.
- **BT-08** — pivots are confirmed before use (`right=3`), so no look-ahead.
- **PR-02** — it used a fixed 2R target, not a break-even trail. The worst exit rule was not in play.
- **BT-06** — the repo already applies multiple-testing correction.

**The honest conclusion.** E-003's null is over-determined. At least four independent
mechanisms — a wrong-signed long thesis, a cost hurdle larger than any documented
effect, spread sensitivity, and a contaminated sample window — each individually
predict a null or negative result. The implementation was not the problem, and a
more sophisticated implementation of the same thesis on the same instrument does not
address a single one of these four. **That is the answer to "what separates the naive
version from the sophisticated version": on this evidence, the sophisticated version
differs only in how many hypotheses it silently tests.**

---

## WHAT IS TESTABLE WITH THE DATA WE ALREADY HAVE

We hold: `GOLD_1h` (13,750 bars, 2024-04-02 → 2026-08-24), `GOLD_15m` (4,501 bars,
2026-06-14 → 2026-08-24), plus EURUSD / GBPUSD / US500 at 1h and 15m. No tick data,
no M1, no M5, no volume, no economic calendar, no spread history.

### Testable NOW with 15m / 1h gold (no new data)
LS-01, LS-03, LS-04(partial), LS-06, LS-07, LS-08, LS-09, LS-11, LS-12, LS-15,
LS-16, LS-20 · PR-01, PR-03, PR-04, PR-06, PR-07, PR-08, PR-09, PR-10 ·
BT-01, BT-02, BT-03, BT-06, BT-07, BT-08, BT-09 · PF-01, PF-02, PF-03, PF-04,
PF-05, PF-06, PF-11, PF-12 (all via `prop_sim.py`) · NS-03, NS-05, NS-06, NS-07,
NS-08 · GX-01, GX-02, GX-04, GX-06

That is **44 of the ~70 modes**, testable today with zero new data. The M15 sample
is only 70 days, which is the binding constraint on most of them.

### Needs longer M15 history (2+ years) — the single highest-value data request
Everything above, re-run for statistical power. Specifically: LS-01's replication
(currently 15m n=495 on a period that overlaps the 1h sample, so **not an
independent confirmation**), all of LS-08/LS-09's sign-stability tests, and every
walk-forward fold count. **This is the #1 data ask: 2+ years of M15 XAUUSD.**

### Genuinely NEEDS M1 / tick data
- **M1-01** — the 28.7% figure is an *extrapolation* from a fitted H=0.554, not a measurement. It must be confirmed on real M1.
- **M1-04, M1-05, M1-07** — M1 structure density, serial dependence, data quality.
- **BT-01 at scalping geometry** — same-bar ambiguity is 0.22% at 1R/3R on 1h; it will be far higher when stop and target are minutes apart. Only tick data settles it.
- **LS-05** — entry-timing A/B (reclaim close vs next-bar confirm) needs sub-15m resolution to be meaningful.
- **BT-05, M1-06** — latency and fill realism need live/demo logs, not history.

### Needs data we cannot get in this container at all
- **NS-01, NS-04, NS-09, PF-09** — need an economic calendar. Currently substituted with an hour-of-day proxy, which is weaker.
- **BT-04, LS-17, GX-03, GX-05** — need a second broker feed and a recorded live spread series.
- **GX-07** — needs DXY / real-yield data.
- **GX-09, BT-10** — need the broker's swap table.

### The cheapest high-value measurements Veer could make this week
1. **Record XAUUSD spread every second for two weeks on MT5, including one NFP.** This single file settles NS-01, GX-03, and calibrates every cost model in the repo. Nothing else in this document is as cheap or as decisive.
2. **Export 2+ years of M15 XAUUSD** from MT5. Unblocks 44 failure modes' worth of statistical power.
3. **Export the broker's contract spec and swap table.** Settles BT-11 and GX-09.

---

## SOURCES

**Primary academic (all `[2nd-hand]` — the PDF hosts are blocked from this container)**
- Osler, C. (2003) *Currency Orders and Exchange Rate Dynamics*, J. Finance 58(5). Order book of one dealing bank, Aug 1999–Apr 2000, 9,655 orders. TP orders cluster *at* round numbers (~9.8%), SL orders cluster *just beyond* (~4.3%); round-number bounce frequency +~3.4pp.
- Osler, C. (2005) *Stop-loss orders and price cascades in currency markets*, J. Int. Money & Finance 24(2) 219–241. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=920687 · https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.pdf — **stop-loss response is larger and longer-lasting than take-profit response; stop-losses propagate trends (continuation), take-profits cause reversals.** This is the load-bearing citation for LS-01/LS-02.
- Bailey, D. & López de Prado, M. (2014) *The Deflated Sharpe Ratio*. https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf — multiple-testing correction; BT-06.
- Bailey, Borwein, López de Prado, Zhu, *The Probability of Backtest Overfitting*. https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
- Mesfin, M. (2026) *Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures: A Systematic Falsification Study*. https://arxiv.org/abs/2605.04004 — 14 signal families, 947 days of 5-minute MNQ, 2021–2025, 2-point round-trip friction. **None passed.** Max gross return per trade 0.07–1.50 points, below the 2-point friction cost.
- Darmanin, A. (2026) *Retail Trader's Ruin: An Anatomy of Popular Signal Failure*. https://arxiv.org/abs/2607.20093 — five retail signal families through pre-declared gates (multiplicity-corrected significance, economic viability after cost, finite-bankroll survival). **Four of six REFUTED**; trend inconclusive.
- Barber & Odean (2000) *Trading is Hazardous to Your Wealth*, J. Finance. 66,465 accounts 1991–96; most active traders 11.4%/yr vs 17.9% market. Cost drag, not signal quality. → M1-03.

**Practitioner / industry (all carry an incentive — noted)**
- Prop-firm statistics aggregators (affiliate-monetised; treat as indicative): pass rates 5–14%, ~7% of entrants ever paid, ~71% of phase-1 failures from daily drawdown, 20–30% trailing drawdown, 10–15% consistency rule. https://www.quantvps.com/blog/prop-firm-statistics · https://thepropfirmguide.com/prop-firm-statistics/ · https://damnpropfirms.com/trading-guides/prop-firm-evaluation-pass-rates-statistics-reality-check/
- Trailing drawdown mechanics, intraday vs EOD high-water mark: https://fundedtrading.com/max-trailing-drawdown-prop-firms/ · https://copilink.com/articles/trailing-drawdown-explained-eod-vs-intraday
- Consistency rule mechanics (30–45% best-day cap): https://funded.now/guides/consistency-rule-explained · https://thortradecopier.com/blog/prop-firm-consistency-rules-explained
- FTMO news rule (±2 min, XAUUSD on the USD-affected list): https://propfirmcircle.com/blog/ftmo-news-trading-rules · https://propvator.com/blog/is-news-trading-allowed-in-ftmo/
- Broker tick-data quality (broker feeds <60% vs Dukascopy 99.9%): https://www.mql5.com/en/forum/287982 · https://www.earnforex.com/guides/quality-metatrader-historical-data/
- Same-bar stop/target ambiguity: https://www.tradingview.com/blog/en/accurate-backtesting-with-bar-magnifier-31746 · https://algorithmicfutures.substack.com/p/backtesting-look-inside-the-bar-backtesting
- Execution latency (VPS vendors — direct incentive to overstate): https://www.vpsforextrader.com/blog/scalping-day-trading-technique/
- XAUUSD spread and news behaviour (broker-affiliated, figures mutually inconsistent — this is why NS-01 is REPORTED and not MEASURED): https://tradingbeasts.com/what-is-the-average-spread-on-xauusd/ · https://www.pro-scalper.com/xauusd-strategies/news-trading-gold
- Liquidity-sweep vendor content, cited only as evidence of what is *claimed*, never as evidence of what is *true* (every one sells brokerage, indicators or courses): https://www.luxalgo.com/library/concept/liquidity-sweep/ · https://internationaltradinginstitute.com/blog/after-the-liquidity-sweep-confirm-reversal-continuation-or-no-trade/ · https://www.vantagemarkets.com/en-za/academy/liquidity-sweeps-and-stop-hunts-on-xauusd/ · https://dailypriceaction.com/blog/liquidity-sweep-reversals/
- The widely repeated "25–35% of confirmed sweeps fail" and "XAUUSD ~62% intraday fakeout" figures appear in vendor content with **no dataset, no sample size and no definition**, and could not be traced to any source in this session or in `findings/01_liquidity_evidence.md`. Classified **FOLKLORE**. Do not repeat them.

**This repository (the strongest evidence available, because it is reproducible)**
- `JARVIS/research/sweep_anatomy.py`, `microstructure_facts.py`, `failure_probes.py` — all numbers marked `[ours]`
- `JARVIS/state/EXPERIMENTS.md` — E-001 through E-008
- `JARVIS/research/findings/01_liquidity_evidence.md` — the prior adversarial evidence review
- `JARVIS/research/findings/06_exit_experiment.md` — exit-rule measurements
- `JARVIS/ea/AUDIT_v19_18.md` — the 748-parameter EA post-mortem

---

## STANDING CAVEATS ON THIS DOCUMENT ITSELF

1. **LS-01 is MEASURED and regime-robust, but still single-instrument.** It holds
   in 3/3 disjoint date blocks on gold 1h (+7.0 to +9.7pp, all |z|>3) and again on
   gold 15m — but the 15m sample (2026-06-14 → 08-24) sits *inside* block C, so it
   is a finer-resolution look at the same calendar time, not an independent sample.
   The effect is absent on EURUSD and US500, which could mean it is gold-specific
   or could mean it is gold-sample-specific. It is **MEASURED**, not **CONFIRMED**,
   until it is reproduced on gold data from outside 2024-2026.
2. **This file itself is a multiple-testing exercise.** Section A of
   `failure_probes.py` ran roughly 24 conditional slices per instrument. At the 5%
   level roughly one in twenty will look significant by chance. The results I have
   leaned on (LS-01 at z=6.95, and the *non*-replication of the filters) survive that
   correction comfortably; the individual filter results do not, which is precisely
   the point being made.
3. **No number in this file is a claim of profitability.** Every measured effect
   here is a conditional frequency with no cost model attached. A +8.9pp frequency
   effect is not an edge until it has been through `study.py`, walk-forward,
   Monte Carlo, cost sensitivity and a long/short split.
4. **The primary academic sources were not read.** Every paper citation is
   second-hand from search synthesis. If LS-01 becomes load-bearing for the system
   design, someone must open Osler 2005 and read it.

# 01 — Liquidity / stop-run concepts: adversarial evidence review

Research date: 2026-08-28. Scope: does the *concept* family behind
"liquidity sweeps / stop runs / smart money concepts" have measurable edge,
independent of the one implementation already tested in E-003?

**Method note, read this first.** Outbound network access in this session
allowed the search index and `raw.githubusercontent.com` only. Every academic
PDF host (arXiv, SSRN, ScienceDirect, NBER, NY Fed, university mirrors) was
blocked by the egress proxy. So: **I did not read the primary papers myself.**
Numbers attributed to papers below come from search-engine synthesis of
abstracts, citing papers and snippets. They are second-hand and are marked
`[2nd-hand]`. The two things I verified directly are (a) the GitHub replication
repo, read in full, and (b) my own arithmetic. Do not treat `[2nd-hand]`
figures as verified until someone opens the PDF. This limitation is stated
because the alternative — implying I read them — would be a lie.

---

## BOTTOM LINE

The *phenomenon* is real and the *trade* is not: order clustering near obvious
price levels is one of the better-documented facts in FX microstructure, but
every measured effect size found in this review is far too small to pay a
retail gold spread, and no rigorous public test — academic or otherwise — shows
a liquidity-sweep rule with positive net expectancy. The single hardest number
in the entire literature is Osler's own: round numbers raise the intraday
bounce frequency by **about 3.4 percentage points** `[2nd-hand]`, while a $0.30
gold round trip against a typical $2 stop raises the break-even win rate by
**5.0 percentage points** (computed below) — the documented edge is smaller
than the documented cost, before any of it is turned into a rule. Worse, the
retail narrative gets Osler backwards: her stop-loss result shows stops
*accelerate* moves through a level (positive feedback → continuation), so the
fade-the-sweep trade is not the thing her stop-loss paper supports. ICT/Smart
Money Concepts specifically has **zero** peer-reviewed support, is a renaming
of Wyckoff/Raschke/Steidlmayer material from 1902–1995, and its load-bearing
terms (displacement, valid inducement, "major" POI) are defined loosely enough
that they cannot be falsified — which is why no honest systematic test of the
full framework exists. Verdict: the underlying microstructure is **SUPPORTED**;
the retail trading system built on top of it is **FOLKLORE**, and E-003's null
result is the expected result, not bad luck.

---

## 1. Stop-loss clustering — the academic foundation

### What Osler actually found, on what data

| Paper | Data | Core finding |
|---|---|---|
| Osler 2000, *Support for Resistance* (FRBNY Econ Policy Review 6(2) 53–68) | S/R levels published by **6 firms**, Jan 1996 – Mar 1998; intraday DEM, JPY, GBP vs USD | Published S/R levels significantly predicted intraday trend *interruptions*; predictive power persisted ≥5 business days after publication `[2nd-hand]` |
| Osler 2003, *Currency Orders and Exchange Rate Dynamics* (J. Finance 58(5)) | Complete order book of a major dealing bank (RBS / NatWest Markets), **1 Aug 1999 – 11 Apr 2000**; **9,655 orders**, aggregate face **>$55bn**; USD/JPY, GBP/USD, EUR/USD. Bounce tests on **2,694 executed orders** | Take-profit orders cluster **at** round numbers (~**9.8%** at rates ending "00"); stop-loss orders cluster **just beyond** round numbers (~**4.3%** at "00") `[2nd-hand]`. Round-number bounce frequency exceeded arbitrary-number bounce frequency in **20 of 20** cases, significant at the 0.01% level; **mean increase ≈ 3.4 percentage points** `[2nd-hand]` |
| Osler 2005, *Stop-loss orders and price cascades in currency markets* (J. Int. Money & Finance 24(2) 219–241) | Same order book | Stop-loss executions generate **positive-feedback** trading; response is **larger** and **lasts longer** than take-profit executions; significant "for hours, although not for days" `[2nd-hand]` |
| Osler & Savaser 2011, *Extreme returns: the case of currencies* (J. Banking & Finance 35(11) 2868–2880) | Price-contingent order data | Price-contingent trading accounts for **over half** of realised excess kurtosis in currency returns `[2nd-hand]` |

### The three things this establishes — and the one it does not

**Established (PROVEN, as facts about that dataset):**
1. Retail-and-institutional stop and limit orders do cluster at obvious price
   levels. Not a conspiracy — a coordination effect. Everyone reads the same
   chart.
2. When a stop cluster is hit, the resulting order flow is real, measurable,
   and moves price more than an equivalent take-profit cluster.
3. This mechanically produces fat tails. Spikes into levels are not illusions.

**Not established:** that any of it is tradeable. Osler's papers are
descriptive microstructure. They report bounce *frequencies* and impulse
responses, not net-of-cost strategy returns. I found **no** paper by Osler or
anyone else claiming a profitable rule from stop clustering.

### The inversion nobody in the retail world mentions

Read the 2003 result carefully. It has two halves that point in **opposite
directions**:

- **Take-profit** orders cluster **at** round numbers → negative feedback →
  price *bounces* at the level. This is the reversal half.
- **Stop-loss** orders cluster **just beyond** round numbers → positive
  feedback → price moves *unusually fast once it crosses* the level. This is
  the continuation half — and Osler 2005 exists specifically to document that
  the stop-loss (continuation) effect is the *larger and longer-lasting* of
  the two.

The retail "liquidity sweep" trade is: price pierces the level, stops trigger,
**price reverses** — and the mechanism named is *stop hunting*. But Osler's
stop-loss mechanism predicts the opposite: crossing the level and running.
The reversal she documents comes from **take-profit** clustering, which is a
different order type sitting at a different price with a different sign.

So the folklore cites the stop-loss paper as its authority for a trade that
paper's mechanism argues against. If anything, Osler 2005 is better evidence
for **breakout continuation** (E-004 Donchian) than for fading sweeps (E-003).
That is a genuinely awkward fact for the whole liquidity-fade thesis and it
should not be glossed over.

### Has it been replicated on modern electronic markets?

**Partially, and weakly.** What I found:

- Price clustering at round numbers still exists structurally: an EBS order
  book study of EUR/USD and USD/JPY around a ten-fold tick-size reduction
  found a large fraction of limit orders placed at or halfway between old
  allowed prices, creating "price barriers" and peaks in book shape — but
  attributed **mainly to manual traders still set to the old resolution**
  (arXiv 1307.5440 / Physica A) `[2nd-hand]`. That attribution matters: it
  frames clustering as a *human habit artefact*, which algo execution erodes.
- Round-number clustering has been re-documented in cryptocurrency prices
  (Finance Research Letters 2022) and in cryptocurrency order books (JBEF
  2024) `[2nd-hand]` — i.e. the effect reappears in whatever market is newest
  and most retail-dominated, which is consistent with it being a
  behavioural-coordination effect rather than a permanent structural one.
- Psychological barriers in exchange rates persist but are **regime-dependent**
  and modulated by central-bank intervention (J. Int. Financial Markets 2025,
  COP/USD, 50 years of daily data) `[2nd-hand]`.

**Could NOT find:** any post-2010 study replicating Osler's *order-book*
clustering result on a modern electronic FX venue with actual stop/limit order
data. Dealer order books stopped being available to researchers. This is a
real evidentiary hole: the foundation of the whole edifice is one bank's book
from a **9-month window in 1999–2000**, before algorithmic execution, before
MiFID, before the machine-readable retail broker era. It has never, as far as
I can find, been re-run on modern data.

### Is it tradeable by retail after costs?

Arithmetic, computed here (`p_breakeven = (1 + c) / (RR + 1)`, where `c` is
round-trip cost expressed in units of 1R risk). Gold round-trip spread $0.30,
the default in `JARVIS/research/engine.py:152`:

| Stop distance | cost c (× risk) | break-even win% @ RR2 | @ RR3 | cost tax vs zero-cost (RR2) |
|---|---|---|---|---|
| $0.50 | 0.600 | 53.3% | 40.0% | +20.0 pp |
| $1.00 | 0.300 | 43.3% | 32.5% | +10.0 pp |
| $2.00 | 0.150 | 38.3% | 28.7% | **+5.0 pp** |
| $3.00 | 0.100 | 36.7% | 27.5% | +3.3 pp |
| $5.00 | 0.060 | 35.3% | 26.5% | +2.0 pp |
| $10.00 | 0.030 | 34.3% | 25.8% | +1.0 pp |

At 3× spread ($0.90 — news, rollover, thin hours, which is exactly when sweeps
happen): a $2 stop needs **48.3%** at RR2; a $1 stop needs **63.3%**.

**Put the two numbers side by side.** Documented level effect: ~**3.4 pp** of
extra bounce frequency `[2nd-hand]`. Cost tax on a normal gold intraday stop:
**5.0 pp**, rising to 10–20 pp on tight stops and 3× on spread widening. The
published effect does not cover the spread. And that 3.4 pp is measured on
*round numbers in 1999 FX*, with perfect hindsight knowledge of which level to
watch and no entry rule, no stop, no slippage, and no signal-selection loss.
A real rule can only do worse than the raw statistic.

This is the single most important paragraph in this document. It explains
E-003's +0.001R without needing to blame the implementation.

**Verdict: clustering = PROVEN (1999–2000 FX). Tradeability by retail =
DISPROVEN by arithmetic, and consistent with E-003's measured null.**

---

## 2. ICT / Smart Money Concepts — the honest evidence

### What I searched for and did not find

I searched specifically for systematic tests with sample sizes and net returns
of: liquidity sweeps, order blocks, fair value gaps, CISD, displacement,
breaker blocks, killzones, Silver Bullet, quarterly theory.

**Peer-reviewed papers testing any ICT/SMC construct: zero.** Not "few" —
none surfaced across a dozen query formulations. The term set does not appear
in the finance literature at all. Everything returned was vendor content
(LuxAlgo, TradingView scripts, broker blogs, Udemy), Medium posts, or YouTube.

**Claims found, and why none of them count:**

| Claim | Source | Why it is not evidence |
|---|---|---|
| "2,600 trades, 26 months, 10 assets incl. Gold/BTC/EURUSD/NAS100" | Medium (`@QuantumAlgo`) | No methodology, no code, no cost model, no walk-forward, no out-of-sample. Blocked from reading. Unreproducible by construction. |
| "win rate exceeds 65% when OB+FVG overlap with HTF bias" | vendor blog | Win rate without R:R is meaningless — E-002 in this repo *proves* that: 69.5% win rate, **−0.066R** expectancy. |
| "rule-based SMC entries: 50–65% win rate, PF >1.5" | vendor blog | Same problem, plus no sample size and no costs. |
| "Silver Bullet 70–80% win rate" | multiple vendor blogs | Contradicted by the same sources admitting results "vary widely" pre-2023 and that some months are "abysmal" — i.e. it is a 2023 in-sample artefact. |
| "70% of breakouts fail; XAUUSD ~62% intraday, EURUSD ~58%, NQ ~54%, BTC ~65%" | trading blog | **Could not trace to any source.** No dataset, no definition of "fail", no paper. Treat as invented until someone produces the data. Flagged because it is the kind of precise-sounding number that gets repeated into fact. |

### Are the concepts falsifiable?

**Partly — and the falsifiable parts are the ones nobody claims edge for.**

- Falsifiable and codeable: FVG (a 3-bar non-overlap is an exact geometric
  condition), sweep-and-close-back (E-003 already codes this), break of
  structure relative to a fixed pivot definition.
- **Not** falsifiable as stated: "sufficient displacement", "valid inducement",
  "major POI", "the algorithm delivered price to a premium array". The
  strongest criticism found puts it precisely: the subjective components
  *prevent* systematic testing, and the grand narrative ("an algorithm controls
  all price movement") is unfalsifiable because any outcome confirms it.

That asymmetry is the tell. The parts that can be tested are old and generic;
the parts that carry the claimed edge are the parts that resist definition.

### Strongest quant criticism found

1. **Provenance.** ICT concepts are documented renamings: order blocks ≈
   supply/demand zones; liquidity sweeps ≈ Wyckoff spring/upthrust (1930s) and
   Raschke's Turtle Soup (1995); FVG ≈ Steidlmayer's Market Profile "single
   prints" (1985) and Al Brooks' micro-gap (~2009); breaker/mitigation ≈ Dow
   (1902) + Wyckoff composite operator. If the mechanism were real and new, the
   30-to-90-year-old originals would have produced a documented track record by
   now. They did not.
2. **Survivorship / outlier manufacture.** With millions of people running SMC,
   the *expected* number of multi-year profitable sequences from a zero-edge
   system is large. Every visible "SMC millionaire" is drawn from that pool.
   The screenshots are a sampling artefact of the population size, not evidence
   about the method.
3. **The manipulation narrative lacks order-flow support.** Failed breakouts
   and sweeps are fully explained by thin books at extremes, momentum cascades
   (which is exactly Osler 2005), and ordinary supply/demand resolution. No
   order-flow study demonstrates institutions targeting retail stops as a
   deliberate strategy. "Search for liquidity" and "hunting you personally"
   produce identical charts; only one is testable, and it is the boring one.
4. **The direct systematic test that does exist, fails.** See below — it is the
   most important single citation in this document.

### The one rigorous test that includes this family: it failed

**Mesfin, *Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures: A
Systematic Falsification Study* (arXiv 2605.04004, 2026)** `[2nd-hand]`

- Data: **947 trading days**, 5-minute MNQ futures, **2021–2025**.
- **14 signal families**, explicitly including **liquidity-grab reversals**,
  opening-range breakouts at multiple horizons, gap continuation/fade, volume
  signature, cross-session (Asia) momentum, volatility-regime classifiers,
  news-driven directional.
- Uniform bar: out-of-sample **walk-forward**, **t ≥ 2.0**, **≥30 trades**,
  positive net return after a fixed **2-point round-trip friction**, and
  consistency across years.
- Result: **none of the 14 families satisfied all requirements.** Maximum gross
  return before costs ranged **0.07 to 1.50 points per trade** — every one of
  them *below the 2-point friction*.
- Author's framing: single-bar directional signals from public OHLCV do not
  generate economically significant edge at 5-minute resolution.

Read that last line again. The gross edge, before costs, on the best of
fourteen families, was **at most 75% of the cost of trading it**. That is the
same shape as E-003 (+0.001R gross-ish, negative as costs rise) and the same
shape as the ORB replication below. Three independent tests, one pattern.

**Verdict: ICT/SMC as a system = FOLKLORE.** Its individual geometric
primitives are codeable and worth testing as hypotheses; its narrative,
its precision claims, and its win-rate marketing are not evidence.

---

## 3. Turtle Soup / failed breakout — the pre-ICT lineage

Connors & Raschke, *Street Smarts: High Probability Short-Term Trading
Strategies* (1995), Chapter 1. Rule (long): market makes a new 20-bar low; the
**previous** 20-bar low was made **at least 4 bars earlier**; buy on a reclaim
back above the prior 20-bar low. "Plus One" allows the reclaim one session
later. This is, structurally, exactly the E-003 signal with a Donchian level
instead of a fractal pivot — **the identical idea, 30 years earlier, under a
different name.**

**Evidence found:** thin and vendor-tier.
- "Profit factor **1.86**, backtest 2000–2020" — cited without instrument,
  trade count, cost model, or parameter-selection disclosure. Untraceable.
- "~60% win rate on currency pairs, GBP/USD ~60.5%" — same problem, and again
  a win rate with no R:R attached, which E-002 shows is uninformative.
- An MQL5 implementation article concludes profitability "depends on the
  applied filters" — which is a polite way of saying the raw pattern did not
  work and needed help.
- Connors & Raschke themselves illustrated it with charts that were already
  old at publication; no published forward test by the authors.

**Could NOT find:** a single peer-reviewed or independently reproducible
systematic test of Turtle Soup with trade count, costs and out-of-sample
validation. For a pattern published in a famous book in 1995, 31 years of
silence is itself informative.

**Verdict: PLAUSIBLE-BUT-UNTESTED, leaning REJECTED.** The lineage point is
the useful one: this is not a new discovery ICT made in 2015. It is a 1995
pattern that never produced a documented track record, renamed. E-003 has now
tested a variant of it on gold and got +0.001R. That is 31 years of the same
answer.

---

## 4. What has better evidence

Ranked by evidence quality, with the retail-cost verdict attached. This is
where the effort should go.

### 4.1 Time-series momentum / trend following — the strongest, but slow

- Moskowitz, Ooi & Pedersen 2012, JFE 104(2) 228–250: **58 liquid futures**
  (equity index, currency, commodity, bond). **All 58** showed positive TSMOM;
  **52 of 58** significant at 5%. Diversified portfolio Sharpe **>1.0**,
  ~2.5× the equity market `[2nd-hand]`.
- Hurst, Ooi & Pedersen, *A Century of Evidence on Trend-Following*: Sharpe
  **≈0.4 in every decade, 1880–2016** `[2nd-hand]`. Survived the Depression,
  wars, and 140 years of publication.
- **The honest caveat:** documented decay. Superior performance "vanishes in
  the post-crisis period 2009–2013" `[2nd-hand]`; most of the 2008-era
  improvement was crisis-specific.
- **Timescale caveat:** all of this is daily-to-monthly. It says nothing about
  1h gold, where cost/risk is 20× worse.
- **Repo link:** E-004 (Donchian, +0.198R, 5/6 folds, survives 3× spread,
  t = +1.63) is a member of this family. That is not a coincidence, and it is
  the reason E-004 outperformed E-003.

**Status: SUPPORTED at daily+ horizons. The best-evidenced thing available.**

### 4.2 Opening range breakout — and the best cautionary tale in this document

- Zarattini, Barbon & Aziz (SSRN 4729284): **>7,000 US stocks, 2016–2023**;
  top-20 "Stocks in Play" portfolio, net performance **>1,600%**, Sharpe
  **2.81**, annualised alpha **36%** `[2nd-hand]`. Base ORB without the
  Stocks-in-Play filter: **$7,500 profit on $25,000, 3.2%/yr, Sharpe 0.48**
  `[2nd-hand]` — note the filter is doing nearly all the work.
- **Independent replication I read in full**
  (`github.com/giovannibrusco/zarattini-2023-orb-qqq`, verified directly):
  - Replicated the QQQ 5-min ORB paper closely: **1,775 trades** (paper 1,795),
    **Sharpe 1.06** (paper 1.12), net PnL **$138,639** — *assuming zero
    slippage, which is the paper's own stated assumption*.
  - Add **$0.02/share** slippage: net PnL collapses to **$4,860**, t-stat
    **0.52**, Sharpe **0.23**, max DD **43.9%**.
  - Break-even slippage: **~2.2¢/share**. QQQ's spread is ~1¢. **"The edge
    lives inside the bid-ask spread."**
  - Best variant (NQ 09:25 confirmation filter): $0.125/share, per-trade
    **t = 2.05** — significant per trade, but strategy Sharpe **0.77** vs
    buy-and-hold **0.72**, bootstrap 95% CIs **[0.05, 1.41]** vs
    **[−0.03, 1.47]**, heavily overlapping. *A significant per-trade edge is
    not a significant strategy.*
  - **76% of the filtered PnL is 2022 alone.** Negative in 2017, 2020, early
    2023.
  - The repo also flags the original authors run day-trading education
    businesses.

**This is the template for how a published intraday edge dies**: assume zero
slippage → headline number; add one cent → nothing; and what survives is one
volatility regime. Every claim in section 2 should be read expecting this.

**Status: PROMISING gross, UNPROVEN net, regime-dependent.**

### 4.3 Market intraday momentum

Gao, Han, Li & Zhou 2018, JFE 129(2) 394–414: SPY, **1993–2013**; the first
half-hour return predicts the last half-hour return, statistically and
economically significant, **stronger on high-volatility days, high-volume days,
recession days and macro-news days**; replicates on 10 other actively traded
ETFs `[2nd-hand]`. **Status: SUPPORTED for US equity ETFs.** Untested on gold
by me; the conditioning result (volatility/volume/news) is the transferable
part and is cheap to test.

### 4.4 Overnight vs intraday

Lou, Polk & Skouras 2019, JFE: hedge portfolio sorted on past-month overnight
returns earns **−3.24%/month intraday, t = −9.34**; sorted on past-month
intraday returns, **+2.19%/month, t = 6.72** `[2nd-hand]`. Enormous t-stats —
but these are **cross-sectional long/short equity portfolios**. Not
implementable on a single XAUUSD MT5 account. **Status: SUPPORTED but not
applicable.**

### 4.5 Short-horizon mean reversion — REJECTED for retail

Avramov, Chordia & Goyal: reversals are strongest in high-turnover, illiquid
stocks, and **contrarian profits are smaller than the likely transaction
costs** `[2nd-hand]`. The effect is real and specifically not harvestable by
anyone paying retail costs. Do not spend time here.

### 4.6 Volatility regime — contested

Moreira & Muir: vol-managed portfolios add **~0.15 Sharpe** `[2nd-hand]`. But
Cederburg, O'Doherty, Wang & Yan (2020), on **103 equity strategies**: "no
statistical or economic evidence" of systematically higher Sharpe; Barroso &
Detzel (2020): does not survive transaction costs `[2nd-hand]`. **Status:
UNPROVEN.** Useful as a *filter* (see 4.3, where high-vol days help), not as a
standalone edge.

### 4.7 XAUUSD-specific anomalies

- **Real and documented, but dead:** Caminschi & Heaney 2014, *Fixing a Leaky
  Fixing*, J. Futures Markets — around the London PM gold fixing, GC futures
  and GLD showed elevated volume and volatility **before** the fix result was
  published, statistically significant return advantages in the **4 minutes**
  after the fix started, and trades in the opening minutes were predictive of
  the fix direction **in some cases exceeding 90%** `[2nd-hand]`. No effect
  *after* publication. This is genuine, published, gold-specific edge — and it
  was an **information-leakage** edge available to fixing participants, not a
  chart pattern. The research contributed to the fixing being replaced by an
  electronic auction; the anomaly was regulated out of existence. Perfect
  illustration that a documented gold anomaly can be real, large, and still
  useless to you.
- **Everything else I found is blog-tier:** "January +5%, 80% positive",
  "September negative 90% of years", Dimitri Speck's averaged minute-data PM-fix
  drift. No peer-reviewed source, no multiple-testing correction, sample sizes
  of ten. Ten Januaries is not a sample. **Status: FOLKLORE until computed
  in-house on our own data.**

**Could NOT find:** any peer-reviewed XAUUSD-specific intraday anomaly that is
still live and accessible to a retail account.

---

## 5. The measurement problem — codeable definitions

The concept only becomes testable when every term is arithmetic. Below,
`i` is the signal bar, all quantities use data available **at or before the
close of bar i**, and entry is at `open[i+1]` — which is what
`JARVIS/research/engine.py:214` already does. Good.

### 5.1 Level construction (must be causal)

```
SwingHigh(j) is true iff  high[j] == max(high[j-L : j+K+1])  and unique
A pivot at bar j is USABLE only from bar i >= j + K.
```
This is what `swing_points()` in `strategies.py:39` already implements, and it
is **correct** — I checked it. It appends a pivot from bar `j = i - right` only
at bar `i`. **E-003 is not a repainting artefact.** Its null is real.

Alternative level families worth testing separately (R-003), each strictly
causal:
- `PDH/PDL` — prior completed day's high/low. Known at the day boundary. Zero
  lookahead risk, zero parameters. **Test this first.**
- `PWH/PWL` — prior completed week's high/low.
- `ASIA_H/ASIA_L` — high/low of a fixed UTC window (e.g. 00:00–07:00),
  usable only after the window closes.
- `EQH/EQL` — n≥2 pivots within `tol × ATR` of each other ("equal highs").
  Parameter: `tol` (start 0.10).
- `ROUND(k)` — nearest multiple of $k (k ∈ {5, 10, 25, 50}). This is the level
  family Osler actually measured. It has never been tested in this repo and
  it is the only one with a published effect size to compare against.

### 5.2 Sweep — three tiers of strictness

Let `L` be a usable level, `A = ATR(14)[i]`, `rng = high[i] - low[i]`.

**Tier 1 — penetrate-and-reclaim (this is E-003):**
```
SWEEP_LONG(i, L) :=
    low[i]  <  L                              # penetrated
and close[i] >= L                             # reclaimed by the close
and (close[i] - low[i]) / rng >= 0.50         # rejection is most of the bar
```

**Tier 2 — add a materiality floor** (removes ties/noise-grazes, which is
probably a large fraction of E-003's 603 trades):
```
and (L - low[i]) >= pen_min * A               # pen_min ∈ {0.10, 0.25, 0.50}
and (L - low[i]) <= pen_max * A               # pen_max ∈ {1.0, 2.0}: too deep = real break
```

**Tier 3 — add displacement (make "displacement" arithmetic, not vibes):**
```
DISPLACEMENT(i) := |close[i] - open[i]| >= disp_k * stdev(|close-open|, 50)
                   with disp_k ∈ {1.5, 2.0, 3.0}
```
Reject the setup unless the reclaim bar (or bar i+1, *charged as a delayed
entry*) displaces. This is the only honest way to encode "displacement": a
z-score against a rolling baseline. Any definition that requires you to
eyeball "an aggressive candle" is not a definition.

### 5.3 Fair value gap — exact, no ambiguity

```
BULL_FVG(j) := low[j+1] > high[j-1]     # 3-bar non-overlap, known at close of j+1
gap_size(j) := low[j+1] - high[j-1]
Material iff gap_size >= fvg_k * A,  fvg_k ∈ {0.15, 0.30, 0.50}
```
An FVG is causal and exact. There is no excuse for a repainting FVG. The
testable base-rate question — *what fraction of FVGs are filled within N bars,
and is that different from a matched random-gap null?* — is a two-hour job and
has, as far as I can find, never been published with a proper null.

### 5.4 Sweep vs. normal breakout, without hindsight

This is the crux, and the honest answer is: **at the moment of penetration you
cannot tell.** The distinction is defined by what happens next, which is the
definition of hindsight. The only non-hindsight separators available at bar `i`
are *conditioning variables*, and each is a testable hypothesis, not a fact:

| Separator | Codeable at bar i | Status |
|---|---|---|
| Close-back-inside on the same bar | yes (Tier 1) | tested, E-003, null |
| Penetration depth in ATR | yes (Tier 2) | untested |
| Bar range vs rolling range (displacement) | yes (Tier 3) | untested |
| Tick volume vs 20-bar mean (the "1.5–2×" folk rule) | yes | untested; the folk threshold is unsourced |
| Time of day / session | yes | untested (R-003) |
| Distance from a scheduled news release | needs a calendar feed | not built (R-004) |
| Higher-timeframe trend agreement | yes (`htf_trend`) | already in E-003 |

**The falsifiable framing:** if "sweep" is a real category distinct from
"breakout", then conditioning on these variables must produce a *monotone*
relationship with forward return. If depth, displacement and volume all move
the expectancy around randomly, the category is not real — it is a label
applied after the outcome is known.

### 5.5 Repainting risk in typical implementations

Where these strategies actually cheat, in descending order of frequency:
1. **Pivot placement.** TradingView's own docs describe the standard failure:
   a script detecting a pivot after `right` bars plots the level *back on the
   pivot bar*, so historical charts show levels that existed before they could
   have been known. Live, the level appears `right` bars later.
   `swing_points()` here does not do this.
2. **Higher-timeframe leakage.** Using an HTF bar's close during a lower-TF bar
   that occurs before the HTF bar completed. `htf_trend()` must be audited for
   this — worth a unit test in `test_engine.py`.
3. **Same-bar signal-and-fill.** Signalling on `close[i]` and filling at
   `close[i]`. The engine fills at `open[i+1]`. Correct.
4. **Zone redrawing.** Order-block/FVG boxes that get moved or extended as new
   bars arrive; the backtest sees the final position, the live trader sees the
   first.
5. **Minor issue in the current code, worth fixing:** stop and target are
   computed from `close[i]` but entry fills at `open[i+1]`, so realised R
   differs from intended R by the overnight/next-bar gap. Not lookahead, but
   it blurs the R measurement. Recompute stop/target from the actual fill.

---

## 6. Failure modes to defend against

1. **Selection bias in the source material.** Every ICT/SMC number found came
   from someone selling a course, an indicator, or a prop-firm affiliate link.
   Not one came from a party with nothing to sell. Even the ORB paper's
   replication flags that its original authors run a day-trading education
   business.
2. **Survivorship in screenshots.** With millions of SMC traders, a zero-edge
   system still manufactures thousands of impressive multi-year equity curves.
   Those are the ones you see. The base rate is the AMF's four-year study of
   real French retail accounts, 2009–2013: **89% lost money; only 11%
   finished profitable** `[2nd-hand]`, consistent year to year despite varying
   market conditions. Broker disclosures show **74–89%** of retail CFD/forex
   accounts losing in any given quarter.
3. **Hindsight in the pattern definition.** "It was a sweep because it
   reversed" is unfalsifiable. Section 5.4 exists to force the definition to
   be made before the outcome.
4. **Cost blindness.** The dominant failure. The ORB paper's headline
   ($138,639) rested entirely on "we assumed no slippage in fills"; one cent
   of slippage removed 96% of it. The MNQ study's gross edges (0.07–1.50 pts)
   were all below its 2-point friction. E-006 in this repo measured a **48%**
   spread bill on a live account. On gold, cost is not a detail — it is
   usually the whole result.
5. **Regime dependence masquerading as edge.** 76% of the ORB filtered PnL was
   2022. E-004's longs (+0.292R) vs shorts (+0.007R) during a +17% gold bull
   run is the same warning. Always split by year and by side.
6. **Multiple testing.** Harvey, Liu & Zhu (RFS 2016) argue a newly discovered
   factor needs **t > 3.0**, not 2.0, because of the volume of search
   `[2nd-hand]`; Bailey & López de Prado's Deflated Sharpe adjusts explicitly
   for the number of variants tried. If we test 6 level families × 3 sweep
   tiers × 3 displacement thresholds, that is **54 tests** — one will show
   t > 2 by chance. Decide the primary hypothesis **before** running the grid,
   and record every variant tried in EXPERIMENTS.md.
7. **Anomaly decay.** Neely, Weller & Ulrich (JFQA 2009): FX filter and MA rule
   profits were genuine in the 1970s–80s and **had disappeared by the
   mid-1990s** `[2nd-hand]`. Kozhan & Salmon: GA rules profitable in 2003, gone
   by 2008 `[2nd-hand]`. Neely & Weller (2003): after realistic costs and
   restricting to normal market hours, **no positive excess returns**
   `[2nd-hand]`. A 1999-2000 microstructure fact is not a 2026 trading edge.

---

## 7. The strongest argument AGAINST this entire approach

Stated as forcefully as I can, because it deserves to be:

> Every step in the chain from "stops cluster" to "I can make money fading
> sweeps on gold" loses more than it gains, and the losses compound.
>
> The clustering is real but measured once, on one bank's book, in one
> nine-month window in 1999–2000, and never replicated on a modern electronic
> market. The published effect size is **~3.4 percentage points** of bounce
> frequency — smaller than the **5.0 percentage point** cost tax on a normal
> gold stop, before any rule is written. The mechanism the retail world cites
> (stop-loss cascades) predicts **continuation**, not the reversal it is used
> to justify; the reversal half comes from take-profit orders, a different
> order type at a different price. The pattern itself is not new — it is
> Raschke's 1995 Turtle Soup, which is Wyckoff's 1930s upthrust, and neither
> produced a documented track record in 30 or 90 years. The one rigorous
> systematic test that included liquidity-grab reversals as a named signal
> family (947 days of 5-min MNQ, walk-forward, t>2, cost-adjusted) rejected
> **all fourteen** families it tested, with maximum gross edge below the
> friction cost. Our own E-003 measured **+0.001R** on 603 gold trades and
> **−0.061R** at 3× spread. And the entire retail-facing literature on the
> topic is produced by people selling courses and indicators.
>
> The prior should therefore be: **there is no edge here**, and the burden is
> on the data to overturn that, not on the skeptic to disprove it. Additional
> effort on liquidity concepts is most likely to produce an
> overfit — because with enough level definitions and displacement thresholds
> you *will* find a t>2 variant in a 54-test grid, and it will be noise.
>
> The opportunity cost is the real damage. E-004 — a 1980s Donchian breakout
> with three parameters — already produced +0.198R, 5/6 positive walk-forward
> folds, and survived 3× spread. It sits in the one strategy family with a
> century of out-of-sample evidence behind it. Every hour spent on sweeps is
> an hour not spent making the thing that already works robust enough to
> trade.

The counter-argument, given fairly: E-003 tested *one* level definition
(fractal pivots) on *one* timeframe (1h) on *one* symbol with *no* materiality
floor and *no* displacement requirement. That is genuinely not a test of the
family. R-003 lists five untested variants. It is legitimate to spend a
**bounded** amount of effort closing that out — but with a pre-registered
hypothesis and a hard stop, not an open-ended search.

---

## 8. What to test first, and what would falsify it

Bounded programme. **Pre-register before running.** Stop when the budget is
spent regardless of results.

### Test A — the null-hypothesis test (do this first, ~1 hour)

*Not a strategy. A measurement.* For every usable level of each family
(`PDH/PDL`, `PWH/PWL`, `ASIA_H/L`, `EQH/EQL`, `ROUND(10)`, fractal pivot),
record every penetration and measure the **forward return distribution at
+1, +4, +12, +24 bars**, conditioned on nothing. Compare against a matched
null: same number of events, drawn at random bars with the same
time-of-day and volatility distribution.

- **Falsifier:** if penetrations of real levels have the same forward-return
  distribution as the matched random null, **the level concept is dead** and
  every strategy built on it is curve-fitting. Stop the whole programme.
- **This test cannot be gamed by an entry rule and has no cost model**, so it
  isolates whether there is any signal at all before implementation losses.
  This is the test E-003 skipped by going straight to a strategy.

### Test B — the Osler test (the one with a published number to beat)

`ROUND(10)` and `ROUND(25)` levels on gold. Measure bounce frequency at round
numbers vs matched arbitrary prices, exactly as Osler 2003 did.

- **Falsifier:** if the excess bounce frequency is not **statistically
  distinguishable from zero**, the foundational result does not replicate on
  2024–2026 gold, and the entire section 1 justification collapses.
- **Second falsifier:** if it replicates at ~3.4 pp but Test C shows that is
  not enough to pay costs, the concept is confirmed-but-untradeable, which is
  the outcome the arithmetic in section 1 predicts. **This is the most likely
  outcome.** Accept it and move on.

### Test C — conditioning monotonicity

On the best level family from Test A, sweep the conditioning variables:
penetration depth (0.1/0.25/0.5/1.0 ATR), displacement z (1.5/2.0/3.0), tick
volume ratio (1.0/1.5/2.0×), session.

- **Falsifier:** if expectancy does **not** vary monotonically with these — if
  the "best" bucket is random across variables and across walk-forward folds —
  then "sweep" is not a distinct category from "breakout" and the label is
  post-hoc. Reject the family.

### Test D — cost sensitivity, mandatory, on anything that survives

Run at 1×, 2×, 3× spread. Standing repo rule.

- **Falsifier:** dies at 2× spread → REJECTED, no discussion. E-003 already
  failed this (−0.031R at 2×, −0.061R at 3×).

### Test E — the honest comparison

Whatever survives A–D must be compared head-to-head against **E-004
(Donchian)** on the same bars, same costs, same folds.

- **Falsifier:** if the best liquidity variant does not beat the 1980s
  breakout, it does not get built. Complexity must earn its keep, and the
  user has already paid once for a system that did not.

### Budget and stopping rule

- **Hard stop: Test A + Test B first.** If both are null, close R-003, record
  the family as REJECTED in EXPERIMENTS.md, and do not reopen it without new
  data (tick data, order-book data, or a news calendar) — not new parameters.
- Log **every** variant tried, including the ones that failed, so the
  multiple-testing count is honest when something eventually shows t > 2.
- Required bar for promotion beyond PROMISING, given the search volume:
  **t > 3.0**, not t > 2.0 (Harvey/Liu/Zhu).

---

## 9. Classification summary

| Claim | Status |
|---|---|
| Stop/limit orders cluster at and near round numbers (1999–2000 FX dealer book) | **PROVEN** (on that data) |
| Stop-loss executions cause positive-feedback price acceleration, larger and longer than take-profit responses; significant for hours not days | **PROVEN** (on that data) |
| Price-contingent orders explain >half of FX return excess kurtosis | **SUPPORTED** |
| Support/resistance levels carry statistically detectable intraday predictive information | **SUPPORTED** (Osler 2000; Chung & Bellotti 2021) |
| Chart patterns carry *incremental information* in large samples | **SUPPORTED** (Lo/Mamaysky/Wang 2000) — with no profitability claim |
| Osler's clustering result still holds on modern electronic FX order books | **UNPROVEN** — never replicated; could not find any post-2010 order-book study |
| The ~3.4 pp round-number bounce effect is large enough to pay retail gold costs | **DISPROVEN by arithmetic** (cost tax 5.0 pp at a $2 stop, 10 pp at $1) |
| Fading liquidity sweeps has positive net expectancy | **UNPROVEN → leaning REJECTED**: E-003 (+0.001R, dies at 2× cost); arXiv 2605.04004 rejected liquidity-grab reversals among 14 families on 947 days of MNQ |
| Institutions deliberately hunt retail stops as a strategy | **FOLKLORE** — no order-flow evidence; indistinguishable from ordinary liquidity search; unfalsifiable as stated |
| Order blocks are distinct from supply/demand zones | **FOLKLORE** — documented renaming |
| "Displacement", "inducement", "major POI" as defined by ICT | **FOLKLORE** — not falsifiable as stated; testable only after being redefined as z-scores (§5.2) |
| FVG geometry, sweep-and-reclaim geometry | **PLAUSIBLE-BUT-UNTESTED** — exact, causal, codeable, no published null-corrected test found |
| Session-scoped levels (PDH/PDL, PWH/PWL, Asia H/L), equal highs/lows | **PLAUSIBLE-BUT-UNTESTED** — R-003 |
| SMC/ICT win rates of 65–80% | **FOLKLORE** — vendor sources, no sample size, no costs; and E-002 proves win rate alone is uninformative (69.5% win, −0.066R) |
| "70% of breakouts fail; XAUUSD ~62% intraday" | **UNSOURCED** — could not trace to any dataset or paper |
| Turtle Soup (Connors & Raschke 1995) works | **PLAUSIBLE-BUT-UNTESTED, leaning REJECTED** — 31 years, no reproducible systematic test found |
| Time-series momentum / trend following | **SUPPORTED** at daily+ horizons (58/58 positive, 52/58 significant; Sharpe ≈0.4/decade over 136 years) — with documented post-2009 decay |
| Opening range breakout | **PROMISING gross, UNPROVEN net** — break-even at 2.2¢/share slippage; 76% of filtered PnL from 2022 |
| Market intraday momentum (first→last half hour) | **SUPPORTED** for US equity ETFs 1993–2013; untested on gold |
| Overnight vs intraday return decomposition | **SUPPORTED** but **not applicable** to a single-symbol MT5 account |
| Short-horizon mean reversion | **REJECTED for retail** — profits below transaction costs |
| Volatility-managed portfolios | **UNPROVEN** — fails out of sample across 103 strategies; does not survive costs |
| London PM gold fix leakage | **PROVEN and then regulated away** — real, gold-specific, and no longer accessible |
| Gold monthly/weekly seasonality | **FOLKLORE until computed here** — 10-year samples, no multiple-testing correction, blog sources only |

### What I could NOT find evidence for — stated plainly

- Any peer-reviewed paper testing any ICT or Smart Money Concepts construct.
- Any post-2010 replication of Osler's order-book clustering on a modern venue.
- Any reproducible systematic test of Turtle Soup with trade count and costs.
- Any published net-of-cost profitable liquidity-sweep rule, on any market.
- Any source for the widely-repeated breakout-failure rates (70% / 62% XAUUSD).
- Any live, retail-accessible, peer-reviewed XAUUSD-specific anomaly.
- Any evidence at all bearing on CISD, killzones, or quarterly theory.

---

## 10. Sources

**Primary academic (all `[2nd-hand]` — see method note):**
- Osler, *Support for Resistance: Technical Analysis and Intraday Exchange Rates*, FRBNY Economic Policy Review 6(2), 2000 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=888805
- Osler, *Currency Orders and Exchange Rate Dynamics: An Explanation for the Predictive Success of Technical Analysis*, Journal of Finance 58(5), 2003 — https://onlinelibrary.wiley.com/doi/abs/10.1111/1540-6261.00588 · working paper: https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr125.pdf
- Osler, *Stop-Loss Orders and Price Cascades in Currency Markets*, JIMF 24(2) 219–241, 2005 — https://www.sciencedirect.com/science/article/abs/pii/S0261560604001147 · working paper: https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.pdf
- Osler & Savaser, *Extreme Returns: The Case of Currencies*, J. Banking & Finance 35(11) 2868–2880, 2011 — https://www.sciencedirect.com/science/article/abs/pii/S037842661100121X
- Mesfin, *Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures: A Systematic Falsification Study*, 2026 — https://arxiv.org/abs/2605.04004
- Chung & Bellotti, *Evidence and Behaviour of Support and Resistance Levels in Financial Time Series*, 2021 — https://arxiv.org/abs/2101.07410
- Lo, Mamaysky & Wang, *Foundations of Technical Analysis*, Journal of Finance 55(4) 1705–1765, 2000 — https://www.nber.org/papers/w7613
- Moskowitz, Ooi & Pedersen, *Time Series Momentum*, JFE 104(2) 228–250, 2012 — https://www.sciencedirect.com/science/article/pii/S0304405X11002613
- Hurst, Ooi & Pedersen, *A Century of Evidence on Trend-Following Investing*, 2017 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026
- Gao, Han, Li & Zhou, *Market Intraday Momentum*, JFE 129(2) 394–414, 2018 — https://www.sciencedirect.com/science/article/abs/pii/S0304405X18301351
- Lou, Polk & Skouras, *A Tug of War: Overnight versus Intraday Expected Returns*, JFE, 2019 — https://personal.lse.ac.uk/polk/research/TugOfWar.pdf
- Zarattini, Barbon & Aziz, *A Profitable Day Trading Strategy For The U.S. Equity Market*, 2024 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4729284 · Zarattini & Aziz, 2023 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416622
- Caminschi & Heaney, *Fixing a Leaky Fixing: Short-Term Market Reactions to the London PM Gold Price Fixing*, J. Futures Markets, 2014 — https://onlinelibrary.wiley.com/doi/10.1002/fut.21636
- Neely, Weller & Ulrich, *The Adaptive Markets Hypothesis: Evidence from the Foreign Exchange Market*, JFQA 44, 2009 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=922345
- Neely & Weller, *Technical Analysis in the Foreign Exchange Market*, FRB St. Louis WP 2011-001 — https://files.stlouisfed.org/files/htdocs/wp/2011/2011-001.pdf
- Avramov, Chordia & Goyal, *Liquidity and Autocorrelations in Individual Stock Returns* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=555968
- Harvey, Liu & Zhu, *…and the Cross-Section of Expected Returns*, RFS 2016 — https://www.nber.org/papers/w20592
- Bailey & López de Prado, *The Deflated Sharpe Ratio* — https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
- Moreira & Muir, *Volatility Managed Portfolios* — https://www.nber.org/system/files/working_papers/w22208/w22208.pdf ; critiques: https://www.sciencedirect.com/science/article/abs/pii/S0304405X2030132X
- *Tick size reduction and price clustering in a FX order book* (EBS) — https://arxiv.org/pdf/1307.5440
- *Examining psychological barriers in exchange rates across various regimes and FX intervention*, 2025 — https://www.sciencedirect.com/science/article/pii/S2214635025000012

**Directly verified by me (read in full):**
- Brusco, *QQQ Opening Range Bias — Replication & Execution Stress Test* — https://github.com/giovannibrusco/zarattini-2023-orb-qqq

**Critical / practitioner sources (low evidentiary weight, used for the criticism section only):**
- AlgoStorm, *ICT & SMC Truth: Evidence-Based Trading Review* — https://algostorm.com/ict-smc-realistic-overview/
- Sentient Trading Society, *The Illusion of Edge: SMC, Survivorship Bias, and Market Reality* — https://wire.insiderfinance.io/the-illusion-of-edge-smc-survivorship-bias-and-market-reality-ae7873ef154d
- Sentient Trading Society, *Dumb Money Concepts and Backtest Limitations* — https://medium.com/@SentientTradingSociety/dumb-money-concepts-and-stat-test-limitations-110dcd4b67cf
- Trading Wyckoff (Villahermosa), SMC provenance — https://tradingwyckoff.com/en/smart-money-concepts/
- TradingView, *Concepts / Repainting* — https://www.tradingview.com/pine-script-docs/concepts/repainting/
- AMF decision restricting CFD marketing (retail loss statistics context) — https://www.amf-france.org/sites/institutionnel/files/contenu_simple/regles_professionnelles_approuvees/AMF's%20decision%20of%201%20August%202019%20restricting%20the%20marketing,%20distribution%20or%20sale,%20in%20France%20or%20from%20France,%20of%20contracts%20for%20differences%20to%20retail%20investors.pdf
- Connors & Raschke, *Street Smarts* (1995), ch. 1 "Turtle Soup"; MQL5 implementation — https://www.mql5.com/en/articles/2717
- LuxAlgo concept library (used once, as instructed, only to fix vocabulary) — https://www.luxalgo.com/library/concept/smart-money-concepts/

**In-repo cross-references:** E-002 (win rate ≠ edge), E-003 (liquidity sweep
null), E-004 (Donchian, the incumbent to beat), E-006 (48% spread bill),
R-003 (untested liquidity variants), `strategies.py:39` (`swing_points`,
verified causal), `engine.py:152` (cost model), `engine.py:214` (next-bar fill).

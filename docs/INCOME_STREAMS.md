# Second Income Stream — Honest Assessment

**Date:** 2026-09-16 · **Capital:** ~£120, possibly a few hundred · **Target:** ~£50/day

> **Source note.** Direct page fetching (`WebFetch`, `curl`) is blocked in this environment. Every
> figure below comes from a **web search result summary** of the named source, not from a page I
> opened myself. Treat them as *reported by that source*, and re-check any number you would bet on.
> Figures marked **[calc]** are my own arithmetic from those inputs. Nothing here is unsourced
> guesswork presented as fact.

---

## 1. The arithmetic, before anything else

£50/day on £120 is **41.7% per day**. Compounded **[calc]**:

| Trading days | Balance |
|---|---|
| 5 | £685 |
| 10 | £3,907 |
| 20 | £127,000 |
| 30 | £4.1 million |
| 60 | £143 billion |
| 252 (1 yr) | £1.6 × 10^40 |

Total global wealth is roughly $5 × 10^14. The 60-day figure already exceeds most national economies.
This is not "hard" — it is arithmetically impossible, which is why no such strategy exists at any size.
At £500, £50/day is 10%/day: £8,725 in 30 days, £152,000 in 60. Same wall, three weeks later.

**Flip it round.** £50/day × 252 days = £12,600/year. The capital required **[calc]**:

| Annual return | Capital needed | Who earns this |
|---|---|---|
| 10% | £126,000 | Good, boring, achievable |
| 20% | £63,000 | Very good, sustained |
| 40% | £31,500 | Top-decile professional |
| 66% | £19,100 | Renaissance Medallion, gross, best ever recorded |

**£50/day is a capital problem, not a strategy problem.** It needs roughly £30k–£125k.

**Realistic range from returns alone [calc]:**

| Capital | 10%/yr | 20%/yr | 30%/yr |
|---|---|---|---|
| £120 | £0.05/day | £0.10/day | £0.14/day |
| £500 | £0.20/day | £0.40/day | £0.60/day |

At £120 the return on capital is statistical noise. What £120 actually buys is **one experiment**, or
one prop-firm challenge ticket. Treat it as a testing budget, not as a trading float.

---

## 2. Category survey

| Category | Capital to be real | Where edge comes from | Realistic return | Failure modes | Cost to find out |
|---|---|---|---|---|---|
| **Systematic FX/futures** | £2k–5k (micro futures day margin is $50–100 but that is not a bankroll; realistic starting bankroll $2,000–5,000 — *TradingSim/QuantCrawler*) | Trend & carry risk premia. Real, documented, low Sharpe | 5–15%/yr at 15–25% vol; 20–30% drawdowns; 1–2 yr flat spells | Overfit backtest; slippage; regime change; discipline | £0 software. **12–24 months of live data** to separate skill from luck. Time is the cost |
| **Crypto market-making** | $50k+ realistically. Negative maker fees are reserved for firms trading **$100M+/month**; retail at $5k–250k competes with algo firms on tech and capital (*Paybis, PAX Markets*) | Bid-ask spread, paid for inventory risk | Negative at retail after adverse selection | Adverse selection (fast traders pull quotes, you get filled by informed flow); inventory risk in one-way moves | Weeks of dev + live capital burned. **Not a non-developer activity** |
| **Funding-rate carry (perp basis)** | £1,000+ before fees stop eating it (capital splits across spot + short perp legs) | **Genuine risk premium** — longs persistently pay shorts for leverage | Vendors claim 8–20% APY; 3-yr backtests claim 12–25% with Sharpe 3–6, <5% DD (*ArbitrageScanner, Darkbot*) — those are vendor-published, discount them. Honest net: 5–15% APY = **£0.05/day on £120** **[calc]** | Funding flips negative for days (*Hyperdash*); exchange failure (FTX); short-leg liquidation on thin margin. **This is the classic all-green-days shape** | £50–100 in fees + one month observing. **Cheapest honest test on the list** |
| **Statistical arbitrage** | Institutions run **50–200 pairs**; retail running 3–5 pairs has variance, not edge (*Quantt*) | Mean reversion in cointegrated spreads | Honest implementations ~Sharpe 1.23; headline 2.67–9.25 figures are in-sample | 20–30% daily turnover; costs flip Sharpe 2.0 → 1.5 → negative; momentum shocks wipe returns | Months of coding. Needs a developer |
| **Cross-exchange spreads** | 2× capital, idle on both venues, plus rebalancing float | Price dislocation — **largely arbitraged away** | Spreads now a few bps; 0.1% taker each side = **0.2% just to break even** (*Backpack Learn, BotVsBot*) | Rebalancing transfers are "the hidden killer"; latency; API failure | **Free.** Watch the same pair on two exchanges for a week. It will show you it is dead |
| **DeFi yield / LP** | Gas makes small mainnet positions uneconomic; L2 is cheaper | Lending: real interest. LP: fee income *minus* impermanent loss | Stablecoin lending **3.5–9% APY** in 2026 (*Eco, Spark*) = **£4–11/yr on £120** **[calc]**. LP: **~49.5% of Uniswap v3 LPs had negative returns vs just holding**; >80% of pools; $199.3M fees vs **$260.1M impermanent loss** (*Topaze Blue via Nasdaq/CryptoSlate*) | Smart contract risk (**Euler lost $200M in 2023 despite audits**); depeg; rates halve overnight | £20–50 gas. Lending is real; the sum is trivial at his capital |
| **Prop-firm challenges** | £77–£1,000 per attempt | Borrowed size, not edge | See §4 | See §4 | One challenge fee |
| **Memecoins** | Any | None. Negative-sum after fees | See §3 | Total loss is the base case | £0 — the base rates are already published |

---

## 3. "All green days" — why it cannot exist

A strategy's daily win rate is set by its Sharpe ratio. Daily Sharpe = annual ÷ √252 **[calc]**:

| Annual Sharpe | Green days | Red days/year |
|---|---|---|
| 1.0 (good retail) | 52.5% | 120 |
| 2.0 (excellent) | 55.0% | 113 |
| 3.0 (professional) | 57.5% | 107 |
| 7.0 (Medallion-class) | 67.0% | 83 |

**The best fund in history is red roughly one day in three.** An honest distribution of a 20%/yr,
15%-vol strategy: ~113–120 losing days, several losing months, at least one 15–25% drawdown per year.

Anything showing 95%+ green days is not a better strategy — it is the **same expected return with
the losses moved into the tail**: short volatility, martingale, or unhedged carry. Many small wins,
then one day that takes everything:

- **XIV (inverse VIX ETN), 5 Feb 2018** — down **>90% in one day**, terminated. VIX rose 115% in a session (*CFA Institute, CNBC, Cboe*).
- **LJM Preservation & Growth Fund** — uncovered short volatility. $9.67 → $4.27 (−55.8%), then → $1.94. **−80% in two days**, ~$1bn lost (*Chief Investment Officer, SteadyOptions*).

Both had years of near-perfect green-day records first. That record *was the warning*.

**Memecoin base rates:**

| Finding | Source |
|---|---|
| **98.6%** of Pump.fun tokens collapse into pump-and-dumps or rug pulls | *The Defiant*, citing report |
| **Fewer than 2%** of tokens ever graduate to a major DEX | *arXiv 2512.11850* (page blocked; via search summary) |
| **~97%** of meme coins have died or lost nearly all volume | *STORM Partners* |
| **93.75% of 304,161** active Solana memecoin traders lost money over 90 days; **median loss $120** | Widely reported on-chain study (*Cryptopolitan, Cointribune, Pluang*) |
| Of the 6.25% who won, **88% made under $100**; only **25 wallets** cleared $10,000 | same |
| Aggregate trader losses **~$1.26 billion** | same |
| Only **0.25%** of traders cleared $500 in 60 days | *Route 2 FI via CoinOTAG* |

The median memecoin trader loses **exactly his entire stake**. £120 is the median loss.

**Retail trading base rates generally:** 74–89% of retail CFD accounts lose money (*ESMA / national
regulators*); the FCA found **82% losing**, average −£2,200. Chague, De-Losso & Giovannetti tracked
**all 19,646** individuals who began day-trading Brazilian index futures 2013–2015: **97% of those
who persisted past 300 days lost money; 1.1% earned more than minimum wage; 0.5% more than a bank
teller's starting salary** (*SSRN 3423101*).

---

## 4. Prop-firm challenges — the real economics

This matters most because he already trades. It is also the only route listed that **bridges the
capital gap** rather than requiring capital he does not have.

**Costs and terms (FTMO, representative):** $10k 2-step ≈ **€89**; $200k ≈ **€1,080** (*JP Trading
Capital, BrokerAnalysis*). Profit split **80%**, rising to **90%** on the scaling plan after ~6 months
of consistency. Challenge fee is **refunded with your first payout**. A breached *funded* account
has no reset — it must be repurchased at full price.

**Pass rates — published vs independent:**

| Metric | Figure | Source |
|---|---|---|
| FTMO historically cited, 2-step | 9–12% per attempt | *TradersSecondBrain* |
| Blended independent, 2025–26 | **12.3%** (range 5–14%) | *QuantVPS / Track360* |
| **Buyers who ever receive a payout** | **~7%** | same |
| Funded traders who get ≥1 payout | ~45% | same |
| Average payout when it happens | **4% of account** ($4,000 on $100k) | same |
| First-phase failures from **daily drawdown breach** | 71% | same |
| FTMO: 4.5M customers, 200k funded, $650M paid — **denominator never published** | 200k/4.5M = **4.4%** **[calc]** | *Coinlaw, Track360* |

**Expected value of buying one challenge [calc]**, using the ~7% buyer-to-payout rate, 4% average
payout, and the fee refund:

| Account | Fee | EV per challenge | Break-even payout rate you must personally hit |
|---|---|---|---|
| $100k | ~€580 | **−£259** (−45%) | **12.7%** |
| $10k | ~€96 | **−£61** (−64%) | **19.4%** |

**Read this carefully:** EV is negative *for the average buyer*, and **small challenges are
proportionally worse** (fee is 0.89% of a $10k account vs 0.54% of a $100k one) — yet the small one is
all £120 buys. To break even you must convert attempts to payouts at ~13–19%, roughly **2–3× the
observed base rate**. That is not impossible — it is the one number in this document he can actually
move, because unlike memecoins it responds to skill. But it requires being genuinely in the top
decile, and **71% of failures are risk-management breaches, not bad strategy**.

**The business model, plainly.** Firms earn from challenge fees and resets, not from your trading.
Rules are tuned so a *statistically normal losing streak* breaches the daily drawdown before the
profit target is hit. That is why 71% of failures are drawdown breaches. FTMO is a real business
(£329M revenue, £62.5M net profit in 2024 — *TheIndustrySpread*), so payouts are real; but **80–100
prop firms shut down between Feb 2024 and end-2025** (*ThePropFirmGuide, VeritasChain*), and the CFTC's
flagship case against My Forex Funds ($310M, 135,000 customers) was **dismissed with prejudice in May
2025 with $3M+ in sanctions against the CFTC** (*Reuters, DeSilva Law*) — the sector is unregulated and
unsettled. **Firm risk is a real line item: assume some chance the firm, not the market, takes your money.**

---

## 5. Ranked — what to test first

| # | Test | Why | Cheapest experiment that settles it | Cost |
|---|---|---|---|---|
| 1 | **Prop challenge, smallest size** | Only route that bridges the capital gap; skill-responsive; he already trades | Trade his existing strategy on a **free demo under exact challenge rules** (daily DD, max DD, target) for 30 days, no exceptions. Hit the target without a breach **twice** before paying a fee | **£0** |
| 2 | **Daily-drawdown discipline audit** | 71% of failures are this, not strategy. Fixes #1 before it costs money | Log every day of his last 3 months. Count days that would have breached a 5% daily / 10% total limit. If any, #1 is a guaranteed loss of the fee | **£0** |
| 3 | **Funding-rate carry, observation only** | Genuine risk premium; the only category with real edge at small size — but also the exact all-green-days shape | Record 8-hourly funding on BTC/ETH perps for 30 days. Count negative intervals. Compute net APY after fees *before* deploying a penny | **£0** |
| 4 | **Systematic FX/futures** | Real but slow; needs size and a long track record to prove | Paper-trade the rules for 6 months with fixed sizing. Compare to backtest — if live diverges, it was overfit | £0 + 6 months |
| 5 | **Stablecoin lending** | Real yield, trivial amount. Worth knowing the plumbing for later | £50 into Aave on an L2 for a month. Measure net after gas | ~£50 |
| — | **Cross-exchange spreads** | Watch two venues for a week; the data will kill it | £0 | £0 |
| — | **Market-making, stat arb** | Require capital and a developer he does not have | Do not test | — |
| ✗ | **Memecoins** | 93.75% lose; median loss is his whole stake | Nothing to test — the base rates are published | — |

**The honest summary:** at £120, trading returns cannot produce £50/day and never will. The two things
that can are **more capital** and **borrowed size**. Prop firms are the only listed bridge, they have
negative EV for the average buyer, and the single lever that moves that EV is drawdown discipline —
which costs £0 to test and is the most likely reason he has failed challenges before.

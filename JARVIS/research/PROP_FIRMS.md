# PROP FIRM RULE RESEARCH — for risk-engine encoding
**Compiled:** 2026-08-29
**Purpose:** encode enforceable risk rules; assess firms for an EA-driven, ~10-account XAUUSD copy-trade plan.

---

## 0. METHOD AND ITS LIMITS — READ THIS FIRST

This session's network egress policy **blocked direct page fetches to every prop-firm domain**
(`ftmo.com`, `maventrading.com`, `lucidtrading.com`, `fundednext.com`, `the5ers.com`,
`fundingpips.com`, `alphacapitalgroup.uk`, `e8markets.com` — all returned `EGRESS_BLOCKED`).

Everything below therefore comes from **search-engine summaries of official-domain pages**
(help centres, FAQ, trading-objectives pages), not from pages I opened and read line by line.

Confidence tiers used throughout:

| Tag | Meaning |
|---|---|
| `OFFICIAL-SUMMARY` | Sourced from the firm's own help-centre/FAQ URL, via search summary. High confidence, **not** page-verified. |
| `AFFILIATE` | From a review/comparison site that earns commission. Treat as rumour. |
| `UNVERIFIED` | Could not confirm from an official source. **Do not encode this into the risk engine.** |

**Hard instruction for the engine build:** before any real money is committed, a human must open each
firm's help-centre URL (listed in §8) and confirm the four numbers that actually kill accounts —
daily-loss %, daily-loss *basis*, daily-loss *reset time*, and whether max drawdown trails.
An unverified drawdown rule in a risk engine is worse than no rule.

---

## 1. BOTTOM LINE (5 sentences)

**Both firms you named are wrong for this plan: Lucid Trading is a futures-only firm and does not
offer XAUUSD at all, and Maven Trading prohibits Expert Advisors outright without prior written
approval — an EA plan there is a rule breach, not a strategy.** Of the alternatives, **E8 Markets is
the standout** because it is the only firm found that *explicitly permits copy trading across your
own accounts* and allows headroom well past $400k, followed by **FundedNext** (EAs welcomed,
own-account copy trading explicitly allowed, but capped at **$300,000 total per trader and per EA
strategy**) and **FundingPips** (fully automated EAs allowed **only if you wrote them** and can prove
ownership; $400k cap; no weekend holds). **FTMO is the most reputable and best-documented firm here
but is structurally incompatible with the ten-account plan: its cap is $400,000 per trader *or per
strategy*, and it explicitly reserves the right to suspend accounts when identical strategies are
detected across them.** **Alpha Capital is disqualified — fully automated execution EAs are banned
under any circumstances; The5ers allows only EAs whose source code you own and caps allocation very
low per program.** Net recommendation: **do not run ten accounts at one firm on one EA** — the
per-strategy allocation caps make it a rule breach at every major firm; instead spread 3–4 accounts
each across E8, FundedNext and FundingPips, prove one payout first, and build the risk engine to the
conservative superset in §7.

---

## 2. THE TWO DISQUALIFICATIONS, STATED PLAINLY

### Lucid Trading — wrong asset class
- Lucid is a **futures prop firm**. Its own site brands it "The Best Prop Firm For Futures", and its
  help centre states Lucid supports **futures markets only** — no forex, no XAUUSD. `OFFICIAL-SUMMARY`
- Its rule vocabulary (Max Loss Limit, End-of-Day drawdown, Initial Trail Balance) is futures-firm
  language, not MT4/MT5 forex language.
- If you want gold at Lucid you would trade **GC/MGC futures**, a different instrument with different
  tick value, margin, session hours and roll mechanics. **Your XAUUSD EA does not transfer.**
- **Verdict: excluded from the comparison for this plan.** Rules below are recorded for completeness only.

### Maven Trading — EAs prohibited
- Maven's own rules pages state: **"EAs are not permitted on any Maven Trading platform"**; use of an
  EA "will result in you not passing your challenge", repeated use "could result in account
  suspension". A prior-approval exception exists but is described as rare. `OFFICIAL-SUMMARY`
- Also prohibited: **grid/gap strategies** across all challenge and funded accounts; **copy trading
  from another individual** (both parties breached); reverse/group hedging. `OFFICIAL-SUMMARY`
- **Verdict: an EA-driven plan at Maven is a rule breach by construction.** Do not spend challenge
  fees here unless Maven grants written EA approval first — get it in writing, before purchase.

---

## 3. COMPARISON TABLE

Percentages are of **initial account size** unless stated. All figures `OFFICIAL-SUMMARY` unless tagged.

| | **FTMO** | **FundedNext** | **The5ers** | **FundingPips** | **Alpha Capital** | **E8 Markets** | **Maven** | **Lucid** |
|---|---|---|---|---|---|---|---|---|
| **Asset class** | FX/CFD/metals | FX/CFD + separate futures arm | FX/CFD | FX/CFD | FX/CFD | FX/CFD + separate futures arm | FX/CFD | **Futures only** |
| **XAUUSD available** | Yes | Yes | Yes | Yes | Yes | Yes | Yes | **No** |
| **Account sizes** | $10k / $25k / $50k / $100k / $200k | $6k / $15k / $25k / $50k / $100k / $200k | Bootcamp $5–20k; High Stakes $2.5k–$100k | $5k / $10k / $25k / $50k / $100k / $200k | up to $200k | $25k / $50k / $100k / $150k+ | up to $200k | n/a here |
| **Price (entry)** | `UNVERIFIED` current pricing; 14-day free trial offered on both 1- and 2-step | `UNVERIFIED` exact; see app.fundednext.com/pricing | High Stakes from **$19**; Hyper Growth **$74**; Bootcamp **$95** (+$205 later = $300 total) | 2 Step Pro from **$29**; 2 Step Standard from **$33** | `UNVERIFIED` | `UNVERIFIED` | 2-step from ~**$18–19 with coupon** | n/a |
| **Phase structure** | 1-step and 2-step | Stellar 1-Step (10%), Stellar Lite (8%/4%), Stellar 2-Step (8%/5%), Stellar Instant | Bootcamp (multi-level, 6%/level), High Stakes 2-step (10%/5%), Hyper Growth 1-step (10%) | 1 Step Flex, 2 Step Standard, 2 Step Pro, 2 Step Flex, 3-Step, Zero (instant) | Alpha One (1-step), Alpha Pro, Alpha Three, Alpha Swing, Alpha Direct | E8 One (1-step), E8 Classic, E8 Track, E8 Signature, E8 Pro | 1-step (8%), 2-step (8%/5%), 3-step, Instant | LucidPro / LucidFlex / LucidDirect / LucidDaily |
| **Daily loss limit** | **5%** (2-step) / **3%** (1-step) | **5%** (Evaluation/Express/Stellar 2-step) | **5%** (High Stakes) | **3%** (Zero, 2 Step Pro) / **5%** (2 Step Standard) | **4%** (Alpha One); 3–5% by plan | **4%** (Classic, One) | **4%** (2-step) / **3%** (1-step) / **2%** (3-step) | Soft DLL on 50k+, none on 25k |
| **DLL basis** | **Equity** vs balance recorded at 00:00 CE(S)T. Floating losses count. | **Equity** (closed P/L minus floating losses) vs day-start balance; fixed $ = 5% of *initial* balance | Higher of previous day's **closing equity or balance** | Higher of day-start **balance or equity**; equity may not fall by the % — **floating included** | Higher of day's starting **balance or equity**; unrealised losses count; carried-over floating loss *reduces* the day's allowance | Day's **starting balance** minus fixed $ amount (from initial balance) | Higher of **balance or equity** at 00:00 UTC | End-of-day based |
| **DLL reset** | **00:00 CE(S)T** | **00:00 server time** = GMT+3 (DST) / GMT+2 (rest of year) | Start of new session | Day baseline (server) `UNVERIFIED` exact clock | **00:00 GMT+3** (broker time) | **00:00 server time** | **00:00 UTC** | Session close |
| **DLL breach = ?** | Account fail | **Account breached/failed** even if max loss untouched | High Stakes: daily **pause**, not termination | Breach | Breach | Breach | Breach (Instant/1-step) `UNVERIFIED` per-model | Soft lock, no fail |
| **Max drawdown** | **10%** (2-step) | **6–10%** by model; Instant = equity ≥ 94% of initial | **10%** absolute from initial (High Stakes); Hyper Growth stop-out **6%** below initial | **6%** of initial (several models) | Alpha One **6%** | Classic **8%**; One **4% dynamic** `UNVERIFIED` headline % | 2-step **8% static**; 1-step Elite static; **1-step Essential + Instant TRAILING 5%** | EOD trailing MLL, locks at $100 buffer |
| **Static or trailing** | **Ratcheting**: limit recalculated daily at 00:00 as (highest balance at 00:00 of any prior day, or initial) − 10%. **Can only increase.** ⚠️ see §4.1 | **Ratcheting on new highs**; steps up, never down | **Static/absolute** from initial (High Stakes, Hyper Growth) | **Static from initial** on the 6% models `UNVERIFIED` for Pro | **Trailing** high-water mark, **locks at initial balance once +6%** | **EOD dynamic**: rises only when you **close** profit (not on equity), locks permanently at initial balance level | **Static** on 2-step/3-step/1-step Elite; **trailing** on Instant + 1-step Essential | EOD trailing, locks once live profit = starting drawdown |
| **Consistency rule** | None stated in objectives `UNVERIFIED` | **None for CFDs**; 40% for Futures | `UNVERIFIED` | **35%** best-day cap **+ 7 profitable days** each ≥0.5% of account | **40%** best day | **None in challenge**; **40% best day** on Performance stage | **15%** — *largest winning **trade** / total profit* | LucidPro 40% / LucidDirect 20% / LucidFlex 50% |
| **Min trading days** | **4** | 1-Step: **2**; Lite: **5**; 2-Step: **5** | High Stakes: **3 profitable days per step** (≥0.5% each); Bootcamp/Hyper Growth L1: none | **0** (2 minimum from 26 Aug 2026 on new/reset accounts) | `UNVERIFIED` | No time limit; ≥1 trade per 60 days | ~**5–10** `UNVERIFIED` exact per model | `UNVERIFIED` |
| **EA / algo** | **Allowed.** Caveat: if third-party, the same EA must not be used by other traders — $400k cap is **per client OR per strategy** | **Allowed**, MT4/MT5, with an **EA usage fee**; each EA must use a **distinct strategy**, no identical trades across accounts | **Allowed only if you own the source code.** Third-party EAs where others hold the same trades = prohibited | **Self-developed: full automation allowed with proof of ownership** (source code, VCS history, dev environment, or a live call). **Third-party EAs: risk/trade-manager use only** | **Fully automated execution EAs PROHIBITED, "will not be approved under any circumstances."** Only virtual/hidden SL-TP EAs allowed | **Allowed**, provided multiple *users* are not running the same trades/strategy | **PROHIBITED** without prior approval | Bots and trade copiers permitted; **HFT not**; **hedging hard-banned** |
| **HFT / tick scalp / latency arb** | Forbidden practices policy | Prohibited strategies list | Prohibited: arbitrage, seconds-duration HFT, rollover scalping | Prohibited | Prohibited | Prohibited | Prohibited: HFT, toxic order flow, tick scalping, long/short arb, reverse arb | HFT not allowed |
| **Martingale / grid** | `UNVERIFIED` (not explicitly banned in sources seen) | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | "all-or-nothing" strategies rejected | `UNVERIFIED` | **Grid/gap prohibited on all accounts** | `UNVERIFIED` |
| **News trading** | Restricted on **funded Standard accounts only** (not during evaluation, not on Swing): may hold positions opened **>2 min before** the restricted event | **Allowed** (CFDs and futures) | `UNVERIFIED` exact window | **Cannot open or close within ±5 min (10-min window)** of restricted high-impact news on affected currencies; trades opened **<5 h before** news are flagged if closed in that window | Restricted `UNVERIFIED` exact window | **No restrictions** on E8 Signature Forex | **No news restrictions** | Allowed incl. NFP/FOMC/CPI |
| **Weekend / overnight** | Restricted on funded **Standard** only; **Swing has no restriction**; no restriction during evaluation | **Allowed** | `UNVERIFIED` | **Weekend holds NOT allowed** on 2 Step Standard/Pro Master accounts — auto-closed Friday (soft, not a hard breach) | `UNVERIFIED` | `UNVERIFIED` | **Weekend holds permitted, all account types** | n/a |
| **Profit split** | **90%** (1-step); **80%** (2-step), 90% via Scaling/Premium | `UNVERIFIED` headline (commonly 80–95% by model) | High Stakes **80%**; Hyper Growth/Bootcamp start **50%**, scale to 100% | **60–100%** depending on payout cadence chosen | up to **80%**, 90% as Qualified Analyst | E8 One **up to 100%**; Signature **80%** | **80%** minimum | **90/10** |
| **First payout timing** | Request from the **14th day** after first trade; reviewed 1–2 business days, paid 1–2 business days after invoice approval | On demand, **guaranteed within 24 h**; Stellar 1-Step cycle 5 business days, Stellar 2-Step first cycle **21 days** | **14 days** after funding, then every 14 days | **Every Tuesday**; also weekly/biweekly/monthly/on-demand cycles | On-demand performance fee | **On demand**, earliest **3 days** into performance stage; **max 5 payouts per account** then deactivated | Every **10 business days**; **1st payout capped at 6%** of balance, 2nd at 8%, then uncapped | Buffer must be cleared first |
| **Own-account copy trading** | **Not explicitly permitted.** No account limit, but **$400k cap per trader OR per strategy**, and FTMO "reserves the right to suspend" accounts where identical strategies exceed the cap | **Explicitly ALLOWED** between own challenge accounts, **total capital ≤ $300,000** | **Prohibited** for third-party/copy-from-external; own-algo across own accounts `UNVERIFIED`; low per-program caps | **Permitted** between own accounts under the same individual; **native Trade Copier**, beta cap **4 accounts per user** | Signal-following = "group trading" = prohibited; same EA across multiple traders = breach | **Explicitly ALLOWED across your own accounts** (challenge, performance, personal), each managed individually, within per-product allocation cap | Copy trading **from another individual prohibited** (both breached) | Trade copiers permitted |
| **Total allocation cap** | **$400,000 per trader OR per strategy** (pre-scaling); scaling ceiling $2M | **$300,000** across all accounts / per EA strategy | Very low: Hyper Growth **$40,000 max capital per trader**; High Stakes capped by account-count matrix | **$400,000** across Evaluation + Master + Prime | **$400,000** across all four plans combined | **$500,000** on E8 One performance stage; up to **$4,250,000** simulated across SimFi performance. **Applies per household/IP.** | up to $200,000 initial `UNVERIFIED` as a hard cap | n/a |

---

## 4. THE DETAIL THAT KILLS ACCOUNTS — WORKED BREACH EXAMPLES

**The universal mechanic:** every firm above measures the daily limit against **equity**, not balance.
Floating loss on an open position counts immediately. **You can fail an account without closing a
single trade, and without any stop-loss being hit.** An EA that holds through a spike is the #1 cause
of funded-account death.

XAUUSD sizing convention used below: **1.00 lot = 100 oz**, so **$1.00/oz move = $100 per lot**.
Gold assumed near $3,900; a $20/oz intraday swing is ~0.5% and entirely routine.

### 4.1 FTMO — $100k 2-Step funded account
- Max Daily Loss = 5% of initial = **$5,000**, measured against balance at **00:00 CE(S)T**.
- Say balance at 00:00 CE(S)T = **$103,000**. Breach floor for the day = 103,000 − 5,000 = **$98,000 equity**.
- Intraday you close +$1,500 (balance $104,500) and the EA opens **3.0 lots** long gold.
- Gold falls **$22/oz** → floating = −$6,600. Equity = 104,500 − 6,600 = **$97,900**.
- **$97,900 < $98,000 → account failed.** No stop hit, nothing closed, and you were *up* $1,500 on the day.
- **Note the trap in the profit:** the floor is anchored to the 00:00 *balance*, so today's realised
  profit does **not** buy you room downward — it only raises the balance you fall from.
- ⚠️ **Ambiguity to resolve before encoding:** the max-loss description found — "recalculated daily at
  00:00 as (highest balance at 00:00 of any preceding day, or initial capital) − 10%, can only
  increase" — is a *ratcheting* limit. FTMO's 2-step has historically been described as a **static
  10%**. I could not separate the 1-step and 2-step wording from an official page. **Treat FTMO max
  loss as ratcheting (the harsher reading) until a human confirms.** `UNVERIFIED`

### 4.2 FundedNext — $100k Stellar 2-Step
- DLL = 5% of **initial** balance = **$5,000**, reset **00:00 server (GMT+2/+3)**. Current daily loss
  = closed P/L − floating losses.
- Day-start balance **$102,000** → floor **$97,000** equity.
- EA holds **3.0 lots** gold; adverse move of **$17/oz** → −$5,100 floating → equity **$96,900**.
- **Breached.** FundedNext's own docs are explicit: breaching the DLL fails the account **even if the
  Maximum Loss Limit is untouched.**
- **DST trap for the engine:** the server rolls GMT+3 ↔ GMT+2 seasonally. An engine hard-coded to one
  offset will compute the wrong daily anchor twice a year, on the exact days volatility is unusual.
- **Instant variant:** equity must never fall below **94% of initial** — a **6% trailing** floor.

### 4.3 FundingPips — $100k 2 Step Pro
- DLL = **3%** of the higher of day-start balance/equity = **$3,000**. This is the tightest daily limit
  in the group.
- Day-start balance **$101,000** → floor **$98,000**.
- EA holds **2.0 lots** gold; adverse **$15/oz** → −$3,000 → equity **$98,000** → **breached**.
- **A $15 gold move on 2 lots kills a $100k account.** That is roughly a 0.4% move — a single CPI
  candle. At 3% daily, an XAUUSD EA effectively cannot carry more than ~1 lot per $100k without
  living inside breach distance.
- Compounding constraints: **no weekend holds** (auto-closed Friday), **±5 min news blackout**, trades
  opened **within 5 h before** news get flagged if closed in the window, **35% best-day consistency**,
  and **7 profitable days ≥0.5% each** before a reward. An EA that makes its month in two big days
  **cannot get paid here.**

### 4.4 E8 Markets — the ratchet trap (EOD dynamic drawdown)
- **E8 Classic $100k:** daily floor = day-start balance − **$4,000**; overall floor **$92,000** (8% from
  initial). Day-start $103,000 → daily floor **$99,000**. 3 lots, gold −$14/oz = −$4,200 → equity
  $98,800 → **daily breach**, while the overall floor at $92,000 was never remotely threatened.
- **E8 One $100k (dynamic):** floor starts at 100,000 − 4,000 = **$96,000**. The floor rises **only
  when you close profit**, at end of day. Close the week at **$103,000** → floor ratchets to **$99,000**.
  You are now +$3,000 but have only **$4,000** of total room left — *less* headroom than on day one
  relative to your equity high. One 3-lot position going −$14/oz takes you to $98,800 → **account dead
  while still in profit.**
- **This is the single worst structure for an EA with occasional losing streaks.** A strategy that
  grinds up 3% then gives back 4% survives a static 8% drawdown and dies instantly on a 4% dynamic one.
  The floor locks at initial balance only *after* you have trailed the full amount.

### 4.5 The5ers — High Stakes $100k
- Daily = **5%** taken from the higher of the previous day's **closing equity or balance**.
- Previous close **$104,000** → floor **$98,800**. 3 lots, gold −$18/oz = −$5,400 → equity $98,600 →
  daily limit hit.
- **Mitigation worth noting:** on High Stakes the daily breach is a **pause**, not a termination — the
  account is disabled for the day and resumes. That is materially kinder to an EA than FundedNext's
  hard fail. Max loss remains **10% absolute from initial** ($90,000) and does **not** trail — the most
  forgiving overall-drawdown model in this comparison.

### 4.6 Alpha Capital — Alpha One $100k (trailing, with the carry-over trap)
- Daily limit **4%** on the higher of day-start balance/equity. **If you carry an open floating loss
  from the previous day, that loss is subtracted from today's allowance.** An EA holding a swing
  position overnight starts the day with a *reduced* daily budget it never asked for.
- Trailing floor: starts at **$94,000**; at balance $102,000 the floor is **$96,000**; the floor stops
  trailing at +6% ($106,000) and **locks at $100,000** forever after.
- Worked: balance $102,000, floating −$4,100 → equity $97,900. Daily floor = 102,000 − 4,000 = $98,000
  → **daily breach at −$4,100 floating**, on a $41/oz move at 1 lot or a $13.7/oz move at 3 lots.
- Academic anyway: **fully automated execution EAs are banned**, so this account cannot legitimately
  run your strategy.

### 4.7 Maven Trading — $100k 2-Step (recorded for completeness; EAs banned)
- DLL **4%** on the higher of balance/equity at **00:00 UTC**. Day-start $101,000 → floor **$97,000**.
  3 lots, gold −$13.4/oz → breach.
- **The extra hazard: the "M2 Account Saver."** It force-closes all open positions at **2% drawdown**
  and, on first trigger, **permanently cuts your profit split to 50%** for the life of the account.
  Second trigger = account permanently deactivated. So on Maven a normal EA drawdown of 2% is not a
  fail — it is a **permanent 30-point haircut to your payout**. That is a punitive term I have not seen
  at any other firm here, and it interacts terribly with a systematic strategy that routinely breathes
  2%.
- Consistency is **15% of total profit for the largest winning TRADE** (not day) — the strictest
  consistency rule found anywhere in this set. A single good gold trade can lock you out of payout
  until you have grown total profit to ~6.7× that trade.

### 4.8 Lucid Trading (futures; not applicable to XAUUSD)
- End-of-day drawdown: MLL updates only at session close, so intraday recovery is safe. Soft daily
  loss lock on $50k+ accounts locks trading rather than failing the account. Consistency 40%
  (LucidPro) / 20% (LucidDirect). Hedging hard-banned.
- **Structurally the most EA-friendly drawdown model in this whole document** — and completely useless
  to you, because there is no XAUUSD.

---

## 5. COPY TRADING AND MULTI-ACCOUNT — WHERE THE 10-ACCOUNT PLAN BREAKS

**The plan as stated does not survive contact with the allocation caps.** Ten $100k accounts = $1M of
allocation on **one strategy**. Every major firm caps that:

| Firm | Own-account copy trading | Cap that binds | Max $100k accounts on ONE strategy |
|---|---|---|---|
| **E8 Markets** | **Explicitly allowed** across own challenge/performance/personal accounts | $500k on E8 One performance; up to $4.25M across SimFi performance; **per household/IP** | ~**5** on E8 One; more across products |
| **FundingPips** | **Permitted** for accounts under the same individual; native Trade Copier, **4 accounts max in beta** | **$400k** across Evaluation + Master + Prime | **4** |
| **FTMO** | Not explicitly permitted; **suspension risk** if identical strategies exceed the cap | **$400k per trader OR per strategy** | **4** |
| **Alpha Capital** | Signals/shared EA = "group trading" = breach | **$400k** across all plans | n/a (EAs banned) |
| **FundedNext** | **Explicitly allowed** between own accounts | **$300k** total, and **$300k per EA strategy** | **3** |
| **The5ers** | Third-party/external copy prohibited; own-algo `UNVERIFIED` | Hyper Growth **$40k per trader**; High Stakes by account-count matrix | ~1 |
| **Maven** | Copy from another individual prohibited | up to $200k `UNVERIFIED` | n/a (EAs banned) |
| **Lucid** | Trade copiers permitted | `UNVERIFIED` | n/a (futures) |

**Read that again: the phrase "per strategy" at FTMO and FundedNext is deliberate.** These firms
fingerprint trade timing and direction across accounts. Ten accounts running one EA is *exactly* the
pattern the cap exists to catch. Splitting across email addresses is worse — FTMO states holding
multiple accounts through different registrations is not permitted, and Maven runs aggressive IP
monitoring. **Do not attempt it.** The realistic legitimate structure is:

> ~3 accounts at E8 + ~3 at FundedNext + ~3–4 at FundingPips = 9–10 accounts, ~$900k–$1M allocation,
> each firm individually within its cap, and each firm's rules honoured by a per-firm config in the
> engine.

**Also confront the correlation problem, which no rulebook will warn you about:** one EA on ten
accounts is one bet with ten times the fee exposure, not diversification. The day the strategy has its
worst session, **all ten accounts hit their daily limit simultaneously**. Ten challenge fees, ten
resets. Diversification requires *uncorrelated strategies*, not duplicated ones.

---

## 6. COUNTERPARTY RISK

### Industry backdrop — this is not a theoretical risk
- **80–100 prop firms shut down between Feb 2024 and end-2025** — the largest collapse in the sector's
  history. Drivers: MetaQuotes revoking MT4/MT5 licences from firms without proper broker
  relationships; the CFTC action against My Forex Funds; and firms whose payouts were funded by
  incoming challenge fees running dry when growth stalled. `AFFILIATE-ish sources` (propfirmguide,
  tradernotion, mypropgenius — aggregators, some run affiliate links)
- Named casualties with unpaid traders: **True Forex Funds** (licences pulled Feb 2024, closed May
  2024, ~300 traders / ~$1.2M reportedly unpaid); **The Funded Trader** (CEO acknowledged $2M+ in
  denied payouts, early 2024).
- **Regulatory:** Italy's **CONSOB** warned (July 2024) that retail prop challenges simulate trading
  "in a type of finance video game", flagging rigged difficulty and unpaid splits. As of Q3 2026 the
  **CFTC consultation, NFA Notice I-26-12, SEC enforcement and ESMA framing** have ended the grey area;
  NFA-member firms face compliance deadlines through **Nov–Dec 2026**. Expect rule changes, product
  withdrawals and possible geographic exclusions **during** your funded period.
- **Broker-backed vs simulated:** essentially all of these firms run **simulated ("SimFi"/demo)
  environments** — E8 literally names its product stage "SimFi". You are not trading real capital; you
  are buying a performance contract. **This matters enormously:** your payout is an unsecured claim on
  the firm's balance sheet, ranking behind nothing and protected by nothing. There is no segregated
  client money, no FSCS/SIPC, no broker to claim against. A firm that is "regulated" as a company is
  not a regulated broker holding your funds.

### Firm-by-firm
| Firm | Age / standing | Assessment |
|---|---|---|
| **FTMO** | Founded **2015**, 10+ years, **$450M+ paid out** (Finance Magnates, mainstream trade press — not affiliate). Withdrew from US clients early 2024. | **Lowest counterparty risk in the set by a wide margin.** Best-documented rules. The problem is fit, not solvency. |
| **FundedNext** | Large, established, 24-hour payout guarantee (with $1,000 compensation clause). Frequently grouped with FTMO/FundingPips as the top three. | **Low-to-moderate.** Strong payout reputation; the guarantee is a real commercial commitment. |
| **FundingPips** | Established, weekly "Tuesday Pay Day", cited for frequent on-time payouts. | **Low-to-moderate.** |
| **The5ers** | Long-established (pre-dates most of this cohort), suspended US clients early 2024 alongside FTMO. | **Low-to-moderate.** |
| **E8 Markets** | Established brand (formerly E8 Funding). **No payout-complaint or regulatory information surfaced in my searches — that is an absence of evidence, not evidence of absence.** | **Moderate — and specifically under-researched here.** Before allocating, check independent payout-proof threads. |
| **Alpha Capital** | UK-based. | Moot — EAs banned. |
| **Maven Trading** | **Launched 2022.** ~4 years old. Claims 220,000+ registered traders, 25,000+ funded accounts, $130M+ paid (April 2026). Trustpilot ~4.3–4.6 across ~5,000 reviews. Entities in **Dubai and Vancouver**. | **Moderate.** Not a fly-by-night, but a **discount-tier firm** ($18 challenges) — and low fees mean thin margins, which is the exact profile that failed in 2024–25. Documented frictions: strict IP monitoring delaying payouts, high spreads, **$10k payout cap across all accounts per two cycles** — which alone caps a 10-account plan at ~$5k/10 business days. Trustpilot scores for prop firms are heavily incentivised (firms offer rewards for reviews); discount them. Note: most of the "reviews" surfaced were **AFFILIATE** sites. |
| **Lucid Trading** | **Founded early 2025** by AJ Campanella. **Roughly 18 months old.** Reviews positive on payout speed (traders report minutes-fast payouts). | **HIGH counterparty risk — say it plainly.** An 18-month-old firm has never been through a full stress cycle. Fast payouts today prove liquidity today, not solvency in a drawdown. Documented red flags: **stopped publishing prices in Aug 2026** ("get final price at checkout" — opaque pricing is a classic pre-trouble signal); **rules shift between evaluation and funded stages**; a trader reported **Uzbekistan added to restricted countries without warning after they had already passed** — i.e. the firm changes eligibility retroactively. Also **futures-only**, so irrelevant to your plan regardless. |

**Blunt statement of the real risk:** you are proposing to spend real money on ~10 challenge fees to
acquire ~10 unsecured claims on prop firms' balance sheets. The fees are gone the moment you pay them.
The payout is a promise. **Prove one payout from one firm, with your real EA, before buying account
number two.** That is not conservatism, it is the only way to price the counterparty.

---

## 7. RECOMMENDED CONSERVATIVE DEFAULT RISK-ENGINE CONFIG

Design principle: **the engine must be compliant at the strictest firm in the set at all times**, so a
single EA config can be deployed anywhere without re-tuning. Every value below is the harshest
constraint found across firms, then buffered. Per-firm overrides can loosen it later; the *default*
must be the superset.

```yaml
# ---- account model ----
account_currency: USD
equity_source: TICK            # NEVER balance. Every firm measures equity. Poll on every tick.
poll_interval_ms: 250          # max staleness before a floating loss can outrun the check

# ---- daily loss ----
daily_loss_limit_pct: 3.0      # strictest found (FundingPips Zero / 2 Step Pro)
daily_loss_basis: MAX(day_start_balance, day_start_equity)   # harshest anchor across firms
daily_loss_includes_floating: true
daily_loss_soft_stop_pct: 1.0  # stop opening new positions
daily_loss_hard_flat_pct: 1.5  # force-close everything; 50% of the strictest limit
carry_over_floating_reduces_budget: true   # Alpha Capital behaviour, applied everywhere

# ---- daily anchor / reset (the DST trap) ----
# Firms reset at 00:00 UTC (Maven), 00:00 CE(S)T (FTMO), 00:00 GMT+2/+3 (FundedNext, Alpha).
# Do not pick one. Evaluate the day-start anchor at ALL of them and use the WORST floor.
daily_anchor_times_utc: ["21:00", "22:00", "23:00", "00:00"]
daily_anchor_rule: USE_MOST_RESTRICTIVE
dst_aware: true                # recompute offsets from tz database, never hard-code

# ---- max drawdown ----
max_drawdown_pct: 6.0          # strictest overall floor found
max_drawdown_model: TRAILING   # assume trailing ALWAYS; never assume static
trailing_basis: MAX(highest_closed_balance, highest_equity)  # harsher than either alone
trailing_updates: CONTINUOUS   # harsher than EOD-only; safe under EOD firms too
trailing_locks_at_initial_balance: false   # do not rely on the lock existing
max_drawdown_soft_stop_pct: 3.0
max_drawdown_hard_flat_pct: 4.0

# ---- position sizing (derived from the 3% daily limit on XAUUSD) ----
risk_per_trade_pct: 0.35
max_total_open_risk_pct: 0.70
max_concurrent_positions: 2
max_lots_per_100k: 1.0         # 1.0 lot = 100 oz; a $30/oz spike = 1.0% of a $100k account
hard_stop_loss_required: true  # every position carries a broker-side SL, not a virtual one
max_stop_distance_usd_per_oz: 12.0
slippage_buffer_pct: 0.25      # assume fills worse than modelled; gold gaps

# ---- consistency ----
max_single_day_profit_pct_of_total: 15    # strictest day-based is 20% (LucidDirect); buffered
max_single_trade_profit_pct_of_total: 15  # Maven's largest-TRADE rule, the strictest found
min_profitable_days_before_payout: 7      # FundingPips
min_profitable_day_threshold_pct: 0.5     # FundingPips
min_trading_days: 10                      # exceeds every minimum found

# ---- news ----
news_blackout_before_min: 300   # 5 HOURS - FundingPips flags trades opened <5h pre-news
news_blackout_after_min: 5
news_no_open_or_close_window_min: 5   # +/- 5 min hard freeze on affected pairs
news_impact_filter: HIGH        # red folder; XAUUSD => USD events: NFP, CPI, FOMC, PPI, GDP
flatten_before_news: true       # do not merely stop opening - be flat

# ---- session / calendar ----
weekend_hold: false             # FundingPips prohibits; be flat regardless
friday_flatten_utc: "20:00"
overnight_hold: false           # default off (FTMO Standard restricts); per-firm override to enable
rollover_blackout_utc: ["21:55", "22:10"]   # The5ers bans rollover scalping

# ---- strategy conduct ----
min_trade_duration_sec: 120     # defeats "HFT / tick scalping" classification everywhere
martingale: false               # no size-up after loss, ever
grid: false                     # explicitly prohibited at Maven
hedging: false                  # hard-banned at Lucid; group-hedging banned at Maven
arbitrage_latency: false
ea_source_code_owned: true      # REQUIRED by The5ers and FundingPips - keep VCS history as proof

# ---- multi-account governance ----
max_total_allocation_per_firm_usd: 300000   # strictest cap found (FundedNext), applied to all
max_total_allocation_per_strategy_usd: 300000
max_accounts_per_firm: 3
distinct_registration_per_firm: false       # NEVER multi-register; FTMO prohibits, Maven IP-monitors
copy_trade_only_within_own_accounts: true
household_ip_aware: true                    # E8 applies caps per household/IP
stagger_entries_ms: 0                       # do NOT randomise to disguise copying - that is evasion

# ---- payout policy ----
withdraw_at_first_eligible_cycle: true      # counterparty risk is real; do not let profit accumulate
max_unwithdrawn_profit_pct: 4.0
```

**Two engine-design notes that matter more than any single number:**

1. **The floating-loss monitor is the whole product.** Balance-based checks are useless — every worked
   example in §4 breaches on unrealised P/L. If the engine only evaluates on trade close, it will
   watch accounts die.
2. **Model the daily anchor as a set, not a scalar.** The four different reset clocks in this document
   are the most likely source of a silent bug that fails an account at 23:30 UTC on a Sunday in
   October.

---

## 8. EVERY RULE I COULD NOT VERIFY — DO NOT ENCODE THESE

| Firm | Unverified item | Why it matters |
|---|---|---|
| **FTMO** | Whether the 2-step max loss is **static 10%** or **ratchets** on prior-day 00:00 balance highs | Changes whether a profitable-then-drawdown EA survives. **Encode the harsher (trailing) reading until confirmed.** |
| **FTMO** | Presence/absence of any consistency rule | Could block a payout after passing |
| **FTMO** | Current challenge pricing | Budgeting only |
| **FundedNext** | Headline profit split per model; exact challenge pricing; the size of the **EA usage fee** | The EA fee is a real recurring cost across 10 accounts |
| **FundedNext** | Whether the 6–10% max loss trails on **every** model or only Instant/1-Step | Core drawdown mechanic |
| **The5ers** | Consistency rule terms; news window; weekend/overnight policy; whether **own-EA copy trading across own accounts** is permitted | The own-account copy question is decisive for including them at all |
| **FundingPips** | Exact daily-anchor **clock time**; whether the 6% max loss is static or trailing on 2 Step Pro | Static vs trailing is the difference between surviving and not |
| **Alpha Capital** | Exact news window; minimum trading days; pricing | Moot — EAs banned |
| **E8 Markets** | **E8 One's headline overall drawdown %** (4% dynamic was described but the product's total allowance is unclear); pricing; per-product allocation caps beyond E8 One's $500k; daily-anchor server offset | E8 is the top recommendation — **these must be confirmed first** |
| **E8 Markets** | Any payout-complaint history | No data found either way |
| **Maven** | Exact minimum trading days per model; whether a hard allocation cap exists; per-model DLL breach consequence | Moot — EAs banned |
| **Lucid** | Everything about copy-trade caps and minimum days | Moot — futures only |
| **All firms** | **Martingale / grid explicit permissibility** (only Maven confirmed banning grid) | Assume banned everywhere |
| **All firms** | Whether **XAUUSD-specific** leverage or lot caps apply | Gold often carries lower leverage than FX; verify per firm before sizing |

---

## 9. RANKING FOR AN EA + MULTI-ACCOUNT XAUUSD PLAN

Scored 1–5, higher is better.

| Firm | Rule clarity / EA-friendliness | Drawdown model vs losing streaks | Copy-trade permissiveness | Payout reliability | **Total** |
|---|---|---|---|---|---|
| **E8 Markets** | 4 — EAs allowed, clear help centre | 2 — **EOD dynamic ratchet is hostile**; Classic's static 8% is much better | **5 — only firm to explicitly bless own-account copying, caps up to $500k–$4.25M** | 3 — no adverse data, but none confirming either | **14** |
| **FundedNext** | 4 — EAs welcomed, but an EA fee applies and "distinct strategy" language cuts against copying | 3 — 6–10% by model, ratchets on new highs; **hard fail on daily breach** | 4 — explicit, but **$300k cap = 3 accounts** | **5 — 24h payout guarantee** | **16** |
| **FundingPips** | 3 — **self-written EAs fully allowed with proof**, third-party crippled to risk-manager only | 3 — 6% static-ish, but **3% daily is brutal for gold** | 4 — permitted, native copier, 4-account beta cap, $400k | 4 — weekly Tuesday payouts | **14** |
| **The5ers** | 3 — EAs allowed **only if you own the source**; HFT/rollover bans | **5 — 10% absolute static drawdown, and daily breach is a PAUSE not a fail. Best structure here for a streaky EA.** | 1 — external copy prohibited, **$40k Hyper Growth cap** | 4 | **13** |
| **FTMO** | 4 — best documentation in the industry | 3 — pending the static/trailing ambiguity | 1 — **$400k per trader OR per strategy + explicit suspension language** | **5 — 10 years, $450M+ paid** | **13** |
| **Alpha Capital** | **1 — automated execution EAs banned outright** | 2 — trailing, carry-over floating penalty | 1 — signals = group trading = breach | 3 | **7** |
| **Maven** | **1 — EAs prohibited**; plus the M2 50%-split penalty at 2% DD | 3 — static 8% on 2-step is decent | 1 | 3 — 4 yrs, discount tier, $10k payout cap | **8** |
| **Lucid** | n/a — **futures only, no XAUUSD** | 5 (EOD, soft daily lock) — irrelevant | 4 — copiers allowed | 2 — **18 months old, opaque pricing since Aug 2026, retroactive country restrictions** | **excluded** |

### Recommendation

1. **Start with ONE account.** FundedNext $50k Stellar 2-Step or E8 Classic $50k. Run the real EA.
   **Take one payout.** Until money has moved from a prop firm to your bank, every projection here is
   fiction.
2. **Then scale to 3 firms, not 1:** ~3 accounts at **E8 Markets** (prefer **E8 Classic**'s static 8%
   over E8 One's dynamic ratchet), ~3 at **FundedNext**, ~3–4 at **FundingPips**. That reaches ~10
   accounts while staying inside every per-firm and per-strategy cap.
3. **Use FTMO for exactly one flagship account** — best counterparty in the industry — and run a
   *deliberately different* configuration on it (different timeframe or filter set) so it is not
   caught by the per-strategy cap. Do not put ten FTMO accounts on one EA; the rules say what happens.
4. **Exclude Lucid** (no XAUUSD), **Maven** (EAs banned; the M2 profit-split penalty is punitive) and
   **Alpha Capital** (automated execution EAs banned).
5. **Build the engine to §7's superset**, then add per-firm override files. Do not tune the EA per firm
   — tune the *guardrail*, and let the EA stay identical.
6. **Budget the fees as a total loss.** Ten challenge fees at $30–$300 each is $300–$3,000 with a
   realistic expectation of buying several resets. If that number is uncomfortable, the answer is
   fewer accounts, not cheaper firms — cheap firms are the ones that folded in 2024–25.

---

## 10. SOURCES

**Official firm domains** (help centres / FAQ / rules pages — reached via search summaries only;
direct fetch was blocked by this session's egress policy, see §0):

- FTMO — https://ftmo.com/en/trading-objectives/ · https://ftmo.com/en/forbidden-trading-practices/ · https://ftmo.com/en/faq/how-many-accounts-can-i-have/ · https://ftmo.com/en/faq/which-instruments-can-i-trade-and-what-strategies-am-i-allowed-to-use/ · https://ftmo.com/en/faq/can-i-trade-news/ · https://ftmo.com/en/faq/do-i-have-to-close-my-positions-overnight/ · https://ftmo.com/en/reward-growth-and-scaling-plan/ · https://academy.ftmo.com/lesson/maximum-daily-loss/ · https://academy.ftmo.com/lesson/maximum-loss/
- FundedNext — https://help.fundednext.com/en/articles/8019811-how-can-i-calculate-the-daily-loss-limit · https://help.fundednext.com/en/articles/8019812-how-can-i-calculate-the-maximum-loss-limit · https://help.fundednext.com/en/articles/8394309-when-does-the-daily-loss-limit-reset-with-fundednext-cfd · https://help.fundednext.com/en/articles/8019805-what-is-the-copy-trading-rule-at-fundednext · https://help.fundednext.com/en/articles/8020763-is-ea-allowed-in-fundednext · https://help.fundednext.com/en/articles/8020351-what-are-the-restricted-prohibited-trading-strategies · https://fundednext.com/general-rules/cfds/trading-objectives · https://fundednext.com/package-comparison
- The5ers — https://help.the5ers.com/what-is-drawdown-and-how-is-it-calculated/ · https://help.the5ers.com/what-is-the-drawdown-rule-for-high-stakes/ · https://www.the5ers.com/faqs/prohibited-trading-practices/ · https://the5ers.com/faqs/can-i-use-an-ea-expert-advisor-can-i-set-a-stealth-mode-stop-loss/ · https://help.the5ers.com/hyper-growth/ · https://help.the5ers.com/how-many-the5ers-accounts-can-i-have/ · https://the5ers.com/high-stakes/ · https://the5ers.com/bootcamp/
- FundingPips — https://fundingpips.com/trading-objectives · https://help.fundingpips.com/hc/en-us/articles/34505029138449-Trading-Conduct-and-Security-Standards · https://help.fundingpips.com/hc/en-us/articles/34502027344017-2-Step-Pro-Model · https://help.fundingpips.com/hc/en-us/articles/34501809112081-2-Step-Standard · https://help.fundingpips.com/hc/en-us/articles/34504137479441-News-Trading-Weekend-Holding · https://help.fundingpips.com/hc/en-us/articles/49580068780817-Trade-Copier · https://fundingpips.com/blog/fundingpips-maximum-allocation
- Alpha Capital — https://help.alphacapitalgroup.uk/en/articles/6934210-what-are-the-daily-risk-limits-and-how-do-they-work · https://help.alphacapitalgroup.uk/en/articles/6934220-what-is-the-maximum-total-loss · https://help.alphacapitalgroup.uk/en/articles/6934236-can-i-use-an-expert-advisor-ea · https://help.alphacapitalgroup.uk/en/articles/6934275-what-are-prohibited-trading-strategies · https://help.alphacapitalgroup.uk/en/articles/10097421-alpha-one
- E8 Markets — https://help.e8markets.com/en/articles/11769446-daily-drawdown · https://help.e8markets.com/en/articles/11782996-dynamic-drawdown · https://help.e8markets.com/en/articles/11864596-eod-dynamic-drawdown · https://help.e8markets.com/en/articles/11775980-e8-one · https://help.e8markets.com/en/articles/12041696-e8-classic · https://help.e8markets.com/en/articles/6929927-trading-policies-and-prohibited-trading-strategies · https://help.e8markets.com/en/articles/9453469-can-i-copy-trades-or-trade-as-a-team · https://help.e8markets.com/en/articles/11755943-e8-signature-forex
- Maven Trading — https://maventrading.com/day-trading-rules · https://maventrading.com/faqs · https://maventrading.com/terms-and-conditions · https://maventrading.com/pricing · https://maventrading.com/challenges/1-step · https://maventrading.com/challenges/2-step
- Lucid Trading — https://support.lucidtrading.com/en/collections/12931279-rules-and-guidelines · https://support.lucidtrading.com/en/articles/12890122-lucidpro-daily-loss-limit · https://support.lucidtrading.com/en/articles/12890092-lucidpro-payouts · https://support.lucidtrading.com/en/articles/12890164-luciddirect-payout-objectives · https://support.lucidtrading.com/en/articles/11508978-approved-products-and-commissions · https://lucidtrading.com/general-faq/

**Non-affiliate / trade press**
- Finance Magnates — FTMO $450M+ paid out at 10 years: https://www.financemagnates.com/forex/ftmo-announces-over-450-million-paid-out-as-prop-trading-firm-turns-10/
- The Industry Spread — regulators closing in on retail prop trading 2026: https://theindustryspread.com/retail-prop-trading-regulation-2026-my-forex-funds-cftc/ · https://theindustryspread.com/eu-regulators-prop-trading-mifid-ii-perimeter/
- Track360 — prop firm regulation roundup Q3 2026: https://track360.io/blog/prop-firm-regulation-news-roundup-q3-2026

**⚠️ AFFILIATE / COMMISSION-EARNING SITES — used only for shutdown lists and reputation colour, never for rule values:**
- https://thepropfirmguide.com/prop-firms-that-shut-down/ — **AFFILIATE**
- https://www.tradernotion.com/blog/prop-firms-that-shut-down-in-2023-2026 — **AFFILIATE**
- https://mypropgenius.com/closed-firms/ — **AFFILIATE**
- https://propfirmquiz.com/flagged/ — **AFFILIATE**
- https://propfirmmatch.com/prop-firms/maven-trading — **AFFILIATE**
- https://thetrustedprop.com/prop-firms/maven-trading — **AFFILIATE**
- https://blueberryfunded.com/maven-trading-prop-firm/ — **AFFILIATE** (and a competing prop firm)
- https://proptradingvibes.com/blog/maven-trading-legit — **AFFILIATE**
- https://clearank.com/prop-trading-firms/maven-trading-review/ — **AFFILIATE**
- https://vettedpropfirms.com/lucid-trading-review/ — **AFFILIATE**
- https://damnpropfirms.com/prop-firms/lucid-trading-rules-explained/ — **AFFILIATE**
- https://propfirmperk.com/guides/lucid-trading-review-2026 — **AFFILIATE**
- https://propvator.com/blog/maven-trading-static-drawdown/ — **AFFILIATE**
- https://lunefi.com/blog/maven-trading-complete-guide-to-rules-and-payouts — **AFFILIATE**
- https://propjournal.net/prop-firms/maven-trading/rules — **AFFILIATE**

**Standing caveat:** prop firm rules change frequently and without notice — Lucid retroactively added a
restricted country and stopped publishing prices mid-2026; FTMO and The5ers dropped US clients in 2024.
**Re-verify every value in §7 against the official help centre immediately before any account purchase,
and re-verify quarterly thereafter.** Nothing in this document is a substitute for reading the firm's
own rules page on the day you pay.

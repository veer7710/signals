# JARVIS — overnight research report
Session 2026-08-27/28 · branch `claude/jarvis-ai-operating-system-2xaclm`

**Status: PARTIAL.** Five deep-research agents (liquidity evidence, JARVIS
architecture, quant strategy landscape, funded accounts, deep EA audit) were
launched and all five were killed by the account's session usage limit before
writing their findings. Those five topics remain OPEN and are queued as the
first actions for the next session.

What follows is what was actually measured and verified tonight. Every number
here came from code that ran; none is estimated.

---

## 1. The single most important finding

**Your instinct to protect profit early is the thing destroying your EA.**

You described it yourself: the EA is "focused on indubitable profits" and
"never closes right at the peak". I tested that directly — 11 exit rules over
an identical set of ~845 entries, on four markets, with full costs.

Expectancy per trade:

| Exit rule | GOLD | US500 | EURUSD | GBPUSD |
|---|---|---|---|---|
| **Break-even at 0.5R, then trail** | **-0.161R** | **-0.188R** | **-0.308R** | **-0.293R** |
| Fixed 3R target | +0.181R | -0.025R | -0.155R | -0.133R |
| Hold 20 bars | +0.201R | -0.004R | -0.116R | -0.120R |

Moving to break-even early is the **worst rule on all four markets**. It drops
the win rate to 15-20%, because ordinary noise scratches the trade out before
the rare large winner — the one that pays for everything — can develop.

This is not a tuning problem. Protecting profit early and capturing big moves
are mathematically opposed. Your EA is configured on the losing side.

## 2. "It never closes at the peak" — that is normal, and permanent

I ran an ORACLE exit that closes every trade at its exact best price. It
requires knowing the future, so it is not tradeable. It returns **+3.019R** per
trade on gold. The best real exit returns **+0.201R**.

A perfect exit would be about **15x better** than the best achievable one.

That gap is not a defect in your EA. Every trader alive pays it. Chasing it is
what produced 748 parameters. **Stop trying to close at the peak.**

## 3. Your entries are the bigger problem

In my baseline, 23% of trades never reached 0.3R profit. In your EA's own
logs: **153 of 188 losers, 81%, never went £0.30 green.**

No exit rule rescues a trade that was wrong immediately. Fix entries first.

## 4. I tested 8 strategies on 4 markets. Nothing passed.

Expectancy in R, after spread, slippage and commission:

| Strategy | GOLD | US500 | EURUSD | GBPUSD | markets +ve |
|---|---|---|---|---|---|
| ma_cross | +0.200 | +0.046 | +0.008 | -0.052 | 3/4 |
| donchian_trend | +0.198 | +0.130 | -0.146 | -0.067 | 2/4 |
| tsmom | +0.076 | +0.044 | -0.151 | -0.290 | 2/4 |
| **liquidity_sweep** | +0.001 | -0.033 | -0.170 | -0.238 | **1/4** |
| ema_pullback | -0.142 | -0.004 | -0.247 | -0.080 | 0/4 |
| mean_revert | -0.062 | -0.034 | -0.096 | -0.084 | 0/4 |
| orb (opening range) | -0.140 | -0.089 | -0.291 | -0.299 | 0/4 |

Then I put the best one through the full gauntlet. It failed too: `ma_cross`
on gold has a t-statistic of 1.22 (needs >2), only 3 of 6 walk-forward periods
positive — and all three are the recent gold rally — and makes **+0.704R on
longs against -0.199R on shorts.** That is a bull market, not an edge.

**Nothing I tested reaches PROMISING.** That is the honest state.

## 5. What I changed my mind about

Earlier in the session I rated `donchian_trend` PROMISING (+0.198R, 5/6
walk-forward folds). Testing it on three more markets showed it negative on all
three. **Downgraded to UNPROVEN.** An edge in one market and not three others
is far more likely to be an artifact of that market's history.

I also found and fixed a bug in my own walk-forward code that was producing
impossible 0% win rates, and wrote regression tests so it cannot recur silently.

## 6. Liquidity sweeps — where this stands

Two independent tests, both negative: positive in 1 of 4 markets, and the edge
dies as costs rise (+0.001R at normal spread, -0.061R at 3x).

This is **not** a final verdict on liquidity as a concept. I tested one
implementation on one timeframe. The deeper evidence review — Osler's
stop-cascade research, systematic tests of ICT/SMC concepts, the Turtle Soup
lineage — is one of the five research jobs that got cut off. That is genuinely
unfinished, not concluded.

What I can say: the concept is **UNPROVEN**, and your own `LiquidityEngine_v2.pine`
already contains the strongest warning against it, at line 126: a 7-year test
on 2.55M EURUSD bars found the best of 54 variations reached 56% hit rate and
**not one was profitable after a 0.5-pip cost.** You wrote that down yourself.

## 7. Where the real evidence probably lives

Every test tonight was 1-hour bars on four correlated instruments. That is
close to the hardest possible version of this game: highest cost drag, lowest
signal, no diversification.

The published trend-following evidence (Moskowitz/Ooi/Pedersen; AQR's "A
Century of Evidence") is on **daily-and-slower timeframes across 50+ diversified
instruments.** Not intraday, not one symbol.

**You are looking in the hardest place.** The single highest-value next test is
daily data across 20-40 uncorrelated markets with simple trend rules. The repo
does not hold that data yet.

## 8. The £200/day question, honestly

You want £200/day from the EA. Tonight's measurements say the strategy to
produce that does not exist yet — not in your EA, and not in any of the 8
alternatives I tested. That is not pessimism, it is the state of the evidence.

What DOES exist now is the machinery to find out fast and honestly: an engine
that cannot lie to you, 17 regression tests including one proving it finds no
edge in random data, and a scan that kills a bad idea in about 30 seconds.

That machinery is the real progress. It is what stops the next twelve months
becoming another twenty versions of v19.

## 9. What NOT to pursue

- **Do not run v19.18 live.** Its own logs record -£252 across 188 losers.
- **Do not patch it to v19.19.** Twenty rounds of patching is the failure mode.
- **Do not add parameters.** 748 is already ~40x too many.
- **Do not use early break-even or tight trailing stops.** Measured as the
  worst rule on four markets.
- **Do not judge a system by win rate.** 30% wins at 3R beat 53% wins at 1R.
- **Do not open 40 funded accounts on one strategy.** FTMO caps allocation at
  $400k per trader *or per strategy*, and identical fills across firms trigger
  copy-trade detection and dual payout denial. It is also not diversification —
  40 accounts on one strategy is 40x leverage on a single bet, and they all
  breach on the same day.

## 10. Still open (the five cut-off research jobs)

1. Liquidity/ICT evidence review — Osler, systematic SMC tests, Turtle Soup
2. JARVIS architecture — agents, memory, voice, MCP, dashboard, install list
3. Quant strategy evidence landscape + anti-overfitting rules
4. Funded-account economics and multi-account risk architecture
5. Line-by-line EA audit (exit paths, sizing, martingale check, bug hunt)

These are queued in `NEXT_ACTIONS.md` and should run first next session.

# Exit experiment — "why does it never close at the peak?"

Run: `python3 JARVIS/research/exit_study.py GOLD 1h`
Identical entries across every policy (overlapping positions allowed, so the
exit rule cannot change WHICH trades are taken). Costs charged on every fill.

## The headline

**The instinct to protect profit early is the single worst exit rule tested,
on every market.**

Expectancy per trade, "break-even at 0.5R then trail" vs "fixed 3R target":

| Market | BE@0.5R + trail | best simple exit | difference |
|---|---|---|---|
| GOLD | **-0.161R** | +0.201R (time 20) | 0.36R |
| US500 | **-0.188R** | +0.050R (fixed 2R) | 0.24R |
| EURUSD | **-0.308R** | -0.084R (fixed 1R) | 0.22R |
| GBPUSD | **-0.293R** | -0.120R (fixed 2R) | 0.17R |

Worst on all four. Win rate collapses to 15-20% because the trade is
repeatedly scratched at break-even by ordinary noise, so the wins that pay for
the losses never get the room to happen.

**This is exactly what Veer described**: the EA is "focused on indubitable
profits", and that focus is the mechanism destroying it. It is not a tuning
problem. Protecting profit early and capturing big moves are mathematically
opposed, and his EA is configured for the losing side of that trade-off.

## The peak is not capturable — and that is normal

An ORACLE exit that closes at the exact best price of every trade (impossible;
requires knowing the future) returns **+3.019R** per trade on gold. The best
real, tradeable exit returns **+0.201R**.

A perfect exit would be roughly 15x better than the best achievable one. The
gap — about 2.8R per trade — is not a defect in anyone's EA. It is the price
of not knowing where the top is, and every trader on earth pays it.

**So "it never closes right at the peak" is not a bug to be fixed.** No system
closes at the peak. Chasing it is what produced 748 parameters.

## Why profits get given back — the real distribution

Gold, 845 trades:

| Measure | Value |
|---|---|
| Median best-ever profit (MFE) | 1.12R |
| 75th percentile | 3.89R |
| 90th percentile | 7.51R |
| Maximum | 102.68R |
| Median drawdown before that (MAE) | 1.16R |

The distribution is extremely skewed. Most trades never go far; a few go
enormously far. **Total profit comes from the tail.** Any rule that caps the
tail to protect the median — a break-even stop, a tight trail, a fixed small
target — cuts off the only trades that pay.

Also: **23% of trades never reached 0.3R profit at all.** Those are entry
failures; no exit rule can rescue them. In Veer's own EA that figure was
**81%** (153 of 188 losers). His entries are far worse than this baseline, so
exits are not even his main problem.

## What this means for the rebuild

1. **Do not move to break-even early.** It is the most expensive habit in the
   file, worth roughly 0.2-0.4R per trade.
2. **Let winners run.** Fixed 3R or a time-based hold beat every trailing
   variant on gold.
3. **A low win rate is correct** for this style. 30% wins with 3R targets
   beats 53% wins with 1R targets (+0.181R vs +0.054R). Judging the system by
   win rate will push every decision the wrong way.
4. **Fix entries before exits.** 23% dead trades here, 81% in his EA.

## Caveat, stated plainly

These exit results use ONE entry type (Donchian breakout). A different entry
could interact differently with exits. The break-even finding replicated
across four markets, which is strong; the ranking of the other exits did not
replicate as cleanly and should be treated as gold-specific until retested.

## This experiment also DAMAGED an earlier finding

`donchian_trend` was rated PROMISING (E-004) on gold: +0.198R, 5/6
walk-forward folds positive. It is **negative on US500, EURUSD and GBPUSD**
across almost every exit rule.

An edge that appears on one symbol and vanishes on three others is far more
likely to be an artifact of gold's 2024-2026 bull run than a structural edge.
E-004 is downgraded from PROMISING to UNPROVEN. This is the adversarial test
(A-001) partially executing itself, and it went against the candidate.

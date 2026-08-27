# Lessons learned

## L-001 — A capped take-profit with an ATR-scaled stop silently destroys R:R
The deleted signal system used `TP = min(60 pips, ...)` while
`SL = 1.2 x ATR` with no cap. As gold's volatility rose, the stop grew to
178 pips while the target stayed pinned at 60 — a 0.34 reward:risk. It then
needed a ~75% win rate merely to break even, and its measured 70% win rate
felt like success while the account bled.
**Rule:** the target and the stop must scale TOGETHER. Fix the reward:risk
ratio, then let volatility scale both. Encoded as the deliberately-broken
control strategy `capped_target_trap` in `strategies.py` — a regression
canary. If a future "improvement" ever scores near it, something is wrong.

## L-002 — Precomputed per-bar state must be rebuilt per data slice
See FAILURE_LOG F-001. Any strategy that precomputes arrays indexed by bar
position is bound to the series it was built from. Slicing the data without
rebuilding the strategy silently corrupts every index.

## L-003 — A high win rate is not an edge
The deleted system won 70% of trades and was still statistically
indistinguishable from random. Win rate is meaningless without the
reward:risk ratio beside it. The only honest summary statistic is
expectancy in R, with its t-statistic.

## L-004 — One outlier trade is not a track record
That system's entire profit (+327 of +327 total) came from ONE swing trade
that happened to risk 100% of the account and win. Strip it out and 30
intraday trades netted +34 over 40 days. Always report results with and
without the largest contributor.

## L-005 — Extreme numbers are a bug signal, not a discovery
0% win rates, 99% win rates, and enormous profit factors almost always mean
a broken backtest, not a found edge. Investigate before celebrating.

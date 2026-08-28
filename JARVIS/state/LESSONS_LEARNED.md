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

## L-006 — One web search is not research (and it nearly cost us)
On 2026-08-27 I recommended installing OmniRoute after a single search that
returned enthusiastic write-ups. Deeper verification the next day found it
ships TLS/JA3-JA4 fingerprint stealth — a feature whose purpose is defeating
provider anti-abuse detection — plus a disclosed default-secret auth bypass.
I had recommended, in the same session where I refused to evade usage limits,
a tool built to evade usage limits.
The URL I quoted was also not the canonical repository.
**Rule:** before recommending any software be installed, verify the canonical
source (GitHub API, not search-engine ranking), check what the tool actually
does rather than what its marketing says, and check for known vulnerabilities.
Popularity in search results is not evidence of safety or legitimacy.

## L-007 — Parallelism is a budget, not a free lunch
Five research agents launched at once were all killed by the usage limit
before writing their findings (F-003). Multi-agent work reportedly costs on the
order of 15x a chat interaction in tokens. Launch in batches of 2-3, and always
checkpoint verified work to disk before spawning anything.
Corollary from the architecture research: parallelise READS (research, sweeps,
log analysis), never WRITES (two agents editing the same code).

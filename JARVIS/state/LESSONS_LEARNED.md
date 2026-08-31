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

## L-008 — A silent no-op is worse than a crash
A `str.replace` whose anchor does not match returns the input unchanged and
looks like it worked. That shipped a non-compiling file to the user (F-005).
Two rules now:
- Every programmatic edit asserts its anchor was found before writing.
- Every generated artifact gets a checker that verifies the property that
  actually matters. The audit that passed the broken file checked declaration
  ORDER; the bug was declaration EXISTENCE. Auditing the wrong property is
  indistinguishable from not auditing at all.
Both checkers in `JARVIS/tools/` are regression-tested against the real bug
they were written for — a checker that has never been shown to fail on known-
bad input is not evidence of anything.

## L-012 — Every stop-order backtest here is optimistic, and by how much is now known
Found by the A4 agent while self-testing its own simulator on a driftless random
walk: its gross payoff came back t +8.35 when it should have been zero. Not a
simulator bug — **intrabar discretisation overshoot**. Assuming a stop order
fills AT its level is free money, because by the time the level is crossed the
true price is already past it. The bias shrank from +0.36 to +0.12 as the
simulated path was refined, which is the signature of a discretisation artefact
rather than an edge.

This applies to every backtest in this repo, since all of them resolve stops by
checking whether a bar's low or high crossed a level and then booking the fill
at that level.

**How much it matters, measured rather than assumed.** `engine.py` already
charges half-spread plus slippage adversely on both fills (lines 194 and 215),
so the effect is partly priced. Re-running the E-050 random-entry control at
slippage from 0.05 up to 0.80 - sixteen times the default, cost rising 0.40 to
1.90 - the signal stays inside the random band at every level:

| slippage | signal | random median | random 95th | inside? |
|---|---|---|---|---|
| 0.05 | +0.321 | +0.220 | +0.424 | yes |
| 0.20 | +0.312 | +0.211 | +0.415 | yes |
| 0.80 | +0.275 | +0.174 | +0.377 | yes |

So the optimism is real but does not carry any conclusion in this repo. It
biases everything in the same direction, and every headline result here is
already zero or negative — a bias toward optimism can only make a negative
verdict safer. It would matter enormously the moment something looked positive,
which is exactly when it must be remembered.

## L-013 — Why nothing works, stated mathematically
Also from A4, and it is the deepest result the project has produced. A spot
position's payoff is LINEAR in price and every exit is a stopping time. By the
optional stopping theorem, on a martingale ANY non-anticipating exit rule has
zero expected gross return. E-037 measured these series to be martingales at
15m and 1h.

That is not one exit rule failing. It is the entire class of exit rules failing,
for a reason that no amount of searching can overturn. Monetising volatility
requires CONVEXITY, and convexity is the one thing a spot account cannot buy.

Confirmed numerically: a straddle plus its fade equals exactly -2 x legs x cost,
to 3.18e-13. There is no arrangement of spot positions that escapes it.

The two live consequences: non-directional structure is closed for spot
instruments and should not be revisited, and it reopens instantly if an
options-capable account ever exists. The optional-stopping argument needs the
martingale property, which was only measured at 15m and 1h - **M1 is not
covered by it**, which is one more reason M1 is the strongest open branch.

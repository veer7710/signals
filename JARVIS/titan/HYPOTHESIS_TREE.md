# Hypothesis tree — status of every branch

Legend: **DEAD** tested and failed · **OPEN** untested · **BLOCKED** needs data
· **PARTIAL** tested in one form only

## DIRECTIONAL EDGE FROM PRICE PATTERN
- Liquidity sweep, fade — **DEAD** (44.5% vs 49.2% coin flip)
- Liquidity sweep, follow — **DEAD** (54.1% raw, does not survive costs + MTC)
- SuperTrend flip — **DEAD** (E-030, live: -0.58R/trade, TP 0 of 12)
- Donchian / MA cross / TSMOM / ORB / mean-revert — **DEAD**
- Order block — **DEAD** (2/8 markets, best OOS t +1.29)
- Fair value gap / inverse FVG — **DEAD** (2/8)
- Trend pullback to MA — **DEAD** (1/8)
- Breakout from compression — **DEAD** (0/8)
- Premium/discount — **DEAD** (1/8)
- Structure bias (BOS/CHoCH) as a filter — **DEAD** (E-036)
- Confluence score of all the above — **DEAD** (5/8, backwards on gold 15m)
- **Root cause: E-037. The series has no directional persistence to exploit.**

## ENTRY EXECUTION (not edge, but real)
- Limit entry on the pullback — **PARTIAL**, +0.451R vs +0.321R OOS on GOLD 1h,
  t +2.47, halves disagree. Cuts drawdown; does not create an edge.
- Signal-to-fill delay — **MEASURED**, materially changes results, now modelled
- 71.7% of signals retrace through the entry within 3 bars — **MEASURED**

## FILTERS
- ADX < 35 — **PARTIAL**, the only factor that separated alone (4/5, +0.324R)
- ATR vs median, session, DEMA slope, room-to-run — **DEAD** (<=5/8; room NEGATIVE)

## VOLATILITY, NON-DIRECTIONAL — **OPEN, HIGHEST VALUE**
Returns being unpredictable does not make VOLATILITY unpredictable; volatility
clustering is among the most robust facts in finance. Untested here.
- Is ATR/realised vol autocorrelated in this data?
- Does compression predict expansion SIZE (not direction)?
- Can that be traded without a directional bet, or used to size one?

## CONDITIONAL / REGIME — **OPEN**
A variance ratio tests unconditional behaviour. Untested:
- Hour-of-day and day-of-week expectancy
- Behaviour in the N bars after a large-range bar
- Behaviour after a gap, after an inside-bar run
- The transition low->high volatility rather than the level

## MICROSTRUCTURE — **BLOCKED on M1 data**
Where a real edge is most plausible and least tested. Bid-ask bounce produces
genuine negative autocorrelation at 1-tick and 1-minute horizons that does not
exist at 15m. Blocked on `JARVIS/tools/GET_M1_DATA.md`.

## COST AND SIZING — **MEASURED**
- 15m FX round-trip cost is 46-49% of a typical bar. Structurally untradeable.
- Minimum lot forces ~21% account risk per trade on a 60 pound account at a
  12-point stop. Leverage (PU Prime 1:500) is not the constraint; stop size is.

# PLAN2.md — pre-registered SIGNAL SCREEN
Written before running. Purpose: find out whether ANY simple signal on gold carries
information that survives the spread, or whether the problem is the instrument/timeframe.

## Method
- Candidates computed from OHLC only, on closed bars, no lookahead.
- Information measure: forward close-to-close return from the signal bar, in the signal's
  direction, at horizons of 1/2/3/5/10/20 BARS of that timeframe. No costs, no exits.
- Timeframes: M1, M5, M15, M30, H1, H4.
- Data: 2019-01-01 onward (100% broker data), 2.79M M1 bars.

## Acceptance thresholds (fixed NOW)
Roughly 12 candidates x 6 timeframes x 6 horizons = ~430 tests. At p<0.05 that yields ~22
false positives by chance, so the ordinary |t|>2 bar is useless here.
A candidate is flagged REAL only if ALL of:
  1. |t| >= 4.0 at some horizon  (Bonferroni-ish for ~430 tests)
  2. mean forward return >= 1.5 x median spread at that horizon (must clear the round trip)
  3. same sign and |t| >= 2 in BOTH walk-forward halves (2019-2022 / 2023-2026)
  4. n >= 500 signals
Anything meeting 1-2 but failing 3-4 is logged as UNCONFIRMED, not as a finding.

## Honest expectation
Simple OHLC-derived signals on a liquid instrument are mostly arbitraged. The likely
outcome is that nothing clears the bar. That result is still worth having, because it
tells us the constraint is cost/timeframe, not indicator choice, and it stops another
100 versions of tuning.

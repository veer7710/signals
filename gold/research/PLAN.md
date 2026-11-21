# PLAN.md — pre-registered study design
Written BEFORE any data was inspected. Measures and pass/fail thresholds fixed here.
If a later analysis uses a measure not listed here, that must be declared as exploratory.

## 0. The signal under test
From `pine/XAUUSD_CLEAN_rebuilt.pine`:
    buy  = stDir == -1 and stDir[1] ==  1 and barstate.isconfirmed
    sell = stDir ==  1 and stDir[1] == -1 and barstate.isconfirmed
This is a PURE Supertrend(ATR 7, mult 1.2) direction flip on a CLOSED bar.
The DEMA(60 on M1) is PLOTTED ONLY — it does not gate the signal.
=> Signal generation has no free parameters to tune. Everything else is execution.

## 1. Execution model (fixed now, not negotiable later)
- Signal is detected on the close of bar i. Fill at the OPEN of bar i+1.
- Entry fill = open(i+1) + spread/2 for buys, − spread/2 for sells  (cost charged on both legs).
- Exits are evaluated on bars i+1 onwards using that bar's high/low.
- If a bar touches both a protective stop and a profit level, the STOP is assumed to fill first.
  (Intrabar order is unknowable; the pessimistic read is the only honest one.)
- No lookahead anywhere: no value from bar j may influence a decision made at bar i<j.
- Spread: measured from data if bid/ask is available. Otherwise modelled at 0.30 pt
  and sensitivity-tested at 0.20 / 0.30 / 0.50.
- Units: 1 "pt" = 1.00 USD of gold price. At 0.01 lots, 1 pt = GBP 0.733.

## 2. Primary question
Does the raw signal, held to the opposite signal, make money after spread?
This is THE BENCHMARK. Every added rule must beat it, or it is not justified.

PRE-REGISTERED VERDICT THRESHOLDS (hold-to-flip, net of spread, per trade):
- >= +0.30 pt/trade  => the raw signal has an exploitable edge on its own.
- 0 to +0.30 pt/trade => marginal; edge exists but costs eat it; exit work is the lever.
- < 0 pt/trade        => the raw signal alone is NOT tradeable. Any claimed edge must then
                         come from exits/sizing and must be proven separately and
                         out-of-sample, not assumed.

## 3. Leg definitions (used by everything below)
- A LEG runs from one signal bar close to the next OPPOSITE signal bar close.
- leg_available = (best price reached in the signal's direction during the leg) − entry_fill.
  This is the most the trade could ever have paid.
- leg_holdflip  = exit_fill − entry_fill, holding to the opposite signal.
- leg_mfe / leg_mae = max favourable / max adverse excursion from entry_fill.
- giveback = leg_mfe − leg_holdflip.

## 4. Measures
### 4.1 Timing / lag
- lag_pts = |entry_fill − (extreme of the PREVIOUS leg)|: how much of the move was already
  gone when the signal printed.
- Report median, p25, p75, p90. Expectation to test: lag ~= 1.2 x ATR(7) by construction.
- Split the lag into (a) indicator lag (bar close) and (b) execution lag (fill at next open).

### 4.2 Trend capture  [PRIMARY]
- capture_ratio = sum(leg_holdflip) / sum(leg_available), all legs.
- Distribution of leg_available: share of legs >= 2, 5, 10, 20, 40 pts.
- PASS/FAIL: capture >= 50% good | 30-50% mediocre | < 30% the exits are the problem.

### 4.3 Fakes and early failure
- A FAKE = leg_available < 2 x spread (never offered enough to cover the round trip).
- fake_rate = share of legs that are fakes, and their share of total loss.
- Separability test: distribution of adverse excursion in the first 30/60/90/120/180 s,
  winners vs losers.
- PRE-REGISTERED RULE for accepting an early cut: at the chosen threshold it must remove
  >= 60% of losing points while removing < 25% of winning points. Otherwise rejected.

### 4.4 Regimes  (action is SIZE, never refusal)
Buckets: hour of day (UTC and broker GMT+3), ATR(14) quintile, efficiency-ratio quintile,
weekday, and session (Asia / London / NY-overlap / late-NY).
- For each: n, net pt/trade after spread, share of total points.
- A regime counts as BAD only at n >= 100 trades AND net pt/trade < 0.

### 4.5 Giveback  (his #1 complaint)
- sum(leg_mfe) vs sum(leg_holdflip) vs sum(realised). The gap is what the exits lose.

### 4.6 Re-entry value
- For legs stopped out early: did the leg still go on to reach its extreme, and by how much?

## 5. Validity controls (red-team conditions agreed in advance)
- Walk-forward: data split in half by time. Any threshold chosen on H1 is reported on H2.
  A rule that only works in-sample is reported as failed.
- Minimum sample for ANY conclusion: 200 trades or 1 month, whichever is larger.
- Win rate is NOT evidence and will not be quoted as such.
- Every result reported in points AND in GBP at 0.01 lots on a 50 pound account,
  including max drawdown and worst single day.
- Costs are always included before any verdict.

## 6. What would prove this whole approach wrong
- Hold-to-flip is negative after spread AND no regime subset with n>=100 is positive
  AND capture ratio cannot be lifted above 30% by any exit tested out-of-sample.
  If that is the finding, the honest answer is that this signal needs something it
  does not currently have, and I will say so.

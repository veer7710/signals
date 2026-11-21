# DATA REPORT
## Primary dataset: `data/xauusd_m1.parquet`
Source: GitHub `Best6626840/xauusd-m1-data` — Exness `XAUUSDm` M1 **bid** bars, Dukascopy backfill pre-2018.
- 3,830,747 bars, 2016-01-03 23:00 -> 2026-11-19 15:46 UTC (10.9 years)
- Columns: ts, dt, open, high, low, close, tick_volume, **spread** ($), src
- `spread_points` converted: 1 point = $0.001 (so 240 -> $0.24)
- Provenance flagged per bar: 3,371,512 Exness / 459,235 Dukascopy backfill. **2019+ is 100% Exness.**

## Integrity (verified independently twice)
- modal gap 60s at **99.92%** of intervals
- **0** duplicate timestamps, **0** OHLC violations, **0** non-positive prices, **0** Saturday bars
- Residual unexplained missing in-session minutes: **0.52%** (mostly a documented 2016 hole)
- Largest gaps are year-end holidays (80h), not feed breaks

## Timezone — CONFIRMED genuine UTC
Weekend gap starts Fri 20:00-21:00 UTC and ends Sun 22:00-23:00 UTC (= 17:00 New York). Matches the real FX session, so the `time_utc` label is true UTC, not a broker offset.

## Cross-validation against two INDEPENDENT feeds
| pair | overlap | median close diff | 1-min return r |
|---|---|---|---|
| Best vs HistData (America/New_York, DST-aware) | 1,858,634 min | **+$0.090** | 0.848 |
| Best vs parshant65 daily-file feed | 984,539 min | **-$0.079** | 0.892 |
All three agree on the Nov-2026 daily closes and on the 2026 drawdown (4139 -> 3688) — that move is REAL, not a data artefact.

## Cross-check against the owner's own live tape
His handover cites an overnight run 4657 -> 4696 in late August 2026. This dataset's August 2026 high is **4695.5**. His 21 Aug fills at 4610-4618 and 20 Aug at 4522-4539 all sit inside the month's 4025-4695 range. The data is consistent with his tickets.

## Spread (the cost that decides everything)
Median by year: 2024 $0.199 | 2025 $0.160 | 2026 $0.240. p90 2026 $0.280.
Flat across the clock except rollover (22:00 UTC: median $0.20, p90 $0.60).
**This independently corroborates the handover's "spread about 0.3 pt" figure.**

## Honest limitations
1. Feed is **Exness**, he trades **PU Prime**. Spread level will differ somewhat; all results are therefore sensitivity-tested across $0.16 / $0.20 / $0.30 / $0.50.
2. Spread is per-bar, not per-tick, so intra-bar spread spikes are smoothed.
3. Commission is NOT in the feed; modelled separately as a price-unit cost.
4. Bid bars: longs modelled entering at ask and exiting on bid triggers; shorts entering at bid and exiting on ask triggers. One full spread per round trip, with correct trigger timing for both directions.

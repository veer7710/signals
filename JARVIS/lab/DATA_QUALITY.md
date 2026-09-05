# DATA_QUALITY — what this project can and cannot measure

**Updated 2026-09-04. This file is the constraint on every claim in the repo.**

## THE BLOCKER IS GONE
For its entire life this project had no M1 or M5 data and every M1 statement was
inference. `raw.githubusercontent.com` and anonymous `git clone` of public GitHub
repos are reachable through this session's proxy, even though every market-data
host is not. That is the channel.

## SOURCES

| source | what | status |
|---|---|---|
| `github.com/FX-Data/FX-Data-XAUUSD-DS` | XAUUSD **tick** data, bid+ask, year branches 2007-2018 | **IN USE** |
| `data/*_15m.json`, `*_1h.json` | GOLD/US500/EURUSD/GBPUSD, 2025-26 | in use, provenance unverified |
| histdata.com, dukascopy, stooq, yahoo, binance | — | **403 at the gateway** |
| huggingface.co | recent XAUUSD minute datasets exist | **unreachable (000)** |

## THE TICK DATASET, VERIFIED
`XAUUSD/<year>/<month>/YYYY-MM-DD--HHh_ticks.csv`
```
2018.03.27 10:00:00.635,13.48641,13.48842,0.00,0.00
timestamp(ms)           bid      ask      vol  vol
```
- **Price is scaled by 1/100.** 13.48641 x 100 = 1348.64, which is exactly where
  gold traded on 2018-03-27. Verified against the historical price, not assumed.
- **Both volume columns are identically zero.** This feed carries NO volume. Any
  volume-based hypothesis is untestable here and must be marked so.
- Built: **18,816,940 ticks -> 157,051 M1 bars**, 2018-01-01 to 2018-06-19.
- Converter: `JARVIS/tools/ticks_to_bars.py`. Bars are built from the **bid**
  and additionally carry `spread_mean`, `spread_max`, `ticks` per bar.

## THE MEASUREMENT THAT CHANGES THE PROJECT
```
GOLD M1 2018          median      p95        max
  spread              0.229      0.272      2.982 points
  ATR(14)             0.246      -          -     points
  ticks per bar         102
```
**The project assumed `Costs.spread = 0.46` for ninety experiments. The real
median is 0.229 — the assumed cost was double the truth.**

## AND THE REGIME CORRECTION THAT MATTERS MORE
2018 is not today. Measured, not assumed, by comparing the same timeframe:
```
                     bars     price    ATR(14)   ATR/price
2018 M15 (ticks)    10475    1322.9      1.145     8.65 bp
2025-26 15m (repo)   4554    4133.8      8.444    20.43 bp
2018 M1  (ticks)   157051    1322.9      0.246     1.86 bp
```
**M15 ATR grew 7.38x while price grew only 3.12x** — gold is far more volatile
*relative to its price* now. Scaling the measured M1 ATR by that same ratio:

> **estimated M1 ATR today ~= 0.246 x 7.38 = 1.82 points**

| spread | spread/ATR | cost/stop at a 2 ATR stop | verdict vs E-089 (<=0.11) |
|---|---|---|---|
| 0.20 (ECN/raw) | 0.11 | **0.11** | **exactly at threshold — viable** |
| 0.30 | 0.17 | 0.17 | marginal |
| 0.46 (standard) | 0.25 | 0.25 | edge dies |

**E-089 concluded M1 was unviable (cost/stop 0.22-0.38) from an assumed 0.46
spread and an unmeasured ATR. Both inputs were wrong, in opposite directions.
The corrected answer is that M1 gold is viable TODAY and it turns entirely on
the account's spread.**

## DEFECT IN THIS FEED — the missing hour
**There are ZERO bars at 00:00 UTC on every day**, and 199 gaps of exactly 61
minutes. The source drops the 00h file. Consequences:
- any session / time-of-day study on this feed is contaminated at the daily
  boundary; exclude 23:00-01:00 or the "re-open" effect is an artifact
- ATR and any recursive indicator computed across the gap treats the jump as one
  bar's move, inflating the range at the boundary
Found while probing hourly bar counts. Not yet corrected in the built files.

## HONEST LIMITS ON ALL OF THE ABOVE
1. **The M1 ATR figure for today is an ESTIMATE**, built from a measured 2018 M1
   ATR times a measured M15 volatility ratio. It is a measurement chain, not a
   direct measurement. Direct confirmation needs recent M1 bars, which are not
   reachable from here — `ExportHistory.mq5` from Veer's own terminal remains the
   way to close it, and it is now a *confirmation* rather than a blocker.
2. **The tick feed is Dukascopy-derived (ECN).** PU Prime is a retail broker and
   will be wider. 0.229 is a floor, not Veer's number.
3. **No volume.** The feed's volume columns are zero.
4. **Six months, one year, one regime** (2018 H1, gold 1275-1366, a quiet range).
   Nothing here has seen a 2020 or 2025-style trend at M1.
5. **The 2025-26 15m/1h files have unverified provenance** — no broker, no
   feed, no spread column. They are the basis of ~100 experiments and should be
   re-sourced or cross-checked.

## WHAT IS NOW ANSWERABLE THAT WAS NOT
- real per-bar, per-hour spread instead of an assumed constant
- realistic bid/ask execution and slippage modelling
- M1 trend-birth, MAE/MFE and entry-timing research
- whether any mechanism survives at M1 resolution at all
- the cost floor, from data rather than extrapolation

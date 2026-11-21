# Regenerating the dataset

Not committed: `data/raw/` (747 MB) and `data/xauusd_m1.parquet` (116 MB, above GitHub's
per-file limit).

## Primary source
GitHub `Best6626840/xauusd-m1-data` — Exness `XAUUSDm` M1 **bid** bars with a real per-bar
spread column, 2016-01-03 → 2026-11-19 UTC, 3,830,747 bars.

```bash
mkdir -p data/raw/Best6626840_xauusd-m1-data && cd data/raw/Best6626840_xauusd-m1-data
BASE=https://raw.githubusercontent.com/Best6626840/xauusd-m1-data/HEAD/data
for y in $(seq 2016 2026); do curl -sSLO $BASE/XAUUSDm_M1_$y.csv.gz; done
curl -sSLO $BASE/filled_bars.csv.gz
gunzip -k *.gz
cd ../../.. && python3 -I data/build_dataset.py      # writes data/xauusd_m1.parquet
python3 -I data/validate.py                          # health check
```

`spread_points` → dollars: 1 point = $0.001 (so 240 = $0.24). `build_dataset.py` does this.

## Cross-check sources (optional, used to validate prices)
- `Craig-Pang/QuantXAU` and `Paaktingc/forex_bot` — HistData.com `DAT_ASCII_XAUUSD_M1_*.csv`.
  Timestamps are **America/New_York WITH DST** — convert with a DST-aware tz, not a fixed
  offset (a constant +5h gives r=0.335; proper conversion gives r=0.848).
- `parshant65-lang/Gold-XAUUSD-1m-2020-2025` — daily UTC files, genuinely UTC.

Agreement achieved: median close diff +$0.090 vs HistData, −$0.079 vs parshant65.

## Honest limitation
The feed is **Exness**; the account is **PU Prime**. Spread levels differ somewhat, so every
result is sensitivity-tested across $0.16 / $0.20 / $0.30 / $0.50. For a definitive answer,
export M1 history from the actual PU Prime terminal and re-run.

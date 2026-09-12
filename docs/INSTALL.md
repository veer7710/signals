# Install and run

## Files

| EA (MetaTrader 5) | Pine (TradingView) | what it does |
|---|---|---|
| `mq5/SuperTrendSniper2.mq5` | `pine/SUPERTREND_SNIPER_V2.pine` | mini-trend scalper, rebuilt exit |
| `mq5/LiquidityEngine.mq5` | `pine/LIQUIDITY_ENGINE.pine` | liquidity pools / sweeps / SMC context |
| `mq5/SessionRangeEngine.mq5` | `pine/SESSION_RANGE_ENGINE.pine` | 13:00 GMT session range break |
| `mq5/ApexEngine.mq5` | `pine/APEX_ENGINE.pine` | **funded-account engine** — HTF bias + pullback + Asian break |

**Start with ApexEngine.** It is the best-supported system here: positive
in-sample and out-of-sample on both timeframes (PF 1.31–2.00), with sizing
set to the Monte-Carlo optimum for a prop challenge (0.20% risk → 80% pass
rate). Set `InpHtf` in the EA and `Higher timeframe` in the Pine to the
same value — H4 for an M15 or H1 chart.

Each Pine is its EA's chart, not a separate product. They share the same
SuperTrend recursion, the same ATR contract, the same next-bar-open fill
rule, and the same arming rule. `research/check_parity.py` proves the
SuperTrend halves agree bar for bar (0 mismatches on 3 datasets).

## MetaTrader 5

1. File → Open Data Folder → `MQL5/Experts/`, drop the three `.mq5` files in.
2. In MetaEditor press F7 on each. **No file in this repo has ever been
   compiled** — I have no MetaEditor here. Send me the error list and I
   will fix it; expect a handful of first-compile issues.
3. Enable **Allow Algo Trading**, and in Tools → Options → Expert Advisors
   allow file operations (the guards persist to a file so a restart cannot
   reset your daily limit).
4. Attach to XAUUSD. Any timeframe.

## TradingView

Pine Editor → paste → Add to chart. Any timeframe. Signals appear only on
**confirmed** bars, so an arrow that appears never disappears.

## Settings to start with

Leave the defaults. They are the measured ones. The two that matter:

- `InpArmAtR = 1.0` — the fix. The trail does nothing until the trade is
  1R in profit. Setting this to 0 restores the old behaviour that pinned
  your average winner at $5.06.
- `InpTrailAtr = 3.0` — measured best on both timeframes (+$4.54/trade,
  t=3.44, vs the old exit on 498 paired entries).

`InpRiskPct = 0.50` with `InpUseRiskPct = true`. If risk-% sizing asks for
less than your broker's minimum lot, **the trade is skipped, never rounded
up**. Rounding up is what margin-called the £50 account. The panel counts
these as "size too small" so you can see when the account is too small for
the timeframe.

## Funded accounts

`InpDailyLossPct = 3.0`, `InpMaxDDPct = 6.0`. Both are checked **before**
every order and persisted to a file in the common data folder, so an EA
restart cannot reset the day. Set them below your firm's actual limits.

The daily halt clears at the next day roll. The max-drawdown halt does
**not** — it stays until you delete the `.guard` file. That is deliberate.

## Reading the panel

```
CAPTURE RATIO 0.34  (exit-R / peak-R, n=57)
```

This is the number your handover asked for and the one the old EA never
reported. It is a **diagnostic, not a target** — see FINDINGS §5. If it
reads near 1.0 you are cutting winners; the old EA's problem looked like
a healthy 0.14–0.17 precisely because losers drag it down.

```
skipped: stop too wide 12 | size too small 3
```

What the risk cap refused. A filter earns its place only if what it
refuses is worse than what it takes — these counters are how you check.

## Re-running the research

```bash
pip install numpy pandas
python3 research/check_parity.py     # EA/Pine agreement
python3 research/run_markers.py      # every entry marker vs a null
python3 research/run_paired.py       # the exit result
python3 research/validate.py         # regenerates the shipped numbers
```

## What would actually move this forward

1. **Export M1 and M5 gold from your MT5** (2019–2023 if you have it). Every
   M1 statement in FINDINGS.md is inferred from 15m/1h, not measured. This
   is the single biggest gap.
2. **Export NAS100.** The EAs are symbol-agnostic, but I have no NAS100
   data and gold results do not transfer.
3. **Run the Sniper on demo for two weeks with the journal on**, then send
   me the log. Capture ratio and peak-R per trade from *your* broker, with
   *your* spread, beats anything I can infer from Yahoo futures data.

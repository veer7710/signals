# SESSION STATE — 2026-09-02

## Where this session got to

Four deliverables were asked for: the liquidity Pine, the SuperTrend Pine, a
liquidity EA and the SuperTrend EA — all clean, all trading real levels, all
with a working live position box.

### Shipped
| file | state |
|---|---|
| `JARVIS/pine/LIQUIDITY_CLEAN_1_1.pine` | rebuilt on the E-069 geometry: retest entry, 0.5 ATR target, stop 1.5 ATR beyond the sweep wick, zone = one confirmed pivot. Static-check clean. |
| `JARVIS/pine/XAUUSD_CLEAN_3_6.pine` | minimum stop 1.5 → 2.0 ATR (E-071). Static-check clean. |
| `JARVIS/ea/build/LiquiditySniper.mq5` | **NEW.** The E-069 geometry as an EA. Real broker-side limit orders. Check clean. |
| `JARVIS/ea/build/SuperTrendSniper.mq5` | build 2.14. Timer-driven readout, 2.0 ATR stop, ADX gate off, stall tiers cut, give-back arms at 3R. Check clean. |

### The five findings that changed the code
1. **E-068** — my liquidity measurement was wrong in three places and fired 12
   times in 4501 bars. Veer's reported 80% win rate is reproduced exactly by
   the corrected geometry. The entry (retest, not sweep close) is the whole
   edge: the sweep close scores −0.003R at ZERO cost.
2. **E-069** — that geometry survives everything: GOLD 1h n=401, 87.8%,
   +0.106R, PF 1.85, t=+5.05, walk-forward 6/6, 7.8 control-sd. **PROMISING.**
3. **E-070/071/072** — SuperTrend is the OPPOSITE animal. Its entry is fine
   (market beats every limit variant); its exit was wrong. A 91.6% win rate
   near-target cell LOSES 548 points. Stop 1.5 → 2.0 ATR doubles the points.
4. **E-073** — E-056, the project's most-cited result, does **not** survive
   being counted once per trade. Pooled over 1826 independent trades the gap
   is +0.046 with a 95% interval of [−0.002, +0.105]. Downgraded CONFIRMED →
   SUPPORTED, magnitude wrong by 6x, EA tiers cut to match.
5. **E-074/075** — only the DEMA gate has ever paid for itself; the ADX
   ceiling refused a quarter of all signals for nothing. And the give-back
   rule was never the problem — **arming it at 0.6R was**. Armed at 3R it is
   the highest-expectancy exit tested.

## The three things that are still true and still limiting
1. **There is no M1 or M5 data in the repository.** Every conclusion here is
   measured on 15m and 1h bars. `JARVIS/ea/tools/ExportHistory.mq5` fixes this
   in one drag-and-drop and has still not been run.
2. **Nothing here is proof of profit.** The strongest verdict any of it holds
   is PROMISING, and that means "has not been disproved".
3. **Both strategies are GOLD (and index) results.** All four FX rows are
   REJECTED on the liquidity rules and negative on the SuperTrend ones.

## Standing rule that keeps being vindicated
Three results this session failed the same way: a statistic computed over the
wrong unit. E-050 for want of a control, E-064 for a single control seed,
E-073 for counting bars as trades. **Any result quoted with an n far larger
than the number of independent decisions behind it is wrong until re-counted.**

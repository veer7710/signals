# NEXT ACTIONS

## 1. THE ONE THING ONLY VEER CAN DO
Run `JARVIS/ea/tools/ExportHistory.mq5` in MT5 and commit `GOLD_M1.json`.
Re-verified this session: the network gateway returns 403 to CONNECT on every
market-data host, so this cannot come from inside a session.

Four of the five findings below name M1 as what would settle them:
- **E-093** the frequency row — how many trades M1 actually gives is the one
  cell in the funded table that cannot be filled in, and it decides the whole
  funded track.
- **E-096** the edge row — £40 vs £100 turns on whether the M1 edge is +0.041R.
- **E-094** the sideways work was underpowered at 101 and 338 trades.
- **E-092** the DEMA gate is unproven, and on M1 it is DEMA(60), never tested.

## 2. WORK THAT DOES NOT NEED IT
- **Liquidity Pine/EA parity.** E-092 did the SuperTrend pair. The liquidity
  pair (`LIQUIDITY_CLEAN_1_6.pine` vs `LiquiditySniper.mq5`) has not been
  checked and is the funded track. Same method: `pine_ea_parity.py`.
- **The 1.0R vs 4.0R decision is Veer's.** E-095 measured it; the default was
  deliberately left at his stated preference. He should see the table.
- **P83 the funded phase** — payout rate and time to first payout, now that
  `funded.py` can simulate a rule set properly.
- **P85 trailing vs static drawdown as different strategies.** `funded.py`
  models both correctly now, and they have not been compared as strategies.

## 3. DECISIONS WAITING ON VEER
1. **£100, not £40.** E-096 is unambiguous on the arithmetic. Does he fund to
   £100 directly and skip the only leg with real ruin risk?
2. **Which firm.** `JARVIS/ea/FUNDED_CARD.md`. Buy from a firm with no
   consistency rule — FTMO or The5ers measured 98.2%. This is worth more than
   any EA setting and it is free.
3. **`InpProfitStopArmR`.** Stay at 1.0 (his instruction, and 15m agrees) or go
   to 4.0 (the only value beating OFF on both timeframes, and the only one that
   keeps any ≥4R trade alive)?

## 4. STANDING
Nothing in this session touched a live account. Nothing here is a claim of
profit — the strongest verdict any of it holds is SUPPORTED.

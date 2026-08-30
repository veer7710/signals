# Capability map

Legend: WORKING · PARTIAL · MISSING · BLOCKED (needs Veer or external access)

## Research & analysis
| Capability | Status | Note |
|---|---|---|
| Backtesting w/ realistic costs | WORKING | `study.py`, tested |
| Walk-forward validation | WORKING | 6 folds, factory-rebuilt |
| Monte Carlo drawdown | WORKING | 20k reshuffles |
| Look-ahead detection | WORKING | enforced + tested |
| Statistical significance | WORKING | t-stat, Wilson CI |
| Web research | WORKING | used for R-001, R-002 |
| Tick-level backtesting | MISSING | no tick data |
| MT5 strategy tester | BLOCKED | Veer's Windows PC only |
| Live market data | MISSING | needs an authorised API |
| Reading chart images | PARTIAL | if Veer uploads them |
| Reading TradingView live | BLOCKED | ToS + auth |

## Engineering
| Capability | Status | Note |
|---|---|---|
| Python | WORKING | 3.11 |
| Node | WORKING | v22 |
| Git / GitHub | WORKING | branch + push |
| MQL5 authoring | PARTIAL | can write, cannot compile here |
| Pine analysis | BLOCKED | no scripts supplied |
| Docker | UNKNOWN | not checked |

## JARVIS system
| Capability | Status | Note |
|---|---|---|
| Persistent memory | WORKING | `JARVIS/state/` |
| Session continuity | WORKING | CLAUDE.md + resume + handoff |
| Specialist agents | PARTIAL | 6 defined, unproven in use |
| Regression testing | WORKING | `test_engine.py` |
| Task scheduling | MISSING | |
| Model routing | MISSING | needs OmniRoute (R-001) |
| Voice interface | MISSING | |
| Dashboard | MISSING | A-006 |
| Notifications | MISSING | |

## Biggest capability gaps, ranked by leverage
1. **The actual EA and Pine scripts.** Everything EA-related is blocked.
2. **More market data.** One symbol, one bull regime = weak conclusions.
3. **MT5 execution loop.** Without it, nothing reaches a real account.
4. **Broker/prop-firm specifics.** Costs and rules change every verdict.

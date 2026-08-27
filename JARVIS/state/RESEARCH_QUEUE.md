# Research queue

## R-001 — Legitimate ways to increase AI throughput  [RESEARCHED 2026-08-27]
- **OmniRoute** (github.com/pitbaden/omniroute) — open-source local AI
  gateway, OpenAI-compatible on localhost:20128, routes across 300+
  providers with automatic fallback when one hits its quota, plus built-in
  token compression. Works with Claude Code. Aggregating providers' own
  free tiers is legitimate; it is not evasion of any single provider's
  limits. STATUS: recommended to install, not yet installed.
- **Graphify** (graphifyai.net, MIT) — builds a knowledge graph of the repo
  and serves it over MCP so Claude queries structure instead of reading raw
  files. Reported ~70x fewer tokens per query on large codebases. Only pays
  off once JARVIS is large; note this repo is currently small.
- **Local models via Ollama** on Veer's PC for bulk/background work.
- Not viable: evading limits, multiple accounts, ToS circumvention (D-005).

## R-002 — Prop firm multi-account rules  [RESEARCHED 2026-08-27 — CRITICAL]
- FTMO caps total allocation at **$400,000 per trader OR PER STRATEGY**
  before scaling. Identical strategies across accounts exceeding that cap
  → accounts suspended.
- Multiple registrations to dodge the cap → prohibited.
- Across DIFFERENT firms is generally allowed, BUT firms detect copy-trading
  via near-identical fill timestamps and shared IP addresses; matched fills
  can get payouts denied at BOTH firms simultaneously.
- **Consequence for the 40-account plan:** it cannot be 40 identical
  accounts. Needs different firms, deliberately varied execution
  (entry offsets, sizing, symbols), and separate network paths. This is a
  hard constraint on the whole scaling thesis — see NEXT_ACTIONS A-004.

## R-003 — Liquidity concepts still untested (E-003 covered only one)
Prior-day/prior-week high-low, session highs/lows (Asia/London/NY), equal
highs/lows clustering, displacement + FVG confirmation, sweep-then-reclaim
on 15m. Each is a separate testable hypothesis.

## R-004 — Not yet started
Open-source JARVIS projects worth borrowing from; MT5 Python bridge for
automated tick-level testing; news/calendar feed for event filtering;
broker symbol specs (contract size, swap, commission) for GOLD.

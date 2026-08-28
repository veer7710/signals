# Research queue

## R-001 — Legitimate ways to increase AI throughput  [RESEARCHED 2026-08-27]
- **OmniRoute — RECOMMENDATION RETRACTED 2026-08-28. DO NOT INSTALL.**
  My first pass recommended it after a shallow search. Deeper verification
  found two disqualifying problems:
  (a) it ships **TLS/JA3-JA4 fingerprint stealth and a MITM proxy** as
      features. Fingerprint stealth exists to defeat provider anti-abuse
      detection. That is evasion, and it violates D-005 directly — the very
      thing this project refused to do.
  (b) a disclosed auth-bypass class issue (default `JWT_SECRET` of
      `omniroute-default-secret-change-me`).
  Also: the URL originally cited (`pitbaden/omniroute`) is NOT the canonical
  repo and is best treated as a mirror of unknown provenance. Do not
  `docker run` or `npm i -g` from it.
  **Lesson:** a single web search is not research. Recorded in
  LESSONS_LEARNED as L-006.
- **Graphify** — still plausible, but **the domain I originally cited
  (`graphifyai.net`) could not be verified as the project's real domain.**
  Treat install instructions from it as untrusted until confirmed from the
  project's own GitHub README. In any case it only pays off on large
  codebases and this repo is small, so it is not needed yet.
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

# Failure log

Failures are training data. Every entry: what broke, root cause, class, fix,
and the regression test that now guards it.

---
## F-001 — walk-forward produced impossible 0% win rates
- **Class:** CODE / ARCHITECTURE
- **Symptom:** Walk-forward folds reported 0% win rate over 40+ trades and
  ~-0.95R expectancy. Statistically impossible; a real strategy cannot lose
  every single trade.
- **Root cause:** Strategies precompute per-series state (higher-timeframe
  trend gate, swing pivots) indexed by bar position. `walk_forward()` was
  handed a strategy object built on the FULL series, then ran it over a
  SLICE. Bar index `i` therefore referred to two different bars — the gate
  and pivots came from the wrong point in history. Stops were placed on the
  wrong side of price, so almost everything stopped out.
- **Detection:** The number was too extreme to be real. A plausible-looking
  wrong number would have shipped.
- **Fix:** `walk_forward()` now takes a FACTORY `make_fn(sub) -> signal_fn`
  and rebuilds the strategy per fold, so all precomputed state matches the
  series being traded.
- **Regression test:** `test_engine.py` :: F-001 block asserts walk-forward
  folds never show sub-2% win rates.
- **Lesson:** Any strategy carrying precomputed per-bar state MUST be
  rebuilt for each data slice. Generalised in LESSONS_LEARNED L-002.

---
## F-002 — bulk `rm -rf` of repo contents was blocked
- **Class:** PERMISSION
- **Symptom:** Combined `git rm -r --cached . && rm -rf ...` denied by the
  sandbox classifier.
- **Root cause:** Broad recursive deletion is treated as destructive.
- **Fix:** Used explicit `git rm <named files>` instead — tracked, reviewable,
  recoverable from git history.
- **Lesson:** Delete by explicit filename, never by recursive wildcard.

---
## F-003 — five research agents killed by the account usage limit
- **Class:** ENVIRONMENT / EXECUTION
- **Symptom:** all five background research agents terminated with HTTP 429
  ("session limit") within minutes of each other. Four had reached the point of
  writing their findings; only one file survived.
- **Root cause:** five Opus agents launched simultaneously, each doing
  web-heavy research, against a shared session budget. Anthropic's own
  reporting puts multi-agent token use at roughly 15x a chat interaction, so
  five in parallel exhausted the budget quickly.
- **Fix:** launch research agents in batches of 2-3, not 5. Checkpoint the main
  session's own findings to disk BEFORE spawning, so a limit hit never costs
  verified work.
- **Lesson:** parallelism is not free. Budget it like any other resource.
  Generalised in LESSONS_LEARNED L-007.

---
## F-004 — recommended installing a tool that evades provider limits
- **Class:** REASONING / RESEARCH
- **Symptom:** recommended OmniRoute to Veer after one web search, in the same
  session that refused to evade usage limits on principle (D-005).
- **Root cause:** treated search-result enthusiasm as evidence. The tool ships
  TLS/JA3-JA4 fingerprint stealth, whose purpose is defeating provider
  anti-abuse detection, plus a disclosed default-secret auth bypass. The URL
  cited was also not the canonical repository.
- **Fix:** recommendation retracted in RESEARCH_QUEUE R-001.
- **Lesson:** L-006 — verify the canonical source and what a tool actually does
  before recommending an install.

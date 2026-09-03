# 02 — JARVIS architecture research (v2)

**Date:** 2026-08-28
**Author:** research agent (Opus 5)
**Supersedes:** the 2026-08-27 version of this file. Corrections to that
version are listed in §2.
**Status:** research findings. Nothing here is CONFIRMED. Every third-party
number is labelled as a third-party claim. **No number in this document was
computed by this system.**

---

## 1. BOTTOM LINE — the recommended architecture in ten sentences

1. Build JARVIS as **one main agent loop that owns all state** (Claude Code as
   the harness), with **stateless, read-heavy sub-agents** used only to keep
   verbose work out of the main context — this is the one architectural choice
   with the strongest evidence behind it from teams who actually shipped.
2. Do **not** build a multi-agent society: the Berkeley MAST taxonomy attributes
   ~41.8% of multi-agent failures to specification/design and ~36.9% to
   inter-agent misalignment (i.e. most multi-agent failure is *your design*,
   not the model), and Anthropic's own research system reportedly costs ~15x
   the tokens of chat, which only pays for breadth-first *read* tasks.
3. **Memory stays as markdown files in git** — `SESSION_STATE.md`,
   `DECISIONS.md`, `FAILURE_LOG.md`, `EXPERIMENTS.md` — because Anthropic
   removed vector search from Claude Code in favour of grep and reported it
   "outperformed everything, by a lot"; a corpus of a few hundred files does
   not need embeddings, and a vector index silently goes stale while you edit.
4. Adopt Anthropic's published **long-running-agent harness pattern**
   (initializer agent → `init.sh` → repeated coding agent → progress artifact →
   commit) because it is exactly the shape `JARVIS/bin/resume` is already
   groping towards, and it is the only published pattern for making progress
   across many context windows.
5. **Verification must be external and mechanical** — `test_engine.py`,
   `study.py`, `git diff`, MT5 read-backs — because the 2025–2026 literature is
   consistent that models cannot reliably self-correct without an external
   signal (one 2026 study reports ~64.5% of self-generated errors survive
   self-checking yet are caught when shown externally); a "critic agent" that
   shares the generator's blind spots is theatre.
6. **Run few MCP servers, all pinned, all read-only where money is involved**:
   filesystem, Playwright, a *self-written* read-only MT5 bridge, Obsidian's
   own Local REST API — and treat every MCP server as untrusted third-party
   code (66% of 1,808 scanned servers had a security finding; 40+ MCP CVEs in
   2026 alone).
7. **Voice is a cascaded pipeline, not a speech-to-speech model** — faster-whisper
   → the same main agent → Kokoro/Piper TTS — because cascaded is what ships in
   2026 and it is the only architecture where tool calls are inspectable.
8. **The conciseness problem is solved structurally, not by asking politely**:
   force the model to emit two fields (`speech`, `detail`), send only `speech`
   to TTS, classify each reply into a response class with a hard word budget,
   and truncate in code — because RLHF-trained models have a documented length
   bias and "be concise" is an instruction they will drift off within three turns.
9. **The dominant security risk is indirect prompt injection** (the lethal
   trifecta: private data + untrusted content + an outbound channel), which
   JARVIS will hit the moment it reads the web or email while holding broker
   credentials — the mitigation is architectural separation, never a filter.
10. **Build order: memory harness → tools → scheduler with budget guards →
    dashboard → voice → local models.** Voice last: it adds the least capability
    and the most yak-shaving, and building it early is how this project dies.

---

## 2. Corrections to the 2026-08-27 version of this file

The previous version was written when several primary sources were unreachable.
They are still unreachable (see §16), but targeted verification changed four
things. These are the parts of the old file that were **wrong or misleading**:

| Claim in v1 | Status now |
|---|---|
| OmniRoute lives at `github.com/pitbaden/omniroute` | **Wrong owner.** The canonical repo is **`diegosouzapw/OmniRoute`** — verified via the GitHub API on 2026-08-28: 57,114 stars, 7,855 forks, created 2026-02-13, default branch `release/v3.8.51`. `pitbaden/omniroute` appears in search indexes with the same description and is best treated as a mirror/fork of unknown provenance. **Do not `docker run` or `npm i -g` from the URL Veer supplied.** |
| Graphify = `safishamsi/graphify` | **Moved.** The GitHub API shows user `safishamsi` currently owns **no repo named graphify**; the live repo is **`Graphify-Labs/graphify`** (verified 2026-08-28: 111,698 stars, 10,865 forks, 1,140 open issues, default branch `v8`). Official sites appear to be `graphify.com` and `graphify.net`. The `graphifyai.net` domain Veer named **could not be verified as the project's domain** — treat any install instructions from it as untrusted until the domain is confirmed from the GitHub README. |
| OmniRoute treated as merely "not worth it" | **Understated.** It has a disclosed auth-bypass class issue (default `JWT_SECRET` = `omniroute-default-secret-change-me`, tracked as CVE-2026-49352 in secondary reporting) and ships **TLS/JA3-JA4 fingerprint stealth and a MITM proxy** as features. Fingerprint stealth exists to defeat provider anti-abuse. That is evasion, and it collides head-on with **D-005**. It is now a hard SKIP on policy grounds, not just cost grounds. |
| Sub-agent isolation framed as purely a Cognition-vs-Anthropic disagreement | **Resolved in practice.** Both camps now describe the same shape: one main loop carries state; sub-agents are stateless workers with narrow scope and their own context window. The disagreement was about *parallel writers*, and nobody defends those. |

---

## 3. AGENT ARCHITECTURE

### 3.1 Single agent vs multi-agent — what the evidence actually says

**The case against multi-agent, from people who shipped:**

Cognition (the Devin team) published *Don't Build Multi-Agents*. Their argument
is not "multi-agent is hard", it is that **actions carry implicit decisions**:
when two agents act in parallel on the same task, each has made assumptions the
other cannot see, and the results conflict in ways no merge step can repair.
Their prescription is a **single-threaded linear agent** with continuous
context, and — when the task overflows the window — a dedicated model whose
only job is to **compress the history into key details, events and decisions**.
Their more recent public position is that some multi-agent setups now work, and
they all share one property: *one main loop carries state, sub-agents are
stateless workers with narrow scope*.

The **MAST** taxonomy (UC Berkeley, arXiv 2503.13657) is the closest thing to
data. Built by grounded theory over 150+ traces (each averaging >15,000 lines)
across five to seven open-source multi-agent frameworks, six annotators,
inter-annotator agreement κ = 0.88, later extended to 1,600+ traces. It defines
**14 failure modes in 3 categories**, and the reported distribution is the
important part:

- **Specification & system design ~41.8%** — task misinterpretation, ambiguous
  roles, bad decomposition, duplicate roles, **missing termination conditions**.
- **Inter-agent misalignment ~36.9%** — context lost at handoff, conflicting
  outputs, format mismatch.
- **Task verification** — the remainder.

Read that as: **~79% of multi-agent failure is you failing to specify the system
or failing to pass context, not the model being dumb.** Adding a second agent
adds a handoff, and handoffs are where the failures live.

**The case for multi-agent, from people who shipped:**

Anthropic's multi-agent research system is an **orchestrator-worker**: a lead
agent plans, spawns 3–5 sub-agents in parallel, each with its own context
window and tools, then synthesises with a separate citation pass. The widely
quoted figures are **+90.2% over single-agent Claude Opus 4 on their internal
research eval** at roughly **15x the tokens of a chat turn**. Note carefully
what the task is: **breadth-first read-only research** where the total
information exceeds one context window and the sub-tasks are genuinely
independent. Secondary write-ups also note the published architecture has **no
circuit breakers or per-run caps**, and that the 15x multiplier compounds badly
when a sub-agent recursively spawns more sub-agents or a tool returns an
oversized result.

**Synthesis — the rule for JARVIS:**

> Parallelise **reads**. Serialise **writes**. Never let two agents hold a
> writable resource at once.

Concretely for this repo:
- **Parallel sub-agents are correct for:** literature/web research (the five
  jobs in A-000), scanning 20–40 markets for the A-008 daily study, reading the
  20,695-line EA, adversarially reviewing `donchian_trend` on separate symbols.
- **Single main loop only, always, for:** editing `strategies.py`, updating
  `EXPERIMENTS.md`, anything touching MT5, any git commit.
- **Every sub-agent must have:** an objective, an output format, the tools it
  may use, a hard token/step budget, and an explicit termination condition.
  Missing termination conditions are a named MAST failure mode; the A-000
  research jobs died last session precisely because nothing bounded them.

### 3.2 Context management — what actually works

Anthropic's *Effective context engineering for AI agents* names three
techniques and they are all worth stealing:

1. **Compaction** — when nearing the window limit, summarise the conversation
   and reinitialise a new window with the summary. Claude Code's own
   implementation preserves architectural decisions, unresolved bugs and
   implementation details while discarding redundant tool outputs. *For JARVIS:
   you already have the human-readable version of this — `SESSION_STATE.md`.
   Make the agent write it as the LAST act of every session, not as an
   afterthought.*
2. **Structured note-taking** — write findings to files, not to the context.
   *Already your `findings/` directory.*
3. **Sub-agent context isolation** — each sub-agent gets exactly the context it
   needs and nothing else; the parent receives only the distilled result.

Add **just-in-time retrieval**: the guiding principle Anthropic states is *find
the smallest set of high-signal tokens that maximise the likelihood of the
desired outcome*. Load file paths and let the agent `grep`; do not paste files.

**Why this matters more than it sounds — context rot.** Chroma Research's July
2025 report tested 18 frontier models (GPT-4.1, Claude 4, Gemini 2.5, Qwen3 and
others) on tasks extended from Needle-in-a-Haystack and reported that **every
model degrades as input length grows**, well before the window is full; for
1M-token models the clearly observable effect is reported around 300k–400k
tokens. Distractors and haystack structure matter more than raw length. The
practical consequence: **a long context is not a free memory**. Compaction is
not a workaround for a small window, it is a performance optimisation.

**MCP tool-definition bloat is a specific, fixable case of this.** Anthropic
shipped **Tool Search** (`defer_loading: true`) and **code execution with MCP**
for exactly this: reported ~85% token reduction from deferring tool schemas,
and one published case of 150,000 → 2,000 tokens (~98.7%) by having the agent
call MCP servers from code rather than loading every schema. **The lesson for
JARVIS is simpler than the feature: every MCP server you add taxes every turn
forever.** Five good servers beat twenty.

### 3.3 Planning and decomposition

The honest state: **neither ReAct nor plan-and-execute is universally better**,
and several 2026 write-ups say so explicitly — results depend on workload.
What survives contact with practice:

- **ReAct (think → act → observe → repeat) is the right default** for tasks
  reachable in ~3–5 tool calls.
- **Plan-then-execute wins on structured multi-step work** ("research five
  competitors, compare, draft a report") because a ReAct agent given a broad
  goal wanders. The planner also lets cheap models execute steps.
- **The externalised todo list is the cheap 80% of both.** Writing the plan to
  a file that survives compaction is what actually keeps a long task on target,
  and it doubles as the audit trail. `NEXT_ACTIONS.md` is already this — the
  improvement is to make the agent *check items off in the file* as it goes,
  not just at the end.
- Plan-then-execute is also the **security-relevant** pattern: it is one of the
  three named defensive patterns in the design-patterns paper (§11), because a
  plan fixed before untrusted content is read cannot be rewritten by that
  content.

### 3.4 Error recovery and verification — proven vs marketing

**Proven:**
- **External, mechanical verification.** A test suite, a compiler, a linter, a
  re-read of the file you just wrote, a `git diff`, an MT5 position read-back.
  This is the only verification with a strong evidence base.
- **Idempotency + retry with backoff** at the tool layer.
- **Bounded retries with a distinct escalation path.** The documented failure
  is an agent looping the same failing call thousands of times overnight.

**Marketing / weak:**
- **"Reflexion"-style self-critique with no external signal.** *Large Language
  Models Cannot Self-Correct Reasoning Yet* (arXiv 2310.01798) is the canonical
  cite and the 2025–2026 follow-ups agree: prompted self-feedback rarely
  repairs reasoning errors and can degrade accuracy. A 2026 study reports
  **~64.5% of self-generated errors survive self-checking** while the same
  errors are caught when presented externally.
- **A "critic agent" using the same model and the same context.** It shares the
  generator's blind spots by construction. It becomes useful only when given a
  *different input* — the diff, the test output, the raw data — i.e. when it is
  really an external-verification harness wearing a costume.
- **LLM-as-judge as the primary gate.** Fine as a regression smoke test on
  subjective quality, useless as the thing standing between you and a bad trade.

**For JARVIS specifically, the verification hierarchy is already correct and
should be written into the harness as a hook:** no strategy claim leaves the
building without `test_engine.py` passing and `study.py` output pasted. Make it
a `PostToolUse`/`Stop` hook, not a rule in a markdown file the agent may skim.

### 3.5 The long-running harness pattern (steal this)

Anthropic's *Effective harnesses for long-running agents* (26 Nov 2025) is the
single most directly applicable published pattern for this project:

- An **initializer agent** runs **once**: sets up the environment, expands the
  prompt into a structured `feature-list.json`, and writes an **`init.sh`** that
  every future session runs on boot.
- A **coding agent** is then **woken repeatedly**. Each session: make
  incremental progress on **one** feature, run the tests, write a
  **progress note** (`claude-progress.txt`), and **commit**.
- The artifacts — not the context — are what carries state between sessions.

Map onto this repo, which is 80% of the way there already:

| Anthropic's artifact | JARVIS equivalent | Gap to close |
|---|---|---|
| `init.sh` | `JARVIS/bin/resume` | Make it also run `test_engine.py` and print the result, so a session starts knowing whether the engine is trustworthy. |
| `feature-list.json` | `NEXT_ACTIONS.md` | Give each action a machine-readable status field so a scheduler can pick "the next unblocked action" without an LLM call. |
| `claude-progress.txt` | `SESSION_STATE.md` | Enforce writing it via a `Stop` hook. A session that ends without it has thrown away its work — CLAUDE.md already says so; make the harness enforce it. |
| per-session commit | already the rule | Enforce via hook too. |

---

## 4. MEMORY

### 4.1 Files vs vectors vs graphs — the decision, with the evidence

**The strongest single data point against reflexively adding a vector DB:** in
May 2025 Anthropic **removed vector search from Claude Code**, replacing the
embedding pipeline, local vector DB and chunking heuristics with `grep`. Claude
Code's creator Boris Cherny is quoted saying the result "outperformed
everything. By a lot." Cursor, Windsurf, Cline and Sourcegraph Amp are reported
to have followed. An Amazon Science paper at AAAI 2026 is cited as measuring
agentic keyword search at **94.5% of RAG faithfulness with zero vector store**.

Why grep wins on a corpus like this one:
- **Precision.** Exact match; embeddings introduce fuzzy positives you cannot
  see and cannot debug.
- **Freshness.** An index drifts from the files the moment you edit. Your repo
  changes every session.
- **No maintenance surface.** No chunk size, no embedding model version, no
  re-index job to forget.
- **Privacy.** Nothing leaves the machine to be embedded.
- **The filenames and headings ARE the index** — if you name files well.

**Decision rule (use this, not vibes):**

| Situation | Right tool |
|---|---|
| < ~1,000 documents, you wrote them, they have good names and headings | **Markdown files + grep.** This is JARVIS today. |
| Thousands of documents you did NOT write, no consistent naming, fuzzy recall needed ("that thing about drawdown") | Hybrid **BM25 + embeddings**, in that order of importance |
| You need *relationships* answered — "what calls this function", "what breaks if I change this input" | **Knowledge graph** (deterministic AST, not LLM-extracted) |
| Recall over a long chat history spanning months | A **memory layer** (mem0/Zep) — or, cheaper, a well-maintained `SESSION_STATE.md` |

**Where JARVIS sits: the middle column is not you.** The repo is small,
self-authored, well-named and version-controlled. Adding a vector DB here would
add a stale index, an embedding dependency and a failure mode, in exchange for
fuzzy matching over text you can already grep. **Do not install one.**

### 4.2 The one thing to ADD to your memory system

Your files record *what happened*. They do not force each line to declare *what
kind of claim it is*. That is how a guess becomes a fact three sessions later.
Add a typed-claim convention — it costs nothing and it is the highest-leverage
memory change available:

```markdown
- [FACT 2026-08-27 src:study.py] donchian_trend longs +0.292R, shorts +0.007R on GOLD 1h.
- [ASSUMPTION 2026-08-28] Prop firms detect copy trading via fill timestamps.
- [DECISION D-005 2026-08-27] Usage limits will not be evaded.
- [HYPOTHESIS E-00x] Cascade veto improves sweep entries. UNPROVEN.
```

Rules: a FACT needs a source you can re-run. An ASSUMPTION may never be cited
as a reason. Promotion from HYPOTHESIS to anything else requires a `study.py`
run pasted into `EXPERIMENTS.md`. This is a lint rule you can enforce with 20
lines of Python in a hook — it is the memory equivalent of `test_engine.py`.

### 4.3 The named products, evaluated honestly

**Graphify — CONDITIONAL, and read §2 first.**
- Real repo: **`Graphify-Labs/graphify`** (verified 2026-08-28: 111,698 stars,
  10,865 forks, 1,140 open issues, Python, default branch `v8`). `safishamsi`
  no longer hosts it. The domain Veer gave (`graphifyai.net`) does not match the
  sites found (`graphify.com`, `graphify.net`) — **verify the domain from the
  GitHub README before downloading anything from it.**
- What it actually is: **a code knowledge graph**, not a personal-memory
  system. Tree-sitter AST parsing across ~20 languages, deterministic (no LLM
  tokens to build), SHA-256 cache so re-runs only process changed files,
  optional MCP server exposing `query_graph` / `get_node` / `get_neighbors` /
  `shortest_path`, Leiden community detection, Apache-2.0, runs on-device.
- **Honest verdict:** useless as JARVIS's memory. Genuinely interesting for
  **one specific job in this repo**: `XAUUSD_QUAD_v19_18.mq5` is 20,695 lines
  with 748 inputs, and A-005/the EA audit is exactly a "what calls what, what
  breaks if I change this input" problem — the one problem class where a graph
  beats grep. Note MQL5 is unlikely to be among the supported tree-sitter
  grammars (C/C++ parsing may partially work). **Try it only if you return to
  the EA. Do not install it now.** The star count is extraordinary for a repo
  created 2026-04-03 and should not by itself be read as quality.

**Obsidian + MCP — YES, if and only if you already keep notes in Obsidian.**
- The clean 2026 path: the **Local REST API** community plugin, version 5.x,
  **serves MCP itself at `/mcp/`** — one install instead of two, and Claude Code
  speaks HTTP MCP natively (`http://127.0.0.1:27123/mcp/`, plain HTTP endpoint,
  avoiding the self-signed cert dance).
- The older, most-established alternative is `MarkusPfundstein/mcp-obsidian`
  (~3k stars), which still requires the Local REST API plugin underneath.
- **Caveat that decides it:** these require Obsidian to be *running*. A
  scheduled 3 a.m. agent cannot depend on a GUI app being open.
- **Verdict:** Obsidian is a fine *human* front-end onto a vault of markdown.
  It is a bad *dependency* for an autonomous agent. If you want notes, point
  Obsidian at a folder in this repo and let the agent use plain file tools.
  Zero servers, zero uptime requirement, and the agent's memory and your notes
  become the same artifact.

**mem0 / Zep / Letta (MemGPT) — SKIP for now, all three.**
- **The benchmark situation is a vendor fight, not evidence.** On LOCOMO: Zep
  originally reported ~84%; mem0's replication scored Zep at 58.44% and alleged
  methodology errors; Zep rebutted with 75.14%. mem0 reports 67.13% LLM-as-judge
  with p95 search latency ~0.200s and ~1,764 tokens/conversation vs 26,031 for
  full context; Zep is reported at 58.10% with **p95 search latency ~59.8s**,
  which would be unusable interactively. **These numbers are self-reported by
  competitors under different harnesses.** LongMemEval is regarded as more
  rigorous and is also run under inconsistent harnesses. Treat all of it as
  marketing until you measure on your own data.
- **Architecturally:** mem0 = vector-first memory layer; Zep = temporal
  knowledge graph (Graphiti engine); Letta/MemGPT = LLM-as-OS with main
  context / recall store / archival store.
- **Verdict:** these solve *"my chatbot has talked to 10,000 users and must
  recall each one"*. You are one user with a git repo. They would add a
  service, a database, an embedding dependency and a new failure mode to
  replace a file you can read with your own eyes. **Revisit only if you can
  state a specific recall failure that grep could not have solved.**

**Anthropic's own memory tool — worth knowing, not worth adopting yet.**
Claude's `memory` tool (public beta) is **file-based by design**: the model
issues read/write instructions and the files live on your side; it pairs with
**context editing** to clear stale tool results. Two things follow. First, it
validates the file-based approach — the vendor's own memory primitive is a
directory of files. Second, if you later drive JARVIS through the Agent SDK
rather than the CLI, this is the memory API to use, and your existing
`JARVIS/state/` directory is already the right shape for it.

---

## 5. TOOL USE / MCP

### 5.1 Principles before servers

Anthropic's *Writing effective tools for AI agents* gives four rules that
matter more than any server choice:

1. **High-impact functionality over API surface coverage.** Do not wrap every
   MT5 function. Wrap the five things you actually ask for.
2. **Namespacing.** `mt5_read_positions`, `mt5_read_history` — the prefix tells
   the agent (and you) the blast radius.
3. **Token efficiency.** Paginate, filter, truncate, with sensible defaults. A
   tool that returns 400 candles when asked for the last price is a context
   leak that costs you on every future turn.
4. **Clear errors.** An error string should tell the agent what to do next
   ("symbol not found; call mt5_list_symbols"), not just what failed.

And the meta-rule from §3.2: **every server taxes every turn**. Budget for
5–7 servers total, not 20.

### 5.2 The servers worth running — and the ones to write yourself

**Filesystem — you already have it.** Claude Code's built-in Read/Write/Edit/
Grep/Glob are the filesystem MCP server, better integrated. **Do not install a
separate filesystem MCP server.** If you ever need one outside Claude Code, the
official reference implementation restricted to explicitly allowed directories
is the one to use.

**Browser: Playwright MCP (Microsoft) — INSTALL.**
`npx @playwright/mcp@latest`. It drives an **accessibility snapshot** (text
tree), not screenshots: fast, deterministic, survives layout changes, and works
with a text-only model. Third-party 2026 comparisons put DOM-driven stacks
**12–17 percentage points ahead of vision-driven** on reliability (one set of
figures: Playwright+Claude 92%, Browserbase 90%, Stagehand 89%, computer-use
78%, CUA 75%), while also noting a Playwright-MCP success rate of ~78% in the
wild because anti-bot systems now block automated sessions — and an "honest
ceiling" of ~64.4% across 5,750 mixed read/write tasks. **Read that as: browser
automation is a 2-in-3 proposition on the open web. Design around failure.**

**Browser, debugging variant: `chrome-devtools-mcp` (Google) — OPTIONAL.**
`npx chrome-devtools-mcp@latest`. Speaks Chrome DevTools Protocol: network
requests, console, performance traces, CPU/network emulation. Use it if you end
up debugging a web dashboard; not needed for scraping.

**browser-use / computer-use / CUA — SKIP for now.** Vision-driven agents are
slower, more expensive, harder to debug, and behind on reliability. Revisit
only for a specific site where the DOM route is genuinely blocked.

**MT5 — WRITE YOUR OWN. Do not install a trading-capable MCP server.**
This is the most important tool decision in the document.
- The `MetaTrader5` Python package is **Windows-only and official** — which is
  fine, Veer is on Windows. (Linux users need Wine + RPyC shims like
  `mt5linux`/`MT5LinuxEnhanced`; irrelevant here, and one less reason to move
  this to a Linux box.)
- Existing MCP servers exist and are real: **`ariadng/metatrader-mcp-server`**
  (verified 2026-08-28: 778 stars, 255 forks, actively updated) and
  **`Qoyyuum/mcp-metatrader5-server`** (213 stars, 78 forks). Both are built to
  let an LLM **place trades**.
- **That is exactly the capability you must not grant.** D-006 says no live
  action without per-session confirmation; the lethal trifecta (§11) says never
  put an order-placing tool in the same context that reads untrusted text.
- **Do this instead:** ~150 lines of `fastmcp` exposing **only**
  `mt5_symbol_info`, `mt5_copy_rates`, `mt5_positions_get`,
  `mt5_history_deals_get`, `mt5_account_info`. No `order_send`. Not "disabled by
  config" — **absent from the file**. Reading the two repos above for their
  connection/retry handling is worthwhile; installing them is not.
- Order placement, when it eventually happens, goes through a **separate
  script Veer runs by hand** after reading a printed order ticket. That is the
  maker-checker pattern, and it is the cheapest possible implementation of it.

**Market data.** MT5 itself is your candle source — it is what you will trade
on, so it is the only price series whose quirks matter. For the things MT5 does
not give you: `kjpou1/forexfactory-mcp` exposes the ForexFactory economic
calendar as MCP tools (JSON-first, agent-oriented) and is the most obviously
useful non-price feed for a gold/FX system — a news-blackout filter is a
testable hypothesis you cannot currently test. GoldAPI.io and fastFOREX both
advertise MCP endpoints for spot metals; Alpha Vantage has a free tier and MCP
support. **Treat every one of these as untrusted text entering the context**
(§11) — a calendar entry is attacker-controllable in principle.

**Email / calendar — DEFER, and be deliberate about it.** This is the single
highest-risk category in the whole document: reading email is reading
attacker-authored text, and the moment JARVIS can also send anything or reach
the broker, you have assembled the lethal trifecta by hand. If you eventually
want it: a **read-only, single-label** Gmail scope, in a **separate agent
session** with no MT5 tools, no filesystem write, and no outbound HTTP. Not in
the main loop. Ever.

**Screen reading / Windows control — DEFER.** `Windows-MCP` is the credible
option and it is architecturally the right one: it reads the **Windows UI
Automation accessibility tree**, not screenshots, so a text-only model can
drive it. Microsoft's **OmniParser V2 / OmniParser X** is the vision fallback
that tokenises a screenshot into interactable elements. You need neither: MT5
exposes Python, so screen-scraping the terminal is a solved problem you should
not re-open. Revisit only for an app with no API.

**Obsidian** — see §4.3. Optional, and only as a human front-end.

**Rule for all of them:** pin versions, read the source before first run, and
run each with the narrowest possible scope. See §11.3.

---

## 6. VOICE

### 6.1 Architecture: cascaded, not speech-to-speech

**Cascaded** = STT → text → LLM (with tools) → TTS.
**Speech-to-speech (S2S)** = audio in, audio out, no text layer.

S2S is the exciting one and it is the wrong choice here. The 2026 consensus
across vendor and independent write-ups: **cascaded dominates production**; S2S
is research-to-early-production. The reasons that decide it for JARVIS:

- **Tool calling.** Multiple sources say the same thing: choose S2S if you do
  *not* need reliable function calling and do *not* need to inspect the
  reasoning layer. JARVIS is nothing but tool calls and an inspectable
  reasoning layer.
- **Debuggability.** With a text layer you can log exactly what was heard, what
  was decided, and what was said. Without it you have an opaque box wired to
  your broker.
- **Provider flexibility.** Cascaded: 5+ STT, 7+ TTS, dozens of LLMs. S2S:
  effectively two vendors.
- **Cost predictability.** Cascaded is quoted at ~$0.0095–$0.17/min; S2S spans
  ~$0.00165/min to ~$0.30/min depending on vendor — a 182x spread.
- The one real S2S advantage is latency (one source claims ~85% reduction vs a
  *non-streaming* cascade — note the qualifier; a *streaming* cascade closes
  most of that gap).

**Verdict: cascaded. And the LLM in the middle is the same main agent** — not a
separate "voice model" with its own personality and its own memory. Two brains
is how you get an assistant that contradicts itself.

### 6.2 Speech-to-text

Veer is on Windows, presumably with an NVIDIA GPU. That makes this easy.

| Option | Notes | Verdict |
|---|---|---|
| **faster-whisper** (CTranslate2) | Reported ~12x real-time for large-v3 on an RTX 4070 at ~2.5 GB VRAM with int8; built-in VAD pipeline. Reported as the better CUDA path than whisper.cpp on Windows/NVIDIA. | **Use this.** `large-v3-turbo` is reported ~4x faster than large-v3 for ~0.3% WER cost. |
| whisper.cpp | Better on Apple Silicon; weaker on Windows/NVIDIA. | Skip on this hardware. |
| NVIDIA Parakeet-TDT-0.6B-v3 | Reported 6.34% avg WER on the HF Open ASR Leaderboard — the strongest open self-host option; strong CPU story. | Worth benchmarking against faster-whisper on **your** microphone. |
| Deepgram Nova-3 | Sub-300 ms, best-in-class endpointing; but one independent benchmark reports ~25.3% WER on mixed real-world data vs vendor figures. | Only if local latency proves unusable. |
| AssemblyAI Universal-3 Pro | Reported 5.6% mean WER; streaming P50 ~150 ms, P90 ~240 ms post-VAD. | The accuracy-first cloud option. |

**Note the structural trade-off** one benchmark makes explicit: the two fastest
streaming models also post the highest WER, and the most accurate sits further
down the latency distribution. **No provider leads on both.** For a personal
assistant in a quiet room, accuracy matters more than 100 ms — a misheard
symbol name is worse than a pause. Start local with faster-whisper; you keep
your data, pay nothing, and can measure before buying anything.

### 6.3 Text-to-speech

| Option | Notes | Verdict |
|---|---|---|
| **Kokoro-82M** | 82M params, runs on CPU, repeatedly named the best lightweight open TTS of 2026. | **Start here.** Free, local, good enough, no account. |
| **Piper** | The Home Assistant default; extremely light; ONNX; trivially embeddable. Robotic next to Kokoro. | Fallback / low-power. |
| ElevenLabs Flash v2.5 | ~120–150 ms TTFB, best-in-class naturalness. | Buy only if you decide the voice quality genuinely changes how much you use it. |
| Cartesia Sonic / Qwen3-TTS | Sub-100 ms TTFB claims (97 ms streaming). | Only if latency becomes the binding constraint. |

All latency figures above are vendor or third-party benchmark claims. **Measure
TTFB on your own machine before choosing** — for barge-in what matters is time
to *first audio chunk*, not total synthesis time.

### 6.4 Wake word and barge-in

**Wake word.** `openWakeWord` (used by Home Assistant, built on a Google audio
embedding model, fine-tuned with Piper-generated speech) is the open option and
you can train "Jarvis" yourself. Home Assistant's own documentation is candid
that it has more false positives/negatives than Amazon's and Google's
cloud-trained models and **struggles with background noise**. Picovoice
**Porcupine** claims 97%+ detection with <1 false alarm per 10 hours in noise,
trains a custom phrase from typed text in seconds, and supports Windows x86_64
— but the free tier is evaluation-only and commercial use is a paid,
sales-gated tier. **For personal use on one PC, start with openWakeWord; if
false triggers annoy you, Porcupine's free personal tier is the fix.**
Cheapest option of all: **a hotkey**. Push-to-talk has a 0% false-positive rate
and costs nothing, and for a desk-bound trading assistant it is not obviously
worse.

**Barge-in.** The rule that matters: **keep turn detection running while the
agent is speaking.** When user speech is detected during playback, cancel the
TTS stream immediately and hand control back to STT. Naive VAD-based barge-in
over-triggers on backchannels ("mm-hm", "yeah") and background noise; the 2026
production answer is a **dedicated turn-detection model** — Pipecat's
`SmartTurnAnalyzer`, LiveKit's `TurnDetector`. LiveKit reports its adaptive
interruption handling **rejects 51% of VAD-based barge-ins** as false, and has
it on by default in Python Agents v1.5.0+.

**Framework:** if you want this solved rather than built, **Pipecat** (self-host
a pipeline of processors, choose your own transport) is the better fit for a
local desktop assistant than **LiveKit** (which bundles transport/telephony you
do not need). Both are real and shipping. Home Assistant's **Wyoming protocol**
is the other genuinely mature option and worth reading even if you don't adopt
it: it is a small, boring protocol that makes STT/TTS/wake-word swappable, and
Whisper/Piper/Wyoming each report ~8.9% installation share across all active
Home Assistant installs — a substantial installed base for a fully local stack.


---

## INCOMPLETE — sections 7-10 were never written

This document stops mid-way through the voice section. The research agent
producing it was cut off before writing:

- **7. Model routing / cost** (partially covered: OmniRoute is a hard SKIP,
  see §2)
- **8. Orchestration, scheduling, background work, budgets**
- **9. Dashboard — what an agent control centre should actually show**
- **10. Security — indirect prompt injection, secrets, least privilege**
  (the BOTTOM LINE flags this as the dominant risk, but the detail is missing)
- **11. Existing open-source JARVIS projects worth borrowing from**
- **12. The exact install list**

Do not treat the absence of these sections as "nothing to do there". They are
queued in NEXT_ACTIONS as A-000. What IS usable and verified here: the
single-main-loop architecture (§1, §3), the markdown-memory conclusion (§4),
the MCP guidance (§5), the voice-conciseness design (§1.7-1.8, §6), and the
OmniRoute retraction (§2).
### 6.5 THE VOICE-CONCISENESS SOLUTION

This is the part Veer explicitly cares about, so here is the whole thing.

#### 6.5.1 Why "be concise" fails

It is not a prompting skill issue. It is structural:

- **RLHF trained the length bias in.** Reward models treat verbosity as
  quality because human annotators preferred longer answers in a reported ~63%
  of benchmark comparisons. You are fighting the objective the model was
  optimised against.
- **Instructions decay across turns.** A system-prompt rule competes with 40
  turns of the model's own verbose output, which is a much stronger stylistic
  prior than one line of instruction.
- **"Be concise" is not copyable.** One source puts it well: *models
  pattern-match before they follow rules — "be concise" gives them nothing to
  copy; a real dialogue showing exactly how concise gives them a blueprint.*
- **`max_tokens` alone truncates mid-word.** It is a safety net, not a
  mechanism. (Documented as one of the most common and hardest-to-debug LLM
  failure modes.)

The literature's answer is that **no single control works and five stacked
controls do**: explicit length instruction, structured output format, few-shot
examples of correctly-sized answers, a stop sequence at a natural boundary, and
a task-appropriate `max_tokens`. One source reports that combination cutting
output 40–74% without quality loss. Notably, **large models reduce length ~60%
in response to brevity instructions vs ~15% for small models** — so use the
big model for the shaping and don't expect a 3B model to obey.

#### 6.5.2 The design: two channels, one model, a hard cap in code

**Core idea: the model does not decide how long to speak. The schema and the
code decide. The model only decides what to say.**

Every JARVIS turn returns a structured object. Only one field is ever spoken.

```json
{
  "class":  "ack | status | answer | alert | question | refusal",
  "speech": "Donchian holds up on gold. Fails on EURUSD.",
  "detail": "Full markdown: walk-forward table, Monte Carlo bands, the cost
             sensitivity grid, and the exact study.py command that produced it.",
  "needs_confirmation": false
}
```

- `speech` → TTS. **Nothing else is ever spoken.**
- `detail` → the dashboard, the log, `EXPERIMENTS.md`. Read with the eyes.
- `class` → selects the word budget, enforced in code.

This is the whole trick. Every failed attempt at a concise voice assistant
tries to make one output stream serve both a listener and a reader. **Those are
different media with different bandwidth. Give them different fields.**

#### 6.5.3 The response classes and their budgets

| class | budget | when | example |
|---|---|---|---|
| `ack` | **≤ 4 words** | command accepted, work starting | "On it." / "Running the study." |
| `status` | **≤ 12 words** | progress, completion | "Done. Walk-forward passed, Monte Carlo didn't." |
| `answer` | **≤ 25 words** | a question was asked | "Longs earn 0.29R, shorts basically zero. The edge is direction-dependent." |
| `alert` | **≤ 15 words**, leads with the problem | something is wrong | "Stop. The engine tests are failing. Numbers are meaningless." |
| `question` | **≤ 15 words**, ends with the question | needs a decision from Veer | "US500 or EURUSD first?" |
| `refusal` | **≤ 15 words** | blocked by a rule | "No. That's live trading. Confirm it explicitly and I'll do it." |

Two more rules that do most of the perceived-terseness work:

- **Never speak a number you can show.** "Three of five tests passed" is
  speech. The table is `detail`. Spoken digits are where verbosity re-enters.
- **Lead with the verdict.** "Failed. Shorts have no edge." not "So I ran the
  walk-forward analysis and after looking at the results it turns out…".

#### 6.5.4 The system prompt fragment (few-shot, because rules alone fail)

```text
You speak through a speaker. Your speech field is HEARD, not read.

Return JSON: {class, speech, detail, needs_confirmation}.
Only `speech` is spoken aloud. Everything else goes in `detail`.

Word budgets, hard: ack 4, status 12, answer 25, alert 15, question 15,
refusal 15. If you exceed the budget, cut words until you fit. Cutting the
caveat is correct; cutting the verdict is not.

Never speak: preambles ("Sure!", "Great question"), restatements of what
was asked, lists, numbers with more than two significant figures, file
paths, code, or apologies. Put all of it in `detail`.

Lead with the outcome. The first three words carry the meaning.

Examples:

USER: run the study on gold
{"class":"ack","speech":"Running it.","detail":"Executing `python3 JARVIS/research/study.py GOLD 1h`. Will report walk-forward, Monte Carlo, cost sensitivity, long/short split.","needs_confirmation":false}

USER: how did it go
{"class":"status","speech":"Mixed. Longs work, shorts don't.","detail":"| test | result |\n|---|---|\n| in-sample | +0.15R |\n| walk-forward | +0.09R |\n| Monte Carlo 5th pct | -0.02R |\n| longs | +0.292R |\n| shorts | +0.007R |\nThe headline edge is carried entirely by the long side, consistent with gold's trend over the sample.","needs_confirmation":false}

USER: is it profitable
{"class":"refusal","speech":"Can't say that. It's PROMISING, not confirmed.","detail":"Per CLAUDE.md standing rules, a backtest is evidence, never proof. Current status in EXPERIMENTS.md: PROMISING. It has not faced out-of-sample symbols or adversarial review.","needs_confirmation":false}

USER: put on a live trade
{"class":"question","speech":"That's live. Confirm the exact order?","detail":"D-006 requires per-session confirmation for any action touching a funded account. Proposed ticket printed to the dashboard for review.","needs_confirmation":true}
```

Four examples beat four paragraphs of instruction. That is the point.

#### 6.5.5 Enforcement in code — the part that actually guarantees it

Prompts drift. Code does not. This runs between the model and the TTS:

```python
BUDGET = {"ack": 4, "status": 12, "answer": 25,
          "alert": 15, "question": 15, "refusal": 15}

BANNED_OPENERS = ("sure", "great", "certainly", "of course",
                  "i'd be happy", "let me", "so,", "well,", "absolutely")

def shape_for_speech(reply: dict) -> str:
    cls = reply.get("class", "answer")
    text = " ".join(reply.get("speech", "").split())

    # 1. strip preamble openers the model slipped in
    low = text.lower()
    for opener in BANNED_OPENERS:
        if low.startswith(opener):
            text = text[len(opener):].lstrip(" ,.!")
            break

    # 2. hard word cap, but cut at a SENTENCE boundary, never mid-clause
    words = text.split()
    cap = BUDGET.get(cls, 25)
    if len(words) > cap:
        clipped = " ".join(words[:cap])
        cut = max(clipped.rfind("."), clipped.rfind("?"), clipped.rfind("!"))
        text = clipped[:cut + 1] if cut > 0 else clipped.rstrip(",;:") + "."

    # 3. never speak a path, a command, or a code fence
    if any(t in text for t in ("/", "\\", "```", "()")):
        text = "Details are on the dashboard."

    return text
```

Plus, at the API layer: **`max_tokens` sized to the class** (≈ 2x the word
budget in tokens, as the safety net) and **`stop` sequences** at `"\n\n"` so a
second paragraph can never be generated in the first place.

#### 6.5.6 Escape hatches, so terseness never becomes uselessness

Terse is only good if the detail is one word away:

- **"Explain."** / **"Details."** → speak the first 40 words of `detail`.
- **"Show me."** → open the dashboard at that turn's `detail`.
- Every spoken turn writes `speech`, `detail` and the tool trace to the log,
  so nothing said aloud is the only record of anything.

#### 6.5.7 The one measurement to run

Log the word count of every spoken turn. Plot the distribution weekly. **If the
median drifts up, the prompt has decayed and the code cap is the only thing
holding.** This is a two-line addition to the logger and it is the difference
between a design and a hope.

---

## 7. MODEL ROUTING, COST, LOCAL MODELS

### 7.1 OmniRoute — honest evaluation: **SKIP, on policy grounds**

The project is real and large. Verified via the GitHub API on 2026-08-28:
**`diegosouzapw/OmniRoute`**, 57,114 stars, 7,855 forks, created 2026-02-13,
TypeScript, MIT, actively released (`release/v3.8.51`). It is an
OpenAI-compatible gateway in front of ~300+ providers and ~1,200 models with
auto-fallback, caching, rate limits and observability, keys encrypted AES-256-GCM
on local disk. That last part is a genuine architectural advantage over a hosted
gateway. **The URL Veer supplied (`pitbaden/omniroute`) is not the canonical
repo — do not install from it.**

**Why it is still a SKIP for JARVIS, in order of seriousness:**

1. **It collides with D-005.** The headline pitch is free/quota-pooled access
   across ~90 free providers, and the feature list includes **JA3/JA4 TLS
   fingerprint stealth and a MITM proxy**. Fingerprint stealth exists for one
   reason: to stop provider anti-abuse from recognising automated traffic. That
   is evasion. Reviewers also note that many providers' free tiers forbid
   production use and that using one model across multiple accounts violates
   terms almost everywhere, with real suspension risk. **D-005 already settled
   this: losing the account is strictly worse than working within the limits.**
2. **A disclosed auth-bypass class.** Secondary reporting cites
   **CVE-2026-49352**: the default `JWT_SECRET` ships as
   `omniroute-default-secret-change-me`, and if left unchanged an
   unauthenticated remote attacker can forge an `auth_token` cookie and take
   full admin control of the dashboard and API. Reviewers also flag optional
   encryption and fail-open guardrails. A gateway holding every API key you own
   is the worst possible place for a default secret.
3. **It solves a problem you do not have.** You use Claude Code on a
   subscription. A multi-provider router adds a hop, a process, a config
   surface and an attack surface to a system whose actual bottleneck is
   research throughput, not per-token price.

**If you ever genuinely need a gateway** (e.g. to run local models and Claude
behind one endpoint, with per-project spend caps): use **LiteLLM**. It is the
boring, widely-deployed, audit-friendly choice and it is what the same reviewers
recommend over OmniRoute for anything you care about.

### 7.2 Local models via Ollama — where they earn their place

Local models are worth installing for **volume, privacy and always-on**, not for
quality. Do not route reasoning about strategies to them.

**Third-party 2026 rankings for a 24 GB card** (claims, not measurements):
`qwen3-coder:30b` — 30B MoE with ~3.3B active, ~19 GB at Q4_K_M, 256k context,
described as the best quality-per-GB for agentic coding; `qwen2.5-coder:32b` —
strongest dense coder at ~20 GB; `devstral:24b` — ~46.8% SWE-Bench Verified at
14 GB, the only local coder with a hard agentic number; `gpt-oss:20b` at ~14 GB.
Budget 2–6 GB on top for KV cache.

**Jobs local models should actually take in JARVIS:**

| Job | Why local wins |
|---|---|
| The **voice shaper** fallback | Runs every turn; latency and cost dominate; the task is mechanical rewriting. |
| **Log/trace triage** overnight | Thousands of lines, zero reasoning depth needed, no reason to pay for it. |
| **News/calendar classification** | High volume, low stakes, and it keeps untrusted text out of the privileged context — see §11. |
| **Draft commit messages / file summaries** | Cheap, reversible, human-reviewed. |

**Jobs local models must never take:** anything that decides a strategy is
valid, anything that writes to `EXPERIMENTS.md` or `DECISIONS.md`, anything that
touches MT5. The whole value of this project is not fooling yourself, and a 30B
model is materially worse at not fooling itself.

---

## 8. ORCHESTRATION AND SCHEDULING

### 8.1 The pattern, in one line

**Windows Task Scheduler → `run_job.py` (supervisor with budget guards) →
`claude -p` with a scoped prompt → artifacts + commit → notify.**

Do not reach for Temporal, Prefect, Airflow or Celery. They are real and good;
Temporal in particular gives genuinely durable execution — full workflow
histories, durable timers, mid-function resume, retry policies with exponential
backoff (default 2.0 coefficient, 1 s initial, 100 s cap) — and it now ships
integrations with agent SDKs. But its own positioning is explicit that it is
**not** for "scheduled tasks or simple cron jobs", and its value appears at
"complex state + long execution time" across services. You have one machine and
one user. **A supervisor script plus git is your durable state**, and git is a
better audit log than any workflow engine's UI.

### 8.2 The overnight-safety guards — non-negotiable

The documented failure mode is specific and it has already happened to people:
*an agent entered a retry loop around 11 p.m. and had made thousands of
identical failing tool calls by 7 a.m., all billing*. Your version of this is
worse, because your last session was killed by a usage limit mid-research and
wrote nothing.

Implement all six. They are perhaps 150 lines total:

1. **Wall-clock cap per job.** Hard kill at N minutes. No exceptions.
2. **Token/cost cap per job and per night**, checked before each model call —
   the recommended layering is per-request ceiling, per-session rolling budget,
   per-key daily cap, model-tier routing, circuit breaker.
3. **Cost-velocity breaker.** Trip on spend *rate*, not just total; a fast loop
   burns the session cap before a total-only check notices.
4. **Loop breaker.** **Two or three consecutive identical tool calls with no
   progress marker trips the breaker.** This is the single highest-value guard
   and it is ten lines: hash `(tool_name, args)`, count repeats, abort.
5. **Explicit termination condition in every job prompt.** "Stop when
   `findings/0X.md` exists and is non-empty." Missing termination conditions
   are a named MAST failure mode.
6. **A read-only night.** Overnight jobs get: filesystem read, filesystem write
   **only under `JARVIS/research/findings/`**, web search, and nothing else. No
   MT5. No git push to a shared branch. No email. Nothing irreversible happens
   while you are asleep.

Plus one habit: **checkpoint on a timer, not at the end.** Every job writes
partial findings every ~10 minutes. Last session proves why: five agents died
at a usage limit and produced zero files because everything was written at the
end. A job that dies at 80% should leave 80% of a document behind.

### 8.3 Job shapes worth scheduling

- **Nightly (~02:00):** run `test_engine.py`; run `study.py` across the symbol
  list; diff against yesterday's numbers; write a delta report. Cheap,
  deterministic, mostly not even an LLM job.
- **Nightly research (one job, not five):** the A-000 queue, one topic per
  night, with a hard budget. Serialising them is how you avoid last session's
  failure.
- **Weekly:** dependency and MCP-server integrity check (§11.3); prune
  `SESSION_STATE.md`.
- **On demand:** everything else. Resist scheduling things you have not run
  manually at least twice.

---

## 9. DASHBOARD AND OBSERVABILITY

### 9.1 What agent observability tools show that actually matters

The useful finding from the 2026 comparisons is a diagnosis, not a product
pick: **most agent incidents are tool-call failures, context truncation and
runaway loops — not model errors** — and standard APM cannot see any of them
without agent-aware instrumentation. Agent failures appear in **multi-step
causal chains**, so you need full-session traces, not per-call logs.

Product situation, briefly and bluntly:
- **Langfuse** — the self-hosting choice; genuinely free, no per-seat pricing,
  production-ready, acquired by ClickHouse in Jan 2026 with capabilities
  unchanged. **This is the one to use if you use one.**
- **LangSmith** — best if you live in LangChain/LangGraph; self-host is
  Enterprise-only. You are not in LangChain.
- **Braintrust** — most generous free tier (1M spans/month), but proprietary
  SaaS, no self-hosting. Your traces would include broker context. No.
- **AgentOps** — strongest multi-framework debugging.
- **OpenTelemetry GenAI semantic conventions** are the portable layer, and
  **Claude Code emits OTel natively** — so instrument to OTel and you can swap
  or stack backends later.

**Honest recommendation: do not install any of them in phase 1.** With one
user and one agent loop, a JSONL trace file per session plus `git log` gives you
95% of the value. Add Langfuse when you have overnight jobs you are not
watching — that is the moment traces stop being a luxury.

### 9.2 What actually belongs on the JARVIS control centre

Ordered by how often it would change a decision. A dashboard that shows
everything shows nothing.

**Top strip — "is anything on fire":**
1. `test_engine.py` status + timestamp. **Red here invalidates every number
   below it.** This is the most important pixel on the screen.
2. Spend today / spend this month vs cap. Rate, not just total.
3. Jobs: running / queued / failed last night.
4. MT5 link status, account equity, open positions **read-only**.

**Main panel — the work:**
5. **Experiment ledger**: every hypothesis with its status word (CONFIRMED /
   SUPPORTED / PROMISING / UNPROVEN / REJECTED / DISPROVEN), sorted by last
   touched. This is the actual product of the project.
6. **Delta since yesterday**: which numbers moved, on which symbols. Numbers
   that move without a code change mean something is wrong.
7. **Pending approvals**: anything with `needs_confirmation: true`, with the
   exact action and a one-click approve/deny. Empty most of the time.

**Lower — the audit:**
8. Session trace list: prompt, tools called, tokens, cost, artifacts written,
   commit SHA. One line per session, expandable.
9. **Spoken-word-count distribution** (§6.5.7) — your early warning that voice
   shaping has decayed.
10. `FAILURE_LOG.md` rendered, newest first. Read weekly.

**What to leave off, deliberately:** live price charts (MT5 does that better),
a chat window (you have a terminal and a microphone), token-usage sparklines
per model, anything described as an "agent thought stream". Watching an agent
think is entertainment, not observability.

**Build it as a single static HTML page** regenerated by the nightly job from
files in the repo. No server, no framework, no auth surface, no login to a
dashboard that reads your broker account. If it needs a server later, bind it
to `127.0.0.1` and nothing else.

---

## 10. EXISTING OPEN-SOURCE "JARVIS" PROJECTS — evaluated bluntly

Most GitHub "JARVIS" repos are a wake word, a Gemini call and `pyttsx3`. Those
are demos. These are the ones with architecture worth reading:

| Project | Verified signal | Worth stealing |
|---|---|---|
| **`open-jarvis/OpenJarvis`** | 9,093 stars, 2,096 forks, Python, created 2026-02-15, actively updated (GitHub API, 2026-08-28). Associated with Stanford Hazy Research / Scaling Intelligence Lab and an "Intelligence Per Watt" research programme. | **The most credible of the JARVIS-named projects.** Structured around tools, context, memory and agent-style execution; skills-as-tools discovered from a catalog; explicitly privacy-first/local. Read its skill-catalog and memory layout. Do not adopt it wholesale — it is a research artifact and you already have a harness. |
| **`leon-ai/leon`** | ~17k stars, running since 2017, MIT, Node+Python, mid-rebuild for 2.0. | Longest-lived open personal assistant. Worth reading for its **skill/module boundary and deterministic-workflow-vs-agent split** — the oldest and most battle-tested answer to "when does the assistant call code instead of thinking". |
| **`OpenHands`** (ex-OpenDevin) | ICLR 2025 paper; reported ~53% SWE-bench Verified, and ~72% with Claude Sonnet 4.5 + extended thinking in later reporting. | Read for **sandboxing, RBAC and audit trails** — it takes "the agent runs code on my machine" seriously in a way most projects don't. |
| **Open Interpreter** | ~60k stars. | The local-code-execution pattern, and a cautionary tale about how much power a natural-language shell hands out. |
| **`kortix-ai/suna`** | Open generalist agent; Next.js + FastAPI + Docker + Supabase/Redis, Playwright for browsing. | A reference for **service decomposition** if JARVIS ever outgrows one process. Note the operational weight — that stack is the thing you are trying not to need. |
| **`HKUDS/Vibe-Trading`** | 31,917 stars, 5,209 forks, Python, created 2026-04-01, topics include MCP + multi-agent + backtesting (GitHub API, 2026-08-28). | The most-starred trading-agent project. **Read it for how it wires MCP to a backtester — and read it adversarially.** A 30k-star agentic-trading repo is a strong prior for survivorship-biased backtests. Treat any performance claim in it as DISPROVEN until your own engine reproduces it. |
| **Home Assistant voice stack** (Whisper + Wyoming + Piper + openWakeWord) | ~8.9% of active HA installs per component (2026.7). | Not a JARVIS, but the **most-deployed local voice architecture in existence**. Steal the Wyoming component boundary even if you don't use the protocol. |

**Blunt summary:** none of these should be JARVIS. The Claude Code harness you
already run is better than all of them for this use case, because it is the one
with real context management, real permissions and real hooks. Read them for
**specific patterns** — OpenJarvis's skill catalog, Leon's workflow/agent split,
OpenHands's sandboxing, Home Assistant's voice component boundary — and write
your own 300 lines.

---

## 11. SECURITY — ranked by expected loss

### 11.1 Rank 1 — Indirect prompt injection / the lethal trifecta
**Severity: catastrophic. Likelihood: high the day JARVIS reads the web.**

Simon Willison's framing (June 2025) is the one to internalise. The **lethal
trifecta** is:

1. access to **private data**,
2. exposure to **untrusted content**,
3. the ability to **communicate externally**.

Any system with all three can be made to exfiltrate the private data by
whoever authors the untrusted content. There is no code vulnerability
involved — a language model has **no reliable separation between data and
instructions**. The GitHub MCP exploit is the canonical demonstration: one
server that could read attacker-filed public issues, read private repos, and
open PRs — all three circles in one tool.

**JARVIS assembles this trifecta by default.** Private data: `.env`, broker
credentials, `DECISIONS.md`, your strategy research. Untrusted content: every
web page a research agent fetches, every economic-calendar entry, every email
if you add one. External communication: the browser, the web fetch, any
notification channel, and — worst — MT5.

**Mitigations that actually work (architectural, not filters):**

- **Guarantee at least one circle is missing on every execution path.** Audit
  every tool against the three capabilities and make it structurally
  impossible for one session to hold all three. This is the whole defence.
- **Two-context split, enforced by process boundary:**
  - **DIRTY context** — reads the web, news, email. Has *no* filesystem write,
    *no* secrets, *no* MT5, and cannot make network calls other than fetching.
    Its **only** output is a file written to a quarantine directory.
  - **CLEAN context** — reads that file **as data**, holds the secrets and the
    MT5 connection, never fetches a URL.
  - The handoff is a file on disk, not a conversation. Untrusted text can then
    only lie to you; it cannot instruct the privileged agent's tools.
- **Plan-then-execute**: fix the plan *before* untrusted content enters, so
  content cannot rewrite the plan. This is one of the named patterns in
  *Design Patterns for Securing LLM Agents against Prompt Injections*
  (arXiv 2506.08837), alongside **Action-Selector** and **Dual LLM**. The
  paper's honest framing is worth repeating: these patterns **constrain the
  agent so it cannot solve arbitrary tasks** — security is bought with utility.
- **CaMeL** (DeepMind) is the strongest published version: the privileged LLM
  emits code in a sandboxed DSL specifying which tools run and how outputs
  flow, and untrusted output is never allowed to become control flow.
- **What does NOT work:** telling the model to ignore instructions in fetched
  content; regex filters; "prompt injection detection" classifiers. Assume
  every one of them fails.

### 11.2 Rank 2 — The MT5 connection
**Severity: direct financial loss. Likelihood: medium.**

- **No `order_send` in any MCP server, ever.** Not disabled — absent (§5.2).
- **Demo account credentials only** in anything an agent can read.
- Live credentials live in a separate file the agent has no path to, used only
  by a script Veer runs by hand.
- **Maker-checker**: the agent proposes an order ticket; a human approves it.
  This is the standard pattern for irreversible actions and it costs you one
  keystroke.
- **Risk-tier every action** by reversibility and blast radius. The widely used
  four-tier version: read/analysis runs freely; reversible writes run with
  logging sufficient to undo; **money movement, deletion and external
  communication require human approval, non-negotiable.**
- D-006 already says all of this. The gap is that it is enforced by prose.
  **Make it a permissions rule and a hook.**

### 11.3 Rank 3 — MCP supply chain
**Severity: high (full machine compromise). Likelihood: medium.**

The ecosystem numbers are bad and they are not hype:
- An AgentSeal scan of **1,808 servers: 66% had a security finding**; Enkrypt
  AI (Oct 2025) reported **33% of 1,000 scanned servers had critical
  vulnerabilities**. **40+ MCP CVEs disclosed in 2026 alone.**
- **CVE-2025-54136** (CVSS 8.8) confirmed the **rug-pull** pattern: tool
  definitions approved at install do **not** survive later server-side changes.
  A server can be benign when you audit it and malicious next week.
- **Tool poisoning**: adversarial instructions hidden in tool *descriptions*,
  parameter schemas or response content — which the model reads as
  instructions. The MCP spec provides no native defence against this, or
  against cross-server tool shadowing. It is an architectural trust-model
  problem, not a patchable bug class.
- OX Security (April 2026) reported a command-execution issue in the **official
  MCP SDKs** (Python, TypeScript, Java, Rust): the **stdio transport executed
  OS commands without sanitisation**, enabling RCE on a vulnerable host.

**Rules:**
1. **Pin exact versions.** Never `@latest` in a config file that runs unattended.
2. **Read the source before first run.** For a 500-line server this is 20 minutes.
3. **Prefer official/vendor-maintained servers** (Microsoft's Playwright,
   Google's chrome-devtools) over community ones.
4. **Write your own for anything touching money.** Non-negotiable.
5. **Re-audit on every upgrade** — the rug-pull CVE means install-time approval
   is not durable. Diff the tool descriptions, not just the code.
6. **Keep the total count small.** Each server is a trust decision you must
   maintain forever.

### 11.4 Rank 4 — Secrets
**Severity: high. Likelihood: medium.**

- `.env`, gitignored — CLAUDE.md already requires this. Verify with
  `git check-ignore -v .env` and add a pre-commit hook that greps staged diffs
  for key-shaped strings.
- **Deny the agent read access to `.env` explicitly** in Claude Code
  permissions. The agent needs the *effect* of a credential, not its value:
  give it a script that uses the key, not the key.
- Separate credentials by blast radius: demo MT5 / live MT5 / broker portal /
  API keys — four different secrets, four different scopes.
- Rotate anything that has ever appeared in a terminal you screenshotted.

### 11.5 Rank 5 — Unsandboxed local execution
**Severity: high. Likelihood: low if careful, certain if not.**

The agent runs shell commands on the machine that holds your trading account.
Overnight jobs get a strict allowlist (§8.2, guard 6). Interactive sessions get
the permission prompt. **Never enable a blanket bypass-permissions mode on this
machine.** If you want a fast lane, use it in a container or a scratch clone,
not in the repo that holds `state/`.

### 11.6 Rank 6 — Runaway spend
**Severity: moderate (money + a dead session). Likelihood: medium — it already
happened to this project once.**
Covered in §8.2. The loop breaker and the cost-velocity breaker are the two
that matter.

### 11.7 Rank 7 — Exposed local endpoints
**Severity: moderate. Likelihood: low.**
Ollama, the Obsidian REST API, any dashboard: **bind to `127.0.0.1` only**,
never `0.0.0.0`. Check with `netstat -ano | findstr LISTENING` after adding
anything. A gateway or dashboard holding every key you own must not be
reachable from your LAN.


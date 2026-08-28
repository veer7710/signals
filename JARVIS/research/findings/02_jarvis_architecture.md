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

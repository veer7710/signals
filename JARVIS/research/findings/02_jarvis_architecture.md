# 02 — JARVIS architecture research

**Date:** 2026-08-27
**Author:** research agent (Opus 5)
**Status:** research findings, not a decision record. Nothing here is CONFIRMED.
Every claim traceable to a source in §10. Numbers quoted from third parties are
labelled as such and are **not** numbers this project has computed.

---

## 1. BOTTOM LINE — the recommended architecture in ten sentences

1. Build JARVIS as **one main agent loop that owns all state**, running as
   Claude Code, with **stateless sub-agents used only for read-heavy or
   verbose work** — this is the single architectural choice the evidence most
   strongly supports.
2. Do **not** build a multi-agent society; the published failure taxonomies say
   most multi-agent failure is *design* failure (context not passed, no
   verification), and Anthropic's own multi-agent system reportedly burns ~15x
   the tokens of chat for a benefit that only pays on high-value parallel
   *research*, not on writes.
3. **Memory should be markdown files in the git repo** — the structure you
   already have (`SESSION_STATE`, `DECISIONS`, `FAILURE_LOG`, `EXPERIMENTS`)
   is the correct design for a corpus of this size; a vector DB or knowledge
   graph buys nothing until you are past roughly a thousand documents.
4. Add **one thing** to memory that you do not have: a typed claim format that
   forces every stored line to declare itself FACT / ASSUMPTION / DECISION /
   HYPOTHESIS with a source and a date, so retrieval cannot launder a guess
   into a fact.
5. **Verification must be external and mechanical** — tests, the backtest
   engine, MT5 read-backs, `git diff` — because the research is consistent that
   LLMs cannot reliably self-correct without an external signal; a "critic"
   agent that shares the generator's blind spots is theatre.
6. **Tools via MCP, but few of them, all pinned**: filesystem, an MT5
   **read-only** server, Obsidian's own REST/MCP endpoint, Playwright for the
   browser — and treat every MCP server as untrusted third-party code.
7. **Voice is a separate, dumb layer**: STT → the same main agent → a small,
   cheap **"voice shaper" model** that converts the agent's full answer into a
   spoken line under a hard word cap, enforced in code, not by politeness.
8. **The conciseness problem is solved structurally, not by prompting** — make
   the model emit two fields (`speech`, `detail`), send only `speech` to TTS,
   truncate it deterministically, and classify each reply into a response class
   with its own length budget.
9. **The dominant security risk is indirect prompt injection**, because JARVIS
   will read the web and email while holding both secrets and an MT5
   connection — never let one context both read untrusted text and hold a
   capability that can move money.
10. **Build order: memory → tools → scheduler+budget → dashboard → voice →
    local models.** Voice is the last thing, not the first, because it is the
    layer that adds the least capability and the most yak-shaving.

---

## 2. AGENT ARCHITECTURE — what the evidence actually says

### 2.1 Single agent vs multi-agent

The honest state of the evidence in 2026:

**Against multi-agent (strong, from people who shipped):**

- Cognition's *Don't Build Multi-Agents* is the canonical write-up. Its core
  claim: reliability comes from **context engineering**, and multi-agent
  architectures fail because decision-making becomes dispersed and context
  cannot be passed thoroughly enough between agents. Their update a year later
  is the useful part: the setups that *do* work share one property — **one main
  loop carries state; sub-agents are stateless workers with narrow scope.**
- The **read/write asymmetry** is the sharpest heuristic anyone has produced:
  *read* actions parallelise well; *write* actions do not, because you then
  have to both pass context in and merge conflicting outputs back out. For
  JARVIS: parallelise research, backtest sweeps, and log analysis. Never
  parallelise "edit the strategy code".
- **MAST** (*Why Do Multi-Agent LLM Systems Fail?*, NeurIPS 2025) built a
  taxonomy of 14 failure modes from 1,600+ annotated traces across 7 frameworks,
  grouped into (i) system design/specification issues, (ii) inter-agent
  misalignment, (iii) task verification and termination. Headline: **failures
  are predominantly design failures, not model failures.** More tokens and
  bigger models do not fix them.

**For multi-agent (narrow, and expensive):**

- Anthropic's *How we built our multi-agent research system* reports their
  orchestrator-worker Research system beating single-agent Opus by a large
  margin on breadth-first research, with a lead agent spawning 3–5 subagents
  that each run tools in parallel. The caveats in the same post are the
  important half: it uses on the order of **15x the tokens of a chat
  interaction**, token spend alone reportedly explains most of the performance
  variance, and it is suited to tasks that **parallelise cleanly and are
  read-only**. They explicitly do not claim this for coding.

**Verdict for JARVIS.** Use the Anthropic pattern *only* for the shape of work
it was validated on — parallel research and evidence-gathering. Use the
Cognition pattern for everything else. Concretely:

```
main loop (Claude Code, holds ALL state: session state, decisions, plan)
  ├─ sub-agent: researcher      (read-only tools, returns a summary)
  ├─ sub-agent: backtest-runner (runs study.py, returns the table only)
  ├─ sub-agent: log-reader      (greps overnight logs, returns anomalies)
  └─ sub-agent: adversary       (read-only, tries to break a claim)
```

Every one of those is **read-heavy, stateless, and returns a short artefact**.
None of them writes strategy code. That is the line.

You already have "6 agents" per `SESSION_STATE.md`. The action item is not to
add more — it is to audit each one against two questions: *does it write?* and
*does it need context the main loop has?* If yes to either, fold it back into
the main loop.

### 2.2 Context management — what actually works

Four mechanisms, in descending order of value for this project:

1. **Sub-agent context isolation.** A Claude Code sub-agent gets a fresh
   context window, its own system prompt, and a restricted tool list; it does
   not see your conversation history and returns only a summary. This is the
   cheapest large win: a backtest run that would dump 4,000 lines of output into
   your main context instead returns twelve lines. Config lives in
   `.claude/agents/*.md` with YAML frontmatter (`name`, `description`, `tools`
   allowlist, `disallowedTools`, `model`, `maxTurns`, `permissionMode`).
   Use `tools:` allowlists — this doubles as a security control.
2. **Compaction.** Claude Code auto-compacts past ~95% of the window by
   summarising the trajectory. Anthropic's API-side equivalent (context editing,
   beta header `context-management-2025-06-27`) clears old tool-use/result pairs
   while preserving the prompt-cache prefix; they report substantial token
   savings and a performance *improvement* on long-horizon tasks. Treat
   auto-compaction as a **failure mode to design around**, not a feature: a
   compaction that happens before you write `SESSION_STATE.md` throws away the
   session. Your existing rule "a session that ends without a checkpoint has
   thrown away its own work" is exactly right — enforce it with a hook, not a
   habit (see §6).
3. **File-system-as-context.** The most durable pattern: the agent writes
   findings to disk *as it goes* and re-reads on demand. This is what the
   Anthropic memory tool does (a plain file directory the model can CRUD), and
   what your repo already is. It survives compaction, crashes, and model
   switches. Anthropic's own reported gain from memory tool + context editing
   over baseline is large — but the mechanism is unglamorous: *write it down.*
4. **Retrieval.** Last, and least, at your scale. See §3.

### 2.3 Planning and decomposition

What works:

- **Plan first, in a separate phase, with a human gate.** Claude Code's plan
  mode exists for this. The reported consensus in 2026 practice is that planning
  is the differentiator, not prompt cleverness — parallelism without a plan just
  ships the wrong thing faster.
- **Write the plan to a file** (`NEXT_ACTIONS.md` — you have this). A plan in
  context is lost at compaction; a plan on disk is not.
- **Decompose to verifiable units.** Every subtask should end with something a
  machine can check: a test passes, a file exists, a number is produced. If a
  subtask ends with "the agent thinks it's fine", it is not a subtask.

What doesn't work, and should be skipped:

- **Elaborate planner/executor/critic hierarchies.** This is MAST category (i)
  in a box. The planner has less context than the executor and produces plans
  that don't survive contact with the filesystem.
- **Tree-of-thought / graph-of-thought style search** for practical agent work.
  Impressive on puzzle benchmarks, weak return on "run this backtest and tell me
  if it survives costs".
- **Re-planning every turn.** Burns tokens, causes drift. Plan, then execute
  until an assumption breaks, then re-plan explicitly.

### 2.4 Error recovery, verification, self-critique — proven vs marketing

**Proven:**

- **External verifiers.** The FunSearch/AlphaEvolve pattern — generator proposes,
  a *deterministic* evaluator scores against a fitness function or test suite
  that does not invoke an LLM. For JARVIS this maps perfectly onto your existing
  rule: `test_engine.py` must pass before any backtest number is trusted, and
  `study.py` (walk-forward, Monte Carlo, cost sensitivity, long/short split) is
  the fitness function. **Your verifier already exists. That is the single
  strongest thing about this project's architecture.**
- **Retry with the error text in context.** Boring, effective. Failed tool call
  → feed the stderr back → retry once → escalate. The `CRITICTOOL` line of work
  studies exactly this scenario (self-critique in tool-calling error cases) and
  the finding is that models handle *externally supplied* error signals far
  better than self-generated ones.
- **Cross-context review.** There is 2026 work (*Cross-Context Review*)
  specifically on separating production and review into different sessions —
  which is the honest justification for a reviewer sub-agent: not that it is
  smarter, but that it has **not** seen the reasoning that produced the error.
  That is why a fresh-context adversary agent beats "please double-check your
  work" in the same context.

**Marketing:**

- **Self-critique in the same context.** *Large Language Models Cannot
  Self-Correct Reasoning Yet* (DeepMind) is still the load-bearing citation:
  without external feedback, self-correction often *degrades* performance. The
  mechanism is correlated failure — the generator and the evaluator are the same
  weights with the same blind spots. Models will correct an identical error
  when it is presented as someone else's, and miss it in their own output.
- **Multi-agent debate as a quality mechanism.** Reported as no better than
  plain self-consistency for an equal number of sampled responses. You are
  paying N times for majority voting with extra steps.
- **"Reflection" as a product feature.** Where it helps, it helps because it
  smuggles in an external signal (a tool, a test, a retrieval). Where there is
  no external signal, it does not help.

**Rule to adopt:** *No claim advances a status level (`UNPROVEN` →
`PROMISING` → `SUPPORTED`) on the basis of an LLM's opinion. Only on the basis
of a program's output.* This is already the spirit of your CLAUDE.md; make it
literal.

---

## 3. MEMORY — the hard problem, and why yours is already close to right

### 3.1 Files vs vectors vs graphs

The decision is a function of corpus size and query type, and at your size it is
not close.

| Corpus | Query type | Right tool |
|---|---|---|
| 10–500 docs | "what did we decide about X" | **Markdown + an index file + grep** |
| 500–5,000 | mixed recall | Markdown + BM25/full-text (SQLite FTS5) |
| 5,000+ | fuzzy semantic recall | Embeddings + vector index |
| Any size | "what changed, and when" | Temporal graph (only if you need it) |
| Code | "what calls this / blast radius" | Code graph (tree-sitter), not embeddings |

**Evidence that files beat RAG at personal scale.** The recurring, well-documented
pattern in 2026 write-ups is teams building a vector pipeline for a corpus that
turns out to be ~150K tokens — i.e. it fits in one prompt. The reported break
point for the "markdown index + wikilinks, agent follows links" approach is
around **1,000 documents**, past which relationship-following starts missing
things and a real retrieval layer earns its keep. Your JARVIS state directory is
five files. You are two orders of magnitude below the threshold.

There is a second, less-quoted finding worth knowing: on **numerical reasoning**
tasks, retrieval-augmented setups have been reported to *beat* long-context
stuffing, because retrieval forces the relevant numbers into a small window
instead of burying them. For a trading system this is a real consideration — but
the fix is "pass the results table explicitly", not "install a vector DB".

**Grep is a retrieval engine.** `grep -r "donchian" JARVIS/state/` is exact,
zero-latency, zero-dependency, auditable, and has no embedding drift. An agent
with `Grep` + `Glob` + `Read` and a good directory layout outperforms a badly
tuned vector store on a small corpus, and it never hallucinates a chunk boundary.

**When to revisit:** when `JARVIS/` exceeds ~1,000 markdown files, or when you
genuinely need "what did I believe about GOLD in March vs now" as a *query*
rather than a `git log`. Note that **git already gives you temporal memory for
free** — every belief change is a commit. Most of what a temporal knowledge
graph sells you, `git log -p JARVIS/state/DECISIONS.md` gives you today.

### 3.2 Typed memory: fact vs assumption vs decision

This is the genuinely valuable upgrade, and it is a *format* change, not a
product purchase. There is no mature off-the-shelf implementation of
epistemically-typed personal memory — the memory vendors store "facts" with no
provenance discipline, which for a trading system is actively dangerous.

Proposed line format for `DECISIONS.md`, `EXPERIMENTS.md`, and a new
`BELIEFS.md`:

```
[FACT]       2026-08-27  src:study.py#L142   GOLD 1h donchian_trend WF Sharpe = <computed>   conf:high
[ASSUMPTION] 2026-08-27  src:none            Broker spread stays under 0.3 pips overnight    conf:low   expires:2026-09-30
[DECISION]   2026-08-27  src:D-005           Do not evade usage limits. Settled.             conf:final
[HYPOTHESIS] 2026-08-27  src:R-002           Prop-firm rule caps parallel accounts at N      conf:med   test:TODO
[DISPROVEN]  2026-08-27  src:E-001           Old signal system had an edge                   conf:final
```

Five rules that make it work:

1. **Every line has a source.** `src:none` is legal but visible — and an
   `[ASSUMPTION]` with `src:none` and `conf:low` is exactly what should get
   re-tested first.
2. **Assumptions expire.** A date field forces re-validation. Facts do not
   expire; assumptions rot.
3. **Only a program can write `[FACT]`.** Have the agent emit `[HYPOTHESIS]`
   and let a script promote it to `[FACT]` when `study.py` output is attached.
   This is your existing vocabulary (CONFIRMED/SUPPORTED/…) applied to *every*
   stored line, not just strategy claims.
4. **Contradictions are appended, not overwritten**, with the superseded line
   marked `[SUPERSEDED by …]`. Git preserves the history anyway; making it
   explicit means the agent reads it.
5. **A hook validates the format on commit.** Unparseable line → commit fails.
   Deterministic enforcement beats an instruction the model will drift from.

### 3.3 The named products, evaluated honestly

**Graphify (graphifyai.net / graphify.net / graphify.com)** — *real tool, wrong
category, inflated marketing.*
- What it actually is: a **code** knowledge graph. Tree-sitter parses your repo
  (37 languages) plus docs/SQL/PDFs into a queryable graph so the agent asks
  "what connects auth to the database?" instead of grepping. PyPI package is
  `graphifyy` (double-y); CLI is `graphify`; install is
  `uv tool install graphifyy && graphify install`. Apache-2.0/MIT dual.
- **It is not a personal memory system.** It will not remember that you decided
  not to relitigate D-005. Do not buy it as the answer to §3.
- Skeptical notes you should have: the version is **0.9.50 with 218 PyPI
  releases** (very fast, very young); star counts quoted across write-ups are
  mutually inconsistent (one blog says 75.2k, the repo page reads 111.6k); the
  project runs **three different domains** (`graphify.com`, `graphify.net`,
  `graphifyai.net`); and the discovery surface is saturated with near-identical
  DEV.to/Medium comparison posts, which is a marketing pattern, not an
  engineering one. The token-saving claims ("8x–120x", "70x", "up to 80%") are
  vendor numbers with no independent replication.
- **Verdict: OPTIONAL, PHASE 6.** Worth ten minutes *later*, pointed at the
  trading codebase, if and only if the repo grows large enough that the agent
  wastes real context re-reading files. Not part of the memory architecture.
  Note the package name is one character from an obvious typosquat target —
  pin the exact version.

**Obsidian + MCP** — *yes, but as a view, not as the store.*
- Install the **`obsidian-local-rest-api`** community plugin
  (coddingtonbear, ~2.9k stars). Since v5 (July 2026) it **serves MCP natively**
  at `/mcp/`, so you do not need a separate bridge process. HTTPS on port
  **27124** with a bearer API key from the plugin settings; self-signed cert.
- The right framing: **point an Obsidian vault at `JARVIS/` in the git repo.**
  The files stay the source of truth; Obsidian gives you graph view, backlinks,
  daily notes, and mobile access over the *same* markdown. Zero migration, zero
  lock-in, and if Obsidian dies tomorrow you still have your memory.
- Do **not** let Obsidian become the store with the repo as a copy. Two writers,
  one truth, guaranteed divergence — and your CLAUDE.md rule 6 ("if memory and
  repository disagree, TRUST THE REPOSITORY") already anticipates this.

**mem0** — *skip for now.* Vector-first memory layer, most portable of the three
(bolts on without adopting a runtime). Its own reported LOCOMO/LongMemEval
numbers are strong. But: LOCOMO is a **disputed benchmark** — Zep reported ~84%,
Mem0's replication scored Zep at ~58% alleging methodology errors, Zep rebutted
with ~75%. When three vendors cannot agree on a score for the same system on the
same benchmark, the benchmark is not evidence. Adds a service, a store, and an
extraction LLM call per turn to solve a problem you do not have at five files.

**Letta / MemGPT** — *skip.* It is a **stateful agent runtime** (core / recall /
archival tiers), not a memory library. Adopting it means adopting its agent loop
instead of Claude Code's. Wrong trade for you: you would give up Claude Code's
tooling, subagents, hooks, and permissions to get a memory tiering scheme you
can approximate with three markdown files and a hook. Genuinely interesting
research; wrong layer to insert here.

**Zep / Graphiti** — *skip now, the one to revisit later.* Graphiti is the
open-source temporal knowledge graph underneath Zep (20k+ stars, runs on Neo4j /
FalkorDB / Kuzu / Neptune). The idea is sound and it is the best-motivated of
the three: every edge carries valid-from/valid-to, so "what did I believe then
vs now" is a first-class query. Cost: a graph database, an LLM extraction step
per write, and a schema. **Revisit only if** you get to the point of wanting to
query belief evolution across years of trading decisions programmatically. Until
then, `git log` is the temporal graph and it costs nothing.

**Anthropic memory tool + context editing** — *this is the one worth adopting,
and it is not a product.* The memory tool is literally "Claude gets a directory
it can create/read/update/delete files in, that persists across sessions". That
is what you built by hand. If you move any part of JARVIS to the Agent SDK
rather than the CLI, use `BetaAbstractMemoryTool` (Python) subclassed to point at
`JARVIS/state/`, plus the `context-management-2025-06-27` beta header for
server-side tool-result clearing. Same architecture, less code.

---

## 4. TOOL USE / MCP

### 4.1 Principle first

Every MCP server is **third-party code that injects text directly into your
agent's context**. Tool descriptions are prompt input. That makes the MCP list a
security surface, not a feature list (§8.3). So: **few servers, each pinned,
each with a reason.**

Also relevant: token cost. An independent 2026 benchmark measured the same
browser task at **~114k tokens over MCP vs ~27k over a CLI** — roughly 4x. MCP
buys you *stateful* tool sessions; a CLI wrapped in a Bash call is often
cheaper and simpler. Do not reach for MCP when a script will do. Your
`JARVIS/bin/` directory is the right instinct.

### 4.2 The servers actually worth running

**Filesystem** — you do not need one. Claude Code's native `Read`/`Write`/
`Edit`/`Glob`/`Grep` are better than the reference filesystem MCP server for
this use case, and they respect Claude Code's permission system. Skip.

**MT5 — this is the important one, and the answer is: two servers, or one plus a
script.**

The underlying constraint is hard and worth stating plainly: **the official
`MetaTrader5` PyPI package is Windows-x86-64 only** (wheels for CPython
3.10–3.13), and it **requires a running MT5 terminal on the same machine** — it
drives the terminal, it is not a broker API. `mt5linux` exists (Wine + rpyc) but
adds two failure modes to a financial path. You have a Windows PC; run it there.
Everything else in JARVIS can live anywhere.

Two candidates, and the split matters:

- **`Cloudmeru/MetaTrader-5-MCP-Server`** — **strictly read-only by design**:
  `order_send()`, `order_check()` and position modification are excluded from
  the safe namespace. Exposes `mt5_query` (validated JSON reads), `mt5_analyze`
  (indicators/charts), `mt5_execute` (Python in a curated namespace). stdio /
  HTTP / ASGI transports. MIT. **Very young — single-digit stars.** Read the
  code before you run it; it is small enough to audit in an afternoon.
- **`ariadng/metatrader-mcp-server`** — much more adopted (~776 stars, 255
  forks, MIT, v0.5.x, `pip install metatrader-mcp-server`), **32 tools including
  `place_market_order`, `place_pending_order`, `modify_position`**, and
  **no read-only mode**.

**Recommendation:** install the **read-only** server for the always-on agent
path. Do *not* wire an order-placing MCP server into a general assistant — the
combination of "reads the web" and "can place orders" is the exact thing §8
tells you never to build. If and when you want automated execution, put it
behind a **separate, explicitly-invoked script** with its own credentials, its
own confirmation step, and a demo-account default — consistent with your
existing standing rule that nothing touches a live account without in-session
confirmation. Belt and braces: use a **broker account with trading disabled** or
an investor (read-only) password for the agent's terminal.

**Browser: Playwright, not vision.** The 2026 reliability picture is
consistent — DOM/accessibility-tree-driven automation beats screenshot+vision
computer-use by a reported 12–17 percentage points on common tasks (Playwright+
Claude ~92%, Stagehand ~89%, Anthropic Computer Use ~78%, OpenAI CUA ~75%).
Use `@playwright/mcp` (Microsoft) when the agent needs a *persistent* browser
session across many turns; use a Playwright **script via Bash** when it is a
one-shot scrape, because it is ~4x cheaper in tokens. `browser-use` is
interesting but is a vision/DOM hybrid agent framework that wants to own the
loop — you already have a loop.

**Computer use / screen reading on Windows.** The right mechanism is the
**Windows UI Automation accessibility tree**, not screenshots: it is text, it
works with non-vision models, and a snapshot takes 100–500ms.
`deploymenttheory/windows-mcp-server` (Go, MIT, 35 tools across 13 toolsets,
UIA-based, no CV model required) is the cleanest implementation I found — but
it has **1 star**, and its own docs state that PowerShell/Registry/FileSystem/
Process tools have **full system access with no sandboxing**. That is an honest
README and a genuinely dangerous tool. **Do not install this in Phase 1.** If you
later need MT5 GUI automation that the Python API cannot do, run it in a Windows
VM, not on your daily driver.

**Email / calendar.** `taylorwilsdon/google_workspace_mcp` is the best-maintained
self-hostable option (Gmail + Calendar + Drive + Docs + Sheets, OAuth 2.1,
multi-user, and explicitly sends no data anywhere except Google's APIs using
your own OAuth client). Google also now publishes first-party MCP configuration
guides for Calendar and Workspace. **But add email last**, and add it read-only
first — an agent that reads your inbox is an agent that reads text written by
anyone who knows your address (§8.1).

**Market data.** Nothing here needs MCP. Your data pipeline should be scripts
writing to `data/`, run on a schedule, with the agent reading files. Market data
via MCP means paying context tokens for numbers that belong in a parquet file.

**Memory MCP servers.** The official `memory` reference server (knowledge-graph
based) exists and is one of the seven still-active first-party reference servers
(Fetch, Filesystem, Git, Memory, Sequential Thinking, Time, Everything). Skip
it — it duplicates your files with worse durability. Note also that the
third-party server table in `modelcontextprotocol/servers` was **retired in
April 2026** in favour of `registry.modelcontextprotocol.io`; many early servers
(GitHub, Postgres, Puppeteer, Slack, Brave) moved to `servers-archived`. If a
tutorial tells you to install one of those, the tutorial is stale.

---

## 5. VOICE

### 5.1 The pipeline (and why not a speech-to-speech model)

```
mic → wake word → VAD → STT → [main agent] → voice-shaper → TTS → speakers
                    ↑                                          │
                    └───────── barge-in: cancel ───────────────┘
```

Use the **cascaded STT→LLM→TTS pipeline**, not an end-to-end realtime
speech-to-speech model. Realtime models are lower latency and more natural, but
you **cannot inspect or constrain the text** between reasoning and speech — which
is precisely where the conciseness fix lives (§5.5), and precisely where the
security boundary lives. For a system that trades, inspectability wins.

### 5.2 Speech-to-text

- **Cloud, best accuracy/latency:** **Deepgram Nova-3** (reported ~5–7% WER in
  production, sub-300ms streaming) — and **Deepgram Flux**, which has
  model-integrated end-of-turn detection, is the specifically voice-agent-shaped
  option. AssemblyAI Universal-2 is the accuracy leader among streaming
  commercial models per its own reporting.
- **Local, English, fast:** **NVIDIA Parakeet-TDT** — reported more accurate
  than Whisper large-v3 on English + 25 EU languages at vastly higher
  throughput, ~4x faster than Whisper Small on CPU. This is the surprise pick;
  most people default to Whisper out of habit.
- **Local, multilingual / general:** **faster-whisper** (CUDA on Windows, built-in
  VAD pipeline) or **whisper.cpp** (CPU/CUDA/Vulkan/Metal, `--stream`). Expect
  0.5–2s behind live speech. Whisper large-v3 sits around ~10% WER depending on
  audio.
- **Recommendation:** start with **faster-whisper + `distil-large-v3` or
  `large-v3-turbo` on your GPU** because it is a `pip install` and works
  offline. Move to Deepgram only if end-of-turn detection becomes the annoyance
  (it usually does).

### 5.3 Text-to-speech

- **Local, and the right default: Kokoro-82M.** Apache-2.0, ~327MB weights,
  54 voices, runs **faster than realtime on CPU**, much faster on GPU. Install
  either `pip install kokoro soundfile` (+ `espeak-ng`) or the ONNX route
  (`kokoro-onnx` + `kokoro-v1.0.onnx` + `voices-v1.0.bin`). This is the best
  quality-per-milligram in open TTS right now and it costs nothing per word,
  which matters when your assistant talks all day.
- **Cloud, if you want the voice to be *good*:** **Cartesia Sonic** (reported
  ~188ms P50 time-to-first-audio) or **ElevenLabs Flash v2.5** (~288ms P50 in
  the same independent Coval benchmark, despite marketing ~75ms figures — note
  the discrepancy: **TTFB is not TTFA**; container headers contain no audio, so
  vendor TTFB numbers flatter reality).
- **Skip Piper** for interactive use. It is the Home Assistant default and it is
  fine for "the garage door is open", but one benchmark put it at ~1,720ms first
  audio, which is conversationally dead.
- **Recommendation: Kokoro local, ElevenLabs/Cartesia optional.** A local TTS
  also means JARVIS can talk with no network, which for a background system that
  reports overnight results is genuinely useful.

### 5.4 Wake word and barge-in

- **Wake word: `openWakeWord`** (`pip install openwakeword`, Apache-2.0 code).
  Ships pretrained models including — conveniently — **"hey jarvis"**. A single
  Pi 3 core runs 15–20 models in realtime, so CPU cost on a PC is nil. Custom
  words trainable via a Colab notebook. **Caveat: the pretrained models are
  CC-BY-NC-SA** (non-commercial) because of training-data licensing; fine for
  personal use, not for a product. Also note the project's release cadence has
  been slow — v0.6.0 is from Feb 2024 — so treat it as stable-but-quiet rather
  than actively developed.
- **Picovoice Porcupine** is the commercial alternative (~97%+ detection, <1
  false alarm per 10h claimed, tiny footprint). Better if you want a supported
  SDK or a genuinely custom phrase; openWakeWord's own benchmarking claims to
  beat it on their test data, with the obvious caveat that it is their test data.
- **Barge-in** is the one part you should not write yourself. The correct
  behaviour: VAD fires on the user's track while the agent is speaking →
  **cancel TTS playback, cancel the in-flight LLM stream, roll back the
  interrupted turn in the transcript, start STT on the new audio** — target
  under ~200ms. Getting the transcript rollback right (so the agent knows it was
  cut off mid-sentence and does not believe it said the whole thing) is the part
  everyone gets wrong.
- **Use a framework for this layer: Pipecat** (`pipecat-ai/pipecat`, ~14.8k
  stars, BSD-2, v1.0). It is Python, it is pluggable, and it explicitly supports
  **fully local pipelines** — Whisper/Moonshine/FunASR for STT, Ollama for LLM,
  Piper/XTTS/Kokoro for TTS. Install: `uv tool install "pipecat-ai[cli]"` then
  `pipecat init quickstart`. LiveKit Agents (1.5.x, adaptive turn detection,
  native MCP tool support) is the alternative and is better if you ever want
  telephony or real concurrency — you want neither. **Pipecat, because
  conversation logic and frame-level control is exactly your problem.**
- **Worth studying, not necessarily installing: the Home Assistant / Wyoming
  stack.** `OHF-Voice/wyoming` + `rhasspy/wyoming-satellite` is a
  battle-tested, genuinely deployed peer-to-peer protocol for wiring
  wake-word/STT/TTS services together, running on ~9% of active Home Assistant
  installs. Even if you don't adopt it, steal its architecture: **each stage is
  a separate process behind a simple socket protocol**, so you can swap Whisper
  for Parakeet without touching anything else. That decoupling is the thing.
- **Avoid OpenClaw** despite its enormous adoption — see §7.

### 5.5 THE VOICE-CONCISENESS SOLUTION

This is the part you explicitly care about, so here it is concretely.

**Why "be concise" fails.** LLMs are trained on written text and are verbose by
default; voice-agent practitioners consistently report that a rule has to be
**restated in multiple sections of the prompt** to be followed at all, and it
still decays over a long conversation. Worse, in JARVIS's case the *same model*
is doing deep analytical work — you actively *want* it verbose when it writes
`EXPERIMENTS.md`. A single instruction cannot serve both. Prompting alone is the
wrong layer.

**The fix is five mechanisms, layered. Each one is enforceable in code.**

---

**(1) Split the output into two typed channels. This is the core move.**

The agent never emits "a response". It emits a structured object:

```json
{
  "class": "finding",
  "speech": "Donchian trend fails the cost test. Sharpe drops to point four.",
  "detail": "Walk-forward on GOLD 1h ... [full paragraphs, tables, numbers]",
  "next": "Want me to re-run at 4h?"
}
```

`detail` goes to the terminal, the dashboard, and the log. **Only `speech`
reaches TTS.** Brevity stops being a request the model can drift away from and
becomes a **schema constraint** — and the model no longer has to choose between
being thorough and being brief, because it is doing both, in different fields.
That conflict is the actual root cause of essay-mode voice assistants.

**(2) Response classes with hard, per-class word budgets.**

Force `class` to be one of a fixed set, and enforce the budget in code:

| class | budget | example |
|---|---|---|
| `ack` | ≤ 4 words | "Done." / "Running it now." |
| `status` | ≤ 12 words | "Backtest is at 60 percent. About three minutes." |
| `finding` | ≤ 25 words | "It fails the cost test. Sharpe drops to point four." |
| `question` | ≤ 15 words | "Demo or live?" |
| `error` | ≤ 20 words | "The engine test failed. I stopped before trusting the numbers." |
| `brief` | ≤ 60 words | only when you explicitly say "tell me about…" |

Classification is a cheap, reliable task. Length control is not. So you make the
model do the easy thing and let a lookup table do the hard thing.

**(3) Deterministic truncation at the TTS boundary. Non-negotiable.**

```python
def to_speech(reply):
    budget = BUDGETS[reply["class"]]
    words = reply["speech"].split()
    if len(words) > budget:
        text = " ".join(words[:budget]).rstrip(",;:") + "."
        text += " Details are on screen."
    else:
        text = reply["speech"]
    return strip_markdown(speak_numbers(text))
```

The model cannot argue with a slice. This one function is worth more than any
amount of prompt tuning, because it converts a probabilistic property into a
guaranteed one. The "Details are on screen" tail is important: it gives the
system a graceful way to be short without being unhelpful.

**(4) A dedicated voice-shaper model — decouple reasoning verbosity from speech
verbosity.**

Do not ask the analytical agent to also be a good speaker. Run a **second, tiny,
fast model** (Haiku, or local Qwen via Ollama) whose *entire job* is:

> Input: the agent's full answer + the response class.
> Output: one spoken line, ≤ N words, no markdown, no lists, numbers rounded and
> written as words.

Its system prompt is short, never changes, and is dense with **few-shot pairs** —
which are dramatically more effective than adjectives like "concise":

```
FULL:   The walk-forward analysis across six folds produced a mean Sharpe of
        0.42 after applying realistic spread and commission, down from 1.31
        gross, and the long/short split shows the edge is entirely long-side.
SPOKEN: Costs kill it. Sharpe falls to point four, and it's long-only.

FULL:   I have written the regression test and it passes.
SPOKEN: Test passes.

FULL:   I could not connect to the MT5 terminal; the terminal does not appear
        to be running, so I have not fetched today's bars.
SPOKEN: MT5 isn't running. No data yet.
```

Ten of these are worth a page of instructions. This also **cuts latency and
cost**: the shaper is a small model on a short input, so speech starts while the
big model is still writing `detail`.

**(5) Prompt reinforcement, done properly.**

In the shaper prompt (and the top *and* bottom of the main voice prompt):

- "You are being **heard, not read**. No markdown, no bullet points, no headings,
  no code, no URLs."
- "**Lead with the answer.** Never with preamble. Never 'I'd be happy to…',
  never 'Great question', never restate the question."
- "**Numbers are spoken**: 'point four two' not '0.4231'. Round to two
  significant figures. Never read a table aloud."
- "If the honest answer is one word, say one word."
- "If it needs more than N words, say the headline and add 'details are on
  screen'."
- "**Never apologise.** State the fact."

**(6) Stream sentence-by-sentence into TTS**, and for `class: ack` stop after
the first sentence regardless. This makes short replies *feel* instant, which is
most of the perceived quality.

**Test it.** Write `JARVIS/tests/test_voice_shape.py` with ~30 (full answer →
expected max words) cases and assert the budget holds. Conciseness becomes a
regression test rather than a vibe — which is exactly how you treat everything
else in this repo.

---

## 6. MODEL ROUTING, COST, LOCAL MODELS

### 6.1 OmniRoute — honest evaluation: SKIP

Checked the repo directly (`github.com/pitbaden/omniroute`):

- **8 stars, 1 fork**, MIT, TypeScript, 418 commits, `npm install -g omniroute`,
  runs an OpenAI-compatible endpoint on `localhost:20128`.
- The README claims **339 providers, 19 routing strategies, a built-in MCP
  server with 94 tools, A2A v0.3, Memory and Skills systems, Cloud Agents
  (codex-cloud/devin/jules), a Guardrails framework, an Electron desktop app,
  900+ tests, 30+ language translations, and 210+ planned features across
  multiple phases.**

Those two paragraphs do not describe the same object. A project with that
surface area and 8 stars is one person plus a code-generating model, and the
encyclopedic marketing-toned README is the tell. There are also several
byte-identical forks under different owners circulating in search results, which
is a distribution pattern, not an adoption pattern.

**None of this is illegal or even bad**, but it is not infrastructure you put in
front of every LLM call in a system that trades money. An AI gateway is a
**single point of failure with your API keys in it.**

**And more importantly: you do not need one.** You run Claude Code on a
subscription. A router saves money by sending easy calls to cheap models — but
Claude Code already lets you set `model: haiku` per sub-agent in frontmatter,
which captures most of that benefit with zero new infrastructure and zero new
attack surface.

If you ever genuinely need multi-provider routing, use **LiteLLM** — years old,
tens of thousands of stars, used in production widely, same OpenAI-compatible
proxy shape. Boring is the correct property for this component.

**Verdict: SKIP OmniRoute. Use per-subagent `model:` frontmatter now; LiteLLM
if you ever actually need a gateway.**

### 6.2 Local models via Ollama — where they earn their place

Local models are good enough in 2026 for **bounded, structured, high-volume**
tasks. They are not good enough to be the main JARVIS loop.

**Good local jobs:**
- The **voice shaper** (§5.5.4) — short input, short output, runs constantly.
- Classification and routing ("is this email actionable?", "which log lines are
  anomalies?").
- Summarising long tool output before it enters the main context.
- Overnight bulk work where latency doesn't matter and volume is high.
- Anything you'd feel bad about paying per-token for a thousand times.

**Bad local jobs:** strategy design, code changes to the backtest engine,
anything where a subtle error costs you money. Do not economise on the thinking.

**Model picks (24GB VRAM class, from 2026 comparisons — verify locally before
trusting):**
- **`qwen3-coder:30b`** — 30B MoE, ~3.3B active, ~19GB at Q4_K_M, 256K context.
  Reported best quality-per-GB in the 24–32GB tier and strong on tool selection.
- **`qwen3.6:27b`** — reported ~18GB, strongest general/agentic scores in the tier.
- **`gpt-oss:20b`** — ~14GB, the answer if you only have 16GB.
- Practical note repeated across sources: **Qwen3.x handles tool-calling format
  more reliably** than Mistral or older Llama, and you should **disable
  reasoning mode for tool-calling** — thinking traces corrupt structured output.

`ollama pull qwen3-coder:30b`. Bind Ollama to `127.0.0.1` only (§8.7).

**When local beats cloud:** high volume × low stakes × latency-insensitive, or
network-independence. **When cloud wins:** everything you'd put your money on.

---

## 7. EXISTING OPEN-SOURCE "JARVIS" PROJECTS — evaluated bluntly

**Most of them are demos.** The pattern is: wake word + Whisper + an OpenAI call
+ TTS + a README with a movie reference. There is no architecture to steal
because there is no architecture. Specifically, be suspicious of any repo whose
main artefact is a YouTube demo.

**OpenClaw** — the elephant. ~374k stars, formerly Clawdbot/Moltbot, personal
agent living in WhatsApp/Telegram/Signal/Discord/iMessage, ~5,700 community
"skills", author joined OpenAI Feb 2026 with the project moving to a foundation.
It is genuinely the most-adopted thing in this category.

**Do not install it.** The 2026 security record is not a matter of opinion:
Cisco Talos called it "an absolute nightmare" from a security perspective; The
Register called it a "dumpster fire"; Oasis Security published **ClawJacked**, a
vulnerability chain letting *any website* silently take full control of a
developer's agent with no user interaction; researchers found community skills
performing **active data exfiltration** plus direct prompt injection to bypass
safety; group chats ran powerful tools with no isolation, exposing environment
variables and API keys; and misconfigured public instances have leaked millions
of records including tokens and credentials.

The architecture that makes it popular — an agent with broad host control,
reachable from messaging apps, running community-contributed skills — is
precisely the architecture that makes it unsafe. It is the single clearest
real-world demonstration of the risk in §8. **Read its skill format for ideas.
Do not run it, and above all do not run it on a machine with an MT5 terminal
logged into a funded account.**

**What to actually steal from, per component:**
- **Claude Code itself** — subagents, hooks, skills, permission modes, plan
  mode. You are already standing on the best-engineered agent harness available;
  most "JARVIS" repos are reimplementing it worse.
- **Pipecat** — the voice pipeline and interruption handling.
- **Wyoming / wyoming-satellite** — the decoupled-processes-behind-a-socket
  design for the voice stack.
- **Home Assistant Assist** — the best-proven *local* voice architecture in
  existence, and the reason openWakeWord and Piper are mature at all.
- **The MAST paper and Cognition's post** — for what *not* to build.

**"OpenJarvis", "Hermes Jarvis", and similar** surfaced in searches with heavy
marketing framing and thin primary sources. Treat as unverified. I could not
find independent engineering write-ups for them, which for a personal
trading-adjacent system is a disqualifier on its own.

---

## 8. SECURITY — ranked by expected loss

### 8.1 Rank 1: Indirect prompt injection (severity: catastrophic, likelihood: high)

**The threat.** JARVIS reads a web page, a broker email, a forum post about
prop-firm rules, or a PDF. That text contains instructions. The model cannot
reliably distinguish "content I was asked to read" from "instructions I was
given". If the same context also holds your MT5 connection or your API keys,
you have handed the tools to whoever wrote the page.

**The frame to use: the lethal trifecta.** A context becomes dangerous when it
combines (1) access to private data, (2) exposure to untrusted content, and
(3) the ability to communicate externally or act irreversibly. **Any two is
survivable. All three is exploitable.** Design so no single context ever holds
all three.

**Mitigations, in order of actual effectiveness:**

1. **Capability separation (do this).** The agent that browses has **no** MT5
   tool, **no** secrets in env, and **no** write access to `JARVIS/state/`. It
   writes to a quarantine directory. A separate, clean-context step reads that
   quarantine output *as data* and decides what to promote. This is
   architectural and it actually works, unlike filtering.
2. **Dual-LLM / CaMeL pattern (adopt the shape).** A **privileged** LLM plans
   and holds tools but never sees raw untrusted text; a **quarantined** LLM
   processes untrusted text and has **no tools at all**, returning only typed,
   schema-validated extracts (a number, an enum, a bounded string). Evaluated on
   AgentDojo, CaMeL reportedly mitigated ~67% of injection attacks — note that
   is **not 100%**, which is why (1) is the load-bearing control and this is the
   second layer. Practitioner consensus is that dual-LLM patterns become a
   default architecture over 2026–27.
3. **Human-in-the-loop for irreversible actions (you already have this).** Your
   standing rule — nothing touches a live account without in-session
   confirmation — is the correct control and is stronger than any technical
   mitigation listed above. **Extend it explicitly to: sending email, posting
   anything publicly, `git push --force`, deleting files outside a scratch dir,
   and any spend.**
4. **Structured tool calls with typed arguments.** A tool that takes
   `symbol: Literal["XAUUSD", ...]` and `volume: float ≤ 0.01` cannot be talked
   into something else. Constrain at the type level, not the prompt level.
5. **Input filtering / "ignore instructions in retrieved content".** Listed last
   deliberately: it is bypassable and provides comfort rather than security.
   Include it, rely on nothing.

### 8.2 Rank 2: The MT5 live account (severity: direct financial, likelihood: medium)

Irreversible, denominated in money, and reachable by an automated process. Controls:
- **Investor (read-only) password** for the agent's terminal, or a terminal
  logged into a **demo** account, as the default.
- The always-on agent gets the **read-only** MCP server. Order placement lives
  in a separate script, invoked explicitly, never exposed as an ambient tool.
- **Kill switch:** a documented one-liner that closes the terminal and revokes
  the token. Put it in `JARVIS/bin/` and in `DECISIONS.md`.
- **Position-size cap in code**, not in the prompt.

### 8.3 Rank 3: MCP supply chain (severity: high, likelihood: medium)

Three named attack classes, all with public write-ups:
- **Tool poisoning** — malicious instructions hidden in tool descriptions
  (including in code comments), which the model reads as prompt input. Invariant
  Labs' original disclosure.
- **Rug pull** — a server you approved silently changes its tool descriptions in
  a later version; the host reloads them without re-prompting.
- **Typosquatting / supply chain** — npm and PyPI. Directly relevant here: the
  Graphify CLI is `graphify` but the package is **`graphifyy`**. That is one
  character from a trivially registrable trap. Read the install command; don't
  guess it.

Controls: **pin exact versions** of every MCP server and re-review on upgrade;
prefer servers small enough to actually read; run `mcp-scan` (Invariant Labs,
open source) over your MCP config; keep the server count low.

### 8.4 Rank 4: Secrets (severity: high, likelihood: medium)

Your CLAUDE.md rule ("no secrets in the repo, env vars or a gitignored `.env`")
is correct and is the 80%. Upgrades, cheapest first:
- Verify `.gitignore` covers `.env`, `*.key`, `*.pem`, and any MT5 config; add a
  **pre-commit hook** that greps for high-entropy strings and broker patterns.
  Rely on the hook, not on remembering.
- **1Password CLI** (`op run -- <cmd>` resolves `op://` references at launch and
  never writes to disk) if you want to stop having a plaintext `.env` at all.
  `sops` + `age` is the good free alternative for encrypted-at-rest config in git.
- **Scope keys per purpose.** The browsing agent's environment should contain
  no broker credentials at all — enforced by launching it with a filtered env,
  not by asking it nicely.

### 8.5 Rank 5: Unsandboxed system tools (severity: high, likelihood: low if you're careful)

`windows-mcp-server` and its peers explicitly ship with full system access and no
sandbox. That is a legitimate design choice for a controlled VM and a bad one for
your daily driver. **If you need OS-level automation, run it in a Windows VM
with no credentials and no funded terminal.**

### 8.6 Rank 6: Runaway spend (severity: moderate, likelihood: medium)

Documented 2026 incidents include a widely-shared agent that ran up a
five-figure AWS bill on an unattended task. For overnight runs specifically:
- **Hard cap, not an alert.** A ceiling that rejects calls, with a manual reset.
- `maxTurns` on every sub-agent (Claude Code frontmatter supports it).
- A wall-clock timeout on every scheduled job — the OS kills it, not the agent.
- Recursion guard: sub-agents must not be able to spawn sub-agents.

### 8.7 Rank 7: Exposed local endpoints (severity: moderate, likelihood: low)

Obsidian REST on `27124`, Ollama on `11434`, any MCP HTTP transport, Pipecat's
dev server. **Bind everything to `127.0.0.1`.** If you need remote access, use
Tailscale — never a port forward. Public-instance leakage is exactly how the
OpenClaw credential dumps happened.

---

## 9. THE BUILD

### 9.1 Exact install list, in order

**Everything below runs on the Windows PC unless noted. Do phase N before N+1.**

**Phase 0 — harden what exists (30 min, no downloads)**
```bash
# in the repo
printf '.env\n*.key\n*.pem\n*.log\nJARVIS/quarantine/\n' >> .gitignore
mkdir -p JARVIS/quarantine JARVIS/logs JARVIS/bin
git rm --cached .env 2>/dev/null || true   # if it was ever committed, ROTATE the keys
```
Add a `PreToolUse`/`Stop` hook in `.claude/settings.json` that (a) blocks writes
outside the repo, (b) refuses commits containing secret-shaped strings, (c) fires
your checkpoint reminder. Use the `update-config` skill for the settings syntax.

**Phase 1 — memory format (1 hour, no downloads)**
- Adopt the typed line format (§3.2) in `DECISIONS.md` / `EXPERIMENTS.md`, add
  `BELIEFS.md`.
- Write `JARVIS/bin/validate_memory.py` — parses every state file, fails on a
  malformed line, fails on a `[FACT]` with `src:none`. Wire it into the hook.
- Write `JARVIS/state/INDEX.md`: one line per file saying what lives there. This
  is your retrieval layer.

**Phase 2 — tools (1–2 hours)**
```powershell
# Python env (Windows)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install MetaTrader5            # Windows x86-64 only; MT5 terminal must be running

# MT5 read-only MCP — clone, READ THE CODE, then install
git clone https://github.com/Cloudmeru/MetaTrader-5-MCP-Server
cd MetaTrader-5-MCP-Server
pip install -e .

# Browser automation (only when you need a persistent session)
npm install -g @playwright/mcp
npx playwright install chromium
```
Register in `.claude/settings.json` (stdio transport). Pin versions. Do **not**
install an order-placing MT5 server. Do **not** install a filesystem MCP server.

**Phase 3 — scheduler, budget, logging (2 hours)**
- Windows Task Scheduler → `JARVIS/bin/run_overnight.ps1`, which calls:
  ```powershell
  claude -p "$(Get-Content JARVIS/state/NEXT_ACTIONS.md -Raw)" `
    --output-format json `
    2>&1 | Tee-Object -FilePath "JARVIS/logs/$(Get-Date -f yyyy-MM-dd_HHmm).jsonl"
  ```
  Wrap it with a wall-clock timeout and a spend ceiling read from a config file.
  Kill on breach. Log the reason.
- Every run writes a `RUN_SUMMARY` block: started, ended, tokens, tools called,
  files changed, exit reason. This is the dashboard's data source.

**Phase 4 — dashboard (3 hours)** — see §9.2. Build it against the JSONL logs.

**Phase 5 — voice (a day)**
```powershell
pip install faster-whisper          # STT
pip install kokoro soundfile        # TTS  (also: choco install espeak-ng)
pip install openwakeword            # wake word — includes a "hey jarvis" model
uv tool install "pipecat-ai[cli]"   # pipeline + barge-in
pipecat init quickstart
```
Then write `JARVIS/bin/voice_shaper.py` (§5.5) and
`JARVIS/tests/test_voice_shape.py`. **Write the test first.**

**Phase 6 — local models + optional extras**
```powershell
# Ollama: download installer from ollama.com, then
ollama pull qwen3-coder:30b        # or gpt-oss:20b on 16GB
# bind to localhost only
setx OLLAMA_HOST "127.0.0.1:11434"
```
Optional, only if justified by then:
- Obsidian desktop → Community Plugins → **Local REST API** → enable, copy the
  API key, point a vault at `JARVIS/`. Native MCP at `https://127.0.0.1:27124/mcp/`.
- `uv tool install graphifyy && graphify install` — only if the codebase has
  grown enough that context waste is measurable. Pin the version.
- Google Workspace MCP (`taylorwilsdon/google_workspace_mcp`) — **read-only
  scopes first**, and only after Phase 0's capability separation is real.

**Explicitly NOT on the list:** OmniRoute, OpenClaw, mem0, Letta, Zep,
`windows-mcp-server` (unless in a VM), any order-placing MT5 MCP server, any
vector database.

### 9.2 Dashboard — what actually belongs on it

What the observability tools (Langfuse, LangSmith, AgentOps, Braintrust, Arize
Phoenix) got right, and that you should copy: **the unit of debugging is the
session trace, not the LLM call.** Agent failures live in multi-step causal
chains — the wrong tool at step 4 that only surfaces at step 20. A dashboard of
per-call metrics will not show you that.

Panels worth building, ranked:

1. **Session timeline.** Every run as a horizontal trace: turns, tool calls
   (name, duration, success/fail), sub-agent spawns, retries, compaction events,
   final exit reason. Click a step, see the input and output. This is 80% of the
   value.
2. **Exit-reason histogram.** Completed / hit turn cap / hit budget / crashed /
   blocked by permission. If "hit turn cap" dominates, your tasks are too big.
   This one number tells you more about system health than anything else.
3. **Cost and tokens per run, with a burn-rate line against the cap.** Alarm
   before the cap, kill at it.
4. **Tool error rate by tool.** The tool with the highest failure rate is
   usually a bad *description*, not a bad tool — Anthropic's own reported win was
   a tool-testing agent that rewrote flawed tool descriptions and cut task time
   ~40%.
5. **Memory diff.** What did `DECISIONS.md` / `BELIEFS.md` gain or lose
   overnight? Any `[FACT]` written without a `src:`? Any assumption past its
   expiry? This is the one panel generic tools don't have and you specifically
   need.
6. **Verification status.** Did `test_engine.py` pass on the current HEAD? Red or
   green, big, at the top. If it is red, every number on the page is meaningless
   — say so on the page.
7. **Open questions / blocked-on-human queue.** What is JARVIS waiting for you to
   decide? This is what makes it feel like an operating system rather than a
   script.

Do **not** put a chat window on the dashboard. You have a chat window.

**Build vs buy:** for a personal system, build it. A static HTML page rendered
from the JSONL logs by a Python script is a couple of hours and has zero
dependencies. **Self-host Langfuse** (Postgres + ClickHouse, framework-agnostic,
OpenTelemetry-based) only if you later want retention, search, and eval scoring
across months. Emit **OpenTelemetry GenAI-convention spans** from day one either
way — it costs nothing now and means you can point any backend at it later.

### 9.3 Phased build order — the one-line version

| Phase | Build | Why here |
|---|---|---|
| 0 | Hooks, gitignore, quarantine dir, kill switch | Cheapest risk reduction available |
| 1 | Typed memory + validator + INDEX.md | Everything downstream reads this |
| 2 | MT5 read-only MCP, Playwright, sub-agent tool allowlists | Capability, safely scoped |
| 3 | Scheduler + budget cap + JSONL run logs | Makes overnight work possible *and* survivable |
| 4 | Dashboard over the logs | You cannot improve what you cannot see |
| 5 | Voice: shaper + test first, then pipeline | Highest delight, lowest capability |
| 6 | Ollama, Obsidian, Graphify (optional) | Optimisations, not foundations |

**The thing to resist:** building voice first. It is the most fun and it makes
the least difference. A JARVIS that silently produces a correct overnight
research report is worth more than one that says "Good morning, sir" and is
wrong.

---

## 10. SOURCES

**Agent architecture**
- Cognition — *Don't Build Multi-Agents*: https://cognition.com/blog/dont-build-multi-agents
- Cognition/Walden Yan follow-up (one main loop carries state; stateless subagents): https://x.com/walden_yan/status/2047054554433462360
- Anthropic Engineering — *How we built our multi-agent research system*: https://www.anthropic.com/engineering/multi-agent-research-system
- Anthropic Engineering — *Building Effective AI Agents*: https://www.anthropic.com/engineering/building-effective-agents
- LangChain — *How and when to build multi-agent systems*: https://www.langchain.com/blog/how-and-when-to-build-multi-agent-systems
- *Why Do Multi-Agent LLM Systems Fail?* (MAST, NeurIPS 2025): https://arxiv.org/abs/2503.13657 · https://neurips.cc/virtual/2025/poster/121528
- Token-spend analysis of Anthropic's results: https://whitepapers.gravity7.com/notes/multi-agent-research-performance-is-primarily-a-token-spending-function-token-us/
- Multi-agent cost compounding: https://www.augmentcode.com/guides/multi-agent-cost-compounding

**Context engineering / memory**
- Claude Code subagents (context isolation, frontmatter, tool allowlists): https://code.claude.com/docs/en/sub-agents
- Claude Cookbook — context engineering: memory, compaction, tool clearing: https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools
- LangChain — Context engineering for agents: https://www.langchain.com/blog/context-engineering-for-agents
- *Context Engineering 2.0*: https://arxiv.org/pdf/2510.26493
- Anthropic memory tool walkthrough: https://www.leoniemonigatti.com/blog/claude-memory-tool.html
- Anthropic managed-agents memory: https://usewire.io/blog/anthropic-managed-agents-memory-context-engineering/
- Long context vs RAG (2026): https://truestandard.ai/blog/long-context-vs-rag-2026 · https://www.sitepoint.com/long-context-vs-rag-1m-token-windows/
- *LongRAG*: https://arxiv.org/pdf/2406.15319
- Agent memory framework survey: https://www.graphlit.com/blog/survey-of-ai-agent-memory-frameworks
- Mem0 / Zep / Letta comparisons + LOCOMO dispute: https://aiworkflowlab.dev/article/agent-memory-mem0-vs-letta-vs-zep-2026 · https://www.developersdigest.tech/blog/best-ai-agent-memory-providers-2026
- Graphiti (Zep OSS temporal KG): https://github.com/getzep/graphiti · https://help.getzep.com/graphiti/getting-started/welcome
- Graphify: https://github.com/Graphify-Labs/graphify · https://pypi.org/project/graphifyy/ · https://graphifyai.net/
- Obsidian Local REST API (native MCP since v5): https://github.com/coddingtonbear/obsidian-local-rest-api
- Obsidian MCP setup guide: https://mcp.directory/blog/obsidian-mcp-complete-guide-2026

**Verification / self-critique**
- *LLMs Cannot Self-Correct Reasoning Yet* (DeepMind): https://arxiv.org/abs/2310.01798
- *CRITICTOOL* (self-critique in tool-call errors): https://arxiv.org/pdf/2506.13977
- *Cross-Context Review* (separate production and review sessions): https://arxiv.org/pdf/2603.12123
- *The Verification Horizon: No Silver Bullet for Coding Agent Rewards*: https://arxiv.org/pdf/2606.26300
- *Who Verifies the Agents?* NeurIPS 2026 workshop: https://verify-agents-workshop.github.io/
- Verification loop pattern: https://aipatternbook.com/verification-loop

**Tools / MCP**
- Official MCP registry: https://registry.modelcontextprotocol.io/
- MCP reference servers: https://modelcontextprotocol.io/examples · https://github.com/modelcontextprotocol/servers
- MT5 read-only MCP: https://github.com/Cloudmeru/MetaTrader-5-MCP-Server
- MT5 full-trading MCP (776 stars, no read-only mode): https://github.com/ariadng/metatrader-mcp-server
- MetaTrader5 PyPI (Windows-only wheels): https://pypi.org/project/MetaTrader5 · https://pypi.org/project/mt5linux
- MQL5 — connecting AI agents to MT5 via MCP: https://www.mql5.com/en/articles/21905
- Browser automation reliability comparison: https://www.digitalapplied.com/blog/browser-automation-ai-agents-playwright-stagehand-2026
- MCP vs CLI token benchmark (~114k vs ~27k): https://www.ytyng.com/en/blog/ai-browser-automation-tools-comparison-2026
- Windows UIA MCP server: https://github.com/deploymenttheory/windows-mcp-server · https://mcp.directory/blog/windows-mcp-guide
- MCP accessibility-tree standardization: https://arxiv.org/abs/2608.24898
- Google Workspace MCP: https://github.com/taylorwilsdon/google_workspace_mcp · https://developers.google.com/workspace/guides/configure-mcp-servers

**Voice**
- LiveKit prompting guide for voice agents: https://docs.livekit.io/agents/start/prompting/
- Vapi voice AI prompting guide: https://docs.vapi.ai/prompting-guide
- Pipecat: https://github.com/pipecat-ai/pipecat
- Wyoming protocol + satellite: https://github.com/OHF-Voice/wyoming · https://github.com/rhasspy/wyoming-satellite
- Home Assistant on wake words: https://www.home-assistant.io/voice_control/about_wake_word/
- openWakeWord: https://github.com/dscripka/openWakeWord
- Picovoice Porcupine: https://picovoice.ai/platform/porcupine/ · https://picovoice.ai/blog/complete-guide-to-wake-word/
- Kokoro TTS: https://github.com/thewh1teagle/kokoro-onnx · https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX
- TTS latency benchmarks (TTFA vs TTFB): https://gradium.ai/content/tts-latency-benchmark-2026
- STT benchmarks: https://www.coval.ai/blog/best-speech-to-text-providers-in-2026-independent-benchmarks-and-how-to-choose/ · https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks
- Parakeet vs Whisper: https://snailtext.app/blog/whisper-vs-parakeet-tdt/
- whisper.cpp vs faster-whisper: https://www.promptquorum.com/power-local-llm/local-whisper-stt-comparison-2026
- Voice agent latency architecture: https://qubittool.com/blog/voice-conversation-ai-agent-latency-architecture

**Routing / local models**
- OmniRoute: https://github.com/pitbaden/omniroute
- Ollama model rankings by VRAM: https://www.morphllm.com/best-ollama-models · https://www.promptquorum.com/local-llms

**Orchestration / scheduling**
- Claude Code headless mode: https://amux.io/guides/claude-code-headless/
- Durable execution for agents (Temporal / Inngest / DBOS / Restate): https://www.reactify-solutions.com/articles/durable-ai-agents-2026 · https://www.inngest.com/blog/durable-execution-key-to-harnessing-ai-agents
- Agent budget guardrails and runaway-cost incidents: https://blog.alephant.io/10-real-time-ai-api-budget-guardrails-for-2026/ · https://waxell.ai/blog/ai-agent-token-budget-enforcement

**Dashboard / observability**
- Langfuse: https://langfuse.com/blog/2024-07-ai-agent-observability-with-langfuse
- Platform comparisons: https://latitude.so/blog/best-ai-agent-observability-tools-2026-comparison · https://www.digitalapplied.com/blog/agent-observability-platforms-langsmith-langfuse-arize-2026

**Security**
- CaMeL / dual-LLM: https://simonwillison.net/2025/Apr/11/camel/ · https://css.csail.mit.edu/6.5660/2026/readings/camel.pdf
- *Design Patterns for Securing LLM Agents against Prompt Injections*: https://arxiv.org/abs/2506.08837
- MCP tool poisoning (Invariant Labs): https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks
- State of MCP security 2026 (Microsoft): https://techcommunity.microsoft.com/blog/microsoft-security-blog/the-state-of-mcp-security-in-2026/4531327
- *ETDI* (tool squatting / rug pulls): https://arxiv.org/pdf/2506.01333
- OpenClaw security record: https://blogs.cisco.com/ai/personal-ai-agents-like-openclaw-are-a-security-nightmare · https://www.theregister.com/2026/02/03/openclaw_security_problems/ · https://www.oasis.security/blog/openclaw-vulnerability · https://www.securityweek.com/openclaw-security-issues-continue-as-secureclaw-open-source-tool-debuts/
- Secrets management: https://www.1password.dev/get-started/secure-ai-access · https://paulocurado.com/blog/managing-secrets-with-sops-age-and-1password/

---

## 11. Caveats on this document

- **Several primary sources could not be fetched directly** from this
  environment (anthropic.com, cognition.com, langchain.com, arxiv.org,
  simonwillison.net are all blocked by the egress proxy). Their content here
  comes from search-result summaries and secondary write-ups. **The specific
  numbers attributed to Anthropic (15x tokens, 90.2%, 80% variance, ~40% tool
  improvement) and to MAST (14 modes, 1,642 traces, κ=0.88) should be verified
  against the primary sources before being quoted anywhere that matters.**
- **All performance numbers in §5 (TTS/STT latency and WER) are vendor or
  third-party benchmark figures**, several from parties with a commercial
  interest. They are directionally useful for shortlisting and should not be
  treated as measurements. Measure on your own hardware before committing.
- **Star counts and adoption figures were read from repo pages at time of
  writing** and are inconsistent across secondary sources for Graphify
  specifically — treat that project's popularity claims as unverified.
- Per this project's standing rules: **nothing in this document is a computed
  result of this system**, and no architecture here is CONFIRMED. It is
  research input to a design decision, and should be recorded in
  `DECISIONS.md` only once you have actually decided.

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


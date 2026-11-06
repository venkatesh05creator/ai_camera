# GitHub Research — JARVIS-style Assistant Feature Survey

**Repo:** Aegis AI (venkatesh05creator/ai_camera)  
**Branch:** `cleanup/prune` (Phase 3B research)  
**Date:** 2026-11-06  
**Goal:** Learn from open-source JARVIS-style assistants and transplant the best ideas into Aegis AI without weakening its privacy/security model.

---

## Method

Searched GitHub for repos matching topics: `jarvis`, `ai-assistant`, `voice-assistant`, `mcp`, `agentic`, `surveillance`, `computer-vision`.  
Started from the six named seeds: PanPenek/JarvisAi, adirangel/JARVIS, KofTwentyTwo/Jarvis, rexper101/jarvis, sujankim/jarvis-ai-platform, Ali120B/jarvis.

Each repo was fetched and recorded: licence, architecture, standout features, implementation approach, and estimated cost to add to Aegis. Features were then scored on:
- **Value** — usefulness to a camera-assistant owner (1–5)
- **Effort** — effort to reimplement in our FastAPI/Python architecture (1–5, 1 = low)
- **Privacy/security risk** — risk to the owner-only/consent/grounding model (1–5, 1 = low)

**Licence rule:** copy code only if MIT or Apache-2.0, with attribution in `THIRD_PARTY_NOTICES`. Never copy GPL or unlicensed code; reimplement the idea instead.

---

## Repo shortlist

| # | Repo | Licence | Stars | Primary language / stack | Summary |
|---|------|---------|-------|--------------------------|---------|
| R1 | sujankim/jarvis-ai-platform | Apache-2.0 | 19 | Java 21, Spring Boot 4, Spring AI 2.0, Ollama, PostgreSQL+pgvector, Redis | Local-first modular AI orchestration platform; pgvector long-term memory, RAG, MCP tool runtime, Whisper/TTS voice, ReACT agent system, `doctor`/`benchmark-latency` commands |
| R2 | isair/jarvis | Non-commercial (custom) | 2.2k | Python desktop app, Ollama / OpenAI-compatible | Private local AI assistant; voice + text chat, personal memory (diary + knowledge graph), dictation hotkey, MCP tool integrations, local redaction before model context |
| R3 | PanPenek/JarvisAi | MIT | 24 | Python, FastAPI, openWakeWord, faster-whisper, Kokoro TTS, Ollama, SQLite+ChromaDB | Wake word ("Hey Jarvis"), screen vision (OCR), 31 desktop tools, Iron Man HUD web UI, persistent memory, agentic tool chaining (up to 15 sequential calls) |
| R4 | adirangel/JARVIS | MIT | 2 | Python, Gemini Live (native audio WebSocket), Tkinter HUD, SQLite+ChromaDB | Real-time voice via Gemini 2.5 Flash Live, 30+ tools (apps, web, files, code, agents), forever memory (2-stage fact extraction), autonomous background agents, self-evolving skills, purchase-approval guard |
| R5 | KofTwentyTwo/Jarvis | MIT | 3 | Swift (SPM packages), Ollama/Claude, openWakeWord, Silero VAD, sqlite-vec, MCP, React Three Fiber HUD | macOS menu-bar assistant; boot-health probes (8 probes, ok→soft→loud→critical), 18 boundary-gate linters, typed JSON Bus, per-turn replay/audit log, memory (SQLite+FTS5+sqlite-vec) |
| R6 | rexper101/jarvis | — | — | — | **404** — repo not found at this path |
| R7 | Ali120B/jarvis | — | — | — | **404** — repo not found at this path |

---

## Per-repo findings

### R1 — sujankim/jarvis-ai-platform (Apache-2.0)

**Architecture:** Java/Spring Boot backend with Spring Shell CLI, Spring AI provider router (Ollama primary, Gemini fallback), pgvector long-term memory, RAG document pipeline, MCP tool server, ReACT agent orchestrator, Redis session cache. Phased releases (v0.1–v0.6).

**Standout features relevant to Aegis:**
- Long-term vector memory (pgvector) with memory extraction/injection and CLI `memory list/add/delete`
- `doctor` and `benchmark-latency` commands for honest startup health + latency diagnostics
- Provider abstraction (local Ollama + cloud fallback) — mirrors our `OWNERAI_AI_PROVIDER=offline|openai_compatible`
- MCP tool runtime so new tools plug in through a validated interface
- ReACT agent system for multi-step task execution

**Implementation approach:** provider router, vector memory store, tool registry with MCP, agent planner/executor.

**Cost to add to Aegis:** Medium. Reimplement memory + provider abstraction + doctor/benchmark in Python/FastAPI behind feature flags. Code is Apache-2.0 (permissive) → can copy with attribution.

**Score:** Value 5 / Effort 3 / Privacy risk 2

---

### R2 — isair/jarvis (Non-commercial custom licence)

**Note:** Licence is **non-commercial** (free for personal use; commercial requires separate licence). Per our rule we may **reimplement ideas but not copy code**.

**Architecture:** Python desktop application; local model server (Ollama or OpenAI-compatible); local file access limited to home directory; conversation memory stored locally under `~/.local/share/jarvis`; sensitive info redacted before model context and saved diary.

**Standout features relevant to Aegis:**
- Voice + text chat sharing one conversation + memory
- Dictation hotkey (hold to record, release to paste)
- MCP servers for browser automation, Home Assistant, GitHub, databases
- Local redaction before model context
- Rolling transcript so assistant can join an ongoing conversation

**Cost to add to Aegis:** Low–Medium for *ideas* (cannot copy code). Wake-word/dictation and local redaction patterns are worth reimplementing.

**Score:** Value 4 / Effort 3 / Privacy risk 1 (local-by-default; redaction is a *positive* pattern)

---

### R3 — PanPenek/JarvisAi (MIT)

**Architecture:** Python FastAPI web UI + WebSocket event bus; pipeline Wake word (openWakeWord) → STT (faster-whisper) → LLM (Ollama/OpenAI-compatible) → Tool Router (31 tools) → TTS (Kokoro); memory SQLite+ChromaDB.

**Standout features relevant to Aegis:**
- Wake word "Hey Jarvis" with stop/interrupt ("Stop", "Cancel", "Shut up", Esc)
- Screen vision / OCR (`read_screen`, `find_on_screen`, `click_at`) — *relevant to privacy zones / blur discussion but must not identify strangers*
- Iron Man HUD web UI with real-time tool execution panel and event feed
- Agentic tool chaining (up to 15 sequential tool calls)
- Persistent memory (SQLite + ChromaDB semantic search)

**Cost to add to Aegis:** Low–Medium. Wake word + local STT/TTS are MIT (permissive) → copy with attribution. Screen-vision tools conflict with Principle 1 (never identify strangers) → adapt only as blur/zone primitives, not identification.

**Score:** Value 4 / Effort 2 / Privacy risk 3 (screen vision / desktop control is the highest-risk category; must be gated behind owner confirmation and never identify non-enrolled people)

---

### R4 — adirangel/JARVIS (MIT)

**Architecture:** Python single-file-ish entry (`main.py`) + Tkinter Iron Man HUD; Gemini 2.5 Flash native-audio WebSocket (4 concurrent async tasks: listen/send/receive/play); tool registry + dispatcher; memory manager with 2-stage fact extraction; autonomous agent manager; skill loader (importlib) for self-evolution.

**Standout features relevant to Aegis:**
- Purchase protection — financial transactions require explicit user approval (`purchase_approval` tool) — directly relevant to Principle 4 (state-changing actions need owner confirmation)
- Command blocklist + PowerShell injection prevention + file path validation — good patterns for our SafeToolRegistry
- Forever memory: SQLite facts/messages/profile + ChromaDB vector search, with recency/access boosting
- Autonomous agents (command, script, monitor, autonomous, research, tool, multi-step) with persisted state
- Self-evolving skills (create/install skills from GitHub or SKILL.md) — *do not adopt: runtime self-installing skills from the internet is explicitly prohibited*

**Cost to add to Aegis:** Medium. MIT (permissive) → copy tool-confirmation and blocklist patterns with attribution. Autonomous agents and self-installing skills are out of scope / prohibited.

**Score:** Value 4 / Effort 3 / Privacy risk 2 (purchase/confirmation pattern lowers risk; self-install skills prohibited)

---

### R5 — KofTwentyTwo/Jarvis (MIT)

**Architecture:** macOS Swift host (14 SPM packages, one per subsystem) + WKWebView React Three Fiber HUD; typed JSON Bus as the only Swift↔JS channel; MCP runtime; local voice (openWakeWord + Silero VAD + STT/TTS); memory (SQLite + FTS5 + sqlite-vec).

**Standout features relevant to Aegis:**
- **Boot-health probes:** 8 probes on strict-mode escalation ladder (ok → soft → loud → critical); `.unknown(reason:)` is honest absence; a probe never returns `.ok` when the dependency is broken. Critical failures turn menu-bar red + non-dismissible banner + degrade agent system prompt. Directly relevant to Phase 3 item #5 (camera tamper & health detection).
- **18 boundary-gate linters** — architectural invariants the type system can't catch (single-writer state, no rogue `evaluateJavaScript`, pinned embedding dim, install order, …) — relevant to our lint/bandit/pip-audit gates.
- **Per-turn replay/audit log** — user input, LLM output, tool calls, tool results — relevant to Phase 3B "replay/audit log of every assistant turn".
- Memory: mem0-style ADD/UPDATE/NOOP extraction on Qwen 2.5-Coder + sqlite-vec.

**Cost to add to Aegis:** Medium. MIT (permissive) → copy boot-health probe pattern + boundary-gate idea with attribution. Reimplement in Python (ruff/bandit already cover some of this).

**Score:** Value 5 / Effort 3 / Privacy risk 1 (health probes are observability, not identification — low risk)

---

## Ranked feature list (for your pick)

| Rank | Feature | Source repo | Licence | Value | Effort | Privacy risk | Aegis phase mapping | Copy code? |
|------|---------|-------------|---------|-------|--------|--------------|---------------------|------------|
| 1 | Camera tamper & health boot-probes (lens covered, blur, low light, frozen stream; honest `.unknown`; critical → notification) | R5 KofTwentyTwo | MIT | 5 | 3 | 1 | Phase 3 item #5 | Yes (MIT) + attribution |
| 2 | Learned "normal" baseline / long-term vector memory of events + preferences with owner view/delete | R1 sujankim | Apache-2.0 | 5 | 3 | 2 | Phase 3 item #2 | Yes (Apache-2.0) + attribution |
| 3 | Wake word + local STT/TTS ("Hey Jarvis", stop/interrupt, Kokoro/Whisper-style) | R3 PanPenek | MIT | 4 | 2 | 3 | Phase 3B voice idea | Yes (MIT) + attribution |
| 4 | Per-turn replay/audit log (question, intent, tools called, evidence used, answer) | R5 KofTwentyTwo | MIT | 4 | 2 | 1 | Phase 3B memory idea | Yes (MIT) + attribution |
| 5 | Explicit owner-confirmation guard for state-changing / mutating tools + command blocklist | R4 adirangel | MIT | 4 | 3 | 2 | Principle 4 (SafeToolRegistry) | Yes (MIT) + attribution |
| 6 | Provider abstraction + `doctor`/`benchmark-latency` commands | R1 sujankim | Apache-2.0 | 3 | 2 | 1 | Phase 3B provider/doctor idea | Yes (Apache-2.0) + attribution |
| 7 | MCP tool runtime for pluggable validated tools | R1/R2/R5 | Apache-2.0 / custom / MIT | 3 | 3 | 2 | Phase 3B MCP idea | Yes (where MIT/Apache) + attribution |
| 8 | Self-evolving / self-installing skills from the internet | R4 adirangel | MIT | 2 | 4 | 5 | — | **No** (prohibited by master prompt) |
| 9 | Unrestricted desktop control / screen vision identification | R3 PanPenek | MIT | 2 | 3 | 5 | — | **No** (violates Principle 1) |

**Not adoptable (per master prompt):** runtime self-installing skills from the internet (R4), unrestricted desktop control / identifying non-enrolled people (R3 screen vision), auto-purchases (R4 purchase flows — the *confirmation guard* is adoptable, the *purchase action* is not).

---

## Recommended first transplants

Given the Definition of Done (each feature needs tests + feature flag, lint/bandit/pip-audit clean), the lowest-risk, highest-value starters are:

1. **Camera tamper & health detection (R5 boot-probes)** — Phase 3 item #5. Observability only, never identifies anyone. Maps cleanly to a `CameraHealthService` behind a feature flag with tamper/health tests.
2. **Learned normal baseline + vector memory (R1)** — Phase 3 item #2. Builds on stored events only (metadata), respects consent, owner view/delete.
3. **Wake word + local STT/TTS (R3)** — Phase 3B voice idea. MIT; gate behind feature flag; never used to identify strangers.

---

## WAITING FOR YOUR PICK

Per the master prompt: *"Score every feature on: value to a camera-assistant owner, effort, and risk to privacy/security. Present the ranked list and WAIT for my pick."*

**Please tell me which feature(s) you want me to implement first.** For each approved feature I will:
- Reimplement it in our FastAPI/Python (ownerai) architecture behind a feature flag
- Route any state-changing action through `SafeToolRegistry` with explicit owner confirmation
- Respect consent and grounding rules
- Add tests (including negative security/privacy tests)
- Add attribution to `THIRD_PARTY_NOTICES` if code is copied (MIT/Apache-2.0 only)

Reply with the rank number(s) or feature name(s) you want built, and I'll proceed.

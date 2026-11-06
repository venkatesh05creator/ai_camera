# OpenJarvis Study Notes — Aegis AI Phase O

**Source:** open-jarvis/OpenJarvis (GitHub), Apache-2.0 license  
**Homepage:** https://openjarvis.stanford.edu/  
**Docs:** https://open-jarvis.github.io/OpenJarvis/  
**Paper:** arXiv:2605.17172 "OpenJarvis: Personal AI, On Personal Devices" (Stanford Hazy Research / Scaling Intelligence Lab)  
**Stars:** 13.5k | **Forks:** 3.2k | **Commits:** 1,307  
**Studied:** 2026-11-06

---

## 1. Overview

OpenJarvis is a research framework for **composable, on-device AI systems**. Three core ideas:
1. **Shared primitives** for building on-device agents (exchangeable layers).
2. **Evaluations** that treat energy, FLOPs, latency, and dollar cost as first-class constraints alongside accuracy.
3. **A learning loop** that improves models/prompts/agent behavior from local trace data.

Goal: personal AI agents that run locally by default, calling the cloud only when truly necessary.

---

## 2. The Five Primitives

OpenJarvis is built around five composable layers, each with a clean interface and swappable independently:

| Primitive | What it does | OpenJarvis implementation |
|-----------|--------------|---------------------------|
| **1. Intelligence** | Pick a model, or let the system pick one for your hardware. Manages the full catalog of local models across providers. | `openjarvis.intelligence.model_catalog` |
| **2. Engine** | The inference runtime: Ollama, vLLM, SGLang, llama.cpp, MLX, Exo, LiteLLM, cloud (OpenAI/Anthropic/Google), and more. Same `InferenceEngine` interface; auto-detects hardware and recommends best fit. | `openjarvis.engine.*` (ollama, litellm, cloud, gemma_cpp, apple_fm, nexa_shim, nim, multi, vllm_pearl, etc.) |
| **3. Agents** | Multi-step reasoning with tool use. Eight built-in agent types from simple chat to orchestrated workflows. | `openjarvis.agents.*` (orchestrator, native_react, operative, monitor_operative, morning_digest, deep_research, code_assistant/native_openhands, simple) |
| **4. Tools & Memory** | Web search, calculator, file I/O, code interpreter, retrieval, persistent local state, and any external MCP server. | `openjarvis.tools.*`, `openjarvis.memory.*`, `openjarvis.mcp.*` |
| **5. Learning** | Every interaction generates traces that drive automatic improvements to model weights, prompts, and agent behavior. | `openjarvis.learning.*` (dspy/gepa/ace optimizers, skill discovery, RL telemetry) |

**Registry pattern** is used throughout so any primitive can be swapped without touching the others.

---

## 3. `jarvis init` — Hardware Detection & Config Presets

`jarvis init --preset <name> --force` replaces config with a starter preset and performs hardware detection:

- Auto-detects GPU vendor, model, and VRAM; recommends the optimal inference engine for the hardware.
- Installs uv, the Python venv, Ollama, and a starter model (~3 minutes on broadband).
- The Rust extension and larger models download in the background; `jarvis doctor` shows status.

**Presets:**
| Preset | Purpose |
|--------|---------|
| `morning-digest-mac` / `morning-digest-linux` / `morning-digest-minimal` | Spoken daily briefing from email, calendar, health, news |
| `deep-research` | Multi-hop research across indexed docs with citations |
| `code-assistant` | Agent with code execution, file I/O, shell access |
| `scheduled-monitor` | Stateful agent on a schedule with memory |
| `chat-simple` | Lightweight conversation, no tools |

Connection example: `jarvis connect gdrive` (one OAuth covers Gmail/Calendar/Tasks); `jarvis digest --fresh` generates and plays the first briefing.

---

## 4. `jarvis doctor`

Honest startup health probe: reports the status of engine, model, database, disk, keys, and permissions. The Rust extension and larger models download in the background while `jarvis doctor` shows real-time status. This is the model for an "honest startup health probe that never fakes a healthy result."

---

## 5. Scheduled Agents

OpenJarvis ships eight built-in agents across three execution modes (on-demand, scheduled, continuous):

| Agent | Mode | What it does |
|-------|------|--------------|
| `morning_digest` | Scheduled | Daily briefing from email, calendar, health, news — with TTS audio |
| `deep_research` | On-demand | Multi-hop research with citations across web and local docs |
| `monitor_operative` | Continuous | Long-horizon monitoring with memory, compression, retrieval |
| `orchestrator` | On-demand | Multi-turn reasoning with automatic tool selection |
| `native_react` | On-demand | ReAct (Thought-Action-Observation) loop |
| `operative` | Continuous | Persistent autonomous agent with state management |
| `native_openhands` | On-demand | CodeAct — generates and executes Python code |
| `simple` | On-demand | Single-turn chat, no tools |

Cron-based agents monitor, summarize, and act (code review, email triage, research digests) running 24/7 on local hardware.

---

## 6. Skills Format (agentskills.io)

Skills teach agents how to use tools and improve reasoning. **Every skill is a tool** — agents discover them from a catalog and invoke on demand.

- Open standard: https://agentskills.io/specification
- Install: `jarvis skill install hermes:arxiv`; sync: `jarvis skill sync hermes --category research`
- Use: `jarvis ask "Use the code-explainer skill to explain this Python code: ..."`
- Optimize from trace history: `jarvis optimize skills --policy dspy`
- Benchmark impact: `jarvis bench skills --max-samples 5 --seeds 42`
- Import from Hermes Agent (~150 skills), OpenClaw (~13,700 community skills), or any GitHub repo.

Skill tool_adapter / tool_translator layers map skill schemas to the agent's tool contract.

---

## 7. Trace Logging

Every assistant interaction generates a **trace** (question, intent, tools called, evidence, answer, latency, tokens). Traces are stored locally and drive the learning loop:
- `openjarvis.evals.core.trace`, `event_recorder`, `tracker`
- `openjarvis.analytics.events`, `identity`, `redaction` (PII stripped before storage)
- `openjarvis.telemetry.session`, `energy_monitor`, `gpu_monitor`

Traces feed automatic skill optimization (`jarvis optimize skills`) and model/prompt improvement.

---

## 8. Evaluation (latency, energy, cost alongside accuracy)

OpenJarvis treats energy, FLOPs, latency, and dollar cost as **first-class constraints alongside accuracy**:

- `openjarvis.bench.energy`, `bench.latency`, `bench.throughput`
- `openjarvis.telemetry.energy_monitor`, `energy_nvidia`, `energy_apple`, `energy_amd`, `energy_rapl` (GPU power draw per vendor)
- `openjarvis.telemetry.flops`, `gpu_monitor`, `instrumented_engine`
- Cost calculator (`openjarvis.server.cost_calculator`, `savings`)
- Trackers: `sheets_tracker`, `wandb_tracker`
- Eval backends: `jarvis_agent`, `jarvis_direct`, `tb_agent`, `terminalbench`, `swebench`, `gaia`, `simpleqa`, `morning_brief`, etc.
- `jarvis bench skills`, `jarvis eval`, `jarvis telemetry`

---

## 9. Security-Relevant Building Blocks (for Aegis)

OpenJarvis includes a `openjarvis.security.*` package directly relevant to Aegis AI:
- `credential_stripper`, `injection_scanner`, `rate_limiter`, `ssrf`, `subprocess_sandbox`, `taint`, `guardrails`, `audit`, `boundary`, `capabilities`, `file_policy`, `scanner`, `severity_policy`, `signing`, `runtime`

Many are Apache-2.0 and could be adapted (with attribution) into Aegis AI's SafeToolRegistry and prompt-injection defenses.

---

## 10. Licence

**Apache-2.0** — permissive. Code may be copied into Aegis AI with attribution in `THIRD_PARTY_NOTICES`. No GPL, no copyleft.

---

## 11. Ideas Worth Transplanting to Aegis AI

| # | Idea | OpenJarvis basis | Aegis mapping | Value | Effort | Privacy risk |
|---|------|------------------|---------------|-------|--------|--------------|
| O-1 | `aegis doctor` command — real checks for camera, model, DB, disk, keys, permissions | `jarvis doctor` (honest status, never fakes healthy) | Extend existing `DOCTOR` feature flag | 5 | 2 | 1 |
| O-2 | Overnight security briefing agent — spoken + written summary from stored events | `morning_digest` scheduled agent | New feature flag; read-only; Gmail/Calendar only if owner opts in with read-only OAuth | 4 | 4 | 3 |
| O-3 | Engine auto-detect + switch — local (Ollama) first, cloud optional, visible indicator of which answered | Engine primitive auto-detects hardware; provider abstraction | Extend existing `OFFLINE_FIRST` + provider switcher | 4 | 2 | 1 |
| O-4 | Trace log of every JARVIS turn + offline eval harness measuring grounding accuracy & hallucinated detections | `Learning` primitive + `evals` with latency/energy/cost tracking | Extend `REPLAY_LOG` + add eval harness behind flag | 5 | 4 | 1 |
| O-5 | Skills format for Aegis tools — new tools declared in one validated file | `agentskills.io` + skill tool_adapter/translator | New `AEGIS_SKILLS` flag; validated skill manifest; no auto-install from internet | 3 | 4 | 4 |

**Not adopted:** Runtime self-installing skills from the internet (prohibited by master prompt); any cloud-only dependency as default; sending traces to third parties.

---

## 12. Proposed Build Order (ranked)

Per the master prompt, I present this ranked list and **WAIT for your pick** before building:

1. **O-1 `aegis doctor` command** — highest value (5), low effort (2), low risk (1). Directly strengthens honest health reporting.
2. **O-4 Trace log + offline eval harness** — highest value (5), higher effort (4), low risk (1). Strengthens grounding/hallucination detection (part of Definition of Done).
3. **O-3 Engine auto-detect + switch** — value (4), low effort (2), low risk (1). Improves offline-first transparency.
4. **O-2 Overnight security briefing agent** — value (4), higher effort (4), medium risk (3) — needs careful consent gating.
5. **O-5 Skills format** — value (3), higher effort (4), medium-high risk (4) — must not allow auto-install from internet.

**WAITING FOR YOUR PICK.** Tell me which O-candidate(s) to build (or "none"), and I'll implement the chosen one(s) behind a feature flag with tests, then proceed to Phase W (World Monitor) and Phase UX (loading/empty states).

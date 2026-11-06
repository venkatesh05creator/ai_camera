# Phase 1 — Brief Plan (redesign-v2)

## 1. Architecture & stack (one-line reasons)

| Piece | Choice | Why (one line) |
|---|---|---|
| Backend | **FastAPI** (async Python) | one language for API + vision, async camera streams |
| Database | **SQLite + Alembic** | single-owner app, zero server ops, easy encrypted backups |
| Frontend | **React + TypeScript + Vite + Tailwind PWA** | installable phone-as-camera PWA, mobile-first, one shell |
| Vision | **OpenCV + YOLOv8n-class (ONNX Runtime)** | free, runs CPU, motion-gated so idle CPU ≈ 0 |
| AI brain | **Ollama local-first** (llama3.1:8b / qwen2.5:7b slots) | unlimited quota, offline, private; size chosen after HW answers |
| Cloud fallback | Groq/Gemini/NIM/OpenRouter behind one router + quota meter | free tiers shrink/shift often, so fallback is optional & metered |
| Voice | **faster-whisper** (STT) + **Piper** (TTS), offline | free, local, no audio ever leaves the machine |
| PC control | allow-listed tool executor + per-action verification | open/verify/log/undo pattern, shell off by default |
| Packaging | Docker compose + `start.bat`/`start.sh` | fresh machine running in <10 min |
| CI | GitHub Actions: ruff, mypy, pytest, bandit, pip-audit, gitleaks | every gate runs on every push |

## 2. Folder structure

```
backend/app/{api, core, models, schemas, services, workers, tools}
web/                     # PWA (React)
docs/                    # plan, threat model, phase reports
tests/                   # backend tests (integration-first)
scripts/                 # start scripts, sync helpers
```

## 3. Features

**MVP (Phases 2–4 of the build):** owner account/sessions, streaming chat with evidence badges + verifier, tool allow-list, memory (encrypted, editable, delete/export), camera registry (webcam + phone PWA), motion-gated detection w/ events + encrypted clips, camera health watchdog, honest "camera off / 0 people" answers, notifications.
**Phase 2:** consent enrolment + person log, footage semantic search, automations w/ dry-run, object memory ("where are my keys"), cross-camera "person #12".
**Later:** voice I/O + wake word, Telegram bot, PC control & routines, sports/physics analytics, coding-agent supervisor, public-camera counts, floor-plan view, plugin SDK.

## 4. Free models/services — limits verified today (Nov 2026, each has a live quota meter in-app)

| Service | Free limit (verified) | Role |
|---|---|---|
| Ollama (local) | unlimited | default for everything |
| Groq | ~30 req/min, ~1,000–14,400 req/day (model-dependent) | fast text fallback |
| Gemini | ~1,500 req/day per project, but reports of 20–50/day on some models now | vision caption fallback |
| OpenRouter `:free` | 20 req/min, 50 req/day (1,000/day only after one-time $10) | rare fallback |
| NVIDIA NIM | ~1,000 credits at signup, 5,000 lifetime (~1 credit/call) | last resort only |

Rule: privacy-local content **never** leaves the machine unless you explicitly allow cloud for that request; router degrades honestly ("local model only today").

## 5. THREAT MODEL (every asset has a named mitigation)

| Asset | Threat | Mitigation |
|---|---|---|
| Cameras / streams | SSRF, LAN probing, eavesdropping | URL validator blocking link-local/private ranges unless you allow; loopback bind; per-camera tokens; HMAC-signed ingestion + replay protection |
| Biometric templates | theft/misuse, enrol bypass | AES-256-GCM at rest, separate key, consent gate enforced server-side, delete-on-withdraw |
| API keys (.env) | commit/log leak | only `.env.example` committed, gitleaks in CI, no key ever logged; rotation runbook |
| PC-control tools | malicious command injection | allow-list only, confirmation cards with TTL, sandboxed shell (off by default), audit log + undo |
| LLM | prompt injection (web/frames/Telegram) | untrusted text wrapped + never executed; tool outputs are data; injection test suite per phase |
| Public/official feeds | toS breach, misidentification | counts only, no face recognition, source note per feed, provenance logged |
| Local data (DB, clips) | theft of laptop | encrypted at rest, panic-switch, auto-retention per camera |
| You (owner) | account takeover | Argon2id, session rotation + expiry, lockout, optional TOTP |

## 6. Build risks (plain)

- Model size vs. your hardware — need your specs (Q1 below).
- Free quotas move weekly — router must measure, not assume (design includes it).
- Windows file-lock quirks kill dev servers — scripts will stop stale processes on start.
- Vision stack wants a GPU for.video; CPU-only plan uses motion gating + lower FPS.

## 7. Milestones (what you can test after each)

| M | After phase… | You can test… |
|---|---|---|
| M1 | 2 Secure foundation | create owner, log in, empty honest dashboard; negative-tests green |
| M2 | 3 AI brain | "Summarize my day" with evidence badges; 30-case grounding eval green |
| M3 | 4 Cameras | webcam events metadata-only; camera off → says so |
| M4 | 5 People | "who is at my desk" works, notification arrives |
| M5 | 6 Control/voice | "open YouTube, search X" verified; Telegram locked to you |
| M6 | 7 Sports | calibrated ball speed w/ error margin; uncalibrated → refused |
| M7 | 8+9 | spec→branch supervisor; release checklist + red-team report |

## 8. My 5 questions

1. **CPU / GPU / RAM?** (decides local model: 7B vs 3B, vs CPU-only quantization)
2. **First priority:** desk/camera security alerts, or voice+PC-control JARVIS?
3. **Cameras to start:** laptop webcam? Android phone? Any RTSP/IP camera?
4. **Voice languages:** English only, or English+Hindi/Telugu mix?
5. **Telegram remote control** — MVP or later?

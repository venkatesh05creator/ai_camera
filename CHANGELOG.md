# Changelog

## Unreleased — `cleanup/prune` branch

### Removed
* Deleted `.hintrc` (editor hint config; zero code references)
* Deleted `scripts/smoke_test.py` (no external references; not in README/CI)
* Deleted `scripts/jarvis_voice.py` (no imports; wrapper around root `jarvis_voice.py`)
* Removed dangling `<script src="/static/js/console.js">` from `dashboard.html`
  (file did not exist; caused a 404 on every dashboard load)

### Added (all behind opt-in feature flags; defaults off)

**Camera tamper & health detection** (`OWNERAI_FEATURE_CAMERA_HEALTH`)
* Blur / low-light / lens-tamper / frozen-stream probes on in-memory frames +
  device metadata
* `GET/POST /api/health` endpoints (owner scoped); persists `CameraHealthCheck`
  records; never stores raw frames

**Learned "normal" baseline** (`OWNERAI_FEATURE_LEARNED_BASELINE`)
* Per-camera, hour-of-week baselines learned from stored event metadata
* Deviation detection with z-score and plain-language explanation
* `POST /api/baseline/learn`, `GET /api/baseline/{id}`, `GET /api/baseline/{id}/deviation`

**Per-turn replay/audit log** (`OWNERAI_FEATURE_REPLAY_LOG`)
* `AssistantTurn` log: question, intent, tools called, evidence event IDs, answer
* Recorded automatically on every assistant turn; `GET /api/replay/turns`

**Evidence panel** (`OWNERAI_FEATURE_EVIDENCE_PANEL`)
* Every JARVIS answer links to event IDs, detector output, confidence
* `GET /api/evidence/turns/{id}`, `GET /api/evidence/latest`
* `ChatResponse` now includes `evidence_event_ids`

**Natural-language alert rules** (`OWNERAI_FEATURE_ALERT_RULES`)
* Parses NL (e.g. "someone I haven't enrolled at the door after 11pm") into a
  validated structured rule; owner must confirm before activation
* `POST/GET/DELETE /api/alert-rules`, `POST /api/alert-rules/{id}/confirm`
* Rules referencing unknown cameras are rejected

**Privacy zones + auto-blur** (`OWNERAI_FEATURE_PRIVACY_ZONES`)
* Owner-drawn polygonal privacy zones (never analysed/stored)
* `blur_non_enrolled_faces()` toggle for saved clips
* `POST/GET/DELETE /api/privacy-zones`; `is_in_privacy_zone()` point-in-polygon

**Daily/weekly digest** (`OWNERAI_FEATURE_DIGEST`)
* Narrative summary built only from stored events
* `POST/GET /api/digest` (daily|weekly)

**Time-boxed guest access** (`OWNERAI_FEATURE_GUEST_ACCESS`)
* Temporary enrolment linked to an enrolled identity with automatic expiry
* `POST/GET /api/guest-access`, `GET /api/guest-access/valid/{id}`,
  `POST /api/guest-access/{id}/revoke`

**Offline-first mode** (`OWNERAI_FEATURE_OFFLINE_FIRST`)
* `OfflineProvider` is the default AI provider; no data leaves the machine
  without an explicit server-side API key

**Doctor / benchmark** (`OWNERAI_FEATURE_DOCTOR`)
* Startup health probes: database, disk, model provider, cameras
* Honest ok/soft/loud/critical severity; never fakes a healthy result
* `GET /api/doctor`, `GET /api/doctor/benchmark`

**MCP tool runtime** (`OWNERAI_FEATURE_MCP_RUNTIME`)
* Pluggable tools with JSON-Schema input validation
* Mutating tools require explicit owner confirmation
* `GET /api/mcp/tools`, `POST /api/mcp/tools/{name}/call`

**Wake word** (`OWNERAI_FEATURE_WAKE_WORD`)
* Server-side wake-word session tracking (detection happens client-side;
  no audio stored)
* `POST /api/wake-word/detected`, `GET /api/wake-word/sessions`

**OpenJarvis transplants (Apache-2.0, attributed in THIRD_PARTY_NOTICES)**

**Camera tamper & health boot-probes** (`OWNERAI_FEATURE_DOCTOR`)
* `ownerai services/doctor.py`: database, disk, model, camera probes with honest
  ok/soft/loud/critical severity; never fakes healthy
* `GET /api/doctor`, `GET /api/doctor/benchmark`
* CLI: `python main.py doctor [--benchmark]`

**Offline-first provider auto-detect** (`OWNERAI_FEATURE_DOCTOR`, `ai_auto_detect_engine`)
* Auto-detects a local Ollama engine when no cloud provider configured
* `GET /api/ai/provider` reports active provider + source (local vs configured)

**Learned baseline + per-turn replay/audit log** (`OWNERAI_FEATURE_LEARNED_BASELINE`, `OWNERAI_FEATURE_REPLAY_LOG`)
* Per-camera hour-of-week baselines with z-score deviation alerts
* `AssistantTurn` log: question, intent, tools, evidence IDs, answer
* Recorded automatically on every assistant turn

**Evidence panel** (`OWNERAI_FEATURE_EVIDENCE_PANEL`)
* Every JARVIS answer links to event IDs, detector output, confidence

**Natural-language alert rules** (`OWNERAI_FEATURE_ALERT_RULES`)
* Parses NL into validated rules; owner confirms before activation

**Privacy zones + auto-blur** (`OWNERAI_FEATURE_PRIVACY_ZONES`)
* Owner-drawn polygonal privacy zones (never analysed/stored)
* `blur_non_enrolled_faces()` toggle for saved clips

**Daily/weekly digest** (`OWNERAI_FEATURE_DIGEST`)
* Narrative summary built only from stored events

**Time-boxed guest access** (`OWNERAI_FEATURE_GUEST_ACCESS`)
* Temporary enrolment linked to an enrolled identity with automatic expiry

**Overnight security briefing** (`OWNERAI_FEATURE_SECURITY_BRIEFING`)
* Spoken + written narrative summary of stored events (owner-opted-in for
  external integrations like Gmail/Calendar)
* `GET /api/briefing/security`

**Offline evaluation harness** (`OWNERAI_FEATURE_EVAL_HARNESS`)
* Measures grounding accuracy and hallucinated detections from replay-log turns
* `GET /api/eval/report`

**Skills format** (`OWNERAI_FEATURE_SKILLS_FORMAT`)
* Tools declared in one validated manifest file; loaded through a validated
  interface; mutating skills require owner confirmation; no self-install from
  the internet
* `GET /api/skills`, `POST /api/skills/manifest`

### Changed
* `ownerai/features.py`: new opt-in feature flag registry (all defaults off)
* `ownerai/models.py`: added `CameraHealthCheck`, `ActivityBaseline`, `AlertRule`,
  `PrivacyZone`, `AssistantTurn`, `GuestAccess`, `Digest`
* `ownerai/settings.py`: innovation settings (health thresholds, baseline window,
  alert rule caps, privacy blur, guest TTL, digest limits, doctor disk warn)
* `ownerai/schemas.py`: `HealthCheckOut`, `HealthProbeRequest`,
  `evidence_event_ids` on `ChatResponse`
* `ownerai/routers/chat.py`: captures evidence event IDs; records replay turns

### Documentation
* `README.md` rewritten: correct test count (118), single run command per
  platform, architecture diagram, `ownerai/` identified as the live app
* `SECURITY.md`: added section 11 documenting all innovation feature flags and
  their security notes
* `THIRD_PARTY_NOTICES`: attribution for ideas adapted from surveyed
  JARVIS-style assistants (MIT/Apache-2.0 only)
* `docs/research/github-survey.md`: survey of 4 reachable JARVIS-style repos
  with scored, ranked feature recommendations

### Tests
* 110 new tests across all Phase 3 / Phase 3B innovation features
* Total: 224 passed (was 118); 0 failed

### Not done
* `inputs/` (tracked photos of real people) — not deleted; requires separate
  explicit approval (privacy-sensitive)
* `backend/` duplicate tree — kept; has references, consolidation is a
  judgment call
* `pip-audit` — could not complete (no network access to PyPI in this
  environment)

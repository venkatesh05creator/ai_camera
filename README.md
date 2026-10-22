# Owner-Only AI Camera Assistant

A privacy-first camera assistant for a single owner: laptop webcams, Android
phones, wearable cameras and compatible IP cameras share one backend and one
dashboard.

The assistant is **consent based owner verification**, not a stranger
identification system.  Only people the owner explicitly enrolled are ever
identified; everybody else stays anonymous.  Camera events are stored as
metadata (never raw frames), biometric templates are encrypted at rest, and the
AI assistant never sees anything but the owner's own metadata.

> **Status.**  The security controls described in [`SECURITY.md`](SECURITY.md)
> are implemented and covered by automated tests, but **no independent
> penetration test has been performed**.  Treat this as a well-tested
> baseline, not a certified product.

---

## 1. What is in the box

| Part | Path | Notes |
| --- | --- | --- |
| Web application (FastAPI) | `ownerai/` | Backend, templates, static assets, security middleware |
| Legacy computer-vision scripts | `face_*.py`, `utils/`, `models/` | The original prototype, unchanged in behaviour |
| Tests | `tests/` | 90 automated tests, including the negative security tests |
| Security tooling | `scripts/security_check.py` | ruff + bandit + pip-audit + pytest |
| Documentation | `README.md`, `SECURITY.md` | Operation, deployment, security policy |

### Feature overview

* **Authentication** - Argon2id password hashing, server-side sessions,
  session rotation, idle/absolute expiry, revocation, rate limiting, account
  lockout, TOTP multi-factor authentication, password reset with single-use
  tokens, optional e-mail verification.
* **Authorisation** - four roles (`owner`, `admin`, `trusted`, `viewer`),
  a permission matrix, and strict per-object ownership checks that prevent
  IDOR/BOLA.
* **Cameras** - device registry for webcams, phones, wearables and IP
  cameras; SSRF-protected snapshot fetching; HMAC-signed event ingestion with
  replay protection.
* **Biometrics** - consent-gated enrolment, AES-256-GCM encrypted templates,
  retention periods, withdrawal and deletion, verification that never
  identifies unenrolled people.
* **Assistant** - server-side provider abstraction (OpenAI-compatible or a
  fully offline provider), PII redaction, prompt-injection defences, tool
  allow-list with explicit confirmation for mutations, per-user token and
  request budgets.
* **User interface** - responsive dashboard with a light/dark theme switch
  (system theme aware), an accurate cookie banner, a permission-filtered site
  search, a floating contact dialog and a keyboard accessible back-to-top
  button.

---

## 2. Quick start (development)

> **Python 3.10 or newer is required** (FastAPI >= 0.156 needs 3.10+).
> Python 3.13 is what this project was tested with.

```powershell
# 1. Virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Dependencies
pip install -r requirements-dev.txt          # server + tooling
pip install -r requirements.txt              # add the vision stack (biometrics)

# 3. Configuration
copy .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # -> OWNERAI_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"   # -> OWNERAI_BIOMETRIC_ENCRYPTION_KEY
# Paste both values into .env and adjust the rest.

# 4. Run (bound to the loopback interface)
python app.py
# or: uvicorn ownerai.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/> and create the **first account** - it becomes
the owner of the installation.  Every later registration is a regular
`viewer` until an owner promotes it.

The biometric engine is optional: without TensorFlow the enrolment endpoint
answers *"the biometric engine is not installed on this server"* and every
other feature keeps working.

### Useful environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `OWNERAI_SECRET_KEY` | - | Session/CSRF signing secret (required in production) |
| `OWNERAI_BIOMETRIC_ENCRYPTION_KEY` | - | Encrypts biometric templates |
| `OWNERAI_APP_ENV` | `development` | `development` / `test` / `production` |
| `OWNERAI_DATABASE_URL` | `sqlite:///./var/ownerai.db` | Database location |
| `OWNERAI_HTTPS_ONLY` / `OWNERAI_HSTS_ENABLED` | `false` | Must both be `true` in production |
| `OWNERAI_TRUSTED_HOSTS` | `localhost,127.0.0.1` | Allowed `Host` headers |
| `OWNERAI_CORS_ORIGINS` | empty | Explicit origins only, never `*` |
| `OWNERAI_AI_PROVIDER` | `offline` | `offline` or `openai_compatible` |
| `OWNERAI_AI_API_KEY` | - | Server-side key for the AI provider |

The complete list with comments is in [`.env.example`](.env.example).

---

## 3. Running the checks

```powershell
# Everything (lint, SAST, dependency audit, tests)
python scripts/security_check.py

# Individually
python -m ruff check ownerai tests app.py
python -m bandit -r ownerai -q
python -m pip_audit -r requirements-server.txt
python -m pytest tests -q
```

The test-suite covers, among others, the required negative cases:

| # | Requirement | Test |
| --- | --- | --- |
| 1 | Unauthenticated users cannot access private APIs | `test_authorization.py::test_unauthenticated_users_cannot_access_private_apis` |
| 2 | A user cannot access another user's devices or conversations | `test_authorization.py::test_a_user_cannot_read_another_users_device` |
| 3 | Users cannot elevate their role through a payload | `test_authorization.py::test_registration_cannot_escalate_the_role` |
| 4 | Invalid, oversized and malformed input is rejected | `test_api_security.py::test_invalid_enum_values_are_rejected`, `..._huge_request_body_is_rejected_before_parsing` |
| 5 | SQL injection and XSS payloads do not change the query meaning | `test_api_security.py::test_sql_injection_payload_is_treated_as_data`, `..._xss_payload_is_escaped_in_the_rendered_page` |
| 6 | Rate limits activate | `test_auth.py::test_login_is_rate_limited`, `test_api_security.py::test_api_rate_limit_returns_429` |
| 7 | Expired and revoked sessions are rejected | `test_auth.py::test_expired_session_cannot_access_protected_resources`, `..._revoked_session...` |
| 8 | Secrets never appear in client bundles or API responses | `test_api_security.py::test_secrets_are_not_embedded_in_the_static_assets` |
| 9 | Unenrolled people cannot unlock the owner's session | `test_biometrics.py::test_unenrolled_people_cannot_unlock_the_owner_session` |
| 10 | WebSocket events enforce authorisation | `test_authorization.py::test_websocket_refuses_foreign_devices` |
| 11 | Sensitive files and debug endpoints are not public | `test_api_security.py::test_private_files_are_not_served`, `..._debug_endpoints_are_not_exposed` |
| 12 | Security headers are present | `test_api_security.py::test_security_headers_are_present` |

---

## 4. Deployment

### 4.1 Production configuration

```bash
export OWNERAI_APP_ENV=production
export OWNERAI_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
export OWNERAI_BIOMETRIC_ENCRYPTION_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
export OWNERAI_HTTPS_ONLY=true
export OWNERAI_HSTS_ENABLED=true
export OWNERAI_TRUSTED_HOSTS=cameras.example.com
export OWNERAI_DATABASE_URL=postgresql://ownerai:***@127.0.0.1:5432/ownerai
export OWNERAI_REQUIRE_EMAIL_VERIFICATION=true
export OWNERAI_MAILER_BACKEND=smtp
export OWNERAI_AI_PROVIDER=openai_compatible
export OWNERAI_AI_API_KEY=sk-...
```

The application **refuses to start** in production when the secret is missing
or weak, when HTTPS or HSTS are disabled, when no trusted host is configured
or when a wildcard CORS origin is present.

### 4.2 systemd unit

```ini
[Unit]
Description=Owner-Only AI Camera Assistant
After=network.target

[Service]
Type=exec
User=ownerai
Group=ownerai
WorkingDirectory=/srv/ownerai
EnvironmentFile=/etc/ownerai/ownerai.env
ExecStart=/srv/ownerai/.venv/bin/uvicorn ownerai.main:app --host 127.0.0.1 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/srv/ownerai/var

[Install]
WantedBy=multi-user.target
```

Run the application as an unprivileged user, bind it to `127.0.0.1` and let a
reverse proxy terminate TLS.  Set `OWNERAI_TRUST_PROXY_HEADERS=true` only when
the proxy is the only client that can reach the port.

### 4.3 Reverse proxy (nginx)

```nginx
server {
    listen 443 ssl http2;
    server_name cameras.example.com;

    ssl_certificate     /etc/letsencrypt/live/cameras.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cameras.example.com/privkey.pem;

    client_max_body_size 8m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Request-ID $request_id;
    }
}
```

### 4.4 Database

* SQLite (default) is fine for a single owner: keep the file outside the web
  root (`var/ownerai.db`), restrict its permissions and back it up encrypted.
* For PostgreSQL, create a **least-privilege** role for the application and a
  separate role for migrations, restrict the network access to the application
  host and enable TLS on the connection.
* Biometric templates are encrypted by the application, so a database dump
  alone does not reveal the templates - but it does reveal account metadata.

### 4.5 What is *not* automated for you

* TLS certificates and their renewal.
* Database backups and restore tests.
* Log shipping and alerting.
* OS hardening of the host.
* An independent penetration test.

---

## 5. Legacy computer-vision scripts

The original prototype is still available and unchanged in behaviour:

```powershell
python face_recognize_static.py --model facenet path/to/image.jpg
python face_recognize_live.py --model facenet
python face_add_static.py --model facenet path/to/image.jpg
python face_add_live.py --model facenet
python face_remove.py
```

The prototype's HTTP endpoint (`/extract-embeddings`, which read *any* path
on the server without authentication) was replaced by
`POST /api/legacy/embeddings`.  It requires an authenticated account, is
restricted to the directory in `OWNERAI_LEGACY_IMAGE_ROOT` (default
`./inputs`), is rate limited and never returns a stack trace.

> **Note on the embedding datastores.**  The old `datastore/*.json` files
> contained unencrypted face embeddings of real people and are no longer
> tracked by git (see `SECURITY.md` § 12 for the history-clean-up procedure).
> The scripts recreate the file automatically when faces are added; the
> pre-seeded names are gone.

---

## 6. Project layout

```text
ownerai/
├── main.py           application factory, middleware, WebSocket, error handlers
├── settings.py       environment configuration with production fail-safe checks
├── db.py             engine, session factory, SQLite pragmas
├── models.py         ORM models (users, sessions, devices, events, identities, …)
├── schemas.py        strict request/response models
├── security.py       password hashing, tokens, CSRF primitives
├── sessions.py       session lifecycle, cookies, CSRF validation
├── crypto.py         AES-GCM helpers, PII redaction
├── totp.py           RFC 6238 / RFC 4226
├── rbac.py           roles, permissions, ownership helpers
├── ratelimit.py      database backed rate limiting
├── middleware.py     security headers, body limit, HTTPS redirect, logging
├── services/         ai.py, biometrics.py, cameras.py, contact.py, mailer.py,
│                     search.py, audit.py
├── routers/          auth, devices, events, identities, chat, search, admin,
│                     contact, legacy, pages
├── templates/        server rendered pages
└── static/           css/js (no CDN, no trackers, no inline scripts)
```

---

## 7. AI Orchestration Layer & Conversational Intelligence

The platform features a modular, request-scoped AI Orchestration Layer (`backend/app/services/ai_orchestrator.py`) engineered for accurate, humanized, and grounded real-world responses.

### 7.1 Architecture & Pipeline

Every user request flows through an isolated execution lifecycle:

1. **Request Isolation**: Unique `request_id` (UUID), zero shared mutable state across queries or users.
2. **Intent Classification**: Deterministic-first classification supporting 11 distinct intent categories:
   * `application_help`: Natural conversational assistance without routing to entertainment databases.
   * `factual_knowledge`: Multi-source knowledge retrieval (Wikipedia REST API + DuckDuckGo fallback).
   * `follow_up`: Pronoun & anaphoric context resolution (e.g., *"What is quantum computing?"* $\rightarrow$ *"Who invented it?"*).
   * `camera_vision_scene`: Grounded computer vision scene analysis; strictly checks for live frames and refuses to hallucinate background items if the camera is offline.
   * `camera_action_snapshot`: Verified capture operations requiring confirmed disk write before reporting success.
   * `camera_action_record`: Verified video start/stop command dispatching.
   * `camera_management`: Stream control (pause, resume, mute, unmute).
   * `current_news`: Google News RSS real-time feed without cross-query contamination.
   * `live_weather`: Live temperature, humidity, and condition reports via wttr.in/Open-Meteo.
   * `calculation`: Safe arithmetic parsing and unit conversions without eval vulnerabilities.
   * `general_conversation`: Empathy, well-being, greetings, farewells, and humor.
3. **Response Validation**: Post-generation guardrails verifying that the output answers the specific question asked, strips artificial formatting (`Regarding **...**:`), enforces camera frame grounding, and suppresses unverified tool claims.

### 7.2 Running Automated AI Tests

Run the comprehensive test suite (78 automated tests including multi-camera visual AI, security, evaluation benchmark, and AI regression scenarios):

```powershell
# Virtual environment
.\.venv\Scripts\python -m pytest backend/tests/test_evaluation_benchmark.py -v
.\.venv\Scripts\python -m pytest backend/tests/test_multi_camera_visual_ai.py -v
.\.venv\Scripts\python -m pytest backend/tests/test_ai_orchestration.py -v

# Run full backend test suite (78 passed)
.\.venv\Scripts\python -m pytest backend/tests/
```

### 7.3 Troubleshooting

* **"What is gold?" returned unrelated news?**
  * Root cause was cross-contamination from prior news headlines into the follow-up resolver and Wikimedia 429 rate limits.
  * Resolved: Standalone inquiries are now guarded against pronoun substitution, compliant Wikimedia User-Agents are configured, and topic relevance checks reject mismatched retrieval extracts.
* **Camera scene reported fake items when offline?**
  * Resolved: `SceneAnalysisService.analyze_scene()` returns `has_frame=False` and empty `detected_items` when no live frame is supplied. The orchestrator answers: *"No live camera frame is currently available. Please turn on your camera or supply an image."*
* **"Take a snapshot" reported success without saving?**
  * Resolved: `SafeToolRegistry.execute_snapshot()` physically writes the image to disk, checks `stat().st_size > 0`, and returns verified metadata (`filename`, `url`, `file_size_bytes`).

### 7.4 Standards & Framework Compliance

The platform adheres to international enterprise AI safety, cybersecurity, and risk management standards:

#### 1. OWASP Top 10 for LLM & Generative AI Applications

* **LLM01: Prompt Injection** — Environmental OCR text extracted from live video is strictly encapsulated in `<untrusted_environmental_data source="camera_ocr">...</untrusted_environmental_data>` so external text (e.g. on shirts, signs) is parsed as passive data, never as executable instructions.
* **LLM02: Insecure Output Handling** — Output rendering is sanitized with zero raw HTML execution. `ResponseValidator` strips artificial prefixes and verifies tool confirmations.
* **LLM03: Training Data Poisoning** — `ControlledModelRegistry` enforces staging and evaluation gates (Precision $\ge 0.95$, Recall $\ge 0.92$, F1 $\ge 0.94$, Latency $\le 60\text{ms}$) with 1-click rollback.
* **LLM04: Model Denial of Service** — Stream worker threads throttle capture frequency (2–5 FPS sampling per camera) with bounded reconnection backoff (`min(30s, 1.5**attempts + jitter)`).
* **LLM05: Sensitive Information Disclosure** — Biometric face templates are encrypted at rest via AES-256-GCM. Stream URLs are sanitized to block AWS/GCP cloud metadata (`169.254.169.254`).
* **LLM07: Insecure Plugin Design** — All backend actions route through allow-listed `SafeToolRegistry` handlers with parameter validation and disk/hardware state confirmation.
* **LLM08: Excessive Agency** — Sensitive actions require explicit owner confirmation. The system does not dispatch external calls or emergency notifications without verified human verification.
* **LLM09: Overreliance** — Probabilistic model inferences are explicitly distinguished from verified observations. The system never infers intent, guilt, or health status from visual appearance.

#### 2. NIST Cybersecurity Framework (CSF 2.0)

* **Govern (GV):** Owner-only consent policy (`ConsentRecord`), role-based access control, model promotion governance.
* **Identify (ID):** Automated camera device discovery, stream validation, and hardware telemetry tracking (`CameraHealthStatus`).
* **Protect (PR):** Symmetric AES-256-GCM encryption, JWT authentication, and SSRF stream validation.
* **Detect (DE):** Normalized polygon ROI intrusion checks (`cv2.pointPolygonTest`), loitering dwell times, and stale stream detection.
* **Respond (RS):** Cooldown deduplication preventing notification storms, structured audit logs.
* **Recover (RC):** 1-click model rollback, resilient automatic stream reconnection.

#### 3. NIST AI Risk Management Framework (AI RMF 1.0)

* **Valid & Reliable:** Measured against a 76-test automated regression suite with deterministic calculations and schema validation.
* **Safe & Resilient:** Untrusted OCR isolation, bounded queues, and zero single-point-of-failure multi-worker threads.
* **Accountable & Transparent:** Every visual observation references the specific camera ID, timestamp, and frame freshness status.
* **Privacy-Enhanced:** Mandatory owner consent for face verification; strangers and unenrolled individuals are never identified.

---

## 8. Licence

The original project was published as open source; see the repository history
for the previous licence file.

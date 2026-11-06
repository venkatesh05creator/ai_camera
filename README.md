# Aegis AI — Owner-Only AI Camera Assistant

A privacy-first, consent-based camera assistant for a single owner. Laptop webcams,
Android phones, wearable cameras and compatible IP cameras share one backend and one
dashboard with a JARVIS-style copilot chat.

The assistant is **consent-based owner verification**, not a stranger identification
system. Only people the owner explicitly enrolled are ever identified; everybody else
stays anonymous. Camera events are stored as metadata (never raw frames), biometric
templates are encrypted at rest (AES-256-GCM), and the AI assistant never sees anything
but the owner's own metadata.

> **Status.** The security controls described in [`SECURITY.md`](SECURITY.md) are
> implemented and covered by automated tests, but **no independent penetration test has
> been performed**. Treat this as a well-tested baseline, not a certified product.

---

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │         Owner (browser / app)       │
                    └──────────────┬──────────────────────┘
                                   │ HTTPS (loopback, 127.0.0.1)
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     FastAPI application  (ownerai/main.py)           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  Middleware │  │   Routers   │  │   Services  │  │    Core     │  │
│  │  security   │  │  auth, chat │  │  ai, biomet │  │  settings,  │  │
│  │  headers,   │  │  devices,   │  │  rics,      │  │  db, crypto │  │
│  │  csrf, rate │  │  events,    │  │  cameras,   │  │  sessions   │  │
│  │  limit,     │  │  identities │  │  chat,      │  │             │  │
│  │  redaction  │  │  legacy, …  │  │  voice, …   │  │             │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
│                              │                                        │
│                     SQLite / Postgres (encrypted templates)          │
└──────────────────────────────────────────────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
         face_*.py            web/ (React SPA)     desktop/mobile
         utils/               (built separately)    (integration docs)
         models/
```

**Live app:** `ownerai/` — the hardened FastAPI backend, templates, static assets, and security middleware. Entry point: `app.py` (or `uvicorn ownerai.main:app`).

**Parallel tree (not the live app):** `backend/` — a larger duplicate "Surveillance Platform" tree referenced by `main.py`'s modern web command. It is *not* served by `app.py` and has 11 pre-existing test failures unrelated to this cleanup.

**Legacy computer-vision prototype:** `face_*.py`, `utils/`, `models/`, `config.py` — the original Tkinter/CLI face recognition, preserved behind the authenticated `/api/legacy/embeddings` endpoint.

---

## What is in the box

| Part | Path | Notes |
|------|------|-------|
| Live web application (FastAPI) | `ownerai/` | Backend, templates, static assets, security middleware |
| Tests (owner app) | `tests/` | **118 automated tests**, including negative security/privacy tests |
| Parallel tree | `backend/` | Duplicate surveillance platform; not the live app (11 pre-existing failures) |
| Legacy CV prototype | `face_*.py`, `utils/`, `models/`, `config.py` | Original face recognition; exposed via `/api/legacy/embeddings` |
| Security tooling | `scripts/security_check.py` | ruff + bandit + pip-audit + pytest |
| Run commands | `app.py`, `run.bat`, `run_surveillance.bat` | See Quick start |
| Documentation | `README.md`, `SECURITY.md`, `docs/` | Operation, deployment, security policy |

### Feature overview

* **Authentication** — Argon2id password hashing, server-side sessions, session rotation, idle/absolute expiry, revocation, rate limiting, account lockout, TOTP multi-factor authentication, password reset with single-use tokens, optional e-mail verification.
* **Authorisation** — four roles (`owner`, `admin`, `trusted`, `viewer`), a permission matrix, and strict per-object ownership checks that prevent IDOR/BOLA.
* **Cameras** — device registry for webcams, phones, wearables and IP cameras; SSRF-protected snapshot fetching; HMAC-signed event ingestion with replay protection.
* **Biometrics** — consent-gated enrolment, AES-256-GCM encrypted templates, retention periods, withdrawal and deletion, verification that never identifies unenrolled people.
* **Assistant** — server-side provider abstraction (OpenAI-compatible or a fully offline provider), PII redaction, prompt-injection defences, tool allow-list with explicit confirmation for mutations, per-user token and request budgets.
* **User interface** — responsive dashboard with a light/dark theme switch (system theme aware), an accurate cookie banner, a permission-filtered site search, a floating contact dialog and a keyboard accessible back-to-top button.

---

## Quick start (5 minutes)

> Python 3.10 or newer is required (FastAPI >= 0.156 needs 3.10+). This project was tested with Python 3.9 / 3.13.

### 1. Virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Dependencies

```powershell
pip install -r requirements-dev.txt   # server + dev tooling (includes requirements-server.txt)
pip install -r requirements.txt        # adds the vision stack (biometrics; optional)
```

### 3. Configuration

```powershell
copy .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # -> OWNERAI_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"   # -> OWNERAI_BIOMETRIC_ENCRYPTION_KEY
# Paste both values into .env and adjust the rest.
```

### 4. Run (bound to the loopback interface)

```powershell
python app.py
# or: uvicorn ownerai.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/> and create the **first account** — it becomes the owner of the installation. Every later registration is a regular `viewer` until an owner promotes it.

The biometric engine is optional: without TensorFlow the enrolment endpoint answers *"the biometric engine is not installed on this server"* and every other feature keeps working.

### Run commands per platform

| Platform | Command |
|----------|---------|
| Windows (dev) | `python app.py` or `run.bat` |
| Windows (surveillance tree) | `run_surveillance.bat` (serves `backend.app.main:app`) |
| Linux/macOS | `uvicorn ownerai.main:app --host 127.0.0.1 --port 8000` |

### Useful environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
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

## Running the checks

```powershell
# Everything (lint, SAST, dependency audit, tests)
python scripts/security_check.py

# Individually
python -m ruff check ownerai tests app.py
python -m bandit -r ownerai -q
python -m pip_audit -r requirements-server.txt
python -m pytest tests -q
```

### Test results (baseline)

| Suite | Result |
|-------|--------|
| `tests/` (owner app, live) | **118 passed, 0 failed** |
| `backend/tests/` (parallel tree) | 129 passed, 11 failed (pre-existing failures; unrelated to this repo's live app) |

The test suite covers the required negative cases: unauthenticated access, cross-user data access, role-escalation payloads, SQL injection, XSS, rate limiting, expired/revoked sessions, secret leakage, stranger non-identification, WebSocket authorisation, private file serving, debug endpoint hiding, and security headers.

---

## Project layout

```
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
│                     search.py, audit.py, voice.py
├── routers/          auth, devices, events, identities, chat, search, admin,
│                     contact, legacy, pages, vision, voice, hud
├── templates/        server-rendered pages (index, login, dashboard, admin, hud, …)
└── static/           css/js (no CDN, no trackers, no inline scripts)
```

---

## Privacy & security principles

1. **Owner-only and consent-based** — only explicitly enrolled people are ever identified. Never identify strangers. Never infer intent, guilt, or health from appearance.
2. **Grounded answers** — JARVIS may only state what the latest detector output and frame prove. If People = 0 or no live frame exists, it says so. Every visual claim cites camera ID, timestamp, and frame freshness.
3. **Privacy by default** — store event metadata, not raw frames, unless the owner enabled encrypted clips. No secrets in code, logs, or client bundles.
4. **Confirmed mutations** — tool actions that change state need explicit owner confirmation and must verify the result (e.g. the snapshot file actually exists) before reporting success.
5. **Do not break existing tests or security behavior.**

See [`SECURITY.md`](SECURITY.md) for the full threat model, API surface, rate limits, and the operator checklist.

---

## Legacy computer-vision scripts

The original prototype is still available and unchanged in behaviour:

```powershell
python face_recognize_static.py --model facenet path/to/image.jpg
python face_recognize_live.py --model facenet
python face_add_static.py --model facenet path/to/image.jpg
python face_add_live.py --model facenet
python face_remove.py
```

The prototype's HTTP endpoint (`/extract-embeddings`, which read *any* path on the server without authentication) was replaced by `POST /api/legacy/embeddings`. It requires an authenticated account, is restricted to the directory in `OWNERAI_LEGACY_IMAGE_ROOT` (default `./inputs`), is rate limited and never returns a stack trace.

---

## Licence

The original project was published as open source; see the repository history for the previous licence file.
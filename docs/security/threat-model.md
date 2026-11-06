# Threat Model — Aegis AI

**Scope:** The `ownerai/` FastAPI application (the live app), its SQLite/Postgres
database, encrypted biometric templates, the JARVIS assistant, and the
innovation features behind opt-in feature flags.

**Threat actors:** anonymous internet user, authenticated low-privilege user,
compromised browser (XSS), compromised device (phone/wearable), hostile
network/DNS, prompt injection through data, insider with database access.

**Out of scope:** physical attacks, a compromised host, a compromised reverse
proxy. Those break every control in this document.

---

## Data-flow diagram (mermaid)

```mermaid
flowchart TD
    Owner((Owner)) -->|HTTPS / loopback| Browser[Browser / App]
    Browser -->|session cookie + CSRF token| API[FastAPI ownerai/]
    
    subgraph CameraLayer[Camera / device layer]
        Cam[Webcam / phone / IP cam]
        Cam -->|HMAC-signed event + nonce| Ingest[/api/devices/ingest]
    end
    
    API --> Auth[Authentication / sessions]
    Auth --> DB[(SQLite / Postgres)]
    DB -->|owner_id filtered| Auth
    
    API --> CBAC[RBAC + ownership checks]
    CBAC --> DB
    
    API --> JARVIS[JARVIS AI orchestrator]
    JARVIS --> Context[<camera_context> / <user_input> untrusted data wrappers]
    JARVIS --> Provider[AI provider: offline default / OpenAI-compatible]
    Provider -.->|only if API key configured| Cloud[(Third-party LLM)]
    
    JARVIS --> ToolReg[SafeToolRegistry allow-list]
    ToolReg -->|mutating = confirmed only| Mutate[Owner confirms + result verified]
    
    API --> Events[CameraEvent metadata only]
    Events --> DB
    
    API --> Templates[EnrolledIdentity AES-256-GCM]
    Templates --> DB
    
    subgraph Dev[web/ React SPA — not live, dev-only]
        Web[web/ build output]
    end
    
    style Cloud fill:#f96,stroke:#333
    style Dev fill:#bbb,stroke:#999,stroke-dasharray: 5 5
```

**Trust boundary:** everything inside `ownerai/` is server-side trusted. The
browser, the AI provider, and the camera ingestion path are untrusted and are
validated before use. `web/` is a separate, unbuilt client that is not mounted
by the live `app.py`.

---

## STRIDE analysis

| Threat | Asset | Scenario | Existing control | Residual |
|--------|-------|----------|------------------|----------|
| **Spoofing** | Session | Attacker steals session cookie | `HttpOnly`, `SameSite=Lax`, `Secure` in prod; token SHA-256 hashed in DB | Low |
| **Spoofing** | Camera event | Attacker forges device event | HMAC-signed device requests, nonce replay protection | Low |
| **Tampering** | Biometric template | Attacker modifies encrypted template | AES-256-GCM (authenticated encryption), InvalidTag rejected | Low |
| **Tampering** | AI answer | Prompt injection via OCR/event text | `<camera_context>`/`<user_input>` untrusted wrappers; model told data != instructions | Low |
| **Repudiation** | Audit log | Attacker denies an action | Append-only `audit_logs`, IP hash, no secrets | Low |
| **Information disclosure** | Template / secret | DB dump reveals templates or keys | Templates AES-256-GCM; keys env-only, never in logs/responses/bundles | Low |
| **Information disclosure** | Session | Session token in DB usable after dump | Only SHA-256 hash stored | Low |
| **Information disclosure** | Owner data | Cross-user access (IDOR/BOLA) | Every object filtered by `owner_id`; foreign → `404` | Low |
| **Denial of service** | API | Request flood | Rate limits per IP/user, 8 MiB body cap, 429 + Retry-After | Low |
| **Elevation of privilege** | Role | User assigns self `owner` | `extra="forbid"` schema rejects unknown `role` field; owner can't be self-assigned | Low |
| **Elevation of privilege** | Tool | Model executes mutating tool | Mutating tools require `confirmed=True` via separate authorised endpoint; result verified before success | Low |

---

## Data classification

| Data | Classification | Stored? | Encrypted? | Leaves server? |
|------|---------------|---------|------------|----------------|
| Password hash | Secret | DB (users) | Argon2id hash | No |
| Session token hash | Secret | DB (user_sessions) | SHA-256 hash | No (cookie only) |
| Biometric template | Secret | DB (enrolled_identities) | AES-256-GCM | No |
| Encryption key | Secret | Env only | N/A | No |
| App secret key | Secret | Env only | N/A | No |
| Camera event metadata | Private | DB (camera_events) | No | No (owner only) |
| AI provider key | Secret | Env only | N/A | Yes, to provider if configured |
| Client IP | Private | Logs (masked last octet) | No | No |
| Raw camera frames | Private | Not stored | N/A | No |

---

## Assumptions

1. The operator sets `OWNERAI_SECRET_KEY` and `OWNERAI_BIOMETRIC_ENCRYPTION_KEY`
   with strong random values (`.env.example` provides placeholders only).
2. Production runs with `OWNERAI_APP_ENV=production`, `OWNERAI_HTTPS_ONLY=true`,
   `OWNERAI_HSTS_ENABLED=true`, and a non-wildcard `OWNERAI_TRUSTED_HOSTS`.
3. `OWNERAI_TRUST_PROXY_HEADERS=true` only when a reverse proxy is the sole
   client (see S3, SSRF/IP-spoofing finding).
4. The Git history still contains legacy biometric data (SECURITY.md §12); if
   the repo was ever public, history must be rewritten with `git filter-repo`.

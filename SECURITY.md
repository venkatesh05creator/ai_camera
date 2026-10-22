# Security policy

This document describes the security model of the **Owner-Only AI Camera
Assistant**, the endpoint inventory and the operational requirements for a
safe deployment.  It is written for the operator of the installation.

> **Scope statement.**  Nothing in this repository can be described as
> "completely secure" or "bug free".  The controls below reduce a defined set
> of risks; they do not eliminate them.  Section *Known limitations* lists
> what is explicitly **not** covered.

---

## 1. Threat model

The installation processes data that is privacy sensitive: camera metadata,
biometric templates of the owner and private AI conversations.  The relevant
threat actors are:

| Actor | Goal | Primary control |
| --- | --- | --- |
| Anonymous internet user | Read private data, take over an account | Authentication, rate limits, generic errors |
| Authenticated low-privilege user | Read another account's data, gain privileges | Server-side RBAC + ownership checks (IDOR protection) |
| Compromised browser (XSS) | Steal the session or read page data | Strict CSP without inline script, `HttpOnly` session cookie, CSRF tokens, output encoding |
| Compromised device (phone/wearable) | Forge camera events | HMAC-signed device requests, nonce replay protection |
| Hostile network / DNS | Turn the camera fetch into an SSRF probe | URL allow-listing, private address rejection, redirect re-validation, size/time caps |
| Prompt injection through data | Make the assistant leak data or act | Untrusted-data delimiters, server-side permission checks, no autonomous tools, confirmation for mutations |
| Insider with database access | Read biometric templates | AES-GCM encryption at rest, least-privilege DB accounts, audit log |

Explicitly **out of scope**: physical attacks, a compromised host or a
compromised reverse proxy.  Those break every control in this document.

---

## 2. Authentication

* Passwords are hashed with **Argon2id** (`argon2-cffi`, 64 MiB, 3 iterations,
  4 lanes, 32 byte hash, 16 byte salt).  Parameters are re-checked on every
  successful login and hashes are upgraded automatically.
* Passwords are never stored, logged or returned in any form.
* Sessions are **server side**: the browser only receives a 256-bit random
  token in an `HttpOnly`, `SameSite=Lax` cookie (`Secure` in production).  The
  database stores only the SHA-256 hash of the token, so a database dump does
  not yield usable sessions.
* Sessions have an **idle timeout** (30 min) and an **absolute timeout**
  (12 h), are rotated on login and on a change of the authentication level
  (MFA), and can be revoked individually or all at once.
* Login, registration, password reset, e-mail verification and search are
  **rate limited** per IP (and per user where applicable) with `429` responses
  and a `Retry-After` header.
* Failed logins are counted; five failures lock the account for 15 minutes.
* Error messages are **identical** for unknown accounts and wrong passwords so
  that accounts cannot be enumerated.
* Password resets use single-use, hashed tokens with an expiry.  The response
  is identical whether or not the account exists.
* **TOTP (RFC 6238)** multi-factor authentication is available and can be
  enforced for administrators.  The shared secret is stored encrypted; backup
  codes are stored hashed.

## 3. Authorisation

Roles: `owner`, `admin`, `trusted`, `viewer`.  The full matrix lives in
`ownerai/rbac.py`.

* Every request is authorised **on the server**.  Hiding a button in the UI is
  never treated as a control.
* Every object carries an `owner_id`.  Reads and writes are filtered by it;
  foreign objects produce `404` (not `403`) so that the API does not disclose
  their existence.
* Ownership is checked **before** the permission, so a low-privilege user
  cannot use the difference between `403` and `404` to probe for objects.
* Users cannot assign themselves a role.  The payload of a registration or
  profile request is validated with a schema that rejects unknown fields, so a
  `role` field is a `422`, not a silent privilege change.
* Only the owner may grant the owner role; an administrator may not.
* Nobody may change their own role.

## 4. API surface

| Method & path | Authentication | Authorisation | Notes |
| --- | --- | --- | --- |
| `GET /` | none | - | Landing page, sets the CSRF cookie |
| `GET /login`, `/register`, `/forgot-password`, `/reset-password`, `/verify-email`, `/docs` | none | - | Static forms |
| `GET /health` | none | - | Minimal probe, no internal details |
| `GET /api/search` | optional | owner-scoped | Anonymous visitors only see the public docs |
| `POST /api/contact` | CSRF token | rate limited | Honeypot + fill-in-time trap, e-mail stored encrypted |
| `POST /api/auth/register` | CSRF token | rate limited | First account of an installation becomes the owner |
| `POST /api/auth/login` | CSRF token | rate limited | Generic errors, session rotation, lockout |
| `POST /api/auth/mfa/verify` | CSRF token | session | Rotates the session |
| `POST /api/auth/logout` | CSRF token | session | Revokes the session, clears the cookies |
| `GET /api/auth/me` | session | - | Own account only |
| `GET /api/auth/sessions` | session | owner | Own sessions only |
| `DELETE /api/auth/sessions/{id}` | CSRF token | owner | Own sessions only |
| `POST /api/auth/password/change` | CSRF token | session | Revokes the other sessions |
| `POST /api/auth/password/forgot` | CSRF token | rate limited | Generic response |
| `POST /api/auth/password/reset` | single-use token | - | CSRF exempt (documented in `dependencies.py`) |
| `POST /api/auth/email/verify` | single-use token | - | CSRF exempt (documented in `dependencies.py`) |
| `POST /api/auth/mfa/setup`, `/mfa/enable`, `/mfa/disable` | CSRF token | owner | Secret stored encrypted |
| `GET/POST /api/devices` | session | `devices:read` / `devices:write` | Owner scoped |
| `GET/PATCH/DELETE /api/devices/{id}` | session | owner + permission | Foreign id → `404` |
| `POST /api/devices/{id}/rotate-token` | CSRF token | `devices:write` | Token shown once, only its hash is stored |
| `GET/POST /api/devices/{id}/events` | session | `events:read` / `events:write` | Owner scoped |
| `POST /api/devices/{id}/snapshot` | CSRF token | `devices:read` | SSRF protected, size/time capped |
| `POST /api/devices/ingest` | device token + HMAC | device owner | Nonce replay protection |
| `GET /api/events` | session | `events:read` | Owner scoped, paginated |
| `GET/POST /api/identities` | session | `identities:read` / `identities:write` | Consent mandatory, template encrypted |
| `DELETE /api/identities/{id}` | CSRF token | `identities:delete` | Destroys the template |
| `POST /api/identities/verify` | CSRF token | owner | Unenrolled people stay anonymous |
| `GET /api/chat/conversations`, `GET .../messages` | session | `chat:read` | Owner scoped |
| `POST /api/chat` | CSRF token | `chat:write` | Quotas, redaction, injection defence |
| `POST /api/chat/tools/{tool}` | CSRF token | tool permission | Mutations require `confirmed: true` |
| `DELETE /api/chat/conversations/{id}` | CSRF token | `chat:write` | Owner scoped |
| `GET /api/admin/users`, `/audit`, `/contacts`, `/stats` | session | `admin:*` | Administrators and owner |
| `PATCH /api/admin/users/{id}/role` | CSRF token | `admin:roles` | Owner only, no self-modification |
| `POST /api/admin/users/{id}/status` | CSRF token | `admin:users` | Cannot disable yourself |
| `PATCH /api/admin/contacts/{id}` | CSRF token | `admin:contacts` | Status only |
| `POST /api/legacy/embeddings` | session | `devices:read` | Path restricted to an allow-listed directory |
| `WS /ws/events` | session cookie | per subscription | Foreign devices are filtered out |
| `GET /api/docs`, `/api/openapi.json` | none | - | Disabled in production |

## 5. Input validation

* Every request body is validated by a Pydantic model with
  `extra="forbid"`, whitespace trimming and explicit length limits.
* Query and path parameters are bounded (pagination is clamped, search terms
  are limited to 120 characters, LIKE wildcards are escaped).
* Request bodies are capped (`OWNERAI_MAX_REQUEST_BODY_BYTES`, 8 MiB) and
  rejected with `413` before they are parsed.
* All database access goes through the SQLAlchemy ORM with bound parameters.
  No string concatenation into SQL exists in the code base.
* Output is escaped by the template engine; the front-end never uses
  `innerHTML` with server data.
* Uploads are limited to images, are size capped and are decoded by OpenCV
  (which fails on non-images).

## 6. Rate limiting and quotas

| Scope | Limit (default) | Window |
| --- | --- | --- |
| `login` | 5 | 300 s |
| `register` | 3 | 3600 s |
| `password_reset` | 3 | 3600 s |
| `search` | 30 | 60 s |
| `ai` | 20 | 60 s |
| `contact` | 3 | 3600 s |
| `event_write`, `camera_snapshot`, `legacy_embeddings`, `upload` | 10 | 600 s |
| AI token budget | 100 000 tokens | per user per UTC day |
| AI request budget | 200 | per user per UTC day |

The counters live in the database, so all workers of a multi-process
deployment share the same state.

## 7. Security headers

Set on every response by `ownerai/middleware.py`:

```http
Content-Security-Policy: default-src 'self'; base-uri 'self'; object-src 'none';
  frame-ancestors 'none'; form-action 'self'; img-src 'self' data: blob:;
  media-src 'self' blob:; font-src 'self'; style-src 'self'; script-src 'self';
  worker-src 'self' blob:; manifest-src 'self'; connect-src 'self' ws://… wss://…
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Cross-Origin-Opener-Policy: same-origin
Permissions-Policy: camera=(self), microphone=(), geolocation=(), payment=(),
  usb=(), accelerometer=(), gyroscope=(), magnetometer=(), interest-cohort=()
Strict-Transport-Security: max-age=31536000; includeSubDomains   (production only)
```

* There is **no** `unsafe-inline` and **no** `unsafe-eval`; the front-end
  ships external CSS and JS files only.
* `Strict-Transport-Security` is only sent when `OWNERAI_HSTS_ENABLED` is
  true, which the production configuration check requires together with
  `OWNERAI_HTTPS_ONLY`.
* Authenticated pages are served with `Cache-Control: no-store`.
* CORS is disabled unless `OWNERAI_CORS_ORIGINS` lists explicit origins;
  wildcard origins are rejected by the production configuration check.

## 8. Secrets

* Every secret is read from the environment (prefix `OWNERAI_`) or a local
  `.env` file that is excluded from version control.
* `.env.example` contains placeholders only.
* The production configuration check refuses to start when the secret is
  missing, shorter than 32 characters or equal to the development default.
* Secrets are never sent to the browser, never written to a log (a redacting
  log filter is installed) and never included in an API response.
* The AI key and the biometric encryption key stay on the server; the
  front-end bundle contains no key material (verified by a test).

**If a secret ever leaks, deleting the file does not invalidate it.**  Rotate
the credential at the provider, then redeploy.

## 9. Biometric and AI privacy

* Enrolment requires an explicit `consent: true` flag; without it the server
  refuses to store anything.
* Templates are encrypted with AES-256-GCM (key derived from
  `OWNERAI_BIOMETRIC_ENCRYPTION_KEY`) and carry a consent timestamp, a
  consent version and an expiry.
* Withdrawal deletes the template immediately; expired templates are purged.
* Only the owner's own templates are compared during verification, so an
  unenrolled person can never be identified - the answer is simply "not
  matched".
* Raw camera frames and audio are never stored.  Only event metadata is.
* The assistant receives **metadata**, never raw media.
* Before anything is sent to a third-party AI provider, e-mail addresses, IP
  addresses and long numbers are redacted.
* Retrieved content and user input are wrapped in `<camera_context>` /
  `<user_input>` markers and are explicitly declared untrusted, so injected
  instructions cannot change the rules.
* The model never executes a mutating tool.  It may only *propose* one; the
  proposal is executed by a separate, separately authorised endpoint after an
  explicit confirmation.
* Permissions are evaluated by the backend before any context is assembled.

## 10. Known limitations

These are real and are **not** fixed by this document:

1. **Face recognition is a fallible signal.**  A false positive can
   "verify" a look-alike.  The threshold (0.72 by default) is a starting
   point, not a guarantee, and should be tuned for the deployment.
2. **No liveness detection.**  A photograph of the owner would pass the
   verification.  Treat the biometric unlock as one factor, never as the only
   factor.
3. **The offline AI provider is not an LLM.**  Without an API key the
   assistant answers with a deterministic message - no data leaves the
   machine, but there is no real assistant either.
4. **DNS rebinding.**  The camera URL is resolved and checked before the
   connection is opened, but the name is resolved again by the HTTP client.
   Use an IP allow-list for high-risk deployments.
5. **SQLite.**  The default database is a single file.  It is fine for one
   owner, but a busy multi-user deployment should use PostgreSQL, where the
   rate limiter still works (shared table) but transactions must be reviewed.
6. **Rate limiting is per installation.**  A distributed deployment across
   several hosts needs a shared store; the current implementation shares the
   counters only through the database.
7. **The biometric engine is optional.**  Without TensorFlow the enrolment
   endpoint reports "not installed" instead of failing - the application
   itself keeps running.
8. **E-mail verification is optional** and disabled by default in
   development.  Enable `OWNERAI_REQUIRE_EMAIL_VERIFICATION=true` in
   production.
9. **The support contact address** shown in the UI comes from the
   configuration; do not put a personal address into a public installation.
10. **No pentest has been performed by a third party.**  The automated tests
    and scanners in this repository are a baseline, not a certificate.

## 11. Reporting a vulnerability

Open a private issue with the repository owner.  Please include a
reproduction step, the affected version and the impact.  Do not include real
camera data, real biometric templates or production credentials in a report.

## 12. Repository hygiene and previously committed data

Earlier revisions of this repository contained material that must not be in
version control:

* `data/Faces/**` and `data/office_images/**` - photographs of real people,
* `datastore/*.json` and `datastore_512_Dim.json` - face **embeddings**
  (biometric templates) derived from those photographs,
* `node_modules/**` and `load_test/**` - a vendored Node.js tree with its
  own dependency advisories.

The working tree no longer tracks any of it (see `.gitignore`), but **the
Git history still contains it**.  Removing a file from the current revision
does not remove it from the repository history.

If this repository is (or was) public, the following is required:

```bash
# 1. Rewrite the history (requires git-filter-repo)
pip install git-filter-repo
git filter-repo --path data/Faces --path data/office_images --path datastore \
                --path datastore_512_Dim.json --invert-paths
# 2. Force-push and have every collaborator re-clone.
# 3. Inform the people whose faces were in the data set - an embedding is
#    biometric data and cannot be "un-published" once it was cloned.
```

The embeddings in the old datastore were stored **unencrypted**.  They must be
treated as compromised: the affected people should be asked to re-enrol (the
new enrolment path encrypts the template) and the old embeddings deleted.

## 13. Operator checklist before going live

* [ ] `OWNERAI_SECRET_KEY` and `OWNERAI_BIOMETRIC_ENCRYPTION_KEY` generated
      with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
* [ ] `OWNERAI_APP_ENV=production`, `OWNERAI_HTTPS_ONLY=true`,
      `OWNERAI_HSTS_ENABLED=true`.
* [ ] `OWNERAI_TRUSTED_HOSTS` set to the public host names.
* [ ] TLS terminated at the edge, `OWNERAI_TRUST_PROXY_HEADERS=true` only when
      the proxy is the only client.
* [ ] Database file or server outside the web root, with restricted file
      permissions.
* [ ] `OWNERAI_REQUIRE_EMAIL_VERIFICATION=true` and a real SMTP backend.
* [ ] `OWNERAI_AI_API_KEY` set (or the offline provider deliberately chosen).
* [ ] Backups encrypted, retention and restore tested.
* [ ] `pip-audit`, `bandit`, `ruff` and the test-suite green in CI.
* [ ] Log shipping configured; logs contain no personal data.

# Security Findings — Aegis AI

**Scope:** `ownerai/` (live app), `web/` (dev client, not live), `backend/` (parallel tree, not live).  
**Scans run:** ruff (clean), bandit (clean), npm audit (2 dev-build advisories), pip-audit (not run — no network), semgrep/gitleaks/trivy/trufflehog (not installed — no network).  
**Method:** Automated scans + manual OWASP Top 10 + OWASP Top 10 for LLM review.

---

## Scan results

| Tool | Target | Result | Notes |
|------|--------|--------|-------|
| ruff | `ownerai`, `tests`, `app.py` | CLEAN | E/F/W/B/S/C4/I rules |
| bandit | `ownerai` | CLEAN | No high/medium issues |
| pip-audit | `requirements-server.txt` | NOT RUN | No outbound network to PyPI in this environment |
| npm audit | `web/` | 2 findings | `vite` high, `esbuild` moderate — dev/build tools only |
| semgrep | — | NOT INSTALLED | No network to install |
| gitleaks/trufflehog | — | NOT INSTALLED | No network to install; Git history reviewed manually (see F-004) |
| trivy | Dockerfiles/compose | NOT INSTALLED | No Dockerfiles tracked in live app; `infrastructure/` reviewed manually |

---

## Findings table

| ID | Severity | Finding | File | Fix | Regression test |
|----|----------|---------|------|-----|-----------------|
| F-001 | Medium | Git history contains legacy biometric data (photos of real people + unencrypted face embeddings in `data/Faces/`, `datastore/*.json`). If the repo was ever public, those embeddings are compromised. | Git history (SECURITY.md §12) | Rewrite history with `git filter-repo --invert-paths`, force-push, notify affected people to re-enrol with the new encrypted path. | Test confirms no `datastore/*.json` or `data/Faces/**` is tracked (`git ls-files` empty for those paths). |
| F-002 | Low | `client_ip()` trusts `X-Forwarded-For` when `OWNERAI_TRUST_PROXY_HEADERS=true`. If enabled without a trusted reverse proxy, an attacker can spoof their IP and bypass per-IP rate limits. | `ownerai/middleware.py:194-201` | Document that the flag must only be set when the proxy is the sole client. Add startup warning when flag is true in non-production. | Test asserts `client_ip()` falls back to `request.client.host` when `trust_proxy_headers=false`. |
| F-003 | Low | `npm audit` reports `vite` (high, direct dev dep) path traversal in optimized deps `.map` handling, and `esbuild` (moderate, indirect) allowing websites to send requests to the dev server. | `web/package.json` | Both are dev/build tools only; `web/` is not mounted by live `app.py` and no `web/dist` is tracked. Accept as dev-only risk; upgrade `vite` to >=8.3.6 when the web build is reactivated. | Test asserts no `web/dist` or `web/node_modules` is tracked by git. |
| F-004 | Medium | Biometric key derivation uses plain `sha256(secret)` rather than a memory-hard KDF (Argon2/PBKDF2/scrypt). Acceptable for a single-owner deployment but weaker than the Argon2id used for passwords. | `ownerai/crypto.py:30-32` | Consider deriving the AES key with `hashlib.pbkdf2_hmac` or Argon2id in a future release. | Test asserts `encrypt_bytes`/`decrypt_bytes` round-trip and that tampered ciphertext raises `EncryptionError`. |
| F-005 | Low | CSRF token signing uses `sha256("csrf:{nonce}:{secret}")` rather than HMAC. Functionally equivalent for secrecy but not standard construction. | `ownerai/security.py:124-138` | Accept (constant-time compare, 256-bit nonce). No change required. | Test asserts anonymous CSRF token verification rejects tampered signatures. |
| F-006 | Low | `pip-audit`, `semgrep`, `gitleaks`, `trufflehog`, `trivy` could not run in this environment (no outbound network). | CI workflow `.github/workflows/security.yml` | Add these to CI so they run on push/PR/schedule when network is available. | Test asserts `.github/workflows/security.yml` exists and references pip-audit, ruff, bandit, npm-audit. |
| F-007 | Informational | `backend/` is a duplicate parallel tree with 11 pre-existing test failures and is not the live app. | `backend/` | Keep documented as non-live; consolidation is a product decision. | Test asserts `ownerai/main:app` is the entry point referenced by `app.py`, `run.bat`, `scripts/security_check.py`. |
| F-008 | Informational | No secrets or face embeddings are tracked in the working tree (`.env`, `datastore/`, `data/Faces/` are gitignored). | `.gitignore` | Maintain `.gitignore` coverage; CI should assert `git ls-files` returns nothing for secrets/embeddings. | Test asserts `.env` is not tracked and `.env.example` is. |

---

## OWASP Top 10 + OWASP Top 10 for LLM — manual review

| Area | Check | Status | Evidence |
|------|-------|--------|----------|
| **A01 Broken Access Control** | Every route/WebSocket checks owner + device ownership | PASS | `resource_or_404`, `owns_resource`, `has_permission` on every router; foreign → 404 |
| | Foreign object → 404 not 403 | PASS | `resource_or_404` raises 404 |
| | Role cannot be escalated via payload | PASS | `extra="forbid"` schema rejects unknown `role` field |
| **A02 Cryptographic Failures** | Passwords Argon2id (64 MiB, 3 iter, 4 lanes) | PASS | `ownerai/security.py:21-27` |
| | Templates AES-256-GCM | PASS | `ownerai/crypto.py` |
| | Secrets never in logs/responses/bundles | PASS | `RedactingFilter`, `SecretStr`, test `test_secrets_are_not_embedded_in_the_static_assets` |
| **A03 Injection** | SQL via bound parameters / ORM only | PASS | SQLAlchemy ORM, no string concatenation |
| | Path traversal in snapshot/clip download | PASS | `_resolve_image` realpath containment check in `legacy.py` |
| **A04 Insecure Design** | Owner-only consent model | PASS | `consent: true` required for enrolment; strangers stay anonymous |
| **A05 Security Misconfiguration** | Production fail-safe (secret, HTTPS, HSTS, trusted hosts) | PASS | `settings.py:_validate_environment` |
| | Strict CSP, no unsafe-inline/eval | PASS | `middleware.py:_csp` |
| **A06 Identification/Auth Failures** | Argon2id, session rotation, lockout after 5 failures | PASS | `security.py`, `sessions.py` |
| | Generic login errors (no enumeration) | PASS | Identical messages for unknown account / wrong password |
| **A07 Software/Data Failures** | Body size cap (8 MiB) before parse | PASS | `RequestBodyLimitMiddleware` |
| | Rate limits (login 5/300s, register 3/3600s, ...) | PASS | `ratelimit.py` |
| **A08 Software/Data Failures** | CI/CD secret via GitHub Secrets only | PASS | `security.yml` uses `${{ secrets.* }}`, nothing committed |
| **LLM01 Prompt Injection** | Camera/OCR/event text wrapped as untrusted data | PASS | `wrap_untrusted`, `<camera_context>`/`<user_input>` |
| **LLM02 Insecure Output Handling** | Output validated, no raw HTML | PASS | `ResponseValidator` strips artificial prefixes |
| **LLM07 Insecure Plugin Design** | SafeToolRegistry allow-list + confirmation | PASS | `TOOL_SPECS`, `mutating` flag, `confirmed=True` required |
| **LLM08 Excessive Agency** | Mutating tools need owner confirmation + result verify | PASS | `execute_tool` requires `confirmed`; snapshot verifies file exists |

---

## Accepted risks (with reason)

| ID | Risk | Reason accepted |
|----|------|-----------------|
| F-002 | IP spoofing via `X-Forwarded-For` | Only dangerous if `OWNERAI_TRUST_PROXY_HEADERS=true` is misconfigured; documentation warns against it |
| F-003 | vite/esbuild advisories | Dev/build tools only; not shipped to production; `web/` not live |
| F-004 | SHA-256 key derivation | Single-owner deployment; templates additionally protected by AES-GCM authentication |
| F-006 | Scans not run locally | No network in this environment; CI workflow added for when network is available |

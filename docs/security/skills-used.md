# Security Skills Used — Aegis AI

## Decision: Community skill library NOT installed

**Repo:** `mukul975/Anthropic-Cybersecurity-Skills` (community project, NOT published by Anthropic)

**Status:** Not installed. No skills were added from this repository.

**Reason:** The master prompt requires reading each `SKILL.md` *before* installing any skill, and installing only defensive skills (secure coding, appsec, API security, cloud/container config, secrets management, DevSecOps, detection and monitoring), with a pinned commit. This environment has no outbound network access (pip-audit and npm registry are unreachable), so the `mukul975/Anthropic-Cybersecurity-Skills` repository cannot be cloned and its `SKILL.md` files cannot be read. Installing without reading the source would violate the untrusted-code rule, so the library is deliberately excluded.

## What would be installed (when network is available)

If network access is restored, the following defensive skills would be considered — one at a time, each after reading its `SKILL.md`, with the commit pinned:

| Skill (candidate) | Category | Why | Pin |
|---|---|---|---|
| secure-coding | Secure coding | Review new Aegis AI feature code for injection, path traversal, insecure deserialization | TBD after reading SKILL.md |
| appsec | Application security | Review authentication, session, CSRF, CORS handling | TBD |
| api-security | API security | Review tool allow-list, argument validation, rate limiting | TBD |
| secrets-management | Secrets management | Verify no secrets in code, logs, client bundles | TBD |
| cloud-container-config | Cloud/container config | Review Dockerfile, compose, non-root user, TLS defaults | TBD |
| devsecops | DevSecOps | Review CI security workflow, secret handling via GitHub Secrets | TBD |
| detection-monitoring | Detection & monitoring | Review audit log, tamper-evident logging, health probes | TBD |

**Skills explicitly NOT installed (offensive):** Any skill whose `SKILL.md` describes exploitation, fuzzing against third-party targets, or offensive techniques. Per the master prompt, no skill is ever used to attack a system the owner does not own.

## Installed security tooling (this repo)

| Tool | Purpose | Status |
|------|---------|--------|
| `ruff` | Python lint + SAST (E, F, W, B, S, C4, I rules) | Clean — `python -m ruff check ownerai tests app.py` |
| `bandit` | Python SAST for insecure patterns | Clean — `python -m bandit -r ownerai -q` |
| `pip-audit` | Python dependency vulnerability scan | Not run — no network to PyPI (recorded as limitation) |
| `npm audit` | Frontend dependency audit | Run — 2 dev-build advisories (see findings.md) |
| GitHub Actions `.github/workflows/security.yml` | CI: pip-audit, ruff+bandit, npm-audit | Added |

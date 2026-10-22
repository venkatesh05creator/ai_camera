# Threat Model & Security Controls

## 1. System Assets & Sensitivity Classification

| Asset | Sensitivity | Threat Vectors | Safeguards |
|---|---|---|---|
| **Biometric Templates** | High (Critical) | Exfiltration, unauthorized identification, database dump | AES-256-GCM encrypted at rest; decrypted in-memory only; purged upon consent withdrawal. |
| **Camera Credentials** | High | SSRF, credential stuffing, stream interception | AES-256-GCM encryption; SSRF IP destination allow-listing; no raw secrets returned in API. |
| **User Passwords** | High | Brute-force, dictionary attacks, hash reversal | Argon2id (64MB memory, 2 iterations, 16B salt); account lockout after 5 consecutive failures. |
| **Video Streams & Snapshots** | Medium-High | Unauthorized eavesdropping, link sharing | JWT stream authentication; short-lived signed URLs; loopback binding in development. |
| **Audit Logs** | Medium | Log tampering, history repudiation | Append-only database table; actor, IP, timestamp, and outcome recorded. |

---

## 2. Privacy Threat Mitigations

1. **Mass Surveillance Prevention:** The system specifically disables stranger indexing. Detected individuals who have not explicitly granted enrollment consent are tagged only with ephemeral, session-scoped tracker IDs (e.g. `TRK-003`) that are periodically pruned.
2. **Biometric Self-Determination:** Biometric templates cannot be stored without an explicit, recorded `ConsentRecord` carrying a timestamp, scope, and notice version.
3. **Voluntary Demographic Data:** Age and gender are recorded as user-entered profile attributes and are **never inferred** from video feeds.
4. **Tenant Isolation:** Every camera, event, and identity is bound to a verified owner ID, preventing Insecure Direct Object References (IDOR/BOLA).

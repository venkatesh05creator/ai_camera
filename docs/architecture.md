# Cross-Platform AI Surveillance Platform — Architecture Specification

## 1. Core Privacy Architecture

The central architectural tenet of this system is:
> **Detect everyone, identify only consenting enrolled people, and keep everyone else anonymous.**

1. **Anonymous Multi-Object Tracking:** Every detected person is initially assigned a temporary, session-scoped tracker ID (e.g. `TRK-001`). This ID is ephemeral and is never mapped to a persistent demographic or stranger profile.
2. **Consent-Gated Biometric Verification:** Face recognition is restricted to comparing detected faces against authorized biometric templates enrolled with an active, unwithdrawn `ConsentRecord`.
3. **Voluntary Demographic Data:** Age and gender are recorded strictly as voluntary user-entered profile attributes and are **never inferred** from video feeds.
4. **Immediate Deletion on Consent Withdrawal:** When consent is withdrawn, all associated biometric templates (`FaceTemplate`) are immediately purged and overwritten.

---

## 2. System Architecture & Component Diagram

```
+--------------------------------------------------------------------------+
|                          Application Clients                             |
|  - Web Dashboard (React + TypeScript + Vite)                             |
|  - Windows Desktop Application (Tauri / Python Bridge)                   |
|  - Mobile Nodes (Flutter Android / iOS)                                  |
+--------------------------------------------------------------------------+
                                     |
                                     v [HTTPS / WSS]
+--------------------------------------------------------------------------+
|                         Secure API Gateway                               |
|  - FastAPI (Python 3.13)                                                 |
|  - Argon2id Password Hashing + JWT Sessions                              |
|  - Role-Based Access Control (Owner, Admin, Operator, Viewer)            |
|  - Rate Limiting + Content-Security-Policy                               |
+--------------------------------------------------------------------------+
          |                         |                         |
          v                         v                         v
+-------------------+     +-------------------+     +-------------------+
|  Camera Service   |     |  Inference Worker |     |   Event Service   |
| - Webcams (Index) |     | - Motion (MOG2)   |     | - Alert Dispatch  |
| - RTSP / IP Feeds |     | - Tracker (IOU)   |     | - Review Queue    |
| - Mobile Streams  |     | - FaceNet TFLite  |     | - Reports Engine  |
+-------------------+     +-------------------+     +-------------------+
          |                         |                         |
          +-------------------------+-------------------------+
                                    |
                                    v
+--------------------------------------------------------------------------+
|                           Data Storage Layer                             |
|  - SQLite / PostgreSQL (System of Record)                                |
|  - AES-256-GCM Encrypted Biometric Store                                 |
|  - Local Encrypted Snapshot Storage                                      |
+--------------------------------------------------------------------------+
```

---

## 3. Data Flow Lifecycle

1. **Camera Ingestion:** `CameraStreamManager` establishes a low-latency connection to laptop webcams, RTSP streams, or mobile camera streams.
2. **Motion & Person Detection:** `MotionDetector` isolates dynamic bounding boxes; `PersonDetector` identifies human silhouettes and face ROIs.
3. **Anonymous Tracking:** `AnonymousTracker` computes centroid movement and assigns persistent `TRK-xxx` identifiers across frames.
4. **Consent-Gated Verification:** For each face crop, `FaceVerifier` checks active consent records in the database, decrypts matching AES-256-GCM templates in memory, and performs cosine similarity comparison.
5. **Event Emission:**
   - If match $\ge$ threshold $\rightarrow$ Event recorded with `person_id` and verified name.
   - If unknown $\rightarrow$ Event recorded with `person_id = NULL` and anonymous `track_id`.
6. **Live Stream Delivery:** The annotated feed is broadcast over MJPEG (`/api/v1/stream/mjpeg/{camera_id}`) and telemetry over WebSockets (`/api/v1/stream/ws`).

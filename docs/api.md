# API Specification — Version 1.0 (`/api/v1`)

All endpoints require JWT Bearer Authentication (`Authorization: Bearer <token>`) except `/auth/login` and `/auth/register`.

---

## 1. Authentication (`/api/v1/auth`)

| Method | Endpoint | Request Body | Description |
|---|---|---|---|
| `POST` | `/auth/register` | `{ email, password, display_name, role }` | Register a new user (first user becomes `owner`). |
| `POST` | `/auth/login` | `{ email, password }` | Authenticate with Argon2id; returns JWT access token. |
| `GET` | `/auth/me` | None | Returns profile and permissions of authenticated user. |

---

## 2. Camera Management (`/api/v1/cameras`)

| Method | Endpoint | Request Body | Description |
|---|---|---|---|
| `GET` | `/cameras` | None | List accessible cameras with connection status and FPS. |
| `POST` | `/cameras` | `{ name, source_type, location_label, stream_url }` | Register a webcam, RTSP, IP camera, or mobile device. |
| `GET` | `/cameras/{id}` | None | Retrieve specific camera details. |
| `PUT` | `/cameras/{id}` | `{ name, location_label, status, stream_url }` | Update camera configuration. |
| `DELETE` | `/cameras/{id}` | None | Disconnect and unregister camera. |
| `POST` | `/cameras/{id}/snapshot` | None | Capture and save a snapshot to object storage. |

---

## 3. People Directory & Consent (`/api/v1/people`)

| Method | Endpoint | Request Body | Description |
|---|---|---|---|
| `GET` | `/people` | `?q=<name>&status=<enrolled>` | Search directory of enrolled identities. |
| `POST` | `/people` | `{ name, age, gender, role_relationship, notes, contact_details }` | Create profile (age/gender are voluntary, user-provided). |
| `GET` | `/people/{id}` | None | Retrieve profile details and consent status. |
| `PUT` | `/people/{id}` | `{ name, age, gender, notes, contact_details }` | Update person profile. |
| `DELETE` | `/people/{id}` | None | Delete profile and revoke/purge all biometric templates. |
| `POST` | `/people/{id}/consent` | `{ confirm_explicit_consent: true, consent_scope, notice_version }` | Grant explicit verification consent. |
| `POST` | `/people/{id}/withdraw` | None | Withdraw consent; immediately purges biometric templates. |
| `POST` | `/people/{id}/enroll` | `{ image_base64 }` | Extract face embedding and encrypt with AES-256-GCM. |

---

## 4. Detection Events & Alerts (`/api/v1/events` & `/api/v1/alerts`)

| Method | Endpoint | Request Body | Description |
|---|---|---|---|
| `GET` | `/events` | `?camera_id=&event_type=&limit=` | Query chronological detection and motion history. |
| `PUT` | `/events/{id}/review` | `{ review_status: "confirmed" \| "false_positive" }` | Mark event review state. |
| `GET` | `/alerts` | `?status=active` | List actionable alerts. |
| `PUT` | `/alerts/{id}/acknowledge` | None | Acknowledge alert. |
| `PUT` | `/alerts/{id}/resolve` | None | Resolve alert. |

---

## 5. Streaming & Media (`/api/v1/stream`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/stream/mjpeg/{camera_id}` | Live annotated video stream (`multipart/x-mixed-replace`). |
| `GET` | `/stream/snapshot/{filename}` | Retrieve snapshot image. |
| `WS` | `/stream/ws` | WebSocket for real-time live telemetry, heartbeat, and alerts. |

---

## 6. Reports & Audit (`/api/v1/reports` & `/api/v1/audit-logs`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/reports/summary` | Aggregated surveillance KPIs and camera distribution metrics. |
| `GET` | `/reports/export` | Download complete event history as CSV. |
| `GET` | `/audit-logs` | Retrieve immutable security audit trail. |

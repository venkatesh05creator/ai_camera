# Flutter Android & iOS Mobile Application — Architecture & Integration Plan

## 1. Overview & Multi-Role Design
The Flutter mobile application provides a unified cross-platform mobile client for Android and iOS that operates in two primary modes:

1. **Security Operations & Review Client**:
   - Live multi-camera monitoring adapted for handheld viewports (single-camera focused layout with horizontal swipe).
   - Real-time push alert notifications with rich snapshot previews.
   - Quick-action event acknowledgment and false-match correction.
   - Consent-first people directory management.

2. **Authenticated Mobile Camera Node**:
   - Turns any registered smartphone (Android or iOS) into an encrypted wireless camera source feeding into the central inference engine.
   - Secure device registration via QR code cryptographic handshake.
   - Hardware-accelerated H.264 video encoding via native device camera pipelines.

---

## 2. Architecture & Data Flow

```
┌────────────────────────────────────────────────────────┐
│               Flutter App (Android / iOS)              │
│ ┌──────────────────────┐      ┌──────────────────────┐ │
│ │  Mobile Camera Node  │      │  Security Dashboard  │ │
│ │  - camera package    │      │  - Riverpod State    │ │
│ │  - flutter_webrtc    │      │  - flutter_secure_   │ │
│ │  - Battery optimizer │      │    storage           │ │
│ └──────────┬───────────┘      └──────────┬───────────┘ │
└────────────┼─────────────────────────────┼─────────────┘
             │ Encrypted WebRTC Stream     │ REST API / WebSockets
             │ (DTLS-SRTP)                 │ (Bearer Token)
┌────────────▼─────────────────────────────▼─────────────┐
│                 Central FastAPI Backend                │
│             - Ingestion Worker / WebRTC SFU            │
│             - Push Notification Dispatcher (FCM/APNs)  │
└────────────────────────────────────────────────────────┘
```

---

## 3. Key Capabilities & Implementation

### A. Cryptographic Device Enrollment Handshake
To prevent rogue devices from impersonating cameras, a mobile device must be explicitly paired by an administrator:
1. Administrator navigates to **Cameras > Add Camera > Mobile Device** in the web/desktop dashboard.
2. Dashboard displays a one-time cryptographic pairing QR code containing:
   `{"server": "https://surveillance.local:8000", "pairing_token": "PAIR-98a7c2...", "nonce": "xyz"}`
3. The Flutter app scans the QR code, generates a hardware-backed keypair in the device's Secure Enclave / Android Keystore, and calls `POST /api/v1/mobile-devices/register`.
4. The server registers the device in the `mobile_devices` table and issues a scoped, revokable device token.

### B. Mobile Camera Streaming Pipeline
- Utilizes `flutter_webrtc` (WebRTC) for sub-second latency streaming over Wi-Fi or 5G.
- Fallback to lightweight MJPEG / RTSP over TLS if WebRTC is firewalled.
- Automatically adjusts video bitrate (720p @ 15fps or 1080p @ 30fps) based on network conditions and thermal throttling.

### C. Push Notifications (FCM & APNs)
- Integrated via `firebase_messaging` on Android and native APNs on iOS.
- Delivers actionable alert payloads with priority flags:
  ```json
  {
    "notification": {
      "title": "Restricted Area Motion",
      "body": "Unidentified movement detected on North Corridor (TRK-084)"
    },
    "data": {
      "camera_id": "cam-102",
      "event_id": "ev-591a",
      "severity": "high",
      "snapshot_url": "https://surveillance.local:8000/api/v1/stream/snapshot/snap_591a.jpg"
    }
  }
  ```

### D. Consent-Based Mobile Enrollment Wizard
Allows enrolling members of an organization or household directly from a smartphone:
1. **Voluntary Profile Details**: Self-reported name, optional self-reported age and gender (never AI-inferred).
2. **Camera Selfie Capture**: Guides subject with face detection framing guidelines.
3. **Explicit Digital Consent Checkbox**: Displays legal notice version and scope. Requires user signature/toggle.
4. **Local Verification Check**: Generates 512-dim embedding, encrypts via AES-256-GCM, and uploads to `/api/v1/people/{id}/enroll`.

---

## 4. Flutter Dependencies (`pubspec.yaml`)

```yaml
name: surveillance_mobile
description: Cross-platform AI Surveillance Client & Mobile Camera Node
version: 2.0.0+1

environment:
  sdk: ">=3.2.0 <4.0.0"

dependencies:
  flutter:
    sdk: flutter
  flutter_riverpod: ^2.5.1
  dio: ^5.4.1
  flutter_secure_storage: ^9.0.0
  camera: ^0.10.5+9
  flutter_webrtc: ^0.9.48
  firebase_core: ^2.27.0
  firebase_messaging: ^14.7.19
  mobile_scanner: ^5.0.0
  cached_network_image: ^3.3.1
  intl: ^0.19.0
```

---

## 5. Build & Deployment Commands
```bash
# Android APK / App Bundle
flutter build apk --release --obfuscate --split-debug-info=./build/debug-info

# iOS IPA
flutter build ipa --release --obfuscate --split-debug-info=./build/debug-info
```

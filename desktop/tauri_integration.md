# Tauri Windows Desktop Application — Architecture & Integration Plan

## 1. Overview & Purpose
The Windows desktop application provides an ultra-lightweight, native OS desktop shell around the React + TypeScript surveillance dashboard using **Tauri v2**. Unlike resource-heavy Electron apps (which package an entire Chromium browser and Node runtime per window), Tauri utilizes the native Windows **WebView2** runtime and a compiled Rust backend.

This achieves:
- **Tiny binary footprint** (~8–15 MB installer vs 120+ MB for Electron).
- **Minimal RAM consumption** (~35 MB idling vs 250+ MB).
- **Controlled native hardware access**: Restricted, auditable Rust commands for local USB webcams, tray minimization, and Windows Action Center toast notifications.

---

## 2. Security & Least Privilege Architecture

### Principle of Narrow Permissions
In accordance with Section 1 of the specification:
> *"Use a narrowly permissioned desktop bridge; never expose unrestricted shell commands to the frontend."*

Tauri's IPC (Inter-Process Communication) bridge is locked down:
- `tauri.conf.json` enables only explicitly allowlisted commands.
- Shell execution (`tauri:shell`) is **strictly disabled**.
- File system access is restricted strictly to user-designated export folders (e.g., `Downloads/SurveillanceReports`).

```
┌────────────────────────────────────────────────────────┐
│                   React + TS Frontend                  │
│     (Vite bundle served from local custom protocol)    │
└───────────────────────────┬────────────────────────────┘
                            │ Tauri IPC (invoke)
┌───────────────────────────▼────────────────────────────┐
│                    Rust Native Bridge                  │
│  - camera_device_list()                                │
│  - show_native_alert(title, body, severity)            │
│  - toggle_tray_minimize()                              │
│  - get_secure_credential(key) via Windows DPAPI        │
└───────────────────────────┬────────────────────────────┘
                            │ Native Windows APIs
┌───────────────────────────▼────────────────────────────┐
│         Windows OS (WebView2, Media Foundation, DPAPI) │
└────────────────────────────────────────────────────────┘
```

---

## 3. Native Windows Capabilities

### A. Windows Media Foundation Camera Bridge
Enumerates connected USB/laptop webcams natively without launching browser permission prompts:
```rust
// desktop/src-tauri/src/camera.rs
#[tauri::command]
pub fn list_local_cameras() -> Result<Vec<CameraDevice>, String> {
    // Queries Windows Media Foundation (IMFActivate) for video capture hardware
    let devices = enumerate_mf_video_devices()?;
    Ok(devices)
}
```

### B. Windows Action Center Push Notifications
When a high-severity event or unreviewed motion is triggered by the backend WebSocket, Tauri dispatches a native Windows Toast notification with interactive "Acknowledge" or "View Feed" buttons.

### C. System Tray Minimization
Closing the monitoring window minimizes it to the Windows notification tray (taskbar notification area) with an icon reflecting current system health (green = all cameras online, red = alert active).

### D. Windows DPAPI Encrypted Local Storage
Server tokens and camera connection secrets stored locally on the Windows machine are encrypted using the Windows **Data Protection API (DPAPI)** via `CryptProtectData`, tying decryption strictly to the logged-in Windows user account.

---

## 4. Tauri Configuration (`tauri.conf.json`)

```json
{
  "productName": "AI Surveillance Studio",
  "version": "2.0.0",
  "identifier": "com.surveillance.desktop",
  "build": {
    "frontendDist": "../../web/dist",
    "devUrl": "http://localhost:5173"
  },
  "app": {
    "windows": [
      {
        "title": "AI Surveillance Studio - Security Center",
        "width": 1440,
        "height": 900,
        "minWidth": 1024,
        "minHeight": 680,
        "resizable": true,
        "fullscreen": false
      }
    ],
    "trayIcon": {
      "iconPath": "icons/tray-normal.png",
      "tooltip": "AI Surveillance Monitoring Active"
    },
    "security": {
      "csp": "default-src 'self' tauri:; connect-src 'self' ws://127.0.0.1:8000 http://127.0.0.1:8000; img-src 'self' data: blob: http://127.0.0.1:8000"
    }
  }
}
```

---

## 5. Build & Distribution Commands
```powershell
# 1. Build the React web frontend
cd web && npm run build && cd ..

# 2. Compile signed Windows desktop executable / MSI installer
cd desktop/src-tauri
cargo tauri build --target x86_64-pc-windows-msvc
```
Outputs an optimized Windows installer at `desktop/src-tauri/target/release/bundle/msi/`.

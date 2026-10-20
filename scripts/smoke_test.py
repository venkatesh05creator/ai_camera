#!/usr/bin/env python3
"""End-to-end smoke test against a real uvicorn server.

    python scripts/smoke_test.py

The script starts the application on a free loopback port, exercises the
public pages, the registration/login flow, the dashboard and the security
headers, and prints a PASS/FAIL line for every step.  It never touches a
production installation - it uses its own throw-away database.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_server(base_url: str, process: subprocess.Popen, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            return False
        try:
            response = httpx.get(f"{base_url}/health", timeout=2.0)
            if response.status_code == 200:
                return True
        except httpx.HTTPError:
            time.sleep(0.4)
    return False


def main() -> int:
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    db_path = Path(tempfile.gettempdir()) / f"ownerai_smoke_{port}.db"

    env = dict(os.environ)
    env.update(
        {
            "OWNERAI_APP_ENV": "test",
            "OWNERAI_SECRET_KEY": "smoke-test-secret-key-0123456789-abcdefghijkl",
            "OWNERAI_BIOMETRIC_ENCRYPTION_KEY": "smoke-biometric-key-0123456789-abcdefgh",
            "OWNERAI_DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
            "OWNERAI_MAILER_BACKEND": "null",
            "OWNERAI_LOG_LEVEL": "WARNING",
        }
    )

    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "ownerai.main:app", "--host", "127.0.0.1", "--port", str(port),
         "--log-level", "warning"],
        cwd=str(ROOT),
        env=env,
    )

    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name}{(' - ' + detail) if detail else ''}")

    try:
        if not wait_for_server(base_url, process):
            print("the server did not start")
            return 1

        with httpx.Client(base_url=base_url, follow_redirects=False) as client:
            landing = client.get("/")
            check("landing page", landing.status_code == 200, f"status {landing.status_code}")
            check(
                "security headers",
                "Content-Security-Policy" in landing.headers
                and landing.headers.get("X-Content-Type-Options") == "nosniff",
            )
            check(
                "CSP forbids inline script",
                "unsafe-inline" not in landing.headers.get("Content-Security-Policy", ""),
            )
            csrf = client.cookies.get("ownerai_csrf")
            check("csrf cookie issued", bool(csrf))

            for path in ["/login", "/register", "/docs", "/forgot-password"]:
                response = client.get(path)
                check(f"page {path}", response.status_code == 200, f"status {response.status_code}")

            private = client.get("/api/devices")
            check("private api requires auth", private.status_code == 401, f"status {private.status_code}")

            registration = client.post(
                "/api/auth/register",
                json={"email": "smoke@example.test", "password": "Smoke-Test-Pass-1!", "display_name": "smoke"},
                headers={"X-CSRF-Token": csrf},
            )
            check("registration", registration.status_code == 201, registration.text[:120])

            no_csrf = client.post("/api/devices", json={"name": "x", "device_type": "webcam"})
            check("state change without csrf is rejected", no_csrf.status_code == 403)

            me = client.get("/api/auth/me")
            check("session works", me.status_code == 200, me.text[:120])

            device = client.post(
                "/api/devices",
                json={"name": "Hallway", "device_type": "webcam", "location_label": "hall"},
                headers={"X-CSRF-Token": client.cookies.get("ownerai_csrf")},
            )
            check("device created", device.status_code == 201, device.text[:120])

            dashboard = client.get("/dashboard")
            check("dashboard renders", dashboard.status_code == 200, f"status {dashboard.status_code}")

            css = client.get("/static/css/app.css")
            check("static assets served", css.status_code == 200)

            secret_leak = "smoke-test-secret-key" in dashboard.text or "smoke-test-secret-key" in css.text
            check("no secret in the client payload", not secret_leak)

            search = client.get("/api/search?q=camera")
            check("search works", search.status_code == 200)

            chat = client.post(
                "/api/chat",
                json={"message": "Which cameras do I have?"},
                headers={"X-CSRF-Token": client.cookies.get("ownerai_csrf")},
            )
            check("assistant answers", chat.status_code == 200, chat.text[:120])

            logout = client.post(
                "/api/auth/logout", headers={"X-CSRF-Token": client.cookies.get("ownerai_csrf")}
            )
            check("logout", logout.status_code == 200)
            after = client.get("/api/auth/me")
            check("session invalidated", after.status_code == 401)

    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            process.kill()
        if db_path.exists():
            try:
                db_path.unlink()
            except OSError:  # pragma: no cover
                pass

    failed = [name for name, ok, _ in results if not ok]
    print("\n{}/{} checks passed.".format(len(results) - len(failed), len(results)))
    if failed:
        print("failed: " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

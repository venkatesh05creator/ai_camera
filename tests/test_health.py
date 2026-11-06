"""Health endpoint reports only real, measured values."""

from __future__ import annotations


def test_healthz_reports_real_metrics(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"]["reachable"] is True
    # latency is a real measurement: a float > 0
    assert float(body["db"]["latency_ms"]) > 0
    assert body["app_env"] == "test"
    assert float(body["uptime_seconds"]) >= 0
    assert body["panic_active"] is False


def test_healthz_is_open(client):
    # health must work without authentication
    resp = client.get("/healthz")
    assert resp.status_code == 200

"""Integration tests for audit logs, retention controls, and reports."""

from fastapi import status
from backend.app.services.audit_service import log_action


def test_audit_log_querying(client, admin_headers, db_session, test_admin_user):
    # Create an audit event
    log_action(
        db=db_session,
        action="camera_registered",
        resource_type="camera",
        actor_user_id=test_admin_user.id,
        resource_id="cam-test-1",
        details={"ip": "127.0.0.1"},
    )

    response = client.get("/api/v1/audit-logs", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    logs = response.json()
    assert len(logs) >= 1
    recent = logs[0]
    assert "action" in recent
    assert "timestamp" in recent


def test_reports_kpis(client, admin_headers):
    response = client.get("/api/v1/reports/summary", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "active_cameras_count" in data
    assert "total_events" in data


def test_retention_sweep_cleans_expired_files(tmp_path):
    import os
    import time
    from backend.app.services.retention_service import clean_directory_by_age

    # Create dummy files: one fresh, one expired (10 days old)
    fresh_file = tmp_path / "fresh_snap.jpg"
    fresh_file.write_bytes(b"fresh image data")

    expired_file = tmp_path / "old_snap.jpg"
    expired_file.write_bytes(b"old image data to clean")
    old_time = time.time() - (10 * 86400)
    os.utime(str(expired_file), (old_time, old_time))

    res = clean_directory_by_age(tmp_path, max_age_days=7)
    assert res["files_removed"] == 1
    assert res["bytes_reclaimed"] > 0
    assert not expired_file.exists()
    assert fresh_file.exists()


def test_retention_sweep_api_endpoint(client):
    response = client.post("/api/v1/system/retention-sweep")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "snapshots" in data
    assert "media" in data
    assert "total_files_removed" in data

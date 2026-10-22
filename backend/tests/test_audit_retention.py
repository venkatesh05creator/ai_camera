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

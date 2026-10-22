"""Integration tests for camera registration, credential encryption, and stream security."""

from fastapi import status
from backend.app.models.entities import Camera


def test_register_camera_with_encrypted_credentials(client, admin_headers, db_session):
    payload = {
        "name": "North Gate CCTV",
        "source_type": "rtsp",
        "location_label": "Building A - Perimeter",
        "stream_url": "rtsp://camera.internal.local:554/live/ch0",
        "connection_secret": "SuperSecretRTSPPassword123!",
    }
    response = client.post("/api/v1/cameras", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "North Gate CCTV"
    assert data["source_type"] == "rtsp"
    assert data["status"] == "online"

    # CRITICAL SECURITY RULE: Connection secret must NEVER be returned in plaintext API responses!
    assert "SuperSecretRTSPPassword123!" not in str(data)
    assert "connection_secret" not in data

    # Verify in DB that it is encrypted at rest using AES-256-GCM
    cam_in_db = db_session.query(Camera).filter_by(id=data["id"]).first()
    assert cam_in_db is not None
    assert cam_in_db.connection_secret_encrypted is not None
    assert cam_in_db.connection_secret_encrypted != "SuperSecretRTSPPassword123!"
    # Verify decryption method returns original secret
    assert cam_in_db.get_decrypted_secret() == "SuperSecretRTSPPassword123!"


def test_stream_unauthorized_rejection(client):
    # Live MJPEG stream without token must be rejected or closed
    response = client.get("/api/v1/stream/mjpeg/non-existent-camera-id")
    # Stream endpoint checks auth or requires token query parameter
    assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_404_NOT_FOUND]


def test_delete_camera_stops_worker_cleanly(client, admin_headers, db_session):
    from backend.app.workers.inference_worker import worker_registry
    from backend.app.services.camera_service import camera_manager

    # 1. Register camera
    payload = {
        "name": "Warehouse Loading Dock",
        "source_type": "webcam",
        "location_label": "Warehouse",
        "stream_url": "0",
    }
    create_resp = client.post("/api/v1/cameras", json=payload, headers=admin_headers)
    assert create_resp.status_code == status.HTTP_201_CREATED
    cam_id = create_resp.json()["id"]

    # 2. Simulate active worker
    worker = worker_registry.get_or_start_worker(cam_id)
    assert worker is not None
    assert cam_id in worker_registry.workers

    # 3. Delete camera via API
    del_resp = client.delete(f"/api/v1/cameras/{cam_id}", headers=admin_headers)
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT

    # 4. Verify worker was cleanly stopped and removed from registry
    assert worker_registry.get_worker(cam_id) is None
    assert worker.is_running is False

    # 5. Verify camera row is gone from DB
    deleted_cam = db_session.query(Camera).filter_by(id=cam_id).first()
    assert deleted_cam is None

    # 6. Verify read_frame on deleted camera does not raise ObjectDeletedError
    frame = camera_manager.read_frame(cam_id)
    assert frame is None


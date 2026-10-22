"""Integration tests for authentication, JWT issuance, and role-based access control."""

from fastapi import status


def test_login_success(client, test_admin_user):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": test_admin_user.email, "password": "AdminSecurePassword123!"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == test_admin_user.email
    assert data["user"]["role"] == "owner"


def test_login_invalid_password(client, test_admin_user):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": test_admin_user.email, "password": "WrongPassword999!"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid" in response.json()["detail"]


def test_unauthenticated_access_rejected(client):
    # Any protected endpoint without Authorization header must return 401
    response = client.get("/api/v1/cameras")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    response = client.get("/api/v1/people")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    response = client.get("/api/v1/audit-logs")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_viewer_role_forbidden_from_admin_actions(client, viewer_headers):
    # Viewer can read cameras
    resp_get = client.get("/api/v1/cameras", headers=viewer_headers)
    assert resp_get.status_code == status.HTTP_200_OK

    # Viewer CANNOT register new cameras (requires admin/owner)
    resp_cam = client.post(
        "/api/v1/cameras",
        json={
            "name": "Unauthorized Cam",
            "source_type": "webcam",
            "location_label": "Restricted Zone",
        },
        headers=viewer_headers,
    )
    assert resp_cam.status_code == status.HTTP_403_FORBIDDEN

    # Viewer CANNOT enroll new persons
    resp_person = client.post(
        "/api/v1/people",
        json={
            "name": "Illegal Profile",
            "age": 25,
            "gender": "Other",
            "role_relationship": "visitor",
        },
        headers=viewer_headers,
    )
    assert resp_person.status_code == status.HTTP_403_FORBIDDEN


def test_admin_can_perform_admin_actions(client, admin_headers):
    # Admin can list cameras
    resp_cam = client.get("/api/v1/cameras", headers=admin_headers)
    assert resp_cam.status_code == status.HTTP_200_OK

    # Admin can list people
    resp_people = client.get("/api/v1/people", headers=admin_headers)
    assert resp_people.status_code == status.HTTP_200_OK

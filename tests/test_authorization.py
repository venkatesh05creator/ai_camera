"""Authorisation, IDOR and privilege escalation tests."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from ownerai.db import get_engine
from ownerai.models import Conversation, Device, Role, User

from .conftest import auth_headers, create_user


def _create_device(client, name="Living room") -> int:
    response = client.post(
        "/api/devices",
        json={"name": name, "device_type": "webcam", "location_label": "hall"},
        headers=auth_headers(client),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_unauthenticated_users_cannot_access_private_apis(client):
    for method, path in [
        ("get", "/api/devices"),
        ("get", "/api/events"),
        ("get", "/api/identities"),
        ("get", "/api/chat/conversations"),
        ("get", "/api/auth/me"),
        ("get", "/api/admin/users"),
        ("get", "/api/admin/audit"),
    ]:
        response = getattr(client, method)(path)
        assert response.status_code == 401, f"{path} returned {response.status_code}"


def test_anonymous_search_only_returns_public_documentation(client):
    """Search is available to anonymous visitors but never leaks private data."""
    response = client.get("/api/search?q=owner")
    assert response.status_code == 200
    hits = response.json()["hits"]
    assert all(hit["type"] == "help" for hit in hits)


def test_a_user_cannot_read_another_users_device(client, viewer):
    """IDOR: changing the object id must not expose foreign data."""
    other_id = create_user("other@example.test", role="trusted")
    with Session(get_engine()) as session:
        device = Device(owner_id=other_id, name="Secret camera", device_type="ip_camera")
        session.add(device)
        session.commit()
        device_id = device.id

    assert viewer.get(f"/api/devices/{device_id}").status_code == 404
    assert viewer.patch(
        f"/api/devices/{device_id}", json={"name": "hijacked"}, headers=auth_headers(viewer)
    ).status_code == 404
    assert viewer.delete(f"/api/devices/{device_id}", headers=auth_headers(viewer)).status_code == 404
    assert viewer.get(f"/api/devices/{device_id}/events").status_code == 404
    assert viewer.post(
        f"/api/devices/{device_id}/events", json={"kind": "motion"}, headers=auth_headers(viewer)
    ).status_code == 404


def test_a_user_cannot_read_another_users_conversation(client, viewer):
    other_id = create_user("other2@example.test", role="trusted")
    with Session(get_engine()) as session:
        conversation = Conversation(owner_id=other_id, title="Private chat")
        session.add(conversation)
        session.commit()
        conversation_id = conversation.id

    assert viewer.get(f"/api/chat/conversations/{conversation_id}/messages").status_code == 404
    assert viewer.delete(
        f"/api/chat/conversations/{conversation_id}", headers=auth_headers(viewer)
    ).status_code == 404


def test_a_user_cannot_see_another_users_events_in_the_event_feed(client, viewer):
    other_id = create_user("other3@example.test", role="trusted")
    with Session(get_engine()) as session:
        device = Device(owner_id=other_id, name="Foreign camera", device_type="webcam")
        session.add(device)
        session.commit()
        from ownerai.models import CameraEvent

        event = CameraEvent(device_id=device.id, owner_id=other_id, kind="motion", summary="secret")
        session.add(event)
        session.commit()

    events = viewer.get("/api/events").json()
    assert all(item["summary"] != "secret" for item in events)


def test_registration_cannot_escalate_the_role(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "escalate@example.test", "password": "Correct-Horse-9!", "role": Role.OWNER.value},
        headers=auth_headers(client),
    )
    assert response.status_code == 422
    with Session(get_engine()) as session:
        assert session.query(User).filter(User.email == "escalate@example.test").count() == 0


def test_a_user_cannot_change_their_own_role(client, admin_user):
    with Session(get_engine()) as session:
        admin = session.query(User).filter(User.email == "admin@example.test").one()
        admin_id = admin.id

    response = admin_user.patch(
        f"/api/admin/users/{admin_id}/role",
        json={"role": "owner"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 403


def test_an_administrator_cannot_grant_the_owner_role(client, admin_user):
    target_id = create_user("target@example.test", role="viewer")
    response = admin_user.patch(
        f"/api/admin/users/{target_id}/role",
        json={"role": "owner"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 403


def test_an_owner_can_grant_a_lower_role(client, owner):
    target_id = create_user("target2@example.test", role="viewer")
    response = owner.patch(
        f"/api/admin/users/{target_id}/role",
        json={"role": "trusted"},
        headers=auth_headers(owner),
    )
    assert response.status_code == 200
    with Session(get_engine()) as session:
        user = session.get(User, target_id)
        assert user.role == "trusted"


def test_admin_endpoints_are_forbidden_for_regular_users(client, viewer):
    for path in ["/api/admin/users", "/api/admin/audit", "/api/admin/contacts", "/api/admin/stats"]:
        assert viewer.get(path).status_code == 403, path


def test_a_viewer_cannot_create_a_device(client, viewer):
    response = viewer.post(
        "/api/devices", json={"name": "cam", "device_type": "webcam"}, headers=auth_headers(viewer)
    )
    assert response.status_code == 403


def test_a_trusted_user_can_manage_their_own_devices(client, trusted):
    device_id = _create_device(trusted, "Phone camera")
    response = trusted.patch(
        f"/api/devices/{device_id}", json={"status": "paused"}, headers=auth_headers(trusted)
    )
    assert response.status_code == 200
    assert response.json()["status"] == "paused"


def test_only_the_owner_of_a_device_can_delete_it(client, owner, trusted):
    """Ownership is checked before the permission - a foreign device is a 404."""
    device_id = _create_device(trusted, "Wearable")
    assert trusted.delete(f"/api/devices/{device_id}", headers=auth_headers(trusted)).status_code == 403
    assert owner.delete(f"/api/devices/{device_id}", headers=auth_headers(owner)).status_code == 404


def test_search_never_returns_another_users_data(client, viewer):
    other_id = create_user("other4@example.test", role="trusted")
    with Session(get_engine()) as session:
        device = Device(owner_id=other_id, name="Confidential camera", device_type="webcam")
        session.add(device)
        session.commit()

    hits = viewer.get("/api/search?q=Confidential").json()
    assert hits["total"] == 0
    assert all("Confidential" not in hit["title"] for hit in hits["hits"])


def test_websocket_requires_authentication(client):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/events") as websocket:
            websocket.receive_json()


def test_websocket_allows_the_owner_to_subscribe_to_its_own_devices(client, owner):
    device_id = _create_device(owner, "Desk camera")
    with owner.websocket_connect("/ws/events") as websocket:
        websocket.send_json({"action": "subscribe", "device_ids": [device_id]})
        message = websocket.receive_json()
    assert message["type"] == "subscribed"
    assert message["device_ids"] == [device_id]


def test_websocket_refuses_foreign_devices(client, owner, viewer):
    """The subscription list is filtered on the server."""
    device_id = _create_device(owner, "Owner camera")
    with viewer.websocket_connect("/ws/events") as websocket:
        websocket.send_json({"action": "subscribe", "device_ids": [device_id]})
        message = websocket.receive_json()
    assert message["type"] == "subscribed"
    assert message["device_ids"] == []

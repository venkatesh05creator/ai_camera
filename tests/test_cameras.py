"""Phase 4: vision pipeline, registry, HMAC ingest, snapshots, retention."""

from __future__ import annotations

from datetime import UTC

OWNER = "owner@example.com"
PASSWORD = "correct horse battery staple"


def bootstrap(client):
    resp = client.post("/api/auth/bootstrap", json={
        "email": OWNER, "password": PASSWORD, "display_name": "Venki"})
    assert resp.status_code == 201
    return client


def authed(client):
    bootstrap(client)
    assert client.post("/api/auth/login", json={
        "email": OWNER, "password": PASSWORD}).status_code == 200
    return client


def csrf(client):
    return client.cookies.get("aegis_csrf", "")


def make_camera(client, kind="phone", source="pixel-phone"):
    resp = client.post("/api/cameras", json={
        "name": f"Test {kind}", "kind": kind, "source": source},
        headers={"X-CSRF-Token": csrf(client)})
    assert resp.status_code == 201, resp.text
    return resp.json()


# ------------------------------------------------------------------- vision
def test_motion_gate_detects_change():
    import cv2
    import numpy as np

    from backend.app.vision.pipeline import motion_score

    def blank(v):
        return np.full((100, 100, 3), v, np.uint8)

    def grey(f):
        return cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)

    a, b = blank(100), blank(100)
    assert motion_score(grey(a), grey(b)) == 0.0
    b[20:40, 20:40] = 200
    assert motion_score(grey(a), grey(b)) > 0.0


def test_pipeline_gates_detection_on_motion():
    import numpy as np

    from backend.app.vision.pipeline import FrameProcessor

    calls = []

    class Det:
        def detect(self, frame):
            calls.append(1)
            return tuple()

    p = FrameProcessor(detector=Det())
    still = np.full((100, 100, 3), 128, np.uint8)
    for i in range(3):
        v = p.process(still.copy(), now=float(i))
        assert v.persons == 0
    assert calls == []  # detector never ran on a static scene

    moved = still.copy()
    moved[10:90, 10:90] = 240
    v = p.process(moved, now=3.0)
    assert v.motion_score > 0
    assert calls == [1]  # exactly one gated detection


def test_blur_boxes_only_touches_boxes():
    import numpy as np

    from backend.app.vision.pipeline import blur_boxes

    frame = np.zeros((100, 200, 3), np.uint8)
    frame[:, 150:] = 255  # white area must survive untouched
    frame[10:60, 10:35] = 0        # box region: hard left/right edge
    frame[10:60, 35:60] = 255
    out = blur_boxes(frame, [(10, 10, 50, 50)])
    assert (out[:, 150:] == 255).all()           # outside box: untouched
    region = out[10:60, 10:60]
    assert (((region > 0) & (region < 255)).any())  # edge smeared by blur


def test_synthetic_person_frame_encodes_and_withholds():
    import numpy as np

    from backend.app.vision.pipeline import FrameProcessor

    class OnePerson:
        def detect(self, frame):
            return ((30, 30, 80, 160),)

    p = FrameProcessor(detector=OnePerson())
    frame = np.full((480, 640, 3), 90, np.uint8)
    verdict = p.process(frame, now=0.0)
    # first frame: no previous frame => no motion => no detection (honest)
    assert verdict.persons == 0
    moved = frame.copy()
    moved[100:300, 200:400] = 220
    verdict = p.process(moved, now=1.0)
    assert verdict.persons == 1
    event = p.make_event(moved, verdict, now=1.0)
    # no real face can be found on synthetic art: must withhold, not store
    assert event.snapshot_jpeg is None
    assert event.snapshot_status == "withheld-no-detector"


# ----------------------------------------------------------------- registry
def test_rtsp_private_hosts_blocked_by_ssrf(client):
    authed(client)
    resp = client.post("/api/cameras", json={
        "name": "lan-cam", "kind": "rtsp",
        "source": "rtsp://192.168.1.50:554/stream"},
        headers={"X-CSRF-Token": csrf(client)})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ssrf_blocked"


def test_token_shown_once(client):
    authed(client)
    cam = make_camera(client)
    assert cam["token"]

    listing = client.get("/api/cameras")
    row = [c for c in listing.json() if c["id"] == cam["id"]][0]
    assert "token" not in row  # never served again
    assert row["enabled"] is True
    assert row["running"] is False  # honest: workers start on demand


def test_camera_requires_owner_role(client):
    authed(client)
    import asyncio

    from backend.app.db import get_session_factory
    from backend.app.models.user import Role
    from backend.app.models.user import User as UserModel
    from backend.app.security import passwords

    factory = get_session_factory()

    async def add_viewer():
        async with factory() as session:
            session.add(UserModel(
                email="viewer@example.com", display_name="Viewer",
                password_hash=passwords.hash_password("a-long-viewer-passphrase"),
                role=Role.VIEWER.value))
            await session.commit()
    asyncio.run(add_viewer())

    assert client.post("/api/auth/login", json={
        "email": "viewer@example.com",
        "password": "a-long-viewer-passphrase"}).status_code == 200
    test_channels = client.post("/api/cameras", json={
        "name": "v", "kind": "webcam", "source": "0"},
        headers={"X-CSRF-Token": csrf(client)})
    assert test_channels.status_code == 403


# ------------------------------------------------------------------- ingest
def _jpeg_bytes():
    import cv2
    import numpy as np
    ok, buf = cv2.imencode(".jpg", np.full((60, 80, 3), 90, np.uint8))
    assert ok
    return buf.tobytes()


def _headers(camera_id, raw_token, body, *, ts=None, nonce=None):
    import uuid
    from datetime import datetime

    from backend.app.services.camera_service import compute_signature

    ts = ts or datetime.now(UTC).isoformat()
    nonce = nonce or uuid.uuid4().hex
    sig = compute_signature(raw_token, camera_id, ts, nonce, body)
    return {
        "X-Camera-Token": raw_token,
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "X-Signature": sig,
    }, nonce


def test_ingest_accepts_valid_frame(client, monkeypatch):
    authed(client)
    cam = make_camera(client)

    import backend.app.routers.cameras as cams_router
    from backend.app.vision.pipeline import FrameVerdict

    class StubProc:
        def process(self, frame, *, now):
            return FrameVerdict(0.5, 0, ())

    monkeypatch.setattr(cams_router, "FrameProcessor",
                        lambda *a, **kw: StubProc())
    body = _jpeg_bytes()
    headers, _nonce = _headers(cam["id"], cam["token"], body)
    resp = client.post(f"/api/cameras/{cam['id']}/frame",
                       content=body, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["persons"] == 0

    # replay the exact same frame: same headers, nonce already spent -> 409
    replay = client.post(f"/api/cameras/{cam['id']}/frame",
                         content=body, headers=headers)
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "replay"


def test_ingest_rejects_bad_signature_token_and_stale_ts(client):
    authed(client)
    cam = make_camera(client)
    body = _jpeg_bytes()

    headers, _ = _headers(cam["id"], cam["token"], body)
    bad_sig = dict(headers, **{"X-Signature": "deadbeef"})
    resp = client.post(f"/api/cameras/{cam['id']}/frame",
                       content=body, headers=bad_sig)
    assert resp.status_code == 401

    headers2, _ = _headers(cam["id"], "wrong-token", body)
    resp = client.post(f"/api/cameras/{cam['id']}/frame",
                       content=body, headers=headers2)
    assert resp.status_code == 401

    from datetime import datetime, timedelta
    old = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    headers3, _ = _headers(cam["id"], cam["token"], body, ts=old)
    resp = client.post(f"/api/cameras/{cam['id']}/frame",
                       content=body, headers=headers3)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "stale_timestamp"


def test_person_event_stores_encrypted_blurred_snapshot(client, monkeypatch):
    authed(client)
    cam = make_camera(client)

    import backend.app.routers.cameras as cams_router
    import backend.app.vision.pipeline as pipe
    from backend.app.vision.pipeline import FrameVerdict

    class PersonProc:
        def process(self, frame, *, now):
            return FrameVerdict(0.9, 2, ((10, 10, 40, 90), (100, 10, 40, 90)))

        def make_event(self, frame, verdict, *, now):
            return pipe.PersonEvent(verdict.persons, verdict.motion_score,
                                    frame.tobytes()[:4] and b"\xff\xd8fake",
                                    "stored")

    monkeypatch.setattr(cams_router, "FrameProcessor",
                        lambda *a, **kw: PersonProc())
    body = _jpeg_bytes()
    headers, _ = _headers(cam["id"], cam["token"], body)
    resp = client.post(f"/api/cameras/{cam['id']}/frame",
                       content=body, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["persons"] == 2

    events = client.get(f"/api/cameras/{cam['id']}/events")
    assert events.status_code == 200
    items = events.json()["items"]
    assert len(items) == 1 and items[0]["kind"] == "person"
    assert items[0]["snapshot_status"] == "stored"
    event_id = items[0]["id"]

    # ciphertext at rest (never the raw image bytes)
    import asyncio

    from sqlalchemy import text as sql_text

    from backend.app.db import get_session_factory

    async def read_raw():
        async with get_session_factory()() as session:
            return (await session.execute(sql_text(
                "SELECT snapshot_encrypted FROM camera_events WHERE id=:i"),
                {"i": event_id})).scalar_one()

    encrypted = asyncio.run(read_raw())
    assert encrypted and not encrypted.startswith("/9j")  # not raw JPEG b64

    snap = client.get(f"/api/cameras/{cam['id']}/events/{event_id}/snapshot")
    assert snap.status_code == 200
    assert snap.content[:2] == b"\xff\xd8"  # decrypts to a JPEG seed

    notifs = client.get("/api/notifications")
    assert notifs.json()["unread"] >= 1


# ---------------------------------------------------------------- retention
def test_retention_purge_respects_per_camera_cutoff(client):
    authed(client)
    cam = make_camera(client)

    import asyncio

    from sqlalchemy import text as sql_text

    from backend.app.db import get_session_factory

    async def seed():
        async with get_session_factory()() as session:
            await session.execute(sql_text(
                "INSERT INTO camera_events (camera_id, ts, kind, person_count,"
                " motion_score, snapshot_status) VALUES (:c,"
                " '2000-01-01 00:00:00', 'person', 1, 0.5, 'withheld')"),
                {"c": cam["id"]})
            await session.execute(sql_text(
                "INSERT INTO camera_events (camera_id, ts, kind, person_count,"
                " motion_score, snapshot_status) VALUES (:c,"
                " datetime('now'), 'person', 1, 0.5, 'withheld')"),
                {"c": cam["id"]})
            await session.commit()
    asyncio.run(seed())

    resp = client.post("/api/cameras/purge",
                       headers={"X-CSRF-Token": csrf(client)})
    assert resp.status_code == 200
    events = client.get(f"/api/cameras/{cam['id']}/events").json()
    assert all("2000" not in i["ts"] for i in events["items"])
    assert events["count"] == 1  # only the recent one survives

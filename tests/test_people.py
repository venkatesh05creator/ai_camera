"""Phase 5: consent enrolment, encrypted templates, unknown-never-named,
delete-on-withdraw. The face engine is faked deterministically here."""

from __future__ import annotations

OWNER = "owner@example.com"
PASSWORD = "correct horse battery staple"
CONSENT = "I, the account owner, give consent for this device to store an encrypted face template under my name"


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


# --------------------------------------------------------- fake face engine
class FakeEngine:
    """Deterministic embeddings: each 'person' maps to a fixed color."""

    PALETTE = {"venki": (0.0, 0.0, 255.0), "other": (0.0, 255.0, 0.0)}

    def __init__(self, vectors: dict | None = None):
        # name -> embedding (length 512)
        self.vectors = vectors or {}

    def read_faces(self, frame):
        import numpy as np

        from backend.app.vision.face import FaceReading

        label = None
        try:
            got = np.asarray(frame, dtype=np.float32).mean(axis=(0, 1))
            best, best_dist = None, 1e9
            for name, color in self.PALETTE.items():
                dist = float(np.linalg.norm(got - np.array(color)))
                if dist < best_dist:
                    best, best_dist = name, dist
            if best_dist < 40:  # survives JPEG lossy compression
                label = best
        except Exception:
            label = None
        if not label or label not in self.vectors:
            return []
        return [FaceReading(box=(0, 0, 80, 80),
                            embedding=self.vectors[label].copy(),
                            quality=0.99)]

    @staticmethod
    def average(samples):
        import numpy as np
        stacked = np.stack(samples)
        mean = stacked.mean(axis=0)
        norm = float(np.linalg.norm(mean))
        return mean / norm


def vec(seed: int):
    import numpy as np
    rng = np.random.default_rng(seed)
    v = rng.normal(size=512).astype(np.float32)
    return v / np.linalg.norm(v)


def jpeg_with_label(label: str) -> str:
    import base64

    import cv2
    import numpy as np

    color = FakeEngine.PALETTE.get(label, (0.0, 0.0, 0.0))
    frame = np.full((120, 120, 3), color, np.uint8)
    ok, buf = cv2.imencode(".jpg", frame)
    assert ok
    return base64.b64encode(buf.tobytes()).decode()


def install_fake_engine(monkeypatch, workers=None):
    vectors = {"venki": vec(1), "other": vec(2)}
    engine = FakeEngine(vectors)

    import backend.app.services.people_service as ps
    import backend.app.vision.face as face_mod

    monkeypatch.setattr(ps, "get_engine", lambda settings: engine)
    monkeypatch.setattr(face_mod, "get_engine",
                        lambda settings: engine)
    return engine


# ------------------------------------------------------------------ consent
def test_enrol_requires_consent_first(client):
    authed(client)
    resp = client.post("/api/people", json={
        "name": "Nobody", "consent_text": "short"}, headers={"X-CSRF-Token": csrf(client)})
    assert resp.status_code == 422

    resp = client.post("/api/people", json={
        "name": "Venki", "consent_text": CONSENT},
        headers={"X-CSRF-Token": csrf(client)})
    assert resp.status_code == 201
    body = resp.json()
    assert body["has_template"] is False  # consent alone grants nothing

    # list never leaks template bytes
    listing = client.get("/api/people")
    assert listing.status_code == 200
    row = [p for p in listing.json()["people"] if p["id"] == body["id"]][0]
    assert "embedding" not in str(row).lower()


def test_enrol_identify_and_withdraw_flow(client, monkeypatch):
    authed(client)
    engine = install_fake_engine(monkeypatch)

    pid = client.post("/api/people", json={
        "name": "Venki", "consent_text": CONSENT},
        headers={"X-CSRF-Token": csrf(client)}).json()["id"]

    samples = [jpeg_with_label("venki")] * 3
    enrol = client.post(f"/api/people/{pid}/enrol",
                        json={"images": samples},
                        headers={"X-CSRF-Token": csrf(client)})
    assert enrol.status_code == 200, enrol.text
    assert enrol.json()["samples"] == 3

    # the same deterministic vector matches at every threshold check
    import asyncio

    from backend.app.config import get_settings
    from backend.app.db import get_session_factory
    from backend.app.services import people_service

    async def match():
        async with get_session_factory()() as session:
            settings = get_settings()
            templates = await people_service.load_templates(session, settings)
            assert templates and templates[0][1].shape == (512,)
            v = engine.vectors["venki"]
            pid_seen, score = people_service.identify(
                v, templates, threshold=settings.face_match_threshold)
            assert pid_seen == pid
            assert score > 0.99
            # a different enrolled vector is NOT this person
            v2 = engine.vectors["other"]
            other, _score = people_service.identify(
                v2, templates, threshold=settings.face_match_threshold)
            assert other is None
            return True
    assert asyncio.run(match())

    # ciphertext at rest: template column is an AES token, not raw floats
    import asyncio as _aio

    from sqlalchemy import text as sql_text

    async def read_raw():
        async with get_session_factory()() as session:
            return (await session.execute(sql_text(
                "SELECT embedding_encrypted FROM face_templates"))).scalar_one()

    raw = _aio.run(read_raw())
    assert raw and "[" not in raw[:64]

    # withdraw: everything goes
    deleted = client.delete(f"/api/people/{pid}",
                            headers={"X-CSRF-Token": csrf(client)})
    assert deleted.status_code == 200
    emptied = client.get("/api/people")
    assert emptied.json()["count"] == 0

    async def templates_gone():
        async with get_session_factory()() as session:
            rows = (await session.execute(sql_text(
                "SELECT COUNT(*) FROM face_templates"))).scalar_one()
            people_rows = (await session.execute(sql_text(
                "SELECT COUNT(*) FROM people"))).scalar_one()
            return rows, people_rows
    rows, people_rows = _aio.run(templates_gone())
    assert rows == 0 and people_rows == 0


def test_enrol_requires_three_samples_and_a_face(client, monkeypatch):
    authed(client)
    install_fake_engine(monkeypatch)
    pid = client.post("/api/people", json={
        "name": "Venki", "consent_text": CONSENT},
        headers={"X-CSRF-Token": csrf(client)}).json()["id"]

    few = client.post(f"/api/people/{pid}/enrol",
                      json={"images": [jpeg_with_label("venki")] * 2},
                      headers={"X-CSRF-Token": csrf(client)})
    assert few.status_code == 422

    blank = jpeg_with_label("someone-else")
    noface = client.post(f"/api/people/{pid}/enrol",
                         json={"images": [blank] * 3},
                         headers={"X-CSRF-Token": csrf(client)})
    assert noface.status_code == 422
    assert noface.json()["error"]["code"] == "no_face_in_sample"


# --------------------------------------------------------- unknown, always
def test_unknown_face_never_named(client, monkeypatch):
    authed(client)
    install_fake_engine(monkeypatch)

    pid = client.post("/api/people", json={
        "name": "Venki", "consent_text": CONSENT},
        headers={"X-CSRF-Token": csrf(client)}).json()["id"]
    client.post(f"/api/people/{pid}/enrol",
                json={"images": [jpeg_with_label("venki")] * 3},
                headers={"X-CSRF-Token": csrf(client)})

    import asyncio

    from backend.app.config import get_settings
    from backend.app.db import get_session_factory
    from backend.app.services import people_service

    async def stranger():
        async with get_session_factory()() as session:
            settings = get_settings()
            templates = await people_service.load_templates(session, settings)
            v = vec(99)  # never enrolled
            person_id, score = people_service.identify(
                v, templates, threshold=settings.face_match_threshold)
            assert person_id is None
            assert score < settings.face_match_threshold
            return person_id, score
    person_id, score = asyncio.run(stranger())
    assert person_id is None
    assert score < 0.35


# --------------------------------------------------- last-seen ("who is by")
def test_last_seen_endpoint_roundtrip(client, monkeypatch):
    authed(client)
    pid = client.post("/api/people", json={
        "name": "Venki", "consent_text": CONSENT},
        headers={"X-CSRF-Token": csrf(client)}).json()["id"]

    cam = client.post("/api/cameras", json={
        "name": "Desk", "kind": "webcam", "source": "0"},
        headers={"X-CSRF-Token": csrf(client)}).json()

    # directly write an event carrying encrypted labels for Venki
    import asyncio

    from backend.app.config import get_settings
    from backend.app.db import get_session_factory
    from backend.app.security.crypto import encrypt_text
    from backend.app.services import camera_service
    from backend.app.services.memory_service import memory_key

    async def seed():
        async with get_session_factory()() as session:
            labels = {"known": [{"person_id": pid, "name": "Venki",
                                 "score": 0.99}], "unknown_faces": 1}
            import json
            settings = get_settings()
            await camera_service.record_event(
                session, settings, camera_id=cam["id"], kind="person",
                person_count=2, motion_score=0.6, snapshot_jpeg=None,
                snapshot_status="withheld",
                labels_encrypted=encrypt_text(
                    memory_key(settings), json.dumps(labels)))
            await session.commit()
    asyncio.run(seed())

    resp = client.get(f"/api/people/{pid}/last-seen")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Venki"
    assert len(resp.json()["seen"]) == 1

"""Biometric privacy tests.

The vision stack is stubbed out so that the tests focus on the security
properties: consent, encryption at rest, ownership and the fact that
unenrolled people can never unlock an owner session.
"""

from __future__ import annotations

import base64

import pytest
from sqlalchemy.orm import Session

from ownerai.db import get_engine
from ownerai.models import EnrolledIdentity
from ownerai.services import biometrics

from .conftest import auth_headers


@pytest.fixture()
def stub_embeddings(monkeypatch):
    """Replace the TFLite call with a deterministic vector."""

    def fake_compute_embedding(image, model_name="mobile_facenet"):
        import numpy as np

        vector = np.zeros(8, dtype="float32")
        vector[0] = 1.0
        return vector

    monkeypatch.setattr(biometrics, "compute_embedding", fake_compute_embedding)
    return fake_compute_embedding


def _sample_image() -> str:
    import cv2
    import numpy as np

    image = np.full((120, 120, 3), 128, dtype="uint8")
    ok, buffer = cv2.imencode(".png", image)
    assert ok
    return "data:image/png;base64," + base64.b64encode(buffer.tobytes()).decode("ascii")


def test_enrolment_requires_explicit_consent(client, owner, stub_embeddings):
    response = owner.post(
        "/api/identities",
        json={"label": "Owner", "consent": False, "images": [_sample_image()]},
        headers=auth_headers(owner),
    )
    assert response.status_code == 422


def test_enrolment_stores_the_template_encrypted(client, owner, stub_embeddings):
    response = owner.post(
        "/api/identities",
        json={"label": "Owner", "consent": True, "images": [_sample_image()]},
        headers=auth_headers(owner),
    )
    assert response.status_code == 201, response.text
    identity_id = response.json()["id"]

    with Session(get_engine()) as session:
        identity = session.get(EnrolledIdentity, identity_id)
        blob = identity.template_encrypted
        assert blob
        # The raw vector must not be readable in the database.
        assert b"1.000000" not in blob
        # ... but the owner can decrypt it again.
        assert biometrics._decrypt_template(blob) == [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_identities_of_other_users_are_not_listed(client, owner, viewer, stub_embeddings):
    owner.post(
        "/api/identities",
        json={"label": "Owner", "consent": True, "images": [_sample_image()]},
        headers=auth_headers(owner),
    )
    listed = viewer.get("/api/identities").json()
    assert listed == []


def test_a_user_cannot_withdraw_a_foreign_template(client, owner, viewer, stub_embeddings):
    created = owner.post(
        "/api/identities",
        json={"label": "Owner", "consent": True, "images": [_sample_image()]},
        headers=auth_headers(owner),
    )
    identity_id = created.json()["id"]
    assert viewer.delete(f"/api/identities/{identity_id}", headers=auth_headers(viewer)).status_code == 404


def test_unenrolled_people_cannot_unlock_the_owner_session(client, owner, stub_embeddings, monkeypatch):
    """A face that does not match the enrolled template never unlocks anything."""
    owner.post(
        "/api/identities",
        json={"label": "Owner", "consent": True, "images": [_sample_image()]},
        headers=auth_headers(owner),
    )

    def foreign_embedding(image, model_name="mobile_facenet"):
        import numpy as np

        vector = np.zeros(8, dtype="float32")
        vector[1] = 1.0
        return vector

    monkeypatch.setattr(biometrics, "compute_embedding", foreign_embedding)
    response = owner.post(
        "/api/identities/verify",
        json={"image": _sample_image()},
        headers=auth_headers(owner),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is False
    assert body["label"] is None


def test_the_enrolled_owner_can_be_verified(client, owner, stub_embeddings):
    owner.post(
        "/api/identities",
        json={"label": "Owner", "consent": True, "images": [_sample_image()]},
        headers=auth_headers(owner),
    )
    response = owner.post(
        "/api/identities/verify",
        json={"image": _sample_image()},
        headers=auth_headers(owner),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is True
    assert body["label"] == "Owner"


def test_withdrawing_consent_destroys_the_template(client, owner, stub_embeddings):
    created = owner.post(
        "/api/identities",
        json={"label": "Owner", "consent": True, "images": [_sample_image()]},
        headers=auth_headers(owner),
    )
    identity_id = created.json()["id"]
    assert owner.delete(f"/api/identities/{identity_id}", headers=auth_headers(owner)).status_code == 200

    with Session(get_engine()) as session:
        identity = session.get(EnrolledIdentity, identity_id)
        assert identity.withdrawn_at is not None
        assert biometrics._decrypt_template(identity.template_encrypted) == []


def test_templates_expire_after_the_retention_period(client, owner, stub_embeddings):
    from datetime import datetime, timedelta, timezone

    from ownerai.db import session_scope

    created = owner.post(
        "/api/identities",
        json={"label": "Owner", "consent": True, "images": [_sample_image()]},
        headers=auth_headers(owner),
    )
    identity_id = created.json()["id"]
    with Session(get_engine()) as session:
        identity = session.get(EnrolledIdentity, identity_id)
        identity.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        session.commit()

    with session_scope() as session:
        removed = biometrics.purge_expired_templates(session)
    assert removed >= 1

    with Session(get_engine()) as session:
        identity = session.get(EnrolledIdentity, identity_id)
        assert identity.withdrawn_at is not None


def test_biometric_templates_are_never_serialised_in_api_responses(client, owner, stub_embeddings):
    created = owner.post(
        "/api/identities",
        json={"label": "Owner", "consent": True, "images": [_sample_image()]},
        headers=auth_headers(owner),
    )
    body = created.text
    assert "template_encrypted" not in body
    assert "1.0,0.0" not in body
    assert "embedding" not in body.lower().replace("embedding_dim", "")

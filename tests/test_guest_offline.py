"""Tests for time-boxed guest access (Phase 3 #7) and offline-first mode (Phase 3 #8)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from ownerai.db import get_engine
from ownerai.models import EnrolledIdentity, GuestAccess, User
from ownerai.services.ai import build_provider, OfflineProvider
from ownerai.services.guest import (
    grant_guest_access,
    is_guest_access_valid,
    revoke_guest_access,
)
from ownerai.settings import get_settings


class TestGuestService:
    def test_grant_and_valid(self, owner):
        os.environ["OWNERAI_FEATURE_GUEST_ACCESS"] = "1"
        try:
            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                user_id = user.id
                identity = EnrolledIdentity(
                    owner_id=user_id,
                    label="cleaner",
                    model_name="mobile_facenet",
                    embedding_dim=128,
                    template_encrypted=b"\x00" * 32,
                    consent_at=datetime.now(timezone.utc),
                    expires_at=None,
                )
                session.add(identity)
                session.commit()
                session.refresh(identity)
                identity_id = identity.id

            grant = grant_guest_access(user_id, identity_id, "cleaner", ttl_hours=24)
            assert grant.id is not None
            assert is_guest_access_valid(identity_id) is True

            # Revoke
            assert revoke_guest_access(grant.id, user_id) is True
            assert is_guest_access_valid(identity_id) is False
        finally:
            os.environ.pop("OWNERAI_FEATURE_GUEST_ACCESS", None)

    def test_guest_disabled(self):
        assert is_guest_access_valid(1) is False

    def test_expired_grant_invalid(self, owner):
        os.environ["OWNERAI_FEATURE_GUEST_ACCESS"] = "1"
        try:
            from datetime import datetime, timedelta, timezone
            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                user_id = user.id
                identity = EnrolledIdentity(
                    owner_id=user_id,
                    label="temp",
                    model_name="mobile_facenet",
                    embedding_dim=128,
                    template_encrypted=b"\x00" * 32,
                    consent_at=datetime.now(timezone.utc),
                    expires_at=None,
                )
                session.add(identity)
                session.commit()
                session.refresh(identity)
                identity_id = identity.id

                grant = GuestAccess(
                    owner_id=user_id,
                    enrolled_identity_id=identity_id,
                    guest_label="expired",
                    expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
                )
                session.add(grant)
                session.commit()

            assert is_guest_access_valid(identity_id) is False
        finally:
            os.environ.pop("OWNERAI_FEATURE_GUEST_ACCESS", None)


class TestGuestEndpoints:
    def test_guest_requires_flag(self, owner):
        resp = owner.post("/api/guest-access", json={"enrolled_identity_id": 1, "guest_label": "x"})
        assert resp.status_code == 403


class TestOfflineFirst:
    def test_offline_provider_default(self):
        settings = get_settings()
        provider = build_provider(settings)
        assert isinstance(provider, OfflineProvider)
        assert provider.name == "offline"

    def test_offline_provider_no_data_leaves(self):
        provider = OfflineProvider()
        response = provider.complete(
            [{"role": "user", "content": "Who is at the door?"}], max_tokens=100
        )
        assert "offline" in response.text.lower() or "no external" in response.text.lower()
        assert response.provider == "offline"
        assert response.tokens == 0

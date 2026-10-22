"""Integration tests for privacy-first consent management and biometric template lifecycle."""

from fastapi import status
from backend.app.models.entities import ConsentRecord, FaceTemplate, Person
from backend.app.services.consent_service import grant_consent, withdraw_consent


def test_voluntary_profile_attributes_stored(client, admin_headers, db_session):
    # Enrolling a person with voluntary self-reported age and gender
    payload = {
        "name": "Jane Consenting User",
        "age": 29,
        "gender": "Female",
        "role_relationship": "resident",
        "contact_details": "jane@example.com",
        "notes": "Consented resident profile",
    }
    response = client.post("/api/v1/people", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "Jane Consenting User"
    assert data["age"] == 29
    assert data["gender"] == "Female"
    assert data["consent_active"] is True


def test_consent_lifecycle_and_biometrics_purge(client, admin_headers, db_session, test_admin_user):
    # 1. Create person
    p = Person(
        name="Mark Tester",
        age=40,
        gender="Male",
        role_relationship="employee",
        contact_details="mark@work.com",
        status="enrolled",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    # 2. Grant explicit consent
    consent = grant_consent(db_session, p.id, recorded_by_user_id=test_admin_user.id)
    assert consent.withdrawn_at is None
    assert p.has_active_consent(db_session) is True

    # 3. Simulate an encrypted face template stored for Mark
    template = FaceTemplate(
        person_id=p.id,
        template_encrypted=b"encrypted_sample_biometric_blob_12345",
        model_version="facenet",
        embedding_dim=512,
    )
    db_session.add(template)
    db_session.commit()

    # Verify template exists in DB
    tmpl = db_session.query(FaceTemplate).filter_by(person_id=p.id).first()
    assert tmpl is not None
    assert tmpl.revoked_at is None
    assert len(tmpl.template_encrypted) > 0

    # 4. Withdraw consent via API endpoint
    resp_withdraw = client.post(f"/api/v1/people/{p.id}/withdraw", headers=admin_headers)
    assert resp_withdraw.status_code == status.HTTP_200_OK

    # 5. Verify biometric template payload was immediately PURGED from DB upon consent withdrawal
    db_session.expire_all()
    tmpl_after = db_session.query(FaceTemplate).filter_by(person_id=p.id).first()
    assert tmpl_after.revoked_at is not None
    assert tmpl_after.template_encrypted == b"", "Biometric template payload must be completely purged upon withdrawal"

    # Verify consent record is marked withdrawn
    updated_consent = db_session.query(ConsentRecord).filter_by(person_id=p.id).order_by(ConsentRecord.granted_at.desc()).first()
    assert updated_consent.withdrawn_at is not None


def test_person_deletion_cascades_all_data(client, admin_headers, db_session):
    # Create person
    p = Person(
        name="Temporary Person",
        role_relationship="contractor",
        status="enrolled",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    # Delete person via API
    resp_del = client.delete(f"/api/v1/people/{p.id}", headers=admin_headers)
    assert resp_del.status_code == status.HTTP_204_NO_CONTENT

    # Verify deleted from DB
    assert db_session.query(Person).filter_by(id=p.id).first() is None

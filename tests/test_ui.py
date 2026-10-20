"""UI / UX tests for the required interface features."""

from __future__ import annotations

from .conftest import auth_headers


def test_public_pages_render(client):
    for path in ["/", "/login", "/register", "/forgot-password", "/docs"]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.headers["content-type"].startswith("text/html")


def test_the_landing_page_offers_the_required_features(client):
    body = client.get("/").text
    # Dark mode toggle
    assert "data-theme-toggle" in body
    # Cookie banner
    assert "data-cookie-banner" in body
    assert "ownerai_session" in body and "ownerai_csrf" in body
    # Floating contact button
    assert "data-contact-open" in body
    assert "data-contact-dialog" in body
    # Back to top button
    assert "data-back-to-top" in body
    # Site search
    assert "data-search-form" in body
    # Accessibility basics
    assert 'class="skip-link"' in body
    assert 'aria-label=' in body


def test_the_cookie_banner_describes_the_real_behaviour(client):
    """The banner must not claim tracking that does not exist."""
    body = client.get("/").text
    assert "No analytics" in body or "no analytics" in body
    assert "third-party tracking" in body
    # There is no third party script at all.
    assert "googletagmanager" not in body
    assert "google-analytics" not in body


def test_the_contact_dialog_has_an_accessible_form(client):
    body = client.get("/").text
    assert 'aria-labelledby="contact-title"' in body
    assert 'id="contact-email"' in body
    assert 'id="contact-subject"' in body
    assert 'id="contact-message"' in body
    assert 'data-contact-submit' in body
    # The honeypot must not be visible to humans.
    assert 'aria-hidden="true"' in body


def test_the_theme_toggle_exposes_its_state(client):
    body = client.get("/").text
    assert 'aria-pressed="false"' in body
    assert "Switch colour theme" in body or "Switch to the" in body


def test_the_back_to_top_button_is_keyboard_accessible(client):
    body = client.get("/").text
    assert "<button" in body
    assert 'data-back-to-top' in body
    assert 'aria-label="Back to top of the page"' in body


def test_the_dashboard_requires_authentication(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert "/login" in response.headers["location"]


def test_the_admin_page_requires_admin_permissions(client, viewer):
    response = viewer.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/dashboard")


def test_the_admin_page_is_available_for_administrators(client, admin_user):
    response = admin_user.get("/admin")
    assert response.status_code == 200
    assert "Administration" in response.text


def test_the_dashboard_contains_the_expected_panels(client, owner):
    body = owner.get("/dashboard").text
    for marker in [
        "data-devices-body",
        "data-events-list",
        "data-identities-list",
        "data-chat-log",
        "data-sessions-list",
        "data-identity-consent",
    ]:
        assert marker in body, marker


def test_search_returns_help_documents_for_anonymous_visitors(client):
    response = client.get("/api/search?q=privacy")
    assert response.status_code == 200
    hits = response.json()["hits"]
    assert hits
    assert all(hit["type"] == "help" for hit in hits)


def test_search_is_limited_for_authenticated_users(client, owner):
    response = owner.get("/api/search?q=camera")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 0
    assert body["query"] == "camera"


def test_the_contact_form_rejects_a_honeypot_submission(client):
    """A filled honeypot is silently accepted but never stored."""
    response = client.post(
        "/api/contact",
        json={
            "email": "bot@example.test",
            "subject": "Cheap watches",
            "message": "Buy our products, this message is long enough.",
            "website": "http://spam.example",
        },
        headers=auth_headers(client),
    )
    assert response.status_code == 202
    assert "received" in response.json()["message"]

    from sqlalchemy.orm import Session

    from ownerai.db import get_engine
    from ownerai.models import ContactMessage

    with Session(get_engine()) as session:
        assert session.query(ContactMessage).count() == 0


def test_the_contact_form_stores_a_valid_message(client):
    response = client.post(
        "/api/contact",
        json={
            "email": "user@example.test",
            "subject": "Question about cameras",
            "message": "Does the assistant work with IP cameras at night?",
            "website": "",
        },
        headers=auth_headers(client),
    )
    assert response.status_code == 202

    from sqlalchemy.orm import Session

    from ownerai.db import get_engine
    from ownerai.models import ContactMessage

    with Session(get_engine()) as session:
        stored = session.query(ContactMessage).one()
        assert stored.subject == "Question about cameras"
        # The address is stored encrypted, not in clear text.
        assert b"user@example.test" not in stored.email_ciphertext

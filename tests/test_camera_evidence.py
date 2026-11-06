"""Chat evidence must honestly report camera state (camera off -> says so)."""

from __future__ import annotations

from backend.app.services import evidence

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
    csrf = client.cookies.get("aegis_csrf", "")
    return client, csrf


def test_pack_includes_camera_and_reports_offline(client):
    client, csrf = authed(client)
    cam = client.post("/api/cameras", json={
        "name": "Desk", "kind": "webcam", "source": "0"},
        headers={"X-CSRF-Token": csrf})
    assert cam.status_code == 201

    from backend.app.ai.providers import ChatReply
    from backend.app.ai.router import LLMRouter

    seen = {}

    async def spy(self, session, *, messages, allow_remote=False):
        seen["ctx"] = "\n".join(m.content for m in messages)
        return ChatReply(text="The Desk camera is off [E3].",
                         provider="stub", model="stub-1")

    import asyncio

    import backend.app.services.chat_service as chat_svc
    from backend.app.config import get_settings
    from backend.app.db import get_session_factory

    async def build():
        async with get_session_factory()() as session:
            pack = await evidence.build_pack(session, get_settings())
            return [i.to_dict() for i in pack.items]

    # monkeypatch router via chat_service usage: call answer with stub
    orig = LLMRouter.complete
    LLMRouter.complete = spy  # type: ignore[method-assign]
    try:
        async def run():
            async with get_session_factory()() as session:
                return await chat_svc.answer(
                    session, get_settings(), question="Is the Desk camera on?")
        result = asyncio.run(run())
    finally:
        LLMRouter.complete = orig  # type: ignore[method-assign]

    texts = " ".join(i["text"] for i in result["evidence"])
    assert "Desk" in texts and "starting" in texts or "offline" in texts
    assert result["answer"] == "The Desk camera is off [E3]."

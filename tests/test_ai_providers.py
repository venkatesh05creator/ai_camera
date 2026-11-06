"""LLM providers + router: fake transports, honest errors, privacy gating."""

from __future__ import annotations

import pytest

from backend.app.ai.providers import (
    ChatMessage,
    OllamaProvider,
    OpenAICompatibleProvider,
    ProviderError,
)
from backend.app.ai.router import LLMRouter


class FakeResponse:
    """Minimal httpx Response stand-in for stream tests."""

    def __init__(self, status_code: int, lines: list[str]) -> None:
        self.status_code = status_code
        self._lines = lines

    async def aread(self) -> bytes:
        return "\n".join(self._lines).encode()

    async def aiter_lines(self):
        for line in self._lines:
            yield line


def patch_stream(monkeypatch, provider_module_reader):
    """Replace httpx.AsyncClient usage in providers with a fake factory."""
    import backend.app.ai.providers as prov

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def stream(self, method, url, **kwargs):
            reader = provider_module_reader
            return _Ctx(reader(method, url, kwargs))

    class _Ctx:
        def __init__(self, resp):
            self.resp = resp

        async def __aenter__(self):
            return self.resp

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(prov.httpx, "AsyncClient", FakeClient)


def ollama_lines(*texts, done_usage=True):
    out = []
    import json
    for t in texts:
        out.append(json.dumps({"message": {"content": t}}))
    if done_usage:
        out.append(json.dumps({
            "done": True, "prompt_eval_count": 42, "eval_count": 7}))
    return out


# ------------------------------------------------------------------ ollama
async def _collect(gen):
    events = []
    async for e in gen:
        events.append(e)
    return events


def test_ollama_streams_and_usage(monkeypatch):
    patch_stream(monkeypatch,
                 lambda m, u, k: FakeResponse(200, ollama_lines("Hi", " there")))
    provider = OllamaProvider("http://127.0.0.1:11434", "test-model")

    async def run():
        events = []
        async for e in provider.stream_complete(
                [ChatMessage("user", "hello")], max_tokens=10,
                temperature=0.0, timeout=5.0):
            events.append(e)
        return events

    import asyncio
    events = asyncio.run(run())
    deltas = [e.text for e in events if e.kind == "delta"]
    assert deltas == ["Hi", " there"]
    done = [e for e in events if e.kind == "done"][0]
    assert done.reply.text == "Hi there"
    assert done.reply.input_tokens == 42
    assert done.reply.output_tokens == 7


def test_ollama_unreachable_is_honest(monkeypatch):
    import httpx as _httpx_mod

    def boom(*a, **kw):
        raise _httpx_mod.ConnectError("refused", request=None)

    monkeypatch.setattr(_httpx_mod, "AsyncClient", boom)
    provider = OllamaProvider("http://127.0.0.1:9", "test-model")

    async def run():
        with pytest.raises(ProviderError) as caught:
            async for _ in provider.stream_complete(
                    [ChatMessage("user", "hi")], max_tokens=5,
                    temperature=0.0, timeout=2.0):
                pass
        return caught.value

    import asyncio
    err = asyncio.run(run())
    assert err.code == "unreachable"
    assert "not reachable" in err.message


def test_ollama_404_names_the_missing_model(monkeypatch):
    patch_stream(monkeypatch, lambda m, u, k: FakeResponse(404, []))
    provider = OllamaProvider("http://127.0.0.1:11434", "missing-model")

    async def run():
        with pytest.raises(ProviderError) as caught:
            async for _ in provider.stream_complete(
                    [ChatMessage("user", "hi")], max_tokens=5,
                    temperature=0.0, timeout=2.0):
                pass
        return caught.value

    import asyncio
    err = asyncio.run(run())
    assert err.code == "model_missing"
    assert "ollama pull missing-model" in err.message


# ------------------------------------------------------- openai-compatible
def test_openai_sse_stream_and_usage(monkeypatch):
    patch_stream(monkeypatch, lambda m, u, k: FakeResponse(200, [
        'data: {"choices":[{"delta":{"content":"A"}}]}',
        'data: {"choices":[{"delta":{"content":"B"}}]}',
        'data: {"usage":{"prompt_tokens":10,"completion_tokens":2}}',
        'data: [DONE]',
    ]))
    provider = OpenAICompatibleProvider(
        "groq", "https://api.groq.com/openai/v1", "m", "test-key")

    async def run():
        return [e async for e in provider.stream_complete(
            [ChatMessage("user", "hi")], max_tokens=5, temperature=0.0,
            timeout=2.0)]

    import asyncio
    events = asyncio.run(run())
    assert "".join(e.text for e in events if e.kind == "delta") == "AB"
    done = [e for e in events if e.kind == "done"][0]
    assert done.reply.input_tokens == 10
    assert done.reply.output_tokens == 2


def test_openai_429_and_401_have_distinct_codes(monkeypatch):
    for status, code in ((429, "rate_limited"), (401, "bad_key")):
        patch_stream(monkeypatch, lambda m, u, k, s=status: FakeResponse(s, []))
        provider = OpenAICompatibleProvider(
            "groq", "https://x", "m", "key")

        async def run():
            with pytest.raises(ProviderError) as caught:
                async for _ in provider.stream_complete(  # noqa: B023
                        [ChatMessage("user", "hi")], max_tokens=5,
                        temperature=0.0, timeout=2.0):
                    pass
            return caught.value

        import asyncio
        assert asyncio.run(run()).code == code


# ------------------------------------------------------------------ router
def make_settings(**kw):
    from backend.app.config import Settings
    base = dict(
        app_env="test",
        database_url="sqlite+aiosqlite:///./var/router-test.db",
        secret_key="x" * 40,
        json_logs=False,
        log_level="WARNING",
        groq_api_key="test-groq-key",
    )
    base.update(kw)
    return Settings(**base)


@pytest.fixture()
def router_session(settings):
    import asyncio

    from backend.app.db import get_session_factory, reset_engine
    reset_engine()

    async def setup():
        from backend.app.db import get_engine
        from backend.app.models.base import create_all
        get_engine(settings)
        await create_all()

    asyncio.run(setup())
    factory = get_session_factory()
    yield (LLMRouter(settings), factory)
    reset_engine()


def test_router_never_touches_remote_without_permission(router_session):
    """Privacy rule: allow_remote=False must not even construct a remote call."""
    router, factory = router_session
    assert [p.name for p in router.providers(allow_remote=False)] == ["ollama"]
    # even with a key configured, default is local-only
    assert not any(p.name == "groq"
                   for p in router.providers(allow_remote=False))


def test_router_falls_back_and_meters(router_session, monkeypatch):
    import asyncio

    from backend.app.ai.providers import ChatReply
    router, factory = router_session

    class FailingOllama:
        name = "ollama"
        model = "llama3.1:8b"

        async def complete(self, messages, **kwargs):
            raise ProviderError("unreachable", "down", 503)

    class GoodGroq:
        name = "groq"
        model = "openai/gpt-oss-120b"

        async def complete(self, messages, **kwargs):
            return ChatReply(text="hello from cloud", provider="groq",
                             model=self.model, input_tokens=5,
                             output_tokens=3)

    monkeypatch.setattr(router, "providers",
                        lambda *, allow_remote: [FailingOllama(), GoodGroq()])

    async def run():
        async with factory() as session:
            reply = await router.complete(
                session, messages=[ChatMessage("user", "hi")],
                allow_remote=True)
            await session.commit()
            return reply

    reply = asyncio.run(run())
    assert reply.text == "hello from cloud"
    assert reply.provider == "groq"

    async def meter():
        async with factory() as session:
            return await router.summary(session)

    rows = asyncio.run(meter())
    by_provider = {r["provider"]: r for r in rows}
    assert by_provider["groq"]["requests"] == 1
    assert by_provider["groq"]["input_tokens"] == 5
    assert by_provider["ollama"]["errors"] == 1


def test_router_all_fail_is_honest(router_session, monkeypatch):
    import asyncio

    router, factory = router_session

    class Dead:
        def __init__(self, name):
            self.name = name
            self.model = "m"

        async def complete(self, messages, **kwargs):
            raise ProviderError("unreachable", f"{self.name} down", 503)

    monkeypatch.setattr(router, "providers",
                        lambda *, allow_remote: [Dead("a"), Dead("b")])

    async def run():
        async with factory() as session:
            with pytest.raises(ProviderError):
                await router.complete(
                    session, messages=[ChatMessage("user", "hi")],
                    allow_remote=True)
            await session.commit()

    asyncio.run(run())


def test_cooldown_blocks_remembered_429(router_session):
    import asyncio

    router, factory = router_session

    async def run():
        async with factory() as session:
            await router.record_usage(
                session, provider="groq", model="m",
                input_tokens=None, output_tokens=None, error=True,
                cooldown_minutes=5)
            await session.commit()
            return await router.in_cooldown(session, provider="groq", model="m")

    assert asyncio.run(run()) is True

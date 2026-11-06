"""Pluggable LLM providers: Ollama (local) + OpenAI-compatible cloud.

Design rules enforced here:
- a provider NEVER invents an answer: transport/parse failures raise
  :class:`ProviderError` with the real cause
- streaming yields token deltas; the final event carries real usage counts
  (``None`` when the provider does not report them — never estimated)
- API keys only ever travel in headers; they are never logged
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    def __init__(self, code: str, message: str, status: int = 502) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


@dataclass(frozen=True)
class ChatMessage:
    role: str  # system | user | assistant | tool
    content: str


@dataclass(frozen=True)
class ChatReply:
    text: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class StreamEvent:
    kind: str  # delta | done
    text: str = ""
    reply: ChatReply | None = None


class BaseProvider:
    name: str = "base"
    model: str = ""

    async def complete(self, messages: list[ChatMessage], *,
                       max_tokens: int, temperature: float,
                       timeout: float) -> ChatReply:
        parts: list[str] = []
        final: ChatReply | None = None
        async for event in self.stream_complete(
                messages, max_tokens=max_tokens, temperature=temperature,
                timeout=timeout):
            if event.kind == "delta":
                parts.append(event.text)
            elif event.kind == "done" and event.reply is not None:
                final = event.reply
        if final is None:  # pragma: no cover - defensive
            raise ProviderError("empty_stream", "provider ended without a result")
        return final

    def stream_complete(self, messages: list[ChatMessage], *,
                        max_tokens: int, temperature: float,
                        timeout: float) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError


class OllamaProvider(BaseProvider):
    """Local-first provider talking to a local Ollama daemon."""

    def __init__(self, host: str, model: str) -> None:
        self.name = "ollama"
        self.host = host.rstrip("/")
        self.model = model

    async def stream_complete(self, messages: list[ChatMessage], *,
                              max_tokens: int, temperature: float,
                              timeout: float) -> AsyncIterator[StreamEvent]:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content}
                         for m in messages],
            "stream": True,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        text_parts: list[str] = []
        usage_in: int | None = None
        usage_out: int | None = None
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                        "POST", f"{self.host}/api/chat", json=payload) as resp:
                    if resp.status_code != 200:
                        if resp.status_code == 404:
                            raise ProviderError(
                                "model_missing",
                                f"local model '{self.model}' not found in Ollama "
                                f"(pull it first: ollama pull {self.model})", 503)
                        if resp.status_code == 429:
                            raise ProviderError("rate_limited",
                                                "local provider rate-limited", 429)
                        raise ProviderError(
                            "provider_http",
                            f"Ollama returned HTTP {resp.status_code}", 502)
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue  # heartbeat/garbage: never answer from noise
                        chunk = obj.get("message", {}).get("content", "")
                        if chunk:
                            text_parts.append(chunk)
                            yield StreamEvent("delta", chunk)
                        if obj.get("done"):
                            usage_in = obj.get("prompt_eval_count")
                            usage_out = obj.get("eval_count")
        except httpx.ConnectError as exc:
            raise ProviderError(
                "unreachable",
                "Ollama is not reachable on this machine "
                f"({self.host}). Install/start Ollama or check the address.",
                503) from exc
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", "local model timed out", 504) from exc
        full = "".join(text_parts)
        yield StreamEvent("done", reply=ChatReply(
            text=full, provider=self.name, model=self.model,
            input_tokens=usage_in, output_tokens=usage_out))


class OpenAICompatibleProvider(BaseProvider):
    """Groq / OpenRouter / NVIDIA NIM (all /v1/chat/completions APIs)."""

    def __init__(self, name: str, base_url: str, model: str,
                 api_key: str) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    async def stream_complete(self, messages: list[ChatMessage], *,
                              max_tokens: int, temperature: float,
                              timeout: float) -> AsyncIterator[StreamEvent]:
        if not self.api_key:
            raise ProviderError("no_key", f"{self.name} has no API key set", 503)
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content}
                         for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        text_parts: list[str] = []
        usage_in: int | None = None
        usage_out: int | None = None
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                        "POST", f"{self.base_url}/chat/completions",
                        json=payload, headers=headers) as resp:
                    if resp.status_code != 200:
                        detail = (await resp.aread())[:300]
                        if resp.status_code == 429:
                            raise ProviderError(
                                "rate_limited",
                                f"{self.name} free quota is exhausted right now",
                                429)
                        if resp.status_code == 401:
                            raise ProviderError(
                                "bad_key",
                                f"{self.name} rejected the API key "
                                "(check it in .env)", 503)
                        raise ProviderError(
                            "provider_http",
                            f"{self.name} returned HTTP {resp.status_code}: "
                            f"{detail.decode('utf-8', 'replace')}", 502)
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data in ("", "[DONE]"):
                            continue
                        try:
                            obj = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = obj.get("choices") or []
                        if choices:
                            delta = choices[0].get("delta", {}).get("content")
                            if delta:
                                text_parts.append(delta)
                                yield StreamEvent("delta", delta)
                        usage = obj.get("usage")
                        if isinstance(usage, dict):
                            usage_in = usage.get("prompt_tokens")
                            usage_out = usage.get("completion_tokens")
        except httpx.ConnectError as exc:
            raise ProviderError("unreachable",
                                f"{self.name} could not be reached", 503) from exc
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", f"{self.name} timed out", 504) from exc
        yield StreamEvent("done", reply=ChatReply(
            text="".join(text_parts), provider=self.name, model=self.model,
            input_tokens=usage_in, output_tokens=usage_out))


# --- optional cloud endpoints (keys come from .env, nothing hardcoded) -------

def groq_provider(api_key: str) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        "groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-120b", api_key)


def openrouter_provider(api_key: str) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        "openrouter", "https://openrouter.ai/api/v1",
        "meta-llama/llama-3.3-70b-instruct:free", api_key)


def nvidia_provider(api_key: str) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        "nvidia", "https://integrate.api.nvidia.com/v1",
        "meta/llama-3.1-70b-instruct", api_key)

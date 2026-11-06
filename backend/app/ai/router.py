"""Local-first provider router with quota meter.

Order: Ollama first. Remote providers are tried ONLY when
``allow_remote=True`` for that request AND an API key is configured
(privacy rule: local content never leaves the machine unasked).

Every attempt updates the persisted quota meter; a 429 puts the provider in
cooldown for 5 minutes. If everything fails the router raises honestly —
it never fabricates a reply.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select

from ..config import Settings
from ..models.provider import ProviderUsage
from ..models.user import utcnow
from .providers import (
    BaseProvider,
    ChatMessage,
    ChatReply,
    OllamaProvider,
    ProviderError,
    groq_provider,
    nvidia_provider,
    openrouter_provider,
)

logger = logging.getLogger(__name__)


def _today() -> str:
    return utcnow().strftime("%Y-%m-%d")


class LLMRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def providers(self, *, allow_remote: bool) -> list[BaseProvider]:
        providers: list[BaseProvider] = [
            OllamaProvider(self.settings.ollama_host, self.settings.ollama_model),
        ]
        if allow_remote:
            if self.settings.groq_api_key.get_secret_value():
                providers.append(groq_provider(
                    self.settings.groq_api_key.get_secret_value()))
            if self.settings.openrouter_api_key.get_secret_value():
                providers.append(openrouter_provider(
                    self.settings.openrouter_api_key.get_secret_value()))
            if self.settings.nvidia_api_key.get_secret_value():
                providers.append(nvidia_provider(
                    self.settings.nvidia_api_key.get_secret_value()))
        return providers

    # ---------------------------------------------------------------- quota
    async def _usage_row(self, session, provider: str,
                         model: str) -> ProviderUsage:
        day = _today()
        row = (await session.execute(
            select(ProviderUsage).where(
                ProviderUsage.provider == provider,
                ProviderUsage.model == model,
                ProviderUsage.day == day))).scalar_one_or_none()
        if row is None:
            row = ProviderUsage(provider=provider, model=model, day=day)
            session.add(row)
            await session.flush()
        return row

    async def record_usage(self, session, *, provider: str, model: str,
                           input_tokens: int | None, output_tokens: int | None,
                           error: bool = False,
                           cooldown_minutes: int = 0) -> None:
        """Persist one real attempt (success or failure) into the meter."""
        row = await self._usage_row(session, provider, model)
        row.requests += 1
        if error:
            row.errors += 1
            if cooldown_minutes:
                row.cooldown_until = utcnow() + timedelta(minutes=cooldown_minutes)
        if input_tokens is not None:
            row.input_tokens = (row.input_tokens or 0) + input_tokens
        if output_tokens is not None:
            row.output_tokens = (row.output_tokens or 0) + output_tokens

    async def in_cooldown(self, session, *, provider: str,
                          model: str) -> bool:
        day = _today()
        row = (await session.execute(
            select(ProviderUsage).where(
                ProviderUsage.provider == provider,
                ProviderUsage.model == model,
                ProviderUsage.day == day))).scalar_one_or_none()
        return bool(row and row.cooldown_until and row.cooldown_until > utcnow())

    async def summary(self, session) -> list[dict]:
        """Real counts per provider/model today (no invented numbers)."""
        rows = (await session.execute(
            select(ProviderUsage).where(ProviderUsage.day == _today())
            .order_by(ProviderUsage.provider, ProviderUsage.model)
        )).scalars().all()
        return [
            {
                "provider": r.provider,
                "model": r.model,
                "day": r.day,
                "requests": r.requests,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "errors": r.errors,
                "cooldown_until": (r.cooldown_until.isoformat()
                                   if r.cooldown_until else None),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------ chat
    async def complete(self, session, *, messages: list[ChatMessage],
                       allow_remote: bool = False) -> ChatReply:
        """Try providers in order; honest failure if all fail."""
        last_error: ProviderError | None = None
        for provider in self.providers(allow_remote=allow_remote):
            if await self.in_cooldown(session, provider=provider.name,
                                      model=provider.model):
                logger.info("provider %s in cooldown, skipped", provider.name)
                continue
            try:
                reply = await provider.complete(
                    messages,
                    max_tokens=self.settings.chat_max_tokens,
                    temperature=self.settings.chat_temperature,
                    timeout=self.settings.chat_timeout_seconds,
                )
                await self.record_usage(
                    session, provider=provider.name, model=provider.model,
                    input_tokens=reply.input_tokens,
                    output_tokens=reply.output_tokens)
                return reply
            except ProviderError as exc:
                last_error = exc
                await self.record_usage(
                    session, provider=provider.name, model=provider.model,
                    input_tokens=None, output_tokens=None, error=True,
                    cooldown_minutes=5 if exc.code == "rate_limited" else 0)
                logger.info("provider %s failed: %s", provider.name, exc.code)
                continue
        if last_error is not None:
            raise last_error
        raise ProviderError("no_provider", "no provider available", 503)

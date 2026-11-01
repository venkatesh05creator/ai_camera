"""Hybrid Cloud + Offline AI Brain with Rate Limit Failover.

Adapted from Project JARVIS jarvis_brain.py.
Uses free Groq endpoints for ultra-fast responses, and smoothly falls back
to offline local processing if API rate limits or network issues occur.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

KEYFILE = os.path.expanduser("~/.openjarvis/free.key")
MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

_GROQ_COOLDOWN_UNTIL: float = 0.0

DEFAULT_SYSTEM_PROMPT = """You are Jarvis, a fast, highly capable AI executive assistant running on the user's computer.
Respond concisely in 1-2 sentences. Be direct, helpful, and natural. Do not use filler or formal corporate jargon.
"""


def get_groq_api_key() -> Optional[str]:
    """Retrieve Groq API key from environment variable or ~/.openjarvis/free.key."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if key:
        return key
    if os.path.exists(KEYFILE):
        try:
            with open(KEYFILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception:
            pass
    return None


def is_cloud_ready() -> bool:
    """Returns True if the cloud brain has a key and is not currently in rate-limit cooldown."""
    key = get_groq_api_key()
    if not key:
        return False
    return time.time() >= _GROQ_COOLDOWN_UNTIL


def get_cooldown_remaining() -> float:
    """Returns seconds remaining in rate limit cooldown, or 0.0 if active."""
    rem = _GROQ_COOLDOWN_UNTIL - time.time()
    return max(0.0, rem)


def set_cooldown(seconds: float) -> None:
    """Set cooldown timer for rate limit backoff."""
    global _GROQ_COOLDOWN_UNTIL
    _GROQ_COOLDOWN_UNTIL = max(_GROQ_COOLDOWN_UNTIL, time.time() + float(seconds))


def parse_retry_after(error_text: str, default: int = 60) -> int:
    """Extract wait time from Groq HTTP 429 response message."""
    s = str(error_text).lower()
    m = re.search(r"try again in\s*(\d+)m\s*([0-9]+(?:\.[0-9]+)?)s", s)
    if m:
        return int(float(m.group(1)) * 60 + float(m.group(2))) + 2
    m2 = re.search(r"try again in\s*([0-9]+(?:\.[0-9]+)?)s", s)
    if m2:
        return int(float(m2.group(1))) + 2
    return default


class HybridResponse(tuple):
    """Dual-access response object supporting both tuple unpacking and dict/attribute access."""
    def __new__(cls, answer: Optional[str], provider_mode: str):
        return super().__new__(cls, (answer, provider_mode))

    @property
    def answer(self) -> Optional[str]:
        return self[0]

    @property
    def reply(self) -> Optional[str]:
        return self[0]

    @property
    def provider(self) -> str:
        return self[1]

    @property
    def model(self) -> str:
        return self[1]

    def get(self, key: str, default: Any = None) -> Any:
        if key in ("reply", "answer", "text"):
            return self[0] if self[0] is not None else default
        if key in ("provider", "mode", "model"):
            return self[1]
        if key == "cooldown_active":
            return "cooldown" in self[1] or "rate_limited" in self[1]
        return default

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, str):
            val = self.get(item, KeyError)
            if val is KeyError:
                raise KeyError(item)
            return val
        return super().__getitem__(item)


def think_hybrid(
    query: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    system_prompt: Optional[str] = None,
    timeout_seconds: float = 8.0,
) -> HybridResponse:
    """Execute LLM query via Groq with automatic HTTP 429 rate limit failover."""
    global _GROQ_COOLDOWN_UNTIL

    key = get_groq_api_key()
    if not key:
        return HybridResponse("Local offline fallback active. Configure GROQ_API_KEY for cloud model acceleration.", "offline_unconfigured")

    now = time.time()
    if now < _GROQ_COOLDOWN_UNTIL:
        rem = round(_GROQ_COOLDOWN_UNTIL - now, 1)
        logger.info("Groq in rate-limit cooldown (%.1fs remaining), using local fallback", rem)
        return HybridResponse("Local offline fallback active during Groq rate limit cooldown.", f"cooldown_active_{rem}s")

    sys_content = system_prompt or DEFAULT_SYSTEM_PROMPT
    msgs: List[Dict[str, str]] = [{"role": "system", "content": sys_content}]

    if conversation_history:
        for m in conversation_history[-6:]:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role in ["user", "system", "assistant"] and content:
                msgs.append({"role": role, "content": content})

    msgs.append({"role": "user", "content": query})

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    base_url = "https://api.groq.com/openai/v1/chat/completions"

    for model in MODELS:
        payload = {
            "model": model,
            "messages": msgs,
            "max_tokens": 300,
            "temperature": 0.5,
        }
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                resp = client.post(base_url, json=payload, headers=headers)
                if resp.status_code == 429:
                    wait_sec = parse_retry_after(resp.text)
                    set_cooldown(wait_sec)
                    logger.warning("Groq HTTP 429 rate limit hit. Cooldown set for %ds. Falling back to local engine.", wait_sec)
                    return HybridResponse("Local offline fallback active during Groq rate limit cooldown.", f"rate_limited_cooldown_{wait_sec}s")

                resp.raise_for_status()
                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                return HybridResponse(text, f"groq:{model}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                wait_sec = parse_retry_after(exc.response.text)
                set_cooldown(wait_sec)
                logger.warning("Groq HTTP 429 rate limit hit. Cooldown set for %ds.", wait_sec)
                return HybridResponse("Local offline fallback active during Groq rate limit cooldown.", f"rate_limited_cooldown_{wait_sec}s")
            logger.warning("Groq model %s error: %s", model, exc)
            continue
        except Exception as exc:
            logger.warning("Groq model %s attempt failed: %s", model, exc)
            continue

    return HybridResponse("Local offline fallback active. Cloud model currently unreachable.", "cloud_unavailable_fallback")


class HybridBrain:
    """Class wrapper for hybrid cloud + offline AI engine."""

    @staticmethod
    def think_hybrid(query: str, **kwargs) -> HybridResponse:
        return think_hybrid(query, **kwargs)

    @staticmethod
    def is_cloud_ready() -> bool:
        return is_cloud_ready()

    @staticmethod
    def get_cooldown_remaining() -> float:
        return get_cooldown_remaining()

    @staticmethod
    def set_cooldown(seconds: float) -> None:
        return set_cooldown(seconds)

    @staticmethod
    def get_groq_api_key() -> Optional[str]:
        return get_groq_api_key()


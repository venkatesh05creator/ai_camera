"""Tests for AI provider selection + auto-detect (Phase O-3)."""

from __future__ import annotations

from unittest import mock

from ownerai.services.ai import OfflineProvider, build_provider, provider_summary
from ownerai.settings import Settings


def _fresh_settings():
    """Return a fresh Settings instance (not the cached singleton) so tests
    do not contaminate each other via the lru_cached get_settings()."""
    s = Settings()
    # Ensure a clean, offline-by-default starting point.
    s.ai_provider = "offline"
    s.ai_auto_detect_engine = False
    s.ai_api_key = None
    return s


class TestProviderSummary:
    def test_offline_by_default(self):
        """No cloud provider configured -> offline provider (local, private)."""
        summary = provider_summary(_fresh_settings())
        assert summary["provider"] == "offline"
        assert summary["source"] == "default"
        assert summary["local"] is True

    def test_auto_detect_off_returns_offline_when_no_cloud(self):
        s = _fresh_settings()
        summary = provider_summary(s)
        assert summary["provider"] == "offline"
        assert summary["local"] is True

    def test_openai_compatible_configured(self):
        s = _fresh_settings()
        s.ai_provider = "openai_compatible"
        s.ai_api_key = "sk-test"
        summary = provider_summary(s)
        assert summary["source"] == "configured"
        assert summary["local"] is False


class TestBuildProvider:
    def test_returns_offline_by_default(self):
        provider = build_provider(_fresh_settings())
        assert isinstance(provider, OfflineProvider)
        assert provider.name == "offline"

    def test_auto_detect_without_ollama_falls_back_to_offline(self):
        """No Ollama running locally -> offline provider (safe fallback)."""
        s = _fresh_settings()
        s.ai_auto_detect_engine = True
        provider = build_provider(s)
        assert isinstance(provider, OfflineProvider)
        assert provider.name == "offline"

    def test_auto_detect_uses_ollama_when_available(self):
        s = _fresh_settings()
        s.ai_auto_detect_engine = True
        with mock.patch(
            "ownerai.services.ai._ollama_available", return_value=True
        ):
            provider = build_provider(s)
        # Should NOT be offline; it should be the Ollama-compatible provider.
        assert not isinstance(provider, OfflineProvider)
        assert provider.name == "ollama"

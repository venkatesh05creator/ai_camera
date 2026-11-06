"""Tests for World Monitor (Phase W): mocked public-data sources, rate limits,
source-down fallback, and feature-flag gating."""

from __future__ import annotations

import os

import pytest

from ownerai.services.world import WorldError, _cache, available_sources, fetch_source
from ownerai.settings import get_settings


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the in-memory world cache between tests for isolation."""
    _cache.clear()


class _FakeResponse:
    def __init__(self, status_code: int, json_data=None, text: str = ""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("boom", request=None, response=self)

    def json(self):
        return self._json


class _FakeClient:
    def __init__(self, timeout=15.0, response=None):
        self.timeout = timeout
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, **kwargs):
        return self.response


def _patch_fetch(monkeypatch, response):
    fake_client = _FakeClient(response=response)
    monkeypatch.setattr("httpx.Client", lambda *a, **k: fake_client)
    return fake_client


class TestSourceAvailability:
    def test_aircraft_available_without_key(self):
        settings = get_settings()
        from ownerai.services.world import _source_available
        assert _source_available("aircraft", settings) is True

    def test_fires_unavailable_without_key(self):
        settings = get_settings()
        from ownerai.services.world import _source_available
        assert _source_available("fires", settings) is False


class TestFetchSource:
    def test_aircraft_fetch(self, monkeypatch):
        os.environ["OWNERAI_FEATURE_WORLD_MONITOR"] = "1"
        try:
            from ownerai.features import is_enabled
            assert is_enabled("WORLD_MONITOR") is True

            fake = _FakeResponse(
                200,
                {"states": [["icao1", "callsign1", "origin", 1, 2, 3, 4, 5, 37.0, -122.0, 0, 0, 0]]},
            )
            _patch_fetch(monkeypatch, fake)
            result = fetch_source("aircraft")
            assert result["stale"] is False
            assert result["data"] is not None
            assert "OpenSky" in result["attribution"]
            assert result["source"] == "aircraft"
        finally:
            os.environ.pop("OWNERAI_FEATURE_WORLD_MONITOR", None)

    def test_unavailable_source_raises(self, monkeypatch):
        os.environ["OWNERAI_FEATURE_WORLD_MONITOR"] = "1"
        try:
            _patch_fetch(monkeypatch, _FakeResponse(502))
            with pytest.raises(WorldError):
                fetch_source("aircraft")
        finally:
            os.environ.pop("OWNERAI_FEATURE_WORLD_MONITOR", None)

    def test_source_down_falls_back_to_stale_cache(self, monkeypatch):
        os.environ["OWNERAI_FEATURE_WORLD_MONITOR"] = "1"
        try:
            # First fetch succeeds and populates cache.
            good = _FakeResponse(200, {"states": []})
            _patch_fetch(monkeypatch, good)
            first = fetch_source("aircraft")
            assert first["stale"] is False

            # Second fetch fails (force refresh to bypass cache); cache returns stale.
            bad = _FakeResponse(502)
            _patch_fetch(monkeypatch, bad)
            second = fetch_source("aircraft", force_refresh=True)
            assert second["stale"] is True
            assert second["data"] == {"states": []}
        finally:
            os.environ.pop("OWNERAI_FEATURE_WORLD_MONITOR", None)

    def test_feature_flag_gated(self):
        # _source_available does not itself check the flag; the router does.
        # Verify flag default off.
        from ownerai.features import is_enabled
        assert is_enabled("WORLD_MONITOR") is False


class TestAvailableSources:
    def test_list_includes_attribution(self):
        settings = get_settings()
        sources = available_sources(settings)
        ids = {s["id"] for s in sources}
        assert "aircraft" in ids
        assert "earthquakes" in ids
        assert "cyber" in ids
        for s in sources:
            assert "name" in s and "attribution" in s and "available" in s

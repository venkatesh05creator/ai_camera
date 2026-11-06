"""Tests for the skills format system (Phase O-5)."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from ownerai.routers.skills import _registry
from ownerai.services.skills import SkillError, SkillsRegistry


@pytest.fixture(autouse=True)
def _reset_registry():
    _registry.reset()


def _echo_handler(text: str) -> dict:
    return {"echo": text}


def _set_handler(key: str, value: str) -> dict:
    return {"set": {key: value}}


class TestSkillsService:
    def test_skills_disabled(self):
        os.environ.pop("OWNERAI_FEATURE_SKILLS_FORMAT", None)
        registry = SkillsRegistry()
        with pytest.raises(SkillError, match="not enabled"):
            registry.register_handler("echo", _echo_handler)
        assert registry.list_skills() == {}

    def test_register_handler_disabled(self):
        os.environ.pop("OWNERAI_FEATURE_SKILLS_FORMAT", None)
        registry = SkillsRegistry()
        with pytest.raises(SkillError, match="not enabled"):
            registry.register_handler("echo", _echo_handler)

    def test_register_and_load_manifest(self):
        os.environ["OWNERAI_FEATURE_SKILLS_FORMAT"] = "1"
        try:
            registry = SkillsRegistry()
            registry.register_handler("echo", _echo_handler)
            registry.register_handler("set", _set_handler)

            manifest = {
                "skills": [
                    {
                        "name": "echo",
                        "description": "Echo back text.",
                        "input_schema": {
                            "type": "object",
                            "properties": {"text": {"type": "string"}},
                            "required": ["text"],
                        },
                        "mutating": False,
                        "handler": "echo",
                    },
                    {
                        "name": "set",
                        "description": "Set a key/value (mutating).",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "value": {"type": "string"},
                            },
                            "required": ["key", "value"],
                        },
                        "mutating": True,
                        "handler": "set",
                    },
                ]
            }

            with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False
            ) as fh:
                json.dump(manifest, fh)
                path = fh.name

            try:
                loaded = registry.load_manifest(path)
                assert set(loaded) == {"echo", "set"}
                skills = registry.list_skills()
                assert set(skills) == {"echo", "set"}
                assert skills["echo"].mutating is False
                assert skills["set"].mutating is True

                # Non-mutating skill executes directly.
                result = registry.execute_skill("echo", {"text": "hello"})
                assert result["status"] == "ok"
                assert result["result"] == {"echo": "hello"}

                # Mutating skill requires confirmation.
                unconfirmed = registry.execute_skill("set", {"key": "a", "value": "b"})
                assert unconfirmed["status"] == "requires_confirmation"

                confirmed = registry.execute_skill(
                    "set", {"key": "a", "value": "b"}, confirmed=True
                )
                assert confirmed["status"] == "ok"

                # Missing required argument.
                with pytest.raises(SkillError, match="missing required argument"):
                    registry.execute_skill("echo", {})

                # Unknown skill.
                with pytest.raises(SkillError, match="unknown skill"):
                    registry.execute_skill("nonexistent", {})
            finally:
                os.unlink(path)
        finally:
            os.environ.pop("OWNERAI_FEATURE_SKILLS_FORMAT", None)

    def test_load_manifest_invalid(self):
        os.environ["OWNERAI_FEATURE_SKILLS_FORMAT"] = "1"
        try:
            registry = SkillsRegistry()
            registry.register_handler("echo", _echo_handler)
            manifest = {"skills": [{"name": "bad", "description": "bad schema", "input_schema": "not-an-object", "mutating": False, "handler": "echo"}]}
            with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False
            ) as fh:
                json.dump(manifest, fh)
                path = fh.name
            try:
                with pytest.raises(SkillError, match="input_schema"):
                    registry.load_manifest(path)
            finally:
                os.unlink(path)
        finally:
            os.environ.pop("OWNERAI_FEATURE_SKILLS_FORMAT", None)

    def test_load_manifest_unknown_handler(self):
        os.environ["OWNERAI_FEATURE_SKILLS_FORMAT"] = "1"
        try:
            registry = SkillsRegistry()
            manifest = {
                "skills": [
                    {
                        "name": "orphan",
                        "description": "no handler",
                        "input_schema": {"type": "object"},
                        "handler": "does_not_exist",
                    }
                ]
            }
            with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False
            ) as fh:
                json.dump(manifest, fh)
                path = fh.name
            try:
                with pytest.raises(SkillError, match="unknown handler"):
                    registry.load_manifest(path)
            finally:
                os.unlink(path)
        finally:
            os.environ.pop("OWNERAI_FEATURE_SKILLS_FORMAT", None)


class TestSkillsEndpoints:
    def test_skills_requires_flag(self, owner):
        resp = owner.get("/api/skills")
        assert resp.status_code == 403

    def test_skills_manifest_requires_flag(self, owner):
        resp = owner.post("/api/skills/manifest", json={"path": "skills/manifest.json"})
        assert resp.status_code == 403

    def test_skills_list_empty(self, owner):
        os.environ["OWNERAI_FEATURE_SKILLS_FORMAT"] = "1"
        try:
            resp = owner.get("/api/skills")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["feature"] == "SKILLS_FORMAT"
            assert data["skills"] == {}
        finally:
            os.environ.pop("OWNERAI_FEATURE_SKILLS_FORMAT", None)

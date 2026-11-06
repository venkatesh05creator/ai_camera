"""Tests for doctor (Phase 3B), MCP runtime (Phase 3B), wake word (Phase 3B)."""

from __future__ import annotations

import os

import pytest

from ownerai.services.doctor import DoctorError, run_doctor, benchmark_provider
from ownerai.services.mcp import MCPError, MCPRuntime
from ownerai.services.wake_word import _wake_word


class TestDoctor:
    def test_doctor_disabled(self):
        with pytest.raises(DoctorError, match="not enabled"):
            run_doctor()

    def test_doctor_enabled(self, owner):
        os.environ["OWNERAI_FEATURE_DOCTOR"] = "1"
        try:
            report = run_doctor()
            assert report.overall in ("ok", "degraded", "critical")
            assert len(report.checks) == 4  # database, disk, model, cameras
            names = {c.name for c in report.checks}
            assert names == {"database", "disk", "model", "cameras"}
        finally:
            os.environ.pop("OWNERAI_FEATURE_DOCTOR", None)

    def test_benchmark(self, owner):
        os.environ["OWNERAI_FEATURE_DOCTOR"] = "1"
        try:
            result = benchmark_provider(runs=3)
            assert result["runs"] == 3
            assert "provider" in result
            assert "errors" in result
        finally:
            os.environ.pop("OWNERAI_FEATURE_DOCTOR", None)


class TestDoctorEndpoints:
    def test_doctor_requires_flag(self, owner):
        resp = owner.get("/api/doctor")
        assert resp.status_code == 403

    def test_doctor_enabled(self, owner):
        os.environ["OWNERAI_FEATURE_DOCTOR"] = "1"
        try:
            resp = owner.get("/api/doctor")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert "overall" in data
            assert "checks" in data
        finally:
            os.environ.pop("OWNERAI_FEATURE_DOCTOR", None)

    def test_benchmark_endpoint(self, owner):
        os.environ["OWNERAI_FEATURE_DOCTOR"] = "1"
        try:
            resp = owner.get("/api/doctor/benchmark?runs=3")
            assert resp.status_code == 200, resp.text
        finally:
            os.environ.pop("OWNERAI_FEATURE_DOCTOR", None)


class TestMCP:
    def test_mcp_disabled(self):
        runtime = MCPRuntime()
        assert runtime.list_tools() == []

    def test_mcp_register_and_call(self, owner):
        os.environ["OWNERAI_FEATURE_MCP_RUNTIME"] = "1"
        try:
            runtime = MCPRuntime()

            def echo_handler(args):
                return {"echo": args.get("text", "")}

            runtime.register(
                "echo",
                "Echo back text",
                {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                echo_handler,
                mutating=False,
            )

            tools = runtime.list_tools()
            assert len(tools) == 1
            assert tools[0]["name"] == "echo"
            assert tools[0]["mutating"] is False

            result = runtime.call("echo", {"text": "hello"})
            assert result["status"] == "ok"
            assert result["result"] == {"echo": "hello"}

            # Missing required arg
            with pytest.raises(MCPError, match="missing required argument"):
                runtime.call("echo", {})

            # Mutating tool requires confirmation
            def set_handler(args):
                return {"set": args.get("key")}

            runtime.register(
                "set",
                "Set a value",
                {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
                set_handler,
                mutating=True,
            )
            unconfirmed = runtime.call("set", {"key": "x"})
            assert unconfirmed["status"] == "requires_confirmation"

            confirmed = runtime.call("set", {"key": "x"}, confirmed=True)
            assert confirmed["status"] == "ok"

            # Unknown tool
            with pytest.raises(MCPError, match="unknown tool"):
                runtime.call("nonexistent", {})
        finally:
            os.environ.pop("OWNERAI_FEATURE_MCP_RUNTIME", None)


class TestMCPEndpoints:
    def test_mcp_requires_flag(self, owner):
        resp = owner.get("/api/mcp/tools")
        assert resp.status_code == 403


class TestWakeWord:
    def test_wake_word_disabled(self):
        assert _wake_word.register_wake_word("s1", "d1") is None
        assert _wake_word.get_session("s1") is None

    def test_wake_word_session(self, owner):
        os.environ["OWNERAI_FEATURE_WAKE_WORD"] = "1"
        try:
            session = _wake_word.register_wake_word("sess-1", "device-1", ttl_seconds=30)
            assert session is not None
            assert session.is_active()

            got = _wake_word.get_session("sess-1")
            assert got is not None
            assert got.session_id == "sess-1"

            recorded = _wake_word.record_command(
                "sess-1", "turn on the light", "device_control", "done"
            )
            assert recorded is True

            active = _wake_word.list_active_sessions()
            assert len(active) == 1
            assert active[0]["command_count"] == 1
        finally:
            os.environ.pop("OWNERAI_FEATURE_WAKE_WORD", None)


class TestWakeWordEndpoints:
    def test_wake_word_requires_flag(self, owner):
        resp = owner.post("/api/wake-word/detected", json={"session_id": "s1", "device_id": "d1"})
        assert resp.status_code == 403

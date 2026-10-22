"""Tests for JARVIS features integrated into ownerai: tools, voice commands, HUD, and telemetry."""

import pytest
from sqlalchemy.orm import Session
from ownerai.db import get_engine
from ownerai.services.ai import execute_tool, TOOL_SPECS
from ownerai.services.voice import build_command
from ownerai.models import User, Role


def test_ownerai_jarvis_tool_specs():
    """Verify market, mail, and system action tools exist in TOOL_SPECS."""
    assert "get_stock_analysis" in TOOL_SPECS
    assert "get_market_overview" in TOOL_SPECS
    assert "get_mail_brief" in TOOL_SPECS
    assert "system_action" in TOOL_SPECS
    assert TOOL_SPECS["get_stock_analysis"]["mutating"] is False
    assert TOOL_SPECS["system_action"]["mutating"] is True


def test_ownerai_execute_market_and_mail_tools(client, owner):
    """Verify execution of non-mutating JARVIS tools."""
    with Session(get_engine()) as session:
        user = session.query(User).filter_by(role=Role.OWNER).first()
        if not user:
            user = User(
                email="owner_jarvis@example.test",
                password_hash="argon2id$mock",
                role=Role.OWNER,
                is_active=True,
            )
            session.add(user)
            session.commit()

        # Market overview
        res_market = execute_tool(session, user, "get_market_overview", {})
        assert res_market["status"] == "ok"
        assert "briefing" in res_market["result"]

        # Stock analysis
        res_stock = execute_tool(session, user, "get_stock_analysis", {"symbol": "^NSEI"})
        assert res_stock["status"] == "ok"
        assert "signal" in res_stock["result"]

        # Mail brief
        res_mail = execute_tool(session, user, "get_mail_brief", {})
        assert res_mail["status"] == "ok"
        assert "briefing" in res_mail["result"]


def test_ownerai_execute_mutating_system_tool_requires_confirmation(client, owner):
    """Mutating system action tool must require explicit confirmation."""
    with Session(get_engine()) as session:
        user = session.query(User).filter_by(role=Role.OWNER).first()
        if not user:
            user = User(
                email="owner_system@example.test",
                password_hash="argon2id$mock",
                role=Role.OWNER,
                is_active=True,
            )
            session.add(user)
            session.commit()

        # Without confirmation
        unconfirmed = execute_tool(session, user, "system_action", {"target": "terminal"}, confirmed=False)
        assert unconfirmed["status"] == "requires_confirmation"

        # With confirmation
        confirmed = execute_tool(session, user, "system_action", {"target": "terminal"}, confirmed=True)
        assert confirmed["status"] == "ok"


def test_ownerai_voice_commands_jarvis(client, owner):
    """Verify voice commands for HUD navigation, market report, mail brief, and time."""
    with Session(get_engine()) as session:
        user = session.query(User).filter_by(role=Role.OWNER).first()

        # Open HUD
        cmd_hud = build_command(session, user, "Jarvis, open the hud")
        assert cmd_hud.intent == "open_hud"
        assert cmd_hud.action.get("url") == "/hud"

        # Market Report
        cmd_market = build_command(session, user, "Stock market report")
        assert cmd_market.intent == "market_report"
        assert len(cmd_market.answer) > 10

        # Mail Brief
        cmd_mail = build_command(session, user, "Read unread emails")
        assert cmd_mail.intent == "mail_brief"
        assert "unread" in cmd_mail.answer.lower() or "mail" in cmd_mail.answer.lower()

        # Time and Date
        cmd_time = build_command(session, user, "What time is it?")
        assert cmd_time.intent == "current_time"
        assert "currently" in cmd_time.answer.lower()


def test_hud_endpoints(client):
    """Verify HUD state API returns system vitals, market quotes, and mic simulation."""
    res = client.get("/api/hud/state")
    assert res.status_code == 200
    data = res.json()
    assert "vitals" in data
    assert "cpu" in data["vitals"]
    assert "ram" in data["vitals"]
    assert "stocks" in data
    assert isinstance(data["stocks"], list)
    assert "state" in data

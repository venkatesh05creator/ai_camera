"""Tests for integrated JARVIS capabilities: Market Intelligence, System Actions, and Orchestration."""

import pytest
from backend.app.agents.jarvis_orchestrator import JarvisOrchestrator
from backend.app.agents.contracts import AgentType
from backend.app.services.market_service import (
    DEFAULT_TICKERS,
    analyze_ticker,
    market_briefing,
    get_market_watchlist,
)
from backend.app.services.system_actions import (
    launch_application,
    search_youtube,
    search_google,
    send_whatsapp_web,
    get_mail_briefing,
    set_system_volume,
    get_current_time_and_date,
)


def test_market_service_ticker_analysis():
    """Verify market analysis returns valid momentum, technical signals, and sparkline data."""
    data = analyze_ticker("^NSEI")
    assert data is not None
    assert data["symbol"] == "^NSEI"
    assert "price" in data
    assert "signal" in data
    assert data["signal"] in ["STRONG BUY", "BUY / ACCUMULATE", "HOLD", "SELL / TAKE PROFIT", "STRONG SELL / SHORT"]
    assert "spark" in data
    assert isinstance(data["spark"], list)


def test_market_service_briefing_and_watchlist():
    """Verify spoken market briefing and structured watchlist telemetry."""
    briefing = market_briefing()
    assert isinstance(briefing, str)
    assert len(briefing) > 10

    watchlist = get_market_watchlist()
    assert len(watchlist) == len(DEFAULT_TICKERS)
    symbols = [w["symbol"] for w in watchlist]
    assert "RELIANCE.NS" in symbols
    assert "NVDA" in symbols


def test_system_actions_utilities():
    """Verify YouTube, Google, WhatsApp, and mail briefing handlers."""
    yt = search_youtube("lofi hip hop")
    assert yt["success"] is True
    assert "youtube.com/results" in yt["url"]

    ggl = search_google("FastAPI multi-agent")
    assert ggl["success"] is True
    assert "google.com/search" in ggl["url"]

    wa = send_whatsapp_web("Pallavi", "Team sync in 10 minutes")
    assert wa["success"] is True
    assert "web.whatsapp.com/send" in wa["url"]

    mail = get_mail_briefing()
    assert isinstance(mail, str)
    assert "unread" in mail.lower() or "mail" in mail.lower()

    td = get_current_time_and_date()
    assert "time" in td and "date" in td


def test_system_volume_controls():
    """Verify system volume commands complete safely without exception."""
    res_mute = set_system_volume("mute")
    assert "message" in res_mute
    res_up = set_system_volume("louder")
    assert "message" in res_up


def test_jarvis_orchestrator_market_routing():
    """Verify JarvisOrchestrator routes stock queries to Market Intelligence."""
    res = JarvisOrchestrator.dispatch("Jarvis, what is the stock market report?")
    assert res.agent_type == AgentType.RESEARCH
    assert res.status == "success"
    assert "market" in res.answer.lower() or "nifty" in res.answer.lower()


def test_jarvis_orchestrator_specific_stock_routing():
    """Verify JarvisOrchestrator analyzes specific stocks like Reliance."""
    res = JarvisOrchestrator.dispatch("Should I buy Reliance stock?")
    assert res.agent_type == AgentType.RESEARCH
    assert res.status == "success"
    assert "reliance" in res.answer.lower()
    assert "signal" in res.answer.lower()


def test_jarvis_orchestrator_app_and_media_routing():
    """Verify JarvisOrchestrator handles app launch, YouTube playback, and WhatsApp."""
    # YouTube
    res_yt = JarvisOrchestrator.dispatch("Play lofi music on YouTube")
    assert res_yt.agent_type == AgentType.ACTION
    assert res_yt.status == "success"
    assert "youtube" in res_yt.answer.lower()

    # WhatsApp
    res_wa = JarvisOrchestrator.dispatch("Send message on WhatsApp to Pallavi saying Hello")
    assert res_wa.agent_type == AgentType.ACTION
    assert res_wa.status == "success"
    assert "whatsapp" in res_wa.answer.lower()

    # Mail Briefing
    res_mail = JarvisOrchestrator.dispatch("Jarvis, check my unread emails")
    assert res_mail.agent_type == AgentType.RESEARCH
    assert res_mail.status == "success"
    assert "unread" in res_mail.answer.lower() or "mail" in res_mail.answer.lower()

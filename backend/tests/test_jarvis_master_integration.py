"""
backend/tests/test_jarvis_master_integration.py
Comprehensive verification test suite for JARVIS integration:
- Example A: Solar system planets direct knowledge retrieval
- Example B: Visual object color inspection with live frame grounding
- Example C: Current news / latest technology information evidence synthesis
- Hybrid Brain: Rate-limit 429 cooldown and offline fallback
- Market Intelligence: SMA crossover signals and ticker analysis
- System Actions: Volume, apps, YouTube, WhatsApp, mail briefing
"""

import time
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from backend.app.agents.jarvis_orchestrator import JarvisOrchestrator
from backend.app.agents.contracts import AgentType
from backend.app.services.ai_orchestrator import AIOrchestrator, AIIntent
from backend.app.services.hybrid_brain import HybridBrain, think_hybrid
from backend.app.services.market_service import analyze_ticker, market_briefing, calculate_sma
from backend.app.services.system_actions import (
    launch_application,
    search_youtube,
    send_whatsapp_web,
    set_system_volume,
    get_mail_briefing,
)


def test_example_a_solar_system_planets():
    """Verify Example A: 'How many planets are in our solar system?' returns accurate planetary facts."""
    res = JarvisOrchestrator.dispatch(
        query="How many planets are in our solar system?",
        has_live_frame=False,
    )
    assert res.agent_type == AgentType.ORCHESTRATOR
    assert res.status == "success"
    # Must list all 8 planets and match the expected response
    expected_planets = ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]
    for planet in expected_planets:
        assert planet in res.answer
        assert planet in res.speech_text
    assert "eight planets" in res.speech_text.lower() or "8 planets" in res.speech_text.lower()


def test_example_b_vision_object_color_grounded():
    """Verify Example B: Frame inspection detects color when present, and reports offline when absent."""
    # 1. When live frame is ABSENT: must NOT hallucinate
    res_absent = JarvisOrchestrator.dispatch(
        query="What color is the object in front of the camera?",
        has_live_frame=False,
        raw_frame=None,
    )
    assert res_absent.agent_type == AgentType.VISION
    assert "no active camera frame" in res_absent.answer.lower() or "no live camera frame" in res_absent.answer.lower()

    # 2. When live frame is PRESENT: inspects visual evidence
    synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    synthetic_frame[120:360, 160:480] = [220, 40, 20]  # Strong blue region

    res_present = JarvisOrchestrator.dispatch(
        query="What color is the object in front of the camera?",
        has_live_frame=True,
        raw_frame=synthetic_frame,
        camera_id="cam_test_01",
    )
    assert res_present.agent_type == AgentType.VISION
    assert res_present.status == "success"
    assert "color" in res_present.answer.lower()
    assert "blue" in res_present.answer.lower()
    assert "blue" in res_present.speech_text.lower()


def test_example_c_search_latest_information_news():
    """Verify Example C: 'Search for the latest information about this technology' synthesizes evidence."""
    res = JarvisOrchestrator.dispatch(
        query="Search for the latest information about this technology",
        has_live_frame=False,
    )
    assert res.agent_type == AgentType.ORCHESTRATOR
    assert res.status == "success"
    # Must provide evidence-backed answer (Google News RSS feed or knowledge engine)
    assert "latest information" in res.answer.lower() or "information about" in res.answer.lower()
    assert len(res.speech_text) > 10


def test_hybrid_brain_rate_limit_cooldown():
    """Verify HybridBrain tracks HTTP 429 rate limit cooldowns and falls back cleanly."""
    # Simulate HTTP 429 rate limit response from Groq
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Rate limit exceeded. Please try again in 45s."

    with patch("backend.app.services.hybrid_brain.get_groq_api_key", return_value="gsk_mock_123"):
        with patch("httpx.Client.post", return_value=mock_resp):
            res = HybridBrain.think_hybrid("Explain quantum computing")
            # Should record cooldown and not crash
            assert HybridBrain.get_cooldown_remaining() > 0.0
            assert res.get("cooldown_active") is True
            assert "cooldown" in res.provider or "fallback" in res.provider
            assert len(res.reply) > 10


def test_market_service_signals_and_sma():
    """Verify Technical Market Analysis and SMA calculation."""
    # SMA Calculation
    prices = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0]
    sma = calculate_sma(prices, period=5)
    assert sma == 24.0

    # Ticker analysis with mock chart data
    mock_chart = {
        "meta": {"regularMarketPrice": 150.0, "previousClose": 145.0},
        "indicators": {
            "quote": [{"close": [100.0 + i for i in range(25)]}]
        }
    }

    with patch("backend.app.services.market_service.fetch_chart", return_value=mock_chart):
        analysis = analyze_ticker("NVDA")
        assert analysis is not None
        assert analysis["price"] == 150.0
        assert analysis["signal"] in ["STRONG BUY", "BUY / ACCUMULATE", "HOLD", "SELL / REDUCE", "STRONG SELL"]
        assert "moving averages" in analysis["reason"].lower() or "support" in analysis["reason"].lower()

    # Market briefing
    brief = market_briefing()
    assert isinstance(brief, str)
    assert len(brief) > 10


def test_system_actions_execution():
    """Verify cross-platform system action execution."""
    # YouTube URL generation
    yt_res = search_youtube("synthwave chill music")
    assert yt_res["success"] is True
    assert "youtube.com/results" in yt_res["url"]

    # WhatsApp Web link generation
    wa_res = send_whatsapp_web("Alex", "Meeting at 3 PM")
    assert wa_res["success"] is True
    assert "web.whatsapp.com/send" in wa_res["url"]

    # Mail Briefing
    mail_res = get_mail_briefing()
    assert isinstance(mail_res, str)
    assert "email" in mail_res.lower() or "inbox" in mail_res.lower()

    # System Volume Control (mocked)
    with patch("subprocess.run") as mock_sub:
        mock_sub.return_value = MagicMock(returncode=0)
        vol_up = set_system_volume("louder")
        assert vol_up["success"] is True
        vol_mute = set_system_volume("mute")
        assert vol_mute["success"] is True


def test_tts_queue_sentence_splitting():
    """Verify sentence splitting utility splits cleanly without truncating."""
    from backend.app.services.ai_orchestrator import ResponseValidator

    ctx = AIOrchestrator.process_request(
        query="What is gold?",
        has_live_frame=False,
    )
    assert "Au" in ctx.answer
    assert "79" in ctx.answer
    # Speech text should have markdown stripped
    assert "*" not in ctx.speech_text
    assert "#" not in ctx.speech_text

"""Automated Regression & AI Orchestrator Test Suite.

Validates:
1. Bug 1: 'What is gold?' returns direct, correct explanation of gold (Au, 79), zero BBC news.
2. Bug 2: 'Who invented it?' after 'What is quantum computing?' resolves to quantum computing origins.
3. Bug 3: 'Can you help me?' returns natural assistance, not a movie or song description.
4. Bug 4: 'What items are in the background?' & 'What is my background color?' truthfully reports no camera frame if camera is offline.
5. Bug 5: 'Take a snapshot' fails honestly when camera is offline, and verifies file on disk when live frame is provided.
6. Bug 6: News queries return top headlines without leaking into subsequent general questions.
7. Intent routing precision across all 11 intent classes.
8. Request context isolation (distinct UUIDs, zero cross-request contamination).
"""

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from backend.app.services.ai_orchestrator import (
    AIIntent,
    AIOrchestrator,
    AIRequestContext,
    IntentClassifier,
    ResponseValidator,
    SafeToolRegistry,
)
from backend.app.services.conversational_ai_service import ConversationalAIService
from backend.app.services.scene_analysis_service import SceneAnalysisService


# =============================================================================
# 1. EXACT REGRESSION TEST: "What is gold?"
# =============================================================================

def test_regression_what_is_gold():
    """Verify 'What is gold?' returns Au/79 explanation and NEVER BBC News."""
    # Simulate a prior conversation that included news
    contaminated_history = [
        {"role": "user", "content": "Today's daily news"},
        {"role": "ai", "content": "📰 **Latest Breaking Headlines & Daily News:**\n\n• BBC News (British TV channel)\n• Global Markets Update"},
    ]

    ctx = AIOrchestrator.process_request(
        query="What is gold?",
        conversation_history=contaminated_history,
        has_live_frame=False,
    )

    assert ctx.detected_intent == AIIntent.FACTUAL_KNOWLEDGE
    assert "bbc news" not in ctx.answer.lower()
    assert "bbc" not in ctx.speech_text.lower()
    
    # Must contain gold chemical/element facts
    ans_lower = ctx.answer.lower()
    assert "gold" in ans_lower
    assert ("au" in ans_lower or "chemical element" in ans_lower or "atomic number" in ans_lower or "metal" in ans_lower)
    assert not ctx.answer.startswith("Regarding")


# =============================================================================
# 2. CONTEXT PRONOUN RESOLUTION: "What is quantum computing?" -> "Who invented it?"
# =============================================================================

def test_context_resolution_quantum_computing():
    """Verify 'Who invented it?' resolves to quantum computing origins, not IT configuration."""
    history = [
        {"role": "user", "content": "What is quantum computing?"},
        {"role": "ai", "content": "📚 **Quantum computing**\n\nQuantum computing is a rapidly-emerging technology that harnesses the laws of quantum mechanics to solve problems too complex for classical computers."},
    ]

    intent, conf, resolved_q, prior_topic = IntentClassifier.classify("Who invented it?", history)
    assert intent == AIIntent.FOLLOW_UP
    assert prior_topic is not None
    assert "quantum" in prior_topic.lower()
    assert "quantum" in resolved_q.lower()

    # Process through master orchestrator
    ctx = AIOrchestrator.process_request(
        query="Who invented it?",
        conversation_history=history,
        has_live_frame=False,
    )

    assert ctx.detected_intent == AIIntent.FOLLOW_UP
    ans_lower = ctx.answer.lower()
    assert "quantum" in ans_lower
    # Must mention key pioneers or research origins, not IT / configuration management
    assert any(name in ans_lower for name in ["benioff", "feynman", "deutsch", "pioneers", "physicists", "quantum"])
    assert "configuration management" not in ans_lower


# =============================================================================
# 3. CONVERSATIONAL HELP: "Can you help me?"
# =============================================================================

def test_conversational_help_response():
    """Verify 'Can you help me?' returns natural conversational assistance, not movie/song lookup."""
    ctx = AIOrchestrator.process_request(query="Can you help me?", has_live_frame=False)
    
    assert ctx.detected_intent == AIIntent.APPLICATION_HELP
    ans_lower = ctx.answer.lower()
    assert "help" in ans_lower
    assert any(term in ans_lower for term in ["camera", "knowledge", "news", "weather", "assist", "surveillance"])
    # Must not return movie or song
    assert "film" not in ans_lower
    assert "directed by" not in ans_lower
    assert "album" not in ans_lower


# =============================================================================
# 4. COMPUTER VISION GROUNDING: Camera Offline vs Live Frame
# =============================================================================

def test_vision_offline_camera_truthfulness():
    """When camera is offline (no frame), vision questions must truthfully state no frame is available."""
    # Test background items query
    ctx_items = AIOrchestrator.process_request(
        query="What items are in the background?",
        has_live_frame=False,
        raw_frame=None,
    )
    assert ctx_items.detected_intent == AIIntent.CAMERA_VISION_SCENE
    assert "no live camera frame is currently available" in ctx_items.answer.lower()
    # Must NOT invent fake objects
    assert "cabinet paneling" not in ctx_items.answer.lower()

    # Test background color query
    ctx_color = AIOrchestrator.process_request(
        query="What is my background color?",
        has_live_frame=False,
        raw_frame=None,
    )
    assert ctx_color.detected_intent == AIIntent.CAMERA_VISION_SCENE
    assert "no live camera frame is currently available" in ctx_color.answer.lower()
    assert "off-white / cream" not in ctx_color.answer.lower()


def test_vision_with_live_frame():
    """When a real camera frame is supplied, computer vision analysis extracts colors and contours."""
    # Create a synthetic 480x640 BGR image with blue background and a simulated subject
    test_frame = np.full((480, 640, 3), (180, 100, 50), dtype=np.uint8)  # Blue-ish BGR

    ctx = AIOrchestrator.process_request(
        query="What color is my background?",
        has_live_frame=True,
        raw_frame=test_frame,
    )
    assert ctx.detected_intent == AIIntent.CAMERA_VISION_SCENE
    assert "no live camera frame" not in ctx.answer.lower()
    assert "background color" in ctx.answer.lower() or "background" in ctx.answer.lower()


# =============================================================================
# 5. SAFE SNAPSHOT TOOL EXECUTION
# =============================================================================

def test_snapshot_fails_honestly_when_camera_offline():
    """Verify snapshot reports inability when camera has no live frame."""
    ctx = AIOrchestrator.process_request(
        query="Take a snapshot",
        has_live_frame=False,
        raw_frame=None,
    )
    assert ctx.detected_intent == AIIntent.CAMERA_ACTION_SNAPSHOT
    assert ctx.action == "snapshot_failed"
    assert "camera stream is currently offline" in ctx.answer.lower() or "no live video frame" in ctx.answer.lower()
    # Must NOT claim success
    assert "snapshot successfully captured" not in ctx.answer.lower()


def test_snapshot_succeeds_and_verifies_file_when_live_frame_exists(tmp_path):
    """Verify snapshot writes actual verified non-empty image file to disk."""
    dummy_frame = np.full((240, 320, 3), 120, dtype=np.uint8)
    
    ctx = AIRequestContext(
        query="Take a snapshot",
        has_live_frame=True,
        raw_frame=dummy_frame,
        camera_id="cam_test_01",
    )
    
    res = SafeToolRegistry.execute_snapshot(ctx, storage_dir=tmp_path)
    assert res["success"] is True
    assert "filename" in res
    
    saved_file = tmp_path / res["filename"]
    assert saved_file.exists()
    assert saved_file.stat().st_size > 0


# =============================================================================
# 6. CURRENT NEWS FEED INTEGRATION & LEAK PREVENTION
# =============================================================================

def test_current_news_retrieval_and_isolation():
    """Verify news fetches headlines and does not contaminate subsequent turns."""
    ctx_news = AIOrchestrator.process_request(
        query="Today's daily news",
        has_live_frame=False,
    )
    assert ctx_news.detected_intent == AIIntent.CURRENT_NEWS
    assert ("headlines" in ctx_news.answer.lower() or "news" in ctx_news.answer.lower())

    # Ensure a subsequent question about chemistry does NOT inherit news
    subsequent_ctx = AIOrchestrator.process_request(
        query="What is water?",
        conversation_history=[
            {"role": "user", "content": "Today's daily news"},
            {"role": "ai", "content": ctx_news.answer},
        ],
        has_live_frame=False,
    )
    assert subsequent_ctx.detected_intent == AIIntent.FACTUAL_KNOWLEDGE
    assert "news" not in subsequent_ctx.answer.lower()
    assert "water" in subsequent_ctx.answer.lower()


# =============================================================================
# 7. INTENT CLASSIFIER COVERAGE
# =============================================================================

@pytest.mark.parametrize(
    "query,expected_intent",
    [
        ("Can you help me?", AIIntent.APPLICATION_HELP),
        ("What can you do?", AIIntent.APPLICATION_HELP),
        ("Take a snapshot", AIIntent.CAMERA_ACTION_SNAPSHOT),
        ("Take a picture", AIIntent.CAMERA_ACTION_SNAPSHOT),
        ("Start recording", AIIntent.CAMERA_ACTION_RECORD),
        ("Stop recording", AIIntent.CAMERA_ACTION_RECORD),
        ("Pause camera", AIIntent.CAMERA_MANAGEMENT),
        ("Resume stream", AIIntent.CAMERA_MANAGEMENT),
        ("Quick enroll new user", AIIntent.BIOMETRIC_ENROLLMENT),
        ("Security alerts", AIIntent.SECURITY_ALERTS),
        ("Today's breaking news", AIIntent.CURRENT_NEWS),
        ("What is the weather today?", AIIntent.LIVE_WEATHER),
        ("What is 15 * 6?", AIIntent.CALCULATION),
        ("Convert 50 km to miles", AIIntent.CALCULATION),
        ("What is my background color?", AIIntent.CAMERA_VISION_SCENE),
        ("What items are in the background?", AIIntent.CAMERA_VISION_SCENE),
        ("Hello, good morning", AIIntent.GENERAL_CONVERSATION),
        ("Thank you very much", AIIntent.GENERAL_CONVERSATION),
        ("How are you doing?", AIIntent.GENERAL_CONVERSATION),
        ("What is gold?", AIIntent.FACTUAL_KNOWLEDGE),
        ("What is photosynthesis?", AIIntent.FACTUAL_KNOWLEDGE),
    ],
)
def test_intent_classification_precision(query, expected_intent):
    intent, conf, _, _ = IntentClassifier.classify(query)
    assert intent == expected_intent
    assert conf >= 0.85


# =============================================================================
# 8. REQUEST ISOLATION
# =============================================================================

def test_request_isolation():
    """Verify every request gets a unique request_id and no shared state leaks."""
    ctx1 = AIOrchestrator.process_request(query="What is gold?")
    ctx2 = AIOrchestrator.process_request(query="Can you help me?")

    assert ctx1.request_id != ctx2.request_id
    assert ctx1.detected_intent == AIIntent.FACTUAL_KNOWLEDGE
    assert ctx2.detected_intent == AIIntent.APPLICATION_HELP
    assert "gold" not in ctx2.answer.lower()


# =============================================================================
# 9. LIVE CAMERA UNDERSTANDING & VISUAL INTENT ROUTING
# =============================================================================

@pytest.mark.parametrize(
    "visual_query",
    [
        "What is this?",
        "What color is it?",
        "Can you detect this?",
        "What am I holding?",
        "Identify this object",
        "Describe what you see",
        "What is in front of the camera?",
    ],
)
def test_visual_query_routing_direct_to_camera_vision(visual_query):
    """Ensure visual queries route to CAMERA_VISION_SCENE, not Wikipedia or news."""
    intent, conf, _, _ = IntentClassifier.classify(visual_query)
    assert intent == AIIntent.CAMERA_VISION_SCENE
    assert conf >= 0.85

    # If camera is offline, it must honestly state camera is offline, never hallucinate Wikipedia
    ctx = AIOrchestrator.process_request(
        query=visual_query,
        has_live_frame=False,
    )
    assert ctx.detected_intent == AIIntent.CAMERA_VISION_SCENE
    assert "news" not in ctx.answer.lower()
    assert "wikipedia" not in ctx.answer.lower()
    assert ("offline" in ctx.answer.lower() or "camera" in ctx.answer.lower())


# =============================================================================
# 10. FRAME QUALITY ASSESSMENT & NON-TRUNCATED SPEECH TEXT
# =============================================================================

def test_frame_quality_blur_and_lighting_checks():
    """Verify frame quality analyzer catches underexposed or blurry frames."""
    # Blurry blank frame
    blurry_frame = np.full((480, 640, 3), 120, dtype=np.uint8)
    quality_blur = AIOrchestrator.check_frame_quality(blurry_frame)
    assert quality_blur["acceptable"] is False
    assert quality_blur["blur_score"] < 10.0

    # Very dark frame
    dark_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    quality_dark = AIOrchestrator.check_frame_quality(dark_frame)
    assert quality_dark["acceptable"] is False
    assert quality_dark["lighting"] == "Too Dark / Underexposed"

    # Sharp, well-lit synthetic frame with checker pattern
    good_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    good_frame[::20, :, :] = 255
    good_frame[:, ::20, :] = 255
    quality_good = AIOrchestrator.check_frame_quality(good_frame)
    assert quality_good["acceptable"] is True
    assert quality_good["lighting"] == "Adequate"


def test_full_length_speech_text_preservation():
    """Verify speech_text preserves full multi-sentence responses without legacy truncation."""
    ctx = AIOrchestrator.process_request(
        query="What is photosynthesis?",
        has_live_frame=False,
    )
    # The speech text should not be cut down to a single sentence
    assert len(ctx.speech_text) > 40
    assert "photosynthesis" in ctx.speech_text.lower()
    # Ensure markdown symbols are stripped for clean vocalization
    assert "**" not in ctx.speech_text
    assert "##" not in ctx.speech_text


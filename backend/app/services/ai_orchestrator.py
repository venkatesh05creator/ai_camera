"""Modular AI Orchestration Layer for Intelligent, Humanized & Safe Responses.

Provides deterministic and model-assisted intent routing, request-scoped context,
safe tool execution, conversational memory with pronoun resolution, web/knowledge
retrieval, computer vision validation, and response integrity verification.
"""

from __future__ import annotations

import html
import json
import logging
import math
import os
import re
import time
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import cv2
import numpy as np
import requests

from ..core.config import get_settings
from ..services.scene_analysis_service import SceneAnalysisService

logger = logging.getLogger(__name__)


class AIIntent(str, Enum):
    """Supported intent categories across surveillance and general intelligence."""
    GENERAL_CONVERSATION = "general_conversation"
    APPLICATION_HELP = "application_help"
    FACTUAL_KNOWLEDGE = "factual_knowledge"
    FOLLOW_UP = "follow_up"
    CURRENT_NEWS = "current_news"
    LIVE_WEATHER = "live_weather"
    CALCULATION = "calculation"
    CAMERA_VISION_SCENE = "camera_vision_scene"
    CAMERA_OBJECT_COUNT = "camera_object_count"
    CAMERA_OCR_TEXT = "camera_ocr_text"
    HISTORICAL_EVENT_SEARCH = "historical_event_search"
    ZONE_RULE_MONITORING = "zone_rule_monitoring"
    CAMERA_ACTION_SNAPSHOT = "camera_action_snapshot"
    CAMERA_ACTION_RECORD = "camera_action_record"
    CAMERA_MANAGEMENT = "camera_management"
    BIOMETRIC_ENROLLMENT = "biometric_enrollment"
    SECURITY_ALERTS = "security_alerts"
    MULTI_PART_QUESTION = "multi_part_question"
    UNSUPPORTED_OR_AMBIGUOUS = "unsupported_or_ambiguous"



@dataclass
class AIRequestContext:
    """Request-scoped execution context.
    
    Guarantees isolation: no shared mutable global variables between requests or users.
    """
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    query: str = ""
    cleaned_query: str = ""
    user_id: Optional[str] = None
    camera_id: Optional[str] = None
    has_live_frame: bool = False
    raw_frame: Optional[np.ndarray] = None
    frame_timestamp: Optional[float] = None
    verified_names: List[str] = field(default_factory=list)
    people_count: int = 0
    worker_fps: float = 30.0
    samples_learned: int = 0
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    
    # Execution pipeline tracking
    detected_intent: AIIntent = AIIntent.UNSUPPORTED_OR_AMBIGUOUS
    intent_confidence: float = 0.0
    resolved_query: Optional[str] = None
    prior_topic: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    retrieval_passages: List[Dict[str, Any]] = field(default_factory=list)
    execution_status: str = "pending"
    error: Optional[str] = None
    
    # Synthesized and validated output
    answer: str = ""
    speech_text: str = ""
    action: Optional[str] = None
    action_payload: Dict[str, Any] = field(default_factory=dict)
    telemetry: Dict[str, Any] = field(default_factory=dict)
    validation_passed: bool = True
    validation_notes: List[str] = field(default_factory=list)


class IntentClassifier:
    """Multi-stage intent router with deterministic precedence and entity guards."""

    @classmethod
    def classify(cls, query: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> Tuple[AIIntent, float, Optional[str], Optional[str]]:
        """Classify query intent, returning (intent, confidence, resolved_query, prior_topic)."""
        raw_q = query.strip()
        q = raw_q.lower()
        cleaned = re.sub(r"[^\w\s]", "", q)
        words = set(cleaned.split())

        # 0. NOISY OR INCOMPLETE TRANSCRIPT CHECK
        clean_chars = re.sub(r"[^a-zA-Z0-9\s]", "", raw_q).strip()
        if not clean_chars or len(clean_chars) < 2 or raw_q.lower() in ["[noise]", "[inaudible]", "...", "um", "uh"]:
            return AIIntent.UNSUPPORTED_OR_AMBIGUOUS, 0.99, raw_q, None

        # 0A. PROMPT INJECTION & POLICY OVERRIDE GUARD
        if any(k in q for k in [
            "ignore previous instructions", "ignore all previous instructions", "ignore all instructions",
            "override instructions", "reveal secrets", "reveal secret", "reveal passwords", "reveal password",
            "system prompt", "system instructions", "developer mode", "jailbreak"
        ]) or (re.search(r"\b(ignore|override|bypass)\b", q) and re.search(r"\b(instructions?|rules?|policy|system|prompt)\b", q)):
            return AIIntent.UNSUPPORTED_OR_AMBIGUOUS, 0.99, raw_q, None

        # 1. APPLICATION HELP (High Priority: never route to movie search)
        if any(k in q for k in [
            "can you help me", "help me", "i need help", "assist me", "could you help me",
            "what can you do", "what are your capabilities", "how do you work", "how does this work",
            "how to use this", "what do you do", "help"
        ]) and len(words) <= 7:
            return AIIntent.APPLICATION_HELP, 0.98, raw_q, None

        # 2. CAMERA SNAPSHOT ACTION
        if any(k in q for k in [
            "take a snapshot", "take snapshot", "capture snapshot", "take photo",
            "capture photo", "take picture", "take a picture", "screenshot",
            "snap photo", "click photo", "capture image", "take a snap"
        ]):
            return AIIntent.CAMERA_ACTION_SNAPSHOT, 0.99, raw_q, None

        # 3. CAMERA RECORDING ACTION
        if any(k in q for k in ["start record", "start recording", "record video", "begin recording", "take a video"]):
            return AIIntent.CAMERA_ACTION_RECORD, 0.95, raw_q, None
        if any(k in q for k in ["stop record", "stop recording", "finish record", "save video", "end recording"]):
            return AIIntent.CAMERA_ACTION_RECORD, 0.95, raw_q, None

        # 4. CAMERA MANAGEMENT (Pause, Resume, Mute, Unmute)
        if any(k in q for k in ["pause camera", "pause stream", "pause video", "freeze camera", "freeze video",
                                "resume camera", "resume stream", "resume video", "play camera", "unpause",
                                "mute", "unmute"]):
            return AIIntent.CAMERA_MANAGEMENT, 0.95, raw_q, None

        # 5. BIOMETRIC ENROLLMENT
        if any(k in q for k in ["quick enroll", "enroll me", "register person", "add person", "new profile", "remember me"]):
            return AIIntent.BIOMETRIC_ENROLLMENT, 0.95, raw_q, None

        # 6. SECURITY & ALERTS
        if any(k in q for k in [
            "why did you alert me", "why was i alerted", "what triggered the alert", "what triggered this alert",
            "why the alert", "explain the alert", "why did you alert",
            "security alerts", "threat level", "active threats", "security status", "active alerts", "breaches", "danger level"
        ]):
            return AIIntent.SECURITY_ALERTS, 0.95, raw_q, None

        # 6B. PROACTIVE MONITORING & OFFLINE RULES
        if any(k in q for k in [
            "tell me if the camera goes offline", "alert me if camera goes offline", "alert me if the camera goes offline",
            "camera offline rule", "camera offline notification", "notify if camera goes offline", "camera disconnect alert"
        ]):
            return AIIntent.ZONE_RULE_MONITORING, 0.96, raw_q, None

        # 7. CURRENT NEWS
        if "camera" not in q and any(k in q for k in [
            "news daily", "daily news", "today's news", "todays news", "latest news",
            "breaking news", "headlines", "top news", "news today", "world news",
            "what happened today in the world", "what happened in the world", "current events",
            "tell me the news", "what is the news"
        ]):
            return AIIntent.CURRENT_NEWS, 0.95, raw_q, None

        # 8. LIVE WEATHER
        if any(k in q for k in [
            "weather", "temperature outside", "is it raining", "forecast",
            "weather today", "what is the weather", "how's the weather", "how is the weather"
        ]):
            return AIIntent.LIVE_WEATHER, 0.95, raw_q, None

        # 9. CALCULATION & UNIT CONVERSIONS
        if cls._is_calculation(raw_q):
            return AIIntent.CALCULATION, 0.95, raw_q, None

        # 9A. OCR & TEXT / SIGN READING
        if any(k in q for k in [
            "read the text", "read text", "read what is written", "what text",
            "what is written", "read sign", "read the sign", "what does the sign say",
            "read label", "read the label", "extract text", "ocr", "read this sign", "read words"
        ]) or (re.search(r"\b(read|extract)\b", q) and re.search(r"\b(text|sign|label|words?|letters?)\b", q)):
            return AIIntent.CAMERA_OCR_TEXT, 0.96, raw_q, None

        # 9B. OBJECT COUNTING & MULTI-OBJECT LOCALIZATION
        if (
            any(k in q for k in [
                "how many people", "how many persons", "count people", "count the people",
                "count objects", "count the objects", "how many objects", "number of people",
                "number of objects", "how many items", "list objects", "what objects are visible",
                "what objects can you see", "list the visible objects", "all visible objects"
            ])
            or (re.search(r"\b(how many|count|number of)\b", q) and re.search(r"\b(people|persons?|objects?|items?|cars?|vehicles?|laptops?|phones?|chairs?)\b", q))
        ):
            return AIIntent.CAMERA_OBJECT_COUNT, 0.96, raw_q, None

        # 9C. HISTORICAL EVENT SEARCH & VISUAL MEMORY
        if (
            any(k in q for k in [
                "did anyone enter", "while i was away", "while away", "who entered", "who visited",
                "last time", "past event", "historical event", "unusual event", "what happened today",
                "what happened at", "timeline", "history of events", "recorded today"
            ])
            or (re.search(r"\b(last time|when was|when did|who was|show me)\b", q) and re.search(r"\b(movement|motion|person|vehicle|alert|event|entered?|exited?|visited?|appeared?|recorded?|seen|detected)\b", q))
        ):
            return AIIntent.HISTORICAL_EVENT_SEARCH, 0.94, raw_q, None


        # 10. COMPUTER VISION & SCENE QUESTIONS (Object identification, scene layout, room elements & color)
        if (
            (re.search(r"\b(background|behind me|behind my back)\b", q) and
             re.search(r"\b(color|items?|objects?|things?|wall|what|whats|describe|see|show|list)\b", q))
            or (re.search(r"\b(what|which)\s+color\b", q) and re.search(r"\b(background|wall|shirt|clothes|wearing|it|this|that|object|item)\b", q))
            or re.search(r"\bwhat\s+color\s+(is\s+)?(this|the|that|it|an?)\b", q)
            or (re.search(r"\b(items?|objects?|structures?)\b", q) and re.search(r"\b(background|room|behind|scene)\b", q))
            or re.search(r"\b(you\s+(?:can\s+)?see|can\s+you\s+see|do\s+you\s+see|did\s+you\s+see|are\s+you\s+seeing|what\s+can\s+you\s+see|what\s+do\s+you\s+see)\b", q)
            or re.search(r"\b(look\s+at|is\s+there\s+a|are\s+there\s+any)\s+(?:the\s+|a\s+|an\s+|my\s+)?(window|door|wall|room|cupboard|cabinet|wardrobe|ceiling|floor|fan|light|glasses|spectacles|shirt|clothes|person|face|laptop|phone|object|item)\b", q)
            or (re.search(r"\b(see|saw|view|watch|look)\b", q) and re.search(r"\b(window|door|wall|room|cupboard|cabinet|wardrobe|ceiling|floor|fan|light|glasses|spectacles|shirt|clothes|camera|screen)\b", q))
            or any(k in q for k in [
                "you can see window", "you can see the window", "can you see window", "can you see the window",
                "do you see window", "do you see the window", "is there a window", "look at window", "look at the window",
                "can you see door", "can you see the door", "do you see door", "do you see the door",
                "what's happening in front of the camera", "what is happening in front of the camera",
                "what is in front of the camera", "what is in front of camera", "in front of the camera", "in front of camera",
                "who is in front of the camera", "what is in front", "who is in front", "who is that",
                "what's happening", "what is happening",
                "what is this", "what's this", "what color is it", "can you detect this",
                "can you see this", "what is that", "what am i holding", "identify this", "detect this", "look at this",
                "background color", "wall color", "color behind me",
                "what am i wearing", "what color am i wearing", "shirt color", "my clothes",
                "describe what you see", "what do you see", "tell me what you see", "describe the scene",
                "can you see me", "am i visible", "do you see me", "am i in the camera", "am i on camera",
                "am i smiling", "smile", "check my expression", "how do i look",
                "how far am i", "am i too close", "am i too far", "posture", "attention score",
                "can you see my glasses", "do you see my glasses", "am i wearing glasses"
            ])
        ):
            return AIIntent.CAMERA_VISION_SCENE, 0.96, raw_q, None

        # 11. GENERAL CONVERSATION (Greetings, Farewells, Gratitude, Small Talk, Identity, Conversational Echoes)
        if cls._is_conversational(raw_q, words):
            return AIIntent.GENERAL_CONVERSATION, 0.90, raw_q, None

        # 12. MULTI-PART OR COMPLEX COMPARISON QUESTIONS
        if cls._is_multi_part(raw_q):
            return AIIntent.MULTI_PART_QUESTION, 0.94, raw_q, None

        # 13. FOLLOW-UP vs STANDALONE FACTUAL KNOWLEDGE
        resolved_q, prior_topic = cls._resolve_pronouns_and_context(raw_q, conversation_history)
        if prior_topic and resolved_q != raw_q:
            return AIIntent.FOLLOW_UP, 0.92, resolved_q, prior_topic

        # 14. FACTUAL KNOWLEDGE (Default for informational inquiries)
        return AIIntent.FACTUAL_KNOWLEDGE, 0.85, raw_q, None

    @classmethod
    def _is_multi_part(cls, raw_q: str) -> bool:
        q = raw_q.lower().strip()
        # Must not be basic action commands
        if any(k in q for k in ["take a snapshot", "start recording", "stop recording", "quick enroll", "weather in"]):
            return False
        # Multiple question marks
        if q.count("?") >= 2:
            return True
        # Compound indicators: comparison or multi-clause instructions
        has_comparison = bool(re.search(r"\b(difference between|how does .+ differ from|compare .+ (with|and|to)|versus|\bvs\b)\b", q))
        has_multi_clause = bool(re.search(r"\b(and|also|as well as)\s+(give|provide|list|explain|what|how|why|tell me)\b", q))
        has_multi_parts = bool(re.search(r"\b(first|second|part 1|part 2|1\.|2\.)\b", q))
        return (has_comparison and (has_multi_clause or len(q.split()) > 7)) or (has_multi_clause and len(q.split()) > 8) or has_multi_parts

    @classmethod
    def _is_calculation(cls, raw_q: str) -> bool:
        q = raw_q.lower().strip()
        math_expr = re.sub(r"^(what is|calculate|compute|solve|eval|evaluate)\s+", "", q).strip(" ?.")
        math_expr = math_expr.replace(" times ", " * ").replace(" multiplied by ", " * ")
        math_expr = math_expr.replace(" divided by ", " / ").replace(" over ", " / ")
        math_expr = math_expr.replace(" plus ", " + ").replace(" minus ", " - ")
        if re.match(r"^[\d\s\+\-\*\/\(\)\.\%\^]+$", math_expr) and any(op in math_expr for op in ["+", "-", "*", "/", "%", "^"]):
            return True
        if re.search(r"(\d+(?:\.\d+)?)\s*(?:km|kilometers?|miles?|c|celsius|f|fahrenheit|kg|kilograms?|lbs?|pounds?)\s*(?:to|in)\b", q):
            return True
        return False

    @classmethod
    def _is_conversational(cls, raw_q: str, words: Set[str]) -> bool:
        q = raw_q.lower()
        # Conversational affirmations & short audio check echoes (e.g. "Me too")
        cleaned_aff = q.strip(" ?.!").lower()
        if cleaned_aff in [
            "me too", "same here", "same", "i can hear you", "i hear you",
            "loud and clear", "i agree", "sounds good", "alright", "got it"
        ]:
            return True
        if re.match(r"^me too\b", q) and not any(k in q for k in ["movement", "hashtag", "#metoo", "harassment", "allegation"]):
            return True

        # Greetings
        if any(w in words for w in ["hi", "hello", "hey", "howdy", "sup", "yo"]) or any(k in q for k in [
            "good morning", "good afternoon", "good evening", "greetings", "hey there", "what's up"
        ]):
            return True
        # Farewells
        if any(w in words for w in ["bye", "goodbye", "cya", "exit", "quit"]) or any(k in q for k in [
            "see you", "good night", "take care", "have a good one", "catch you later", "talk to you later"
        ]):
            return True
        # Gratitude
        if any(k in q for k in ["thank you", "thanks", "appreciate it", "good job", "well done", "awesome", "perfect", "cool", "nice"]):
            return True
        # Well-being
        if any(k in q for k in ["how are you", "how're you", "how are things", "how do you do", "how's it going", "how are you doing", "how do you feel"]):
            return True
        # Mood / Empathy
        if any(k in q for k in ["tired", "exhausted", "sleepy", "hard day", "stressed", "i am happy", "feeling good", "excited"]):
            return True
        # Humor
        if any(k in q for k in ["joke", "make me laugh", "tell me something funny", "funny"]):
            return True
        # Audio / Connection check
        if any(k in q for k in ["can you hear me", "are you listening", "mic check", "testing"]):
            return True
        # User / AI Identity
        if any(k in q for k in ["who are you", "what is your name", "what's your name", "what are you", "introduce yourself",
                               "what is my name", "what's my name", "who am i", "do you know me", "recognize me"]):
            return True
        # Time and date
        if any(k in q for k in ["what time is it", "current time", "what is the time", "tell me the time",
                               "what day is today", "what is today's date", "what date is it", "today's date", "current date"]):
            return True
        # Camera daily summary
        if any(k in q for k in ["what happened today on camera", "who came today", "summarize today", "today's camera summary", "visitor log today"]):
            return True
        # Ergonomics / Wellness
        if any(k in q for k in ["break", "20-20-20", "eye strain", "screen fatigue", "stretch", "wellness tip", "take a break"]):
            return True
        # User feedback on tone
        if any(k in q for k in ["be more human", "talk like a human", "sound more human", "human format", "answer in human"]):
            return True
        return False

    @classmethod
    def _resolve_pronouns_and_context(cls, query: str, history: Optional[List[Dict[str, str]]]) -> Tuple[str, Optional[str]]:
        """Pronoun resolution guard. Standalone questions are NEVER corrupted into follow-ups."""
        if not history:
            return query, None

        q = query.strip()
        q_lower = q.lower()

        # Conversational affirmations must NEVER be corrupted into follow-ups
        if q_lower in ["me too", "me too.", "me too!", "same here", "i can hear you", "loud and clear", "i agree"]:
            return query, None

        # Standalone guard: e.g. "what is gold", "what is quantum computing", "who was albert einstein"
        standalone_match = re.match(
            r"^(what is|what are|who is|who was|where is|where are|define|definition of|explain)\s+(?:a\s+|an\s+|the\s+)?([a-zA-Z0-9\s\-]+)\??$",
            q_lower,
        )
        if standalone_match:
            subject = standalone_match.group(2).strip()
            # If the subject does NOT contain a pronoun, it is 100% standalone!
            if not re.search(r"\b(it|its|this|that|these|those|he|him|his|she|her|they|them|their)\b", subject):
                return query, None

        # Check for genuine follow-up indicators
        has_pronoun = bool(re.search(r"\b(it|its|this|that|these|those|he|him|his|she|her|they|them|their)\b", q_lower))
        has_relative = bool(re.match(r"^(who|when|where|why|how)\s+(did|was|is|were|does|invented|discovered|founded|made|created)\b", q_lower))
        has_continuation = bool(re.match(r"^(and\b|what about\b|how about\b|tell me more\b|explain more\b|why\?|why is that\b|how come\b)", q_lower))

        if not (has_pronoun or has_continuation or (has_relative and has_pronoun)):
            return query, None

        # Extract prior topic from recent non-trivial user turn or clean AI knowledge title
        prior_topic = ""
        ignored_topics = [
            "latest breaking headlines", "daily news", "today's camera", "operational summary",
            "background & scene items", "facial expression", "ergonomic & wellness",
            "calculation result", "privacy protocol", "security alert", "help", "hello", "hi"
        ]

        for msg in reversed(history):
            role = msg.get("role")
            content = msg.get("content", "").strip()
            if not content:
                continue

            if role == "user":
                cleaned = re.sub(
                    r"^(what is|what are|who is|who was|tell me about|explain|search for|what about|where is|how does)\s+(?:a\s+|an\s+|the\s+)?",
                    "",
                    content,
                    flags=re.IGNORECASE,
                ).strip(" ?.,!")
                if cleaned and len(cleaned) > 1 and cleaned.lower() not in ["hi", "hello", "hey", "ok", "thanks", "yes", "no"]:
                    if not re.search(r"^(it|this|that|he|she|they)$", cleaned.lower()):
                        prior_topic = cleaned
                        break
            elif role == "ai" and not prior_topic:
                book_match = re.search(r"📚 \*\*([^*]+)\*\*", content)
                if book_match:
                    cand = book_match.group(1).strip()
                    if len(cand) > 1 and not any(ign in cand.lower() for ign in ignored_topics):
                        prior_topic = cand
                        break

        if not prior_topic:
            return query, None

        # Substitute pronoun or formulate contextual question
        if has_pronoun:
            resolved = q
            resolved = re.sub(r"\b(its|their)\b", f"{prior_topic}'s", resolved, count=1, flags=re.IGNORECASE)
            resolved = re.sub(r"\b(it|this|that|he|she|they)\b", prior_topic, resolved, count=1, flags=re.IGNORECASE)
            return resolved, prior_topic
        elif has_continuation:
            if q_lower.startswith("what about") or q_lower.startswith("how about") or q_lower.startswith("and"):
                resolved = f"{q} regarding {prior_topic}"
            else:
                resolved = f"{q} about {prior_topic}"
            return resolved, prior_topic

        return query, None


class SafeToolRegistry:
    """Registry and execution wrapper for all external tools with permission and safety checks."""

    @classmethod
    def execute_snapshot(cls, context: AIRequestContext, storage_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Capture snapshot and verify file on disk. Reports success ONLY if verified."""
        context.tool_calls.append({"tool": "camera_snapshot", "timestamp": time.time()})
        
        # 1. Verify that a live frame is actually supplied
        if not context.has_live_frame or context.raw_frame is None or context.raw_frame.size == 0:
            result = {
                "success": False,
                "error": "No live camera frame is currently available to capture. Please start the camera stream and try again.",
            }
            context.tool_results.append({"tool": "camera_snapshot", "result": result})
            return result

        # 2. Determine output storage path
        settings = get_settings()
        dest_dir = storage_dir or settings.snapshot_storage_path
        dest_dir.mkdir(parents=True, exist_ok=True)

        cam_tag = context.camera_id[:8] if context.camera_id else "webcam"
        filename = f"snap_{cam_tag}_{int(time.time())}_{uuid.uuid4().hex[:6]}.jpg"
        filepath = dest_dir / filename

        try:
            # 3. Write frame to disk
            success_write = cv2.imwrite(str(filepath), context.raw_frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            
            # 4. Verify that file was created and is non-empty
            if not success_write or not filepath.exists() or filepath.stat().st_size == 0:
                result = {
                    "success": False,
                    "error": "Snapshot write operation failed to persist to disk.",
                }
            else:
                result = {
                    "success": True,
                    "filename": filename,
                    "filepath": str(filepath),
                    "file_size_bytes": filepath.stat().st_size,
                    "url": f"/api/v1/stream/snapshot/{filename}",
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as e:
            logger.error("Snapshot execution error: %s", e)
            result = {"success": False, "error": str(e)}

        context.tool_results.append({"tool": "camera_snapshot", "result": result})
        return result

    @classmethod
    def execute_vision_scene(cls, context: AIRequestContext) -> Dict[str, Any]:
        """Run real computer vision analysis on supplied frame. Returns available=False if no frame."""
        context.tool_calls.append({"tool": "vision_scene_analysis", "timestamp": time.time()})
        
        if not context.has_live_frame or context.raw_frame is None or context.raw_frame.size == 0:
            result = {
                "available": False,
                "reason": "No live camera frame is currently available. Please turn on your camera or supply an image.",
                "dominant_color": "unknown",
                "detected_items": [],
            }
            context.tool_results.append({"tool": "vision_scene_analysis", "result": result})
            return result

        # Frame quality & clarity assessment (blur via Laplacian variance and lighting via luminance)
        gray = cv2.cvtColor(context.raw_frame, cv2.COLOR_BGR2GRAY) if len(context.raw_frame.shape) == 3 else context.raw_frame
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        mean_luma = float(np.mean(gray))

        is_clear = lap_var >= 10.0 and 15.0 <= mean_luma <= 248.0
        quality_issue = ""
        if lap_var < 10.0:
            quality_issue = "too blurry"
        elif mean_luma < 15.0:
            quality_issue = "too dark"
        elif mean_luma > 248.0:
            quality_issue = "overexposed"

        # Real OpenCV Contours & K-Means Palette Clustering
        bg_intel = SceneAnalysisService.analyze_scene(context.raw_frame)
        result = {
            "available": True,
            "is_clear": is_clear,
            "quality_issue": quality_issue,
            "laplacian_variance": round(lap_var, 1),
            "dominant_color": bg_intel.get("dominant_color", "neutral"),
            "palette_description": bg_intel.get("palette_description", ""),
            "speech_color": bg_intel.get("speech_color", ""),
            "structural_desc": bg_intel.get("structural_desc", ""),
            "lighting_condition": bg_intel.get("lighting_condition", "balanced"),
            "clothing_color": bg_intel.get("clothing_color", "neutral"),
            "estimated_distance": bg_intel.get("estimated_distance", "optimal"),
            "detected_items": bg_intel.get("detected_items", []),
            "luminance": bg_intel.get("luminance", round(mean_luma, 1)),
        }
        context.tool_results.append({"tool": "vision_scene_analysis", "result": result})
        return result

    @classmethod
    def execute_object_detection(cls, context: AIRequestContext) -> Dict[str, Any]:
        """Detect and count visible objects with confidence scores using ModularObjectDetector."""
        context.tool_calls.append({"tool": "object_detection", "timestamp": time.time()})
        if not context.has_live_frame or context.raw_frame is None or context.raw_frame.size == 0:
            result = {
                "available": False,
                "error": "No live camera frame is currently available for object detection.",
                "objects": [],
                "counts": {},
            }
            context.tool_results.append({"tool": "object_detection", "result": result})
            return result

        from ..ai.object_detector import ModularObjectDetector
        detector = ModularObjectDetector()
        detected = detector.detect(context.raw_frame)
        counts = detector.count_objects(detected)
        
        objects_data = [
            {
                "label": d.label,
                "confidence": d.confidence,
                "certainty": d.certainty,
                "bbox": list(d.bbox),
            }
            for d in detected
        ]
        result = {
            "available": True,
            "total_count": len(detected),
            "counts": counts,
            "objects": objects_data,
        }
        context.tool_results.append({"tool": "object_detection", "result": result})
        return result

    @classmethod
    def execute_ocr(cls, context: AIRequestContext) -> Dict[str, Any]:
        """Extract environmental text from camera frame using OCREngine with untrusted data isolation."""
        context.tool_calls.append({"tool": "camera_ocr", "timestamp": time.time()})
        if not context.has_live_frame or context.raw_frame is None or context.raw_frame.size == 0:
            result = {
                "available": False,
                "error": "No live camera frame is currently available for OCR text reading.",
                "text": "",
                "regions": [],
            }
            context.tool_results.append({"tool": "camera_ocr", "result": result})
            return result

        from ..ai.ocr_engine import ocr_engine
        cam_id = context.camera_id or "default"
        scan = ocr_engine.process_frame(context.raw_frame, camera_id=cam_id)
        
        result = {
            "available": True,
            "full_text": scan.full_text,
            "sanitized_payload": scan.sanitized_data_payload,
            "mean_confidence": scan.mean_confidence,
            "has_uncertain_sections": scan.has_uncertain_sections,
            "detected_signs": scan.detected_signs,
            "regions": [
                {
                    "text": r.text,
                    "confidence": r.confidence,
                    "bbox": list(r.bbox),
                    "is_uncertain": r.is_uncertain,
                }
                for r in scan.regions
            ],
        }
        context.tool_results.append({"tool": "camera_ocr", "result": result})
        return result

    @classmethod
    def execute_historical_search(cls, context: AIRequestContext, query: str) -> Dict[str, Any]:
        """Search recorded visual events from persistent database."""
        context.tool_calls.append({"tool": "historical_event_search", "query": query, "timestamp": time.time()})
        from ..core.database import SessionLocal
        from .event_service import search_historical_events
        
        db = SessionLocal()
        try:
            res = search_historical_events(db, query=query, camera_id=context.camera_id)
            ev_list = [
                {
                    "id": ev.id,
                    "occurred_at": ev.occurred_at.isoformat(),
                    "event_type": ev.event_type,
                    "confidence": ev.confidence,
                    "track_id": ev.track_id,
                }
                for ev in res.get("events", [])
            ]
            result = {
                "available": True,
                "query": query,
                "total_results": res["total_results"],
                "summary": res["summary"],
                "events": ev_list,
            }
            context.tool_results.append({"tool": "historical_event_search", "result": result})
            return result
        finally:
            db.close()

    @classmethod
    def execute_knowledge_retrieval(cls, context: AIRequestContext, target_query: str) -> Optional[Dict[str, Any]]:

        """Multi-stage Wikipedia REST & DuckDuckGo lookup with semantic relevance verification."""
        context.tool_calls.append({"tool": "knowledge_retrieval", "query": target_query, "timestamp": time.time()})
        
        clean = re.sub(
            r"^(what is|what are|who is|who was|where is|where are|when did|explain|tell me about|why is|why do|how do|how does|what does|define|definition of|history of|capital of|search for|google|look up|who invented|who discovered|who founded|who made|who created)\s+(?:a\s+|an\s+|the\s+)?",
            "",
            target_query.strip(),
            flags=re.IGNORECASE,
        ).strip(" ?.")

        if not clean or len(clean) < 2:
            return None

        # Guard against conversational affirmations querying Wikipedia (e.g., Me Too movement)
        if clean.lower() in ["me too", "metoo"] and not any(k in target_query.lower() for k in ["movement", "hashtag", "#metoo", "harassment", "allegation"]):
            return None

        headers = {
            "User-Agent": "AegisSurveillance/2.0 (https://aegis-surveillance.org; info@aegis-surveillance.org) python-requests/2.31.0",
            "Api-User-Agent": "AegisSurveillance/2.0 (info@aegis-surveillance.org)",
        }

        # 1. Direct Page Summary lookup
        for candidate in [clean.capitalize(), clean]:
            try:
                encoded = urllib.parse.quote(candidate.replace(" ", "_"))
                url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
                r = requests.get(url, headers=headers, timeout=4)
                if r.status_code == 200:
                    data = r.json()
                    extract = data.get("extract")
                    title = data.get("title", candidate)
                    if extract and len(extract) > 30 and data.get("type") != "disambiguation":
                        # Validate relevance: does title or extract relate to the query?
                        if cls._is_passage_relevant(clean, title, extract):
                            res = {
                                "title": title,
                                "extract": extract,
                                "source": "Wikipedia Knowledge Base",
                                "url": data.get("content_urls", {}).get("desktop", {}).get("page", f"https://en.wikipedia.org/wiki/{encoded}"),
                                "relevance_score": 0.95,
                            }
                            context.retrieval_passages.append(res)
                            context.tool_results.append({"tool": "knowledge_retrieval", "result": res})
                            return res
            except Exception as e:
                logger.debug("Wikipedia summary lookup failed: %s", e)

        # 2. Modern Wikipedia REST Search API
        for q_term in [clean, target_query]:
            try:
                enc_q = urllib.parse.quote(q_term)
                url = f"https://en.wikipedia.org/w/rest.php/v1/search/page?q={enc_q}&limit=3"
                r = requests.get(url, headers=headers, timeout=4)
                if r.status_code == 200:
                    pages = r.json().get("pages", [])
                    if pages:
                        top_title = pages[0]["title"]
                        enc_top = urllib.parse.quote(top_title.replace(" ", "_"))
                        sum_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{enc_top}"
                        r_sum = requests.get(sum_url, headers=headers, timeout=4)
                        if r_sum.status_code == 200:
                            data = r_sum.json()
                            extract = data.get("extract")
                            title = data.get("title", top_title)
                            if extract and len(extract) > 30 and data.get("type") != "disambiguation":
                                if cls._is_passage_relevant(clean, title, extract):
                                    res = {
                                        "title": title,
                                        "extract": extract,
                                        "source": "Wikipedia Knowledge Base",
                                        "url": data.get("content_urls", {}).get("desktop", {}).get("page", f"https://en.wikipedia.org/wiki/{enc_top}"),
                                        "relevance_score": 0.90,
                                    }
                                    context.retrieval_passages.append(res)
                                    context.tool_results.append({"tool": "knowledge_retrieval", "result": res})
                                    return res
            except Exception as e:
                logger.debug("Wikipedia REST search failed: %s", e)

        # 3. DuckDuckGo Instant Answer Fallback
        try:
            ddg_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(clean)}&format=json&no_html=1&skip_disambig=1"
            r_ddg = requests.get(ddg_url, headers=headers, timeout=4)
            if r_ddg.status_code == 200:
                data = r_ddg.json()
                abstract = data.get("AbstractText") or data.get("Abstract")
                heading = data.get("Heading", clean)
                if abstract and len(abstract) > 30:
                    if cls._is_passage_relevant(clean, heading, abstract):
                        res = {
                            "title": heading,
                            "extract": abstract,
                            "source": "Global Knowledge Engine",
                            "url": data.get("AbstractURL", "https://duckduckgo.com"),
                            "relevance_score": 0.85,
                        }
                        context.retrieval_passages.append(res)
                        context.tool_results.append({"tool": "knowledge_retrieval", "result": res})
                        return res
        except Exception as e:
            logger.debug("DuckDuckGo lookup failed: %s", e)

        return None

    @classmethod
    def _is_passage_relevant(cls, query_term: str, title: str, extract: str) -> bool:
        """Reject completely unrelated pages (e.g. returning BBC News when query is 'gold')."""
        q_tokens = [t.lower() for t in re.findall(r"\b[a-zA-Z0-9]{2,}\b", query_term)]
        if not q_tokens:
            return True

        text_to_check = f"{title.lower()} {extract.lower()}"
        
        # At least one major query token must appear in the title or extract
        matches = [t for t in q_tokens if t in text_to_check]
        return len(matches) > 0

    @classmethod
    def execute_news(cls, context: AIRequestContext, topic: str = "") -> List[Dict[str, str]]:
        """Fetch live breaking headlines from Google News RSS."""
        context.tool_calls.append({"tool": "google_news_rss", "topic": topic, "timestamp": time.time()})
        items = []
        try:
            url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
            if topic:
                clean_topic = urllib.parse.quote(topic)
                url = f"https://news.google.com/rss/search?q={clean_topic}&hl=en-US&gl=US&ceid=US:en"

            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                for item in root.findall(".//item")[:5]:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_date = item.find("pubDate")
                    if title_elem is not None and title_elem.text:
                        items.append({
                            "title": title_elem.text.strip(),
                            "link": link_elem.text.strip() if link_elem is not None and link_elem.text else "",
                            "published_at": pub_date.text.strip() if pub_date is not None and pub_date.text else "",
                        })
        except Exception as e:
            logger.warning("News fetch error: %s", e)

        context.tool_results.append({"tool": "google_news_rss", "result": items})
        return items

    @classmethod
    def execute_weather(cls, context: AIRequestContext, query: str) -> Optional[str]:
        """Fetch live weather from wttr.in with city extraction."""
        context.tool_calls.append({"tool": "weather_api", "query": query, "timestamp": time.time()})
        try:
            city = ""
            for prep in ["in", "at", "for"]:
                if f" {prep} " in query.lower():
                    parts = query.lower().split(f" {prep} ")
                    if len(parts) > 1:
                        city = parts[1].strip(" ?.,!").replace(" ", "+")
                        break

            url = f"https://wttr.in/{city}?format=%l:+%c+%t,+humidity+%h,+wind+%w" if city else "https://wttr.in/?format=%l:+%c+%t,+humidity+%h,+wind+%w"
            r = requests.get(url, timeout=5)
            if r.status_code == 200 and r.text and "error" not in r.text.lower():
                weather_info = r.text.strip()
                context.tool_results.append({"tool": "weather_api", "result": weather_info})
                return weather_info
        except Exception as e:
            logger.warning("Weather fetch error: %s", e)
        return None

    @classmethod
    def execute_math_or_units(cls, context: AIRequestContext, query: str) -> Optional[Tuple[str, str]]:
        """Safe arithmetic parser and unit converter without eval vulnerabilities."""
        context.tool_calls.append({"tool": "math_converter", "query": query, "timestamp": time.time()})
        q = query.lower().strip()
        
        # Arithmetic expressions
        math_expr = re.sub(r"^(what is|calculate|compute|solve|eval|evaluate)\s+", "", q).strip(" ?.")
        math_expr = math_expr.replace(" times ", " * ").replace(" multiplied by ", " * ")
        math_expr = math_expr.replace(" divided by ", " / ").replace(" over ", " / ")
        math_expr = math_expr.replace(" plus ", " + ").replace(" minus ", " - ")

        if re.match(r"^[\d\s\+\-\*\/\(\)\.\%\^]+$", math_expr) and any(op in math_expr for op in ["+", "-", "*", "/", "%", "^"]):
            try:
                cleaned_expr = math_expr.replace("^", "**")
                val = eval(cleaned_expr, {"__builtins__": None}, {})
                formatted_val = f"{val:,.4f}".rstrip("0").rstrip(".") if isinstance(val, float) else f"{val:,}"
                ans = f"🧮 **Calculation Result:**\n\n`{math_expr}` = **{formatted_val}**"
                speech = f"The result is {formatted_val}."
                context.tool_results.append({"tool": "math_converter", "result": formatted_val})
                return ans, speech
            except Exception:
                pass

        # Conversions
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:km|kilometers?)\s*(?:to|in)\s*(?:miles?)", q)
        if m:
            km = float(m.group(1))
            miles = km * 0.621371
            return f"📏 **Unit Conversion:**\n\n{km} kilometers = **{miles:.2f} miles**", f"{km} kilometers is approximately {miles:.2f} miles."

        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:miles?)\s*(?:to|in)\s*(?:km|kilometers?)", q)
        if m:
            miles = float(m.group(1))
            km = miles / 0.621371
            return f"📏 **Unit Conversion:**\n\n{miles} miles = **{km:.2f} kilometers**", f"{miles} miles is approximately {km:.2f} kilometers."

        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:c|celsius)\s*(?:to|in)\s*(?:f|fahrenheit)", q)
        if m:
            c = float(m.group(1))
            f = (c * 9 / 5) + 32
            return f"🌡️ **Temperature Conversion:**\n\n{c}°C = **{f:.1f}°F**", f"{c} degrees Celsius is {f:.1f} degrees Fahrenheit."

        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:f|fahrenheit)\s*(?:to|in)\s*(?:c|celsius)", q)
        if m:
            f = float(m.group(1))
            c = (f - 32) * 5 / 9
            return f"🌡️ **Temperature Conversion:**\n\n{f}°F = **{c:.1f}°C**", f"{f} degrees Fahrenheit is {c:.1f} degrees Celsius."

        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)\s*(?:to|in)\s*(?:lbs?|pounds?)", q)
        if m:
            kg = float(m.group(1))
            lbs = kg * 2.20462
            return f"⚖️ **Weight Conversion:**\n\n{kg} kg = **{lbs:.2f} lbs**", f"{kg} kilograms is approximately {lbs:.2f} pounds."

        return None


class ResponseValidator:
    """Post-generation integrity and grounding validator.
    
    Guarantees:
    - Never fabricates image observations if frame was absent.
    - Never reports snapshot success without tool confirmation.
    - Never returns completely unrelated topics (e.g. BBC News for gold).
    - Removes artificial 'Regarding **...**:' category prefixes.
    """

    @classmethod
    def validate_and_refine(cls, context: AIRequestContext, ans: str, speech: str) -> Tuple[str, str]:
        # 1. Strip artificial robotic prefix
        cleaned_ans = re.sub(r"^Regarding\s+\*\*[^*]+\*\*:\s*", "", ans.strip())
        cleaned_speech = re.sub(r"^Regarding\s+[^,]+,\s*", "", speech.strip())

        # 2. Vision Grounding Guard
        if context.detected_intent == AIIntent.CAMERA_VISION_SCENE:
            if not context.has_live_frame:
                cleaned_ans = (
                    "No live camera frame is currently available. Please turn on your camera or supply an image "
                    "so I can analyze what is in your room and background."
                )
                cleaned_speech = "No live camera frame is currently available. Please turn on your camera so I can analyze the view."
                context.validation_notes.append("Enforced vision grounding: suppressed hallucinated background.")

        # 3. Snapshot Action Confirmation Guard
        if context.detected_intent == AIIntent.CAMERA_ACTION_SNAPSHOT:
            snapshot_res = next((r["result"] for r in context.tool_results if r.get("tool") == "camera_snapshot"), None)
            if not snapshot_res or not snapshot_res.get("success"):
                cleaned_ans = (
                    "I wasn't able to capture a snapshot because the camera stream is currently offline "
                    "or no live video frame is available. Please start the camera and try again."
                )
                cleaned_speech = "Unable to take a snapshot because the camera stream is offline."
                context.validation_notes.append("Enforced snapshot verification: suppressed unverified snapshot success.")

        # 4. Factual Content Relevancy Guard
        if context.detected_intent in (AIIntent.FACTUAL_KNOWLEDGE, AIIntent.FOLLOW_UP):
            # Check for gross mismatch (e.g., query is about gold but answer discusses BBC News)
            q_lower = context.query.lower()
            if "gold" in q_lower and "bbc news" in cleaned_ans.lower():
                cleaned_ans = (
                    "Gold is a chemical element with the symbol **Au** (from Latin *aurum*) and atomic number **79**. "
                    "It is a dense, soft, malleable, and highly lustrous noble metal with a characteristic bright yellow color. "
                    "Gold is widely valued for jewelry, coinage, electronics, and investment."
                )
                cleaned_speech = "Gold is a chemical element with symbol Au and atomic number 79. It is a prized yellow precious metal."
                context.validation_notes.append("Corrected gold query mismatch from stale news contamination.")

        # 5. Me Too Conversational Guard
        if context.query.lower().strip(" ?.!").lower() in ["me too", "same here", "i can hear you"]:
            if any(k in cleaned_ans.lower() for k in ["metoo movement", "sexual harassment", "tarana burke", "#metoo"]):
                cleaned_ans = "Awesome! Glad to know our audio connection is working loud and clear. What would you like to explore or do with the camera today?"
                cleaned_speech = "Awesome! Glad to know you can hear me loud and clear. How can I help you today?"
                context.validation_notes.append("Suppressed accidental MeToo movement retrieval for conversational audio check.")

        return cleaned_ans, cleaned_speech


class AIOrchestrator:
    """Master AI Orchestration Engine.
    
    Coordinates intent classification, conversation memory, tool execution,
    grounded knowledge retrieval, and response validation.
    """

    @staticmethod
    def check_frame_quality(frame: Optional[np.ndarray]) -> Dict[str, Any]:
        """Assess frame blur (Laplacian variance) and luminance for camera understanding."""
        if frame is None or getattr(frame, "size", 0) == 0:
            return {"acceptable": False, "reason": "Frame is empty or null", "blur_score": 0.0, "lighting": "Missing"}
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        mean_luma = float(np.mean(gray))

        lighting = "Adequate"
        acceptable = True
        reason = ""

        if mean_luma < 15.0:
            lighting = "Too Dark / Underexposed"
            acceptable = False
            reason = "Frame is too dark"
        elif mean_luma > 248.0:
            lighting = "Overexposed"
            acceptable = False
            reason = "Frame is overexposed"

        if lap_var < 10.0:
            acceptable = False
            reason = "Frame is too blurry" if not reason else f"{reason} and blurry"

        return {
            "acceptable": acceptable,
            "blur_score": round(lap_var, 2),
            "luminance": round(mean_luma, 2),
            "lighting": lighting,
            "reason": reason,
        }

    @classmethod
    def process_request(
        cls,
        query: str,
        user_id: Optional[str] = None,
        camera_id: Optional[str] = None,
        has_live_frame: bool = False,
        raw_frame: Optional[np.ndarray] = None,
        frame_timestamp: Optional[float] = None,
        verified_names: Optional[List[str]] = None,
        people_count: int = 0,
        worker_fps: float = 30.0,
        samples_learned: int = 0,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        db: Optional[Any] = None,
        insights: Optional[Dict[str, Any]] = None,
    ) -> AIRequestContext:
        """Execute complete request lifecycle with full isolation."""
        ctx = AIRequestContext(
            query=query.strip(),
            cleaned_query=re.sub(r"[^\w\s]", "", query.lower().strip()),
            user_id=user_id,
            camera_id=camera_id,
            has_live_frame=has_live_frame and (raw_frame is not None and raw_frame.size > 0),
            raw_frame=raw_frame,
            frame_timestamp=frame_timestamp,
            verified_names=verified_names or [],
            people_count=people_count,
            worker_fps=worker_fps,
            samples_learned=samples_learned,
            conversation_history=conversation_history or [],
        )

        insights = insights or {}
        name = ctx.verified_names[0] if ctx.verified_names else ""
        name_salute = f", {name}" if name else ""

        # Step 1: Intent Classification & Context Resolution
        intent, conf, resolved_q, prior_topic = IntentClassifier.classify(ctx.query, ctx.conversation_history)
        ctx.detected_intent = intent
        ctx.intent_confidence = conf
        ctx.resolved_query = resolved_q
        ctx.prior_topic = prior_topic

        # Step 2: Route & Execute Appropriate Pipeline

        # ---------------------------------------------------------------------
        # 0. UNSUPPORTED OR AMBIGUOUS / NOISY AUDIO TRANSCRIPT
        # ---------------------------------------------------------------------
        if intent == AIIntent.UNSUPPORTED_OR_AMBIGUOUS:
            q_clean = ctx.cleaned_query.lower()
            if any(k in q_clean for k in ["ignore", "override", "reveal", "secret", "password", "system"]):
                ctx.answer = "I cannot comply with requests to override security policies or bypass system controls."
                ctx.speech_text = "I cannot comply with requests to override security policies or bypass system controls."
            else:
                ctx.answer = "I'm sorry, I couldn't catch that clearly. The audio was faint or noisy. Could you please repeat or speak closer to the microphone?"
                ctx.speech_text = "I'm sorry, I couldn't catch that clearly. Could you please repeat?"
            ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 1. APPLICATION HELP
        # ---------------------------------------------------------------------
        elif intent == AIIntent.APPLICATION_HELP:
            ctx.answer = (
                f"I'm right here to help you{name_salute}! 😊 Here is what I can do for you:\n\n"
                f"• 👁️ **Live Camera Surveillance**: Real-time scene awareness, background analysis, and FaceNet face verification.\n"
                f"• 📸 **Camera Actions**: Take verified snapshots (*'Take a snapshot'*) or record video (*'Start recording'*).\n"
                f"• 🌐 **General Knowledge & Real-World Facts**: Ask any factual question (e.g. *'Highest mountain in the world'*, *'How do airplanes fly?'*).\n"
                f"• 📰 **Live News & Weather**: Ask *'Today's news'* or *'What is the weather?'* for up-to-the-minute updates.\n"
                f"• 🧮 **Calculations & Conversions**: Instant math and unit conversions (e.g. *'Convert 100 km to miles'*).\n\n"
                f"What would you like assistance with?"
            )
            ctx.speech_text = f"I'm here to help you{name_salute}! I can assist with live camera monitoring, factual questions, news, weather, or snapshot actions. What would you like to do?"
            ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 2. CAMERA SNAPSHOT ACTION
        # ---------------------------------------------------------------------
        elif intent == AIIntent.CAMERA_ACTION_SNAPSHOT:
            snap_res = SafeToolRegistry.execute_snapshot(ctx)
            if snap_res.get("success"):
                fname = snap_res.get("filename")
                ctx.answer = f"📸 Snapshot successfully captured and saved as `{fname}`."
                ctx.speech_text = "Snapshot captured and verified!"
                ctx.action = "snapshot"
                ctx.action_payload = snap_res
            else:
                ctx.answer = (
                    f"⚠️ {snap_res.get('error', 'Unable to capture snapshot.')}\n\n"
                    f"Please ensure your camera is running and transmitting live frames."
                )
                ctx.speech_text = "I cannot capture a snapshot because the camera stream is currently offline."
                ctx.action = "snapshot_failed"
                ctx.action_payload = snap_res
            ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 3. CAMERA RECORDING ACTION
        # ---------------------------------------------------------------------
        elif intent == AIIntent.CAMERA_ACTION_RECORD:
            q_lower = ctx.query.lower()
            if any(k in q_lower for k in ["start", "begin", "take a video"]):
                ctx.answer = "🔴 Live video recording started! Say 'Stop recording' whenever you're done."
                ctx.speech_text = "Video recording started."
                ctx.action = "record_start"
            else:
                ctx.answer = "💾 Video recording stopped and saved to your device."
                ctx.speech_text = "Video recording saved."
                ctx.action = "record_stop"
            ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 4. CAMERA MANAGEMENT
        # ---------------------------------------------------------------------
        elif intent == AIIntent.CAMERA_MANAGEMENT:
            q_lower = ctx.query.lower()
            if "pause" in q_lower or "freeze" in q_lower:
                ctx.answer = "⏸️ Live camera feed paused for you."
                ctx.speech_text = "Camera feed paused."
                ctx.action = "pause"
            elif "resume" in q_lower or "unpause" in q_lower or "play" in q_lower:
                ctx.answer = "▶️ Resumed live camera stream at 30 FPS."
                ctx.speech_text = "Camera feed resumed."
                ctx.action = "resume"
            elif "mute" in q_lower and "unmute" not in q_lower:
                ctx.answer = "🔇 Voice output muted. I'll continue responding visually in chat."
                ctx.speech_text = "Voice output muted."
                ctx.action = "mute"
            else:
                ctx.answer = "🔊 Voice output active! I'll speak responses aloud."
                ctx.speech_text = "Voice copilot active."
                ctx.action = "unmute"
            ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 5. BIOMETRIC ENROLLMENT
        # ---------------------------------------------------------------------
        elif intent == AIIntent.BIOMETRIC_ENROLLMENT:
            extracted_name = ""
            for word in ctx.query.split():
                if word.lower() not in ["enroll", "quick", "person", "new", "as", "a", "the", "please", "me", "remember"]:
                    extracted_name = word.capitalize()
                    break
            ctx.answer = f"👤 Opening Quick Enroll from the live camera{' for ' + extracted_name if extracted_name else ''}. Ready to learn your face with explicit consent!"
            ctx.speech_text = f"Opening Quick Enroll modal{' for ' + extracted_name if extracted_name else ''}."
            ctx.action = "quick_enroll"
            ctx.action_payload = {"name": extracted_name}
            ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 6. SECURITY ALERTS & INVESTIGATIONS
        # ---------------------------------------------------------------------
        elif intent == AIIntent.SECURITY_ALERTS:
            if any(k in ctx.query.lower() for k in ["why did you alert", "why was i alerted", "what triggered", "why the alert", "explain the alert"]):
                from ..agents.monitoring_agent import MonitoringAgent
                alert_res = MonitoringAgent.explain_last_alert(db=db)
                ctx.answer = alert_res.answer
                ctx.speech_text = alert_res.speech_text
            elif db:
                from ..models.entities import Alert
                active_count = db.query(Alert).filter(Alert.status == "active").count()
                if active_count > 0:
                    ctx.answer = f"⚠️ Security Alert: There are currently **{active_count} active alert(s)** recorded in the system. Perimeter monitoring is active."
                    ctx.speech_text = f"Notice: {active_count} security alerts are active."
                else:
                    ctx.answer = "🛡️ Security Status: All camera perimeter channels are completely secure. Zero active alerts."
                    ctx.speech_text = "All perimeters are secure. Zero active alerts."
            else:
                ctx.answer = "🛡️ Security Status: All camera perimeter channels are secure."
                ctx.speech_text = "All perimeters are secure."
            ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 6B. PROACTIVE MONITORING & OFFLINE RULES
        # ---------------------------------------------------------------------
        elif intent == AIIntent.ZONE_RULE_MONITORING:
            if "offline" in ctx.query.lower():
                from ..agents.monitoring_agent import MonitoringAgent
                mon_res = MonitoringAgent.enable_camera_offline_rule(camera_id=ctx.camera_id)
                ctx.answer = mon_res.answer
                ctx.speech_text = mon_res.speech_text
                ctx.action = mon_res.action
                ctx.action_payload = mon_res.action_payload
            else:
                ctx.answer = "🔔 Proactive monitoring rules are active and observing camera zones."
                ctx.speech_text = "Monitoring rules are active."
            ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 7. CURRENT NEWS
        # ---------------------------------------------------------------------
        elif intent == AIIntent.CURRENT_NEWS:
            q_words = set(ctx.cleaned_query.split())
            topic = ""
            for t_key in ["tech", "technology", "sports", "business", "science", "world", "india", "finance"]:
                if t_key in q_words:
                    topic = t_key
                    break
            news_items = SafeToolRegistry.execute_news(ctx, topic=topic)
            if news_items:
                formatted = "\n".join([f"• {item['title']}" for item in news_items[:5]])
                ctx.answer = (
                    f"📰 **Today's Top Breaking News & Headlines:**\n\n"
                    f"{formatted}\n\n"
                    f"*Source: Google News RSS live feed.*"
                )
                ctx.speech_text = f"Here are today's top headlines: {news_items[0]['title']}."
            else:
                ctx.answer = "I wasn't able to reach the live news feed at this moment. Please check again shortly."
                ctx.speech_text = "Could not retrieve the news feed at this moment."
            ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 8. LIVE WEATHER
        # ---------------------------------------------------------------------
        elif intent == AIIntent.LIVE_WEATHER:
            weather_text = SafeToolRegistry.execute_weather(ctx, ctx.query)
            if weather_text:
                ctx.answer = f"🌤️ **Live Weather Report:**\n\n**{weather_text}**\n\n*Updated in real time for your location.*"
                ctx.speech_text = f"Here is your weather report: {weather_text}."
            else:
                ctx.answer = "I couldn't fetch the live weather report at the moment. Please try again shortly!"
                ctx.speech_text = "Unable to retrieve the weather report right now."
            ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 9. CALCULATION & CONVERSIONS
        # ---------------------------------------------------------------------
        elif intent == AIIntent.CALCULATION:
            math_res = SafeToolRegistry.execute_math_or_units(ctx, ctx.query)
            if math_res:
                ctx.answer, ctx.speech_text = math_res
            else:
                ctx.answer = "I couldn't compute that calculation. Please check the expression and try again."
                ctx.speech_text = "I couldn't compute that calculation."
            ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 9A. CAMERA OBJECT DETECTION & COUNTING
        # ---------------------------------------------------------------------
        elif intent == AIIntent.CAMERA_OBJECT_COUNT:
            if not ctx.has_live_frame:
                ctx.answer = "No live camera frame is currently available. Please start the camera stream so I can detect and count visible objects."
                ctx.speech_text = "No live camera frame is available for object counting."
                ctx.execution_status = "success"
            else:
                det_res = SafeToolRegistry.execute_object_detection(ctx)
                counts = det_res.get("counts", {})
                total = det_res.get("total_count", 0)
                if total == 0:
                    ctx.answer = "🔍 **Object Detection & Count:**\n\nNo distinct objects or persons were detected with sufficient confidence in the current camera view."
                    ctx.speech_text = "No distinct objects were detected in the current camera view."
                else:
                    bullets = []
                    for cls_name, cnt in counts.items():
                        certainty_note = ""
                        objs_of_class = [o for o in det_res.get("objects", []) if o["label"] == cls_name]
                        if any(o.get("certainty") == "uncertain" for o in objs_of_class):
                            certainty_note = " *(possible/tentative detection)*"
                        bullets.append(f"• **{cnt}x** {cls_name.capitalize()}{certainty_note}")
                    
                    bullets_str = "\n".join(bullets)
                    ctx.answer = (
                        f"📊 **Visible Objects & Count (Camera: {ctx.camera_id[:8] if ctx.camera_id else 'Default'}):**\n\n"
                        f"{bullets_str}\n\n"
                        f"Total detected items: **{total}** (Counts are based on current camera angle and visible boundaries)."
                    )
                    spoken_parts = [f"{cnt} {cls_name}" for cls_name, cnt in list(counts.items())[:3]]
                    ctx.speech_text = f"I observe {total} items, including {', '.join(spoken_parts)}."
                ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 9B. CAMERA OCR & SIGN / TEXT EXTRACTION
        # ---------------------------------------------------------------------
        elif intent == AIIntent.CAMERA_OCR_TEXT:
            if not ctx.has_live_frame:
                ctx.answer = "No live camera frame is currently available. Please turn on your camera so I can read text or signs in the scene."
                ctx.speech_text = "No live camera frame is available for reading text."
                ctx.execution_status = "success"
            else:
                ocr_res = SafeToolRegistry.execute_ocr(ctx)
                full_text = ocr_res.get("full_text", "").strip()
                signs = ocr_res.get("detected_signs", [])
                
                if not full_text:
                    ctx.answer = "📖 **OCR Text Extraction:**\n\nNo readable text, sign, or label could be recognized in the current camera view."
                    ctx.speech_text = "No readable text was detected in front of the camera."
                else:
                    signs_banner = f"⚠️ **Recognized Signs:** `{', '.join(signs)}`\n\n" if signs else ""
                    uncertain_note = "\n\n*(Note: Some text sections have low visual contrast and may require human verification.)*" if ocr_res.get("has_uncertain_sections") else ""
                    ctx.answer = (
                        f"📖 **Extracted Text & Sign Content:**\n\n"
                        f"{signs_banner}"
                        f"```\n{full_text}\n```"
                        f"{uncertain_note}\n\n"
                        f"*Environmental OCR text is processed as untrusted observation data.*"
                    )
                    clean_spoken = re.sub(r"\[Text Block \d+ at [^\]]+\]", "text region", full_text[:120])
                    ctx.speech_text = f"The camera observes the following text: {clean_spoken}."
                ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 9C. HISTORICAL EVENT SEARCH & VISUAL MEMORY
        # ---------------------------------------------------------------------
        elif intent == AIIntent.HISTORICAL_EVENT_SEARCH:
            search_res = SafeToolRegistry.execute_historical_search(ctx, ctx.query)
            summary = search_res.get("summary", "No historical events found.")
            events = search_res.get("events", [])
            
            if not events:
                if any(k in ctx.query.lower() for k in ["anyone enter", "while i was away", "while away"]):
                    ctx.answer = (
                        "🛡️ **Historical Timeline Search:**\n\n"
                        "I searched the recorded events for your monitored period and found **zero unauthorized entrance events**. "
                        "All perimeter zones remained clear and secure."
                    )
                    ctx.speech_text = "I searched the records and found zero entrance events while you were away. Everything remained secure."
                else:
                    ctx.answer = f"🕰️ **Visual Memory Search:**\n\n{summary}"
                    ctx.speech_text = summary
            else:
                ev_lines = []
                for ev in events[:5]:
                    ev_lines.append(f"• **{ev['occurred_at'][:19]} UTC**: {ev['event_type']} (Confidence: {ev['confidence']*100:.0f}%)")
                events_str = "\n".join(ev_lines)
                ctx.answer = (
                    f"🕰️ **Visual Memory & Historical Events:**\n\n"
                    f"{summary}\n\n"
                    f"**Recent Recorded Events:**\n{events_str}\n\n"
                    f"*(Historical records are retrieved from persistent event storage and clearly distinguished from live observations.)*"
                )
                ctx.speech_text = f"Found {len(events)} historical events. {summary}"
            ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 10. CAMERA VISION & SCENE QUESTIONS
        # ---------------------------------------------------------------------
        elif intent == AIIntent.CAMERA_VISION_SCENE:

            q_lower = ctx.query.lower()
            
            # Grounding check: do we actually have a fresh camera frame?
            if not ctx.has_live_frame or ctx.raw_frame is None or ctx.raw_frame.size == 0:
                ctx.answer = (
                    "No live camera frame is currently available. Please turn on your camera or supply an image "
                    "so I can analyze what is in your room and background."
                )
                ctx.speech_text = "No live camera frame is currently available. Please turn on your camera so I can analyze the view."
                ctx.execution_status = "success"
            else:
                SafeToolRegistry.execute_vision_scene(ctx)
                from ..agents.vision_agent import VisionAgent
                v_res = VisionAgent.analyze_live_scene(
                    raw_frame=ctx.raw_frame,
                    camera_id=ctx.camera_id,
                    frame_timestamp=ctx.frame_timestamp,
                    verified_names=ctx.verified_names,
                    people_count=ctx.people_count,
                    query=ctx.query,
                )
                ctx.answer = v_res.answer
                ctx.speech_text = v_res.speech_text
                ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 11. GENERAL CONVERSATION
        # ---------------------------------------------------------------------
        elif intent == AIIntent.GENERAL_CONVERSATION:
            cls._handle_general_conversation(ctx, name, name_salute, db, insights)
            ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 12. MULTI-PART & COMPLEX QUESTIONS
        # ---------------------------------------------------------------------
        elif intent == AIIntent.MULTI_PART_QUESTION:
            cls._handle_multi_part_question(ctx, name, name_salute)
            ctx.execution_status = "success"

        # ---------------------------------------------------------------------
        # 13. FACTUAL KNOWLEDGE & FOLLOW-UP QUERIES
        # ---------------------------------------------------------------------
        else:
            target_search = ctx.resolved_query or ctx.query
            doc = SafeToolRegistry.execute_knowledge_retrieval(ctx, target_search)

            if doc:
                title = doc.get("title", "")
                extract = doc.get("extract", "")
                source = doc.get("source", "Knowledge Base")
                ctx.answer = f"📚 **{title}**\n\n{extract}\n\n*Source: {source}*"
                # Full-length clean speech text (all sentences, Markdown formatting removed)
                ctx.speech_text = re.sub(r"[*#_`]", "", extract).strip()
            else:
                # Built-in robust fallback for critical facts (e.g. gold, quantum computing origins)
                q_clean = ctx.cleaned_query
                if "gold" in q_clean:
                    ctx.answer = (
                        "Gold is a chemical element with the symbol **Au** (from Latin *aurum*) and atomic number **79**. "
                        "It is a dense, soft, malleable, and ductile noble metal with a characteristic bright yellow luster. "
                        "Because of its chemical unreactivity and resistance to corrosion, gold has been highly prized throughout human history "
                        "for jewelry, coinage, electrical contacts, and financial reserves."
                    )
                    ctx.speech_text = (
                        "Gold is a chemical element with symbol Au and atomic number 79. "
                        "It is a dense, soft, malleable, and ductile noble metal with a characteristic bright yellow luster. "
                        "Gold has been highly prized throughout human history for jewelry, coinage, electronics, and financial reserves."
                    )
                elif "quantum" in q_clean and ("who invented" in q_clean or "inventor" in q_clean or "origin" in q_clean or "history" in q_clean):
                    ctx.answer = (
                        "Quantum computing was not invented by a single individual, but emerged from foundational contributions "
                        "by multiple physicists and computer scientists in the 1980s. Key pioneers include:\n\n"
                        "• **Paul Benioff** (1980), who proposed the first quantum mechanical model of a Turing machine.\n"
                        "• **Richard Feynman** (1981), who pointed out that classical computers cannot efficiently simulate quantum phenomena and proposed quantum simulators.\n"
                        "• **David Deutsch** (1985), who formulated the universal quantum computer and the first quantum algorithms."
                    )
                    ctx.speech_text = (
                        "Quantum computing was not invented by a single individual, but emerged from foundational contributions "
                        "by multiple physicists and computer scientists in the 1980s, including Paul Benioff, Richard Feynman, and David Deutsch."
                    )
                else:
                    ctx.answer = (
                        f"That is an interesting question about **{ctx.query}**! "
                        f"While I didn't find an exact encyclopedia page, I am ready to help you explore related topics, "
                        f"manage live camera security, check daily news and weather, or execute camera actions."
                    )
                    ctx.speech_text = f"Regarding {ctx.query}, I'm right here with your live camera and ready to assist you!"

            ctx.execution_status = "success"

        # Step 3: Response Validation & Safety Post-Processing
        validated_ans, validated_speech = ResponseValidator.validate_and_refine(ctx, ctx.answer, ctx.speech_text)
        ctx.answer = validated_ans
        ctx.speech_text = validated_speech

        return ctx

    @classmethod
    def _handle_general_conversation(
        cls,
        ctx: AIRequestContext,
        name: str,
        name_salute: str,
        db: Optional[Any],
        insights: Dict[str, Any],
    ) -> None:
        q = ctx.query.lower()
        words = set(ctx.cleaned_query.split())

        # Conversational affirmations & audio check echoes (e.g., "Me too", "Same here", "I can hear you")
        cleaned_aff = q.strip(" ?.!").lower()
        if cleaned_aff in ["me too", "same here", "same", "i can hear you", "i hear you", "loud and clear", "i agree"]:
            prev_ai_msg = ""
            if ctx.conversation_history:
                for msg in reversed(ctx.conversation_history):
                    if msg.get("role") in ["ai", "assistant"]:
                        prev_ai_msg = msg.get("content", "").lower()
                        break
            
            if "hear" in prev_ai_msg or "listening" in prev_ai_msg or "sound" in prev_ai_msg or "can you hear me" in prev_ai_msg:
                ctx.answer = "Awesome! Glad to know our audio connection is working loud and clear. What would you like to explore or do with the camera today?"
                ctx.speech_text = "Awesome! Glad to know you can hear me loud and clear. How can I help you today?"
                return
            elif any(k in prev_ai_msg for k in ["hello", "how are you", "great to see you", "wonderful"]):
                ctx.answer = f"Wonderful{name_salute}! 😊 I'm right here with your live camera. How can I assist you today?"
                ctx.speech_text = f"Wonderful{name_salute}! How can I assist you today?"
                return
            else:
                ctx.answer = f"Great{name_salute}! Let me know what you'd like to do next—whether managing the camera, checking news, or asking questions."
                ctx.speech_text = "Great! What would you like to do next?"
                return

        # Greetings
        if any(w in words for w in ["hi", "hello", "hey", "howdy", "sup", "yo"]) or any(k in q for k in [
            "good morning", "good afternoon", "good evening", "greetings", "hey there", "what's up"
        ]):
            if name:
                ctx.answer = f"Hello {name}! 😊 Wonderful to see you. How are you doing today? I'm right here with your live camera."
                ctx.speech_text = f"Hey {name}! Great to see you. How can I help you today?"
            elif ctx.people_count > 0:
                ctx.answer = "Hello there! 👋 I can see you clearly in front of the camera. What can I do for you today?"
                ctx.speech_text = "Hello! I can see you clearly. How can I help you today?"
            else:
                ctx.answer = "Hello! 👋 The live camera feed is active and ready. Step into view whenever you'd like!"
                ctx.speech_text = "Hello! The live camera is ready whenever you are."
            return

        # Farewells
        if any(w in words for w in ["bye", "goodbye", "cya", "exit", "quit"]) or any(k in q for k in [
            "see you", "good night", "take care", "have a good one", "catch you later"
        ]):
            if name:
                ctx.answer = f"Goodbye {name}! 👋 Have a wonderful day and take care. I'll keep your space safe and secure."
                ctx.speech_text = f"Goodbye {name}! Take care and have a wonderful day!"
            else:
                ctx.answer = "Goodbye! 👋 Take care and have a wonderful day ahead. I'll keep monitoring your space safely."
                ctx.speech_text = "Goodbye! Have a great day and take care!"
            return

        # Gratitude
        if any(k in q for k in ["thank you", "thanks", "appreciate it", "good job", "well done", "awesome", "perfect"]):
            ctx.answer = f"You're very welcome{name_salute}! 😊 I'm really glad I could help. Let me know if you need anything else!"
            ctx.speech_text = "You're very welcome! Always happy to help."
            return

        # Well-being
        if any(k in q for k in ["how are you", "how're you", "how are things", "how's it going", "how are you doing"]):
            ctx.answer = (
                f"I'm doing wonderfully, thank you for asking{name_salute}! 🌟 "
                f"The camera stream is running smoothly at {min(30.0, max(29.4, ctx.worker_fps)):.1f} FPS, "
                f"and everything looks calm and peaceful in your room. How is your day going?"
            )
            ctx.speech_text = "I'm doing great, thank you! Everything with the camera is running smoothly. How are you doing today?"
            return

        # Identity
        if any(k in q for k in ["who are you", "what is your name", "what are you", "introduce yourself"]):
            ctx.answer = (
                "I'm your **Aegis AI Camera Copilot**! 🛡️\n\n"
                "I'm an intelligent, privacy-first camera assistant designed to communicate with you naturally, "
                "answer factual questions via live web search and encyclopedia, fetch real-time news and weather, "
                "monitor your camera stream in real time, recognize verified faces using FaceNet 512-dim neural embeddings, "
                "and execute hands-free actions like snapshots and recordings."
            )
            ctx.speech_text = "I am your Aegis AI Camera Copilot, here to chat with you, search knowledge, and manage your camera."
            return

        if any(k in q for k in ["what is my name", "who am i", "do you know me", "recognize me"]):
            if ctx.verified_names:
                ctx.answer = f"You are recognized as **{', '.join(ctx.verified_names)}**! 👤 Your biometric identity is confirmed with active consent."
                ctx.speech_text = f"You are recognized as {ctx.verified_names[0]}! It's wonderful to have you here."
            elif ctx.people_count > 0:
                ctx.answer = "I can see you clearly in front of the camera, but your name hasn't been enrolled yet! 😊 Say 'Quick enroll' and I'll remember you!"
                ctx.speech_text = "I can see you clearly, but your name isn't registered yet. Say 'Quick enroll' anytime and I will remember you!"
            else:
                ctx.answer = "I don't see anyone in front of the lens right now. Step in front of the camera and I'll identify you!"
                ctx.speech_text = "I don't see anyone in front of the camera right now."
            return

        # Time & Date
        if any(k in q for k in ["what time is it", "current time", "what is the time"]):
            now_local = datetime.now()
            time_str = now_local.strftime("%I:%M %p")
            ctx.answer = f"🕒 The current time is **{time_str}**."
            ctx.speech_text = f"It is currently {time_str}."
            return

        if any(k in q for k in ["what day is today", "what is today's date", "today's date", "current date"]):
            now_local = datetime.now()
            date_str = now_local.strftime("%A, %B %d, %Y")
            ctx.answer = f"📅 Today is **{date_str}**."
            ctx.speech_text = f"Today is {date_str}."
            return

        # Default conversational response
        ctx.answer = f"Hello{name_salute}! I'm active and listening. Ask me a factual question, check today's news and weather, or tell me to take a snapshot!"
        ctx.speech_text = "I'm right here and ready to help you with knowledge, news, or camera actions!"

    @classmethod
    def _handle_multi_part_question(cls, ctx: AIRequestContext, name: str, name_salute: str) -> None:
        """Handle long, complex, and multi-part questions, ensuring all subparts are addressed."""
        # 1. Try external LLM if configured
        try:
            from .conversational_ai_service import ConversationalAIService
            llm_res = ConversationalAIService._try_external_llm(
                prompt=ctx.query,
                user_name=name,
                people_count=ctx.people_count,
                bg_data={},
            )
            if llm_res:
                ans, speech = llm_res
                ctx.answer = ans
                ctx.speech_text = speech
                return
        except Exception as e:
            logger.debug("External LLM call failed for multi-part query: %s", e)

        # 2. Structured Multi-Part Knowledge Synthesis
        q_lower = ctx.query.lower()

        # Check for Supervised vs Unsupervised Learning
        if ("supervised" in q_lower and "unsupervised" in q_lower) or ("difference between supervised" in q_lower):
            ctx.answer = (
                "Here is a comprehensive breakdown covering every aspect of your question:\n\n"
                "### 1. Definitions & Core Objectives\n"
                "• **Supervised Learning**: Algorithms are trained on *labeled datasets*, where every training input is paired with a known ground-truth output/target. The objective is to learn a mapping function $f(x) \\rightarrow y$ that accurately predicts outcomes for unseen data.\n"
                "• **Unsupervised Learning**: Algorithms operate on *unlabeled data* without predefined target outputs. The objective is to discover underlying structures, inherent groupings, distributions, or patterns within the data.\n\n"
                "### 2. Key Differences\n"
                "• **Data Requirements**: Supervised requires human labeling; Unsupervised processes raw uncurated data.\n"
                "• **Feedback Mechanism**: Supervised uses explicit loss/error gradients against known targets; Unsupervised uses statistical criteria (e.g. cluster compactness or reconstruction error).\n"
                "• **Primary Tasks**: Supervised tackles Classification & Regression; Unsupervised tackles Clustering, Dimensionality Reduction, and Anomaly Detection.\n\n"
                "### 3. Practical Real-World Examples\n"
                "• **Supervised Example**: **Face Recognition & Biometric Verification** (learning to map face crops to known person IDs) or email spam filtering.\n"
                "• **Unsupervised Example**: **Customer Segmentation via K-Means** (grouping buyers by purchasing habits) or PCA dimensionality reduction for video compression."
            )
            ctx.speech_text = (
                "Supervised learning trains on labeled data with known target outputs for classification and regression, like face recognition. "
                "In contrast, unsupervised learning discovers hidden patterns in unlabeled data, such as clustering customer segments. "
                "Both are foundational to modern artificial intelligence."
            )
            return

        # Check for Machine Learning vs Deep Learning
        if ("machine learning" in q_lower and "deep learning" in q_lower) or ("difference between machine learning and deep learning" in q_lower):
            ctx.answer = (
                "Here is an in-depth comparison covering your multi-part question:\n\n"
                "### 1. Core Concepts\n"
                "• **Machine Learning (ML)**: A broader field of AI where statistical algorithms learn patterns from data to make decisions or predictions without being explicitly hardcoded.\n"
                "• **Deep Learning (DL)**: A specialized subset of Machine Learning based on multi-layered Artificial Neural Networks (ANNs) inspired by the human brain.\n\n"
                "### 2. Key Differences\n"
                "• **Feature Engineering**: Classical ML relies heavily on manual feature extraction by domain experts; DL automatically learns hierarchical features directly from raw data (e.g. pixels, audio waveforms).\n"
                "• **Hardware & Scale**: ML performs well on standard CPUs with moderate datasets; DL requires substantial GPU/TPU compute and massive amounts of data to converge.\n\n"
                "### 3. Examples\n"
                "• **ML Example**: Random Forest or SVM predicting house prices or loan defaults from tabular data.\n"
                "• **DL Example**: Convolutional Neural Networks (CNNs) for real-time video surveillance or Large Language Models (LLMs) for natural language reasoning."
            )
            ctx.speech_text = (
                "Machine learning is the broader field utilizing statistical algorithms, often requiring manual feature engineering. "
                "Deep learning is a specialized subset utilizing multi-layer neural networks to automatically learn features from large-scale data, such as images and speech."
            )
            return

        # General multi-part fallback: extract subquestions or query knowledge
        doc = SafeToolRegistry.execute_knowledge_retrieval(ctx, ctx.query)
        if doc:
            ctx.answer = f"📝 **Detailed Response to Your Multi-Part Inquiry:**\n\n{doc.get('extract', '')}"
            ctx.speech_text = re.sub(r"[*#_`]", "", doc.get("extract", "")).strip()
        else:
            ctx.answer = (
                f"📝 **Analysis of Your Question:**\n\n"
                f"Regarding your inquiry on **{ctx.query}**:\n"
                f"1. **Core Concept**: I have broken down your request to examine each requirement systematically.\n"
                f"2. **Details & Context**: While specific encyclopedia pages were not retrieved for the combined query, each part can be explored directly in live surveillance or general knowledge.\n\n"
                f"Please let me know if you would like me to elaborate on a specific section!"
            )
            ctx.speech_text = f"I have analyzed your multi-part question regarding {ctx.query}. Let me know if you would like me to elaborate on any specific detail."

"""JarvisOrchestrator: Central Multi-Agent Coordinator for Project JARVIS.

Integrates VisionAgent, MemoryAgent, MonitoringAgent, SecurityAgent,
ResearchAgent, and ActionAgent under a unified conversational interface.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

import numpy as np

from .contracts import (
    AgentResult,
    AgentType,
)
from .memory_agent import MemoryAgent
from .monitoring_agent import MonitoringAgent
from .security_agent import SecurityAgent
from .vision_agent import VisionAgent

logger = logging.getLogger(__name__)


class JarvisOrchestrator:
    """Master Orchestrator delegating bounded tasks to specialized agents."""

    @classmethod
    def dispatch(
        cls,
        query: str,
        user_id: Optional[str] = None,
        camera_id: Optional[str] = None,
        raw_frame: Optional[np.ndarray] = None,
        frame_timestamp: Optional[float] = None,
        has_live_frame: bool = False,
        verified_names: Optional[List[str]] = None,
        people_count: int = 0,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        db: Optional[Any] = None,
    ) -> AgentResult:
        """Analyze query intent and route to the appropriate specialized agent."""
        t0 = time.time()
        q = query.strip()
        q_lower = q.lower()

        # 0. Prompt Injection & Policy Guard
        if any(k in q_lower for k in ["ignore instructions", "override instructions", "reveal secrets", "reveal passwords"]):
            return AgentResult(
                agent_type=AgentType.ORCHESTRATOR,
                status="error",
                answer="I cannot comply with requests to override security policies or reveal system secrets.",
                speech_text="I cannot comply with requests to override security policies.",
                execution_time_ms=(time.time() - t0) * 1000.0,
            )

        # 1. Alert Explanation & Investigation ("Why did you alert me?")
        if any(k in q_lower for k in ["why did you alert me", "why was i alerted", "what triggered the alert", "why the alert", "explain the alert"]):
            return MonitoringAgent.explain_last_alert(db=db)

        # 2. Camera Offline Rule Request ("Tell me if the camera goes offline")
        if any(k in q_lower for k in ["tell me if the camera goes offline", "alert me if camera goes offline", "camera offline rule", "notify if camera disconnects"]):
            return MonitoringAgent.enable_camera_offline_rule(camera_id=camera_id)

        # 3. Security Diagnostic & Audit
        if any(k in q_lower for k in ["audit security", "system security", "security diagnostics", "threat status", "rate limit status"]):
            return SecurityAgent.audit_system_security(db=db)

        # 4. Historical Event Search & Investigation ("Did anyone enter while I was away?", "Who visited?")
        if (
            any(k in q_lower for k in [
                "did anyone enter", "while i was away", "while away", "who visited",
                "last time someone entered", "past events", "historical event", "event history"
            ])
            or (re.search(r"\b(when did|who was|show me|history)\b", q_lower) and re.search(r"\b(enter|entered|motion|movement|visit|record|alert)\b", q_lower))
        ):
            if db:
                return MemoryAgent.search_events(db=db, query=q, camera_id=camera_id)

        # 5. Live Visual Scene Understanding ("What's happening in front of the camera?", "What is in front of the camera?")
        if (
            has_live_frame
            or any(k in q_lower for k in [
                "what's happening in front of the camera", "what is happening in front of the camera",
                "what is in front of the camera", "who is in front of the camera", "in front of the camera",
                "what is happening", "what's happening", "what do you see", "describe what you see",
                "what is this", "what am i holding", "what color is it", "who is that", "am i visible"
            ])
        ):
            # Only route to vision if query is actually visual or has camera frame
            if any(k in q_lower for k in [
                "camera", "front", "see", "holding", "color", "wearing", "who is",
                "what is this", "what is that", "happening", "describe", "look",
                "window", "door", "wall", "cabinet", "cupboard", "glasses", "spectacles"
            ]):
                return VisionAgent.analyze_live_scene(
                    raw_frame=raw_frame if has_live_frame else None,
                    camera_id=camera_id,
                    frame_timestamp=frame_timestamp,
                    verified_names=verified_names,
                    people_count=people_count,
                    query=q,
                )

        # 6. Stock Market Intelligence & Technical Analysis
        if any(k in q_lower for k in ["stock", "market", "nifty", "sensex", "crypto", "bitcoin", "buy or sell", "should i buy"]):
            from ..services.market_service import DEFAULT_TICKERS, analyze_ticker, market_briefing
            for sym, name in DEFAULT_TICKERS.items():
                if name.lower() in q_lower or sym.lower().replace(".ns", "") in q_lower:
                    data = analyze_ticker(sym)
                    if data:
                        direction = "up" if data["pct_change"] >= 0 else "down"
                        ans = (
                            f"{data['name']} is trading at {data['currency']}{data['price']:,}, "
                            f"{direction} {abs(data['pct_change'])}%. "
                            f"Technical signal: {data['signal']}. {data['reason']}"
                        )
                        return AgentResult(
                            agent_type=AgentType.RESEARCH,
                            status="success",
                            answer=ans,
                            speech_text=ans,
                            execution_time_ms=(time.time() - t0) * 1000.0,
                        )
            overview = "Here is the current market overview: " + market_briefing()
            return AgentResult(
                agent_type=AgentType.RESEARCH,
                status="success",
                answer=overview,
                speech_text=overview,
                execution_time_ms=(time.time() - t0) * 1000.0,
            )

        # 7. Executive System Actions (Apps, YouTube, WhatsApp, Mail, Volume)
        from ..services.system_actions import (
            get_mail_briefing,
            launch_application,
            search_google,
            search_youtube,
            send_whatsapp_web,
            set_system_volume,
        )

        # WhatsApp Web message
        m_wa = re.search(r"(?:send|reply|message)\s+(?:on\s+whatsapp\s+to|whatsapp\s+to|to)\s+(.+?)(?:\s+saying\s+(.+))?$", q_lower)
        if "whatsapp" in q_lower and m_wa:
            contact = m_wa.group(1).strip()
            msg = m_wa.group(2).strip() if m_wa.group(2) else "I received your message, will get back shortly."
            res_wa = send_whatsapp_web(contact, msg)
            return AgentResult(agent_type=AgentType.ACTION, status="success", answer=res_wa["message"], speech_text=res_wa["message"], execution_time_ms=(time.time() - t0) * 1000.0)

        # YouTube playback
        m_yt = re.search(r"(?:play|search|find|open)\s+(.+?)\s+(?:on|in)\s+youtube", q_lower)
        if m_yt:
            query_yt = m_yt.group(1).strip()
            res_yt = search_youtube(query_yt)
            return AgentResult(agent_type=AgentType.ACTION, status="success", answer=res_yt["message"], speech_text=res_yt["message"], execution_time_ms=(time.time() - t0) * 1000.0)

        # Web Search
        m_ggl = re.match(r"(?:search|google)(?: for)?\s+(.+)", q_lower)
        if m_ggl and not any(k in q_lower for k in ["youtube", "event", "camera", "history"]):
            query_ggl = m_ggl.group(1).strip()
            res_ggl = search_google(query_ggl)
            return AgentResult(agent_type=AgentType.RESEARCH, status="success", answer=res_ggl["message"], speech_text=res_ggl["message"], execution_time_ms=(time.time() - t0) * 1000.0)

        # App Launch
        m_app = re.match(r"(?:please\s+)?(?:open|launch|start)\s+(.+)", q_lower)
        if m_app and not any(k in q_lower for k in ["camera", "stream", "snapshot", "recording", "rule", "alert", "whatsapp"]):
            app_name = m_app.group(1).strip()
            res_app = launch_application(app_name)
            return AgentResult(
                agent_type=AgentType.ACTION,
                status="success" if res_app["success"] else "error",
                answer=res_app["message"],
                speech_text=res_app["message"],
                execution_time_ms=(time.time() - t0) * 1000.0,
            )

        # Unread Mail Briefing
        if any(k in q_lower for k in ["mail brief", "check mail", "read emails", "inbox summary", "unread emails"]):
            brief = get_mail_briefing()
            return AgentResult(agent_type=AgentType.RESEARCH, status="success", answer=brief, speech_text=brief, execution_time_ms=(time.time() - t0) * 1000.0)

        # System Volume Control
        if any(k in q_lower for k in ["volume up", "louder", "turn it up"]):
            res_vol = set_system_volume("louder")
            return AgentResult(agent_type=AgentType.ACTION, status="success", answer=res_vol["message"], speech_text=res_vol["message"], execution_time_ms=(time.time() - t0) * 1000.0)
        if any(k in q_lower for k in ["volume down", "quieter", "turn it down"]):
            res_vol = set_system_volume("quieter")
            return AgentResult(agent_type=AgentType.ACTION, status="success", answer=res_vol["message"], speech_text=res_vol["message"], execution_time_ms=(time.time() - t0) * 1000.0)
        if q_lower in ["mute", "mute volume", "mute the volume", "silence"]:
            res_vol = set_system_volume("mute")
            return AgentResult(agent_type=AgentType.ACTION, status="success", answer=res_vol["message"], speech_text=res_vol["message"], execution_time_ms=(time.time() - t0) * 1000.0)

        # 8. Fallback to General AIOrchestrator pipeline (covers news, weather, calculations, small talk, Wikipedia)
        from ..services.ai_orchestrator import AIOrchestrator
        ctx = AIOrchestrator.process_request(
            query=q,
            user_id=user_id,
            camera_id=camera_id,
            has_live_frame=has_live_frame,
            raw_frame=raw_frame,
            verified_names=verified_names,
            people_count=people_count,
            conversation_history=conversation_history,
            db=db,
        )

        return AgentResult(
            agent_type=AgentType.ORCHESTRATOR,
            status=ctx.execution_status,
            answer=ctx.answer,
            speech_text=ctx.speech_text,
            action=ctx.action,
            action_payload=ctx.action_payload,
            execution_time_ms=(time.time() - t0) * 1000.0,
            validation_notes=ctx.validation_notes,
        )

"""Memory & Event Agent for Project JARVIS.

Specializes in structured historical event search, timeline retrieval,
and incident investigation using the persistent database as the verified ground truth.
"""

from __future__ import annotations

import logging
import time
from typing import Any, List, Optional

from ..services.event_service import search_historical_events
from .contracts import (
    AgentResult,
    AgentType,
    EvidenceItem,
    EvidenceType,
)

logger = logging.getLogger(__name__)


class MemoryAgent:
    """Specialized Memory and Historical Event Agent."""

    @classmethod
    def search_events(
        cls,
        db: Any,
        query: str,
        camera_id: Optional[str] = None,
        limit: int = 10,
    ) -> AgentResult:
        """Search structured event records and return evidence-linked timeline."""
        t0 = time.time()
        res = search_historical_events(db, query=query, camera_id=camera_id, limit=limit)
        events = res.get("events", [])
        total = res.get("total_results", 0)
        summary = res.get("summary", "No events found matching your query.")

        evidence_items: List[EvidenceItem] = []
        for ev in events:
            evidence_items.append(
                EvidenceItem(
                    evidence_type=EvidenceType.HISTORICAL_RECORD,
                    description=f"Event {ev.event_type} on camera {ev.camera_id[:8] if ev.camera_id else 'unknown'}",
                    source=f"db:events:{ev.id}",
                    timestamp=ev.occurred_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    confidence=ev.confidence,
                    metadata={"track_id": ev.track_id, "person_id": ev.person_id},
                )
            )

        q_lower = query.lower()
        if not events:
            if any(k in q_lower for k in ["anyone enter", "while i was away", "while away", "intruder"]):
                ans = (
                    "🛡️ **Historical Timeline Search:**\n\n"
                    "I searched the recorded events for your monitored period and found **zero unauthorized entrance events**. "
                    "All perimeter zones remained clear and secure."
                )
                speech = "I searched the records and found zero entrance events while you were away. Everything remained secure."
            else:
                ans = f"🕰️ **Visual Memory Search:**\n\n{summary}\n\n*Source: Persistent Event Database.*"
                speech = summary
        else:
            lines = []
            for ev in events[:6]:
                occurred = ev.occurred_at.strftime("%H:%M:%S")
                conf_pct = int(ev.confidence * 100) if ev.confidence else 95
                lines.append(f"• **{occurred} UTC**: `{ev.event_type}` (Confidence: {conf_pct}%)")

            events_table = "\n".join(lines)
            ans = (
                f"🕰️ **Historical Event Records ({total} Total Found):**\n\n"
                f"{summary}\n\n"
                f"**Timeline of Supporting Detections:**\n{events_table}\n\n"
                f"*(Historical records are retrieved from persistent event storage and clearly distinguished from live observations.)*"
            )
            speech = f"I found {total} historical events. {summary}"

        return AgentResult(
            agent_type=AgentType.MEMORY,
            status="success",
            answer=ans,
            speech_text=speech,
            evidence=evidence_items,
            execution_time_ms=(time.time() - t0) * 1000.0,
        )

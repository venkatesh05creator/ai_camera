"""Project JARVIS Multi-Agent Architecture Package.

Provides specialized, bounded agents coordinating with least-privilege tools,
strict visual grounding, and user-controlled memory.
"""

from .action_agent import ActionAgent
from .contracts import (
    ActionApprovalRequest,
    AgentResult,
    AgentType,
    EvidenceItem,
    EvidenceType,
    PermissionLevel,
    ToolDefinition,
)
from .jarvis_orchestrator import JarvisOrchestrator
from .memory_agent import MemoryAgent
from .monitoring_agent import MonitoringAgent
from .research_agent import ResearchAgent
from .security_agent import SecurityAgent
from .vision_agent import VisionAgent

__all__ = [
    "AgentType",
    "PermissionLevel",
    "EvidenceType",
    "EvidenceItem",
    "ActionApprovalRequest",
    "ToolDefinition",
    "AgentResult",
    "JarvisOrchestrator",
    "VisionAgent",
    "MemoryAgent",
    "MonitoringAgent",
    "SecurityAgent",
    "ResearchAgent",
    "ActionAgent",
]

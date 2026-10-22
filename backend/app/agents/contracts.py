"""Typed Contracts and Data Definitions for Project JARVIS Agent System.

Defines agent roles, permission levels, tool definitions, approval requests,
and typed result structures with strict evidence provenance tracking.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class AgentType(str, Enum):
    """Specialized agents in the JARVIS multi-agent architecture."""
    ORCHESTRATOR = "orchestrator"
    VISION = "vision"
    MEMORY = "memory"
    MONITORING = "monitoring"
    SECURITY = "security"
    RESEARCH = "research"
    ACTION = "action"


class PermissionLevel(str, Enum):
    """Least-privilege permission tiers for tool and action execution."""
    READ_ONLY = "read_only"                       # No state changes, safe to auto-execute
    REVERSIBLE_CONFIG = "reversible_config"       # Non-destructive setting toggles (e.g. mute, pause stream)
    SENSITIVE_CONSEQUENTIAL = "sensitive"         # File creation, video recording, biometric enrollment
    PROHIBITED = "prohibited"                     # Arbitrary shell, raw code, unrestricted network


class EvidenceType(str, Enum):
    """Strictly categorizes what the assistant reports."""
    DIRECT_OBSERVATION = "direct_observation"     # Directly detected in fresh camera frame
    MODEL_INFERENCE = "model_inference"           # Inferred scene description or posture
    HISTORICAL_RECORD = "historical_record"       # Retrieved from persistent database event logs
    UNKNOWN = "unknown"                           # Explicitly unverified or unobservable fact


@dataclass
class EvidenceItem:
    """Individual piece of grounded evidence with provenance."""
    evidence_type: EvidenceType
    description: str
    source: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%H:%M:%S UTC"))
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionApprovalRequest:
    """Approval request for sensitive or consequential operations."""
    approval_token: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_name: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    permission_level: PermissionLevel = PermissionLevel.SENSITIVE_CONSEQUENTIAL
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 300.0)  # 5 min expiry
    is_approved: bool = False
    actor_user_id: Optional[str] = None

    def is_valid(self) -> bool:
        """Check if approval is within expiration time and approved."""
        return self.is_approved and (time.time() <= self.expires_at)


@dataclass
class ToolDefinition:
    """Contract specification for an allowlisted, typed agent tool."""
    name: str
    description: str
    permission_level: PermissionLevel
    parameters_schema: Dict[str, Any]
    handler: Callable[..., Any]
    timeout_seconds: float = 10.0
    requires_approval: bool = False


@dataclass
class AgentResult:
    """Standardized output returned by every specialized agent."""
    agent_type: AgentType
    status: str = "success"                       # "success", "error", "awaiting_approval"
    answer: str = ""
    speech_text: str = ""
    evidence: List[EvidenceItem] = field(default_factory=list)
    action: Optional[str] = None
    action_payload: Dict[str, Any] = field(default_factory=dict)
    approval_request: Optional[ActionApprovalRequest] = None
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    validation_notes: List[str] = field(default_factory=list)

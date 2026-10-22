"""Action Agent for Project JARVIS.

Enforces least privilege and policy-driven execution for allowlisted tools.
Requires explicit owner approval for sensitive or consequential operations.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from .contracts import (
    ActionApprovalRequest,
    AgentResult,
    AgentType,
    PermissionLevel,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


class ActionAgent:
    """Specialized Agent for secure, bounded tool execution."""

    _tools: Dict[str, ToolDefinition] = {}
    _active_approvals: Dict[str, ActionApprovalRequest] = {}

    @classmethod
    def register_tool(cls, tool: ToolDefinition) -> None:
        """Register an allowlisted tool with its permission contract."""
        cls._tools[tool.name] = tool

    @classmethod
    def request_approval(
        cls,
        action_name: str,
        parameters: Dict[str, Any],
        reason: str,
        actor_user_id: Optional[str] = None,
    ) -> ActionApprovalRequest:
        """Create a pending approval request for a sensitive/consequential action."""
        req = ActionApprovalRequest(
            action_name=action_name,
            parameters=parameters,
            reason=reason,
            permission_level=PermissionLevel.SENSITIVE_CONSEQUENTIAL,
            actor_user_id=actor_user_id,
        )
        cls._active_approvals[req.approval_token] = req
        return req

    @classmethod
    def confirm_approval(cls, approval_token: str) -> Optional[ActionApprovalRequest]:
        """Validate and grant an active approval request."""
        req = cls._active_approvals.get(approval_token)
        if req and not req.is_consumed and time.time() <= req.expires_at:
            req.is_approved = True
            return req
        return None

    @classmethod
    def execute_tool(
        cls,
        tool_name: str,
        parameters: Dict[str, Any],
        approval_token: Optional[str] = None,
        actor_user_id: Optional[str] = None,
    ) -> AgentResult:
        """Execute tool respecting permission levels and approval tokens."""
        t0 = time.time()
        tool = cls._tools.get(tool_name)

        if not tool:
            return AgentResult(
                agent_type=AgentType.ACTION,
                status="error",
                error=f"Tool '{tool_name}' is not in the allowlisted tool registry.",
                answer=f"⚠️ Action rejected: `{tool_name}` is not an authorized tool.",
                speech_text=f"Action rejected: {tool_name} is not authorized.",
                execution_time_ms=(time.time() - t0) * 1000.0,
            )

        # Prohibited check
        if tool.permission_level == PermissionLevel.PROHIBITED:
            return AgentResult(
                agent_type=AgentType.ACTION,
                status="error",
                error=f"Execution of prohibited tool '{tool_name}' was blocked.",
                answer="🚫 Security policy violation: This action is prohibited.",
                speech_text="This action is prohibited by system policy.",
                execution_time_ms=(time.time() - t0) * 1000.0,
            )

        # Sensitive Consequential check: requires approval if marked
        if tool.requires_approval or tool.permission_level == PermissionLevel.SENSITIVE_CONSEQUENTIAL:
            if not approval_token:
                # Generate new approval request
                approval = cls.request_approval(
                    action_name=tool_name,
                    parameters=parameters,
                    reason=f"Action '{tool_name}' requires explicit owner approval.",
                    actor_user_id=actor_user_id,
                )
                return AgentResult(
                    agent_type=AgentType.ACTION,
                    status="awaiting_approval",
                    approval_request=approval,
                    answer=(
                        f"⚠️ **Approval Required for Action:** `{tool_name}`\n\n"
                        f"• Reason: {approval.reason}\n"
                        f"• Parameters: `{parameters}`\n"
                        f"• Token: `{approval.approval_token}` (Expires in 5 minutes)\n\n"
                        f"Please confirm whether you approve this operation."
                    ),
                    speech_text=f"Action {tool_name} requires your explicit approval. Would you like me to proceed?",
                    execution_time_ms=(time.time() - t0) * 1000.0,
                )
            else:
                valid_approval = cls.confirm_approval(approval_token)
                if not valid_approval or valid_approval.is_consumed or (time.time() > valid_approval.expires_at):
                    return AgentResult(
                        agent_type=AgentType.ACTION,
                        status="error",
                        error="Invalid or expired approval token.",
                        answer="⚠️ Action blocked: The approval token has expired or is invalid.",
                        speech_text="Approval token has expired.",
                        execution_time_ms=(time.time() - t0) * 1000.0,
                    )
                if valid_approval.action_name != tool_name:
                    return AgentResult(
                        agent_type=AgentType.ACTION,
                        status="error",
                        error=f"Approval token was issued for '{valid_approval.action_name}', not '{tool_name}'.",
                        answer="⚠️ Action blocked: Approval token does not match requested action.",
                        speech_text="Approval token does not match requested action.",
                        execution_time_ms=(time.time() - t0) * 1000.0,
                    )
                if valid_approval.parameters != parameters:
                    return AgentResult(
                        agent_type=AgentType.ACTION,
                        status="error",
                        error="Approval token parameters do not match requested execution parameters.",
                        answer="⚠️ Action blocked: Action parameters do not match approved parameters.",
                        speech_text="Action parameters do not match approved parameters.",
                        execution_time_ms=(time.time() - t0) * 1000.0,
                    )
                if actor_user_id and valid_approval.actor_user_id and valid_approval.actor_user_id != actor_user_id:
                    return AgentResult(
                        agent_type=AgentType.ACTION,
                        status="error",
                        error="Cross-user approval token execution rejected.",
                        answer="⚠️ Action blocked: Approval token was not issued for your account.",
                        speech_text="Approval token was not issued for your account.",
                        execution_time_ms=(time.time() - t0) * 1000.0,
                    )
                # Consume approval token so it cannot be replayed
                valid_approval.is_consumed = True
                cls._active_approvals.pop(approval_token, None)

        # Execute allowlisted handler
        try:
            result_data = tool.handler(**parameters)
            return AgentResult(
                agent_type=AgentType.ACTION,
                status="success",
                action=tool_name,
                action_payload={"result": result_data, "parameters": parameters},
                answer=f"✅ Successfully executed action: **{tool.description}**.",
                speech_text=f"Action {tool_name} executed successfully.",
                execution_time_ms=(time.time() - t0) * 1000.0,
            )
        except Exception as e:
            logger.error("Tool execution error in %s: %s", tool_name, e)
            return AgentResult(
                agent_type=AgentType.ACTION,
                status="error",
                error=str(e),
                answer=f"⚠️ Failed to execute action `{tool_name}`: {e}",
                speech_text=f"Execution error for action {tool_name}.",
                execution_time_ms=(time.time() - t0) * 1000.0,
            )

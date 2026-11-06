"""Pluggable Model Context Protocol tool runtime (Phase 3B rank #7).

Tools register with a JSON-Schema-like input spec and are called through a
validated interface.  Mutating tools require explicit owner confirmation
(consistent with SafeToolRegistry).  Ships behind the ``MCP_RUNTIME`` feature
flag.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..features import is_enabled
from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)


class MCPError(RuntimeError):
    """Raised by the MCP runtime."""


class MCPTool:
    """A single registered MCP tool."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler,
        *,
        mutating: bool = False,
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.handler = handler
        self.mutating = mutating


class MCPRuntime:
    """Registry of MCP tools with validation and confirmation gating."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._tools: dict[str, MCPTool] = {}

    def _enabled(self) -> bool:
        return is_enabled("MCP_RUNTIME")

    def register(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler,
        *,
        mutating: bool = False,
    ) -> None:
        """Register a tool.  Re-registering overwrites."""
        if not self._enabled():
            raise MCPError("MCP_RUNTIME feature is not enabled")
        self._tools[name] = MCPTool(name, description, input_schema, handler, mutating=mutating)
        logger.info("mcp tool registered", extra={"tool": name, "mutating": mutating})

    def list_tools(self) -> list[dict[str, Any]]:
        """Return all registered tools (without handlers)."""
        if not self._enabled():
            return []
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
                "mutating": t.mutating,
            }
            for t in self._tools.values()
        ]

    def call(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        """Call a registered tool with validation.

        Mutating tools require ``confirmed=True``.
        """
        if not self._enabled():
            raise MCPError("MCP_RUNTIME feature is not enabled")
        tool = self._tools.get(name)
        if tool is None:
            raise MCPError(f"unknown tool: {name}")
        if tool.mutating and not confirmed:
            return {
                "tool": name,
                "status": "requires_confirmation",
                "arguments": arguments,
                "message": "This action changes state and must be confirmed explicitly.",
            }
        # Basic input validation: required fields present.
        required = tool.input_schema.get("required", []) or []
        for field in required:
            if field not in arguments:
                raise MCPError(f"missing required argument: {field}")
        try:
            result = tool.handler(arguments)
            return {"tool": name, "status": "ok", "result": result}
        except Exception as exc:  # pragma: no cover - tool-specific
            logger.exception("mcp tool call failed", extra={"tool": name})
            raise MCPError(f"tool {name} failed: {type(exc).__name__}") from exc

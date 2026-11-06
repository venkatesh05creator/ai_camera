"""Skills format for Aegis tools (OpenJarvis transplant, Phase O-5).

New tools are declared in one validated skill manifest file and loaded through
a validated interface.  Skills are NOT self-installed from the internet -
that is explicitly prohibited.  Each skill declares its input schema and
whether it mutates state; mutating skills require explicit owner confirmation
through SafeToolRegistry, exactly like built-in tools.

Ships behind the ``SKILLS_FORMAT`` feature flag (opt-in, default off).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from ..features import is_enabled
from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)


class SkillError(RuntimeError):
    """Raised when a skill manifest cannot be loaded or validated."""


@dataclass
class Skill:
    """A single skill declaration.

    ``handler`` names a function previously registered with
    ``SkillsRegistry.register_handler``.  The handler receives the validated
    input arguments and returns a result dict.
    """

    name: str
    description: str
    input_schema: Dict[str, Any]
    mutating: bool = False
    handler: str = ""

    def to_tool_spec(self, permission: str) -> Dict[str, Any]:
        """Convert to a SafeToolRegistry tool spec."""
        return {
            "description": self.description,
            "permission": permission,
            "mutating": self.mutating,
            "input_schema": self.input_schema,
            "skill": self.name,
        }


@dataclass
class SkillHandler:
    """A registered skill handler function."""

    func: Callable[..., Any]


class SkillsRegistry:
    """Loads skill manifests and registers them as SafeToolRegistry tools.

    Skills are declared by the owner in a manifest file and are never
    auto-installed from the internet.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._handlers: Dict[str, SkillHandler] = {}
        self._skills: Dict[str, Skill] = {}

    def _enabled(self) -> bool:
        return is_enabled("SKILLS_FORMAT")

    def register_handler(self, name: str, func: Callable[..., Any]) -> None:
        """Register a handler function that a skill manifest can reference."""
        if not self._enabled():
            raise SkillError("SKILLS_FORMAT feature is not enabled")
        self._handlers[name] = SkillHandler(func)

    def reset(self) -> None:
        """Clear all registered handlers and loaded skills (for tests)."""
        self._handlers.clear()
        self._skills.clear()

    def _validate_input_schema(self, schema: Any) -> None:
        """Validate that ``schema`` is a minimal JSON Schema object."""
        if not isinstance(schema, dict):
            raise SkillError("input_schema must be a JSON object")
        if schema.get("type") not in (None, "object"):
            raise SkillError("input_schema.type must be 'object' or omitted")
        props = schema.get("properties")
        if props is not None and not isinstance(props, dict):
            raise SkillError("input_schema.properties must be an object")
        required = schema.get("required")
        if required is not None and not isinstance(required, list):
            raise SkillError("input_schema.required must be a list")

    def load_manifest(self, path: str) -> Dict[str, Skill]:
        """Load and validate a skill manifest file.

        The manifest is a JSON object with a ``skills`` list.  Each skill
        declares name, description, input_schema, mutating flag and handler
        name.  Returns the loaded skills keyed by name.
        """
        if not self._enabled():
            raise SkillError("SKILLS_FORMAT feature is not enabled")

        with open(path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        if not isinstance(manifest, dict):
            raise SkillError("manifest must be a JSON object")
        skills_raw = manifest.get("skills")
        if not isinstance(skills_raw, list):
            raise SkillError("manifest.skills must be a list")

        loaded: Dict[str, Skill] = {}
        for entry in skills_raw:
            if not isinstance(entry, dict):
                raise SkillError("each skill must be a JSON object")
            name = str(entry.get("name", "")).strip()
            description = str(entry.get("description", ""))
            input_schema = entry.get("input_schema", {}) or {}
            mutating = bool(entry.get("mutating", False))
            handler = str(entry.get("handler", "")).strip()

            if not name:
                raise SkillError("skill missing name")
            if not handler:
                raise SkillError(f"skill {name!r} missing handler")
            if handler not in self._handlers:
                raise SkillError(f"skill {name!r} references unknown handler {handler!r}")
            self._validate_input_schema(input_schema)

            skill = Skill(
                name=name,
                description=description,
                input_schema=input_schema,
                mutating=mutating,
                handler=handler,
            )
            loaded[name] = skill
            self._skills[name] = skill
        return loaded

    def list_skills(self) -> Dict[str, Skill]:
        """Return all loaded skills keyed by name."""
        if not self._enabled():
            return {}
        return dict(self._skills)

    def handler_for(self, name: str) -> Optional[SkillHandler]:
        """Return the handler for a registered skill name."""
        return self._skills.get(name) and self._handlers.get(self._skills[name].handler)

    def register_tool_specs(self) -> int:
        """Register all loaded skills into the SafeToolRegistry (TOOL_SPECS).

        Returns the number of skills registered.  Mutating skills are flagged
        so they require explicit owner confirmation.
        """
        from ..services.ai import TOOL_SPECS  # noqa: PLC0415

        count = 0
        for name, skill in self._skills.items():
            if name in TOOL_SPECS:
                logger.warning("skill %s shadows existing tool %s", name, name)
            handler = self._handlers.get(skill.handler)
            if handler is None:
                raise SkillError(f"skill {name!r} has no registered handler")
            TOOL_SPECS[name] = skill.to_tool_spec(permission="chat:write")
            count += 1
        return count

    def execute_skill(
        self, name: str, arguments: Dict[str, Any], *, confirmed: bool = False
    ) -> Dict[str, Any]:
        """Execute a loaded skill with confirmation gating for mutating skills.

        Mirrors SafeToolRegistry confirmation semantics.
        """
        if not self._enabled():
            raise SkillError("SKILLS_FORMAT feature is not enabled")
        skill = self._skills.get(name)
        if skill is None:
            raise SkillError(f"unknown skill {name!r}")
        handler = self._handlers.get(skill.handler)
        if handler is None:
            raise SkillError(f"skill {name!r} has no registered handler")
        if skill.mutating and not confirmed:
            return {
                "tool": name,
                "status": "requires_confirmation",
                "arguments": arguments,
                "message": "This skill changes state and must be confirmed explicitly.",
            }
        # Validate required arguments.
        required = skill.input_schema.get("required", []) or []
        for field_name in required:
            if field_name not in arguments:
                raise SkillError(f"missing required argument: {field_name}")
        try:
            result = handler.func(**arguments)
            return {"tool": name, "status": "ok", "result": result}
        except Exception as exc:  # pragma: no cover - skill-specific
            logger.exception("skill %s failed", name)
            raise SkillError(f"skill {name} failed: {type(exc).__name__}") from exc

"""Voice command handling.

The voice interface must not make mistakes, so *commands* are **not** routed
through a language model.  A small, deterministic grammar recognises a fixed
set of intents and answers them from the caller's own data.  Only free-form
questions fall through to the assistant, where the existing prompt-injection
defences and budgets apply.

Privacy notes:

* The audio itself never reaches this server - the browser performs the
  speech recognition locally (Web Speech API) and sends the resulting text.
* Transcripts are treated exactly like a typed chat message: they are stored
  in the owner's conversation history and nowhere else.
* The parser is an allow-list.  A command can never trigger an action that
  the caller is not allowed to perform, and it never evaluates anything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models import User

#: The colour palette of the application (mirrors static/css/app.css).
THEME_BACKGROUNDS = {
    "light": "#f4f6fb",
    "dark": "#0d1220",
}

_PUNCTUATION = re.compile(r"[^\w\s#]+", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Lower-case, strip punctuation and collapse whitespace."""
    lowered = (text or "").strip().lower()
    lowered = _PUNCTUATION.sub(" ", lowered)
    return _WHITESPACE.sub(" ", lowered).strip()


@dataclass
class VoiceCommand:
    """The result of parsing a spoken (or typed) command."""

    intent: str
    answer: str
    speak: str = ""
    action: Dict[str, Any] = field(default_factory=dict)
    #: ``True`` when only the browser can answer the question (it owns the
    #: rendered state, e.g. the effective background colour).
    client_resolved: bool = False
    #: ``True`` when the question was handed over to the assistant.
    use_assistant: bool = False

    def __post_init__(self) -> None:
        if not self.speak:
            self.speak = self.answer


# ---------------------------------------------------------------------------
# Intent definitions
# ---------------------------------------------------------------------------
# Each entry maps a normalised command to an intent.  The longest, most
# specific phrase wins, so "switch to dark mode" is never swallowed by
# "what is the theme".
_KEYWORD_INTENTS: List[tuple[str, str]] = [
    # --- theme / appearance -------------------------------------------
    ("switch to dark mode", "theme_dark"),
    ("switch to the dark mode", "theme_dark"),
    ("turn on dark mode", "theme_dark"),
    ("enable dark mode", "theme_dark"),
    ("use the dark theme", "theme_dark"),
    ("go dark", "theme_dark"),
    ("switch to light mode", "theme_light"),
    ("switch to the light mode", "theme_light"),
    ("turn on light mode", "theme_light"),
    ("enable light mode", "theme_light"),
    ("use the light theme", "theme_light"),
    ("go light", "theme_light"),
    ("what is my background color", "background_color"),
    ("what is my background colour", "background_color"),
    ("what colour is the background", "background_color"),
    ("what color is the background", "background_color"),
    ("what is the background color", "background_color"),
    ("what is the background colour", "background_color"),
    ("what is my background", "background_color"),
    ("what is the background", "background_color"),
    ("background color", "background_color"),
    ("background colour", "background_color"),
    ("what theme am i using", "current_theme"),
    ("which theme am i using", "current_theme"),
    ("what is the current theme", "current_theme"),
    ("am i in dark mode", "current_theme"),
    ("is dark mode on", "current_theme"),
    ("is light mode on", "current_theme"),
    # --- the owner's own data -----------------------------------------
    ("how many cameras do i have", "device_count"),
    ("how many devices do i have", "device_count"),
    ("how many cameras", "device_count"),
    ("how many devices", "device_count"),
    ("how many cameras are there", "device_count"),
    ("how many events do i have", "event_count"),
    ("how many events are there", "event_count"),
    ("how many events", "event_count"),
    ("count my events", "event_count"),
    ("what was the last event", "latest_event"),
    ("what was the latest event", "latest_event"),
    ("what happened last", "latest_event"),
    ("latest event", "latest_event"),
    ("last event", "latest_event"),
    ("how many identities do i have", "identity_count"),
    ("how many faces are enrolled", "identity_count"),
    ("how many identities", "identity_count"),
    ("how many faces", "identity_count"),
    ("how many conversations do i have", "conversation_count"),
    ("how many conversations", "conversation_count"),
    ("how many sessions are active", "session_count"),
    # --- navigation / control -----------------------------------------
    ("open the dashboard", "open_dashboard"),
    ("go to the dashboard", "open_dashboard"),
    ("show the dashboard", "open_dashboard"),
    ("open the hud", "open_hud"),
    ("open hud", "open_hud"),
    ("show the hud", "open_hud"),
    ("open workplace", "open_hud"),
    ("stock market report", "market_report"),
    ("market briefing", "market_report"),
    ("how is the market", "market_report"),
    ("market report", "market_report"),
    ("check emails", "mail_brief"),
    ("read unread emails", "mail_brief"),
    ("unread emails", "mail_brief"),
    ("what time is it", "current_time"),
    ("what is the time", "current_time"),
    ("what date is today", "current_time"),
    ("what is today's date", "current_time"),
    ("open the administration", "open_admin"),
    ("go to the administration", "open_admin"),
    ("show the administration", "open_admin"),
    ("scroll to top", "scroll_top"),
    ("back to top", "scroll_top"),
    ("stop talking", "stop_speaking"),
    ("stop speaking", "stop_speaking"),
    ("be quiet", "stop_speaking"),
    ("shut up", "stop_speaking"),
    # --- small talk ----------------------------------------------------
    ("hello", "greeting"),
    ("hi", "greeting"),
    ("hey", "greeting"),
    ("good morning", "greeting"),
    ("good evening", "greeting"),
    ("thank you", "thanks"),
    ("thanks", "thanks"),
    ("what can you do", "help"),
    ("what do you do", "help"),
    ("help", "help"),
]

#: Phrases that are explicitly not commands (they are real questions).
_QUESTION_MARKERS = ("what ", "why ", "how ", "when ", "where ", "who ", "which ")

#: Words that may precede a command ("tell me how many cameras ...").
_LEAD_IN_WORDS = frozenset(
    {
        "tell",
        "me",
        "please",
        "can",
        "you",
        "do",
        "know",
        "i",
        "want",
        "to",
        "hey",
        "jarvis",
        "ok",
        "okay",
        "so",
        "now",
        "and",
        "also",
        "well",
        "just",
    }
)

#: Words that may follow a command ("how many cameras do i have please").
_FILLER_WORDS = frozenset(
    {
        "please",
        "thanks",
        "thank",
        "you",
        "now",
        "ok",
        "okay",
        "right",
        "for",
        "me",
        "exactly",
        "again",
        "today",
        "and",
        "tell",
    }
)

#: Intents that are answered by the browser because only it knows the state.
CLIENT_RESOLVED = {"background_color", "current_theme", "theme_dark", "theme_light", "scroll_top", "stop_speaking"}


def _only_words(text: str, allowed: frozenset) -> bool:
    """Return ``True`` when every word of ``text`` is in ``allowed``."""
    words = [word for word in text.split() if word]
    if not words:
        return False
    return all(word in allowed for word in words)


def match_intent(text: str) -> str:
    """Return the intent of a command or ``"assistant"`` when nothing matched.

    The matcher is deliberately strict: an utterance is only treated as a
    command when it *is* the command (plus an optional short lead-in or
    filler).  Anything longer - in particular an injected instruction that
    merely ends with a command phrase - is handed to the assistant, where the
    regular prompt-injection defences apply.
    """
    normalised = normalise(text)
    if not normalised:
        return "empty"

    best_intent = ""
    best_length = 0
    for phrase, intent in _KEYWORD_INTENTS:
        matched = False
        if normalised == phrase:
            matched = True
        elif normalised.startswith(phrase + " "):
            remainder = normalised[len(phrase) :].strip()
            matched = _only_words(remainder, _FILLER_WORDS)
        elif normalised.endswith(" " + phrase):
            prefix = normalised[: -len(phrase)].strip()
            matched = _only_words(prefix, _LEAD_IN_WORDS)
        if matched and len(phrase) > best_length:
            best_intent = intent
            best_length = len(phrase)
    if best_intent:
        return best_intent

    # A question that merely contains a keyword is a question, not a command.
    if normalised.startswith(_QUESTION_MARKERS) or normalised.endswith("?"):
        return "assistant"
    if "can you" in normalised or "could you" in normalised or "please" in normalised:
        return "assistant"
    return "assistant"


def help_text() -> str:
    """The list of supported commands (also used by the assistant prompt)."""
    return (
        "You can ask: how many cameras do I have, what was the latest event, how many "
        "events are there, how many faces are enrolled, what is my background colour, "
        "what theme am I using, switch to dark mode, switch to light mode, open the "
        "dashboard, or ask me anything about your cameras."
    )


def build_command(
    db: Session,
    user: User,
    text: str,
    *,
    language: str = "en-US",
) -> VoiceCommand:
    """Parse a command and build the answer from the caller's own data."""
    intent = match_intent(text)

    if intent == "empty":
        return VoiceCommand(intent="empty", answer="I did not catch that. Please repeat the question.")

    if intent == "greeting":
        return VoiceCommand(intent="greeting", answer="Hello. How can I help with your cameras?")
    if intent == "thanks":
        return VoiceCommand(intent="thanks", answer="You are welcome.")
    if intent == "help":
        return VoiceCommand(intent="help", answer=help_text())

    if intent in {"background_color", "current_theme"}:
        palette = "The light theme uses {light}, the dark theme uses {dark}.".format(
            light=THEME_BACKGROUNDS["light"], dark=THEME_BACKGROUNDS["dark"]
        )
        return VoiceCommand(
            intent=intent,
            answer=palette,
            client_resolved=True,
            action={"type": "describe_appearance"},
        )

    if intent in {"theme_dark", "theme_light"}:
        target = "dark" if intent == "theme_dark" else "light"
        return VoiceCommand(
            intent=intent,
            answer=f"Switching to the {target} theme.",
            client_resolved=True,
            action={"type": "set_theme", "theme": target},
        )

    if intent == "open_dashboard":
        return VoiceCommand(
            intent="open_dashboard",
            answer="Opening the dashboard.",
            client_resolved=True,
            action={"type": "navigate", "url": "/dashboard"},
        )
    if intent == "open_hud":
        return VoiceCommand(
            intent="open_hud",
            answer="Initializing Holographic HUD.",
            client_resolved=True,
            action={"type": "navigate", "url": "/hud"},
        )
    if intent == "market_report":
        from backend.app.services.market_service import market_briefing
        brief = market_briefing()
        return VoiceCommand(
            intent="market_report",
            answer=brief,
            speak=brief,
        )
    if intent == "mail_brief":
        from backend.app.services.system_actions import get_mail_briefing
        mail = get_mail_briefing()
        return VoiceCommand(
            intent="mail_brief",
            answer=mail,
            speak=mail,
        )
    if intent == "current_time":
        from backend.app.services.system_actions import get_current_time_and_date
        td = get_current_time_and_date()
        ans = f"It is currently {td['time']} on {td['date']}."
        return VoiceCommand(
            intent="current_time",
            answer=ans,
            speak=ans,
        )
    if intent == "open_admin":
        return VoiceCommand(
            intent="open_admin",
            answer="Opening the administration console.",
            client_resolved=True,
            action={"type": "navigate", "url": "/admin"},
        )
    if intent == "scroll_top":
        return VoiceCommand(
            intent="scroll_top",
            answer="Back at the top.",
            client_resolved=True,
            action={"type": "scroll_top"},
        )
    if intent == "stop_speaking":
        return VoiceCommand(
            intent="stop_speaking",
            answer="Stopped.",
            client_resolved=True,
            action={"type": "stop_speaking"},
        )

    if intent == "device_count":
        from ..services.search import count_resources

        counts = count_resources(db, user)
        word = "camera" if counts["devices"] == 1 else "cameras"
        return VoiceCommand(
            intent="device_count",
            answer=f"You have {counts['devices']} {word} registered.",
        )

    if intent == "event_count":
        from ..services.search import count_resources

        counts = count_resources(db, user)
        word = "event" if counts["events"] == 1 else "events"
        return VoiceCommand(
            intent="event_count",
            answer=f"You have {counts['events']} recorded {word}.",
        )

    if intent == "identity_count":
        from ..services.search import count_resources

        counts = count_resources(db, user)
        word = "identity" if counts["identities"] == 1 else "identities"
        return VoiceCommand(
            intent="identity_count",
            answer=f"You have {counts['identities']} enrolled {word}.",
        )

    if intent == "conversation_count":
        from ..services.search import count_resources

        counts = count_resources(db, user)
        word = "conversation" if counts["conversations"] == 1 else "conversations"
        return VoiceCommand(
            intent="conversation_count",
            answer=f"You have {counts['conversations']} {word}.",
        )

    if intent == "session_count":
        from sqlalchemy import select

        from ..models import UserSession

        sessions = db.scalars(
            select(UserSession).where(
                UserSession.user_id == user.id, UserSession.revoked_at.is_(None)
            )
        ).all()
        word = "session" if len(sessions) == 1 else "sessions"
        return VoiceCommand(
            intent="session_count",
            answer=f"You have {len(sessions)} active {word}.",
        )

    if intent == "latest_event":
        from sqlalchemy import select

        from ..models import CameraEvent

        event = db.scalars(
            select(CameraEvent)
            .where(CameraEvent.owner_id == user.id)
            .order_by(CameraEvent.occurred_at.desc())
            .limit(1)
        ).first()
        if event is None:
            return VoiceCommand(intent="latest_event", answer="There are no recorded events yet.")
        summary = event.summary or "no summary"
        stamp = event.occurred_at.strftime("%Y-%m-%d %H:%M UTC")
        return VoiceCommand(
            intent="latest_event",
            answer=f"The latest event was {event.kind} at {stamp}: {summary}.",
        )

    # Free-form question -> the assistant.
    return VoiceCommand(intent="assistant", answer="", use_assistant=True)


def command_to_payload(command: VoiceCommand, *, conversation_id: Optional[int] = None) -> Dict[str, Any]:
    """Serialise a command for the client."""
    payload: Dict[str, Any] = {
        "intent": command.intent,
        "answer": command.answer,
        "speak": command.speak,
        "action": command.action,
        "client_resolved": command.client_resolved,
    }
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    return payload

"""Evidence packs + deterministic answer verification.

Chat evidence comes from real, verifiable sources only:
- audit log entries (hash-chained; see audit_service)
- encrypted memory items the owner taught the assistant

The verifier checks every factual claim in a model reply against the pack:
- badges like ``[E1]`` must reference a real evidence id
- sentences stating facts must carry a valid badge (or a non-factual
  preamble: greeting, honesty marker, meta talk)
- anything failing is reported, never silently accepted
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..services import audit_service, camera_service, memory_service

_BADGE_RE = re.compile(r"\[(E\d+)\]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# openers that are conversation, not factual claims
_NON_FACTUAL_OPENERS = (
    "hi", "hello", "hey", "namaste", "thanks", "thank you", "sorry",
    "hmm", "okay", "ok", "here", "sure", "of course", "good",
    "the short answer", "in short",
)

# sentences asserting ignorance / asking for evidence are not claims
_HONESTY_MARKERS = (
    "don't have evidence", "do not have evidence", "don't know",
    "do not know", "no evidence", "cannot find", "couldn't find",
    "not enough info", "i need more", "i don't see", "missing",
)


class EvidenceItem:
    def __init__(self, item_id: str, source: str, title: str, text: str) -> None:
        self.id = item_id
        self.source = source
        self.title = title
        self.text = text

    def to_dict(self) -> dict:
        return {"id": self.id, "source": self.source,
                "title": self.title, "text": self.text}


class EvidencePack:
    def __init__(self, items: list[EvidenceItem]) -> None:
        self.items = items

    def by_id(self, item_id: str) -> EvidenceItem | None:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def as_context(self) -> str:
        """Text block for the system prompt (all untrusted data)."""
        if not self.items:
            return ("<evidence>\n(no evidence available right now — say so "
                    "when asked about facts)\n</evidence>")
        lines = ["<evidence untrusted=\"true\">"]
        for item in self.items:
            lines.append(f"[{item.id}] ({item.source}) {item.title}: {item.text}")
        lines.append("</evidence>")
        return "\n".join(lines)


def _is_non_factual(sentence: str) -> bool:
    low = sentence.strip().lower()
    if low.endswith("?"):
        return True  # a question is not a factual claim
    core = _BADGE_RE.sub("", low)
    if len(core.split()) < 3:
        return True  # fragments ("thanks", "E3?", "Yes.") carry no claim
    if any(low.startswith(opener) for opener in _NON_FACTUAL_OPENERS):
        return True
    return any(marker in low for marker in _HONESTY_MARKERS)


def verify_reply(answer: str, pack: EvidencePack) -> dict:
    """Deterministic verification of one model reply against the pack.

    Returns:
      valid_badges: badges referencing real evidence ids (unique, ordered)
      invalid_badges: badges pointing at nothing (hallucinated ids)
      unsupported_sentences: factual-looking sentences without 1+ valid badges
      cleaned_text: the answer with invalid badge refs stripped
    """
    valid: list[str] = []
    invalid: list[str] = []
    for badge in _BADGE_RE.findall(answer):
        if badge in [i.id for i in pack.items] and badge not in valid:
            valid.append(badge)
        elif badge not in invalid and badge not in valid:
            invalid.append(badge)

    unsupported: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(answer.strip()):
        if not sentence.strip() or _is_non_factual(sentence):
            continue
        refs = _BADGE_RE.findall(sentence)
        if any(r in valid for r in refs):
            continue
        unsupported.append(sentence.strip())

    cleaned = _BADGE_RE.sub(
        lambda m: m.group(0) if m.group(1) in valid else "", answer)
    return {
        "valid_badges": valid,
        "invalid_badges": invalid,
        "unsupported_sentences": unsupported,
        "cleaned_text": cleaned,
    }


async def build_pack(session: AsyncSession, settings: Settings) -> EvidencePack:
    """Today's audit entries + all memory items, numbered E1..E12."""
    items: list[EvidenceItem] = []
    entries = await audit_service.list_today(session)
    for entry in entries[:8]:
        items.append(EvidenceItem(
            f"E{len(items) + 1}",
            source=f"audit #{entry.id}",
            title=entry.action,
            text=(
                f"{entry.action} result={entry.result} "
                f"at {entry.ts.strftime('%H:%M:%S')} UTC"
                + (f" target={entry.target}" if entry.target else ""))))
    for item in await memory_service.list_items(session):
        public = memory_service.to_public(item, settings)
        items.append(EvidenceItem(
            f"E{len(items) + 1}", source=f"memory #{item.id}",
            title=item.kind, text=public["text"]))
    # camera verdicts (honest: counts/offline only, never identities)
    from ..models.cameras import Camera, CameraHealth

    cameras = (await session.execute(
        select(Camera).order_by(Camera.id.asc()))).scalars().all()
    for camera in cameras:
        health = await session.get(CameraHealth, camera.id)
        status = camera_service.effective_status(health)
        text = (
            f"Camera '{camera.name}' ({camera.kind}) is {status['status']}")
        if status.get("error"):
            text += f" — error: {status['error']}"
        items.append(EvidenceItem(
            f"E{len(items) + 1}", source=f"camera #{camera.id}",
            title=camera.name, text=text))
    return EvidencePack(items[:12])

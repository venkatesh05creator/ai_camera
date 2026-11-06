"""Encrypted memory service: create, edit, delete, export.

Encryption is AES-256-GCM via security.crypto. The key comes from
OWNERAI_BIOMETRIC_ENCRYPTION_KEY (fallback: the app secret) — the same
material TOTP uses. Plaintext never touches the DB or logs.
"""

from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..models.memory import MemoryItem
from ..models.user import utcnow
from ..security.crypto import CryptoError, decrypt_text, derive_key, encrypt_text


class MemoryError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def memory_key(settings: Settings) -> bytes:
    material = (settings.biometric_encryption_key.get_secret_value()
                or settings.secret_key.get_secret_value()
                or "aegis-dev-key")
    return derive_key(material)


def to_public(item: MemoryItem, settings: Settings) -> dict:
    try:
        text = decrypt_text(memory_key(settings), item.text_encrypted)
    except CryptoError as exc:
        raise MemoryError("decrypt_failed",
                          "stored memory cannot be decrypted", 500) from exc
    return {
        "id": item.id,
        "kind": item.kind,
        "text": text,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


async def list_items(session: AsyncSession) -> list[MemoryItem]:
    return list((await session.execute(
        select(MemoryItem).order_by(MemoryItem.id.asc()))).scalars().all())


async def create_item(session: AsyncSession, settings: Settings, *,
                      kind: str, text: str) -> MemoryItem:
    text = " ".join(text.split())  # normalize whitespace, never silently trim meaning
    if not text:
        raise MemoryError("empty", "memory text cannot be empty", 422)
    if len(text) > 2000:
        raise MemoryError("too_long", "memory text cannot exceed 2000 chars", 422)
    item = MemoryItem(kind=(kind or "fact")[:32],
                      text_encrypted=encrypt_text(memory_key(settings), text))
    session.add(item)
    await session.flush()
    return item


async def update_item(session: AsyncSession, settings: Settings,
                      item_id: int, *, text: str) -> MemoryItem:
    item = await session.get(MemoryItem, item_id)
    if item is None:
        raise MemoryError("not_found", "memory item not found", 404)
    text = " ".join(text.split())
    if not text:
        raise MemoryError("empty", "memory text cannot be empty", 422)
    item.text_encrypted = encrypt_text(memory_key(settings), text)
    item.updated_at = utcnow()
    await session.flush()
    return item


async def delete_item(session: AsyncSession, item_id: int) -> bool:
    item = await session.get(MemoryItem, item_id)
    if item is None:
        return False
    await session.execute(delete(MemoryItem).where(MemoryItem.id == item_id))
    await session.flush()
    return True


async def export_json(session: AsyncSession, settings: Settings) -> bytes:
    items = [to_public(item, settings) for item in await list_items(session)]
    payload = {"items": items, "exported_at": utcnow().isoformat(),
               "count": len(items)}
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")

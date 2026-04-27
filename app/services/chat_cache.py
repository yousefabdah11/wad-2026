from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.db.redis_client import get_redis_client


def _messages_key(*, user_id: int, chat_id: int) -> str:
    return f"cache:chat_messages:{user_id}:{chat_id}"


async def get_cached_message_payloads(*, user_id: int, chat_id: int) -> list[dict[str, Any]] | None:
    r = get_redis_client()
    if r is None:
        return None
    raw = await r.get(_messages_key(user_id=user_id, chat_id=chat_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, TypeError):
        return None
    return None


async def set_cached_message_payloads(
    *, user_id: int, chat_id: int, payloads: list[dict[str, Any]]
) -> None:
    r = get_redis_client()
    if r is None:
        return
    await r.set(
        _messages_key(user_id=user_id, chat_id=chat_id),
        json.dumps(payloads),
        ex=settings.chat_cache_ttl_seconds,
    )


async def invalidate_chat_messages(*, user_id: int, chat_id: int) -> None:
    r = get_redis_client()
    if r is None:
        return
    await r.delete(_messages_key(user_id=user_id, chat_id=chat_id))

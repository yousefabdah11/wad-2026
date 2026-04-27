from __future__ import annotations

import json
import secrets

from app.core.config import settings
from app.db.redis_client import get_redis_client


def _refresh_key(token: str) -> str:
    return f"refresh:{token}"


def refresh_ttl_seconds() -> int:
    return int(settings.refresh_token_ttl_days) * 86400


async def issue_refresh_token(user_id: int) -> str:
    r = get_redis_client()
    if r is None:
        raise RuntimeError("Redis is not connected")
    token = secrets.token_urlsafe(48)
    payload = json.dumps({"user_id": user_id})
    await r.set(_refresh_key(token), payload, ex=refresh_ttl_seconds())
    return token


async def consume_refresh_token(old_token: str | None) -> int | None:
    r = get_redis_client()
    if not old_token or r is None:
        return None
    key = _refresh_key(old_token)
    raw = await r.get(key)
    if not raw:
        return None
    await r.delete(key)
    try:
        data = json.loads(raw)
        return int(data["user_id"])
    except (KeyError, ValueError, TypeError):
        return None


async def peek_refresh_user_id(token: str | None) -> int | None:
    """Read user_id without deleting (used before rotation)."""
    r = get_redis_client()
    if not token or r is None:
        return None
    raw = await r.get(_refresh_key(token))
    if not raw:
        return None
    try:
        return int(json.loads(raw)["user_id"])
    except (KeyError, ValueError, TypeError):
        return None


async def revoke_refresh_token(token: str | None) -> None:
    r = get_redis_client()
    if not token or r is None:
        return
    await r.delete(_refresh_key(token))


async def store_oauth_state(state: str) -> None:
    r = get_redis_client()
    if r is None:
        raise RuntimeError("Redis is not connected")
    await r.set(f"oauth_state:{state}", "1", ex=600)


async def pop_oauth_state(state: str | None) -> bool:
    r = get_redis_client()
    if not state or r is None:
        return False
    key = f"oauth_state:{state}"
    ok = await r.get(key)
    if ok:
        await r.delete(key)
        return True
    return False

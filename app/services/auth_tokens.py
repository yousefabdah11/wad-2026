from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.user import User
from app.services import refresh_tokens


async def issue_tokens_for_user(user: User) -> tuple[str, str]:
    access = create_access_token(
        user_id=user.id,
        username=user.username,
        is_admin=user.is_admin,
    )
    refresh = await refresh_tokens.issue_refresh_token(user.id)
    return access, refresh


async def exchange_refresh_for_tokens(
    db: AsyncSession, *, old_refresh: str | None
) -> tuple[User, str, str] | None:
    """
    Validate an opaque refresh token in Redis, revoke it, and mint a new access + refresh pair.
    """
    user_id = await refresh_tokens.peek_refresh_user_id(old_refresh)
    if not user_id:
        return None
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        await refresh_tokens.revoke_refresh_token(old_refresh)
        return None
    await refresh_tokens.revoke_refresh_token(old_refresh)
    new_rt = await refresh_tokens.issue_refresh_token(user.id)
    new_at = create_access_token(
        user_id=user.id,
        username=user.username,
        is_admin=user.is_admin,
    )
    return user, new_at, new_rt

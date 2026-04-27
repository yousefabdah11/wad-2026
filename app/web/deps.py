from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ACCESS_TOKEN_COOKIE, PENDING_AUTH_COOKIES_STATE_KEY, REFRESH_TOKEN_COOKIE
from app.core.security import decode_access_token
from app.db.database import get_db
from app.models.user import User
from app.services.auth_tokens import exchange_refresh_for_tokens

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _load_user(db: AsyncSession, user_id: int) -> User | None:
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


async def resolve_session_user(request: Request, db: AsyncSession) -> User | None:
    token = None
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token:
        token = request.cookies.get(ACCESS_TOKEN_COOKIE)

    if token:
        payload = decode_access_token(token)
        if payload:
            try:
                user_id = int(payload["sub"])
            except (TypeError, ValueError):
                user_id = 0
            user = await _load_user(db, user_id)
            if user:
                return user

    rt = request.cookies.get(REFRESH_TOKEN_COOKIE)
    rotated = await exchange_refresh_for_tokens(db, old_refresh=rt)
    if not rotated:
        return None
    user, new_at, new_rt = rotated
    setattr(request.state, PENDING_AUTH_COOKIES_STATE_KEY, (new_at, new_rt))
    return user


async def get_optional_user(
    request: Request,
    db: DbSession,
) -> User | None:
    return await resolve_session_user(request, db)


async def get_current_user(
    request: Request,
    db: DbSession,
) -> User:
    user = await resolve_session_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user

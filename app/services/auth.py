from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services import refresh_tokens
from app.services.auth_tokens import exchange_refresh_for_tokens, issue_tokens_for_user
from app.services.users import create_password_user, verify_password_user


@dataclass(frozen=True)
class AuthTokenPair:
    user: User
    access_token: str
    refresh_token: str


class RegistrationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def issue_password_tokens(
    db: AsyncSession, *, username: str, password: str
) -> AuthTokenPair | None:
    user = await verify_password_user(db, username=username.strip(), password=password)
    if not user:
        return None
    access, refresh = await issue_tokens_for_user(user)
    return AuthTokenPair(user=user, access_token=access, refresh_token=refresh)


async def register_password_user(db: AsyncSession, *, username: str, password: str) -> User:
    username_clean = username.strip()
    if len(username_clean) < 2:
        raise RegistrationError("username")
    if len(password) < 6:
        raise RegistrationError("password")
    try:
        return await create_password_user(db, username=username_clean, password=password)
    except IntegrityError as exc:
        raise RegistrationError("taken") from exc


async def rotate_refresh_tokens(
    db: AsyncSession, *, refresh_token: str | None
) -> AuthTokenPair | None:
    rotated = await exchange_refresh_for_tokens(db, old_refresh=refresh_token)
    if not rotated:
        return None
    user, access, refresh = rotated
    return AuthTokenPair(user=user, access_token=access, refresh_token=refresh)


async def logout_refresh_token(refresh_token: str | None) -> None:
    await refresh_tokens.revoke_refresh_token(refresh_token)

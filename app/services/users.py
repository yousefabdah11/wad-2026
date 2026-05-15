from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password, verify_password
from app.models.oauth_account import OAuthAccount
from app.models.user import User


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def create_password_user(db: AsyncSession, *, username: str, password: str) -> User:
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise
    await db.refresh(user)
    return user


async def verify_password_user(db: AsyncSession, *, username: str, password: str) -> User | None:
    user = await get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


async def get_user_with_oauth_accounts(db: AsyncSession, *, user_id: int) -> User:
    stmt = select(User).options(selectinload(User.oauth_accounts)).where(User.id == user_id)
    return (await db.execute(stmt)).scalar_one()


async def get_oauth_account(
    db: AsyncSession, *, provider: str, provider_user_id: str
) -> OAuthAccount | None:
    q = select(OAuthAccount).where(
        OAuthAccount.provider == provider,
        OAuthAccount.provider_user_id == provider_user_id,
    )
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def ensure_github_user(
    db: AsyncSession,
    *,
    github_id: int,
    login: str,
    email: str | None,
) -> User:
    sid = str(github_id)
    existing = await get_oauth_account(db, provider="github", provider_user_id=sid)
    if existing:
        user = await db.get(User, existing.user_id)
        if user:
            existing.provider_login = login
            existing.provider_email = email
            await db.commit()
            return user

    login_clean = (login or "").strip() or f"gh_{sid}"
    candidates = [login_clean, f"{login_clean}_{sid}", f"gh_{sid}", f"github_{sid}"]
    username = ""
    seen: set[str] = set()
    for cand in candidates:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        if await get_user_by_username(db, cand) is None:
            username = cand
            break
    if not username:
        username = f"github_{sid}_{secrets.token_hex(3)}"

    user = User(username=username, password_hash=None)
    db.add(user)
    await db.flush()
    oauth = OAuthAccount(
        user_id=user.id,
        provider="github",
        provider_user_id=sid,
        provider_login=login,
        provider_email=email,
    )
    db.add(oauth)
    await db.commit()
    await db.refresh(user)
    return user

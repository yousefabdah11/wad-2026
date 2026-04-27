from __future__ import annotations

import datetime as dt
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt rejects secrets > 72 bytes; keep hashing aligned with verification.
_BCRYPT_MAX_BYTES = 72


def _bcrypt_clip(secret: str) -> str:
    raw = secret.encode("utf-8")
    if len(raw) <= _BCRYPT_MAX_BYTES:
        return secret
    return raw[:_BCRYPT_MAX_BYTES].decode("utf-8", errors="ignore")


def hash_password(password: str) -> str:
    return pwd_context.hash(_bcrypt_clip(password))


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    return pwd_context.verify(_bcrypt_clip(plain), hashed)


def create_access_token(*, user_id: int, username: str | None, is_admin: bool) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(seconds=settings.access_token_ttl_seconds)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username or "",
        "is_admin": is_admin,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None

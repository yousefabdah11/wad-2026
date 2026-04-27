from __future__ import annotations

from fastapi import Response

from app.core.config import settings
from app.core.constants import ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE
from app.services import refresh_tokens


def _cookie_secure() -> bool:
    return settings.app_base_url.lower().startswith("https://")


def set_auth_cookies(response: Response, *, access_token: str, refresh_token: str) -> None:
    sec = _cookie_secure()
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        httponly=True,
        max_age=settings.access_token_ttl_seconds,
        samesite="lax",
        secure=sec,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        httponly=True,
        max_age=refresh_tokens.refresh_ttl_seconds(),
        samesite="lax",
        secure=sec,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    sec = _cookie_secure()
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/", secure=sec)
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path="/", secure=sec)

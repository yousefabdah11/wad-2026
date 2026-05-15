from __future__ import annotations

import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services import refresh_tokens
from app.services.auth_tokens import issue_tokens_for_user
from app.services.github_api import exchange_github_code, fetch_github_profile
from app.services.users import ensure_github_user


@dataclass(frozen=True)
class OAuthTokenPair:
    access_token: str
    refresh_token: str


class GitHubOAuthConfigError(RuntimeError):
    pass


class GitHubOAuthStateError(ValueError):
    pass


class GitHubOAuthCallbackError(ValueError):
    pass


async def build_github_authorization_url() -> str:
    if not (settings.github_client_id and settings.github_client_secret):
        raise GitHubOAuthConfigError("github_config")

    state = secrets.token_urlsafe(32)
    await refresh_tokens.store_oauth_state(state)
    query = urlencode(
        {
            "client_id": settings.github_client_id,
            "redirect_uri": settings.github_redirect_uri,
            "scope": "user:email",
            "state": state,
            "allow_signup": "true",
        }
    )
    return f"https://github.com/login/oauth/authorize?{query}"


async def complete_github_oauth(
    db: AsyncSession, *, code: str | None, state: str | None
) -> OAuthTokenPair:
    if not code or not state:
        raise GitHubOAuthCallbackError("github")
    if not await refresh_tokens.pop_oauth_state(state):
        raise GitHubOAuthStateError("github_state")

    access = await exchange_github_code(code)
    profile = await fetch_github_profile(access)
    email = profile.get("resolved_email")
    user = await ensure_github_user(
        db,
        github_id=int(profile["id"]),
        login=str(profile.get("login") or ""),
        email=str(email) if email is not None else None,
    )
    access_token, refresh_token = await issue_tokens_for_user(user)
    return OAuthTokenPair(access_token=access_token, refresh_token=refresh_token)

from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.services import refresh_tokens
from app.services.auth_tokens import issue_tokens_for_user
from app.services.github_api import exchange_github_code, fetch_github_profile
from app.services.users import ensure_github_user
from app.web.cookies import set_auth_cookies
from app.web.deps import DbSession

router = APIRouter(tags=["oauth"])


@router.get("/auth/github/login")
async def github_login() -> RedirectResponse:
    if not (settings.github_client_id and settings.github_client_secret):
        return RedirectResponse("/login?error=github_config", status_code=303)
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
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{query}", status_code=303)


@router.get("/auth/github/callback")
async def github_callback(request: Request, db: DbSession) -> RedirectResponse:
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        return RedirectResponse("/login?error=github", status_code=303)
    if not await refresh_tokens.pop_oauth_state(state):
        return RedirectResponse("/login?error=github_state", status_code=303)
    try:
        access = await exchange_github_code(code)
        profile = await fetch_github_profile(access)
        github_id = int(profile["id"])
        login = str(profile.get("login") or "")
        email = profile.get("resolved_email")
        if email is not None:
            email = str(email)
        user = await ensure_github_user(
            db,
            github_id=github_id,
            login=login,
            email=email,
        )
        at, rt = await issue_tokens_for_user(user)
        resp = RedirectResponse("/chats", status_code=303)
        set_auth_cookies(resp, access_token=at, refresh_token=rt)
        return resp
    except Exception:
        logger.exception("GitHub OAuth callback failed")
        return RedirectResponse("/login?error=github", status_code=303)

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

from app.services import oauth as oauth_service
from app.web.cookies import set_auth_cookies
from app.web.deps import DbSession

router = APIRouter(tags=["oauth"])


@router.get("/auth/github/login")
async def github_login() -> RedirectResponse:
    try:
        authorization_url = await oauth_service.build_github_authorization_url()
    except oauth_service.GitHubOAuthConfigError:
        return RedirectResponse("/login?error=github_config", status_code=303)
    return RedirectResponse(authorization_url, status_code=303)


@router.get("/auth/github/callback")
async def github_callback(request: Request, db: DbSession) -> RedirectResponse:
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    try:
        tokens = await oauth_service.complete_github_oauth(db, code=code, state=state)
        resp = RedirectResponse("/chats", status_code=303)
        set_auth_cookies(
            resp,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
        )
        return resp
    except oauth_service.GitHubOAuthStateError:
        return RedirectResponse("/login?error=github_state", status_code=303)
    except oauth_service.GitHubOAuthCallbackError:
        return RedirectResponse("/login?error=github", status_code=303)
    except Exception:
        logger.exception("GitHub OAuth callback failed")
        return RedirectResponse("/login?error=github", status_code=303)

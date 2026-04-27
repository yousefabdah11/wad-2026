ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"
GITHUB_OAUTH_STATE_PREFIX = "oauth_state:"

# `request.state` key: tuple[str, str] of (access_token, refresh_token) to set on the outgoing response
# (FastAPI does not merge Depends(Response).set_cookie into HTMLResponse / RedirectResponse.)
PENDING_AUTH_COOKIES_STATE_KEY = "_pending_auth_cookies"

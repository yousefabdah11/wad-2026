from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.constants import PENDING_AUTH_COOKIES_STATE_KEY
from app.db.database import engine
from app.db.redis_client import connect_redis, disconnect_redis, get_redis_client
from app.routers import api, oauth_github, pages
from app.web.cookies import set_auth_cookies

app = FastAPI()


@app.middleware("http")
async def apply_pending_auth_cookies(request: Request, call_next):
    """
    After refresh-token rotation, auth cookies must be set on the *actual* response object.
    FastAPI does not merge cookies from Depends(Response) into HTMLResponse / RedirectResponse.
    """
    response = await call_next(request)
    pending = getattr(request.state, PENDING_AUTH_COOKIES_STATE_KEY, None)
    if isinstance(pending, tuple) and len(pending) == 2:
        access, refresh = pending
        set_auth_cookies(response, access_token=access, refresh_token=refresh)
        try:
            delattr(request.state, PENDING_AUTH_COOKIES_STATE_KEY)
        except AttributeError:
            pass
    return response


app.include_router(pages.router)
app.include_router(oauth_github.router)
app.include_router(api.router)


@app.on_event("startup")
async def on_startup() -> None:
    await connect_redis()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await disconnect_redis()


@app.get("/health")
async def health() -> JSONResponse:
    db_ok = False
    redis_ok = False

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    try:
        rc = get_redis_client()
        if rc is None:
            redis_ok = False
        else:
            await rc.ping()
            redis_ok = True
    except Exception:
        redis_ok = False

    status_code = 200 if (db_ok and redis_ok) else 503
    return JSONResponse(
        status_code=status_code,
        content={"ok": db_ok and redis_ok, "postgres": db_ok, "redis": redis_ok},
    )

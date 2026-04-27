from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.constants import REFRESH_TOKEN_COOKIE
from app.models.user import User
from app.services import refresh_tokens
from app.services.auth_tokens import issue_tokens_for_user
from app.services.chats import append_turn, create_chat, get_chat_for_user, list_chats_for_user
from app.services.chat_stream import sse_chat_message_events
from app.services.llm import generate_answer
from app.services.users import create_password_user, verify_password_user
from app.web.cookies import clear_auth_cookies, set_auth_cookies
from app.web.deps import DbSession, get_optional_user

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


def _safe_internal_path(next_url: str | None, *, default: str = "/chats") -> str:
    """Avoid open redirects: only same-origin relative paths starting with a single '/'."""
    if not next_url:
        return default
    u = next_url.strip()
    if not u.startswith("/") or u.startswith("//"):
        return default
    if "://" in u or "\\" in u:
        return default
    return u


@router.get("/", response_model=None)
async def home(user: Annotated[User | None, Depends(get_optional_user)]) -> RedirectResponse:
    if user:
        return RedirectResponse("/chats", status_code=303)
    return RedirectResponse("/login", status_code=303)


@router.get("/login", response_class=HTMLResponse, response_model=None)
async def login_page(
    request: Request,
    user: Annotated[User | None, Depends(get_optional_user)],
) -> HTMLResponse | RedirectResponse:
    if user:
        return RedirectResponse("/chats", status_code=303)
    err = request.query_params.get("error")
    return templates.TemplateResponse(
        request,
        "login.html",
        {"title": "Login", "error": err, "current_user": None},
    )


@router.post("/login", response_model=None)
async def login_submit(
    request: Request,
    db: DbSession,
    username: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse:
    user = await verify_password_user(db, username=username.strip(), password=password)
    if not user:
        return RedirectResponse("/login?error=credentials", status_code=303)
    access, refresh = await issue_tokens_for_user(user)
    nxt = _safe_internal_path(request.query_params.get("next"))
    resp = RedirectResponse(nxt, status_code=303)
    set_auth_cookies(resp, access_token=access, refresh_token=refresh)
    return resp


@router.get("/register", response_class=HTMLResponse, response_model=None)
async def register_page(
    request: Request,
    user: Annotated[User | None, Depends(get_optional_user)],
) -> HTMLResponse | RedirectResponse:
    if user:
        return RedirectResponse("/chats", status_code=303)
    err = request.query_params.get("error")
    return templates.TemplateResponse(
        request,
        "register.html",
        {"title": "Register", "error": err, "current_user": None},
    )


@router.post("/register", response_model=None)
async def register_submit(
    db: DbSession,
    username: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse:
    u = username.strip()
    if len(u) < 2:
        return RedirectResponse("/register?error=username", status_code=303)
    if len(password) < 6:
        return RedirectResponse("/register?error=password", status_code=303)
    try:
        await create_password_user(db, username=u, password=password)
    except IntegrityError:
        return RedirectResponse("/register?error=taken", status_code=303)
    return RedirectResponse("/login?error=created", status_code=303)


@router.post("/logout", response_model=None)
async def logout_post(request: Request) -> RedirectResponse:
    rt = request.cookies.get(REFRESH_TOKEN_COOKIE)
    await refresh_tokens.revoke_refresh_token(rt)
    resp = RedirectResponse("/login", status_code=303)
    clear_auth_cookies(resp)
    return resp


@router.get("/chats", response_class=HTMLResponse, response_model=None)
async def chats_page(
    request: Request,
    db: DbSession,
    user: Annotated[User | None, Depends(get_optional_user)],
) -> HTMLResponse | RedirectResponse:
    if not user:
        return RedirectResponse("/login?error=auth", status_code=303)
    chats = await list_chats_for_user(db, user_id=user.id)
    return templates.TemplateResponse(
        request,
        "chats.html",
        {"title": "Chats", "current_user": user, "chats": chats},
    )


@router.post("/chats", response_model=None)
async def chats_create(
    db: DbSession,
    user: Annotated[User | None, Depends(get_optional_user)],
    title: str = Form(""),
) -> RedirectResponse:
    if not user:
        return RedirectResponse("/login?error=auth", status_code=303)
    chat = await create_chat(db, user_id=user.id, title=title)
    return RedirectResponse(f"/chats/{chat.id}", status_code=303)


@router.get("/chats/{chat_id}", response_class=HTMLResponse, response_model=None)
async def chat_detail(
    request: Request,
    chat_id: int,
    db: DbSession,
    user: Annotated[User | None, Depends(get_optional_user)],
) -> HTMLResponse | RedirectResponse:
    if not user:
        return RedirectResponse("/login?error=auth", status_code=303)
    chat = await get_chat_for_user(db, chat_id=chat_id, user_id=user.id)
    if not chat:
        return RedirectResponse("/chats", status_code=303)
    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "title": chat.title or f"Chat {chat.id}",
            "current_user": user,
            "chat": chat,
            "messages": chat.messages,
        },
    )


@router.post("/chats/{chat_id}/messages", response_model=None)
async def chat_send_message(
    chat_id: int,
    db: DbSession,
    user: Annotated[User | None, Depends(get_optional_user)],
    content: str = Form(...),
) -> RedirectResponse:
    if not user:
        return RedirectResponse("/login?error=auth", status_code=303)
    chat = await get_chat_for_user(db, chat_id=chat_id, user_id=user.id)
    if not chat:
        return RedirectResponse("/chats", status_code=303)
    text = (content or "").strip()
    if not text:
        return RedirectResponse(f"/chats/{chat_id}", status_code=303)
    answer = generate_answer(text)
    await append_turn(db, chat=chat, user_text=text, assistant_text=answer)
    return RedirectResponse(f"/chats/{chat_id}", status_code=303)


@router.post("/chats/{chat_id}/messages/stream", response_model=None)
async def chat_send_message_stream(
    chat_id: int,
    db: DbSession,
    user: Annotated[User | None, Depends(get_optional_user)],
    content: str = Form(...),
) -> StreamingResponse:
    if not user:

        async def auth_err():
            yield b'data: {"error":"auth"}\n\n'

        return StreamingResponse(auth_err(), media_type="text/event-stream", status_code=401)

    async def events():
        async for chunk in sse_chat_message_events(
            db, user_id=user.id, chat_id=chat_id, user_text=content
        ):
            yield chunk

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/profile", response_class=HTMLResponse, response_model=None)
async def profile_page(
    request: Request,
    db: DbSession,
    user: Annotated[User | None, Depends(get_optional_user)],
) -> HTMLResponse | RedirectResponse:
    if not user:
        return RedirectResponse("/login?error=auth", status_code=303)
    stmt = select(User).options(selectinload(User.oauth_accounts)).where(User.id == user.id)
    full_user = (await db.execute(stmt)).scalar_one()
    return templates.TemplateResponse(
        request,
        "profile.html",
        {"title": "Profile", "current_user": full_user},
    )

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError

from app.core.constants import REFRESH_TOKEN_COOKIE
from app.models.chat import Chat
from app.models.message import Message
from app.models.user import User
from app.services import refresh_tokens
from app.services.auth_tokens import exchange_refresh_for_tokens, issue_tokens_for_user
from app.services import chat_cache
from app.services.chats import append_turn, create_chat, get_chat_for_user, list_chats_for_user
from app.services.chat_stream import sse_chat_message_events
from app.services.llm import generate_answer
from app.services.users import create_password_user, verify_password_user
from app.web.cookies import clear_auth_cookies, set_auth_cookies
from app.web.deps import DbSession, get_current_user

router = APIRouter(prefix="/api", tags=["api"])


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str | None
    is_admin: bool


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ChatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str | None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    role: str
    content: str


class ChatCreateBody(BaseModel):
    title: str | None = None


class ChatMessageBody(BaseModel):
    content: str


class LoginJsonBody(BaseModel):
    username: str
    password: str


class RegisterJsonBody(BaseModel):
    username: str
    password: str


async def _issue_tokens_or_none(
    db: DbSession, *, username: str, password: str
) -> tuple[User, str, str] | None:
    user = await verify_password_user(db, username=username.strip(), password=password)
    if not user:
        return None
    access, refresh = await issue_tokens_for_user(user)
    return user, access, refresh


@router.post("/auth/token", response_model=TokenOut)
async def auth_token_oauth2_form(
    db: DbSession,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenOut:
    """
    OAuth2-style password flow (same shape as `3-lesson/with-refresh`: POST form fields `username`, `password`).
    """
    out = await _issue_tokens_or_none(db, username=form_data.username, password=form_data.password)
    if not out:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    _, access, refresh = out
    return TokenOut(access_token=access, refresh_token=refresh)


@router.post("/auth/login", response_model=TokenOut)
async def auth_login_json(db: DbSession, body: LoginJsonBody) -> TokenOut:
    """JSON login returning bearer access + opaque refresh (stored in Redis)."""
    out = await _issue_tokens_or_none(db, username=body.username, password=body.password)
    if not out:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    _, access, refresh = out
    return TokenOut(access_token=access, refresh_token=refresh)


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def auth_register_json(db: DbSession, body: RegisterJsonBody) -> User:
    u = body.username.strip()
    if len(u) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username too short")
    if len(body.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password too short")
    try:
        user = await create_password_user(db, username=u, password=body.password)
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
    return user


@router.get("/me", response_model=UserOut)
async def api_me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@router.post("/auth/refresh", response_model=TokenOut)
async def api_refresh(
    request: Request,
    response: Response,
    db: DbSession,
    refresh_token: str | None = Query(
        default=None,
        description="Opaque refresh token from /auth/login; browser clients may rely on the HttpOnly cookie instead.",
    ),
) -> TokenOut:
    rt = refresh_token or request.cookies.get(REFRESH_TOKEN_COOKIE)
    rotated = await exchange_refresh_for_tokens(db, old_refresh=rt)
    if not rotated:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    _, new_at, new_rt = rotated
    set_auth_cookies(response, access_token=new_at, refresh_token=new_rt)
    return TokenOut(access_token=new_at, refresh_token=new_rt)


@router.post("/auth/logout")
async def api_logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Query(
        default=None,
        description="Opaque refresh token to revoke; falls back to cookie if omitted.",
    ),
) -> dict[str, bool]:
    rt = refresh_token or request.cookies.get(REFRESH_TOKEN_COOKIE)
    await refresh_tokens.revoke_refresh_token(rt)
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/chats", response_model=list[ChatOut])
async def api_list_chats(
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> list[Chat]:
    return await list_chats_for_user(db, user_id=user.id)


@router.post("/chats", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
async def api_create_chat(
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    body: ChatCreateBody,
) -> Chat:
    return await create_chat(db, user_id=user.id, title=body.title)


@router.get("/chats/{chat_id}", response_model=ChatOut)
async def api_get_chat(
    chat_id: int,
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> Chat:
    chat = await get_chat_for_user(db, chat_id=chat_id, user_id=user.id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return chat


@router.get("/chats/{chat_id}/messages", response_model=list[MessageOut])
async def api_list_messages(
    chat_id: int,
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> list[MessageOut]:
    cached = await chat_cache.get_cached_message_payloads(user_id=user.id, chat_id=chat_id)
    if cached is not None:
        return [MessageOut.model_validate(row) for row in cached]

    chat = await get_chat_for_user(db, chat_id=chat_id, user_id=user.id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    rows = [MessageOut.model_validate(m) for m in chat.messages]
    await chat_cache.set_cached_message_payloads(
        user_id=user.id,
        chat_id=chat_id,
        payloads=[r.model_dump() for r in rows],
    )
    return rows


@router.post("/chats/{chat_id}/messages", response_model=list[MessageOut])
async def api_post_message(
    chat_id: int,
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    body: ChatMessageBody,
) -> list[MessageOut]:
    chat = await get_chat_for_user(db, chat_id=chat_id, user_id=user.id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    text = body.content.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty message")
    answer = generate_answer(text)
    await append_turn(db, chat=chat, user_text=text, assistant_text=answer)
    chat2 = await get_chat_for_user(db, chat_id=chat_id, user_id=user.id)
    assert chat2 is not None
    return [MessageOut.model_validate(m) for m in chat2.messages]


@router.post("/chats/{chat_id}/messages/stream", response_model=None)
async def api_post_message_stream(
    chat_id: int,
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    body: ChatMessageBody,
) -> StreamingResponse:
    text = body.content.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty message")

    async def gen():
        async for chunk in sse_chat_message_events(
            db, user_id=user.id, chat_id=chat_id, user_text=body.content
        ):
            yield chunk

    return StreamingResponse(gen(), media_type="text/event-stream")

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict

from app.core.constants import REFRESH_TOKEN_COOKIE
from app.models.chat import Chat
from app.models.user import User
from app.services import auth as auth_service
from app.services.chats import (
    ChatNotFoundError,
    EmptyMessageError,
    append_user_turn_and_list_payloads,
    create_chat,
    get_chat_for_user,
    list_chats_for_user,
    list_message_payloads_for_user,
)
from app.services.chat_stream import sse_chat_message_events
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


_REGISTER_ERROR_DETAILS = {
    "username": "Username too short",
    "password": "Password too short",
    "taken": "Username already exists",
}


@router.post("/auth/token", response_model=TokenOut)
async def auth_token_oauth2_form(
    db: DbSession,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenOut:
    """
    OAuth2-style password flow (same shape as `3-lesson/with-refresh`: POST form fields `username`, `password`).
    """
    tokens = await auth_service.issue_password_tokens(
        db, username=form_data.username, password=form_data.password
    )
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/auth/login", response_model=TokenOut)
async def auth_login_json(db: DbSession, body: LoginJsonBody) -> TokenOut:
    """JSON login returning bearer access + opaque refresh (stored in Redis)."""
    tokens = await auth_service.issue_password_tokens(
        db, username=body.username, password=body.password
    )
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def auth_register_json(db: DbSession, body: RegisterJsonBody) -> User:
    try:
        return await auth_service.register_password_user(
            db, username=body.username, password=body.password
        )
    except auth_service.RegistrationError as exc:
        detail = _REGISTER_ERROR_DETAILS.get(exc.code, "Invalid registration")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc


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
    rotated = await auth_service.rotate_refresh_tokens(db, refresh_token=rt)
    if not rotated:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    set_auth_cookies(
        response,
        access_token=rotated.access_token,
        refresh_token=rotated.refresh_token,
    )
    return TokenOut(access_token=rotated.access_token, refresh_token=rotated.refresh_token)


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
    await auth_service.logout_refresh_token(rt)
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
) -> list[dict[str, Any]]:
    try:
        return await list_message_payloads_for_user(db, user_id=user.id, chat_id=chat_id)
    except ChatNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found") from exc


@router.post("/chats/{chat_id}/messages", response_model=list[MessageOut])
async def api_post_message(
    chat_id: int,
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    body: ChatMessageBody,
) -> list[dict[str, Any]]:
    try:
        return await append_user_turn_and_list_payloads(
            db, user_id=user.id, chat_id=chat_id, user_text=body.content
        )
    except ChatNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found") from exc
    except EmptyMessageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty message") from exc


@router.post("/chats/{chat_id}/messages/stream", response_model=None)
async def api_post_message_stream(
    chat_id: int,
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    body: ChatMessageBody,
) -> StreamingResponse:
    return StreamingResponse(
        sse_chat_message_events(db, user_id=user.id, chat_id=chat_id, user_text=body.content),
        media_type="text/event-stream",
    )

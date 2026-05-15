from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import Chat
from app.models.message import Message
from app.services import chat_cache
from app.services.llm import generate_answer


class ChatNotFoundError(ValueError):
    pass


class EmptyMessageError(ValueError):
    pass


def _message_payload(message: Message) -> dict[str, Any]:
    return {
        "id": message.id,
        "chat_id": message.chat_id,
        "role": message.role,
        "content": message.content,
    }


async def list_chats_for_user(db: AsyncSession, *, user_id: int) -> list[Chat]:
    stmt = (
        select(Chat)
        .where(Chat.user_id == user_id)
        .order_by(Chat.updated_at.desc(), Chat.id.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_chat(db: AsyncSession, *, user_id: int, title: str | None) -> Chat:
    chat = Chat(user_id=user_id, title=(title or "").strip() or "New chat")
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return chat


async def get_chat_for_user(db: AsyncSession, *, chat_id: int, user_id: int) -> Chat | None:
    stmt = (
        select(Chat)
        .options(selectinload(Chat.messages))
        .where(Chat.id == chat_id, Chat.user_id == user_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def append_turn(
    db: AsyncSession,
    *,
    chat: Chat,
    user_text: str,
    assistant_text: str,
) -> None:
    db.add(Message(chat_id=chat.id, role="user", content=user_text))
    db.add(Message(chat_id=chat.id, role="assistant", content=assistant_text))
    await db.commit()
    await chat_cache.invalidate_chat_messages(user_id=chat.user_id, chat_id=chat.id)


async def list_message_payloads_for_user(
    db: AsyncSession, *, user_id: int, chat_id: int
) -> list[dict[str, Any]]:
    cached = await chat_cache.get_cached_message_payloads(user_id=user_id, chat_id=chat_id)
    if cached is not None:
        return cached

    chat = await get_chat_for_user(db, chat_id=chat_id, user_id=user_id)
    if not chat:
        raise ChatNotFoundError("Chat not found")

    payloads = [_message_payload(message) for message in chat.messages]
    await chat_cache.set_cached_message_payloads(
        user_id=user_id,
        chat_id=chat_id,
        payloads=payloads,
    )
    return payloads


async def append_user_turn_and_list_payloads(
    db: AsyncSession, *, user_id: int, chat_id: int, user_text: str
) -> list[dict[str, Any]]:
    chat = await get_chat_for_user(db, chat_id=chat_id, user_id=user_id)
    if not chat:
        raise ChatNotFoundError("Chat not found")

    text = user_text.strip()
    if not text:
        raise EmptyMessageError("Empty message")

    answer = generate_answer(text)
    await append_turn(db, chat=chat, user_text=text, assistant_text=answer)
    return await list_message_payloads_for_user(db, user_id=user_id, chat_id=chat_id)


async def append_user_turn(
    db: AsyncSession, *, user_id: int, chat_id: int, user_text: str
) -> None:
    chat = await get_chat_for_user(db, chat_id=chat_id, user_id=user_id)
    if not chat:
        raise ChatNotFoundError("Chat not found")

    text = user_text.strip()
    if not text:
        raise EmptyMessageError("Empty message")

    await append_turn(db, chat=chat, user_text=text, assistant_text=generate_answer(text))


async def append_user_message(db: AsyncSession, *, chat: Chat, user_text: str) -> None:
    db.add(Message(chat_id=chat.id, role="user", content=user_text))
    await db.commit()


async def append_assistant_message(db: AsyncSession, *, chat_id: int, assistant_text: str) -> None:
    db.add(Message(chat_id=chat_id, role="assistant", content=assistant_text))
    await db.commit()
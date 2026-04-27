from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import Chat
from app.models.message import Message
from app.services import chat_cache


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


async def append_user_message(db: AsyncSession, *, chat: Chat, user_text: str) -> None:
    db.add(Message(chat_id=chat.id, role="user", content=user_text))
    await db.commit()


async def append_assistant_message(db: AsyncSession, *, chat_id: int, assistant_text: str) -> None:
    db.add(Message(chat_id=chat_id, role="assistant", content=assistant_text))
    await db.commit()
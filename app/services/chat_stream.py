from __future__ import annotations

import json
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import chat_cache
from app.services.chats import (
    append_assistant_message,
    append_user_message,
    get_chat_for_user,
)
from app.services.llm import generate_answer_tokens


async def sse_chat_message_events(
    db: AsyncSession,
    *,
    user_id: int,
    chat_id: int,
    user_text: str,
) -> AsyncIterator[bytes]:
    chat = await get_chat_for_user(db, chat_id=chat_id, user_id=user_id)
    if chat is None:
        yield f"data: {json.dumps({'error': 'not_found'})}\n\n".encode()
        return
    text = user_text.strip()
    if not text:
        yield f"data: {json.dumps({'error': 'empty'})}\n\n".encode()
        return

    await append_user_message(db, chat=chat, user_text=text)
    await chat_cache.invalidate_chat_messages(user_id=user_id, chat_id=chat_id)

    pieces: list[str] = []
    async for token in generate_answer_tokens(text):
        pieces.append(token)
        yield f"data: {json.dumps({'token': token})}\n\n".encode()

    assistant = "".join(pieces)
    await append_assistant_message(db, chat_id=chat.id, assistant_text=assistant)
    await chat_cache.invalidate_chat_messages(user_id=user_id, chat_id=chat_id)
    yield f"data: {json.dumps({'done': True})}\n\n".encode()

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_llama: Any | None = None
_llama_lock = threading.RLock()


def _reset_llama() -> None:
    global _llama
    with _llama_lock:
        if _llama is not None:
            closer = getattr(_llama, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:
                    pass
        _llama = None


def _validate_llm_for_completion(llm: Any) -> None:
    """llama-cpp can load encoder GGUFs; completion needs a causal LM checkpoint."""
    meta = getattr(llm, "metadata", None)
    if not isinstance(meta, dict):
        return
    arch = str(meta.get("general.architecture", "")).strip().lower()
    if arch == "bert":
        name = str(meta.get("general.name", "")).strip() or "this checkpoint"
        raise ValueError(
            f"GGUF is an encoder/embedding model ({name!r}, architecture=bert). "
            "Point LLM_MODEL_PATH at a causal instruct/chat GGUF (Llama, Mistral, Phi, Qwen, etc.)."
        )


def _create_llama() -> Any:
    from llama_cpp import Llama  # type: ignore

    kwargs: dict[str, Any] = {
        "model_path": settings.llm_model_path,
        "n_ctx": settings.llm_n_ctx,
        "n_threads": settings.llm_n_threads,
    }
    # Windows: memory-mapped weights can trigger odd llama.cpp / backend errors.
    if sys.platform == "win32":
        kwargs["use_mmap"] = False
    llm = Llama(**kwargs)
    try:
        _validate_llm_for_completion(llm)
    except BaseException:
        closer = getattr(llm, "close", None)
        if callable(closer):
            try:
                closer()
            except Exception:
                pass
        raise
    return llm


def _get_llama_locked() -> Any:
    """Must be called with _llama_lock held."""
    global _llama
    if _llama is None:
        _llama = _create_llama()
    return _llama


def generate_answer(prompt: str) -> str:
    """
    Best-effort local LLM answer generation (non-streaming, homework base.py style).

    If llama-cpp-python isn't installed/working, returns a stub response.
    """
    try:
        with _llama_lock:
            llm = _get_llama_locked()
            result = llm(
                prompt,
                max_tokens=settings.llm_max_tokens,
                stream=False,
            )
            text = result["choices"][0]["text"]
            return text.strip() or "(empty response)"
    except Exception as exc:
        logger.warning("LLM unavailable, using stub (install model + llama-cpp or check LLM_MODEL_PATH): %s", exc)
        _reset_llama()
        detail = str(exc).strip()
        if isinstance(exc, ValueError) and "encoder/embedding model" in detail:
            return f"{detail}\n\n(Your message: {prompt})"
        return f"(LLM not configured yet) You asked: {prompt}"


def _stream_chunks_sync(prompt: str) -> list[str]:
    """Run full streaming inference under one lock (used from a worker thread)."""
    with _llama_lock:
        llm = _get_llama_locked()
        stream = llm(prompt, max_tokens=settings.llm_max_tokens, stream=True)
        parts: list[str] = []
        for chunk in stream:
            piece = (chunk.get("choices") or [{}])[0].get("text") or ""
            if piece:
                parts.append(piece)
        return parts


async def generate_answer_tokens(prompt: str) -> AsyncIterator[str]:
    """
    Token/chunk stream (homework streaming.py style: chunk['choices'][0]['text']).

    Stub path yields small slices with a short async delay so the UI can visualize streaming.
    """
    try:
        parts = await asyncio.to_thread(_stream_chunks_sync, prompt)
        for piece in parts:
            yield piece
    except Exception as exc:
        logger.warning("LLM stream unavailable, using stub: %s", exc)
        _reset_llama()
        detail = str(exc).strip()
        if isinstance(exc, ValueError) and "encoder/embedding model" in detail:
            msg = f"{detail}\n\n(Your message: {prompt})"
        else:
            msg = f"(LLM not configured yet) You asked: {prompt}"
        step = 8
        for i in range(0, len(msg), step):
            await asyncio.sleep(0.04)
            yield msg[i : i + step]

# LLM integration plan

## Goal (homework requirement)

Provide a ChatGPT-like experience where user prompts produce assistant answers, and both sides are **persisted** per chat.

## Option A (recommended): Local GGUF model via `llama_cpp_python`

- Dependencies: `pip install -r requirements-llm.txt`
- Recommended Python: **3.12** on Windows for best wheel support.
- Model file: set `LLM_MODEL_PATH` (e.g. `./model.gguf`)
- Call pattern:
  - non-streaming: `Llama(...)(prompt, max_tokens=..., stream=False)`
  - optional streaming (bonus): `stream=True` and append chunks as they arrive

### Persistence approach

- On user submit:
  - insert `messages(role='user', content=...)`
  - call LLM
  - insert `messages(role='assistant', content=answer)`

Conversation replay is optional; the spec allows not re-sending full history.

## Option B: Stubbed local responder (fallback)

If local LLM dependencies are not installed yet, the app can run with a simple fallback responder that returns a deterministic placeholder answer. This keeps the rest of the homework (auth, persistence, UI, JWT/Redis) working.

### If the UI shows `(LLM not configured yet) You asked: …`

That string is **expected** until a real model runs. Check, in order:

1. **A GGUF file exists** on disk and `LLM_MODEL_PATH` in `.env` points to it (default `./model.gguf` relative to the process **current working directory** — usually the `project/` folder when you start Uvicorn). There is **no** model committed in this repo; you must download one (e.g. a small instruct model from Hugging Face in GGUF format).
2. **`llama_cpp_python` is installed** in the same environment as the app: `pip install -r requirements-llm.txt`. On **Python 3.14** wheels may be missing and the install can fail; use **Python 3.12** + a fresh venv if needed.
3. **Server logs** — after a code change, the app logs a **warning** with the underlying exception (missing file, import error, etc.) when falling back to the stub.

4. **`Memory is not initialized`** (from llama-cpp) — often happens when `LLM_MODEL_PATH` points at an **encoder / embedding** GGUF (logs may show `general.architecture = bert`, e.g. **gte-small**). Those files are **not** chat models. Download a **causal** instruct/chat GGUF (Llama, Mistral, Phi, Qwen, …) and update `LLM_MODEL_PATH`. On Windows the app sets **`use_mmap=False`** for weights; keep **`LLM_N_CTX`** reasonable for your model.

## Streaming (bonus, homework `streaming.py` pattern)

- Service: `app/services/llm.py` → `generate_answer_tokens()` async iterator (`stream=True`, chunk `choices[0]["text"]` when using llama-cpp).
- **API**: `POST /api/chats/{chat_id}/messages/stream` with JSON body `{ "content": "..." }` and `Authorization: Bearer …` → `text/event-stream` SSE frames: `{"token": "…"}`, then `{"done": true}`.
- **MVC**: `POST /chats/{id}/messages/stream` (form `content`) with session cookies; chat page **Send (stream)** uses `fetch` + `ReadableStream` to append tokens, then reloads when `done`.
- Persistence: user row is written first, assistant row after the stream completes (full assistant text).

## Redis cache-aside (bonus)

- `GET /api/chats/{id}/messages` caches the serialized message list under `cache:chat_messages:{user_id}:{chat_id}` with TTL `CHAT_CACHE_TTL_SECONDS` (see `.env.example`). Invalidated when new messages are appended (including streaming).


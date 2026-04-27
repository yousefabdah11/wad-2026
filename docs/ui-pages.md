# UI pages (server-rendered MVC)

This project uses server-rendered HTML pages (MVC). Controllers are FastAPI route handlers that render Jinja2 templates.

## Pages

### Public
- `GET /` → redirect to `/chats` if logged in, else `/login`
- `GET /login` → login form (username/password) + “Sign in with GitHub”
- `POST /login` → performs login; sets auth cookies; redirects to `/chats`
- `GET /register` → registration form
- `POST /register` → creates user; redirects to `/login` (or auto-login)
- `POST /logout` → clears cookies + revokes refresh session; redirects to `/login`

### Authenticated
- `GET /chats` → list chats + create chat form
- `POST /chats` → create chat (title optional) then redirect `/chats/{chat_id}`
- `GET /chats/{chat_id}` → chat view (messages + prompt input)
- `POST /chats/{chat_id}/messages` → submit user prompt, store message, call LLM, store assistant message, redirect back
- `GET /profile` → show user info + linked GitHub account (if any)

## How pages call services

- Controllers should stay thin:
  - read form input
  - call service functions (auth/chat/llm)
  - render template / redirect

## Auth on server-rendered pages

- Access token (JWT) is stored in an **HttpOnly cookie** (short TTL).
- Refresh token/session id is stored in an **HttpOnly cookie** (30 days).
- Protected pages validate access token; if expired, they attempt refresh via Redis and retry once.


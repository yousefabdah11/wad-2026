# Homework assignment — technical specification

This document describes the requirements for the homework project.

## Deadlines

- **Soft deadline:** 14.05.26  
- **Hard deadline:** 18.05.26

**Feedback and revisions:** if you receive feedback **before** the **soft** deadline, you may **submit corrections** to your work. If feedback arrives **after** the soft deadline, **no further corrections** based on that feedback are allowed.

The **hard** deadline is the final cutoff for acceptance of the submission.

## Required stack

- **Python**
- **FastAPI**
- **PostgreSQL** or **MongoDB** (choose one as the primary database)
- If you use **PostgreSQL**, schema changes **must** be applied via **database migrations**. **Alembic** is the **preferred** tool.
- **JWT** (access/refresh token flow)
- **GitHub OAuth**
- **Redis**

## Architecture

Pick **one** primary UI strategy. The required server-side pattern depends on it:


| UI approach                                                   | Required architecture                                                                                                        |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **SPA** (single-page application)                             | **MCS — Model–Controller–Service** (models, route handlers/controllers, services; thin routers, business logic in services). |
| **Server-rendered HTML** (templates generated on the backend) | **MVC — Model–View–Controller** (models, views/templates, controllers).                                                      |


If you use a **SPA**, it will be graded **only visually** (UI/UX), not for deep frontend code review.

## Core feature: LLM chat (ChatGPT-like)

Implement a chat experience similar in spirit to OpenAI ChatGPT:

- Users can **create chats** (conversation threads).
- Within each chat, **request/response history** is persisted.
- Inside a chat, users can **ask the LLM questions** and receive answers.

**Note:** You may omit storing a long **prompt history** in memory for the model (to save resources); minimal or stateless prompting per request is acceptable.

### Optional simplifications (allowed)

- Not re-sending the full conversation to the model on every turn is allowed.

## Authentication and security

- **Registration** with **login + password**; **login must be unique**.
- **Passwords** must be stored **hashed** in the database (e.g. bcrypt, argon2).
- **GitHub OAuth** sign-in must be supported alongside (or as an alternative to) password login.
- Expose an **HTTP API** protected with **JWT** (access tokens).
- **Refresh sessions** (refresh tokens or equivalent session records) must be stored in **Redis** with a **TTL of 30 days**.

## API

- REST (or similar) API built with **FastAPI**.
- Endpoints for auth, chats, messages, and LLM interaction as appropriate for your design.
- JWT validation on protected routes.

## Local LLM (recommended setup)

You may use `**llama-cpp-python`** (`from llama_cpp import Llama`) to run a **local GGUF model on CPU** without extra GPU resources.

- A sample model file (e.g. `model.gguf`) can be attached to the project for local inference.
- Minimal examples: `**base.py`** — non-streaming (`stream=False`, full text in `result["choices"][0]["text"]`); `**streaming.py**` — streaming (`stream=True`, chunks via `chunk["choices"][0]["text"]`).

---

## Starred (bonus) requirements

Items below are **optional** enhancements:

- **Visualize streaming LLM output** (tokens arriving incrementally in the UI or API consumer).
- **Auto-refresh** of the answer visualization (e.g. periodically reloading the page to refresh the chat view is acceptable).
- **Caching** of chat history (e.g. Redis or in-memory with clear invalidation rules) to reduce database load.

---

## Deliverables (typical expectations)

- Source code in a **Git** repository (e.g. GitHub).
- Instructions to run the app (dependencies, env vars, DB/Redis, OAuth app settings).
- Brief note on which frontend mode you chose and how your project follows **MCS** (SPA) or **MVC** (server HTML), plus how JWT + refresh tokens + Redis interact in your design.
- **Report in MD format (then I will make PDF version)**, submitted alongside the project, containing at minimum:
  - **API structure** — main routes, resource groups, and how clients use the API (can include a short overview or generated OpenAPI excerpt).
  - **Code structure** — how the codebase is organized (packages, layers, key modules) and short explanations of important parts.
  - **UI** — **screenshots** of the main screens so reviewers can see how the application looks in use.
  - **Database** — **schema / structure** of the database (for relational DBs: tables and relationships, or an ERD/diagram; for MongoDB: collections and main document shapes).


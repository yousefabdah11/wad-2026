# Setup on a new machine (full checklist)

This guide walks through everything needed to run the WAD homework project **locally without Docker**: Python, PostgreSQL, Redis, environment variables, database migrations, optional GitHub OAuth, and optional local LLM.

**Primary target:** Windows. Most steps are the same on macOS/Linux; only Postgres/Redis installation and shell paths differ.

---

## What you are installing

| Component | Role |
|-----------|------|
| **Python 3.12** (recommended) | App runtime and venv |
| **PostgreSQL** | Stores users, chats, messages, OAuth links |
| **Redis** | Refresh-token sessions (30-day TTL) and optional chat message cache |
| **`.env`** | Secrets and connection URLs (never commit real `.env`) |
| **Alembic** | Applies SQL schema migrations to Postgres |
| **Optional:** GitHub OAuth | “Sign in with GitHub” |
| **Optional:** `requirements-llm.txt` + GGUF | Local chat model via `llama-cpp-python` |

---

## 1. Install Python

1. Install **Python 3.12** from [python.org](https://www.python.org/downloads/) (use “Add python.exe to PATH”).
2. Open **PowerShell** and verify:

```powershell
py --version
py -m pip --version
```

Use **`py -3.12`** if multiple Python versions are installed.

**Why 3.12:** `llama-cpp-python` (optional LLM) ships prebuilt wheels for 3.12 on Windows. On very new Python (e.g. 3.14), the LLM install may fail or compile from source.

---

## 2. Install PostgreSQL

1. Install **PostgreSQL** with the official Windows installer (include **command line tools** / `psql`).
2. Ensure the **PostgreSQL** Windows service is running.
3. Create a database user and database (adjust names/passwords if you like; then match `DATABASE_URL` in `.env`).

Open **SQL Shell (psql)** or `psql` as a superuser (often `postgres`) and run:

```sql
CREATE USER wad_user WITH PASSWORD 'wad12oo2d';
CREATE DATABASE wad_app OWNER wad_user;
GRANT ALL PRIVILEGES ON DATABASE wad_app TO wad_user;
```

4. Confirm you can connect:

```powershell
psql -h localhost -U wad_user -d wad_app
```

(Enter `wad_password` when prompted.)

---

## 3. Install Redis (Redis-compatible on Windows)

Windows does not ship Redis as a built-in service. Pick one:

- **Memurai** (recommended): Redis-compatible, Windows service, default port **6379**.
- **WSL2 + Redis**: Install Redis inside Linux on WSL and expose `localhost:6379`.

After it is running, you should be able to reach **`localhost:6379`**. Memurai often includes a CLI; otherwise use any Redis client to run `PING` → `PONG`.

---

## 4. Get the project on the machine

- Clone the repo **or** copy the `project/` folder.
- All commands below assume your **current directory is the `project/` folder** (the one that contains `app/`, `alembic/`, `requirements.txt`, and `.env.example`).

```powershell
cd path\to\wad-2026-main\project
```

---

## 5. Create a virtual environment and install Python packages

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Optional — local LLM (only if you need the real GGUF model, not the stub):**

```powershell
pip install -r requirements-llm.txt
```

---

## 6. Configure `.env`

1. Copy the example file:

```powershell
copy .env.example .env
```

2. Edit **`.env`** and set at least the following.

### Core (required for a working app)

| Variable | Purpose | Example |
|----------|---------|---------|
| `APP_BASE_URL` | Public base URL of the app (cookies, redirects, OAuth) | `http://localhost:8000` |
| `DATABASE_URL` | **Async** SQLAlchemy URL for Postgres | `postgresql+asyncpg://wad_user:wad_password@localhost:5432/wad_app` |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` |
| `JWT_SECRET` | HS256 signing secret — **use a long random string** (32+ bytes). Short values cause PyJWT warnings. | Generate e.g. 64 hex chars |

### Token lifetimes (defaults in `.env.example` are fine)

| Variable | Typical value |
|----------|----------------|
| `JWT_ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_TTL_SECONDS` | `900` (15 minutes) |
| `REFRESH_TOKEN_TTL_DAYS` | `30` |

### GitHub OAuth (required only for “Login with GitHub”)

| Variable | Notes |
|----------|--------|
| `GITHUB_CLIENT_ID` | From GitHub OAuth App |
| `GITHUB_CLIENT_SECRET` | From GitHub OAuth App |
| `GITHUB_REDIRECT_URI` | Must match GitHub app callback, e.g. `http://localhost:8000/auth/github/callback` |

Full steps: **`docs/github-oauth-setup.md`**.

### Local LLM (optional)

| Variable | Notes |
|----------|--------|
| `LLM_MODEL_PATH` | Path to a **causal** instruct/chat **`.gguf`** file (not BERT/embedding). On Windows, an **absolute** path avoids cwd issues, e.g. `C:/projects/.../model.gguf` |
| `LLM_MAX_TOKENS`, `LLM_N_CTX`, `LLM_N_THREADS` | Tune for your machine; see **`docs/llm.md`** |

### Optional cache TTL

| Variable | Purpose |
|----------|---------|
| `CHAT_CACHE_TTL_SECONDS` | Redis cache-aside for `GET /api/chats/{id}/messages` |

---

## 7. Apply database migrations

With venv **activated** and **cwd = `project/`**:

```powershell
alembic upgrade head
```

This creates/updates tables in the database pointed to by `DATABASE_URL`.

---

## 8. Run the application

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open **`http://127.0.0.1:8000`** (or the host/port you chose).

---

## 9. Quick verification

- **Postgres:** app starts without DB connection errors; you can register/login (if not using GitHub only).
- **Redis:** refresh login / token rotation works; health or logs do not show Redis connection errors.
- **OAuth:** after configuring GitHub app + `.env`, use “Login with GitHub” and confirm callback URL matches exactly.

---

## 10. Troubleshooting

| Symptom | Things to check |
|---------|------------------|
| `could not connect to server` (Postgres) | Service running, host/port, `DATABASE_URL` user/password/database name, firewall |
| Redis connection refused | Memurai/WSL Redis running, `REDIS_URL` host/port/db index |
| `ModuleNotFoundError` / wrong packages | Venv activated, `pip install -r requirements.txt` run **inside** `project/` |
| Alembic errors | `DATABASE_URL` correct, user owns DB, run from `project/` |
| OAuth redirect mismatch | `GITHUB_REDIRECT_URI`, `APP_BASE_URL`, and GitHub OAuth App callback URL must align |
| LLM stub / “encoder/embedding model” | `LLM_MODEL_PATH` must point to a **causal** chat GGUF; see **`docs/llm.md`** |

---

## Other operating systems

- Use the same **Python venv** and **`pip install -r requirements.txt`** from the `project/` directory.
- Install **PostgreSQL** and **Redis** using your OS package manager or installers; keep `DATABASE_URL` and `REDIS_URL` in sync.
- Venv activation: macOS/Linux: `source .venv/bin/activate`

---

## Related docs

- **`docs/local-setup-windows.md`** — shorter Windows-focused notes (overlap with this file).
- **`docs/github-oauth-setup.md`** — GitHub OAuth App + scopes + env vars.
- **`docs/llm.md`** — local GGUF model, streaming, troubleshooting.

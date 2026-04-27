# Local setup (Windows, no Docker)

For a **single checklist from zero** (new laptop, all env vars explained, troubleshooting), use **`docs/setup-new-machine.md`**. This file is a shorter companion.

This project is designed to run **fully locally** on Windows (no Docker).

## 1) Install Python

- Install **Python 3.12** (from python.org)
- Verify in PowerShell:

```powershell
python --version
pip --version
```

If `python` is not found, use:

```powershell
py --version
```

### Important note about local LLM on Windows

If you are on a bleeding-edge Python version (for example, `py -0p` shows only Python 3.14),
`llama_cpp_python` may not have a prebuilt wheel and will try to compile from source.
For this homework, use **Python 3.12** for the local LLM path and recreate your venv if needed.

## 2) Install PostgreSQL (local)

1. Install PostgreSQL using the official Windows installer.
2. Ensure these are installed:
   - PostgreSQL Server
   - Command-line tools (`psql`)
   - (Optional) pgAdmin
3. Verify the service is running and `psql` works:

```powershell
psql --version
```

### Create DB + user

Open `psql` as a superuser and run:

```sql
CREATE USER wad_user WITH PASSWORD 'wad12oo2d';
CREATE DATABASE wad_app OWNER wad_user;
```

## 3) Install Redis locally (Windows)

Windows does not ship an official Redis service. Use one of these:

- **Recommended**: **Memurai** (Redis-compatible, Windows-native service)
- **Alternative**: run Redis via **WSL2** (still local, but requires WSL)

After installation, verify Redis is reachable (default port `6379`).

## 4) Create venv + install Python requirements

From `project/`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Optional: local LLM requirements (recommended on Python 3.12):

```powershell
pip install -r requirements-llm.txt
```

## 5) Configure env vars

Copy `.env.example` → `.env` and fill values.

## 6) Run migrations

```powershell
alembic upgrade head
```

## 7) Start app

```powershell
uvicorn app.main:app --reload
```


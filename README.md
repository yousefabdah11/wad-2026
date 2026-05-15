# WAD Homework Project (Local, No Docker)

This is the implementation project for the WAD homework.

## Local prerequisites (Windows)

- **Python 3.12 recommended** (3.11+ works for most deps, but local LLM installs are best on 3.12)
- **PostgreSQL** installed locally (server + `psql`)
- **Redis-compatible server** installed locally (recommended on Windows: **Memurai**)
- **draw.io Desktop** for the ERD (`ERD.drawio` → export `ERD.png`)

**New machine or first-time setup:** follow the full checklist in **`docs/setup-new-machine.md`** (Python, Postgres, Redis, `.env`, packages, migrations, optional OAuth/LLM).

## Quick start (after you install prerequisites)

1) Create virtual environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

2) Install dependencies

```powershell
pip install -r requirements.txt
```

Optional: local LLM dependencies (recommended only after confirming Python 3.12):

```powershell
pip install -r requirements-llm.txt
```

3) Configure environment variables

Copy `.env.example` to `.env` and fill values.

4) Run migrations

```powershell
alembic upgrade head
```

5) Start the server

```powershell
uvicorn app.main:app --reload
```


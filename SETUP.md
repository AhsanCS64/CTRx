# CTRx Backend Setup Guide

## Project structure
```
CTRx/
├─ backend/
│  ├─ app/
│  │  ├─ __init__.py
│  │  └─ main.py          # FastAPI entry point with health check
│  ├─ database.py          # SQLAlchemy engine, session, Base, FastAPI DB dependency
│  ├─ config.py            # Loads ``.env`` and exposes ``DATABASE_URL``
│  ├─ alembic/             # Alembic migration folder (empty for now)
│  │  ├─ env.py            # Alembic environment configuration
│  │  └─ versions/         # Future migration scripts go here
│  ├─ alembic.ini          # Alembic config file (points to ``alembic`` folder)
│  ├─ requirements.txt     # Pin‑exact versions of required packages
│  └─ .gitignore           # Includes ``.env`` and virtual‑env artefacts
└─ ...
```

## 1️⃣ Configure the database URL
Edit **`backend/.env`** and replace ``YOUR_PASSWORD`` with the password for the `ctrx_app` PostgreSQL role:
```
DATABASE_URL=postgresql+psycopg://ctrx_app:<your‑password>@localhost:5432/ctrx
```
The code loads this variable at runtime, so **do not hard‑code** credentials.

## 2️⃣ Install Python dependencies (offline)
Because the sandbox has no internet access, install the packages from local wheels or a pre‑downloaded bundle:
```powershell
# Activate the virtual environment
& "k:\Personal Projects\CTRx\backend\.venv\Scripts\activate"

# Then install from a local ``requirements.txt`` (the file is provided below)
pip install -r requirements.txt --no-index --find-links <path‑to‑offline‑wheels>
```
If you have internet on your machine, you can simply run:
```powershell
pip install -r requirements.txt
```
### `requirements.txt`
```
fastapi>=0.110.0
uvicorn[standard]>=0.30.0
python-dotenv>=1.0.0
SQLAlchemy>=2.0.0
psycopg[binary]>=3.2.0
alembic>=1.13.0
```
*(These versions are known to work with Python 3.13 in the current venv.)*

## 3️⃣ Initialise Alembic (once)
```powershell
# Initialise the Alembic environment (creates ``alembic`` folder and ``versions`` sub‑folder)
 alembic init backend/alembic
```
We have already committed a custom **`backend/alembic/env.py`** that
* imports the ``engine`` from ``backend.database``
* sets ``target_metadata = Base.metadata``
* reads the ``DATABASE_URL`` from the same ``.env`` file.
No migration is applied yet – the schema already exists.

## 4️⃣ Run the FastAPI server
```powershell
# From the project root
& "k:\Personal Projects\CTRx\backend\.venv\Scripts\python.exe" -m uvicorn backend.app.main:app \
    --host 127.0.0.1 --port 8000
```
Visit **`http://127.0.0.1:8000/health`** in a browser or with `curl`:
```powershell
curl http://127.0.0.1:8000/health
```
You should see a JSON payload similar to:
```json
{ "status": "ok", "db": 1 }
```
If the request fails, double‑check:
* The password in ``.env``
* That the PostgreSQL server is running and reachable on `localhost:5432`
* That the role `ctrx_app` has `CONNECT` rights to the `ctrx` database.

## 5️⃣ Future migrations
When you add SQLAlchemy model classes, run:
```powershell
alembic revision --autogenerate -m "Add <description>"
```
and then apply them with:
```powershell
alembic upgrade head
```
Because Alembic reads the same ``DATABASE_URL`` from ``.env``, the migrations will target the existing database without dropping anything.

---
### TL;DR checklist
1. **Edit `.env`** → set real password.
2. **Install deps** (`pip install -r requirements.txt`).
3. **Start server** (`python -m uvicorn backend.app.main:app`).
4. **Test** `/health` endpoint.
5. **Use Alembic** for any future schema changes.

Feel free to reach out if you hit any issues while installing the packages offline or connecting to PostgreSQL.

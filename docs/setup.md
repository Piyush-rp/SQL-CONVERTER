# Setup guide

## Option A - Docker Compose (fastest path to something running)

1. `cp .env.example .env` and fill in `SECRET_KEY` (generate one - see the
   comment in `.env.example`) plus at least one LLM provider API key.
2. `docker compose up --build`
3. Frontend: http://localhost:8080 - Backend API docs: http://localhost:8000/docs

The `backend` container runs Alembic migrations automatically on startup
(see the `CMD` in `backend/Dockerfile`), so the metadata database schema is
always current when the container comes up.

## Option B - Local development (no Docker)

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in SECRET_KEY and an LLM API key
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Run the test suite (no external services required - it uses SQLite):

```bash
pytest -v
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite's dev server proxies `/api` to `http://localhost:8000` (see
`vite.config.ts`), so the backend needs to already be running.

## Try it immediately with demo data

Don't have a database handy to test against? Generate one:

```bash
python3 scripts/seed_demo_data.py demo.sqlite
```

Then in the app, add a connection with engine `sqlite` and file path
pointing at `demo.sqlite` (use the absolute path if running the backend in
Docker - mount the file into the container, or run the backend locally
for a quick try).

## Connecting to SQL Server

`pyodbc` needs the Microsoft ODBC Driver installed on the machine/image
that's running the backend - Docker users get this automatically (the
`Dockerfile` installs it). For local (non-Docker) development against SQL
Server, follow Microsoft's install guide for "ODBC Driver 18 for SQL
Server" for your OS, then reference `driver=ODBC+Driver+18+for+SQL+Server`
in the connection's `extra_params` field (this is also the default the
connector falls back to - see `app/database/connector.py`).

PostgreSQL, MySQL and SQLite need no extra system packages - their drivers
(`psycopg2-binary`, `pymysql`) are pure-wheel/pip-installable.

## Optional: Redis (multi-instance scaling)

Set `REDIS_URL=redis://localhost:6379/0` (or your Redis host) to switch
the schema cache and rate limiter to Redis-backed implementations - see
`docs/scaling.md`. Leave it blank for a single instance; everything works
the same either way.

## Optional: Vault (secrets provider)

Set `SECRETS_PROVIDER=vault`, `VAULT_ADDR`, and `VAULT_TOKEN` to source
`SECRET_KEY`/`OPENAI_API_KEY`/`ANTHROPIC_API_KEY` from HashiCorp Vault's
KV v2 engine instead of `.env`. Store them as a flat map at
`VAULT_SECRET_PATH` (default `sqlcopilot`):

```bash
vault kv put secret/sqlcopilot \
  SECRET_KEY="..." \
  OPENAI_API_KEY="..." \
  ANTHROPIC_API_KEY="..."
```

## Creating your first user

The **first** account registered via `POST /api/v1/auth/register` is
automatically made an admin (see `app/auth/service.py`); every account
after that defaults to the least-privileged `viewer` role. Promote other
users to `admin`/`editor` directly in the `users` table until an admin UI
exists (see `docs/roadmap.md`).

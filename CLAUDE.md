# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

```bash
# Start everything (PostgreSQL + backend + frontend)
docker compose up --build

# Backend only (from backend/)
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend only (from frontend/)
npm run dev          # dev server with HMR
npm run build        # production build
```

No test suite exists. Verify changes via Swagger UI at http://localhost:8000/docs or the frontend at http://localhost:5173.

Default login: `admin` / `admin123` (superadmin).

## Architecture

Full-stack RBAC demo: **FastAPI** backend + **Vue 3** frontend + **PostgreSQL**, all orchestrated by Docker Compose.

### Backend (`backend/`)

- **Framework:** FastAPI with async SQLAlchemy 2.0 + asyncpg
- **Models:** 9 SQLAlchemy ORM tables in `app/models.py` — organizations, users, resources, roles, role_inclusions, role_resource_permissions, user_roles, org_exchanges, exchange_roles
- **Auth:** JWT bearer tokens (python-jose) + bcrypt passwords in `app/auth.py`. Token lifetime is 60 min (env-configurable).
- **Routers:** `app/routers/` — one module per domain: auth, organizations, users, resources, roles, resolve, exchanges
- **Permissions engine:** `app/permissions.py` — recursive CTEs for cycle detection, effective permission resolution (BIT_OR aggregation with foreign propagation limits), org subtree scoping, and exchange-based role access checks
- **Caching:** `app/cache.py` — in-memory dict cache for resolved permissions, keyed by user_id. Invalidated per-user on role assign/revoke, globally on role structure changes.
- **Migrations:** Alembic in `backend/alembic/`. Backend container runs `alembic upgrade head` on startup. Migrations handle schema only; seed data lives in `app/seed.py`.
- **Seed / Reset:** `app/seed.py` defines demo data with deterministic UUIDs (`uuid5`) and an `async reset(db)` function that truncates all tables and re-inserts. Exposed via `POST /reset` (30s rate limit, no auth). A daily background task auto-resets. `scripts/export_seed.py` exports current DB state into seed.py format.

### Frontend (`frontend/`)

- **Framework:** Vue 3 + Vite + Pinia + Vue Router + vue-i18n (en/uk)
- **State:** Pinia store in `src/stores/auth.js`; Axios instance with auto-injected bearer token in `src/stores/api.js`
- **Routing:** Auth guard redirects unauthenticated users to `/login`
- **Views:** Login, Orgs, Users, Roles, Resources, Resolve, Exchanges, RoleTree, Wiki

## Key Domain Concepts

- **Org hierarchy:** Organizations form a tree via `parent_id`. Superadmins see all; org_admins see their subtree; regular users see only their own org.
- **Role DAG:** Roles include other roles. Cycle detection uses a recursive CTE walk before any insertion. Self-inclusion is blocked by a DB check constraint.
- **@members roles:** Auto-created system roles (one per org, `is_org_role=true`). Cannot be edited or deleted. Users are auto-enrolled on creation.
- **Permission bitmasks:** Per resource-type encoding — document: read(1), write(2); video: view(1), comment(2), stream(4). Effective permissions are computed by BIT_OR across the role inclusion tree.
- **Org exchanges:** Bilateral agreements between two orgs enabling cross-org role sharing. Each side exposes specific roles to the partner. Exchanges use canonical pair ordering (`org_a_id < org_b_id`) to prevent duplicates. Closing an exchange cascades deletion of dependent cross-org role inclusions.
- **Foreign propagation limits:** A role's "vertical line" through org X is X's ancestors (up to root) plus X's descendants — but NOT X's siblings. Before any foreign crossing, roles follow inclusions freely. A foreign crossing occurs when moving to an org outside the current org's vertical line (i.e., lateral movement, typically via exchange). After crossing into org B, only B's vertical line is reachable — ancestors and descendants of B, but not siblings or other branches. This prevents transitive cross-org leaks while allowing vertical propagation. Implemented as a Python-side DAG walk in `permissions.py`.
- **Demo reset:** `POST /reset` truncates all tables and re-inserts seed data from `app/seed.py`. Rate-limited to once per 30 seconds. Also runs automatically every 24 hours via background task. Frontend has a "Reset Demo" button in the nav bar.

## Environment Variables (set in docker-compose.yml)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Async PostgreSQL connection string |
| `SECRET_KEY` | JWT signing key |
| `ALGORITHM` | JWT algorithm (HS256) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime |

## Creating a New Alembic Migration

```bash
cd backend
alembic revision --autogenerate -m "description"
```

The `env.py` reads `DATABASE_URL` from the environment and uses the sync driver equivalent for migrations.

## Fly.io Deployment

Live at **https://rbac-mock.fly.dev/**. Single Fly.io machine runs both frontend and backend:

```
Internet → nginx :8080
             ├─ /*        → Vue SPA static files (/usr/share/nginx/html)
             ├─ /api/*    → proxy to uvicorn :8000 (strips /api prefix)
             └─ /health   → proxy to uvicorn :8000/health
           uvicorn :8000 (FastAPI, 2 workers)
             └─ Fly Postgres (internal network)
```

### Deployment Files (project root)

| File | Purpose |
|---|---|
| `fly.toml` | Fly app config — region (`fra`), VM size (`shared-cpu-1x`, 512MB), health checks, auto-stop/start |
| `Dockerfile.fly` | Multi-stage build: Stage 1 builds Vue frontend (`node:20-slim`), Stage 2 runs Python + nginx + supervisor (`python:3.12-slim`) |
| `nginx.conf` | Serves SPA with history-mode fallback, proxies `/api/` to uvicorn with prefix stripping, caches hashed assets |
| `supervisord.conf` | Manages nginx and uvicorn as foreground processes (PID 1) |
| `start.sh` | Runs `alembic upgrade head`, then `exec supervisord` |

### DATABASE_URL Gotcha

Fly Postgres sets `DATABASE_URL` as `postgres://user:pass@host:5432/db?sslmode=disable`. This breaks asyncpg in two ways:

1. **Wrong scheme** — asyncpg needs `postgresql+asyncpg://`, not `postgres://`
2. **`sslmode` param** — asyncpg doesn't accept `sslmode`; use `ssl=disable` instead

After `fly postgres attach`, override the secret manually. The attach output prints the password — save it. If you missed it, reset it:

```bash
# Generate a new secure password
NEW_PW=$(openssl rand -base64 24)

# Reset the database user password
echo "ALTER USER rbac_mock WITH PASSWORD '${NEW_PW}';" \
  | fly postgres connect --app rbac-mock-db --database rbac_mock

# Set the corrected URL
fly secrets set DATABASE_URL="postgresql+asyncpg://rbac_mock:${NEW_PW}@top2.nearest.of.rbac-mock-db.internal:5432/rbac_mock?ssl=disable" --app rbac-mock
```

### Secrets vs Environment

| Variable | Location | Notes |
|---|---|---|
| `DATABASE_URL` | `fly secrets set` | Must use `postgresql+asyncpg://` scheme (see gotcha above) |
| `SECRET_KEY` | `fly secrets set` | Generate with `openssl rand -hex 32` |
| `ALGORITHM` | `fly.toml [env]` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `fly.toml [env]` | `60` |
| `CORS_ORIGINS` | `fly.toml [env]` (optional) | Comma-separated origins; defaults to localhost. Not needed in production (same-origin). |

### Routine Commands

```bash
fly deploy                  # Build and deploy
fly logs --app rbac-mock    # Stream logs (nginx + uvicorn + migrations)
fly status --app rbac-mock  # Machine state and health checks
fly ssh console --app rbac-mock  # Shell into the running machine
```

### Design Notes

- **Single machine** — frontend uses relative `/api` paths, so same-origin serving via nginx avoids all CORS complexity.
- **nginx + supervisord** — standard pattern for multi-process Fly containers. nginx handles static files and proxies; supervisord keeps both processes alive.
- **Auto-stop** — `min_machines_running = 0` allows scale-to-zero for cost savings. First request after idle has cold-start latency (~5s for boot + migrations check).
- **CORS origins** — configurable via `CORS_ORIGINS` env var in `backend/app/main.py`. Defaults to `http://localhost:5173,http://frontend:5173` for local dev. Not needed in production (same origin).

# RBAC Mockup

A demonstrative Role-Based Access Control system with:
- Hierarchical org structure
- Recursive role composition (DAG) with cycle detection
- Resource-type-based permission bitmasks
- Web UI for full CRUD + effective-permission resolution

## Quick Start

```bash
docker compose up --build
```

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Default credentials

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | superadmin |

## Permission Bitmask Encoding

| Resource Type | Bit 1 | Bit 2 | Bit 4 |
|--------------|-------|-------|-------|
| document | read | write | — |
| video | view | comment | stream |

## Fly.io Deployment

Live demo: **https://rbac-mock.fly.dev/**

### First-Time Setup

```bash
# 1. Install flyctl and authenticate
brew install flyctl
fly auth login

# 2. Create the app
fly apps create rbac-mock

# 3. Create a Fly Postgres database (unmanaged, single node)
fly postgres create --name rbac-mock-db --region fra \
  --vm-size shared-cpu-1x --initial-cluster-size 1 --volume-size 1

# 4. Attach the database to the app
fly postgres attach rbac-mock-db --app rbac-mock
```

> **Important: Fix DATABASE_URL.** The `fly postgres attach` command sets `DATABASE_URL` with a `postgres://` scheme and `?sslmode=disable`, but asyncpg requires `postgresql+asyncpg://` and rejects `sslmode`. You must override it manually.
>
> The `fly postgres attach` output prints the password — save it. If you missed it, reset the password:
>
> ```bash
> # Generate a new secure password
> NEW_PW=$(openssl rand -base64 24)
>
> # Reset the database user password
> echo "ALTER USER rbac_mock WITH PASSWORD '${NEW_PW}';" \
>   | fly postgres connect --app rbac-mock-db --database rbac_mock
>
> # Set the corrected URL (asyncpg-compatible scheme, ssl instead of sslmode)
> fly secrets set DATABASE_URL="postgresql+asyncpg://rbac_mock:${NEW_PW}@top2.nearest.of.rbac-mock-db.internal:5432/rbac_mock?ssl=disable" --app rbac-mock
> ```

```bash
# 5. Generate a secret key for JWT signing
fly secrets set SECRET_KEY="$(openssl rand -hex 32)" --app rbac-mock

# 6. Deploy
fly deploy
```

### Subsequent Deploys

```bash
fly deploy
```

### Useful Commands

```bash
fly logs --app rbac-mock      # Stream application logs
fly status --app rbac-mock    # Check machine state and health
fly open --app rbac-mock      # Open the app in your browser
```

## Verification Steps

1. `docker compose up` — all three services start clean
2. Login as `admin` / `admin123`
3. Create a child org → create user → mark as org_admin
4. Login as org_admin → create a role → assign `read` permission (bit=1) on a document resource
5. Create a second role with `write` permission (bit=2) → include it in the first role
6. Assign the first role to a user → hit `GET /resolve/user/{id}` → confirm bits = 3 (read|write)
7. Attempt to create a cycle: role A includes B, then B includes A → API returns 422
8. Superadmin-only endpoints (POST /orgs/) return 403 for non-superadmin users

## Project Structure

```
rbac-mock/
├── docker-compose.yml
├── fly.toml                    # Fly.io app configuration
├── Dockerfile.fly              # Production multi-stage build
├── nginx.conf                  # nginx: SPA serving + API proxy
├── supervisord.conf            # Process manager for nginx + uvicorn
├── start.sh                    # Entrypoint: migrations + supervisord
├── backend/                    # FastAPI + SQLAlchemy async + asyncpg
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/               # DB migrations + seed data
│   └── app/
│       ├── main.py            # FastAPI app + CORS
│       ├── database.py        # Async engine
│       ├── models.py          # SQLAlchemy ORM (7 tables)
│       ├── schemas.py         # Pydantic v2
│       ├── auth.py            # JWT + bcrypt
│       ├── cache.py           # In-memory permission cache
│       ├── permissions.py     # Cycle check, effective perms, admin scope
│       └── routers/           # auth, orgs, users, resources, roles, resolve, interactions
└── frontend/                  # Vue 3 + Vite + Pinia + vue-i18n
    ├── Dockerfile
    ├── src/
    │   ├── i18n.js            # Internationalization setup (en/uk)
    │   ├── locales/           # en.json, uk.json
    │   ├── stores/            # Pinia auth store + Axios instance
    │   ├── router/            # Vue Router with auth guard
    │   └── views/             # Login, Orgs, Users, Roles, Resources, Resolve,
    │                          # Interactions, RoleTree, Wiki
```

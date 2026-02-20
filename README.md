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
mock-rbms/
├── docker-compose.yml
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
│       ├── permissions.py     # Cycle check, effective perms, admin scope
│       └── routers/           # auth, orgs, users, resources, roles, resolve
└── frontend/                  # Vue 3 + Vite + Pinia
    ├── Dockerfile
    ├── src/
    │   ├── stores/            # Pinia auth store + Axios instance
    │   ├── router/            # Vue Router
    │   └── views/             # Login, Orgs, Users, Roles, Resources, Resolve
```

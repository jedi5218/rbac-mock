"""Demo seed data with deterministic UUIDs.

Provides a complete initial state for the RBAC demo and an async reset()
function that truncates all tables and re-inserts the seed data.
"""

import uuid

import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Fixed namespace for uuid5 — ensures stable, reproducible IDs.
NAMESPACE = uuid.UUID("e58ed763-928c-4155-bee9-fae2cee20735")


def _id(key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, key))


def _pw(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


# ── Organizations ────────────────────────────────────────────────────────────

ORGS = [
    {"id": _id("org:Root Corp"),  "name": "Root Corp",  "parent_id": None},
    {"id": _id("org:Division A"), "name": "Division A", "parent_id": _id("org:Root Corp")},
    {"id": _id("org:Team Alpha"), "name": "Team Alpha", "parent_id": _id("org:Division A")},
]

# ── Users ────────────────────────────────────────────────────────────────────

USERS = [
    {
        "id": _id("user:admin"),
        "username": "admin",
        "description": "Superadmin account",
        "password_hash": _pw("admin123"),
        "org_id": _id("org:Root Corp"),
        "is_superadmin": True,
        "is_org_admin": True,
    },
]

# ── Roles (including @members) ──────────────────────────────────────────────

ROLES = [
    # @members (auto-managed, one per org)
    {"id": _id("role:Root Corp/@members"),  "name": "@members", "org_id": _id("org:Root Corp"),  "is_org_role": True},
    {"id": _id("role:Division A/@members"), "name": "@members", "org_id": _id("org:Division A"), "is_org_role": True},
    {"id": _id("role:Team Alpha/@members"), "name": "@members", "org_id": _id("org:Team Alpha"), "is_org_role": True},
    # Custom roles
    {"id": _id("role:Root Corp/Reader"), "name": "Reader", "org_id": _id("org:Root Corp"), "is_org_role": False},
    {"id": _id("role:Root Corp/Writer"), "name": "Writer", "org_id": _id("org:Root Corp"), "is_org_role": False},
    {"id": _id("role:Division A/Viewer"), "name": "Viewer", "org_id": _id("org:Division A"), "is_org_role": False},
]

# ── Role inclusions ─────────────────────────────────────────────────────────

ROLE_INCLUSIONS = [
    # @members chain: child includes parent
    {"role_id": _id("role:Division A/@members"), "included_role_id": _id("role:Root Corp/@members")},
    {"role_id": _id("role:Team Alpha/@members"), "included_role_id": _id("role:Division A/@members")},
    # Writer includes Reader
    {"role_id": _id("role:Root Corp/Writer"), "included_role_id": _id("role:Root Corp/Reader")},
]

# ── Resources ────────────────────────────────────────────────────────────────

RESOURCES = [
    {"id": _id("res:Root Corp/Company Handbook"), "name": "Company Handbook", "resource_type": "document", "org_id": _id("org:Root Corp")},
    {"id": _id("res:Division A/Onboarding Video"), "name": "Onboarding Video", "resource_type": "video", "org_id": _id("org:Division A")},
]

# ── Role-resource permissions ───────────────────────────────────────────────

PERMISSIONS = [
    {"role_id": _id("role:Root Corp/Reader"), "resource_id": _id("res:Root Corp/Company Handbook"), "permission_bits": 1},
    {"role_id": _id("role:Root Corp/Writer"), "resource_id": _id("res:Root Corp/Company Handbook"), "permission_bits": 2},
    {"role_id": _id("role:Division A/Viewer"), "resource_id": _id("res:Division A/Onboarding Video"), "permission_bits": 5},
]

# ── User roles (including @members auto-assignments) ────────────────────────

USER_ROLES = [
    {"user_id": _id("user:admin"), "role_id": _id("role:Root Corp/@members")},
]

# ── Org exchanges ────────────────────────────────────────────────────────────

EXCHANGES: list[dict] = []

# ── Exchange roles ───────────────────────────────────────────────────────────

EXCHANGE_ROLES: list[dict] = []


# ── Reset function ───────────────────────────────────────────────────────────

_ALL_TABLES = [
    ("organizations", ORGS),
    ("users", USERS),
    ("roles", ROLES),
    ("role_inclusions", ROLE_INCLUSIONS),
    ("resources", RESOURCES),
    ("role_resource_permissions", PERMISSIONS),
    ("user_roles", USER_ROLES),
    ("org_exchanges", EXCHANGES),
    ("exchange_roles", EXCHANGE_ROLES),
]


async def reset(db: AsyncSession) -> None:
    """Truncate all tables and re-insert seed data."""
    await db.execute(text(
        "TRUNCATE organizations, users, resources, roles, "
        "role_inclusions, role_resource_permissions, user_roles, "
        "org_exchanges, exchange_roles CASCADE"
    ))

    for table, rows in _ALL_TABLES:
        if not rows:
            continue
        cols = list(rows[0].keys())
        col_list = ", ".join(cols)
        val_list = ", ".join(f":{c}" for c in cols)
        stmt = text(f"INSERT INTO {table} ({col_list}) VALUES ({val_list})")
        for row in rows:
            await db.execute(stmt, row)

    await db.commit()

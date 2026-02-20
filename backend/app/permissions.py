from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

# ── Bit-label maps ────────────────────────────────────────────────────────────

PERMISSION_LABELS = {
    "document": {1: "read", 2: "write"},
    "video": {1: "view", 2: "comment", 4: "stream"},
}


def decode_bits(resource_type: str, bits: int) -> list[str]:
    labels = PERMISSION_LABELS.get(resource_type, {})
    return [label for bit, label in sorted(labels.items()) if bits & bit]


# ── Cycle detection ───────────────────────────────────────────────────────────

async def check_inclusion_cycle(db: AsyncSession, role_id: str, new_included_id: str) -> None:
    """
    Raise HTTPException(422) if adding role_id → new_included_id would create a cycle.
    Strategy: walk downward from new_included_id; if role_id is reachable, it's a cycle.
    """
    sql = text("""
        WITH RECURSIVE reachable AS (
            SELECT included_role_id AS id
            FROM role_inclusions
            WHERE role_id = :new_included
            UNION
            SELECT ri.included_role_id
            FROM role_inclusions ri
            JOIN reachable r ON ri.role_id = r.id
        )
        SELECT 1 FROM reachable WHERE id = :role_id
        LIMIT 1
    """)
    result = await db.execute(sql, {"new_included": new_included_id, "role_id": role_id})
    if result.scalar() is not None:
        raise HTTPException(status_code=422, detail="Adding this inclusion would create a cycle in the role DAG")


# ── Effective permissions ─────────────────────────────────────────────────────

async def get_effective_permissions(db: AsyncSession, user_id: str) -> list[dict]:
    sql = text("""
        WITH RECURSIVE role_tree AS (
            SELECT role_id FROM user_roles WHERE user_id = :uid
            UNION
            SELECT ri.included_role_id
            FROM role_inclusions ri
            JOIN role_tree rt ON ri.role_id = rt.role_id
        )
        SELECT
            r.id          AS resource_id,
            r.name        AS resource_name,
            r.resource_type,
            BIT_OR(rrp.permission_bits) AS bits
        FROM role_tree rt
        JOIN role_resource_permissions rrp ON rrp.role_id = rt.role_id
        JOIN resources r ON r.id = rrp.resource_id
        GROUP BY r.id, r.name, r.resource_type
    """)
    result = await db.execute(sql, {"uid": user_id})
    rows = result.mappings().all()
    return [
        {
            "resource_id": str(row["resource_id"]),
            "resource_name": row["resource_name"],
            "resource_type": row["resource_type"],
            "permission_bits": row["bits"],
            "permission_labels": decode_bits(row["resource_type"], row["bits"]),
        }
        for row in rows
    ]


# ── Role inherited permissions ────────────────────────────────────────────────

async def get_role_inherited_permissions(db: AsyncSession, role_id: str) -> dict[str, int]:
    """
    Return {resource_id: bits} for permissions flowing from included roles only
    (not the role's own direct permissions).
    """
    sql = text("""
        WITH RECURSIVE role_tree AS (
            SELECT included_role_id AS role_id
            FROM role_inclusions
            WHERE role_id = :role_id
            UNION
            SELECT ri.included_role_id
            FROM role_inclusions ri
            JOIN role_tree rt ON ri.role_id = rt.role_id
        )
        SELECT rrp.resource_id, BIT_OR(rrp.permission_bits) AS bits
        FROM role_tree rt
        JOIN role_resource_permissions rrp ON rrp.role_id = rt.role_id
        GROUP BY rrp.resource_id
    """)
    result = await db.execute(sql, {"role_id": role_id})
    return {str(row[0]): row[1] for row in result.fetchall()}


# ── Org subtree helpers ───────────────────────────────────────────────────────

async def get_subtree_org_ids(db: AsyncSession, root_org_id: str) -> list[str]:
    """Return all org IDs in the subtree rooted at root_org_id (inclusive)."""
    sql = text("""
        WITH RECURSIVE subtree AS (
            SELECT id FROM organizations WHERE id = :root_org_id
            UNION
            SELECT o.id FROM organizations o JOIN subtree s ON o.parent_id = s.id
        )
        SELECT id FROM subtree
    """)
    result = await db.execute(sql, {"root_org_id": root_org_id})
    return [str(row[0]) for row in result.fetchall()]


async def visible_org_ids(db: AsyncSession, current_user) -> list[str] | None:
    """
    Returns the list of org IDs the current user can see/manage, or None meaning all
    (superadmin). Org admins see their subtree; regular users see only their own org.
    """
    if current_user.is_superadmin:
        return None
    if current_user.is_org_admin:
        return await get_subtree_org_ids(db, current_user.org_id)
    return [current_user.org_id]


# ── Admin scope check ─────────────────────────────────────────────────────────

async def org_in_subtree(db: AsyncSession, admin_org_id: str, target_org_id: str) -> bool:
    """Return True if target_org_id is within the subtree rooted at admin_org_id."""
    sql = text("""
        WITH RECURSIVE subtree AS (
            SELECT id FROM organizations WHERE id = :admin_org_id
            UNION
            SELECT o.id FROM organizations o JOIN subtree s ON o.parent_id = s.id
        )
        SELECT 1 FROM subtree WHERE id = :target_org_id LIMIT 1
    """)
    result = await db.execute(sql, {"admin_org_id": admin_org_id, "target_org_id": target_org_id})
    return result.scalar() is not None

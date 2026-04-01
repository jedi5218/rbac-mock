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
    """
    Resolve effective permissions with foreign-propagation limits.

    Once a cross-org boundary is crossed during role tree traversal, only roles
    from the crossed-into org's subtree may be followed. Further foreign
    inclusions are blocked. This prevents transitive cross-org sharing.
    """
    sql = text("""
        WITH RECURSIVE
        -- Pre-compute org descendant relationships
        org_descendants AS (
            SELECT id AS root_id, id AS desc_id FROM organizations
            UNION ALL
            SELECT od.root_id, o.id
            FROM organizations o
            JOIN org_descendants od ON o.parent_id = od.desc_id
        ),

        -- Walk the role inclusion tree with propagation tracking
        role_tree AS (
            -- Base: user's directly assigned roles (no boundary crossed)
            SELECT r.id AS role_id, r.org_id,
                   CAST(NULL AS TEXT) AS home_subtree_root
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            WHERE ur.user_id = :uid

            UNION ALL

            -- Recursive: follow inclusions with propagation limits
            SELECT r2.id, r2.org_id,
                CASE
                    -- Already crossed a boundary: keep the same home root
                    WHEN rt.home_subtree_root IS NOT NULL THEN rt.home_subtree_root
                    -- Same org: no crossing
                    WHEN r2.org_id = rt.org_id THEN NULL
                    -- Child org (in subtree): no crossing
                    WHEN EXISTS (
                        SELECT 1 FROM org_descendants
                        WHERE root_id = rt.org_id AND desc_id = r2.org_id
                    ) THEN NULL
                    -- Crossing into a foreign org: record as new home root
                    ELSE r2.org_id
                END
            FROM role_inclusions ri
            JOIN role_tree rt ON ri.role_id = rt.role_id
            JOIN roles r2 ON ri.included_role_id = r2.id
            WHERE
                -- No boundary crossed yet: allow any inclusion
                rt.home_subtree_root IS NULL
                -- Already crossed: only allow if included role is within home subtree
                OR EXISTS (
                    SELECT 1 FROM org_descendants
                    WHERE root_id = rt.home_subtree_root AND desc_id = r2.org_id
                )
        )
        SELECT
            res.id          AS resource_id,
            res.name        AS resource_name,
            res.resource_type,
            BIT_OR(rrp.permission_bits) AS bits
        FROM role_tree rt
        JOIN role_resource_permissions rrp ON rrp.role_id = rt.role_id
        JOIN resources res ON res.id = rrp.resource_id
        GROUP BY res.id, res.name, res.resource_type
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


# ── Org-role helper ───────────────────────────────────────────────────────────

async def get_org_role(db: AsyncSession, org_id: str):
    """Return the auto-created @members role for an org, or None."""
    from sqlalchemy import select
    from app.models import Role
    result = await db.execute(
        select(Role).where(Role.org_id == org_id, Role.is_org_role == True)
    )
    return result.scalar_one_or_none()


# ── Exchange helpers ──────────────────────────────────────────────────────────

async def is_role_exposed_to_org(db: AsyncSession, role_id: str, admin_org_id: str) -> bool:
    """Check if a role is exposed through any exchange to any org in admin's subtree."""
    sql = text("""
        WITH RECURSIVE subtree AS (
            SELECT id FROM organizations WHERE id = :admin_org_id
            UNION
            SELECT o.id FROM organizations o JOIN subtree s ON o.parent_id = s.id
        )
        SELECT 1
        FROM exchange_roles er
        JOIN org_exchanges ex ON ex.id = er.exchange_id
        JOIN roles r ON r.id = er.role_id
        WHERE er.role_id = :role_id
          AND (
              (r.org_id = ex.org_a_id AND ex.org_b_id IN (SELECT id FROM subtree))
              OR
              (r.org_id = ex.org_b_id AND ex.org_a_id IN (SELECT id FROM subtree))
          )
        LIMIT 1
    """)
    result = await db.execute(sql, {"role_id": role_id, "admin_org_id": admin_org_id})
    return result.scalar() is not None


async def get_exchanged_role_ids(db: AsyncSession, admin_org_id: str) -> list[str]:
    """Return IDs of roles exposed to any org in the admin's subtree via exchanges."""
    sql = text("""
        WITH RECURSIVE subtree AS (
            SELECT id FROM organizations WHERE id = :admin_org_id
            UNION
            SELECT o.id FROM organizations o JOIN subtree s ON o.parent_id = s.id
        )
        SELECT DISTINCT er.role_id
        FROM exchange_roles er
        JOIN org_exchanges ex ON ex.id = er.exchange_id
        JOIN roles r ON r.id = er.role_id
        WHERE (r.org_id = ex.org_a_id AND ex.org_b_id IN (SELECT id FROM subtree))
           OR (r.org_id = ex.org_b_id AND ex.org_a_id IN (SELECT id FROM subtree))
    """)
    result = await db.execute(sql, {"admin_org_id": admin_org_id})
    return [str(row[0]) for row in result.fetchall()]



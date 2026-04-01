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


# ── Cross-org interactions ─────────────────────────────────────────────────────

async def get_interactions(db: AsyncSession, org_ids: list[str]) -> dict[str, dict]:
    """
    For each org in org_ids, find cross-org role interactions, excluding
    ancestor/descendant org relationships (intra-hierarchy sharing is expected).

    Returns:  {this_org_id: {foreign_org_id: {"foreign_org_name": str, "roles": [...]}}}
    """
    if not org_ids:
        return {}

    sql = text("""
        WITH RECURSIVE
        -- Ancestors of each visible org (walk up)
        ancestors AS (
            SELECT id AS org_id, parent_id AS related_id
            FROM   organizations
            WHERE  id = ANY(:org_ids) AND parent_id IS NOT NULL
            UNION
            SELECT a.org_id, o.parent_id
            FROM   organizations o
            JOIN   ancestors a ON o.id = a.related_id
            WHERE  o.parent_id IS NOT NULL
        ),
        -- Descendants of each visible org (walk down)
        descendants AS (
            SELECT parent_id AS org_id, id AS related_id
            FROM   organizations
            WHERE  parent_id = ANY(:org_ids)
            UNION
            SELECT d.org_id, o.id
            FROM   organizations o
            JOIN   descendants d ON o.parent_id = d.related_id
        ),
        -- Self entries (each org is related to itself)
        self_rel AS (
            SELECT id AS org_id, id AS related_id
            FROM   organizations WHERE id = ANY(:org_ids)
        ),
        -- Union of all intra-hierarchy org pairs to exclude
        excluded AS (
            SELECT org_id, related_id FROM ancestors
            UNION
            SELECT org_id, related_id FROM descendants
            UNION
            SELECT org_id, related_id FROM self_rel
        ),
        -- Cross-org role inclusions from two directions
        raw AS (
            -- Our org's role INCLUDES foreign org's role
            SELECT r1.org_id AS this_org,
                   r2.org_id AS foreign_org,
                   r1.id     AS this_role_id,
                   r1.name   AS this_role_name,
                   r2.id     AS foreign_role_id,
                   r2.name   AS foreign_role_name,
                   'includes'::text AS relation
            FROM   role_inclusions ri
            JOIN   roles r1 ON ri.role_id          = r1.id
            JOIN   roles r2 ON ri.included_role_id = r2.id
            WHERE  r1.org_id = ANY(:org_ids)
              AND  r1.org_id != r2.org_id

            UNION ALL

            -- Our org's role IS INCLUDED BY foreign org's role
            SELECT r1.org_id,
                   r2.org_id,
                   r1.id, r1.name,
                   r2.id, r2.name,
                   'included_by'::text
            FROM   role_inclusions ri
            JOIN   roles r1 ON ri.included_role_id = r1.id
            JOIN   roles r2 ON ri.role_id          = r2.id
            WHERE  r1.org_id = ANY(:org_ids)
              AND  r1.org_id != r2.org_id
        )
        SELECT raw.*,
               o_foreign.name AS foreign_org_name
        FROM   raw
        JOIN   organizations o_foreign ON o_foreign.id = raw.foreign_org
        WHERE  NOT EXISTS (
            SELECT 1 FROM excluded e
            WHERE  e.org_id = raw.this_org AND e.related_id = raw.foreign_org
        )
        ORDER BY raw.this_org, raw.foreign_org, raw.this_role_name
    """)

    result = await db.execute(sql, {"org_ids": org_ids})
    rows = result.mappings().all()

    # Group: this_org → foreign_org → list of role links
    out: dict[str, dict] = {}
    for row in rows:
        this_org    = str(row["this_org"])
        foreign_org = str(row["foreign_org"])
        out.setdefault(this_org, {})
        out[this_org].setdefault(foreign_org, {
            "foreign_org_id":   foreign_org,
            "foreign_org_name": row["foreign_org_name"],
            "roles": [],
        })
        out[this_org][foreign_org]["roles"].append({
            "this_role_id":    str(row["this_role_id"]),
            "this_role_name":  row["this_role_name"],
            "foreign_role_id": str(row["foreign_role_id"]),
            "foreign_role_name": row["foreign_role_name"],
            "relation":        row["relation"],
        })
    return out

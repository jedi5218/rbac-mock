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

    Walks the role inclusion DAG in Python to avoid heavy recursive CTEs
    that can OOM small Postgres instances.

    Propagation rule: before any foreign crossing, roles follow inclusions
    freely. A "vertical line" through org X is defined as X's ancestors
    (up to root) plus X's descendants — but NOT siblings (other children
    of X's parent). A foreign crossing occurs when moving to an org outside
    the current org's vertical line. After a crossing into org B, the role
    may only continue along B's vertical line: B's ancestors and descendants,
    but not B's siblings or other branches. This prevents lateral leaks
    (e.g., A↔B exchange won't leak to D via B1↔D if B1 is a child of B).
    """
    # 1. Fetch all org parent relationships
    org_rows = (await db.execute(text(
        "SELECT id::text, parent_id::text FROM organizations"
    ))).fetchall()
    parent_of: dict[str, str | None] = {}
    children_of: dict[str | None, list[str]] = {}
    for oid, pid in org_rows:
        parent_of[oid] = pid
        children_of.setdefault(pid, []).append(oid)

    # ancestors_of[org] = {org, parent, grandparent, ...}
    ancestors_of: dict[str, set[str]] = {}
    def _build_ancestors(oid: str) -> set[str]:
        if oid in ancestors_of:
            return ancestors_of[oid]
        s = {oid}
        pid = parent_of.get(oid)
        if pid is not None and pid in parent_of:
            s |= _build_ancestors(pid)
        ancestors_of[oid] = s
        return s

    # subtree_of[org] = {org, children, grandchildren, ...}
    subtree_of: dict[str, set[str]] = {}
    def _build_subtree(oid: str) -> set[str]:
        if oid in subtree_of:
            return subtree_of[oid]
        s = {oid}
        for child in children_of.get(oid, []):
            s |= _build_subtree(child)
        subtree_of[oid] = s
        return s

    for oid, _ in org_rows:
        _build_ancestors(oid)
        _build_subtree(oid)

    # vertical_line_of[org] = ancestors ∪ descendants (no siblings)
    vertical_line_of: dict[str, set[str]] = {}
    for oid in parent_of:
        vertical_line_of[oid] = ancestors_of[oid] | subtree_of[oid]

    # 2. Fetch role org mappings and inclusion edges
    role_org: dict[str, str] = {}
    for row in (await db.execute(text("SELECT id::text, org_id::text FROM roles"))).fetchall():
        role_org[row[0]] = row[1]

    inclusions: dict[str, list[str]] = {}  # parent_role -> [included_role, ...]
    for row in (await db.execute(text(
        "SELECT role_id::text, included_role_id::text FROM role_inclusions"
    ))).fetchall():
        inclusions.setdefault(row[0], []).append(row[1])

    # 3. Fetch user's directly assigned roles
    user_role_rows = (await db.execute(
        text("SELECT role_id::text FROM user_roles WHERE user_id = :uid"),
        {"uid": user_id},
    )).fetchall()

    # 4. Walk the DAG with propagation tracking
    #    crossed_into: the org we crossed into via a foreign boundary, or None.
    #    After crossing into org B, only B's vertical line is reachable.
    collected_roles: set[str] = set()
    queue: list[tuple[str, str | None]] = []
    for (rid,) in user_role_rows:
        queue.append((rid, None))

    visited: set[tuple[str, str | None]] = set()
    while queue:
        role_id, crossed_into = queue.pop()
        state = (role_id, crossed_into)
        if state in visited:
            continue
        visited.add(state)
        collected_roles.add(role_id)

        cur_org = role_org.get(role_id)
        if not cur_org:
            continue
        for child_id in inclusions.get(role_id, []):
            child_org = role_org.get(child_id)
            if not child_org:
                continue

            if crossed_into is not None:
                # Already crossed — only allow within crossed_into's vertical line
                if child_org not in vertical_line_of.get(crossed_into, set()):
                    continue
                new_crossed = crossed_into
            else:
                # No crossing yet — check if this is a vertical move
                if child_org in vertical_line_of.get(cur_org, set()):
                    new_crossed = None
                else:
                    new_crossed = child_org  # lateral move = foreign crossing

            queue.append((child_id, new_crossed))

    if not collected_roles:
        return []

    # 5. Fetch permissions for collected roles
    placeholders = ", ".join(f":r{i}" for i in range(len(collected_roles)))
    params = {f"r{i}": rid for i, rid in enumerate(collected_roles)}
    result = await db.execute(text(f"""
        SELECT res.id, res.name, res.resource_type,
               BIT_OR(rrp.permission_bits) AS bits
        FROM role_resource_permissions rrp
        JOIN resources res ON res.id = rrp.resource_id
        WHERE rrp.role_id::text IN ({placeholders})
        GROUP BY res.id, res.name, res.resource_type
    """), params)
    rows = result.mappings().all()
    return [
        {
            "resource_id": str(row["id"]),
            "resource_name": row["name"],
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



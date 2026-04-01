from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, Organization, Role, UserRole, RoleInclusion
from app.schemas import UserCreate, UserUpdate, UserOut, RoleOut, RoleTreeResponse, RoleTreeNode
from app.auth import get_current_user, require_superadmin, require_admin, hash_password
from app.permissions import org_in_subtree, get_org_role, get_subtree_org_ids
import app.cache as cache

router = APIRouter(prefix="/users", tags=["users"])


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _sync_org_role(db: AsyncSession, user_id: str, old_org_id: str | None, new_org_id: str) -> None:
    """Move a user from one org's @members role to another's."""
    if old_org_id and old_org_id != new_org_id:
        old_role = await get_org_role(db, old_org_id)
        if old_role:
            ur = await db.get(UserRole, (user_id, old_role.id))
            if ur:
                await db.delete(ur)

    if old_org_id != new_org_id or old_org_id is None:
        new_role = await get_org_role(db, new_org_id)
        if new_role:
            existing = await db.get(UserRole, (user_id, new_role.id))
            if not existing:
                db.add(UserRole(user_id=user_id, role_id=new_role.id))


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.is_superadmin:
        result = await db.execute(select(User))
        return result.scalars().all()
    if current_user.is_org_admin:
        all_orgs = (await db.execute(select(Organization))).scalars().all()
        visible = [o.id for o in all_orgs if await org_in_subtree(db, current_user.org_id, o.id)]
        result = await db.execute(select(User).where(User.org_id.in_(visible)))
        return result.scalars().all()
    return [current_user]


@router.post("/", response_model=UserOut, status_code=201)
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_superadmin)):
    org = await db.get(Organization, body.org_id)
    if not org:
        raise HTTPException(404, "Org not found")
    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        org_id=body.org_id,
        is_superadmin=body.is_superadmin,
        is_org_admin=body.is_org_admin,
    )
    db.add(user)
    await db.flush()
    # Auto-enrol in org's @members role
    await _sync_org_role(db, user.id, None, body.org_id)
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    is_self = current_user.id == user_id
    is_superadmin = current_user.is_superadmin
    is_scoped_admin = (
        current_user.is_org_admin
        and await org_in_subtree(db, current_user.org_id, user.org_id)
    )

    if not (is_self or is_superadmin or is_scoped_admin):
        raise HTTPException(403, "Forbidden")

    if body.username is not None:
        user.username = body.username
    if body.email is not None:
        user.email = body.email
    if body.password is not None:
        user.password_hash = hash_password(body.password)

    if is_superadmin:
        if body.org_id is not None and body.org_id != user.org_id:
            new_org = await db.get(Organization, body.org_id)
            if not new_org:
                raise HTTPException(404, "Org not found")
            old_org_id = user.org_id
            user.org_id = body.org_id
            await _sync_org_role(db, user_id, old_org_id, body.org_id)
        if body.is_superadmin is not None:
            user.is_superadmin = body.is_superadmin
        if body.is_org_admin is not None:
            user.is_org_admin = body.is_org_admin
    elif is_scoped_admin:
        if body.is_org_admin is not None:
            user.is_org_admin = body.is_org_admin

    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id == user_id:
        raise HTTPException(403, "Cannot delete yourself")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    is_superadmin = current_user.is_superadmin
    is_scoped_admin = (
        current_user.is_org_admin
        and await org_in_subtree(db, current_user.org_id, user.org_id)
    )

    if not (is_superadmin or is_scoped_admin):
        raise HTTPException(403, "Forbidden")
    if is_scoped_admin and user.is_superadmin:
        raise HTTPException(403, "Cannot delete a superadmin")

    await db.delete(user)
    await db.commit()
    cache.invalidate_user(user_id)


@router.get("/{user_id}/role-tree", response_model=RoleTreeResponse)
async def get_role_tree(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")

    if not current_user.is_superadmin:
        if current_user.is_org_admin:
            if not await org_in_subtree(db, current_user.org_id, target.org_id):
                raise HTTPException(403, "User is outside your org subtree")
        elif current_user.id != user_id:
            raise HTTPException(403, "You can only view your own role tree")

    # Load all roles and inclusions in two queries
    all_roles: dict[str, Role] = {
        r.id: r for r in (await db.execute(select(Role))).scalars().all()
    }
    inclusions_map: dict[str, list[str]] = {}
    for inc in (await db.execute(select(RoleInclusion))).scalars().all():
        inclusions_map.setdefault(inc.role_id, []).append(inc.included_role_id)

    # Directly assigned roles
    direct_roles = (await db.execute(
        select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )).scalars().all()

    # Pre-compute org subtrees for propagation tracking
    org_subtrees: dict[str, set[str]] = {}
    for role in all_roles.values():
        if role.org_id not in org_subtrees:
            org_subtrees[role.org_id] = set(await get_subtree_org_ids(db, role.org_id))

    def _in_subtree(parent_org_id: str, child_org_id: str) -> bool:
        return child_org_id in org_subtrees.get(parent_org_id, set())

    def build_node(
        role_id: str,
        path: frozenset[str],
        home_subtree_root: str | None = None,
    ) -> RoleTreeNode:
        role = all_roles[role_id]
        is_cycle = role_id in path
        new_path = path | {role_id}
        children = []
        if not is_cycle:
            for inc_id in inclusions_map.get(role_id, []):
                if inc_id not in all_roles:
                    continue
                inc_role = all_roles[inc_id]
                # Determine if this inclusion crosses an org boundary
                same_subtree = (
                    inc_role.org_id == role.org_id
                    or _in_subtree(role.org_id, inc_role.org_id)
                )
                if home_subtree_root is not None and not same_subtree:
                    # Already crossed a boundary; this is another foreign hop — blocked
                    also_in_home = _in_subtree(home_subtree_root, inc_role.org_id)
                    children.append(RoleTreeNode(
                        id=inc_role.id,
                        name=inc_role.name,
                        org_id=inc_role.org_id,
                        is_org_role=inc_role.is_org_role,
                        is_cycle=False,
                        is_propagation_blocked=not also_in_home,
                        included=[] if not also_in_home else build_node(
                            inc_id, new_path, home_subtree_root
                        ).included,
                    ))
                else:
                    # Compute the new home_subtree_root
                    new_home = home_subtree_root
                    if not same_subtree and home_subtree_root is None:
                        new_home = inc_role.org_id  # first foreign hop
                    children.append(build_node(inc_id, new_path, new_home))

        return RoleTreeNode(
            id=role.id,
            name=role.name,
            org_id=role.org_id,
            is_org_role=role.is_org_role,
            is_cycle=is_cycle,
            is_propagation_blocked=False,
            included=children,
        )

    roots = [build_node(r.id, frozenset()) for r in direct_roles]
    return RoleTreeResponse(user_id=user_id, username=target.username, roles=roots)


@router.get("/{user_id}/roles", response_model=list[RoleOut])
async def list_user_roles(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    result = await db.execute(
        select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return result.scalars().all()


@router.post("/{user_id}/roles/{role_id}", status_code=204)
async def assign_role(
    user_id: str,
    role_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    if role.is_org_role:
        raise HTTPException(403, "Org-member roles are managed automatically")

    if not current_user.is_superadmin:
        if not await org_in_subtree(db, current_user.org_id, user.org_id):
            raise HTTPException(403, "User is outside your org subtree")
        if not await org_in_subtree(db, current_user.org_id, role.org_id):
            raise HTTPException(403, "Role is outside your org subtree")

    if not await db.get(UserRole, (user_id, role_id)):
        db.add(UserRole(user_id=user_id, role_id=role_id))
        await db.commit()
        cache.invalidate_user(user_id)


@router.delete("/{user_id}/roles/{role_id}", status_code=204)
async def revoke_role(
    user_id: str,
    role_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    role = await db.get(Role, role_id)
    if role and role.is_org_role:
        raise HTTPException(403, "Org-member roles are managed automatically")

    if not current_user.is_superadmin:
        if not await org_in_subtree(db, current_user.org_id, user.org_id):
            raise HTTPException(403, "Forbidden")

    ur = await db.get(UserRole, (user_id, role_id))
    if ur:
        await db.delete(ur)
        await db.commit()
        cache.invalidate_user(user_id)

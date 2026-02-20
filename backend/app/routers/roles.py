from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Role, RoleInclusion, RoleResourcePermission, Organization, Resource, User, UserRole
from app.schemas import (
    RoleCreate, RoleUpdate, RoleOut, UserOut,
    InclusionCreate, ParentRoleAdd, PermissionSet, PermissionOut,
)
from app.auth import get_current_user, require_admin
from app.permissions import (
    check_inclusion_cycle, org_in_subtree, visible_org_ids,
    get_role_inherited_permissions,
)

router = APIRouter(prefix="/roles", tags=["roles"])


# ── Scope helpers ─────────────────────────────────────────────────────────────

async def _admin_owns_org(current_user: User, org_id: str, db: AsyncSession):
    if current_user.is_superadmin:
        return
    if not await org_in_subtree(db, current_user.org_id, org_id):
        raise HTTPException(403, "Role org is outside your admin scope")


async def _can_use_role(current_user: User, role: Role, db: AsyncSession):
    """Check that the admin can reference role (public → always; private → org scope)."""
    if role.is_public or current_user.is_superadmin:
        return
    if not await org_in_subtree(db, current_user.org_id, role.org_id):
        raise HTTPException(
            403,
            f"Role '{role.name}' is private and outside your org scope",
        )


def _guard_org_role(role: Role, operation: str = "modify"):
    if role.is_org_role:
        raise HTTPException(403, f"Cannot {operation} an org-member (@members) role")


# ── Role CRUD ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[RoleOut])
async def list_roles(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    org_ids = await visible_org_ids(db, current_user)
    if org_ids is None:
        result = await db.execute(select(Role))
    else:
        result = await db.execute(select(Role).where(Role.org_id.in_(org_ids)))
    return result.scalars().all()


@router.post("/", response_model=RoleOut, status_code=201)
async def create_role(
    body: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    org = await db.get(Organization, body.org_id)
    if not org:
        raise HTTPException(404, "Org not found")
    await _admin_owns_org(current_user, body.org_id, db)
    role = Role(name=body.name, org_id=body.org_id, is_public=body.is_public, is_org_role=False)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


@router.put("/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: str,
    body: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    _guard_org_role(role, "rename")
    await _admin_owns_org(current_user, role.org_id, db)
    if body.name is not None:
        role.name = body.name
    if body.is_public is not None:
        role.is_public = body.is_public
    await db.commit()
    await db.refresh(role)
    return role


@router.delete("/{role_id}", status_code=204)
async def delete_role(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    _guard_org_role(role, "delete")
    await _admin_owns_org(current_user, role.org_id, db)
    await db.delete(role)
    await db.commit()


# ── Users with this role ──────────────────────────────────────────────────────

@router.get("/{role_id}/users", response_model=list[UserOut])
async def list_role_users(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    q = select(User).join(UserRole, UserRole.user_id == User.id).where(UserRole.role_id == role_id)
    org_ids = await visible_org_ids(db, current_user)
    if org_ids is not None:
        q = q.where(User.org_id.in_(org_ids))
    result = await db.execute(q)
    return result.scalars().all()


# ── Inclusions (roles this role inherits from) ────────────────────────────────

@router.get("/{role_id}/inclusions", response_model=list[RoleOut])
async def list_inclusions(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not await db.get(Role, role_id):
        raise HTTPException(404, "Role not found")
    result = await db.execute(
        select(Role).join(RoleInclusion, RoleInclusion.included_role_id == Role.id)
        .where(RoleInclusion.role_id == role_id)
    )
    return result.scalars().all()


@router.post("/{role_id}/inclusions", status_code=204)
async def add_inclusion(
    role_id: str,
    body: InclusionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    included = await db.get(Role, body.included_role_id)
    if not included:
        raise HTTPException(404, "Included role not found")
    if role_id == body.included_role_id:
        raise HTTPException(422, "A role cannot include itself")

    await _admin_owns_org(current_user, role.org_id, db)
    # Public included roles can be used by anyone; private ones require scope
    await _can_use_role(current_user, included, db)

    await check_inclusion_cycle(db, role_id, body.included_role_id)
    if not await db.get(RoleInclusion, (role_id, body.included_role_id)):
        db.add(RoleInclusion(role_id=role_id, included_role_id=body.included_role_id))
        await db.commit()


@router.delete("/{role_id}/inclusions/{included_role_id}", status_code=204)
async def remove_inclusion(
    role_id: str,
    included_role_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    await _admin_owns_org(current_user, role.org_id, db)
    inc = await db.get(RoleInclusion, (role_id, included_role_id))
    if inc:
        await db.delete(inc)
        await db.commit()


# ── Parent roles (roles that include this role) ───────────────────────────────

@router.get("/{role_id}/parents", response_model=list[RoleOut])
async def list_parents(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not await db.get(Role, role_id):
        raise HTTPException(404, "Role not found")
    result = await db.execute(
        select(Role).join(RoleInclusion, RoleInclusion.role_id == Role.id)
        .where(RoleInclusion.included_role_id == role_id)
    )
    return result.scalars().all()


@router.post("/{role_id}/parents", status_code=204)
async def add_parent(
    role_id: str,
    body: ParentRoleAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    # Org-member roles cannot have parents (they are leaf nodes in the DAG)
    _guard_org_role(role, "add parents to")

    parent = await db.get(Role, body.parent_role_id)
    if not parent:
        raise HTTPException(404, "Parent role not found")
    if role_id == body.parent_role_id:
        raise HTTPException(422, "A role cannot be its own parent")

    # The admin must manage the child role's org
    await _admin_owns_org(current_user, role.org_id, db)
    # The parent role must be accessible (public OR within admin's scope)
    await _can_use_role(current_user, parent, db)

    await check_inclusion_cycle(db, body.parent_role_id, role_id)
    if not await db.get(RoleInclusion, (body.parent_role_id, role_id)):
        db.add(RoleInclusion(role_id=body.parent_role_id, included_role_id=role_id))
        await db.commit()


@router.delete("/{role_id}/parents/{parent_role_id}", status_code=204)
async def remove_parent(
    role_id: str,
    parent_role_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    _guard_org_role(role, "remove parents from")
    parent = await db.get(Role, parent_role_id)
    if not parent:
        raise HTTPException(404, "Parent role not found")
    await _can_use_role(current_user, parent, db)
    inc = await db.get(RoleInclusion, (parent_role_id, role_id))
    if inc:
        await db.delete(inc)
        await db.commit()


# ── Permissions ───────────────────────────────────────────────────────────────

@router.get("/{role_id}/permissions", response_model=list[PermissionOut])
async def list_permissions(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not await db.get(Role, role_id):
        raise HTTPException(404, "Role not found")
    result = await db.execute(
        select(RoleResourcePermission).where(RoleResourcePermission.role_id == role_id)
    )
    return result.scalars().all()


@router.get("/{role_id}/inherited-permissions", response_model=dict[str, int])
async def get_inherited_permissions(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not await db.get(Role, role_id):
        raise HTTPException(404, "Role not found")
    return await get_role_inherited_permissions(db, role_id)


@router.put("/{role_id}/permissions/{resource_id}", response_model=PermissionOut)
async def set_permission(
    role_id: str,
    resource_id: str,
    body: PermissionSet,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    if not await db.get(Resource, resource_id):
        raise HTTPException(404, "Resource not found")
    await _admin_owns_org(current_user, role.org_id, db)
    perm = await db.get(RoleResourcePermission, (role_id, resource_id))
    if perm:
        perm.permission_bits = body.permission_bits
    else:
        perm = RoleResourcePermission(role_id=role_id, resource_id=resource_id, permission_bits=body.permission_bits)
        db.add(perm)
    await db.commit()
    await db.refresh(perm)
    return perm


@router.delete("/{role_id}/permissions/{resource_id}", status_code=204)
async def remove_permission(
    role_id: str,
    resource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    await _admin_owns_org(current_user, role.org_id, db)
    perm = await db.get(RoleResourcePermission, (role_id, resource_id))
    if perm:
        await db.delete(perm)
        await db.commit()

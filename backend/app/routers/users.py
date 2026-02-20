from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, Organization, Role, UserRole
from app.schemas import UserCreate, UserUpdate, UserOut, RoleOut
from app.auth import get_current_user, require_superadmin, require_admin, hash_password
from app.permissions import org_in_subtree, get_org_role

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
    if not current_user.is_superadmin and current_user.id != user_id:
        raise HTTPException(403, "Forbidden")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    if body.username is not None:
        user.username = body.username
    if body.email is not None:
        user.email = body.email
    if body.password is not None:
        user.password_hash = hash_password(body.password)

    if body.org_id is not None and current_user.is_superadmin and body.org_id != user.org_id:
        new_org = await db.get(Organization, body.org_id)
        if not new_org:
            raise HTTPException(404, "Org not found")
        old_org_id = user.org_id
        user.org_id = body.org_id
        await _sync_org_role(db, user_id, old_org_id, body.org_id)

    if body.is_superadmin is not None and current_user.is_superadmin:
        user.is_superadmin = body.is_superadmin
    if body.is_org_admin is not None and current_user.is_superadmin:
        user.is_org_admin = body.is_org_admin

    await db.commit()
    await db.refresh(user)
    return user


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

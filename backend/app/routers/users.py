from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, Organization, Role, UserRole
from app.schemas import UserCreate, UserUpdate, UserOut, RoleOut
from app.auth import get_current_user, require_superadmin, require_admin, hash_password
from app.permissions import org_in_subtree

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.is_superadmin:
        result = await db.execute(select(User))
        return result.scalars().all()
    # org_admin sees own org + descendants
    if current_user.is_org_admin:
        all_orgs = await db.execute(select(Organization))
        all_orgs_list = all_orgs.scalars().all()
        visible_org_ids = [
            o.id for o in all_orgs_list
            if await org_in_subtree(db, current_user.org_id, o.id)
        ]
        result = await db.execute(select(User).where(User.org_id.in_(visible_org_ids)))
        return result.scalars().all()
    # Regular user sees only themselves
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
    # superadmin can update anyone; regular user can update only themselves
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
    if body.org_id is not None and current_user.is_superadmin:
        org = await db.get(Organization, body.org_id)
        if not org:
            raise HTTPException(404, "Org not found")
        user.org_id = body.org_id
    if body.is_superadmin is not None and current_user.is_superadmin:
        user.is_superadmin = body.is_superadmin
    if body.is_org_admin is not None and current_user.is_superadmin:
        user.is_org_admin = body.is_org_admin
    await db.commit()
    await db.refresh(user)
    return user


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

    # Admin scope check
    if not current_user.is_superadmin:
        if not await org_in_subtree(db, current_user.org_id, user.org_id):
            raise HTTPException(403, "Cannot assign roles to users outside your org subtree")
        if not await org_in_subtree(db, current_user.org_id, role.org_id):
            raise HTTPException(403, "Cannot assign roles from outside your org subtree")

    existing = await db.get(UserRole, (user_id, role_id))
    if existing:
        return  # idempotent

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

    if not current_user.is_superadmin:
        if not await org_in_subtree(db, current_user.org_id, user.org_id):
            raise HTTPException(403, "Forbidden")

    ur = await db.get(UserRole, (user_id, role_id))
    if ur:
        await db.delete(ur)
        await db.commit()


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


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

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Organization, User, Role, RoleInclusion, UserRole
from app.schemas import OrgCreate, OrgUpdate, OrgOut
from app.auth import get_current_user, require_superadmin
from app.permissions import get_org_role

router = APIRouter(prefix="/orgs", tags=["organizations"])


async def _create_org_role(db: AsyncSession, org_id: str, parent_id: str | None = None) -> Role:
    """Create the automatic @members role for a new org and wire the inclusion chain."""
    role = Role(name="@members", org_id=org_id, is_public=True, is_org_role=True)
    db.add(role)
    await db.flush()  # materialise role.id
    if parent_id:
        parent_members = await get_org_role(db, parent_id)
        if parent_members:
            db.add(RoleInclusion(role_id=role.id, included_role_id=parent_members.id))
    return role


@router.get("/", response_model=list[OrgOut])
async def list_orgs(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Organization))
    return result.scalars().all()


@router.post("/", response_model=OrgOut, status_code=201)
async def create_org(body: OrgCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_superadmin)):
    if body.parent_id:
        parent = await db.get(Organization, body.parent_id)
        if not parent:
            raise HTTPException(404, "Parent org not found")
    org = Organization(name=body.name, parent_id=body.parent_id)
    db.add(org)
    await db.flush()          # materialise org.id
    await _create_org_role(db, org.id, parent_id=body.parent_id)
    await db.commit()
    await db.refresh(org)
    return org


@router.put("/{org_id}", response_model=OrgOut)
async def update_org(org_id: str, body: OrgUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_superadmin)):
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Org not found")
    if body.name is not None:
        org.name = body.name
    if body.parent_id is not None:
        if body.parent_id == org_id:
            raise HTTPException(422, "Org cannot be its own parent")
        new_parent = await db.get(Organization, body.parent_id)
        if not new_parent:
            raise HTTPException(404, "Parent org not found")
        # Rewire @members chain: drop old parent inclusion, add new one
        org_members = await get_org_role(db, org_id)
        if org_members:
            if org.parent_id:
                old_parent_members = await get_org_role(db, org.parent_id)
                if old_parent_members:
                    old_inc = await db.get(RoleInclusion, (org_members.id, old_parent_members.id))
                    if old_inc:
                        await db.delete(old_inc)
            new_parent_members = await get_org_role(db, body.parent_id)
            if new_parent_members:
                if not await db.get(RoleInclusion, (org_members.id, new_parent_members.id)):
                    db.add(RoleInclusion(role_id=org_members.id, included_role_id=new_parent_members.id))
        org.parent_id = body.parent_id
    await db.commit()
    await db.refresh(org)
    return org


@router.delete("/{org_id}", status_code=204)
async def delete_org(org_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_superadmin)):
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Org not found")

    child_count = (await db.execute(
        select(func.count()).select_from(Organization).where(Organization.parent_id == org_id)
    )).scalar()
    if child_count > 0:
        raise HTTPException(422, "Cannot delete org with child organizations")

    user_count = (await db.execute(
        select(func.count()).select_from(User).where(User.org_id == org_id)
    )).scalar()
    if user_count > 0:
        raise HTTPException(422, "Cannot delete org that still has users")

    # Remove the auto-created @members role first (its user_roles cascade-delete)
    org_role = await get_org_role(db, org_id)
    if org_role:
        await db.delete(org_role)
        await db.flush()

    # Fail if non-system roles remain
    role_count = (await db.execute(
        select(func.count()).select_from(Role).where(Role.org_id == org_id)
    )).scalar()
    if role_count > 0:
        raise HTTPException(422, "Cannot delete org that still has roles; remove them first")

    await db.delete(org)
    await db.commit()

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.database import get_db
from app.models import Organization, User
from app.schemas import OrgCreate, OrgUpdate, OrgOut
from app.auth import get_current_user, require_superadmin

router = APIRouter(prefix="/orgs", tags=["organizations"])


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
        parent = await db.get(Organization, body.parent_id)
        if not parent:
            raise HTTPException(404, "Parent org not found")
        org.parent_id = body.parent_id
    await db.commit()
    await db.refresh(org)
    return org


@router.delete("/{org_id}", status_code=204)
async def delete_org(org_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_superadmin)):
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Org not found")
    # Check no children
    child_count = await db.execute(
        select(func.count()).select_from(Organization).where(Organization.parent_id == org_id)
    )
    if child_count.scalar() > 0:
        raise HTTPException(422, "Cannot delete org with child organizations")
    await db.delete(org)
    await db.commit()

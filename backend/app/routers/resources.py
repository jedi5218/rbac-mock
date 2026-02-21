from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Resource, Organization, User, RoleResourcePermission
from app.schemas import ResourceCreate, ResourceUpdate, ResourceOut, PermissionOut
from app.auth import get_current_user, require_admin
from app.permissions import org_in_subtree, visible_org_ids

router = APIRouter(prefix="/resources", tags=["resources"])


async def _admin_owns_org(current_user: User, org_id: str, db: AsyncSession):
    if current_user.is_superadmin:
        return
    if not await org_in_subtree(db, current_user.org_id, org_id):
        raise HTTPException(403, "Resource org is outside your admin scope")


@router.get("/", response_model=list[ResourceOut])
async def list_resources(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    org_ids = await visible_org_ids(db, current_user)
    if org_ids is None:
        result = await db.execute(select(Resource))
    else:
        result = await db.execute(select(Resource).where(Resource.org_id.in_(org_ids)))
    return result.scalars().all()


@router.post("/", response_model=ResourceOut, status_code=201)
async def create_resource(
    body: ResourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    org = await db.get(Organization, body.org_id)
    if not org:
        raise HTTPException(404, "Org not found")
    await _admin_owns_org(current_user, body.org_id, db)
    resource = Resource(name=body.name, resource_type=body.resource_type, org_id=body.org_id)
    db.add(resource)
    await db.commit()
    await db.refresh(resource)
    return resource


@router.put("/{resource_id}", response_model=ResourceOut)
async def update_resource(
    resource_id: str,
    body: ResourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    resource = await db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(404, "Resource not found")
    await _admin_owns_org(current_user, resource.org_id, db)
    if body.name is not None:
        resource.name = body.name
    if body.resource_type is not None:
        resource.resource_type = body.resource_type
    if body.org_id is not None:
        await _admin_owns_org(current_user, body.org_id, db)
        resource.org_id = body.org_id
    await db.commit()
    await db.refresh(resource)
    return resource


@router.get("/{resource_id}/permissions", response_model=list[PermissionOut])
async def list_resource_permissions(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not await db.get(Resource, resource_id):
        raise HTTPException(404, "Resource not found")
    result = await db.execute(
        select(RoleResourcePermission).where(RoleResourcePermission.resource_id == resource_id)
    )
    return result.scalars().all()


@router.delete("/{resource_id}", status_code=204)
async def delete_resource(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    resource = await db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(404, "Resource not found")
    await _admin_owns_org(current_user, resource.org_id, db)
    await db.delete(resource)
    await db.commit()

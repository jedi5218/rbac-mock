from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Organization, User
from app.schemas import OrgInteractionsOut
from app.auth import require_admin
from app.permissions import visible_org_ids, get_subtree_org_ids, get_interactions

router = APIRouter(prefix="/interactions", tags=["interactions"])


@router.get("/", response_model=list[OrgInteractionsOut])
async def get_interactions_view(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Resolve the set of org IDs this admin can see
    org_ids = await visible_org_ids(db, current_user)
    if org_ids is None:
        # superadmin — all orgs
        result = await db.execute(select(Organization.id))
        org_ids = [str(r[0]) for r in result.fetchall()]

    if not org_ids:
        return []

    interactions_map = await get_interactions(db, org_ids)

    # Fetch org details for all visible orgs
    result = await db.execute(
        select(Organization).where(Organization.id.in_(org_ids))
    )
    orgs = result.scalars().all()

    return [
        OrgInteractionsOut(
            org_id=org.id,
            org_name=org.name,
            parent_id=org.parent_id,
            interactions=[
                {
                    "foreign_org_id":   entry["foreign_org_id"],
                    "foreign_org_name": entry["foreign_org_name"],
                    "roles": entry["roles"],
                }
                for entry in interactions_map.get(org.id, {}).values()
            ],
        )
        for org in orgs
    ]

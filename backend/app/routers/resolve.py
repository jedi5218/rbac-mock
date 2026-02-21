from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import ResolveResponse
from app.auth import get_current_user
from app.permissions import get_effective_permissions, org_in_subtree
import app.cache as cache

router = APIRouter(prefix="/resolve", tags=["resolve"])


@router.get("/user/{user_id}", response_model=ResolveResponse)
async def resolve_user(
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
            raise HTTPException(403, "You can only resolve your own permissions")

    cached = cache.get_resolve(user_id)
    if cached is not None:
        return ResolveResponse(user_id=user_id, permissions=cached)

    perms = await get_effective_permissions(db, user_id)
    cache.set_resolve(user_id, perms)
    return ResolveResponse(user_id=user_id, permissions=perms)

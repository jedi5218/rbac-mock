from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete

from app.database import get_db
from app.models import (
    OrgExchange, ExchangeRole, Role, RoleInclusion, Organization, User,
)
from app.schemas import (
    ExchangeCreate, ExchangeOut, ExchangeRoleOut,
    ExposeRoleRequest, ExchangeImpact,
)
from app.auth import require_admin
from app.permissions import org_in_subtree, visible_org_ids
import app.cache as cache

router = APIRouter(prefix="/exchanges", tags=["exchanges"])


def _normalize_pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


async def _build_exchange_out(db: AsyncSession, ex: OrgExchange) -> ExchangeOut:
    org_a = await db.get(Organization, ex.org_a_id)
    org_b = await db.get(Organization, ex.org_b_id)
    # Load exposed roles with names and org info
    result = await db.execute(
        select(ExchangeRole, Role, Organization)
        .join(Role, ExchangeRole.role_id == Role.id)
        .join(Organization, Role.org_id == Organization.id)
        .where(ExchangeRole.exchange_id == ex.id)
    )
    roles_out = [
        ExchangeRoleOut(
            role_id=er.role_id,
            role_name=role.name,
            role_org_id=role.org_id,
            role_org_name=org.name,
        )
        for er, role, org in result.all()
    ]
    return ExchangeOut(
        id=ex.id,
        org_a_id=ex.org_a_id,
        org_a_name=org_a.name,
        org_b_id=ex.org_b_id,
        org_b_name=org_b.name,
        created_at=ex.created_at,
        exposed_roles=roles_out,
    )


@router.get("/", response_model=list[ExchangeOut])
async def list_exchanges(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    org_ids = await visible_org_ids(db, current_user)
    if org_ids is None:
        result = await db.execute(select(OrgExchange))
    else:
        result = await db.execute(
            select(OrgExchange).where(
                or_(
                    OrgExchange.org_a_id.in_(org_ids),
                    OrgExchange.org_b_id.in_(org_ids),
                )
            )
        )
    exchanges = result.scalars().all()
    return [await _build_exchange_out(db, ex) for ex in exchanges]


@router.post("/", response_model=ExchangeOut, status_code=201)
async def create_exchange(
    body: ExchangeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Validate orgs exist
    org = await db.get(Organization, body.org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    partner = await db.get(Organization, body.partner_org_id)
    if not partner:
        raise HTTPException(404, "Partner organization not found")
    if body.org_id == body.partner_org_id:
        raise HTTPException(422, "Cannot create exchange with the same organization")

    # Admin must have scope over their own org
    if not current_user.is_superadmin:
        if not await org_in_subtree(db, current_user.org_id, body.org_id):
            raise HTTPException(403, "Organization is outside your admin scope")

    # Prevent exchanges between ancestor/descendant orgs
    if await org_in_subtree(db, body.org_id, body.partner_org_id):
        raise HTTPException(422, "Cannot create exchange between orgs in the same hierarchy")
    if await org_in_subtree(db, body.partner_org_id, body.org_id):
        raise HTTPException(422, "Cannot create exchange between orgs in the same hierarchy")

    # Normalize and check for duplicates
    a_id, b_id = _normalize_pair(body.org_id, body.partner_org_id)
    existing = await db.execute(
        select(OrgExchange).where(
            OrgExchange.org_a_id == a_id, OrgExchange.org_b_id == b_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Exchange already exists between these organizations")

    exchange = OrgExchange(org_a_id=a_id, org_b_id=b_id)
    db.add(exchange)
    await db.commit()
    await db.refresh(exchange)
    return await _build_exchange_out(db, exchange)


@router.get("/{exchange_id}", response_model=ExchangeOut)
async def get_exchange(
    exchange_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    exchange = await db.get(OrgExchange, exchange_id)
    if not exchange:
        raise HTTPException(404, "Exchange not found")
    return await _build_exchange_out(db, exchange)


async def _compute_impact(
    db: AsyncSession, exchange: OrgExchange, admin_org_id: str | None,
) -> ExchangeImpact:
    """Compute the impact of closing an exchange: how many inclusions will be removed."""
    # Find cross-org role_inclusions between the pair where the included role was exposed
    result = await db.execute(
        select(RoleInclusion)
        .join(Role, RoleInclusion.included_role_id == Role.id)
        .join(ExchangeRole, and_(
            ExchangeRole.exchange_id == exchange.id,
            ExchangeRole.role_id == RoleInclusion.included_role_id,
        ))
        .where(
            or_(
                # role from org_a includes exposed role from org_b
                and_(
                    Role.org_id == exchange.org_b_id,
                    RoleInclusion.role_id.in_(
                        select(Role.id).where(Role.org_id == exchange.org_a_id)
                    ),
                ),
                # role from org_b includes exposed role from org_a
                and_(
                    Role.org_id == exchange.org_a_id,
                    RoleInclusion.role_id.in_(
                        select(Role.id).where(Role.org_id == exchange.org_b_id)
                    ),
                ),
            )
        )
    )
    inclusions = result.scalars().all()

    # Count partner-exposed roles (roles that the partner org exposed, which only
    # the partner admin can re-expose)
    partner_org_id = exchange.org_b_id if admin_org_id == exchange.org_a_id else exchange.org_a_id
    partner_org = await db.get(Organization, partner_org_id)
    partner_roles_result = await db.execute(
        select(ExchangeRole)
        .join(Role, ExchangeRole.role_id == Role.id)
        .where(ExchangeRole.exchange_id == exchange.id, Role.org_id == partner_org_id)
    )
    partner_role_count = len(partner_roles_result.scalars().all())

    return ExchangeImpact(
        inclusions_removed=len(inclusions),
        partner_exposed_roles=partner_role_count,
        partner_org_name=partner_org.name if partner_org else "",
    )


@router.get("/{exchange_id}/impact", response_model=ExchangeImpact)
async def get_exchange_impact(
    exchange_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    exchange = await db.get(OrgExchange, exchange_id)
    if not exchange:
        raise HTTPException(404, "Exchange not found")
    # Determine which side the admin is on
    admin_org = exchange.org_a_id
    if not current_user.is_superadmin:
        if await org_in_subtree(db, current_user.org_id, exchange.org_b_id):
            admin_org = exchange.org_b_id
    return await _compute_impact(db, exchange, admin_org)


@router.delete("/{exchange_id}", status_code=204)
async def delete_exchange(
    exchange_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    exchange = await db.get(OrgExchange, exchange_id)
    if not exchange:
        raise HTTPException(404, "Exchange not found")

    # Admin must have scope over at least one side
    if not current_user.is_superadmin:
        a_ok = await org_in_subtree(db, current_user.org_id, exchange.org_a_id)
        b_ok = await org_in_subtree(db, current_user.org_id, exchange.org_b_id)
        if not a_ok and not b_ok:
            raise HTTPException(403, "Exchange is outside your admin scope")

    # Cascade: delete cross-org role_inclusions where the included role was exposed
    exposed_role_ids = [er.role_id for er in (
        await db.execute(
            select(ExchangeRole).where(ExchangeRole.exchange_id == exchange.id)
        )
    ).scalars().all()]

    if exposed_role_ids:
        # Delete inclusions where the included role was exposed AND the parent role
        # is from the partner org
        await db.execute(
            delete(RoleInclusion).where(
                RoleInclusion.included_role_id.in_(exposed_role_ids),
                RoleInclusion.role_id.in_(
                    select(Role.id).where(
                        or_(
                            Role.org_id == exchange.org_a_id,
                            Role.org_id == exchange.org_b_id,
                        )
                    )
                ),
                # Only delete cross-org inclusions (not same-org ones)
                RoleInclusion.included_role_id.in_(
                    select(Role.id).where(Role.org_id == exchange.org_a_id)
                ) & RoleInclusion.role_id.in_(
                    select(Role.id).where(Role.org_id == exchange.org_b_id)
                ) | RoleInclusion.included_role_id.in_(
                    select(Role.id).where(Role.org_id == exchange.org_b_id)
                ) & RoleInclusion.role_id.in_(
                    select(Role.id).where(Role.org_id == exchange.org_a_id)
                ),
            )
        )

    await db.delete(exchange)  # cascades exchange_roles
    await db.commit()
    cache.invalidate_all()


@router.post("/{exchange_id}/roles", status_code=204)
async def expose_role(
    exchange_id: str,
    body: ExposeRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    exchange = await db.get(OrgExchange, exchange_id)
    if not exchange:
        raise HTTPException(404, "Exchange not found")

    role = await db.get(Role, body.role_id)
    if not role:
        raise HTTPException(404, "Role not found")

    # Role must belong to one of the exchange orgs
    if role.org_id not in (exchange.org_a_id, exchange.org_b_id):
        raise HTTPException(422, "Role does not belong to either organization in this exchange")

    # Admin must have scope over the role's org
    if not current_user.is_superadmin:
        if not await org_in_subtree(db, current_user.org_id, role.org_id):
            raise HTTPException(403, "Role's organization is outside your admin scope")

    # Check not already exposed
    existing = await db.get(ExchangeRole, (exchange_id, body.role_id))
    if existing:
        raise HTTPException(409, "Role is already exposed in this exchange")

    db.add(ExchangeRole(exchange_id=exchange_id, role_id=body.role_id))
    await db.commit()
    cache.invalidate_all()


@router.delete("/{exchange_id}/roles/{role_id}", status_code=204)
async def unexpose_role(
    exchange_id: str,
    role_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    exchange = await db.get(OrgExchange, exchange_id)
    if not exchange:
        raise HTTPException(404, "Exchange not found")

    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "Role not found")

    # Admin must have scope over the role's org
    if not current_user.is_superadmin:
        if not await org_in_subtree(db, current_user.org_id, role.org_id):
            raise HTTPException(403, "Role's organization is outside your admin scope")

    er = await db.get(ExchangeRole, (exchange_id, role_id))
    if not er:
        raise HTTPException(404, "Role is not exposed in this exchange")

    # Cascade: remove role_inclusions where this role is included by the partner org
    partner_org_id = exchange.org_b_id if role.org_id == exchange.org_a_id else exchange.org_a_id
    await db.execute(
        delete(RoleInclusion).where(
            RoleInclusion.included_role_id == role_id,
            RoleInclusion.role_id.in_(
                select(Role.id).where(Role.org_id == partner_org_id)
            ),
        )
    )

    await db.delete(er)
    await db.commit()
    cache.invalidate_all()

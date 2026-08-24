from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from contracts.constants.permissions import DELEGATE
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AuthorityGrant, CaseAccess, Delegation

ROLE_PERMISSIONS = {
    "owner": ["view", "submit", "approve", "manage", "delegate", "delete"],
    "coordinator": ["view", "submit", "manage"],
    "viewer": ["view"],
}
ROLE_RANK = {"viewer": 1, "coordinator": 2, "owner": 3}


class Publisher(Protocol):
    async def publish(self, event: dict[str, Any]) -> None: ...


@dataclass
class AccessDecision:
    allowed: bool = False
    role: str = ""
    permissions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


def permissions_for(role: str, override: list[str]) -> list[str]:
    return sorted(set(override or ROLE_PERMISSIONS.get(role, [])))


async def check_access(
    session: AsyncSession,
    user_id: UUID,
    resource_type: str,
    resource_id: UUID,
    action: str,
) -> AccessDecision:
    now = datetime.now(UTC)
    grants = (
        await session.scalars(
            select(AuthorityGrant).where(
                AuthorityGrant.grantee_id == user_id,
                AuthorityGrant.resource_type == resource_type,
                AuthorityGrant.resource_id == resource_id,
                AuthorityGrant.revoked_at.is_(None),
                or_(AuthorityGrant.expires_at.is_(None), AuthorityGrant.expires_at > now),
            )
        )
    ).all()
    candidates = [
        AccessDecision(
            allowed=action in permissions_for(grant.role, grant.permissions),
            role=grant.role,
            permissions=permissions_for(grant.role, grant.permissions),
            limitations=[f"expires_at:{grant.expires_at.isoformat()}"] if grant.expires_at else [],
        )
        for grant in grants
    ]

    delegations = (
        await session.scalars(
            select(Delegation).where(
                Delegation.delegate_id == user_id,
                Delegation.status == "active",
                Delegation.valid_from <= now,
                or_(Delegation.valid_until.is_(None), Delegation.valid_until > now),
            )
        )
    ).all()
    for delegation in delegations:
        if not _delegation_matches(delegation, resource_type, resource_id):
            continue
        delegator = await _direct_access(
            session, delegation.delegator_id, resource_type, resource_id, DELEGATE, now
        )
        if not delegator.allowed:
            continue
        permissions = permissions_for(delegation.role, delegation.permissions)
        limitations = [f"delegated_by:{delegation.delegator_id}"]
        if delegation.valid_until:
            limitations.append(f"valid_until:{delegation.valid_until.isoformat()}")
        candidates.append(
            AccessDecision(
                allowed=action in permissions,
                role=delegation.role,
                permissions=permissions,
                limitations=limitations,
            )
        )

    allowed = [candidate for candidate in candidates if candidate.allowed]
    pool = allowed or candidates
    return max(pool, key=lambda item: ROLE_RANK[item.role]) if pool else AccessDecision()


async def list_user_cases(session: AsyncSession, user_id: UUID) -> list[tuple[UUID, str, datetime]]:
    now = datetime.now(UTC)
    rows = (
        await session.execute(
            select(CaseAccess, AuthorityGrant)
            .join(AuthorityGrant, CaseAccess.grant_id == AuthorityGrant.id)
            .where(
                CaseAccess.user_id == user_id,
                AuthorityGrant.revoked_at.is_(None),
                or_(AuthorityGrant.expires_at.is_(None), AuthorityGrant.expires_at > now),
            )
        )
    ).all()
    cases = {access.case_id: (access.role, grant.granted_at) for access, grant in rows}
    delegated = (
        await session.scalars(
            select(Delegation).where(
                Delegation.delegate_id == user_id,
                Delegation.scope_type == "case",
                Delegation.status == "active",
                Delegation.valid_from <= now,
                or_(Delegation.valid_until.is_(None), Delegation.valid_until > now),
            )
        )
    ).all()
    for delegation in delegated:
        if delegation.scope_id is None:
            continue
        owner = await _direct_access(
            session,
            delegation.delegator_id,
            "case",
            delegation.scope_id,
            DELEGATE,
            now,
        )
        if owner.allowed and delegation.scope_id not in cases:
            cases[delegation.scope_id] = (delegation.role, delegation.valid_from)
    return [
        (case_id, role, granted_at)
        for case_id, (role, granted_at) in sorted(cases.items(), key=lambda item: str(item[0]))
    ]


async def _direct_access(
    session: AsyncSession,
    user_id: UUID,
    resource_type: str,
    resource_id: UUID,
    action: str,
    now: datetime,
) -> AccessDecision:
    grants = (
        await session.scalars(
            select(AuthorityGrant).where(
                AuthorityGrant.grantee_id == user_id,
                AuthorityGrant.resource_type == resource_type,
                AuthorityGrant.resource_id == resource_id,
                AuthorityGrant.revoked_at.is_(None),
                or_(AuthorityGrant.expires_at.is_(None), AuthorityGrant.expires_at > now),
            )
        )
    ).all()
    candidates = [
        AccessDecision(
            allowed=action in permissions_for(grant.role, grant.permissions),
            role=grant.role,
            permissions=permissions_for(grant.role, grant.permissions),
        )
        for grant in grants
    ]
    allowed = [candidate for candidate in candidates if candidate.allowed]
    pool = allowed or candidates
    return max(pool, key=lambda item: ROLE_RANK[item.role]) if pool else AccessDecision()


def _delegation_matches(delegation: Delegation, resource_type: str, resource_id: UUID) -> bool:
    return (
        delegation.scope_type == "all_cases"
        and resource_type == "case"
        or delegation.scope_type == resource_type
        and delegation.scope_id == resource_id
    )


async def create_grant(
    session: AsyncSession,
    publisher: Publisher,
    actor_id: UUID | None,
    grantee_id: UUID,
    resource_type: str,
    resource_id: UUID,
    role: str,
    expires_at: datetime | None = None,
) -> AuthorityGrant:
    if actor_id is not None:
        decision = await check_access(session, actor_id, resource_type, resource_id, DELEGATE)
        if not decision.allowed:
            raise PermissionError("Delegation permission required")
    existing = await session.scalar(
        select(AuthorityGrant).where(
            AuthorityGrant.grantee_id == grantee_id,
            AuthorityGrant.resource_type == resource_type,
            AuthorityGrant.resource_id == resource_id,
            AuthorityGrant.revoked_at.is_(None),
            or_(
                AuthorityGrant.expires_at.is_(None),
                AuthorityGrant.expires_at > datetime.now(UTC),
            ),
        )
    )
    if existing:
        if actor_id is None and existing.role == "owner":
            return existing
        raise ValueError("Active grant already exists")

    grant = AuthorityGrant(
        grantor_id=actor_id,
        grantee_id=grantee_id,
        resource_type=resource_type,
        resource_id=resource_id,
        role=role,
        expires_at=expires_at,
    )
    session.add(grant)
    await session.flush()
    if resource_type == "case":
        session.add(
            CaseAccess(
                user_id=grantee_id,
                case_id=resource_id,
                role=role,
                grant_id=grant.id,
            )
        )
    await publisher.publish(
        _event(
            "authority.granted",
            grant_id=str(grant.id),
            grantor_id=str(actor_id) if actor_id else None,
            grantee_id=str(grantee_id),
            resource_type=resource_type,
            resource_id=str(resource_id),
            role=role,
            permissions=permissions_for(role, grant.permissions),
        )
    )
    await session.commit()
    return grant


async def revoke_grant(
    session: AsyncSession,
    publisher: Publisher,
    actor_id: UUID,
    grant: AuthorityGrant,
    reason: str | None,
) -> None:
    if grant.revoked_at:
        return
    if grant.grantor_id is None and grant.role == "owner":
        raise PermissionError("System ownership grants cannot be revoked")
    decision = await check_access(
        session, actor_id, grant.resource_type, grant.resource_id, "manage"
    )
    if grant.grantor_id != actor_id and not decision.allowed:
        raise PermissionError("Grantor or manage permission required")
    grant.revoked_at = datetime.now(UTC)
    grant.revocation_reason = reason
    await session.execute(delete(CaseAccess).where(CaseAccess.grant_id == grant.id))
    await publisher.publish(
        _event(
            "authority.revoked",
            grant_id=str(grant.id),
            revocation_reason=reason,
        )
    )
    await session.commit()


async def create_delegation(
    session: AsyncSession,
    publisher: Publisher,
    delegator_id: UUID,
    delegate_id: UUID,
    scope_type: str,
    scope_id: UUID | None,
    role: str,
    permissions: list[str],
    valid_until: datetime | None,
) -> Delegation:
    if delegator_id == delegate_id:
        raise ValueError("Cannot delegate authority to yourself")
    if scope_type != "all_cases":
        if scope_id is None:
            raise ValueError("scope_id is required for scoped delegations")
        decision = await check_access(
            session,
            delegator_id,
            scope_type,
            scope_id,
            DELEGATE,
        )
        if not decision.allowed:
            raise PermissionError("Delegation permission required")
    delegation = Delegation(
        delegator_id=delegator_id,
        delegate_id=delegate_id,
        scope_type=scope_type,
        scope_id=scope_id,
        role=role,
        permissions=permissions,
        valid_until=valid_until,
    )
    session.add(delegation)
    await session.flush()
    await publisher.publish(
        _event(
            "authority.delegation_created",
            delegation_id=str(delegation.id),
            delegator_id=str(delegator_id),
            delegate_id=str(delegate_id),
            scope_type=scope_type,
            scope_id=str(scope_id) if scope_id else None,
            role=role,
            permissions=permissions_for(role, permissions),
        )
    )
    await session.commit()
    return delegation


async def revoke_delegation(
    session: AsyncSession,
    publisher: Publisher,
    actor_id: UUID,
    delegation: Delegation,
) -> None:
    if delegation.delegator_id != actor_id:
        raise PermissionError("Only the delegator can revoke this delegation")
    if delegation.status != "active":
        return
    delegation.status = "revoked"
    await publisher.publish(
        _event("authority.delegation_revoked", delegation_id=str(delegation.id))
    )
    await session.commit()


async def expire_authority(
    sessions: async_sessionmaker[AsyncSession], publisher: Publisher
) -> None:
    now = datetime.now(UTC)
    async with sessions() as session:
        grants = (
            await session.scalars(
                select(AuthorityGrant).where(
                    AuthorityGrant.revoked_at.is_(None), AuthorityGrant.expires_at <= now
                )
            )
        ).all()
        delegations = (
            await session.scalars(
                select(Delegation).where(
                    Delegation.status == "active", Delegation.valid_until <= now
                )
            )
        ).all()
        for grant in grants:
            grant.revoked_at = now
            grant.revocation_reason = "expired"
            await session.execute(delete(CaseAccess).where(CaseAccess.grant_id == grant.id))
            await publisher.publish(
                _event(
                    "authority.revoked",
                    grant_id=str(grant.id),
                    revocation_reason="expired",
                )
            )
        for delegation in delegations:
            delegation.status = "expired"
            await publisher.publish(
                _event(
                    "authority.delegation_revoked",
                    delegation_id=str(delegation.id),
                    revocation_reason="expired",
                )
            )
        await session.commit()


def _event(event_type: str, **fields: Any) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "timestamp": datetime.now(UTC).isoformat(),
        **fields,
    }

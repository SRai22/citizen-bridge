from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from contracts.constants.permissions import DELEGATE
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.models import AuthorityGrant, CaseAccess, Delegation, DelegationApprovalRequest

ROLE_PERMISSIONS = {
    "owner": ["view", "submit", "approve", "manage", "delegate", "delete"],
    "coordinator": ["view", "submit", "manage"],
    "viewer": ["view"],
}
ROLE_RANK = {"viewer": 1, "coordinator": 2, "owner": 3}
ROLE_LIMITATIONS = {
    "owner": [],
    "coordinator": [
        "Cannot approve legal declarations",
        "Cannot authorize payments or delete the case",
    ],
    "viewer": ["View-only access"],
}


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
            limitations=ROLE_LIMITATIONS.get(grant.role, [])
            + ([f"expires_at:{grant.expires_at.isoformat()}"] if grant.expires_at else []),
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
        limitations = [
            *ROLE_LIMITATIONS.get(delegation.role, []),
            f"delegated_by:{delegation.delegator_id}",
        ]
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


async def list_case_users(session: AsyncSession, case_id: UUID) -> list[UUID]:
    now = datetime.now(UTC)
    direct = set(
        (
            await session.scalars(
                select(CaseAccess.user_id)
                .join(AuthorityGrant, CaseAccess.grant_id == AuthorityGrant.id)
                .where(
                    CaseAccess.case_id == case_id,
                    AuthorityGrant.revoked_at.is_(None),
                    or_(AuthorityGrant.expires_at.is_(None), AuthorityGrant.expires_at > now),
                )
            )
        ).all()
    )
    delegations = (
        await session.scalars(
            select(Delegation).where(
                Delegation.status == "active",
                Delegation.valid_from <= now,
                or_(Delegation.valid_until.is_(None), Delegation.valid_until > now),
                or_(
                    Delegation.scope_type == "all_cases",
                    (Delegation.scope_type == "case") & (Delegation.scope_id == case_id),
                ),
            )
        )
    ).all()
    for delegation in delegations:
        delegator = await _direct_access(
            session, delegation.delegator_id, "case", case_id, "view", now
        )
        if delegator.allowed:
            direct.add(delegation.delegate_id)
    return sorted(direct, key=str)


async def list_case_access(
    session: AsyncSession, case_id: UUID
) -> list[tuple[UUID, str, datetime, UUID | None]]:
    now = datetime.now(UTC)
    rows = (
        await session.execute(
            select(CaseAccess, AuthorityGrant)
            .join(AuthorityGrant, CaseAccess.grant_id == AuthorityGrant.id)
            .where(
                CaseAccess.case_id == case_id,
                AuthorityGrant.revoked_at.is_(None),
                or_(AuthorityGrant.expires_at.is_(None), AuthorityGrant.expires_at > now),
            )
        )
    ).all()
    result = {
        access.user_id: (access.role, grant.granted_at, grant.grantor_id)
        for access, grant in rows
    }
    delegations = (
        await session.scalars(
            select(Delegation).where(
                Delegation.status == "active",
                Delegation.valid_from <= now,
                or_(Delegation.valid_until.is_(None), Delegation.valid_until > now),
                or_(
                    Delegation.scope_type == "all_cases",
                    (Delegation.scope_type == "case") & (Delegation.scope_id == case_id),
                ),
            )
        )
    ).all()
    for delegation in delegations:
        if (
            await _direct_access(
                session, delegation.delegator_id, "case", case_id, DELEGATE, now
            )
        ).allowed:
            result[delegation.delegate_id] = (
                delegation.role,
                delegation.valid_from,
                delegation.delegator_id,
            )
    return [
        (user_id, role, granted_at, granted_by)
        for user_id, (role, granted_at, granted_by) in result.items()
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
            limitations=ROLE_LIMITATIONS.get(grant.role, []),
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


async def assign_case_coordinator(
    session: AsyncSession,
    publisher: Publisher,
    user_id: UUID,
    case_id: UUID,
    subject_person_id: UUID | None = None,
    relationship: str | None = None,
) -> AuthorityGrant:
    grant = await session.scalar(
        select(AuthorityGrant).where(
            AuthorityGrant.grantee_id == user_id,
            AuthorityGrant.resource_type == "case",
            AuthorityGrant.resource_id == case_id,
            AuthorityGrant.revoked_at.is_(None),
        ).options(selectinload(AuthorityGrant.case_access))
    )
    if grant is None:
        grant = await create_grant(
            session, publisher, None, user_id, "case", case_id, "coordinator"
        )
    else:
        grant.role = "coordinator"
        if grant.case_access:
            grant.case_access.role = "coordinator"
        await session.commit()
    await publisher.publish(
        _event(
            "authority.coordinator_assigned",
            grant_id=str(grant.id),
            user_id=str(user_id),
            case_id=str(case_id),
            subject_person_id=str(subject_person_id) if subject_person_id else None,
            relationship=relationship,
        )
    )
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
            grantee_id=str(grant.grantee_id),
            resource_type=grant.resource_type,
            resource_id=str(grant.resource_id),
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


async def request_delegation(
    session: AsyncSession,
    publisher: Publisher,
    from_user_id: UUID,
    to_user_id: UUID,
    scope_id: UUID,
    message: str | None,
    expires_at: datetime | None,
) -> DelegationApprovalRequest:
    if from_user_id == to_user_id:
        raise ValueError("Cannot delegate authority to yourself")
    if not (
        await check_access(session, from_user_id, "case", scope_id, DELEGATE)
    ).allowed:
        raise PermissionError("Delegation permission required")
    existing = await session.scalar(
        select(DelegationApprovalRequest).where(
            DelegationApprovalRequest.from_user_id == from_user_id,
            DelegationApprovalRequest.to_user_id == to_user_id,
            DelegationApprovalRequest.scope_id == scope_id,
            DelegationApprovalRequest.status == "pending",
        )
    )
    if existing:
        return existing
    request = DelegationApprovalRequest(
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        scope_type="case",
        scope_id=scope_id,
        role="coordinator",
        message=message,
        expires_at=expires_at,
    )
    session.add(request)
    await session.flush()
    await publisher.publish(
        _event(
            "authority.delegation_requested",
            delegation_request_id=str(request.id),
            from_user=str(from_user_id),
            to_user=str(to_user_id),
            scope_type="case",
            scope_id=str(scope_id),
        )
    )
    await session.commit()
    return request


async def respond_to_delegation_request(
    session: AsyncSession,
    publisher: Publisher,
    request: DelegationApprovalRequest,
    actor_id: UUID,
    accept: bool,
) -> DelegationApprovalRequest:
    if request.to_user_id != actor_id:
        raise PermissionError("Only the requested delegate can respond")
    if request.status != "pending":
        raise ValueError("Delegation request is no longer pending")
    if request.expires_at and request.expires_at <= datetime.now(UTC):
        request.status = "expired"
        await session.commit()
        raise ValueError("Delegation request has expired")
    request.status = "accepted" if accept else "rejected"
    request.responded_at = datetime.now(UTC)
    if accept:
        delegation = await create_delegation(
            session,
            publisher,
            request.from_user_id,
            request.to_user_id,
            request.scope_type,
            request.scope_id,
            request.role,
            [],
            request.expires_at,
        )
        request.delegation_id = delegation.id
        await publisher.publish(
            _event(
                "authority.delegation_accepted",
                delegation_id=str(delegation.id),
                delegation_request_id=str(request.id),
                delegate_id=str(actor_id),
                scope_id=str(request.scope_id),
            )
        )
    else:
        await publisher.publish(
            _event(
                "authority.delegation_rejected",
                delegation_request_id=str(request.id),
                delegate_id=str(actor_id),
                scope_id=str(request.scope_id),
            )
        )
    await session.commit()
    return request


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
        requests = (
            await session.scalars(
                select(DelegationApprovalRequest).where(
                    DelegationApprovalRequest.status == "pending",
                    DelegationApprovalRequest.expires_at <= now,
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
                    grantee_id=str(grant.grantee_id),
                    resource_type=grant.resource_type,
                    resource_id=str(grant.resource_id),
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
        for request in requests:
            request.status = "expired"
            await publisher.publish(
                _event(
                    "authority.delegation_expired",
                    delegation_request_id=str(request.id),
                    from_user=str(request.from_user_id),
                    to_user=str(request.to_user_id),
                    scope_id=str(request.scope_id),
                )
            )
        await session.commit()


def _event(event_type: str, **fields: Any) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "timestamp": datetime.now(UTC).isoformat(),
        **fields,
    }

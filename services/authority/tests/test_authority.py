from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from contracts.generated import authority_pb2

from app.grpc.server import AuthorityServicer
from app.models import AuthorityGrant, Delegation
from app.service import (
    check_access,
    create_delegation,
    create_grant,
    expire_authority,
    list_user_cases,
    revoke_delegation,
    revoke_grant,
)


def auth(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


@pytest.mark.asyncio
async def test_grant_check_list_and_revoke(authority_context) -> None:
    client, sessions, publisher, users = authority_context
    owner_id, coordinator_id, outsider_id, case_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    users.update({owner_id, coordinator_id, outsider_id})
    async with sessions() as session:
        await create_grant(session, publisher, None, owner_id, "case", case_id, "owner")

    granted = await client.post(
        "/api/authority/grants",
        headers=auth(owner_id),
        json={
            "grantee_id": str(coordinator_id),
            "resource_type": "case",
            "resource_id": str(case_id),
            "role": "coordinator",
        },
    )
    assert granted.status_code == 201
    grant_id = granted.json()["grant_id"]

    allowed = await client.get(
        "/api/authority/check",
        headers=auth(coordinator_id),
        params={
            "user_id": str(coordinator_id),
            "resource_type": "case",
            "resource_id": str(case_id),
            "action": "submit",
        },
    )
    denied = await client.get(
        "/api/authority/check",
        headers=auth(coordinator_id),
        params={
            "user_id": str(coordinator_id),
            "resource_type": "case",
            "resource_id": str(case_id),
            "action": "approve",
        },
    )
    cases = await client.get("/api/authority/cases", headers=auth(coordinator_id))
    assert allowed.json()["allowed"] is True
    assert denied.json()["allowed"] is False
    assert cases.json()["cases"][0]["case_id"] == str(case_id)

    forbidden = await client.post(
        "/api/authority/grants",
        headers=auth(coordinator_id),
        json={
            "grantee_id": str(outsider_id),
            "resource_type": "case",
            "resource_id": str(case_id),
            "role": "viewer",
        },
    )
    assert forbidden.status_code == 403

    revoked = await client.request(
        "DELETE",
        f"/api/authority/grants/{grant_id}",
        headers=auth(owner_id),
        json={"reason": "No longer coordinating"},
    )
    assert revoked.status_code == 204
    assert publisher.events[-1]["event_type"] == "authority.revoked"


@pytest.mark.asyncio
async def test_delegation_and_expiration(authority_context) -> None:
    client, sessions, publisher, users = authority_context
    owner_id, delegate_id, case_id = uuid4(), uuid4(), uuid4()
    users.update({owner_id, delegate_id})
    async with sessions() as session:
        await create_grant(session, publisher, None, owner_id, "case", case_id, "owner")

    delegated = await client.post(
        "/api/authority/delegations",
        headers=auth(owner_id),
        json={
            "delegate_id": str(delegate_id),
            "scope_type": "case",
            "scope_id": str(case_id),
            "role": "viewer",
        },
    )
    assert delegated.status_code == 201
    async with sessions() as session:
        assert (await check_access(session, delegate_id, "case", case_id, "view")).allowed

        expired = AuthorityGrant(
            grantor_id=owner_id,
            grantee_id=delegate_id,
            resource_type="document",
            resource_id=uuid4(),
            role="viewer",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        session.add(expired)
        await session.flush()
        expired_id = expired.id
        await session.commit()

    await expire_authority(sessions, publisher)
    async with sessions() as session:
        expired = await session.get(AuthorityGrant, expired_id)
        assert expired is not None and expired.revocation_reason == "expired"

    delegation_id = delegated.json()["delegation_id"]
    revoked = await client.delete(
        f"/api/authority/delegations/{delegation_id}", headers=auth(owner_id)
    )
    assert revoked.status_code == 204
    async with sessions() as session:
        delegation = await session.get(Delegation, UUID(delegation_id))
        assert delegation is not None and delegation.status == "revoked"


class AbortContext:
    async def abort(self, code, detail) -> None:
        raise RuntimeError((code, detail))


@pytest.mark.asyncio
async def test_grpc_registers_case_owner(authority_context) -> None:
    _, sessions, publisher, users = authority_context
    user_id, case_id = uuid4(), uuid4()
    users.add(user_id)
    servicer = AuthorityServicer(sessions, publisher)

    registered = await servicer.RegisterCaseOwner(
        authority_pb2.RegisterCaseOwnerRequest(user_id=str(user_id), case_id=str(case_id)),
        AbortContext(),
    )
    checked = await servicer.CheckAccess(
        authority_pb2.CheckAccessRequest(
            user_id=str(user_id),
            resource_type="case",
            resource_id=str(case_id),
            action="approve",
        ),
        AbortContext(),
    )

    assert registered.role == "owner"
    assert checked.allowed is True


@pytest.mark.asyncio
async def test_grant_and_delegation_guardrails(authority_context) -> None:
    _, sessions, publisher, _ = authority_context
    owner_id, delegate_id, outsider_id, case_id = uuid4(), uuid4(), uuid4(), uuid4()
    async with sessions() as session:
        owner = await create_grant(session, publisher, None, owner_id, "case", case_id, "owner")
        assert (
            await create_grant(session, publisher, None, owner_id, "case", case_id, "owner")
        ).id == owner.id

        with pytest.raises(ValueError, match="Active grant"):
            await create_grant(session, publisher, owner_id, owner_id, "case", case_id, "viewer")
        with pytest.raises(PermissionError, match="Delegation permission"):
            await create_grant(
                session, publisher, outsider_id, delegate_id, "case", case_id, "viewer"
            )
        with pytest.raises(PermissionError, match="cannot be revoked"):
            await revoke_grant(session, publisher, owner_id, owner, None)
        with pytest.raises(ValueError, match="yourself"):
            await create_delegation(
                session, publisher, owner_id, owner_id, "case", case_id, "viewer", [], None
            )
        with pytest.raises(ValueError, match="scope_id"):
            await create_delegation(
                session, publisher, owner_id, delegate_id, "case", None, "viewer", [], None
            )
        with pytest.raises(PermissionError, match="Delegation permission"):
            await create_delegation(
                session,
                publisher,
                outsider_id,
                delegate_id,
                "case",
                case_id,
                "viewer",
                [],
                None,
            )


@pytest.mark.asyncio
async def test_global_delegation_and_expired_delegation(authority_context) -> None:
    _, sessions, publisher, _ = authority_context
    owner_id, delegate_id, case_id = uuid4(), uuid4(), uuid4()
    async with sessions() as session:
        await create_grant(session, publisher, None, owner_id, "case", case_id, "owner")
        global_delegation = await create_delegation(
            session,
            publisher,
            owner_id,
            delegate_id,
            "all_cases",
            None,
            "viewer",
            [],
            None,
        )
        assert (await check_access(session, delegate_id, "case", case_id, "view")).allowed
        assert not (await check_access(session, delegate_id, "document", case_id, "view")).allowed

        scoped = await create_delegation(
            session,
            publisher,
            owner_id,
            uuid4(),
            "case",
            case_id,
            "viewer",
            [],
            datetime.now(UTC) - timedelta(seconds=1),
        )
        scoped_id = scoped.id
        await session.commit()

        with pytest.raises(PermissionError, match="delegator"):
            await revoke_delegation(session, publisher, delegate_id, global_delegation)

    await expire_authority(sessions, publisher)
    async with sessions() as session:
        expired = await session.get(Delegation, scoped_id)
        assert expired is not None and expired.status == "expired"
        cases = await list_user_cases(session, delegate_id)
        assert cases == []

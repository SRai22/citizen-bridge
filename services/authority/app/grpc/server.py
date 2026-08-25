from datetime import datetime
from uuid import UUID

import grpc
from contracts.generated import authority_pb2, authority_pb2_grpc
from grpc import aio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.kafka import EventPublisher
from app.models import AuthorityGrant
from app.service import (
    assign_case_coordinator,
    check_access,
    create_grant,
    list_case_users,
    list_user_cases,
    permissions_for,
    revoke_grant,
)

RESOURCE_TYPES = {"case", "person", "document", "household"}
ROLES = {"coordinator", "viewer"}
PERMISSIONS = {"view", "submit", "approve", "manage", "delegate", "delete"}


class AuthorityServicer(authority_pb2_grpc.AuthorityServiceServicer):
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        publisher: EventPublisher,
    ) -> None:
        self.sessions = sessions
        self.publisher = publisher

    async def CheckAccess(self, request, context):  # noqa: N802
        try:
            user_id = UUID(request.user_id)
            resource_id = UUID(request.resource_id)
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid UUID")
        if request.resource_type not in RESOURCE_TYPES or request.action not in PERMISSIONS:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid resource or action")
        async with self.sessions() as session:
            decision = await check_access(
                session, user_id, request.resource_type, resource_id, request.action
            )
        return authority_pb2.CheckAccessResponse(
            allowed=decision.allowed,
            role=decision.role,
            permissions=decision.permissions,
            limitations=decision.limitations,
        )

    async def GetUserCases(self, request, context):  # noqa: N802
        try:
            user_id = UUID(request.user_id)
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid user ID")
        async with self.sessions() as session:
            cases = await list_user_cases(session, user_id)
        return authority_pb2.CaseAccessList(
            cases=[
                authority_pb2.CaseAccess(
                    case_id=str(case_id),
                    role=role,
                    permissions=permissions_for(role, []),
                )
                for case_id, role, _ in cases
            ]
        )

    async def GetCaseUsers(self, request, context):  # noqa: N802
        try:
            case_id = UUID(request.case_id)
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid case ID")
        async with self.sessions() as session:
            user_ids = await list_case_users(session, case_id)
        return authority_pb2.CaseUserList(user_ids=[str(user_id) for user_id in user_ids])

    async def GrantAccess(self, request, context):  # noqa: N802
        try:
            actor_id = UUID(request.actor_user_id)
            grantee_id = UUID(request.grantee_id)
            resource_id = UUID(request.resource_id)
            expires_at = datetime.fromisoformat(request.expires_at) if request.expires_at else None
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid request value")
        if request.resource_type not in RESOURCE_TYPES or request.role not in ROLES:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid resource or role")
        async with self.sessions() as session:
            try:
                grant = await create_grant(
                    session,
                    self.publisher,
                    actor_id,
                    grantee_id,
                    request.resource_type,
                    resource_id,
                    request.role,
                    expires_at,
                )
            except PermissionError as exc:
                await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(exc))
            except ValueError as exc:
                await context.abort(grpc.StatusCode.ALREADY_EXISTS, str(exc))
        return _grant_response(grant)

    async def RevokeAccess(self, request, context):  # noqa: N802
        try:
            actor_id = UUID(request.actor_user_id)
            grant_id = UUID(request.grant_id)
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid UUID")
        async with self.sessions() as session:
            grant = await session.get(AuthorityGrant, grant_id)
            if grant is None:
                return authority_pb2.RevokeResponse(revoked=False)
            try:
                await revoke_grant(session, self.publisher, actor_id, grant, request.reason or None)
            except PermissionError as exc:
                await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(exc))
        return authority_pb2.RevokeResponse(revoked=True)

    async def RegisterCaseOwner(self, request, context):  # noqa: N802
        try:
            user_id = UUID(request.user_id)
            case_id = UUID(request.case_id)
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid UUID")
        async with self.sessions() as session:
            grant = await create_grant(
                session,
                self.publisher,
                None,
                user_id,
                "case",
                case_id,
                "owner",
            )
        return _grant_response(grant)

    async def RegisterCaseCoordinator(self, request, context):  # noqa: N802
        try:
            user_id = UUID(request.user_id)
            case_id = UUID(request.case_id)
            subject_person_id = (
                UUID(request.subject_person_id) if request.subject_person_id else None
            )
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid UUID")
        async with self.sessions() as session:
            grant = await assign_case_coordinator(
                session,
                self.publisher,
                user_id,
                case_id,
                subject_person_id,
                request.relationship or None,
            )
        return _grant_response(grant)


def _grant_response(grant: AuthorityGrant):
    return authority_pb2.GrantResponse(
        grant_id=str(grant.id),
        grantee_id=str(grant.grantee_id),
        resource_type=grant.resource_type,
        resource_id=str(grant.resource_id),
        role=grant.role,
        permissions=permissions_for(grant.role, grant.permissions),
    )


def create_server(
    port: int,
    sessions: async_sessionmaker[AsyncSession],
    publisher: EventPublisher,
) -> aio.Server:
    server = aio.server()
    authority_pb2_grpc.add_AuthorityServiceServicer_to_server(
        AuthorityServicer(sessions, publisher), server
    )
    server.add_insecure_port(f"[::]:{port}")
    return server

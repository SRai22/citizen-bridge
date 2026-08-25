import json
from dataclasses import dataclass

import grpc
from contracts.generated import (
    auth_pb2,
    auth_pb2_grpc,
    authority_pb2,
    authority_pb2_grpc,
    catalog_pb2,
    catalog_pb2_grpc,
)


@dataclass
class UserContext:
    user_id: str
    username: str


@dataclass
class AccessContext:
    allowed: bool
    role: str
    permissions: list[str]


class AuthClient:
    def __init__(self, target: str) -> None:
        self.channel = grpc.aio.insecure_channel(target)
        self.stub = auth_pb2_grpc.AuthServiceStub(self.channel)

    async def validate(self, token: str) -> UserContext | None:
        try:
            response = await self.stub.ValidateToken(auth_pb2.ValidateTokenRequest(token=token))
        except grpc.aio.AioRpcError as exc:
            raise ConnectionError("Auth service unavailable") from exc
        if not response.valid:
            return None
        return UserContext(response.user_id, response.username)

    async def check(self) -> None:
        await self.channel.channel_ready()

    async def close(self) -> None:
        await self.channel.close()


class AuthorityClient:
    def __init__(self, target: str) -> None:
        self.channel = grpc.aio.insecure_channel(target)
        self.stub = authority_pb2_grpc.AuthorityServiceStub(self.channel)

    async def check_access(self, user_id: str, case_id: str, action: str) -> AccessContext:
        try:
            response = await self.stub.CheckAccess(
                authority_pb2.CheckAccessRequest(
                    user_id=user_id,
                    resource_type="case",
                    resource_id=case_id,
                    action=action,
                )
            )
        except grpc.aio.AioRpcError as exc:
            raise ConnectionError("Authority service unavailable") from exc
        return AccessContext(response.allowed, response.role, list(response.permissions))

    async def case_access(self, user_id: str) -> list[tuple[str, str]]:
        try:
            response = await self.stub.GetUserCases(
                authority_pb2.GetUserCasesRequest(user_id=user_id)
            )
        except grpc.aio.AioRpcError as exc:
            raise ConnectionError("Authority service unavailable") from exc
        return [(item.case_id, item.role) for item in response.cases]

    async def register_owner(self, user_id: str, case_id: str) -> AccessContext:
        try:
            response = await self.stub.RegisterCaseOwner(
                authority_pb2.RegisterCaseOwnerRequest(user_id=user_id, case_id=case_id)
            )
        except grpc.aio.AioRpcError as exc:
            raise ConnectionError("Authority service unavailable") from exc
        return AccessContext(True, response.role, list(response.permissions))

    async def check(self) -> None:
        await self.channel.channel_ready()

    async def close(self) -> None:
        await self.channel.close()


class CatalogClient:
    def __init__(self, target: str) -> None:
        self.channel = grpc.aio.insecure_channel(target)
        self.stub = catalog_pb2_grpc.CatalogServiceStub(self.channel)

    async def list_applicable(self, profile: dict[str, object]) -> list[dict]:
        try:
            response = await self.stub.ListApplicableWorkflows(
                catalog_pb2.ProfileContext(profile_json=json.dumps(profile))
            )
        except grpc.aio.AioRpcError as exc:
            if exc.code() == grpc.StatusCode.INVALID_ARGUMENT:
                raise ValueError(exc.details()) from exc
            raise ConnectionError("Catalog service unavailable") from exc
        return [json.loads(workflow.definition_json) for workflow in response.workflows]

    async def check(self) -> None:
        await self.channel.channel_ready()

    async def close(self) -> None:
        await self.channel.close()

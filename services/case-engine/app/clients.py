import json
from dataclasses import dataclass, field

import grpc
import httpx
from contracts.generated import (
    ai_pb2,
    ai_pb2_grpc,
    auth_pb2,
    auth_pb2_grpc,
    authority_pb2,
    authority_pb2_grpc,
    catalog_pb2,
    catalog_pb2_grpc,
    documents_pb2,
    documents_pb2_grpc,
)


@dataclass
class UserContext:
    user_id: str
    username: str
    token: str = ""


@dataclass
class AccessContext:
    allowed: bool
    role: str
    permissions: list[str]
    limitations: list[str] = field(default_factory=list)


class AuthClient:
    def __init__(self, target: str, http_url: str = "", internal_token: str = "") -> None:
        self.channel = grpc.aio.insecure_channel(target)
        self.stub = auth_pb2_grpc.AuthServiceStub(self.channel)
        self.http = httpx.AsyncClient(base_url=http_url) if http_url else None
        self.internal_token = internal_token

    async def validate(self, token: str) -> UserContext | None:
        try:
            response = await self.stub.ValidateToken(auth_pb2.ValidateTokenRequest(token=token))
        except grpc.aio.AioRpcError as exc:
            raise ConnectionError("Auth service unavailable") from exc
        if not response.valid:
            return None
        return UserContext(response.user_id, response.username, token)

    async def profile(self, user: UserContext) -> dict:
        if self.http is None:
            raise ConnectionError("Auth profile service unavailable")
        try:
            response = await self.http.get(
                "/api/auth/me/profile", headers={"Authorization": f"Bearer {user.token}"}
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ConnectionError("Auth profile service unavailable") from exc
        return response.json()

    async def profile_by_user(self, user_id: str) -> dict:
        if self.http is None:
            raise ConnectionError("Auth profile service unavailable")
        try:
            response = await self.http.get(
                f"/api/auth/users/{user_id}/profile",
                headers={"X-Internal-Service-Token": self.internal_token},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ConnectionError("Auth profile service unavailable") from exc
        return response.json()

    async def check(self) -> None:
        await self.channel.channel_ready()

    async def close(self) -> None:
        if self.http:
            await self.http.aclose()
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
        return AccessContext(
            response.allowed,
            response.role,
            list(response.permissions),
            list(response.limitations),
        )

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
        return AccessContext(True, response.role, list(response.permissions), [])

    async def register_coordinator(
        self,
        user_id: str,
        case_id: str,
        subject_person_id: str = "",
        relationship: str = "",
    ) -> AccessContext:
        try:
            response = await self.stub.RegisterCaseCoordinator(
                authority_pb2.RegisterCaseCoordinatorRequest(
                    user_id=user_id,
                    case_id=case_id,
                    subject_person_id=subject_person_id,
                    relationship=relationship,
                )
            )
        except grpc.aio.AioRpcError as exc:
            raise ConnectionError("Authority service unavailable") from exc
        return AccessContext(
            True,
            response.role,
            list(response.permissions),
            [
                "Cannot approve legal declarations",
                "Cannot authorize payments or delete the case",
            ],
        )

    async def check(self) -> None:
        await self.channel.channel_ready()

    async def close(self) -> None:
        await self.channel.close()


class CatalogClient:
    def __init__(self, target: str, http_url: str = "") -> None:
        self.channel = grpc.aio.insecure_channel(target)
        self.stub = catalog_pb2_grpc.CatalogServiceStub(self.channel)
        self.http = httpx.AsyncClient(base_url=http_url) if http_url else None

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

    async def benefits(self) -> list[dict]:
        return (await self._get("/api/catalog/benefits"))["benefits"]

    async def benefit(self, benefit_id: str) -> dict | None:
        try:
            return await self._get(f"/api/catalog/benefits/{benefit_id}")
        except KeyError:
            return None

    async def workflow(self, workflow_id: str) -> dict:
        return await self._get(f"/api/catalog/workflows/{workflow_id}")

    async def _get(self, path: str) -> dict:
        if self.http is None:
            raise ConnectionError("Catalog HTTP service unavailable")
        try:
            response = await self.http.get(path)
            if response.status_code == 404:
                raise KeyError(path)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ConnectionError("Catalog service unavailable") from exc
        return response.json()

    async def check(self) -> None:
        await self.channel.channel_ready()

    async def close(self) -> None:
        if self.http:
            await self.http.aclose()
        await self.channel.close()


class DocumentsClient:
    def __init__(self, target: str) -> None:
        self.channel = grpc.aio.insecure_channel(target)
        self.stub = documents_pb2_grpc.DocumentServiceStub(self.channel)

    async def check_requirements(self, user_id: str, document_types: list[str]) -> dict:
        try:
            response = await self.stub.CheckRequirements(
                documents_pb2.CheckRequirementsRequest(
                    user_id=user_id, document_types=document_types
                )
            )
        except grpc.aio.AioRpcError as exc:
            raise ConnectionError("Documents service unavailable") from exc
        return {
            "available": list(response.available_types),
            "missing": list(response.missing_types),
        }

    async def check(self) -> None:
        await self.channel.channel_ready()

    async def close(self) -> None:
        await self.channel.close()


class AIClient:
    def __init__(self, target: str) -> None:
        self.channel = grpc.aio.insecure_channel(target)
        self.stub = ai_pb2_grpc.AIServiceStub(self.channel)

    async def interpret_rejection(self, task_id: str, rejection_text: str) -> dict:
        try:
            response = await self.stub.InterpretRejection(
                ai_pb2.InterpretRejectionRequest(task_id=task_id, rejection_text=rejection_text)
            )
        except grpc.aio.AioRpcError as exc:
            raise ConnectionError("AI service unavailable") from exc
        return {"reason": response.reason, "remediation_steps": list(response.remediation_steps)}

    async def check(self) -> None:
        await self.channel.channel_ready()

    async def close(self) -> None:
        await self.channel.close()

import os
from collections.abc import AsyncIterator
from uuid import UUID

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("OTEL_ENABLED", "false")

from app.api import ai_client, auth_client, authority_client, catalog_client, publisher
from app.clients import AccessContext, UserContext
from app.db.base import Base
from app.db.session import get_session
from app.main import app


class FakeAuth:
    def __init__(self, users: set[UUID]) -> None:
        self.users = users

    async def validate(self, token: str) -> UserContext | None:
        try:
            user_id = UUID(token)
        except ValueError:
            return None
        return UserContext(str(user_id), "test-user") if user_id in self.users else None


class FakeAuthority:
    def __init__(self) -> None:
        self.access: dict[UUID, dict[UUID, str]] = {}

    async def register_owner(self, user_id: str, case_id: str) -> AccessContext:
        self.access.setdefault(UUID(user_id), {})[UUID(case_id)] = "owner"
        return AccessContext(True, "owner", ["view", "submit", "approve", "manage"])

    async def register_coordinator(
        self,
        user_id: str,
        case_id: str,
        subject_person_id: str = "",
        relationship: str = "",
    ) -> AccessContext:
        self.access.setdefault(UUID(user_id), {})[UUID(case_id)] = "coordinator"
        return AccessContext(
            True,
            "coordinator",
            ["view", "submit", "manage"],
            ["Cannot approve legal declarations"],
        )

    async def check_access(self, user_id: str, case_id: str, action: str) -> AccessContext:
        role = self.access.get(UUID(user_id), {}).get(UUID(case_id), "")
        permissions = (
            ["view", "submit", "approve", "manage"]
            if role == "owner"
            else ["view", "submit", "manage"]
            if role == "coordinator"
            else []
        )
        return AccessContext(action in permissions, role, permissions)

    async def case_access(self, user_id: str) -> list[tuple[str, str]]:
        return [
            (str(case_id), role) for case_id, role in self.access.get(UUID(user_id), {}).items()
        ]


class FakePublisher:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    async def publish(self, topic: str, event: dict[str, object]) -> None:
        self.events.append((topic, event))


class FakeCatalog:
    async def list_applicable(self, profile: dict[str, object]) -> list[dict]:
        if profile.get("location", {}).get("state") != "Karnataka":
            raise ValueError(
                "Workflow 'family_pension' requires inactive workflow(s): death_certificate"
            )
        values = (
            ("death_certificate", "death_registration", "Obtain Death Certificate", 7, []),
            (
                "family_pension",
                "family_pension_application",
                "Apply for Family Pension",
                30,
                ["death_certificate"],
            ),
            (
                "bescom_transfer",
                "bescom_name_transfer",
                "Transfer BESCOM Account",
                15,
                ["death_certificate"],
            ),
            (
                "ration_card",
                "ration_card_modification",
                "Update Ration Card",
                30,
                ["death_certificate"],
            ),
        )
        return [
            {
                "id": workflow_id,
                "description": title,
                "tasks": [
                    {
                        "id": task_id,
                        "name": title,
                        "estimated_duration_days": days,
                    }
                ],
                "inter_workflow_dependencies": dependencies,
                "stages": [
                    {"id": "submitted", "label": "Submitted", "order": 1},
                    {"id": "under_review", "label": "Under Review", "order": 2},
                    {"id": "issued", "label": "Issued", "order": 3},
                ],
                "typical_duration_days": [max(1, days // 2), days],
            }
            for workflow_id, task_id, title, days, dependencies in values
        ]


class FakeAI:
    async def interpret_rejection(self, task_id: str, rejection_text: str) -> dict:
        return {
            "reason": "A Legal Heir Certificate is required.",
            "remediation_steps": ["add_task:legal_heir_certificate:bescom_transfer"],
        }


@pytest_asyncio.fixture
async def case_context():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        execution_options={"schema_translate_map": {"cases": None}},
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    users: set[UUID] = set()
    auth = FakeAuth(users)
    authority = FakeAuthority()
    events = FakePublisher()
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[auth_client] = lambda: auth
    app.dependency_overrides[authority_client] = lambda: authority
    app.dependency_overrides[catalog_client] = lambda: FakeCatalog()
    app.dependency_overrides[ai_client] = lambda: FakeAI()
    app.dependency_overrides[publisher] = lambda: events
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, sessions, users, authority, events
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

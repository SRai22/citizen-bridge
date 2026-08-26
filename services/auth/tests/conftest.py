import os
from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("JWT_SECRET", "test-only-secret-with-at-least-32-characters")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-internal-token")
os.environ.setdefault("OTP_DEMO_CODE", "123456")

from app.api import get_catalog, get_data_services, get_publisher
from app.db.base import Base
from app.db.session import get_session
from app.main import app


class FakePublisher:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def publish(self, event: dict[str, object]) -> None:
        self.events.append(event)


class FakeCatalog:
    async def benefit_requirements(self) -> dict[str, int]:
        return {"annual_income": 3, "date_of_birth": 4}


class FakeDataServices:
    async def export(self, user_id: str) -> dict[str, object]:
        return {"cases": [], "documents": []}


@pytest_asyncio.fixture
async def api_context() -> AsyncIterator[tuple[AsyncClient, FakePublisher, async_sessionmaker]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        execution_options={"schema_translate_map": {"auth": None}},
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    publisher = FakePublisher()
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_publisher] = lambda: publisher
    app.dependency_overrides[get_catalog] = lambda: FakeCatalog()
    app.dependency_overrides[get_data_services] = lambda: FakeDataServices()
    app.state.session_factory = sessions
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, publisher, sessions
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

import os
from collections.abc import AsyncIterator
from types import SimpleNamespace
from uuid import UUID

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("OTEL_ENABLED", "false")

from app.api import auth_client, publisher
from app.db.base import Base
from app.db.session import get_session
from app.main import app


class FakeAuth:
    async def validate(self, token: str):
        try:
            user_id = UUID(token)
        except ValueError:
            return SimpleNamespace(valid=False, user_id="")
        return SimpleNamespace(valid=True, user_id=str(user_id))


class FakePublisher:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def publish(self, event: dict) -> None:
        self.events.append(event)


@pytest_asyncio.fixture
async def document_context():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        execution_options={"schema_translate_map": {"documents": None}},
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    events = FakePublisher()
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[auth_client] = lambda: FakeAuth()
    app.dependency_overrides[publisher] = lambda: events
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, sessions, events
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

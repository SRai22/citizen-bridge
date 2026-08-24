import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SERVICE_NAME", "test-service")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@postgres/test")
os.environ.setdefault("JWT_SECRET", "test-only-secret-with-at-least-32-characters")
os.environ.setdefault("ENABLE_WEBSOCKET", "true")

from app.main import app


async def healthy() -> None:
    return None


@pytest.fixture
def client() -> Iterator[TestClient]:
    original = app.state.health_checks
    app.state.health_checks = {"database": healthy, "kafka": healthy}
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.state.health_checks = original

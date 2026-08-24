import pytest
from app.config import Settings
from pydantic import ValidationError


def test_rejects_placeholder_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(
            service_name="test",
            database_url="postgresql+asyncpg://test:test@postgres/test",
            jwt_secret="change-me-in-production",
        )

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Keep async tests on the asyncio backend used by the application."""
    return "asyncio"

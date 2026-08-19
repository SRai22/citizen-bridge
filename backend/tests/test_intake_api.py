from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai import IntakeAgent
from app.api.intake import sessions as intake_sessions
from app.db.session import create_database_engine, get_session, init_db
from app.main import create_app
from app.models import Case, Task


@pytest.mark.anyio
async def test_openai_request_uses_strict_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOCK_AI", "false")
    create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=('{"status":"in_progress","message":"Which city?","profile":null}')
                    )
                )
            ]
        )
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    result = await IntakeAgent(cast(Any, client)).reply(
        [{"role": "user", "content": "My father passed away"}]
    )

    response_format = create.await_args.kwargs["response_format"]
    assert result.status == "in_progress"
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert "profile" in response_format["json_schema"]["schema"]["properties"]


@pytest.fixture
async def intake_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession]]]:
    monkeypatch.setenv("MOCK_AI", "true")
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'intake.db'}")
    await init_db(engine)
    database_sessions = async_sessionmaker(engine, expire_on_commit=False)
    application = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with database_sessions() as session:
            yield session

    application.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        yield client, database_sessions
    intake_sessions.clear()
    await engine.dispose()


@pytest.mark.anyio
async def test_mock_intake_creates_case_and_activates_all_workflows(
    intake_context: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, database_sessions = intake_context
    started = await client.post("/api/intake/start")

    assert started.status_code == 201
    session_id = started.json()["session_id"]
    assert started.json()["status"] == "in_progress"
    assert "sorry" in started.json()["message"].lower()

    replies = [
        "My father passed away",
        "Bengaluru, Karnataka",
        "He was a retired state government employee receiving a pension",
        "My mother is alive; father held the BESCOM connection and ration card",
    ]
    response = started
    for reply in replies:
        response = await client.post(
            f"/api/intake/{session_id}/message",
            json={"message": reply},
        )
        assert response.status_code == 200

    completed = response.json()
    assert completed["status"] == "complete"
    assert completed["profile"]["location"] == {
        "city": "Bengaluru",
        "state": "Karnataka",
    }
    assert completed["profile"]["assets"]["bescom"] is True

    clarified = await client.post(
        f"/api/intake/{session_id}/message",
        json={"message": "I need to correct one detail"},
    )
    assert clarified.status_code == 200
    assert clarified.json()["status"] == "complete"

    confirmed = await client.post(f"/api/intake/{session_id}/confirm")
    assert confirmed.status_code == 200
    case_id = UUID(confirmed.json()["case_id"])
    assert (await client.post(f"/api/intake/{session_id}/confirm")).json() == confirmed.json()

    async with database_sessions() as session:
        case = await session.get(Case, case_id)
        tasks = list((await session.scalars(select(Task).where(Task.case_id == case_id))).all())

    assert case is not None
    assert case.status.value == "active"
    assert {task.workflow_id for task in tasks} == {
        "death_certificate",
        "family_pension",
        "bescom_transfer",
        "ration_card",
    }


@pytest.mark.anyio
async def test_incomplete_unknown_and_unavailable_intakes_return_clear_errors(
    intake_context: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = intake_context
    session_id = (await client.post("/api/intake/start")).json()["session_id"]

    assert (await client.post(f"/api/intake/{session_id}/confirm")).status_code == 409
    assert (await client.post(f"/api/intake/{uuid4()}/confirm")).status_code == 404

    monkeypatch.setenv("MOCK_AI", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    unavailable = await client.post(
        f"/api/intake/{session_id}/message",
        json={"message": "My father passed away"},
    )

    assert unavailable.status_code == 503
    assert "temporarily unavailable" in unavailable.json()["detail"]

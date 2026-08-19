"""Tests for demo seed and reset API endpoints."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import create_database_engine, init_db
from app.main import create_app


@pytest.fixture
async def demo_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'demo.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url.replace("+aiosqlite", ""))
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("MOCK_AI", "true")

    engine = create_database_engine(db_url)
    await init_db(engine)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    from app.db.session import get_session

    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    await engine.dispose()


@pytest.mark.anyio
async def test_reset_clears_all_data(demo_client: AsyncClient) -> None:
    # Seed first so there's data to clear
    seed_resp = await demo_client.post("/api/demo/seed")
    assert seed_resp.status_code == 200

    reset_resp = await demo_client.post("/api/demo/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "ok"

    # Seeding again should work (tables are empty, not dropped)
    seed_resp2 = await demo_client.post("/api/demo/seed")
    assert seed_resp2.status_code == 200


@pytest.mark.anyio
async def test_seed_initial_creates_case_with_four_workflows(demo_client: AsyncClient) -> None:
    resp = await demo_client.post("/api/demo/seed", params={"state": "initial"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "initial"
    assert data["tasks"] >= 4

    case_resp = await demo_client.get(f"/api/cases/{data['case_id']}")
    assert case_resp.status_code == 200
    case = case_resp.json()
    assert case["status"] == "active"
    workflow_ids = {t["workflow_id"] for t in case["tasks"]}
    assert "death_certificate" in workflow_ids
    assert "family_pension" in workflow_ids
    assert "bescom_transfer" in workflow_ids
    assert "ration_card" in workflow_ids


@pytest.mark.anyio
async def test_seed_after_death_cert(demo_client: AsyncClient) -> None:
    resp = await demo_client.post("/api/demo/seed", params={"state": "after_death_cert"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "after_death_cert"

    case_resp = await demo_client.get(f"/api/cases/{data['case_id']}")
    case = case_resp.json()

    tasks_by_wf = {t["workflow_id"]: t for t in case["tasks"]}
    assert tasks_by_wf["death_certificate"]["status"] == "completed"
    assert tasks_by_wf["family_pension"]["status"] == "ready"
    assert tasks_by_wf["bescom_transfer"]["status"] == "ready"
    assert tasks_by_wf["ration_card"]["status"] == "ready"

    assert len(case["documents"]) >= 1
    assert any(d["document_type"] == "death_certificate" for d in case["documents"])


@pytest.mark.anyio
async def test_seed_after_bescom_rejection(demo_client: AsyncClient) -> None:
    resp = await demo_client.post("/api/demo/seed", params={"state": "after_bescom_rejection"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "after_bescom_rejection"

    case_resp = await demo_client.get(f"/api/cases/{data['case_id']}")
    case = case_resp.json()

    tasks_by_wf = {t["workflow_id"]: t for t in case["tasks"]}
    assert tasks_by_wf["death_certificate"]["status"] == "completed"
    assert tasks_by_wf["bescom_transfer"]["status"] == "blocked"
    assert "legal_heir_certificate" in tasks_by_wf
    assert tasks_by_wf["legal_heir_certificate"]["status"] == "ready"


@pytest.mark.anyio
async def test_reset_then_seed_is_idempotent(demo_client: AsyncClient) -> None:
    for _ in range(3):
        await demo_client.post("/api/demo/reset")
        resp = await demo_client.post("/api/demo/seed")
        assert resp.status_code == 200
        assert resp.json()["tasks"] >= 4


@pytest.mark.anyio
async def test_demo_disabled_returns_403(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'nodemo.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url.replace("+aiosqlite", ""))
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("MOCK_AI", "true")

    engine = create_database_engine(db_url)
    await init_db(engine)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    from app.db.session import get_session

    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/demo/reset")).status_code == 403
        assert (await client.post("/api/demo/seed")).status_code == 403

    await engine.dispose()

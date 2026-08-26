from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from contracts.generated import documents_pb2
from contracts.lib.events import EventConsumer
from sqlalchemy import select

from app.grpc.server import DocumentServicer
from app.models import Document, ProcessedEvent
from app.service import consume_task_completed, expire_documents


def headers(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


class AbortContext:
    async def abort(self, code, detail) -> None:
        raise RuntimeError((code, detail))


@pytest.mark.asyncio
async def test_document_lifecycle(document_context) -> None:
    client, _, events = document_context
    user_id, other_id = uuid4(), uuid4()

    uploaded = await client.post(
        "/api/docs/upload",
        headers=headers(user_id),
        json={"document_type": "aadhaar", "title": "Aadhaar — Asha Rao"},
    )
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]
    assert uploaded.json()["proof_category"] == "identity"
    assert uploaded.json()["provenance_type"] == "user_uploaded"

    forbidden = await client.get(f"/api/docs/{document_id}", headers=headers(other_id))
    assert forbidden.status_code == 404
    detail = await client.get(f"/api/docs/{document_id}", headers=headers(user_id))
    assert detail.status_code == 200
    assert detail.json()["usage_history"][0]["action"] == "viewed"

    accessed = await client.post(
        f"/api/docs/{document_id}/access",
        headers=headers(user_id),
        json={"action": "shared", "purpose": "Pension application", "recipient": "Treasury"},
    )
    assert accessed.status_code == 201
    access_log = await client.get(f"/api/docs/{document_id}/access-log", headers=headers(user_id))
    assert len(access_log.json()["accesses"]) == 2
    shares = await client.get("/api/docs/shares", headers=headers(user_id))
    assert shares.json()["active_shares"][0]["shared_with"] == "Treasury"
    revoked = await client.post(
        f"/api/docs/shares/{accessed.json()['id']}/revoke", headers=headers(user_id)
    )
    assert revoked.json()["revoked"] is True
    assert (await client.get("/api/docs/shares", headers=headers(user_id))).json() == {
        "active_shares": []
    }

    missing = await client.post(
        "/api/docs/check-requirements",
        headers=headers(user_id),
        json={"user_id": str(user_id), "requirements": [{"type": "aadhaar"}]},
    )
    assert missing.json()["requirements"][0]["status"] == "missing"

    superseded = await client.post(
        f"/api/docs/{document_id}/supersede",
        headers=headers(user_id),
        json={"new_document_data": {"document_type": "aadhaar", "title": "New Aadhaar"}},
    )
    assert superseded.status_code == 201, superseded.text
    listed = await client.get("/api/docs", headers=headers(user_id))
    assert [item["title"] for item in listed.json()["documents_by_category"]["identity"]] == [
        "New Aadhaar"
    ]
    assert [event["event_type"] for event in events.events].count("document.accessed") == 2


@pytest.mark.asyncio
async def test_task_documents_requirements_and_expiration(document_context) -> None:
    _, sessions, events = document_context
    user_id, task_id, case_id = uuid4(), uuid4(), uuid4()
    event = {
        "event_type": "task.completed",
        "owner_user_id": str(user_id),
        "task_id": str(task_id),
        "case_id": str(case_id),
        "task_type": "death_registration",
    }
    async with sessions() as session:
        await consume_task_completed(session, events, event)
        await consume_task_completed(session, events, event)
        rows = (await session.scalars(select(Document))).all()
        assert len(rows) == 1
        assert rows[0].verification_status == "verified"
        rows[0].valid_until = datetime.now(UTC) - timedelta(days=1)
        await session.commit()

    await expire_documents(sessions, events)
    async with sessions() as session:
        document = await session.scalar(select(Document))
        assert document.verification_status == "expired"
    assert events.events[-1]["event_type"] == "document.expired"
    assert any(event["event_type"] == "document.verified" for event in events.events)


@pytest.mark.asyncio
async def test_grpc_checks_document_requirements(document_context) -> None:
    _, sessions, events = document_context
    user_id, task_id, case_id = uuid4(), uuid4(), uuid4()
    async with sessions() as session:
        await consume_task_completed(
            session,
            events,
            {
                "event_type": "task.completed",
                "owner_user_id": str(user_id),
                "task_id": str(task_id),
                "case_id": str(case_id),
                "task_type": "death_registration",
            },
        )

    response = await DocumentServicer(sessions, events).CheckRequirements(
        documents_pb2.CheckRequirementsRequest(
            user_id=str(user_id), document_types=["death_certificate", "aadhaar"]
        ),
        AbortContext(),
    )

    assert response.available_types == ["death_certificate"]
    assert response.missing_types == ["aadhaar"]


@pytest.mark.asyncio
async def test_consumer_tracks_processed_events(document_context) -> None:
    _, sessions, _ = document_context
    consumer = EventConsumer(
        "unused:9092",
        "documents-test",
        ("tasks",),
        sessions,
        ProcessedEvent,
    )
    event_id = str(uuid4())

    assert await consumer._seen(event_id) is False
    await consumer._mark(event_id)
    assert await consumer._seen(event_id) is True

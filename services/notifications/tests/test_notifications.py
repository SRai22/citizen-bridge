from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models import Notification
from app.service import generate_weekly_digests, handle_event
from app.websocket import ConnectionManager


class FakeAuthority:
    def __init__(self, users: list[str]) -> None:
        self.users = users

    async def case_users(self, case_id: str) -> list[str]:
        return self.users


class FakeBroadcaster:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict]] = []

    async def broadcast_to_user(self, user_id: str, message: dict) -> None:
        self.messages.append((user_id, message))


class FakeSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.messages: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        self.messages.append(message)


def headers(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


@pytest.mark.asyncio
async def test_event_to_api_and_digest(notification_context) -> None:
    client, sessions = notification_context
    user_id, other_id, case_id = uuid4(), uuid4(), uuid4()
    broadcast = FakeBroadcaster()
    event = {
        "event_id": str(uuid4()),
        "event_type": "task.completed",
        "case_id": str(case_id),
        "task_id": str(uuid4()),
        "title": "Death Certificate",
        "new_status": "completed",
    }
    async with sessions() as session:
        created = await handle_event(
            session,
            broadcast,
            FakeAuthority([str(user_id), str(other_id)]),
            event,
        )
    assert len(created) == 2
    assert len(broadcast.messages) == 2
    assert broadcast.messages[0][1]["type"] == "notification"

    listed = await client.get(
        "/api/notifications", headers=headers(user_id), params={"unread_only": "true"}
    )
    assert listed.status_code == 200
    assert listed.json()["unread_count"] == 1
    notification_id = listed.json()["notifications"][0]["id"]

    read = await client.patch(
        f"/api/notifications/{notification_id}/read", headers=headers(user_id)
    )
    assert read.status_code == 204
    assert (await client.get("/api/notifications", headers=headers(user_id))).json()[
        "unread_count"
    ] == 0

    preferences = await client.patch(
        "/api/notifications/preferences",
        headers=headers(user_id),
        json={"digest_enabled": True, "digest_day": "monday"},
    )
    assert preferences.json()["digest_day"] == "monday"
    summary = await client.get("/api/notifications/digest", headers=headers(user_id))
    assert len(summary.json()["completions"]) == 1

    await generate_weekly_digests(sessions, broadcast, "monday")
    await generate_weekly_digests(sessions, broadcast, "monday")
    async with sessions() as session:
        digest_count = await session.scalar(
            select(func.count()).select_from(Notification).where(
                Notification.user_id == user_id,
                Notification.notification_type == "digest",
            )
        )
    assert digest_count == 1

    activity = await client.get(
        "/api/notifications/activity",
        headers=headers(user_id),
        params={"category": "submissions", "limit": 1},
    )
    assert activity.status_code == 200
    assert activity.json()["activities"][0]["activity_type"] == "task_completed"
    assert activity.json()["groups"][0]["activities"][0]["case_id"] == str(case_id)


@pytest.mark.asyncio
async def test_activity_audit_is_user_scoped_and_granular(notification_context) -> None:
    client, sessions = notification_context
    user_id, other_id, document_id = uuid4(), uuid4(), uuid4()
    event = {
        "event_id": str(uuid4()),
        "event_type": "document.accessed",
        "owner_user_id": str(user_id),
        "document_id": str(document_id),
        "document_title": "Income Certificate",
        "action": "shared",
        "recipient": "Pension Department",
        "purpose": "Eligibility verification",
        "data_fields_accessed": ["annual_income"],
    }
    async with sessions() as session:
        await handle_event(session, FakeBroadcaster(), FakeAuthority([]), event)

    own = await client.get(
        "/api/notifications/audit-log",
        headers=headers(user_id),
        params={"category": "sharing", "document_id": str(document_id)},
    )
    assert own.status_code == 200
    assert own.json()["entries"][0]["details"]["purpose"] == "Eligibility verification"
    assert own.json()["entries"][0]["details"]["data_fields_accessed"] == [
        "annual_income"
    ]
    hidden = await client.get("/api/notifications/activity", headers=headers(other_id))
    assert hidden.json()["activities"] == []


@pytest.mark.asyncio
async def test_connection_manager_broadcasts() -> None:
    manager = ConnectionManager()
    socket = FakeSocket()
    await manager.connect(socket, "user-1")
    await manager.broadcast_to_user("user-1", {"type": "notification"})
    assert socket.accepted is True
    assert socket.messages == [{"type": "notification"}]
    manager.disconnect(socket, "user-1")
    assert "user-1" not in manager.connections

from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients import AuthorityClient
from app.models import Notification, NotificationPreference
from app.schemas import NotificationCreate, NotificationResponse, PreferencePatch


class Broadcaster(Protocol):
    async def broadcast_to_user(self, user_id: str, message: dict) -> None: ...


class Publisher(Protocol):
    async def publish(self, event: dict) -> None: ...


async def preference(session: AsyncSession, user_id: UUID) -> NotificationPreference:
    result = await session.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    if result is None:
        result = NotificationPreference(user_id=user_id)
        session.add(result)
        await session.commit()
        await session.refresh(result)
    return result


async def update_preference(
    session: AsyncSession, user_id: UUID, patch: PreferencePatch
) -> NotificationPreference:
    result = await preference(session, user_id)
    for key, value in patch.model_dump(exclude_none=True).items():
        setattr(result, key, value)
    await session.commit()
    await session.refresh(result)
    return result


async def create_notification(
    session: AsyncSession,
    broadcaster: Broadcaster,
    payload: NotificationCreate,
    publisher: Publisher | None = None,
) -> Notification:
    notification = Notification(**payload.model_dump())
    session.add(notification)
    await session.commit()
    await session.refresh(notification)
    if publisher:
        await publisher.publish(
            {
                "event_type": "notification.created",
                "notification_id": str(notification.id),
                "user_id": str(notification.user_id),
                "notification_type": notification.notification_type,
                "priority": notification.priority,
                "timestamp": notification.created_at.isoformat(),
            }
        )
    settings = await preference(session, payload.user_id)
    category_enabled = settings.categories.get(payload.notification_type, True)
    should_push = settings.push_enabled and category_enabled
    if payload.priority == "urgent":
        should_push = should_push and settings.urgent_push
    if should_push:
        await broadcaster.broadcast_to_user(str(payload.user_id), websocket_message(notification))
    return notification


async def mark_read(session: AsyncSession, notification: Notification) -> None:
    if not notification.read:
        notification.read = True
        notification.read_at = datetime.now(UTC)
        await session.commit()


async def handle_event(
    session: AsyncSession,
    broadcaster: Broadcaster,
    authority: AuthorityClient,
    event: dict,
    publisher: Publisher | None = None,
) -> list[Notification]:
    routed = await route_event(authority, event)
    return [
        await create_notification(
            session,
            broadcaster,
            NotificationCreate(user_id=UUID(user_id), **draft),
            publisher,
        )
        for user_id, draft in routed
    ]


async def route_event(authority: AuthorityClient, event: dict) -> list[tuple[str, dict]]:
    event_type = str(event.get("event_type", ""))
    status = str(event.get("new_status", ""))
    users: list[str]
    draft: dict
    if event_type.startswith("task."):
        if not event.get("case_id"):
            return []
        users = await authority.case_users(str(event["case_id"]))
        title = str(event.get("title") or "Task")
        if event_type == "task.completed" or status == "completed":
            draft = _draft(
                "task_status", "normal", f"{title} completed", "This task is complete.", event
            )
        elif event_type == "task.failed" or status == "failed":
            draft = _draft(
                "rejection",
                "urgent",
                f"{title} was not successful",
                "Review the task for next steps.",
                event,
            )
        elif status == "ready":
            draft = _draft(
                "task_status",
                "normal",
                f"{title} is ready",
                "This task is ready for action.",
                event,
            )
        else:
            return []
    elif event_type in {"document.created", "document.expired"}:
        owner = event.get("owner_user_id")
        if not owner:
            return []
        users = [str(owner)]
        title = (
            str(event.get("title") or event.get("document_type", "Document"))
            .replace("_", " ")
            .title()
        )
        draft = (
            _draft(
                "deadline",
                "urgent",
                f"{title} expired",
                "Upload or fetch a current version.",
                event,
            )
            if event_type == "document.expired"
            else _draft(
                "document_issued",
                "low",
                f"New document: {title}",
                "A new document was added to your profile.",
                event,
            )
        )
    elif event_type in {"authority.granted", "authority.revoked"}:
        grantee = event.get("grantee_id")
        if not grantee:
            return []
        users = [str(grantee)]
        resource = str(event.get("resource_id", "resource"))
        draft = (
            _draft(
                "security",
                "urgent",
                "Access revoked",
                f"Your access to {resource} was revoked.",
                event,
            )
            if event_type == "authority.revoked"
            else _draft(
                "security",
                "normal",
                "Access granted",
                f"You were granted access to {resource}.",
                event,
            )
        )
    else:
        return []
    return [(user_id, draft) for user_id in dict.fromkeys(users)]


def _draft(kind: str, priority: str, title: str, body: str, event: dict) -> dict:
    return {
        "notification_type": kind,
        "priority": priority,
        "title": title,
        "body": body,
        "data": event,
    }


def week_bounds(week: str | None) -> tuple[str, datetime, datetime]:
    if week:
        try:
            year, number = week.split("-W")
            monday = date.fromisocalendar(int(year), int(number), 1)
        except (ValueError, TypeError) as exc:
            raise ValueError("Week must use ISO format YYYY-Www") from exc
    else:
        today = datetime.now(UTC).date()
        year, number, _ = today.isocalendar()
        monday = date.fromisocalendar(year, number, 1)
        week = f"{year}-W{number:02d}"
    start = datetime.combine(monday, time.min, tzinfo=UTC)
    return week, start, start + timedelta(days=7)


async def digest(session: AsyncSession, user_id: UUID, week: str | None = None) -> dict:
    week, start, end = week_bounds(week)
    rows = (
        await session.scalars(
            select(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.created_at >= start,
                Notification.created_at < end,
                Notification.notification_type != "digest",
            )
            .order_by(Notification.created_at.desc())
        )
    ).all()
    groups = {
        key: []
        for key in ("ready_actions", "new_opportunities", "status_updates", "completions")
    }
    for item in rows:
        if item.notification_type == "benefit_discovered":
            group = "new_opportunities"
        elif item.data.get("new_status") == "ready" or item.priority == "urgent":
            group = "ready_actions"
        elif (
            item.data.get("new_status") == "completed"
            or item.data.get("event_type") == "task.completed"
        ):
            group = "completions"
        else:
            group = "status_updates"
        groups[group].append(NotificationResponse.model_validate(item).model_dump(mode="json"))
    return {"week": week, **groups}


async def generate_weekly_digests(
    sessions: async_sessionmaker[AsyncSession],
    broadcaster: Broadcaster,
    run_day: str | None = None,
    publisher: Publisher | None = None,
) -> None:
    async with sessions() as session:
        user_ids = (
            await session.scalars(select(distinct(Notification.user_id)))
        ).all()
        for user_id in user_ids:
            settings = await preference(session, user_id)
            if not settings.digest_enabled or run_day and settings.digest_day != run_day:
                continue
            summary = await digest(session, user_id)
            existing = (
                await session.scalars(
                    select(Notification).where(
                        Notification.user_id == user_id,
                        Notification.notification_type == "digest",
                    )
                )
            ).all()
            if any(item.data.get("week") == summary["week"] for item in existing):
                continue
            await create_notification(
                session,
                broadcaster,
                NotificationCreate(
                    user_id=user_id,
                    notification_type="digest",
                    priority="low",
                    title=f"Weekly summary — {summary['week']}",
                    body="Your weekly Citizen Bridge summary is ready.",
                    data=summary,
                ),
                publisher,
            )


def websocket_message(notification: Notification) -> dict:
    return {
        "type": "notification",
        "notification_id": str(notification.id),
        "notification_type": notification.notification_type,
        "priority": notification.priority,
        "title": notification.title,
        "body": notification.body,
        "data": notification.data,
        "timestamp": notification.created_at.isoformat(),
    }

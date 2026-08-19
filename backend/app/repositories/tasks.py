"""Persistence operations for tasks."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Task

TASK_LOAD_OPTIONS = (
    selectinload(Task.dependencies),
    selectinload(Task.external_applications),
    selectinload(Task.approval_requests),
    selectinload(Task.produced_documents),
)


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_case(self, case_id: UUID) -> list[Task]:
        query = select(Task).where(Task.case_id == case_id).options(*TASK_LOAD_OPTIONS)
        return list((await self.session.scalars(query)).all())

    async def get_for_case(self, case_id: UUID, task_id: UUID) -> Task | None:
        query = (
            select(Task)
            .where(Task.case_id == case_id, Task.id == task_id)
            .options(*TASK_LOAD_OPTIONS)
        )
        tasks = await self.session.scalars(query)
        return tasks.one_or_none()

    async def update_input_data(self, task: Task, input_data: dict[str, Any]) -> Task:
        task.input_data = input_data
        await self.session.commit()
        loaded = await self.get_for_case(task.case_id, task.id)
        if loaded is None:  # pragma: no cover - guarded by the loaded input entity
            raise RuntimeError("Updated task disappeared")
        return loaded

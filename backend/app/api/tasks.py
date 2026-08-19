"""Case-scoped task API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import WorkflowLoader
from app.db.session import get_session
from app.models import Task, TaskStatus
from app.repositories import CaseRepository, TaskRepository
from app.schemas import RequiredDocumentRead, TaskDetailRead, TaskInputUpdate, TaskRead

router = APIRouter(prefix="/api/cases/{case_id}/tasks", tags=["tasks"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    case_id: UUID,
    session: SessionDep,
) -> list[TaskRead]:
    if not await CaseRepository(session).exists(case_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    tasks = await TaskRepository(session).list_for_case(case_id)
    return [TaskRead.model_validate(task) for task in tasks]


async def require_task(session: AsyncSession, case_id: UUID, task_id: UUID) -> Task:
    task = await TaskRepository(session).get_for_case(case_id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get("/{task_id}", response_model=TaskDetailRead)
async def get_task(
    case_id: UUID,
    task_id: UUID,
    session: SessionDep,
) -> TaskDetailRead:
    task = await require_task(session, case_id, task_id)
    response = TaskDetailRead.model_validate(task)
    workflow = next(
        (
            definition
            for definition in WorkflowLoader().load_all()
            if definition.id == task.workflow_id
        ),
        None,
    )
    if workflow is None:
        return response
    task_definition = next(
        (definition for definition in workflow.tasks if definition.id == task.task_type),
        None,
    )
    if task_definition is None:
        return response
    return response.model_copy(
        update={
            "description": workflow.description,
            "required_documents": [
                RequiredDocumentRead.model_validate(document.model_dump())
                for document in task_definition.required_documents
            ],
        }
    )


@router.patch("/{task_id}", response_model=TaskDetailRead)
async def update_task(
    case_id: UUID,
    task_id: UUID,
    payload: TaskInputUpdate,
    session: SessionDep,
) -> TaskDetailRead:
    task = await require_task(session, case_id, task_id)
    if task.status not in {TaskStatus.READY, TaskStatus.IN_PROGRESS}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot update task in {task.status.value} status",
        )
    updated = await TaskRepository(session).update_input_data(task, payload.input_data)
    return TaskDetailRead.model_validate(updated)

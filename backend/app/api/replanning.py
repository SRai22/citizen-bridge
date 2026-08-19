"""Rejection interpretation and dynamic remediation endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import (
    Interpretation,
    RejectionAIUnavailableError,
    RejectionInterpreter,
    RemediationAction,
)
from app.core import DependencySolverError, WorkflowEngine, WorkflowEngineError
from app.db.session import get_session
from app.models import ExternalApplication, ExternalApplicationStatus, Task, TaskStatus
from app.repositories import CaseRepository, TaskRepository
from app.schemas import CaseRead

router = APIRouter(prefix="/api/cases/{case_id}", tags=["replanning"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
interpreter = RejectionInterpreter()


@router.post(
    "/tasks/{task_id}/interpret-rejection",
    response_model=Interpretation,
)
async def interpret_rejection(
    case_id: UUID,
    task_id: UUID,
    session: SessionDep,
) -> Interpretation:
    task = await TaskRepository(session).get_for_case(case_id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.status != TaskStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed tasks can have a rejection interpreted.",
        )

    application = await session.scalar(
        select(ExternalApplication)
        .where(
            ExternalApplication.task_id == task.id,
            ExternalApplication.status == ExternalApplicationStatus.REJECTED,
        )
        .order_by(ExternalApplication.responded_at.desc(), ExternalApplication.created_at.desc())
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No rejected application was found for this task.",
        )

    rejection_message = application.response_payload.get("message")
    if not isinstance(rejection_message, str) or not rejection_message:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The rejected application has no rejection message.",
        )
    try:
        return await interpreter.interpret(
            rejection_message,
            {
                "workflow_id": task.workflow_id,
                "task_type": task.task_type,
                "title": task.title,
                "input_data": task.input_data,
                "rejection_data": application.response_payload.get("data", {}),
            },
        )
    except RejectionAIUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error


@router.post("/accept-remediation", response_model=CaseRead)
async def accept_remediation(
    case_id: UUID,
    remediation: RemediationAction,
    session: SessionDep,
) -> CaseRead:
    target = await session.scalar(
        select(Task)
        .where(
            Task.case_id == case_id,
            Task.workflow_id == remediation.dependency_target,
        )
        .order_by(Task.created_at, Task.id)
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remediation dependency target not found.",
        )
    if target.status not in {TaskStatus.FAILED, TaskStatus.BLOCKED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot remediate a task in {target.status.value} status.",
        )

    engine = WorkflowEngine(session)
    try:
        remediation_tasks = await engine.activate_dynamic_workflow(
            case_id,
            remediation.workflow_id,
            commit=False,
        )
        prerequisite = remediation_tasks[-1]
        await engine.dependency_solver.add_dependency(target.id, prerequisite.id)
        if target.status == TaskStatus.FAILED:
            await engine.transition_task(
                target.id,
                TaskStatus.BLOCKED,
                {
                    "reason": "remediation_accepted",
                    "workflow_id": remediation.workflow_id,
                },
            )
        else:
            await session.commit()
    except (WorkflowEngineError, DependencySolverError) as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    case = await CaseRepository(session).get(case_id)
    if case is None:  # pragma: no cover - target lookup established the case
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return CaseRead.model_validate(case)

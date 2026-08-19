"""Approval decision API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.submission_errors import submission_http_error
from app.core import SubmissionService, SubmissionServiceError
from app.db.session import get_session
from app.schemas import ApprovalRequestRead, ExternalApplicationRead

router = APIRouter(prefix="/api/approvals", tags=["approvals"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("/{approval_id}/approve", response_model=ExternalApplicationRead)
async def approve_submission(
    approval_id: UUID,
    session: SessionDep,
) -> ExternalApplicationRead:
    try:
        application = await SubmissionService(session).approve(approval_id)
    except SubmissionServiceError as error:
        raise submission_http_error(error) from error
    return ExternalApplicationRead.model_validate(application)


@router.post("/{approval_id}/reject", response_model=ApprovalRequestRead)
async def reject_submission(
    approval_id: UUID,
    session: SessionDep,
) -> ApprovalRequestRead:
    try:
        approval = await SubmissionService(session).reject(approval_id)
    except SubmissionServiceError as error:
        raise submission_http_error(error) from error
    return ApprovalRequestRead.model_validate(approval)

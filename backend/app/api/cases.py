"""Case API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import SubmissionService
from app.db.session import get_session
from app.models import CaseStatus, Document
from app.repositories import CaseRepository
from app.schemas import ApprovalRequestRead, CaseCreate, CaseRead, DocumentRead

router = APIRouter(prefix="/api/cases", tags=["cases"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreate,
    session: SessionDep,
) -> CaseRead:
    case = await CaseRepository(session).create(payload)
    return CaseRead.model_validate(case)


@router.get("/{case_id}", response_model=CaseRead)
async def get_case(
    case_id: UUID,
    session: SessionDep,
) -> CaseRead:
    case = await CaseRepository(session).get(case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return CaseRead.model_validate(case)


@router.get("/{case_id}/documents", response_model=list[DocumentRead])
async def list_case_documents(
    case_id: UUID,
    session: SessionDep,
) -> list[DocumentRead]:
    if not await CaseRepository(session).exists(case_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    documents = await session.scalars(
        select(Document)
        .where(Document.case_id == case_id)
        .order_by(Document.created_at, Document.id)
    )
    return [DocumentRead.model_validate(document) for document in documents.all()]


@router.get("/{case_id}/approvals", response_model=list[ApprovalRequestRead])
async def list_case_approvals(
    case_id: UUID,
    session: SessionDep,
) -> list[ApprovalRequestRead]:
    if not await CaseRepository(session).exists(case_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    approvals = await SubmissionService(session).list_approvals(case_id)
    return [ApprovalRequestRead.model_validate(approval) for approval in approvals]


@router.post("/{case_id}/activate", response_model=CaseRead)
async def activate_case(
    case_id: UUID,
    session: SessionDep,
) -> CaseRead:
    repository = CaseRepository(session)
    case = await repository.get(case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if case.status != CaseStatus.INTAKE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot activate case in {case.status.value} status",
        )
    return CaseRead.model_validate(await repository.activate(case))

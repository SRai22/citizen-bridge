"""Demo seed data and reset endpoints."""

import os
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import WorkflowEngine
from app.db.session import get_session
from app.models import (
    Case,
    CaseStatus,
    Document,
    ExternalApplication,
    ExternalApplicationStatus,
    HouseholdProfile,
    LifeEvent,
    Person,
    Task,
    TaskStatus,
    VerificationStatus,
)
from app.repositories import CaseRepository

router = APIRouter(prefix="/api/demo", tags=["demo"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _demo_enabled() -> bool:
    return os.getenv("DEMO_MODE", "true").lower() == "true"


def _require_demo_mode() -> None:
    if not _demo_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo endpoints are disabled.",
        )


# -- Seed profile data ---------------------------------------------------------

DECEASED_NAME = "Ramesh Kumar Sharma"
SPOUSE_NAME = "Lakshmi Sharma"
USER_NAME = "Vikram Sharma"
ADDRESS = "#42, 3rd Cross, Jayanagar 4th Block, Bengaluru - 560041"
BESCOM_CONSUMER = "BLR-S-JN4-00847"
RATION_CARD = "KA-BLR-2819456"

WORKFLOW_CONTEXT: dict[str, object] = {
    "deceased": {
        "name": DECEASED_NAME,
        "relationship": "father",
        "occupation": "retired Karnataka state government employee",
        "pension_status": "active",
        "is_deceased": True,
        "was_electricity_account_holder": True,
        "was_head_of_household": True,
    },
    "surviving_spouse": {"exists": True},
    "location": {"city": "Bengaluru", "state": "Karnataka"},
    "assets": {"bescom": True, "ration_card": True, "property": False},
}


class SeedState(StrEnum):
    INITIAL = "initial"
    AFTER_DEATH_CERT = "after_death_cert"
    AFTER_BESCOM_REJECTION = "after_bescom_rejection"


class SeedResponse(BaseModel):
    case_id: UUID
    state: str
    tasks: int


class ResetResponse(BaseModel):
    status: str


# -- Reset endpoint -------------------------------------------------------------

TABLES_TO_CLEAR = [
    "audit_entries",
    "approval_requests",
    "external_applications",
    "task_dependencies",
    "documents",
    "tasks",
    "people",
    "household_profiles",
    "life_events",
    "cases",
]


@router.post("/reset", response_model=ResetResponse)
async def reset_demo(session: SessionDep) -> ResetResponse:
    _require_demo_mode()
    for table in TABLES_TO_CLEAR:
        await session.execute(text(f"DELETE FROM {table}"))  # noqa: S608
    await session.commit()
    return ResetResponse(status="ok")


# -- Seed endpoint --------------------------------------------------------------


@router.post("/seed", response_model=SeedResponse)
async def seed_demo(
    session: SessionDep,
    state: SeedState = SeedState.INITIAL,
) -> SeedResponse:
    _require_demo_mode()

    case = _create_base_case(session)
    await session.flush()

    engine = WorkflowEngine(session)
    tasks = await engine.activate_workflows(case.id, WORKFLOW_CONTEXT)

    if state in (SeedState.AFTER_DEATH_CERT, SeedState.AFTER_BESCOM_REJECTION):
        await _complete_death_cert(session, engine, case.id, tasks)

    if state == SeedState.AFTER_BESCOM_REJECTION:
        await _reject_bescom(session, engine, case.id, tasks)

    await session.commit()
    loaded = await CaseRepository(session).get(case.id)
    return SeedResponse(
        case_id=case.id,
        state=state.value,
        tasks=len(loaded.tasks) if loaded else len(tasks),
    )


# -- Helper builders -----------------------------------------------------------


def _create_base_case(session: AsyncSession) -> Case:
    case = Case(
        status=CaseStatus.ACTIVE,
        life_event=LifeEvent(
            event_type="father_death",
            context={
                "source": "demo_seed",
                "title": "Post-death Administrative Actions",
                "profile": WORKFLOW_CONTEXT,
            },
        ),
        household_profile=HouseholdProfile(
            location_city="Bengaluru",
            location_state="Karnataka",
            people=[
                Person(
                    name=DECEASED_NAME,
                    relationship="father",
                    role="deceased",
                    is_deceased=True,
                    attributes={
                        "occupation": "retired Karnataka state government employee",
                        "pension_status": "active",
                        "age": 72,
                    },
                ),
                Person(
                    name=SPOUSE_NAME,
                    relationship="spouse",
                    role="surviving_member",
                    is_deceased=False,
                    attributes={"occupation": "homemaker", "age": 67},
                ),
                Person(
                    name=USER_NAME,
                    relationship="son",
                    role="surviving_member",
                    is_deceased=False,
                    attributes={"occupation": "software engineer", "age": 42},
                ),
            ],
        ),
    )
    session.add(case)
    return case


def _find_task(tasks: list[Task], workflow_id: str) -> Task:
    return next(t for t in tasks if t.workflow_id == workflow_id)


async def _complete_death_cert(
    session: AsyncSession,
    engine: WorkflowEngine,
    case_id: UUID,
    tasks: list[Task],
) -> None:
    dc = _find_task(tasks, "death_certificate")
    await engine.transition_task(dc.id, TaskStatus.IN_PROGRESS, commit=False)
    await engine.transition_task(dc.id, TaskStatus.SUBMITTED, commit=False)
    await engine.transition_task(
        dc.id,
        TaskStatus.COMPLETED,
        {"source": "demo_seed"},
        commit=False,
    )

    session.add(
        ExternalApplication(
            task_id=dc.id,
            adapter_type="death_certificate",
            external_reference_id="BBMP/D/2026/00142",
            status=ExternalApplicationStatus.APPROVED,
            request_payload={
                "deceased_name": DECEASED_NAME,
                "date_of_death": "2026-08-10",
                "place_of_death": "Bengaluru",
                "cause_of_death": "Cardiac arrest",
            },
            response_payload={
                "registration_number": "BBMP/D/2026/00142",
                "date_of_registration": "2026-08-12",
                "registrar": "Registrar of Births and Deaths, BBMP South Zone",
            },
        )
    )

    session.add(
        Document(
            case_id=case_id,
            produced_by_task_id=dc.id,
            document_type="death_certificate",
            owner_name=DECEASED_NAME,
            issuer="Registrar of Births and Deaths, BBMP South Zone",
            verification_status=VerificationStatus.VERIFIED,
            extracted_fields={
                "registration_number": "BBMP/D/2026/00142",
                "deceased_name": DECEASED_NAME,
                "date_of_death": "2026-08-10",
                "place_of_death": "Bengaluru",
                "cause_of_death": "Cardiac arrest",
                "date_of_registration": "2026-08-12",
            },
        )
    )
    await session.flush()


async def _reject_bescom(
    session: AsyncSession,
    engine: WorkflowEngine,
    case_id: UUID,
    tasks: list[Task],
) -> None:
    bescom = _find_task(tasks, "bescom_transfer")
    await engine.transition_task(bescom.id, TaskStatus.IN_PROGRESS, commit=False)
    await engine.transition_task(bescom.id, TaskStatus.SUBMITTED, commit=False)
    await engine.transition_task(
        bescom.id,
        TaskStatus.FAILED,
        {"source": "demo_seed", "reason": "insufficient_succession_docs"},
        commit=False,
    )

    rejection_message = (
        "Application rejected. Supporting documentation establishing the proposed "
        "transferee's relationship or succession rights is insufficient. A Legal Heir "
        "Certificate or Succession Certificate issued by a competent authority is required "
        "to process this name transfer application."
    )
    session.add(
        ExternalApplication(
            task_id=bescom.id,
            adapter_type="bescom",
            external_reference_id="BESCOM/NT/2026/04819",
            status=ExternalApplicationStatus.REJECTED,
            request_payload={
                "consumer_number": BESCOM_CONSUMER,
                "current_holder_name": DECEASED_NAME,
                "proposed_holder_name": SPOUSE_NAME,
                "property_address": ADDRESS,
            },
            response_payload={
                "message": rejection_message,
                "data": {
                    "rejection_code": "INSUFFICIENT_SUCCESSION_DOCS",
                    "required_document": "legal_heir_certificate",
                },
            },
        )
    )

    # Activate legal heir workflow and block BESCOM on it
    remediation_tasks = await engine.activate_dynamic_workflow(
        case_id,
        "legal_heir_certificate",
        commit=False,
    )
    prerequisite = remediation_tasks[-1]
    await engine.dependency_solver.add_dependency(bescom.id, prerequisite.id)
    await engine.transition_task(
        bescom.id,
        TaskStatus.BLOCKED,
        {"reason": "remediation_accepted", "workflow_id": "legal_heir_certificate"},
        commit=False,
    )
    await session.flush()

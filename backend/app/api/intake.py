"""Conversational intake endpoints."""

from dataclasses import dataclass, field
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import HouseholdProfile, IntakeAgent, IntakeAIUnavailableError
from app.core import WorkflowEngine
from app.db.session import get_session
from app.models import CaseStatus
from app.repositories import CaseRepository
from app.schemas import CaseCreate, HouseholdProfileCreate, LifeEventCreate, PersonCreate

router = APIRouter(prefix="/api/intake", tags=["intake"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
INITIAL_MESSAGE = (
    "I’m sorry you’re going through this. I’ll ask a few short questions so we can identify "
    "the services your family may need. What happened, and who passed away?"
)


class IntakeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)


class IntakeResponse(BaseModel):
    session_id: UUID
    status: Literal["in_progress", "complete"]
    message: str
    profile: HouseholdProfile | None = None


class IntakeConfirmationResponse(BaseModel):
    case_id: UUID


@dataclass
class IntakeSession:
    messages: list[dict[str, str]] = field(
        default_factory=lambda: [{"role": "assistant", "content": INITIAL_MESSAGE}]
    )
    profile: HouseholdProfile | None = None
    confirmed_case_id: UUID | None = None


sessions: dict[UUID, IntakeSession] = {}
agent = IntakeAgent()


@router.post("/start", response_model=IntakeResponse, status_code=status.HTTP_201_CREATED)
async def start_intake() -> IntakeResponse:
    session_id = uuid4()
    sessions[session_id] = IntakeSession()
    return IntakeResponse(
        session_id=session_id,
        status="in_progress",
        message=INITIAL_MESSAGE,
    )


@router.post("/{session_id}/message", response_model=IntakeResponse)
async def send_message(session_id: UUID, payload: IntakeRequest) -> IntakeResponse:
    intake_session = _session_or_404(session_id)
    intake_session.profile = None
    intake_session.messages.append({"role": "user", "content": payload.message})
    try:
        turn = await agent.reply(intake_session.messages)
    except IntakeAIUnavailableError as error:
        intake_session.messages.pop()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    intake_session.messages.append({"role": "assistant", "content": turn.message})
    intake_session.profile = turn.profile
    return IntakeResponse(session_id=session_id, **turn.model_dump())


@router.post("/{session_id}/confirm", response_model=IntakeConfirmationResponse)
async def confirm_intake(
    session_id: UUID,
    session: SessionDep,
) -> IntakeConfirmationResponse:
    intake_session = _session_or_404(session_id)
    if intake_session.confirmed_case_id is not None:
        return IntakeConfirmationResponse(case_id=intake_session.confirmed_case_id)
    if intake_session.profile is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The intake conversation is not complete.",
        )

    profile = intake_session.profile
    case = await CaseRepository(session).create(_case_payload(profile))
    case.status = CaseStatus.ACTIVE
    await WorkflowEngine(session).activate_workflows(case.id, profile.workflow_context())
    intake_session.confirmed_case_id = case.id
    return IntakeConfirmationResponse(case_id=case.id)


def _session_or_404(session_id: UUID) -> IntakeSession:
    try:
        return sessions[session_id]
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intake session not found.",
        ) from error


def _case_payload(profile: HouseholdProfile) -> CaseCreate:
    people = [
        PersonCreate(
            name=profile.deceased.name,
            relationship=profile.deceased.relationship,
            role="deceased",
            is_deceased=True,
            attributes={
                "occupation": profile.deceased.occupation,
                "pension_status": profile.deceased.pension_status,
            },
        ),
        *[
            PersonCreate(
                name=member.name,
                relationship=member.relationship,
                role="surviving_member",
                attributes={
                    "occupation": member.occupation,
                    "pension_status": member.pension_status,
                },
            )
            for member in profile.surviving_members
        ],
    ]
    return CaseCreate(
        life_event=LifeEventCreate(
            type=f"{profile.deceased.relationship.lower()}_death",
            context={"source": "ai_intake", "profile": profile.model_dump()},
        ),
        household_profile=HouseholdProfileCreate(
            location_city=profile.location.city,
            location_state=profile.location.state,
            people=people,
        ),
    )

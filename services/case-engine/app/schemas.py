from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import CaseStatus, TaskStatus


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LifeEventCreate(RequestModel):
    type: str = Field(min_length=1, max_length=100)
    context: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class PersonCreate(RequestModel):
    id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    relationship: str = Field(min_length=1, max_length=100)
    role: str | None = Field(default=None, max_length=100)
    is_deceased: bool = False
    attributes: dict[str, Any] = Field(default_factory=dict)


class HouseholdCreate(RequestModel):
    location_city: str | None = Field(default=None, max_length=100)
    location_state: str | None = Field(default=None, max_length=100)
    people: list[PersonCreate] = Field(default_factory=list)


class CaseCreate(RequestModel):
    life_event: LifeEventCreate
    household_profile: HouseholdCreate | None = None
    subject_person_index: int | None = Field(default=None, ge=0)
    subject_relationship: str | None = Field(default=None, max_length=100)


class TaskTransition(RequestModel):
    status: TaskStatus
    output_data: dict[str, Any] = Field(default_factory=dict)


class TaskStageAdvance(RequestModel):
    stage: str = Field(min_length=1, max_length=100)


class TaskInputUpdate(RequestModel):
    input_data: dict[str, Any]


class Progress(BaseModel):
    completed: int
    total: int


class WaitState(BaseModel):
    stages_known: bool
    stages: list[dict[str, Any]] = Field(default_factory=list)
    current_stage: str | None = None
    status_label: str | None = None
    submitted_at: datetime | None = None
    estimated_wait: dict[str, int | None]
    last_update: datetime | None
    is_overdue: bool
    message: str | None = None


class TaskResponse(BaseModel):
    task_id: UUID
    case_id: UUID
    workflow_id: str
    task_type: str
    title: str
    description: str | None
    status: TaskStatus
    completed_at: datetime | None
    blocked_reason: str | None = None
    blocked_by_task_ids: list[UUID] = Field(default_factory=list)
    wait_state: WaitState | None = None
    wait_summary: str | None = None


class TaskGroups(BaseModel):
    ready: list[TaskResponse] = Field(default_factory=list)
    waiting: list[TaskResponse] = Field(default_factory=list)
    blocked: list[TaskResponse] = Field(default_factory=list)
    completed: list[TaskResponse] = Field(default_factory=list)


class SubjectResponse(BaseModel):
    person_id: UUID | None = None
    name: str
    relationship: str


class CaseSummary(BaseModel):
    case_id: UUID
    title: str
    status: CaseStatus
    life_event_type: str
    my_role: str
    progress: Progress
    created_at: datetime
    updated_at: datetime


class CaseListResponse(BaseModel):
    cases: list[CaseSummary]


class CaseDetail(CaseSummary):
    my_permissions: list[str]
    limitations: list[str] = Field(default_factory=list)
    subject: SubjectResponse | None
    tasks_by_group: TaskGroups
    life_event: dict[str, Any]


class CaseCreated(CaseDetail):
    pass


CaseStatusFilter = Literal["intake", "active", "completed", "abandoned"]


class SetSubjectRequest(RequestModel):
    case_id: UUID
    subject_person_id: UUID
    relationship: str = Field(min_length=1, max_length=100)
    role: Literal["coordinator"] = "coordinator"

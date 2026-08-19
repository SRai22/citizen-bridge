"""Pydantic response shapes for persisted domain entities."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    ApprovalStatus,
    CaseStatus,
    ExternalApplicationStatus,
    TaskStatus,
    VerificationStatus,
)


class ORMReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class LifeEventRead(ORMReadModel):
    case_id: UUID
    event_type: str
    context: dict[str, Any]
    occurred_at: datetime


class PersonRead(ORMReadModel):
    household_id: UUID
    name: str
    relationship: str
    role: str | None
    is_deceased: bool
    attributes: dict[str, Any]


class HouseholdProfileRead(ORMReadModel):
    case_id: UUID
    location_city: str | None
    location_state: str | None
    people: list[PersonRead] = Field(default_factory=list)


class TaskDependencyRead(ORMReadModel):
    task_id: UUID
    depends_on_task_id: UUID
    dependency_type: str


class ExternalApplicationRead(ORMReadModel):
    task_id: UUID
    adapter_type: str
    external_reference_id: str | None
    status: ExternalApplicationStatus
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]
    submitted_at: datetime | None
    responded_at: datetime | None


class ApprovalRequestRead(ORMReadModel):
    task_id: UUID
    action_description: str
    status: ApprovalStatus
    context: dict[str, Any]
    requested_at: datetime
    resolved_at: datetime | None


class TaskRead(ORMReadModel):
    case_id: UUID
    workflow_id: str
    task_type: str
    status: TaskStatus
    title: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    completed_at: datetime | None
    dependencies: list[TaskDependencyRead] = Field(default_factory=list)
    external_applications: list[ExternalApplicationRead] = Field(default_factory=list)
    approval_requests: list[ApprovalRequestRead] = Field(default_factory=list)


class DocumentRead(ORMReadModel):
    case_id: UUID
    produced_by_task_id: UUID | None
    document_type: str
    owner_name: str
    issuer: str | None
    issued_at: datetime | None
    verification_status: VerificationStatus
    extracted_fields: dict[str, Any]
    metadata: dict[str, Any] = Field(validation_alias="metadata_")


class AuditEntryRead(ORMReadModel):
    case_id: UUID
    task_id: UUID | None
    event_type: str
    description: str
    details: dict[str, Any]


class CaseRead(ORMReadModel):
    status: CaseStatus
    life_event: LifeEventRead | None
    household_profile: HouseholdProfileRead | None
    tasks: list[TaskRead] = Field(default_factory=list)
    documents: list[DocumentRead] = Field(default_factory=list)
    audit_entries: list[AuditEntryRead] = Field(default_factory=list)

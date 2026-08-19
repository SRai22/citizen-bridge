"""Core SQLAlchemy domain models for case orchestration."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as orm_relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class CaseStatus(StrEnum):
    INTAKE = "intake"
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class TaskStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ExternalApplicationStatus(StrEnum):
    PREPARED = "prepared"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    APPROVED = "approved"
    REJECTED = "rejected"
    ERROR = "error"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


def enum_column(enum_class: type[StrEnum], *, default: StrEnum) -> Mapped[Any]:
    """Create a portable enum column that persists enum values as strings."""
    return mapped_column(
        Enum(
            enum_class,
            values_callable=lambda members: [member.value for member in members],
            native_enum=False,
            validate_strings=True,
        ),
        default=default,
        index=True,
    )


def json_column() -> Mapped[dict[str, Any]]:
    """Create a mutable JSON object column with an independent default."""
    return mapped_column(MutableDict.as_mutable(JSON), default=dict)


class Case(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cases"

    status: Mapped[CaseStatus] = enum_column(CaseStatus, default=CaseStatus.INTAKE)

    life_event: Mapped[LifeEvent | None] = orm_relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    household_profile: Mapped[HouseholdProfile | None] = orm_relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    tasks: Mapped[list[Task]] = orm_relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    documents: Mapped[list[Document]] = orm_relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    audit_entries: Mapped[list[AuditEntry]] = orm_relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class LifeEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "life_events"

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), unique=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100))
    context: Mapped[dict[str, Any]] = json_column()
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    case: Mapped[Case] = orm_relationship(back_populates="life_event")


class HouseholdProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "household_profiles"

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), unique=True, index=True
    )
    location_city: Mapped[str | None] = mapped_column(String(100))
    location_state: Mapped[str | None] = mapped_column(String(100))

    case: Mapped[Case] = orm_relationship(back_populates="household_profile")
    people: Mapped[list[Person]] = orm_relationship(
        back_populates="household",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Person(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "people"

    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household_profiles.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    relationship: Mapped[str] = mapped_column(String(100))
    role: Mapped[str | None] = mapped_column(String(100))
    is_deceased: Mapped[bool] = mapped_column(Boolean, default=False)
    attributes: Mapped[dict[str, Any]] = json_column()

    household: Mapped[HouseholdProfile] = orm_relationship(back_populates="people")


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_case_id_status", "case_id", "status"),)

    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    workflow_id: Mapped[str] = mapped_column(String(100))
    task_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[TaskStatus] = enum_column(TaskStatus, default=TaskStatus.PENDING)
    title: Mapped[str] = mapped_column(String(250))
    input_data: Mapped[dict[str, Any]] = json_column()
    output_data: Mapped[dict[str, Any]] = json_column()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    case: Mapped[Case] = orm_relationship(back_populates="tasks")
    dependencies: Mapped[list[TaskDependency]] = orm_relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        foreign_keys="TaskDependency.task_id",
        passive_deletes=True,
    )
    dependents: Mapped[list[TaskDependency]] = orm_relationship(
        back_populates="depends_on_task",
        cascade="all, delete-orphan",
        foreign_keys="TaskDependency.depends_on_task_id",
        passive_deletes=True,
    )
    produced_documents: Mapped[list[Document]] = orm_relationship(back_populates="produced_by_task")
    external_applications: Mapped[list[ExternalApplication]] = orm_relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    approval_requests: Mapped[list[ApprovalRequest]] = orm_relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    audit_entries: Mapped[list[AuditEntry]] = orm_relationship(back_populates="task")


class TaskDependency(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependency_edge"),
    )

    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    depends_on_task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    dependency_type: Mapped[str] = mapped_column(String(50), default="completion")

    task: Mapped[Task] = orm_relationship(
        back_populates="dependencies",
        foreign_keys=[task_id],
    )
    depends_on_task: Mapped[Task] = orm_relationship(
        back_populates="dependents",
        foreign_keys=[depends_on_task_id],
    )


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    produced_by_task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    document_type: Mapped[str] = mapped_column(String(100), index=True)
    owner_name: Mapped[str] = mapped_column(String(200))
    issuer: Mapped[str | None] = mapped_column(String(200))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_status: Mapped[VerificationStatus] = enum_column(
        VerificationStatus,
        default=VerificationStatus.PENDING,
    )
    extracted_fields: Mapped[dict[str, Any]] = json_column()
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        MutableDict.as_mutable(JSON),
        default=dict,
    )

    case: Mapped[Case] = orm_relationship(back_populates="documents")
    produced_by_task: Mapped[Task | None] = orm_relationship(back_populates="produced_documents")


class ExternalApplication(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_applications"

    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    adapter_type: Mapped[str] = mapped_column(String(100))
    external_reference_id: Mapped[str | None] = mapped_column(String(200), index=True)
    status: Mapped[ExternalApplicationStatus] = enum_column(
        ExternalApplicationStatus,
        default=ExternalApplicationStatus.PREPARED,
    )
    request_payload: Mapped[dict[str, Any]] = json_column()
    response_payload: Mapped[dict[str, Any]] = json_column()
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    task: Mapped[Task] = orm_relationship(back_populates="external_applications")


class ApprovalRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "approval_requests"

    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    action_description: Mapped[str] = mapped_column(String(500))
    status: Mapped[ApprovalStatus] = enum_column(
        ApprovalStatus,
        default=ApprovalStatus.PENDING,
    )
    context: Mapped[dict[str, Any]] = json_column()
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    task: Mapped[Task] = orm_relationship(back_populates="approval_requests")


class AuditEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_entries"

    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(String(1000))
    details: Mapped[dict[str, Any]] = json_column()

    case: Mapped[Case] = orm_relationship(back_populates="audit_entries")
    task: Mapped[Task | None] = orm_relationship(back_populates="audit_entries")

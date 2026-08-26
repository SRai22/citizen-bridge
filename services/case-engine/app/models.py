from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.ext.mutable import MutableDict, MutableList
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


def enum_column(enum: type[StrEnum], default: StrEnum) -> Mapped[Any]:
    return mapped_column(
        Enum(
            enum,
            values_callable=lambda members: [member.value for member in members],
            native_enum=False,
        ),
        default=default,
        index=True,
    )


def json_column() -> Mapped[dict[str, Any]]:
    return mapped_column(MutableDict.as_mutable(JSON), default=dict)


class Case(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cases"
    __table_args__ = {"schema": "cases"}

    title: Mapped[str] = mapped_column(String(250))
    status: Mapped[CaseStatus] = enum_column(CaseStatus, CaseStatus.INTAKE)
    life_event_type: Mapped[str] = mapped_column(String(100), index=True)
    profile: Mapped[dict[str, Any]] = json_column()
    subject_person_id: Mapped[UUID | None] = mapped_column(index=True)
    coordinator_user_id: Mapped[UUID | None] = mapped_column(index=True)
    subject_relationship: Mapped[str | None] = mapped_column(String(100))
    tasks: Mapped[list[Task]] = orm_relationship(
        back_populates="case", cascade="all, delete-orphan", passive_deletes=True
    )
    life_event: Mapped[LifeEvent] = orm_relationship(
        back_populates="case", cascade="all, delete-orphan", passive_deletes=True
    )
    household_profile: Mapped[HouseholdProfile | None] = orm_relationship(
        back_populates="case", cascade="all, delete-orphan", passive_deletes=True
    )


class LifeEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "life_events"
    __table_args__ = {"schema": "cases"}

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.cases.id", ondelete="CASCADE"), unique=True
    )
    event_type: Mapped[str] = mapped_column(String(100))
    context: Mapped[dict[str, Any]] = json_column()
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    case: Mapped[Case] = orm_relationship(back_populates="life_event")


class HouseholdProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "household_profiles"
    __table_args__ = {"schema": "cases"}

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.cases.id", ondelete="CASCADE"), unique=True
    )
    location_city: Mapped[str | None] = mapped_column(String(100))
    location_state: Mapped[str | None] = mapped_column(String(100))
    case: Mapped[Case] = orm_relationship(back_populates="household_profile")
    people: Mapped[list[Person]] = orm_relationship(
        back_populates="household", cascade="all, delete-orphan", passive_deletes=True
    )


class Person(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "persons"
    __table_args__ = {"schema": "cases"}

    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.household_profiles.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    relationship: Mapped[str] = mapped_column(String(100))
    role: Mapped[str | None] = mapped_column(String(100))
    is_deceased: Mapped[bool] = mapped_column(Boolean, default=False)
    attributes: Mapped[dict[str, Any]] = json_column()
    household: Mapped[HouseholdProfile] = orm_relationship(back_populates="people")


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_case_status", "case_id", "status"), {"schema": "cases"})

    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.cases.id", ondelete="CASCADE"))
    workflow_id: Mapped[str] = mapped_column(String(100))
    task_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[TaskStatus] = enum_column(TaskStatus, TaskStatus.PENDING)
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str | None] = mapped_column(String(1000))
    estimated_duration_days: Mapped[int] = mapped_column(default=1)
    input_data: Mapped[dict[str, Any]] = json_column()
    output_data: Mapped[dict[str, Any]] = json_column()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    case: Mapped[Case] = orm_relationship(back_populates="tasks")
    dependencies: Mapped[list[TaskDependency]] = orm_relationship(
        back_populates="task",
        foreign_keys="TaskDependency.task_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    wait_state: Mapped[TaskWaitState | None] = orm_relationship(
        back_populates="task", cascade="all, delete-orphan", passive_deletes=True
    )
    external_applications: Mapped[list[ExternalApplication]] = orm_relationship(
        back_populates="task", cascade="all, delete-orphan", passive_deletes=True
    )
    approval_requests: Mapped[list[ApprovalRequest]] = orm_relationship(
        back_populates="task", cascade="all, delete-orphan", passive_deletes=True
    )


class TaskWaitState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_wait_states"
    __table_args__ = {"schema": "cases"}

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.tasks.id", ondelete="CASCADE"), unique=True, index=True
    )
    stages_known: Mapped[bool] = mapped_column(Boolean, default=False)
    stages: Mapped[list[dict[str, Any]]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    current_stage: Mapped[str | None] = mapped_column(String(100))
    stage_entered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_wait_days_min: Mapped[int | None] = mapped_column(Integer)
    estimated_wait_days_max: Mapped[int | None] = mapped_column(Integer)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status_update_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_overdue: Mapped[bool] = mapped_column(Boolean, default=False)
    task: Mapped[Task] = orm_relationship(back_populates="wait_state")


class TaskDependency(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependency_edge"),
        {"schema": "cases"},
    )

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.tasks.id", ondelete="CASCADE"), index=True
    )
    depends_on_task_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.tasks.id", ondelete="CASCADE"), index=True
    )
    dependency_type: Mapped[str] = mapped_column(String(50), default="completion")
    task: Mapped[Task] = orm_relationship(back_populates="dependencies", foreign_keys=[task_id])


class ExternalApplication(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_applications"
    __table_args__ = {"schema": "cases"}

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.tasks.id", ondelete="CASCADE"), index=True
    )
    adapter_type: Mapped[str] = mapped_column(String(100))
    external_reference_id: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50), default="prepared")
    request_payload: Mapped[dict[str, Any]] = json_column()
    response_payload: Mapped[dict[str, Any]] = json_column()
    task: Mapped[Task] = orm_relationship(back_populates="external_applications")


class ApprovalRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "approval_requests"
    __table_args__ = {"schema": "cases"}

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.tasks.id", ondelete="CASCADE"), index=True
    )
    action_description: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    context: Mapped[dict[str, Any]] = json_column()
    task: Mapped[Task] = orm_relationship(back_populates="approval_requests")


class AuditEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_entries"
    __table_args__ = {"schema": "cases"}

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.cases.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cases.tasks.id", ondelete="SET NULL"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(String(1000))
    details: Mapped[dict[str, Any]] = json_column()


class ActiveBenefit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "active_benefits"
    __table_args__ = (
        UniqueConstraint("user_id", "benefit_id", name="uq_active_benefit_user_scheme"),
        {"schema": "cases"},
    )

    user_id: Mapped[UUID] = mapped_column(index=True)
    benefit_id: Mapped[str] = mapped_column(String(100), index=True)
    source_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.cases.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    amount: Mapped[str] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    next_payment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BenefitDiscovery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "benefit_discoveries"
    __table_args__ = (
        UniqueConstraint("user_id", "benefit_id", name="uq_benefit_discovery_user_scheme"),
        {"schema": "cases"},
    )

    user_id: Mapped[UUID] = mapped_column(index=True)
    benefit_id: Mapped[str] = mapped_column(String(100), index=True)


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    __table_args__ = {"schema": "cases"}

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    consumer_group: Mapped[str] = mapped_column(String(100))

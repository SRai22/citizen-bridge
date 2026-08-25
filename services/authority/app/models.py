from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def now() -> datetime:
    return datetime.now(UTC)


class AuthorityGrant(Base):
    __tablename__ = "authority_grants"
    __table_args__ = (
        CheckConstraint(
            "resource_type IN ('case', 'person', 'document', 'household')",
            name="ck_authority_grants_resource_type",
        ),
        CheckConstraint(
            "role IN ('owner', 'coordinator', 'viewer')", name="ck_authority_grants_role"
        ),
        Index(
            "ix_authority_active_resource",
            "grantee_id",
            "resource_type",
            "resource_id",
            "revoked_at",
        ),
        {"schema": "authority"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    grantor_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    grantee_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    resource_type: Mapped[str] = mapped_column(String(20))
    resource_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    role: Mapped[str] = mapped_column(String(20))
    permissions: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    case_access: Mapped["CaseAccess | None"] = relationship(
        back_populates="grant", cascade="all, delete-orphan"
    )


class CaseAccess(Base):
    __tablename__ = "case_access"
    __table_args__ = (
        UniqueConstraint("user_id", "case_id", name="uq_authority_case_access_user_case"),
        {"schema": "authority"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    case_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    role: Mapped[str] = mapped_column(String(20))
    grant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("authority.authority_grants.id", ondelete="CASCADE"),
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    grant: Mapped[AuthorityGrant] = relationship(back_populates="case_access")


class Delegation(Base):
    __tablename__ = "delegations"
    __table_args__ = (
        CheckConstraint(
            "scope_type IN ('case', 'person', 'all_cases')",
            name="ck_authority_delegations_scope_type",
        ),
        CheckConstraint("role IN ('coordinator', 'viewer')", name="ck_authority_delegations_role"),
        CheckConstraint(
            "status IN ('active', 'expired', 'revoked')",
            name="ck_authority_delegations_status",
        ),
        Index("ix_authority_active_delegations", "delegate_id", "status"),
        {"schema": "authority"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    delegator_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    delegate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    scope_type: Mapped[str] = mapped_column(String(20))
    scope_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    role: Mapped[str] = mapped_column(String(20))
    permissions: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DelegationApprovalRequest(Base):
    __tablename__ = "delegation_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'expired')",
            name="ck_authority_delegation_requests_status",
        ),
        {"schema": "authority"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    from_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    to_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    scope_type: Mapped[str] = mapped_column(String(20))
    scope_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    role: Mapped[str] = mapped_column(String(20), default="coordinator")
    message: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delegation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    __table_args__ = ({"schema": "authority"},)

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    consumer_group: Mapped[str] = mapped_column(String(100))

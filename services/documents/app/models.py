from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def now() -> datetime:
    return datetime.now(UTC)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('pending','verified','expired','rejected')",
            name="ck_documents_verification_status",
        ),
        CheckConstraint(
            "provenance_type IN ('platform_issued','user_uploaded','digilocker','auto_fetched')",
            name="ck_documents_provenance_type",
        ),
        {"schema": "documents"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    subject_person_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    document_type: Mapped[str] = mapped_column(String(100), index=True)
    proof_category: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(250))
    issuer: Mapped[str | None] = mapped_column(String(250))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    verification_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    provenance_type: Mapped[str] = mapped_column(String(30))
    provenance_source: Mapped[str | None] = mapped_column(String(500))
    source_case_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    source_task_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    extracted_fields: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", MutableDict.as_mutable(JSON), default=dict
    )
    file_name: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(150))
    file_size: Mapped[int | None]
    # ponytail: encrypted DB blobs suit the MVP; move to object storage when volume grows.
    file_content: Mapped[bytes | None] = mapped_column(LargeBinary)
    superseded_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.documents.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    accesses: Mapped[list["DocumentAccessLog"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentAccessLog(Base):
    __tablename__ = "document_access_logs"
    __table_args__ = ({"schema": "documents"},)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.documents.id", ondelete="CASCADE"),
        index=True,
    )
    accessed_by_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    accessed_by_service: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(30))
    purpose: Mapped[str | None] = mapped_column(String(500))
    recipient: Mapped[str | None] = mapped_column(String(250))
    case_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    task_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    document: Mapped[Document] = relationship(back_populates="accesses")


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    __table_args__ = ({"schema": "documents"},)

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    consumer_group: Mapped[str] = mapped_column(String(100))

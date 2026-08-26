from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def now() -> datetime:
    return datetime.now(UTC)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "conversation_type IN ('intake','support','clarification')",
            name="ck_ai_conversations_type",
        ),
        CheckConstraint(
            "status IN ('active','completed','abandoned')",
            name="ck_ai_conversations_status",
        ),
        {"schema": "ai"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    conversation_type: Mapped[str] = mapped_column(String(30), default="intake")
    context: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSON), default=dict)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    messages: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON), default=list
    )
    extracted_profile: Mapped[dict[str, Any] | None] = mapped_column(MutableDict.as_mutable(JSON))
    model_used: Mapped[str] = mapped_column(String(100))
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    request_logs: Mapped[list["AIRequestLog"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class AIRequestLog(Base):
    __tablename__ = "ai_request_logs"
    __table_args__ = ({"schema": "ai"},)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ai.conversations.id", ondelete="SET NULL"),
        index=True,
    )
    request_type: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    conversation: Mapped[Conversation | None] = relationship(back_populates="request_logs")


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    __table_args__ = ({"schema": "ai"},)

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    consumer_group: Mapped[str] = mapped_column(String(100))

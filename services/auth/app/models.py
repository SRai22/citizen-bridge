from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(60))
    name: Mapped[str | None] = mapped_column(String(120))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    gender: Mapped[str | None] = mapped_column(String(50))
    caste_category: Mapped[str | None] = mapped_column(String(20))
    annual_income: Mapped[int | None] = mapped_column(BigInteger)
    occupation: Mapped[str | None] = mapped_column(String(120))
    education_level: Mapped[str | None] = mapped_column(String(120))
    marital_status: Mapped[str | None] = mapped_column(String(50))
    last_enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    phone: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    aadhaar_linked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = orm_relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    profile_provenance: Mapped[list["ProfileFieldProvenance"]] = orm_relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    family_members: Mapped[list["FamilyMember"]] = orm_relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class FamilyMember(Base):
    __tablename__ = "family_members"
    __table_args__ = (
        UniqueConstraint("user_id", "name", "relationship", name="uq_family_member_identity"),
        {"schema": "auth"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    relationship: Mapped[str] = mapped_column(String(50))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    phone: Mapped[str | None] = mapped_column(String(32))
    is_deceased: Mapped[bool] = mapped_column(Boolean, default=False)
    death_date: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    user: Mapped[User] = orm_relationship(back_populates="family_members")


class ProfileFieldProvenance(Base):
    __tablename__ = "profile_field_provenance"
    __table_args__ = (
        Index("ix_auth_profile_provenance_user_field", "user_id", "field_name"),
        {"schema": "auth"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE")
    )
    field_name: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(40))
    source_reference: Mapped[str | None] = mapped_column(String(500))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disputed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    user: Mapped[User] = orm_relationship(back_populates="profile_provenance")


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    __table_args__ = ({"schema": "auth"},)

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    consumer_group: Mapped[str] = mapped_column(String(100))


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_auth_refresh_tokens_token_hash", "token_hash", unique=True),
        {"schema": "auth"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    device_info: Mapped[str | None] = mapped_column(String(512))
    user: Mapped[User] = orm_relationship(back_populates="refresh_tokens")

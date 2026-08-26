"""Add progressive profile fields and provenance."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_profile_enrichment"
down_revision: str | None = "0002_partial_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name, type_ in (
        ("gender", sa.String(50)),
        ("caste_category", sa.String(20)),
        ("annual_income", sa.BigInteger()),
        ("occupation", sa.String(120)),
        ("education_level", sa.String(120)),
        ("marital_status", sa.String(50)),
        ("last_enriched_at", sa.DateTime(timezone=True)),
    ):
        op.add_column("users", sa.Column(name, type_, nullable=True), schema="auth")

    op.create_table(
        "profile_field_provenance",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(50), nullable=False),
        sa.Column("value", sa.String(500), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_reference", sa.String(500)),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("confirmed_by_user", sa.Boolean(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("disputed_at", sa.DateTime(timezone=True)),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="auth",
    )
    op.create_index(
        "ix_auth_profile_provenance_user_field",
        "profile_field_provenance",
        ["user_id", "field_name"],
        schema="auth",
    )
    op.create_table(
        "processed_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumer_group", sa.String(100), nullable=False),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_table("processed_events", schema="auth")
    op.drop_table("profile_field_provenance", schema="auth")
    for name in (
        "last_enriched_at",
        "marital_status",
        "education_level",
        "occupation",
        "annual_income",
        "caste_category",
        "gender",
    ):
        op.drop_column("users", name, schema="auth")

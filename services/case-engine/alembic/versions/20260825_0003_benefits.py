"""add active benefits

Revision ID: 20260825_0003
Revises: 20260825_0002
"""

import sqlalchemy as sa

from alembic import op

revision = "20260825_0003"
down_revision = "20260825_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The initial migration uses the live ORM metadata and may already have
    # created these tables on a fresh database. Keep this revision compatible
    # with both that path and databases created from the historical schema.
    tables = set(sa.inspect(op.get_bind()).get_table_names(schema="cases"))

    if "active_benefits" not in tables:
        op.create_table(
            "active_benefits",
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("benefit_id", sa.String(length=100), nullable=False),
            sa.Column("source_case_id", sa.Uuid(), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("amount", sa.String(length=100), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("next_payment_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["source_case_id"], ["cases.cases.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source_case_id"),
            sa.UniqueConstraint(
                "user_id", "benefit_id", name="uq_active_benefit_user_scheme"
            ),
            schema="cases",
        )
        op.create_index(
            "ix_cases_active_benefits_user_id",
            "active_benefits",
            ["user_id"],
            schema="cases",
        )
        op.create_index(
            "ix_cases_active_benefits_benefit_id",
            "active_benefits",
            ["benefit_id"],
            schema="cases",
        )
        op.create_index(
            "ix_cases_active_benefits_status",
            "active_benefits",
            ["status"],
            schema="cases",
        )

    if "benefit_discoveries" not in tables:
        op.create_table(
            "benefit_discoveries",
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("benefit_id", sa.String(length=100), nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id", "benefit_id", name="uq_benefit_discovery_user_scheme"
            ),
            schema="cases",
        )
        op.create_index(
            "ix_cases_benefit_discoveries_user_id",
            "benefit_discoveries",
            ["user_id"],
            schema="cases",
        )
        op.create_index(
            "ix_cases_benefit_discoveries_benefit_id",
            "benefit_discoveries",
            ["benefit_id"],
            schema="cases",
        )

    if "processed_events" not in tables:
        op.create_table(
            "processed_events",
            sa.Column("event_id", sa.String(length=36), nullable=False),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("consumer_group", sa.String(length=100), nullable=False),
            sa.PrimaryKeyConstraint("event_id"),
            schema="cases",
        )


def downgrade() -> None:
    op.drop_table("processed_events", schema="cases")
    op.drop_table("benefit_discoveries", schema="cases")
    op.drop_table("active_benefits", schema="cases")

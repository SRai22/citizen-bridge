"""Add citizen activity projection."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_activity_feed"
down_revision = "0002_notification_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_event_id", sa.String(36), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activity_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("description", sa.String(1000)),
        sa.Column("icon", sa.String(30), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True)),
        sa.Column("task_id", postgresql.UUID(as_uuid=True)),
        sa.Column("document_id", postgresql.UUID(as_uuid=True)),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_event_id", "user_id", "activity_type", name="uq_activity_source_user_type"
        ),
        schema="notifications",
    )
    for column in (
        "user_id",
        "activity_type",
        "category",
        "case_id",
        "task_id",
        "document_id",
        "occurred_at",
    ):
        op.create_index(
            f"ix_notifications_activity_entries_{column}",
            "activity_entries",
            [column],
            schema="notifications",
        )


def downgrade() -> None:
    op.drop_table("activity_entries", schema="notifications")

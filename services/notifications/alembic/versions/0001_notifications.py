"""Create notifications and preferences."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_notifications"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "priority IN ('urgent','normal','low')", name="ck_notifications_priority"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="notifications",
    )
    for column in ("user_id", "notification_type", "priority", "read", "created_at"):
        op.create_index(
            f"ix_notifications_notifications_{column}",
            "notifications",
            [column],
            schema="notifications",
        )
    op.create_table(
        "notification_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("push_enabled", sa.Boolean(), nullable=False),
        sa.Column("digest_enabled", sa.Boolean(), nullable=False),
        sa.Column("digest_day", sa.String(10), nullable=False),
        sa.Column("urgent_push", sa.Boolean(), nullable=False),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_notification_preferences_user_id"),
        schema="notifications",
    )
    op.create_index(
        "ix_notifications_notification_preferences_user_id",
        "notification_preferences",
        ["user_id"],
        schema="notifications",
    )


def downgrade() -> None:
    op.drop_table("notification_preferences", schema="notifications")
    op.drop_table("notifications", schema="notifications")

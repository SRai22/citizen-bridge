"""Add idempotent event tracking."""

import sqlalchemy as sa

from alembic import op

revision = "0002_processed_events"
down_revision = "0001_ai_service"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processed_events",
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumer_group", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
        schema="ai",
    )


def downgrade() -> None:
    op.drop_table("processed_events", schema="ai")

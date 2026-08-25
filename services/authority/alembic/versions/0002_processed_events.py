"""Add Kafka consumer idempotency tracking."""

import sqlalchemy as sa

from alembic import op

revision = "0002_authority_events"
down_revision = "0001_authority"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processed_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumer_group", sa.String(100), nullable=False),
        schema="authority",
    )


def downgrade() -> None:
    op.drop_table("processed_events", schema="authority")

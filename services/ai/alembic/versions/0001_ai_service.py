"""Create AI conversations and request logs."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_ai_service"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_type", sa.String(30), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("extracted_profile", sa.JSON()),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("total_tokens_used", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "conversation_type IN ('intake','support','clarification')",
            name="ck_ai_conversations_type",
        ),
        sa.CheckConstraint(
            "status IN ('active','completed','abandoned')",
            name="ck_ai_conversations_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="ai",
    )
    op.create_index("ix_ai_conversations_user_id", "conversations", ["user_id"], schema="ai")
    op.create_index("ix_ai_conversations_status", "conversations", ["status"], schema="ai")
    op.create_table(
        "ai_request_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("request_type", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("cost_estimate", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["ai.conversations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="ai",
    )
    op.create_index(
        "ix_ai_ai_request_logs_conversation_id",
        "ai_request_logs",
        ["conversation_id"],
        schema="ai",
    )
    op.create_index(
        "ix_ai_ai_request_logs_request_type",
        "ai_request_logs",
        ["request_type"],
        schema="ai",
    )


def downgrade() -> None:
    op.drop_table("ai_request_logs", schema="ai")
    op.drop_table("conversations", schema="ai")

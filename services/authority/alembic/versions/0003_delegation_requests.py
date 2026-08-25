"""Add delegation consent requests."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_delegation_requests"
down_revision = "0002_authority_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delegation_requests",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("from_user_id", postgresql.UUID(), nullable=False),
        sa.Column("to_user_id", postgresql.UUID(), nullable=False),
        sa.Column("scope_type", sa.String(20), nullable=False),
        sa.Column("scope_id", postgresql.UUID(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("message", sa.String(500)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("responded_at", sa.DateTime(timezone=True)),
        sa.Column("delegation_id", postgresql.UUID()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'expired')",
            name="ck_authority_delegation_requests_status",
        ),
        schema="authority",
    )
    for column in ("from_user_id", "to_user_id", "scope_id", "status"):
        op.create_index(
            f"ix_authority_delegation_requests_{column}",
            "delegation_requests",
            [column],
            schema="authority",
        )


def downgrade() -> None:
    op.drop_table("delegation_requests", schema="authority")

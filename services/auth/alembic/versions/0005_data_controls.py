"""Add data export and account deletion requests."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005_data_controls"
down_revision = "0004_family_members"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="auth",
    )
    op.create_index("ix_auth_data_exports_user_id", "data_exports", ["user_id"], schema="auth")
    op.create_index("ix_auth_data_exports_status", "data_exports", ["status"], schema="auth")
    op.create_table(
        "account_deletions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("cooling_off_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="auth",
    )
    op.create_index(
        "ix_auth_account_deletions_user_id",
        "account_deletions",
        ["user_id"],
        schema="auth",
    )
    op.create_index(
        "ix_auth_account_deletions_status",
        "account_deletions",
        ["status"],
        schema="auth",
    )
    op.create_index(
        "ix_auth_account_deletions_cooling_off_until",
        "account_deletions",
        ["cooling_off_until"],
        schema="auth",
    )


def downgrade() -> None:
    op.drop_table("account_deletions", schema="auth")
    op.drop_table("data_exports", schema="auth")

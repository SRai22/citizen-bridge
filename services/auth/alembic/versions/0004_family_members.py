"""Add family members."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_family_members"
down_revision: str | None = "0003_profile_enrichment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "family_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("relationship", sa.String(50), nullable=False),
        sa.Column("date_of_birth", sa.Date()),
        sa.Column("phone", sa.String(32)),
        sa.Column("is_deceased", sa.Boolean(), nullable=False),
        sa.Column("death_date", sa.Date()),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", "relationship", name="uq_family_member_identity"),
        schema="auth",
    )
    op.create_index("ix_auth_family_members_user_id", "family_members", ["user_id"], schema="auth")


def downgrade() -> None:
    op.drop_table("family_members", schema="auth")

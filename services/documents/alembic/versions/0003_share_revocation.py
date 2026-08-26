"""Track document share revocation."""

import sqlalchemy as sa

from alembic import op

revision = "0003_share_revocation"
down_revision = "0002_document_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_access_logs",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        schema="documents",
    )


def downgrade() -> None:
    op.drop_column("document_access_logs", "revoked_at", schema="documents")

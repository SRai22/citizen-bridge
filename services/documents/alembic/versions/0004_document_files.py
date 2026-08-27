"""Store uploaded document files."""

import sqlalchemy as sa

from alembic import op

revision = "0004_document_files"
down_revision = "0003_share_revocation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in (
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("mime_type", sa.String(150), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("file_content", sa.LargeBinary(), nullable=True),
    ):
        op.add_column("documents", column, schema="documents")


def downgrade() -> None:
    for column in ("file_content", "file_size", "mime_type", "file_name"):
        op.drop_column("documents", column, schema="documents")

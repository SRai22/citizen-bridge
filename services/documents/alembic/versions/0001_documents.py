"""Create documents and access logs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_documents"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_person_id", postgresql.UUID(as_uuid=True)),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("proof_category", sa.String(50), nullable=False),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("issuer", sa.String(250)),
        sa.Column("issued_at", sa.DateTime(timezone=True)),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("verification_status", sa.String(20), nullable=False),
        sa.Column("provenance_type", sa.String(30), nullable=False),
        sa.Column("provenance_source", sa.String(500)),
        sa.Column("source_case_id", postgresql.UUID(as_uuid=True)),
        sa.Column("source_task_id", postgresql.UUID(as_uuid=True)),
        sa.Column("extracted_fields", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("superseded_by_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "verification_status IN ('pending','verified','expired','rejected')",
            name="ck_documents_verification_status",
        ),
        sa.CheckConstraint(
            "provenance_type IN ('platform_issued','user_uploaded','digilocker','auto_fetched')",
            name="ck_documents_provenance_type",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_id"], ["documents.documents.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="documents",
    )
    for column in (
        "owner_user_id",
        "subject_person_id",
        "document_type",
        "proof_category",
        "valid_until",
        "verification_status",
        "source_case_id",
        "source_task_id",
    ):
        op.create_index(f"ix_documents_documents_{column}", "documents", [column], schema="documents")
    op.create_table(
        "document_access_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("accessed_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("accessed_by_service", sa.String(100)),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("purpose", sa.String(500)),
        sa.Column("recipient", sa.String(250)),
        sa.Column("case_id", postgresql.UUID(as_uuid=True)),
        sa.Column("task_id", postgresql.UUID(as_uuid=True)),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="documents",
    )
    op.create_index(
        "ix_documents_document_access_logs_document_id",
        "document_access_logs",
        ["document_id"],
        schema="documents",
    )
    op.create_index(
        "ix_documents_document_access_logs_accessed_by_user_id",
        "document_access_logs",
        ["accessed_by_user_id"],
        schema="documents",
    )


def downgrade() -> None:
    op.drop_table("document_access_logs", schema="documents")
    op.drop_table("documents", schema="documents")

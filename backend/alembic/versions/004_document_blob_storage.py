"""Corpus binaries in Postgres (BYTEA); optional nullable storage_path for legacy."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import BYTEA

revision: str = "004_doc_blob"
down_revision: Union[str, Sequence[str], None] = "003_prefs_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("content_bytes", BYTEA(), nullable=True))
    op.add_column("documents", sa.Column("size_bytes", sa.Integer(), nullable=True))

    op.alter_column(
        "documents",
        "storage_path",
        existing_type=sa.String(length=4096),
        nullable=True,
    )

    op.create_index(
        "ix_documents_ready_dedup",
        "documents",
        ["project_id", "knowledge_scope", "owner_principal_id", "checksum"],
        unique=False,
        postgresql_where=sa.text("status = 'ready' AND checksum IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_documents_ready_dedup", table_name="documents")
    op.alter_column(
        "documents",
        "storage_path",
        existing_type=sa.String(length=4096),
        nullable=False,
    )
    op.drop_column("documents", "size_bytes")
    op.drop_column("documents", "content_bytes")

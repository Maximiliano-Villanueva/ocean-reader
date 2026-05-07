"""Parent + child chunks for hybrid BM25 + vector RRF retrieval."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "005_chunk_hybrid"
down_revision: Union[str, Sequence[str], None] = "004_doc_blob"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chunks",
        sa.Column("parent_chunk_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_chunks_parent_chunk_id_chunks",
        "chunks",
        "chunks",
        ["parent_chunk_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_chunks_parent_chunk_id", "chunks", ["parent_chunk_id"])
    op.alter_column("chunks", "embedding", nullable=True)


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM chunks
             WHERE embedding IS NULL
            """
        )
    )
    op.alter_column("chunks", "embedding", nullable=False)
    op.drop_index("ix_chunks_parent_chunk_id", table_name="chunks")
    op.drop_constraint("fk_chunks_parent_chunk_id_chunks", "chunks", type_="foreignkey")
    op.drop_column("chunks", "parent_chunk_id")

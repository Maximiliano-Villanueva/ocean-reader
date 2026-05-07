"""Add validation_schemas table (versioned schema definitions per project)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "006_validation_schemas"
down_revision: Union[str, Sequence[str], None] = "005_chunk_hybrid"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "validation_schemas",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), nullable=False),
        sa.Column("schema_key", sa.String(length=128), nullable=False),
        sa.Column("version_label", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("body", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_validation_schemas_project_key", "validation_schemas", ["project_id", "schema_key"])
    op.create_index(
        "uq_validation_schemas_active_per_key",
        "validation_schemas",
        ["project_id", "schema_key"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"),
    )
    op.create_index(
        "uq_validation_schemas_version_per_project",
        "validation_schemas",
        ["project_id", "schema_key", "version_label"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_validation_schemas_version_per_project", table_name="validation_schemas")
    op.drop_index("uq_validation_schemas_active_per_key", table_name="validation_schemas")
    op.drop_index("ix_validation_schemas_project_key", table_name="validation_schemas")
    op.drop_table("validation_schemas")

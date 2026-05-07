"""Drop user_preferences table (snippets feature removed)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "007_drop_user_prefs"
down_revision: Union[str, Sequence[str], None] = "006_validation_schemas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("user_preferences")


def downgrade() -> None:
    """Restore empty prefs table compatible with pre-drop ORM (for dev rollback only)."""

    op.create_table(
        "user_preferences",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("project_id", UUID(as_uuid=True), nullable=True),
        sa.Column("knowledge_scope", sa.String(length=32), nullable=False, server_default="company"),
        sa.Column("owner_principal_id", UUID(as_uuid=True), nullable=True),
        sa.Column("snippets", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(knowledge_scope = 'company' AND owner_principal_id IS NULL) OR "
            "(knowledge_scope = 'user_private' AND owner_principal_id IS NOT NULL)",
            name="ck_prefs_knowledge_owner",
        ),
    )

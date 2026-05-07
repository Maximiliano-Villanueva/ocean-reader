"""Snippet knowledge scopes (company vs user-private) + organization isolation."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003_prefs_scope"
down_revision: Union[str, Sequence[str], None] = "002_org_scope"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "00000000-0000-4000-8000-000000000001"


def upgrade() -> None:
    op.add_column("user_preferences", sa.Column("organization_id", UUID(as_uuid=True), nullable=True))
    op.add_column(
        "user_preferences",
        sa.Column("knowledge_scope", sa.String(length=32), nullable=False, server_default="company"),
    )
    op.add_column("user_preferences", sa.Column("owner_principal_id", UUID(as_uuid=True), nullable=True))

    op.execute(
        sa.text(
            f"UPDATE user_preferences up SET organization_id = '{DEFAULT_ORG_ID}'::uuid "
            "WHERE up.project_id IS NULL"
        ),
    )

    op.execute(
        sa.text(
            """
            UPDATE user_preferences up
               SET organization_id = p.organization_id
              FROM projects p
             WHERE up.project_id IS NOT NULL
               AND up.project_id = p.id
               AND up.organization_id IS NULL
            """
        )
    )

    op.alter_column("user_preferences", "organization_id", nullable=False)

    op.create_foreign_key(
        "fk_user_preferences_organization_id",
        "user_preferences",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_prefs_knowledge_owner",
        "user_preferences",
        sa.text(
            "(knowledge_scope = 'company' AND owner_principal_id IS NULL) OR "
            "(knowledge_scope = 'user_private' AND owner_principal_id IS NOT NULL)"
        ),
    )


def downgrade() -> None:
    op.drop_constraint("ck_prefs_knowledge_owner", "user_preferences", type_="check")
    op.drop_constraint("fk_user_preferences_organization_id", "user_preferences", type_="foreignkey")
    op.drop_column("user_preferences", "owner_principal_id")
    op.drop_column("user_preferences", "knowledge_scope")
    op.drop_column("user_preferences", "organization_id")

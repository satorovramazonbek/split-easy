"""Create quick_split_drafts: the saved quick split page of a signed-in user.

Guests use the quick split page in memory only. After sign-in the page state
(free-form participant names and expenses) is saved here as one JSON document
per user, so it survives a page reload and a new login.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quick_split_drafts",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(data) > 0", name="ck_quick_split_drafts_data_not_empty"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_quick_split_drafts_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_quick_split_drafts"),
    )


def downgrade() -> None:
    op.drop_table("quick_split_drafts")

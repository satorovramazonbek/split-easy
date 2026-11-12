"""Add group_members.left_at: a member with history can leave at balance 0.

FR-7: the owner removes a member only when the member's balance is 0. A member
who paid or took part in expenses cannot lose the membership row - expenses and
settlements point to it (composite foreign keys, ON DELETE RESTRICT) and the
history must stay correct. Such a member is marked as left instead; a member
without any history is deleted as before.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "group_members",
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # SQLite >= 3.35 drops a plain column in place. Batch mode would copy and
    # drop the table, which foreign keys from expenses/settlements forbid.
    op.execute("ALTER TABLE group_members DROP COLUMN left_at")

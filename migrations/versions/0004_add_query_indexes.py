"""Add indexes for the main list and balance queries.

Kept separate from the table migrations so the benchmark can compare the same
data with and without them (``alembic downgrade 0003`` / ``upgrade 0004``).
Why each index exists and why some columns are not indexed: docs/DB.md.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_group_members_user_id", "group_members", ["user_id"]),
    (
        "ix_expenses_group_id_expense_date_id",
        "expenses",
        ["group_id", "expense_date", "id"],
    ),
    ("ix_expenses_group_id_paid_by", "expenses", ["group_id", "paid_by"]),
    ("ix_expense_shares_user_id", "expense_shares", ["user_id"]),
    ("ix_settlements_group_id_created_at", "settlements", ["group_id", "created_at"]),
    (
        "ix_notifications_user_id_created_at",
        "notifications",
        ["user_id", "created_at"],
    ),
]


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table)

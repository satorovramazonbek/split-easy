"""Make the (group_id, paid_by) expenses index covering by adding amount.

Measured on the seed data (docs/benchmark.md): "who paid how much" queries
(report 4, the paid part of report 1) read ``amount`` from the table for every
expense of the group. With ``amount`` in the index the table is not touched:
report 4 went from ~3.9 ms to ~0.5 ms. The old index is replaced, not kept,
so writes do not pay for two indexes on the same leading columns.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_expenses_group_id_paid_by", table_name="expenses")
    op.create_index(
        "ix_expenses_group_id_paid_by_amount",
        "expenses",
        ["group_id", "paid_by", "amount"],
    )


def downgrade() -> None:
    op.drop_index("ix_expenses_group_id_paid_by_amount", table_name="expenses")
    op.create_index("ix_expenses_group_id_paid_by", "expenses", ["group_id", "paid_by"])

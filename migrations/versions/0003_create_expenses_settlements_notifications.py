"""Create expenses, expense_shares, settlements and notifications tables.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("paid_by", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("split_type", sa.String(length=20), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        sa.CheckConstraint(
            "length(trim(description)) > 0", name="ck_expenses_description_not_blank"
        ),
        sa.CheckConstraint(
            "category IN ('food', 'transport', 'accommodation', 'other')",
            name="ck_expenses_category_valid",
        ),
        sa.CheckConstraint(
            "split_type IN ('equal', 'exact', 'percentage', 'shares')",
            name="ck_expenses_split_type_valid",
        ),
        sa.ForeignKeyConstraint(
            ["group_id", "paid_by"],
            ["group_members.group_id", "group_members.user_id"],
            name="fk_expenses_group_id_paid_by_group_members",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.id"],
            name="fk_expenses_group_id_groups",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_expenses_created_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_expenses"),
    )
    op.create_table(
        "expense_shares",
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("share_amount", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "share_amount >= 0", name="ck_expense_shares_share_amount_non_negative"
        ),
        sa.ForeignKeyConstraint(
            ["expense_id"],
            ["expenses.id"],
            name="fk_expense_shares_expense_id_expenses",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_expense_shares_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("expense_id", "user_id", name="pk_expense_shares"),
    )
    op.create_table(
        "settlements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("from_user_id", sa.Integer(), nullable=False),
        sa.Column("to_user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_settlements_amount_positive"),
        sa.CheckConstraint(
            "from_user_id <> to_user_id", name="ck_settlements_different_users"
        ),
        sa.ForeignKeyConstraint(
            ["group_id", "from_user_id"],
            ["group_members.group_id", "group_members.user_id"],
            name="fk_settlements_group_id_from_user_id_group_members",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["group_id", "to_user_id"],
            ["group_members.group_id", "group_members.user_id"],
            name="fk_settlements_group_id_to_user_id_group_members",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.id"],
            name="fk_settlements_group_id_groups",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_settlements"),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(trim(message)) > 0", name="ck_notifications_message_not_blank"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_notifications_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("settlements")
    op.drop_table("expense_shares")
    op.drop_table("expenses")

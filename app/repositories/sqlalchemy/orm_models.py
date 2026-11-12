"""SQLAlchemy table mappings.

The schema is described in docs/DB.md and must stay identical to the Alembic
migrations (migrations/) and the hand-written docs/schema.sql; a test checks it.

Integrity rules live in the database itself, not only in Python:
- CHECK: positive amounts, non-negative shares, no self-settlement, enum values;
- composite foreign keys to group_members: whoever pays an expense or takes part
  in a settlement must be a member of that group, and a member with financial
  history cannot be removed (ON DELETE RESTRICT).
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.models import Category, SplitType
from app.infrastructure.database import Base


def _in(column: str, values: type[Category] | type[SplitType]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GroupORM(Base):
    __tablename__ = "groups"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("length(currency) = 3", name="currency_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    # Soft delete: expenses and settlements of a deleted group stay in history.
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GroupMemberORM(Base):
    """M:N link between users and groups; the PK forbids duplicates."""

    __tablename__ = "group_members"
    __table_args__ = (
        # "My groups": the PK (group_id, user_id) cannot be used to search by user.
        Index("ix_group_members_user_id", "user_id"),
    )

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # FR-7: a member with financial history whose balance is 0 "leaves": the
    # row stays (expenses and settlements point to it), only left_at is set.
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExpenseORM(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("length(trim(description)) > 0", name="description_not_blank"),
        CheckConstraint(_in("category", Category), name="category_valid"),
        CheckConstraint(_in("split_type", SplitType), name="split_type_valid"),
        ForeignKeyConstraint(
            ["group_id", "paid_by"],
            ["group_members.group_id", "group_members.user_id"],
            ondelete="RESTRICT",
        ),
        # Group expense list, newest first, paginated.
        Index("ix_expenses_group_id_expense_date_id", "group_id", "expense_date", "id"),
        # "Who paid how much" per group; also serves the composite FK check.
        # amount makes it covering: the table is not read (migration 0005).
        Index("ix_expenses_group_id_paid_by_amount", "group_id", "paid_by", "amount"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="RESTRICT"))
    description: Mapped[str] = mapped_column(String(200))
    amount: Mapped[int] = mapped_column(Integer)  # in so'm, never float
    paid_by: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(20))
    split_type: Mapped[str] = mapped_column(String(20))
    expense_date: Mapped[date] = mapped_column(Date)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Python-side link only (no schema change). The default lazy loading issues
    # one query per expense when shares are read in a loop - the N+1 problem;
    # list queries use selectinload() instead (see docs/DB.md, section 6).
    shares: Mapped[list["ExpenseShareORM"]] = relationship(
        order_by="ExpenseShareORM.user_id",
        cascade="all, delete-orphan",
        passive_deletes=True,  # the database cascades the delete itself
    )


class ExpenseShareORM(Base):
    """Stored split result (deliberate denormalization, see docs/DB.md)."""

    __tablename__ = "expense_shares"
    __table_args__ = (
        CheckConstraint("share_amount >= 0", name="share_amount_non_negative"),
        # Total owed by a user across expenses (balances).
        Index("ix_expense_shares_user_id", "user_id"),
    )

    expense_id: Mapped[int] = mapped_column(
        ForeignKey("expenses.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    share_amount: Mapped[int] = mapped_column(Integer)


class SettlementORM(Base):
    __tablename__ = "settlements"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("from_user_id <> to_user_id", name="different_users"),
        ForeignKeyConstraint(
            ["group_id", "from_user_id"],
            ["group_members.group_id", "group_members.user_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["group_id", "to_user_id"],
            ["group_members.group_id", "group_members.user_id"],
            ondelete="RESTRICT",
        ),
        # Settlement history of a group in time order.
        Index("ix_settlements_group_id_created_at", "group_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="RESTRICT"))
    from_user_id: Mapped[int] = mapped_column(Integer)
    to_user_id: Mapped[int] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class NotificationORM(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("length(trim(message)) > 0", name="message_not_blank"),
        # "My notifications", newest first.
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QuickSplitDraftORM(Base):
    """The signed-in user's quick split page (participants and expenses as JSON).

    One row per user. The page is a scratchpad with free-form names, not group
    members, so it is kept as a JSON document instead of rows in ``expenses``;
    the service validates its structure before saving (migration 0006).
    """

    __tablename__ = "quick_split_drafts"
    __table_args__ = (CheckConstraint("length(data) > 0", name="data_not_empty"),)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    data: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

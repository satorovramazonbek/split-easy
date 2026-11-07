"""Domain models.

Plain Python dataclasses with no dependency on FastAPI or SQLAlchemy.
Validation that protects business invariants lives here, so an invalid
object cannot be created in the first place.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from app.domain.exceptions import InvalidAmountError, InvalidSplitError
from app.domain.money import validate_amount


class SplitType(StrEnum):
    """Supported ways to split an expense."""

    EQUAL = "equal"
    EXACT = "exact"
    PERCENTAGE = "percentage"
    SHARES = "shares"


class Category(StrEnum):
    """Expense categories."""

    FOOD = "food"
    TRANSPORT = "transport"
    ACCOMMODATION = "accommodation"
    OTHER = "other"


@dataclass(frozen=True)
class User:
    """A registered user (DESIGN.md 5.1). Only the password hash is stored."""

    id: int | None
    username: str
    email: str
    password_hash: str
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Group:
    """A group of users that share expenses."""

    id: int
    name: str
    currency: str
    owner_id: int
    is_deleted: bool = False
    created_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class GroupMember:
    """Membership of a user in a group."""

    group_id: int
    user_id: int
    joined_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class ExpenseShare:
    """The part of an expense that one participant owes."""

    user_id: int
    share_amount: int

    def __post_init__(self) -> None:
        if isinstance(self.share_amount, bool) or not isinstance(
            self.share_amount, int
        ):
            raise InvalidAmountError("Share amount must be an integer")
        if self.share_amount < 0:
            raise InvalidAmountError("Share amount cannot be negative")


@dataclass(frozen=True)
class Expense:
    """An expense paid by one member and split between participants.

    Invariant: the sum of ``shares`` is exactly ``amount``.
    """

    id: int | None
    group_id: int
    description: str
    amount: int
    paid_by: int
    split_type: SplitType
    shares: tuple[ExpenseShare, ...]
    category: Category = Category.OTHER
    expense_date: date = field(default_factory=date.today)
    created_by: int | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        validate_amount(self.amount)
        if not self.shares:
            raise InvalidSplitError("Expense must have at least one participant")
        if len(set(self.participant_ids)) != len(self.shares):
            raise InvalidSplitError("Each participant can appear only once")
        shares_sum = sum(share.share_amount for share in self.shares)
        if shares_sum != self.amount:
            raise InvalidSplitError(
                f"Shares sum ({shares_sum}) must equal amount ({self.amount})"
            )

    @property
    def participant_ids(self) -> list[int]:
        """User ids of all participants, in order."""
        return [share.user_id for share in self.shares]


@dataclass(frozen=True)
class Settlement:
    """A payment from one member to another that reduces debt."""

    id: int | None
    group_id: int
    from_user_id: int
    to_user_id: int
    amount: int
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        validate_amount(self.amount)
        if self.from_user_id == self.to_user_id:
            raise InvalidSplitError("A user cannot settle with themselves")


@dataclass
class Notification:
    """An in-app notification for a user."""

    id: int | None
    user_id: int
    message: str
    is_read: bool = False
    created_at: datetime = field(default_factory=datetime.now)

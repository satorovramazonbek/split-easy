"""Group expenses and settlements (DESIGN.md: ExpenseService, SettlementService).

Every write goes through the Unit of Work: an expense with all its shares and
the notifications for its participants, or a settlement and the notification
for the other party, is saved completely or not at all (spec section 10.4).

Access rules:
- only members of a group see and add its expenses and settlements;
- the payer, every participant and both settlement parties must be members;
- an expense is deleted by its author or by the group owner;
- a settlement is recorded by one of its parties or by the group owner.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.domain.exceptions import DomainError
from app.domain.models import Category, Expense, Notification, Settlement, SplitType
from app.domain.split_strategies import Participant
from app.repositories.interfaces.errors import ReferenceIntegrityError
from app.repositories.interfaces.unit_of_work import UnitOfWork
from app.services.group_service import require_member_group
from app.services.quick_split_service import split_amount

MAX_DESCRIPTION_LENGTH = 200
MAX_PAGE_SIZE = 100


class ExpenseError(Exception):
    """Base class for expense and settlement errors."""


class InvalidExpenseError(ExpenseError):
    """The input breaks a rule (amount, split values, unknown member, ...)."""


class ExpenseNotFoundError(ExpenseError):
    """No such expense in this group."""


class ExpensePermissionError(ExpenseError):
    """The user may not change this expense or record this settlement."""


# Domain errors are in English (they are also used by the JSON quick split);
# the web pages show them in Uzbek.
_UZ_ERRORS: list[tuple[re.Pattern[str], Callable[[re.Match[str]], str]]] = [
    (
        re.compile(r"Exact amounts sum \((\d+)\) must equal total \((\d+)\)"),
        lambda m: f"Aniq summalar yig'indisi ({m[1]}) umumiy summaga ({m[2]}) "
        "teng bo'lishi kerak",
    ),
    (
        re.compile(r"Percentages must add up to 100, got (.+)"),
        lambda m: f"Foizlar yig'indisi 100 bo'lishi kerak (hozir: {m[1]})",
    ),
    (
        re.compile(r"Exact amounts must be whole numbers|Exact split requires integer"),
        lambda m: "Aniq summalar butun son bo'lishi kerak",
    ),
    (
        re.compile(r"Exact amounts cannot be negative"),
        lambda m: "Summa manfiy bo'lishi mumkin emas",
    ),
    (
        re.compile(r"(Percentage|Share) must be positive"),
        lambda m: "Har bir ishtirokchi uchun musbat qiymat kiriting",
    ),
    (
        re.compile(r"(Percentage|Share) must be an integer or Decimal"),
        lambda m: "Har bir tanlangan ishtirokchi uchun qiymat kiriting",
    ),
    (
        re.compile(r"Amount must be"),
        lambda m: "Summa musbat butun son bo'lishi kerak",
    ),
    (
        re.compile(r"at least one participant"),
        lambda m: "Kamida bitta ishtirokchini tanlang",
    ),
    (
        re.compile(r"only once"),
        lambda m: "Har bir ishtirokchi faqat bir marta tanlanadi",
    ),
    (
        re.compile(r"Unknown split type"),
        lambda m: "Bo'lish usuli noto'g'ri",
    ),
]


def translate_error(message: str) -> str:
    for pattern, render in _UZ_ERRORS:
        match = pattern.search(message)
        if match:
            return render(match)
    return message


def _money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


@dataclass(frozen=True)
class ExpenseData:
    """A new group expense as entered by the user."""

    description: str
    amount: int
    paid_by: int
    split_type: str
    participants: Sequence[Participant]
    category: str = Category.OTHER.value
    expense_date: date | None = None


@dataclass(frozen=True)
class ExpensePage:
    items: list[Expense]
    total: int
    limit: int
    offset: int


class ExpenseService:
    def __init__(
        self,
        uow: UnitOfWork,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._uow = uow
        self._clock = clock

    # --- expenses ------------------------------------------------------------

    def add_expense(self, user, group_id: int, data: ExpenseData) -> Expense:
        with self._uow as uow:
            group = require_member_group(uow.groups, user, group_id)
            members = {m.user_id for m in uow.groups.list_members(group.id)}
            expense = self._build(user, group.id, members, data)
            try:
                saved = uow.expenses.add(expense)
            except ReferenceIntegrityError as error:
                raise InvalidExpenseError("Ishtirokchi guruh a'zosi emas") from error

            author = user.username
            uow.notifications.add_many(
                Notification(
                    id=None,
                    user_id=share.user_id,
                    message=(
                        f"{author} «{group.name}» guruhiga «{saved.description}» "
                        f"xarajatini qo'shdi ({_money(saved.amount)} {group.currency}). "
                        f"Sizning ulushingiz: {_money(share.share_amount)} "
                        f"{group.currency}."
                    ),
                    created_at=saved.created_at,
                )
                for share in saved.shares
                if share.user_id != user.id and share.share_amount > 0
            )
            uow.commit()
            return saved

    # Reads do not open the Unit of Work: leaving it without commit() rolls the
    # request's session back, which would also drop earlier unsaved writes.

    def list_expenses(
        self, user, group_id: int, *, limit: int = 20, offset: int = 0
    ) -> ExpensePage:
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        offset = max(0, offset)
        uow = self._uow
        require_member_group(uow.groups, user, group_id)
        return ExpensePage(
            items=uow.expenses.list_for_group(group_id, limit=limit, offset=offset),
            total=uow.expenses.count_for_group(group_id),
            limit=limit,
            offset=offset,
        )

    def get_expense(self, user, group_id: int, expense_id: int) -> Expense:
        require_member_group(self._uow.groups, user, group_id)
        return self._expense_in_group(self._uow, group_id, expense_id)

    def delete_expense(self, user, group_id: int, expense_id: int) -> None:
        with self._uow as uow:
            group = require_member_group(uow.groups, user, group_id)
            expense = self._expense_in_group(uow, group_id, expense_id)
            if user.id not in (expense.created_by, group.owner_id):
                raise ExpensePermissionError(
                    "Xarajatni faqat uni qo'shgan foydalanuvchi yoki guruh egasi "
                    "o'chira oladi"
                )
            uow.expenses.delete(expense.id)
            uow.commit()

    # --- settlements ---------------------------------------------------------

    def record_settlement(
        self, user, group_id: int, from_user_id: int, to_user_id: int, amount: int
    ) -> Settlement:
        with self._uow as uow:
            group = require_member_group(uow.groups, user, group_id)
            if user.id not in (from_user_id, to_user_id, group.owner_id):
                raise ExpensePermissionError(
                    "To'lovni faqat uning ishtirokchisi yoki guruh egasi belgilay oladi"
                )
            members = {m.user_id for m in uow.groups.list_members(group.id)}
            if from_user_id not in members or to_user_id not in members:
                raise InvalidExpenseError("To'lov ishtirokchilari guruh a'zosi emas")
            try:
                settlement = Settlement(
                    id=None,
                    group_id=group.id,
                    from_user_id=from_user_id,
                    to_user_id=to_user_id,
                    amount=amount,
                    created_at=self._clock(),
                )
            except DomainError as error:
                if "themselves" in str(error):
                    raise InvalidExpenseError(
                        "O'zingizga to'lov qilib bo'lmaydi"
                    ) from error
                raise InvalidExpenseError(translate_error(str(error))) from error
            try:
                saved = uow.settlements.add(settlement)
            except ReferenceIntegrityError as error:
                raise InvalidExpenseError(
                    "To'lov ishtirokchilari guruh a'zosi emas"
                ) from error

            users = uow.users.get_many([from_user_id, to_user_id])
            other = to_user_id if user.id == from_user_id else from_user_id
            uow.notifications.add_many(
                [
                    Notification(
                        id=None,
                        user_id=other,
                        message=(
                            f"«{group.name}»: {users[from_user_id].username} → "
                            f"{users[to_user_id].username} "
                            f"{_money(amount)} {group.currency} to'lovi belgilandi."
                        ),
                        created_at=saved.created_at,
                    )
                ]
                if other != user.id
                else []
            )
            uow.commit()
            return saved

    def list_settlements(self, user, group_id: int) -> list[Settlement]:
        require_member_group(self._uow.groups, user, group_id)
        return self._uow.settlements.list_for_group(group_id)

    # --- helpers -------------------------------------------------------------

    def _build(self, user, group_id: int, members: set[int], data) -> Expense:
        description = " ".join(data.description.split())
        if not description:
            raise InvalidExpenseError("Xarajat tavsifini kiriting")
        if len(description) > MAX_DESCRIPTION_LENGTH:
            raise InvalidExpenseError(
                f"Tavsif {MAX_DESCRIPTION_LENGTH} belgidan oshmasligi kerak"
            )
        try:
            category = Category(data.category)
        except ValueError:
            raise InvalidExpenseError("Kategoriya noto'g'ri") from None
        try:
            split_type = SplitType(data.split_type)
        except ValueError:
            raise InvalidExpenseError("Bo'lish usuli noto'g'ri") from None
        if data.paid_by not in members:
            raise InvalidExpenseError("To'lovchi guruh a'zosi bo'lishi kerak")
        if not data.participants:
            raise InvalidExpenseError("Kamida bitta ishtirokchini tanlang")
        if any(p.user_id not in members for p in data.participants):
            raise InvalidExpenseError("Har bir ishtirokchi guruh a'zosi bo'lishi kerak")

        now = self._clock()
        try:
            shares = split_amount(data.amount, split_type.value, data.participants)
            return Expense(
                id=None,
                group_id=group_id,
                description=description,
                amount=data.amount,
                paid_by=data.paid_by,
                split_type=split_type,
                shares=tuple(shares),
                category=category,
                expense_date=data.expense_date or now.date(),
                created_by=user.id,
                created_at=now,
            )
        except DomainError as error:
            raise InvalidExpenseError(translate_error(str(error))) from error

    @staticmethod
    def _expense_in_group(uow, group_id: int, expense_id: int) -> Expense:
        expense = uow.expenses.get(expense_id)
        if expense is None or expense.group_id != group_id:
            raise ExpenseNotFoundError("Xarajat topilmadi")
        return expense

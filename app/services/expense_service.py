"""Group expenses: add, list, edit, delete (FR-10 - FR-14).

Single responsibility: this class only knows the rules of expenses.
- Settlements live in ``SettlementService``.
- Notifications are not created here: after an expense is saved the service
  publishes an ``ExpenseAdded`` event; the notifiers subscribed to it (in-app,
  email) react (Observer). The service does not know them.

Transactions (spec 10.4): the expense, all its shares and whatever the
observers write (notifications) are saved through one Unit of Work - all or
nothing. An edit replaces the old shares in the same transaction.

Access rules:
- only members see and add expenses of a group;
- the payer and every participant must be members;
- an expense is edited or deleted by its author or by the group owner (FR-12).
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.domain.events import EventPublisher, ExpenseAdded, ShareInfo
from app.domain.exceptions import DomainError
from app.domain.models import Category, Expense, Group, SplitType, User
from app.domain.split_strategies import Participant
from app.domain.split_strategy_factory import split_amount
from app.repositories.interfaces.errors import ReferenceIntegrityError
from app.repositories.interfaces.unit_of_work import UnitOfWork
from app.services.group_service import require_member_group
from app.services.messages import translate_error

MAX_DESCRIPTION_LENGTH = 200
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


class ExpenseError(Exception):
    """Base class for expense errors."""


class InvalidExpenseError(ExpenseError):
    """The input breaks a rule (amount, split values, unknown member, ...)."""


class ExpenseNotFoundError(ExpenseError):
    """No such expense in this group."""


class ExpensePermissionError(ExpenseError):
    """The user may not change this expense."""


@dataclass(frozen=True)
class ExpenseData:
    """A group expense as entered by the user (new or edited)."""

    description: str
    amount: int
    paid_by: int
    split_type: str
    participants: Sequence[Participant]
    category: str = Category.OTHER.value
    expense_date: date | None = None


@dataclass(frozen=True)
class ExpensePage:
    """One page of the expense list (FR-13)."""

    items: list[Expense]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        return max(1, math.ceil(self.total / self.page_size))


class ExpenseService:
    def __init__(
        self,
        uow: UnitOfWork,
        events: EventPublisher,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._uow = uow
        self._events = events
        self._clock = clock

    # --- writing (inside the Unit of Work) ---------------------------------

    def add_expense(self, user: User, group_id: int, data: ExpenseData) -> Expense:
        with self._uow as uow:
            group = require_member_group(uow.groups, user, group_id)
            now = self._clock()
            expense = self._build(
                group, data, created_by=user.id, created_at=now, today=now.date()
            )
            try:
                saved = uow.expenses.add(expense)
            except ReferenceIntegrityError as error:
                raise InvalidExpenseError("Ishtirokchi guruh a'zosi emas") from error
            # Observers (notifications) write in this same transaction.
            self._events.publish(
                ExpenseAdded(
                    group_id=group.id,
                    group_name=group.name,
                    currency=group.currency,
                    expense_id=saved.id,
                    description=saved.description,
                    amount=saved.amount,
                    author_id=user.id,
                    author_name=user.username,
                    shares=tuple(
                        ShareInfo(s.user_id, s.share_amount) for s in saved.shares
                    ),
                )
            )
            uow.commit()
            return saved

    def update_expense(
        self, user: User, group_id: int, expense_id: int, data: ExpenseData
    ) -> Expense:
        """FR-12: author or owner; old shares are replaced in one transaction."""
        with self._uow as uow:
            group = require_member_group(uow.groups, user, group_id)
            old = self._expense_in_group(uow, group_id, expense_id)
            self._check_can_change(user, group, old, "tahrirlay")
            expense = self._build(
                group,
                data,
                created_by=old.created_by,
                created_at=old.created_at,
                today=self._clock().date(),
                expense_id=old.id,
            )
            try:
                saved = uow.expenses.replace(expense)
            except ReferenceIntegrityError as error:
                raise InvalidExpenseError("Ishtirokchi guruh a'zosi emas") from error
            uow.commit()
            return saved

    def delete_expense(self, user: User, group_id: int, expense_id: int) -> None:
        with self._uow as uow:
            group = require_member_group(uow.groups, user, group_id)
            expense = self._expense_in_group(uow, group_id, expense_id)
            self._check_can_change(user, group, expense, "o'chira")
            uow.expenses.delete(expense.id)
            uow.commit()

    # --- reading --------------------------------------------------------------
    # Reads do not open the Unit of Work: leaving it without commit() rolls the
    # request's session back, which would also drop earlier unsaved writes.

    def list_expenses(
        self,
        user: User,
        group_id: int,
        *,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        category: str | None = None,
    ) -> ExpensePage:
        """FR-13 (newest first, paginated) and FR-14 (category filter)."""
        require_member_group(self._uow.groups, user, group_id)
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))
        try:
            chosen = Category(category) if category else None
        except ValueError:
            raise InvalidExpenseError("Kategoriya noto'g'ri") from None
        total = self._uow.expenses.count_for_group(group_id, chosen)
        last_page = max(1, math.ceil(total / page_size))
        page = min(max(1, page), last_page)
        items = self._uow.expenses.list_for_group(
            group_id, limit=page_size, offset=(page - 1) * page_size, category=chosen
        )
        return ExpensePage(items=items, total=total, page=page, page_size=page_size)

    def get_expense(self, user: User, group_id: int, expense_id: int) -> Expense:
        require_member_group(self._uow.groups, user, group_id)
        return self._expense_in_group(self._uow, group_id, expense_id)

    def all_expenses(self, user: User, group_id: int) -> list[Expense]:
        """Every expense of the group, newest first (used by the export)."""
        require_member_group(self._uow.groups, user, group_id)
        total = self._uow.expenses.count_for_group(group_id)
        return self._uow.expenses.list_for_group(group_id, limit=max(total, 1))

    # --- helpers --------------------------------------------------------------

    def _build(
        self,
        group: Group,
        data: ExpenseData,
        *,
        created_by: int | None,
        created_at: datetime,
        today: date,
        expense_id: int | None = None,
    ) -> Expense:
        """Validate the input and split the amount with the chosen strategy."""
        members = {m.user_id for m in self._uow.groups.list_members(group.id)}
        description = " ".join(data.description.split())
        if not description:
            raise InvalidExpenseError("Xarajat tavsifini kiriting")
        if len(description) > MAX_DESCRIPTION_LENGTH:
            raise InvalidExpenseError(
                f"Tavsif {MAX_DESCRIPTION_LENGTH} belgidan oshmasligi kerak"
            )
        try:
            category = Category(data.category)
            split_type = SplitType(data.split_type)
        except ValueError:
            raise InvalidExpenseError(
                "Kategoriya yoki bo'lish usuli noto'g'ri"
            ) from None
        expense_date = data.expense_date or today
        if expense_date > today:
            raise InvalidExpenseError("Sana kelajakda bo'lishi mumkin emas")
        if data.paid_by not in members:
            raise InvalidExpenseError("To'lovchi guruh a'zosi bo'lishi kerak")
        if not data.participants:
            raise InvalidExpenseError("Kamida bitta ishtirokchini tanlang")
        if any(p.user_id not in members for p in data.participants):
            raise InvalidExpenseError("Har bir ishtirokchi guruh a'zosi bo'lishi kerak")
        try:
            shares = split_amount(data.amount, split_type.value, data.participants)
            return Expense(
                id=expense_id,
                group_id=group.id,
                description=description,
                amount=data.amount,
                paid_by=data.paid_by,
                split_type=split_type,
                shares=tuple(shares),
                category=category,
                expense_date=expense_date,
                created_by=created_by,
                created_at=created_at,
            )
        except DomainError as error:
            raise InvalidExpenseError(translate_error(str(error))) from error

    @staticmethod
    def _check_can_change(
        user: User, group: Group, expense: Expense, verb: str
    ) -> None:
        if user.id not in (expense.created_by, group.owner_id):
            raise ExpensePermissionError(
                f"Xarajatni faqat uni qo'shgan foydalanuvchi yoki guruh egasi "
                f"{verb} oladi"
            )

    @staticmethod
    def _expense_in_group(uow: UnitOfWork, group_id: int, expense_id: int) -> Expense:
        expense = uow.expenses.get(expense_id)
        if expense is None or expense.group_id != group_id:
            raise ExpenseNotFoundError("Xarajat topilmadi")
        return expense

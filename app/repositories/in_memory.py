"""In-memory implementation of every repository (Repository pattern, 2nd version).

The services depend only on the interfaces in ``app/repositories/interfaces``.
These classes keep the data in Python dicts, so services can be tested without
a database (NFR-4) and fast. The same contract tests run against them and the
SQLAlchemy versions (``tests/integration/test_repository_contracts.py``), which
shows they are interchangeable (Liskov Substitution).
"""

from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime
from itertools import count
from types import TracebackType
from typing import Self

from app.domain.balance import calculate_balances
from app.domain.models import (
    Category,
    Expense,
    Group,
    GroupMember,
    Notification,
    Settlement,
    User,
)
from app.repositories.interfaces.errors import ReferenceIntegrityError
from app.repositories.interfaces.group_repository import DuplicateMemberError
from app.repositories.interfaces.report_repository import MemberBalance
from app.repositories.interfaces.user_repository import DuplicateUserError


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.users: dict[int, User] = {}

    def add(self, user: User) -> User:
        if any(
            u.username == user.username or u.email == user.email
            for u in self.users.values()
        ):
            raise DuplicateUserError(user.username)
        stored = replace(user, id=len(self.users) + 1)
        self.users[stored.id] = stored
        return stored

    def get_by_id(self, user_id: int) -> User | None:
        return self.users.get(user_id)

    def get_many(self, user_ids: Iterable[int]) -> dict[int, User]:
        return {i: self.users[i] for i in user_ids if i in self.users}

    def get_by_username(self, username: str) -> User | None:
        return next((u for u in self.users.values() if u.username == username), None)

    def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    def update_username(self, user_id: int, username: str) -> User:
        if any(u.username == username and u.id != user_id for u in self.users.values()):
            raise DuplicateUserError(username)
        stored = replace(self.users[user_id], username=username)
        self.users[user_id] = stored
        return stored


class InMemoryGroupRepository:
    def __init__(self, history: "InMemoryHistory | None" = None) -> None:
        self.groups: dict[int, Group] = {}
        self.members: dict[tuple[int, int], GroupMember] = {}
        self.left: dict[tuple[int, int], datetime] = {}
        self._history = history

    def add(self, group: Group) -> Group:
        stored = replace(group, id=len(self.groups) + 1)
        self.groups[stored.id] = stored
        return stored

    def get_by_id(self, group_id: int) -> Group | None:
        return self.groups.get(group_id)

    def list_for_user(self, user_id: int) -> list[Group]:
        return sorted(
            (
                g
                for g in self.groups.values()
                if not g.is_deleted and (g.id, user_id) in self.members
            ),
            key=lambda g: (g.created_at, g.id),
            reverse=True,
        )

    def mark_deleted(self, group_id: int) -> None:
        self.groups[group_id] = replace(self.groups[group_id], is_deleted=True)

    def add_member(self, member: GroupMember) -> GroupMember:
        key = (member.group_id, member.user_id)
        if key in self.members:
            raise DuplicateMemberError(str(key))
        self.left.pop(key, None)  # a member who left comes back
        self.members[key] = member
        return member

    def remove_member(self, group_id: int, user_id: int, at: datetime) -> None:
        key = (group_id, user_id)
        self.members.pop(key, None)
        if self._history is not None and self._history.has_history(group_id, user_id):
            self.left[key] = at

    def is_member(self, group_id: int, user_id: int) -> bool:
        return (group_id, user_id) in self.members

    def list_members(self, group_id: int) -> list[GroupMember]:
        return sorted(
            (m for (g, _), m in self.members.items() if g == group_id),
            key=lambda m: (m.joined_at, m.user_id),
        )


class InMemoryExpenseRepository:
    def __init__(self, groups: InMemoryGroupRepository) -> None:
        self.expenses: dict[int, Expense] = {}
        self._groups = groups
        self._ids = count(1)

    def get(self, expense_id: int) -> Expense | None:
        return self.expenses.get(expense_id)

    def _of_group(self, group_id: int, category: Category | None) -> list[Expense]:
        rows = [
            e
            for e in self.expenses.values()
            if e.group_id == group_id and (category is None or e.category == category)
        ]
        return sorted(rows, key=lambda e: (e.expense_date, e.id), reverse=True)

    def list_for_group(
        self,
        group_id: int,
        *,
        limit: int = 20,
        offset: int = 0,
        category: Category | None = None,
    ) -> list[Expense]:
        return self._of_group(group_id, category)[offset : offset + limit]

    def count_for_group(self, group_id: int, category: Category | None = None) -> int:
        return len(self._of_group(group_id, category))

    def _check(self, expense: Expense) -> None:
        # Same rule as the composite foreign key in the database.
        if not self._groups.is_member(expense.group_id, expense.paid_by):
            raise ReferenceIntegrityError("payer is not a member of the group")

    def add(self, expense: Expense) -> Expense:
        self._check(expense)
        stored = replace(expense, id=next(self._ids))
        self.expenses[stored.id] = stored
        return stored

    def replace(self, expense: Expense) -> Expense:
        if expense.id not in self.expenses:
            raise LookupError(f"Expense {expense.id} does not exist")
        self._check(expense)
        self.expenses[expense.id] = expense
        return expense

    def delete(self, expense_id: int) -> None:
        self.expenses.pop(expense_id, None)


class InMemorySettlementRepository:
    def __init__(self, groups: InMemoryGroupRepository) -> None:
        self.settlements: list[Settlement] = []
        self._groups = groups

    def add(self, settlement: Settlement) -> Settlement:
        for user_id in (settlement.from_user_id, settlement.to_user_id):
            if not self._groups.is_member(settlement.group_id, user_id):
                raise ReferenceIntegrityError("party is not a member of the group")
        stored = replace(settlement, id=len(self.settlements) + 1)
        self.settlements.append(stored)
        return stored

    def list_for_group(self, group_id: int) -> list[Settlement]:
        return [s for s in self.settlements if s.group_id == group_id]


class InMemoryNotificationRepository:
    def __init__(self) -> None:
        self.notifications: list[Notification] = []

    def add_many(self, notifications: Iterable[Notification]) -> list[Notification]:
        stored = []
        for n in notifications:
            stored.append(replace(n, id=len(self.notifications) + 1))
            self.notifications.append(stored[-1])
        return stored

    def list_for_user(
        self, user_id: int, *, unread_only: bool = False, limit: int = 20
    ) -> list[Notification]:
        rows = [
            n
            for n in reversed(self.notifications)
            if n.user_id == user_id and not (unread_only and n.is_read)
        ]
        return rows[:limit]

    def get_for_user(self, notification_id: int, user_id: int) -> Notification | None:
        return next(
            (
                n
                for n in self.notifications
                if n.id == notification_id and n.user_id == user_id
            ),
            None,
        )

    def count_unread(self, user_id: int) -> int:
        return sum(
            1 for n in self.notifications if n.user_id == user_id and not n.is_read
        )

    def mark_read(self, notification_id: int, user_id: int) -> bool:
        for i, n in enumerate(self.notifications):
            if n.id == notification_id and n.user_id == user_id:
                self.notifications[i] = replace(n, is_read=True)
                return True
        return False

    def mark_all_read(self, user_id: int) -> int:
        unread = [
            n.id for n in self.notifications if n.user_id == user_id and not n.is_read
        ]
        for notification_id in unread:
            self.mark_read(notification_id, user_id)
        return len(unread)


class InMemoryHistory:
    """Answers "does this member have expenses or settlements here?"."""

    def __init__(self) -> None:
        self.expenses: InMemoryExpenseRepository | None = None
        self.settlements: InMemorySettlementRepository | None = None

    def has_history(self, group_id: int, user_id: int) -> bool:
        expenses = self.expenses.expenses.values() if self.expenses else []
        settlements = self.settlements.settlements if self.settlements else []
        return any(
            e.group_id == group_id
            and (e.paid_by == user_id or user_id in e.participant_ids)
            for e in expenses
        ) or any(
            s.group_id == group_id and user_id in (s.from_user_id, s.to_user_id)
            for s in settlements
        )


class InMemoryBalanceReader:
    """``BalanceReader`` computed by the domain function instead of raw SQL."""

    def __init__(self, uow: "InMemoryUnitOfWork") -> None:
        self._uow = uow

    def member_balances(self, group_id: int) -> list[MemberBalance]:
        uow = self._uow
        expenses = [e for e in uow.expenses.expenses.values() if e.group_id == group_id]
        settlements = uow.settlements.list_for_group(group_id)
        members = [m.user_id for m in uow.groups.list_members(group_id)]
        balances = calculate_balances(expenses, settlements, member_ids=members)
        names = uow.users.get_many(members)
        rows = []
        for user_id in sorted(members):
            paid = sum(e.amount for e in expenses if e.paid_by == user_id)
            owed = sum(
                s.share_amount
                for e in expenses
                for s in e.shares
                if s.user_id == user_id
            )
            sent = sum(s.amount for s in settlements if s.from_user_id == user_id)
            received = sum(s.amount for s in settlements if s.to_user_id == user_id)
            rows.append(
                MemberBalance(
                    user_id=user_id,
                    username=names[user_id].username if user_id in names else "?",
                    paid=paid,
                    owed=owed,
                    sent=sent,
                    received=received,
                    balance=balances.get(user_id, 0),
                )
            )
        return rows


class InMemoryUnitOfWork:
    """``UnitOfWork`` for tests: ``commit()`` is recorded, changes are kept.

    ``committed`` lets a test check that a service committed (or did not).
    """

    def __init__(self) -> None:
        history = InMemoryHistory()
        self.users = InMemoryUserRepository()
        self.groups = InMemoryGroupRepository(history)
        self.expenses = InMemoryExpenseRepository(self.groups)
        self.settlements = InMemorySettlementRepository(self.groups)
        self.notifications = InMemoryNotificationRepository()
        history.expenses = self.expenses
        history.settlements = self.settlements
        self.committed = 0

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def commit(self) -> None:
        self.committed += 1

    def rollback(self) -> None:
        return None

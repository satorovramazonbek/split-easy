"""Unit of Work: the service decides where a transaction starts and ends.

Spec section 10.4: an expense and all its shares, an edit (old shares out, new
shares in), a settlement and its notification - each is saved completely or not
at all. Only the service knows which writes belong together, so the boundary
lives there, not in a repository::

    with uow:
        expense = uow.expenses.add(expense)
        uow.notifications.add_many(...)
        uow.commit()          # nothing is saved without this line

Leaving the ``with`` block without ``commit()`` - or because of an exception -
rolls everything back.
"""

from types import TracebackType
from typing import Protocol, Self

from app.repositories.interfaces.expense_repository import ExpenseRepository
from app.repositories.interfaces.group_repository import GroupRepository
from app.repositories.interfaces.notification_repository import (
    NotificationRepository,
)
from app.repositories.interfaces.settlement_repository import SettlementRepository
from app.repositories.interfaces.user_repository import UserRepository


class UnitOfWork(Protocol):
    users: UserRepository
    groups: GroupRepository
    expenses: ExpenseRepository
    settlements: SettlementRepository
    notifications: NotificationRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

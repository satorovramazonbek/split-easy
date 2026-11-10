"""SQLAlchemy ``UnitOfWork``: all repositories share one session/transaction."""

from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session

from app.repositories.sqlalchemy.expense_repository import SqlAlchemyExpenseRepository
from app.repositories.sqlalchemy.group_repository import SqlAlchemyGroupRepository
from app.repositories.sqlalchemy.notification_repository import (
    SqlAlchemyNotificationRepository,
)
from app.repositories.sqlalchemy.settlement_repository import (
    SqlAlchemySettlementRepository,
)
from app.repositories.sqlalchemy.user_repository import SqlAlchemyUserRepository


class SqlAlchemyUnitOfWork:
    """Wraps a session; in the web app it is the request's session."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self.users = SqlAlchemyUserRepository(session)
        self.groups = SqlAlchemyGroupRepository(session)
        self.expenses = SqlAlchemyExpenseRepository(session)
        self.settlements = SqlAlchemySettlementRepository(session)
        self.notifications = SqlAlchemyNotificationRepository(session)
        self._committed = False

    def __enter__(self) -> Self:
        self._committed = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        # No commit() -> nothing is kept, also when no exception happened:
        # forgetting to commit must not save half of an operation.
        if exc_type is not None or not self._committed:
            self.rollback()

    def commit(self) -> None:
        self._session.commit()
        self._committed = True

    def rollback(self) -> None:
        self._session.rollback()

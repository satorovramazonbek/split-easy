"""SQLAlchemy implementation of ``NotificationRepository``."""

from collections.abc import Iterable

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.models import Notification
from app.repositories.interfaces.errors import ReferenceIntegrityError
from app.repositories.sqlalchemy.orm_models import NotificationORM
from app.repositories.sqlalchemy.user_repository import as_utc


def _to_domain(row: NotificationORM) -> Notification:
    return Notification(
        id=row.id,
        user_id=row.user_id,
        message=row.message,
        is_read=row.is_read,
        created_at=as_utc(row.created_at),
    )


class SqlAlchemyNotificationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_many(self, notifications: Iterable[Notification]) -> list[Notification]:
        rows = [
            NotificationORM(
                user_id=n.user_id,
                message=n.message,
                is_read=n.is_read,
                created_at=n.created_at,
            )
            for n in notifications
        ]
        try:
            with self._session.begin_nested():
                self._session.add_all(rows)
                self._session.flush()
        except IntegrityError as error:
            raise ReferenceIntegrityError(str(error.orig)) from error
        return [_to_domain(row) for row in rows]

    def list_for_user(
        self, user_id: int, *, unread_only: bool = False, limit: int = 20
    ) -> list[Notification]:
        statement = select(NotificationORM).where(NotificationORM.user_id == user_id)
        if unread_only:
            statement = statement.where(NotificationORM.is_read.is_(False))
        statement = statement.order_by(
            NotificationORM.created_at.desc(), NotificationORM.id.desc()
        ).limit(limit)
        return [_to_domain(row) for row in self._session.scalars(statement)]

    def count_unread(self, user_id: int) -> int:
        return self._session.scalar(
            select(func.count()).where(
                NotificationORM.user_id == user_id,
                NotificationORM.is_read.is_(False),
            )
        )

    def mark_read(self, notification_id: int, user_id: int) -> bool:
        result = self._session.execute(
            update(NotificationORM)
            .where(
                NotificationORM.id == notification_id,
                NotificationORM.user_id == user_id,  # someone else's: no change
            )
            .values(is_read=True)
            .execution_options(synchronize_session="fetch")
        )
        return result.rowcount == 1

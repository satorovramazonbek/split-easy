"""SQLAlchemy implementation of ``UserRepository``."""

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.models import User
from app.repositories.interfaces.user_repository import DuplicateUserError
from app.repositories.sqlalchemy.orm_models import UserORM


def as_utc(value: datetime) -> datetime:
    # SQLite does not store the timezone; all timestamps are written in UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _to_domain(row: UserORM) -> User:
    return User(
        id=row.id,
        username=row.username,
        email=row.email,
        password_hash=row.password_hash,
        created_at=as_utc(row.created_at),
    )


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, user: User) -> User:
        row = UserORM(
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            created_at=user.created_at,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()  # assigns the id; commit happens per request
        except IntegrityError as error:
            raise DuplicateUserError(str(error.orig)) from error
        return _to_domain(row)

    def get_by_id(self, user_id: int) -> User | None:
        row = self._session.get(UserORM, user_id)
        return _to_domain(row) if row else None

    def get_many(self, user_ids: Iterable[int]) -> dict[int, User]:
        ids = set(user_ids)
        if not ids:
            return {}
        rows = self._session.scalars(select(UserORM).where(UserORM.id.in_(ids)))
        return {row.id: _to_domain(row) for row in rows}

    def update_username(self, user_id: int, username: str) -> User:
        row = self._session.get(UserORM, user_id)
        if row is None:
            raise LookupError(f"User {user_id} does not exist")
        try:
            with self._session.begin_nested():
                row.username = username
                self._session.flush()
        except IntegrityError as error:
            # The savepoint rollback expires the row; reload the stored name.
            self._session.refresh(row)
            raise DuplicateUserError(str(error.orig)) from error
        return _to_domain(row)

    def get_by_username(self, username: str) -> User | None:
        return self._one(select(UserORM).where(UserORM.username == username))

    def get_by_email(self, email: str) -> User | None:
        return self._one(select(UserORM).where(UserORM.email == email))

    def _one(self, statement: Select[tuple[UserORM]]) -> User | None:
        row = self._session.scalars(statement).first()
        return _to_domain(row) if row else None

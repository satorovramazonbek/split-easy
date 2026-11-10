"""Abstraction the services depend on (Dependency Inversion)."""

from collections.abc import Iterable
from typing import Protocol

from app.domain.models import User


class DuplicateUserError(Exception):
    """Storage rejected the user because username or email already exists."""


class UserRepository(Protocol):
    def add(self, user: User) -> User:
        """Persist a new user and return it with the assigned id.

        Raises ``DuplicateUserError`` if username or email is taken.
        """

    def get_by_id(self, user_id: int) -> User | None: ...

    def get_many(self, user_ids: Iterable[int]) -> dict[int, User]:
        """Users by id in one query; unknown ids are skipped."""

    def get_by_username(self, username: str) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def update_username(self, user_id: int, username: str) -> User:
        """Save a new username and return the updated user.

        Raises ``DuplicateUserError`` if another user has this username.
        """

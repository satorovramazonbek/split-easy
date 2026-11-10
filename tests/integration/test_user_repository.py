from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.domain.models import User
from app.repositories.interfaces.user_repository import DuplicateUserError
from app.repositories.sqlalchemy.user_repository import SqlAlchemyUserRepository


def make_user(username: str = "aziza", email: str = "aziza@example.com") -> User:
    return User(
        id=None,
        username=username,
        email=email,
        password_hash="hash",
        created_at=datetime(2026, 11, 7, tzinfo=UTC),
    )


def test_add_and_find_user(session: Session) -> None:
    repo = SqlAlchemyUserRepository(session)

    saved = repo.add(make_user())

    assert saved.id is not None
    assert repo.get_by_id(saved.id) == saved
    assert repo.get_by_username("aziza") == saved
    assert repo.get_by_email("aziza@example.com") == saved


def test_missing_user_returns_none(session: Session) -> None:
    repo = SqlAlchemyUserRepository(session)

    assert repo.get_by_id(1) is None
    assert repo.get_by_username("nobody") is None
    assert repo.get_by_email("nobody@example.com") is None


@pytest.mark.parametrize(
    "duplicate",
    [make_user(email="other@example.com"), make_user(username="other")],
    ids=["username", "email"],
)
def test_unique_constraints(session: Session, duplicate: User) -> None:
    repo = SqlAlchemyUserRepository(session)
    first = repo.add(make_user())

    with pytest.raises(DuplicateUserError):
        repo.add(duplicate)

    # The savepoint is rolled back; the first user is still usable.
    assert repo.get_by_id(first.id) == first


def test_update_username(session: Session) -> None:
    repo = SqlAlchemyUserRepository(session)
    user = repo.add(make_user())

    updated = repo.update_username(user.id, "aziza_a")

    assert updated.username == "aziza_a"
    assert repo.get_by_username("aziza_a").id == user.id
    assert repo.get_by_username("aziza") is None


def test_update_username_to_taken_name_is_rejected(session: Session) -> None:
    repo = SqlAlchemyUserRepository(session)
    aziza = repo.add(make_user())
    repo.add(make_user("ramazon", "ramazon@example.com"))

    with pytest.raises(DuplicateUserError):
        repo.update_username(aziza.id, "ramazon")

    # Only the failed update was rolled back; the session still works.
    assert repo.get_by_id(aziza.id).username == "aziza"

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.models import Group, GroupMember, User
from app.repositories.interfaces.group_repository import DuplicateMemberError
from app.repositories.sqlalchemy.group_repository import SqlAlchemyGroupRepository
from app.repositories.sqlalchemy.user_repository import SqlAlchemyUserRepository

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


@pytest.fixture
def users(session: Session) -> list[User]:
    repo = SqlAlchemyUserRepository(session)
    return [
        repo.add(
            User(
                id=None,
                username=name,
                email=f"{name}@example.com",
                password_hash="x",
                created_at=NOW,
            )
        )
        for name in ("aziza", "ramazon")
    ]


@pytest.fixture
def repo(session: Session) -> SqlAlchemyGroupRepository:
    return SqlAlchemyGroupRepository(session)


def new_group(owner: User, name: str = "Sayohat", at: datetime = NOW) -> Group:
    return Group(id=None, name=name, currency="UZS", owner_id=owner.id, created_at=at)


def test_add_and_get_group(repo, users) -> None:
    saved = repo.add(new_group(users[0]))

    assert saved.id is not None
    assert repo.get_by_id(saved.id) == saved
    assert repo.get_by_id(999) is None


def test_members_and_listing(repo, users) -> None:
    aziza, ramazon = users
    older = repo.add(new_group(aziza, "Eski", NOW - timedelta(days=1)))
    newer = repo.add(new_group(aziza, "Yangi"))
    for group in (older, newer):
        repo.add_member(GroupMember(group.id, aziza.id, NOW))
    repo.add_member(GroupMember(newer.id, ramazon.id, NOW + timedelta(minutes=1)))

    assert [g.name for g in repo.list_for_user(aziza.id)] == ["Yangi", "Eski"]
    assert [g.name for g in repo.list_for_user(ramazon.id)] == ["Yangi"]
    assert [m.user_id for m in repo.list_members(newer.id)] == [aziza.id, ramazon.id]
    assert repo.is_member(newer.id, ramazon.id)
    assert not repo.is_member(older.id, ramazon.id)

    repo.remove_member(newer.id, ramazon.id, NOW)  # no history -> row deleted

    assert not repo.is_member(newer.id, ramazon.id)
    assert repo.list_for_user(ramazon.id) == []


def test_duplicate_member_is_rejected(repo, users) -> None:
    group = repo.add(new_group(users[0]))
    repo.add_member(GroupMember(group.id, users[0].id, NOW))

    with pytest.raises(DuplicateMemberError):
        repo.add_member(GroupMember(group.id, users[0].id, NOW))

    assert repo.is_member(group.id, users[0].id)


def test_deleted_groups_are_hidden_from_listing(repo, users) -> None:
    group = repo.add(new_group(users[0]))
    repo.add_member(GroupMember(group.id, users[0].id, NOW))

    repo.mark_deleted(group.id)

    assert repo.list_for_user(users[0].id) == []
    assert repo.get_by_id(group.id).is_deleted


def test_foreign_keys_are_enforced(repo, session: Session) -> None:
    with pytest.raises(IntegrityError):
        repo.add(Group(id=None, name="X", currency="UZS", owner_id=999, created_at=NOW))
    session.rollback()


def test_blank_name_is_rejected_by_database(repo, users, session: Session) -> None:
    with pytest.raises(IntegrityError):
        repo.add(new_group(users[0], name="   "))
    session.rollback()

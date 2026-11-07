from datetime import UTC, datetime

import pytest

from app.domain.models import User
from app.services.group_service import (
    AlreadyMemberError,
    GroupNotFoundError,
    GroupPermissionError,
    GroupService,
    InvalidGroupError,
    MemberNotFoundError,
    OwnerCannotLeaveError,
    UserNotFoundError,
)
from tests.unit.fakes import InMemoryGroupRepository, InMemoryUserRepository

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


@pytest.fixture
def users() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
def service(users: InMemoryUserRepository) -> GroupService:
    return GroupService(InMemoryGroupRepository(), users, clock=lambda: NOW)


def make_user(users: InMemoryUserRepository, username: str) -> User:
    return users.add(
        User(
            id=None,
            username=username,
            email=f"{username}@example.com",
            password_hash="x",
            created_at=NOW,
        )
    )


@pytest.fixture
def aziza(users) -> User:
    return make_user(users, "aziza")


@pytest.fixture
def ramazon(users) -> User:
    return make_user(users, "ramazon")


@pytest.fixture
def ali(users) -> User:
    return make_user(users, "ali")


def test_create_group_makes_owner_a_member(service: GroupService, aziza) -> None:
    details = service.create_group(aziza, "  Sayohat  ", "usd")

    assert details.group.name == "Sayohat"
    assert details.group.currency == "USD"
    assert details.group.owner_id == aziza.id
    assert details.group.created_at == NOW
    assert [(m.username, m.is_owner) for m in details.members] == [("aziza", True)]


def test_create_group_defaults_to_uzs(service: GroupService, aziza) -> None:
    assert service.create_group(aziza, "Uy").group.currency == "UZS"


@pytest.mark.parametrize(
    ("name", "currency"),
    [("   ", "UZS"), ("x" * 101, "UZS"), ("Uy", "SO'M"), ("Uy", "U1S")],
)
def test_create_group_validates_input(service, aziza, name, currency) -> None:
    with pytest.raises(InvalidGroupError):
        service.create_group(aziza, name, currency)


def test_list_groups_shows_only_my_active_groups(service, aziza, ramazon) -> None:
    trip = service.create_group(aziza, "Sayohat").group
    home = service.create_group(aziza, "Uy").group
    service.create_group(ramazon, "Ramazonniki")
    service.delete_group(aziza, home.id)

    assert [g.name for g in service.list_groups(aziza)] == [trip.name]


def test_add_member_by_username_or_email(service, aziza, ramazon, ali) -> None:
    group = service.create_group(aziza, "Sayohat").group

    service.add_member(aziza, group.id, " RAMAZON ")
    details = service.add_member(aziza, group.id, "ali@example.com")

    assert [m.username for m in details.members] == ["aziza", "ramazon", "ali"]
    assert [m.is_owner for m in details.members] == [True, False, False]


def test_any_member_can_add_members(service, aziza, ramazon, ali) -> None:
    group = service.create_group(aziza, "Sayohat").group
    service.add_member(aziza, group.id, "ramazon")

    details = service.add_member(ramazon, group.id, "ali")

    assert len(details.members) == 3


def test_add_unknown_user(service, aziza) -> None:
    group = service.create_group(aziza, "Sayohat").group

    with pytest.raises(UserNotFoundError):
        service.add_member(aziza, group.id, "nobody")


def test_add_existing_member(service, aziza, ramazon) -> None:
    group = service.create_group(aziza, "Sayohat").group
    service.add_member(aziza, group.id, "ramazon")

    with pytest.raises(AlreadyMemberError):
        service.add_member(aziza, group.id, "ramazon")


def test_non_member_cannot_see_or_change_group(service, aziza, ramazon) -> None:
    group = service.create_group(aziza, "Sayohat").group

    with pytest.raises(GroupNotFoundError):
        service.get_group(ramazon, group.id)
    with pytest.raises(GroupNotFoundError):
        service.add_member(ramazon, group.id, "ramazon")
    with pytest.raises(GroupNotFoundError):
        service.delete_group(ramazon, group.id)


def test_missing_group(service, aziza) -> None:
    with pytest.raises(GroupNotFoundError):
        service.get_group(aziza, 999)


def test_owner_removes_member(service, aziza, ramazon) -> None:
    group = service.create_group(aziza, "Sayohat").group
    service.add_member(aziza, group.id, "ramazon")

    service.remove_member(aziza, group.id, ramazon.id)

    assert [m.username for m in service.get_group(aziza, group.id).members] == ["aziza"]
    with pytest.raises(GroupNotFoundError):
        service.get_group(ramazon, group.id)


def test_member_can_leave(service, aziza, ramazon) -> None:
    group = service.create_group(aziza, "Sayohat").group
    service.add_member(aziza, group.id, "ramazon")

    service.remove_member(ramazon, group.id, ramazon.id)

    assert service.list_groups(ramazon) == []


def test_member_cannot_remove_others(service, aziza, ramazon, ali) -> None:
    group = service.create_group(aziza, "Sayohat").group
    service.add_member(aziza, group.id, "ramazon")
    service.add_member(aziza, group.id, "ali")

    with pytest.raises(GroupPermissionError):
        service.remove_member(ramazon, group.id, ali.id)


def test_owner_cannot_be_removed(service, aziza, ramazon) -> None:
    group = service.create_group(aziza, "Sayohat").group
    service.add_member(aziza, group.id, "ramazon")

    with pytest.raises(OwnerCannotLeaveError):
        service.remove_member(aziza, group.id, aziza.id)
    with pytest.raises(OwnerCannotLeaveError):
        service.remove_member(ramazon, group.id, aziza.id)


def test_remove_non_member(service, aziza, ramazon) -> None:
    group = service.create_group(aziza, "Sayohat").group

    with pytest.raises(MemberNotFoundError):
        service.remove_member(aziza, group.id, ramazon.id)


def test_only_owner_deletes_group(service, aziza, ramazon) -> None:
    group = service.create_group(aziza, "Sayohat").group
    service.add_member(aziza, group.id, "ramazon")

    with pytest.raises(GroupPermissionError):
        service.delete_group(ramazon, group.id)

    service.delete_group(aziza, group.id)

    with pytest.raises(GroupNotFoundError):
        service.get_group(aziza, group.id)

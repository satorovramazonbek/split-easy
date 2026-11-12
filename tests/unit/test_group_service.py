from datetime import UTC, datetime

import pytest

from app.domain.models import User
from app.repositories.in_memory import (
    InMemoryBalanceReader,
    InMemoryUnitOfWork,
    InMemoryUserRepository,
)
from app.services.group_service import (
    AlreadyMemberError,
    GroupNotFoundError,
    GroupPermissionError,
    GroupService,
    InvalidGroupError,
    MemberHasDebtError,
    MemberNotFoundError,
    OwnerCannotLeaveError,
    UserNotFoundError,
)

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


@pytest.fixture
def uow() -> InMemoryUnitOfWork:
    """All in-memory repositories, sharing one set of data."""
    return InMemoryUnitOfWork()


@pytest.fixture
def users(uow: InMemoryUnitOfWork) -> InMemoryUserRepository:
    return uow.users


@pytest.fixture
def service(uow: InMemoryUnitOfWork) -> GroupService:
    return GroupService(
        uow.groups, uow.users, InMemoryBalanceReader(uow), clock=lambda: NOW
    )


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


def test_only_owner_can_add_members(service, aziza, ramazon, ali) -> None:
    group = service.create_group(aziza, "Sayohat").group
    service.add_member(aziza, group.id, "ramazon")

    with pytest.raises(GroupPermissionError):
        service.add_member(ramazon, group.id, "ali")

    assert len(service.get_group(aziza, group.id).members) == 2


def test_add_unknown_user(service, aziza) -> None:
    group = service.create_group(aziza, "Sayohat").group

    with pytest.raises(UserNotFoundError):
        service.add_member(aziza, group.id, "nobody")


def test_add_existing_member(service, aziza, ramazon) -> None:
    group = service.create_group(aziza, "Sayohat").group
    service.add_member(aziza, group.id, "ramazon")

    with pytest.raises(AlreadyMemberError):
        service.add_member(aziza, group.id, "ramazon")


def test_non_member_gets_permission_error(service, aziza, ramazon) -> None:
    group = service.create_group(aziza, "Sayohat").group

    with pytest.raises(GroupPermissionError):
        service.get_group(ramazon, group.id)
    with pytest.raises(GroupPermissionError):
        service.add_member(ramazon, group.id, "ramazon")
    with pytest.raises(GroupPermissionError):
        service.remove_member(ramazon, group.id, aziza.id)
    with pytest.raises(GroupPermissionError):
        service.delete_group(ramazon, group.id)


def test_missing_group(service, aziza) -> None:
    with pytest.raises(GroupNotFoundError):
        service.get_group(aziza, 999)
    with pytest.raises(GroupNotFoundError):
        service.add_member(aziza, 999, "aziza")


def test_owner_removes_member(service, aziza, ramazon) -> None:
    group = service.create_group(aziza, "Sayohat").group
    service.add_member(aziza, group.id, "ramazon")

    service.remove_member(aziza, group.id, ramazon.id)

    assert [m.username for m in service.get_group(aziza, group.id).members] == ["aziza"]
    assert service.list_groups(ramazon) == []
    with pytest.raises(GroupPermissionError):
        service.get_group(ramazon, group.id)


@pytest.mark.parametrize("target", ["ramazon", "ali"])
def test_member_cannot_remove_anyone(service, aziza, ramazon, ali, target) -> None:
    group = service.create_group(aziza, "Sayohat").group
    service.add_member(aziza, group.id, "ramazon")
    service.add_member(aziza, group.id, "ali")
    target_id = {"ramazon": ramazon.id, "ali": ali.id}[target]

    with pytest.raises(GroupPermissionError):
        service.remove_member(ramazon, group.id, target_id)


def test_owner_cannot_be_removed(service, aziza) -> None:
    group = service.create_group(aziza, "Sayohat").group

    with pytest.raises(OwnerCannotLeaveError):
        service.remove_member(aziza, group.id, aziza.id)


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


# --- FR-7: remove a member only when their balance is 0 -------------------------


def _shared_expense(uow, group_id: int, payer: User, other: User) -> None:
    """payer paid 100 000 for both: other owes 50 000."""
    from unittest.mock import Mock

    from app.domain.split_strategies import Participant
    from app.services.expense_service import ExpenseData, ExpenseService

    ExpenseService(uow, Mock(), clock=lambda: NOW).add_expense(
        payer,
        group_id,
        ExpenseData(
            description="Ovqat",
            amount=100_000,
            paid_by=payer.id,
            split_type="equal",
            participants=[Participant(payer.id), Participant(other.id)],
        ),
    )


def test_member_with_non_zero_balance_cannot_be_removed(
    service, uow, aziza, ramazon
) -> None:
    group = service.create_group(aziza, "Sayohat").group
    service.add_member(aziza, group.id, "ramazon")
    _shared_expense(uow, group.id, aziza, ramazon)

    with pytest.raises(MemberHasDebtError):
        service.remove_member(aziza, group.id, ramazon.id)

    assert uow.groups.is_member(group.id, ramazon.id)


def test_member_with_history_and_zero_balance_leaves_and_can_come_back(
    service, uow, aziza, ramazon
) -> None:
    from app.domain.models import Settlement

    group = service.create_group(aziza, "Sayohat").group
    service.add_member(aziza, group.id, "ramazon")
    _shared_expense(uow, group.id, aziza, ramazon)
    uow.settlements.add(Settlement(None, group.id, ramazon.id, aziza.id, 50_000, NOW))

    service.remove_member(aziza, group.id, ramazon.id)

    assert not uow.groups.is_member(group.id, ramazon.id)
    assert (group.id, ramazon.id) in uow.groups.left  # history is kept
    service.add_member(aziza, group.id, "ramazon")  # may be added again
    assert uow.groups.is_member(group.id, ramazon.id)

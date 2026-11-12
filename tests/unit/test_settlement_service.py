"""SettlementService with in-memory repositories and a Mock event publisher."""

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from app.domain.events import SettlementRecorded
from app.domain.models import Group, GroupMember, User
from app.domain.split_strategies import Participant
from app.repositories.in_memory import InMemoryBalanceReader, InMemoryUnitOfWork
from app.services.expense_service import ExpenseData, ExpenseService
from app.services.settlement_service import (
    InvalidSettlementError,
    SettlementPermissionError,
    SettlementService,
)

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


@pytest.fixture
def uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork()


@pytest.fixture
def events() -> Mock:
    return Mock()


@pytest.fixture
def people(uow: InMemoryUnitOfWork) -> dict[str, User]:
    """aziza paid 300 000 for three: ramazon and bobur owe her 100 000 each."""
    users = {
        n: uow.users.add(User(None, n, f"{n}@example.com", "hash"))
        for n in ("aziza", "ramazon", "bobur")
    }
    group = uow.groups.add(Group(None, "Sayohat", "UZS", users["aziza"].id))
    for user in users.values():
        uow.groups.add_member(GroupMember(group.id, user.id, NOW))
    ExpenseService(uow, Mock(), clock=lambda: NOW).add_expense(
        users["aziza"],
        group.id,
        ExpenseData(
            description="Mehmonxona",
            amount=300_000,
            paid_by=users["aziza"].id,
            split_type="equal",
            participants=[Participant(u.id) for u in users.values()],
        ),
    )
    return users


@pytest.fixture
def service(uow: InMemoryUnitOfWork, events: Mock) -> SettlementService:
    return SettlementService(uow, InMemoryBalanceReader(uow), events, clock=lambda: NOW)


def test_balances_add_up_to_zero(service, people) -> None:
    balances = {b.username: b.balance for b in service.balances(people["aziza"], 1)}

    assert balances == {"aziza": 200_000, "ramazon": -100_000, "bobur": -100_000}
    assert sum(balances.values()) == 0


def test_settle_plan_brings_everyone_to_zero(service, people) -> None:
    plan = service.settle_plan(people["aziza"], 1)

    assert sorted(t.amount for t in plan) == [100_000, 100_000]
    assert all(t.to_user_id == people["aziza"].id for t in plan)


def test_recording_a_payment_changes_balances_and_publishes_event(
    service, events, uow, people
) -> None:
    service.record_settlement(
        people["ramazon"], 1, people["ramazon"].id, people["aziza"].id, 100_000
    )

    balances = {b.username: b.balance for b in service.balances(people["aziza"], 1)}
    assert balances["ramazon"] == 0
    assert uow.committed >= 1
    event = events.publish.call_args.args[0]
    assert isinstance(event, SettlementRecorded)
    assert (event.from_name, event.to_name, event.amount) == (
        "ramazon",
        "aziza",
        100_000,
    )
    assert event.recorded_by == people["ramazon"].id


def test_payment_larger_than_the_debt_is_rejected(service, events, people) -> None:
    with pytest.raises(InvalidSettlementError, match="qarzdan oshmasligi"):
        service.record_settlement(
            people["ramazon"], 1, people["ramazon"].id, people["aziza"].id, 100_001
        )

    events.publish.assert_not_called()


def test_second_identical_payment_is_rejected(service, people) -> None:
    pay = (people["ramazon"], 1, people["ramazon"].id, people["aziza"].id, 100_000)
    service.record_settlement(*pay)

    with pytest.raises(InvalidSettlementError, match="kerak emas"):
        service.record_settlement(*pay)


def test_only_a_party_or_the_owner_records_a_payment(service, people) -> None:
    with pytest.raises(SettlementPermissionError):
        service.record_settlement(
            people["bobur"], 1, people["ramazon"].id, people["aziza"].id, 1_000
        )


def test_self_payment_is_rejected(service, people) -> None:
    with pytest.raises(InvalidSettlementError, match="O'zingizga"):
        service.record_settlement(
            people["aziza"], 1, people["aziza"].id, people["aziza"].id, 1_000
        )

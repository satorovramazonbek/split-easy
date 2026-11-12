"""ExpenseService with in-memory repositories and a Mock event publisher.

No database and no web framework (NFR-4). The Mock replaces the event bus, so
the tests check that the service *publishes* ExpenseAdded without knowing who
listens (spec 12.2: "ExpenseAdded hodisasi yuboriladi ... Mock yordamida").
"""

from datetime import UTC, date, datetime
from unittest.mock import Mock

import pytest

from app.domain.events import ExpenseAdded
from app.domain.models import GroupMember, User
from app.domain.split_strategies import Participant
from app.repositories.in_memory import InMemoryUnitOfWork
from app.services.expense_service import (
    ExpenseData,
    ExpenseNotFoundError,
    ExpensePermissionError,
    ExpenseService,
    InvalidExpenseError,
)
from app.services.group_service import GroupNotFoundError, GroupPermissionError

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


@pytest.fixture
def uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork()


@pytest.fixture
def events() -> Mock:
    return Mock()


@pytest.fixture
def service(uow: InMemoryUnitOfWork, events: Mock) -> ExpenseService:
    return ExpenseService(uow, events, clock=lambda: NOW)


def add_user(uow: InMemoryUnitOfWork, name: str) -> User:
    return uow.users.add(User(None, name, f"{name}@example.com", "hash"))


@pytest.fixture
def people(uow: InMemoryUnitOfWork) -> dict[str, User]:
    """Group 1 of aziza (owner) and ramazon; ali is not a member."""
    users = {n: add_user(uow, n) for n in ("aziza", "ramazon", "ali")}
    from app.domain.models import Group

    group = uow.groups.add(Group(None, "Sayohat", "UZS", users["aziza"].id))
    for name in ("aziza", "ramazon"):
        uow.groups.add_member(GroupMember(group.id, users[name].id, NOW))
    return users


def data(people: dict[str, User], **overrides: object) -> ExpenseData:
    values: dict[str, object] = {
        "description": "Ovqat",
        "amount": 300_000,
        "paid_by": people["aziza"].id,
        "split_type": "equal",
        "participants": [
            Participant(people["aziza"].id),
            Participant(people["ramazon"].id),
        ],
        "category": "food",
    }
    values.update(overrides)
    return ExpenseData(**values)  # type: ignore[arg-type]


# --- adding ----------------------------------------------------------------------


def test_member_adds_expense_and_it_is_committed(service, uow, people) -> None:
    expense = service.add_expense(people["aziza"], 1, data(people))

    assert expense.id is not None
    assert [s.share_amount for s in expense.shares] == [150_000, 150_000]
    assert uow.committed == 1


def test_adding_expense_publishes_expense_added_event(service, events, people) -> None:
    expense = service.add_expense(people["aziza"], 1, data(people))

    events.publish.assert_called_once()
    event = events.publish.call_args.args[0]
    assert isinstance(event, ExpenseAdded)
    assert event.expense_id == expense.id
    assert event.author_name == "aziza"
    assert [(s.user_id, s.share_amount) for s in event.shares] == [
        (people["aziza"].id, 150_000),
        (people["ramazon"].id, 150_000),
    ]


def test_non_member_cannot_add_expense(service, events, people) -> None:
    with pytest.raises(GroupPermissionError):
        service.add_expense(people["ali"], 1, data(people))

    events.publish.assert_not_called()


def test_missing_group(service, people) -> None:
    with pytest.raises(GroupNotFoundError):
        service.add_expense(people["aziza"], 99, data(people))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"description": "  "}, "tavsifini"),
        ({"category": "cars"}, "noto'g'ri"),
        ({"expense_date": date(2026, 11, 11)}, "kelajakda"),
        ({"paid_by": 999}, "To'lovchi"),
        ({"participants": []}, "Kamida bitta"),
        ({"participants": [Participant(999)]}, "guruh a'zosi"),
        (
            {
                "split_type": "percentage",
                "participants": [Participant(1, 10), Participant(2, 10)],
            },
            "Foizlar yig'indisi 100",
        ),
    ],
)
def test_invalid_expense_is_rejected_and_nothing_is_published(
    service, events, uow, people, overrides, message
) -> None:
    with pytest.raises(InvalidExpenseError, match=message):
        service.add_expense(people["aziza"], 1, data(people, **overrides))

    events.publish.assert_not_called()
    assert uow.expenses.expenses == {}


# --- editing and deleting (FR-12) ------------------------------------------------------


def test_author_edits_expense_and_shares_are_recalculated(service, people) -> None:
    expense = service.add_expense(people["ramazon"], 1, data(people))

    edited = service.update_expense(
        people["ramazon"], 1, expense.id, data(people, amount=100_000)
    )

    assert edited.id == expense.id
    assert edited.created_by == people["ramazon"].id  # the author stays
    assert [s.share_amount for s in edited.shares] == [50_000, 50_000]


def test_owner_may_edit_and_delete_any_expense(service, people) -> None:
    expense = service.add_expense(people["ramazon"], 1, data(people))

    service.update_expense(people["aziza"], 1, expense.id, data(people, amount=10))
    service.delete_expense(people["aziza"], 1, expense.id)

    with pytest.raises(ExpenseNotFoundError):
        service.get_expense(people["aziza"], 1, expense.id)


def test_other_member_cannot_edit_or_delete(service, uow, people) -> None:
    expense = service.add_expense(people["aziza"], 1, data(people))
    bobur = add_user(uow, "bobur")
    uow.groups.add_member(GroupMember(1, bobur.id, NOW))

    with pytest.raises(ExpensePermissionError):
        service.update_expense(bobur, 1, expense.id, data(people))
    with pytest.raises(ExpensePermissionError):
        service.delete_expense(bobur, 1, expense.id)


# --- listing (FR-13, FR-14) ---------------------------------------------------------


def test_list_is_paginated_and_filtered_by_category(service, people) -> None:
    for day, category in [(1, "food"), (2, "transport"), (3, "food"), (4, "food")]:
        service.add_expense(
            people["aziza"],
            1,
            data(people, category=category, expense_date=date(2026, 11, day)),
        )

    first = service.list_expenses(people["aziza"], 1, page=1, page_size=2)
    food = service.list_expenses(people["aziza"], 1, category="food")

    assert first.total == 4 and first.pages == 2
    assert [e.expense_date.day for e in first.items] == [4, 3]  # newest first
    assert [e.expense_date.day for e in food.items] == [4, 3, 1]


def test_page_past_the_end_shows_the_last_page(service, people) -> None:
    service.add_expense(people["aziza"], 1, data(people))

    result = service.list_expenses(people["aziza"], 1, page=99)

    assert result.page == 1
    assert len(result.items) == 1

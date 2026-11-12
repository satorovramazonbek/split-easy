"""Repository contract tests (Liskov Substitution, spec section 9).

Every test runs twice: against the SQLAlchemy repositories (in-memory SQLite)
and against the in-memory ones. The same assertions pass for both, so a
service can use either implementation without noticing the difference.
"""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.domain.models import (
    Category,
    Expense,
    ExpenseShare,
    Group,
    GroupMember,
    SplitType,
    User,
)
from app.repositories.in_memory import InMemoryUnitOfWork
from app.repositories.interfaces.errors import ReferenceIntegrityError
from app.repositories.interfaces.group_repository import DuplicateMemberError
from app.repositories.interfaces.user_repository import DuplicateUserError
from app.repositories.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


@pytest.fixture(params=["sqlalchemy", "in_memory"])
def uow(request: pytest.FixtureRequest, session: Session) -> Iterator[Any]:
    if request.param == "sqlalchemy":
        yield SqlAlchemyUnitOfWork(session)
    else:
        yield InMemoryUnitOfWork()


def user(uow: Any, name: str) -> User:
    return uow.users.add(User(None, name, f"{name}@example.com", "hash", NOW))


@pytest.fixture
def world(uow: Any) -> dict[str, int]:
    aziza, ramazon = user(uow, "aziza"), user(uow, "ramazon")
    group = uow.groups.add(Group(None, "Sayohat", "UZS", aziza.id, created_at=NOW))
    uow.groups.add_member(GroupMember(group.id, aziza.id, NOW))
    uow.groups.add_member(GroupMember(group.id, ramazon.id, NOW + timedelta(minutes=1)))
    return {"aziza": aziza.id, "ramazon": ramazon.id, "group": group.id}


def expense(world: dict[str, int], day: int, **overrides: Any) -> Expense:
    values: dict[str, Any] = {
        "id": None,
        "group_id": world["group"],
        "description": f"X{day}",
        "amount": 100,
        "paid_by": world["aziza"],
        "split_type": SplitType.EQUAL,
        "shares": (
            ExpenseShare(world["aziza"], 50),
            ExpenseShare(world["ramazon"], 50),
        ),
        "category": Category.FOOD,
        "expense_date": date(2026, 11, day),
        "created_by": world["aziza"],
        "created_at": NOW,
    }
    values.update(overrides)
    return Expense(**values)


# --- UserRepository --------------------------------------------------------------


def test_users_round_trip_and_lookup(uow) -> None:
    stored = user(uow, "aziza")

    assert stored.id is not None
    assert uow.users.get_by_id(stored.id).username == "aziza"
    assert uow.users.get_by_username("aziza").id == stored.id
    assert uow.users.get_by_email("aziza@example.com").id == stored.id
    assert uow.users.get_by_username("nobody") is None


def test_duplicate_username_is_rejected(uow) -> None:
    user(uow, "aziza")

    with pytest.raises(DuplicateUserError):
        uow.users.add(User(None, "aziza", "other@example.com", "hash", NOW))


# --- GroupRepository ---------------------------------------------------------------


def test_members_in_join_order_and_duplicates_rejected(uow, world) -> None:
    members = [m.user_id for m in uow.groups.list_members(world["group"])]

    assert members == [world["aziza"], world["ramazon"]]
    with pytest.raises(DuplicateMemberError):
        uow.groups.add_member(GroupMember(world["group"], world["aziza"], NOW))


def test_removed_member_is_not_listed_and_can_be_added_again(uow, world) -> None:
    uow.groups.remove_member(world["group"], world["ramazon"], NOW)

    assert not uow.groups.is_member(world["group"], world["ramazon"])
    assert uow.groups.list_for_user(world["ramazon"]) == []
    uow.groups.add_member(GroupMember(world["group"], world["ramazon"], NOW))
    assert uow.groups.is_member(world["group"], world["ramazon"])


def test_member_with_history_leaves_but_history_stays(uow, world) -> None:
    saved = uow.expenses.add(expense(world, 1))

    uow.groups.remove_member(world["group"], world["ramazon"], NOW)

    assert not uow.groups.is_member(world["group"], world["ramazon"])
    assert uow.expenses.get(saved.id).participant_ids == [
        world["aziza"],
        world["ramazon"],
    ]


# --- ExpenseRepository -------------------------------------------------------------


def test_expense_round_trip(uow, world) -> None:
    saved = uow.expenses.add(expense(world, 1))

    loaded = uow.expenses.get(saved.id)
    assert loaded.amount == 100
    assert [(s.user_id, s.share_amount) for s in loaded.shares] == [
        (world["aziza"], 50),
        (world["ramazon"], 50),
    ]


def test_list_newest_first_paginated_and_filtered(uow, world) -> None:
    for day in (1, 2, 3):
        uow.expenses.add(expense(world, day))
    uow.expenses.add(expense(world, 4, category=Category.TRANSPORT))

    page = uow.expenses.list_for_group(world["group"], limit=2, offset=1)
    food = uow.expenses.list_for_group(world["group"], category=Category.FOOD)

    assert [e.description for e in page] == ["X3", "X2"]
    assert [e.description for e in food] == ["X3", "X2", "X1"]
    assert uow.expenses.count_for_group(world["group"]) == 4
    assert uow.expenses.count_for_group(world["group"], Category.TRANSPORT) == 1


def test_replace_and_delete(uow, world) -> None:
    saved = uow.expenses.add(expense(world, 1))

    uow.expenses.replace(
        expense(
            world, 1, id=saved.id, amount=30, shares=(ExpenseShare(world["aziza"], 30),)
        )
    )
    assert uow.expenses.get(saved.id).participant_ids == [world["aziza"]]

    uow.expenses.delete(saved.id)
    assert uow.expenses.get(saved.id) is None


def test_payer_must_be_a_member(uow, world) -> None:
    outsider = user(uow, "begona")

    with pytest.raises(ReferenceIntegrityError):
        uow.expenses.add(
            expense(
                world, 1, paid_by=outsider.id, shares=(ExpenseShare(outsider.id, 100),)
            )
        )

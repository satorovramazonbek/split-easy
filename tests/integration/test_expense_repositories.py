"""Expense, settlement and notification repositories, Unit of Work and N+1."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.domain.models import (
    Category,
    Expense,
    ExpenseShare,
    Group,
    GroupMember,
    Notification,
    Settlement,
    SplitType,
    User,
)
from app.repositories.interfaces.errors import ReferenceIntegrityError
from app.repositories.sqlalchemy.expense_repository import SqlAlchemyExpenseRepository
from app.repositories.sqlalchemy.orm_models import ExpenseORM
from app.repositories.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


@pytest.fixture
def uow(session: Session) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(session)


@pytest.fixture
def ids(uow: SqlAlchemyUnitOfWork) -> dict[str, int]:
    """aziza owns group "Sayohat" with ramazon; ali is not a member."""
    with uow:
        result = {
            name: uow.users.add(User(None, name, f"{name}@example.com", "x", NOW)).id
            for name in ("aziza", "ramazon", "ali")
        }
        group = uow.groups.add(
            Group(None, "Sayohat", "UZS", result["aziza"], False, NOW)
        )
        for name in ("aziza", "ramazon"):
            uow.groups.add_member(GroupMember(group.id, result[name], NOW))
        result["group"] = group.id
        uow.commit()
    return result


def expense(ids, amount=300_000, payer="aziza", day=date(2026, 11, 1), **kw) -> Expense:
    half = amount // 2
    shares = kw.pop(
        "shares",
        (ExpenseShare(ids["aziza"], amount - half), ExpenseShare(ids["ramazon"], half)),
    )
    return Expense(
        id=kw.pop("id", None),
        group_id=ids["group"],
        description=kw.pop("description", "Kechki ovqat"),
        amount=amount,
        paid_by=ids[payer],
        split_type=SplitType.EQUAL,
        shares=tuple(shares),
        category=kw.pop("category", Category.FOOD),
        expense_date=day,
        created_by=ids[payer],
        created_at=NOW,
    )


def fresh(engine: Engine) -> Session:
    """A new session: sees only what was really committed."""
    return Session(engine)


# --- expenses -------------------------------------------------------------------


def test_add_and_get_round_trip(uow, ids) -> None:
    with uow:
        saved = uow.expenses.add(expense(ids))
        uow.commit()

    assert saved.id is not None
    assert uow.expenses.get(saved.id) == saved
    assert sum(s.share_amount for s in saved.shares) == saved.amount
    assert uow.expenses.get(999) is None


def test_list_is_paginated_newest_first(uow, ids) -> None:
    with uow:
        for i in range(5):
            uow.expenses.add(expense(ids, 1_000 * (i + 1), day=date(2026, 1, 1 + i)))
        uow.commit()
    group = ids["group"]

    first = uow.expenses.list_for_group(group, limit=2)
    second = uow.expenses.list_for_group(group, limit=2, offset=2)

    assert [e.expense_date.day for e in first] == [5, 4]
    assert [e.expense_date.day for e in second] == [3, 2]
    assert uow.expenses.count_for_group(group) == 5


def test_category_filter(uow, ids) -> None:
    with uow:
        uow.expenses.add(expense(ids, category=Category.FOOD))
        uow.expenses.add(expense(ids, category=Category.TRANSPORT))
        uow.commit()

    found = uow.expenses.list_for_group(ids["group"], category=Category.TRANSPORT)

    assert [e.category for e in found] == [Category.TRANSPORT]
    assert uow.expenses.count_for_group(ids["group"], Category.TRANSPORT) == 1


def test_replace_swaps_shares(uow, ids) -> None:
    with uow:
        saved = uow.expenses.add(expense(ids, 300_000))
        uow.commit()

    edited = expense(
        ids,
        400_000,
        id=saved.id,
        description="Tushlik",
        shares=[ExpenseShare(ids["ramazon"], 400_000)],
    )
    with uow:
        result = uow.expenses.replace(edited)
        uow.commit()

    assert result.description == "Tushlik"
    assert result.shares == (ExpenseShare(ids["ramazon"], 400_000),)


def test_replace_missing_expense(uow, ids) -> None:
    with pytest.raises(LookupError):
        uow.expenses.replace(expense(ids, id=999))
    with pytest.raises(ValueError):
        uow.expenses.replace(expense(ids))


def test_failed_replace_keeps_old_shares(uow, ids, engine) -> None:
    with uow:
        saved = uow.expenses.add(expense(ids, 300_000))
        uow.commit()
    broken = expense(ids, 300_000, id=saved.id, shares=[ExpenseShare(999, 300_000)])

    with pytest.raises(ReferenceIntegrityError), uow:
        uow.expenses.replace(broken)
        uow.commit()

    with fresh(engine) as session:
        assert SqlAlchemyExpenseRepository(session).get(saved.id) == saved


def test_delete_removes_shares(uow, ids, engine) -> None:
    with uow:
        saved = uow.expenses.add(expense(ids))
        uow.expenses.delete(saved.id)
        uow.commit()

    with fresh(engine) as session:
        assert session.execute(select(ExpenseORM)).first() is None
        assert (
            session.execute(select(ExpenseORM.shares.property.mapper.class_)).first()
            is None
        )


def test_payer_must_be_member(uow, ids) -> None:
    with pytest.raises(ReferenceIntegrityError):
        uow.expenses.add(
            expense(ids, payer="ali", shares=[ExpenseShare(ids["aziza"], 300_000)])
        )


# --- settlements and notifications ------------------------------------------------


def settlement(ids, sender="ramazon", receiver="aziza", amount=150_000) -> Settlement:
    return Settlement(None, ids["group"], ids[sender], ids[receiver], amount, NOW)


def test_settlements(uow, ids) -> None:
    with uow:
        first = uow.settlements.add(settlement(ids))
        uow.settlements.add(settlement(ids, "aziza", "ramazon", 10_000))
        uow.commit()

    listed = uow.settlements.list_for_group(ids["group"])

    assert listed[0] == first and len(listed) == 2
    with pytest.raises(ReferenceIntegrityError):
        uow.settlements.add(settlement(ids, receiver="ali"))


def test_notifications(uow, ids) -> None:
    with uow:
        saved = uow.notifications.add_many(
            [
                Notification(None, ids["aziza"], "Yangi xarajat", False, NOW),
                Notification(None, ids["aziza"], "To'lov", False, NOW + timedelta(1)),
                Notification(None, ids["ramazon"], "Yangi xarajat", False, NOW),
            ]
        )
        uow.commit()
    first, second = saved[0].id, saved[1].id

    assert [n.message for n in uow.notifications.list_for_user(ids["aziza"])] == [
        "To'lov",
        "Yangi xarajat",
    ]
    assert uow.notifications.count_unread(ids["aziza"]) == 2
    assert not uow.notifications.mark_read(first, ids["ramazon"])  # not his
    assert uow.notifications.mark_read(first, ids["aziza"])
    unread = uow.notifications.list_for_user(ids["aziza"], unread_only=True)
    assert [n.id for n in unread] == [second]
    with pytest.raises(ReferenceIntegrityError):
        uow.notifications.add_many([Notification(None, 999, "x", False, NOW)])


# --- Unit of Work: all or nothing (spec 10.4) ---------------------------------------


def test_commit_saves_expense_and_notifications(uow, ids, engine) -> None:
    with uow:
        saved = uow.expenses.add(expense(ids))
        uow.notifications.add_many(
            [Notification(None, ids["ramazon"], "Yangi xarajat", False, NOW)]
        )
        uow.commit()

    with fresh(engine) as session:
        assert SqlAlchemyExpenseRepository(session).get(saved.id) == saved


def test_no_commit_means_nothing_saved(uow, ids, engine) -> None:
    with uow:
        uow.expenses.add(expense(ids))
        # forgot uow.commit()

    with fresh(engine) as session:
        assert session.execute(select(ExpenseORM)).first() is None


def test_error_rolls_back_the_whole_unit(uow, ids, engine) -> None:
    """Settlement fails on the database -> the expense written before it is gone."""
    with pytest.raises(ReferenceIntegrityError), uow:
        uow.expenses.add(expense(ids))
        uow.settlements.add(settlement(ids, receiver="ali"))
        uow.commit()

    with fresh(engine) as session:
        assert session.execute(select(ExpenseORM)).first() is None


def test_python_error_rolls_back_too(uow, ids, engine) -> None:
    with pytest.raises(RuntimeError), uow:
        uow.expenses.add(expense(ids))
        raise RuntimeError("notification service is down")

    with fresh(engine) as session:
        assert session.execute(select(ExpenseORM)).first() is None


# --- N+1 (spec 10.6) ------------------------------------------------------------------


@contextmanager
def count_queries(engine: Engine) -> Iterator[list[str]]:
    """Data queries only: BEGIN/COMMIT/SAVEPOINT are not counted."""
    statements: list[str] = []
    control = ("BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE")

    def before_cursor_execute(conn, cursor, statement, *args) -> None:
        if not statement.lstrip().upper().startswith(control):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


@pytest.fixture
def hundred_expenses(uow, ids) -> int:
    with uow:
        for i in range(100):
            uow.expenses.add(
                expense(ids, 1_000 + i, day=date(2026, 1, 1) + timedelta(i))
            )
        uow.commit()
    return ids["group"]


def test_n_plus_one_before_lazy_loading(engine, hundred_expenses) -> None:
    """The naive way: load expenses, then touch .shares in a loop -> 1 + 100."""
    with fresh(engine) as session, count_queries(engine) as statements:
        rows = session.scalars(
            select(ExpenseORM).where(ExpenseORM.group_id == hundred_expenses)
        ).all()
        total = sum(len(row.shares) for row in rows)

    assert total == 200
    assert len(statements) == 101


def test_n_plus_one_after_selectinload(engine, hundred_expenses) -> None:
    """Repository: one query for expenses + one IN (...) for all shares."""
    with fresh(engine) as session, count_queries(engine) as statements:
        expenses = SqlAlchemyExpenseRepository(session).list_for_group(
            hundred_expenses, limit=100
        )
        total = sum(len(e.shares) for e in expenses)

    assert total == 200
    assert len(statements) <= 3  # spec: at most 3 for 100 expenses
    assert len(statements) == 2

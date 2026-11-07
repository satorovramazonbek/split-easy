"""Integrity rules enforced by the database itself (spec section 10.1)."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import insert, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.models import User
from app.repositories.sqlalchemy.group_repository import SqlAlchemyGroupRepository
from app.repositories.sqlalchemy.orm_models import ExpenseORM, SettlementORM
from app.repositories.sqlalchemy.user_repository import SqlAlchemyUserRepository
from app.services.group_service import GroupService, MemberHasHistoryError

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


@pytest.fixture
def world(session: Session) -> dict[str, int]:
    """Group 1 owned by aziza with member ramazon; ali is not a member."""
    users = SqlAlchemyUserRepository(session)
    ids = {
        name: users.add(
            User(
                id=None,
                username=name,
                email=f"{name}@example.com",
                password_hash="x",
                created_at=NOW,
            )
        ).id
        for name in ("aziza", "ramazon", "ali")
    }
    service = GroupService(SqlAlchemyGroupRepository(session), users, lambda: NOW)
    owner = users.get_by_id(ids["aziza"])
    ids["group"] = service.create_group(owner, "Sayohat").group.id
    service.add_member(owner, ids["group"], "ramazon")
    session.commit()
    return ids


def add_expense(session: Session, world, **overrides) -> int:
    values = {
        "group_id": world["group"],
        "description": "Kechki ovqat",
        "amount": 300_000,
        "paid_by": world["aziza"],
        "category": "food",
        "split_type": "equal",
        "expense_date": date(2026, 11, 7),
        "created_by": world["aziza"],
        "created_at": NOW,
        **overrides,
    }
    # Core insert (not raw SQL) so dates are stored exactly as the ORM stores them.
    return session.execute(insert(ExpenseORM.__table__).values(values)).lastrowid


def add_settlement(session: Session, world, **overrides) -> None:
    values = {
        "group_id": world["group"],
        "from_user_id": world["ramazon"],
        "to_user_id": world["aziza"],
        "amount": 150_000,
        "created_at": NOW,
        **overrides,
    }
    session.execute(insert(SettlementORM.__table__).values(values))


def count(session: Session, table: str) -> int:
    return session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def test_valid_expense_and_settlement_are_stored(session: Session, world) -> None:
    add_expense(session, world)
    add_settlement(session, world)

    assert count(session, "expenses") == 1
    assert count(session, "settlements") == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": 0},
        {"amount": -100},
        {"description": "   "},
        {"category": "games"},
        {"split_type": "random"},
    ],
    ids=["zero", "negative", "blank", "category", "split_type"],
)
def test_expense_check_constraints(session: Session, world, overrides) -> None:
    with pytest.raises(IntegrityError):
        add_expense(session, world, **overrides)


def test_payer_must_be_group_member(session: Session, world) -> None:
    with pytest.raises(IntegrityError):
        add_expense(session, world, paid_by=world["ali"])


def test_negative_share_is_rejected(session: Session, world) -> None:
    expense_id = add_expense(session, world)

    with pytest.raises(IntegrityError):
        session.execute(
            text(
                "INSERT INTO expense_shares (expense_id, user_id, share_amount)"
                " VALUES (:e, :u, -1)"
            ),
            {"e": expense_id, "u": world["aziza"]},
        )


@pytest.mark.parametrize("case", ["zero_amount", "to_self", "to_non_member"])
def test_settlement_constraints(session: Session, world, case: str) -> None:
    overrides = {
        "zero_amount": {"amount": 0},
        "to_self": {"from_user_id": world["aziza"], "to_user_id": world["aziza"]},
        "to_non_member": {"to_user_id": world["ali"]},
    }[case]

    with pytest.raises(IntegrityError):
        add_settlement(session, world, **overrides)


def test_deleting_expense_cascades_to_shares(session: Session, world) -> None:
    expense_id = add_expense(session, world)
    session.execute(
        text(
            "INSERT INTO expense_shares (expense_id, user_id, share_amount)"
            " VALUES (:e, :a, 150000), (:e, :r, 150000)"
        ),
        {"e": expense_id, "a": world["aziza"], "r": world["ramazon"]},
    )

    session.execute(text("DELETE FROM expenses WHERE id = :e"), {"e": expense_id})

    assert count(session, "expense_shares") == 0


def test_deleted_author_sets_created_by_to_null(session: Session, world) -> None:
    expense_id = add_expense(session, world, created_by=world["ali"])

    session.execute(text("DELETE FROM users WHERE id = :u"), {"u": world["ali"]})

    created_by = session.execute(
        text("SELECT created_by FROM expenses WHERE id = :e"), {"e": expense_id}
    ).scalar_one()
    assert created_by is None


def test_group_with_expenses_cannot_be_hard_deleted(session: Session, world) -> None:
    add_expense(session, world)

    with pytest.raises(IntegrityError):
        session.execute(text("DELETE FROM groups WHERE id = :g"), {"g": world["group"]})


@pytest.mark.parametrize("record", ["expense", "settlement"])
def test_member_with_history_cannot_be_removed(
    session: Session, world, record: str
) -> None:
    if record == "expense":
        add_expense(session, world, paid_by=world["ramazon"])
    else:
        add_settlement(session, world)
    users = SqlAlchemyUserRepository(session)
    service = GroupService(SqlAlchemyGroupRepository(session), users, lambda: NOW)
    owner = users.get_by_id(world["aziza"])

    with pytest.raises(MemberHasHistoryError):
        service.remove_member(owner, world["group"], world["ramazon"])

    # The failed delete was rolled back to its savepoint; the member is still there.
    assert SqlAlchemyGroupRepository(session).is_member(
        world["group"], world["ramazon"]
    )

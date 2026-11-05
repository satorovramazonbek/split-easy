"""Tests for domain models in app.domain.models."""

from datetime import date

import pytest

from app.domain.exceptions import InvalidAmountError, InvalidSplitError
from app.domain.models import (
    Category,
    Expense,
    ExpenseShare,
    Group,
    Settlement,
    SplitType,
)


def make_expense(**overrides: object) -> Expense:
    data: dict[str, object] = {
        "id": 1,
        "group_id": 1,
        "description": "Kechki ovqat",
        "amount": 300,
        "paid_by": 1,
        "split_type": SplitType.EQUAL,
        "category": Category.FOOD,
        "expense_date": date(2026, 11, 5),
        "created_by": 1,
        "shares": (
            ExpenseShare(user_id=1, share_amount=100),
            ExpenseShare(user_id=2, share_amount=100),
            ExpenseShare(user_id=3, share_amount=100),
        ),
    }
    data.update(overrides)
    return Expense(**data)  # type: ignore[arg-type]


def test_expense_is_created_when_shares_sum_matches_amount() -> None:
    # Act
    expense = make_expense()

    # Assert
    assert expense.amount == 300
    assert expense.participant_ids == [1, 2, 3]


def test_expense_raises_error_when_shares_sum_differs_from_amount() -> None:
    shares = (
        ExpenseShare(user_id=1, share_amount=100),
        ExpenseShare(user_id=2, share_amount=50),
    )
    with pytest.raises(InvalidSplitError):
        make_expense(shares=shares)


@pytest.mark.parametrize("amount", [0, -300])
def test_expense_raises_error_when_amount_is_not_positive(amount: int) -> None:
    with pytest.raises(InvalidAmountError):
        make_expense(amount=amount, shares=())


def test_expense_raises_error_when_participant_is_duplicated() -> None:
    shares = (
        ExpenseShare(user_id=1, share_amount=150),
        ExpenseShare(user_id=1, share_amount=150),
    )
    with pytest.raises(InvalidSplitError):
        make_expense(shares=shares)


def test_expense_share_raises_error_when_amount_is_negative() -> None:
    with pytest.raises(InvalidAmountError):
        ExpenseShare(user_id=1, share_amount=-1)


def test_settlement_raises_error_when_payer_and_receiver_are_same() -> None:
    with pytest.raises(InvalidSplitError):
        Settlement(id=1, group_id=1, from_user_id=1, to_user_id=1, amount=100)


def test_settlement_raises_error_when_amount_is_not_positive() -> None:
    with pytest.raises(InvalidAmountError):
        Settlement(id=1, group_id=1, from_user_id=1, to_user_id=2, amount=0)


def test_group_defaults_to_not_deleted() -> None:
    group = Group(id=1, name="Sayohat", currency="UZS", owner_id=1)

    assert group.is_deleted is False


def test_split_type_can_be_created_from_string() -> None:
    assert SplitType("percentage") is SplitType.PERCENTAGE

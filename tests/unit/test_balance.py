"""Tests for balance calculation in app.domain.balance."""

import pytest

from app.domain.balance import calculate_balances
from app.domain.models import Expense, ExpenseShare, Settlement, SplitType
from app.domain.split_strategies import Participant
from app.domain.split_strategy_factory import SplitStrategyFactory


def make_expense(
    amount: int,
    paid_by: int,
    participants: list[Participant],
    split_type: SplitType = SplitType.EQUAL,
) -> Expense:
    shares = SplitStrategyFactory.create(split_type).split(amount, participants)
    return Expense(
        id=None,
        group_id=1,
        description="test",
        amount=amount,
        paid_by=paid_by,
        split_type=split_type,
        shares=tuple(shares),
    )


def test_two_person_expense_gives_correct_balances() -> None:
    # Arrange: user 1 pays 100 for both
    expense = make_expense(
        100, paid_by=1, participants=[Participant(1), Participant(2)]
    )

    # Act
    balances = calculate_balances([expense])

    # Assert
    assert balances == {1: 50, 2: -50}


def test_trip_example_from_specification() -> None:
    # Ali=1, Vali=2, Sardor=3, Dilshod=4
    everyone = [Participant(1), Participant(2), Participant(3), Participant(4)]
    expenses = [
        make_expense(400_000, paid_by=1, participants=everyone),
        make_expense(100_000, paid_by=2, participants=everyone),
        make_expense(300_000, paid_by=3, participants=everyone),
    ]

    balances = calculate_balances(expenses)

    assert balances == {1: 200_000, 2: -100_000, 3: 100_000, 4: -200_000}


def test_settlement_changes_balances() -> None:
    expense = make_expense(
        100, paid_by=1, participants=[Participant(1), Participant(2)]
    )
    settlement = Settlement(
        id=None, group_id=1, from_user_id=2, to_user_id=1, amount=50
    )

    balances = calculate_balances([expense], [settlement])

    assert balances == {1: 0, 2: 0}


def test_partial_settlement_reduces_debt() -> None:
    expense = make_expense(
        100, paid_by=1, participants=[Participant(1), Participant(2)]
    )
    settlement = Settlement(
        id=None, group_id=1, from_user_id=2, to_user_id=1, amount=20
    )

    balances = calculate_balances([expense], [settlement])

    assert balances == {1: 30, 2: -30}


def test_members_without_activity_have_zero_balance() -> None:
    expense = make_expense(
        100, paid_by=1, participants=[Participant(1), Participant(2)]
    )

    balances = calculate_balances([expense], member_ids=[1, 2, 3])

    assert balances[3] == 0


def test_no_expenses_gives_empty_balances() -> None:
    assert calculate_balances([]) == {}


def test_payer_who_is_not_participant_gets_full_amount() -> None:
    expense = Expense(
        id=None,
        group_id=1,
        description="gift",
        amount=90,
        paid_by=1,
        split_type=SplitType.EXACT,
        shares=(
            ExpenseShare(user_id=2, share_amount=45),
            ExpenseShare(user_id=3, share_amount=45),
        ),
    )

    balances = calculate_balances([expense])

    assert balances == {1: 90, 2: -45, 3: -45}


@pytest.mark.parametrize(
    ("split_type", "participants"),
    [
        (SplitType.EQUAL, [Participant(1), Participant(2), Participant(3)]),
        (SplitType.EXACT, [Participant(1, 50), Participant(2, 30), Participant(3, 21)]),
        (
            SplitType.PERCENTAGE,
            [Participant(1, 33), Participant(2, 33), Participant(3, 34)],
        ),
        (SplitType.SHARES, [Participant(1, 3), Participant(2, 2), Participant(3, 1)]),
    ],
)
def test_sum_of_balances_is_always_zero(
    split_type: SplitType, participants: list[Participant]
) -> None:
    expenses = [
        make_expense(101, paid_by=1, participants=participants, split_type=split_type),
        make_expense(101, paid_by=2, participants=participants, split_type=split_type),
    ]
    settlements = [
        Settlement(id=None, group_id=1, from_user_id=3, to_user_id=1, amount=17)
    ]

    balances = calculate_balances(expenses, settlements)

    assert sum(balances.values()) == 0

from decimal import Decimal

import pytest

from app.domain.exceptions import InvalidSplitError, UnknownSplitTypeError
from app.domain.settlement import Transfer
from app.domain.split_strategies import Participant
from app.services.quick_split_service import ExpenseInput, QuickSplitService

MEMBERS = [1, 2, 3, 4]


def equal(amount: int, paid_by: int, members=MEMBERS) -> ExpenseInput:
    return ExpenseInput(
        description="",
        amount=amount,
        paid_by=paid_by,
        split_type="equal",
        participants=[Participant(user_id) for user_id in members],
    )


@pytest.fixture
def service() -> QuickSplitService:
    return QuickSplitService()


def test_readme_trip_example(service: QuickSplitService) -> None:
    result = service.calculate(
        MEMBERS, [equal(400_000, 1), equal(100_000, 2), equal(300_000, 3)]
    )

    assert result.total == 800_000
    assert result.paid == {1: 400_000, 2: 100_000, 3: 300_000, 4: 0}
    assert result.owed == {1: 200_000, 2: 200_000, 3: 200_000, 4: 200_000}
    assert result.balances == {1: 200_000, 2: -100_000, 3: 100_000, 4: -200_000}
    assert result.transfers == [Transfer(4, 1, 200_000), Transfer(2, 3, 100_000)]


def test_empty_description_gets_default(service: QuickSplitService) -> None:
    expense = service.build_expense(MEMBERS, equal(100, 1))

    assert expense.description == "Xarajat"


def test_exact_split_accepts_whole_decimals(service: QuickSplitService) -> None:
    data = ExpenseInput(
        description="Ovqat",
        amount=10_000,
        paid_by=1,
        split_type="exact",
        participants=[Participant(1, Decimal(7000)), Participant(2, Decimal(3000))],
    )

    expense = service.build_expense(MEMBERS, data)

    assert [share.share_amount for share in expense.shares] == [7000, 3000]


def test_exact_split_rejects_fractional_amounts(service: QuickSplitService) -> None:
    data = ExpenseInput(
        description="",
        amount=10,
        paid_by=1,
        split_type="exact",
        participants=[Participant(1, Decimal("5.5")), Participant(2, Decimal("4.5"))],
    )

    with pytest.raises(InvalidSplitError):
        service.build_expense(MEMBERS, data)


def test_percentage_split(service: QuickSplitService) -> None:
    data = ExpenseInput(
        description="",
        amount=1000,
        paid_by=2,
        split_type="percentage",
        participants=[Participant(1, Decimal(25)), Participant(2, Decimal(75))],
    )

    expense = service.build_expense(MEMBERS, data)

    assert [share.share_amount for share in expense.shares] == [250, 750]


def test_payer_must_be_member(service: QuickSplitService) -> None:
    with pytest.raises(InvalidSplitError):
        service.build_expense(MEMBERS, equal(100, 99))


def test_participants_must_be_members(service: QuickSplitService) -> None:
    with pytest.raises(InvalidSplitError):
        service.build_expense(MEMBERS, equal(100, 1, members=[1, 99]))


def test_duplicate_member_ids_rejected(service: QuickSplitService) -> None:
    with pytest.raises(InvalidSplitError):
        service.calculate([1, 1], [])


def test_unknown_split_type(service: QuickSplitService) -> None:
    data = ExpenseInput("", 100, 1, "magic", [Participant(1)])

    with pytest.raises(UnknownSplitTypeError):
        service.build_expense(MEMBERS, data)


def test_no_expenses_gives_zero_balances(service: QuickSplitService) -> None:
    result = service.calculate([1, 2], [])

    assert result.balances == {1: 0, 2: 0}
    assert result.transfers == []

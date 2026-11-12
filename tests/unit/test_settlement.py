import pytest

from app.domain.exceptions import InvalidSplitError
from app.domain.settlement import Transfer, simplify_debts


def test_readme_example_needs_two_transfers() -> None:
    # Ali=1, Vali=2, Sardor=3, Dilshod=4 (see README)
    balances = {1: 200_000, 2: -100_000, 3: 100_000, 4: -200_000}

    assert simplify_debts(balances) == [
        Transfer(4, 1, 200_000),
        Transfer(2, 3, 100_000),
    ]


def test_all_zero_balances_need_no_transfers() -> None:
    assert simplify_debts({1: 0, 2: 0}) == []


def test_one_creditor_many_debtors() -> None:
    transfers = simplify_debts({1: 300, 2: -100, 3: -100, 4: -100})

    assert transfers == [Transfer(2, 1, 100), Transfer(3, 1, 100), Transfer(4, 1, 100)]


def test_transfers_settle_every_balance() -> None:
    balances = {1: 70, 2: -45, 3: 25, 4: -30, 5: -20}
    remaining = dict(balances)

    transfers = simplify_debts(balances)

    for transfer in transfers:
        remaining[transfer.from_user_id] += transfer.amount
        remaining[transfer.to_user_id] -= transfer.amount
        assert transfer.amount > 0
    assert all(value == 0 for value in remaining.values())
    assert len(transfers) <= len(balances) - 1


def test_unbalanced_input_is_rejected() -> None:
    with pytest.raises(InvalidSplitError):
        simplify_debts({1: 10, 2: -5})


@pytest.mark.parametrize(
    "balances",
    [
        {1: 300, 2: -100, 3: -100, 4: -100},
        {1: 500, 2: 250, 3: -400, 4: -200, 5: -150},
        {1: 1, 2: -1},
        {1: 70, 2: 30, 3: -10, 4: -20, 5: -30, 6: -40},
    ],
)
def test_plan_has_at_most_n_minus_1_transfers(balances: dict[int, int]) -> None:
    """Spec 12.2: N people with a non-zero balance need at most N - 1 transfers."""
    non_zero = [b for b in balances.values() if b != 0]

    transfers = simplify_debts(balances)

    assert len(transfers) <= len(non_zero) - 1

"""Tests for split strategies in app.domain.split_strategies."""

from decimal import Decimal

import pytest

from app.domain.exceptions import InvalidAmountError, InvalidSplitError
from app.domain.split_strategies import (
    EqualSplitStrategy,
    ExactSplitStrategy,
    Participant,
    PercentageSplitStrategy,
)


def amounts(shares: list) -> dict[int, int]:
    return {share.user_id: share.share_amount for share in shares}


# --- Equal ---------------------------------------------------------------


def test_equal_split_divides_amount_evenly() -> None:
    # Arrange
    strategy = EqualSplitStrategy()
    participants = [Participant(1), Participant(2), Participant(3)]

    # Act
    shares = strategy.split(300, participants)

    # Assert
    assert amounts(shares) == {1: 100, 2: 100, 3: 100}


def test_equal_split_gives_remainder_to_first_participants() -> None:
    shares = EqualSplitStrategy().split(
        100, [Participant(1), Participant(2), Participant(3)]
    )

    assert amounts(shares) == {1: 34, 2: 33, 3: 33}
    assert sum(amounts(shares).values()) == 100


def test_equal_split_raises_error_when_participants_are_empty() -> None:
    with pytest.raises(InvalidSplitError):
        EqualSplitStrategy().split(100, [])


@pytest.mark.parametrize("total", [0, -100])
def test_equal_split_raises_error_when_amount_is_not_positive(total: int) -> None:
    with pytest.raises(InvalidAmountError):
        EqualSplitStrategy().split(total, [Participant(1)])


def test_equal_split_raises_error_when_participant_is_duplicated() -> None:
    with pytest.raises(InvalidSplitError):
        EqualSplitStrategy().split(100, [Participant(1), Participant(1)])


def test_participant_value_can_be_decimal() -> None:
    participant = Participant(user_id=1, value=Decimal("12.5"))

    assert participant.value == Decimal("12.5")


# --- Exact ---------------------------------------------------------------


def test_exact_split_uses_given_amounts() -> None:
    participants = [Participant(1, 50), Participant(2, 40), Participant(3, 30)]

    shares = ExactSplitStrategy().split(120, participants)

    assert amounts(shares) == {1: 50, 2: 40, 3: 30}


@pytest.mark.parametrize("values", [[50, 40, 20], [50, 40, 40]])
def test_exact_split_raises_error_when_sum_is_not_total(values: list[int]) -> None:
    participants = [Participant(i + 1, v) for i, v in enumerate(values)]

    with pytest.raises(InvalidSplitError):
        ExactSplitStrategy().split(120, participants)


def test_exact_split_raises_error_when_amount_is_negative() -> None:
    participants = [Participant(1, 130), Participant(2, -10)]

    with pytest.raises(InvalidSplitError):
        ExactSplitStrategy().split(120, participants)


@pytest.mark.parametrize("value", [None, 12.5, Decimal("60")])
def test_exact_split_raises_error_when_value_is_not_integer(value: object) -> None:
    participants = [Participant(1, 60), Participant(2, value)]  # type: ignore[arg-type]

    with pytest.raises(InvalidSplitError):
        ExactSplitStrategy().split(120, participants)


def test_exact_split_allows_zero_share() -> None:
    shares = ExactSplitStrategy().split(100, [Participant(1, 100), Participant(2, 0)])

    assert amounts(shares) == {1: 100, 2: 0}


# --- Percentage ----------------------------------------------------------


def test_percentage_split_divides_by_percentages() -> None:
    participants = [Participant(1, 50), Participant(2, 30), Participant(3, 20)]

    shares = PercentageSplitStrategy().split(300000, participants)

    assert amounts(shares) == {1: 150000, 2: 90000, 3: 60000}


def test_percentage_split_accepts_decimal_percentages_and_keeps_total() -> None:
    participants = [
        Participant(1, Decimal("33.33")),
        Participant(2, Decimal("33.33")),
        Participant(3, Decimal("33.34")),
    ]

    shares = PercentageSplitStrategy().split(100, participants)

    assert sum(amounts(shares).values()) == 100


@pytest.mark.parametrize(
    "values",
    [[50, 30, 10], [50, 30, 30], [Decimal("99.99"), 0]],
)
def test_percentage_split_raises_error_when_sum_is_not_100(values: list) -> None:
    participants = [Participant(i + 1, v) for i, v in enumerate(values)]

    with pytest.raises(InvalidSplitError):
        PercentageSplitStrategy().split(1000, participants)


@pytest.mark.parametrize("value", [0, -10, None, 50.0, True])
def test_percentage_split_raises_error_when_value_is_invalid(value: object) -> None:
    participants = [Participant(1, 50), Participant(2, value)]  # type: ignore[arg-type]

    with pytest.raises(InvalidSplitError):
        PercentageSplitStrategy().split(1000, participants)

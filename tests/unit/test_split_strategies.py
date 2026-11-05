"""Tests for split strategies in app.domain.split_strategies."""

from decimal import Decimal

import pytest

from app.domain.exceptions import InvalidAmountError, InvalidSplitError
from app.domain.split_strategies import EqualSplitStrategy, Participant


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

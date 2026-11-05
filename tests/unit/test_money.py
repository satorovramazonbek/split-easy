"""Tests for money helpers in app.domain.money."""

from decimal import Decimal

import pytest

from app.domain.exceptions import InvalidAmountError
from app.domain.money import allocate_proportionally, split_evenly, validate_amount


@pytest.mark.parametrize(
    ("total", "parts", "expected"),
    [
        (300, 3, [100, 100, 100]),
        (100, 3, [34, 33, 33]),
        (10, 4, [3, 3, 2, 2]),
        (1, 3, [1, 0, 0]),
    ],
)
def test_split_evenly_distributes_remainder_to_first_participants(
    total: int, parts: int, expected: list[int]
) -> None:
    # Act
    result = split_evenly(total, parts)

    # Assert
    assert result == expected
    assert sum(result) == total


def test_split_evenly_raises_error_when_parts_is_not_positive() -> None:
    with pytest.raises(ValueError):
        split_evenly(100, 0)


@pytest.mark.parametrize(
    ("total", "weights", "expected"),
    [
        (300, [1, 1, 1], [100, 100, 100]),
        (100, [1, 1, 1], [34, 33, 33]),
        (120, [2, 1, 1], [60, 30, 30]),
        (100, [Decimal("50"), Decimal("30"), Decimal("20")], [50, 30, 20]),
        (100, [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")], [34, 33, 33]),
    ],
)
def test_allocate_proportionally_keeps_exact_total(
    total: int, weights: list[int | Decimal], expected: list[int]
) -> None:
    # Act
    result = allocate_proportionally(total, weights)

    # Assert
    assert result == expected
    assert sum(result) == total


def test_allocate_proportionally_raises_error_when_weights_sum_is_zero() -> None:
    with pytest.raises(ValueError):
        allocate_proportionally(100, [0, 0])


@pytest.mark.parametrize("amount", [0, -1, -100])
def test_validate_amount_rejects_non_positive_values(amount: int) -> None:
    with pytest.raises(InvalidAmountError):
        validate_amount(amount)


@pytest.mark.parametrize("amount", [1.5, "100", True, Decimal("10")])
def test_validate_amount_rejects_non_integer_types(amount: object) -> None:
    with pytest.raises(InvalidAmountError):
        validate_amount(amount)


def test_validate_amount_returns_value_when_valid() -> None:
    assert validate_amount(500) == 500

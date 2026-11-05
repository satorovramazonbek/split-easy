"""Helpers for working with money.

All amounts are stored as ``int`` in the smallest currency unit (e.g. so'm or
tiyin). ``float`` is never used, so there are no rounding surprises such as
``0.1 + 0.2 != 0.3``.

Rounding rule: when an amount cannot be divided exactly, the leftover units are
given one by one to participants in order, so the parts always add up to the
original total.
"""

from collections.abc import Sequence
from decimal import Decimal
from fractions import Fraction

from app.domain.exceptions import InvalidAmountError

Weight = int | Decimal


def validate_amount(amount: object) -> int:
    """Return ``amount`` if it is a positive ``int``, otherwise raise.

    ``bool`` is rejected even though it is a subclass of ``int``.
    """
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise InvalidAmountError(
            f"Amount must be an integer, got {type(amount).__name__}"
        )
    if amount <= 0:
        raise InvalidAmountError(f"Amount must be positive, got {amount}")
    return amount


def _distribute_remainder(parts: list[int], remainder: int) -> list[int]:
    """Add one unit to the first ``remainder`` parts."""
    for index in range(remainder):
        parts[index] += 1
    return parts


def split_evenly(total: int, parts: int) -> list[int]:
    """Split ``total`` into ``parts`` integer pieces that differ by at most 1."""
    if parts <= 0:
        raise ValueError("Number of parts must be positive")
    base, remainder = divmod(total, parts)
    return _distribute_remainder([base] * parts, remainder)


def allocate_proportionally(total: int, weights: Sequence[Weight]) -> list[int]:
    """Split ``total`` proportionally to ``weights``.

    Calculations use :class:`fractions.Fraction`, so the result is exact.
    Each part is rounded down first, then the remainder is distributed in order.
    """
    exact_weights = [Fraction(weight) for weight in weights]
    weights_sum = sum(exact_weights, Fraction(0))
    if weights_sum <= 0:
        raise ValueError("Sum of weights must be positive")

    parts = [int(total * weight // weights_sum) for weight in exact_weights]
    return _distribute_remainder(parts, total - sum(parts))
